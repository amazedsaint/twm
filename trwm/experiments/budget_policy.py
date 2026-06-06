from __future__ import annotations

from dataclasses import dataclass, replace

from ..budget_policy import BudgetCandidate, ReceiptBudgetPolicy, validate_budget_policy_snapshot
from ..core import ProposalTrace, TransactionEngine
from .operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate, normalize_inventory_state


BUDGET_POLICY_LIMIT = 3
BUDGET_POLICY_ORDER = (8, 7, 5, 4)


@dataclass(frozen=True)
class BudgetPolicyReport:
    training_receipt_count: int
    budget: int
    candidate_count: int
    learned_success_token: str
    learned_success_lower_bound: float
    cheap_first_selected: tuple[str, ...]
    cheap_first_committed: bool
    cheap_first_verifier_calls: int
    cheap_first_cost_spent: int
    learned_selected: tuple[str, ...]
    learned_committed: bool
    learned_committed_label: str
    learned_verifier_calls: int
    learned_cost_spent: int
    learned_expected_utility: float
    verifier_call_gain: float
    verifier_cost_ratio: float
    evaluation_receipt_count: int
    heldout_trace_disjoint: bool
    snapshot_valid: bool
    tamper_detected: bool
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int


def run_budget_policy_benchmark() -> BudgetPolicyReport:
    seed_state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
    policy = ReceiptBudgetPolicy()
    training_engine = TransactionEngine(InventoryReservationAdapter())
    training_specs = (("quantity-5", 5), ("quantity-8", 8), ("quantity-7", 7))
    training_branch_ids: list[str] = []
    for label, quantity in training_specs:
        branch_id = f"budget-policy-train-{label}"
        training_branch_ids.append(branch_id)
        receipt = training_engine.transact(
            seed_state,
            ProposalTrace(branch_id=branch_id, actions=({"label": label},)),
            make_reservation_candidate(seed_state, f"train-{label}", "widget", 8, quantity, context="budget-policy-train"),
        ).receipt
        policy.update(label, receipt)

    candidates = _budget_candidates(seed_state)
    cheap_engine = TransactionEngine(InventoryReservationAdapter())
    cheap = _cheap_first_submit(cheap_engine, seed_state, candidates, BUDGET_POLICY_LIMIT)

    learned_engine = TransactionEngine(InventoryReservationAdapter())
    learned = policy.submit(
        learned_engine,
        seed_state,
        candidates,
        budget=BUDGET_POLICY_LIMIT,
        trace_prefix="budget-policy-learned",
    )
    snapshot = policy.snapshot()
    tampered = replace(snapshot, rows=tuple(replace(row, successes=0) for row in snapshot.rows))
    committed_state = normalize_inventory_state(learned.state)
    replay_rollback_rate = 0.0
    if learned_engine.ledger.audit():
        try:
            learned_engine.replay_audit(seed_state)
            replay_rollback_rate = 1.0 if learned_engine.rollback_audit(seed_state) == seed_state else 0.0
        except Exception:
            replay_rollback_rate = 0.0

    return BudgetPolicyReport(
        training_receipt_count=len(training_specs),
        budget=BUDGET_POLICY_LIMIT,
        candidate_count=len(candidates),
        learned_success_token="quantity-5",
        learned_success_lower_bound=policy.score("quantity-5").success_lower_bound,
        cheap_first_selected=cheap.submitted_labels,
        cheap_first_committed=cheap.committed,
        cheap_first_verifier_calls=len(cheap.submitted_labels),
        cheap_first_cost_spent=cheap.verifier_cost_spent,
        learned_selected=learned.selected_labels,
        learned_committed=learned.committed,
        learned_committed_label=learned.committed_label,
        learned_verifier_calls=len(learned.receipts),
        learned_cost_spent=learned.verifier_cost_spent,
        learned_expected_utility=policy.plan(candidates, BUDGET_POLICY_LIMIT).expected_utility,
        verifier_call_gain=len(cheap.submitted_labels) / len(learned.receipts) if learned.receipts else float("inf"),
        verifier_cost_ratio=cheap.verifier_cost_spent / learned.verifier_cost_spent if learned.verifier_cost_spent else float("inf"),
        evaluation_receipt_count=len(learned.receipts),
        heldout_trace_disjoint=not {receipt.branch_id for receipt in learned.receipts}.intersection(training_branch_ids),
        snapshot_valid=validate_budget_policy_snapshot(snapshot),
        tamper_detected=not validate_budget_policy_snapshot(tampered),
        ledger_audit=learned_engine.ledger.audit() and committed_state.stock["widget"] == 0,
        replay_rollback_rate=replay_rollback_rate,
        invalid_commit_count=training_engine.invalid_commit_count + cheap_engine.invalid_commit_count + learned_engine.invalid_commit_count,
    )


def _budget_candidates(state: InventoryState) -> tuple[BudgetCandidate, ...]:
    cost_by_quantity = {8: 1, 7: 1, 5: 3, 4: 2}
    return tuple(
        BudgetCandidate(
            label=f"quantity-{quantity}",
            token=f"quantity-{quantity}",
            candidate=make_reservation_candidate(
                state,
                f"budget-q{quantity}",
                "widget",
                8,
                quantity,
                context="budget-policy",
                cost=cost_by_quantity[quantity],
            ),
            verifier_cost=cost_by_quantity[quantity],
            reward=float(quantity),
            base_rank=idx,
        )
        for idx, quantity in enumerate(BUDGET_POLICY_ORDER)
    )


@dataclass(frozen=True)
class _CheapOutcome:
    committed: bool
    submitted_labels: tuple[str, ...]
    verifier_cost_spent: int


def _cheap_first_submit(engine: TransactionEngine, state: InventoryState, candidates: tuple[BudgetCandidate, ...], budget: int) -> _CheapOutcome:
    spent = 0
    submitted: list[str] = []
    for idx, row in enumerate(sorted(candidates, key=lambda item: (item.verifier_cost, item.base_rank, item.label))):
        if spent + row.verifier_cost > budget:
            continue
        outcome = engine.transact(
            state,
            ProposalTrace(branch_id=f"budget-policy-cheap-{idx}-{row.label}", actions=({"label": row.label},)),
            row.candidate,
        )
        submitted.append(row.label)
        spent += row.verifier_cost
        if outcome.committed:
            return _CheapOutcome(True, tuple(submitted), spent)
    return _CheapOutcome(False, tuple(submitted), spent)
