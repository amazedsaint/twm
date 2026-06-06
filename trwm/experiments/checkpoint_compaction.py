from __future__ import annotations

from dataclasses import dataclass, replace

from ..checkpoint import (
    CHECKPOINT_SCHEMA,
    audit_compacted_view,
    build_checkpoint,
    replay_from_checkpoint,
    validate_checkpoint,
)
from ..core import GENESIS_HEAD, ProposalTrace, StateSnapshot, TransactionEngine
from ..experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate


CHECKPOINT_END_INDEX = 3


@dataclass(frozen=True)
class CheckpointCompactionReport:
    schema_version: str
    receipt_count: int
    committed_count: int
    checkpoint_receipt_count: int
    checkpoint_committed_count: int
    suffix_receipt_count: int
    full_replay_commits: int
    checkpoint_replay_commits: int
    replay_calls_saved: int
    final_state_hash_equal: bool
    final_head_equal: bool
    checkpoint_valid: bool
    compacted_audit: bool
    tamper_detected: bool
    stale_suffix_rejected: bool
    original_ledger_audit: bool
    invalid_commit_count: int


def run_checkpoint_compaction_benchmark() -> CheckpointCompactionReport:
    seed_state, final_state, engine = _make_checkpoint_ledger()
    adapter = InventoryReservationAdapter()
    checkpoint = build_checkpoint(engine.ledger, adapter, seed_state, end_index=CHECKPOINT_END_INDEX)
    suffix = tuple(engine.ledger.rows[CHECKPOINT_END_INDEX:])
    replay = replay_from_checkpoint(checkpoint, suffix, adapter, expected_final_head=engine.ledger.head)
    full_state = engine.replay_audit(seed_state)
    tampered = replace(checkpoint, checkpoint_state=InventoryState(stock={"widget": 99}, reserved={}, committed_orders=()))
    stale_suffix = (replace(suffix[0], parent_head=GENESIS_HEAD), *suffix[1:])

    full_replay_commits = len(engine.ledger.committed_rows())
    checkpoint_replay_commits = replay.suffix_committed_count
    return CheckpointCompactionReport(
        schema_version=CHECKPOINT_SCHEMA,
        receipt_count=len(engine.ledger.rows),
        committed_count=full_replay_commits,
        checkpoint_receipt_count=checkpoint.receipt_count,
        checkpoint_committed_count=checkpoint.committed_count,
        suffix_receipt_count=replay.suffix_receipt_count,
        full_replay_commits=full_replay_commits,
        checkpoint_replay_commits=checkpoint_replay_commits,
        replay_calls_saved=full_replay_commits - checkpoint_replay_commits,
        final_state_hash_equal=StateSnapshot.capture(replay.state).state_hash == StateSnapshot.capture(full_state).state_hash
        and StateSnapshot.capture(replay.state).state_hash == StateSnapshot.capture(final_state).state_hash,
        final_head_equal=replay.head == engine.ledger.head,
        checkpoint_valid=validate_checkpoint(checkpoint),
        compacted_audit=audit_compacted_view(checkpoint, suffix, adapter, expected_final_head=engine.ledger.head),
        tamper_detected=not validate_checkpoint(tampered),
        stale_suffix_rejected=not audit_compacted_view(checkpoint, stale_suffix, adapter, expected_final_head=engine.ledger.head),
        original_ledger_audit=engine.ledger.audit(),
        invalid_commit_count=engine.invalid_commit_count,
    )


def _make_checkpoint_ledger() -> tuple[InventoryState, InventoryState, TransactionEngine]:
    seed_state = InventoryState(stock={"widget": 10}, reserved={"widget": 0})
    state = seed_state
    engine = TransactionEngine(InventoryReservationAdapter())
    specs = (
        ("order-1", 2, 2),
        ("order-too-large", 12, 12),
        ("order-2", 3, 3),
        ("order-2", 1, 1),
        ("order-3", 1, 1),
        ("order-4", 2, 2),
    )
    for idx, (order_id, requested, quantity) in enumerate(specs):
        candidate = make_reservation_candidate(
            state,
            order_id,
            "widget",
            requested=requested,
            quantity=quantity,
            context="checkpoint-compaction",
        )
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"checkpoint-compaction-{idx}",
                actions=({"order_id": order_id, "quantity": quantity},),
                seeds=("checkpoint", idx),
                model_version="checkpoint.compaction.v1",
            ),
            candidate,
        )
        state = outcome.state
    return seed_state, state, engine
