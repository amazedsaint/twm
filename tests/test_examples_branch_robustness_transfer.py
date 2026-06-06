from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_robustness_transfer import (
    run_branch_robustness_transfer_certified_experiment,
    run_branch_robustness_transfer_experiment,
    validate_branch_robustness_certificate,
    validate_branch_robustness_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchRobustnessTransferExampleTests(unittest.TestCase):
    def test_certified_branch_robustness_transfer(self) -> None:
        result = run_branch_robustness_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_robustness_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_robustness_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 18)
        self.assertEqual(report.total_committed_count, 15)
        self.assertEqual(report.total_rejected_count, 3)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_brittle_success_count, 3)
        self.assertEqual(report.source_robust_variant_success_count, 9)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.robust_success_count, 3)
        self.assertEqual(report.same_budget_robust_count, 3)
        self.assertEqual(report.branch_robustness_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 12)
        self.assertEqual(report.memory_receipt_count, 12)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_robustness_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_robustness_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_robustness_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 18)
        self.assertEqual(len(certificate.branch_robustness_certificate_hashes), 3)
        self.assertEqual(len(result.branch_robustness_certificates), 3)
        self.assertTrue(report.sources)

        for row, robustness in zip(report.rows, result.branch_robustness_certificates):
            self.assertEqual(len(row.variant_ids), 3)
            self.assertEqual(len(row.source_contexts), 4)
            self.assertGreater(row.brittle_source_margin, 0)
            self.assertGreater(row.min_robust_source_margin, 0)
            self.assertEqual(row.min_robust_source_margin, min(row.robust_source_margins))
            self.assertLess(row.static_target_margin, 0)
            self.assertGreater(row.robust_target_margin, 0)
            self.assertEqual(row.source_brittle_committed_count, 1)
            self.assertEqual(row.source_robust_variant_success_count, 3)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.robust_committed)
            self.assertEqual(row.source_verifier_call_count, 4)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.robust_verifier_call_count, 1)
            self.assertEqual(len(row.source_brittle_receipt_hashes), 1)
            self.assertEqual(len(row.source_robust_receipt_hashes), 3)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.robust_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_robustness_certificate(robustness, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_robustness_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.robust_success_count, 3)
        self.assertEqual(report.same_budget_robust_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_robustness_transfer_certified_experiment()
        invalid = replace(
            result.branch_robustness_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_robustness_transfer_certificate(invalid, result.report))

    def test_missing_robust_success_fails_transfer_certificate(self) -> None:
        result = run_branch_robustness_transfer_certified_experiment()
        invalid = replace(
            result.branch_robustness_transfer_certificate,
            robust_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_robustness_transfer_certificate(invalid, result.report))

    def test_tampered_robust_margin_fails(self) -> None:
        result = run_branch_robustness_transfer_certified_experiment()
        invalid = replace(
            result.branch_robustness_certificates[0],
            robust_source_margins=(-0.01, 0.10, 0.11),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_robustness_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
