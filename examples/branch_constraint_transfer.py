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


BRANCH_CONSTRAINT_CERTIFICATE_SCHEMA = "trwm.branch_constraint_certificate.v1"
BRANCH_CONSTRAINT_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_constraint_transfer_certificate.v1"
BRANCH_CONSTRAINT_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1016/0004-3702(77)90007-8",
)
BRANCH_CONSTRAINT_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source receipts can certify a "
    "pairwise incompatible branch combination so the target spends the same one-call verifier budget "
    "on a compatible pair instead of replaying the failed pair. It is not a CSP solver, arc-consistency "
    "algorithm, path-consistency result, planning algorithm, robotics safety, chemistry, materials "
    "discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchConstraintCertificate:
    schema_version: str
    domain: str
    constraint_rule_id: str
    constraint_rule_version: str
    source_context_id: str
    target_context_id: str
    incompatible_pair: tuple[str, str]
    compatible_pair: tuple[str, str]
    static_action: str
    constraint_action: str
    source_incompatible_reject_receipt_hashes: tuple[str, ...]
    source_compatible_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    constraint_target_receipt_hashes: tuple[str, ...]
    constraint_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    constraint_branch_selection_certificate_hash: str
    static_committed: bool
    constraint_committed: bool
    static_verifier_call_count: int
    constraint_verifier_call_count: int
    same_budget: bool
    constraint_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONSTRAINT_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch constraint certificate schema: {self.schema_version}")
        for field_name in (
            "incompatible_pair",
            "compatible_pair",
            "source_incompatible_reject_receipt_hashes",
            "source_compatible_commit_receipt_hashes",
            "static_target_receipt_hashes",
            "constraint_target_receipt_hashes",
            "constraint_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_constraint_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchConstraintDomainReport:
    domain: str
    source_context: str
    target_context: str
    incompatible_pair: tuple[str, str]
    compatible_pair: tuple[str, str]
    static_action: str
    constraint_action: str
    source_incompatible_reject_receipt_hashes: tuple[str, ...]
    source_compatible_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    constraint_target_receipt_hashes: tuple[str, ...]
    static_committed: bool
    constraint_committed: bool
    static_verifier_call_count: int
    constraint_verifier_call_count: int
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    constraint_branch_selection_certificate_hash: str
    constraint_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchConstraintTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchConstraintDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_incompatible_reject_count: int
    source_compatible_commit_count: int
    static_success_count: int
    constraint_success_count: int
    same_budget_constraint_count: int
    branch_constraint_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_constraint_certificates_valid: bool
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
class BranchConstraintTransferCertificate:
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
    branch_constraint_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_incompatible_reject_count: int
    source_compatible_commit_count: int
    static_success_count: int
    constraint_success_count: int
    same_budget_constraint_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONSTRAINT_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch constraint transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_constraint_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_constraint_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchConstraintTransferResult(CertifiedExampleResult):
    report: BranchConstraintTransferReport
    branch_constraint_transfer_certificate: BranchConstraintTransferCertificate
    branch_constraint_certificates: tuple[BranchConstraintCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_constraint_transfer_experiment() -> BranchConstraintTransferReport:
    return run_branch_constraint_transfer_certified_experiment().report


def run_branch_constraint_transfer_certified_experiment() -> CertifiedBranchConstraintTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchConstraintDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    constraint_certificates: list[BranchConstraintCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:pairwise-constraint"
        target_context = f"{spec.domain_id}:target:pairwise-constraint"
        action_map = _constraint_actions(spec)
        incompatible_source = _with_context(action_map["incompatible"], source_context)
        compatible_source = _with_context(action_map["compatible"], source_context)
        incompatible_target = _with_context(action_map["incompatible"], target_context)
        compatible_target = _with_context(action_map["compatible"], target_context)

        source_outcome = runtime.step(
            state,
            _make_constraint_traces(
                spec,
                context=source_context,
                phase="source-pairwise-evidence",
                actions=(incompatible_source, compatible_source),
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
            _make_constraint_traces(
                spec,
                context=target_context,
                phase="target-incompatible-pair",
                actions=(incompatible_target,),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        constraint_outcome = runtime.step(
            state,
            _make_constraint_traces(
                spec,
                context=target_context,
                phase="target-compatible-pair",
                actions=(compatible_target,),
            ),
        )
        state = normalize_state(constraint_outcome.state)
        constraint_branch_certificate = build_branch_selection_certificate(
            constraint_outcome.receipts,
            verifier_call_count=constraint_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(constraint_outcome.receipts), constraint_branch_certificate))

        certificate = build_branch_constraint_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            incompatible_pair=_pair(incompatible_source),
            compatible_pair=_pair(compatible_source),
            static_action=str(incompatible_target["action"]),
            constraint_action=str(compatible_target["action"]),
            source_incompatible_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
            source_compatible_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            constraint_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in constraint_outcome.receipts),
            constraint_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in constraint_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            constraint_branch_selection_certificate_hash=constraint_branch_certificate.certificate_hash,
            static_committed=static_outcome.committed,
            constraint_committed=constraint_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            constraint_verifier_call_count=constraint_outcome.verifier_calls,
        )
        constraint_certificates.append(certificate)
        rows.append(
            BranchConstraintDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                incompatible_pair=certificate.incompatible_pair,
                compatible_pair=certificate.compatible_pair,
                static_action=certificate.static_action,
                constraint_action=certificate.constraint_action,
                source_incompatible_reject_receipt_hashes=certificate.source_incompatible_reject_receipt_hashes,
                source_compatible_commit_receipt_hashes=certificate.source_compatible_commit_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                constraint_target_receipt_hashes=certificate.constraint_target_receipt_hashes,
                static_committed=certificate.static_committed,
                constraint_committed=certificate.constraint_committed,
                static_verifier_call_count=certificate.static_verifier_call_count,
                constraint_verifier_call_count=certificate.constraint_verifier_call_count,
                source_branch_selection_certificate_hash=certificate.source_branch_selection_certificate_hash,
                static_branch_selection_certificate_hash=certificate.static_branch_selection_certificate_hash,
                constraint_branch_selection_certificate_hash=certificate.constraint_branch_selection_certificate_hash,
                constraint_certificate_hash=certificate.certificate_hash,
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

    report = BranchConstraintTransferReport(
        schema_version="trwm.example.branch_constraint_transfer.v1",
        experiment_id="branch_constraint_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_incompatible_reject_count=sum(len(row.source_incompatible_reject_receipt_hashes) for row in rows),
        source_compatible_commit_count=sum(len(row.source_compatible_commit_receipt_hashes) for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        constraint_success_count=sum(1 for row in rows if row.constraint_committed),
        same_budget_constraint_count=sum(1 for row in rows if row.same_budget),
        branch_constraint_certificate_count=len(constraint_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_constraint_certificates_valid=all(
            validate_branch_constraint_certificate(certificate, row)
            for certificate, row in zip(constraint_certificates, rows)
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
        sources=BRANCH_CONSTRAINT_SOURCES,
        learning=(
            "Branch history can improve combinatorial exploration by certifying incompatible pairs. "
            "The target spends the same one-call verifier budget, but the certificate points it away "
            "from the source-rejected pair and toward a compatible pair that still requires fresh verification."
        ),
    )
    transfer_certificate = build_branch_constraint_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_constraint_certificate_hashes=tuple(certificate.certificate_hash for certificate in constraint_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_constraint_transfer",
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
        claim_boundary=BRANCH_CONSTRAINT_CLAIM_BOUNDARY,
        sources=BRANCH_CONSTRAINT_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchConstraintTransferResult(
        report=report,
        branch_constraint_transfer_certificate=transfer_certificate,
        branch_constraint_certificates=tuple(constraint_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_constraint_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    incompatible_pair: tuple[str, str],
    compatible_pair: tuple[str, str],
    static_action: str,
    constraint_action: str,
    source_incompatible_reject_receipt_hashes: tuple[str, ...],
    source_compatible_commit_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    constraint_target_receipt_hashes: tuple[str, ...],
    constraint_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    constraint_branch_selection_certificate_hash: str,
    static_committed: bool,
    constraint_committed: bool,
    static_verifier_call_count: int,
    constraint_verifier_call_count: int,
) -> BranchConstraintCertificate:
    return BranchConstraintCertificate(
        schema_version=BRANCH_CONSTRAINT_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        constraint_rule_id="receipt_bound_pairwise_constraint",
        constraint_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        incompatible_pair=incompatible_pair,
        compatible_pair=compatible_pair,
        static_action=static_action,
        constraint_action=constraint_action,
        source_incompatible_reject_receipt_hashes=source_incompatible_reject_receipt_hashes,
        source_compatible_commit_receipt_hashes=source_compatible_commit_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        constraint_target_receipt_hashes=constraint_target_receipt_hashes,
        constraint_target_commit_receipt_hashes=constraint_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        constraint_branch_selection_certificate_hash=constraint_branch_selection_certificate_hash,
        static_committed=static_committed,
        constraint_committed=constraint_committed,
        static_verifier_call_count=static_verifier_call_count,
        constraint_verifier_call_count=constraint_verifier_call_count,
        same_budget=static_verifier_call_count == constraint_verifier_call_count == 1,
        constraint_reason="source_reject_identifies_incompatible_pair",
    )


def validate_branch_constraint_certificate(
    certificate: BranchConstraintCertificate,
    row: BranchConstraintDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONSTRAINT_CERTIFICATE_SCHEMA:
            return False
        if certificate.constraint_rule_id != "receipt_bound_pairwise_constraint":
            return False
        if certificate.constraint_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.static_action,
            certificate.constraint_action,
            certificate.constraint_reason,
        ):
            if not _nonempty(value):
                return False
        if not _valid_pair(certificate.incompatible_pair) or not _valid_pair(certificate.compatible_pair):
            return False
        if certificate.incompatible_pair == certificate.compatible_pair:
            return False
        if certificate.static_action == certificate.constraint_action:
            return False
        if certificate.static_committed or not certificate.constraint_committed:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.constraint_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.constraint_reason != "source_reject_identifies_incompatible_pair":
            return False
        for values, expected_len in (
            (certificate.source_incompatible_reject_receipt_hashes, 1),
            (certificate.source_compatible_commit_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.constraint_target_receipt_hashes, 1),
            (certificate.constraint_target_commit_receipt_hashes, 1),
        ):
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.constraint_branch_selection_certificate_hash,
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
            if row.incompatible_pair != certificate.incompatible_pair:
                return False
            if row.compatible_pair != certificate.compatible_pair:
                return False
            if row.static_action != certificate.static_action:
                return False
            if row.constraint_action != certificate.constraint_action:
                return False
            if row.source_incompatible_reject_receipt_hashes != certificate.source_incompatible_reject_receipt_hashes:
                return False
            if row.source_compatible_commit_receipt_hashes != certificate.source_compatible_commit_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.constraint_target_receipt_hashes != certificate.constraint_target_receipt_hashes:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.constraint_committed != certificate.constraint_committed:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.constraint_verifier_call_count != certificate.constraint_verifier_call_count:
                return False
            if row.source_branch_selection_certificate_hash != certificate.source_branch_selection_certificate_hash:
                return False
            if row.static_branch_selection_certificate_hash != certificate.static_branch_selection_certificate_hash:
                return False
            if row.constraint_branch_selection_certificate_hash != certificate.constraint_branch_selection_certificate_hash:
                return False
            if row.constraint_certificate_hash != certificate.certificate_hash:
                return False
            if row.same_budget != certificate.same_budget:
                return False
        return certificate.certificate_hash == branch_constraint_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_constraint_transfer_certificate(
    report: BranchConstraintTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_constraint_certificate_hashes: tuple[str, ...],
) -> BranchConstraintTransferCertificate:
    return BranchConstraintTransferCertificate(
        schema_version=BRANCH_CONSTRAINT_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_constraint_certificate_hashes=branch_constraint_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_incompatible_reject_count=report.source_incompatible_reject_count,
        source_compatible_commit_count=report.source_compatible_commit_count,
        static_success_count=report.static_success_count,
        constraint_success_count=report.constraint_success_count,
        same_budget_constraint_count=report.same_budget_constraint_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CONSTRAINT_CLAIM_BOUNDARY,
    )


def validate_branch_constraint_transfer_certificate(
    certificate: BranchConstraintTransferCertificate,
    report: BranchConstraintTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONSTRAINT_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_constraint_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_constraint_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_incompatible_reject_count != certificate.domain_count:
            return False
        if certificate.source_compatible_commit_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.constraint_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_constraint_count != certificate.domain_count:
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
            if not report.all_branch_constraint_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_incompatible_reject_count != certificate.source_incompatible_reject_count:
                return False
            if report.source_compatible_commit_count != certificate.source_compatible_commit_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.constraint_success_count != certificate.constraint_success_count:
                return False
            if report.same_budget_constraint_count != certificate.same_budget_constraint_count:
                return False
        return certificate.certificate_hash == branch_constraint_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_constraint_certificate_hash(certificate: BranchConstraintCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchConstraintCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_constraint_transfer_certificate_hash(
    certificate: BranchConstraintTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchConstraintTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchConstraintTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchConstraintTransferReport,
    transfer_certificate: BranchConstraintTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_constraint_transfer_g1",
        claim_text=(
            "Pairwise incompatible source branch receipts can improve local target exploration under "
            "matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_constraint_transfer",
        requirements=(
            requirement(
                "branch_constraint_transfer_certificate_valid",
                validate_branch_constraint_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid),
            requirement("all_branch_constraint_certificates_valid", report.all_branch_constraint_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_incompatible_rejects_bound", report.source_incompatible_reject_count == report.domain_count),
            requirement("source_compatible_commits_bound", report.source_compatible_commit_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("constraint_succeeds_all_domains", report.constraint_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_constraint_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_incompatible_reject_count": report.source_incompatible_reject_count,
            "source_compatible_commit_count": report.source_compatible_commit_count,
            "static_success_count": report.static_success_count,
            "constraint_success_count": report.constraint_success_count,
        },
        boundary=BRANCH_CONSTRAINT_CLAIM_BOUNDARY,
        sources=BRANCH_CONSTRAINT_SOURCES,
    )


def _make_constraint_traces(
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
            seeds=("branch-constraint-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.constraint.transfer.v1",
        )
        for action in actions
    )


def _constraint_actions(spec: ExplorationDomainSpec) -> Mapping[str, Mapping[str, Any]]:
    if spec.domain_id == "robotics_replan":
        return {
            "incompatible": {
                "domain": spec.domain_id,
                "action": "narrow_pass__sharp_merge",
                "pair": ("narrow_pass", "sharp_merge"),
                "utility": 9,
                "clearance": 0.12,
                "turn_rate": 0.74,
            },
            "compatible": {
                "domain": spec.domain_id,
                "action": "wide_pass__soft_merge",
                "pair": ("wide_pass", "soft_merge"),
                "utility": 7,
                "clearance": 0.33,
                "turn_rate": 0.42,
                "target_commit": True,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "incompatible": {
                "domain": spec.domain_id,
                "action": "donor_lock__ring_compress",
                "pair": ("donor_lock", "ring_compress"),
                "utility": 9,
                "valence_ok": True,
                "strain": 0.56,
            },
            "compatible": {
                "domain": spec.domain_id,
                "action": "donor_relax__ring_pad",
                "pair": ("donor_relax", "ring_pad"),
                "utility": 7,
                "valence_ok": True,
                "strain": 0.17,
                "target_commit": True,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "incompatible": {
                "domain": spec.domain_id,
                "action": "rapid_heat__fast_quench",
                "pair": ("rapid_heat", "fast_quench"),
                "utility": 9,
                "thermal_gradient": 0.78,
                "phase_purity": 0.86,
            },
            "compatible": {
                "domain": spec.domain_id,
                "action": "ramp_heat__staged_quench",
                "pair": ("ramp_heat", "staged_quench"),
                "utility": 7,
                "thermal_gradient": 0.39,
                "phase_purity": 0.94,
                "target_commit": True,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _with_context(action: Mapping[str, Any], context: str) -> Mapping[str, Any]:
    return {**dict(action), "context": context}


def _pair(action: Mapping[str, Any]) -> tuple[str, str]:
    pair = tuple(str(value) for value in action["pair"])
    if len(pair) != 2:
        raise ValueError("pair must contain exactly two tokens")
    return (pair[0], pair[1])


def _valid_pair(value: tuple[str, ...]) -> bool:
    return isinstance(value, tuple) and len(value) == 2 and all(_nonempty(token) for token in value)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_constraint_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
