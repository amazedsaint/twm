from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_continuation_transfer import (
    run_branch_continuation_transfer_certified_experiment,
    run_branch_continuation_transfer_experiment,
    validate_branch_continuation_certificate,
    validate_branch_continuation_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchContinuationTransferExampleTests(unittest.TestCase):
    def test_certified_branch_continuation_transfer(self) -> None:
        result = run_branch_continuation_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_continuation_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_continuation_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 30)
        self.assertEqual(report.total_committed_count, 18)
        self.assertEqual(report.total_rejected_count, 12)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_continuation_committed_count, 9)
        self.assertEqual(report.source_jump_rejected_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.continuation_success_count, 3)
        self.assertEqual(report.same_budget_continuation_count, 3)
        self.assertEqual(report.branch_continuation_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 12)
        self.assertEqual(report.memory_receipt_count, 12)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_continuation_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_continuation_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_continuation_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 24)
        self.assertEqual(len(certificate.branch_continuation_certificate_hashes), 3)
        self.assertEqual(len(result.branch_continuation_certificates), 3)
        self.assertTrue(report.sources)

        for row, continuation in zip(report.rows, result.branch_continuation_certificates):
            self.assertEqual(row.path_parameter_id, "lambda")
            self.assertEqual(row.lambda_sequence, (0.33, 0.66, 1.0))
            self.assertAlmostEqual(row.max_lambda_step, 0.34, places=6)
            self.assertEqual(len(row.source_continuation_action_ids), 3)
            self.assertEqual(len(row.static_target_action_ids), 3)
            self.assertEqual(len(row.continuation_target_action_ids), 3)
            self.assertEqual(row.source_continuation_committed_count, 3)
            self.assertEqual(row.source_jump_rejected_count, 1)
            self.assertEqual(row.static_committed_count, 0)
            self.assertEqual(row.continuation_committed_count, 3)
            self.assertFalse(row.static_final_committed)
            self.assertTrue(row.continuation_final_committed)
            self.assertEqual(row.source_verifier_call_count, 4)
            self.assertEqual(row.static_verifier_call_count, 3)
            self.assertEqual(row.continuation_verifier_call_count, 3)
            self.assertEqual(len(row.source_continuation_receipt_hashes), 3)
            self.assertEqual(len(row.source_jump_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 3)
            self.assertEqual(len(row.continuation_target_receipt_hashes), 3)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_continuation_certificate(continuation, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_continuation_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.continuation_success_count, 3)
        self.assertEqual(report.same_budget_continuation_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_continuation_transfer_certified_experiment()
        invalid = replace(
            result.branch_continuation_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_continuation_transfer_certificate(invalid, result.report))

    def test_missing_continuation_success_fails_transfer_certificate(self) -> None:
        result = run_branch_continuation_transfer_certified_experiment()
        invalid = replace(
            result.branch_continuation_transfer_certificate,
            continuation_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_continuation_transfer_certificate(invalid, result.report))

    def test_tampered_lambda_sequence_fails(self) -> None:
        result = run_branch_continuation_transfer_certified_experiment()
        invalid = replace(
            result.branch_continuation_certificates[0],
            lambda_sequence=(0.5, 0.33, 1.0),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_continuation_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
