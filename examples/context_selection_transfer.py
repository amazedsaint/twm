from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Iterable, Mapping

from examples.ancestral_branch_exploration import (
    ANCESTRAL_BRANCH_SOURCES,
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
from trwm.ancestral import (
    AncestralBranchMemory,
    AncestralContextDescriptor,
    AncestralContextSelectionCertificate,
    build_ancestral_context_selection_certificate,
    validate_ancestral_branch_memory_snapshot,
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


CONTEXT_SELECTION_TRANSFER_CERTIFICATE_SCHEMA = "trwm.context_selection_transfer_certificate.v1"
CONTEXT_SELECTION_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example certifies descriptor-based ancestor "
    "selection before branch-history reuse, not a learned similarity metric, statistical transfer "
    "guarantee, robotics safety result, chemistry result, or materials-discovery result."
)
CONTEXT_SELECTION_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://dblp.org/rec/journals/aicom/AamodtP94",
    "https://arxiv.org/abs/2009.00909",
)


@dataclass(frozen=True)
class ContextSelectionDomainReport:
    domain: str
    target_context: str
    candidate_contexts: tuple[str, ...]
    selected_contexts: tuple[str, ...]
    rejected_contexts: tuple[str, ...]
    selected_top_action: str
    committed_target_action: str
    static_budget_committed: bool
    selected_budget_committed: bool
    bypass_rejected_context_committed: bool
    bypass_rejected_context_blocked: bool
    selection_certificate_hash: str
    source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    selected_target_receipt_hashes: tuple[str, ...]
    bypass_target_receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]
    rejected_reasons: Mapping[str, str]


@dataclass(frozen=True)
class ContextSelectionTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[ContextSelectionDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    selected_context_count: int
    rejected_context_count: int
    static_budget_success_count: int
    selected_budget_success_count: int
    bypass_rejected_context_blocked_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    all_context_selection_certificates_valid: bool
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
class ContextSelectionTransferCertificate:
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
    memory_snapshot_hash: str
    selected_context_count: int
    rejected_context_count: int
    static_budget_success_count: int
    selected_budget_success_count: int
    bypass_rejected_context_blocked_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_SELECTION_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid context selection transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "context_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", context_selection_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedContextSelectionTransferResult(CertifiedExampleResult):
    report: ContextSelectionTransferReport
    context_selection_transfer_certificate: ContextSelectionTransferCertificate
    context_selection_certificates: tuple[AncestralContextSelectionCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_context_selection_transfer_experiment() -> ContextSelectionTransferReport:
    return run_context_selection_transfer_certified_experiment().report


def run_context_selection_transfer_certified_experiment() -> CertifiedContextSelectionTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[ContextSelectionDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    context_selection_certificates: list[AncestralContextSelectionCertificate] = []

    for spec in DOMAIN_SPECS:
        target_descriptor = _descriptor(spec, f"{spec.domain_id}:target", regime="target-compatible")
        compatible_descriptors = (
            _descriptor(spec, f"{spec.domain_id}:ancestor_a", regime="target-compatible"),
            _descriptor(spec, f"{spec.domain_id}:ancestor_b", regime="target-compatible"),
        )
        misleading_descriptor = _descriptor(spec, f"{spec.domain_id}:misleading_ancestor", regime="source-only")
        candidate_descriptors = (*compatible_descriptors, misleading_descriptor)
        selection_certificate = build_ancestral_context_selection_certificate(
            target_descriptor,
            candidate_descriptors,
            required_tag_keys=("regime",),
        )
        context_selection_certificates.append(selection_certificate)

        source_receipts: list[Receipt] = []
        branch_cert_hashes: list[str] = []
        for episode, descriptor in enumerate(candidate_descriptors):
            if descriptor.context_id == misleading_descriptor.context_id:
                actions = tuple(_make_misleading_source_action(spec, action, descriptor.context_id) for action in spec.actions)
            else:
                actions = tuple(_with_context(action, descriptor.context_id) for action in spec.actions)
            outcome = runtime.step(
                state,
                _make_traces(spec, context=descriptor.context_id, phase="source", episode=episode, actions=actions),
            )
            state = normalize_state(outcome.state)
            branch_certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), branch_certificate))
            branch_cert_hashes.append(branch_certificate.certificate_hash)
            source_receipts.extend(outcome.receipts)
            memory.update_branch(outcome.receipts, branch_certificate)

        target_actions = tuple(_with_context(action, target_descriptor.context_id) for action in spec.actions)
        action_tokens = tuple(str(action["action"]) for action in target_actions)

        static_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=target_descriptor.context_id,
                phase="target-static-budget-one",
                episode=0,
                actions=(target_actions[0],),
            ),
        )
        static_branch_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_branch_certificate))
        branch_cert_hashes.append(static_branch_certificate.certificate_hash)

        selected_order = tuple(str(action) for action in memory.rank_from_contexts(selection_certificate.selected_context_ids, action_tokens))
        selected_action = _action_by_name(target_actions, selected_order[0])
        selected_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=target_descriptor.context_id,
                phase="target-selected-budget-one",
                episode=0,
                actions=(selected_action,),
            ),
        )
        state = normalize_state(selected_outcome.state)
        selected_branch_certificate = build_branch_selection_certificate(
            selected_outcome.receipts,
            verifier_call_count=selected_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(selected_outcome.receipts), selected_branch_certificate))
        branch_cert_hashes.append(selected_branch_certificate.certificate_hash)

        bypass_order = tuple(str(action) for action in memory.rank_from_contexts(selection_certificate.rejected_context_ids, action_tokens))
        bypass_action = _action_by_name(target_actions, bypass_order[0])
        bypass_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=target_descriptor.context_id,
                phase="target-rejected-context-bypass",
                episode=0,
                actions=(bypass_action,),
            ),
        )
        bypass_branch_certificate = build_branch_selection_certificate(
            bypass_outcome.receipts,
            verifier_call_count=bypass_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(bypass_outcome.receipts), bypass_branch_certificate))
        branch_cert_hashes.append(bypass_branch_certificate.certificate_hash)

        rows.append(
            ContextSelectionDomainReport(
                domain=spec.domain_id,
                target_context=target_descriptor.context_id,
                candidate_contexts=selection_certificate.candidate_context_ids,
                selected_contexts=selection_certificate.selected_context_ids,
                rejected_contexts=selection_certificate.rejected_context_ids,
                selected_top_action=selected_order[0],
                committed_target_action=spec.committed_action,
                static_budget_committed=static_outcome.committed,
                selected_budget_committed=selected_outcome.committed,
                bypass_rejected_context_committed=bypass_outcome.committed,
                bypass_rejected_context_blocked=not bypass_outcome.committed,
                selection_certificate_hash=selection_certificate.certificate_hash,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_receipts),
                static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
                selected_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in selected_outcome.receipts),
                bypass_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in bypass_outcome.receipts),
                branch_selection_certificate_hashes=tuple(branch_cert_hashes),
                rejected_reasons=selection_certificate.rejected_reasons,
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
        for certificate in context_selection_certificates
    )
    report = ContextSelectionTransferReport(
        schema_version="trwm.example.context_selection_transfer.v1",
        experiment_id="context_selection_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        selected_context_count=sum(len(row.selected_contexts) for row in rows),
        rejected_context_count=sum(len(row.rejected_contexts) for row in rows),
        static_budget_success_count=sum(1 for row in rows if row.static_budget_committed),
        selected_budget_success_count=sum(1 for row in rows if row.selected_budget_committed),
        bypass_rejected_context_blocked_count=sum(1 for row in rows if row.bypass_rejected_context_blocked),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        all_context_selection_certificates_valid=all_context_selection_certificates_valid,
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
        sources=CONTEXT_SELECTION_SOURCES,
        learning=(
            "Finding useful branches of the past requires a certified context-selection layer. "
            "Descriptor-compatible ancestors improve target budgeted exploration, while rejected "
            "contexts remain auditable non-authoritative proposal evidence."
        ),
    )
    context_selection_transfer_certificate = build_context_selection_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        context_selection_certificate_hashes=tuple(certificate.certificate_hash for certificate in context_selection_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="context_selection_branch_transfer",
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
        claim_boundary=CONTEXT_SELECTION_CLAIM_BOUNDARY,
        sources=CONTEXT_SELECTION_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, context_selection_transfer_certificate, evidence_certificate)
    return CertifiedContextSelectionTransferResult(
        report=report,
        context_selection_transfer_certificate=context_selection_transfer_certificate,
        context_selection_certificates=tuple(context_selection_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_context_selection_transfer_certificate(
    report: ContextSelectionTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    context_selection_certificate_hashes: tuple[str, ...],
) -> ContextSelectionTransferCertificate:
    return ContextSelectionTransferCertificate(
        schema_version=CONTEXT_SELECTION_TRANSFER_CERTIFICATE_SCHEMA,
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
        memory_snapshot_hash=report.memory_snapshot_hash,
        selected_context_count=report.selected_context_count,
        rejected_context_count=report.rejected_context_count,
        static_budget_success_count=report.static_budget_success_count,
        selected_budget_success_count=report.selected_budget_success_count,
        bypass_rejected_context_blocked_count=report.bypass_rejected_context_blocked_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=CONTEXT_SELECTION_CLAIM_BOUNDARY,
    )


def validate_context_selection_transfer_certificate(
    certificate: ContextSelectionTransferCertificate,
    report: ContextSelectionTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != CONTEXT_SELECTION_TRANSFER_CERTIFICATE_SCHEMA:
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
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if certificate.static_budget_success_count != 0:
            return False
        if certificate.selected_budget_success_count != certificate.domain_count:
            return False
        if certificate.bypass_rejected_context_blocked_count != certificate.domain_count:
            return False
        if certificate.selected_context_count != certificate.domain_count * 2:
            return False
        if certificate.rejected_context_count != certificate.domain_count:
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
            if example_report_hash(report) != certificate.report_hash:
                return False
        return certificate.certificate_hash == context_selection_transfer_certificate_hash(certificate)
    except Exception:
        return False


def context_selection_transfer_certificate_hash(
    certificate: ContextSelectionTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, ContextSelectionTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedContextSelectionTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: ContextSelectionTransferReport,
    transfer_certificate: ContextSelectionTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="context_selection_transfer_g1",
        claim_text=(
            "Certified context selection can admit compatible ancestor branch histories that improve "
            "target exploration while excluding misleading ancestor contexts before reuse."
        ),
        evidence_grade="G1",
        scope="context_selection_transfer",
        requirements=(
            requirement(
                "context_selection_transfer_certificate_valid",
                validate_context_selection_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_context_selection_certificates_valid", report.all_context_selection_certificates_valid),
            requirement("memory_snapshot_valid", report.memory_snapshot_valid),
            requirement("static_budget_fails_all_domains", report.static_budget_success_count == 0),
            requirement("selected_budget_succeeds_all_domains", report.selected_budget_success_count == report.domain_count),
            requirement(
                "bypass_rejected_context_blocked_all_domains",
                report.bypass_rejected_context_blocked_count == report.domain_count,
            ),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "selected_context_count": report.selected_context_count,
            "rejected_context_count": report.rejected_context_count,
            "static_budget_success_count": report.static_budget_success_count,
            "selected_budget_success_count": report.selected_budget_success_count,
            "bypass_rejected_context_blocked_count": report.bypass_rejected_context_blocked_count,
        },
        boundary=CONTEXT_SELECTION_CLAIM_BOUNDARY,
        sources=CONTEXT_SELECTION_SOURCES,
    )


def _descriptor(spec: ExplorationDomainSpec, context_id: str, *, regime: str) -> AncestralContextDescriptor:
    if spec.domain_id == "robotics_replan":
        hard_gate_keys = ("clearance", "turn_rate")
        family = "trajectory"
    elif spec.domain_id == "molecule_repair":
        hard_gate_keys = ("strain", "valence_ok")
        family = "molecule_edit"
    elif spec.domain_id == "material_process":
        hard_gate_keys = ("phase_purity", "thermal_gradient")
        family = "process_window"
    else:
        raise ValueError(f"unknown domain: {spec.domain_id}")
    return AncestralContextDescriptor(
        context_id=context_id,
        domain=spec.domain_id,
        family=family,
        hard_gate_keys=hard_gate_keys,
        residual_kinds=(spec.residual_kind,),
        tags={"regime": regime},
    )


def _make_traces(
    spec: ExplorationDomainSpec,
    *,
    context: str,
    phase: str,
    episode: int,
    actions: Iterable[Mapping[str, Any]],
) -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"{context}:{phase}:{episode}:{action['action']}",
            actions=(dict(action),),
            seeds=("context-selection-transfer", spec.domain_id, context, phase, episode, action["action"]),
            model_version="context.selection.transfer.v1",
        )
        for action in actions
    )


def _with_context(action: Mapping[str, Any], context: str) -> dict[str, Any]:
    return {**dict(action), "context": context}


def _action_by_name(actions: Iterable[Mapping[str, Any]], action_name: str) -> Mapping[str, Any]:
    for action in actions:
        if str(action["action"]) == action_name:
            return action
    raise ValueError(f"unknown action {action_name!r}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def main() -> None:
    print(json.dumps(result_as_dict(run_context_selection_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
