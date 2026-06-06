from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_residual_template_transfer import (
    BRANCH_RESIDUAL_TEMPLATE_SOURCES,
    branch_residual_template_certificate_hash,
    branch_residual_template_transfer_certificate_hash,
    run_branch_residual_template_transfer_certified_experiment,
    run_branch_residual_template_transfer_experiment,
    validate_branch_residual_template_certificate,
    validate_branch_residual_template_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate
from trwm.core import stable_hash


class BranchResidualTemplateTransferExampleTests(unittest.TestCase):
    def test_branch_residual_template_transfer_certifies_repair_template_reuse(self) -> None:
        result = run_branch_residual_template_transfer_certified_experiment()
        report = result.report
        evidence = result.evidence_certificate
        claim = result.claim_certificate
        transfer_certificate = result.branch_residual_template_transfer_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_residual_template_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.total_receipt_count, 12)
        self.assertEqual(report.total_committed_count, 6)
        self.assertEqual(report.total_rejected_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_reject_count, 3)
        self.assertEqual(report.source_repair_success_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.template_success_count, 3)
        self.assertEqual(report.same_budget_template_count, 3)
        self.assertEqual(report.branch_residual_template_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 6)
        self.assertEqual(report.memory_receipt_count, 6)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_residual_template_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_residual_template_transfer_certificate(transfer_certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.receipt_count, report.total_receipt_count)
        self.assertEqual(evidence.receipt_hashes, transfer_certificate.receipt_hashes)
        self.assertIn("https://journals.sagepub.com/doi/10.3233/AIC-1994-7104", evidence.sources)
        self.assertEqual(tuple(evidence.sources), BRANCH_RESIDUAL_TEMPLATE_SOURCES)

        self.assertEqual(len(result.branch_residual_template_certificates), 3)
        for certificate, row in zip(result.branch_residual_template_certificates, report.rows):
            self.assertTrue(validate_branch_residual_template_certificate(certificate, row))
            self.assertTrue(row.source_rejected)
            self.assertTrue(row.source_repair_committed)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.templated_committed)
            self.assertTrue(row.same_budget)
            self.assertEqual(row.source_verifier_call_count, 2)
            self.assertEqual(row.static_verifier_call_count, 1)
            self.assertEqual(row.templated_verifier_call_count, 1)
            self.assertEqual(len(row.source_reject_receipt_hashes), 1)
            self.assertEqual(len(row.source_repair_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 1)
            self.assertEqual(len(row.templated_target_receipt_hashes), 1)
            self.assertGreaterEqual(len(row.template_field_keys), 1)
            self.assertEqual(len(set(row.template_field_keys)), len(row.template_field_keys))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_residual_template_transfer_experiment()

        self.assertEqual(report.experiment_id, "branch_residual_template_transfer")
        self.assertEqual(report.template_success_count, report.domain_count)

    def test_transfer_certificate_detects_tampered_report_hash(self) -> None:
        result = run_branch_residual_template_transfer_certified_experiment()
        certificate = result.branch_residual_template_transfer_certificate
        tampered = replace(
            certificate,
            report_hash=stable_hash({"tampered": True}),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_residual_template_transfer_certificate(tampered, result.report))

    def test_transfer_certificate_requires_template_success(self) -> None:
        result = run_branch_residual_template_transfer_certified_experiment()
        certificate = result.branch_residual_template_transfer_certificate
        tampered = replace(
            certificate,
            template_success_count=2,
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_residual_template_transfer_certificate_hash(tampered))
        self.assertFalse(validate_branch_residual_template_transfer_certificate(tampered, result.report))

    def test_residual_template_certificate_rejects_missing_template_fields(self) -> None:
        result = run_branch_residual_template_transfer_certified_experiment()
        certificate = result.branch_residual_template_certificates[0]
        row = result.report.rows[0]
        tampered = replace(
            certificate,
            template_field_keys=(),
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_residual_template_certificate_hash(tampered))
        self.assertFalse(validate_branch_residual_template_certificate(tampered, row))

    def test_residual_template_certificate_requires_target_commit(self) -> None:
        result = run_branch_residual_template_transfer_certified_experiment()
        certificate = result.branch_residual_template_certificates[0]
        row = result.report.rows[0]
        tampered = replace(
            certificate,
            templated_committed=False,
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_residual_template_certificate_hash(tampered))
        self.assertFalse(validate_branch_residual_template_certificate(tampered, row))


if __name__ == "__main__":
    unittest.main()
