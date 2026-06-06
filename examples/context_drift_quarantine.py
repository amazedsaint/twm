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
from examples.context_selection_transfer import CONTEXT_SELECTION_SOURCES, _action_by_name, _descriptor, _make_traces, _with_context
from trwm.ancestral import (
    AncestralBranchMemory,
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
from trwm.core import Ledger, Receipt, TransactionEngine, stable_hash


CONTEXT_DRIFT_QUARANTINE_CERTIFICATE_SCHEMA = "trwm.context_drift_quarantine_certificate.v1"
CONTEXT_DRIFT_TRANSFER_CERTIFICATE_SCHEMA = "trwm.context_drift_quarantine_transfer_certificate.v1"
CONTEXT_DRIFT_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows stale committed branch evidence can "
    "be quarantined by explicit context-version tags before reuse. It is not statistical concept-drift "
    "detection, online learning, robotics safety, chemistry, materials-discovery, or scientific-autonomy "
    "evidence."
)
CONTEXT_DRIFT_SOURCES = CONTEXT_SELECTION_SOURCES


@dataclass(frozen=True)
class ContextDriftQuarantineCertificate:
    schema_version: str
    domain: str
    target_context: str
    stale_context_ids: tuple[str, ...]
    current_context_ids: tuple[str, ...]
    coarse_selection_certificate_hash: str
    drift_selection_certificate_hash: str
    stale_top_action: str
    drift_top_action: str
    committed_target_action: str
    stale_source_committed_receipt_hashes: tuple[str, ...]
    current_source_committed_receipt_hashes: tuple[str, ...]
    stale_target_reject_receipt_hashes: tuple[str, ...]
    drift_target_commit_receipt_hashes: tuple[str, ...]
    stale_verifier_call_count: int
    drift_verifier_call_count: int
    stale_committed: bool
    drift_committed: bool
    same_budget: bool
    quarantine_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_DRIFT_QUARANTINE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid context drift quarantine certificate schema: {self.schema_version}")
        for field_name in (
            "stale_context_ids",
            "current_context_ids",
            "stale_source_committed_receipt_hashes",
            "current_source_committed_receipt_hashes",
            "stale_target_reject_receipt_hashes",
            "drift_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", context_drift_quarantine_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class ContextDriftDomainReport:
    domain: str
    target_context: str
    stale_contexts: tuple[str, ...]
    current_contexts: tuple[str, ...]
    coarse_selected_contexts: tuple[str, ...]
    drift_selected_contexts: tuple[str, ...]
    quarantined_contexts: tuple[str, ...]
    stale_top_action: str
    drift_top_action: str
    committed_target_action: str
    stale_budget_committed: bool
    drift_budget_committed: bool
    stale_source_receipt_hashes: tuple[str, ...]
    current_source_receipt_hashes: tuple[str, ...]
    stale_target_receipt_hashes: tuple[str, ...]
    drift_target_receipt_hashes: tuple[str, ...]
    coarse_selection_certificate_hash: str
    drift_selection_certificate_hash: str
    drift_quarantine_certificate_hash: str
    branch_selection_certificate_hashes: tuple[str, ...]
    same_budget: bool


@dataclass(frozen=True)
class ContextDriftQuarantineReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[ContextDriftDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    stale_budget_success_count: int
    drift_budget_success_count: int
    quarantined_context_count: int
    drift_quarantine_certificate_count: int
    context_selection_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    all_context_selection_certificates_valid: bool
    all_context_drift_quarantine_certificates_valid: bool
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
class ContextDriftQuarantineTransferCertificate:
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
    context_drift_quarantine_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    stale_budget_success_count: int
    drift_budget_success_count: int
    quarantined_context_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CONTEXT_DRIFT_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid context drift transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "context_selection_certificate_hashes",
            "context_drift_quarantine_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", context_drift_quarantine_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedContextDriftQuarantineResult(CertifiedExampleResult):
    report: ContextDriftQuarantineReport
    context_drift_quarantine_transfer_certificate: ContextDriftQuarantineTransferCertificate
    context_selection_certificates: tuple[AncestralContextSelectionCertificate, ...]
    context_drift_quarantine_certificates: tuple[ContextDriftQuarantineCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_context_drift_quarantine_experiment() -> ContextDriftQuarantineReport:
    return run_context_drift_quarantine_certified_experiment().report


def run_context_drift_quarantine_certified_experiment() -> CertifiedContextDriftQuarantineResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[ContextDriftDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    selection_certificates: list[AncestralContextSelectionCertificate] = []
    drift_certificates: list[ContextDriftQuarantineCertificate] = []
    drift_audits: list[
        tuple[
            ContextDriftQuarantineCertificate,
            tuple[Receipt, ...],
            tuple[Receipt, ...],
            tuple[Receipt, ...],
            tuple[Receipt, ...],
            AncestralContextSelectionCertificate,
            AncestralContextSelectionCertificate,
        ]
    ] = []

    for spec in DOMAIN_SPECS:
        target = _versioned_descriptor(spec, f"{spec.domain_id}:drift_target", epoch="current")
        stale = _versioned_descriptor(spec, f"{spec.domain_id}:stale_ancestor", epoch="old")
        current = _versioned_descriptor(spec, f"{spec.domain_id}:current_ancestor", epoch="current")
        candidates = (stale, current)
        coarse_selection = build_ancestral_context_selection_certificate(target, candidates, required_tag_keys=("regime",))
        drift_selection = build_ancestral_context_selection_certificate(target, candidates, required_tag_keys=("regime", "epoch"))
        selection_certificates.extend((coarse_selection, drift_selection))

        stale_actions = tuple(_make_misleading_source_action(spec, action, stale.context_id) for action in spec.actions)
        stale_source = runtime.step(
            state,
            _make_traces(spec, context=stale.context_id, phase="stale-source", episode=0, actions=stale_actions),
        )
        state = normalize_state(stale_source.state)
        stale_source_certificate = build_branch_selection_certificate(stale_source.receipts, verifier_call_count=stale_source.verifier_calls)
        branch_certificate_pairs.append((tuple(stale_source.receipts), stale_source_certificate))
        memory.update_branch(stale_source.receipts, stale_source_certificate)

        target_actions = tuple(_with_context(action, target.context_id) for action in spec.actions)
        action_tokens = tuple(str(action["action"]) for action in target_actions)
        stale_order = tuple(str(action) for action in memory.rank_from_contexts(coarse_selection.selected_context_ids, action_tokens))
        stale_target = runtime.step(
            state,
            _make_traces(
                spec,
                context=target.context_id,
                phase="stale-drift-budget-one",
                episode=0,
                actions=(_action_by_name(target_actions, stale_order[0]),),
            ),
        )
        stale_target_certificate = build_branch_selection_certificate(stale_target.receipts, verifier_call_count=stale_target.verifier_calls)
        branch_certificate_pairs.append((tuple(stale_target.receipts), stale_target_certificate))

        current_actions = tuple(_with_context(action, current.context_id) for action in spec.actions)
        current_source = runtime.step(
            state,
            _make_traces(spec, context=current.context_id, phase="current-source", episode=0, actions=current_actions),
        )
        state = normalize_state(current_source.state)
        current_source_certificate = build_branch_selection_certificate(current_source.receipts, verifier_call_count=current_source.verifier_calls)
        branch_certificate_pairs.append((tuple(current_source.receipts), current_source_certificate))
        memory.update_branch(current_source.receipts, current_source_certificate)

        drift_order = tuple(str(action) for action in memory.rank_from_contexts(drift_selection.selected_context_ids, action_tokens))
        drift_target = runtime.step(
            state,
            _make_traces(
                spec,
                context=target.context_id,
                phase="drift-quarantine-budget-one",
                episode=0,
                actions=(_action_by_name(target_actions, drift_order[0]),),
            ),
        )
        state = normalize_state(drift_target.state)
        drift_target_certificate = build_branch_selection_certificate(drift_target.receipts, verifier_call_count=drift_target.verifier_calls)
        branch_certificate_pairs.append((tuple(drift_target.receipts), drift_target_certificate))

        drift_certificate = build_context_drift_quarantine_certificate(
            domain=spec.domain_id,
            target_context=target.context_id,
            coarse_selection=coarse_selection,
            drift_selection=drift_selection,
            stale_top_action=stale_order[0],
            drift_top_action=drift_order[0],
            committed_target_action=spec.committed_action,
            stale_source_receipts=tuple(stale_source.receipts),
            current_source_receipts=tuple(current_source.receipts),
            stale_target_outcome=stale_target,
            drift_target_outcome=drift_target,
        )
        drift_certificates.append(drift_certificate)
        drift_audits.append(
            (
                drift_certificate,
                tuple(stale_source.receipts),
                tuple(current_source.receipts),
                tuple(stale_target.receipts),
                tuple(drift_target.receipts),
                coarse_selection,
                drift_selection,
            )
        )
        rows.append(
            ContextDriftDomainReport(
                domain=spec.domain_id,
                target_context=target.context_id,
                stale_contexts=(stale.context_id,),
                current_contexts=(current.context_id,),
                coarse_selected_contexts=coarse_selection.selected_context_ids,
                drift_selected_contexts=drift_selection.selected_context_ids,
                quarantined_contexts=coarse_selection.selected_context_ids[:1],
                stale_top_action=stale_order[0],
                drift_top_action=drift_order[0],
                committed_target_action=spec.committed_action,
                stale_budget_committed=stale_target.committed,
                drift_budget_committed=drift_target.committed,
                stale_source_receipt_hashes=tuple(receipt.receipt_hash for receipt in stale_source.receipts),
                current_source_receipt_hashes=tuple(receipt.receipt_hash for receipt in current_source.receipts),
                stale_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in stale_target.receipts),
                drift_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in drift_target.receipts),
                coarse_selection_certificate_hash=coarse_selection.certificate_hash,
                drift_selection_certificate_hash=drift_selection.certificate_hash,
                drift_quarantine_certificate_hash=drift_certificate.certificate_hash,
                branch_selection_certificate_hashes=(
                    stale_source_certificate.certificate_hash,
                    current_source_certificate.certificate_hash,
                    stale_target_certificate.certificate_hash,
                    drift_target_certificate.certificate_hash,
                ),
                same_budget=drift_certificate.same_budget,
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
    all_context_selection_certificates_valid = all(validate_ancestral_context_selection_certificate(cert) for cert in selection_certificates)
    all_drift_certificates_valid = all(
        validate_context_drift_quarantine_certificate(
            certificate,
            stale_source_receipts=stale_source,
            current_source_receipts=current_source,
            stale_target_receipts=stale_target,
            drift_target_receipts=drift_target,
            coarse_selection=coarse_selection,
            drift_selection=drift_selection,
        )
        for certificate, stale_source, current_source, stale_target, drift_target, coarse_selection, drift_selection in drift_audits
    )
    all_branch_selection_certificates_valid = all(validate_branch_selection_certificate(certificate) for _, certificate in branch_certificate_pairs)
    all_branch_selection_audits_valid = all(audit_branch_selection(receipts, certificate) for receipts, certificate in branch_certificate_pairs)
    report = ContextDriftQuarantineReport(
        schema_version="trwm.example.context_drift_quarantine.v1",
        experiment_id="context_drift_quarantine",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        stale_budget_success_count=sum(1 for row in rows if row.stale_budget_committed),
        drift_budget_success_count=sum(1 for row in rows if row.drift_budget_committed),
        quarantined_context_count=sum(len(row.quarantined_contexts) for row in rows),
        drift_quarantine_certificate_count=len(drift_certificates),
        context_selection_certificate_count=len(selection_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        all_context_selection_certificates_valid=all_context_selection_certificates_valid,
        all_context_drift_quarantine_certificates_valid=all_drift_certificates_valid,
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
        sources=CONTEXT_DRIFT_SOURCES,
        learning=(
            "Committed past branch evidence needs validity scope. A stale context can rank an old action "
            "first and fail under the target verifier, while an epoch-aware selection certificate "
            "quarantines stale evidence and commits the current-compatible action at the same budget."
        ),
    )
    transfer_certificate = build_context_drift_quarantine_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        context_selection_certificate_hashes=tuple(certificate.certificate_hash for certificate in selection_certificates),
        context_drift_quarantine_certificate_hashes=tuple(certificate.certificate_hash for certificate in drift_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="context_drift_branch_transfer",
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
        claim_boundary=CONTEXT_DRIFT_CLAIM_BOUNDARY,
        sources=CONTEXT_DRIFT_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedContextDriftQuarantineResult(
        report=report,
        context_drift_quarantine_transfer_certificate=transfer_certificate,
        context_selection_certificates=tuple(selection_certificates),
        context_drift_quarantine_certificates=tuple(drift_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_context_drift_quarantine_certificate(
    *,
    domain: str,
    target_context: str,
    coarse_selection: AncestralContextSelectionCertificate,
    drift_selection: AncestralContextSelectionCertificate,
    stale_top_action: str,
    drift_top_action: str,
    committed_target_action: str,
    stale_source_receipts: tuple[Receipt, ...],
    current_source_receipts: tuple[Receipt, ...],
    stale_target_outcome: Any,
    drift_target_outcome: Any,
) -> ContextDriftQuarantineCertificate:
    return ContextDriftQuarantineCertificate(
        schema_version=CONTEXT_DRIFT_QUARANTINE_CERTIFICATE_SCHEMA,
        domain=domain,
        target_context=target_context,
        stale_context_ids=tuple(context for context in coarse_selection.selected_context_ids if context not in drift_selection.selected_context_ids),
        current_context_ids=drift_selection.selected_context_ids,
        coarse_selection_certificate_hash=coarse_selection.certificate_hash,
        drift_selection_certificate_hash=drift_selection.certificate_hash,
        stale_top_action=stale_top_action,
        drift_top_action=drift_top_action,
        committed_target_action=committed_target_action,
        stale_source_committed_receipt_hashes=tuple(
            receipt.receipt_hash for receipt in stale_source_receipts if receipt.committed and _receipt_action(receipt) == stale_top_action
        ),
        current_source_committed_receipt_hashes=tuple(
            receipt.receipt_hash for receipt in current_source_receipts if receipt.committed and _receipt_action(receipt) == drift_top_action
        ),
        stale_target_reject_receipt_hashes=tuple(receipt.receipt_hash for receipt in stale_target_outcome.receipts if receipt.hard_result.rejected),
        drift_target_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in drift_target_outcome.receipts if receipt.committed),
        stale_verifier_call_count=int(stale_target_outcome.verifier_calls),
        drift_verifier_call_count=int(drift_target_outcome.verifier_calls),
        stale_committed=bool(stale_target_outcome.committed),
        drift_committed=bool(drift_target_outcome.committed),
        same_budget=stale_target_outcome.verifier_calls == drift_target_outcome.verifier_calls,
        quarantine_reason="tag_mismatch:epoch",
    )


def validate_context_drift_quarantine_certificate(
    certificate: ContextDriftQuarantineCertificate,
    *,
    stale_source_receipts: tuple[Receipt, ...] | None = None,
    current_source_receipts: tuple[Receipt, ...] | None = None,
    stale_target_receipts: tuple[Receipt, ...] | None = None,
    drift_target_receipts: tuple[Receipt, ...] | None = None,
    coarse_selection: AncestralContextSelectionCertificate | None = None,
    drift_selection: AncestralContextSelectionCertificate | None = None,
) -> bool:
    try:
        if certificate.schema_version != CONTEXT_DRIFT_QUARANTINE_CERTIFICATE_SCHEMA:
            return False
        for value in (
            certificate.domain,
            certificate.target_context,
            certificate.stale_top_action,
            certificate.drift_top_action,
            certificate.committed_target_action,
            certificate.quarantine_reason,
        ):
            if not value:
                return False
        if not certificate.stale_context_ids or not certificate.current_context_ids:
            return False
        if certificate.stale_top_action == certificate.committed_target_action:
            return False
        if certificate.drift_top_action != certificate.committed_target_action:
            return False
        if certificate.stale_committed or not certificate.drift_committed:
            return False
        if certificate.stale_verifier_call_count != certificate.drift_verifier_call_count:
            return False
        if certificate.stale_verifier_call_count <= 0 or not certificate.same_budget:
            return False
        if certificate.quarantine_reason != "tag_mismatch:epoch":
            return False
        for value in (certificate.coarse_selection_certificate_hash, certificate.drift_selection_certificate_hash):
            if not _is_hash(value):
                return False
        for values in (
            certificate.stale_source_committed_receipt_hashes,
            certificate.current_source_committed_receipt_hashes,
            certificate.stale_target_reject_receipt_hashes,
            certificate.drift_target_commit_receipt_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if coarse_selection is not None:
            if coarse_selection.certificate_hash != certificate.coarse_selection_certificate_hash:
                return False
            if set(certificate.stale_context_ids).difference(coarse_selection.selected_context_ids):
                return False
            if not validate_ancestral_context_selection_certificate(coarse_selection):
                return False
        if drift_selection is not None:
            if drift_selection.certificate_hash != certificate.drift_selection_certificate_hash:
                return False
            if drift_selection.selected_context_ids != certificate.current_context_ids:
                return False
            if set(certificate.current_context_ids).intersection(certificate.stale_context_ids):
                return False
            if not validate_ancestral_context_selection_certificate(drift_selection):
                return False
        if stale_source_receipts is not None:
            stale_commits = tuple(
                receipt.receipt_hash for receipt in stale_source_receipts if receipt.committed and _receipt_action(receipt) == certificate.stale_top_action
            )
            if stale_commits != certificate.stale_source_committed_receipt_hashes:
                return False
            if any(not receipt.static_valid() for receipt in stale_source_receipts):
                return False
        if current_source_receipts is not None:
            current_commits = tuple(
                receipt.receipt_hash for receipt in current_source_receipts if receipt.committed and _receipt_action(receipt) == certificate.drift_top_action
            )
            if current_commits != certificate.current_source_committed_receipt_hashes:
                return False
            if any(not receipt.static_valid() for receipt in current_source_receipts):
                return False
        if stale_target_receipts is not None:
            stale_rejects = tuple(receipt.receipt_hash for receipt in stale_target_receipts if receipt.hard_result.rejected)
            if stale_rejects != certificate.stale_target_reject_receipt_hashes:
                return False
            if any(receipt.committed or not receipt.static_valid() for receipt in stale_target_receipts):
                return False
            if any(_receipt_action(receipt) != certificate.stale_top_action for receipt in stale_target_receipts):
                return False
        if drift_target_receipts is not None:
            drift_commits = tuple(receipt.receipt_hash for receipt in drift_target_receipts if receipt.committed)
            if drift_commits != certificate.drift_target_commit_receipt_hashes:
                return False
            if not drift_commits:
                return False
            if any(not receipt.static_valid() for receipt in drift_target_receipts):
                return False
            if any(_receipt_action(receipt) != certificate.drift_top_action for receipt in drift_target_receipts):
                return False
        return certificate.certificate_hash == context_drift_quarantine_certificate_hash(certificate)
    except Exception:
        return False


def build_context_drift_quarantine_transfer_certificate(
    report: ContextDriftQuarantineReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    context_selection_certificate_hashes: tuple[str, ...],
    context_drift_quarantine_certificate_hashes: tuple[str, ...],
) -> ContextDriftQuarantineTransferCertificate:
    return ContextDriftQuarantineTransferCertificate(
        schema_version=CONTEXT_DRIFT_TRANSFER_CERTIFICATE_SCHEMA,
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
        context_drift_quarantine_certificate_hashes=context_drift_quarantine_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        stale_budget_success_count=report.stale_budget_success_count,
        drift_budget_success_count=report.drift_budget_success_count,
        quarantined_context_count=report.quarantined_context_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=CONTEXT_DRIFT_CLAIM_BOUNDARY,
    )


def validate_context_drift_quarantine_transfer_certificate(
    certificate: ContextDriftQuarantineTransferCertificate,
    report: ContextDriftQuarantineReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != CONTEXT_DRIFT_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        for value in (certificate.report_hash, certificate.ledger_head, certificate.memory_snapshot_hash):
            if not _is_hash(value):
                return False
        for values in (
            certificate.receipt_hashes,
            certificate.branch_selection_certificate_hashes,
            certificate.context_selection_certificate_hashes,
            certificate.context_drift_quarantine_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if certificate.stale_budget_success_count != 0:
            return False
        if certificate.drift_budget_success_count != certificate.domain_count:
            return False
        if certificate.quarantined_context_count != certificate.domain_count:
            return False
        if len(certificate.context_drift_quarantine_certificate_hashes) != certificate.domain_count:
            return False
        if len(certificate.context_selection_certificate_hashes) != certificate.domain_count * 2:
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
            if not report.all_context_drift_quarantine_certificates_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
        return certificate.certificate_hash == context_drift_quarantine_transfer_certificate_hash(certificate)
    except Exception:
        return False


def context_drift_quarantine_certificate_hash(certificate: ContextDriftQuarantineCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, ContextDriftQuarantineCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def context_drift_quarantine_transfer_certificate_hash(
    certificate: ContextDriftQuarantineTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, ContextDriftQuarantineTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedContextDriftQuarantineResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: ContextDriftQuarantineReport,
    transfer_certificate: ContextDriftQuarantineTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="context_drift_quarantine_g1",
        claim_text=(
            "Stale committed branch evidence can be quarantined by context-version certificates, allowing "
            "current-compatible past branches to improve target exploration at the same verifier budget."
        ),
        evidence_grade="G1",
        scope="context_drift_quarantine",
        requirements=(
            requirement(
                "context_drift_transfer_certificate_valid",
                validate_context_drift_quarantine_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_context_selection_certificates_valid", report.all_context_selection_certificates_valid),
            requirement("all_context_drift_quarantine_certificates_valid", report.all_context_drift_quarantine_certificates_valid),
            requirement("memory_snapshot_valid", report.memory_snapshot_valid),
            requirement("stale_budget_fails_all_domains", report.stale_budget_success_count == 0),
            requirement("drift_budget_succeeds_all_domains", report.drift_budget_success_count == report.domain_count),
            requirement("quarantined_contexts_present", report.quarantined_context_count == report.domain_count),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "stale_budget_success_count": report.stale_budget_success_count,
            "drift_budget_success_count": report.drift_budget_success_count,
            "quarantined_context_count": report.quarantined_context_count,
            "drift_quarantine_certificate_count": report.drift_quarantine_certificate_count,
        },
        boundary=CONTEXT_DRIFT_CLAIM_BOUNDARY,
        sources=CONTEXT_DRIFT_SOURCES,
    )


def _versioned_descriptor(spec, context_id: str, *, epoch: str):
    descriptor = _descriptor(spec, context_id, regime="target-compatible")
    return type(descriptor)(
        context_id=descriptor.context_id,
        domain=descriptor.domain,
        family=descriptor.family,
        hard_gate_keys=descriptor.hard_gate_keys,
        residual_kinds=descriptor.residual_kinds,
        tags={**dict(descriptor.tags), "epoch": epoch},
    )


def _receipt_action(receipt: Receipt) -> str:
    payload = receipt.replay_bundle.get("candidate_payload") if isinstance(receipt.replay_bundle, Mapping) else None
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get("action", ""))


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def main() -> None:
    print(json.dumps(result_as_dict(run_context_drift_quarantine_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
