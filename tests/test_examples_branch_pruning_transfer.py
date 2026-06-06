from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_pruning_transfer import (
    run_branch_pruning_transfer_certified_experiment,
    run_branch_pruning_transfer_experiment,
    validate_branch_pruning_certificate,
    validate_branch_pruning_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchPruningTransferExampleTests(unittest.TestCase):
    def test_certified_branch_pruning_transfer(self) -> None:
        result = run_branch_pruning_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_pruning_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_pruning_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 21)
        self.assertEqual(report.total_committed_count, 6)
        self.assertEqual(report.total_rejected_count, 12)
        self.assertEqual(report.total_rolled_back_loser_count, 3)
        self.assertEqual(report.pruned_action_count, 6)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.pruned_budget_success_count, 3)
        self.assertEqual(report.same_budget_pruning_count, 3)
        self.assertEqual(report.branch_pruning_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_pruning_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_pruning_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_pruning_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 9)
        self.assertEqual(len(certificate.branch_pruning_certificate_hashes), 3)
        self.assertEqual(len(result.branch_pruning_certificates), 3)
        self.assertTrue(all(validate_branch_pruning_certificate(row) for row in result.branch_pruning_certificates))

        for row, pruning in zip(report.rows, result.branch_pruning_certificates):
            self.assertEqual(len(row.candidate_actions), 4)
            self.assertEqual(len(row.pruned_actions), 2)
            self.assertEqual(row.baseline_actions, row.pruned_actions)
            self.assertEqual(len(row.pruned_candidate_actions), 2)
            self.assertEqual(row.pruned_candidate_actions[0], row.committed_target_action)
            self.assertFalse(set(row.pruned_actions) & set(row.pruned_candidate_actions))
            self.assertFalse(row.static_budget_committed)
            self.assertTrue(row.pruned_budget_committed)
            self.assertTrue(row.same_budget)
            self.assertEqual(len(row.source_receipt_hashes), 3)
            self.assertEqual(len(row.static_receipt_hashes), 2)
            self.assertEqual(len(row.pruned_receipt_hashes), 2)
            self.assertTrue(validate_branch_pruning_certificate(pruning, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_pruning_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.pruned_budget_success_count, 3)
        self.assertEqual(report.pruned_action_count, 6)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_pruning_transfer_certified_experiment()
        invalid = replace(
            result.branch_pruning_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_pruning_transfer_certificate(invalid, result.report))

    def test_missing_pruned_success_fails_transfer_certificate(self) -> None:
        result = run_branch_pruning_transfer_certified_experiment()
        invalid = replace(
            result.branch_pruning_transfer_certificate,
            pruned_budget_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_pruning_transfer_certificate(invalid, result.report))

    def test_missing_pruning_certificate_fails_transfer_certificate(self) -> None:
        result = run_branch_pruning_transfer_certified_experiment()
        invalid = replace(
            result.branch_pruning_transfer_certificate,
            branch_pruning_certificate_hashes=result.branch_pruning_transfer_certificate.branch_pruning_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_branch_pruning_transfer_certificate(invalid, result.report))

    def test_tampered_pruning_certificate_fails(self) -> None:
        result = run_branch_pruning_transfer_certified_experiment()
        invalid = replace(
            result.branch_pruning_certificates[0],
            pruned_actions=result.branch_pruning_certificates[0].pruned_actions[:1],
            certificate_hash="",
        )

        self.assertFalse(validate_branch_pruning_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
