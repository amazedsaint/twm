from __future__ import annotations

from dataclasses import replace
import unittest

from examples.branch_composition_transfer import (
    run_branch_composition_transfer_certified_experiment,
    run_branch_composition_transfer_experiment,
    validate_branch_composition_certificate,
    validate_branch_composition_transfer_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class BranchCompositionTransferExampleTests(unittest.TestCase):
    def test_certified_branch_composition_transfer(self) -> None:
        result = run_branch_composition_transfer_certified_experiment()
        report = result.report
        certificate = result.branch_composition_transfer_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_composition_transfer.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 24)
        self.assertEqual(report.total_committed_count, 9)
        self.assertEqual(report.total_rejected_count, 15)
        self.assertEqual(report.total_rolled_back_loser_count, 0)
        self.assertEqual(report.source_branch_pair_count, 3)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.component_only_budget_success_count, 0)
        self.assertEqual(report.composed_budget_success_count, 3)
        self.assertEqual(report.same_budget_composition_count, 3)
        self.assertEqual(report.branch_composition_certificate_count, 3)
        self.assertEqual(report.memory_row_count, 12)
        self.assertEqual(report.memory_receipt_count, 12)
        self.assertTrue(report.memory_snapshot_valid)
        self.assertTrue(report.all_branch_composition_certificates_valid)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_branch_composition_transfer_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.domain, "branch_composition_transfer")
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 18)
        self.assertEqual(len(certificate.branch_composition_certificate_hashes), 3)
        self.assertEqual(len(result.branch_composition_certificates), 3)
        self.assertTrue(all(validate_branch_composition_certificate(row) for row in result.branch_composition_certificates))

        for row, composition in zip(report.rows, result.branch_composition_certificates):
            self.assertEqual(len(row.source_contexts), 2)
            self.assertEqual(len(row.fragment_keys), 2)
            self.assertEqual(len(row.source_committed_actions), 2)
            self.assertEqual(len(row.source_receipt_hashes), 4)
            self.assertEqual(len(row.source_branch_selection_certificate_hashes), 2)
            self.assertEqual(len(row.target_branch_selection_certificate_hashes), 4)
            self.assertEqual(len(row.static_receipt_hashes), 1)
            self.assertEqual(len(row.component_a_receipt_hashes), 1)
            self.assertEqual(len(row.component_b_receipt_hashes), 1)
            self.assertEqual(len(row.composed_receipt_hashes), 1)
            self.assertNotEqual(row.static_top_action, row.committed_target_action)
            self.assertNotEqual(row.component_a_top_action, row.committed_target_action)
            self.assertNotEqual(row.component_b_top_action, row.committed_target_action)
            self.assertEqual(row.composed_top_action, row.committed_target_action)
            self.assertFalse(row.static_budget_committed)
            self.assertFalse(row.component_a_budget_committed)
            self.assertFalse(row.component_b_budget_committed)
            self.assertTrue(row.composed_budget_committed)
            self.assertTrue(row.same_budget)
            self.assertTrue(validate_branch_composition_certificate(composition, row))

    def test_report_only_api_remains_available(self) -> None:
        report = run_branch_composition_transfer_experiment()

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.component_only_budget_success_count, 0)
        self.assertEqual(report.composed_budget_success_count, 3)

    def test_tampered_report_hash_fails_transfer_certificate(self) -> None:
        result = run_branch_composition_transfer_certified_experiment()
        invalid = replace(
            result.branch_composition_transfer_certificate,
            report_hash="0" * 64,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_composition_transfer_certificate(invalid, result.report))

    def test_component_only_success_count_fails_transfer_certificate(self) -> None:
        result = run_branch_composition_transfer_certified_experiment()
        invalid = replace(
            result.branch_composition_transfer_certificate,
            component_only_budget_success_count=1,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_composition_transfer_certificate(invalid, result.report))

    def test_missing_composition_certificate_fails_transfer_certificate(self) -> None:
        result = run_branch_composition_transfer_certified_experiment()
        invalid = replace(
            result.branch_composition_transfer_certificate,
            branch_composition_certificate_hashes=result.branch_composition_transfer_certificate.branch_composition_certificate_hashes[:2],
            certificate_hash="",
        )

        self.assertFalse(validate_branch_composition_transfer_certificate(invalid, result.report))

    def test_tampered_composition_certificate_fails(self) -> None:
        result = run_branch_composition_transfer_certified_experiment()
        invalid = replace(
            result.branch_composition_certificates[0],
            component_a_committed=True,
            certificate_hash="",
        )

        self.assertFalse(validate_branch_composition_certificate(invalid))


if __name__ == "__main__":
    unittest.main()
