from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_counterfactual_transfer import (
    run_branch_counterfactual_transfer_certified_experiment,
    run_branch_counterfactual_transfer_experiment,
    validate_branch_counterfactual_certificate,
    validate_branch_counterfactual_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchCounterfactualTransferExampleTests(unittest.TestCase):
    def test_certified_branch_counterfactual_transfer(self) -> None:
        result = run_branch_counterfactual_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_counterfactual_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_counterfactual_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 15)
        self.assertEqual(report.total_committed_count, 6)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 3)
        self.assertEqual(report.stale_winner_success_count, 0)
        self.assertEqual(report.counterfactual_success_count, 3)
        self.assertEqual(report.rolled_back_counterfactual_count, 3)
        self.assertEqual(report.same_budget_comparison_count, 3)
        self.assertEqual(report.counterfactual_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_counterfactual_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_counterfactual_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_counterfactual_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 9)
        self.assertEqual(len(certificate.branch_counterfactual_certificate_hashes), 3)
        self.assertEqual(len(result.branch_counterfactual_certificates), 3)

        for row, counterfactual in zip(report.rows, result.branch_counterfactual_certificates):
            self.assertNotEqual(row.source_winner_action, row.counterfactual_action)
            self.assertEqual(row.stale_target_action, row.source_winner_action)
            self.assertFalse(row.stale_winner_committed)
            self.assertTrue(row.counterfactual_committed)
            self.assertEqual(row.source_rolled_back_counterfactual_count, 1)
            self.assertEqual(row.stale_verifier_call_count, 1)
            self.assertEqual(row.counterfactual_verifier_call_count, 1)
            self.assertEqual(len(row.source_receipt_hashes), 3)
            self.assertEqual(len(row.source_committed_receipt_hashes), 1)
            self.assertEqual(len(row.source_rolled_back_receipt_hashes), 1)
            self.assertEqual(len(row.stale_target_receipt_hashes), 1)
            self.assertEqual(len(row.counterfactual_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_counterfactual_certificate(counterfactual, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_counterfactual_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.stale_winner_success_count, 0)
        self.assertEqual(report.counterfactual_success_count, 3)
        self.assertEqual(report.rolled_back_counterfactual_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_counterfactual_transfer_certified_experiment()
        invalid = replace(
            result.branch_counterfactual_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_counterfactual_transfer_certificate(invalid, result.report))

    def test_missing_counterfactual_rollbacks_fail_transfer_certificate(self) -> None:
        result = run_branch_counterfactual_transfer_certified_experiment()
        invalid = replace(
            result.branch_counterfactual_transfer_certificate,
            rolled_back_counterfactual_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_counterfactual_transfer_certificate(invalid, result.report))

    def test_tampered_counterfactual_certificate_fails(self) -> None:
        result = run_branch_counterfactual_transfer_certified_experiment()
        invalid = replace(
            result.branch_counterfactual_certificates[0],
            source_has_rolled_back_counterfactual=False,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_counterfactual_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
