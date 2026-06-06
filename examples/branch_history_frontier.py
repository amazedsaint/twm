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
from examples.common import CertifiedExampleResult, report_as_dict, validate_example_evidence_certificate
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
)
BRANCH_HISTORY_FRONTIER_CLAIM_BOUNDARY = (
    "G1 aggregate over local deterministic branch-history examples only. It shows a staged evidence "
    "path for proposal ordering, context selection, retrieval refinement, query-policy reuse, conflict "
    "resolution, drift quarantine, and retained-memory influence. It is not a statistical exploration "
    "algorithm, regret guarantee, MCTS result, automatic similarity metric, or scientific-discovery claim."
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
    branch_conflict_certificate_count: int
    query_policy_certificate_count: int
    drift_quarantine_certificate_count: int
    quarantined_context_count: int
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
            run_analogical_branch_transfer_certified_experiment(),
            run_context_selection_transfer_certified_experiment(),
            run_context_refinement_transfer_certified_experiment(),
            run_context_query_policy_transfer_certified_experiment(),
            run_context_drift_quarantine_certified_experiment(),
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
        branch_conflict_certificate_count=_metric(children, "branch_conflict_certificate_count"),
        query_policy_certificate_count=_metric(children, "query_policy_certificate_count"),
        drift_quarantine_certificate_count=_metric(children, "drift_quarantine_certificate_count"),
        quarantined_context_count=_metric(children, "quarantined_context_count"),
        retention_certificate_count=_metric(children, "retention_certificate_count"),
        influence_certificate_count=_metric(children, "influence_certificate_count"),
        aggregate_sources=tuple(sorted({source for child in children for source in child.evidence_certificate.sources})),
        learning=(
            "The branch-history evidence path is now staged: receipt-bound ordering first, explicit "
            "ancestor reuse second, certified context selection third, counterexample-driven refinement "
            "fourth, reusable query-policy and conflict-resolution certificates fifth, drift quarantine "
            "sixth, and retained-memory influence with matched ablation seventh."
        ),
    )
    claim = certify_claim(
        claim_id="branch_history_frontier_g1",
        claim_text=(
            "The certified branch-history examples identify a local G1 substrate path where branches of "
            "the past improve exploration only through audited proposal ordering, selection, refinement, "
            "query-policy, conflict-resolution, drift-quarantine, retention, and influence certificates."
        ),
        evidence_grade="G1",
        scope="branch_history_frontier",
        requirements=(
            requirement("exactly_seven_branch_history_stages", report.stage_count == 7),
            requirement(
                "expected_child_experiments",
                set(report.child_experiment_ids)
                == {
                    "ancestral_branch_exploration",
                    "analogical_branch_transfer",
                    "context_selection_transfer",
                    "context_refinement_transfer",
                    "context_query_policy_transfer",
                    "context_drift_quarantine",
                    "context_retention_transfer",
                },
            ),
            requirement("all_evidence_certificates_valid", report.all_evidence_valid),
            requirement("all_primary_certificates_valid", report.all_primary_certificates_valid),
            requirement("all_child_claims_supported", report.all_claims_supported),
            requirement("no_invalid_commits", report.total_invalid_commit_count == 0),
            requirement("same_budget_checks_all_stages", report.same_budget_stage_count == report.stage_count),
            requirement("query_policy_conflict_certificates_present", report.branch_conflict_certificate_count == 6),
            requirement(
                "drift_quarantine_certificates_present",
                report.drift_quarantine_certificate_count == 3 and report.quarantined_context_count == 3,
            ),
            requirement("retention_and_influence_certificates_present", report.retention_certificate_count == 3 and report.influence_certificate_count == 3),
            requirement("source_coverage", set(report.aggregate_sources) == set(BRANCH_HISTORY_FRONTIER_SOURCES)),
        ),
        metrics={
            "stage_count": report.stage_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "branch_conflict_certificate_count": report.branch_conflict_certificate_count,
            "query_policy_certificate_count": report.query_policy_certificate_count,
            "drift_quarantine_certificate_count": report.drift_quarantine_certificate_count,
            "quarantined_context_count": report.quarantined_context_count,
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
    if experiment_id == "context_retention_transfer":
        return child.context_retention_transfer_certificate
    raise ValueError(f"unknown branch-history experiment: {experiment_id}")


def _primary_certificate_valid(child: CertifiedExampleResult) -> bool:
    experiment_id = child.evidence_certificate.experiment_id
    if experiment_id == "ancestral_branch_exploration":
        return validate_ancestral_branch_exploration_certificate(child.exploration_certificate, child.report)
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


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_history_frontier_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
