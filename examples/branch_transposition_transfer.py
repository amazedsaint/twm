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


BRANCH_TRANSPOSITION_CERTIFICATE_SCHEMA = "trwm.branch_transposition_certificate.v1"
BRANCH_TRANSPOSITION_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_transposition_transfer_certificate.v1"
BRANCH_TRANSPOSITION_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://journals.sagepub.com/doi/10.3233/ICG-1990-13203",
    "https://aaai.org/Papers/AAAI/2004/AAAI04-108.pdf",
)
BRANCH_TRANSPOSITION_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound canonical "
    "state signatures can filter duplicate known-bad target proposals before target exploration "
    "under a matched one-call verifier budget. It is not a transposition-table performance "
    "result, Zobrist-hashing implementation, duplicate-detection algorithm, graph-search "
    "scalability result, robotics safety, chemistry, materials discovery, or scientific "
    "autonomy evidence."
)


@dataclass(frozen=True)
class BranchTranspositionCertificate:
    schema_version: str
    domain: str
    transposition_rule_id: str
    transposition_rule_version: str
    source_context_id: str
    target_context_id: str
    canonical_state_key: str
    source_duplicate_action_id: str
    source_alternative_action_id: str
    static_target_action: str
    transposition_target_action: str
    source_duplicate_receipt_hashes: tuple[str, ...]
    source_alternative_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    transposition_target_receipt_hashes: tuple[str, ...]
    transposition_target_commit_receipt_hashes: tuple[str, ...]
    source_duplicate_branch_selection_certificate_hash: str
    source_alternative_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    transposition_branch_selection_certificate_hash: str
    source_duplicate_rejected: bool
    source_alternative_committed: bool
    static_duplicate_rejected: bool
    transposition_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    transposition_verifier_call_count: int
    same_budget: bool
    duplicate_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_TRANSPOSITION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch transposition certificate schema: {self.schema_version}")
        for field_name in (
            "source_duplicate_receipt_hashes",
            "source_alternative_receipt_hashes",
            "static_target_receipt_hashes",
            "transposition_target_receipt_hashes",
            "transposition_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_transposition_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchTranspositionDomainReport:
    domain: str
    source_context: str
    target_context: str
    canonical_state_key: str
    source_duplicate_action_id: str
    source_alternative_action_id: str
    static_target_action: str
    transposition_target_action: str
    source_duplicate_rejected: bool
    source_alternative_committed: bool
    static_duplicate_rejected: bool
    transposition_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    transposition_verifier_call_count: int
    source_duplicate_receipt_hashes: tuple[str, ...]
    source_alternative_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    transposition_target_receipt_hashes: tuple[str, ...]
    branch_transposition_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchTranspositionTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchTranspositionDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_duplicate_rejected_count: int
    source_alternative_committed_count: int
    static_success_count: int
    transposition_success_count: int
    same_budget_transposition_count: int
    branch_transposition_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_transposition_certificates_valid: bool
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
class BranchTranspositionTransferCertificate:
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
    branch_transposition_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_duplicate_rejected_count: int
    source_alternative_committed_count: int
    static_success_count: int
    transposition_success_count: int
    same_budget_transposition_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_TRANSPOSITION_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch transposition transfer certificate schema: {self.schema_version}")
        for field_name in ("domains", "receipt_hashes", "branch_selection_certificate_hashes", "branch_transposition_certificate_hashes"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_transposition_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchTranspositionTransferResult(CertifiedExampleResult):
    report: BranchTranspositionTransferReport
    branch_transposition_transfer_certificate: BranchTranspositionTransferCertificate
    branch_transposition_certificates: tuple[BranchTranspositionCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_transposition_transfer_experiment() -> BranchTranspositionTransferReport:
    return run_branch_transposition_transfer_certified_experiment().report


def run_branch_transposition_transfer_certified_experiment() -> CertifiedBranchTranspositionTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchTranspositionDomainReport] = []
    transposition_certificates: list[BranchTranspositionCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_transposition_plan(spec)
        source_context = f"{spec.domain_id}:source:branch-transposition"
        target_context = f"{spec.domain_id}:target:branch-transposition"

        source_duplicate_outcome = runtime.step(
            state,
            _make_transposition_traces(spec, context=source_context, phase="source-duplicate", actions=(plan["source_duplicate"],)),
        )
        source_duplicate_selection = build_branch_selection_certificate(
            source_duplicate_outcome.receipts,
            verifier_call_count=source_duplicate_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_duplicate_outcome.receipts), source_duplicate_selection))
        memory.update_branch(source_duplicate_outcome.receipts, source_duplicate_selection)

        source_alternative_outcome = runtime.step(
            state,
            _make_transposition_traces(spec, context=source_context, phase="source-alternative", actions=(plan["source_alternative"],)),
        )
        state = normalize_state(source_alternative_outcome.state)
        source_alternative_selection = build_branch_selection_certificate(
            source_alternative_outcome.receipts,
            verifier_call_count=source_alternative_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_alternative_outcome.receipts), source_alternative_selection))
        memory.update_branch(source_alternative_outcome.receipts, source_alternative_selection)

        static_outcome = runtime.step(
            state,
            _make_transposition_traces(spec, context=target_context, phase="target-static-duplicate", actions=(plan["target_static"],)),
        )
        static_selection = build_branch_selection_certificate(static_outcome.receipts, verifier_call_count=static_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        transposition_outcome = runtime.step(
            state,
            _make_transposition_traces(spec, context=target_context, phase="target-transposition", actions=(plan["target_transposition"],)),
        )
        state = normalize_state(transposition_outcome.state)
        transposition_selection = build_branch_selection_certificate(
            transposition_outcome.receipts,
            verifier_call_count=transposition_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(transposition_outcome.receipts), transposition_selection))

        certificate = build_branch_transposition_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            canonical_state_key=str(plan["canonical_state_key"]),
            source_duplicate_action_id=str(plan["source_duplicate"]["action"]),
            source_alternative_action_id=str(plan["source_alternative"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            transposition_target_action=str(plan["target_transposition"]["action"]),
            source_duplicate_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_duplicate_outcome.receipts),
            source_alternative_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_alternative_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            transposition_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in transposition_outcome.receipts),
            transposition_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in transposition_outcome.receipts if receipt.committed
            ),
            source_duplicate_branch_selection_certificate_hash=source_duplicate_selection.certificate_hash,
            source_alternative_branch_selection_certificate_hash=source_alternative_selection.certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            transposition_branch_selection_certificate_hash=transposition_selection.certificate_hash,
            source_duplicate_rejected=any(receipt.hard_result.rejected for receipt in source_duplicate_outcome.receipts),
            source_alternative_committed=source_alternative_outcome.committed,
            static_duplicate_rejected=any(receipt.hard_result.rejected for receipt in static_outcome.receipts),
            transposition_committed=transposition_outcome.committed,
            source_verifier_call_count=source_duplicate_outcome.verifier_calls + source_alternative_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            transposition_verifier_call_count=transposition_outcome.verifier_calls,
        )
        transposition_certificates.append(certificate)
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

    report = BranchTranspositionTransferReport(
        schema_version="trwm.example.branch_transposition_transfer.v1",
        experiment_id="branch_transposition_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_duplicate_rejected_count=sum(1 for row in rows if row.source_duplicate_rejected),
        source_alternative_committed_count=sum(1 for row in rows if row.source_alternative_committed),
        static_success_count=sum(1 for row in rows if not row.static_duplicate_rejected),
        transposition_success_count=sum(1 for row in rows if row.transposition_committed),
        same_budget_transposition_count=sum(1 for row in rows if row.same_budget),
        branch_transposition_certificate_count=len(transposition_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_transposition_certificates_valid=all(
            validate_branch_transposition_certificate(certificate, row)
            for certificate, row in zip(transposition_certificates, rows)
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
        sources=BRANCH_TRANSPOSITION_SOURCES,
        learning=(
            "Transposition reuse separates canonical duplicate evidence from commit authority. Source receipts "
            "can mark a canonical state as already rejected and rank a non-duplicate target branch first, "
            "but the target branch still commits only through a fresh hard-verifier receipt."
        ),
    )
    transfer_certificate = build_branch_transposition_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_transposition_certificate_hashes=tuple(certificate.certificate_hash for certificate in transposition_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_transposition_transfer",
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
        claim_boundary=BRANCH_TRANSPOSITION_CLAIM_BOUNDARY,
        sources=BRANCH_TRANSPOSITION_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchTranspositionTransferResult(
        report=report,
        branch_transposition_transfer_certificate=transfer_certificate,
        branch_transposition_certificates=tuple(transposition_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_transposition_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    canonical_state_key: str,
    source_duplicate_action_id: str,
    source_alternative_action_id: str,
    static_target_action: str,
    transposition_target_action: str,
    source_duplicate_receipt_hashes: tuple[str, ...],
    source_alternative_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    transposition_target_receipt_hashes: tuple[str, ...],
    transposition_target_commit_receipt_hashes: tuple[str, ...],
    source_duplicate_branch_selection_certificate_hash: str,
    source_alternative_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    transposition_branch_selection_certificate_hash: str,
    source_duplicate_rejected: bool,
    source_alternative_committed: bool,
    static_duplicate_rejected: bool,
    transposition_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    transposition_verifier_call_count: int,
) -> BranchTranspositionCertificate:
    return BranchTranspositionCertificate(
        schema_version=BRANCH_TRANSPOSITION_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        transposition_rule_id="receipt_bound_canonical_transposition",
        transposition_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        canonical_state_key=canonical_state_key,
        source_duplicate_action_id=source_duplicate_action_id,
        source_alternative_action_id=source_alternative_action_id,
        static_target_action=static_target_action,
        transposition_target_action=transposition_target_action,
        source_duplicate_receipt_hashes=source_duplicate_receipt_hashes,
        source_alternative_receipt_hashes=source_alternative_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        transposition_target_receipt_hashes=transposition_target_receipt_hashes,
        transposition_target_commit_receipt_hashes=transposition_target_commit_receipt_hashes,
        source_duplicate_branch_selection_certificate_hash=source_duplicate_branch_selection_certificate_hash,
        source_alternative_branch_selection_certificate_hash=source_alternative_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        transposition_branch_selection_certificate_hash=transposition_branch_selection_certificate_hash,
        source_duplicate_rejected=source_duplicate_rejected,
        source_alternative_committed=source_alternative_committed,
        static_duplicate_rejected=static_duplicate_rejected,
        transposition_committed=transposition_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        transposition_verifier_call_count=transposition_verifier_call_count,
        same_budget=static_verifier_call_count == transposition_verifier_call_count == 1,
        duplicate_reason="target_static_reaches_source_rejected_canonical_state",
    )


def validate_branch_transposition_certificate(
    certificate: BranchTranspositionCertificate,
    row: BranchTranspositionDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_TRANSPOSITION_CERTIFICATE_SCHEMA:
            return False
        if certificate.transposition_rule_id != "receipt_bound_canonical_transposition":
            return False
        if certificate.transposition_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.canonical_state_key):
            return False
        if certificate.source_duplicate_action_id == certificate.source_alternative_action_id:
            return False
        if certificate.static_target_action == certificate.transposition_target_action:
            return False
        if not (
            certificate.source_duplicate_rejected
            and certificate.source_alternative_committed
            and certificate.static_duplicate_rejected
            and certificate.transposition_committed
        ):
            return False
        if certificate.source_verifier_call_count != 2:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.transposition_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.duplicate_reason != "target_static_reaches_source_rejected_canonical_state":
            return False
        hash_groups = (
            (certificate.source_duplicate_receipt_hashes, 1),
            (certificate.source_alternative_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.transposition_target_receipt_hashes, 1),
            (certificate.transposition_target_commit_receipt_hashes, 1),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_duplicate_branch_selection_certificate_hash,
            certificate.source_alternative_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.transposition_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.canonical_state_key != certificate.canonical_state_key:
                return False
            if row.source_duplicate_action_id != certificate.source_duplicate_action_id:
                return False
            if row.source_alternative_action_id != certificate.source_alternative_action_id:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.transposition_target_action != certificate.transposition_target_action:
                return False
            if row.source_duplicate_receipt_hashes != certificate.source_duplicate_receipt_hashes:
                return False
            if row.source_alternative_receipt_hashes != certificate.source_alternative_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.transposition_target_receipt_hashes != certificate.transposition_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_transposition_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_transposition_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_transposition_transfer_certificate(
    report: BranchTranspositionTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_transposition_certificate_hashes: tuple[str, ...],
) -> BranchTranspositionTransferCertificate:
    return BranchTranspositionTransferCertificate(
        schema_version=BRANCH_TRANSPOSITION_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_transposition_certificate_hashes=branch_transposition_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_duplicate_rejected_count=report.source_duplicate_rejected_count,
        source_alternative_committed_count=report.source_alternative_committed_count,
        static_success_count=report.static_success_count,
        transposition_success_count=report.transposition_success_count,
        same_budget_transposition_count=report.same_budget_transposition_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_TRANSPOSITION_CLAIM_BOUNDARY,
    )


def validate_branch_transposition_transfer_certificate(
    certificate: BranchTranspositionTransferCertificate,
    report: BranchTranspositionTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_TRANSPOSITION_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        if not _is_hash(certificate.report_hash) or not _is_hash(certificate.ledger_head):
            return False
        if not _is_hash(certificate.memory_snapshot_hash):
            return False
        for values in (certificate.receipt_hashes, certificate.branch_selection_certificate_hashes, certificate.branch_transposition_certificate_hashes):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_transposition_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_duplicate_rejected_count != certificate.domain_count:
            return False
        if certificate.source_alternative_committed_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.transposition_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_transposition_count != certificate.domain_count:
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
            if tuple(row.branch_transposition_certificate_hash for row in report.rows) != certificate.branch_transposition_certificate_hashes:
                return False
            if report.branch_transposition_certificate_count != len(certificate.branch_transposition_certificate_hashes):
                return False
            if not report.all_branch_transposition_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_duplicate_rejected_count != certificate.source_duplicate_rejected_count:
                return False
            if report.source_alternative_committed_count != certificate.source_alternative_committed_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.transposition_success_count != certificate.transposition_success_count:
                return False
            if report.same_budget_transposition_count != certificate.same_budget_transposition_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_transposition_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_transposition_certificate_hash(certificate: BranchTranspositionCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchTranspositionCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_transposition_transfer_certificate_hash(
    certificate: BranchTranspositionTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchTranspositionTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchTranspositionTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchTranspositionTransferReport,
    transfer_certificate: BranchTranspositionTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_transposition_transfer_g1",
        claim_text=(
            "Receipt-bound canonical transposition certificates can improve local target exploration "
            "by filtering duplicate known-bad target states and trying non-duplicate branches under "
            "matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_transposition_transfer",
        requirements=(
            requirement(
                "branch_transposition_transfer_certificate_valid",
                validate_branch_transposition_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_transposition_certificates_valid", report.all_branch_transposition_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_duplicates_reject_all_domains", report.source_duplicate_rejected_count == report.domain_count),
            requirement("source_alternatives_commit_all_domains", report.source_alternative_committed_count == report.domain_count),
            requirement("static_duplicates_fail_all_domains", report.static_success_count == 0),
            requirement("transposition_succeeds_all_domains", report.transposition_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_transposition_count == report.domain_count),
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
            "transposition_success_count": report.transposition_success_count,
        },
        boundary=BRANCH_TRANSPOSITION_CLAIM_BOUNDARY,
        sources=BRANCH_TRANSPOSITION_SOURCES,
    )


def _row_from_certificate(certificate: BranchTranspositionCertificate) -> BranchTranspositionDomainReport:
    return BranchTranspositionDomainReport(
        domain=certificate.domain,
        source_context=certificate.source_context_id,
        target_context=certificate.target_context_id,
        canonical_state_key=certificate.canonical_state_key,
        source_duplicate_action_id=certificate.source_duplicate_action_id,
        source_alternative_action_id=certificate.source_alternative_action_id,
        static_target_action=certificate.static_target_action,
        transposition_target_action=certificate.transposition_target_action,
        source_duplicate_rejected=certificate.source_duplicate_rejected,
        source_alternative_committed=certificate.source_alternative_committed,
        static_duplicate_rejected=certificate.static_duplicate_rejected,
        transposition_committed=certificate.transposition_committed,
        source_verifier_call_count=certificate.source_verifier_call_count,
        static_verifier_call_count=certificate.static_verifier_call_count,
        transposition_verifier_call_count=certificate.transposition_verifier_call_count,
        source_duplicate_receipt_hashes=certificate.source_duplicate_receipt_hashes,
        source_alternative_receipt_hashes=certificate.source_alternative_receipt_hashes,
        static_target_receipt_hashes=certificate.static_target_receipt_hashes,
        transposition_target_receipt_hashes=certificate.transposition_target_receipt_hashes,
        branch_transposition_certificate_hash=certificate.certificate_hash,
        same_budget=certificate.same_budget,
    )


def _make_transposition_traces(
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
            seeds=("branch-transposition-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.transposition.transfer.v1",
        )
        for action in actions
    )


def _domain_transposition_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    canonical_state_key = f"{spec.domain_id}:duplicate:hard_reject_state"
    if spec.domain_id == "robotics_replan":
        return {
            "canonical_state_key": canonical_state_key,
            "source_duplicate": {"domain": spec.domain_id, "action": "trans_source_alias_cut_a", "utility": 9, "canonical_state_key": canonical_state_key, "clearance": 0.12, "turn_rate": 0.78},
            "source_alternative": {"domain": spec.domain_id, "action": "trans_source_clear_detour", "utility": 8, "canonical_state_key": f"{spec.domain_id}:detour_state", "clearance": 0.34, "turn_rate": 0.42},
            "target_static": {"domain": spec.domain_id, "action": "trans_target_alias_cut_b", "utility": 9, "canonical_state_key": canonical_state_key, "clearance": 0.14, "turn_rate": 0.80},
            "target_transposition": {"domain": spec.domain_id, "action": "trans_target_clear_detour", "utility": 8, "canonical_state_key": f"{spec.domain_id}:target_detour_state", "clearance": 0.36, "turn_rate": 0.43},
        }
    if spec.domain_id == "molecule_repair":
        return {
            "canonical_state_key": canonical_state_key,
            "source_duplicate": {"domain": spec.domain_id, "action": "trans_source_alias_valence_a", "utility": 9, "canonical_state_key": canonical_state_key, "valence_ok": False, "strain": 0.32},
            "source_alternative": {"domain": spec.domain_id, "action": "trans_source_valence_relief", "utility": 8, "canonical_state_key": f"{spec.domain_id}:relief_state", "valence_ok": True, "strain": 0.20},
            "target_static": {"domain": spec.domain_id, "action": "trans_target_alias_valence_b", "utility": 9, "canonical_state_key": canonical_state_key, "valence_ok": False, "strain": 0.31},
            "target_transposition": {"domain": spec.domain_id, "action": "trans_target_valence_relief", "utility": 8, "canonical_state_key": f"{spec.domain_id}:target_relief_state", "valence_ok": True, "strain": 0.18},
        }
    if spec.domain_id == "material_process":
        return {
            "canonical_state_key": canonical_state_key,
            "source_duplicate": {"domain": spec.domain_id, "action": "trans_source_alias_flash_a", "utility": 9, "canonical_state_key": canonical_state_key, "thermal_gradient": 0.74, "phase_purity": 0.86},
            "source_alternative": {"domain": spec.domain_id, "action": "trans_source_tempered_path", "utility": 8, "canonical_state_key": f"{spec.domain_id}:tempered_state", "thermal_gradient": 0.40, "phase_purity": 0.95},
            "target_static": {"domain": spec.domain_id, "action": "trans_target_alias_flash_b", "utility": 9, "canonical_state_key": canonical_state_key, "thermal_gradient": 0.72, "phase_purity": 0.87},
            "target_transposition": {"domain": spec.domain_id, "action": "trans_target_tempered_path", "utility": 8, "canonical_state_key": f"{spec.domain_id}:target_tempered_state", "thermal_gradient": 0.38, "phase_purity": 0.96},
        }
    raise ValueError(f"unknown transposition domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_transposition_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
