from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping

from examples.ancestral_branch_exploration import (
    AncestralExplorationAdapter,
    AncestralExplorationProjector,
    AncestralExplorationState,
    DOMAIN_SPECS,
    HighestUtilityRanker,
    normalize_state,
)
from examples.analogical_branch_transfer import _make_misleading_source_action
from examples.common import (
    CertifiedExampleResult,
    ExampleEvidenceCertificate,
    build_example_evidence_certificate,
    example_report_hash,
    report_as_dict,
    validate_example_evidence_certificate,
)
from examples.context_refinement_transfer import CONTEXT_REFINEMENT_SOURCES
from examples.context_selection_transfer import _action_by_name, _descriptor, _make_traces, _with_context
from trwm.ancestral import (
    AncestralBranchMemory,
    AncestralContextRefinementCertificate,
    AncestralContextSelectionCertificate,
    build_ancestral_context_refinement_certificate,
    build_ancestral_context_selection_certificate,
    validate_ancestral_branch_memory_snapshot,
    validate_ancestral_context_refinement_certificate,
    validate_ancestral_context_selection_certificate,
)
from trwm.branch import (
    BranchSelectionCertificate,
    BranchRuntime,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, Receipt, TransactionEngine, stable_hash


CONTEXT_QUERY_POLICY_CERTIFICATE_SCHEMA = "trwm.context_query_policy_certificate.v1"
CONTEXT_QUERY_POLICY_TRANSFER_CERTIFICATE_SCHEMA = "trwm.context_query_policy_transfer_certificate.v1"
CONTEXT_QUERY_POLICY_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows a rejected calibration branch can "
    "produce a certified query-policy refinement that improves held-out sibling target exploration under "
    "the same one-call verifier budget. It is not automatic feature discovery, statistical active "
    "learning, CEGAR completeness, robotics safety, chemistry, materials-discovery, or scientific "
    "autonomy evidence."
)
CONTEXT_QUERY_POLICY_SOURCES = CONTEXT_REFINEMENT_SOURCES


@dataclass(frozen=True)
class ContextQueryPolicyCertificate:
    schema_version: str
    domain: str
    policy_rule_id: str
    policy_rule_version: str
    calibration_context_id: str
    sibling_context_id: str
    candidate_context_ids: tuple[str, ...]
    calibration_base_selection_certificate_hash: str
    calibration_refined_selection_certificate_hash: str
    sibling_base_selection_certificate_hash: str
    sibling_policy_selection_certificate_hash: str
    refinement_certificate_hash: str
    counterexample_receipt_hash: str
    counterexample_residual_kind: str
    previous_required_tag_keys: tuple[str, ...]
    policy_required_tag_keys: tuple[str, ...]
    selected_before_ids: tuple[str, ...]
    selected_after_ids: tuple[str, ...]
    sibling_stale_selected_ids: tuple[str, ...]
    sibling_policy_selected_ids: tuple[str, ...]
    stale_top_action: str
    policy_top_action: str
    committed_target_action: str
    stale_committed: bool
    policy_committed: bool
    stale_verifier_call_count: int
    policy_verifier_call_count: int
    stale_receipt_hashes: tuple[str, ...]
    policy_receipt_hashes: tuple[str, ...]
    same_budget: bool
    policy_transfer_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_QUERY_POLICY_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid context query policy certificate schema: {self.schema_version}")
        for field_name in (
            "candidate_context_ids",
            "previous_required_tag_keys",
            "policy_required_tag_keys",
            "selected_before_ids",
            "selected_after_ids",
            "sibling_stale_selected_ids",
            "sibling_policy_selected_ids",
            "stale_receipt_hashes",
            "policy_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", context_query_policy_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class ContextQueryPolicyDomainReport:
    domain: str
    calibration_context: str
    sibling_context: str
    candidate_contexts: tuple[str, ...]
    calibration_coarse_selected_contexts: tuple[str, ...]
    calibration_policy_selected_contexts: tuple[str, ...]
    sibling_stale_selected_contexts: tuple[str, ...]
    sibling_policy_selected_contexts: tuple[str, ...]
    calibration_coarse_top_action: str
    sibling_stale_top_action: str
    sibling_policy_top_action: str
    committed_target_action: str
    calibration_coarse_budget_committed: bool
    sibling_stale_budget_committed: bool
    sibling_policy_budget_committed: bool
    counterexample_receipt_hash: str
    counterexample_residual_kind: str
    refinement_certificate_hash: str
    query_policy_certificate_hash: str
    calibration_base_selection_certificate_hash: str
    calibration_refined_selection_certificate_hash: str
    sibling_base_selection_certificate_hash: str
    sibling_policy_selection_certificate_hash: str
    source_receipt_hashes: tuple[str, ...]
    calibration_coarse_receipt_hashes: tuple[str, ...]
    sibling_stale_receipt_hashes: tuple[str, ...]
    sibling_policy_receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]
    same_budget: bool


@dataclass(frozen=True)
class ContextQueryPolicyTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[ContextQueryPolicyDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    calibration_coarse_budget_success_count: int
    sibling_stale_budget_success_count: int
    sibling_policy_budget_success_count: int
    same_budget_query_policy_count: int
    query_policy_certificate_count: int
    refinement_certificate_count: int
    context_selection_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    all_context_selection_certificates_valid: bool
    all_context_refinement_certificates_valid: bool
    all_context_query_policy_certificates_valid: bool
    all_branch_selection_certificates_valid: bool
    all_branch_selection_audits_valid: bool
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    verifier_id: str
    verifier_version: str
    ledger_head: str
    hard_gate_keys: tuple[str, ...]
    residual_kinds: tuple[str, ...]
    sources: tuple[str, ...]
    learning: str


@dataclass(frozen=True)
class ContextQueryPolicyTransferCertificate:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    report_schema_version: str
    report_hash: str
    domain_count: int
    domains: tuple[str, ...]
    ledger_head: str
    receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]
    context_selection_certificate_hashes: tuple[str, ...]
    context_refinement_certificate_hashes: tuple[str, ...]
    context_query_policy_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    calibration_coarse_budget_success_count: int
    sibling_stale_budget_success_count: int
    sibling_policy_budget_success_count: int
    same_budget_query_policy_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_QUERY_POLICY_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid context query policy transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "context_selection_certificate_hashes",
            "context_refinement_certificate_hashes",
            "context_query_policy_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", context_query_policy_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedContextQueryPolicyTransferResult(CertifiedExampleResult):
    report: ContextQueryPolicyTransferReport
    context_query_policy_transfer_certificate: ContextQueryPolicyTransferCertificate
    context_selection_certificates: tuple[AncestralContextSelectionCertificate, ...]
    context_refinement_certificates: tuple[AncestralContextRefinementCertificate, ...]
    context_query_policy_certificates: tuple[ContextQueryPolicyCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_context_query_policy_transfer_experiment() -> ContextQueryPolicyTransferReport:
    return run_context_query_policy_transfer_certified_experiment().report


def run_context_query_policy_transfer_certified_experiment() -> CertifiedContextQueryPolicyTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[ContextQueryPolicyDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    selection_certificates: list[AncestralContextSelectionCertificate] = []
    refinement_certificates: list[AncestralContextRefinementCertificate] = []
    query_policy_certificates: list[ContextQueryPolicyCertificate] = []
    query_policy_audits: list[
        tuple[
            ContextQueryPolicyCertificate,
            tuple[Receipt, ...],
            tuple[Receipt, ...],
            AncestralContextSelectionCertificate,
            AncestralContextSelectionCertificate,
            AncestralContextSelectionCertificate,
            AncestralContextSelectionCertificate,
            AncestralContextRefinementCertificate,
            Receipt,
        ]
    ] = []

    for spec in DOMAIN_SPECS:
        calibration_descriptor = _descriptor(spec, f"{spec.domain_id}:calibration_target", regime="target-compatible")
        sibling_descriptor = _descriptor(spec, f"{spec.domain_id}:sibling_target", regime="target-compatible")
        compatible_descriptor = _descriptor(spec, f"{spec.domain_id}:policy_ancestor", regime="target-compatible")
        misleading_descriptors = (
            _descriptor(spec, f"{spec.domain_id}:policy_misleading_a", regime="source-only"),
            _descriptor(spec, f"{spec.domain_id}:policy_misleading_b", regime="source-only"),
        )
        candidate_descriptors = (compatible_descriptor, *misleading_descriptors)
        calibration_base_selection = build_ancestral_context_selection_certificate(
            calibration_descriptor,
            candidate_descriptors,
            required_tag_keys=(),
        )
        calibration_refined_selection = build_ancestral_context_selection_certificate(
            calibration_descriptor,
            candidate_descriptors,
            required_tag_keys=("regime",),
        )
        sibling_base_selection = build_ancestral_context_selection_certificate(
            sibling_descriptor,
            candidate_descriptors,
            required_tag_keys=(),
        )
        sibling_policy_selection = build_ancestral_context_selection_certificate(
            sibling_descriptor,
            candidate_descriptors,
            required_tag_keys=("regime",),
        )
        selection_certificates.extend(
            (
                calibration_base_selection,
                calibration_refined_selection,
                sibling_base_selection,
                sibling_policy_selection,
            )
        )

        source_receipts: list[Receipt] = []
        branch_certificate_hashes: list[str] = []
        for episode, descriptor in enumerate(candidate_descriptors):
            if descriptor.context_id in {row.context_id for row in misleading_descriptors}:
                actions = tuple(_make_misleading_source_action(spec, action, descriptor.context_id) for action in spec.actions)
            else:
                actions = tuple(_with_context(action, descriptor.context_id) for action in spec.actions)
            outcome = runtime.step(
                state,
                _make_traces(
                    spec,
                    context=descriptor.context_id,
                    phase="query-policy-source",
                    episode=episode,
                    actions=actions,
                ),
            )
            state = normalize_state(outcome.state)
            branch_certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), branch_certificate))
            branch_certificate_hashes.append(branch_certificate.certificate_hash)
            source_receipts.extend(outcome.receipts)
            memory.update_branch(outcome.receipts, branch_certificate)

        calibration_actions = tuple(_with_context(action, calibration_descriptor.context_id) for action in spec.actions)
        action_tokens = tuple(str(action["action"]) for action in calibration_actions)
        calibration_coarse_order = tuple(
            str(action) for action in memory.rank_from_contexts(calibration_base_selection.selected_context_ids, action_tokens)
        )
        calibration_coarse_action = _action_by_name(calibration_actions, calibration_coarse_order[0])
        calibration_coarse_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=calibration_descriptor.context_id,
                phase="calibration-coarse-budget-one",
                episode=0,
                actions=(calibration_coarse_action,),
            ),
        )
        calibration_coarse_branch_certificate = build_branch_selection_certificate(
            calibration_coarse_outcome.receipts,
            verifier_call_count=calibration_coarse_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(calibration_coarse_outcome.receipts), calibration_coarse_branch_certificate))
        branch_certificate_hashes.append(calibration_coarse_branch_certificate.certificate_hash)

        refinement_certificate = build_ancestral_context_refinement_certificate(
            target=calibration_descriptor,
            candidates=candidate_descriptors,
            base_selection=calibration_base_selection,
            refined_selection=calibration_refined_selection,
            counterexample_receipt=calibration_coarse_outcome.receipts[0],
            added_required_tag_keys=("regime",),
            refinement_reason="calibration_reject_refines_sibling_query_policy",
        )
        refinement_certificates.append(refinement_certificate)

        sibling_actions = tuple(_with_context(action, sibling_descriptor.context_id) for action in spec.actions)
        sibling_action_tokens = tuple(str(action["action"]) for action in sibling_actions)
        sibling_stale_order = tuple(
            str(action) for action in memory.rank_from_contexts(sibling_base_selection.selected_context_ids, sibling_action_tokens)
        )
        sibling_stale_action = _action_by_name(sibling_actions, sibling_stale_order[0])
        sibling_stale_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=sibling_descriptor.context_id,
                phase="sibling-stale-query-budget-one",
                episode=0,
                actions=(sibling_stale_action,),
            ),
        )
        sibling_stale_branch_certificate = build_branch_selection_certificate(
            sibling_stale_outcome.receipts,
            verifier_call_count=sibling_stale_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(sibling_stale_outcome.receipts), sibling_stale_branch_certificate))
        branch_certificate_hashes.append(sibling_stale_branch_certificate.certificate_hash)

        sibling_policy_order = tuple(
            str(action) for action in memory.rank_from_contexts(sibling_policy_selection.selected_context_ids, sibling_action_tokens)
        )
        sibling_policy_action = _action_by_name(sibling_actions, sibling_policy_order[0])
        sibling_policy_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=sibling_descriptor.context_id,
                phase="sibling-query-policy-budget-one",
                episode=0,
                actions=(sibling_policy_action,),
            ),
        )
        state = normalize_state(sibling_policy_outcome.state)
        sibling_policy_branch_certificate = build_branch_selection_certificate(
            sibling_policy_outcome.receipts,
            verifier_call_count=sibling_policy_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(sibling_policy_outcome.receipts), sibling_policy_branch_certificate))
        branch_certificate_hashes.append(sibling_policy_branch_certificate.certificate_hash)

        query_policy_certificate = build_context_query_policy_certificate(
            domain=spec.domain_id,
            calibration_context_id=calibration_descriptor.context_id,
            sibling_context_id=sibling_descriptor.context_id,
            candidate_context_ids=calibration_base_selection.candidate_context_ids,
            calibration_base_selection=calibration_base_selection,
            calibration_refined_selection=calibration_refined_selection,
            sibling_base_selection=sibling_base_selection,
            sibling_policy_selection=sibling_policy_selection,
            refinement_certificate=refinement_certificate,
            counterexample_receipt=calibration_coarse_outcome.receipts[0],
            stale_top_action=sibling_stale_order[0],
            policy_top_action=sibling_policy_order[0],
            committed_target_action=spec.committed_action,
            stale_outcome=sibling_stale_outcome,
            policy_outcome=sibling_policy_outcome,
            policy_transfer_reason="calibration_refinement_applied_to_heldout_sibling_target",
        )
        query_policy_certificates.append(query_policy_certificate)
        query_policy_audits.append(
            (
                query_policy_certificate,
                tuple(sibling_stale_outcome.receipts),
                tuple(sibling_policy_outcome.receipts),
                calibration_base_selection,
                calibration_refined_selection,
                sibling_base_selection,
                sibling_policy_selection,
                refinement_certificate,
                calibration_coarse_outcome.receipts[0],
            )
        )

        residual = calibration_coarse_outcome.receipts[0].hard_result.residual
        residual_kind = str(residual.get("kind", "")) if isinstance(residual, Mapping) else ""
        rows.append(
            ContextQueryPolicyDomainReport(
                domain=spec.domain_id,
                calibration_context=calibration_descriptor.context_id,
                sibling_context=sibling_descriptor.context_id,
                candidate_contexts=calibration_base_selection.candidate_context_ids,
                calibration_coarse_selected_contexts=calibration_base_selection.selected_context_ids,
                calibration_policy_selected_contexts=calibration_refined_selection.selected_context_ids,
                sibling_stale_selected_contexts=sibling_base_selection.selected_context_ids,
                sibling_policy_selected_contexts=sibling_policy_selection.selected_context_ids,
                calibration_coarse_top_action=calibration_coarse_order[0],
                sibling_stale_top_action=sibling_stale_order[0],
                sibling_policy_top_action=sibling_policy_order[0],
                committed_target_action=spec.committed_action,
                calibration_coarse_budget_committed=calibration_coarse_outcome.committed,
                sibling_stale_budget_committed=sibling_stale_outcome.committed,
                sibling_policy_budget_committed=sibling_policy_outcome.committed,
                counterexample_receipt_hash=calibration_coarse_outcome.receipts[0].receipt_hash,
                counterexample_residual_kind=residual_kind,
                refinement_certificate_hash=refinement_certificate.certificate_hash,
                query_policy_certificate_hash=query_policy_certificate.certificate_hash,
                calibration_base_selection_certificate_hash=calibration_base_selection.certificate_hash,
                calibration_refined_selection_certificate_hash=calibration_refined_selection.certificate_hash,
                sibling_base_selection_certificate_hash=sibling_base_selection.certificate_hash,
                sibling_policy_selection_certificate_hash=sibling_policy_selection.certificate_hash,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_receipts),
                calibration_coarse_receipt_hashes=tuple(receipt.receipt_hash for receipt in calibration_coarse_outcome.receipts),
                sibling_stale_receipt_hashes=tuple(receipt.receipt_hash for receipt in sibling_stale_outcome.receipts),
                sibling_policy_receipt_hashes=tuple(receipt.receipt_hash for receipt in sibling_policy_outcome.receipts),
                branch_selection_certificate_hashes=tuple(branch_certificate_hashes),
                same_budget=query_policy_certificate.same_budget,
            )
        )

    memory_snapshot = memory.snapshot()
    all_receipts = tuple(engine.ledger.rows)
    ledger_audit_ok = engine.ledger.audit()
    replay_audit_ok = False
    rollback_audit_ok = False
    if ledger_audit_ok:
        try:
            replay_audit_ok = engine.replay_audit(seed) == state
            rollback_audit_ok = engine.rollback_audit(seed) == seed
        except Exception:
            replay_audit_ok = False
            rollback_audit_ok = False
    all_branch_selection_certificates_valid = all(
        validate_branch_selection_certificate(certificate) for _, certificate in branch_certificate_pairs
    )
    all_branch_selection_audits_valid = all(
        audit_branch_selection(receipts, certificate) for receipts, certificate in branch_certificate_pairs
    )
    all_context_selection_certificates_valid = all(
        validate_ancestral_context_selection_certificate(certificate)
        for certificate in selection_certificates
    )
    all_context_refinement_certificates_valid = all(
        validate_ancestral_context_refinement_certificate(certificate)
        for certificate in refinement_certificates
    )
    all_context_query_policy_certificates_valid = all(
        validate_context_query_policy_certificate(
            certificate,
            stale_receipts=stale_receipts,
            policy_receipts=policy_receipts,
            calibration_base_selection=calibration_base_selection,
            calibration_refined_selection=calibration_refined_selection,
            sibling_base_selection=sibling_base_selection,
            sibling_policy_selection=sibling_policy_selection,
            refinement_certificate=refinement_certificate,
            counterexample_receipt=counterexample_receipt,
        )
        for (
            certificate,
            stale_receipts,
            policy_receipts,
            calibration_base_selection,
            calibration_refined_selection,
            sibling_base_selection,
            sibling_policy_selection,
            refinement_certificate,
            counterexample_receipt,
        ) in query_policy_audits
    )
    report = ContextQueryPolicyTransferReport(
        schema_version="trwm.example.context_query_policy_transfer.v1",
        experiment_id="context_query_policy_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        calibration_coarse_budget_success_count=sum(1 for row in rows if row.calibration_coarse_budget_committed),
        sibling_stale_budget_success_count=sum(1 for row in rows if row.sibling_stale_budget_committed),
        sibling_policy_budget_success_count=sum(1 for row in rows if row.sibling_policy_budget_committed),
        same_budget_query_policy_count=sum(1 for row in rows if row.same_budget),
        query_policy_certificate_count=len(query_policy_certificates),
        refinement_certificate_count=len(refinement_certificates),
        context_selection_certificate_count=len(selection_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        all_context_selection_certificates_valid=all_context_selection_certificates_valid,
        all_context_refinement_certificates_valid=all_context_refinement_certificates_valid,
        all_context_query_policy_certificates_valid=all_context_query_policy_certificates_valid,
        all_branch_selection_certificates_valid=all_branch_selection_certificates_valid,
        all_branch_selection_audits_valid=all_branch_selection_audits_valid,
        replay_audit_ok=replay_audit_ok,
        rollback_audit_ok=rollback_audit_ok,
        ledger_audit_ok=ledger_audit_ok,
        invalid_commit_count=engine.invalid_commit_count,
        verifier_id=engine.adapter.verifier_id,
        verifier_version=engine.adapter.verifier_version,
        ledger_head=engine.ledger.head,
        hard_gate_keys=("clearance", "turn_rate", "valence_ok", "strain", "thermal_gradient", "phase_purity"),
        residual_kinds=tuple(sorted({spec.residual_kind for spec in DOMAIN_SPECS})),
        sources=CONTEXT_QUERY_POLICY_SOURCES,
        learning=(
            "A failed calibration branch can refine the ancestor query policy once, then the refined "
            "required-tag policy can improve held-out sibling target exploration against a stale "
            "coarse-query baseline under the same one-call verifier budget."
        ),
    )
    transfer_certificate = build_context_query_policy_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        context_selection_certificate_hashes=tuple(certificate.certificate_hash for certificate in selection_certificates),
        context_refinement_certificate_hashes=tuple(certificate.certificate_hash for certificate in refinement_certificates),
        context_query_policy_certificate_hashes=tuple(certificate.certificate_hash for certificate in query_policy_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="context_query_policy_branch_transfer",
        verifier_id=engine.adapter.verifier_id,
        verifier_version=engine.adapter.verifier_version,
        ledger_head=engine.ledger.head,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        committed_count=report.total_committed_count,
        rejected_count=report.total_rejected_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        hard_gate_keys=report.hard_gate_keys,
        residual_kinds=report.residual_kinds,
        claim_boundary=CONTEXT_QUERY_POLICY_CLAIM_BOUNDARY,
        sources=CONTEXT_QUERY_POLICY_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedContextQueryPolicyTransferResult(
        report=report,
        context_query_policy_transfer_certificate=transfer_certificate,
        context_selection_certificates=tuple(selection_certificates),
        context_refinement_certificates=tuple(refinement_certificates),
        context_query_policy_certificates=tuple(query_policy_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_context_query_policy_certificate(
    *,
    domain: str,
    calibration_context_id: str,
    sibling_context_id: str,
    candidate_context_ids: tuple[str, ...],
    calibration_base_selection: AncestralContextSelectionCertificate,
    calibration_refined_selection: AncestralContextSelectionCertificate,
    sibling_base_selection: AncestralContextSelectionCertificate,
    sibling_policy_selection: AncestralContextSelectionCertificate,
    refinement_certificate: AncestralContextRefinementCertificate,
    counterexample_receipt: Receipt,
    stale_top_action: str,
    policy_top_action: str,
    committed_target_action: str,
    stale_outcome: Any,
    policy_outcome: Any,
    policy_transfer_reason: str,
    policy_rule_id: str = "counterexample_required_tag_policy",
    policy_rule_version: str = "1.0",
) -> ContextQueryPolicyCertificate:
    residual = counterexample_receipt.hard_result.residual
    residual_kind = str(residual.get("kind", "")) if isinstance(residual, Mapping) else ""
    return ContextQueryPolicyCertificate(
        schema_version=CONTEXT_QUERY_POLICY_CERTIFICATE_SCHEMA,
        domain=domain,
        policy_rule_id=policy_rule_id,
        policy_rule_version=policy_rule_version,
        calibration_context_id=calibration_context_id,
        sibling_context_id=sibling_context_id,
        candidate_context_ids=candidate_context_ids,
        calibration_base_selection_certificate_hash=calibration_base_selection.certificate_hash,
        calibration_refined_selection_certificate_hash=calibration_refined_selection.certificate_hash,
        sibling_base_selection_certificate_hash=sibling_base_selection.certificate_hash,
        sibling_policy_selection_certificate_hash=sibling_policy_selection.certificate_hash,
        refinement_certificate_hash=refinement_certificate.certificate_hash,
        counterexample_receipt_hash=counterexample_receipt.receipt_hash,
        counterexample_residual_kind=residual_kind,
        previous_required_tag_keys=calibration_base_selection.required_tag_keys,
        policy_required_tag_keys=calibration_refined_selection.required_tag_keys,
        selected_before_ids=calibration_base_selection.selected_context_ids,
        selected_after_ids=calibration_refined_selection.selected_context_ids,
        sibling_stale_selected_ids=sibling_base_selection.selected_context_ids,
        sibling_policy_selected_ids=sibling_policy_selection.selected_context_ids,
        stale_top_action=stale_top_action,
        policy_top_action=policy_top_action,
        committed_target_action=committed_target_action,
        stale_committed=bool(stale_outcome.committed),
        policy_committed=bool(policy_outcome.committed),
        stale_verifier_call_count=int(stale_outcome.verifier_calls),
        policy_verifier_call_count=int(policy_outcome.verifier_calls),
        stale_receipt_hashes=tuple(receipt.receipt_hash for receipt in stale_outcome.receipts),
        policy_receipt_hashes=tuple(receipt.receipt_hash for receipt in policy_outcome.receipts),
        same_budget=stale_outcome.verifier_calls == policy_outcome.verifier_calls,
        policy_transfer_reason=policy_transfer_reason,
    )


def validate_context_query_policy_certificate(
    certificate: ContextQueryPolicyCertificate,
    *,
    stale_receipts: tuple[Receipt, ...] | None = None,
    policy_receipts: tuple[Receipt, ...] | None = None,
    calibration_base_selection: AncestralContextSelectionCertificate | None = None,
    calibration_refined_selection: AncestralContextSelectionCertificate | None = None,
    sibling_base_selection: AncestralContextSelectionCertificate | None = None,
    sibling_policy_selection: AncestralContextSelectionCertificate | None = None,
    refinement_certificate: AncestralContextRefinementCertificate | None = None,
    counterexample_receipt: Receipt | None = None,
) -> bool:
    try:
        if certificate.schema_version != CONTEXT_QUERY_POLICY_CERTIFICATE_SCHEMA:
            return False
        for value in (
            certificate.domain,
            certificate.policy_rule_id,
            certificate.policy_rule_version,
            certificate.calibration_context_id,
            certificate.sibling_context_id,
            certificate.counterexample_residual_kind,
            certificate.stale_top_action,
            certificate.policy_top_action,
            certificate.committed_target_action,
            certificate.policy_transfer_reason,
        ):
            if not value:
                return False
        if not certificate.candidate_context_ids or any(not value for value in certificate.candidate_context_ids):
            return False
        for value in (
            certificate.calibration_base_selection_certificate_hash,
            certificate.calibration_refined_selection_certificate_hash,
            certificate.sibling_base_selection_certificate_hash,
            certificate.sibling_policy_selection_certificate_hash,
            certificate.refinement_certificate_hash,
            certificate.counterexample_receipt_hash,
        ):
            if not _is_hash(value):
                return False
        if certificate.previous_required_tag_keys != _unique_keys(certificate.previous_required_tag_keys):
            return False
        if certificate.policy_required_tag_keys != _unique_keys(certificate.policy_required_tag_keys):
            return False
        if not certificate.policy_required_tag_keys:
            return False
        if set(certificate.previous_required_tag_keys).issuperset(certificate.policy_required_tag_keys):
            return False
        if not certificate.selected_before_ids or not certificate.selected_after_ids:
            return False
        if not set(certificate.selected_after_ids).issubset(set(certificate.selected_before_ids)):
            return False
        if set(certificate.selected_before_ids) == set(certificate.selected_after_ids):
            return False
        if not certificate.sibling_stale_selected_ids or not certificate.sibling_policy_selected_ids:
            return False
        if not set(certificate.sibling_policy_selected_ids).issubset(set(certificate.sibling_stale_selected_ids)):
            return False
        if set(certificate.sibling_policy_selected_ids) == set(certificate.sibling_stale_selected_ids):
            return False
        if certificate.sibling_policy_selected_ids != certificate.selected_after_ids:
            return False
        if certificate.stale_top_action == certificate.committed_target_action:
            return False
        if certificate.policy_top_action != certificate.committed_target_action:
            return False
        if certificate.stale_committed:
            return False
        if not certificate.policy_committed:
            return False
        for value in (certificate.stale_verifier_call_count, certificate.policy_verifier_call_count):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return False
        if certificate.stale_verifier_call_count != certificate.policy_verifier_call_count:
            return False
        if not certificate.same_budget:
            return False
        for values in (certificate.stale_receipt_hashes, certificate.policy_receipt_hashes):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if stale_receipts is not None:
            if tuple(receipt.receipt_hash for receipt in stale_receipts) != certificate.stale_receipt_hashes:
                return False
            if any(not receipt.static_valid() for receipt in stale_receipts):
                return False
            if any(receipt.committed for receipt in stale_receipts):
                return False
        if policy_receipts is not None:
            if tuple(receipt.receipt_hash for receipt in policy_receipts) != certificate.policy_receipt_hashes:
                return False
            if any(not receipt.static_valid() for receipt in policy_receipts):
                return False
            if not any(receipt.committed for receipt in policy_receipts):
                return False
        if calibration_base_selection is not None:
            if calibration_base_selection.certificate_hash != certificate.calibration_base_selection_certificate_hash:
                return False
            if calibration_base_selection.required_tag_keys != certificate.previous_required_tag_keys:
                return False
            if calibration_base_selection.selected_context_ids != certificate.selected_before_ids:
                return False
            if not validate_ancestral_context_selection_certificate(calibration_base_selection):
                return False
        if calibration_refined_selection is not None:
            if calibration_refined_selection.certificate_hash != certificate.calibration_refined_selection_certificate_hash:
                return False
            if calibration_refined_selection.required_tag_keys != certificate.policy_required_tag_keys:
                return False
            if calibration_refined_selection.selected_context_ids != certificate.selected_after_ids:
                return False
            if not validate_ancestral_context_selection_certificate(calibration_refined_selection):
                return False
        if sibling_base_selection is not None:
            if sibling_base_selection.certificate_hash != certificate.sibling_base_selection_certificate_hash:
                return False
            if sibling_base_selection.selected_context_ids != certificate.sibling_stale_selected_ids:
                return False
            if not validate_ancestral_context_selection_certificate(sibling_base_selection):
                return False
        if sibling_policy_selection is not None:
            if sibling_policy_selection.certificate_hash != certificate.sibling_policy_selection_certificate_hash:
                return False
            if sibling_policy_selection.required_tag_keys != certificate.policy_required_tag_keys:
                return False
            if sibling_policy_selection.selected_context_ids != certificate.sibling_policy_selected_ids:
                return False
            if not validate_ancestral_context_selection_certificate(sibling_policy_selection):
                return False
        if refinement_certificate is not None:
            if refinement_certificate.certificate_hash != certificate.refinement_certificate_hash:
                return False
            if refinement_certificate.counterexample_receipt_hash != certificate.counterexample_receipt_hash:
                return False
            if refinement_certificate.refined_required_tag_keys != certificate.policy_required_tag_keys:
                return False
            if not validate_ancestral_context_refinement_certificate(refinement_certificate):
                return False
        if counterexample_receipt is not None:
            if not counterexample_receipt.static_valid():
                return False
            if counterexample_receipt.receipt_hash != certificate.counterexample_receipt_hash:
                return False
            if counterexample_receipt.hard_result.result != "reject":
                return False
            residual = counterexample_receipt.hard_result.residual
            if not isinstance(residual, Mapping) or str(residual.get("kind", "")) != certificate.counterexample_residual_kind:
                return False
        return certificate.certificate_hash == context_query_policy_certificate_hash(certificate)
    except Exception:
        return False


def build_context_query_policy_transfer_certificate(
    report: ContextQueryPolicyTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    context_selection_certificate_hashes: tuple[str, ...],
    context_refinement_certificate_hashes: tuple[str, ...],
    context_query_policy_certificate_hashes: tuple[str, ...],
) -> ContextQueryPolicyTransferCertificate:
    return ContextQueryPolicyTransferCertificate(
        schema_version=CONTEXT_QUERY_POLICY_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        context_selection_certificate_hashes=context_selection_certificate_hashes,
        context_refinement_certificate_hashes=context_refinement_certificate_hashes,
        context_query_policy_certificate_hashes=context_query_policy_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        calibration_coarse_budget_success_count=report.calibration_coarse_budget_success_count,
        sibling_stale_budget_success_count=report.sibling_stale_budget_success_count,
        sibling_policy_budget_success_count=report.sibling_policy_budget_success_count,
        same_budget_query_policy_count=report.same_budget_query_policy_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=CONTEXT_QUERY_POLICY_CLAIM_BOUNDARY,
    )


def validate_context_query_policy_transfer_certificate(
    certificate: ContextQueryPolicyTransferCertificate,
    report: ContextQueryPolicyTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != CONTEXT_QUERY_POLICY_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        if not _is_hash(certificate.report_hash) or not _is_hash(certificate.ledger_head):
            return False
        if not _is_hash(certificate.memory_snapshot_hash):
            return False
        for values in (
            certificate.receipt_hashes,
            certificate.branch_selection_certificate_hashes,
            certificate.context_selection_certificate_hashes,
            certificate.context_refinement_certificate_hashes,
            certificate.context_query_policy_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if certificate.calibration_coarse_budget_success_count != 0:
            return False
        if certificate.sibling_stale_budget_success_count != 0:
            return False
        if certificate.sibling_policy_budget_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_query_policy_count != certificate.domain_count:
            return False
        if len(certificate.context_refinement_certificate_hashes) != certificate.domain_count:
            return False
        if len(certificate.context_query_policy_certificate_hashes) != certificate.domain_count:
            return False
        if len(certificate.context_selection_certificate_hashes) != certificate.domain_count * 4:
            return False
        if not (certificate.replay_audit_ok and certificate.rollback_audit_ok and certificate.ledger_audit_ok):
            return False
        if certificate.invalid_commit_count != 0:
            return False
        if not certificate.claim_boundary:
            return False
        if report is not None:
            if report.experiment_id != certificate.experiment_id:
                return False
            if report.schema_version != certificate.report_schema_version:
                return False
            if report.domain_count != certificate.domain_count or report.domains != certificate.domains:
                return False
            if report.ledger_head != certificate.ledger_head:
                return False
            if report.memory_snapshot_hash != certificate.memory_snapshot_hash:
                return False
            if not report.memory_snapshot_valid:
                return False
            if not report.all_context_selection_certificates_valid:
                return False
            if not report.all_context_refinement_certificates_valid:
                return False
            if not report.all_context_query_policy_certificates_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
        return certificate.certificate_hash == context_query_policy_transfer_certificate_hash(certificate)
    except Exception:
        return False


def context_query_policy_certificate_hash(certificate: ContextQueryPolicyCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, ContextQueryPolicyCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def context_query_policy_transfer_certificate_hash(
    certificate: ContextQueryPolicyTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, ContextQueryPolicyTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedContextQueryPolicyTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: ContextQueryPolicyTransferReport,
    transfer_certificate: ContextQueryPolicyTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="context_query_policy_transfer_g1",
        claim_text=(
            "Rejected calibration branches can refine ancestor query policy, and the refined policy can "
            "improve held-out sibling exploration under the same verifier budget while hard verification "
            "keeps commit authority."
        ),
        evidence_grade="G1",
        scope="context_query_policy_transfer",
        requirements=(
            requirement(
                "context_query_policy_transfer_certificate_valid",
                validate_context_query_policy_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_context_selection_certificates_valid", report.all_context_selection_certificates_valid),
            requirement("all_context_refinement_certificates_valid", report.all_context_refinement_certificates_valid),
            requirement("all_context_query_policy_certificates_valid", report.all_context_query_policy_certificates_valid),
            requirement("memory_snapshot_valid", report.memory_snapshot_valid),
            requirement("calibration_coarse_budget_fails_all_domains", report.calibration_coarse_budget_success_count == 0),
            requirement("sibling_stale_budget_fails_all_domains", report.sibling_stale_budget_success_count == 0),
            requirement("sibling_policy_budget_succeeds_all_domains", report.sibling_policy_budget_success_count == report.domain_count),
            requirement("same_budget_query_policy_all_domains", report.same_budget_query_policy_count == report.domain_count),
            requirement("query_policy_certificates_present", report.query_policy_certificate_count == report.domain_count),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "calibration_coarse_budget_success_count": report.calibration_coarse_budget_success_count,
            "sibling_stale_budget_success_count": report.sibling_stale_budget_success_count,
            "sibling_policy_budget_success_count": report.sibling_policy_budget_success_count,
            "same_budget_query_policy_count": report.same_budget_query_policy_count,
            "query_policy_certificate_count": report.query_policy_certificate_count,
        },
        boundary=CONTEXT_QUERY_POLICY_CLAIM_BOUNDARY,
        sources=CONTEXT_QUERY_POLICY_SOURCES,
    )


def _unique_keys(values: tuple[str, ...]) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if any(not value for value in rows):
        return ()
    return tuple(dict.fromkeys(rows))


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def main() -> None:
    print(json.dumps(result_as_dict(run_context_query_policy_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
