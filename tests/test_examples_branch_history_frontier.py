from __future__ import annotations

import unittest

from examples.analogical_branch_transfer import run_analogical_branch_transfer_certified_experiment
from examples.ancestral_branch_exploration import run_ancestral_branch_exploration_certified_experiment
from examples.branch_abstraction_transfer import run_branch_abstraction_transfer_certified_experiment
from examples.branch_budget_transfer import run_branch_budget_transfer_certified_experiment
from examples.branch_composition_transfer import run_branch_composition_transfer_certified_experiment
from examples.branch_contingency_transfer import run_branch_contingency_transfer_certified_experiment
from examples.branch_counterfactual_transfer import run_branch_counterfactual_transfer_certified_experiment
from examples.branch_diversity_transfer import run_branch_diversity_transfer_certified_experiment
from examples.branch_hindsight_relabel_transfer import run_branch_hindsight_relabel_transfer_certified_experiment
from examples.branch_intervention_transfer import run_branch_intervention_transfer_certified_experiment
from examples.branch_prerequisite_transfer import run_branch_prerequisite_transfer_certified_experiment
from examples.branch_pruning_transfer import run_branch_pruning_transfer_certified_experiment
from examples.branch_history_frontier import (
    build_branch_history_frontier_result,
    run_branch_history_frontier_experiment,
    tamper_first_child_primary_certificate,
)
from examples.context_query_policy_transfer import run_context_query_policy_transfer_certified_experiment
from examples.context_drift_quarantine import run_context_drift_quarantine_certified_experiment
from examples.context_refinement_transfer import run_context_refinement_transfer_certified_experiment
from examples.context_retention_transfer import run_context_retention_transfer_certified_experiment
from examples.context_selection_transfer import run_context_selection_transfer_certified_experiment
from trwm.claims import validate_claim_certificate


class TestBranchHistoryFrontierExample(unittest.TestCase):
    def test_branch_history_frontier_aggregates_certified_stages(self) -> None:
        result = run_branch_history_frontier_experiment()
        report = result.report
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.branch_history_frontier.v1")
        self.assertEqual(report.stage_count, 17)
        self.assertEqual(
            report.child_experiment_ids,
            (
                "ancestral_branch_exploration",
                "branch_counterfactual_transfer",
                "branch_abstraction_transfer",
                "branch_prerequisite_transfer",
                "branch_contingency_transfer",
                "branch_hindsight_relabel_transfer",
                "branch_intervention_transfer",
                "analogical_branch_transfer",
                "context_selection_transfer",
                "context_refinement_transfer",
                "context_query_policy_transfer",
                "context_drift_quarantine",
                "branch_pruning_transfer",
                "branch_diversity_transfer",
                "branch_budget_transfer",
                "branch_composition_transfer",
                "context_retention_transfer",
            ),
        )
        self.assertEqual(
            tuple(row.stage for row in report.rows),
            (
                "receipt_bound_ordering",
                "accepted_loser_counterfactual_reuse",
                "option_family_branch_abstraction",
                "receipt_bound_prerequisite_ordering",
                "regime_conditioned_branch_reuse",
                "hindsight_goal_relabeling",
                "receipt_bound_field_intervention",
                "explicit_ancestor_reuse",
                "certified_context_selection",
                "counterexample_refinement",
                "heldout_query_policy_conflict",
                "context_drift_quarantine",
                "receipt_bound_branch_pruning",
                "diversity_certified_family_coverage",
                "receipt_bound_budget_allocation",
                "receipt_bound_branch_composition",
                "retained_memory_influence",
            ),
        )
        self.assertTrue(report.all_evidence_valid)
        self.assertTrue(report.all_claims_supported)
        self.assertTrue(report.all_primary_certificates_valid)
        self.assertEqual(report.total_receipt_count, 414)
        self.assertEqual(report.total_committed_count, 156)
        self.assertEqual(report.total_rejected_count, 159)
        self.assertEqual(report.total_invalid_commit_count, 0)
        self.assertEqual(report.same_budget_stage_count, 17)
        self.assertEqual(report.branch_abstraction_certificate_count, 3)
        self.assertEqual(report.branch_prerequisite_certificate_count, 3)
        self.assertEqual(report.branch_contingency_certificate_count, 3)
        self.assertEqual(report.matched_source_context_count, 3)
        self.assertEqual(report.branch_hindsight_relabel_certificate_count, 3)
        self.assertEqual(report.relabeled_goal_count, 3)
        self.assertEqual(report.branch_intervention_certificate_count, 3)
        self.assertEqual(report.intervention_success_count, 3)
        self.assertEqual(report.counterfactual_certificate_count, 3)
        self.assertEqual(report.rolled_back_counterfactual_count, 3)
        self.assertEqual(report.branch_conflict_certificate_count, 6)
        self.assertEqual(report.query_policy_certificate_count, 6)
        self.assertEqual(report.drift_quarantine_certificate_count, 3)
        self.assertEqual(report.quarantined_context_count, 3)
        self.assertEqual(report.branch_pruning_certificate_count, 3)
        self.assertEqual(report.pruned_action_count, 6)
        self.assertEqual(report.branch_diversity_certificate_count, 3)
        self.assertEqual(report.diverse_family_count, 3)
        self.assertEqual(report.branch_budget_certificate_count, 3)
        self.assertEqual(report.static_abstain_count, 3)
        self.assertEqual(report.branch_composition_certificate_count, 3)
        self.assertEqual(report.retention_certificate_count, 3)
        self.assertEqual(report.influence_certificate_count, 3)
        self.assertTrue(all(row.same_budget_comparison for row in report.rows))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")

    def test_frontier_claim_rejects_tampered_primary_certificate(self) -> None:
        children = (
            run_ancestral_branch_exploration_certified_experiment(),
            run_branch_counterfactual_transfer_certified_experiment(),
            run_branch_abstraction_transfer_certified_experiment(),
            run_branch_prerequisite_transfer_certified_experiment(),
            run_branch_contingency_transfer_certified_experiment(),
            run_branch_hindsight_relabel_transfer_certified_experiment(),
            run_branch_intervention_transfer_certified_experiment(),
            run_analogical_branch_transfer_certified_experiment(),
            run_context_selection_transfer_certified_experiment(),
            run_context_refinement_transfer_certified_experiment(),
            run_context_query_policy_transfer_certified_experiment(),
            run_context_drift_quarantine_certified_experiment(),
            run_branch_pruning_transfer_certified_experiment(),
            run_branch_diversity_transfer_certified_experiment(),
            run_branch_budget_transfer_certified_experiment(),
            run_branch_composition_transfer_certified_experiment(),
            run_context_retention_transfer_certified_experiment(),
        )
        result = build_branch_history_frontier_result(tamper_first_child_primary_certificate(children))

        self.assertFalse(result.report.all_primary_certificates_valid)
        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertIn("all_primary_certificates_valid", result.claim_certificate.failed_keys)


if __name__ == "__main__":
    unittest.main()
