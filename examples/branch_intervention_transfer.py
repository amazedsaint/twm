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
    normalize_state,
)
from examples.common import (
    CertifiedExampleResult,
    ExampleEvidenceCertificate,
    build_example_evidence_certificate,
    example_report_hash,
    report_as_dict,
    validate_example_evidence_certificate,
)
from trwm.ancestral import AncestralBranchMemory, validate_ancestral_branch_memory_snapshot
from trwm.branch import (
    BranchRuntime,
    BranchSelectionCertificate,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


BRANCH_INTERVENTION_CERTIFICATE_SCHEMA = "trwm.branch_intervention_certificate.v1"
BRANCH_INTERVENTION_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_intervention_transfer_certificate.v1"
BRANCH_INTERVENTION_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC2836213/",
)
BRANCH_INTERVENTION_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows a source reject/commit pair can "
    "identify one verifier-field intervention for a matched target branch, but target commit authority "
    "remains fresh hard verification. It is not structural causal modeling, do-calculus, causal "
    "inference, automatic repair, robotics safety, chemistry, materials discovery, or scientific "
    "autonomy evidence."
)


@dataclass(frozen=True)
class BranchInterventionCertificate:
    schema_version: str
    domain: str
    intervention_rule_id: str
    intervention_rule_version: str
    source_context_id: str
    target_context_id: str
    intervention_key: str
    intervention_direction: str
    source_before_value: float
    source_after_value: float
    target_before_value: float
    target_after_value: float
    source_reject_action: str
    source_commit_action: str
    static_target_action: str
    intervention_target_action: str
    source_reject_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    intervention_target_receipt_hashes: tuple[str, ...]
    intervention_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    intervention_branch_selection_certificate_hash: str
    source_rejected: bool
    source_committed: bool
    static_committed: bool
    intervention_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    intervention_verifier_call_count: int
    same_budget: bool
    intervention_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_INTERVENTION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch intervention certificate schema: {self.schema_version}")
        for field_name in (
            "source_reject_receipt_hashes",
            "source_commit_receipt_hashes",
            "static_target_receipt_hashes",
            "intervention_target_receipt_hashes",
            "intervention_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "source_before_value",
            "source_after_value",
            "target_before_value",
            "target_after_value",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_intervention_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchInterventionDomainReport:
    domain: str
    source_context: str
    target_context: str
    intervention_key: str
    intervention_direction: str
    source_before_value: float
    source_after_value: float
    target_before_value: float
    target_after_value: float
    source_reject_action: str
    source_commit_action: str
    static_target_action: str
    intervention_target_action: str
    source_rejected: bool
    source_committed: bool
    static_committed: bool
    intervention_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    intervention_verifier_call_count: int
    source_reject_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    intervention_target_receipt_hashes: tuple[str, ...]
    branch_intervention_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchInterventionTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchInterventionDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_reject_count: int
    source_commit_count: int
    static_success_count: int
    intervention_success_count: int
    same_budget_intervention_count: int
    branch_intervention_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_intervention_certificates_valid: bool
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
class BranchInterventionTransferCertificate:
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
    branch_intervention_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_reject_count: int
    source_commit_count: int
    static_success_count: int
    intervention_success_count: int
    same_budget_intervention_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_INTERVENTION_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch intervention transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_intervention_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_intervention_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchInterventionTransferResult(CertifiedExampleResult):
    report: BranchInterventionTransferReport
    branch_intervention_transfer_certificate: BranchInterventionTransferCertificate
    branch_intervention_certificates: tuple[BranchInterventionCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_intervention_transfer_experiment() -> BranchInterventionTransferReport:
    return run_branch_intervention_transfer_certified_experiment().report


def run_branch_intervention_transfer_certified_experiment() -> CertifiedBranchInterventionTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchInterventionDomainReport] = []
    intervention_certificates: list[BranchInterventionCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:field_intervention"
        target_context = f"{spec.domain_id}:target:field_intervention"
        plan = _domain_intervention_plan(spec, source_context, target_context)

        source_outcome = runtime.step(
            state,
            _make_intervention_traces(
                spec,
                context=source_context,
                phase="source-reject-commit",
                actions=(plan["source_reject"], plan["source_commit"]),
            ),
        )
        state = normalize_state(source_outcome.state)
        source_certificate = build_branch_selection_certificate(
            source_outcome.receipts,
            verifier_call_count=source_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_outcome.receipts), source_certificate))
        memory.update_branch(source_outcome.receipts, source_certificate)

        static_outcome = runtime.step(
            state,
            _make_intervention_traces(
                spec,
                context=target_context,
                phase="target-static",
                actions=(plan["target_static"],),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        intervention_outcome = runtime.step(
            state,
            _make_intervention_traces(
                spec,
                context=target_context,
                phase="target-field-intervention",
                actions=(plan["target_intervention"],),
            ),
        )
        state = normalize_state(intervention_outcome.state)
        intervention_certificate = build_branch_selection_certificate(
            intervention_outcome.receipts,
            verifier_call_count=intervention_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(intervention_outcome.receipts), intervention_certificate))

        source_reject_hashes = tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected)
        source_commit_hashes = tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed)
        static_hashes = tuple(receipt.receipt_hash for receipt in static_outcome.receipts)
        intervention_hashes = tuple(receipt.receipt_hash for receipt in intervention_outcome.receipts)
        intervention_commit_hashes = tuple(receipt.receipt_hash for receipt in intervention_outcome.receipts if receipt.committed)

        certificate = build_branch_intervention_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            intervention_key=str(plan["intervention_key"]),
            intervention_direction=str(plan["intervention_direction"]),
            source_before_value=float(plan["source_reject"][plan["intervention_key"]]),
            source_after_value=float(plan["source_commit"][plan["intervention_key"]]),
            target_before_value=float(plan["target_static"][plan["intervention_key"]]),
            target_after_value=float(plan["target_intervention"][plan["intervention_key"]]),
            source_reject_action=str(plan["source_reject"]["action"]),
            source_commit_action=str(plan["source_commit"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            intervention_target_action=str(plan["target_intervention"]["action"]),
            source_reject_receipt_hashes=source_reject_hashes,
            source_commit_receipt_hashes=source_commit_hashes,
            static_target_receipt_hashes=static_hashes,
            intervention_target_receipt_hashes=intervention_hashes,
            intervention_target_commit_receipt_hashes=intervention_commit_hashes,
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            intervention_branch_selection_certificate_hash=intervention_certificate.certificate_hash,
            source_rejected=bool(source_reject_hashes),
            source_committed=source_outcome.committed,
            static_committed=static_outcome.committed,
            intervention_committed=intervention_outcome.committed,
            source_verifier_call_count=source_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            intervention_verifier_call_count=intervention_outcome.verifier_calls,
        )
        intervention_certificates.append(certificate)
        rows.append(
            BranchInterventionDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                intervention_key=certificate.intervention_key,
                intervention_direction=certificate.intervention_direction,
                source_before_value=certificate.source_before_value,
                source_after_value=certificate.source_after_value,
                target_before_value=certificate.target_before_value,
                target_after_value=certificate.target_after_value,
                source_reject_action=certificate.source_reject_action,
                source_commit_action=certificate.source_commit_action,
                static_target_action=certificate.static_target_action,
                intervention_target_action=certificate.intervention_target_action,
                source_rejected=certificate.source_rejected,
                source_committed=certificate.source_committed,
                static_committed=certificate.static_committed,
                intervention_committed=certificate.intervention_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                intervention_verifier_call_count=certificate.intervention_verifier_call_count,
                source_reject_receipt_hashes=certificate.source_reject_receipt_hashes,
                source_commit_receipt_hashes=certificate.source_commit_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                intervention_target_receipt_hashes=certificate.intervention_target_receipt_hashes,
                branch_intervention_certificate_hash=certificate.certificate_hash,
                same_budget=certificate.same_budget,
            )
        )

    memory_snapshot = memory.snapshot()
    all_receipts = tuple(engine.ledger.rows)
    all_branch_selection_certificates_valid = all(
        validate_branch_selection_certificate(certificate) for _, certificate in branch_certificate_pairs
    )
    all_branch_selection_audits_valid = all(
        audit_branch_selection(receipts, certificate) for receipts, certificate in branch_certificate_pairs
    )
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

    report = BranchInterventionTransferReport(
        schema_version="trwm.example.branch_intervention_transfer.v1",
        experiment_id="branch_intervention_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_reject_count=sum(1 for row in rows if row.source_rejected),
        source_commit_count=sum(1 for row in rows if row.source_committed),
        static_success_count=sum(1 for row in rows if row.static_committed),
        intervention_success_count=sum(1 for row in rows if row.intervention_committed),
        same_budget_intervention_count=sum(1 for row in rows if row.same_budget),
        branch_intervention_certificate_count=len(intervention_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_intervention_certificates_valid=all(
            validate_branch_intervention_certificate(certificate, row)
            for certificate, row in zip(intervention_certificates, rows)
        ),
        all_branch_selection_certificates_valid=all_branch_selection_certificates_valid,
        all_branch_selection_audits_valid=all_branch_selection_audits_valid,
        replay_audit_ok=replay_audit_ok,
        rollback_audit_ok=rollback_audit_ok,
        ledger_audit_ok=ledger_audit_ok,
        invalid_commit_count=engine.invalid_commit_count,
        verifier_id=engine.adapter.verifier_id,
        verifier_version=engine.adapter.verifier_version,
        ledger_head=engine.ledger.head,
        hard_gate_keys=(
            "clearance",
            "turn_rate",
            "valence_ok",
            "strain",
            "thermal_gradient",
            "phase_purity",
        ),
        residual_kinds=tuple(sorted({spec.residual_kind for spec in DOMAIN_SPECS})),
        sources=BRANCH_INTERVENTION_SOURCES,
        learning=(
            "A source reject/commit pair can identify a typed verifier field to edit before target "
            "exploration spends its single verifier call. The edit is only proposal evidence: the "
            "target branch still commits only after the target hard verifier accepts the intervened candidate."
        ),
    )
    transfer_certificate = build_branch_intervention_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_intervention_certificate_hashes=tuple(certificate.certificate_hash for certificate in intervention_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_intervention_transfer",
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
        claim_boundary=BRANCH_INTERVENTION_CLAIM_BOUNDARY,
        sources=BRANCH_INTERVENTION_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchInterventionTransferResult(
        report=report,
        branch_intervention_transfer_certificate=transfer_certificate,
        branch_intervention_certificates=tuple(intervention_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_intervention_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    intervention_key: str,
    intervention_direction: str,
    source_before_value: float,
    source_after_value: float,
    target_before_value: float,
    target_after_value: float,
    source_reject_action: str,
    source_commit_action: str,
    static_target_action: str,
    intervention_target_action: str,
    source_reject_receipt_hashes: tuple[str, ...],
    source_commit_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    intervention_target_receipt_hashes: tuple[str, ...],
    intervention_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    intervention_branch_selection_certificate_hash: str,
    source_rejected: bool,
    source_committed: bool,
    static_committed: bool,
    intervention_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    intervention_verifier_call_count: int,
) -> BranchInterventionCertificate:
    return BranchInterventionCertificate(
        schema_version=BRANCH_INTERVENTION_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        intervention_rule_id="source_reject_commit_field_intervention",
        intervention_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        intervention_key=intervention_key,
        intervention_direction=intervention_direction,
        source_before_value=source_before_value,
        source_after_value=source_after_value,
        target_before_value=target_before_value,
        target_after_value=target_after_value,
        source_reject_action=source_reject_action,
        source_commit_action=source_commit_action,
        static_target_action=static_target_action,
        intervention_target_action=intervention_target_action,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        intervention_target_receipt_hashes=intervention_target_receipt_hashes,
        intervention_target_commit_receipt_hashes=intervention_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        intervention_branch_selection_certificate_hash=intervention_branch_selection_certificate_hash,
        source_rejected=source_rejected,
        source_committed=source_committed,
        static_committed=static_committed,
        intervention_committed=intervention_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        intervention_verifier_call_count=intervention_verifier_call_count,
        same_budget=static_verifier_call_count == intervention_verifier_call_count == 1,
        intervention_reason="source_reject_commit_pair_identifies_target_field_intervention",
    )


def validate_branch_intervention_certificate(
    certificate: BranchInterventionCertificate,
    row: BranchInterventionDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_INTERVENTION_CERTIFICATE_SCHEMA:
            return False
        if certificate.intervention_rule_id != "source_reject_commit_field_intervention":
            return False
        if certificate.intervention_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.intervention_key,
            certificate.source_reject_action,
            certificate.source_commit_action,
            certificate.static_target_action,
            certificate.intervention_target_action,
        ):
            if not _nonempty(value):
                return False
        if certificate.intervention_direction not in {"increase", "decrease"}:
            return False
        source_delta = certificate.source_after_value - certificate.source_before_value
        target_delta = certificate.target_after_value - certificate.target_before_value
        if certificate.intervention_direction == "increase" and not (source_delta > 0 and target_delta > 0):
            return False
        if certificate.intervention_direction == "decrease" and not (source_delta < 0 and target_delta < 0):
            return False
        if not certificate.source_rejected or not certificate.source_committed:
            return False
        if certificate.static_committed or not certificate.intervention_committed:
            return False
        if certificate.source_verifier_call_count != 2:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.intervention_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.intervention_reason != "source_reject_commit_pair_identifies_target_field_intervention":
            return False
        for values in (
            certificate.source_reject_receipt_hashes,
            certificate.source_commit_receipt_hashes,
            certificate.static_target_receipt_hashes,
            certificate.intervention_target_receipt_hashes,
            certificate.intervention_target_commit_receipt_hashes,
        ):
            if len(values) != 1 or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.intervention_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.intervention_key != certificate.intervention_key:
                return False
            if row.intervention_direction != certificate.intervention_direction:
                return False
            if row.source_before_value != certificate.source_before_value:
                return False
            if row.source_after_value != certificate.source_after_value:
                return False
            if row.target_before_value != certificate.target_before_value:
                return False
            if row.target_after_value != certificate.target_after_value:
                return False
            if row.source_reject_action != certificate.source_reject_action:
                return False
            if row.source_commit_action != certificate.source_commit_action:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.intervention_target_action != certificate.intervention_target_action:
                return False
            if row.source_rejected != certificate.source_rejected:
                return False
            if row.source_committed != certificate.source_committed:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.intervention_committed != certificate.intervention_committed:
                return False
            if row.source_verifier_call_count != certificate.source_verifier_call_count:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.intervention_verifier_call_count != certificate.intervention_verifier_call_count:
                return False
            if row.source_reject_receipt_hashes != certificate.source_reject_receipt_hashes:
                return False
            if row.source_commit_receipt_hashes != certificate.source_commit_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.intervention_target_receipt_hashes != certificate.intervention_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_intervention_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_intervention_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_intervention_transfer_certificate(
    report: BranchInterventionTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_intervention_certificate_hashes: tuple[str, ...],
) -> BranchInterventionTransferCertificate:
    return BranchInterventionTransferCertificate(
        schema_version=BRANCH_INTERVENTION_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_intervention_certificate_hashes=branch_intervention_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_reject_count=report.source_reject_count,
        source_commit_count=report.source_commit_count,
        static_success_count=report.static_success_count,
        intervention_success_count=report.intervention_success_count,
        same_budget_intervention_count=report.same_budget_intervention_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_INTERVENTION_CLAIM_BOUNDARY,
    )


def validate_branch_intervention_transfer_certificate(
    certificate: BranchInterventionTransferCertificate,
    report: BranchInterventionTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_INTERVENTION_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_intervention_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_intervention_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_reject_count != certificate.domain_count:
            return False
        if certificate.source_commit_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.intervention_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_intervention_count != certificate.domain_count:
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
            if report.memory_snapshot_hash != certificate.memory_snapshot_hash or not report.memory_snapshot_valid:
                return False
            if not report.all_branch_intervention_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
        return certificate.certificate_hash == branch_intervention_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_intervention_certificate_hash(certificate: BranchInterventionCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchInterventionCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_intervention_transfer_certificate_hash(
    certificate: BranchInterventionTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchInterventionTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchInterventionTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchInterventionTransferReport,
    transfer_certificate: BranchInterventionTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_intervention_transfer_g1",
        claim_text=(
            "A source reject/commit branch pair can improve local target exploration by identifying a "
            "receipt-bound field intervention, while target commit authority remains with fresh hard verification."
        ),
        evidence_grade="G1",
        scope="branch_intervention_transfer",
        requirements=(
            requirement(
                "branch_intervention_transfer_certificate_valid",
                validate_branch_intervention_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_intervention_certificates_valid", report.all_branch_intervention_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_rejects_all_domains", report.source_reject_count == report.domain_count),
            requirement("source_commits_all_domains", report.source_commit_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("intervention_succeeds_all_domains", report.intervention_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_intervention_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 2),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_reject_count": report.source_reject_count,
            "source_commit_count": report.source_commit_count,
            "static_success_count": report.static_success_count,
            "intervention_success_count": report.intervention_success_count,
        },
        boundary=BRANCH_INTERVENTION_CLAIM_BOUNDARY,
        sources=BRANCH_INTERVENTION_SOURCES,
    )


def _make_intervention_traces(
    spec: ExplorationDomainSpec,
    *,
    context: str,
    phase: str,
    actions: Iterable[Mapping[str, Any]],
) -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"{context}:{phase}:{action['action']}",
            actions=({**dict(action), "context": context, "phase": phase},),
            seeds=("branch-intervention-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.intervention.transfer.v1",
        )
        for action in actions
    )


def _domain_intervention_plan(
    spec: ExplorationDomainSpec,
    source_context: str,
    target_context: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "intervention_key": "clearance",
            "intervention_direction": "increase",
            "source_reject": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "under_clearance_route",
                "utility": 9,
                "clearance": 0.10,
                "turn_rate": 0.42,
            },
            "source_commit": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "clearance_intervention_route",
                "utility": 8,
                "clearance": 0.34,
                "turn_rate": 0.42,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "target_under_clearance_route",
                "utility": 9,
                "clearance": 0.16,
                "turn_rate": 0.44,
            },
            "target_intervention": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "target_clearance_intervention_route",
                "utility": 8,
                "clearance": 0.34,
                "turn_rate": 0.44,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "intervention_key": "strain",
            "intervention_direction": "decrease",
            "source_reject": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "overstrained_patch",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.48,
            },
            "source_commit": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "strain_intervention_patch",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.20,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "target_overstrained_patch",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.45,
            },
            "target_intervention": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "target_strain_intervention_patch",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.20,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "intervention_key": "thermal_gradient",
            "intervention_direction": "decrease",
            "source_reject": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "hot_gradient_window",
                "utility": 9,
                "thermal_gradient": 0.72,
                "phase_purity": 0.94,
            },
            "source_commit": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "gradient_intervention_window",
                "utility": 8,
                "thermal_gradient": 0.42,
                "phase_purity": 0.94,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "target_hot_gradient_window",
                "utility": 9,
                "thermal_gradient": 0.66,
                "phase_purity": 0.93,
            },
            "target_intervention": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "target_gradient_intervention_window",
                "utility": 8,
                "thermal_gradient": 0.42,
                "phase_purity": 0.93,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_intervention_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
