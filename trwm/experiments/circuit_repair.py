from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


TruthAssignment = tuple[int, ...]
TruthOutput = tuple[int, ...]


OP_NAMES = {
    0: "FALSE",
    1: "NOR",
    2: "A_LT_B",
    3: "NOT_A",
    4: "A_GT_B",
    5: "NOT_B",
    6: "XOR",
    7: "NAND",
    8: "AND",
    9: "XNOR",
    10: "B",
    11: "A_IMPLIES_B",
    12: "A",
    13: "B_IMPLIES_A",
    14: "OR",
    15: "TRUE",
}


@dataclass(frozen=True)
class CircuitGate:
    gate_id: str
    op_mask: int
    inputs: tuple[str, str]


@dataclass(frozen=True)
class BooleanNetlist:
    inputs: tuple[str, ...]
    gates: tuple[CircuitGate, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True)
class TruthRow:
    assignment: TruthAssignment
    outputs: TruthOutput


@dataclass(frozen=True)
class CircuitRepairProblem:
    template_netlist: BooleanNetlist
    target_table: tuple[TruthRow, ...]
    mutable_gate_id: str
    allowed_ops: tuple[int, ...] = tuple(range(16))


@dataclass(frozen=True)
class CircuitRepairState:
    problem: CircuitRepairProblem
    solved: bool = False
    netlist: BooleanNetlist | None = None


@dataclass(frozen=True)
class CircuitEpisodeResult:
    calls: int
    success: bool
    audit_ok: bool
    replay_rollback_ok: bool


@dataclass(frozen=True)
class CircuitRepairReport:
    episodes: int
    op_count: int
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    repair_success_rate: float
    ledger_audit_rate: float
    replay_rollback_rate: float
    invalid_commit_count: int
    learned_residual_kinds: Mapping[str, int]


class BooleanCircuitAdapter:
    verifier_id = "boolean_circuit_truth_table_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        problem = normalize_problem(payload["problem"])
        netlist = normalize_netlist(payload["netlist"])
        metadata = {
            "cost": payload.get("cost", 1),
            "gate_count": len(netlist.gates),
            "truth_rows": len(problem.target_table),
        }
        shape_error = _candidate_shape_error(problem, netlist)
        if shape_error:
            return self._reject("schema_error", {"message": shape_error}, metadata)

        for index, row in enumerate(problem.target_table):
            actual = evaluate_netlist(netlist, row.assignment)
            if actual != row.outputs:
                repair = diagnose_mutable_gate(problem, netlist)
                return self._reject(
                    "truth_table_mismatch",
                    {
                        "row": index,
                        "assignment": row.assignment,
                        "expected": row.outputs,
                        "actual": actual,
                        "repair": repair,
                    },
                    metadata,
                )
        return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)

    def apply_commit(self, state: CircuitRepairState, candidate: TypedCandidate) -> CircuitRepairState:
        current = normalize_state(state)
        problem = normalize_problem(candidate.payload["problem"])
        if current.problem != problem:
            raise ValueError("candidate problem does not match current circuit state")
        netlist = normalize_netlist(candidate.payload["netlist"])
        return CircuitRepairState(problem=problem, solved=True, netlist=netlist)

    def replay(self, state: CircuitRepairState, receipt: Receipt) -> CircuitRepairState:
        current = normalize_state(state)
        payload = receipt.replay_bundle["candidate_payload"]
        problem = normalize_problem(payload["problem"])
        if current.problem != problem:
            raise ValueError("receipt problem does not match replay circuit state")
        netlist = normalize_netlist(payload["netlist"])
        return CircuitRepairState(problem=problem, solved=True, netlist=netlist)

    def rollback(self, state: CircuitRepairState, receipt: Receipt) -> CircuitRepairState:
        return normalize_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


class CircuitResidualRepairer:
    def __init__(self) -> None:
        self.rejected_residuals: dict[str, int] = {}
        self.accepted_ops: dict[str, int] = {}

    def update(self, receipt: Receipt) -> None:
        if receipt.hard_result.accepted:
            payload = receipt.replay_bundle.get("candidate_payload", {}) if isinstance(receipt.replay_bundle, Mapping) else {}
            op_mask = payload.get("op_mask", "unknown") if isinstance(payload, Mapping) else "unknown"
            key = str(op_mask)
            self.accepted_ops[key] = self.accepted_ops.get(key, 0) + 1
            return
        residual = receipt.hard_result.residual
        if receipt.hard_result.rejected and isinstance(residual, Mapping):
            kind = str(residual.get("kind", "unknown"))
            self.rejected_residuals[kind] = self.rejected_residuals.get(kind, 0) + 1

    def propose(self, candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate | None:
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        op_mask = repair.get("op_mask")
        if not isinstance(op_mask, int):
            return None
        problem = normalize_problem(candidate.payload["problem"])
        current_op = int(candidate.payload.get("op_mask", -1))
        if op_mask == current_op:
            return None
        return make_circuit_candidate(
            problem,
            op_mask,
            context=str(candidate.payload.get("context", "circuit-repair")),
            cost=int(candidate.payload.get("cost", 1)) + 1,
        )


def eval_op_mask(op_mask: int, left: int, right: int) -> int:
    if not 0 <= int(op_mask) <= 15:
        raise ValueError("op_mask must be in [0, 15]")
    if left not in (0, 1) or right not in (0, 1):
        raise ValueError("Boolean inputs must be 0 or 1")
    index = (int(left) << 1) | int(right)
    return (int(op_mask) >> index) & 1


def normalize_gate(gate: CircuitGate | Mapping[str, Any]) -> CircuitGate:
    if isinstance(gate, CircuitGate):
        gate_id = gate.gate_id
        op_mask = gate.op_mask
        inputs = gate.inputs
    else:
        gate_id = gate.get("gate_id", gate.get("gateId"))
        op_mask = gate.get("op_mask", gate.get("opMask"))
        inputs = tuple(gate["inputs"])
    if not isinstance(gate_id, str) or not gate_id:
        raise ValueError("gate_id must be a non-empty string")
    op_mask = int(op_mask)
    if not 0 <= op_mask <= 15:
        raise ValueError("op_mask must be in [0, 15]")
    input_tuple = tuple(str(value) for value in inputs)
    if len(input_tuple) != 2:
        raise ValueError("this G1 canary supports binary gates only")
    return CircuitGate(gate_id=gate_id, op_mask=op_mask, inputs=input_tuple)


def normalize_netlist(netlist: BooleanNetlist | Mapping[str, Any]) -> BooleanNetlist:
    if isinstance(netlist, BooleanNetlist):
        inputs = netlist.inputs
        gates = netlist.gates
        outputs = netlist.outputs
    else:
        inputs = tuple(netlist["inputs"])
        gates = tuple(netlist["gates"])
        outputs = tuple(netlist["outputs"])
    normalized_inputs = tuple(str(value) for value in inputs)
    if not normalized_inputs or len(set(normalized_inputs)) != len(normalized_inputs):
        raise ValueError("netlist inputs must be non-empty and unique")
    normalized_gates = tuple(normalize_gate(gate) for gate in gates)
    gate_ids = [gate.gate_id for gate in normalized_gates]
    if len(set(gate_ids)) != len(gate_ids):
        raise ValueError("gate ids must be unique")
    known = set(normalized_inputs)
    for gate in normalized_gates:
        for wire in gate.inputs:
            if wire not in known:
                raise ValueError(f"unknown gate input wire: {wire}")
        known.add(gate.gate_id)
    normalized_outputs = tuple(str(value) for value in outputs)
    if not normalized_outputs:
        raise ValueError("netlist must expose at least one output")
    for output in normalized_outputs:
        if output not in known:
            raise ValueError(f"unknown output wire: {output}")
    return BooleanNetlist(inputs=normalized_inputs, gates=normalized_gates, outputs=normalized_outputs)


def normalize_truth_row(row: TruthRow | Mapping[str, Any]) -> TruthRow:
    if isinstance(row, TruthRow):
        assignment = row.assignment
        outputs = row.outputs
    else:
        assignment = tuple(row["assignment"])
        outputs = tuple(row["outputs"])
    return TruthRow(
        assignment=tuple(_bit(value) for value in assignment),
        outputs=tuple(_bit(value) for value in outputs),
    )


def normalize_problem(problem: CircuitRepairProblem | Mapping[str, Any]) -> CircuitRepairProblem:
    if isinstance(problem, CircuitRepairProblem):
        template = problem.template_netlist
        target_table = problem.target_table
        mutable_gate_id = problem.mutable_gate_id
        allowed_ops = problem.allowed_ops
    else:
        template = problem.get("template_netlist", problem.get("templateNetlist"))
        target_table = tuple(problem.get("target_table", problem.get("targetTable")))
        mutable_gate_id = problem.get("mutable_gate_id", problem.get("mutableGateId"))
        allowed_ops = tuple(problem.get("allowed_ops", problem.get("allowedOps", tuple(range(16)))))
    netlist = normalize_netlist(template)
    mutable_gate_id = str(mutable_gate_id)
    if mutable_gate_id not in {gate.gate_id for gate in netlist.gates}:
        raise ValueError("mutable_gate_id must identify a template gate")
    rows = tuple(normalize_truth_row(row) for row in target_table)
    expected_assignments = tuple(_assignments(len(netlist.inputs)))
    if tuple(row.assignment for row in rows) != expected_assignments:
        raise ValueError("target_table must contain complete assignments in canonical order")
    if any(len(row.outputs) != len(netlist.outputs) for row in rows):
        raise ValueError("target row output arity must match netlist outputs")
    ops = tuple(int(op) for op in allowed_ops)
    if not ops or any(op < 0 or op > 15 for op in ops) or len(set(ops)) != len(ops):
        raise ValueError("allowed_ops must be unique op masks in [0, 15]")
    return CircuitRepairProblem(template_netlist=netlist, target_table=rows, mutable_gate_id=mutable_gate_id, allowed_ops=ops)


def normalize_state(state: CircuitRepairState | Mapping[str, Any]) -> CircuitRepairState:
    if isinstance(state, CircuitRepairState):
        return CircuitRepairState(
            problem=normalize_problem(state.problem),
            solved=bool(state.solved),
            netlist=normalize_netlist(state.netlist) if state.netlist is not None else None,
        )
    return CircuitRepairState(
        problem=normalize_problem(state["problem"]),
        solved=bool(state.get("solved", False)),
        netlist=normalize_netlist(state["netlist"]) if state.get("netlist") is not None else None,
    )


def evaluate_netlist(netlist_input: BooleanNetlist, assignment: Iterable[Any]) -> TruthOutput:
    netlist = normalize_netlist(netlist_input)
    values = tuple(_bit(value) for value in assignment)
    if len(values) != len(netlist.inputs):
        raise ValueError("assignment length must match netlist input count")
    wires: dict[str, int] = dict(zip(netlist.inputs, values))
    for gate in netlist.gates:
        left, right = (wires[wire] for wire in gate.inputs)
        wires[gate.gate_id] = eval_op_mask(gate.op_mask, left, right)
    return tuple(wires[output] for output in netlist.outputs)


def truth_table(netlist_input: BooleanNetlist) -> tuple[TruthRow, ...]:
    netlist = normalize_netlist(netlist_input)
    return tuple(TruthRow(assignment, evaluate_netlist(netlist, assignment)) for assignment in _assignments(len(netlist.inputs)))


def replace_gate_op(netlist_input: BooleanNetlist, gate_id: str, op_mask: int) -> BooleanNetlist:
    netlist = normalize_netlist(netlist_input)
    changed = False
    gates: list[CircuitGate] = []
    for gate in netlist.gates:
        if gate.gate_id == gate_id:
            gates.append(CircuitGate(gate_id=gate.gate_id, op_mask=int(op_mask), inputs=gate.inputs))
            changed = True
        else:
            gates.append(gate)
    if not changed:
        raise ValueError(f"unknown gate: {gate_id}")
    return BooleanNetlist(inputs=netlist.inputs, gates=tuple(gates), outputs=netlist.outputs)


def diagnose_mutable_gate(problem_input: CircuitRepairProblem, netlist_input: BooleanNetlist) -> dict[str, Any] | None:
    problem = normalize_problem(problem_input)
    matches: list[int] = []
    for op_mask in problem.allowed_ops:
        repaired = replace_gate_op(netlist_input, problem.mutable_gate_id, op_mask)
        if all(evaluate_netlist(repaired, row.assignment) == row.outputs for row in problem.target_table):
            matches.append(op_mask)
    if len(matches) != 1:
        return None
    op_mask = matches[0]
    return {"gate_id": problem.mutable_gate_id, "op_mask": op_mask, "op_name": OP_NAMES[op_mask]}


def make_circuit_candidate(problem: CircuitRepairProblem, op_mask: int, context: str = "circuit", cost: int = 1) -> TypedCandidate:
    problem = normalize_problem(problem)
    op_mask = int(op_mask)
    netlist = replace_gate_op(problem.template_netlist, problem.mutable_gate_id, op_mask)
    return TypedCandidate(
        payload={
            "context": context,
            "problem": problem,
            "netlist": netlist,
            "mutable_gate_id": problem.mutable_gate_id,
            "op_mask": op_mask,
            "op_name": OP_NAMES[op_mask],
            "cost": cost,
        },
        type_name="circuit.boolean_netlist",
        schema_version="circuit.boolean_netlist.v1",
        hashes={
            "problem": stable_hash(problem),
            "netlist": stable_hash(netlist),
            "op": stable_hash({"gate_id": problem.mutable_gate_id, "op_mask": op_mask}),
        },
    )


def make_circuit_repair_problem(target_op_mask: int = 6) -> CircuitRepairProblem:
    if not 0 <= int(target_op_mask) <= 15:
        raise ValueError("target_op_mask must be in [0, 15]")
    template = BooleanNetlist(
        inputs=("x0", "x1", "x2"),
        gates=(
            CircuitGate("g0", 6, ("x0", "x1")),
            CircuitGate("g1", 0, ("g0", "x2")),
        ),
        outputs=("g1",),
    )
    target = replace_gate_op(template, "g1", int(target_op_mask))
    return CircuitRepairProblem(template_netlist=template, target_table=truth_table(target), mutable_gate_id="g1")


def run_static_circuit_episode(problem: CircuitRepairProblem, op_order: Iterable[int], ledger: Ledger, episode: int) -> CircuitEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(BooleanCircuitAdapter(), ledger=ledger)
    state = CircuitRepairState(problem=problem)
    calls = 0
    for op_mask in op_order:
        calls += 1
        candidate = make_circuit_candidate(problem, int(op_mask), context="circuit-static", cost=calls)
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"circuit-static-{episode}-{calls}",
                actions=({"gate_id": problem.mutable_gate_id, "op_mask": int(op_mask)},),
                seeds=(episode, calls),
                model_version="circuit.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return _episode_result(calls, True, engine, state)
    return _episode_result(calls, False, engine, state)


def run_repair_circuit_episode(
    problem: CircuitRepairProblem,
    ledger: Ledger,
    repairer: CircuitResidualRepairer,
    episode: int,
    initial_op_mask: int = 0,
) -> CircuitEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(BooleanCircuitAdapter(), ledger=ledger)
    state = CircuitRepairState(problem=problem)
    candidate = make_circuit_candidate(problem, initial_op_mask, context="circuit-repair", cost=1)
    for attempt in range(3):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"circuit-repair-{episode}-{attempt}",
                actions=({"gate_id": problem.mutable_gate_id, "op_mask": candidate.payload["op_mask"]},),
                seeds=(episode, attempt),
                model_version="circuit.residual_repair.v1",
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


def run_circuit_repair_benchmark(seed: int = 47, episodes: int = 45) -> CircuitRepairReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    op_masks = _shuffled_ops(seed)
    static_results: list[CircuitEpisodeResult] = []
    repair_results: list[CircuitEpisodeResult] = []
    static_ledgers: list[Ledger] = []
    repair_ledgers: list[Ledger] = []
    repairer = CircuitResidualRepairer()
    static_order = tuple(range(16))
    for episode in range(episodes):
        target_op = op_masks[episode % len(op_masks)]
        problem = make_circuit_repair_problem(target_op)
        static_ledger = Ledger()
        repair_ledger = Ledger()
        static_ledgers.append(static_ledger)
        repair_ledgers.append(repair_ledger)
        static_results.append(run_static_circuit_episode(problem, static_order, static_ledger, episode))
        repair_results.append(run_repair_circuit_episode(problem, repair_ledger, repairer, episode))
    all_results = (*static_results, *repair_results)
    static_cps = _calls_per_success(static_results)
    repair_cps = _calls_per_success(repair_results)
    return CircuitRepairReport(
        episodes=episodes,
        op_count=16,
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        repair_success_rate=sum(1 for row in repair_results if row.success) / len(repair_results),
        ledger_audit_rate=sum(1 for row in all_results if row.audit_ok) / len(all_results),
        replay_rollback_rate=sum(1 for row in all_results if row.replay_rollback_ok) / len(all_results),
        invalid_commit_count=_invalid_commits((*static_ledgers, *repair_ledgers)),
        learned_residual_kinds=dict(repairer.rejected_residuals),
    )


def _candidate_shape_error(problem: CircuitRepairProblem, netlist: BooleanNetlist) -> str | None:
    template = problem.template_netlist
    if netlist.inputs != template.inputs or netlist.outputs != template.outputs or len(netlist.gates) != len(template.gates):
        return "candidate netlist shape must match template"
    for left, right in zip(template.gates, netlist.gates):
        if left.gate_id != right.gate_id or left.inputs != right.inputs:
            return "candidate gate ids and inputs must match template"
        if left.gate_id != problem.mutable_gate_id and left.op_mask != right.op_mask:
            return "only the mutable gate op may change"
    return None


def _assignments(width: int) -> Iterable[TruthAssignment]:
    for mask in range(2**width):
        yield tuple((mask >> bit) & 1 for bit in range(width))


def _bit(value: Any) -> int:
    if value in (0, False):
        return 0
    if value in (1, True):
        return 1
    raise ValueError(f"Boolean value must be 0/1: {value!r}")


def _episode_result(calls: int, success: bool, engine: TransactionEngine, seed_state: CircuitRepairState) -> CircuitEpisodeResult:
    audit_ok = engine.ledger.audit()
    replay_rollback_ok = False
    if audit_ok:
        try:
            engine.replay_audit(seed_state)
            replay_rollback_ok = engine.rollback_audit(seed_state) == seed_state
        except Exception:
            replay_rollback_ok = False
    return CircuitEpisodeResult(calls=calls, success=success, audit_ok=audit_ok, replay_rollback_ok=replay_rollback_ok)


def _calls_per_success(results: Iterable[CircuitEpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)


def _shuffled_ops(seed: int) -> tuple[int, ...]:
    ops = list(range(1, 16))
    rng = random.Random(seed)
    rng.shuffle(ops)
    return tuple(ops)
