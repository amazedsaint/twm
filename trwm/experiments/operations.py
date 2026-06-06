from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import random
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


@dataclass(frozen=True)
class InventoryState:
    stock: Mapping[str, int]
    reserved: Mapping[str, int]
    committed_orders: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperationsEpisodeResult:
    calls: int
    success: bool
    audit_ok: bool
    replay_rollback_ok: bool


@dataclass(frozen=True)
class OperationsReport:
    episodes: int
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    repair_success_rate: float
    ledger_audit_rate: float
    replay_rollback_rate: float
    invalid_commit_count: int
    learned_residual_kinds: Mapping[str, int]


class InventoryReservationAdapter:
    verifier_id = "inventory_reservation_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        state = normalize_inventory_state(payload["pre_state"])
        order_id = str(payload["order_id"])
        sku = str(payload["sku"])
        requested = int(payload["requested"])
        quantity = int(payload["quantity"])
        diff = _normalize_diff(payload.get("diff", {}), sku)
        metadata = {"cost": payload.get("cost", 1), "requested": requested, "quantity": quantity}
        if not order_id:
            return self._reject("schema_error", {"message": "order_id must be non-empty"}, metadata)
        if order_id in state.committed_orders:
            return self._reject("duplicate_order", {"order_id": order_id}, metadata)
        if requested <= 0 or quantity <= 0:
            return self._reject("schema_error", {"message": "requested and quantity must be positive"}, metadata)
        available = int(state.stock.get(sku, 0))
        if quantity > requested:
            return self._reject(
                "over_reservation",
                {"requested": requested, "quantity": quantity, "repair": {"quantity": requested}},
                metadata,
            )
        if quantity > available:
            repair = {"quantity": available} if available > 0 else None
            return self._reject(
                "stock_shortage",
                {"sku": sku, "requested": requested, "available": available, "quantity": quantity, "repair": repair},
                metadata,
            )
        expected = {"stock_delta": -quantity, "reserved_delta": quantity}
        if diff != expected:
            return self._reject("diff_mismatch", {"expected": expected, "actual": diff}, metadata)
        next_state = apply_inventory_reservation(state, order_id, sku, quantity)
        if _total_units(state, sku) != _total_units(next_state, sku):
            return self._reject("accounting_mismatch", {"sku": sku}, metadata)
        return HardVerifierResult.accept(
            self.verifier_id,
            self.verifier_version,
            metadata={**metadata, "available_before": available, "available_after": next_state.stock.get(sku, 0)},
        )

    def apply_commit(self, state: InventoryState, candidate: TypedCandidate) -> InventoryState:
        payload = candidate.payload
        pre_state = normalize_inventory_state(payload["pre_state"])
        current = normalize_inventory_state(state)
        if current != pre_state:
            raise ValueError("candidate pre_state does not match current inventory state")
        return apply_inventory_reservation(current, str(payload["order_id"]), str(payload["sku"]), int(payload["quantity"]))

    def replay(self, state: InventoryState, receipt: Receipt) -> InventoryState:
        payload = receipt.replay_bundle["candidate_payload"]
        return apply_inventory_reservation(normalize_inventory_state(state), str(payload["order_id"]), str(payload["sku"]), int(payload["quantity"]))

    def rollback(self, state: InventoryState, receipt: Receipt) -> InventoryState:
        return normalize_inventory_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


class InventoryResidualRepairer:
    def __init__(self) -> None:
        self.rejected_residuals: Counter[str] = Counter()
        self.accepted_orders: Counter[str] = Counter()

    def update(self, receipt: Receipt) -> None:
        payload = {}
        if isinstance(receipt.replay_bundle, Mapping):
            candidate_payload = receipt.replay_bundle.get("candidate_payload", {})
            if isinstance(candidate_payload, Mapping):
                payload = candidate_payload
        if receipt.hard_result.accepted:
            self.accepted_orders[str(payload.get("sku", "unknown"))] += 1
            return
        residual = receipt.hard_result.residual
        if receipt.hard_result.rejected and isinstance(residual, Mapping):
            self.rejected_residuals[str(residual.get("kind", "unknown"))] += 1

    def propose(self, candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate | None:
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        quantity = repair.get("quantity")
        if not isinstance(quantity, int) or quantity <= 0:
            return None
        payload = candidate.payload
        return make_reservation_candidate(
            normalize_inventory_state(payload["pre_state"]),
            str(payload["order_id"]),
            str(payload["sku"]),
            int(payload["requested"]),
            quantity,
            context=str(payload.get("context", "inventory-repair")),
            cost=int(payload.get("cost", 1)) + 1,
        )


def normalize_inventory_state(state: InventoryState | Mapping[str, Any]) -> InventoryState:
    if isinstance(state, InventoryState):
        stock = state.stock
        reserved = state.reserved
        committed_orders = state.committed_orders
    else:
        stock = state["stock"]
        reserved = state.get("reserved", {})
        committed_orders = state.get("committed_orders", ())
    stock_out = {str(key): _non_negative_int(value, "stock") for key, value in stock.items()}
    reserved_out = {str(key): _non_negative_int(value, "reserved") for key, value in reserved.items()}
    orders = tuple(str(order_id) for order_id in committed_orders)
    if len(set(orders)) != len(orders):
        raise ValueError("committed_orders must be unique")
    return InventoryState(stock=stock_out, reserved=reserved_out, committed_orders=orders)


def apply_inventory_reservation(state: InventoryState, order_id: str, sku: str, quantity: int) -> InventoryState:
    state = normalize_inventory_state(state)
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    stock = dict(state.stock)
    reserved = dict(state.reserved)
    available = int(stock.get(sku, 0))
    if quantity > available:
        raise ValueError("reservation exceeds available stock")
    stock[sku] = available - quantity
    reserved[sku] = int(reserved.get(sku, 0)) + quantity
    return InventoryState(stock=stock, reserved=reserved, committed_orders=(*state.committed_orders, order_id))


def make_reservation_candidate(
    state: InventoryState,
    order_id: str,
    sku: str,
    requested: int,
    quantity: int,
    context: str = "inventory",
    cost: int = 1,
) -> TypedCandidate:
    state = normalize_inventory_state(state)
    diff = {"stock_delta": -int(quantity), "reserved_delta": int(quantity)}
    return TypedCandidate(
        payload={
            "context": context,
            "pre_state": state,
            "order_id": str(order_id),
            "sku": str(sku),
            "requested": int(requested),
            "quantity": int(quantity),
            "diff": diff,
            "cost": int(cost),
        },
        type_name="ops.inventory_reservation",
        schema_version="ops.inventory_reservation.v1",
        hashes={
            "pre_state": stable_hash(state),
            "order": stable_hash({"order_id": order_id, "sku": sku, "requested": requested, "quantity": quantity}),
            "diff": stable_hash(diff),
        },
    )


def run_static_operations_episode(state: InventoryState, order_id: str, sku: str, requested: int, ledger: Ledger, episode: int) -> OperationsEpisodeResult:
    state = normalize_inventory_state(state)
    engine = TransactionEngine(InventoryReservationAdapter(), ledger=ledger)
    calls = 0
    for quantity in range(requested, 0, -1):
        calls += 1
        candidate = make_reservation_candidate(state, order_id, sku, requested, quantity, context="ops-static", cost=calls)
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"ops-static-{episode}-{quantity}",
                actions=({"order_id": order_id, "sku": sku, "quantity": quantity},),
                seeds=(episode, quantity),
                model_version="ops.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return _episode_result(calls, True, engine, state)
    return _episode_result(calls, False, engine, state)


def run_repair_operations_episode(
    state: InventoryState,
    order_id: str,
    sku: str,
    requested: int,
    ledger: Ledger,
    repairer: InventoryResidualRepairer,
    episode: int,
) -> OperationsEpisodeResult:
    state = normalize_inventory_state(state)
    engine = TransactionEngine(InventoryReservationAdapter(), ledger=ledger)
    candidate = make_reservation_candidate(state, order_id, sku, requested, requested, context="ops-repair", cost=1)
    for attempt in range(3):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"ops-repair-{episode}-{attempt}",
                actions=({"order_id": order_id, "sku": sku, "quantity": candidate.payload["quantity"]},),
                seeds=(episode, attempt),
                model_version="ops.residual_repair.v1",
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


def run_operations_benchmark(seed: int = 31, episodes: int = 48) -> OperationsReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    rng = random.Random(seed)
    static_results: list[OperationsEpisodeResult] = []
    repair_results: list[OperationsEpisodeResult] = []
    static_ledgers: list[Ledger] = []
    repair_ledgers: list[Ledger] = []
    repairer = InventoryResidualRepairer()
    for idx in range(episodes):
        sku = "A" if idx % 2 == 0 else "B"
        available = rng.randint(4, 12)
        requested = available + rng.randint(0, 8)
        state = InventoryState(stock={sku: available}, reserved={sku: 0})
        static_ledger = Ledger()
        repair_ledger = Ledger()
        static_ledgers.append(static_ledger)
        repair_ledgers.append(repair_ledger)
        order_id = f"order-{idx}"
        static_results.append(run_static_operations_episode(state, order_id, sku, requested, static_ledger, idx))
        repair_results.append(run_repair_operations_episode(state, order_id, sku, requested, repair_ledger, repairer, idx))
    static_cps = _calls_per_success(static_results)
    repair_cps = _calls_per_success(repair_results)
    repair_successes = sum(1 for row in repair_results if row.success)
    all_results = (*static_results, *repair_results)
    return OperationsReport(
        episodes=episodes,
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        repair_success_rate=repair_successes / len(repair_results),
        ledger_audit_rate=sum(1 for row in all_results if row.audit_ok) / len(all_results),
        replay_rollback_rate=sum(1 for row in all_results if row.replay_rollback_ok) / len(all_results),
        invalid_commit_count=_invalid_commits((*static_ledgers, *repair_ledgers)),
        learned_residual_kinds=dict(repairer.rejected_residuals),
    )


def _episode_result(calls: int, success: bool, engine: TransactionEngine, seed_state: InventoryState) -> OperationsEpisodeResult:
    audit_ok = engine.ledger.audit()
    replay_rollback_ok = False
    if audit_ok:
        try:
            engine.replay_audit(seed_state)
            replay_rollback_ok = engine.rollback_audit(seed_state) == seed_state
        except Exception:
            replay_rollback_ok = False
    return OperationsEpisodeResult(calls=calls, success=success, audit_ok=audit_ok, replay_rollback_ok=replay_rollback_ok)


def _normalize_diff(diff: Mapping[str, Any], sku: str) -> dict[str, int]:
    _ = sku
    return {"stock_delta": int(diff.get("stock_delta", 0)), "reserved_delta": int(diff.get("reserved_delta", 0))}


def _total_units(state: InventoryState, sku: str) -> int:
    return int(state.stock.get(sku, 0)) + int(state.reserved.get(sku, 0))


def _non_negative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} quantities must be non-negative integers")
    return value


def _calls_per_success(results: Iterable[OperationsEpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
