from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_sensitivity_transfer import (
    run_branch_sensitivity_transfer_certified_experiment,
    run_branch_sensitivity_transfer_experiment,
    validate_branch_sensitivity_certificate,
    validate_branch_sensitivity_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchSensitivityTransferExampleTests(unittest.TestCase):
    def test_certified_branch_sensitivity_transfer(self) -> None:
        result = run_branch_sensitivity_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_sensitivity_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_sensitivity_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 12)
        self.assertEqual(report.total_committed_count, 6)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_negative_rejected_count, 3)
        self.assertEqual(report.source_positive_committed_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.sensitivity_success_count, 3)
        self.assertEqual(report.same_budget_sensitivity_count, 3)
        self.assertEqual(report.branch_sensitivity_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 6)
        self.assertEqual(report.memory_receipt_count, 6)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_sensitivity_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_sensitivity_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_sensitivity_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 12)
        self.assertEqual(len(certificate.branch_sensitivity_certificate_hashes), 3)
        self.assertEqual(len(result.branch_sensitivity_certificates), 3)
        self.assertIn("https://doi.org/10.1080/00401706.1991.10484804", report.sources)
        self.assertIn("https://doi.org/10.1109/9.119632", report.sources)

        for row, sensitivity in zip(report.rows, result.branch_sensitivity_certificates):
            self.assertLess(row.source_negative_value, row.baseline_value)
            self.assertLess(row.static_target_value, row.baseline_value)
            self.assertGreater(row.source_positive_value, row.baseline_value)
            self.assertGreater(row.sensitivity_target_value, row.baseline_value)
            self.assertTrue(row.source_negative_rejected)
            self.assertTrue(row.source_positive_committed)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.sensitivity_committed)
            self.assertEqual(row.source_verifier_call_count, 2)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.sensitivity_verifier_call_count, 1)
            self.assertEqual(len(row.source_negative_receipt_hashes), 1)
            self.assertEqual(len(row.source_positive_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.sensitivity_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_sensitivity_certificate(sensitivity, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_sensitivity_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.sensitivity_success_count, 3)
        self.assertEqual(report.same_budget_sensitivity_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_sensitivity_transfer_certified_experiment()
        invalid = replace(
            result.branch_sensitivity_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_sensitivity_transfer_certificate(invalid, result.report))

    def test_missing_sensitivity_success_fails_transfer_certificate(self) -> None:
        result = run_branch_sensitivity_transfer_certified_experiment()
        invalid = replace(
            result.branch_sensitivity_transfer_certificate,
            sensitivity_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_sensitivity_transfer_certificate(invalid, result.report))

    def test_tampered_perturbation_fails(self) -> None:
        result = run_branch_sensitivity_transfer_certified_experiment()
        invalid = replace(
            result.branch_sensitivity_certificates[0],
            perturbation_delta=0.20,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_sensitivity_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
