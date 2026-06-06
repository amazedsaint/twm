from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..branch import BranchRuntime
from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate
from ..learning import CounterfactualRollbackRanker, ReceiptRanker


CONTEXT = "counterfactual-route"
DEFAULT_ACTIONS = (
    {"context": CONTEXT, "action": "a_slow", "cost": 2, "risk": 0.10},
    {"context": CONTEXT, "action": "b_fast", "cost": 1, "risk": 0.20},
    {"context": CONTEXT, "action": "c_unsafe", "cost": 0, "risk": 1.20},
)


@dataclass(frozen=True)
class CounterfactualChoiceState:
    committed_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class CounterfactualRollbackReport:
    episodes: int
    candidate_count: int
    committed_action: str
    static_top_action: str
    receipt_ranker_top_action: str
    counterfactual_top_action: str
    receipt_ranker_winner_rank: int
    counterfactual_winner_rank: int
    rolled_back_loser_count: int
    hard_reject_count: int
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int


class CounterfactualChoiceAdapter:
    verifier_id = "counterfactual_choice_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        metadata = {"cost": payload["cost"], "risk": payload["risk"], "action": payload["action"]}
        if payload["risk"] > 1.0:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "risk_limit", "risk": payload["risk"], "limit": 1.0},
                metadata=metadata,
            )
        return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)

    def apply_commit(self, state: CounterfactualChoiceState, candidate: TypedCandidate) -> CounterfactualChoiceState:
        current = normalize_state(state)
        payload = _normalize_payload(candidate.payload)
        return CounterfactualChoiceState(committed_actions=(*current.committed_actions, payload["action"]))

    def replay(self, state: CounterfactualChoiceState, receipt: Receipt) -> CounterfactualChoiceState:
        current = normalize_state(state)
        payload = _normalize_payload(receipt.replay_bundle["candidate_payload"])
        return CounterfactualChoiceState(committed_actions=(*current.committed_actions, payload["action"]))

    def rollback(self, state: CounterfactualChoiceState, receipt: Receipt) -> CounterfactualChoiceState:
        return normalize_state(receipt.rollback_bundle["pre_state"])


class CounterfactualChoiceProjector:
    def project(self, _state: CounterfactualChoiceState, trace: ProposalTrace) -> TypedCandidate:
        return make_counterfactual_choice_candidate(trace.actions[-1])


def normalize_state(state: CounterfactualChoiceState | Mapping[str, Any]) -> CounterfactualChoiceState:
    if isinstance(state, CounterfactualChoiceState):
        return CounterfactualChoiceState(committed_actions=tuple(str(action) for action in state.committed_actions))
    return CounterfactualChoiceState(committed_actions=tuple(str(action) for action in state.get("committed_actions", ())))


def make_counterfactual_choice_candidate(payload: Mapping[str, Any]) -> TypedCandidate:
    normalized = _normalize_payload(payload)
    return TypedCandidate(
        payload=normalized,
        type_name="counterfactual.choice",
        schema_version="counterfactual.choice.v1",
    )


def make_counterfactual_traces(episode: int, actions: Iterable[Mapping[str, Any]] = DEFAULT_ACTIONS) -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"counterfactual-{episode}-{action['action']}",
            actions=(dict(action),),
            seeds=("counterfactual", episode, action["action"]),
            model_version="counterfactual.rollback.v1",
        )
        for action in actions
    )


def run_counterfactual_rollback_benchmark(episodes: int = 32) -> CounterfactualRollbackReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, CounterfactualChoiceProjector())
    receipt_ranker = ReceiptRanker()
    counterfactual_ranker = CounterfactualRollbackRanker()
    seed = CounterfactualChoiceState()
    state = seed
    for episode in range(episodes):
        outcome = runtime.step(state, make_counterfactual_traces(episode))
        state = normalize_state(outcome.state)
        for receipt in outcome.receipts:
            receipt_ranker.update(receipt)
            counterfactual_ranker.update(receipt)

    actions = tuple(action["action"] for action in DEFAULT_ACTIONS)
    committed_action = "b_fast"
    receipt_order = receipt_ranker.rank(CONTEXT, actions)
    counterfactual_order = counterfactual_ranker.rank(CONTEXT, actions)
    audit_ok = engine.ledger.audit()
    replay_rollback_rate = 0.0
    if audit_ok:
        try:
            replay_state = engine.replay_audit(seed)
            rollback_state = engine.rollback_audit(seed)
            replay_rollback_rate = 1.0 if replay_state == state and rollback_state == seed else 0.0
        except Exception:
            replay_rollback_rate = 0.0
    return CounterfactualRollbackReport(
        episodes=episodes,
        candidate_count=len(actions),
        committed_action=committed_action,
        static_top_action=actions[0],
        receipt_ranker_top_action=receipt_order[0],
        counterfactual_top_action=counterfactual_order[0],
        receipt_ranker_winner_rank=receipt_order.index(committed_action) + 1,
        counterfactual_winner_rank=counterfactual_order.index(committed_action) + 1,
        rolled_back_loser_count=counterfactual_ranker.stats(CONTEXT, "a_slow").rolled_back,
        hard_reject_count=counterfactual_ranker.stats(CONTEXT, "c_unsafe").rejected,
        ledger_audit=audit_ok,
        replay_rollback_rate=replay_rollback_rate,
        invalid_commit_count=sum(1 for row in engine.ledger.rows if row.committed and not row.hard_result.accepted),
    )


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    action = str(payload["action"])
    context = str(payload.get("context", CONTEXT))
    cost = int(payload["cost"])
    risk = float(payload["risk"])
    if not action:
        raise ValueError("action must be non-empty")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    if risk < 0:
        raise ValueError("risk must be non-negative")
    return {"context": context, "action": action, "cost": cost, "risk": risk}
