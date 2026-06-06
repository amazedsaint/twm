from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from ..budget_policy import BudgetCandidate, ReceiptBudgetPolicy
from ..core import ProposalTrace, Receipt, TransactionEngine
from ..transfer import (
    TRANSFER_EVALUATION_CERTIFICATE_SCHEMA,
    build_transfer_evaluation_certificate,
    transfer_evaluation_rejects_positive_claim,
    transfer_evaluation_supports_positive_claim,
    validate_transfer_evaluation_certificate,
)
from .operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate


TRANSFER_AUDIT_BUDGET = 1


@dataclass(frozen=True)
class CrossDomainTransferReport:
    schema_version: str
    certificate_valid: bool
    positive_transfer_claim_supported: bool
    positive_transfer_claim_rejected: bool
    claim_id: str
    source_domain_count: int
    target_domain_count: int
    source_receipt_count: int
    target_evaluation_receipt_count: int
    source_target_domain_disjoint: bool
    source_target_receipt_disjoint: bool
    same_case_baseline: bool
    transfer_name: str
    baseline_name: str
    source_selected: tuple[str, ...]
    transfer_selected: tuple[str, ...]
    baseline_selected: tuple[str, ...]
    transfer_success_count: int
    baseline_success_count: int
    transfer_verifier_calls: int
    baseline_verifier_calls: int
    success_delta: int
    verifier_call_delta: int
    conclusion: str
    transfer_residual_kind: str
    hard_commit_only: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float
    learner_snapshot_hash: str
    certificate_hash: str
    tamper_detected: bool
    overlap_detected: bool


def run_cross_domain_transfer_audit() -> CrossDomainTransferReport:
    source_state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
    target_state = InventoryState(stock={"widget": 2}, reserved={"widget": 0})

    policy = ReceiptBudgetPolicy()
    source_engine = TransactionEngine(InventoryReservationAdapter())
    source_receipt = source_engine.transact(
        source_state,
        ProposalTrace(branch_id="transfer-source-quantity-5", actions=({"label": "quantity-5"},), model_version="transfer.source.v1"),
        make_reservation_candidate(source_state, "source-q5", "widget", 5, 5, context="transfer-source", cost=1),
    ).receipt
    policy.update("quantity-5", source_receipt)

    target_candidates = _target_candidates(target_state)
    transfer_engine = TransactionEngine(InventoryReservationAdapter())
    transfer = policy.submit(
        transfer_engine,
        target_state,
        target_candidates,
        budget=TRANSFER_AUDIT_BUDGET,
        trace_prefix="transfer-source-policy",
        model_version="transfer.source_policy.v1",
    )

    baseline_engine = TransactionEngine(InventoryReservationAdapter())
    baseline = _target_local_submit(baseline_engine, target_state, target_candidates, TRANSFER_AUDIT_BUDGET)
    snapshot = policy.snapshot()
    eval_receipts = (*transfer.receipts, *baseline.receipts)
    ledger_audit = source_engine.ledger.audit() and transfer_engine.ledger.audit() and baseline_engine.ledger.audit()
    replay_rollback_rate = _replay_rollback_rate(
        (
            (source_engine, source_state),
            (transfer_engine, target_state),
            (baseline_engine, target_state),
        )
    )
    certificate = build_transfer_evaluation_certificate(
        claim_id="source_inventory_policy_transfers_to_target_inventory",
        learner_id="receipt_budget_policy_source_only",
        learner_snapshot_hash=snapshot.snapshot_hash,
        source_domains=("source_inventory",),
        target_domains=("target_inventory",),
        source_receipt_hashes=(source_receipt.receipt_hash,),
        target_evaluation_receipt_hashes=(receipt.receipt_hash for receipt in eval_receipts),
        baseline_name="target_local_quantity_2",
        transfer_name="source_only_quantity_5",
        baseline_success_count=1 if baseline.committed else 0,
        transfer_success_count=1 if transfer.committed else 0,
        baseline_verifier_calls=len(baseline.receipts),
        transfer_verifier_calls=len(transfer.receipts),
        same_case_baseline=True,
        hard_commit_only=all(receipt.committed == receipt.hard_result.accepted for receipt in (source_receipt, *eval_receipts)),
        invalid_commit_count=source_engine.invalid_commit_count + transfer_engine.invalid_commit_count + baseline_engine.invalid_commit_count,
        ledger_audit=ledger_audit,
        replay_rollback_rate=replay_rollback_rate,
        metrics={
            "source_selected": ("quantity-5",),
            "transfer_selected": transfer.selected_labels,
            "baseline_selected": baseline.submitted_labels,
            "target_stock": 2,
            "budget": TRANSFER_AUDIT_BUDGET,
        },
    )
    tampered = replace(certificate, transfer_success_count=1, certificate_hash="")
    overlapping = build_transfer_evaluation_certificate(
        claim_id=certificate.claim_id,
        learner_id=certificate.learner_id,
        learner_snapshot_hash=certificate.learner_snapshot_hash,
        source_domains=certificate.source_domains,
        target_domains=certificate.target_domains,
        source_receipt_hashes=certificate.source_receipt_hashes,
        target_evaluation_receipt_hashes=(certificate.source_receipt_hashes[0],),
        baseline_name=certificate.baseline_name,
        transfer_name=certificate.transfer_name,
        baseline_success_count=certificate.baseline_success_count,
        transfer_success_count=certificate.transfer_success_count,
        baseline_verifier_calls=certificate.baseline_verifier_calls,
        transfer_verifier_calls=certificate.transfer_verifier_calls,
        same_case_baseline=certificate.same_case_baseline,
        hard_commit_only=certificate.hard_commit_only,
        invalid_commit_count=certificate.invalid_commit_count,
        ledger_audit=certificate.ledger_audit,
        replay_rollback_rate=certificate.replay_rollback_rate,
        metrics=certificate.metrics,
    )
    residual = transfer.receipts[0].hard_result.residual if transfer.receipts else {}
    residual_kind = residual.get("kind", "") if isinstance(residual, dict) else ""

    return CrossDomainTransferReport(
        schema_version=TRANSFER_EVALUATION_CERTIFICATE_SCHEMA,
        certificate_valid=validate_transfer_evaluation_certificate(certificate),
        positive_transfer_claim_supported=transfer_evaluation_supports_positive_claim(certificate),
        positive_transfer_claim_rejected=transfer_evaluation_rejects_positive_claim(certificate),
        claim_id=certificate.claim_id,
        source_domain_count=len(certificate.source_domains),
        target_domain_count=len(certificate.target_domains),
        source_receipt_count=len(certificate.source_receipt_hashes),
        target_evaluation_receipt_count=len(certificate.target_evaluation_receipt_hashes),
        source_target_domain_disjoint=certificate.source_target_domain_disjoint,
        source_target_receipt_disjoint=certificate.source_target_receipt_disjoint,
        same_case_baseline=certificate.same_case_baseline,
        transfer_name=certificate.transfer_name,
        baseline_name=certificate.baseline_name,
        source_selected=("quantity-5",),
        transfer_selected=transfer.selected_labels,
        baseline_selected=baseline.submitted_labels,
        transfer_success_count=certificate.transfer_success_count,
        baseline_success_count=certificate.baseline_success_count,
        transfer_verifier_calls=certificate.transfer_verifier_calls,
        baseline_verifier_calls=certificate.baseline_verifier_calls,
        success_delta=certificate.success_delta,
        verifier_call_delta=certificate.verifier_call_delta,
        conclusion=certificate.conclusion,
        transfer_residual_kind=residual_kind,
        hard_commit_only=certificate.hard_commit_only,
        invalid_commit_count=certificate.invalid_commit_count,
        ledger_audit=certificate.ledger_audit,
        replay_rollback_rate=certificate.replay_rollback_rate,
        learner_snapshot_hash=certificate.learner_snapshot_hash,
        certificate_hash=certificate.certificate_hash,
        tamper_detected=not validate_transfer_evaluation_certificate(tampered),
        overlap_detected=not validate_transfer_evaluation_certificate(overlapping),
    )


def _target_candidates(state: InventoryState) -> tuple[BudgetCandidate, ...]:
    quantities = (5, 2)
    return tuple(
        BudgetCandidate(
            label=f"quantity-{quantity}",
            token=f"quantity-{quantity}",
            candidate=make_reservation_candidate(
                state,
                f"target-q{quantity}",
                "widget",
                5,
                quantity,
                context="transfer-target",
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
    candidates: Iterable[BudgetCandidate],
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
            ProposalTrace(branch_id=f"transfer-target-baseline-{idx}-{row.label}", actions=({"label": row.label},), model_version="transfer.target.v1"),
            row.candidate,
        )
        receipts.append(outcome.receipt)
        labels.append(row.label)
        spent += row.verifier_cost
        if outcome.committed:
            return _BaselineOutcome(True, tuple(labels), tuple(receipts))
    return _BaselineOutcome(False, tuple(labels), tuple(receipts))


def _replay_rollback_rate(rows: Iterable[tuple[TransactionEngine, InventoryState]]) -> float:
    total = 0
    ok = 0
    for engine, state in rows:
        total += 1
        try:
            if engine.ledger.audit():
                engine.replay_audit(state)
                if engine.rollback_audit(state) == state:
                    ok += 1
        except Exception:
            pass
    return ok / total if total else 0.0
