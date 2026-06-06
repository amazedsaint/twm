from __future__ import annotations

import unittest

from examples.analogical_branch_transfer import run_analogical_branch_transfer_certified_experiment
from examples.ancestral_branch_exploration import run_ancestral_branch_exploration_certified_experiment
from examples.branch_abstraction_transfer import run_branch_abstraction_transfer_certified_experiment
from examples.branch_boundary_bracket_transfer import run_branch_boundary_bracket_transfer_certified_experiment
from examples.branch_budget_transfer import run_branch_budget_transfer_certified_experiment
from examples.branch_composition_transfer import run_branch_composition_transfer_certified_experiment
from examples.branch_consensus_transfer import run_branch_consensus_transfer_certified_experiment
from examples.branch_contingency_transfer import run_branch_contingency_transfer_certified_experiment
from examples.branch_constraint_transfer import run_branch_constraint_transfer_certified_experiment
from examples.branch_confidence_transfer import run_branch_confidence_transfer_certified_experiment
from examples.branch_credit_assignment_transfer import run_branch_credit_assignment_transfer_certified_experiment
from examples.branch_propensity_match_transfer import run_branch_propensity_match_transfer_certified_experiment
from examples.branch_robustness_transfer import run_branch_robustness_transfer_certified_experiment
from examples.branch_calibration_transfer import run_branch_calibration_transfer_certified_experiment
from examples.branch_conformal_transfer import run_branch_conformal_transfer_certified_experiment
from examples.branch_active_subspace_transfer import run_branch_active_subspace_transfer_certified_experiment
from examples.branch_continuation_transfer import run_branch_continuation_transfer_certified_experiment
from examples.branch_switch_transfer import run_branch_switch_transfer_certified_experiment
from examples.branch_transposition_transfer import run_branch_transposition_transfer_certified_experiment
from examples.branch_outlier_filter_transfer import run_branch_outlier_filter_transfer_certified_experiment
from examples.branch_pareto_transfer import run_branch_pareto_transfer_certified_experiment
from examples.branch_provenance_guard_transfer import run_branch_provenance_guard_transfer_certified_experiment
from examples.branch_counterfactual_transfer import run_branch_counterfactual_transfer_certified_experiment
from examples.branch_curriculum_transfer import run_branch_curriculum_transfer_certified_experiment
from examples.branch_diagnostic_probe_transfer import run_branch_diagnostic_probe_transfer_certified_experiment
from examples.branch_diversity_transfer import run_branch_diversity_transfer_certified_experiment
from examples.branch_hindsight_relabel_transfer import run_branch_hindsight_relabel_transfer_certified_experiment
from examples.branch_invariant_transfer import run_branch_invariant_transfer_certified_experiment
from examples.branch_intervention_transfer import run_branch_intervention_transfer_certified_experiment
from examples.branch_prerequisite_transfer import run_branch_prerequisite_transfer_certified_experiment
from examples.branch_pruning_transfer import run_branch_pruning_transfer_certified_experiment
from examples.branch_recency_weight_transfer import run_branch_recency_weight_transfer_certified_experiment
from examples.branch_restart_transfer import run_branch_restart_transfer_certified_experiment
from examples.branch_symmetry_transfer import run_branch_symmetry_transfer_certified_experiment
from examples.branch_residual_template_transfer import run_branch_residual_template_transfer_certified_experiment
from examples.branch_stop_rule_transfer import run_branch_stop_rule_transfer_certified_experiment
from examples.branch_trust_region_transfer import run_branch_trust_region_transfer_certified_experiment
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
        self.assertEqual(report.stage_count, 42)
        self.assertEqual(
            report.child_experiment_ids,
            (
                "ancestral_branch_exploration",
                "branch_counterfactual_transfer",
                "branch_abstraction_transfer",
                "branch_prerequisite_transfer",
                "branch_curriculum_transfer",
                "branch_contingency_transfer",
                "branch_hindsight_relabel_transfer",
                "branch_intervention_transfer",
                "branch_diagnostic_probe_transfer",
                "branch_residual_template_transfer",
                "branch_boundary_bracket_transfer",
                "branch_consensus_transfer",
                "branch_invariant_transfer",
                "branch_trust_region_transfer",
                "analogical_branch_transfer",
                "context_selection_transfer",
                "context_refinement_transfer",
                "context_query_policy_transfer",
                "context_drift_quarantine",
                "branch_recency_weight_transfer",
                "branch_restart_transfer",
                "branch_symmetry_transfer",
                "branch_constraint_transfer",
                "branch_confidence_transfer",
                "branch_pareto_transfer",
                "branch_outlier_filter_transfer",
                "branch_provenance_guard_transfer",
                "branch_credit_assignment_transfer",
                "branch_propensity_match_transfer",
                "branch_robustness_transfer",
                "branch_calibration_transfer",
                "branch_conformal_transfer",
                "branch_active_subspace_transfer",
                "branch_continuation_transfer",
                "branch_switch_transfer",
                "branch_transposition_transfer",
                "branch_pruning_transfer",
                "branch_diversity_transfer",
                "branch_budget_transfer",
                "branch_stop_rule_transfer",
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
                "receipt_bound_curriculum_sequence",
                "regime_conditioned_branch_reuse",
                "hindsight_goal_relabeling",
                "receipt_bound_field_intervention",
                "receipt_bound_diagnostic_probe",
                "receipt_bound_residual_template",
                "receipt_bound_boundary_bracket",
                "receipt_bound_source_consensus",
                "contrastive_branch_invariant",
                "receipt_bound_trust_region_radius",
                "explicit_ancestor_reuse",
                "certified_context_selection",
                "counterexample_refinement",
                "heldout_query_policy_conflict",
                "context_drift_quarantine",
                "recency_weighted_source_freshness",
                "receipt_bound_restart_anchor",
                "receipt_bound_symmetry_transform",
                "receipt_bound_pairwise_constraint",
                "receipt_bound_confidence_support",
                "receipt_bound_pareto_front",
                "receipt_bound_outlier_filter",
                "receipt_bound_provenance_guard",
                "receipt_bound_credit_assignment",
                "receipt_bound_propensity_match",
                "receipt_bound_uncertainty_set_coverage",
                "receipt_bound_confidence_bin_calibration",
                "receipt_bound_nonconformity_quantile",
                "receipt_bound_active_subspace_projection",
                "receipt_bound_continuation_path",
                "receipt_bound_branch_switchpoint",
                "receipt_bound_canonical_transposition",
                "receipt_bound_branch_pruning",
                "diversity_certified_family_coverage",
                "receipt_bound_budget_allocation",
                "receipt_bound_stop_rule_abstention",
                "receipt_bound_branch_composition",
                "retained_memory_influence",
            ),
        )
        self.assertTrue(report.all_evidence_valid)
        self.assertTrue(report.all_claims_supported)
        self.assertTrue(report.all_primary_certificates_valid)
        self.assertEqual(report.total_receipt_count, 813)
        self.assertEqual(report.total_committed_count, 399)
        self.assertEqual(report.total_rejected_count, 309)
        self.assertEqual(report.total_invalid_commit_count, 0)
        self.assertEqual(report.same_budget_stage_count, 42)
        self.assertEqual(report.branch_abstraction_certificate_count, 3)
        self.assertEqual(report.branch_prerequisite_certificate_count, 3)
        self.assertEqual(report.branch_curriculum_certificate_count, 3)
        self.assertEqual(report.guided_curriculum_success_count, 6)
        self.assertEqual(report.branch_contingency_certificate_count, 3)
        self.assertEqual(report.matched_source_context_count, 3)
        self.assertEqual(report.branch_hindsight_relabel_certificate_count, 3)
        self.assertEqual(report.relabeled_goal_count, 3)
        self.assertEqual(report.branch_intervention_certificate_count, 3)
        self.assertEqual(report.intervention_success_count, 3)
        self.assertEqual(report.branch_diagnostic_probe_certificate_count, 3)
        self.assertEqual(report.guided_probe_success_count, 3)
        self.assertEqual(report.guided_final_success_count, 3)
        self.assertEqual(report.branch_residual_template_certificate_count, 3)
        self.assertEqual(report.template_success_count, 3)
        self.assertEqual(report.branch_boundary_bracket_certificate_count, 3)
        self.assertEqual(report.bracket_success_count, 3)
        self.assertEqual(report.branch_consensus_certificate_count, 3)
        self.assertEqual(report.consensus_success_count, 3)
        self.assertEqual(report.branch_invariant_certificate_count, 3)
        self.assertEqual(report.invariant_success_count, 3)
        self.assertEqual(report.branch_trust_region_certificate_count, 3)
        self.assertEqual(report.trust_region_success_count, 3)
        self.assertEqual(report.counterfactual_certificate_count, 3)
        self.assertEqual(report.rolled_back_counterfactual_count, 3)
        self.assertEqual(report.branch_conflict_certificate_count, 6)
        self.assertEqual(report.query_policy_certificate_count, 6)
        self.assertEqual(report.drift_quarantine_certificate_count, 3)
        self.assertEqual(report.quarantined_context_count, 3)
        self.assertEqual(report.branch_recency_certificate_count, 3)
        self.assertEqual(report.recency_success_count, 3)
        self.assertEqual(report.branch_restart_certificate_count, 3)
        self.assertEqual(report.restart_success_count, 3)
        self.assertEqual(report.branch_symmetry_certificate_count, 3)
        self.assertEqual(report.symmetry_success_count, 3)
        self.assertEqual(report.branch_constraint_certificate_count, 3)
        self.assertEqual(report.constraint_success_count, 3)
        self.assertEqual(report.branch_confidence_certificate_count, 3)
        self.assertEqual(report.confidence_success_count, 3)
        self.assertEqual(report.branch_pareto_certificate_count, 3)
        self.assertEqual(report.pareto_success_count, 3)
        self.assertEqual(report.branch_outlier_filter_certificate_count, 3)
        self.assertEqual(report.filtered_success_count, 3)
        self.assertEqual(report.branch_provenance_guard_certificate_count, 3)
        self.assertEqual(report.guarded_success_count, 3)
        self.assertEqual(report.branch_credit_assignment_certificate_count, 3)
        self.assertEqual(report.credit_success_count, 3)
        self.assertEqual(report.branch_propensity_match_certificate_count, 3)
        self.assertEqual(report.propensity_matched_success_count, 3)
        self.assertEqual(report.branch_robustness_certificate_count, 3)
        self.assertEqual(report.robust_success_count, 3)
        self.assertEqual(report.branch_calibration_certificate_count, 3)
        self.assertEqual(report.calibrated_success_count, 3)
        self.assertEqual(report.branch_conformal_certificate_count, 3)
        self.assertEqual(report.conformal_success_count, 3)
        self.assertEqual(report.branch_active_subspace_certificate_count, 3)
        self.assertEqual(report.active_subspace_success_count, 3)
        self.assertEqual(report.branch_continuation_certificate_count, 3)
        self.assertEqual(report.continuation_success_count, 3)
        self.assertEqual(report.branch_switch_certificate_count, 3)
        self.assertEqual(report.switched_success_count, 3)
        self.assertEqual(report.branch_transposition_certificate_count, 3)
        self.assertEqual(report.transposition_success_count, 3)
        self.assertEqual(report.branch_pruning_certificate_count, 3)
        self.assertEqual(report.pruned_action_count, 6)
        self.assertEqual(report.branch_diversity_certificate_count, 3)
        self.assertEqual(report.diverse_family_count, 3)
        self.assertEqual(report.branch_budget_certificate_count, 3)
        self.assertEqual(report.static_abstain_count, 3)
        self.assertEqual(report.branch_stop_rule_certificate_count, 3)
        self.assertEqual(report.stopped_abstain_count, 6)
        self.assertEqual(report.avoided_verifier_call_count, 6)
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
            run_branch_curriculum_transfer_certified_experiment(),
            run_branch_contingency_transfer_certified_experiment(),
            run_branch_hindsight_relabel_transfer_certified_experiment(),
            run_branch_intervention_transfer_certified_experiment(),
            run_branch_diagnostic_probe_transfer_certified_experiment(),
            run_branch_residual_template_transfer_certified_experiment(),
            run_branch_boundary_bracket_transfer_certified_experiment(),
            run_branch_consensus_transfer_certified_experiment(),
            run_branch_invariant_transfer_certified_experiment(),
            run_branch_trust_region_transfer_certified_experiment(),
            run_analogical_branch_transfer_certified_experiment(),
            run_context_selection_transfer_certified_experiment(),
            run_context_refinement_transfer_certified_experiment(),
            run_context_query_policy_transfer_certified_experiment(),
            run_context_drift_quarantine_certified_experiment(),
            run_branch_recency_weight_transfer_certified_experiment(),
            run_branch_restart_transfer_certified_experiment(),
            run_branch_symmetry_transfer_certified_experiment(),
            run_branch_constraint_transfer_certified_experiment(),
            run_branch_confidence_transfer_certified_experiment(),
            run_branch_pareto_transfer_certified_experiment(),
            run_branch_outlier_filter_transfer_certified_experiment(),
            run_branch_provenance_guard_transfer_certified_experiment(),
            run_branch_credit_assignment_transfer_certified_experiment(),
            run_branch_propensity_match_transfer_certified_experiment(),
            run_branch_robustness_transfer_certified_experiment(),
            run_branch_calibration_transfer_certified_experiment(),
            run_branch_conformal_transfer_certified_experiment(),
            run_branch_active_subspace_transfer_certified_experiment(),
            run_branch_continuation_transfer_certified_experiment(),
            run_branch_switch_transfer_certified_experiment(),
            run_branch_transposition_transfer_certified_experiment(),
            run_branch_pruning_transfer_certified_experiment(),
            run_branch_diversity_transfer_certified_experiment(),
            run_branch_budget_transfer_certified_experiment(),
            run_branch_stop_rule_transfer_certified_experiment(),
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
