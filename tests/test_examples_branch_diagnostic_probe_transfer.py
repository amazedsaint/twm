from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_diagnostic_probe_transfer import (
    branch_diagnostic_probe_certificate_hash,
    branch_diagnostic_probe_transfer_certificate_hash,
    run_branch_diagnostic_probe_transfer_certified_experiment,
    run_branch_diagnostic_probe_transfer_experiment,
    validate_branch_diagnostic_probe_certificate,
    validate_branch_diagnostic_probe_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate
from trwm.core import stable_hash


class BranchDiagnosticProbeTransferExampleTests(unittest.TestCase):
    def test_branch_diagnostic_probe_transfer_certifies_active_probe_reuse(self) -> None:
        result = run_branch_diagnostic_probe_transfer_certified_experiment()
        report = result.report
        evidence = result.evidence_certificate
        claim = result.claim_certificate
        transfer_certificate = result.branch_diagnostic_probe_transfer_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_diagnostic_probe_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.total_receipt_count, 18)
        self.assertEqual(report.total_committed_count, 9)
        self.assertEqual(report.total_rejected_count, 9)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_probe_reject_count, 3)
        self.assertEqual(report.source_probe_success_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.guided_probe_success_count, 3)
        self.assertEqual(report.guided_final_success_count, 3)
        self.assertEqual(report.same_budget_probe_count, 3)
        self.assertEqual(report.branch_diagnostic_probe_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 6)
        self.assertEqual(report.memory_receipt_count, 6)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_diagnostic_probe_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_diagnostic_probe_transfer_certificate(transfer_certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.receipt_count, report.total_receipt_count)
        self.assertEqual(evidence.receipt_hashes, transfer_certificate.receipt_hashes)
        self.assertIn("https://doi.org/10.1214/aoms/1177728069", evidence.sources)

        self.assertEqual(len(result.branch_diagnostic_probe_certificates), 3)
        for certificate, row in zip(result.branch_diagnostic_probe_certificates, report.rows):
            self.assertTrue(validate_branch_diagnostic_probe_certificate(certificate, row))
            self.assertTrue(row.source_probe_rejected)
            self.assertTrue(row.source_probe_committed)
            self.assertFalse(row.static_committed)
            self.assertTrue(row.guided_probe_committed)
            self.assertTrue(row.guided_final_committed)
            self.assertTrue(row.same_budget)
            self.assertEqual(row.source_verifier_call_count, 2)
            self.assertEqual(row.static_verifier_call_count, 2)
            self.assertEqual(row.guided_verifier_call_count, 2)
            self.assertEqual(len(row.source_reject_probe_receipt_hashes), 1)
            self.assertEqual(len(row.source_diagnostic_probe_receipt_hashes), 1)
            self.assertEqual(len(row.static_target_receipt_hashes), 2)
            self.assertEqual(len(row.guided_probe_receipt_hashes), 1)
            self.assertEqual(len(row.guided_final_receipt_hashes), 1)

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_diagnostic_probe_transfer_experiment()

        self.assertEqual(report.experiment_id, "branch_diagnostic_probe_transfer")
        self.assertEqual(report.guided_final_success_count, report.domain_count)

    def test_transfer_certificate_detects_tampered_report_hash(self) -> None:
        result = run_branch_diagnostic_probe_transfer_certified_experiment()
        certificate = result.branch_diagnostic_probe_transfer_certificate
        tampered = replace(
            certificate,
            report_hash=stable_hash({"tampered": True}),
            certificate_hash="",
        )

        self.assertFalse(validate_branch_diagnostic_probe_transfer_certificate(tampered, result.report))

    def test_transfer_certificate_requires_guided_final_success(self) -> None:
        result = run_branch_diagnostic_probe_transfer_certified_experiment()
        certificate = result.branch_diagnostic_probe_transfer_certificate
        tampered = replace(
            certificate,
            guided_final_success_count=2,
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_diagnostic_probe_transfer_certificate_hash(tampered))
        self.assertFalse(validate_branch_diagnostic_probe_transfer_certificate(tampered, result.report))

    def test_probe_certificate_detects_missing_static_receipt(self) -> None:
        result = run_branch_diagnostic_probe_transfer_certified_experiment()
        certificate = result.branch_diagnostic_probe_certificates[0]
        row = result.report.rows[0]
        tampered = replace(
            certificate,
            static_target_receipt_hashes=certificate.static_target_receipt_hashes[:1],
            certificate_hash="",
        )

        self.assertEqual(tampered.certificate_hash, branch_diagnostic_probe_certificate_hash(tampered))
        self.assertFalse(validate_branch_diagnostic_probe_certificate(tampered, row))


if __name__ == "__main__":
    unittest.main()
