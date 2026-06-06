from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_curriculum_transfer import (
    run_branch_curriculum_transfer_certified_experiment,
    run_branch_curriculum_transfer_experiment,
    validate_branch_curriculum_certificate,
    validate_branch_curriculum_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchCurriculumTransferExampleTests(unittest.TestCase):
    def test_certified_branch_curriculum_transfer(self) -> None:
        result = run_branch_curriculum_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_curriculum_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_curriculum_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 27)
        self.assertEqual(report.total_committed_count, 18)
        self.assertEqual(report.total_rejected_count, 9)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_sequence_success_count, 9)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.guided_curriculum_success_count, 6)
        self.assertEqual(report.guided_final_success_count, 3)
        self.assertEqual(report.same_budget_curriculum_count, 3)
        self.assertEqual(report.branch_curriculum_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_curriculum_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_curriculum_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_curriculum_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 21)
        self.assertEqual(len(certificate.branch_curriculum_certificate_hashes), 3)
        self.assertEqual(len(result.branch_curriculum_certificates), 3)

        for row, curriculum in zip(report.rows, result.branch_curriculum_certificates):
            self.assertEqual(row.curriculum_levels, (1, 2))
            self.assertEqual(len(row.source_actions), 3)
            self.assertEqual(len(row.static_actions), 3)
            self.assertEqual(len(row.guided_actions), 3)
            self.assertEqual(row.source_sequence_committed_count, 3)
            self.assertEqual(row.static_committed_count, 0)
            self.assertEqual(row.guided_curriculum_committed_count, 2)
            self.assertTrue(row.guided_final_committed)
            self.assertEqual(row.static_verifier_call_count, 3)
            self.assertEqual(row.guided_verifier_call_count, 3)
            self.assertTrue(row.same_budget)
            self.assertEqual(len(row.source_receipt_hashes), 3)
            self.assertEqual(len(row.static_receipt_hashes), 3)
            self.assertEqual(len(row.guided_curriculum_receipt_hashes), 2)
            self.assertEqual(len(row.guided_final_receipt_hashes), 1)
            self.assertTrue(validate_branch_curriculum_certificate(curriculum, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_curriculum_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.guided_curriculum_success_count, 6)
        self.assertEqual(report.guided_final_success_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_curriculum_transfer_certified_experiment()
        invalid = replace(
            result.branch_curriculum_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_curriculum_transfer_certificate(invalid, result.report))

    def test_missing_guided_final_fails_transfer_certificate(self) -> None:
        result = run_branch_curriculum_transfer_certified_experiment()
        invalid = replace(
            result.branch_curriculum_transfer_certificate,
            guided_final_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_curriculum_transfer_certificate(invalid, result.report))

    def test_missing_curriculum_certificate_fails_transfer_certificate(self) -> None:
        result = run_branch_curriculum_transfer_certified_experiment()
        invalid = replace(
            result.branch_curriculum_transfer_certificate,
            branch_curriculum_certificate_hashes=result.branch_curriculum_transfer_certificate.branch_curriculum_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_branch_curriculum_transfer_certificate(invalid, result.report))

    def test_tampered_curriculum_levels_fail(self) -> None:
        result = run_branch_curriculum_transfer_certified_experiment()
        invalid = replace(
            result.branch_curriculum_certificates[0],
            curriculum_levels=(1, 3),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_curriculum_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
