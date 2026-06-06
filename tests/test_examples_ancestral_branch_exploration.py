from __future__ import annotations

from dataclasses import replace
import unittest

from examples.ancestral_branch_exploration import (
    ANCESTRAL_BRANCH_SOURCES,
    run_ancestral_branch_exploration_certified_experiment,
    run_ancestral_branch_exploration_experiment,
    validate_ancestral_branch_exploration_certificate,
)
from examples.common import validate_example_evidence_certificate
from trwm.claims import validate_claim_certificate


class AncestralBranchExplorationExampleTests(unittest.TestCase):
    def test_certified_experiment_validates_and_improves_budgeted_exploration(self) -> None:
        result = run_ancestral_branch_exploration_certified_experiment()

        report = result.report
        certificate = result.exploration_certificate
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertEqual(report.domain_count, 3)
        self.assertEqual(report.domains, ("robotics_replan", "molecule_repair", "material_process"))
        self.assertEqual(report.total_receipt_count, 33)
        self.assertEqual(report.total_committed_count, 12)
        self.assertEqual(report.total_rejected_count, 12)
        self.assertEqual(report.total_rolled_back_loser_count, 9)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.learned_budget_success_count, 3)
        self.assertEqual(report.static_winner_rank_sum, 9)
        self.assertEqual(report.learned_winner_rank_sum, 3)
        self.assertTrue(report.all_branch_selection_certificates_valid)
        self.assertTrue(report.all_branch_selection_audits_valid)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)

        self.assertTrue(validate_ancestral_branch_exploration_certificate(certificate, report))
        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")

        self.assertEqual(len(certificate.receipt_hashes), report.total_receipt_count)
        self.assertEqual(evidence.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(len(certificate.branch_selection_certificate_hashes), 15)
        self.assertEqual(set(evidence.sources), set(ANCESTRAL_BRANCH_SOURCES))
        self.assertEqual(evidence.domain, "cross_domain_ancestral_exploration")

        for row in report.rows:
            self.assertFalse(row.static_budget_committed)
            self.assertTrue(row.learned_budget_committed)
            self.assertEqual(row.learned_top_action, row.committed_training_action)
            self.assertNotEqual(row.static_top_action, row.committed_training_action)
            self.assertEqual(row.static_winner_rank, 3)
            self.assertEqual(row.learned_winner_rank, 1)
            self.assertEqual(len(row.training_receipt_hashes), 9)
            self.assertEqual(len(row.training_branch_certificate_hashes), 3)
            self.assertEqual(len(row.static_budget_receipt_hashes), 1)
            self.assertEqual(len(row.learned_budget_receipt_hashes), 1)

    def test_report_only_api_remains_available(self) -> None:
        report = run_ancestral_branch_exploration_experiment(training_episodes_per_domain=2)

        self.assertEqual(report.training_episodes_per_domain, 2)
        self.assertEqual(report.total_receipt_count, 24)
        self.assertEqual(report.total_committed_count, 9)
        self.assertEqual(report.total_rejected_count, 9)
        self.assertEqual(report.total_rolled_back_loser_count, 6)
        self.assertEqual(report.static_budget_success_count, 0)
        self.assertEqual(report.learned_budget_success_count, 3)

    def test_tampered_report_hash_fails_exploration_certificate(self) -> None:
        result = run_ancestral_branch_exploration_certified_experiment()
        tampered = replace(result.exploration_certificate, report_hash="0" * 64, certificate_hash="")

        self.assertFalse(validate_ancestral_branch_exploration_certificate(tampered, result.report))

    def test_invalid_learned_success_count_fails_exploration_certificate(self) -> None:
        result = run_ancestral_branch_exploration_certified_experiment()
        invalid = replace(result.exploration_certificate, learned_budget_success_count=2, certificate_hash="")

        self.assertFalse(validate_ancestral_branch_exploration_certificate(invalid, result.report))


if __name__ == "__main__":
    unittest.main()
