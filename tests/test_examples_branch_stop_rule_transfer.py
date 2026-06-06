from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_stop_rule_transfer import (
    TARGET_STOP_BUDGET,
    run_branch_stop_rule_transfer_certified_experiment,
    run_branch_stop_rule_transfer_experiment,
    validate_branch_stop_rule_certificate,
    validate_branch_stop_rule_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchStopRuleTransferExampleTests(unittest.TestCase):
    def test_certified_branch_stop_rule_transfer(self) -> None:
        result = run_branch_stop_rule_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_stop_rule_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_stop_rule_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 21)
        self.assertEqual(report.total_committed_count, 3)
        self.assertEqual(report.total_rejected_count, 12)
        self.assertEqual(report.total_abstained_count, 6)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_commit_count, 3)
        self.assertEqual(report.source_reject_count, 6)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.stopped_success_count, 0)
        self.assertEqual(report.static_verifier_call_count, 6)
        self.assertEqual(report.stopped_verifier_call_count, 0)
        self.assertEqual(report.stopped_abstain_count, 6)
        self.assertEqual(report.avoided_verifier_call_count, 6)
        self.assertEqual(report.same_budget_stop_count, 3)
        self.assertEqual(report.branch_stop_rule_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_stop_rule_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_stop_rule_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_stop_rule_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 9)
        self.assertEqual(len(certificate.branch_stop_rule_certificate_hashes), 3)
        self.assertEqual(len(result.branch_stop_rule_certificates), 3)

        for row, stop_rule in zip(report.rows, result.branch_stop_rule_certificates):
            self.assertEqual(row.budget, TARGET_STOP_BUDGET)
            self.assertEqual(row.static_actions, row.stopped_actions)
            self.assertEqual(len(row.source_actions), 3)
            self.assertEqual(len(row.static_actions), 2)
            self.assertEqual(row.source_rejected_count, 2)
            self.assertEqual(row.source_committed_count, 1)
            self.assertFalse(row.static_committed)
            self.assertFalse(row.stopped_committed)
            self.assertEqual(row.static_verifier_call_count, TARGET_STOP_BUDGET)
            self.assertEqual(row.stopped_verifier_call_count, 0)
            self.assertEqual(row.stopped_abstain_count, TARGET_STOP_BUDGET)
            self.assertEqual(row.avoided_verifier_call_count, TARGET_STOP_BUDGET)
            self.assertEqual(row.unused_verifier_budget, TARGET_STOP_BUDGET)
            self.assertTrue(row.same_budget)
            self.assertEqual(len(row.source_receipt_hashes), 3)
            self.assertEqual(len(row.static_receipt_hashes), 2)
            self.assertEqual(len(row.stopped_receipt_hashes), 2)
            self.assertTrue(validate_branch_stop_rule_certificate(stop_rule, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_stop_rule_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_success_count, 0)
        self.assertEqual(report.stopped_success_count, 0)
        self.assertEqual(report.avoided_verifier_call_count, 6)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_stop_rule_transfer_certified_experiment()
        invalid = replace(
            result.branch_stop_rule_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_stop_rule_transfer_certificate(invalid, result.report))

    def test_missing_abstain_count_fails_transfer_certificate(self) -> None:
        result = run_branch_stop_rule_transfer_certified_experiment()
        invalid = replace(
            result.branch_stop_rule_transfer_certificate,
            stopped_abstain_count=5,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_stop_rule_transfer_certificate(invalid, result.report))

    def test_missing_stop_rule_certificate_fails_transfer_certificate(self) -> None:
        result = run_branch_stop_rule_transfer_certified_experiment()
        invalid = replace(
            result.branch_stop_rule_transfer_certificate,
            branch_stop_rule_certificate_hashes=result.branch_stop_rule_transfer_certificate.branch_stop_rule_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_branch_stop_rule_transfer_certificate(invalid, result.report))

    def test_tampered_stop_rule_certificate_fails(self) -> None:
        result = run_branch_stop_rule_transfer_certified_experiment()
        invalid = replace(
            result.branch_stop_rule_certificates[0],
            stopped_verifier_call_count=1,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_stop_rule_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
