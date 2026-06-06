from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_calibration_transfer import (
    run_branch_calibration_transfer_certified_experiment,
    run_branch_calibration_transfer_experiment,
    validate_branch_calibration_certificate,
    validate_branch_calibration_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchCalibrationTransferExampleTests(unittest.TestCase):
    def test_certified_branch_calibration_transfer(self) -> None:
        result = run_branch_calibration_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_calibration_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_calibration_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 18)
        self.assertEqual(report.total_committed_count, 9)
        self.assertEqual(report.total_rejected_count, 9)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_overconfident_rejected_count, 3)
        self.assertEqual(report.source_calibrated_committed_count, 6)
        self.assertEqual(report.source_calibrated_rejected_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.calibrated_success_count, 3)
        self.assertEqual(report.same_budget_calibrated_count, 3)
        self.assertEqual(report.branch_calibration_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 12)
        self.assertEqual(report.memory_receipt_count, 12)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_calibration_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_calibration_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_calibration_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 18)
        self.assertEqual(len(certificate.branch_calibration_certificate_hashes), 3)
        self.assertEqual(len(result.branch_calibration_certificates), 3)
        self.assertTrue(report.sources)

        for row, calibration in zip(report.rows, result.branch_calibration_certificates):
            self.assertEqual(len(row.overconfident_source_actions), 1)
            self.assertEqual(len(row.calibrated_source_actions), 3)
            self.assertEqual(row.overconfident_empirical_accept_rate, 0.0)
            self.assertAlmostEqual(row.calibrated_empirical_accept_rate, 2.0 / 3.0, places=6)
            self.assertGreaterEqual(row.overconfident_calibration_gap, 0.90)
            self.assertLessEqual(row.calibrated_calibration_gap, 1e-6)
            self.assertEqual(row.source_expected_calibration_error, 0.2375)
            self.assertEqual(row.overconfident_source_rejected_count, 1)
            self.assertEqual(row.calibrated_source_committed_count, 2)
            self.assertEqual(row.calibrated_source_rejected_count, 1)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.calibrated_committed)
            self.assertEqual(row.source_verifier_call_count, 4)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.calibrated_verifier_call_count, 1)
            self.assertEqual(len(row.overconfident_source_receipt_hashes), 1)
            self.assertEqual(len(row.calibrated_source_receipt_hashes), 3)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.calibrated_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_calibration_certificate(calibration, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_calibration_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.calibrated_success_count, 3)
        self.assertEqual(report.same_budget_calibrated_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_calibration_transfer_certified_experiment()
        invalid = replace(
            result.branch_calibration_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_calibration_transfer_certificate(invalid, result.report))

    def test_missing_calibrated_success_fails_transfer_certificate(self) -> None:
        result = run_branch_calibration_transfer_certified_experiment()
        invalid = replace(
            result.branch_calibration_transfer_certificate,
            calibrated_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_calibration_transfer_certificate(invalid, result.report))

    def test_tampered_calibration_gap_fails(self) -> None:
        result = run_branch_calibration_transfer_certified_experiment()
        invalid = replace(
            result.branch_calibration_certificates[0],
            calibrated_calibration_gap=0.25,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_calibration_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
