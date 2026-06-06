from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Iterable, Mapping

from examples.ancestral_branch_exploration import (
    AncestralExplorationAdapter,
    AncestralExplorationProjector,
    AncestralExplorationState,
    DOMAIN_SPECS,
    ExplorationDomainSpec,
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
from examples.context_selection_transfer import (
    CONTEXT_SELECTION_SOURCES,
    _action_by_name,
    _descriptor,
    _make_traces,
    _with_context,
)
from trwm.ancestral import (
    AncestralBranchMemory,
    AncestralContextRefinementCertificate,
    build_ancestral_context_refinement_certificate,
    build_ancestral_context_selection_certificate,
    validate_ancestral_branch_memory_snapshot,
    validate_ancestral_context_refinement_certificate,
    validate_ancestral_context_selection_certificate,
)
from trwm.branch import (
    BranchRuntime,
    BranchSelectionCertificate,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


CONTEXT_REFINEMENT_TRANSFER_CERTIFICATE_SCHEMA = "trwm.context_refinement_transfer_certificate.v1"
CONTEXT_REFINEMENT_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows a rejected target branch can "
    "refine descriptor-based ancestor retrieval by adding an explicit required tag. It is not "
    "automatic feature discovery, statistical active learning, a CEGAR proof, robotics safety, "
    "chemistry, or materials-discovery evidence."
)
CONTEXT_REFINEMENT_SOURCES = (
    *CONTEXT_SELECTION_SOURCES,
    "https://doi.org/10.1007/10722167_15",
    "https://minds.wisconsin.edu/handle/1793/60660",
)


@dataclass(frozen=True)
class ContextRefinementDomainReport:
    domain: str
    target_context: str
    candidate_contexts: tuple[str, ...]
    coarse_selected_contexts: tuple[str, ...]
    refined_selected_contexts: tuple[str, ...]
    newly_rejected_contexts: tuple[str, ...]
    coarse_top_action: str
    refined_top_action: str
    committed_target_action: str
    coarse_budget_committed: bool
    refined_budget_committed: bool
    coarse_counterexample_receipt_hash: str
    coarse_counterexample_residual_kind: str
    refinement_certificate_hash: str
    base_selection_certificate_hash: str
    refined_selection_certificate_hash: str
    source_receipt_hashes: tuple[str, ...]
    refined_target_receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]


@dataclass(frozen=True)
class ContextRefinementTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[ContextRefinementDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    coarse_selected_context_count: int
    refined_selected_context_count: int
    newly_rejected_context_count: int
    coarse_budget_success_count: int
    refined_budget_success_count: int
    refinement_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    all_context_selection_certificates_valid: bool
    all_context_refinement_certificates_valid: bool
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
class ContextRefinementTransferCertificate:
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
    base_selection_certificate_hashes: tuple[str, ...]
    refined_selection_certificate_hashes: tuple[str, ...]
    context_refinement_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    coarse_budget_success_count: int
    refined_budget_success_count: int
    newly_rejected_context_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_REFINEMENT_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid context refinement transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "base_selection_certificate_hashes",
            "refined_selection_certificate_hashes",
            "context_refinement_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", context_refinement_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedContextRefinementTransferResult(CertifiedExampleResult):
    report: ContextRefinementTransferReport
    context_refinement_transfer_certificate: ContextRefinementTransferCertificate
    context_refinement_certificates: tuple[AncestralContextRefinementCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_context_refinement_transfer_experiment() -> ContextRefinementTransferReport:
    return run_context_refinement_transfer_certified_experiment().report


def run_context_refinement_transfer_certified_experiment() -> CertifiedContextRefinementTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[ContextRefinementDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    base_selection_certificates = []
    refined_selection_certificates = []
    refinement_certificates = []

    for spec in DOMAIN_SPECS:
        target_descriptor = _descriptor(spec, f"{spec.domain_id}:target", regime="target-compatible")
        compatible_descriptor = _descriptor(spec, f"{spec.domain_id}:ancestor_a", regime="target-compatible")
        misleading_descriptors = (
            _descriptor(spec, f"{spec.domain_id}:misleading_a", regime="source-only"),
            _descriptor(spec, f"{spec.domain_id}:misleading_b", regime="source-only"),
        )
        candidate_descriptors = (compatible_descriptor, *misleading_descriptors)
        base_selection = build_ancestral_context_selection_certificate(
            target_descriptor,
            candidate_descriptors,
            required_tag_keys=(),
        )
        base_selection_certificates.append(base_selection)

        source_receipts: list[Receipt] = []
        branch_certificate_hashes: list[str] = []
        for episode, descriptor in enumerate(candidate_descriptors):
            if descriptor.context_id in {row.context_id for row in misleading_descriptors}:
                actions = tuple(_make_misleading_source_action(spec, action, descriptor.context_id) for action in spec.actions)
            else:
                actions = tuple(_with_context(action, descriptor.context_id) for action in spec.actions)
            outcome = runtime.step(
                state,
                _make_traces(spec, context=descriptor.context_id, phase="refinement-source", episode=episode, actions=actions),
            )
            state = normalize_state(outcome.state)
            branch_certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), branch_certificate))
            branch_certificate_hashes.append(branch_certificate.certificate_hash)
            source_receipts.extend(outcome.receipts)
            memory.update_branch(outcome.receipts, branch_certificate)

        target_actions = tuple(_with_context(action, target_descriptor.context_id) for action in spec.actions)
        action_tokens = tuple(str(action["action"]) for action in target_actions)
        coarse_order = tuple(str(action) for action in memory.rank_from_contexts(base_selection.selected_context_ids, action_tokens))
        coarse_action = _action_by_name(target_actions, coarse_order[0])
        coarse_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=target_descriptor.context_id,
                phase="target-coarse-budget-one",
                episode=0,
                actions=(coarse_action,),
            ),
        )
        coarse_branch_certificate = build_branch_selection_certificate(
            coarse_outcome.receipts,
            verifier_call_count=coarse_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(coarse_outcome.receipts), coarse_branch_certificate))
        branch_certificate_hashes.append(coarse_branch_certificate.certificate_hash)

        refined_selection = build_ancestral_context_selection_certificate(
            target_descriptor,
            candidate_descriptors,
            required_tag_keys=("regime",),
        )
        refined_selection_certificates.append(refined_selection)
        refinement_certificate = build_ancestral_context_refinement_certificate(
            target=target_descriptor,
            candidates=candidate_descriptors,
            base_selection=base_selection,
            refined_selection=refined_selection,
            counterexample_receipt=coarse_outcome.receipts[0],
            added_required_tag_keys=("regime",),
            refinement_reason="target_reject_from_coarse_ancestor_selection",
        )
        refinement_certificates.append(refinement_certificate)

        refined_order = tuple(str(action) for action in memory.rank_from_contexts(refined_selection.selected_context_ids, action_tokens))
        refined_action = _action_by_name(target_actions, refined_order[0])
        refined_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=target_descriptor.context_id,
                phase="target-refined-budget-one",
                episode=0,
                actions=(refined_action,),
            ),
        )
        state = normalize_state(refined_outcome.state)
        refined_branch_certificate = build_branch_selection_certificate(
            refined_outcome.receipts,
            verifier_call_count=refined_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(refined_outcome.receipts), refined_branch_certificate))
        branch_certificate_hashes.append(refined_branch_certificate.certificate_hash)

        residual = coarse_outcome.receipts[0].hard_result.residual
        residual_kind = str(residual.get("kind", "")) if isinstance(residual, Mapping) else ""
        rows.append(
            ContextRefinementDomainReport(
                domain=spec.domain_id,
                target_context=target_descriptor.context_id,
                candidate_contexts=base_selection.candidate_context_ids,
                coarse_selected_contexts=base_selection.selected_context_ids,
                refined_selected_contexts=refined_selection.selected_context_ids,
                newly_rejected_contexts=refinement_certificate.newly_rejected_context_ids,
                coarse_top_action=coarse_order[0],
                refined_top_action=refined_order[0],
                committed_target_action=spec.committed_action,
                coarse_budget_committed=coarse_outcome.committed,
                refined_budget_committed=refined_outcome.committed,
                coarse_counterexample_receipt_hash=coarse_outcome.receipts[0].receipt_hash,
                coarse_counterexample_residual_kind=residual_kind,
                refinement_certificate_hash=refinement_certificate.certificate_hash,
                base_selection_certificate_hash=base_selection.certificate_hash,
                refined_selection_certificate_hash=refined_selection.certificate_hash,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_receipts),
                refined_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in refined_outcome.receipts),
                branch_selection_certificate_hashes=tuple(branch_certificate_hashes),
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
        for certificate in (*base_selection_certificates, *refined_selection_certificates)
    )
    all_context_refinement_certificates_valid = all(
        validate_ancestral_context_refinement_certificate(certificate)
        for certificate in refinement_certificates
    )
    report = ContextRefinementTransferReport(
        schema_version="trwm.example.context_refinement_transfer.v1",
        experiment_id="context_refinement_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        coarse_selected_context_count=sum(len(row.coarse_selected_contexts) for row in rows),
        refined_selected_context_count=sum(len(row.refined_selected_contexts) for row in rows),
        newly_rejected_context_count=sum(len(row.newly_rejected_contexts) for row in rows),
        coarse_budget_success_count=sum(1 for row in rows if row.coarse_budget_committed),
        refined_budget_success_count=sum(1 for row in rows if row.refined_budget_committed),
        refinement_certificate_count=len(refinement_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        all_context_selection_certificates_valid=all_context_selection_certificates_valid,
        all_context_refinement_certificates_valid=all_context_refinement_certificates_valid,
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
        sources=CONTEXT_REFINEMENT_SOURCES,
        learning=(
            "A rejected target branch can refine ancestor retrieval itself: coarse selection admits "
            "misleading contexts, the hard verifier emits a counterexample receipt, and adding the "
            "regime tag yields a narrower selected ancestor set that commits under the same budget."
        ),
    )
    transfer_certificate = build_context_refinement_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        base_selection_certificate_hashes=tuple(certificate.certificate_hash for certificate in base_selection_certificates),
        refined_selection_certificate_hashes=tuple(certificate.certificate_hash for certificate in refined_selection_certificates),
        context_refinement_certificate_hashes=tuple(certificate.certificate_hash for certificate in refinement_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="context_refinement_branch_transfer",
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
        claim_boundary=CONTEXT_REFINEMENT_CLAIM_BOUNDARY,
        sources=CONTEXT_REFINEMENT_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedContextRefinementTransferResult(
        report=report,
        context_refinement_transfer_certificate=transfer_certificate,
        context_refinement_certificates=tuple(refinement_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_context_refinement_transfer_certificate(
    report: ContextRefinementTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    base_selection_certificate_hashes: tuple[str, ...],
    refined_selection_certificate_hashes: tuple[str, ...],
    context_refinement_certificate_hashes: tuple[str, ...],
) -> ContextRefinementTransferCertificate:
    return ContextRefinementTransferCertificate(
        schema_version=CONTEXT_REFINEMENT_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        base_selection_certificate_hashes=base_selection_certificate_hashes,
        refined_selection_certificate_hashes=refined_selection_certificate_hashes,
        context_refinement_certificate_hashes=context_refinement_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        coarse_budget_success_count=report.coarse_budget_success_count,
        refined_budget_success_count=report.refined_budget_success_count,
        newly_rejected_context_count=report.newly_rejected_context_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=CONTEXT_REFINEMENT_CLAIM_BOUNDARY,
    )


def validate_context_refinement_transfer_certificate(
    certificate: ContextRefinementTransferCertificate,
    report: ContextRefinementTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != CONTEXT_REFINEMENT_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.base_selection_certificate_hashes,
            certificate.refined_selection_certificate_hashes,
            certificate.context_refinement_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if certificate.coarse_budget_success_count != 0:
            return False
        if certificate.refined_budget_success_count != certificate.domain_count:
            return False
        if certificate.newly_rejected_context_count != certificate.domain_count * 2:
            return False
        if len(certificate.context_refinement_certificate_hashes) != certificate.domain_count:
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
            if not report.all_context_refinement_certificates_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
        return certificate.certificate_hash == context_refinement_transfer_certificate_hash(certificate)
    except Exception:
        return False


def context_refinement_transfer_certificate_hash(
    certificate: ContextRefinementTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, ContextRefinementTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedContextRefinementTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: ContextRefinementTransferReport,
    transfer_certificate: ContextRefinementTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="context_refinement_transfer_g1",
        claim_text=(
            "Rejected target branches can refine ancestor retrieval by adding descriptor tags, improving "
            "later target exploration while hard verification keeps commit authority."
        ),
        evidence_grade="G1",
        scope="context_refinement_transfer",
        requirements=(
            requirement(
                "context_refinement_transfer_certificate_valid",
                validate_context_refinement_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_context_refinement_certificates_valid", report.all_context_refinement_certificates_valid),
            requirement("all_context_selection_certificates_valid", report.all_context_selection_certificates_valid),
            requirement("memory_snapshot_valid", report.memory_snapshot_valid),
            requirement("coarse_budget_fails_all_domains", report.coarse_budget_success_count == 0),
            requirement("refined_budget_succeeds_all_domains", report.refined_budget_success_count == report.domain_count),
            requirement("newly_rejected_contexts_present", report.newly_rejected_context_count == report.domain_count * 2),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "coarse_selected_context_count": report.coarse_selected_context_count,
            "refined_selected_context_count": report.refined_selected_context_count,
            "newly_rejected_context_count": report.newly_rejected_context_count,
            "coarse_budget_success_count": report.coarse_budget_success_count,
            "refined_budget_success_count": report.refined_budget_success_count,
        },
        boundary=CONTEXT_REFINEMENT_CLAIM_BOUNDARY,
        sources=CONTEXT_REFINEMENT_SOURCES,
    )


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def main() -> None:
    print(json.dumps(result_as_dict(run_context_refinement_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
