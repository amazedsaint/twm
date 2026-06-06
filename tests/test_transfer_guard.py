from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.experiments.transfer_guard import run_transfer_guard_benchmark
from trwm.transfer import (
    TRANSFER_GUARD_SNAPSHOT_SCHEMA,
    TransferGuardMemory,
    TransferGuardDecision,
    build_transfer_evaluation_certificate,
    transfer_guard_decision_hash,
    transfer_guard_snapshot_hash,
    validate_transfer_evaluation_certificate,
    validate_transfer_guard_decision,
    validate_transfer_guard_snapshot,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
NO_INVALID_COMMITS = 0


class TransferGuardTests(unittest.TestCase):
    def test_guard_blocks_negative_and_admits_positive_transfer_evidence(self) -> None:
        negative = build_transfer_evaluation_certificate(
            claim_id="negative-transfer",
            learner_id="source-policy",
            learner_snapshot_hash=HASH_A,
            source_domains=("source",),
            target_domains=("target",),
            source_receipt_hashes=(HASH_B,),
            target_evaluation_receipt_hashes=(HASH_C,),
            baseline_name="target-baseline",
            transfer_name="source-transfer",
            baseline_success_count=1,
            transfer_success_count=0,
            baseline_verifier_calls=1,
            transfer_verifier_calls=1,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=NO_INVALID_COMMITS,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )
        positive = build_transfer_evaluation_certificate(
            claim_id="positive-transfer",
            learner_id="source-policy",
            learner_snapshot_hash=HASH_A,
            source_domains=("source",),
            target_domains=("other-target",),
            source_receipt_hashes=(HASH_B,),
            target_evaluation_receipt_hashes=(HASH_C,),
            baseline_name="target-baseline",
            transfer_name="source-transfer",
            baseline_success_count=1,
            transfer_success_count=1,
            baseline_verifier_calls=2,
            transfer_verifier_calls=1,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=NO_INVALID_COMMITS,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )
        guard = TransferGuardMemory()
        guard.update(negative)
        guard.update(positive)
        blocked = guard.decide(("source",), "target")
        admitted = guard.decide(("source",), "other-target")
        missing = guard.decide(("source",), "missing-target")
        snapshot = guard.snapshot()
        negative_entry = next(entry for entry in snapshot.entries if entry.target_domain == "target")
        tampered_entries = tuple(
            replace(entry, conclusion="positive_transfer") if entry.target_domain == "target" else entry
            for entry in snapshot.entries
        )
        tampered = replace(snapshot, entries=tampered_entries, snapshot_hash="")
        mismatched_entries = tuple(
            replace(entry, conclusion="positive_transfer") if entry.target_domain == "target" else entry
            for entry in snapshot.entries
        )
        self.assertEqual(negative_entry.conclusion, "negative_transfer")
        mismatched_snapshot = replace(snapshot, entries=mismatched_entries, snapshot_hash="")
        mismatched_snapshot = replace(mismatched_snapshot, snapshot_hash=transfer_guard_snapshot_hash(mismatched_snapshot))
        mismatched_decision = TransferGuardDecision(
            source_domains=("source",),
            target_domain="target",
            admitted=False,
            reason="positive_transfer_certificate",
            conclusion="positive_transfer",
            certificate_hash=negative.certificate_hash,
        )
        mismatched_decision = replace(
            mismatched_decision,
            decision_hash=transfer_guard_decision_hash(mismatched_decision),
        )
        bool_replay_rate = replace(negative, replay_rollback_rate=True)

        self.assertFalse(blocked.admitted)
        self.assertEqual(blocked.reason, "negative_transfer_certificate")
        self.assertTrue(validate_transfer_guard_decision(blocked))
        self.assertTrue(admitted.admitted)
        self.assertEqual(admitted.reason, "positive_transfer_certificate")
        self.assertTrue(validate_transfer_guard_decision(admitted))
        self.assertFalse(missing.admitted)
        self.assertEqual(missing.reason, "no_valid_transfer_certificate")
        self.assertTrue(validate_transfer_guard_decision(missing))
        self.assertEqual(snapshot.schema_version, TRANSFER_GUARD_SNAPSHOT_SCHEMA)
        self.assertTrue(validate_transfer_guard_snapshot(snapshot))
        self.assertFalse(validate_transfer_guard_snapshot(tampered))
        self.assertFalse(validate_transfer_guard_snapshot(mismatched_snapshot))
        self.assertFalse(validate_transfer_guard_decision(mismatched_decision))
        self.assertFalse(validate_transfer_evaluation_certificate(bool_replay_rate))
        with self.assertRaises(ValueError):
            guard.update(replace(negative, transfer_success_count=1))

    def test_transfer_guard_benchmark_blocks_source_policy_and_falls_back(self) -> None:
        report = run_transfer_guard_benchmark()

        self.assertEqual(report.schema_version, TRANSFER_GUARD_SNAPSHOT_SCHEMA)
        self.assertTrue(report.snapshot_valid)
        self.assertTrue(report.decision_valid)
        self.assertTrue(report.guard_blocks_source_policy)
        self.assertFalse(report.guard_decision_admitted)
        self.assertEqual(report.guard_decision_reason, "negative_transfer_certificate")
        self.assertEqual(report.source_selected, ("quantity-5",))
        self.assertEqual(report.unguarded_selected, ("quantity-5",))
        self.assertFalse(report.unguarded_committed)
        self.assertEqual(report.unguarded_residual_kind, "stock_shortage")
        self.assertEqual(report.guarded_selected, ("quantity-2",))
        self.assertTrue(report.guarded_committed)
        self.assertTrue(report.guarded_used_target_baseline)
        self.assertTrue(report.avoided_negative_transfer)
        self.assertEqual(report.certificate_conclusion, "negative_transfer")
        self.assertTrue(report.tamper_detected)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
