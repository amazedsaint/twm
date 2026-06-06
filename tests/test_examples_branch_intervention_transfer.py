from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_intervention_transfer import (
    branch_intervention_certificate_hash,
    branch_intervention_transfer_certificate_hash,
    run_branch_intervention_transfer_certified_experiment,
    run_branch_intervention_transfer_experiment,
    validate_branch_intervention_certificate,
    validate_branch_intervention_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate
from trwm.core import stable_hash


class BranchInterventionTransferExampleTests(unittest.TestCase):
    def test_branch_intervention_transfer_certifies_field_interventions(self) -> None:
        result = run_branch_intervention_transfer_certified_experiment()
        report = result.report
        evidence = result.evidence_certificate
        claim = result.claim_certificate
        transfer_certificate = result.branch_intervention_transfer_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_intervention_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.total_receipt_count, 12)
        self.assertEqual(report.total_committed_count, 6)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_reject_count, 3)
        self.assertEqual(report.source_commit_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.intervention_success_count, 3)
        self.assertEqual(report.same_budget_intervention_count, 3)
        self.assertEqual(report.branch_intervention_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 6)
        self.assertEqual(report.memory_receipt_count, 6)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_intervention_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_intervention_transfer_certificate(transfer_certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.receipt_count, report.total_receipt_count)
        self.assertEqual(evidence.receipt_hashes, transfer_certificate.receipt_hashes)
        self.assertEqual(evidence.committed_count, report.total_committed_count)
        self.assertEqual(evidence.rejected_count, report.total_rejected_count)
        self.assertIn("https://pmc.ncbi.nlm.nih.gov/articles/PMC2836213/", evidence.sources)

        self.assertEqual(len(result.branch_intervention_certificates), 3)
        for certificate, row in zip(result.branch_intervention_certificates, report.rows):
            self.assertTrue(validate_branch_intervention_certificate(certificate, row))
            self.assertTrue(row.source_rejected)
            self.assertTrue(row.source_committed)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.intervention_committed)
            self.assertTrue(row.same_budget)
            self.assertEqual(row.source_verifier_call_count, 2)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.intervention_verifier_call_count, 1)
            self.assertEqual(len(row.source_reject_receipt_hashes), 1)
            self.assertEqual(len(row.source_commit_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.intervention_target_receipt_hashes), 1)
            if row.intervention_direction == "increase":
                self.assertGreater(row.source_after_value, row.source_before_value)
                self.assertGreater(row.target_after_value, row.target_before_value)
            else:
                self.assertEqual(row.intervention_direction, "decrease")
                self.assertLess(row.source_after_value, row.source_before_value)
                self.assertLess(row.target_after_value, row.target_before_value)

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_intervention_transfer_experiment()

        self.assertEqual(report.experiment_id, "branch_intervention_transfer")
        self.assertEqual(report.intervention_success_count, report.domain_count)

    def test_transfer_certificate_detects_tampered_report_hash(self) -> None:
        result = run_branch_intervention_transfer_certified_experiment()
        certificate = result.branch_intervention_transfer_certificate
        tampered = replace(
            certificate,
            report_hash=stable_hash({"tampered": True}),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_intervention_transfer_certificate(tampered, result.report))

    def test_transfer_certificate_requires_intervention_success(self) -> None:
        result = run_branch_intervention_transfer_certified_experiment()
        certificate = result.branch_intervention_transfer_certificate
        tampered = replace(
            certificate,
            intervention_success_count=2,
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_intervention_transfer_certificate_hash(tampered))
        self.assertFalse(validate_branch_intervention_transfer_certificate(tampered, result.report))

    def test_branch_intervention_certificate_detects_invalid_direction(self) -> None:
        result = run_branch_intervention_transfer_certified_experiment()
        certificate = result.branch_intervention_certificates[0]
        row = result.report.rows[0]
        tampered = replace(
            certificate,
            target_after_value=certificate.target_before_value,
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_intervention_certificate_hash(tampered))
        self.assertFalse(validate_branch_intervention_certificate(tampered, row))


if __name__ == "__main__":
    unittest.main()
