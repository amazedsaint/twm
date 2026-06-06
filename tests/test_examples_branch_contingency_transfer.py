from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_contingency_transfer import (
    run_branch_contingency_transfer_certified_experiment,
    run_branch_contingency_transfer_experiment,
    validate_branch_contingency_certificate,
    validate_branch_contingency_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchContingencyTransferExampleTests(unittest.TestCase):
    def test_certified_branch_contingency_transfer(self) -> None:
        result = run_branch_contingency_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_contingency_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_contingency_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 12)
        self.assertEqual(report.total_committed_count, 9)
        self.assertEqual(report.total_rejected_count, 3)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.contingent_success_count, 3)
        self.assertEqual(report.selected_context_count, 3)
        self.assertEqual(report.rejected_context_count, 3)
        self.assertEqual(report.same_budget_contingency_count, 3)
        self.assertEqual(report.branch_contingency_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 6)
        self.assertEqual(report.memory_receipt_count, 6)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_contingency_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_contingency_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_contingency_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 12)
        self.assertEqual(len(certificate.branch_contingency_certificate_hashes), 3)
        self.assertEqual(len(result.branch_contingency_certificates), 3)

        for row, contingency in zip(report.rows, result.branch_contingency_certificates):
            self.assertNotEqual(row.stale_regime, row.target_regime)
            self.assertEqual(row.selected_source_context, row.matched_source_context)
            self.assertEqual(row.rejected_source_contexts, (row.stale_source_context,))
            self.assertNotEqual(row.stale_action, row.contingent_action)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.contingent_committed)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.contingent_verifier_call_count, 1)
            self.assertEqual(len(row.stale_source_receipt_hashes), 1)
            self.assertEqual(len(row.matched_source_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.contingent_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_contingency_certificate(contingency, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_contingency_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.contingent_success_count, 3)
        self.assertEqual(report.same_budget_contingency_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_contingency_transfer_certified_experiment()
        invalid = replace(
            result.branch_contingency_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_contingency_transfer_certificate(invalid, result.report))

    def test_missing_contingent_success_fails_transfer_certificate(self) -> None:
        result = run_branch_contingency_transfer_certified_experiment()
        invalid = replace(
            result.branch_contingency_transfer_certificate,
            contingent_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_contingency_transfer_certificate(invalid, result.report))

    def test_tampered_contingency_certificate_fails(self) -> None:
        result = run_branch_contingency_transfer_certified_experiment()
        invalid = replace(
            result.branch_contingency_certificates[0],
            selected_source_context_id=result.branch_contingency_certificates[0].stale_source_context_id,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_contingency_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
