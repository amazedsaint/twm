from __future__ import annotations

from dataclasses import dataclass, replace

from ..claims import ClaimCertificate, certify_claim, requirement, validate_claim_certificate
from .budget_policy import run_budget_policy_benchmark
from .learning_evaluation import run_learning_evaluation_benchmark
from .residual_topk import run_residual_topk_benchmark
from .rrlm_macro import run_rrlm_macro_benchmark
from .shape_simulator import run_shape_conditionality
from .transfer_audit import run_cross_domain_transfer_audit
from .transfer_guard import run_transfer_guard_benchmark
from .world_loop import run_world_loop_benchmark


PROV_SOURCE = "https://www.w3.org/TR/prov-overview/"
ASSURANCE_SOURCE = "https://standards.iteh.ai/catalog/standards/iso/4734d411-2bff-428f-8f4a-164859f171b8/iso-iec-ieee-15026-2-2022"


@dataclass(frozen=True)
class ClaimAuditReport:
    supported_claim_id: str
    supported_status: str
    supported_requirement_count: int
    supported_failed_keys: tuple[str, ...]
    rejected_claim_id: str
    rejected_status: str
    rejected_failed_keys: tuple[str, ...]
    overclaim_detected: bool
    null_result_recorded: bool
    mechanism_ablation_recorded: bool
    heldout_trace_evaluation: bool
    same_case_equal_budget: bool
    verifier_call_accounting: bool
    learning_evaluation_certificate_valid: bool
    learning_evaluation_supports_claim: bool
    transfer_evaluation_certificate_valid: bool
    transfer_positive_overclaim_rejected: bool
    transfer_guard_snapshot_valid: bool
    transfer_guard_blocks_negative_transfer: bool
    rrlm_proposal_certificate_valid: bool
    rrlm_transport_certificate_valid: bool
    world_learner_update_certificate_valid: bool
    world_learner_delta_certificate_valid: bool
    world_learner_lineage_certificate_valid: bool
    world_learner_merge_certificate_valid: bool
    world_learner_partial_overlap_merge_valid: bool
    world_rrlm_proposal_certificate_valid: bool
    world_program_certificate_valid: bool
    world_program_admission_certificate_valid: bool
    world_program_bundle_verification_certificate_valid: bool
    world_program_replay_verification_certificate_valid: bool
    supported_certificate_valid: bool
    rejected_certificate_valid: bool
    tamper_detected: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float
    supported_certificate_hash: str
    rejected_certificate_hash: str


def run_claim_audit_benchmark() -> ClaimAuditReport:
    budget = run_budget_policy_benchmark()
    learning_eval = run_learning_evaluation_benchmark()
    topk = run_residual_topk_benchmark()
    rrlm = run_rrlm_macro_benchmark()
    shape = run_shape_conditionality()
    transfer = run_cross_domain_transfer_audit()
    transfer_guard = run_transfer_guard_benchmark()
    world_loop = run_world_loop_benchmark()

    invalid_commit_count = (
        budget.invalid_commit_count
        + learning_eval.invalid_commit_count
        + topk.invalid_commit_count
        + rrlm.invalid_commit_count
        + shape.invalid_commit_count
        + transfer.invalid_commit_count
        + transfer_guard.invalid_commit_count
        + world_loop.invalid_commit_count
    )
    ledger_audit = (
        budget.ledger_audit
        and learning_eval.ledger_audit
        and topk.ledger_audit
        and rrlm.ledger_audit
        and shape.ledger_audit
        and transfer.ledger_audit
        and transfer_guard.ledger_audit
        and world_loop.ledger_audit
    )
    replay_rollback_rate = min(
        budget.replay_rollback_rate,
        learning_eval.replay_rollback_rate,
        topk.replay_rollback_rate,
        transfer.replay_rollback_rate,
        transfer_guard.replay_rollback_rate,
        world_loop.replay_rollback_rate,
    )
    heldout_trace_evaluation = (
        budget.heldout_trace_disjoint
        and budget.evaluation_receipt_count > 0
        and learning_eval.train_eval_disjoint
        and learning_eval.evaluation_receipt_count > 0
        and transfer.source_target_receipt_disjoint
        and transfer.target_evaluation_receipt_count > 0
    )
    same_case_equal_budget = (
        budget.budget == 3
        and budget.candidate_count == 4
        and learning_eval.same_case_baseline
        and learning_eval.verifier_budget == 3
        and learning_eval.candidate_count == 4
        and topk.top_k == 2
        and topk.candidate_count == 4
        and transfer.same_case_baseline
        and transfer.transfer_verifier_calls == transfer.baseline_verifier_calls
    )
    verifier_call_accounting = (
        _near(budget.verifier_call_gain, budget.cheap_first_verifier_calls / budget.learned_verifier_calls)
        and learning_eval.verifier_call_gain_denominator > 0
        and learning_eval.verifier_call_gain_numerator == learning_eval.baseline_verifier_calls
        and learning_eval.verifier_call_gain_denominator == learning_eval.learned_verifier_calls
        and _near(topk.calls_to_commit_gain, topk.unranked_verifier_calls / topk.residual_ranked_verifier_calls)
        and transfer.success_delta == transfer.transfer_success_count - transfer.baseline_success_count
        and transfer.verifier_call_delta == transfer.transfer_verifier_calls - transfer.baseline_verifier_calls
    )
    learning_evaluation_certificate_valid = learning_eval.certificate_valid
    learning_evaluation_supports_claim = learning_eval.certificate_supports_claim
    transfer_evaluation_certificate_valid = transfer.certificate_valid
    transfer_positive_overclaim_rejected = transfer.positive_transfer_claim_rejected and not transfer.positive_transfer_claim_supported
    transfer_guard_snapshot_valid = transfer_guard.snapshot_valid and transfer_guard.decision_valid
    transfer_guard_blocks_negative_transfer = (
        transfer_guard.guard_blocks_source_policy
        and transfer_guard.avoided_negative_transfer
        and not transfer_guard.guard_decision_admitted
        and transfer_guard.certificate_conclusion == "negative_transfer"
    )
    rrlm_proposal_certificate_valid = rrlm.snapshot_valid and rrlm.proposal_certificate_valid
    rrlm_transport_certificate_valid = (
        rrlm.transport_certificate_valid
        and rrlm.transport_certificate_i32_admissible_count > 0
        and rrlm.transport_certificate_i32_rejected_count == 0
        and rrlm.transport_tamper_detected
    )
    world_learner_update_certificate_valid = (
        world_loop.learner_update_certificate_valid_count == world_loop.step_count
        and world_loop.learner_update_audit_valid_count == world_loop.step_count
        and world_loop.step_certificate_binds_learner_update
        and world_loop.learner_update_tamper_detected
    )
    world_learner_delta_certificate_valid = (
        world_loop.learner_delta_certificate_valid_count == world_loop.step_count
        and world_loop.learner_delta_audit_valid_count == world_loop.step_count
        and world_loop.learner_delta_binds_updates
        and world_loop.learner_delta_tamper_detected
    )
    world_learner_lineage_certificate_valid = (
        world_loop.learner_lineage_certificate_valid
        and world_loop.learner_lineage_audit_valid
        and world_loop.learner_lineage_binds_updates
        and world_loop.learner_lineage_tamper_detected
    )
    world_learner_merge_certificate_valid = (
        world_loop.learner_merge_certificate_valid
        and world_loop.learner_merge_audit_valid
        and world_loop.learner_merge_disjoint_receipts
        and world_loop.learner_merge_tamper_detected
        and world_loop.learner_merge_conflict_detected
    )
    world_learner_partial_overlap_merge_valid = (
        world_loop.learner_merge_partial_overlap_valid
        and world_loop.learner_merge_partial_overlap_audit_valid
        and world_loop.learner_merge_partial_overlap_counts_shared_once
        and world_loop.learner_merge_partial_overlap_requires_deltas
    )
    world_rrlm_proposal_certificate_valid = (
        not world_loop.rrlm_world_first_committed
        and world_loop.rrlm_world_second_committed
        and world_loop.rrlm_world_selected_repair_macro
        and world_loop.rrlm_world_proposal_certificate_valid
        and world_loop.rrlm_world_transport_certificate_valid
        and world_loop.rrlm_world_artifacts_bound_to_receipts
        and world_loop.rrlm_world_rejected_macro_penalized
        and world_loop.rrlm_world_tamper_detected
    )
    world_program_certificate_valid = (
        world_loop.world_program_manifest_valid
        and world_loop.world_program_certificate_valid
        and world_loop.world_program_audit_valid
        and world_loop.world_program_binds_rrlm_artifacts
        and world_loop.world_program_tamper_detected
    )
    world_program_admission_certificate_valid = (
        world_program_certificate_valid
        and world_loop.world_program_admission_policy_valid
        and world_loop.world_program_admission_certificate_valid
        and world_loop.world_program_admission_audit_valid
        and world_loop.world_program_admitted
        and world_loop.world_program_admission_rejects_unmet_requirements
        and world_loop.world_program_admission_tamper_detected
    )
    world_program_bundle_verification_certificate_valid = (
        world_program_admission_certificate_valid
        and world_loop.world_program_evidence_bundle_valid
        and world_loop.world_program_evidence_bundle_audit_valid
        and world_loop.world_program_bundle_verification_certificate_valid
        and world_loop.world_program_bundle_verified
        and world_loop.world_program_bundle_tamper_detected
    )
    world_program_replay_verification_certificate_valid = (
        world_program_bundle_verification_certificate_valid
        and world_loop.world_program_replay_package_valid
        and world_loop.world_program_replay_package_audit_valid
        and world_loop.world_program_replay_verification_certificate_valid
        and world_loop.world_program_replay_verified
        and world_loop.world_program_replay_tamper_detected
    )
    mechanism_ablation_recorded = (
        rrlm.reversible_only_attempts_per_success > 0
        and rrlm.matched_non_reversible_attempts_per_success > 0
        and rrlm.rrlm_attempts_per_success > 0
        and rrlm.rrlm_cycle_failure_count == 0
    )
    null_result_recorded = _near(rrlm.rrlm_vs_non_reversible_gain, 1.0) and not shape.high_preflight_fits_budget

    supported = _supported_certificate(
        invalid_commit_count=invalid_commit_count,
        ledger_audit=ledger_audit,
        replay_rollback_rate=replay_rollback_rate,
        heldout_trace_evaluation=heldout_trace_evaluation,
        same_case_equal_budget=same_case_equal_budget,
        verifier_call_accounting=verifier_call_accounting,
        learning_evaluation_certificate_valid=learning_evaluation_certificate_valid,
        learning_evaluation_supports_claim=learning_evaluation_supports_claim,
        transfer_evaluation_certificate_valid=transfer_evaluation_certificate_valid,
        transfer_positive_overclaim_rejected=transfer_positive_overclaim_rejected,
        transfer_guard_snapshot_valid=transfer_guard_snapshot_valid,
        transfer_guard_blocks_negative_transfer=transfer_guard_blocks_negative_transfer,
        rrlm_proposal_certificate_valid=rrlm_proposal_certificate_valid,
        rrlm_transport_certificate_valid=rrlm_transport_certificate_valid,
        world_learner_update_certificate_valid=world_learner_update_certificate_valid,
        world_learner_delta_certificate_valid=world_learner_delta_certificate_valid,
        world_learner_lineage_certificate_valid=world_learner_lineage_certificate_valid,
        world_learner_merge_certificate_valid=world_learner_merge_certificate_valid,
        world_learner_partial_overlap_merge_valid=world_learner_partial_overlap_merge_valid,
        world_rrlm_proposal_certificate_valid=world_rrlm_proposal_certificate_valid,
        world_program_certificate_valid=world_program_certificate_valid,
        world_program_admission_certificate_valid=world_program_admission_certificate_valid,
        world_program_bundle_verification_certificate_valid=world_program_bundle_verification_certificate_valid,
        world_program_replay_verification_certificate_valid=world_program_replay_verification_certificate_valid,
        mechanism_ablation_recorded=mechanism_ablation_recorded,
        null_result_recorded=null_result_recorded,
        budget_call_gain=budget.verifier_call_gain,
        topk_call_gain=topk.calls_to_commit_gain,
        learning_eval_certificate_hash=learning_eval.certificate_hash,
        transfer_certificate_hash=transfer.certificate_hash,
        transfer_guard_snapshot_hash=transfer_guard.snapshot_hash,
        transfer_guard_decision_hash=transfer_guard.guard_decision_hash,
        rrlm_proposal_certificate_hash=rrlm.proposal_certificate_hash,
        rrlm_transport_certificate_hash=rrlm.transport_certificate_hash,
        transfer_success_delta=transfer.success_delta,
        rrlm_vs_non_reversible_gain=rrlm.rrlm_vs_non_reversible_gain,
        high_rank_gain=shape.high_gain,
    )
    rejected = _overclaim_certificate(rrlm)
    tampered = replace(supported, metrics={**supported.metrics, "invalid_commit_count": 1})

    return ClaimAuditReport(
        supported_claim_id=supported.claim_id,
        supported_status=supported.status,
        supported_requirement_count=len(supported.requirements),
        supported_failed_keys=supported.failed_keys,
        rejected_claim_id=rejected.claim_id,
        rejected_status=rejected.status,
        rejected_failed_keys=rejected.failed_keys,
        overclaim_detected=rejected.status == "rejected" and "matched_non_reversible_lift" in rejected.failed_keys,
        null_result_recorded=null_result_recorded,
        mechanism_ablation_recorded=mechanism_ablation_recorded,
        heldout_trace_evaluation=heldout_trace_evaluation,
        same_case_equal_budget=same_case_equal_budget,
        verifier_call_accounting=verifier_call_accounting,
        learning_evaluation_certificate_valid=learning_evaluation_certificate_valid,
        learning_evaluation_supports_claim=learning_evaluation_supports_claim,
        transfer_evaluation_certificate_valid=transfer_evaluation_certificate_valid,
        transfer_positive_overclaim_rejected=transfer_positive_overclaim_rejected,
        transfer_guard_snapshot_valid=transfer_guard_snapshot_valid,
        transfer_guard_blocks_negative_transfer=transfer_guard_blocks_negative_transfer,
        rrlm_proposal_certificate_valid=rrlm_proposal_certificate_valid,
        rrlm_transport_certificate_valid=rrlm_transport_certificate_valid,
        world_learner_update_certificate_valid=world_learner_update_certificate_valid,
        world_learner_delta_certificate_valid=world_learner_delta_certificate_valid,
        world_learner_lineage_certificate_valid=world_learner_lineage_certificate_valid,
        world_learner_merge_certificate_valid=world_learner_merge_certificate_valid,
        world_learner_partial_overlap_merge_valid=world_learner_partial_overlap_merge_valid,
        world_rrlm_proposal_certificate_valid=world_rrlm_proposal_certificate_valid,
        world_program_certificate_valid=world_program_certificate_valid,
        world_program_admission_certificate_valid=world_program_admission_certificate_valid,
        world_program_bundle_verification_certificate_valid=world_program_bundle_verification_certificate_valid,
        world_program_replay_verification_certificate_valid=world_program_replay_verification_certificate_valid,
        supported_certificate_valid=validate_claim_certificate(supported),
        rejected_certificate_valid=validate_claim_certificate(rejected),
        tamper_detected=not validate_claim_certificate(tampered),
        invalid_commit_count=invalid_commit_count,
        ledger_audit=ledger_audit,
        replay_rollback_rate=replay_rollback_rate,
        supported_certificate_hash=supported.certificate_hash,
        rejected_certificate_hash=rejected.certificate_hash,
    )


def _supported_certificate(
    *,
    invalid_commit_count: int,
    ledger_audit: bool,
    replay_rollback_rate: float,
    heldout_trace_evaluation: bool,
    same_case_equal_budget: bool,
    verifier_call_accounting: bool,
    learning_evaluation_certificate_valid: bool,
    learning_evaluation_supports_claim: bool,
    transfer_evaluation_certificate_valid: bool,
    transfer_positive_overclaim_rejected: bool,
    transfer_guard_snapshot_valid: bool,
    transfer_guard_blocks_negative_transfer: bool,
    rrlm_proposal_certificate_valid: bool,
    rrlm_transport_certificate_valid: bool,
    world_learner_update_certificate_valid: bool,
    world_learner_delta_certificate_valid: bool,
    world_learner_lineage_certificate_valid: bool,
    world_learner_merge_certificate_valid: bool,
    world_learner_partial_overlap_merge_valid: bool,
    world_rrlm_proposal_certificate_valid: bool,
    world_program_certificate_valid: bool,
    world_program_admission_certificate_valid: bool,
    world_program_bundle_verification_certificate_valid: bool,
    world_program_replay_verification_certificate_valid: bool,
    mechanism_ablation_recorded: bool,
    null_result_recorded: bool,
    budget_call_gain: float,
    topk_call_gain: float,
    learning_eval_certificate_hash: str,
    transfer_certificate_hash: str,
    transfer_guard_snapshot_hash: str,
    transfer_guard_decision_hash: str,
    rrlm_proposal_certificate_hash: str,
    rrlm_transport_certificate_hash: str,
    transfer_success_delta: int,
    rrlm_vs_non_reversible_gain: float,
    high_rank_gain: float,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="g1_learning_claim_boundary",
        claim_text="Selected G1 learning canaries preserve transaction safety and record baselines, ablations, nulls, and trace-disjoint evaluation.",
        evidence_grade="G1",
        scope="budget-policy, residual-topk, RRLM macro, and shape-conditionality canaries",
        boundary="This certificate supports only local deterministic G1 evidence. It is not public benchmark lift, learned-model lift, or real-world safety evidence.",
        sources=(PROV_SOURCE, ASSURANCE_SOURCE),
        metrics={
            "budget_call_gain": budget_call_gain,
            "topk_call_gain": topk_call_gain,
            "learning_eval_certificate_hash": learning_eval_certificate_hash,
            "transfer_certificate_hash": transfer_certificate_hash,
            "transfer_guard_snapshot_hash": transfer_guard_snapshot_hash,
            "transfer_guard_decision_hash": transfer_guard_decision_hash,
            "rrlm_proposal_certificate_hash": rrlm_proposal_certificate_hash,
            "rrlm_transport_certificate_hash": rrlm_transport_certificate_hash,
            "transfer_success_delta": transfer_success_delta,
            "rrlm_vs_non_reversible_gain": rrlm_vs_non_reversible_gain,
            "high_rank_gain": high_rank_gain,
            "invalid_commit_count": invalid_commit_count,
            "replay_rollback_rate": replay_rollback_rate,
        },
        requirements=(
            requirement("claim_boundary_g1", True, evidence_grade="G1"),
            requirement("invalid_commits_zero", invalid_commit_count == 0, invalid_commit_count=invalid_commit_count),
            requirement("ledger_audit", ledger_audit),
            requirement("replay_rollback_rate_one", _near(replay_rollback_rate, 1.0), replay_rollback_rate=replay_rollback_rate),
            requirement("trace_disjoint_evaluation", heldout_trace_evaluation),
            requirement("same_case_equal_budget", same_case_equal_budget),
            requirement("verifier_call_accounting", verifier_call_accounting),
            requirement("learning_evaluation_certificate_valid", learning_evaluation_certificate_valid),
            requirement("learning_evaluation_supports_claim", learning_evaluation_supports_claim),
            requirement("transfer_evaluation_certificate_valid", transfer_evaluation_certificate_valid),
            requirement("transfer_positive_overclaim_rejected", transfer_positive_overclaim_rejected),
            requirement("transfer_guard_snapshot_valid", transfer_guard_snapshot_valid),
            requirement("transfer_guard_blocks_negative_transfer", transfer_guard_blocks_negative_transfer),
            requirement("rrlm_proposal_certificate_valid", rrlm_proposal_certificate_valid),
            requirement("rrlm_transport_certificate_valid", rrlm_transport_certificate_valid),
            requirement("world_learner_update_certificate_valid", world_learner_update_certificate_valid),
            requirement("world_learner_delta_certificate_valid", world_learner_delta_certificate_valid),
            requirement("world_learner_lineage_certificate_valid", world_learner_lineage_certificate_valid),
            requirement("world_learner_merge_certificate_valid", world_learner_merge_certificate_valid),
            requirement("world_learner_partial_overlap_merge_valid", world_learner_partial_overlap_merge_valid),
            requirement("world_rrlm_proposal_certificate_valid", world_rrlm_proposal_certificate_valid),
            requirement("world_program_certificate_valid", world_program_certificate_valid),
            requirement("world_program_admission_certificate_valid", world_program_admission_certificate_valid),
            requirement("world_program_bundle_verification_certificate_valid", world_program_bundle_verification_certificate_valid),
            requirement("world_program_replay_verification_certificate_valid", world_program_replay_verification_certificate_valid),
            requirement("mechanism_ablation_recorded", mechanism_ablation_recorded),
            requirement("null_result_recorded", null_result_recorded),
            requirement("soft_scores_no_commit_authority", True, reason="all listed learners rank or schedule only; commit evidence is hard-verifier ledger evidence"),
        ),
    )


def _overclaim_certificate(rrlm) -> ClaimCertificate:
    return certify_claim(
        claim_id="rrlm_reversibility_alone_lift_overclaim",
        claim_text="RRLM reversibility alone improves over the matched non-reversible receipt ranker.",
        evidence_grade="G1",
        scope="RRLM macro-grid canary",
        boundary="The current result ties the matched non-reversible ranker, so mechanism lift is rejected.",
        sources=(PROV_SOURCE, ASSURANCE_SOURCE),
        metrics={
            "rrlm_vs_non_reversible_gain": rrlm.rrlm_vs_non_reversible_gain,
            "cycle_failure_count": rrlm.rrlm_cycle_failure_count,
            "invalid_commit_count": rrlm.invalid_commit_count,
        },
        requirements=(
            requirement("cycle_exactness", rrlm.rrlm_cycle_failure_count == 0, cycle_failures=rrlm.rrlm_cycle_failure_count),
            requirement("mechanism_ablation_present", rrlm.matched_non_reversible_attempts_per_success > 0),
            requirement("matched_non_reversible_lift", rrlm.rrlm_vs_non_reversible_gain > 1.0, gain=rrlm.rrlm_vs_non_reversible_gain),
            requirement("invalid_commits_zero", rrlm.invalid_commit_count == 0, invalid_commit_count=rrlm.invalid_commit_count),
        ),
    )


def _near(left: float, right: float, eps: float = 1e-12) -> bool:
    return abs(left - right) <= eps
