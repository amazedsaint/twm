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


BRANCH_BOUNDARY_BRACKET_CERTIFICATE_SCHEMA = "trwm.branch_boundary_bracket_certificate.v1"
BRANCH_BOUNDARY_BRACKET_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_boundary_bracket_transfer_certificate.v1"
BRANCH_BOUNDARY_BRACKET_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://proceedings.mlr.press/v37/sui15.html",
)
BRANCH_BOUNDARY_BRACKET_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source reject/commit endpoints can "
    "define a named proposal bracket for target boundary exploration under a matched one-call verifier "
    "budget, but the bracketed target candidate still commits only through fresh hard verification. It "
    "is not SafeOpt, safe Bayesian optimization, active-learning convergence, robotics safety, chemistry, "
    "materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchBoundaryBracketCertificate:
    schema_version: str
    domain: str
    bracket_rule_id: str
    bracket_rule_version: str
    source_context_id: str
    target_context_id: str
    residual_kind: str
    bracket_id: str
    bracket_version: str
    bracket_field_keys: tuple[str, ...]
    source_reject_action: str
    source_safe_action: str
    static_target_action: str
    bracket_target_action: str
    source_reject_receipt_hashes: tuple[str, ...]
    source_safe_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    bracket_target_receipt_hashes: tuple[str, ...]
    bracket_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    bracket_branch_selection_certificate_hash: str
    source_rejected: bool
    source_safe_committed: bool
    static_committed: bool
    bracket_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    bracket_verifier_call_count: int
    same_budget: bool
    bracket_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_BOUNDARY_BRACKET_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch boundary bracket certificate schema: {self.schema_version}")
        for field_name in (
            "bracket_field_keys",
            "source_reject_receipt_hashes",
            "source_safe_receipt_hashes",
            "static_target_receipt_hashes",
            "bracket_target_receipt_hashes",
            "bracket_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_boundary_bracket_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchBoundaryBracketDomainReport:
    domain: str
    source_context: str
    target_context: str
    residual_kind: str
    bracket_id: str
    bracket_field_keys: tuple[str, ...]
    source_reject_action: str
    source_safe_action: str
    static_target_action: str
    bracket_target_action: str
    source_rejected: bool
    source_safe_committed: bool
    static_committed: bool
    bracket_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    bracket_verifier_call_count: int
    source_reject_receipt_hashes: tuple[str, ...]
    source_safe_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    bracket_target_receipt_hashes: tuple[str, ...]
    branch_boundary_bracket_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchBoundaryBracketTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchBoundaryBracketDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_reject_count: int
    source_safe_success_count: int
    static_success_count: int
    bracket_success_count: int
    same_budget_bracket_count: int
    branch_boundary_bracket_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_boundary_bracket_certificates_valid: bool
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
class BranchBoundaryBracketTransferCertificate:
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
    branch_boundary_bracket_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_reject_count: int
    source_safe_success_count: int
    static_success_count: int
    bracket_success_count: int
    same_budget_bracket_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_BOUNDARY_BRACKET_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch boundary bracket transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_boundary_bracket_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_boundary_bracket_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchBoundaryBracketTransferResult(CertifiedExampleResult):
    report: BranchBoundaryBracketTransferReport
    branch_boundary_bracket_transfer_certificate: BranchBoundaryBracketTransferCertificate
    branch_boundary_bracket_certificates: tuple[BranchBoundaryBracketCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_boundary_bracket_transfer_experiment() -> BranchBoundaryBracketTransferReport:
    return run_branch_boundary_bracket_transfer_certified_experiment().report


def run_branch_boundary_bracket_transfer_certified_experiment() -> CertifiedBranchBoundaryBracketTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchBoundaryBracketDomainReport] = []
    bracket_certificates: list[BranchBoundaryBracketCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:boundary_bracket"
        target_context = f"{spec.domain_id}:target:boundary_bracket"
        plan = _domain_bracket_plan(spec, source_context, target_context)

        source_outcome = runtime.step(
            state,
            _make_bracket_traces(
                spec,
                context=source_context,
                phase="source-boundary-bracket",
                actions=(plan["source_reject"], plan["source_safe"]),
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
            _make_bracket_traces(
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

        bracket_outcome = runtime.step(
            state,
            _make_bracket_traces(
                spec,
                context=target_context,
                phase="target-boundary-bracket",
                actions=(plan["target_bracket"],),
            ),
        )
        state = normalize_state(bracket_outcome.state)
        bracket_certificate = build_branch_selection_certificate(
            bracket_outcome.receipts,
            verifier_call_count=bracket_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(bracket_outcome.receipts), bracket_certificate))

        source_reject_hashes = tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected)
        source_safe_hashes = tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed)
        static_hashes = tuple(receipt.receipt_hash for receipt in static_outcome.receipts)
        bracket_hashes = tuple(receipt.receipt_hash for receipt in bracket_outcome.receipts)
        bracket_commit_hashes = tuple(receipt.receipt_hash for receipt in bracket_outcome.receipts if receipt.committed)

        certificate = build_branch_boundary_bracket_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            residual_kind=spec.residual_kind,
            bracket_id=str(plan["bracket_id"]),
            bracket_field_keys=tuple(str(key) for key in plan["bracket_field_keys"]),
            source_reject_action=str(plan["source_reject"]["action"]),
            source_safe_action=str(plan["source_safe"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            bracket_target_action=str(plan["target_bracket"]["action"]),
            source_reject_receipt_hashes=source_reject_hashes,
            source_safe_receipt_hashes=source_safe_hashes,
            static_target_receipt_hashes=static_hashes,
            bracket_target_receipt_hashes=bracket_hashes,
            bracket_target_commit_receipt_hashes=bracket_commit_hashes,
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            bracket_branch_selection_certificate_hash=bracket_certificate.certificate_hash,
            source_rejected=bool(source_reject_hashes),
            source_safe_committed=source_outcome.committed,
            static_committed=static_outcome.committed,
            bracket_committed=bracket_outcome.committed,
            source_verifier_call_count=source_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            bracket_verifier_call_count=bracket_outcome.verifier_calls,
        )
        bracket_certificates.append(certificate)
        rows.append(
            BranchBoundaryBracketDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                residual_kind=certificate.residual_kind,
                bracket_id=certificate.bracket_id,
                bracket_field_keys=certificate.bracket_field_keys,
                source_reject_action=certificate.source_reject_action,
                source_safe_action=certificate.source_safe_action,
                static_target_action=certificate.static_target_action,
                bracket_target_action=certificate.bracket_target_action,
                source_rejected=certificate.source_rejected,
                source_safe_committed=certificate.source_safe_committed,
                static_committed=certificate.static_committed,
                bracket_committed=certificate.bracket_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                bracket_verifier_call_count=certificate.bracket_verifier_call_count,
                source_reject_receipt_hashes=certificate.source_reject_receipt_hashes,
                source_safe_receipt_hashes=certificate.source_safe_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                bracket_target_receipt_hashes=certificate.bracket_target_receipt_hashes,
                branch_boundary_bracket_certificate_hash=certificate.certificate_hash,
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

    report = BranchBoundaryBracketTransferReport(
        schema_version="trwm.example.branch_boundary_bracket_transfer.v1",
        experiment_id="branch_boundary_bracket_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_reject_count=sum(1 for row in rows if row.source_rejected),
        source_safe_success_count=sum(1 for row in rows if row.source_safe_committed),
        static_success_count=sum(1 for row in rows if row.static_committed),
        bracket_success_count=sum(1 for row in rows if row.bracket_committed),
        same_budget_bracket_count=sum(1 for row in rows if row.same_budget),
        branch_boundary_bracket_certificate_count=len(bracket_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_boundary_bracket_certificates_valid=all(
            validate_branch_boundary_bracket_certificate(certificate, row)
            for certificate, row in zip(bracket_certificates, rows)
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
        hard_gate_keys=("clearance", "turn_rate", "strain", "thermal_gradient", "phase_purity"),
        residual_kinds=tuple(sorted({spec.residual_kind for spec in DOMAIN_SPECS})),
        sources=BRANCH_BOUNDARY_BRACKET_SOURCES,
        learning=(
            "Source reject/commit endpoints can narrow target exploration toward a verifier boundary, "
            "but the bracket is only a proposal-ordering hint. The target branch still needs its own "
            "hard-verifier receipt, replay audit, rollback audit, and claim certificate before boundary "
            "exploration lift is counted."
        ),
    )
    transfer_certificate = build_branch_boundary_bracket_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_boundary_bracket_certificate_hashes=tuple(certificate.certificate_hash for certificate in bracket_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_boundary_bracket_transfer",
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
        claim_boundary=BRANCH_BOUNDARY_BRACKET_CLAIM_BOUNDARY,
        sources=BRANCH_BOUNDARY_BRACKET_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchBoundaryBracketTransferResult(
        report=report,
        branch_boundary_bracket_transfer_certificate=transfer_certificate,
        branch_boundary_bracket_certificates=tuple(bracket_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_boundary_bracket_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    residual_kind: str,
    bracket_id: str,
    bracket_field_keys: tuple[str, ...],
    source_reject_action: str,
    source_safe_action: str,
    static_target_action: str,
    bracket_target_action: str,
    source_reject_receipt_hashes: tuple[str, ...],
    source_safe_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    bracket_target_receipt_hashes: tuple[str, ...],
    bracket_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    bracket_branch_selection_certificate_hash: str,
    source_rejected: bool,
    source_safe_committed: bool,
    static_committed: bool,
    bracket_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    bracket_verifier_call_count: int,
) -> BranchBoundaryBracketCertificate:
    return BranchBoundaryBracketCertificate(
        schema_version=BRANCH_BOUNDARY_BRACKET_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        bracket_rule_id="source_reject_commit_boundary_bracket",
        bracket_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        residual_kind=residual_kind,
        bracket_id=bracket_id,
        bracket_version="1.0",
        bracket_field_keys=bracket_field_keys,
        source_reject_action=source_reject_action,
        source_safe_action=source_safe_action,
        static_target_action=static_target_action,
        bracket_target_action=bracket_target_action,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_safe_receipt_hashes=source_safe_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        bracket_target_receipt_hashes=bracket_target_receipt_hashes,
        bracket_target_commit_receipt_hashes=bracket_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        bracket_branch_selection_certificate_hash=bracket_branch_selection_certificate_hash,
        source_rejected=source_rejected,
        source_safe_committed=source_safe_committed,
        static_committed=static_committed,
        bracket_committed=bracket_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        bracket_verifier_call_count=bracket_verifier_call_count,
        same_budget=static_verifier_call_count == bracket_verifier_call_count == 1,
        bracket_reason="source_reject_safe_pair_identifies_target_boundary_candidate",
    )


def validate_branch_boundary_bracket_certificate(
    certificate: BranchBoundaryBracketCertificate,
    row: BranchBoundaryBracketDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_BOUNDARY_BRACKET_CERTIFICATE_SCHEMA:
            return False
        if certificate.bracket_rule_id != "source_reject_commit_boundary_bracket":
            return False
        if certificate.bracket_rule_version != "1.0" or certificate.bracket_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.residual_kind,
            certificate.bracket_id,
            certificate.source_reject_action,
            certificate.source_safe_action,
            certificate.static_target_action,
            certificate.bracket_target_action,
        ):
            if not _nonempty(value):
                return False
        if not certificate.bracket_field_keys or any(not _nonempty(value) for value in certificate.bracket_field_keys):
            return False
        if len(set(certificate.bracket_field_keys)) != len(certificate.bracket_field_keys):
            return False
        if not certificate.source_rejected or not certificate.source_safe_committed:
            return False
        if certificate.static_committed or not certificate.bracket_committed:
            return False
        if certificate.source_verifier_call_count != 2:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.bracket_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.bracket_reason != "source_reject_safe_pair_identifies_target_boundary_candidate":
            return False
        for values in (
            certificate.source_reject_receipt_hashes,
            certificate.source_safe_receipt_hashes,
            certificate.static_target_receipt_hashes,
            certificate.bracket_target_receipt_hashes,
            certificate.bracket_target_commit_receipt_hashes,
        ):
            if len(values) != 1 or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.bracket_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.residual_kind != certificate.residual_kind:
                return False
            if row.bracket_id != certificate.bracket_id:
                return False
            if row.bracket_field_keys != certificate.bracket_field_keys:
                return False
            if row.source_reject_action != certificate.source_reject_action:
                return False
            if row.source_safe_action != certificate.source_safe_action:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.bracket_target_action != certificate.bracket_target_action:
                return False
            if row.source_rejected != certificate.source_rejected:
                return False
            if row.source_safe_committed != certificate.source_safe_committed:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.bracket_committed != certificate.bracket_committed:
                return False
            if row.source_verifier_call_count != certificate.source_verifier_call_count:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.bracket_verifier_call_count != certificate.bracket_verifier_call_count:
                return False
            if row.source_reject_receipt_hashes != certificate.source_reject_receipt_hashes:
                return False
            if row.source_safe_receipt_hashes != certificate.source_safe_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.bracket_target_receipt_hashes != certificate.bracket_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_boundary_bracket_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_boundary_bracket_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_boundary_bracket_transfer_certificate(
    report: BranchBoundaryBracketTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_boundary_bracket_certificate_hashes: tuple[str, ...],
) -> BranchBoundaryBracketTransferCertificate:
    return BranchBoundaryBracketTransferCertificate(
        schema_version=BRANCH_BOUNDARY_BRACKET_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_boundary_bracket_certificate_hashes=branch_boundary_bracket_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_reject_count=report.source_reject_count,
        source_safe_success_count=report.source_safe_success_count,
        static_success_count=report.static_success_count,
        bracket_success_count=report.bracket_success_count,
        same_budget_bracket_count=report.same_budget_bracket_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_BOUNDARY_BRACKET_CLAIM_BOUNDARY,
    )


def validate_branch_boundary_bracket_transfer_certificate(
    certificate: BranchBoundaryBracketTransferCertificate,
    report: BranchBoundaryBracketTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_BOUNDARY_BRACKET_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_boundary_bracket_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_boundary_bracket_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_reject_count != certificate.domain_count:
            return False
        if certificate.source_safe_success_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.bracket_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_bracket_count != certificate.domain_count:
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
            if tuple(row.branch_boundary_bracket_certificate_hash for row in report.rows) != certificate.branch_boundary_bracket_certificate_hashes:
                return False
            if report.branch_boundary_bracket_certificate_count != len(certificate.branch_boundary_bracket_certificate_hashes):
                return False
            if not report.all_branch_boundary_bracket_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_reject_count != certificate.source_reject_count:
                return False
            if report.source_safe_success_count != certificate.source_safe_success_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.bracket_success_count != certificate.bracket_success_count:
                return False
            if report.same_budget_bracket_count != certificate.same_budget_bracket_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_boundary_bracket_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_boundary_bracket_certificate_hash(
    certificate: BranchBoundaryBracketCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchBoundaryBracketCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_boundary_bracket_transfer_certificate_hash(
    certificate: BranchBoundaryBracketTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchBoundaryBracketTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchBoundaryBracketTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchBoundaryBracketTransferReport,
    transfer_certificate: BranchBoundaryBracketTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_boundary_bracket_transfer_g1",
        claim_text=(
            "Past source reject/commit endpoints can improve local target exploration by certifying a "
            "boundary bracket, while target commit authority remains with fresh hard verification."
        ),
        evidence_grade="G1",
        scope="branch_boundary_bracket_transfer",
        requirements=(
            requirement(
                "branch_boundary_bracket_transfer_certificate_valid",
                validate_branch_boundary_bracket_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_boundary_bracket_certificates_valid", report.all_branch_boundary_bracket_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_rejects_all_domains", report.source_reject_count == report.domain_count),
            requirement("source_safe_commits_all_domains", report.source_safe_success_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("brackets_succeed_all_domains", report.bracket_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_bracket_count == report.domain_count),
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
            "source_safe_success_count": report.source_safe_success_count,
            "static_success_count": report.static_success_count,
            "bracket_success_count": report.bracket_success_count,
        },
        boundary=BRANCH_BOUNDARY_BRACKET_CLAIM_BOUNDARY,
        sources=BRANCH_BOUNDARY_BRACKET_SOURCES,
    )


def _make_bracket_traces(
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
            seeds=("branch-boundary-bracket-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.boundary.bracket.transfer.v1",
        )
        for action in actions
    )


def _domain_bracket_plan(
    spec: ExplorationDomainSpec,
    source_context: str,
    target_context: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "bracket_id": "clearance_turn_boundary_bracket",
            "bracket_field_keys": ("clearance", "turn_rate"),
            "source_reject": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "bracket_source_tight_cut",
                "utility": 9,
                "clearance": 0.18,
                "turn_rate": 0.68,
            },
            "source_safe": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "bracket_source_safe_detour",
                "utility": 8,
                "clearance": 0.38,
                "turn_rate": 0.45,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "bracket_target_tight_cut",
                "utility": 9,
                "clearance": 0.20,
                "turn_rate": 0.66,
            },
            "target_bracket": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "bracket_target_threshold_detour",
                "utility": 8,
                "clearance": 0.26,
                "turn_rate": 0.58,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "bracket_id": "strain_threshold_bracket",
            "bracket_field_keys": ("strain",),
            "source_reject": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "bracket_source_high_strain",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.44,
            },
            "source_safe": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "bracket_source_low_strain",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.20,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "bracket_target_high_strain",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.42,
            },
            "target_bracket": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "bracket_target_threshold_strain",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.34,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "bracket_id": "thermal_phase_boundary_bracket",
            "bracket_field_keys": ("thermal_gradient", "phase_purity"),
            "source_reject": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "bracket_source_hot_impure",
                "utility": 9,
                "thermal_gradient": 0.70,
                "phase_purity": 0.88,
            },
            "source_safe": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "bracket_source_cool_pure",
                "utility": 8,
                "thermal_gradient": 0.36,
                "phase_purity": 0.95,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "bracket_target_hot_impure",
                "utility": 9,
                "thermal_gradient": 0.64,
                "phase_purity": 0.89,
            },
            "target_bracket": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "bracket_target_boundary_window",
                "utility": 8,
                "thermal_gradient": 0.49,
                "phase_purity": 0.91,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_boundary_bracket_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
