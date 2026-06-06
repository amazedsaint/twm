from __future__ import annotations

from dataclasses import dataclass

from ..core import ProposalTrace, TransactionEngine
from ..experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate, normalize_inventory_state
from ..residuals import ResidualTaxonomyMemory, residual_signal_from_receipt
from ..topk import ResidualRepairOption, ResidualTopKSubmitter


TOPK_ORDER = (8, 7, 5, 4)
TOPK_LIMIT = 2


@dataclass(frozen=True)
class ResidualTopKReport:
    training_residual_kind: str
    learned_repair_hint: str
    candidate_count: int
    top_k: int
    unranked_submitted: tuple[str, ...]
    unranked_committed: bool
    unranked_verifier_calls: int
    residual_ranked_submitted: tuple[str, ...]
    residual_ranked_committed: bool
    residual_ranked_committed_label: str
    residual_ranked_verifier_calls: int
    calls_to_commit_gain: float
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int


def run_residual_topk_benchmark() -> ResidualTopKReport:
    seed_state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
    memory = ResidualTaxonomyMemory()

    training_engine = TransactionEngine(InventoryReservationAdapter())
    training_candidate = make_reservation_candidate(seed_state, "train-over", "widget", 8, 8, context="topk-train")
    training = training_engine.transact(
        seed_state,
        ProposalTrace(branch_id="topk-train", actions=({"quantity": 8},), model_version="residual.topk.train.v1"),
        training_candidate,
    )
    signal = residual_signal_from_receipt(training.receipt, source_domain="operations")
    memory.update(signal)

    unranked_engine = TransactionEngine(InventoryReservationAdapter())
    unranked_options = _repair_options(seed_state, "unranked")
    unranked = ResidualTopKSubmitter(unranked_engine).submit(
        seed_state,
        unranked_options,
        top_k=TOPK_LIMIT,
        trace_prefix="topk-unranked",
    )

    ranked_engine = TransactionEngine(InventoryReservationAdapter())
    ranked_options = _repair_options(seed_state, "ranked")
    residual_ranked = ResidualTopKSubmitter(ranked_engine, memory).submit(
        seed_state,
        ranked_options,
        top_k=TOPK_LIMIT,
        trace_prefix="topk-ranked",
        residual_signal=signal,
    )

    committed_state = normalize_inventory_state(residual_ranked.state)
    replay_rollback_rate = 0.0
    if ranked_engine.ledger.audit():
        try:
            ranked_engine.replay_audit(seed_state)
            replay_rollback_rate = 1.0 if ranked_engine.rollback_audit(seed_state) == seed_state else 0.0
        except Exception:
            replay_rollback_rate = 0.0

    return ResidualTopKReport(
        training_residual_kind=signal.kind,
        learned_repair_hint=memory.top_repair_hint(signal.kind) or "",
        candidate_count=len(TOPK_ORDER),
        top_k=TOPK_LIMIT,
        unranked_submitted=unranked.submitted_labels,
        unranked_committed=unranked.committed,
        unranked_verifier_calls=unranked.verifier_calls,
        residual_ranked_submitted=residual_ranked.submitted_labels,
        residual_ranked_committed=residual_ranked.committed,
        residual_ranked_committed_label=residual_ranked.committed_label,
        residual_ranked_verifier_calls=residual_ranked.verifier_calls,
        calls_to_commit_gain=unranked.verifier_calls / residual_ranked.verifier_calls if residual_ranked.verifier_calls else float("inf"),
        ledger_audit=ranked_engine.ledger.audit() and committed_state.stock["widget"] == 0,
        replay_rollback_rate=replay_rollback_rate,
        invalid_commit_count=ranked_engine.invalid_commit_count + unranked_engine.invalid_commit_count + training_engine.invalid_commit_count,
    )


def _repair_options(state: InventoryState, prefix: str) -> tuple[ResidualRepairOption, ...]:
    return tuple(
        ResidualRepairOption(
            label=f"quantity-{quantity}",
            candidate=make_reservation_candidate(
                state,
                f"{prefix}-q{quantity}",
                "widget",
                8,
                quantity,
                context="topk-repair",
                cost=idx + 1,
            ),
            repair_hint=f"quantity={quantity}",
            base_rank=idx,
        )
        for idx, quantity in enumerate(TOPK_ORDER)
    )
