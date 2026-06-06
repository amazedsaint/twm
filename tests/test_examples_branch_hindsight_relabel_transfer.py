from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_hindsight_relabel_transfer import (
    run_branch_hindsight_relabel_transfer_certified_experiment,
    run_branch_hindsight_relabel_transfer_experiment,
    validate_branch_hindsight_relabel_certificate,
    validate_branch_hindsight_relabel_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchHindsightRelabelTransferExampleTests(unittest.TestCase):
    def test_certified_branch_hindsight_relabel_transfer(self) -> None:
        result = run_branch_hindsight_relabel_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_hindsight_relabel_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_hindsight_relabel_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 9)
        self.assertEqual(report.total_committed_count, 3)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_reject_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.relabeled_success_count, 3)
        self.assertEqual(report.relabeled_goal_count, 3)
        self.assertEqual(report.same_budget_hindsight_count, 3)
        self.assertEqual(report.branch_hindsight_relabel_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 3)
        self.assertEqual(report.memory_receipt_count, 3)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_hindsight_relabel_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_hindsight_relabel_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_hindsight_relabel_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 9)
        self.assertEqual(len(certificate.branch_hindsight_relabel_certificate_hashes), 3)
        self.assertEqual(len(result.branch_hindsight_relabel_certificates), 3)

        for row, hindsight in zip(report.rows, result.branch_hindsight_relabel_certificates):
            self.assertTrue(row.source_rejected)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.relabeled_committed)
            self.assertEqual(row.achieved_goal, row.relabeled_goal)
            self.assertNotEqual(row.intended_goal, row.relabeled_goal)
            self.assertEqual(row.source_action, row.relabeled_target_action)
            self.assertNotEqual(row.static_target_action, row.relabeled_target_action)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.relabeled_verifier_call_count, 1)
            self.assertEqual(len(row.source_reject_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.relabeled_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_hindsight_relabel_certificate(hindsight, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_hindsight_relabel_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.source_reject_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.relabeled_success_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_hindsight_relabel_transfer_certified_experiment()
        invalid = replace(
            result.branch_hindsight_relabel_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_hindsight_relabel_transfer_certificate(invalid, result.report))

    def test_missing_relabeled_success_fails_transfer_certificate(self) -> None:
        result = run_branch_hindsight_relabel_transfer_certified_experiment()
        invalid = replace(
            result.branch_hindsight_relabel_transfer_certificate,
            relabeled_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_hindsight_relabel_transfer_certificate(invalid, result.report))

    def test_tampered_hindsight_relabel_certificate_fails(self) -> None:
        result = run_branch_hindsight_relabel_transfer_certified_experiment()
        invalid = replace(
            result.branch_hindsight_relabel_certificates[0],
            relabeled_goal=result.branch_hindsight_relabel_certificates[0].intended_goal,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_hindsight_relabel_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
