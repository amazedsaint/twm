from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_budget_transfer import (
    TARGET_BUDGET,
    run_branch_budget_transfer_certified_experiment,
    run_branch_budget_transfer_experiment,
    validate_branch_budget_certificate,
    validate_branch_budget_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchBudgetTransferExampleTests(unittest.TestCase):
    def test_certified_branch_budget_transfer(self) -> None:
        result = run_branch_budget_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_budget_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_budget_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 24)
        self.assertEqual(report.total_committed_count, 6)
        self.assertEqual(report.total_rejected_count, 15)
        self.assertEqual(report.total_abstained_count, 3)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.allocated_budget_success_count, 3)
        self.assertEqual(report.static_abstain_count, 3)
        self.assertEqual(report.allocated_abstain_count, 0)
        self.assertEqual(report.same_budget_allocation_count, 3)
        self.assertEqual(report.branch_budget_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 9)
        self.assertEqual(report.memory_receipt_count, 9)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_budget_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_budget_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_budget_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 9)
        self.assertEqual(len(certificate.branch_budget_certificate_hashes), 3)
        self.assertEqual(len(result.branch_budget_certificates), 3)
        self.assertTrue(all(validate_branch_budget_certificate(row) for row in result.branch_budget_certificates))

        for row, budget in zip(report.rows, result.branch_budget_certificates):
            self.assertEqual(row.budget, TARGET_BUDGET)
            self.assertEqual(row.static_action_costs, (1, 1, 2))
            self.assertEqual(row.allocated_action_costs, (1, 2))
            self.assertEqual(row.allocated_actions[-1], row.committed_target_action)
            self.assertFalse(row.static_budget_committed)
            self.assertTrue(row.allocated_budget_committed)
            self.assertEqual(row.static_verifier_cost, 2)
            self.assertEqual(row.allocated_verifier_cost, TARGET_BUDGET)
            self.assertEqual(row.static_abstained_count, 1)
            self.assertEqual(row.allocated_abstained_count, 0)
            self.assertTrue(row.same_budget)
            self.assertEqual(len(row.source_receipt_hashes), 3)
            self.assertEqual(len(row.static_receipt_hashes), 3)
            self.assertEqual(len(row.allocated_receipt_hashes), 2)
            self.assertTrue(validate_branch_budget_certificate(budget, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_budget_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.allocated_budget_success_count, 3)
        self.assertEqual(report.static_abstain_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_budget_transfer_certified_experiment()
        invalid = replace(
            result.branch_budget_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_budget_transfer_certificate(invalid, result.report))

    def test_missing_allocated_success_fails_transfer_certificate(self) -> None:
        result = run_branch_budget_transfer_certified_experiment()
        invalid = replace(
            result.branch_budget_transfer_certificate,
            allocated_budget_success_count=2,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_budget_transfer_certificate(invalid, result.report))

    def test_missing_budget_certificate_fails_transfer_certificate(self) -> None:
        result = run_branch_budget_transfer_certified_experiment()
        invalid = replace(
            result.branch_budget_transfer_certificate,
            branch_budget_certificate_hashes=result.branch_budget_transfer_certificate.branch_budget_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_branch_budget_transfer_certificate(invalid, result.report))

    def test_tampered_budget_certificate_fails(self) -> None:
        result = run_branch_budget_transfer_certified_experiment()
        invalid = replace(
            result.branch_budget_certificates[0],
            static_abstained_count=0,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_budget_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
