from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_confidence_transfer import (
    CONFIDENCE_Z,
    run_branch_confidence_transfer_certified_experiment,
    run_branch_confidence_transfer_experiment,
    validate_branch_confidence_certificate,
    validate_branch_confidence_transfer_certificate,
    wilson_lower_bound,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchConfidenceTransferExampleTests(unittest.TestCase):
    def test_certified_branch_confidence_transfer(self) -> None:
        result = run_branch_confidence_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_confidence_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_confidence_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 18)
        self.assertEqual(report.total_committed_count, 15)
        self.assertEqual(report.total_rejected_count, 3)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.optimistic_source_commit_count, 3)
        self.assertEqual(report.supported_source_commit_count, 9)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.confidence_success_count, 3)
        self.assertEqual(report.same_budget_confidence_count, 3)
        self.assertEqual(report.branch_confidence_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 6)
        self.assertEqual(report.memory_receipt_count, 12)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_confidence_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_confidence_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_confidence_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 18)
        self.assertEqual(len(certificate.branch_confidence_certificate_hashes), 3)
        self.assertEqual(len(result.branch_confidence_certificates), 3)
        self.assertTrue(report.sources)

        expected_optimistic = wilson_lower_bound(1, 1, CONFIDENCE_Z)
        expected_supported = wilson_lower_bound(3, 3, CONFIDENCE_Z)
        self.assertLess(expected_optimistic, expected_supported)

        for row, confidence in zip(report.rows, result.branch_confidence_certificates):
            self.assertNotEqual(row.optimistic_action, row.supported_action)
            self.assertEqual(row.optimistic_support_count, 1)
            self.assertEqual(row.supported_support_count, 3)
            self.assertAlmostEqual(row.optimistic_lower_bound, expected_optimistic)
            self.assertAlmostEqual(row.supported_lower_bound, expected_supported)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.confidence_committed)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.confidence_verifier_call_count, 1)
            self.assertEqual(len(row.optimistic_source_commit_receipt_hashes), 1)
            self.assertEqual(len(row.supported_source_commit_receipt_hashes), 3)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.confidence_target_receipt_hashes), 1)
            self.assertEqual(len(row.branch_selection_certificate_hashes), 6)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_confidence_certificate(confidence, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_confidence_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.confidence_success_count, 3)
        self.assertEqual(report.same_budget_confidence_count, 3)

    def test_wilson_lower_bound_orders_thin_and_supported_evidence(self) -> None:
        thin = wilson_lower_bound(1, 1, CONFIDENCE_Z)
        supported = wilson_lower_bound(3, 3, CONFIDENCE_Z)

        self.assertEqual(thin, 0.5)
        self.assertEqual(supported, 0.75)
        self.assertLess(thin, supported)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_confidence_transfer_certified_experiment()
        invalid = replace(
            result.branch_confidence_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_confidence_transfer_certificate(invalid, result.report))

    def test_missing_confidence_success_fails_transfer_certificate(self) -> None:
        result = run_branch_confidence_transfer_certified_experiment()
        invalid = replace(
            result.branch_confidence_transfer_certificate,
            confidence_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_confidence_transfer_certificate(invalid, result.report))

    def test_tampered_confidence_certificate_fails(self) -> None:
        result = run_branch_confidence_transfer_certified_experiment()
        invalid = replace(
            result.branch_confidence_certificates[0],
            supported_lower_bound=result.branch_confidence_certificates[0].optimistic_lower_bound,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_confidence_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
