from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_commutativity_transfer import (
    run_branch_commutativity_transfer_certified_experiment,
    run_branch_commutativity_transfer_experiment,
    validate_branch_commutativity_certificate,
    validate_branch_commutativity_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchCommutativityTransferExampleTests(unittest.TestCase):
    def test_certified_branch_commutativity_transfer(self) -> None:
        result = run_branch_commutativity_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_commutativity_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_commutativity_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 15)
        self.assertEqual(report.total_committed_count, 9)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_ab_committed_count, 3)
        self.assertEqual(report.source_ba_committed_count, 3)
        self.assertEqual(report.source_conflict_rejected_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.commutative_success_count, 3)
        self.assertEqual(report.same_budget_commutativity_count, 3)
        self.assertEqual(report.branch_commutativity_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_commutativity_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_commutativity_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_commutativity_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 15)
        self.assertEqual(len(certificate.branch_commutativity_certificate_hashes), 3)
        self.assertEqual(len(result.branch_commutativity_certificates), 3)
        self.assertTrue(report.sources)

        for row, commutativity in zip(report.rows, result.branch_commutativity_certificates):
            self.assertIn(":independent_ab_ba", row.canonical_order_key)
            self.assertIn(":dependent_conflict_order", row.conflict_order_key)
            self.assertNotEqual(row.canonical_order_key, row.conflict_order_key)
            self.assertTrue(row.source_ab_committed)
            self.assertTrue(row.source_ba_committed)
            self.assertTrue(row.source_conflict_rejected)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.commutative_committed)
            self.assertEqual(row.source_verifier_call_count, 3)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.commutative_verifier_call_count, 1)
            self.assertEqual(len(row.source_ab_receipt_hashes), 1)
            self.assertEqual(len(row.source_ba_receipt_hashes), 1)
            self.assertEqual(len(row.source_conflict_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.commutative_target_receipt_hashes), 1)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_commutativity_certificate(commutativity, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_commutativity_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.commutative_success_count, 3)
        self.assertEqual(report.same_budget_commutativity_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_commutativity_transfer_certified_experiment()
        invalid = replace(
            result.branch_commutativity_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_commutativity_transfer_certificate(invalid, result.report))

    def test_missing_commutative_success_fails_transfer_certificate(self) -> None:
        result = run_branch_commutativity_transfer_certified_experiment()
        invalid = replace(
            result.branch_commutativity_transfer_certificate,
            commutative_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_commutativity_transfer_certificate(invalid, result.report))

    def test_tampered_canonical_order_key_fails(self) -> None:
        result = run_branch_commutativity_transfer_certified_experiment()
        invalid = replace(
            result.branch_commutativity_certificates[0],
            canonical_order_key=result.branch_commutativity_certificates[0].conflict_order_key,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_commutativity_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
