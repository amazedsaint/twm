from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_active_subspace_transfer import (
    run_branch_active_subspace_transfer_certified_experiment,
    run_branch_active_subspace_transfer_experiment,
    validate_branch_active_subspace_certificate,
    validate_branch_active_subspace_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchActiveSubspaceTransferExampleTests(unittest.TestCase):
    def test_certified_branch_active_subspace_transfer(self) -> None:
        result = run_branch_active_subspace_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_active_subspace_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_active_subspace_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 15)
        self.assertEqual(report.total_committed_count, 9)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_active_committed_count, 6)
        self.assertEqual(report.source_orthogonal_rejected_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.active_subspace_success_count, 3)
        self.assertEqual(report.same_budget_active_subspace_count, 3)
        self.assertEqual(report.branch_active_subspace_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_active_subspace_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_active_subspace_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_active_subspace_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 15)
        self.assertEqual(len(certificate.branch_active_subspace_certificate_hashes), 3)
        self.assertEqual(len(result.branch_active_subspace_certificates), 3)
        self.assertTrue(report.sources)

        for row, subspace in zip(report.rows, result.branch_active_subspace_certificates):
            self.assertEqual(row.ambient_dimension, 2)
            self.assertEqual(row.subspace_dimension, 1)
            self.assertEqual(row.active_basis_vector, (1.0, 0.0))
            self.assertEqual(row.orthogonal_basis_vector, (0.0, 1.0))
            self.assertEqual(row.projection_threshold, 0.75)
            self.assertEqual(len(row.source_active_action_ids), 2)
            self.assertEqual(row.source_active_projection_scores, (1.0, 0.8))
            self.assertLess(row.source_orthogonal_projection_score, row.projection_threshold)
            self.assertLess(row.static_target_projection_score, row.projection_threshold)
            self.assertGreaterEqual(row.active_subspace_target_projection_score, row.projection_threshold)
            self.assertEqual(row.source_active_committed_count, 2)
            self.assertEqual(row.source_orthogonal_rejected_count, 1)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.active_subspace_committed)
            self.assertEqual(row.source_verifier_call_count, 3)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.active_subspace_verifier_call_count, 1)
            self.assertEqual(len(row.source_active_receipt_hashes), 2)
            self.assertEqual(len(row.source_orthogonal_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.active_subspace_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_active_subspace_certificate(subspace, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_active_subspace_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.active_subspace_success_count, 3)
        self.assertEqual(report.same_budget_active_subspace_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_active_subspace_transfer_certified_experiment()
        invalid = replace(
            result.branch_active_subspace_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_active_subspace_transfer_certificate(invalid, result.report))

    def test_missing_active_subspace_success_fails_transfer_certificate(self) -> None:
        result = run_branch_active_subspace_transfer_certified_experiment()
        invalid = replace(
            result.branch_active_subspace_transfer_certificate,
            active_subspace_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_active_subspace_transfer_certificate(invalid, result.report))

    def test_tampered_projection_score_fails(self) -> None:
        result = run_branch_active_subspace_transfer_certified_experiment()
        invalid = replace(
            result.branch_active_subspace_certificates[0],
            source_active_projection_scores=(1.0, 0.7),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_active_subspace_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
