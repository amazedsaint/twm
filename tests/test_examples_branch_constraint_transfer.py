from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_constraint_transfer import (
    run_branch_constraint_transfer_certified_experiment,
    run_branch_constraint_transfer_experiment,
    validate_branch_constraint_certificate,
    validate_branch_constraint_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchConstraintTransferExampleTests(unittest.TestCase):
    def test_certified_branch_constraint_transfer(self) -> None:
        result = run_branch_constraint_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_constraint_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_constraint_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 12)
        self.assertEqual(report.total_committed_count, 6)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_incompatible_reject_count, 3)
        self.assertEqual(report.source_compatible_commit_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.constraint_success_count, 3)
        self.assertEqual(report.same_budget_constraint_count, 3)
        self.assertEqual(report.branch_constraint_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 6)
        self.assertEqual(report.memory_receipt_count, 6)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_constraint_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_constraint_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_constraint_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 9)
        self.assertEqual(len(certificate.branch_constraint_certificate_hashes), 3)
        self.assertEqual(len(result.branch_constraint_certificates), 3)
        self.assertTrue(report.sources)

        for row, constraint in zip(report.rows, result.branch_constraint_certificates):
            self.assertEqual(len(row.incompatible_pair), 2)
            self.assertEqual(len(row.compatible_pair), 2)
            self.assertNotEqual(row.incompatible_pair, row.compatible_pair)
            self.assertNotEqual(row.static_action, row.constraint_action)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.constraint_committed)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.constraint_verifier_call_count, 1)
            self.assertEqual(len(row.source_incompatible_reject_receipt_hashes), 1)
            self.assertEqual(len(row.source_compatible_commit_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.constraint_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_constraint_certificate(constraint, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_constraint_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.constraint_success_count, 3)
        self.assertEqual(report.same_budget_constraint_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_constraint_transfer_certified_experiment()
        invalid = replace(
            result.branch_constraint_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_constraint_transfer_certificate(invalid, result.report))

    def test_missing_constraint_success_fails_transfer_certificate(self) -> None:
        result = run_branch_constraint_transfer_certified_experiment()
        invalid = replace(
            result.branch_constraint_transfer_certificate,
            constraint_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_constraint_transfer_certificate(invalid, result.report))

    def test_tampered_constraint_certificate_fails(self) -> None:
        result = run_branch_constraint_transfer_certified_experiment()
        invalid = replace(
            result.branch_constraint_certificates[0],
            compatible_pair=result.branch_constraint_certificates[0].incompatible_pair,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_constraint_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
