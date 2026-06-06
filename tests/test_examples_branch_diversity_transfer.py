from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_diversity_transfer import (
    run_branch_diversity_transfer_certified_experiment,
    run_branch_diversity_transfer_experiment,
    validate_branch_diversity_certificate,
    validate_branch_diversity_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchDiversityTransferExampleTests(unittest.TestCase):
    def test_certified_branch_diversity_transfer(self) -> None:
        result = run_branch_diversity_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_diversity_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_diversity_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 21)
        self.assertEqual(report.total_committed_count, 6)
        self.assertEqual(report.total_rejected_count, 15)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.saturated_family_count, 3)
        self.assertEqual(report.diverse_family_count, 3)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.diverse_budget_success_count, 3)
        self.assertEqual(report.same_budget_diversity_count, 3)
        self.assertEqual(report.branch_diversity_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_diversity_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_diversity_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_diversity_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 9)
        self.assertEqual(len(certificate.branch_diversity_certificate_hashes), 3)
        self.assertEqual(len(result.branch_diversity_certificates), 3)
        self.assertTrue(all(validate_branch_diversity_certificate(row) for row in result.branch_diversity_certificates))

        for row, diversity in zip(report.rows, result.branch_diversity_certificates):
            self.assertEqual(len(row.candidate_actions), 4)
            self.assertEqual(len(row.candidate_family_ids), 4)
            self.assertEqual(len(row.baseline_actions), 2)
            self.assertEqual(len(set(row.baseline_family_ids)), 1)
            self.assertEqual(row.baseline_family_ids[0], row.saturated_family_id)
            self.assertEqual(len(row.diverse_actions), 2)
            self.assertEqual(len(set(row.diverse_family_ids)), 2)
            self.assertNotIn(row.saturated_family_id, row.diverse_family_ids)
            self.assertEqual(row.diverse_actions[-1], row.committed_target_action)
            self.assertFalse(row.static_budget_committed)
            self.assertTrue(row.diverse_budget_committed)
            self.assertTrue(row.same_budget)
            self.assertEqual(len(row.source_receipt_hashes), 3)
            self.assertEqual(len(row.static_receipt_hashes), 2)
            self.assertEqual(len(row.diverse_receipt_hashes), 2)
            self.assertTrue(validate_branch_diversity_certificate(diversity, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_diversity_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.diverse_budget_success_count, 3)
        self.assertEqual(report.saturated_family_count, 3)
        self.assertEqual(report.diverse_family_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_diversity_transfer_certified_experiment()
        invalid = replace(
            result.branch_diversity_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_diversity_transfer_certificate(invalid, result.report))

    def test_missing_diverse_success_fails_transfer_certificate(self) -> None:
        result = run_branch_diversity_transfer_certified_experiment()
        invalid = replace(
            result.branch_diversity_transfer_certificate,
            diverse_budget_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_diversity_transfer_certificate(invalid, result.report))

    def test_missing_diversity_certificate_fails_transfer_certificate(self) -> None:
        result = run_branch_diversity_transfer_certified_experiment()
        invalid = replace(
            result.branch_diversity_transfer_certificate,
            branch_diversity_certificate_hashes=result.branch_diversity_transfer_certificate.branch_diversity_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_branch_diversity_transfer_certificate(invalid, result.report))

    def test_tampered_diversity_certificate_fails(self) -> None:
        result = run_branch_diversity_transfer_certified_experiment()
        invalid = replace(
            result.branch_diversity_certificates[0],
            diverse_family_ids=(result.branch_diversity_certificates[0].saturated_family_id, "safe_repair"),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_diversity_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
