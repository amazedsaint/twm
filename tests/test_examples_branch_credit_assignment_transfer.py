from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_credit_assignment_transfer import (
    run_branch_credit_assignment_transfer_certified_experiment,
    run_branch_credit_assignment_transfer_experiment,
    validate_branch_credit_assignment_certificate,
    validate_branch_credit_assignment_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchCreditAssignmentTransferExampleTests(unittest.TestCase):
    def test_certified_branch_credit_assignment_transfer(self) -> None:
        result = run_branch_credit_assignment_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_credit_assignment_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_credit_assignment_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 15)
        self.assertEqual(report.total_committed_count, 12)
        self.assertEqual(report.total_rejected_count, 3)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_success_count, 9)
        self.assertEqual(report.credited_source_count, 3)
        self.assertEqual(report.distractor_source_count, 6)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.credit_success_count, 3)
        self.assertEqual(report.same_budget_credit_count, 3)
        self.assertEqual(report.branch_credit_assignment_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_credit_assignment_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_credit_assignment_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_credit_assignment_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 15)
        self.assertEqual(len(certificate.branch_credit_assignment_certificate_hashes), 3)
        self.assertEqual(len(result.branch_credit_assignment_certificates), 3)
        self.assertTrue(report.sources)

        for row, credit in zip(report.rows, result.branch_credit_assignment_certificates):
            self.assertEqual(len(row.source_actions), 3)
            self.assertEqual(len(row.distractor_actions), 2)
            self.assertNotIn(row.credited_action, row.distractor_actions)
            self.assertEqual(row.credited_credit_value, row.credit_values[0])
            self.assertEqual(row.max_distractor_credit_value, max(row.credit_values[1:]))
            self.assertGreaterEqual(row.credited_credit_value - row.max_distractor_credit_value, row.minimum_credit_gap)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.credit_committed)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.credit_verifier_call_count, 1)
            self.assertEqual(len(row.source_receipt_hashes), 3)
            self.assertEqual(len(row.credited_source_receipt_hashes), 1)
            self.assertEqual(len(row.distractor_source_receipt_hashes), 2)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.credit_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_credit_assignment_certificate(credit, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_credit_assignment_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.credit_success_count, 3)
        self.assertEqual(report.same_budget_credit_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_credit_assignment_transfer_certified_experiment()
        invalid = replace(
            result.branch_credit_assignment_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_credit_assignment_transfer_certificate(invalid, result.report))

    def test_missing_credit_success_fails_transfer_certificate(self) -> None:
        result = run_branch_credit_assignment_transfer_certified_experiment()
        invalid = replace(
            result.branch_credit_assignment_transfer_certificate,
            credit_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_credit_assignment_transfer_certificate(invalid, result.report))

    def test_tampered_credit_certificate_fails(self) -> None:
        result = run_branch_credit_assignment_transfer_certified_experiment()
        invalid = replace(
            result.branch_credit_assignment_certificates[0],
            credit_values=(0.10, 0.92, 0.04),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_credit_assignment_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
