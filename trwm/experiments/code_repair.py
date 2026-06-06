from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


DEFAULT_CODE_OPERATORS = ("left", "+", "-", "*", "max", "min", "right", "absdiff")
INITIAL_CODE_OPERATOR = "left"
BASE_SOURCE = "def combine(x, y):\n    return __op0__(x, y)\n"
DEFAULT_TEST_INPUTS = (
    {"x": 0, "y": 0},
    {"x": 1, "y": 2},
    {"x": 3, "y": 1},
    {"x": -2, "y": 5},
    {"x": 4, "y": -3},
    {"x": -4, "y": -2},
)


@dataclass(frozen=True)
class CodeTestCase:
    inputs: tuple[tuple[str, int], ...]
    expected: int


@dataclass(frozen=True)
class CodePatchProblem:
    file_path: str
    function_name: str
    base_source: str
    source_hash: str
    tests: tuple[CodeTestCase, ...]
    mutable_node_id: str = "op0"
    left_var: str = "x"
    right_var: str = "y"
    allowed_operators: tuple[str, ...] = DEFAULT_CODE_OPERATORS


@dataclass(frozen=True)
class CodePatch:
    node_id: str
    operator: str
    base_hash: str


@dataclass(frozen=True)
class CodeRepairState:
    problem: CodePatchProblem
    solved: bool = False
    operator: str | None = None
    source_after: str | None = None


@dataclass(frozen=True)
class CodeRepairEpisodeResult:
    calls: int
    success: bool
    audit_ok: bool
    replay_rollback_ok: bool


@dataclass(frozen=True)
class CodeRepairReport:
    episodes: int
    candidate_space_size: int
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    repair_success_rate: float
    ledger_audit_rate: float
    replay_rollback_rate: float
    invalid_commit_count: int
    learned_residual_kinds: Mapping[str, int]


class CodePatchAdapter:
    verifier_id = "bounded_unit_test_expression_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        problem = normalize_problem(payload["problem"])
        patch = normalize_patch(payload["patch"])
        source_after = str(payload.get("source_after", payload.get("sourceAfter", "")))
        metadata = {
            "cost": payload.get("cost", 1),
            "test_count": len(problem.tests),
            "operator": patch.operator,
            "source_hash": problem.source_hash,
        }
        shape_error = _candidate_shape_error(problem, patch, source_after)
        if shape_error:
            return self._reject("schema_error", {"message": shape_error}, metadata)

        for idx, test_case in enumerate(problem.tests):
            actual = evaluate_patch(problem, patch.operator, test_case)
            if actual != test_case.expected:
                return self._reject(
                    "test_failure",
                    {
                        "test_index": idx,
                        "inputs": dict(test_case.inputs),
                        "expected": test_case.expected,
                        "actual": actual,
                        "repair": diagnose_operator_repair(problem),
                    },
                    metadata,
                )
        return HardVerifierResult.accept(
            self.verifier_id,
            self.verifier_version,
            metadata={
                **metadata,
                "tests_passed": len(problem.tests),
                "patch_hash": stable_hash({"node_id": patch.node_id, "operator": patch.operator, "base_hash": patch.base_hash}),
            },
        )

    def apply_commit(self, state: CodeRepairState, candidate: TypedCandidate) -> CodeRepairState:
        current = normalize_state(state)
        problem = normalize_problem(candidate.payload["problem"])
        if current.problem != problem:
            raise ValueError("candidate problem does not match current code repair state")
        patch = normalize_patch(candidate.payload["patch"])
        return CodeRepairState(problem=problem, solved=True, operator=patch.operator, source_after=render_source(problem, patch.operator))

    def replay(self, state: CodeRepairState, receipt: Receipt) -> CodeRepairState:
        current = normalize_state(state)
        payload = receipt.replay_bundle["candidate_payload"]
        problem = normalize_problem(payload["problem"])
        if current.problem != problem:
            raise ValueError("receipt problem does not match replay code repair state")
        patch = normalize_patch(payload["patch"])
        return CodeRepairState(problem=problem, solved=True, operator=patch.operator, source_after=render_source(problem, patch.operator))

    def rollback(self, state: CodeRepairState, receipt: Receipt) -> CodeRepairState:
        return normalize_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


class CodeResidualRepairer:
    def __init__(self) -> None:
        self.rejected_residuals: dict[str, int] = {}
        self.accepted_operators: dict[str, int] = {}

    def update(self, receipt: Receipt) -> None:
        if receipt.hard_result.accepted:
            payload = receipt.replay_bundle.get("candidate_payload", {}) if isinstance(receipt.replay_bundle, Mapping) else {}
            patch = payload.get("patch", {}) if isinstance(payload, Mapping) else {}
            operator = str(patch.get("operator", "unknown")) if isinstance(patch, Mapping) else "unknown"
            self.accepted_operators[operator] = self.accepted_operators.get(operator, 0) + 1
            return
        residual = receipt.hard_result.residual
        if receipt.hard_result.rejected and isinstance(residual, Mapping):
            kind = str(residual.get("kind", "unknown"))
            self.rejected_residuals[kind] = self.rejected_residuals.get(kind, 0) + 1

    def propose(self, candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate | None:
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        operator = repair.get("operator")
        if not isinstance(operator, str):
            return None
        patch = normalize_patch(candidate.payload["patch"])
        if operator == patch.operator:
            return None
        return make_code_patch_candidate(
            normalize_problem(candidate.payload["problem"]),
            operator,
            context=str(candidate.payload.get("context", "code-repair")),
            cost=int(candidate.payload.get("cost", 1)) + 1,
        )


def normalize_test_case(test_case: CodeTestCase | Mapping[str, Any]) -> CodeTestCase:
    if isinstance(test_case, CodeTestCase):
        inputs = test_case.inputs
        expected = test_case.expected
    else:
        inputs = test_case["inputs"]
        expected = test_case["expected"]
    if isinstance(expected, bool) or not isinstance(expected, int):
        raise ValueError("expected test output must be an integer")
    if isinstance(inputs, Mapping):
        normalized_inputs = tuple(sorted((str(name), _int_value(value, "test input")) for name, value in inputs.items()))
    else:
        normalized_inputs = tuple(sorted((str(name), _int_value(value, "test input")) for name, value in inputs))
    if len(dict(normalized_inputs)) != len(normalized_inputs):
        raise ValueError("test input names must be unique")
    return CodeTestCase(inputs=normalized_inputs, expected=expected)


def normalize_problem(problem: CodePatchProblem | Mapping[str, Any]) -> CodePatchProblem:
    if isinstance(problem, CodePatchProblem):
        file_path = problem.file_path
        function_name = problem.function_name
        base_source = problem.base_source
        source_hash = problem.source_hash
        tests = problem.tests
        mutable_node_id = problem.mutable_node_id
        left_var = problem.left_var
        right_var = problem.right_var
        allowed_operators = problem.allowed_operators
    else:
        file_path = problem.get("file_path", problem.get("filePath"))
        function_name = problem.get("function_name", problem.get("functionName"))
        base_source = problem.get("base_source", problem.get("baseSource"))
        source_hash = problem.get("source_hash", problem.get("sourceHash"))
        tests = problem.get("tests")
        mutable_node_id = problem.get("mutable_node_id", problem.get("mutableNodeId", "op0"))
        left_var = problem.get("left_var", problem.get("leftVar", "x"))
        right_var = problem.get("right_var", problem.get("rightVar", "y"))
        allowed_operators = problem.get("allowed_operators", problem.get("allowedOperators", DEFAULT_CODE_OPERATORS))
    file_path = str(file_path)
    function_name = str(function_name)
    base_source = str(base_source)
    source_hash = str(source_hash)
    mutable_node_id = str(mutable_node_id)
    left_var = str(left_var)
    right_var = str(right_var)
    if not file_path or "\n" in file_path:
        raise ValueError("file_path must be a non-empty single-line path")
    if not function_name.isidentifier():
        raise ValueError("function_name must be an identifier")
    if not base_source:
        raise ValueError("base_source must be non-empty")
    if not source_hash:
        raise ValueError("source_hash must be non-empty")
    if not mutable_node_id:
        raise ValueError("mutable_node_id must be non-empty")
    if left_var == right_var or not left_var.isidentifier() or not right_var.isidentifier():
        raise ValueError("left_var and right_var must be distinct identifiers")
    normalized_tests = tuple(normalize_test_case(test) for test in tests)
    if not normalized_tests:
        raise ValueError("tests must be non-empty")
    operators = tuple(str(operator) for operator in allowed_operators)
    if not operators or len(set(operators)) != len(operators):
        raise ValueError("allowed_operators must be unique")
    if any(operator not in DEFAULT_CODE_OPERATORS for operator in operators):
        raise ValueError("allowed_operators contains unsupported operator")
    for test in normalized_tests:
        names = dict(test.inputs)
        if left_var not in names or right_var not in names:
            raise ValueError("each test must provide both expression variables")
    return CodePatchProblem(
        file_path=file_path,
        function_name=function_name,
        base_source=base_source,
        source_hash=source_hash,
        tests=normalized_tests,
        mutable_node_id=mutable_node_id,
        left_var=left_var,
        right_var=right_var,
        allowed_operators=operators,
    )


def normalize_patch(patch: CodePatch | Mapping[str, Any]) -> CodePatch:
    if isinstance(patch, CodePatch):
        return CodePatch(node_id=str(patch.node_id), operator=str(patch.operator), base_hash=str(patch.base_hash))
    return CodePatch(
        node_id=str(patch.get("node_id", patch.get("nodeId"))),
        operator=str(patch["operator"]),
        base_hash=str(patch.get("base_hash", patch.get("baseHash"))),
    )


def normalize_state(state: CodeRepairState | Mapping[str, Any]) -> CodeRepairState:
    if isinstance(state, CodeRepairState):
        return CodeRepairState(
            problem=normalize_problem(state.problem),
            solved=bool(state.solved),
            operator=state.operator,
            source_after=state.source_after,
        )
    return CodeRepairState(
        problem=normalize_problem(state["problem"]),
        solved=bool(state.get("solved", False)),
        operator=state.get("operator"),
        source_after=state.get("source_after", state.get("sourceAfter")),
    )


def evaluate_operator(operator: str, left: int, right: int) -> int:
    operator = str(operator)
    if operator == "left":
        return left
    if operator == "right":
        return right
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "max":
        return max(left, right)
    if operator == "min":
        return min(left, right)
    if operator == "absdiff":
        return abs(left - right)
    raise ValueError(f"unsupported operator: {operator}")


def evaluate_patch(problem_input: CodePatchProblem, operator: str, test_case_input: CodeTestCase | Mapping[str, Any]) -> int:
    problem = normalize_problem(problem_input)
    test_case = normalize_test_case(test_case_input)
    values = dict(test_case.inputs)
    return evaluate_operator(operator, values[problem.left_var], values[problem.right_var])


def render_source(problem_input: CodePatchProblem, operator: str) -> str:
    problem = normalize_problem(problem_input)
    left = problem.left_var
    right = problem.right_var
    expressions = {
        "left": left,
        "right": right,
        "+": f"{left} + {right}",
        "-": f"{left} - {right}",
        "*": f"{left} * {right}",
        "max": f"max({left}, {right})",
        "min": f"min({left}, {right})",
        "absdiff": f"abs({left} - {right})",
    }
    if operator not in expressions:
        raise ValueError(f"unsupported operator: {operator}")
    return f"def {problem.function_name}({left}, {right}):\n    return {expressions[operator]}\n"


def diagnose_operator_repair(problem_input: CodePatchProblem) -> dict[str, Any] | None:
    problem = normalize_problem(problem_input)
    matches: list[str] = []
    for operator in problem.allowed_operators:
        if all(evaluate_patch(problem, operator, test_case) == test_case.expected for test_case in problem.tests):
            matches.append(operator)
    if len(matches) != 1:
        return None
    operator = matches[0]
    return {
        "node_id": problem.mutable_node_id,
        "operator": operator,
        "base_hash": problem.source_hash,
        "source_after": render_source(problem, operator),
        "passing_tests": len(problem.tests),
    }


def make_code_patch_candidate(
    problem: CodePatchProblem,
    operator: str,
    context: str = "code-repair",
    cost: int = 1,
) -> TypedCandidate:
    problem = normalize_problem(problem)
    patch = CodePatch(node_id=problem.mutable_node_id, operator=str(operator), base_hash=problem.source_hash)
    source_after = render_source(problem, operator)
    return TypedCandidate(
        payload={
            "context": context,
            "problem": problem,
            "patch": patch,
            "source_after": source_after,
            "cost": cost,
        },
        type_name="code.bounded_expression_patch",
        schema_version="code.bounded_expression_patch.v1",
        hashes={
            "problem": stable_hash(problem),
            "patch": stable_hash(patch),
            "source_after": stable_hash(source_after),
        },
    )


def make_code_repair_problem(target_operator: str = "+") -> CodePatchProblem:
    target_operator = str(target_operator)
    if target_operator not in DEFAULT_CODE_OPERATORS:
        raise ValueError(f"unsupported target operator: {target_operator}")
    source_hash = stable_hash(BASE_SOURCE)
    tests = tuple(
        CodeTestCase(
            inputs=tuple(sorted((name, _int_value(value, "test input")) for name, value in inputs.items())),
            expected=evaluate_operator(target_operator, int(inputs["x"]), int(inputs["y"])),
        )
        for inputs in DEFAULT_TEST_INPUTS
    )
    problem = CodePatchProblem(
        file_path="math_ops.py",
        function_name="combine",
        base_source=BASE_SOURCE,
        source_hash=source_hash,
        tests=tests,
    )
    repair = diagnose_operator_repair(problem)
    if repair is None or repair["operator"] != target_operator:
        raise ValueError("test suite does not uniquely identify target operator")
    return problem


def run_static_code_repair_episode(
    problem: CodePatchProblem,
    operator_order: Iterable[str],
    ledger: Ledger,
    episode: int,
) -> CodeRepairEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(CodePatchAdapter(), ledger=ledger)
    state = CodeRepairState(problem=problem)
    calls = 0
    for operator in operator_order:
        calls += 1
        candidate = make_code_patch_candidate(problem, operator, context="code-static", cost=calls)
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"code-static-{episode}-{calls}",
                actions=({"node_id": problem.mutable_node_id, "operator": operator},),
                seeds=(episode, calls),
                model_version="code.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return _episode_result(calls, True, engine, state)
    return _episode_result(calls, False, engine, state)


def run_repair_code_episode(
    problem: CodePatchProblem,
    ledger: Ledger,
    repairer: CodeResidualRepairer,
    episode: int,
    initial_operator: str = INITIAL_CODE_OPERATOR,
) -> CodeRepairEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(CodePatchAdapter(), ledger=ledger)
    state = CodeRepairState(problem=problem)
    candidate = make_code_patch_candidate(problem, initial_operator, context="code-repair", cost=1)
    for attempt in range(3):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"code-repair-{episode}-{attempt}",
                actions=({"node_id": problem.mutable_node_id, "operator": candidate.payload["patch"].operator},),
                seeds=(episode, attempt),
                model_version="code.residual_repair.v1",
            ),
            candidate,
        )
        repairer.update(outcome.receipt)
        if outcome.committed:
            return _episode_result(attempt + 1, True, engine, state)
        residual = outcome.receipt.hard_result.residual
        if not isinstance(residual, Mapping):
            return _episode_result(attempt + 1, False, engine, state)
        repaired = repairer.propose(candidate, residual)
        if repaired is None:
            return _episode_result(attempt + 1, False, engine, state)
        candidate = repaired
    return _episode_result(3, False, engine, state)


def run_code_repair_benchmark(seed: int = 59, episodes: int = 42) -> CodeRepairReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    targets = [operator for operator in DEFAULT_CODE_OPERATORS if operator != INITIAL_CODE_OPERATOR]
    rng = random.Random(seed)
    rng.shuffle(targets)
    static_results: list[CodeRepairEpisodeResult] = []
    repair_results: list[CodeRepairEpisodeResult] = []
    static_ledgers: list[Ledger] = []
    repair_ledgers: list[Ledger] = []
    repairer = CodeResidualRepairer()
    for episode in range(episodes):
        target_operator = targets[episode % len(targets)]
        problem = make_code_repair_problem(target_operator)
        static_ledger = Ledger()
        repair_ledger = Ledger()
        static_ledgers.append(static_ledger)
        repair_ledgers.append(repair_ledger)
        static_results.append(run_static_code_repair_episode(problem, DEFAULT_CODE_OPERATORS, static_ledger, episode))
        repair_results.append(run_repair_code_episode(problem, repair_ledger, repairer, episode))
    all_results = (*static_results, *repair_results)
    static_cps = _calls_per_success(static_results)
    repair_cps = _calls_per_success(repair_results)
    return CodeRepairReport(
        episodes=episodes,
        candidate_space_size=len(DEFAULT_CODE_OPERATORS),
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        repair_success_rate=sum(1 for row in repair_results if row.success) / len(repair_results),
        ledger_audit_rate=sum(1 for row in all_results if row.audit_ok) / len(all_results),
        replay_rollback_rate=sum(1 for row in all_results if row.replay_rollback_ok) / len(all_results),
        invalid_commit_count=_invalid_commits((*static_ledgers, *repair_ledgers)),
        learned_residual_kinds=dict(repairer.rejected_residuals),
    )


def _candidate_shape_error(problem: CodePatchProblem, patch: CodePatch, source_after: str) -> str | None:
    if problem.source_hash != stable_hash(problem.base_source):
        return "problem source_hash does not match base_source"
    if patch.node_id != problem.mutable_node_id:
        return "patch node_id does not match mutable node"
    if patch.base_hash != problem.source_hash:
        return "patch base_hash does not match problem source_hash"
    if patch.operator not in problem.allowed_operators:
        return "patch operator is not allowed by the problem grammar"
    if source_after != render_source(problem, patch.operator):
        return "source_after must be the canonical rendered patch"
    return None


def _episode_result(calls: int, success: bool, engine: TransactionEngine, seed_state: CodeRepairState) -> CodeRepairEpisodeResult:
    audit_ok = engine.ledger.audit()
    replay_rollback_ok = False
    if audit_ok:
        try:
            engine.replay_audit(seed_state)
            replay_rollback_ok = engine.rollback_audit(seed_state) == seed_state
        except Exception:
            replay_rollback_ok = False
    return CodeRepairEpisodeResult(calls=calls, success=success, audit_ok=audit_ok, replay_rollback_ok=replay_rollback_ok)


def _calls_per_success(results: Iterable[CodeRepairEpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)


def _int_value(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value
