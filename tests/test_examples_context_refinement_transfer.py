from __future__ import annotations

from dataclasses import replace
import unittest

from examples.common import validate_example_evidence_certificate
from examples.context_refinement_transfer import (
    run_context_refinement_transfer_certified_experiment,
    run_context_refinement_transfer_experiment,
    validate_context_refinement_transfer_certificate,
)
from trwm.ancestral import validate_ancestral_context_refinement_certificate
from trwm.claims import validate_claim_certificate


class ContextRefinementTransferExampleTests(unittest.TestCase):
    def test_certified_experiment_validates_refinement_from_counterexample(self) -> None:
        result = run_context_refinement_transfer_certified_experiment()

        report = result.report
        certificate = result.context_refinement_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.context_refinement_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 33)
        self.assertEqual(report.total_committed_count, 12)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 15)
        self.assertEqual(report.coarse_selected_context_count, 9)
        self.assertEqual(report.refined_selected_context_count, 3)
        self.assertEqual(report.newly_rejected_context_count, 6)
        self.assertEqual(report.coarse_budget_success_count, 0)
        self.assertEqual(report.refined_budget_success_count, 3)
        self.assertEqual(report.refinement_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 27)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_context_selection_certificates_valid)
        self.assertTrue(report.all_context_refinement_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_context_refinement_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "context_refinement_branch_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 15)
        self.assertEqual(len(certificate.base_selection_certificate_hashes), 3)
        self.assertEqual(len(certificate.refined_selection_certificate_hashes), 3)
        self.assertEqual(len(certificate.context_refinement_certificate_hashes), 3)
        self.assertEqual(certificate.memory_snapshot_hash, report.memory_snapshot_hash)
        self.assertEqual(len(result.context_refinement_certificates), 3)
        self.assertTrue(all(validate_ancestral_context_refinement_certificate(row) for row in result.context_refinement_certificates))

        for row in report.rows:
            self.assertEqual(len(row.candidate_contexts), 3)
            self.assertEqual(len(row.coarse_selected_contexts), 3)
            self.assertEqual(len(row.refined_selected_contexts), 1)
            self.assertEqual(len(row.newly_rejected_contexts), 2)
            self.assertNotEqual(row.coarse_top_action, row.committed_target_action)
            self.assertEqual(row.refined_top_action, row.committed_target_action)
            self.assertFalse(row.coarse_budget_committed)
            self.assertTrue(row.refined_budget_committed)
            self.assertTrue(row.coarse_counterexample_receipt_hash)
            self.assertTrue(row.coarse_counterexample_residual_kind)
            self.assertEqual(len(row.source_receipt_hashes), 9)
            self.assertEqual(len(row.refined_target_receipt_hashes), 1)
            self.assertEqual(len(row.branch_selection_certificate_hashes), 5)

    def test_report_only_api_remains_available(self) -> None:
        report = run_context_refinement_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.coarse_budget_success_count, 0)
        self.assertEqual(report.refined_budget_success_count, 3)
        self.assertEqual(report.newly_rejected_context_count, 6)

    def test_tampered_report_hash_fails_certificate(self) -> None:
        result = run_context_refinement_transfer_certified_experiment()
        tampered = replace(result.context_refinement_transfer_certificate, report_hash="0" * 64, certificate_hash="")

        self.assertFalse(validate_context_refinement_transfer_certificate(tampered, result.report))

    def test_missing_refinement_rejection_fails_certificate(self) -> None:
        result = run_context_refinement_transfer_certified_experiment()
        invalid = replace(
            result.context_refinement_transfer_certificate,
            newly_rejected_context_count=5,
            certificate_hash="",
        )

        self.assertFalse(validate_context_refinement_transfer_certificate(invalid, result.report))


if __name__ == "__main__":
    unittest.main()
