from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.checkpoint import (
    CHECKPOINT_SCHEMA,
    audit_compacted_view,
    build_checkpoint,
    replay_from_checkpoint,
    validate_checkpoint,
)
from trwm.core import GENESIS_HEAD, ProposalTrace, StateSnapshot, TransactionEngine
from trwm.experiments.checkpoint_compaction import CHECKPOINT_END_INDEX, run_checkpoint_compaction_benchmark
from trwm.experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate


class CheckpointCompactionTests(unittest.TestCase):
    def test_checkpoint_replays_suffix_to_same_head_and_state(self) -> None:
        seed_state, final_state, engine = self._ledger()
        adapter = InventoryReservationAdapter()
        checkpoint = build_checkpoint(engine.ledger, adapter, seed_state, end_index=CHECKPOINT_END_INDEX)
        suffix = tuple(engine.ledger.rows[CHECKPOINT_END_INDEX:])
        replay = replay_from_checkpoint(checkpoint, suffix, adapter, expected_final_head=engine.ledger.head)

        self.assertEqual(checkpoint.schema_version, CHECKPOINT_SCHEMA)
        self.assertTrue(validate_checkpoint(checkpoint))
        self.assertEqual(replay.head, engine.ledger.head)
        self.assertEqual(StateSnapshot.capture(replay.state).state_hash, StateSnapshot.capture(final_state).state_hash)
        self.assertEqual(replay.suffix_committed_count, 2)
        self.assertTrue(audit_compacted_view(checkpoint, suffix, adapter, expected_final_head=engine.ledger.head))

    def test_checkpoint_detects_tamper_and_stale_suffix(self) -> None:
        seed_state, _final_state, engine = self._ledger()
        adapter = InventoryReservationAdapter()
        checkpoint = build_checkpoint(engine.ledger, adapter, seed_state, end_index=CHECKPOINT_END_INDEX)
        suffix = tuple(engine.ledger.rows[CHECKPOINT_END_INDEX:])
        tampered = replace(checkpoint, checkpoint_state=InventoryState(stock={"widget": 99}, reserved={}, committed_orders=()))
        stale_suffix = (replace(suffix[0], parent_head=GENESIS_HEAD), *suffix[1:])

        self.assertFalse(validate_checkpoint(tampered))
        self.assertFalse(audit_compacted_view(checkpoint, stale_suffix, adapter, expected_final_head=engine.ledger.head))

    def test_checkpoint_requires_audited_ledger_and_matching_adapter(self) -> None:
        seed_state, _final_state, engine = self._ledger()
        engine.ledger.rows[0] = replace(engine.ledger.rows[0], commit_decision="hard_reject")

        with self.assertRaises(ValueError):
            build_checkpoint(engine.ledger, InventoryReservationAdapter(), seed_state, end_index=CHECKPOINT_END_INDEX)

    def test_checkpoint_compaction_benchmark(self) -> None:
        report = run_checkpoint_compaction_benchmark()

        self.assertEqual(report.schema_version, CHECKPOINT_SCHEMA)
        self.assertEqual(report.receipt_count, 6)
        self.assertEqual(report.committed_count, 4)
        self.assertEqual(report.checkpoint_receipt_count, 3)
        self.assertEqual(report.checkpoint_committed_count, 2)
        self.assertEqual(report.suffix_receipt_count, 3)
        self.assertEqual(report.full_replay_commits, 4)
        self.assertEqual(report.checkpoint_replay_commits, 2)
        self.assertEqual(report.replay_calls_saved, 2)
        self.assertTrue(report.final_state_hash_equal)
        self.assertTrue(report.final_head_equal)
        self.assertTrue(report.checkpoint_valid)
        self.assertTrue(report.compacted_audit)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.stale_suffix_rejected)
        self.assertTrue(report.original_ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)

    def _ledger(self):
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
            outcome = engine.transact(
                state,
                ProposalTrace(
                    branch_id=f"checkpoint-test-{idx}",
                    actions=({"order_id": order_id, "quantity": quantity},),
                    seeds=("checkpoint-test", idx),
                    model_version="checkpoint.test.v1",
                ),
                make_reservation_candidate(state, order_id, "widget", requested, quantity, context="checkpoint-test"),
            )
            state = outcome.state
        return seed_state, state, engine


if __name__ == "__main__":
    unittest.main()
