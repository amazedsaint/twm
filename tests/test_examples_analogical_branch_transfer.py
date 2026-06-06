from __future__ import annotations

from dataclasses import replace
import unittest

from examples.analogical_branch_transfer import (
    run_analogical_branch_transfer_certified_experiment,
    run_analogical_branch_transfer_experiment,
    validate_analogical_branch_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class AnalogicalBranchTransferExampleTests(unittest.TestCase):
    def test_certified_experiment_validates_cross_context_exploration(self) -> None:
        result = run_analogical_branch_transfer_certified_experiment()

        report = result.report
        certificate = result.analogical_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.analogical_branch_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 36)
        self.assertEqual(report.total_committed_count, 12)
        self.assertEqual(report.total_rejected_count, 12)
        self.assertEqual(report.total_rolled_back_loser_count, 12)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.ancestor_budget_success_count, 3)
        self.assertEqual(report.misleading_transfer_blocked_count, 3)
        self.assertTrue(report.ancestor_memory_snapshot_valid)
        self.assertTrue(report.misleading_memory_snapshot_valid)
        self.assertEqual(report.ancestor_memory_row_count, 18)
        self.assertEqual(report.misleading_memory_row_count, 9)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_analogical_branch_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "cross_context_analogical_branch_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 18)
        self.assertEqual(certificate.ancestor_memory_snapshot_hash, report.ancestor_memory_snapshot_hash)
        self.assertEqual(certificate.misleading_memory_snapshot_hash, report.misleading_memory_snapshot_hash)

        for row in report.rows:
            self.assertEqual(len(row.ancestor_contexts), 2)
            self.assertEqual(len(row.source_receipt_hashes), 6)
            self.assertEqual(len(row.source_branch_certificate_hashes), 2)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.ancestor_target_receipt_hashes), 1)
            self.assertEqual(len(row.misleading_source_receipt_hashes), 3)
            self.assertEqual(len(row.misleading_target_receipt_hashes), 1)
            self.assertFalse(row.static_budget_committed)
            self.assertTrue(row.ancestor_budget_committed)
            self.assertFalse(row.misleading_budget_committed)
            self.assertTrue(row.misleading_transfer_blocked)
            self.assertEqual(row.ancestor_top_action, row.committed_target_action)
            self.assertNotEqual(row.misleading_top_action, row.committed_target_action)

    def test_report_only_api_remains_available(self) -> None:
        report = run_analogical_branch_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.ancestor_budget_success_count, 3)
        self.assertEqual(report.misleading_transfer_blocked_count, 3)

    def test_tampered_report_hash_fails_certificate(self) -> None:
        result = run_analogical_branch_transfer_certified_experiment()
        tampered = replace(result.analogical_certificate, report_hash="0" * 64, certificate_hash="")

        self.assertFalse(validate_analogical_branch_transfer_certificate(tampered, result.report))

    def test_missing_misleading_block_fails_certificate(self) -> None:
        result = run_analogical_branch_transfer_certified_experiment()
        invalid = replace(result.analogical_certificate, misleading_transfer_blocked_count=2, certificate_hash="")

        self.assertFalse(validate_analogical_branch_transfer_certificate(invalid, result.report))


if __name__ == "__main__":
    unittest.main()
