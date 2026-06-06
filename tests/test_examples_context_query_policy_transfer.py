from __future__ import annotations

from dataclasses import replace
import unittest

from examples.common import validate_example_evidence_certificate
from examples.context_query_policy_transfer import (
    run_context_query_policy_transfer_certified_experiment,
    run_context_query_policy_transfer_experiment,
    validate_context_query_policy_certificate,
    validate_context_query_policy_transfer_certificate,
)
from trwm.ancestral import (
    validate_ancestral_context_refinement_certificate,
    validate_ancestral_context_selection_certificate,
)


class ContextQueryPolicyTransferExampleTests(unittest.TestCase):
    def test_certified_context_query_policy_transfer(self) -> None:
        result = run_context_query_policy_transfer_certified_experiment()
        report = result.report
        certificate = result.context_query_policy_transfer_certificate
        evidence = result.evidence_certificate

        self.assertEqual(report.schema_version, "trwm.example.context_query_policy_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.held_out_sibling_count, 6)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(len(report.rows), 6)
        self.assertEqual(report.total_receipt_count, 42)
        self.assertEqual(report.total_committed_count, 15)
        self.assertEqual(report.total_rejected_count, 12)
        self.assertEqual(report.total_rolled_back_loser_count, 15)
        self.assertEqual(report.calibration_coarse_budget_success_count, 0)
        self.assertEqual(report.sibling_stale_budget_success_count, 0)
        self.assertEqual(report.sibling_policy_budget_success_count, 6)
        self.assertEqual(report.same_budget_query_policy_count, 6)
        self.assertEqual(report.query_policy_certificate_count, 6)
        self.assertEqual(report.refinement_certificate_count, 3)
        self.assertEqual(report.context_selection_certificate_count, 18)
        self.assertEqual(report.memory_row_count, 27)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_context_selection_certificates_valid)
        self.assertTrue(report.all_context_refinement_certificates_valid)
        self.assertTrue(report.all_context_query_policy_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(result.claim_certificate.status, "supported")
        self.assertTrue(validate_context_query_policy_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))

        self.assertEqual(evidence.domain, "context_query_policy_branch_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(certificate.held_out_sibling_count, 6)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 24)
        self.assertEqual(len(certificate.context_selection_certificate_hashes), 18)
        self.assertEqual(len(certificate.context_refinement_certificate_hashes), 3)
        self.assertEqual(len(certificate.context_query_policy_certificate_hashes), 6)
        self.assertEqual(len(result.context_selection_certificates), 18)
        self.assertEqual(len(result.context_refinement_certificates), 3)
        self.assertEqual(len(result.context_query_policy_certificates), 6)
        self.assertTrue(all(validate_ancestral_context_selection_certificate(row) for row in result.context_selection_certificates))
        self.assertTrue(all(validate_ancestral_context_refinement_certificate(row) for row in result.context_refinement_certificates))
        self.assertTrue(all(validate_context_query_policy_certificate(row) for row in result.context_query_policy_certificates))

        for row in report.rows:
            self.assertEqual(len(row.candidate_contexts), 3)
            self.assertEqual(len(row.calibration_coarse_selected_contexts), 3)
            self.assertEqual(len(row.calibration_policy_selected_contexts), 1)
            self.assertEqual(len(row.sibling_stale_selected_contexts), 3)
            self.assertEqual(len(row.sibling_policy_selected_contexts), 1)
            self.assertNotEqual(row.calibration_coarse_top_action, row.committed_target_action)
            self.assertNotEqual(row.sibling_stale_top_action, row.committed_target_action)
            self.assertEqual(row.sibling_policy_top_action, row.committed_target_action)
            self.assertFalse(row.calibration_coarse_budget_committed)
            self.assertFalse(row.sibling_stale_budget_committed)
            self.assertTrue(row.sibling_policy_budget_committed)
            self.assertTrue(row.same_budget)
            self.assertEqual(len(row.source_receipt_hashes), 9)
            self.assertEqual(len(row.calibration_coarse_receipt_hashes), 1)
            self.assertEqual(len(row.sibling_stale_receipt_hashes), 1)
            self.assertEqual(len(row.sibling_policy_receipt_hashes), 1)
            self.assertEqual(len(row.branch_selection_certificate_hashes), 6)

        for query_policy in result.context_query_policy_certificates:
            self.assertFalse(query_policy.stale_committed)
            self.assertTrue(query_policy.policy_committed)
            self.assertEqual(query_policy.stale_verifier_call_count, 1)
            self.assertEqual(query_policy.policy_verifier_call_count, 1)
            self.assertTrue(query_policy.same_budget)
            self.assertNotEqual(query_policy.stale_top_action, query_policy.committed_target_action)
            self.assertEqual(query_policy.policy_top_action, query_policy.committed_target_action)
            self.assertEqual(query_policy.policy_required_tag_keys, ("regime",))
            self.assertEqual(query_policy.policy_transfer_reason, "calibration_refinement_applied_to_heldout_sibling_target")

    def test_report_only_api_remains_available(self) -> None:
        report = run_context_query_policy_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.held_out_sibling_count, 6)
        self.assertEqual(report.calibration_coarse_budget_success_count, 0)
        self.assertEqual(report.sibling_stale_budget_success_count, 0)
        self.assertEqual(report.sibling_policy_budget_success_count, 6)
        self.assertEqual(report.same_budget_query_policy_count, 6)

    def test_tampered_report_hash_fails_certificate(self) -> None:
        result = run_context_query_policy_transfer_certified_experiment()
        invalid = replace(
            result.context_query_policy_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_context_query_policy_transfer_certificate(invalid, result.report))

    def test_stale_success_count_fails_certificate(self) -> None:
        result = run_context_query_policy_transfer_certified_experiment()
        invalid = replace(
            result.context_query_policy_transfer_certificate,
            sibling_stale_budget_success_count=1,
            certificate_hash="",
        )

        self.assertFalse(validate_context_query_policy_transfer_certificate(invalid, result.report))

    def test_held_out_sibling_count_mismatch_fails_certificate(self) -> None:
        result = run_context_query_policy_transfer_certified_experiment()
        invalid = replace(
            result.context_query_policy_transfer_certificate,
            held_out_sibling_count=3,
            certificate_hash="",
        )

        self.assertFalse(validate_context_query_policy_transfer_certificate(invalid, result.report))

    def test_missing_query_policy_certificate_fails_transfer_certificate(self) -> None:
        result = run_context_query_policy_transfer_certified_experiment()
        invalid = replace(
            result.context_query_policy_transfer_certificate,
            context_query_policy_certificate_hashes=result.context_query_policy_transfer_certificate.context_query_policy_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_context_query_policy_transfer_certificate(invalid, result.report))

    def test_tampered_query_policy_certificate_fails(self) -> None:
        result = run_context_query_policy_transfer_certified_experiment()
        invalid = replace(
            result.context_query_policy_certificates[0],
            policy_top_action=result.context_query_policy_certificates[0].stale_top_action,
            certificate_hash="",
        )

        self.assertFalse(validate_context_query_policy_certificate(invalid))

    def test_empty_sibling_policy_selection_fails(self) -> None:
        result = run_context_query_policy_transfer_certified_experiment()
        invalid = replace(
            result.context_query_policy_certificates[0],
            sibling_policy_selected_ids=(),
            certificate_hash="",
        )

        self.assertFalse(validate_context_query_policy_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
