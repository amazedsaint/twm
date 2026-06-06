from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any

from examples.analogical_branch_transfer import (
    run_analogical_branch_transfer_certified_experiment,
    validate_analogical_branch_transfer_certificate,
)
from examples.ancestral_branch_exploration import (
    run_ancestral_branch_exploration_certified_experiment,
    validate_ancestral_branch_exploration_certificate,
)
from examples.branch_abstraction_transfer import (
    run_branch_abstraction_transfer_certified_experiment,
    validate_branch_abstraction_transfer_certificate,
)
from examples.branch_boundary_bracket_transfer import (
    run_branch_boundary_bracket_transfer_certified_experiment,
    validate_branch_boundary_bracket_transfer_certificate,
)
from examples.branch_counterfactual_transfer import (
    run_branch_counterfactual_transfer_certified_experiment,
    validate_branch_counterfactual_transfer_certificate,
)
from examples.branch_curriculum_transfer import (
    run_branch_curriculum_transfer_certified_experiment,
    validate_branch_curriculum_transfer_certificate,
)
from examples.branch_contingency_transfer import (
    run_branch_contingency_transfer_certified_experiment,
    validate_branch_contingency_transfer_certificate,
)
from examples.branch_recency_weight_transfer import (
    run_branch_recency_weight_transfer_certified_experiment,
    validate_branch_recency_transfer_certificate,
)
from examples.branch_restart_transfer import (
    run_branch_restart_transfer_certified_experiment,
    validate_branch_restart_transfer_certificate,
)
from examples.branch_symmetry_transfer import (
    run_branch_symmetry_transfer_certified_experiment,
    validate_branch_symmetry_transfer_certificate,
)
from examples.branch_constraint_transfer import (
    run_branch_constraint_transfer_certified_experiment,
    validate_branch_constraint_transfer_certificate,
)
from examples.branch_confidence_transfer import (
    run_branch_confidence_transfer_certified_experiment,
    validate_branch_confidence_transfer_certificate,
)
from examples.branch_pareto_transfer import (
    run_branch_pareto_transfer_certified_experiment,
    validate_branch_pareto_transfer_certificate,
)
from examples.branch_outlier_filter_transfer import (
    run_branch_outlier_filter_transfer_certified_experiment,
    validate_branch_outlier_filter_transfer_certificate,
)
from examples.branch_provenance_guard_transfer import (
    run_branch_provenance_guard_transfer_certified_experiment,
    validate_branch_provenance_guard_transfer_certificate,
)
from examples.branch_credit_assignment_transfer import (
    run_branch_credit_assignment_transfer_certified_experiment,
    validate_branch_credit_assignment_transfer_certificate,
)
from examples.branch_propensity_match_transfer import (
    run_branch_propensity_match_transfer_certified_experiment,
    validate_branch_propensity_match_transfer_certificate,
)
from examples.branch_robustness_transfer import (
    run_branch_robustness_transfer_certified_experiment,
    validate_branch_robustness_transfer_certificate,
)
from examples.branch_consensus_transfer import (
    run_branch_consensus_transfer_certified_experiment,
    validate_branch_consensus_transfer_certificate,
)
from examples.branch_diagnostic_probe_transfer import (
    run_branch_diagnostic_probe_transfer_certified_experiment,
    validate_branch_diagnostic_probe_transfer_certificate,
)
from examples.branch_residual_template_transfer import (
    run_branch_residual_template_transfer_certified_experiment,
    validate_branch_residual_template_transfer_certificate,
)
from examples.branch_hindsight_relabel_transfer import (
    run_branch_hindsight_relabel_transfer_certified_experiment,
    validate_branch_hindsight_relabel_transfer_certificate,
)
from examples.branch_invariant_transfer import (
    run_branch_invariant_transfer_certified_experiment,
    validate_branch_invariant_transfer_certificate,
)
from examples.branch_trust_region_transfer import (
    run_branch_trust_region_transfer_certified_experiment,
    validate_branch_trust_region_transfer_certificate,
)
from examples.branch_intervention_transfer import (
    run_branch_intervention_transfer_certified_experiment,
    validate_branch_intervention_transfer_certificate,
)
from examples.branch_prerequisite_transfer import (
    run_branch_prerequisite_transfer_certified_experiment,
    validate_branch_prerequisite_transfer_certificate,
)
from examples.common import CertifiedExampleResult, report_as_dict, validate_example_evidence_certificate
from examples.branch_composition_transfer import (
    run_branch_composition_transfer_certified_experiment,
    validate_branch_composition_transfer_certificate,
)
from examples.branch_pruning_transfer import (
    run_branch_pruning_transfer_certified_experiment,
    validate_branch_pruning_transfer_certificate,
)
from examples.branch_diversity_transfer import (
    run_branch_diversity_transfer_certified_experiment,
    validate_branch_diversity_transfer_certificate,
)
from examples.branch_budget_transfer import (
    run_branch_budget_transfer_certified_experiment,
    validate_branch_budget_transfer_certificate,
)
from examples.branch_stop_rule_transfer import (
    run_branch_stop_rule_transfer_certified_experiment,
    validate_branch_stop_rule_transfer_certificate,
)
from examples.context_query_policy_transfer import (
    run_context_query_policy_transfer_certified_experiment,
    validate_context_query_policy_transfer_certificate,
)
from examples.context_drift_quarantine import (
    run_context_drift_quarantine_certified_experiment,
    validate_context_drift_quarantine_transfer_certificate,
)
from examples.context_refinement_transfer import (
    run_context_refinement_transfer_certified_experiment,
    validate_context_refinement_transfer_certificate,
)
from examples.context_retention_transfer import (
    run_context_retention_transfer_certified_experiment,
    validate_context_retention_transfer_certificate,
)
from examples.context_selection_transfer import (
    run_context_selection_transfer_certified_experiment,
    validate_context_selection_transfer_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement, validate_claim_certificate


BRANCH_HISTORY_FRONTIER_SOURCES = (
    "https://link.springer.com/article/10.1007/BF00992699",
    "https://papers.nips.cc/paper/3306-regret-minimization-in-games-with-incomplete-information",
    "https://doi.org/10.1007/11871842_29",
    "https://dblp.org/rec/journals/aicom/AamodtP94",
    "https://arxiv.org/abs/2009.00909",
    "https://doi.org/10.1007/10722167_15",
    "https://minds.wisconsin.edu/handle/1793/60660",
    "https://direct.mit.edu/books/monograph/2574/Adaptation-in-Natural-and-Artificial-SystemsAn",
    "https://journals.sagepub.com/doi/10.3233/AIC-1994-7104",
    "https://www.sciencedirect.com/science/article/pii/S1572528616000062",
    "https://digitalcommons.unl.edu/csetechreports/158/",
    "https://users.aalto.fi/~tjunttil/2020-DP-AUT/notes-sat/cdcl.html",
    "https://pubmed.ncbi.nlm.nih.gov/20868264/",
    "https://arxiv.org/abs/1504.04909",
    "https://jmlr.org/papers/v18/16-558.html",
    "https://arxiv.org/abs/1603.06560",
    "https://doi.org/10.1016/S0004-3702(99)00052-1",
    "https://papers.nips.cc/paper/3178-the-epoch-greedy-algorithm-for-multi-armed-bandits-with-side-information",
    "https://papers.neurips.cc/paper/7090-hindsight-experience-replay",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC2836213/",
    "https://doi.org/10.1214/aoms/1177728069",
    "https://proceedings.mlr.press/v37/sui15.html",
    "https://doi.org/10.1145/130385.130417",
    "https://www.ijcai.org/Proceedings/77-1/Papers/048.pdf",
    "https://epubs.siam.org/doi/book/10.1137/1.9780898719857",
    "https://www.sciencedirect.com/science/article/pii/0004370290900463",
    "https://icml.cc/2009/papers/119.pdf",
    "https://proceedings.mlr.press/v202/lin23n.html",
    "https://arxiv.org/abs/0805.3415",
    "https://doi.org/10.1023/A:1006314320276",
    "https://arxiv.org/abs/1602.07576",
    "https://doi.org/10.1016/0004-3702(77)90007-8",
    "https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm",
    "https://doi.org/10.1287/moor.23.4.769",
    "https://doi.org/10.1109/4235.996017",
    "https://doi.org/10.1145/358669.358692",
    "https://doi.org/10.1145/357172.357176",
    "https://doi.org/10.1515/9781400881970-018",
    "https://doi.org/10.1093/biomet/70.1.41",
)
BRANCH_HISTORY_FRONTIER_CLAIM_BOUNDARY = (
    "G1 aggregate over local deterministic branch-history examples only. It shows a staged evidence "
    "path for proposal ordering, counterfactual accepted-loser reuse, option-family abstraction, "
    "prerequisite ordering, curriculum sequencing, regime-conditioned contingency reuse, hindsight goal relabeling, receipt-bound "
    "field intervention, diagnostic probing, residual-template repair, boundary bracketing, source consensus, "
    "contrastive invariant transfer, context selection, retrieval refinement, query-policy reuse, conflict resolution, "
    "drift quarantine, recency-weighted source freshness, restart-anchor backtracking, symmetry-transform transfer, pairwise-constraint transfer, confidence-bound support, Pareto-front transfer, outlier-filter transfer, provenance-guard transfer, credit-assignment transfer, propensity-match transfer, robustness transfer, branch pruning, branch diversity, budget allocation, trust-region radius transfer, "
    "stop-rule abstention, branch composition, and retained-memory influence. "
    "It is not a statistical exploration algorithm, regret guarantee, MCTS result, contextual-bandit "
    "result, Hindsight Experience Replay result, causal inference result, do-calculus result, Bayesian "
    "experimental-design result, active-learning result, case-based reasoning system, automatic similarity "
    "metric, typed symmetry-search system, equivariant neural-network result, CSP solver, arc-consistency "
    "algorithm, statistical validation, production calibration, multiobjective optimizer, Pareto-front "
    "approximation guarantee, RANSAC implementation, robust estimator, outlier-detection guarantee, "
    "Byzantine fault-tolerant protocol, consensus algorithm, security proof, Shapley-value computation, "
    "propensity-score estimator, covariate-balance proof, treatment-effect estimate, causal inference result, "
    "reinforcement-learning credit-assignment result, robust optimization, worst-case guarantee, "
    "distributional robustness, or scientific-discovery claim."
)


@dataclass(frozen=True)
class BranchHistoryFrontierRow:
    stage: str
    experiment_id: str
    report_schema_version: str
    primary_certificate_schema: str
    primary_certificate_hash: str
    evidence_certificate_hash: str
    claim_certificate_hash: str
    baseline: str
    improved_path: str
    stage_result: str
    same_budget_comparison: bool
    next_substrate_requirement: str


@dataclass(frozen=True)
class BranchHistoryFrontierReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    stage_count: int
    child_experiment_ids: tuple[str, ...]
    rows: tuple[BranchHistoryFrontierRow, ...]
    all_evidence_valid: bool
    all_claims_supported: bool
    all_primary_certificates_valid: bool
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_invalid_commit_count: int
    same_budget_stage_count: int
    branch_abstraction_certificate_count: int
    branch_prerequisite_certificate_count: int
    branch_curriculum_certificate_count: int
    guided_curriculum_success_count: int
    branch_contingency_certificate_count: int
    matched_source_context_count: int
    branch_hindsight_relabel_certificate_count: int
    relabeled_goal_count: int
    branch_intervention_certificate_count: int
    intervention_success_count: int
    branch_diagnostic_probe_certificate_count: int
    guided_probe_success_count: int
    guided_final_success_count: int
    branch_residual_template_certificate_count: int
    template_success_count: int
    branch_boundary_bracket_certificate_count: int
    bracket_success_count: int
    branch_consensus_certificate_count: int
    consensus_success_count: int
    branch_invariant_certificate_count: int
    invariant_success_count: int
    branch_trust_region_certificate_count: int
    trust_region_success_count: int
    branch_conflict_certificate_count: int
    counterfactual_certificate_count: int
    rolled_back_counterfactual_count: int
    query_policy_certificate_count: int
    drift_quarantine_certificate_count: int
    quarantined_context_count: int
    branch_recency_certificate_count: int
    recency_success_count: int
    branch_restart_certificate_count: int
    restart_success_count: int
    branch_symmetry_certificate_count: int
    symmetry_success_count: int
    branch_constraint_certificate_count: int
    constraint_success_count: int
    branch_confidence_certificate_count: int
    confidence_success_count: int
    branch_pareto_certificate_count: int
    pareto_success_count: int
    branch_outlier_filter_certificate_count: int
    filtered_success_count: int
    branch_provenance_guard_certificate_count: int
    guarded_success_count: int
    branch_credit_assignment_certificate_count: int
    credit_success_count: int
    branch_propensity_match_certificate_count: int
    propensity_matched_success_count: int
    branch_robustness_certificate_count: int
    robust_success_count: int
    branch_pruning_certificate_count: int
    pruned_action_count: int
    branch_diversity_certificate_count: int
    diverse_family_count: int
    branch_budget_certificate_count: int
    static_abstain_count: int
    branch_stop_rule_certificate_count: int
    stopped_abstain_count: int
    avoided_verifier_call_count: int
    branch_composition_certificate_count: int
    retention_certificate_count: int
    influence_certificate_count: int
    aggregate_sources: tuple[str, ...]
    learning: str


@dataclass(frozen=True)
class BranchHistoryFrontierResult:
    report: BranchHistoryFrontierReport
    claim_certificate: ClaimCertificate


def run_branch_history_frontier_experiment() -> BranchHistoryFrontierResult:
    return build_branch_history_frontier_result(
        (
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
            run_branch_pruning_transfer_certified_experiment(),
            run_branch_diversity_transfer_certified_experiment(),
            run_branch_budget_transfer_certified_experiment(),
            run_branch_stop_rule_transfer_certified_experiment(),
            run_branch_composition_transfer_certified_experiment(),
            run_context_retention_transfer_certified_experiment(),
        )
    )


def build_branch_history_frontier_result(
    children: tuple[CertifiedExampleResult, ...],
) -> BranchHistoryFrontierResult:
    rows = tuple(_frontier_row(child) for child in children)
    evidence_valid = tuple(validate_example_evidence_certificate(child.evidence_certificate, child.report) for child in children)
    primary_valid = tuple(_primary_certificate_valid(child) for child in children)
    claims_supported = tuple(
        validate_claim_certificate(child.claim_certificate) and child.claim_certificate.status == "supported"
        for child in children
    )
    report = BranchHistoryFrontierReport(
        schema_version="trwm.example.branch_history_frontier.v1",
        experiment_id="branch_history_frontier",
        evidence_grade="G1",
        stage_count=len(children),
        child_experiment_ids=tuple(child.evidence_certificate.experiment_id for child in children),
        rows=rows,
        all_evidence_valid=all(evidence_valid),
        all_claims_supported=all(claims_supported),
        all_primary_certificates_valid=all(primary_valid),
        total_receipt_count=sum(child.evidence_certificate.receipt_count for child in children),
        total_committed_count=sum(child.evidence_certificate.committed_count for child in children),
        total_rejected_count=sum(child.evidence_certificate.rejected_count for child in children),
        total_invalid_commit_count=sum(child.evidence_certificate.invalid_commit_count for child in children),
        same_budget_stage_count=sum(1 for row in rows if row.same_budget_comparison),
        branch_abstraction_certificate_count=_metric(children, "branch_abstraction_certificate_count"),
        branch_prerequisite_certificate_count=_metric(children, "branch_prerequisite_certificate_count"),
        branch_curriculum_certificate_count=_metric(children, "branch_curriculum_certificate_count"),
        guided_curriculum_success_count=_metric_for(children, "branch_curriculum_transfer", "guided_curriculum_success_count"),
        branch_contingency_certificate_count=_metric(children, "branch_contingency_certificate_count"),
        matched_source_context_count=_metric_for(children, "branch_contingency_transfer", "selected_context_count"),
        branch_hindsight_relabel_certificate_count=_metric(children, "branch_hindsight_relabel_certificate_count"),
        relabeled_goal_count=_metric_for(children, "branch_hindsight_relabel_transfer", "relabeled_goal_count"),
        branch_intervention_certificate_count=_metric(children, "branch_intervention_certificate_count"),
        intervention_success_count=_metric_for(children, "branch_intervention_transfer", "intervention_success_count"),
        branch_diagnostic_probe_certificate_count=_metric(children, "branch_diagnostic_probe_certificate_count"),
        guided_probe_success_count=_metric_for(children, "branch_diagnostic_probe_transfer", "guided_probe_success_count"),
        guided_final_success_count=_metric_for(children, "branch_diagnostic_probe_transfer", "guided_final_success_count"),
        branch_residual_template_certificate_count=_metric(children, "branch_residual_template_certificate_count"),
        template_success_count=_metric_for(children, "branch_residual_template_transfer", "template_success_count"),
        branch_boundary_bracket_certificate_count=_metric(children, "branch_boundary_bracket_certificate_count"),
        bracket_success_count=_metric_for(children, "branch_boundary_bracket_transfer", "bracket_success_count"),
        branch_consensus_certificate_count=_metric(children, "branch_consensus_certificate_count"),
        consensus_success_count=_metric_for(children, "branch_consensus_transfer", "consensus_success_count"),
        branch_invariant_certificate_count=_metric(children, "branch_invariant_certificate_count"),
        invariant_success_count=_metric_for(children, "branch_invariant_transfer", "invariant_success_count"),
        branch_trust_region_certificate_count=_metric(children, "branch_trust_region_certificate_count"),
        trust_region_success_count=_metric_for(children, "branch_trust_region_transfer", "trust_region_success_count"),
        branch_conflict_certificate_count=_metric(children, "branch_conflict_certificate_count"),
        counterfactual_certificate_count=_metric(children, "counterfactual_certificate_count"),
        rolled_back_counterfactual_count=_metric(children, "rolled_back_counterfactual_count"),
        query_policy_certificate_count=_metric(children, "query_policy_certificate_count"),
        drift_quarantine_certificate_count=_metric(children, "drift_quarantine_certificate_count"),
        quarantined_context_count=_metric(children, "quarantined_context_count"),
        branch_recency_certificate_count=_metric(children, "branch_recency_certificate_count"),
        recency_success_count=_metric_for(children, "branch_recency_weight_transfer", "recency_success_count"),
        branch_restart_certificate_count=_metric(children, "branch_restart_certificate_count"),
        restart_success_count=_metric_for(children, "branch_restart_transfer", "restart_success_count"),
        branch_symmetry_certificate_count=_metric(children, "branch_symmetry_certificate_count"),
        symmetry_success_count=_metric_for(children, "branch_symmetry_transfer", "symmetry_success_count"),
        branch_constraint_certificate_count=_metric(children, "branch_constraint_certificate_count"),
        constraint_success_count=_metric_for(children, "branch_constraint_transfer", "constraint_success_count"),
        branch_confidence_certificate_count=_metric(children, "branch_confidence_certificate_count"),
        confidence_success_count=_metric_for(children, "branch_confidence_transfer", "confidence_success_count"),
        branch_pareto_certificate_count=_metric(children, "branch_pareto_certificate_count"),
        pareto_success_count=_metric_for(children, "branch_pareto_transfer", "pareto_success_count"),
        branch_outlier_filter_certificate_count=_metric(children, "branch_outlier_filter_certificate_count"),
        filtered_success_count=_metric_for(children, "branch_outlier_filter_transfer", "filtered_success_count"),
        branch_provenance_guard_certificate_count=_metric(children, "branch_provenance_guard_certificate_count"),
        guarded_success_count=_metric_for(children, "branch_provenance_guard_transfer", "guarded_success_count"),
        branch_credit_assignment_certificate_count=_metric(children, "branch_credit_assignment_certificate_count"),
        credit_success_count=_metric_for(children, "branch_credit_assignment_transfer", "credit_success_count"),
        branch_propensity_match_certificate_count=_metric(children, "branch_propensity_match_certificate_count"),
        propensity_matched_success_count=_metric_for(children, "branch_propensity_match_transfer", "matched_success_count"),
        branch_robustness_certificate_count=_metric(children, "branch_robustness_certificate_count"),
        robust_success_count=_metric_for(children, "branch_robustness_transfer", "robust_success_count"),
        branch_pruning_certificate_count=_metric(children, "branch_pruning_certificate_count"),
        pruned_action_count=_metric(children, "pruned_action_count"),
        branch_diversity_certificate_count=_metric(children, "branch_diversity_certificate_count"),
        diverse_family_count=_metric(children, "diverse_family_count"),
        branch_budget_certificate_count=_metric(children, "branch_budget_certificate_count"),
        static_abstain_count=_metric(children, "static_abstain_count"),
        branch_stop_rule_certificate_count=_metric(children, "branch_stop_rule_certificate_count"),
        stopped_abstain_count=_metric(children, "stopped_abstain_count"),
        avoided_verifier_call_count=_metric(children, "avoided_verifier_call_count"),
        branch_composition_certificate_count=_metric(children, "branch_composition_certificate_count"),
        retention_certificate_count=_metric(children, "retention_certificate_count"),
        influence_certificate_count=_metric(children, "influence_certificate_count"),
        aggregate_sources=tuple(sorted({source for child in children for source in child.evidence_certificate.sources})),
        learning=(
            "The branch-history evidence path is now staged: receipt-bound ordering first, explicit "
            "accepted-loser counterfactual reuse second, option-family abstraction third, explicit "
            "prerequisite ordering fourth, curriculum sequencing fifth, regime-conditioned contingency reuse sixth, "
            "hindsight goal relabeling seventh, receipt-bound field intervention eighth, diagnostic probe transfer ninth, "
            "residual-template repair tenth, boundary bracketing eleventh, source consensus twelfth, contrastive "
            "invariant transfer thirteenth, trust-region radius transfer fourteenth, explicit ancestor reuse fifteenth, "
            "certified context selection sixteenth, counterexample-driven refinement seventeenth, reusable query-policy "
            "and conflict-resolution certificates eighteenth, drift quarantine nineteenth, recency-weighted source freshness "
            "twentieth, restart-anchor backtracking twenty-first, typed symmetry transfer twenty-second, "
            "pairwise-constraint transfer twenty-third, confidence-bound support twenty-fourth, "
            "Pareto-front transfer twenty-fifth, outlier-filter transfer twenty-sixth, "
            "provenance-guard transfer twenty-seventh, credit-assignment transfer twenty-eighth, "
            "propensity-match transfer twenty-ninth, robustness transfer thirtieth, "
            "receipt-bound branch pruning thirty-first, diversity-certified family coverage thirty-second, "
            "budget-allocation transfer thirty-third, no-good stop-rule abstention thirty-fourth, "
            "branch composition thirty-fifth, and retained-memory influence with matched ablation thirty-sixth."
        ),
    )
    claim = certify_claim(
        claim_id="branch_history_frontier_g1",
        claim_text=(
            "The certified branch-history examples identify a local G1 substrate path where branches of "
            "the past improve exploration only through audited proposal ordering, selection, refinement, "
            "query-policy, conflict-resolution, drift-quarantine, recency weighting, restart-anchor backtracking, symmetry-transform transfer, pairwise-constraint transfer, confidence-bound support, Pareto-front transfer, outlier filtering, provenance guarding, credit assignment, propensity matching, robustness transfer, pruning, diversity, budget-allocation, "
            "counterfactual accepted-loser reuse, option-family abstraction, prerequisite ordering, "
            "regime-conditioned contingency reuse, hindsight goal relabeling, field intervention, diagnostic "
            "probing, residual-template repair, boundary bracketing, source consensus, contrastive invariant transfer, "
            "no-good stop-rule abstention, composition, retention, and influence certificates."
        ),
        evidence_grade="G1",
        scope="branch_history_frontier",
        requirements=(
            requirement("exactly_thirty_six_branch_history_stages", report.stage_count == 36),
            requirement(
                "expected_child_experiments",
                set(report.child_experiment_ids)
                == {
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
                    "branch_pruning_transfer",
                    "branch_diversity_transfer",
                    "branch_budget_transfer",
                    "branch_stop_rule_transfer",
                    "branch_composition_transfer",
                    "context_retention_transfer",
                },
            ),
            requirement("all_evidence_certificates_valid", report.all_evidence_valid),
            requirement("all_primary_certificates_valid", report.all_primary_certificates_valid),
            requirement("all_child_claims_supported", report.all_claims_supported),
            requirement("no_invalid_commits", report.total_invalid_commit_count == 0),
            requirement("same_budget_checks_all_stages", report.same_budget_stage_count == report.stage_count),
            requirement(
                "counterfactual_certificates_present",
                report.counterfactual_certificate_count == 3 and report.rolled_back_counterfactual_count == 3,
            ),
            requirement("branch_abstraction_certificates_present", report.branch_abstraction_certificate_count == 3),
            requirement("branch_prerequisite_certificates_present", report.branch_prerequisite_certificate_count == 3),
            requirement(
                "branch_curriculum_certificates_present",
                report.branch_curriculum_certificate_count == 3 and report.guided_curriculum_success_count == 6,
            ),
            requirement(
                "branch_contingency_certificates_present",
                report.branch_contingency_certificate_count == 3 and report.matched_source_context_count == 3,
            ),
            requirement(
                "branch_hindsight_relabel_certificates_present",
                report.branch_hindsight_relabel_certificate_count == 3 and report.relabeled_goal_count == 3,
            ),
            requirement(
                "branch_intervention_certificates_present",
                report.branch_intervention_certificate_count == 3 and report.intervention_success_count == 3,
            ),
            requirement(
                "branch_diagnostic_probe_certificates_present",
                report.branch_diagnostic_probe_certificate_count == 3
                and report.guided_probe_success_count == 3
                and report.guided_final_success_count == 3,
            ),
            requirement(
                "branch_residual_template_certificates_present",
                report.branch_residual_template_certificate_count == 3 and report.template_success_count == 3,
            ),
            requirement(
                "branch_boundary_bracket_certificates_present",
                report.branch_boundary_bracket_certificate_count == 3 and report.bracket_success_count == 3,
            ),
            requirement(
                "branch_consensus_certificates_present",
                report.branch_consensus_certificate_count == 3 and report.consensus_success_count == 3,
            ),
            requirement(
                "branch_invariant_certificates_present",
                report.branch_invariant_certificate_count == 3 and report.invariant_success_count == 3,
            ),
            requirement(
                "branch_trust_region_certificates_present",
                report.branch_trust_region_certificate_count == 3 and report.trust_region_success_count == 3,
            ),
            requirement("query_policy_conflict_certificates_present", report.branch_conflict_certificate_count == 6),
            requirement(
                "drift_quarantine_certificates_present",
                report.drift_quarantine_certificate_count == 3 and report.quarantined_context_count == 3,
            ),
            requirement(
                "branch_recency_certificates_present",
                report.branch_recency_certificate_count == 3 and report.recency_success_count == 3,
            ),
            requirement(
                "branch_restart_certificates_present",
                report.branch_restart_certificate_count == 3 and report.restart_success_count == 3,
            ),
            requirement(
                "branch_symmetry_certificates_present",
                report.branch_symmetry_certificate_count == 3 and report.symmetry_success_count == 3,
            ),
            requirement(
                "branch_constraint_certificates_present",
                report.branch_constraint_certificate_count == 3 and report.constraint_success_count == 3,
            ),
            requirement(
                "branch_confidence_certificates_present",
                report.branch_confidence_certificate_count == 3 and report.confidence_success_count == 3,
            ),
            requirement(
                "branch_pareto_certificates_present",
                report.branch_pareto_certificate_count == 3 and report.pareto_success_count == 3,
            ),
            requirement(
                "branch_outlier_filter_certificates_present",
                report.branch_outlier_filter_certificate_count == 3 and report.filtered_success_count == 3,
            ),
            requirement(
                "branch_provenance_guard_certificates_present",
                report.branch_provenance_guard_certificate_count == 3 and report.guarded_success_count == 3,
            ),
            requirement(
                "branch_credit_assignment_certificates_present",
                report.branch_credit_assignment_certificate_count == 3 and report.credit_success_count == 3,
            ),
            requirement(
                "branch_propensity_match_certificates_present",
                report.branch_propensity_match_certificate_count == 3 and report.propensity_matched_success_count == 3,
            ),
            requirement(
                "branch_robustness_certificates_present",
                report.branch_robustness_certificate_count == 3 and report.robust_success_count == 3,
            ),
            requirement("branch_pruning_certificates_present", report.branch_pruning_certificate_count == 3 and report.pruned_action_count == 6),
            requirement("branch_diversity_certificates_present", report.branch_diversity_certificate_count == 3 and report.diverse_family_count == 3),
            requirement("branch_budget_certificates_present", report.branch_budget_certificate_count == 3 and report.static_abstain_count == 3),
            requirement(
                "branch_stop_rule_certificates_present",
                report.branch_stop_rule_certificate_count == 3
                and report.stopped_abstain_count == 6
                and report.avoided_verifier_call_count == 6,
            ),
            requirement("branch_composition_certificates_present", report.branch_composition_certificate_count == 3),
            requirement("retention_and_influence_certificates_present", report.retention_certificate_count == 3 and report.influence_certificate_count == 3),
            requirement("source_coverage", set(report.aggregate_sources) == set(BRANCH_HISTORY_FRONTIER_SOURCES)),
        ),
        metrics={
            "stage_count": report.stage_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "branch_abstraction_certificate_count": report.branch_abstraction_certificate_count,
            "branch_prerequisite_certificate_count": report.branch_prerequisite_certificate_count,
            "branch_curriculum_certificate_count": report.branch_curriculum_certificate_count,
            "guided_curriculum_success_count": report.guided_curriculum_success_count,
            "branch_contingency_certificate_count": report.branch_contingency_certificate_count,
            "matched_source_context_count": report.matched_source_context_count,
            "branch_hindsight_relabel_certificate_count": report.branch_hindsight_relabel_certificate_count,
            "relabeled_goal_count": report.relabeled_goal_count,
            "branch_intervention_certificate_count": report.branch_intervention_certificate_count,
            "intervention_success_count": report.intervention_success_count,
            "branch_diagnostic_probe_certificate_count": report.branch_diagnostic_probe_certificate_count,
            "guided_probe_success_count": report.guided_probe_success_count,
            "guided_final_success_count": report.guided_final_success_count,
            "branch_residual_template_certificate_count": report.branch_residual_template_certificate_count,
            "template_success_count": report.template_success_count,
            "branch_boundary_bracket_certificate_count": report.branch_boundary_bracket_certificate_count,
            "bracket_success_count": report.bracket_success_count,
            "branch_consensus_certificate_count": report.branch_consensus_certificate_count,
            "consensus_success_count": report.consensus_success_count,
            "branch_invariant_certificate_count": report.branch_invariant_certificate_count,
            "invariant_success_count": report.invariant_success_count,
            "branch_trust_region_certificate_count": report.branch_trust_region_certificate_count,
            "trust_region_success_count": report.trust_region_success_count,
            "counterfactual_certificate_count": report.counterfactual_certificate_count,
            "rolled_back_counterfactual_count": report.rolled_back_counterfactual_count,
            "branch_conflict_certificate_count": report.branch_conflict_certificate_count,
            "query_policy_certificate_count": report.query_policy_certificate_count,
            "drift_quarantine_certificate_count": report.drift_quarantine_certificate_count,
            "quarantined_context_count": report.quarantined_context_count,
            "branch_recency_certificate_count": report.branch_recency_certificate_count,
            "recency_success_count": report.recency_success_count,
            "branch_restart_certificate_count": report.branch_restart_certificate_count,
            "restart_success_count": report.restart_success_count,
            "branch_symmetry_certificate_count": report.branch_symmetry_certificate_count,
            "symmetry_success_count": report.symmetry_success_count,
            "branch_constraint_certificate_count": report.branch_constraint_certificate_count,
            "constraint_success_count": report.constraint_success_count,
            "branch_confidence_certificate_count": report.branch_confidence_certificate_count,
            "confidence_success_count": report.confidence_success_count,
            "branch_pareto_certificate_count": report.branch_pareto_certificate_count,
            "pareto_success_count": report.pareto_success_count,
            "branch_outlier_filter_certificate_count": report.branch_outlier_filter_certificate_count,
            "filtered_success_count": report.filtered_success_count,
            "branch_provenance_guard_certificate_count": report.branch_provenance_guard_certificate_count,
            "guarded_success_count": report.guarded_success_count,
            "branch_credit_assignment_certificate_count": report.branch_credit_assignment_certificate_count,
            "credit_success_count": report.credit_success_count,
            "branch_propensity_match_certificate_count": report.branch_propensity_match_certificate_count,
            "propensity_matched_success_count": report.propensity_matched_success_count,
            "branch_robustness_certificate_count": report.branch_robustness_certificate_count,
            "robust_success_count": report.robust_success_count,
            "branch_pruning_certificate_count": report.branch_pruning_certificate_count,
            "pruned_action_count": report.pruned_action_count,
            "branch_diversity_certificate_count": report.branch_diversity_certificate_count,
            "diverse_family_count": report.diverse_family_count,
            "branch_budget_certificate_count": report.branch_budget_certificate_count,
            "static_abstain_count": report.static_abstain_count,
            "branch_stop_rule_certificate_count": report.branch_stop_rule_certificate_count,
            "stopped_abstain_count": report.stopped_abstain_count,
            "avoided_verifier_call_count": report.avoided_verifier_call_count,
            "branch_composition_certificate_count": report.branch_composition_certificate_count,
            "retention_certificate_count": report.retention_certificate_count,
            "influence_certificate_count": report.influence_certificate_count,
        },
        boundary=BRANCH_HISTORY_FRONTIER_CLAIM_BOUNDARY,
        sources=BRANCH_HISTORY_FRONTIER_SOURCES,
    )
    return BranchHistoryFrontierResult(report=report, claim_certificate=claim)


def tamper_first_child_primary_certificate(children: tuple[CertifiedExampleResult, ...]) -> tuple[CertifiedExampleResult, ...]:
    if not children:
        raise ValueError("children must be non-empty")
    first = children[0]
    if not hasattr(first, "exploration_certificate"):
        raise ValueError("first child must expose exploration_certificate")
    tampered = replace(first.exploration_certificate, report_hash="0" * 64, certificate_hash="")
    return (replace(first, exploration_certificate=tampered), *children[1:])


def result_as_dict(result: BranchHistoryFrontierResult) -> dict[str, Any]:
    return report_as_dict(result)


def _frontier_row(child: CertifiedExampleResult) -> BranchHistoryFrontierRow:
    experiment_id = child.evidence_certificate.experiment_id
    certificate = _primary_certificate(child)
    stage, baseline, improved_path, stage_result, same_budget, requirement_text = _stage_fields(child)
    return BranchHistoryFrontierRow(
        stage=stage,
        experiment_id=experiment_id,
        report_schema_version=child.report.schema_version,
        primary_certificate_schema=certificate.schema_version,
        primary_certificate_hash=certificate.certificate_hash,
        evidence_certificate_hash=child.evidence_certificate.certificate_hash,
        claim_certificate_hash=child.claim_certificate.certificate_hash,
        baseline=baseline,
        improved_path=improved_path,
        stage_result=stage_result,
        same_budget_comparison=same_budget,
        next_substrate_requirement=requirement_text,
    )


def _primary_certificate(child: CertifiedExampleResult) -> Any:
    experiment_id = child.evidence_certificate.experiment_id
    if experiment_id == "ancestral_branch_exploration":
        return child.exploration_certificate
    if experiment_id == "branch_counterfactual_transfer":
        return child.branch_counterfactual_transfer_certificate
    if experiment_id == "branch_abstraction_transfer":
        return child.branch_abstraction_transfer_certificate
    if experiment_id == "branch_prerequisite_transfer":
        return child.branch_prerequisite_transfer_certificate
    if experiment_id == "branch_curriculum_transfer":
        return child.branch_curriculum_transfer_certificate
    if experiment_id == "branch_contingency_transfer":
        return child.branch_contingency_transfer_certificate
    if experiment_id == "branch_hindsight_relabel_transfer":
        return child.branch_hindsight_relabel_transfer_certificate
    if experiment_id == "branch_intervention_transfer":
        return child.branch_intervention_transfer_certificate
    if experiment_id == "branch_diagnostic_probe_transfer":
        return child.branch_diagnostic_probe_transfer_certificate
    if experiment_id == "branch_residual_template_transfer":
        return child.branch_residual_template_transfer_certificate
    if experiment_id == "branch_boundary_bracket_transfer":
        return child.branch_boundary_bracket_transfer_certificate
    if experiment_id == "branch_consensus_transfer":
        return child.branch_consensus_transfer_certificate
    if experiment_id == "branch_invariant_transfer":
        return child.branch_invariant_transfer_certificate
    if experiment_id == "branch_trust_region_transfer":
        return child.branch_trust_region_transfer_certificate
    if experiment_id == "analogical_branch_transfer":
        return child.analogical_certificate
    if experiment_id == "context_selection_transfer":
        return child.context_selection_transfer_certificate
    if experiment_id == "context_refinement_transfer":
        return child.context_refinement_transfer_certificate
    if experiment_id == "context_query_policy_transfer":
        return child.context_query_policy_transfer_certificate
    if experiment_id == "context_drift_quarantine":
        return child.context_drift_quarantine_transfer_certificate
    if experiment_id == "branch_recency_weight_transfer":
        return child.branch_recency_transfer_certificate
    if experiment_id == "branch_restart_transfer":
        return child.branch_restart_transfer_certificate
    if experiment_id == "branch_symmetry_transfer":
        return child.branch_symmetry_transfer_certificate
    if experiment_id == "branch_constraint_transfer":
        return child.branch_constraint_transfer_certificate
    if experiment_id == "branch_confidence_transfer":
        return child.branch_confidence_transfer_certificate
    if experiment_id == "branch_pareto_transfer":
        return child.branch_pareto_transfer_certificate
    if experiment_id == "branch_outlier_filter_transfer":
        return child.branch_outlier_filter_transfer_certificate
    if experiment_id == "branch_provenance_guard_transfer":
        return child.branch_provenance_guard_transfer_certificate
    if experiment_id == "branch_credit_assignment_transfer":
        return child.branch_credit_assignment_transfer_certificate
    if experiment_id == "branch_propensity_match_transfer":
        return child.branch_propensity_match_transfer_certificate
    if experiment_id == "branch_robustness_transfer":
        return child.branch_robustness_transfer_certificate
    if experiment_id == "branch_pruning_transfer":
        return child.branch_pruning_transfer_certificate
    if experiment_id == "branch_diversity_transfer":
        return child.branch_diversity_transfer_certificate
    if experiment_id == "branch_budget_transfer":
        return child.branch_budget_transfer_certificate
    if experiment_id == "branch_stop_rule_transfer":
        return child.branch_stop_rule_transfer_certificate
    if experiment_id == "branch_composition_transfer":
        return child.branch_composition_transfer_certificate
    if experiment_id == "context_retention_transfer":
        return child.context_retention_transfer_certificate
    raise ValueError(f"unknown branch-history experiment: {experiment_id}")


def _primary_certificate_valid(child: CertifiedExampleResult) -> bool:
    experiment_id = child.evidence_certificate.experiment_id
    if experiment_id == "ancestral_branch_exploration":
        return validate_ancestral_branch_exploration_certificate(child.exploration_certificate, child.report)
    if experiment_id == "branch_counterfactual_transfer":
        return validate_branch_counterfactual_transfer_certificate(child.branch_counterfactual_transfer_certificate, child.report)
    if experiment_id == "branch_abstraction_transfer":
        return validate_branch_abstraction_transfer_certificate(child.branch_abstraction_transfer_certificate, child.report)
    if experiment_id == "branch_prerequisite_transfer":
        return validate_branch_prerequisite_transfer_certificate(child.branch_prerequisite_transfer_certificate, child.report)
    if experiment_id == "branch_curriculum_transfer":
        return validate_branch_curriculum_transfer_certificate(child.branch_curriculum_transfer_certificate, child.report)
    if experiment_id == "branch_contingency_transfer":
        return validate_branch_contingency_transfer_certificate(child.branch_contingency_transfer_certificate, child.report)
    if experiment_id == "branch_hindsight_relabel_transfer":
        return validate_branch_hindsight_relabel_transfer_certificate(child.branch_hindsight_relabel_transfer_certificate, child.report)
    if experiment_id == "branch_intervention_transfer":
        return validate_branch_intervention_transfer_certificate(child.branch_intervention_transfer_certificate, child.report)
    if experiment_id == "branch_diagnostic_probe_transfer":
        return validate_branch_diagnostic_probe_transfer_certificate(child.branch_diagnostic_probe_transfer_certificate, child.report)
    if experiment_id == "branch_residual_template_transfer":
        return validate_branch_residual_template_transfer_certificate(child.branch_residual_template_transfer_certificate, child.report)
    if experiment_id == "branch_boundary_bracket_transfer":
        return validate_branch_boundary_bracket_transfer_certificate(child.branch_boundary_bracket_transfer_certificate, child.report)
    if experiment_id == "branch_consensus_transfer":
        return validate_branch_consensus_transfer_certificate(child.branch_consensus_transfer_certificate, child.report)
    if experiment_id == "branch_invariant_transfer":
        return validate_branch_invariant_transfer_certificate(child.branch_invariant_transfer_certificate, child.report)
    if experiment_id == "branch_trust_region_transfer":
        return validate_branch_trust_region_transfer_certificate(child.branch_trust_region_transfer_certificate, child.report)
    if experiment_id == "analogical_branch_transfer":
        return validate_analogical_branch_transfer_certificate(child.analogical_certificate, child.report)
    if experiment_id == "context_selection_transfer":
        return validate_context_selection_transfer_certificate(child.context_selection_transfer_certificate, child.report)
    if experiment_id == "context_refinement_transfer":
        return validate_context_refinement_transfer_certificate(child.context_refinement_transfer_certificate, child.report)
    if experiment_id == "context_query_policy_transfer":
        return validate_context_query_policy_transfer_certificate(child.context_query_policy_transfer_certificate, child.report)
    if experiment_id == "context_drift_quarantine":
        return validate_context_drift_quarantine_transfer_certificate(child.context_drift_quarantine_transfer_certificate, child.report)
    if experiment_id == "branch_recency_weight_transfer":
        return validate_branch_recency_transfer_certificate(child.branch_recency_transfer_certificate, child.report)
    if experiment_id == "branch_restart_transfer":
        return validate_branch_restart_transfer_certificate(child.branch_restart_transfer_certificate, child.report)
    if experiment_id == "branch_symmetry_transfer":
        return validate_branch_symmetry_transfer_certificate(child.branch_symmetry_transfer_certificate, child.report)
    if experiment_id == "branch_constraint_transfer":
        return validate_branch_constraint_transfer_certificate(child.branch_constraint_transfer_certificate, child.report)
    if experiment_id == "branch_confidence_transfer":
        return validate_branch_confidence_transfer_certificate(child.branch_confidence_transfer_certificate, child.report)
    if experiment_id == "branch_pareto_transfer":
        return validate_branch_pareto_transfer_certificate(child.branch_pareto_transfer_certificate, child.report)
    if experiment_id == "branch_outlier_filter_transfer":
        return validate_branch_outlier_filter_transfer_certificate(
            child.branch_outlier_filter_transfer_certificate,
            child.report,
        )
    if experiment_id == "branch_provenance_guard_transfer":
        return validate_branch_provenance_guard_transfer_certificate(
            child.branch_provenance_guard_transfer_certificate,
            child.report,
        )
    if experiment_id == "branch_credit_assignment_transfer":
        return validate_branch_credit_assignment_transfer_certificate(
            child.branch_credit_assignment_transfer_certificate,
            child.report,
        )
    if experiment_id == "branch_propensity_match_transfer":
        return validate_branch_propensity_match_transfer_certificate(
            child.branch_propensity_match_transfer_certificate,
            child.report,
        )
    if experiment_id == "branch_robustness_transfer":
        return validate_branch_robustness_transfer_certificate(
            child.branch_robustness_transfer_certificate,
            child.report,
        )
    if experiment_id == "branch_pruning_transfer":
        return validate_branch_pruning_transfer_certificate(child.branch_pruning_transfer_certificate, child.report)
    if experiment_id == "branch_diversity_transfer":
        return validate_branch_diversity_transfer_certificate(child.branch_diversity_transfer_certificate, child.report)
    if experiment_id == "branch_budget_transfer":
        return validate_branch_budget_transfer_certificate(child.branch_budget_transfer_certificate, child.report)
    if experiment_id == "branch_stop_rule_transfer":
        return validate_branch_stop_rule_transfer_certificate(child.branch_stop_rule_transfer_certificate, child.report)
    if experiment_id == "branch_composition_transfer":
        return validate_branch_composition_transfer_certificate(child.branch_composition_transfer_certificate, child.report)
    if experiment_id == "context_retention_transfer":
        return validate_context_retention_transfer_certificate(child.context_retention_transfer_certificate, child.report)
    return False


def _stage_fields(child: CertifiedExampleResult) -> tuple[str, str, str, str, bool, str]:
    experiment_id = child.evidence_certificate.experiment_id
    report = child.report
    if experiment_id == "ancestral_branch_exploration":
        return (
            "receipt_bound_ordering",
            f"static budget commits {report.static_budget_success_count}/{report.domain_count}",
            f"past-branch ordering commits {report.learned_budget_success_count}/{report.domain_count}",
            "committed winners outrank stale first proposals",
            True,
            "branch memory snapshot plus branch-selection certificate replay",
        )
    if experiment_id == "branch_counterfactual_transfer":
        return (
            "accepted_loser_counterfactual_reuse",
            f"stale winner commits {report.stale_winner_success_count}/{report.domain_count}",
            f"counterfactual loser commits {report.counterfactual_success_count}/{report.domain_count}",
            f"rolled-back counterfactual receipts {report.rolled_back_counterfactual_count}",
            True,
            "accepted-loser counterfactual certificates before proposal reuse",
        )
    if experiment_id == "branch_abstraction_transfer":
        return (
            "option_family_branch_abstraction",
            f"exact replay commits {report.exact_replay_success_count}/{report.domain_count}",
            f"same-family target action commits {report.abstraction_success_count}/{report.domain_count}",
            f"abstraction certificates {report.branch_abstraction_certificate_count}",
            True,
            "option-family abstraction certificates before adapting past branch actions",
        )
    if experiment_id == "branch_prerequisite_transfer":
        return (
            "receipt_bound_prerequisite_ordering",
            f"static target commits {report.static_success_count}/{report.domain_count}",
            f"guided prerequisite/final commits {report.guided_final_success_count}/{report.domain_count}",
            f"prerequisite certificates {report.branch_prerequisite_certificate_count}",
            True,
            "stateful prerequisite-order certificates before final-branch verification",
        )
    if experiment_id == "branch_curriculum_transfer":
        return (
            "receipt_bound_curriculum_sequence",
            f"static direct curriculum commits {report.static_success_count}/{report.domain_count}",
            f"guided curriculum finals commit {report.guided_final_success_count}/{report.domain_count}",
            f"curriculum certificates {report.branch_curriculum_certificate_count}",
            True,
            "easy-to-hard curriculum certificates before target final verification",
        )
    if experiment_id == "branch_contingency_transfer":
        return (
            "regime_conditioned_branch_reuse",
            f"stale regime reuse commits {report.static_success_count}/{report.domain_count}",
            f"matched regime reuse commits {report.contingent_success_count}/{report.domain_count}",
            f"contingency certificates {report.branch_contingency_certificate_count}",
            True,
            "receipt-bound context-feature switchpoints before reusing past branches",
        )
    if experiment_id == "branch_hindsight_relabel_transfer":
        return (
            "hindsight_goal_relabeling",
            f"static relabeled target commits {report.static_success_count}/{report.domain_count}",
            f"hindsight-relabeled target commits {report.relabeled_success_count}/{report.domain_count}",
            f"hindsight relabel certificates {report.branch_hindsight_relabel_certificate_count}",
            True,
            "goal-labeled rejected receipts plus fresh target verification before relabeled reuse",
        )
    if experiment_id == "branch_intervention_transfer":
        return (
            "receipt_bound_field_intervention",
            f"static target commits {report.static_success_count}/{report.domain_count}",
            f"field-intervention target commits {report.intervention_success_count}/{report.domain_count}",
            f"intervention certificates {report.branch_intervention_certificate_count}",
            True,
            "reject/commit field-intervention certificates before adapting target candidates",
        )
    if experiment_id == "branch_diagnostic_probe_transfer":
        return (
            "receipt_bound_diagnostic_probe",
            f"static unprobed finals commit {report.static_success_count}/{report.domain_count}",
            f"probe-guided finals commit {report.guided_final_success_count}/{report.domain_count}",
            f"diagnostic probe certificates {report.branch_diagnostic_probe_certificate_count}",
            True,
            "diagnostic-probe certificates before spending target final-action verifier budget",
        )
    if experiment_id == "branch_residual_template_transfer":
        return (
            "receipt_bound_residual_template",
            f"static target commits {report.static_success_count}/{report.domain_count}",
            f"template-guided target commits {report.template_success_count}/{report.domain_count}",
            f"residual template certificates {report.branch_residual_template_certificate_count}",
            True,
            "residual-template certificates before applying repair templates to target proposals",
        )
    if experiment_id == "branch_boundary_bracket_transfer":
        return (
            "receipt_bound_boundary_bracket",
            f"static target commits {report.static_success_count}/{report.domain_count}",
            f"bracket-guided target commits {report.bracket_success_count}/{report.domain_count}",
            f"boundary bracket certificates {report.branch_boundary_bracket_certificate_count}",
            True,
            "boundary-bracket certificates before prioritizing target threshold candidates",
        )
    if experiment_id == "branch_consensus_transfer":
        return (
            "receipt_bound_source_consensus",
            f"static singleton-family target commits {report.static_success_count}/{report.domain_count}",
            f"majority-family target commits {report.consensus_success_count}/{report.domain_count}",
            f"source consensus certificates {report.branch_consensus_certificate_count}",
            True,
            "multi-source consensus certificates before prioritizing target proposal families",
        )
    if experiment_id == "branch_invariant_transfer":
        return (
            "contrastive_branch_invariant",
            f"static target commits {report.static_success_count}/{report.domain_count}",
            f"invariant-guided target commits {report.invariant_success_count}/{report.domain_count}",
            f"invariant certificates {report.branch_invariant_certificate_count}",
            True,
            "positive/negative branch invariant certificates before prioritizing target proposals",
        )
    if experiment_id == "branch_trust_region_transfer":
        return (
            "receipt_bound_trust_region_radius",
            f"static overshoot commits {report.static_success_count}/{report.domain_count}",
            f"trust-region target commits {report.trust_region_success_count}/{report.domain_count}",
            f"trust-region certificates {report.branch_trust_region_certificate_count}",
            True,
            "reject/commit radius-cap certificates before sizing target proposal steps",
        )
    if experiment_id == "analogical_branch_transfer":
        return (
            "explicit_ancestor_reuse",
            f"static budget commits {report.static_budget_success_count}/{report.domain_count}",
            f"explicit ancestor reuse commits {report.ancestor_budget_success_count}/{report.domain_count}",
            f"misleading transfer blocked {report.misleading_transfer_blocked_count}/{report.domain_count}",
            True,
            "explicit ancestor contexts plus fail-closed misleading-source handling",
        )
    if experiment_id == "context_selection_transfer":
        return (
            "certified_context_selection",
            f"static budget commits {report.static_budget_success_count}/{report.domain_count}",
            f"selected contexts commit {report.selected_budget_success_count}/{report.domain_count}",
            f"rejected-context bypass blocked {report.bypass_rejected_context_blocked_count}/{report.domain_count}",
            True,
            "descriptor-level context selection certificates before reuse",
        )
    if experiment_id == "context_refinement_transfer":
        return (
            "counterexample_refinement",
            f"coarse query commits {report.coarse_budget_success_count}/{report.domain_count}",
            f"refined query commits {report.refined_budget_success_count}/{report.domain_count}",
            f"newly rejected contexts {report.newly_rejected_context_count}",
            True,
            "counterexample-bound retrieval refinement certificates",
        )
    if experiment_id == "context_query_policy_transfer":
        return (
            "heldout_query_policy_conflict",
            f"stale sibling query commits {report.sibling_stale_budget_success_count}/{report.held_out_sibling_count}",
            f"refined query policy commits {report.sibling_policy_budget_success_count}/{report.held_out_sibling_count}",
            f"conflict certificates {report.branch_conflict_certificate_count}",
            True,
            "portable query-policy and branch-conflict certificates",
        )
    if experiment_id == "context_drift_quarantine":
        return (
            "context_drift_quarantine",
            f"stale drift query commits {report.stale_budget_success_count}/{report.domain_count}",
            f"epoch-aware query commits {report.drift_budget_success_count}/{report.domain_count}",
            f"quarantined contexts {report.quarantined_context_count}",
            True,
            "validity-scoped branch memory and drift quarantine certificates",
        )
    if experiment_id == "branch_recency_weight_transfer":
        return (
            "recency_weighted_source_freshness",
            f"cumulative stale target commits {report.static_success_count}/{report.domain_count}",
            f"recent-window target commits {report.recency_success_count}/{report.domain_count}",
            f"recency certificates {report.branch_recency_certificate_count}",
            True,
            "receipt-freshness certificates before overriding cumulative stale source commits",
        )
    if experiment_id == "branch_restart_transfer":
        return (
            "receipt_bound_restart_anchor",
            f"local continuation commits {report.static_success_count}/{report.domain_count}",
            f"restart-anchor target commits {report.restart_success_count}/{report.domain_count}",
            f"restart certificates {report.branch_restart_certificate_count}",
            True,
            "restart-anchor certificates before abandoning local continuation branches",
        )
    if experiment_id == "branch_symmetry_transfer":
        return (
            "receipt_bound_symmetry_transform",
            f"exact source replay commits {report.static_success_count}/{report.domain_count}",
            f"symmetry-mapped target commits {report.symmetry_success_count}/{report.domain_count}",
            f"symmetry certificates {report.branch_symmetry_certificate_count}",
            True,
            "typed symmetry-transform certificates before mapping past branch actions",
        )
    if experiment_id == "branch_constraint_transfer":
        return (
            "receipt_bound_pairwise_constraint",
            f"incompatible target pairs commit {report.static_success_count}/{report.domain_count}",
            f"constraint-guided target pairs commit {report.constraint_success_count}/{report.domain_count}",
            f"constraint certificates {report.branch_constraint_certificate_count}",
            True,
            "pairwise constraint certificates before combinatorial branch promotion",
        )
    if experiment_id == "branch_confidence_transfer":
        return (
            "receipt_bound_confidence_support",
            f"thin optimistic target commits {report.static_success_count}/{report.domain_count}",
            f"confidence-bound target commits {report.confidence_success_count}/{report.domain_count}",
            f"confidence certificates {report.branch_confidence_certificate_count}",
            True,
            "support-confidence certificates before promoting thin source evidence",
        )
    if experiment_id == "branch_pareto_transfer":
        return (
            "receipt_bound_pareto_front",
            f"scalar replay commits {report.static_success_count}/{report.domain_count}",
            f"Pareto-guided target commits {report.pareto_success_count}/{report.domain_count}",
            f"Pareto certificates {report.branch_pareto_certificate_count}",
            True,
            "multi-objective dominance certificates before scalar objective replay",
        )
    if experiment_id == "branch_outlier_filter_transfer":
        return (
            "receipt_bound_outlier_filter",
            f"outlier replay commits {report.static_success_count}/{report.domain_count}",
            f"inlier-filtered target commits {report.filtered_success_count}/{report.domain_count}",
            f"outlier-filter certificates {report.branch_outlier_filter_certificate_count}",
            True,
            "receipt-bound inlier/outlier provenance before source-branch reuse",
        )
    if experiment_id == "branch_provenance_guard_transfer":
        return (
            "receipt_bound_provenance_guard",
            f"quarantined-source target commits {report.static_success_count}/{report.domain_count}",
            f"provenance-guarded target commits {report.guarded_success_count}/{report.domain_count}",
            f"provenance-guard certificates {report.branch_provenance_guard_certificate_count}",
            True,
            "source-id provenance guard certificates before target branch priority",
        )
    if experiment_id == "branch_credit_assignment_transfer":
        return (
            "receipt_bound_credit_assignment",
            f"low-credit target commits {report.static_success_count}/{report.domain_count}",
            f"credit-guided target commits {report.credit_success_count}/{report.domain_count}",
            f"credit-assignment certificates {report.branch_credit_assignment_certificate_count}",
            True,
            "marginal-credit certificates before weighting source branch fragments",
        )
    if experiment_id == "branch_propensity_match_transfer":
        return (
            "receipt_bound_propensity_match",
            f"mismatched-context target commits {report.static_success_count}/{report.domain_count}",
            f"propensity-matched target commits {report.matched_success_count}/{report.domain_count}",
            f"propensity-match certificates {report.branch_propensity_match_certificate_count}",
            True,
            "covariate-balance and propensity-caliper certificates before context transfer",
        )
    if experiment_id == "branch_robustness_transfer":
        return (
            "receipt_bound_uncertainty_set_coverage",
            f"brittle target commits {report.static_success_count}/{report.domain_count}",
            f"robust target commits {report.robust_success_count}/{report.domain_count}",
            f"robustness certificates {report.branch_robustness_certificate_count}",
            True,
            "uncertainty-set coverage certificates before robust source branch reuse",
        )
    if experiment_id == "branch_composition_transfer":
        return (
            "receipt_bound_branch_composition",
            f"static and single-fragment commits {report.static_budget_success_count + report.component_only_budget_success_count}/{report.domain_count * 3}",
            f"composed proposals commit {report.composed_budget_success_count}/{report.domain_count}",
            f"composition certificates {report.branch_composition_certificate_count}",
            True,
            "fragment-level branch composition certificates before proposal promotion",
        )
    if experiment_id == "branch_pruning_transfer":
        return (
            "receipt_bound_branch_pruning",
            f"unpruned budget commits {report.static_budget_success_count}/{report.domain_count}",
            f"pruned budget commits {report.pruned_budget_success_count}/{report.domain_count}",
            f"pruned actions {report.pruned_action_count}",
            True,
            "nogood-style branch pruning certificates before verifier-budget allocation",
        )
    if experiment_id == "branch_diversity_transfer":
        return (
            "diversity_certified_family_coverage",
            f"repeated-family budget commits {report.static_budget_success_count}/{report.domain_count}",
            f"diverse-family budget commits {report.diverse_budget_success_count}/{report.domain_count}",
            f"diversity certificates {report.branch_diversity_certificate_count}",
            True,
            "quality-diversity-style coverage certificates before branch-budget allocation",
        )
    if experiment_id == "branch_budget_transfer":
        return (
            "receipt_bound_budget_allocation",
            f"static budget commits {report.static_budget_success_count}/{report.domain_count} with {report.static_abstain_count} abstains",
            f"allocated budget commits {report.allocated_budget_success_count}/{report.domain_count}",
            f"budget certificates {report.branch_budget_certificate_count}",
            True,
            "successive-halving-style budget allocation certificates before hard verification",
        )
    if experiment_id == "branch_stop_rule_transfer":
        return (
            "receipt_bound_stop_rule_abstention",
            f"static target spends {report.static_verifier_call_count} verifier calls with {report.static_success_count} commits",
            f"stop rule spends {report.stopped_verifier_call_count} verifier calls with {report.stopped_abstain_count} abstains",
            f"avoided verifier calls {report.avoided_verifier_call_count}",
            True,
            "no-good stop-rule certificates before abstaining from matched target families",
        )
    if experiment_id == "context_retention_transfer":
        return (
            "retained_memory_influence",
            f"static sibling budget commits {report.sibling_static_budget_success_count}/{report.domain_count}",
            f"influence-ranked sibling commits {report.sibling_budget_success_count}/{report.domain_count}",
            f"retention {report.retention_certificate_count}, influence {report.influence_certificate_count}, ablation {report.influence_ablation_certificate_count}",
            True,
            "hash-checked memory mutation plus snapshot-bound influence certificates",
        )
    raise ValueError(f"unknown branch-history experiment: {experiment_id}")


def _metric(children: tuple[CertifiedExampleResult, ...], name: str) -> int:
    return sum(int(getattr(child.report, name, 0)) for child in children)


def _metric_for(children: tuple[CertifiedExampleResult, ...], experiment_id: str, name: str) -> int:
    return sum(
        int(getattr(child.report, name, 0))
        for child in children
        if child.evidence_certificate.experiment_id == experiment_id
    )


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_history_frontier_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
