from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.claims import certify_claim, requirement, validate_claim_certificate
from trwm.experiments.claim_audit import run_claim_audit_benchmark


class ClaimAuditTests(unittest.TestCase):
    def test_claim_certificate_supports_only_when_all_requirements_pass(self) -> None:
        supported = certify_claim(
            claim_id="unit_supported",
            claim_text="unit claim",
            evidence_grade="G1",
            scope="unit",
            requirements=(requirement("a", True), requirement("b", True)),
            metrics={"invalid_commit_count": 0},
            boundary="unit boundary",
        )
        rejected = certify_claim(
            claim_id="unit_rejected",
            claim_text="unit overclaim",
            evidence_grade="G1",
            scope="unit",
            requirements=(requirement("a", True), requirement("b", False, reason="missing evidence")),
            metrics={"invalid_commit_count": 0},
            boundary="unit boundary",
        )

        self.assertEqual(supported.status, "supported")
        self.assertEqual(supported.failed_keys, ())
        self.assertTrue(validate_claim_certificate(supported))
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.failed_keys, ("b",))
        self.assertTrue(validate_claim_certificate(rejected))

    def test_claim_certificate_detects_tampering(self) -> None:
        certificate = certify_claim(
            claim_id="unit_tamper",
            claim_text="unit claim",
            evidence_grade="G1",
            scope="unit",
            requirements=(requirement("a", True),),
        )
        tampered = replace(certificate, metrics={"invalid_commit_count": 1})

        self.assertTrue(validate_claim_certificate(certificate))
        self.assertFalse(validate_claim_certificate(tampered))

    def test_claim_audit_benchmark_supports_boundary_and_rejects_overclaim(self) -> None:
        report = run_claim_audit_benchmark()

        self.assertEqual(report.supported_claim_id, "g1_learning_claim_boundary")
        self.assertEqual(report.supported_status, "supported")
        self.assertEqual(report.supported_failed_keys, ())
        self.assertEqual(report.supported_requirement_count, 28)
        self.assertEqual(report.rejected_claim_id, "rrlm_reversibility_alone_lift_overclaim")
        self.assertEqual(report.rejected_status, "rejected")
        self.assertEqual(report.rejected_failed_keys, ("matched_non_reversible_lift",))
        self.assertTrue(report.overclaim_detected)
        self.assertTrue(report.null_result_recorded)
        self.assertTrue(report.mechanism_ablation_recorded)
        self.assertTrue(report.heldout_trace_evaluation)
        self.assertTrue(report.same_case_equal_budget)
        self.assertTrue(report.verifier_call_accounting)
        self.assertTrue(report.learning_evaluation_certificate_valid)
        self.assertTrue(report.learning_evaluation_supports_claim)
        self.assertTrue(report.transfer_evaluation_certificate_valid)
        self.assertTrue(report.transfer_positive_overclaim_rejected)
        self.assertTrue(report.transfer_guard_snapshot_valid)
        self.assertTrue(report.transfer_guard_blocks_negative_transfer)
        self.assertTrue(report.rrlm_proposal_certificate_valid)
        self.assertTrue(report.rrlm_transport_certificate_valid)
        self.assertTrue(report.world_learner_update_certificate_valid)
        self.assertTrue(report.world_learner_delta_certificate_valid)
        self.assertTrue(report.world_learner_lineage_certificate_valid)
        self.assertTrue(report.world_learner_merge_certificate_valid)
        self.assertTrue(report.world_learner_partial_overlap_merge_valid)
        self.assertTrue(report.world_rrlm_proposal_certificate_valid)
        self.assertTrue(report.world_program_certificate_valid)
        self.assertTrue(report.world_program_admission_certificate_valid)
        self.assertTrue(report.world_program_bundle_verification_certificate_valid)
        self.assertTrue(report.world_program_replay_verification_certificate_valid)
        self.assertTrue(report.supported_certificate_valid)
        self.assertTrue(report.rejected_certificate_valid)
        self.assertTrue(report.tamper_detected)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(len(report.supported_certificate_hash), 64)
        self.assertEqual(len(report.rejected_certificate_hash), 64)


if __name__ == "__main__":
    unittest.main()
