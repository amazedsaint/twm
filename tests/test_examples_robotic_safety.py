from __future__ import annotations

import unittest

from examples.robotic_safety_envelope import run_robotic_safety_envelope_experiment


class TestRoboticSafetyEnvelopeExample(unittest.TestCase):
    def test_robotic_safety_envelope_uses_transactional_hard_gates(self) -> None:
        report = run_robotic_safety_envelope_experiment()

        self.assertEqual(report.schema_version, "trwm.example.robotic_safety_envelope.v1")
        self.assertEqual(report.first_decision, "hard_reject")
        self.assertEqual(report.first_residual_kind, "collision")
        self.assertTrue(report.soft_score_trap_blocked)
        self.assertEqual(report.repaired_decision, "commit")
        self.assertTrue(report.repaired_committed)
        self.assertGreaterEqual(report.repaired_min_clearance, 0)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.receipt_count, 2)
        self.assertEqual(report.committed_count, 1)
        self.assertEqual(len(report.receipt_hashes), 2)
        self.assertTrue(report.sdk_manifest_valid)
        self.assertTrue(report.sdk_manifest_audit_ok)
        self.assertEqual(report.sdk_hard_verifier_calls, 1)
        self.assertEqual(report.learned_residual_kinds, {"collision": 1})
