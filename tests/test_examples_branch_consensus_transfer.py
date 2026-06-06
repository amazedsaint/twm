from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_consensus_transfer import (
    BRANCH_CONSENSUS_SOURCES,
    branch_consensus_certificate_hash,
    branch_consensus_transfer_certificate_hash,
    run_branch_consensus_transfer_certified_experiment,
    run_branch_consensus_transfer_experiment,
    validate_branch_consensus_certificate,
    validate_branch_consensus_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate
from trwm.core import stable_hash


class BranchConsensusTransferExampleTests(unittest.TestCase):
    def test_branch_consensus_transfer_certifies_majority_source_reuse(self) -> None:
        result = run_branch_consensus_transfer_certified_experiment()
        report = result.report
        evidence = result.evidence_certificate
        claim = result.claim_certificate
        transfer_certificate = result.branch_consensus_transfer_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_consensus_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.total_receipt_count, 15)
        self.assertEqual(report.total_committed_count, 12)
        self.assertEqual(report.total_rejected_count, 3)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_majority_success_count, 6)
        self.assertEqual(report.source_singleton_success_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.consensus_success_count, 3)
        self.assertEqual(report.same_budget_consensus_count, 3)
        self.assertEqual(report.branch_consensus_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_consensus_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_consensus_transfer_certificate(transfer_certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.receipt_count, report.total_receipt_count)
        self.assertEqual(evidence.receipt_hashes, transfer_certificate.receipt_hashes)
        self.assertIn("https://doi.org/10.1145/130385.130417", evidence.sources)
        self.assertEqual(tuple(evidence.sources), BRANCH_CONSENSUS_SOURCES)

        self.assertEqual(len(result.branch_consensus_certificates), 3)
        for certificate, row in zip(result.branch_consensus_certificates, report.rows):
            self.assertTrue(validate_branch_consensus_certificate(certificate, row))
            self.assertEqual(row.majority_support_count, 2)
            self.assertEqual(row.singleton_support_count, 1)
            self.assertEqual(row.required_support_count, 2)
            self.assertNotEqual(row.selected_family_id, row.singleton_family_id)
            self.assertEqual(row.source_majority_committed_count, 2)
            self.assertEqual(row.source_singleton_committed_count, 1)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.consensus_committed)
            self.assertTrue(row.same_budget)
            self.assertEqual(row.source_verifier_call_count, 3)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.consensus_verifier_call_count, 1)
            self.assertEqual(len(row.source_majority_receipt_hashes), 2)
            self.assertEqual(len(row.source_singleton_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.consensus_target_receipt_hashes), 1)

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_consensus_transfer_experiment()

        self.assertEqual(report.experiment_id, "branch_consensus_transfer")
        self.assertEqual(report.consensus_success_count, report.domain_count)

    def test_transfer_certificate_detects_tampered_report_hash(self) -> None:
        result = run_branch_consensus_transfer_certified_experiment()
        certificate = result.branch_consensus_transfer_certificate
        tampered = replace(
            certificate,
            report_hash=stable_hash({"tampered": True}),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_consensus_transfer_certificate(tampered, result.report))

    def test_transfer_certificate_requires_consensus_success(self) -> None:
        result = run_branch_consensus_transfer_certified_experiment()
        certificate = result.branch_consensus_transfer_certificate
        tampered = replace(
            certificate,
            consensus_success_count=2,
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_consensus_transfer_certificate_hash(tampered))
        self.assertFalse(validate_branch_consensus_transfer_certificate(tampered, result.report))

    def test_consensus_certificate_rejects_singleton_majority(self) -> None:
        result = run_branch_consensus_transfer_certified_experiment()
        certificate = result.branch_consensus_certificates[0]
        row = result.report.rows[0]
        tampered = replace(
            certificate,
            majority_support_count=1,
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_consensus_certificate_hash(tampered))
        self.assertFalse(validate_branch_consensus_certificate(tampered, row))

    def test_consensus_certificate_requires_target_commit(self) -> None:
        result = run_branch_consensus_transfer_certified_experiment()
        certificate = result.branch_consensus_certificates[0]
        row = result.report.rows[0]
        tampered = replace(
            certificate,
            consensus_committed=False,
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_consensus_certificate_hash(tampered))
        self.assertFalse(validate_branch_consensus_certificate(tampered, row))


if __name__ == "__main__":
    unittest.main()
