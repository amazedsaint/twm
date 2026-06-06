from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.experiments.reliability_audit import (
    FLAWED_PRIMARY_ID,
    STRICT_PRIMARY_ID,
    run_reliability_audit_benchmark,
)
from trwm.reliability import (
    VerifierReliabilityMemory,
    validate_verifier_reliability_snapshot,
    wilson_lower_bound,
)


class ReliabilityAuditTests(unittest.TestCase):
    def test_wilson_lower_bound_is_conservative_for_small_clean_sample(self) -> None:
        self.assertAlmostEqual(wilson_lower_bound(3, 0), 0.438493919551, places=12)
        self.assertLess(wilson_lower_bound(1, 2), wilson_lower_bound(3, 0))
        self.assertEqual(wilson_lower_bound(0, 0), 0.0)

    def test_memory_ranks_false_positive_subject_for_audit(self) -> None:
        memory = VerifierReliabilityMemory()
        for _ in range(3):
            memory.update(STRICT_PRIMARY_ID, audited_success=True)
        memory.update(FLAWED_PRIMARY_ID, audited_success=True)
        memory.update(FLAWED_PRIMARY_ID, audited_success=False)
        memory.update(FLAWED_PRIMARY_ID, audited_success=False)

        self.assertEqual(memory.rank_for_audit((STRICT_PRIMARY_ID, FLAWED_PRIMARY_ID))[0], FLAWED_PRIMARY_ID)
        self.assertEqual(memory.select_for_audit((STRICT_PRIMARY_ID, FLAWED_PRIMARY_ID), 1), (FLAWED_PRIMARY_ID,))
        self.assertEqual(memory.score(STRICT_PRIMARY_ID).audited_failures, 0)
        self.assertEqual(memory.score(FLAWED_PRIMARY_ID).audited_failures, 2)

    def test_snapshot_tamper_detection(self) -> None:
        memory = VerifierReliabilityMemory()
        memory.update(FLAWED_PRIMARY_ID, audited_success=False)
        snapshot = memory.snapshot()
        tampered = replace(snapshot, rows=(replace(snapshot.rows[0], audited_failures=0),))

        self.assertTrue(validate_verifier_reliability_snapshot(snapshot))
        self.assertFalse(validate_verifier_reliability_snapshot(tampered))

    def test_reliability_audit_benchmark_metrics(self) -> None:
        report = run_reliability_audit_benchmark()

        self.assertEqual(report.training_receipt_count, 6)
        self.assertEqual(report.strict_successes, 3)
        self.assertEqual(report.strict_failures, 0)
        self.assertEqual(report.flawed_successes, 1)
        self.assertEqual(report.flawed_failures, 2)
        self.assertEqual(report.risk_order[0], FLAWED_PRIMARY_ID)
        self.assertEqual(report.audit_budget, 1)
        self.assertEqual(report.naive_audited_subject, STRICT_PRIMARY_ID)
        self.assertEqual(report.reliability_audited_subject, FLAWED_PRIMARY_ID)
        self.assertFalse(report.naive_false_positive_detected)
        self.assertTrue(report.reliability_false_positive_detected)
        self.assertEqual(report.reliability_residual_kind, "verifier_false_positive")
        self.assertEqual(report.reliability_audit_residual_kind, "stock_shortage")
        self.assertTrue(report.snapshot_valid)
        self.assertTrue(report.tamper_detected)
        self.assertEqual(report.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
