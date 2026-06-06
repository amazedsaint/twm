from __future__ import annotations

from dataclasses import dataclass, replace

from ..core import ProposalTrace, TransactionEngine, stable_hash
from ..sdk import (
    TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA,
    ProgrammableSubstrate,
    TransferGuardedDomainRouter,
    transfer_guarded_domain_route_hash,
    validate_transfer_guarded_domain_route,
)
from ..transfer import build_transfer_evaluation_certificate, validate_transfer_guard_snapshot
from .operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate


@dataclass(frozen=True)
class SdkTransferGuardReport:
    schema_version: str
    route_valid: bool
    snapshot_valid: bool
    base_router_top_domain: str
    guarded_router_top_domain: str
    base_ranked_domain_ids: tuple[str, ...]
    guarded_ranked_domain_ids: tuple[str, ...]
    blocked_domain_ids: tuple[str, ...]
    source_blocked: bool
    guard_reordered_to_target: bool
    decision_reason: str
    decision_admitted: bool
    unguarded_selected: str
    unguarded_committed: bool
    unguarded_residual_kind: str
    guarded_selected: str
    guarded_committed: bool
    avoided_negative_transfer: bool
    certificate_conclusion: str
    route_hash: str
    decision_hash: str
    snapshot_hash: str
    tamper_detected: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float


def run_sdk_transfer_guard_benchmark() -> SdkTransferGuardReport:
    router = TransferGuardedDomainRouter()
    substrate = ProgrammableSubstrate(router=router)
    substrate.register("source_policy", InventoryReservationAdapter())
    substrate.register("target_policy", InventoryReservationAdapter())

    source_seed = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
    target_seed = InventoryState(stock={"widget": 2}, reserved={"widget": 0})
    source_receipt = substrate.submit(
        "source_policy",
        source_seed,
        ProposalTrace(
            branch_id="sdk-transfer-source-policy",
            actions=({"label": "quantity-5"},),
            seeds=("sdk-transfer", "source"),
            model_version="sdk.transfer.source.v1",
        ),
        make_reservation_candidate(source_seed, "sdk-transfer-source-q5", "widget", 5, 5, context="sdk-transfer", cost=1),
        context="sdk-transfer",
    ).receipt

    base_ranked = tuple(router.rank("sdk-transfer", ("source_policy", "target_policy")))

    eval_transfer_engine = TransactionEngine(InventoryReservationAdapter())
    eval_transfer = eval_transfer_engine.transact(
        target_seed,
        ProposalTrace(
            branch_id="sdk-transfer-eval-source-policy",
            actions=({"label": "quantity-5"},),
            seeds=("sdk-transfer", "eval-source"),
            model_version="sdk.transfer.eval_source.v1",
        ),
        make_reservation_candidate(target_seed, "sdk-transfer-eval-q5", "widget", 5, 5, context="sdk-transfer-eval", cost=1),
    )
    eval_baseline_engine = TransactionEngine(InventoryReservationAdapter())
    eval_baseline = eval_baseline_engine.transact(
        target_seed,
        ProposalTrace(
            branch_id="sdk-transfer-eval-target-policy",
            actions=({"label": "quantity-2"},),
            seeds=("sdk-transfer", "eval-target"),
            model_version="sdk.transfer.eval_target.v1",
        ),
        make_reservation_candidate(target_seed, "sdk-transfer-eval-q2", "widget", 5, 2, context="sdk-transfer-eval", cost=1),
    )
    certificate = build_transfer_evaluation_certificate(
        claim_id="sdk_transfer_guard_blocks_source_policy",
        learner_id="sdk_receipt_router_source_policy",
        learner_snapshot_hash=stable_hash({"source_policy_receipt": source_receipt.receipt_hash}),
        source_domains=("source_policy",),
        target_domains=("target_inventory",),
        source_receipt_hashes=(source_receipt.receipt_hash,),
        target_evaluation_receipt_hashes=(eval_transfer.receipt.receipt_hash, eval_baseline.receipt.receipt_hash),
        baseline_name="target_policy_quantity_2",
        transfer_name="source_policy_quantity_5",
        baseline_success_count=1 if eval_baseline.committed else 0,
        transfer_success_count=1 if eval_transfer.committed else 0,
        baseline_verifier_calls=eval_baseline_engine.hard_verifier_calls,
        transfer_verifier_calls=eval_transfer_engine.hard_verifier_calls,
        same_case_baseline=True,
        hard_commit_only=all(
            receipt.committed == receipt.hard_result.accepted
            for receipt in (source_receipt, eval_transfer.receipt, eval_baseline.receipt)
        ),
        invalid_commit_count=(
            substrate.invalid_commit_count()
            + eval_transfer_engine.invalid_commit_count
            + eval_baseline_engine.invalid_commit_count
        ),
        ledger_audit=(
            substrate.domains["source_policy"].ledger.audit()
            and eval_transfer_engine.ledger.audit()
            and eval_baseline_engine.ledger.audit()
        ),
        replay_rollback_rate=_replay_rollback_rate(
            (
                (TransactionEngine(InventoryReservationAdapter(), ledger=substrate.domains["source_policy"].ledger), source_seed),
                (eval_transfer_engine, target_seed),
                (eval_baseline_engine, target_seed),
            )
        ),
    )
    router.update_transfer_certificate(certificate)
    route = router.rank_with_transfer_guard(
        "sdk-transfer",
        ("source_policy", "target_policy"),
        ("source_policy",),
        "target_inventory",
    )
    snapshot = router.guard_snapshot()
    tampered = replace(route, blocked_domain_ids=(), source_blocked=False, route_hash="")
    tampered = replace(tampered, route_hash=transfer_guarded_domain_route_hash(tampered))

    unguarded_engine = TransactionEngine(InventoryReservationAdapter())
    unguarded_selected = _selection_for_domain(base_ranked[0])
    unguarded = unguarded_engine.transact(
        target_seed,
        ProposalTrace(
            branch_id="sdk-transfer-unguarded",
            actions=({"label": unguarded_selected},),
            seeds=("sdk-transfer", "unguarded"),
            model_version="sdk.transfer.unguarded.v1",
        ),
        _candidate_for_selection(target_seed, "sdk-transfer-unguarded", unguarded_selected),
    )
    guarded_engine = TransactionEngine(InventoryReservationAdapter())
    guarded_selected = _selection_for_domain(route.top_domain_id)
    guarded = guarded_engine.transact(
        target_seed,
        ProposalTrace(
            branch_id="sdk-transfer-guarded",
            actions=({"label": guarded_selected},),
            seeds=("sdk-transfer", "guarded"),
            model_version="sdk.transfer.guarded.v1",
        ),
        _candidate_for_selection(target_seed, "sdk-transfer-guarded", guarded_selected),
    )
    residual = unguarded.receipt.hard_result.residual
    residual_kind = residual.get("kind", "") if isinstance(residual, dict) else ""
    ledger_audit = all(
        engine.ledger.audit()
        for engine in (eval_transfer_engine, eval_baseline_engine, unguarded_engine, guarded_engine)
    ) and substrate.domains["source_policy"].ledger.audit()
    replay_rollback_rate = _replay_rollback_rate(
        (
            (TransactionEngine(InventoryReservationAdapter(), ledger=substrate.domains["source_policy"].ledger), source_seed),
            (eval_transfer_engine, target_seed),
            (eval_baseline_engine, target_seed),
            (unguarded_engine, target_seed),
            (guarded_engine, target_seed),
        )
    )
    return SdkTransferGuardReport(
        schema_version=TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA,
        route_valid=validate_transfer_guarded_domain_route(route),
        snapshot_valid=validate_transfer_guard_snapshot(snapshot),
        base_router_top_domain=base_ranked[0],
        guarded_router_top_domain=route.top_domain_id,
        base_ranked_domain_ids=base_ranked,
        guarded_ranked_domain_ids=route.ranked_domain_ids,
        blocked_domain_ids=route.blocked_domain_ids,
        source_blocked=route.source_blocked,
        guard_reordered_to_target=base_ranked[0] == "source_policy" and route.top_domain_id == "target_policy",
        decision_reason=route.decision_reason,
        decision_admitted=route.decision_admitted,
        unguarded_selected=unguarded_selected,
        unguarded_committed=unguarded.committed,
        unguarded_residual_kind=residual_kind,
        guarded_selected=guarded_selected,
        guarded_committed=guarded.committed,
        avoided_negative_transfer=(not unguarded.committed and guarded.committed and route.top_domain_id == "target_policy"),
        certificate_conclusion=certificate.conclusion,
        route_hash=route.route_hash,
        decision_hash=route.decision_hash,
        snapshot_hash=snapshot.snapshot_hash,
        tamper_detected=not validate_transfer_guarded_domain_route(tampered),
        invalid_commit_count=(
            substrate.invalid_commit_count()
            + eval_transfer_engine.invalid_commit_count
            + eval_baseline_engine.invalid_commit_count
            + unguarded_engine.invalid_commit_count
            + guarded_engine.invalid_commit_count
        ),
        ledger_audit=ledger_audit,
        replay_rollback_rate=replay_rollback_rate,
    )


def _selection_for_domain(domain_id: str) -> str:
    return "quantity-5" if domain_id == "source_policy" else "quantity-2"


def _candidate_for_selection(state: InventoryState, prefix: str, selection: str):
    quantity = 5 if selection == "quantity-5" else 2
    return make_reservation_candidate(state, f"{prefix}-{selection}", "widget", 5, quantity, context="sdk-transfer", cost=1)


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
