from __future__ import annotations

from dataclasses import replace
import unittest

from examples.common import validate_example_evidence_certificate
from examples.context_selection_transfer import (
    run_context_selection_transfer_certified_experiment,
    run_context_selection_transfer_experiment,
    validate_context_selection_transfer_certificate,
)
from trwm.ancestral import validate_ancestral_context_selection_certificate
from trwm.claims import validate_claim_certificate


class ContextSelectionTransferExampleTests(unittest.TestCase):
    def test_certified_experiment_validates_context_selection(self) -> None:
        result = run_context_selection_transfer_certified_experiment()

        report = result.report
        certificate = result.context_selection_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.context_selection_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 36)
        self.assertEqual(report.total_committed_count, 12)
        self.assertEqual(report.total_rejected_count, 12)
        self.assertEqual(report.total_rolled_back_loser_count, 12)
        self.assertEqual(report.selected_context_count, 6)
        self.assertEqual(report.rejected_context_count, 3)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.selected_budget_success_count, 3)
        self.assertEqual(report.bypass_rejected_context_blocked_count, 3)
        self.assertEqual(report.memory_row_count, 27)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_context_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_context_selection_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "context_selection_branch_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 18)
        self.assertEqual(len(certificate.context_selection_certificate_hashes), 3)
        self.assertEqual(certificate.memory_snapshot_hash, report.memory_snapshot_hash)
        self.assertEqual(len(result.context_selection_certificates), 3)
        self.assertTrue(all(validate_ancestral_context_selection_certificate(row) for row in result.context_selection_certificates))

        for row in report.rows:
            self.assertEqual(len(row.candidate_contexts), 3)
            self.assertEqual(len(row.selected_contexts), 2)
            self.assertEqual(len(row.rejected_contexts), 1)
            self.assertEqual(len(row.source_receipt_hashes), 9)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.selected_target_receipt_hashes), 1)
            self.assertEqual(len(row.bypass_target_receipt_hashes), 1)
            self.assertEqual(len(row.branch_selection_certificate_hashes), 6)
            self.assertEqual(row.selected_top_action, row.committed_target_action)
            self.assertFalse(row.static_budget_committed)
            self.assertTrue(row.selected_budget_committed)
            self.assertFalse(row.bypass_rejected_context_committed)
            self.assertTrue(row.bypass_rejected_context_blocked)
            self.assertEqual(tuple(row.rejected_reasons.values()), ("tag_mismatch:regime",))

    def test_report_only_api_remains_available(self) -> None:
        report = run_context_selection_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.selected_context_count, 6)
        self.assertEqual(report.rejected_context_count, 3)
        self.assertEqual(report.selected_budget_success_count, 3)
        self.assertEqual(report.bypass_rejected_context_blocked_count, 3)

    def test_tampered_report_hash_fails_certificate(self) -> None:
        result = run_context_selection_transfer_certified_experiment()
        tampered = replace(result.context_selection_transfer_certificate, report_hash="0" * 64, certificate_hash="")

        self.assertFalse(validate_context_selection_transfer_certificate(tampered, result.report))

    def test_missing_rejected_context_block_fails_certificate(self) -> None:
        result = run_context_selection_transfer_certified_experiment()
        invalid = replace(
            result.context_selection_transfer_certificate,
            bypass_rejected_context_blocked_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_context_selection_transfer_certificate(invalid, result.report))


if __name__ == "__main__":
    unittest.main()
