from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_recency_weight_transfer import (
    run_branch_recency_weight_transfer_certified_experiment,
    run_branch_recency_weight_transfer_experiment,
    validate_branch_recency_certificate,
    validate_branch_recency_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchRecencyWeightTransferExampleTests(unittest.TestCase):
    def test_certified_branch_recency_weight_transfer(self) -> None:
        result = run_branch_recency_weight_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_recency_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_recency_weight_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 18)
        self.assertEqual(report.total_committed_count, 12)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.old_stale_commit_count, 6)
        self.assertEqual(report.recent_stale_reject_count, 3)
        self.assertEqual(report.recent_adapted_commit_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.recency_success_count, 3)
        self.assertEqual(report.same_budget_recency_count, 3)
        self.assertEqual(report.branch_recency_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 12)
        self.assertEqual(report.memory_receipt_count, 12)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_recency_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_recency_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_recency_weight_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 15)
        self.assertEqual(len(certificate.branch_recency_certificate_hashes), 3)
        self.assertEqual(len(result.branch_recency_certificates), 3)

        for row, recency in zip(report.rows, result.branch_recency_certificates):
            self.assertEqual(len(row.source_contexts), 3)
            self.assertNotEqual(row.stale_action, row.adapted_action)
            self.assertEqual(row.cumulative_top_action, row.stale_action)
            self.assertEqual(row.recency_top_action, row.adapted_action)
            self.assertEqual(row.cumulative_stale_commit_count, 2)
            self.assertEqual(row.recent_stale_reject_count, 1)
            self.assertEqual(row.recent_adapted_commit_count, 1)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.recency_committed)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.recency_verifier_call_count, 1)
            self.assertEqual(len(row.old_stale_commit_receipt_hashes), 2)
            self.assertEqual(len(row.recent_stale_reject_receipt_hashes), 1)
            self.assertEqual(len(row.recent_adapted_commit_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.recency_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_recency_certificate(recency, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_recency_weight_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.recency_success_count, 3)
        self.assertEqual(report.same_budget_recency_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_recency_weight_transfer_certified_experiment()
        invalid = replace(
            result.branch_recency_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_recency_transfer_certificate(invalid, result.report))

    def test_missing_recency_success_fails_transfer_certificate(self) -> None:
        result = run_branch_recency_weight_transfer_certified_experiment()
        invalid = replace(
            result.branch_recency_transfer_certificate,
            recency_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_recency_transfer_certificate(invalid, result.report))

    def test_tampered_recency_certificate_fails(self) -> None:
        result = run_branch_recency_weight_transfer_certified_experiment()
        invalid = replace(
            result.branch_recency_certificates[0],
            recency_top_action=result.branch_recency_certificates[0].stale_action,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_recency_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
