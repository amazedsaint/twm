from __future__ import annotations

import unittest

from examples.common import validate_example_evidence_certificate
from examples.robotic_safety_envelope import (
    ROBOTIC_SAFETY_SOURCES,
    run_robotic_safety_envelope_certified_experiment,
    run_robotic_safety_envelope_experiment,
)
from trwm.claims import validate_claim_certificate


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
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.receipt_count, 2)
        self.assertEqual(report.committed_count, 1)
        self.assertEqual(len(report.receipt_hashes), 2)
        self.assertTrue(report.sdk_manifest_valid)
        self.assertTrue(report.sdk_manifest_audit_ok)
        self.assertEqual(report.sdk_hard_verifier_calls, 1)
        self.assertEqual(report.learned_residual_kinds, {"collision": 1})

    def test_robotic_safety_envelope_certified_result(self) -> None:
        result = run_robotic_safety_envelope_certified_experiment()
        report = result.report
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.experiment_id, report.experiment_id)
        self.assertEqual(evidence.domain, "robotics")
        self.assertEqual(evidence.evidence_grade, "G1")
        self.assertEqual(evidence.receipt_count, report.receipt_count)
        self.assertEqual(evidence.receipt_hashes, report.receipt_hashes)
        self.assertEqual(evidence.committed_count, report.committed_count)
        self.assertEqual(evidence.rejected_count, report.rejected_count)
        self.assertEqual(evidence.sources, ROBOTIC_SAFETY_SOURCES)
        self.assertIn("signed_distance_clearance", evidence.hard_gate_keys)
        self.assertEqual(evidence.residual_kinds, ("collision",))
