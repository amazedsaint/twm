from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..branch import BranchRuntime
from ..core import HardVerifierResult, ProposalTrace, Receipt, TransactionEngine, TypedCandidate
from ..verifier_guard import VerifierAgreementAdapter
from .operations import (
    InventoryReservationAdapter,
    InventoryState,
    make_reservation_candidate,
    normalize_inventory_state,
)


GUARD_SKU = "widget"
UNSAFE_ORDER = "unsafe-large"
SAFE_ORDER = "safe-small"


@dataclass(frozen=True)
class VerifierGuardReport:
    branch_count: int
    unguarded_committed_action: str
    unguarded_stock_after: int
    unguarded_negative_stock: bool
    unguarded_ledger_audit: bool
    unguarded_replay_rollback_rate: float
    unguarded_invalid_commit_count: int
    guarded_committed_action: str
    guarded_stock_after: int
    unsafe_rejected_before_commit: bool
    false_positive_count: int
    primary_calls: int
    audit_calls: int
    false_positive_residual_kind: str
    audit_residual_kind: str
    guarded_receipt_decisions: tuple[str, ...]
    guarded_ledger_audit: bool
    guarded_replay_rollback_rate: float
    guarded_invalid_commit_count: int


class FlawedInventoryPrimaryAdapter:
    verifier_id = "flawed_inventory_primary"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        state = normalize_inventory_state(payload["pre_state"])
        order_id = str(payload["order_id"])
        sku = str(payload["sku"])
        requested = int(payload["requested"])
        quantity = int(payload["quantity"])
        diff = {
            "stock_delta": int(payload.get("diff", {}).get("stock_delta", 0)),
            "reserved_delta": int(payload.get("diff", {}).get("reserved_delta", 0)),
        }
        metadata = {"cost": int(payload.get("cost", 1)), "requested": requested, "quantity": quantity}
        if not order_id:
            return self._reject("schema_error", {"message": "order_id must be non-empty"}, metadata)
        if order_id in state.committed_orders:
            return self._reject("duplicate_order", {"order_id": order_id}, metadata)
        if requested <= 0 or quantity <= 0:
            return self._reject("schema_error", {"message": "requested and quantity must be positive"}, metadata)
        if quantity > requested:
            return self._reject("over_reservation", {"requested": requested, "quantity": quantity}, metadata)
        expected = {"stock_delta": -quantity, "reserved_delta": quantity}
        if diff != expected:
            return self._reject("diff_mismatch", {"expected": expected, "actual": diff}, metadata)
        available = int(state.stock.get(sku, 0))
        return HardVerifierResult.accept(
            self.verifier_id,
            self.verifier_version,
            metadata={**metadata, "available_before": available, "available_after": available - quantity},
        )

    def apply_commit(self, state: InventoryState, candidate: TypedCandidate) -> InventoryState:
        payload = candidate.payload
        current = normalize_inventory_state(state)
        pre_state = normalize_inventory_state(payload["pre_state"])
        if current != pre_state:
            raise ValueError("candidate pre_state does not match current inventory state")
        return apply_permissive_inventory_reservation(
            current,
            str(payload["order_id"]),
            str(payload["sku"]),
            int(payload["quantity"]),
        )

    def replay(self, state: InventoryState, receipt: Receipt) -> InventoryState:
        payload = receipt.replay_bundle["candidate_payload"]
        return apply_permissive_inventory_reservation(
            normalize_inventory_state(state),
            str(payload["order_id"]),
            str(payload["sku"]),
            int(payload["quantity"]),
        )

    def rollback(self, state: InventoryState, receipt: Receipt) -> InventoryState:
        return normalize_inventory_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


class VerifierGuardProjector:
    def project(self, state: InventoryState, trace: ProposalTrace) -> TypedCandidate:
        if not trace.actions:
            raise ValueError("verifier guard traces must contain one action payload")
        payload = normalize_guard_payload(trace.actions[0])
        return make_reservation_candidate(
            normalize_inventory_state(state),
            payload["order_id"],
            payload["sku"],
            payload["requested"],
            payload["quantity"],
            context=payload["context"],
            cost=payload["cost"],
        )


def make_verifier_guard_traces() -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"verifier-guard-{payload['order_id']}",
            actions=(payload,),
            seeds=("verifier_guard", payload["order_id"]),
            model_version="verifier.false_positive_guard.v1",
        )
        for payload in _candidate_payloads()
    )


def run_verifier_guard_benchmark() -> VerifierGuardReport:
    seed_state = InventoryState(stock={GUARD_SKU: 5}, reserved={GUARD_SKU: 0})
    traces = make_verifier_guard_traces()

    unguarded_engine = TransactionEngine(FlawedInventoryPrimaryAdapter())
    unguarded = BranchRuntime(unguarded_engine, VerifierGuardProjector()).step(seed_state, traces)
    unguarded_state = unguarded.state

    guard = VerifierAgreementAdapter(FlawedInventoryPrimaryAdapter(), InventoryReservationAdapter())
    guarded_engine = TransactionEngine(guard)
    guarded = BranchRuntime(guarded_engine, VerifierGuardProjector()).step(seed_state, traces)
    guarded_state = normalize_inventory_state(guarded.state)
    guarded_receipts = tuple(guarded.receipts)
    false_positive_receipt = _false_positive_receipt(guarded_receipts)

    return VerifierGuardReport(
        branch_count=len(traces),
        unguarded_committed_action=str(unguarded_state.committed_orders[-1]),
        unguarded_stock_after=int(unguarded_state.stock.get(GUARD_SKU, 0)),
        unguarded_negative_stock=int(unguarded_state.stock.get(GUARD_SKU, 0)) < 0,
        unguarded_ledger_audit=unguarded_engine.ledger.audit(),
        unguarded_replay_rollback_rate=_replay_rollback_rate(unguarded_engine, seed_state),
        unguarded_invalid_commit_count=unguarded_engine.invalid_commit_count,
        guarded_committed_action=guarded_state.committed_orders[-1],
        guarded_stock_after=int(guarded_state.stock.get(GUARD_SKU, 0)),
        unsafe_rejected_before_commit=not any(
            receipt.committed and _order_id(receipt) == UNSAFE_ORDER for receipt in guarded_receipts
        ),
        false_positive_count=guard.false_positive_count,
        primary_calls=guard.primary_calls,
        audit_calls=guard.audit_calls,
        false_positive_residual_kind=str(false_positive_receipt.hard_result.residual["kind"]),
        audit_residual_kind=str(false_positive_receipt.hard_result.residual["audit_residual"]["kind"]),
        guarded_receipt_decisions=tuple(receipt.commit_decision for receipt in guarded_receipts),
        guarded_ledger_audit=guarded_engine.ledger.audit(),
        guarded_replay_rollback_rate=_replay_rollback_rate(guarded_engine, seed_state),
        guarded_invalid_commit_count=guarded_engine.invalid_commit_count,
    )


def apply_permissive_inventory_reservation(state: InventoryState, order_id: str, sku: str, quantity: int) -> InventoryState:
    state = normalize_inventory_state(state)
    stock = dict(state.stock)
    reserved = dict(state.reserved)
    available = int(stock.get(sku, 0))
    stock[sku] = available - int(quantity)
    reserved[sku] = int(reserved.get(sku, 0)) + int(quantity)
    return InventoryState(stock=stock, reserved=reserved, committed_orders=(*state.committed_orders, order_id))


def normalize_guard_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    order_id = str(payload["order_id"])
    if not order_id:
        raise ValueError("order_id must be non-empty")
    return {
        "context": str(payload.get("context", "verifier-guard")),
        "order_id": order_id,
        "sku": str(payload.get("sku", GUARD_SKU)),
        "requested": _positive_int(payload["requested"], "requested"),
        "quantity": _positive_int(payload["quantity"], "quantity"),
        "cost": _positive_int(payload.get("cost", 1), "cost"),
    }


def _candidate_payloads() -> tuple[dict[str, Any], ...]:
    return (
        {"order_id": UNSAFE_ORDER, "sku": GUARD_SKU, "requested": 8, "quantity": 8, "cost": 1},
        {"order_id": SAFE_ORDER, "sku": GUARD_SKU, "requested": 3, "quantity": 3, "cost": 5},
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


def _false_positive_receipt(receipts: tuple[Receipt, ...]) -> Receipt:
    rows = [
        receipt
        for receipt in receipts
        if isinstance(receipt.hard_result.residual, Mapping)
        and receipt.hard_result.residual.get("kind") == "verifier_false_positive"
    ]
    if len(rows) != 1:
        raise AssertionError(f"expected exactly one false-positive receipt, got {len(rows)}")
    return rows[0]


def _order_id(receipt: Receipt) -> str:
    payload = receipt.replay_bundle.get("candidate_payload", {})
    if isinstance(payload, Mapping):
        return str(payload.get("order_id", ""))
    return ""


def _replay_rollback_rate(engine: TransactionEngine, seed_state: InventoryState) -> float:
    try:
        engine.replay_audit(seed_state)
        return 1.0 if engine.rollback_audit(seed_state) == seed_state else 0.0
    except Exception:
        return 0.0
