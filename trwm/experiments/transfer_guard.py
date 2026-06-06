from __future__ import annotations

from dataclasses import dataclass, replace

from ..budget_policy import BudgetCandidate, ReceiptBudgetPolicy
from ..core import ProposalTrace, Receipt, TransactionEngine
from ..transfer import (
    TRANSFER_GUARD_SNAPSHOT_SCHEMA,
    TransferGuardMemory,
    build_transfer_evaluation_certificate,
    validate_transfer_guard_decision,
    validate_transfer_guard_snapshot,
)
from .operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate


TRANSFER_GUARD_BUDGET = 1


@dataclass(frozen=True)
class TransferGuardReport:
    schema_version: str
    snapshot_valid: bool
    decision_valid: bool
    guard_blocks_source_policy: bool
    guard_decision_admitted: bool
    guard_decision_reason: str
    guard_decision_hash: str
    source_selected: tuple[str, ...]
    unguarded_selected: tuple[str, ...]
    unguarded_committed: bool
    unguarded_residual_kind: str
    guarded_selected: tuple[str, ...]
    guarded_committed: bool
    guarded_used_target_baseline: bool
    avoided_negative_transfer: bool
    certificate_conclusion: str
    certificate_hash: str
    snapshot_hash: str
    tamper_detected: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float


def run_transfer_guard_benchmark() -> TransferGuardReport:
    source_state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
    target_state = InventoryState(stock={"widget": 2}, reserved={"widget": 0})

    policy = ReceiptBudgetPolicy()
    source_engine = TransactionEngine(InventoryReservationAdapter())
    source_receipt = source_engine.transact(
        source_state,
        ProposalTrace(branch_id="transfer-guard-source-quantity-5", actions=({"label": "quantity-5"},), model_version="transfer.guard.source.v1"),
        make_reservation_candidate(source_state, "guard-source-q5", "widget", 5, 5, context="transfer-guard-source", cost=1),
    ).receipt
    policy.update("quantity-5", source_receipt)
    candidates = _target_candidates(target_state)

    eval_transfer_engine = TransactionEngine(InventoryReservationAdapter())
    eval_transfer = policy.submit(
        eval_transfer_engine,
        target_state,
        candidates,
        budget=TRANSFER_GUARD_BUDGET,
        trace_prefix="transfer-guard-eval-transfer",
        model_version="transfer.guard.eval_transfer.v1",
    )
    eval_baseline_engine = TransactionEngine(InventoryReservationAdapter())
    eval_baseline = _target_local_submit(eval_baseline_engine, target_state, candidates, TRANSFER_GUARD_BUDGET)
    evaluation_receipts = (*eval_transfer.receipts, *eval_baseline.receipts)
    certificate = build_transfer_evaluation_certificate(
        claim_id="transfer_guard_blocks_source_inventory_negative_transfer",
        learner_id="receipt_budget_policy_source_only",
        learner_snapshot_hash=policy.snapshot().snapshot_hash,
        source_domains=("source_inventory",),
        target_domains=("target_inventory",),
        source_receipt_hashes=(source_receipt.receipt_hash,),
        target_evaluation_receipt_hashes=(receipt.receipt_hash for receipt in evaluation_receipts),
        baseline_name="target_local_quantity_2",
        transfer_name="source_only_quantity_5",
        baseline_success_count=1 if eval_baseline.committed else 0,
        transfer_success_count=1 if eval_transfer.committed else 0,
        baseline_verifier_calls=len(eval_baseline.receipts),
        transfer_verifier_calls=len(eval_transfer.receipts),
        same_case_baseline=True,
        hard_commit_only=all(receipt.committed == receipt.hard_result.accepted for receipt in (source_receipt, *evaluation_receipts)),
        invalid_commit_count=source_engine.invalid_commit_count + eval_transfer_engine.invalid_commit_count + eval_baseline_engine.invalid_commit_count,
        ledger_audit=source_engine.ledger.audit() and eval_transfer_engine.ledger.audit() and eval_baseline_engine.ledger.audit(),
        replay_rollback_rate=_replay_rollback_rate(
            (
                (source_engine, source_state),
                (eval_transfer_engine, target_state),
                (eval_baseline_engine, target_state),
            )
        ),
    )

    guard = TransferGuardMemory()
    guard.update(certificate)
    decision = guard.decide(("source_inventory",), "target_inventory")
    snapshot = guard.snapshot()
    tampered = replace(snapshot, entries=(replace(snapshot.entries[0], conclusion="positive_transfer"),), snapshot_hash="")

    unguarded_engine = TransactionEngine(InventoryReservationAdapter())
    unguarded = policy.submit(
        unguarded_engine,
        target_state,
        candidates,
        budget=TRANSFER_GUARD_BUDGET,
        trace_prefix="transfer-guard-unguarded",
        model_version="transfer.guard.unguarded.v1",
    )
    guarded_engine = TransactionEngine(InventoryReservationAdapter())
    if decision.admitted:
        guarded = policy.submit(
            guarded_engine,
            target_state,
            candidates,
            budget=TRANSFER_GUARD_BUDGET,
            trace_prefix="transfer-guard-admitted",
            model_version="transfer.guard.admitted.v1",
        )
        guarded_selected = guarded.selected_labels
        guarded_committed = guarded.committed
        guarded_receipts = guarded.receipts
        guarded_used_target_baseline = False
    else:
        baseline_guarded = _target_local_submit(guarded_engine, target_state, candidates, TRANSFER_GUARD_BUDGET)
        guarded_selected = baseline_guarded.submitted_labels
        guarded_committed = baseline_guarded.committed
        guarded_receipts = baseline_guarded.receipts
        guarded_used_target_baseline = True

    residual = unguarded.receipts[0].hard_result.residual if unguarded.receipts else {}
    residual_kind = residual.get("kind", "") if isinstance(residual, dict) else ""
    ledger_audit = all(
        engine.ledger.audit()
        for engine in (source_engine, eval_transfer_engine, eval_baseline_engine, unguarded_engine, guarded_engine)
    )
    replay_rollback_rate = _replay_rollback_rate(
        (
            (source_engine, source_state),
            (eval_transfer_engine, target_state),
            (eval_baseline_engine, target_state),
            (unguarded_engine, target_state),
            (guarded_engine, target_state),
        )
    )
    return TransferGuardReport(
        schema_version=TRANSFER_GUARD_SNAPSHOT_SCHEMA,
        snapshot_valid=validate_transfer_guard_snapshot(snapshot),
        decision_valid=validate_transfer_guard_decision(decision),
        guard_blocks_source_policy=not decision.admitted and decision.reason == "negative_transfer_certificate",
        guard_decision_admitted=decision.admitted,
        guard_decision_reason=decision.reason,
        guard_decision_hash=decision.decision_hash,
        source_selected=("quantity-5",),
        unguarded_selected=unguarded.selected_labels,
        unguarded_committed=unguarded.committed,
        unguarded_residual_kind=residual_kind,
        guarded_selected=guarded_selected,
        guarded_committed=guarded_committed,
        guarded_used_target_baseline=guarded_used_target_baseline,
        avoided_negative_transfer=(not unguarded.committed and guarded_committed and guarded_used_target_baseline),
        certificate_conclusion=certificate.conclusion,
        certificate_hash=certificate.certificate_hash,
        snapshot_hash=snapshot.snapshot_hash,
        tamper_detected=not validate_transfer_guard_snapshot(tampered),
        invalid_commit_count=(
            source_engine.invalid_commit_count
            + eval_transfer_engine.invalid_commit_count
            + eval_baseline_engine.invalid_commit_count
            + unguarded_engine.invalid_commit_count
            + guarded_engine.invalid_commit_count
        ),
        ledger_audit=ledger_audit,
        replay_rollback_rate=replay_rollback_rate,
    )


def _target_candidates(state: InventoryState) -> tuple[BudgetCandidate, ...]:
    quantities = (5, 2)
    return tuple(
        BudgetCandidate(
            label=f"quantity-{quantity}",
            token=f"quantity-{quantity}",
            candidate=make_reservation_candidate(
                state,
                f"guard-target-q{quantity}",
                "widget",
                5,
                quantity,
                context="transfer-guard-target",
                cost=1,
            ),
            verifier_cost=1,
            reward=float(quantity),
            base_rank=idx,
        )
        for idx, quantity in enumerate(quantities)
    )


@dataclass(frozen=True)
class _BaselineOutcome:
    committed: bool
    submitted_labels: tuple[str, ...]
    receipts: tuple[Receipt, ...]


def _target_local_submit(
    engine: TransactionEngine,
    state: InventoryState,
    candidates: tuple[BudgetCandidate, ...],
    budget: int,
) -> _BaselineOutcome:
    receipts: list[Receipt] = []
    labels: list[str] = []
    spent = 0
    for idx, row in enumerate(sorted(candidates, key=lambda item: (0 if item.label == "quantity-2" else 1, item.label))):
        if spent + row.verifier_cost > budget:
            continue
        outcome = engine.transact(
            state,
            ProposalTrace(branch_id=f"transfer-guard-target-baseline-{idx}-{row.label}", actions=({"label": row.label},), model_version="transfer.guard.target.v1"),
            row.candidate,
        )
        receipts.append(outcome.receipt)
        labels.append(row.label)
        spent += row.verifier_cost
        if outcome.committed:
            return _BaselineOutcome(True, tuple(labels), tuple(receipts))
    return _BaselineOutcome(False, tuple(labels), tuple(receipts))


def _replay_rollback_rate(rows: tuple[tuple[TransactionEngine, InventoryState], ...]) -> float:
    ok = 0
    for engine, state in rows:
        try:
            if engine.ledger.audit():
                engine.replay_audit(state)
                if engine.rollback_audit(state) == state:
                    ok += 1
        except Exception:
            pass
    return ok / len(rows)
