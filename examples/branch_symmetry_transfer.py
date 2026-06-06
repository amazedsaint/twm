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


BRANCH_SYMMETRY_CERTIFICATE_SCHEMA = "trwm.branch_symmetry_certificate.v1"
BRANCH_SYMMETRY_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_symmetry_transfer_certificate.v1"
BRANCH_SYMMETRY_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://arxiv.org/abs/1602.07576",
)
BRANCH_SYMMETRY_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows a typed symmetry transform can "
    "map a committed source branch into a target action that succeeds under the same one-call "
    "verifier budget while exact source-action replay fails. It is not an equivariant neural-network "
    "result, group-theory proof, automatic symmetry search, robotics safety, chemistry, materials "
    "discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchSymmetryCertificate:
    schema_version: str
    domain: str
    symmetry_rule_id: str
    symmetry_rule_version: str
    symmetry_transform_id: str
    source_context_id: str
    target_context_id: str
    source_action: str
    exact_replay_action: str
    symmetry_action: str
    source_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    symmetry_target_receipt_hashes: tuple[str, ...]
    symmetry_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    symmetry_branch_selection_certificate_hash: str
    exact_replay_committed: bool
    symmetry_committed: bool
    exact_replay_verifier_call_count: int
    symmetry_verifier_call_count: int
    same_budget: bool
    transform_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SYMMETRY_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch symmetry certificate schema: {self.schema_version}")
        for field_name in (
            "source_commit_receipt_hashes",
            "static_target_receipt_hashes",
            "symmetry_target_receipt_hashes",
            "symmetry_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_symmetry_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchSymmetryDomainReport:
    domain: str
    source_context: str
    target_context: str
    symmetry_transform_id: str
    source_action: str
    exact_replay_action: str
    symmetry_action: str
    source_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    symmetry_target_receipt_hashes: tuple[str, ...]
    exact_replay_committed: bool
    symmetry_committed: bool
    exact_replay_verifier_call_count: int
    symmetry_verifier_call_count: int
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    symmetry_branch_selection_certificate_hash: str
    symmetry_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchSymmetryTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchSymmetryDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_commit_count: int
    static_success_count: int
    symmetry_success_count: int
    same_budget_symmetry_count: int
    branch_symmetry_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_symmetry_certificates_valid: bool
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
class BranchSymmetryTransferCertificate:
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
    branch_symmetry_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_commit_count: int
    static_success_count: int
    symmetry_success_count: int
    same_budget_symmetry_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SYMMETRY_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch symmetry transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_symmetry_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_symmetry_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchSymmetryTransferResult(CertifiedExampleResult):
    report: BranchSymmetryTransferReport
    branch_symmetry_transfer_certificate: BranchSymmetryTransferCertificate
    branch_symmetry_certificates: tuple[BranchSymmetryCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_symmetry_transfer_experiment() -> BranchSymmetryTransferReport:
    return run_branch_symmetry_transfer_certified_experiment().report


def run_branch_symmetry_transfer_certified_experiment() -> CertifiedBranchSymmetryTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchSymmetryDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    symmetry_certificates: list[BranchSymmetryCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:symmetry"
        target_context = f"{spec.domain_id}:target:symmetry"
        action_map = _symmetry_actions(spec)
        source_action = _with_context(action_map["source"], source_context)
        exact_replay_action = _with_context(action_map["exact"], target_context)
        symmetry_action = _with_context(action_map["symmetry"], target_context)

        source_outcome = runtime.step(
            state,
            _make_symmetry_traces(
                spec,
                context=source_context,
                phase="source-symmetry-evidence",
                actions=(source_action,),
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
            _make_symmetry_traces(
                spec,
                context=target_context,
                phase="target-exact-replay",
                actions=(exact_replay_action,),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        symmetry_outcome = runtime.step(
            state,
            _make_symmetry_traces(
                spec,
                context=target_context,
                phase="target-symmetry-transform",
                actions=(symmetry_action,),
            ),
        )
        state = normalize_state(symmetry_outcome.state)
        symmetry_branch_certificate = build_branch_selection_certificate(
            symmetry_outcome.receipts,
            verifier_call_count=symmetry_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(symmetry_outcome.receipts), symmetry_branch_certificate))

        certificate = build_branch_symmetry_certificate(
            spec,
            symmetry_transform_id=str(action_map["transform_id"]),
            source_context_id=source_context,
            target_context_id=target_context,
            source_action=str(source_action["action"]),
            exact_replay_action=str(exact_replay_action["action"]),
            symmetry_action=str(symmetry_action["action"]),
            source_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            symmetry_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in symmetry_outcome.receipts),
            symmetry_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in symmetry_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            symmetry_branch_selection_certificate_hash=symmetry_branch_certificate.certificate_hash,
            exact_replay_committed=static_outcome.committed,
            symmetry_committed=symmetry_outcome.committed,
            exact_replay_verifier_call_count=static_outcome.verifier_calls,
            symmetry_verifier_call_count=symmetry_outcome.verifier_calls,
        )
        symmetry_certificates.append(certificate)
        rows.append(
            BranchSymmetryDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                symmetry_transform_id=certificate.symmetry_transform_id,
                source_action=certificate.source_action,
                exact_replay_action=certificate.exact_replay_action,
                symmetry_action=certificate.symmetry_action,
                source_commit_receipt_hashes=certificate.source_commit_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                symmetry_target_receipt_hashes=certificate.symmetry_target_receipt_hashes,
                exact_replay_committed=certificate.exact_replay_committed,
                symmetry_committed=certificate.symmetry_committed,
                exact_replay_verifier_call_count=certificate.exact_replay_verifier_call_count,
                symmetry_verifier_call_count=certificate.symmetry_verifier_call_count,
                source_branch_selection_certificate_hash=certificate.source_branch_selection_certificate_hash,
                static_branch_selection_certificate_hash=certificate.static_branch_selection_certificate_hash,
                symmetry_branch_selection_certificate_hash=certificate.symmetry_branch_selection_certificate_hash,
                symmetry_certificate_hash=certificate.certificate_hash,
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

    report = BranchSymmetryTransferReport(
        schema_version="trwm.example.branch_symmetry_transfer.v1",
        experiment_id="branch_symmetry_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_commit_count=sum(len(row.source_commit_receipt_hashes) for row in rows),
        static_success_count=sum(1 for row in rows if row.exact_replay_committed),
        symmetry_success_count=sum(1 for row in rows if row.symmetry_committed),
        same_budget_symmetry_count=sum(1 for row in rows if row.same_budget),
        branch_symmetry_certificate_count=len(symmetry_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_symmetry_certificates_valid=all(
            validate_branch_symmetry_certificate(certificate, row)
            for certificate, row in zip(symmetry_certificates, rows)
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
        sources=BRANCH_SYMMETRY_SOURCES,
        learning=(
            "Branch history can improve exploration when it carries a typed transform rather than only "
            "an action token. Exact source-action replay fails in each mirrored target, while the "
            "receipt-bound symmetry action commits under the same one-call verifier budget."
        ),
    )
    transfer_certificate = build_branch_symmetry_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_symmetry_certificate_hashes=tuple(certificate.certificate_hash for certificate in symmetry_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_symmetry_transfer",
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
        claim_boundary=BRANCH_SYMMETRY_CLAIM_BOUNDARY,
        sources=BRANCH_SYMMETRY_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchSymmetryTransferResult(
        report=report,
        branch_symmetry_transfer_certificate=transfer_certificate,
        branch_symmetry_certificates=tuple(symmetry_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_symmetry_certificate(
    spec: ExplorationDomainSpec,
    *,
    symmetry_transform_id: str,
    source_context_id: str,
    target_context_id: str,
    source_action: str,
    exact_replay_action: str,
    symmetry_action: str,
    source_commit_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    symmetry_target_receipt_hashes: tuple[str, ...],
    symmetry_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    symmetry_branch_selection_certificate_hash: str,
    exact_replay_committed: bool,
    symmetry_committed: bool,
    exact_replay_verifier_call_count: int,
    symmetry_verifier_call_count: int,
) -> BranchSymmetryCertificate:
    return BranchSymmetryCertificate(
        schema_version=BRANCH_SYMMETRY_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        symmetry_rule_id="typed_symmetry_transform",
        symmetry_rule_version="1.0",
        symmetry_transform_id=symmetry_transform_id,
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        source_action=source_action,
        exact_replay_action=exact_replay_action,
        symmetry_action=symmetry_action,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        symmetry_target_receipt_hashes=symmetry_target_receipt_hashes,
        symmetry_target_commit_receipt_hashes=symmetry_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        symmetry_branch_selection_certificate_hash=symmetry_branch_selection_certificate_hash,
        exact_replay_committed=exact_replay_committed,
        symmetry_committed=symmetry_committed,
        exact_replay_verifier_call_count=exact_replay_verifier_call_count,
        symmetry_verifier_call_count=symmetry_verifier_call_count,
        same_budget=exact_replay_verifier_call_count == symmetry_verifier_call_count == 1,
        transform_reason="source_branch_mapped_by_typed_symmetry",
    )


def validate_branch_symmetry_certificate(
    certificate: BranchSymmetryCertificate,
    row: BranchSymmetryDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_SYMMETRY_CERTIFICATE_SCHEMA:
            return False
        if certificate.symmetry_rule_id != "typed_symmetry_transform":
            return False
        if certificate.symmetry_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.symmetry_transform_id,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.source_action,
            certificate.exact_replay_action,
            certificate.symmetry_action,
            certificate.transform_reason,
        ):
            if not _nonempty(value):
                return False
        if certificate.source_action != certificate.exact_replay_action:
            return False
        if certificate.source_action == certificate.symmetry_action:
            return False
        if certificate.exact_replay_committed or not certificate.symmetry_committed:
            return False
        if certificate.exact_replay_verifier_call_count != 1 or certificate.symmetry_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.transform_reason != "source_branch_mapped_by_typed_symmetry":
            return False
        for values, expected_len in (
            (certificate.source_commit_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.symmetry_target_receipt_hashes, 1),
            (certificate.symmetry_target_commit_receipt_hashes, 1),
        ):
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.symmetry_branch_selection_certificate_hash,
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
            if row.symmetry_transform_id != certificate.symmetry_transform_id:
                return False
            if row.source_action != certificate.source_action:
                return False
            if row.exact_replay_action != certificate.exact_replay_action:
                return False
            if row.symmetry_action != certificate.symmetry_action:
                return False
            if row.source_commit_receipt_hashes != certificate.source_commit_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.symmetry_target_receipt_hashes != certificate.symmetry_target_receipt_hashes:
                return False
            if row.exact_replay_committed != certificate.exact_replay_committed:
                return False
            if row.symmetry_committed != certificate.symmetry_committed:
                return False
            if row.exact_replay_verifier_call_count != certificate.exact_replay_verifier_call_count:
                return False
            if row.symmetry_verifier_call_count != certificate.symmetry_verifier_call_count:
                return False
            if row.source_branch_selection_certificate_hash != certificate.source_branch_selection_certificate_hash:
                return False
            if row.static_branch_selection_certificate_hash != certificate.static_branch_selection_certificate_hash:
                return False
            if row.symmetry_branch_selection_certificate_hash != certificate.symmetry_branch_selection_certificate_hash:
                return False
            if row.symmetry_certificate_hash != certificate.certificate_hash:
                return False
            if row.same_budget != certificate.same_budget:
                return False
        return certificate.certificate_hash == branch_symmetry_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_symmetry_transfer_certificate(
    report: BranchSymmetryTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_symmetry_certificate_hashes: tuple[str, ...],
) -> BranchSymmetryTransferCertificate:
    return BranchSymmetryTransferCertificate(
        schema_version=BRANCH_SYMMETRY_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_symmetry_certificate_hashes=branch_symmetry_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_commit_count=report.source_commit_count,
        static_success_count=report.static_success_count,
        symmetry_success_count=report.symmetry_success_count,
        same_budget_symmetry_count=report.same_budget_symmetry_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_SYMMETRY_CLAIM_BOUNDARY,
    )


def validate_branch_symmetry_transfer_certificate(
    certificate: BranchSymmetryTransferCertificate,
    report: BranchSymmetryTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_SYMMETRY_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_symmetry_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_symmetry_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_commit_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.symmetry_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_symmetry_count != certificate.domain_count:
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
            if not report.all_branch_symmetry_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_commit_count != certificate.source_commit_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.symmetry_success_count != certificate.symmetry_success_count:
                return False
            if report.same_budget_symmetry_count != certificate.same_budget_symmetry_count:
                return False
        return certificate.certificate_hash == branch_symmetry_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_symmetry_certificate_hash(certificate: BranchSymmetryCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchSymmetryCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_symmetry_transfer_certificate_hash(
    certificate: BranchSymmetryTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchSymmetryTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchSymmetryTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchSymmetryTransferReport,
    transfer_certificate: BranchSymmetryTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_symmetry_transfer_g1",
        claim_text=(
            "A typed symmetry transform can improve local target exploration when exact source-action "
            "replay fails under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_symmetry_transfer",
        requirements=(
            requirement(
                "branch_symmetry_transfer_certificate_valid",
                validate_branch_symmetry_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid),
            requirement("all_branch_symmetry_certificates_valid", report.all_branch_symmetry_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_commits_bound", report.source_commit_count == report.domain_count),
            requirement("exact_replay_fails_all_domains", report.static_success_count == 0),
            requirement("symmetry_succeeds_all_domains", report.symmetry_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_symmetry_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_commit_count": report.source_commit_count,
            "static_success_count": report.static_success_count,
            "symmetry_success_count": report.symmetry_success_count,
        },
        boundary=BRANCH_SYMMETRY_CLAIM_BOUNDARY,
        sources=BRANCH_SYMMETRY_SOURCES,
    )


def _make_symmetry_traces(
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
            seeds=("branch-symmetry-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.symmetry.transfer.v1",
        )
        for action in actions
    )


def _symmetry_actions(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "transform_id": "mirror_y_axis",
            "source": {
                "domain": spec.domain_id,
                "action": "left_wall_detour",
                "utility": 8,
                "clearance": 0.34,
                "turn_rate": 0.40,
                "target_commit": True,
            },
            "exact": {
                "domain": spec.domain_id,
                "action": "left_wall_detour",
                "utility": 8,
                "clearance": 0.12,
                "turn_rate": 0.76,
            },
            "symmetry": {
                "domain": spec.domain_id,
                "action": "right_wall_detour",
                "utility": 8,
                "clearance": 0.35,
                "turn_rate": 0.39,
                "target_commit": True,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "transform_id": "enantiomer_mirror",
            "source": {
                "domain": spec.domain_id,
                "action": "clockwise_chiral_patch",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.18,
                "target_commit": True,
            },
            "exact": {
                "domain": spec.domain_id,
                "action": "clockwise_chiral_patch",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.49,
            },
            "symmetry": {
                "domain": spec.domain_id,
                "action": "counterclockwise_chiral_patch",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.16,
                "target_commit": True,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "transform_id": "lattice_reflection",
            "source": {
                "domain": spec.domain_id,
                "action": "upper_grain_anneal",
                "utility": 8,
                "thermal_gradient": 0.38,
                "phase_purity": 0.95,
                "target_commit": True,
            },
            "exact": {
                "domain": spec.domain_id,
                "action": "upper_grain_anneal",
                "utility": 8,
                "thermal_gradient": 0.68,
                "phase_purity": 0.87,
            },
            "symmetry": {
                "domain": spec.domain_id,
                "action": "lower_grain_anneal",
                "utility": 8,
                "thermal_gradient": 0.37,
                "phase_purity": 0.96,
                "target_commit": True,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _with_context(action: Mapping[str, Any], context: str) -> Mapping[str, Any]:
    return {**dict(action), "context": context}


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_symmetry_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
