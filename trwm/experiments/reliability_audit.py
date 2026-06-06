from __future__ import annotations

from dataclasses import dataclass, replace

from ..core import Ledger, ProposalTrace, Receipt, TransactionEngine
from ..reliability import VerifierReliabilityMemory, validate_verifier_reliability_snapshot
from ..verifier_guard import VerifierAgreementAdapter
from .operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate, normalize_inventory_state
from .verifier_guard import FlawedInventoryPrimaryAdapter, UNSAFE_ORDER


STRICT_PRIMARY_ID = "strict_inventory_primary"
FLAWED_PRIMARY_ID = "flawed_inventory_primary"


@dataclass(frozen=True)
class ReliabilityAuditReport:
    training_receipt_count: int
    strict_successes: int
    strict_failures: int
    flawed_successes: int
    flawed_failures: int
    strict_lower_bound: float
    flawed_lower_bound: float
    risk_order: tuple[str, ...]
    audit_budget: int
    naive_audited_subject: str
    reliability_audited_subject: str
    naive_false_positive_detected: bool
    reliability_false_positive_detected: bool
    reliability_residual_kind: str
    reliability_audit_residual_kind: str
    snapshot_valid: bool
    tamper_detected: bool
    invalid_commit_count: int


class StrictInventoryPrimaryAdapter(InventoryReservationAdapter):
    verifier_id = STRICT_PRIMARY_ID

    def verify(self, candidate):
        result = super().verify(candidate)
        return replace(result, verifier_id=self.verifier_id)


def run_reliability_audit_benchmark() -> ReliabilityAuditReport:
    memory = VerifierReliabilityMemory()
    training_receipts: list[Receipt] = []
    for idx in range(3):
        receipt = _guard_receipt(
            StrictInventoryPrimaryAdapter(),
            InventoryState(stock={"widget": 5}, reserved={"widget": 0}),
            f"strict-safe-{idx}",
            1,
            1,
        )
        training_receipts.append(receipt)
        memory.update_from_receipt(receipt)

    training_specs = (("flawed-safe", 2, 2), ("flawed-unsafe-a", 8, 8), ("flawed-unsafe-b", 7, 7))
    for order_id, requested, quantity in training_specs:
        receipt = _guard_receipt(
            FlawedInventoryPrimaryAdapter(),
            InventoryState(stock={"widget": 5}, reserved={"widget": 0}),
            order_id,
            requested,
            quantity,
        )
        training_receipts.append(receipt)
        memory.update_from_receipt(receipt)

    risk_order = memory.rank_for_audit((STRICT_PRIMARY_ID, FLAWED_PRIMARY_ID))
    audit_budget = 1
    naive_audited = (STRICT_PRIMARY_ID,)
    reliability_audited = memory.select_for_audit((STRICT_PRIMARY_ID, FLAWED_PRIMARY_ID), audit_budget)
    future_state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
    naive_receipts = _audit_selected(naive_audited, future_state)
    reliability_receipts = _audit_selected(reliability_audited, future_state)
    snapshot = memory.snapshot()
    tampered = replace(snapshot, rows=tuple(replace(row, audited_failures=0) for row in snapshot.rows))

    strict = memory.score(STRICT_PRIMARY_ID)
    flawed = memory.score(FLAWED_PRIMARY_ID)
    reliability_false_positive = _false_positive_receipt(reliability_receipts)
    return ReliabilityAuditReport(
        training_receipt_count=len(training_receipts),
        strict_successes=strict.audited_successes,
        strict_failures=strict.audited_failures,
        flawed_successes=flawed.audited_successes,
        flawed_failures=flawed.audited_failures,
        strict_lower_bound=strict.wilson_lower_bound,
        flawed_lower_bound=flawed.wilson_lower_bound,
        risk_order=risk_order,
        audit_budget=audit_budget,
        naive_audited_subject=naive_audited[0],
        reliability_audited_subject=reliability_audited[0],
        naive_false_positive_detected=_false_positive_receipt(naive_receipts) is not None,
        reliability_false_positive_detected=reliability_false_positive is not None,
        reliability_residual_kind=str(reliability_false_positive.hard_result.residual["kind"]),
        reliability_audit_residual_kind=str(reliability_false_positive.hard_result.residual["audit_residual"]["kind"]),
        snapshot_valid=validate_verifier_reliability_snapshot(snapshot),
        tamper_detected=not validate_verifier_reliability_snapshot(tampered),
        invalid_commit_count=sum(1 for receipt in (*training_receipts, *naive_receipts, *reliability_receipts) if receipt.committed and not receipt.hard_result.accepted),
    )


def _guard_receipt(primary, state: InventoryState, order_id: str, requested: int, quantity: int) -> Receipt:
    engine = TransactionEngine(VerifierAgreementAdapter(primary, InventoryReservationAdapter()), ledger=Ledger())
    candidate = make_reservation_candidate(state, order_id, "widget", requested, quantity)
    return engine.transact(
        state,
        ProposalTrace(branch_id=f"reliability-train-{order_id}", actions=({"order_id": order_id},)),
        candidate,
    ).receipt


def _audit_selected(subjects: tuple[str, ...], state: InventoryState) -> tuple[Receipt, ...]:
    receipts: list[Receipt] = []
    if STRICT_PRIMARY_ID in subjects:
        receipts.append(_guard_receipt(StrictInventoryPrimaryAdapter(), state, "future-safe", 2, 2))
    if FLAWED_PRIMARY_ID in subjects:
        receipts.append(_guard_receipt(FlawedInventoryPrimaryAdapter(), state, UNSAFE_ORDER, 8, 8))
    return tuple(receipts)


def _false_positive_receipt(receipts: tuple[Receipt, ...]) -> Receipt | None:
    for receipt in receipts:
        residual = receipt.hard_result.residual
        if isinstance(residual, dict) and residual.get("kind") == "verifier_false_positive":
            return receipt
    return None
