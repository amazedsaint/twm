from __future__ import annotations

from dataclasses import replace
import unittest

from examples.common import validate_example_evidence_certificate
from examples.context_drift_quarantine import (
    run_context_drift_quarantine_certified_experiment,
    run_context_drift_quarantine_experiment,
    validate_context_drift_quarantine_certificate,
    validate_context_drift_quarantine_transfer_certificate,
)
from trwm.ancestral import validate_ancestral_context_selection_certificate


class ContextDriftQuarantineExampleTests(unittest.TestCase):
    def test_certified_context_drift_quarantine(self) -> None:
        result = run_context_drift_quarantine_certified_experiment()
        report = result.report
        certificate = result.context_drift_quarantine_transfer_certificate
        evidence = result.evidence_certificate

        self.assertEqual(report.schema_version, "trwm.example.context_drift_quarantine.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 24)
        self.assertEqual(report.total_committed_count, 9)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 9)
        self.assertEqual(report.stale_budget_success_count, 0)
        self.assertEqual(report.drift_budget_success_count, 3)
        self.assertEqual(report.quarantined_context_count, 3)
        self.assertEqual(report.drift_quarantine_certificate_count, 3)
        self.assertEqual(report.context_selection_certificate_count, 6)
        self.assertEqual(report.memory_row_count, 18)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_context_selection_certificates_valid)
        self.assertTrue(report.all_context_drift_quarantine_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(result.claim_certificate.status, "supported")
        self.assertTrue(validate_context_drift_quarantine_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))

        self.assertEqual(evidence.domain, "context_drift_branch_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 12)
        self.assertEqual(len(certificate.context_selection_certificate_hashes), 6)
        self.assertEqual(len(certificate.context_drift_quarantine_certificate_hashes), 3)
        self.assertEqual(len(result.context_selection_certificates), 6)
        self.assertEqual(len(result.context_drift_quarantine_certificates), 3)
        self.assertTrue(all(validate_ancestral_context_selection_certificate(row) for row in result.context_selection_certificates))
        self.assertTrue(all(validate_context_drift_quarantine_certificate(row) for row in result.context_drift_quarantine_certificates))

        for row in report.rows:
            self.assertEqual(len(row.stale_contexts), 1)
            self.assertEqual(len(row.current_contexts), 1)
            self.assertEqual(len(row.coarse_selected_contexts), 2)
            self.assertEqual(len(row.drift_selected_contexts), 1)
            self.assertEqual(len(row.quarantined_contexts), 1)
            self.assertNotEqual(row.stale_top_action, row.committed_target_action)
            self.assertEqual(row.drift_top_action, row.committed_target_action)
            self.assertFalse(row.stale_budget_committed)
            self.assertTrue(row.drift_budget_committed)
            self.assertTrue(row.same_budget)
            self.assertEqual(len(row.stale_source_receipt_hashes), 3)
            self.assertEqual(len(row.current_source_receipt_hashes), 3)
            self.assertEqual(len(row.stale_target_receipt_hashes), 1)
            self.assertEqual(len(row.drift_target_receipt_hashes), 1)
            self.assertEqual(len(row.branch_selection_certificate_hashes), 4)

        for quarantine in result.context_drift_quarantine_certificates:
            self.assertNotEqual(quarantine.stale_top_action, quarantine.committed_target_action)
            self.assertEqual(quarantine.drift_top_action, quarantine.committed_target_action)
            self.assertTrue(quarantine.stale_source_committed_receipt_hashes)
            self.assertTrue(quarantine.current_source_committed_receipt_hashes)
            self.assertTrue(quarantine.stale_target_reject_receipt_hashes)
            self.assertTrue(quarantine.drift_target_commit_receipt_hashes)
            self.assertTrue(quarantine.same_budget)
            self.assertEqual(quarantine.quarantine_reason, "tag_mismatch:epoch")

    def test_report_only_api_remains_available(self) -> None:
        report = run_context_drift_quarantine_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.stale_budget_success_count, 0)
        self.assertEqual(report.drift_budget_success_count, 3)
        self.assertEqual(report.quarantined_context_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_context_drift_quarantine_certified_experiment()
        invalid = replace(
            result.context_drift_quarantine_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_context_drift_quarantine_transfer_certificate(invalid, result.report))

    def test_stale_success_count_fails_transfer_certificate(self) -> None:
        result = run_context_drift_quarantine_certified_experiment()
        invalid = replace(
            result.context_drift_quarantine_transfer_certificate,
            stale_budget_success_count=1,
            certificate_hash="",
        )

        self.assertFalse(validate_context_drift_quarantine_transfer_certificate(invalid, result.report))

    def test_missing_quarantine_certificate_fails_transfer_certificate(self) -> None:
        result = run_context_drift_quarantine_certified_experiment()
        invalid = replace(
            result.context_drift_quarantine_transfer_certificate,
            context_drift_quarantine_certificate_hashes=result.context_drift_quarantine_transfer_certificate.context_drift_quarantine_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_context_drift_quarantine_transfer_certificate(invalid, result.report))

    def test_tampered_quarantine_certificate_fails(self) -> None:
        result = run_context_drift_quarantine_certified_experiment()
        invalid = replace(
            result.context_drift_quarantine_certificates[0],
            quarantine_reason="ignore_epoch",
            certificate_hash="",
        )

        self.assertFalse(validate_context_drift_quarantine_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
