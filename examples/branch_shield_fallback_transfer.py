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


BRANCH_SHIELD_FALLBACK_CERTIFICATE_SCHEMA = "trwm.branch_shield_fallback_certificate.v1"
BRANCH_SHIELD_FALLBACK_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_shield_fallback_transfer_certificate.v1"
BRANCH_SHIELD_FALLBACK_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1609/aaai.v32i1.11797",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC6959420/",
)
BRANCH_SHIELD_FALLBACK_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound unsafe-family "
    "and fallback-family evidence can filter an unsafe target proposal before target exploration "
    "under a matched one-call verifier budget. It is not shield synthesis, runtime assurance, "
    "safe reinforcement learning, temporal-logic enforcement, controller switching, robotics "
    "safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchShieldFallbackCertificate:
    schema_version: str
    domain: str
    shield_rule_id: str
    shield_rule_version: str
    source_context_id: str
    target_context_id: str
    shield_spec_id: str
    unsafe_family: str
    fallback_family: str
    source_unsafe_action_id: str
    source_fallback_action_id: str
    static_target_action: str
    shield_target_action: str
    source_unsafe_receipt_hashes: tuple[str, ...]
    source_fallback_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    shield_target_receipt_hashes: tuple[str, ...]
    shield_target_commit_receipt_hashes: tuple[str, ...]
    source_unsafe_branch_selection_certificate_hash: str
    source_fallback_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    shield_branch_selection_certificate_hash: str
    source_unsafe_rejected: bool
    source_fallback_committed: bool
    static_committed: bool
    shield_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    shield_verifier_call_count: int
    same_budget: bool
    fallback_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SHIELD_FALLBACK_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch shield-fallback certificate schema: {self.schema_version}")
        for field_name in (
            "source_unsafe_receipt_hashes",
            "source_fallback_receipt_hashes",
            "static_target_receipt_hashes",
            "shield_target_receipt_hashes",
            "shield_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_shield_fallback_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchShieldFallbackDomainReport:
    domain: str
    source_context: str
    target_context: str
    shield_spec_id: str
    unsafe_family: str
    fallback_family: str
    source_unsafe_action_id: str
    source_fallback_action_id: str
    static_target_action: str
    shield_target_action: str
    source_unsafe_rejected: bool
    source_fallback_committed: bool
    static_committed: bool
    shield_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    shield_verifier_call_count: int
    source_unsafe_receipt_hashes: tuple[str, ...]
    source_fallback_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    shield_target_receipt_hashes: tuple[str, ...]
    branch_shield_fallback_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchShieldFallbackTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchShieldFallbackDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_unsafe_rejected_count: int
    source_fallback_committed_count: int
    static_success_count: int
    shield_success_count: int
    same_budget_shield_count: int
    branch_shield_fallback_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_shield_fallback_certificates_valid: bool
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
class BranchShieldFallbackTransferCertificate:
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
    branch_shield_fallback_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_unsafe_rejected_count: int
    source_fallback_committed_count: int
    static_success_count: int
    shield_success_count: int
    same_budget_shield_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SHIELD_FALLBACK_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch shield-fallback transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_shield_fallback_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_shield_fallback_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchShieldFallbackTransferResult(CertifiedExampleResult):
    report: BranchShieldFallbackTransferReport
    branch_shield_fallback_transfer_certificate: BranchShieldFallbackTransferCertificate
    branch_shield_fallback_certificates: tuple[BranchShieldFallbackCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_shield_fallback_transfer_experiment() -> BranchShieldFallbackTransferReport:
    return run_branch_shield_fallback_transfer_certified_experiment().report


def run_branch_shield_fallback_transfer_certified_experiment() -> CertifiedBranchShieldFallbackTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchShieldFallbackDomainReport] = []
    shield_certificates: list[BranchShieldFallbackCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_shield_fallback_plan(spec)
        source_context = f"{spec.domain_id}:source:branch-shield-fallback"
        target_context = f"{spec.domain_id}:target:branch-shield-fallback"

        unsafe_outcome = runtime.step(
            state,
            _make_shield_fallback_traces(spec, context=source_context, phase="source-unsafe", actions=(plan["source_unsafe"],)),
        )
        unsafe_selection = build_branch_selection_certificate(unsafe_outcome.receipts, verifier_call_count=unsafe_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(unsafe_outcome.receipts), unsafe_selection))
        memory.update_branch(unsafe_outcome.receipts, unsafe_selection)

        fallback_outcome = runtime.step(
            state,
            _make_shield_fallback_traces(spec, context=source_context, phase="source-fallback", actions=(plan["source_fallback"],)),
        )
        state = normalize_state(fallback_outcome.state)
        fallback_selection = build_branch_selection_certificate(
            fallback_outcome.receipts,
            verifier_call_count=fallback_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(fallback_outcome.receipts), fallback_selection))
        memory.update_branch(fallback_outcome.receipts, fallback_selection)

        static_outcome = runtime.step(
            state,
            _make_shield_fallback_traces(spec, context=target_context, phase="target-static-unsafe", actions=(plan["target_static"],)),
        )
        static_selection = build_branch_selection_certificate(static_outcome.receipts, verifier_call_count=static_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        shield_outcome = runtime.step(
            state,
            _make_shield_fallback_traces(spec, context=target_context, phase="target-shield-fallback", actions=(plan["target_shield"],)),
        )
        state = normalize_state(shield_outcome.state)
        shield_selection = build_branch_selection_certificate(shield_outcome.receipts, verifier_call_count=shield_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(shield_outcome.receipts), shield_selection))

        certificate = build_branch_shield_fallback_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            shield_spec_id=str(plan["shield_spec_id"]),
            unsafe_family=str(plan["unsafe_family"]),
            fallback_family=str(plan["fallback_family"]),
            source_unsafe_action_id=str(plan["source_unsafe"]["action"]),
            source_fallback_action_id=str(plan["source_fallback"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            shield_target_action=str(plan["target_shield"]["action"]),
            source_unsafe_receipt_hashes=tuple(receipt.receipt_hash for receipt in unsafe_outcome.receipts),
            source_fallback_receipt_hashes=tuple(receipt.receipt_hash for receipt in fallback_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            shield_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in shield_outcome.receipts),
            shield_target_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in shield_outcome.receipts if receipt.committed),
            source_unsafe_branch_selection_certificate_hash=unsafe_selection.certificate_hash,
            source_fallback_branch_selection_certificate_hash=fallback_selection.certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            shield_branch_selection_certificate_hash=shield_selection.certificate_hash,
            source_unsafe_rejected=any(receipt.hard_result.rejected for receipt in unsafe_outcome.receipts),
            source_fallback_committed=fallback_outcome.committed,
            static_committed=static_outcome.committed,
            shield_committed=shield_outcome.committed,
            source_verifier_call_count=unsafe_outcome.verifier_calls + fallback_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            shield_verifier_call_count=shield_outcome.verifier_calls,
        )
        shield_certificates.append(certificate)
        rows.append(_row_from_certificate(certificate))

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

    report = BranchShieldFallbackTransferReport(
        schema_version="trwm.example.branch_shield_fallback_transfer.v1",
        experiment_id="branch_shield_fallback_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_unsafe_rejected_count=sum(1 for row in rows if row.source_unsafe_rejected),
        source_fallback_committed_count=sum(1 for row in rows if row.source_fallback_committed),
        static_success_count=sum(1 for row in rows if row.static_committed),
        shield_success_count=sum(1 for row in rows if row.shield_committed),
        same_budget_shield_count=sum(1 for row in rows if row.same_budget),
        branch_shield_fallback_certificate_count=len(shield_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_shield_fallback_certificates_valid=all(
            validate_branch_shield_fallback_certificate(certificate, row)
            for certificate, row in zip(shield_certificates, rows)
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
        hard_gate_keys=("clearance", "turn_rate", "valence_ok", "strain", "thermal_gradient", "phase_purity"),
        residual_kinds=tuple(sorted({spec.residual_kind for spec in DOMAIN_SPECS})),
        sources=BRANCH_SHIELD_FALLBACK_SOURCES,
        learning=(
            "Shield-fallback reuse separates runtime guard evidence from commit authority. Source receipts "
            "can identify an unsafe proposal family and a fallback family to try, but the target fallback "
            "still commits only through a fresh hard-verifier receipt."
        ),
    )
    transfer_certificate = build_branch_shield_fallback_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_shield_fallback_certificate_hashes=tuple(certificate.certificate_hash for certificate in shield_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_shield_fallback_transfer",
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
        claim_boundary=BRANCH_SHIELD_FALLBACK_CLAIM_BOUNDARY,
        sources=BRANCH_SHIELD_FALLBACK_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchShieldFallbackTransferResult(
        report=report,
        branch_shield_fallback_transfer_certificate=transfer_certificate,
        branch_shield_fallback_certificates=tuple(shield_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_shield_fallback_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    shield_spec_id: str,
    unsafe_family: str,
    fallback_family: str,
    source_unsafe_action_id: str,
    source_fallback_action_id: str,
    static_target_action: str,
    shield_target_action: str,
    source_unsafe_receipt_hashes: tuple[str, ...],
    source_fallback_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    shield_target_receipt_hashes: tuple[str, ...],
    shield_target_commit_receipt_hashes: tuple[str, ...],
    source_unsafe_branch_selection_certificate_hash: str,
    source_fallback_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    shield_branch_selection_certificate_hash: str,
    source_unsafe_rejected: bool,
    source_fallback_committed: bool,
    static_committed: bool,
    shield_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    shield_verifier_call_count: int,
) -> BranchShieldFallbackCertificate:
    return BranchShieldFallbackCertificate(
        schema_version=BRANCH_SHIELD_FALLBACK_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        shield_rule_id="receipt_bound_shield_fallback",
        shield_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        shield_spec_id=shield_spec_id,
        unsafe_family=unsafe_family,
        fallback_family=fallback_family,
        source_unsafe_action_id=source_unsafe_action_id,
        source_fallback_action_id=source_fallback_action_id,
        static_target_action=static_target_action,
        shield_target_action=shield_target_action,
        source_unsafe_receipt_hashes=source_unsafe_receipt_hashes,
        source_fallback_receipt_hashes=source_fallback_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        shield_target_receipt_hashes=shield_target_receipt_hashes,
        shield_target_commit_receipt_hashes=shield_target_commit_receipt_hashes,
        source_unsafe_branch_selection_certificate_hash=source_unsafe_branch_selection_certificate_hash,
        source_fallback_branch_selection_certificate_hash=source_fallback_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        shield_branch_selection_certificate_hash=shield_branch_selection_certificate_hash,
        source_unsafe_rejected=source_unsafe_rejected,
        source_fallback_committed=source_fallback_committed,
        static_committed=static_committed,
        shield_committed=shield_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        shield_verifier_call_count=shield_verifier_call_count,
        same_budget=static_verifier_call_count == shield_verifier_call_count == 1,
        fallback_reason="unsafe_family_routes_to_verified_fallback",
    )


def validate_branch_shield_fallback_certificate(
    certificate: BranchShieldFallbackCertificate,
    row: BranchShieldFallbackDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_SHIELD_FALLBACK_CERTIFICATE_SCHEMA:
            return False
        if certificate.shield_rule_id != "receipt_bound_shield_fallback" or certificate.shield_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.shield_spec_id,
            certificate.unsafe_family,
            certificate.fallback_family,
        ):
            if not _nonempty(value):
                return False
        if certificate.unsafe_family == certificate.fallback_family:
            return False
        action_ids = (
            certificate.source_unsafe_action_id,
            certificate.source_fallback_action_id,
            certificate.static_target_action,
            certificate.shield_target_action,
        )
        if len(set(action_ids)) != len(action_ids) or any(not _nonempty(action_id) for action_id in action_ids):
            return False
        if not (
            certificate.source_unsafe_rejected
            and certificate.source_fallback_committed
            and not certificate.static_committed
            and certificate.shield_committed
        ):
            return False
        if certificate.source_verifier_call_count != 2:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.shield_verifier_call_count != 1:
            return False
        if not certificate.same_budget or certificate.fallback_reason != "unsafe_family_routes_to_verified_fallback":
            return False
        hash_groups = (
            (certificate.source_unsafe_receipt_hashes, 1),
            (certificate.source_fallback_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.shield_target_receipt_hashes, 1),
            (certificate.shield_target_commit_receipt_hashes, 1),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_unsafe_branch_selection_certificate_hash,
            certificate.source_fallback_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.shield_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.shield_spec_id != certificate.shield_spec_id:
                return False
            if row.unsafe_family != certificate.unsafe_family or row.fallback_family != certificate.fallback_family:
                return False
            if row.source_unsafe_action_id != certificate.source_unsafe_action_id:
                return False
            if row.source_fallback_action_id != certificate.source_fallback_action_id:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.shield_target_action != certificate.shield_target_action:
                return False
            if row.source_unsafe_receipt_hashes != certificate.source_unsafe_receipt_hashes:
                return False
            if row.source_fallback_receipt_hashes != certificate.source_fallback_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.shield_target_receipt_hashes != certificate.shield_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_shield_fallback_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_shield_fallback_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_shield_fallback_transfer_certificate(
    report: BranchShieldFallbackTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_shield_fallback_certificate_hashes: tuple[str, ...],
) -> BranchShieldFallbackTransferCertificate:
    return BranchShieldFallbackTransferCertificate(
        schema_version=BRANCH_SHIELD_FALLBACK_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_shield_fallback_certificate_hashes=branch_shield_fallback_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_unsafe_rejected_count=report.source_unsafe_rejected_count,
        source_fallback_committed_count=report.source_fallback_committed_count,
        static_success_count=report.static_success_count,
        shield_success_count=report.shield_success_count,
        same_budget_shield_count=report.same_budget_shield_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_SHIELD_FALLBACK_CLAIM_BOUNDARY,
    )


def validate_branch_shield_fallback_transfer_certificate(
    certificate: BranchShieldFallbackTransferCertificate,
    report: BranchShieldFallbackTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_SHIELD_FALLBACK_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_shield_fallback_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_shield_fallback_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_unsafe_rejected_count != certificate.domain_count:
            return False
        if certificate.source_fallback_committed_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.shield_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_shield_count != certificate.domain_count:
            return False
        if not (certificate.replay_audit_ok and certificate.rollback_audit_ok and certificate.ledger_audit_ok):
            return False
        if certificate.invalid_commit_count != 0 or not certificate.claim_boundary:
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
            if tuple(row.branch_shield_fallback_certificate_hash for row in report.rows) != certificate.branch_shield_fallback_certificate_hashes:
                return False
            if report.branch_shield_fallback_certificate_count != len(certificate.branch_shield_fallback_certificate_hashes):
                return False
            if not report.all_branch_shield_fallback_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_unsafe_rejected_count != certificate.source_unsafe_rejected_count:
                return False
            if report.source_fallback_committed_count != certificate.source_fallback_committed_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.shield_success_count != certificate.shield_success_count:
                return False
            if report.same_budget_shield_count != certificate.same_budget_shield_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_shield_fallback_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_shield_fallback_certificate_hash(certificate: BranchShieldFallbackCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchShieldFallbackCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_shield_fallback_transfer_certificate_hash(
    certificate: BranchShieldFallbackTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchShieldFallbackTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchShieldFallbackTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchShieldFallbackTransferReport,
    transfer_certificate: BranchShieldFallbackTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_shield_fallback_transfer_g1",
        claim_text=(
            "Receipt-bound shield-fallback certificates can improve local target exploration by "
            "filtering unsafe target proposal families and trying verified fallback families under "
            "matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_shield_fallback_transfer",
        requirements=(
            requirement(
                "branch_shield_fallback_transfer_certificate_valid",
                validate_branch_shield_fallback_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_shield_fallback_certificates_valid", report.all_branch_shield_fallback_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_unsafe_rejects_all_domains", report.source_unsafe_rejected_count == report.domain_count),
            requirement("source_fallback_commits_all_domains", report.source_fallback_committed_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("shield_succeeds_all_domains", report.shield_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_shield_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 2),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "static_success_count": report.static_success_count,
            "shield_success_count": report.shield_success_count,
        },
        boundary=BRANCH_SHIELD_FALLBACK_CLAIM_BOUNDARY,
        sources=BRANCH_SHIELD_FALLBACK_SOURCES,
    )


def _row_from_certificate(certificate: BranchShieldFallbackCertificate) -> BranchShieldFallbackDomainReport:
    return BranchShieldFallbackDomainReport(
        domain=certificate.domain,
        source_context=certificate.source_context_id,
        target_context=certificate.target_context_id,
        shield_spec_id=certificate.shield_spec_id,
        unsafe_family=certificate.unsafe_family,
        fallback_family=certificate.fallback_family,
        source_unsafe_action_id=certificate.source_unsafe_action_id,
        source_fallback_action_id=certificate.source_fallback_action_id,
        static_target_action=certificate.static_target_action,
        shield_target_action=certificate.shield_target_action,
        source_unsafe_rejected=certificate.source_unsafe_rejected,
        source_fallback_committed=certificate.source_fallback_committed,
        static_committed=certificate.static_committed,
        shield_committed=certificate.shield_committed,
        source_verifier_call_count=certificate.source_verifier_call_count,
        static_verifier_call_count=certificate.static_verifier_call_count,
        shield_verifier_call_count=certificate.shield_verifier_call_count,
        source_unsafe_receipt_hashes=certificate.source_unsafe_receipt_hashes,
        source_fallback_receipt_hashes=certificate.source_fallback_receipt_hashes,
        static_target_receipt_hashes=certificate.static_target_receipt_hashes,
        shield_target_receipt_hashes=certificate.shield_target_receipt_hashes,
        branch_shield_fallback_certificate_hash=certificate.certificate_hash,
        same_budget=certificate.same_budget,
    )


def _make_shield_fallback_traces(
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
            seeds=("branch-shield-fallback-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.shield_fallback.transfer.v1",
        )
        for action in actions
    )


def _domain_shield_fallback_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        unsafe_family = "shortcut_collision_risk"
        fallback_family = "verified_detour"
        return {
            "shield_spec_id": "runtime_guarded_detour",
            "unsafe_family": unsafe_family,
            "fallback_family": fallback_family,
            "source_unsafe": {"domain": spec.domain_id, "action": "shield_source_short_cut", "utility": 10, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "clearance": 0.08, "turn_rate": 0.88},
            "source_fallback": {"domain": spec.domain_id, "action": "shield_source_safe_detour", "utility": 7, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "clearance": 0.34, "turn_rate": 0.42},
            "target_static": {"domain": spec.domain_id, "action": "shield_target_short_cut", "utility": 10, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "clearance": 0.12, "turn_rate": 0.78},
            "target_shield": {"domain": spec.domain_id, "action": "shield_target_safe_detour", "utility": 7, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "clearance": 0.33, "turn_rate": 0.44},
        }
    if spec.domain_id == "molecule_repair":
        unsafe_family = "forced_valence_patch"
        fallback_family = "valence_preserving_repair"
        return {
            "shield_spec_id": "runtime_guarded_valence",
            "unsafe_family": unsafe_family,
            "fallback_family": fallback_family,
            "source_unsafe": {"domain": spec.domain_id, "action": "shield_source_force_patch", "utility": 10, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "valence_ok": False, "strain": 0.31},
            "source_fallback": {"domain": spec.domain_id, "action": "shield_source_valence_repair", "utility": 7, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "valence_ok": True, "strain": 0.17},
            "target_static": {"domain": spec.domain_id, "action": "shield_target_force_patch", "utility": 10, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "valence_ok": False, "strain": 0.30},
            "target_shield": {"domain": spec.domain_id, "action": "shield_target_valence_repair", "utility": 7, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "valence_ok": True, "strain": 0.16},
        }
    if spec.domain_id == "material_process":
        unsafe_family = "flash_quench"
        fallback_family = "controlled_anneal"
        return {
            "shield_spec_id": "runtime_guarded_anneal",
            "unsafe_family": unsafe_family,
            "fallback_family": fallback_family,
            "source_unsafe": {"domain": spec.domain_id, "action": "shield_source_flash_quench", "utility": 10, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "thermal_gradient": 0.88, "phase_purity": 0.84},
            "source_fallback": {"domain": spec.domain_id, "action": "shield_source_controlled_anneal", "utility": 7, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "thermal_gradient": 0.40, "phase_purity": 0.95},
            "target_static": {"domain": spec.domain_id, "action": "shield_target_flash_quench", "utility": 10, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "thermal_gradient": 0.86, "phase_purity": 0.85},
            "target_shield": {"domain": spec.domain_id, "action": "shield_target_controlled_anneal", "utility": 7, "unsafe_family": unsafe_family, "fallback_family": fallback_family, "thermal_gradient": 0.39, "phase_purity": 0.96},
        }
    raise ValueError(f"unknown shield-fallback domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_shield_fallback_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
