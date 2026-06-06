from __future__ import annotations

from dataclasses import replace
import unittest

from examples.common import validate_example_evidence_certificate
from examples.context_retention_transfer import (
    run_context_retention_transfer_certified_experiment,
    run_context_retention_transfer_experiment,
    validate_context_retention_influence_ablation_certificate,
    validate_context_retention_transfer_certificate,
)
from trwm.ancestral import (
    validate_ancestral_branch_influence_certificate,
    validate_ancestral_branch_retention_certificate,
    validate_ancestral_context_refinement_certificate,
)
from trwm.claims import validate_claim_certificate


class ContextRetentionTransferExampleTests(unittest.TestCase):
    def test_certified_experiment_validates_retained_target_branch_transfer(self) -> None:
        result = run_context_retention_transfer_certified_experiment()

        report = result.report
        certificate = result.context_retention_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.context_retention_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 39)
        self.assertEqual(report.total_committed_count, 15)
        self.assertEqual(report.total_rejected_count, 9)
        self.assertEqual(report.total_rolled_back_loser_count, 15)
        self.assertEqual(report.coarse_selected_context_count, 9)
        self.assertEqual(report.refined_selected_context_count, 3)
        self.assertEqual(report.newly_rejected_context_count, 6)
        self.assertEqual(report.retained_context_count, 3)
        self.assertEqual(report.coarse_budget_success_count, 0)
        self.assertEqual(report.refined_budget_success_count, 3)
        self.assertEqual(report.sibling_static_budget_success_count, 0)
        self.assertEqual(report.sibling_budget_success_count, 3)
        self.assertEqual(report.refinement_certificate_count, 3)
        self.assertEqual(report.retention_certificate_count, 3)
        self.assertEqual(report.influence_certificate_count, 3)
        self.assertEqual(report.influence_ablation_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 30)
        self.assertEqual(report.memory_receipt_count, 30)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_context_selection_certificates_valid)
        self.assertTrue(report.all_context_refinement_certificates_valid)
        self.assertTrue(report.all_branch_retention_certificates_valid)
        self.assertTrue(report.all_branch_influence_certificates_valid)
        self.assertTrue(report.all_influence_ablation_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_context_retention_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "context_retention_branch_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 21)
        self.assertEqual(len(certificate.base_selection_certificate_hashes), 3)
        self.assertEqual(len(certificate.refined_selection_certificate_hashes), 3)
        self.assertEqual(len(certificate.context_refinement_certificate_hashes), 3)
        self.assertEqual(len(certificate.branch_retention_certificate_hashes), 3)
        self.assertEqual(len(certificate.branch_influence_certificate_hashes), 3)
        self.assertEqual(len(certificate.influence_ablation_certificate_hashes), 3)
        self.assertEqual(certificate.memory_snapshot_hash, report.memory_snapshot_hash)
        self.assertEqual(len(result.context_refinement_certificates), 3)
        self.assertEqual(len(result.branch_retention_certificates), 3)
        self.assertEqual(len(result.branch_influence_certificates), 3)
        self.assertEqual(len(result.influence_ablation_certificates), 3)
        self.assertTrue(all(validate_ancestral_context_refinement_certificate(row) for row in result.context_refinement_certificates))
        self.assertTrue(all(validate_ancestral_branch_retention_certificate(row) for row in result.branch_retention_certificates))
        self.assertTrue(all(validate_ancestral_branch_influence_certificate(row) for row in result.branch_influence_certificates))
        self.assertTrue(
            all(validate_context_retention_influence_ablation_certificate(row) for row in result.influence_ablation_certificates)
        )

        for row in report.rows:
            self.assertEqual(len(row.candidate_contexts), 3)
            self.assertEqual(len(row.coarse_selected_contexts), 3)
            self.assertEqual(len(row.refined_selected_contexts), 1)
            self.assertEqual(len(row.newly_rejected_contexts), 2)
            self.assertEqual(len(row.retained_contexts_for_sibling), 1)
            self.assertNotEqual(row.coarse_top_action, row.committed_target_action)
            self.assertEqual(row.refined_top_action, row.committed_target_action)
            self.assertNotEqual(row.sibling_static_top_action, row.committed_target_action)
            self.assertEqual(row.sibling_top_action, row.committed_target_action)
            self.assertFalse(row.coarse_budget_committed)
            self.assertTrue(row.refined_budget_committed)
            self.assertFalse(row.sibling_static_budget_committed)
            self.assertTrue(row.sibling_budget_committed)
            self.assertTrue(row.influence_certificate_hash)
            self.assertTrue(row.influence_ablation_certificate_hash)
            self.assertEqual(len(row.source_receipt_hashes), 9)
            self.assertEqual(len(row.refined_target_receipt_hashes), 1)
            self.assertEqual(len(row.sibling_static_receipt_hashes), 1)
            self.assertEqual(len(row.sibling_target_receipt_hashes), 1)
            self.assertEqual(len(row.branch_selection_certificate_hashes), 7)

        for retention in result.branch_retention_certificates:
            self.assertEqual(retention.added_receipt_count, 1)
            self.assertEqual(retention.added_row_count, 1)
            self.assertEqual(len(retention.committed_receipt_hashes), 1)
            self.assertEqual(retention.rejected_receipt_hashes, ())
            self.assertEqual(retention.rolled_back_receipt_hashes, ())
            self.assertEqual(retention.abstained_receipt_hashes, ())

        for influence in result.branch_influence_certificates:
            self.assertEqual(len(influence.query_context_ids), 1)
            self.assertEqual(len(influence.candidate_actions), 3)
            self.assertEqual(len(influence.ranked_actions), 3)
            self.assertEqual(influence.top_action, influence.ranked_actions[0])
            self.assertEqual(len(influence.retention_certificate_hashes), 1)
            self.assertTrue(influence.top_action_receipt_hashes)

        for ablation in result.influence_ablation_certificates:
            self.assertFalse(ablation.baseline_committed)
            self.assertTrue(ablation.influenced_committed)
            self.assertTrue(ablation.same_budget)
            self.assertEqual(ablation.baseline_verifier_call_count, 1)
            self.assertEqual(ablation.influenced_verifier_call_count, 1)
            self.assertEqual(ablation.influenced_top_action, ablation.committed_target_action)
            self.assertNotEqual(ablation.baseline_top_action, ablation.committed_target_action)

    def test_report_only_api_remains_available(self) -> None:
        report = run_context_retention_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.coarse_budget_success_count, 0)
        self.assertEqual(report.refined_budget_success_count, 3)
        self.assertEqual(report.sibling_static_budget_success_count, 0)
        self.assertEqual(report.sibling_budget_success_count, 3)
        self.assertEqual(report.retention_certificate_count, 3)
        self.assertEqual(report.influence_certificate_count, 3)
        self.assertEqual(report.influence_ablation_certificate_count, 3)

    def test_tampered_report_hash_fails_certificate(self) -> None:
        result = run_context_retention_transfer_certified_experiment()
        tampered = replace(result.context_retention_transfer_certificate, report_hash="0" * 64, certificate_hash="")

        self.assertFalse(validate_context_retention_transfer_certificate(tampered, result.report))

    def test_missing_sibling_success_fails_certificate(self) -> None:
        result = run_context_retention_transfer_certified_experiment()
        invalid = replace(
            result.context_retention_transfer_certificate,
            sibling_budget_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_context_retention_transfer_certificate(invalid, result.report))

    def test_missing_influence_certificate_fails_certificate(self) -> None:
        result = run_context_retention_transfer_certified_experiment()
        invalid = replace(
            result.context_retention_transfer_certificate,
            branch_influence_certificate_hashes=result.context_retention_transfer_certificate.branch_influence_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_context_retention_transfer_certificate(invalid, result.report))

    def test_missing_ablation_certificate_fails_certificate(self) -> None:
        result = run_context_retention_transfer_certified_experiment()
        invalid = replace(
            result.context_retention_transfer_certificate,
            influence_ablation_certificate_hashes=result.context_retention_transfer_certificate.influence_ablation_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_context_retention_transfer_certificate(invalid, result.report))


if __name__ == "__main__":
    unittest.main()
