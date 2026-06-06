from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..branch import BranchRuntime, BudgetedBranchRuntime, VerifierBudget
from ..core import HardVerifierResult, ProposalTrace, Receipt, TransactionEngine, TypedCandidate


CONTEXT = "verifier-budget-route"
BUDGET_LIMIT = 4
EXPENSIVE_SOLUTION = "expensive_solution"
CHEAP_DECOY = "cheap_decoy"
CHEAP_SOLUTION = "cheap_solution"


@dataclass(frozen=True)
class VerifierBudgetState:
    committed_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifierBudgetReport:
    candidate_count: int
    budget: int
    unbudgeted_verifier_calls: int
    unbudgeted_committed_action: str
    verifier_calls: int
    verifier_cost: int
    abstained_count: int
    committed_action: str
    skipped_action: str
    verified_rejected_action: str
    budget_residual_kind: str
    expensive_required_cost: int
    remaining_budget_before_expensive: int
    receipt_decisions: tuple[str, ...]
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int


class VerifierBudgetAdapter:
    verifier_id = "verifier_budget_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = normalize_verifier_budget_payload(candidate.payload)
        metadata = {
            "action": payload["action"],
            "cost": payload["plan_cost"],
            "verifier_cost": payload["verifier_cost"],
            "context": payload["context"],
        }
        if payload["accepted"]:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": "candidate_rejected", "action": payload["action"]},
            metadata=metadata,
        )

    def apply_commit(self, state: VerifierBudgetState, candidate: TypedCandidate) -> VerifierBudgetState:
        current = normalize_verifier_budget_state(state)
        payload = normalize_verifier_budget_payload(candidate.payload)
        return VerifierBudgetState(committed_actions=(*current.committed_actions, payload["action"]))

    def replay(self, state: VerifierBudgetState, receipt: Receipt) -> VerifierBudgetState:
        current = normalize_verifier_budget_state(state)
        payload = normalize_verifier_budget_payload(receipt.replay_bundle["candidate_payload"])
        return VerifierBudgetState(committed_actions=(*current.committed_actions, payload["action"]))

    def rollback(self, state: VerifierBudgetState, receipt: Receipt) -> VerifierBudgetState:
        return normalize_verifier_budget_state(receipt.rollback_bundle["pre_state"])


class VerifierBudgetProjector:
    def project(self, state: VerifierBudgetState, trace: ProposalTrace) -> TypedCandidate:
        del state
        if not trace.actions:
            raise ValueError("verifier budget traces must contain one action payload")
        return make_verifier_budget_candidate(normalize_verifier_budget_payload(trace.actions[0]))


def make_verifier_budget_candidate(payload: Mapping[str, Any]) -> TypedCandidate:
    normalized = normalize_verifier_budget_payload(payload)
    return TypedCandidate(
        payload=normalized,
        type_name="verifier_budget.plan",
        schema_version="verifier_budget.plan.v1",
    )


def make_verifier_budget_traces() -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"verifier-budget-{payload['action']}",
            actions=(payload,),
            seeds=("verifier_budget", payload["action"]),
            model_version="verifier.budget.v1",
        )
        for payload in _candidate_payloads()
    )


def run_verifier_budget_benchmark() -> VerifierBudgetReport:
    traces = make_verifier_budget_traces()
    unbudgeted_engine = TransactionEngine(VerifierBudgetAdapter())
    unbudgeted = BranchRuntime(unbudgeted_engine, VerifierBudgetProjector()).step(VerifierBudgetState(), traces)

    engine = TransactionEngine(VerifierBudgetAdapter())
    budgeted = BudgetedBranchRuntime(engine, VerifierBudgetProjector(), VerifierBudget(BUDGET_LIMIT)).step(VerifierBudgetState(), traces)
    receipts = tuple(budgeted.receipts)
    abstain_receipt = _single_receipt(receipts, "abstain")
    reject_receipt = _single_receipt(receipts, "reject")
    abstain_payload = normalize_verifier_budget_payload(abstain_receipt.replay_bundle["candidate_payload"])
    committed = normalize_verifier_budget_state(budgeted.state)
    unbudgeted_committed = normalize_verifier_budget_state(unbudgeted.state)

    return VerifierBudgetReport(
        candidate_count=len(traces),
        budget=BUDGET_LIMIT,
        unbudgeted_verifier_calls=unbudgeted.verifier_calls,
        unbudgeted_committed_action=unbudgeted_committed.committed_actions[-1],
        verifier_calls=budgeted.verifier_calls,
        verifier_cost=budgeted.verifier_cost,
        abstained_count=budgeted.abstained_count,
        committed_action=committed.committed_actions[-1],
        skipped_action=abstain_payload["action"],
        verified_rejected_action=str(reject_receipt.hard_result.metadata["action"]),
        budget_residual_kind=str(abstain_receipt.hard_result.residual["kind"]),
        expensive_required_cost=int(abstain_receipt.hard_result.residual["required_verifier_cost"]),
        remaining_budget_before_expensive=int(abstain_receipt.hard_result.residual["remaining_budget"]),
        receipt_decisions=tuple(receipt.commit_decision for receipt in receipts),
        ledger_audit=engine.ledger.audit(),
        replay_rollback_rate=_replay_rollback_rate(engine),
        invalid_commit_count=engine.invalid_commit_count,
    )


def normalize_verifier_budget_state(state: VerifierBudgetState | Mapping[str, Any]) -> VerifierBudgetState:
    if isinstance(state, VerifierBudgetState):
        return VerifierBudgetState(committed_actions=tuple(str(action) for action in state.committed_actions))
    raw = state.get("committed_actions", state.get("committedActions", ()))
    return VerifierBudgetState(committed_actions=tuple(str(action) for action in raw))


def normalize_verifier_budget_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    action = str(payload["action"])
    if not action:
        raise ValueError("action must be non-empty")
    accepted = payload.get("accepted", False)
    if not isinstance(accepted, bool):
        raise ValueError("accepted must be a boolean")
    return {
        "context": str(payload.get("context", CONTEXT)),
        "action": action,
        "plan_cost": _positive_int(payload.get("plan_cost", payload.get("planCost", 1)), "plan_cost"),
        "verifier_cost": _positive_int(payload.get("verifier_cost", payload.get("verifierCost", 1)), "verifier_cost"),
        "accepted": accepted,
    }


def _candidate_payloads() -> tuple[dict[str, Any], ...]:
    return (
        {"context": CONTEXT, "action": EXPENSIVE_SOLUTION, "plan_cost": 1, "verifier_cost": 7, "accepted": True},
        {"context": CONTEXT, "action": CHEAP_DECOY, "plan_cost": 1, "verifier_cost": 2, "accepted": False},
        {"context": CONTEXT, "action": CHEAP_SOLUTION, "plan_cost": 2, "verifier_cost": 2, "accepted": True},
    )


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value)
    else:
        raise ValueError(f"{field} must be a positive integer")
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _single_receipt(receipts: tuple[Receipt, ...], status: str) -> Receipt:
    rows = [receipt for receipt in receipts if receipt.hard_result.result == status]
    if len(rows) != 1:
        raise AssertionError(f"expected exactly one {status} receipt, got {len(rows)}")
    return rows[0]


def _replay_rollback_rate(engine: TransactionEngine) -> float:
    try:
        engine.replay_audit(VerifierBudgetState())
        return 1.0 if engine.rollback_audit(VerifierBudgetState()) == VerifierBudgetState() else 0.0
    except Exception:
        return 0.0
