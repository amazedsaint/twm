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
    BranchSelectionCertificate,
    BranchRuntime,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


BRANCH_RESTART_CERTIFICATE_SCHEMA = "trwm.branch_restart_certificate.v1"
BRANCH_RESTART_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_restart_transfer_certificate.v1"
BRANCH_RESTART_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1023/A:1006314320276",
)
BRANCH_RESTART_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source branch receipts can certify "
    "that target exploration should restart from a known anchor instead of spending verifier budget on "
    "a local continuation dead end. It is not SAT/CSP restart-performance evidence, a Las Vegas "
    "algorithm result, robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchRestartCertificate:
    schema_version: str
    domain: str
    restart_rule_id: str
    restart_rule_version: str
    source_context_id: str
    target_context_id: str
    local_action: str
    restart_action: str
    source_local_reject_receipt_hashes: tuple[str, ...]
    source_restart_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    restart_target_receipt_hashes: tuple[str, ...]
    restart_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    restart_branch_selection_certificate_hash: str
    local_dead_end_count: int
    restart_anchor_commit_count: int
    static_committed: bool
    restart_committed: bool
    static_verifier_call_count: int
    restart_verifier_call_count: int
    same_budget: bool
    restart_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_RESTART_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch restart certificate schema: {self.schema_version}")
        for field_name in (
            "source_local_reject_receipt_hashes",
            "source_restart_commit_receipt_hashes",
            "static_target_receipt_hashes",
            "restart_target_receipt_hashes",
            "restart_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_restart_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchRestartDomainReport:
    domain: str
    source_context: str
    target_context: str
    local_action: str
    restart_action: str
    local_dead_end_count: int
    restart_anchor_commit_count: int
    static_committed: bool
    restart_committed: bool
    static_verifier_call_count: int
    restart_verifier_call_count: int
    source_local_reject_receipt_hashes: tuple[str, ...]
    source_restart_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    restart_target_receipt_hashes: tuple[str, ...]
    restart_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchRestartTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchRestartDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_local_reject_count: int
    source_restart_commit_count: int
    static_success_count: int
    restart_success_count: int
    same_budget_restart_count: int
    branch_restart_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_restart_certificates_valid: bool
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
class BranchRestartTransferCertificate:
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
    branch_restart_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_local_reject_count: int
    source_restart_commit_count: int
    static_success_count: int
    restart_success_count: int
    same_budget_restart_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_RESTART_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch restart transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_restart_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_restart_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchRestartTransferResult(CertifiedExampleResult):
    report: BranchRestartTransferReport
    branch_restart_transfer_certificate: BranchRestartTransferCertificate
    branch_restart_certificates: tuple[BranchRestartCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_restart_transfer_experiment() -> BranchRestartTransferReport:
    return run_branch_restart_transfer_certified_experiment().report


def run_branch_restart_transfer_certified_experiment() -> CertifiedBranchRestartTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchRestartDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    restart_certificates: list[BranchRestartCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:restart"
        target_context = f"{spec.domain_id}:target:restart"
        local_action = _local_action(spec, source_context)
        restart_action = _restart_action(spec, source_context)
        static_target_action = _local_action(spec, target_context)
        restart_target_action = _restart_action(spec, target_context)

        source_outcome = runtime.step(
            state,
            _make_restart_traces(
                spec,
                context=source_context,
                phase="source-local-dead-end",
                actions=(local_action, restart_action),
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
            _make_restart_traces(
                spec,
                context=target_context,
                phase="target-local-continuation",
                actions=(static_target_action,),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        restart_outcome = runtime.step(
            state,
            _make_restart_traces(
                spec,
                context=target_context,
                phase="target-restart-anchor",
                actions=(restart_target_action,),
            ),
        )
        state = normalize_state(restart_outcome.state)
        restart_certificate = build_branch_selection_certificate(
            restart_outcome.receipts,
            verifier_call_count=restart_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(restart_outcome.receipts), restart_certificate))

        certificate = build_branch_restart_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            local_action=str(local_action["action"]),
            restart_action=str(restart_action["action"]),
            source_local_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
            source_restart_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            restart_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in restart_outcome.receipts),
            restart_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in restart_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            restart_branch_selection_certificate_hash=restart_certificate.certificate_hash,
            static_committed=static_outcome.committed,
            restart_committed=restart_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            restart_verifier_call_count=restart_outcome.verifier_calls,
        )
        restart_certificates.append(certificate)
        rows.append(
            BranchRestartDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                local_action=certificate.local_action,
                restart_action=certificate.restart_action,
                local_dead_end_count=certificate.local_dead_end_count,
                restart_anchor_commit_count=certificate.restart_anchor_commit_count,
                static_committed=static_outcome.committed,
                restart_committed=restart_outcome.committed,
                static_verifier_call_count=static_outcome.verifier_calls,
                restart_verifier_call_count=restart_outcome.verifier_calls,
                source_local_reject_receipt_hashes=certificate.source_local_reject_receipt_hashes,
                source_restart_commit_receipt_hashes=certificate.source_restart_commit_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                restart_target_receipt_hashes=certificate.restart_target_receipt_hashes,
                restart_certificate_hash=certificate.certificate_hash,
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

    report = BranchRestartTransferReport(
        schema_version="trwm.example.branch_restart_transfer.v1",
        experiment_id="branch_restart_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_local_reject_count=sum(row.local_dead_end_count for row in rows),
        source_restart_commit_count=sum(row.restart_anchor_commit_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        restart_success_count=sum(1 for row in rows if row.restart_committed),
        same_budget_restart_count=sum(1 for row in rows if row.same_budget),
        branch_restart_certificate_count=len(restart_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_restart_certificates_valid=all(
            validate_branch_restart_certificate(certificate, row)
            for certificate, row in zip(restart_certificates, rows)
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
        sources=BRANCH_RESTART_SOURCES,
        learning=(
            "Branch history can improve exploration by certifying when local continuation is a dead end. "
            "The target spends the same verifier budget, but tries a restart anchor supported by source "
            "reject/commit receipts instead of repeating the local failure."
        ),
    )
    transfer_certificate = build_branch_restart_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_restart_certificate_hashes=tuple(certificate.certificate_hash for certificate in restart_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_restart_transfer",
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
        claim_boundary=BRANCH_RESTART_CLAIM_BOUNDARY,
        sources=BRANCH_RESTART_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchRestartTransferResult(
        report=report,
        branch_restart_transfer_certificate=transfer_certificate,
        branch_restart_certificates=tuple(restart_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_restart_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    local_action: str,
    restart_action: str,
    source_local_reject_receipt_hashes: tuple[str, ...],
    source_restart_commit_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    restart_target_receipt_hashes: tuple[str, ...],
    restart_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    restart_branch_selection_certificate_hash: str,
    static_committed: bool,
    restart_committed: bool,
    static_verifier_call_count: int,
    restart_verifier_call_count: int,
) -> BranchRestartCertificate:
    return BranchRestartCertificate(
        schema_version=BRANCH_RESTART_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        restart_rule_id="receipt_bound_restart_anchor",
        restart_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        local_action=local_action,
        restart_action=restart_action,
        source_local_reject_receipt_hashes=source_local_reject_receipt_hashes,
        source_restart_commit_receipt_hashes=source_restart_commit_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        restart_target_receipt_hashes=restart_target_receipt_hashes,
        restart_target_commit_receipt_hashes=restart_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        restart_branch_selection_certificate_hash=restart_branch_selection_certificate_hash,
        local_dead_end_count=len(source_local_reject_receipt_hashes),
        restart_anchor_commit_count=len(source_restart_commit_receipt_hashes),
        static_committed=static_committed,
        restart_committed=restart_committed,
        static_verifier_call_count=static_verifier_call_count,
        restart_verifier_call_count=restart_verifier_call_count,
        same_budget=static_verifier_call_count == restart_verifier_call_count == 1,
        restart_reason="source_local_dead_end_selects_restart_anchor",
    )


def validate_branch_restart_certificate(
    certificate: BranchRestartCertificate,
    row: BranchRestartDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_RESTART_CERTIFICATE_SCHEMA:
            return False
        if certificate.restart_rule_id != "receipt_bound_restart_anchor":
            return False
        if certificate.restart_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.local_action,
            certificate.restart_action,
            certificate.restart_reason,
        ):
            if not _nonempty(value):
                return False
        if certificate.local_action == certificate.restart_action:
            return False
        if certificate.local_dead_end_count != 1:
            return False
        if certificate.restart_anchor_commit_count != 1:
            return False
        if certificate.static_committed or not certificate.restart_committed:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.restart_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.restart_reason != "source_local_dead_end_selects_restart_anchor":
            return False
        for values, expected_len in (
            (certificate.source_local_reject_receipt_hashes, 1),
            (certificate.source_restart_commit_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.restart_target_receipt_hashes, 1),
            (certificate.restart_target_commit_receipt_hashes, 1),
        ):
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.restart_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id:
                return False
            if row.target_context != certificate.target_context_id:
                return False
            if row.local_action != certificate.local_action or row.restart_action != certificate.restart_action:
                return False
            if row.local_dead_end_count != certificate.local_dead_end_count:
                return False
            if row.restart_anchor_commit_count != certificate.restart_anchor_commit_count:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.restart_committed != certificate.restart_committed:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.restart_verifier_call_count != certificate.restart_verifier_call_count:
                return False
            if row.source_local_reject_receipt_hashes != certificate.source_local_reject_receipt_hashes:
                return False
            if row.source_restart_commit_receipt_hashes != certificate.source_restart_commit_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.restart_target_receipt_hashes != certificate.restart_target_receipt_hashes:
                return False
            if row.restart_certificate_hash != certificate.certificate_hash:
                return False
            if row.same_budget != certificate.same_budget:
                return False
        return certificate.certificate_hash == branch_restart_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_restart_transfer_certificate(
    report: BranchRestartTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_restart_certificate_hashes: tuple[str, ...],
) -> BranchRestartTransferCertificate:
    return BranchRestartTransferCertificate(
        schema_version=BRANCH_RESTART_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_restart_certificate_hashes=branch_restart_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_local_reject_count=report.source_local_reject_count,
        source_restart_commit_count=report.source_restart_commit_count,
        static_success_count=report.static_success_count,
        restart_success_count=report.restart_success_count,
        same_budget_restart_count=report.same_budget_restart_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_RESTART_CLAIM_BOUNDARY,
    )


def validate_branch_restart_transfer_certificate(
    certificate: BranchRestartTransferCertificate,
    report: BranchRestartTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_RESTART_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_restart_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_restart_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_local_reject_count != certificate.domain_count:
            return False
        if certificate.source_restart_commit_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.restart_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_restart_count != certificate.domain_count:
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
            if not report.all_branch_restart_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_local_reject_count != certificate.source_local_reject_count:
                return False
            if report.source_restart_commit_count != certificate.source_restart_commit_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.restart_success_count != certificate.restart_success_count:
                return False
        return certificate.certificate_hash == branch_restart_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_restart_certificate_hash(certificate: BranchRestartCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchRestartCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_restart_transfer_certificate_hash(
    certificate: BranchRestartTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchRestartTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchRestartTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchRestartTransferReport,
    transfer_certificate: BranchRestartTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_restart_transfer_g1",
        claim_text=(
            "Source local-dead-end and restart-anchor receipts can improve local target exploration "
            "under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_restart_transfer",
        requirements=(
            requirement(
                "branch_restart_transfer_certificate_valid",
                validate_branch_restart_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid),
            requirement("all_branch_restart_certificates_valid", report.all_branch_restart_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_local_dead_ends_bound", report.source_local_reject_count == report.domain_count),
            requirement("source_restart_anchors_bound", report.source_restart_commit_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("restart_succeeds_all_domains", report.restart_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_restart_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_local_reject_count": report.source_local_reject_count,
            "source_restart_commit_count": report.source_restart_commit_count,
            "static_success_count": report.static_success_count,
            "restart_success_count": report.restart_success_count,
        },
        boundary=BRANCH_RESTART_CLAIM_BOUNDARY,
        sources=BRANCH_RESTART_SOURCES,
    )


def _make_restart_traces(
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
            seeds=("branch-restart-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.restart.transfer.v1",
        )
        for action in actions
    )


def _local_action_name(spec: ExplorationDomainSpec) -> str:
    if spec.domain_id == "robotics_replan":
        return "tight_local_patch"
    if spec.domain_id == "molecule_repair":
        return "localized_bond_patch"
    if spec.domain_id == "material_process":
        return "local_temperature_trim"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _restart_action_name(spec: ExplorationDomainSpec) -> str:
    if spec.domain_id == "robotics_replan":
        return "restart_safe_corridor"
    if spec.domain_id == "molecule_repair":
        return "restart_scaffold_repair"
    if spec.domain_id == "material_process":
        return "restart_tempered_schedule"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _local_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _local_action_name(spec),
            "utility": 9,
            "clearance": 0.11,
            "turn_rate": 0.82,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _local_action_name(spec),
            "utility": 9,
            "valence_ok": True,
            "strain": 0.52,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _local_action_name(spec),
            "utility": 9,
            "thermal_gradient": 0.68,
            "phase_purity": 0.89,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _restart_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _restart_action_name(spec),
            "utility": 7,
            "clearance": 0.37,
            "turn_rate": 0.36,
            "target_commit": True,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _restart_action_name(spec),
            "utility": 7,
            "valence_ok": True,
            "strain": 0.15,
            "target_commit": True,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _restart_action_name(spec),
            "utility": 7,
            "thermal_gradient": 0.36,
            "phase_purity": 0.95,
            "target_commit": True,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_restart_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
