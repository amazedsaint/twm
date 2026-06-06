from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import random
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


Clause = tuple[int, ...]
Assignment = tuple[bool, ...]


@dataclass(frozen=True)
class CnfFormula:
    variable_count: int
    clauses: tuple[Clause, ...]


@dataclass(frozen=True)
class CnfState:
    formula: CnfFormula
    solved: bool = False
    assignment: Assignment | None = None


@dataclass(frozen=True)
class SatEpisodeResult:
    calls: int
    success: bool


@dataclass(frozen=True)
class SatCspReport:
    variable_count: int
    episodes: int
    assignment_space_size: int
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    repair_success_rate: float
    ledger_audit: bool
    invalid_commit_count: int
    learned_residual_kinds: Mapping[str, int]


class CnfSatAdapter:
    verifier_id = "cnf_sat_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        formula = normalize_formula(payload["formula"])
        assignment = normalize_assignment(payload["assignment"], formula.variable_count)
        unsatisfied = unsatisfied_clauses(formula, assignment)
        metadata = {
            "cost": payload.get("cost", 1),
            "clause_count": len(formula.clauses),
            "unsatisfied_count": len(unsatisfied),
        }
        if not unsatisfied:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        first_index = unsatisfied[0]
        first_clause = formula.clauses[first_index]
        literal = first_clause[0]
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={
                "kind": "unsatisfied_clause",
                "first_index": first_index,
                "first_clause": first_clause,
                "unsatisfied_count": len(unsatisfied),
                "unsatisfied_indices": unsatisfied,
                "repair": {"variable": abs(literal), "value": literal > 0},
            },
            metadata=metadata,
        )

    def apply_commit(self, state: CnfState, candidate: TypedCandidate) -> CnfState:
        formula = normalize_formula(candidate.payload["formula"])
        assignment = normalize_assignment(candidate.payload["assignment"], formula.variable_count)
        return CnfState(formula=formula, solved=True, assignment=assignment)

    def replay(self, state: CnfState, receipt: Receipt) -> CnfState:
        payload = receipt.replay_bundle["candidate_payload"]
        formula = normalize_formula(payload["formula"])
        assignment = normalize_assignment(payload["assignment"], formula.variable_count)
        return CnfState(formula=formula, solved=True, assignment=assignment)

    def rollback(self, state: CnfState, receipt: Receipt) -> CnfState:
        pre_state = receipt.rollback_bundle["pre_state"]
        if isinstance(pre_state, CnfState):
            return pre_state
        return CnfState(formula=normalize_formula(pre_state["formula"]), solved=bool(pre_state.get("solved", False)), assignment=pre_state.get("assignment"))


class CnfResidualRepairer:
    """Learns residual kinds and proposes local assignment flips from CNF receipts."""

    def __init__(self) -> None:
        self.rejected_residuals: Counter[str] = Counter()
        self.accepted_assignments: Counter[str] = Counter()
        self.repair_variables: Counter[int] = Counter()

    def update(self, receipt: Receipt) -> None:
        bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
        payload = bundle.get("candidate_payload", {})
        if receipt.hard_result.accepted and isinstance(payload, Mapping):
            self.accepted_assignments[stable_hash(payload.get("assignment", ()))[:12]] += 1
            return
        residual = receipt.hard_result.residual
        if receipt.hard_result.rejected and isinstance(residual, Mapping):
            kind = str(residual.get("kind", "unknown"))
            self.rejected_residuals[kind] += 1
            repair = residual.get("repair")
            if isinstance(repair, Mapping) and isinstance(repair.get("variable"), int):
                self.repair_variables[int(repair["variable"])] += 1

    def propose(self, candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate | None:
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        variable = repair.get("variable")
        value = repair.get("value")
        if not isinstance(variable, int) or not isinstance(value, bool):
            return None
        formula = normalize_formula(candidate.payload["formula"])
        assignment = list(normalize_assignment(candidate.payload["assignment"], formula.variable_count))
        if not 1 <= variable <= formula.variable_count:
            return None
        assignment[variable - 1] = value
        return make_cnf_candidate(formula, tuple(assignment), context=str(candidate.payload.get("context", "cnf-repair")), cost=int(candidate.payload.get("cost", 1)) + 1)


def normalize_formula(formula: CnfFormula | Mapping[str, Any]) -> CnfFormula:
    if isinstance(formula, CnfFormula):
        variable_count = formula.variable_count
        clauses = formula.clauses
    else:
        variable_count = int(formula["variable_count"])
        clauses = tuple(tuple(int(literal) for literal in clause) for clause in formula["clauses"])
    if variable_count <= 0:
        raise ValueError("variable_count must be positive")
    if not clauses:
        raise ValueError("formula must contain at least one clause")
    normalized: list[Clause] = []
    for clause in clauses:
        if not clause:
            raise ValueError("empty clauses are not supported in this G1 canary")
        for literal in clause:
            if literal == 0 or abs(literal) > variable_count:
                raise ValueError(f"literal outside variable range: {literal}")
        normalized.append(tuple(clause))
    return CnfFormula(variable_count=variable_count, clauses=tuple(normalized))


def normalize_assignment(assignment: Iterable[Any], variable_count: int) -> Assignment:
    values = tuple(bool(value) for value in assignment)
    if len(values) != variable_count:
        raise ValueError("assignment length must match variable_count")
    return values


def literal_satisfied(literal: int, assignment: Assignment) -> bool:
    value = assignment[abs(literal) - 1]
    return value if literal > 0 else not value


def clause_satisfied(clause: Clause, assignment: Assignment) -> bool:
    return any(literal_satisfied(literal, assignment) for literal in clause)


def unsatisfied_clauses(formula: CnfFormula, assignment: Assignment) -> tuple[int, ...]:
    return tuple(idx for idx, clause in enumerate(formula.clauses) if not clause_satisfied(clause, assignment))


def make_cnf_candidate(formula: CnfFormula, assignment: Assignment, context: str = "cnf", cost: int = 1) -> TypedCandidate:
    formula = normalize_formula(formula)
    assignment = normalize_assignment(assignment, formula.variable_count)
    return TypedCandidate(
        payload={
            "context": context,
            "formula": formula,
            "assignment": assignment,
            "cost": cost,
            "unsatisfied_count": len(unsatisfied_clauses(formula, assignment)),
        },
        type_name="cnf.assignment",
        schema_version="cnf.assignment.v1",
        hashes={
            "formula": stable_hash(formula),
            "assignment": stable_hash(assignment),
        },
    )


def formula_from_target(target: Assignment) -> CnfFormula:
    clauses: list[Clause] = []
    for idx, value in enumerate(target, start=1):
        clauses.append((idx if value else -idx,))
    for idx in range(1, len(target)):
        left = idx if target[idx - 1] else -idx
        right = idx + 1 if target[idx] else -(idx + 1)
        clauses.append((left, right))
    return CnfFormula(variable_count=len(target), clauses=tuple(clauses))


def assignment_from_mask(mask: int, variable_count: int) -> Assignment:
    return tuple(bool((mask >> idx) & 1) for idx in range(variable_count))


def run_static_sat_episode(formula: CnfFormula, assignment_order: Iterable[Assignment], ledger: Ledger, episode: int) -> SatEpisodeResult:
    engine = TransactionEngine(CnfSatAdapter(), ledger=ledger)
    state = CnfState(formula=formula)
    calls = 0
    for idx, assignment in enumerate(assignment_order):
        calls += 1
        candidate = make_cnf_candidate(formula, assignment, context="cnf-static", cost=calls)
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"cnf-static-{episode}-{idx}",
                actions=({"assignment": assignment, "cost": calls},),
                seeds=(episode, idx),
                model_version="cnf.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return SatEpisodeResult(calls, True)
    return SatEpisodeResult(calls, False)


def run_residual_sat_episode(
    formula: CnfFormula,
    initial_assignment: Assignment,
    ledger: Ledger,
    repairer: CnfResidualRepairer,
    episode: int,
    max_repairs: int | None = None,
) -> SatEpisodeResult:
    max_attempts = (max_repairs if max_repairs is not None else formula.variable_count) + 1
    engine = TransactionEngine(CnfSatAdapter(), ledger=ledger)
    state = CnfState(formula=formula)
    candidate = make_cnf_candidate(formula, initial_assignment, context="cnf-repair", cost=1)
    for attempt in range(max_attempts):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"cnf-repair-{episode}-{attempt}",
                actions=({"assignment": candidate.payload["assignment"], "cost": candidate.payload["cost"]},),
                seeds=(episode, attempt),
                model_version="cnf.residual_repair.v1",
            ),
            candidate,
        )
        repairer.update(outcome.receipt)
        if outcome.committed:
            return SatEpisodeResult(attempt + 1, True)
        residual = outcome.receipt.hard_result.residual
        if not isinstance(residual, Mapping):
            return SatEpisodeResult(attempt + 1, False)
        repaired = repairer.propose(candidate, residual)
        if repaired is None:
            return SatEpisodeResult(attempt + 1, False)
        candidate = repaired
    return SatEpisodeResult(max_attempts, False)


def run_sat_csp_benchmark(seed: int = 23, episodes: int = 48, variable_count: int = 8) -> SatCspReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    if variable_count <= 0 or variable_count > 12:
        raise ValueError("variable_count must be in [1, 12] for this G1 canary")
    rng = random.Random(seed)
    masks = list(range(1, 2**variable_count))
    rng.shuffle(masks)
    targets = [assignment_from_mask(masks[idx % len(masks)], variable_count) for idx in range(episodes)]
    static_order = [assignment_from_mask(mask, variable_count) for mask in range(2**variable_count)]

    static_ledger = Ledger()
    repair_ledger = Ledger()
    repairer = CnfResidualRepairer()
    initial = tuple(False for _ in range(variable_count))
    static_results = []
    repair_results = []
    for idx, target in enumerate(targets):
        formula = formula_from_target(target)
        static_results.append(run_static_sat_episode(formula, static_order, static_ledger, idx))
        repair_results.append(run_residual_sat_episode(formula, initial, repair_ledger, repairer, idx))

    static_cps = _calls_per_success(static_results)
    repair_cps = _calls_per_success(repair_results)
    successes = sum(1 for row in repair_results if row.success)
    return SatCspReport(
        variable_count=variable_count,
        episodes=episodes,
        assignment_space_size=2**variable_count,
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        repair_success_rate=successes / len(repair_results),
        ledger_audit=static_ledger.audit() and repair_ledger.audit(),
        invalid_commit_count=_invalid_commits((static_ledger, repair_ledger)),
        learned_residual_kinds=dict(repairer.rejected_residuals),
    )


def _calls_per_success(results: Iterable[SatEpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
