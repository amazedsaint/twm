from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from math import isfinite, sqrt
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


BRANCH_ACTIVE_SUBSPACE_CERTIFICATE_SCHEMA = "trwm.branch_active_subspace_certificate.v1"
BRANCH_ACTIVE_SUBSPACE_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_active_subspace_transfer_certificate.v1"
BRANCH_ACTIVE_SUBSPACE_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1137/1.9781611973860",
)
BRANCH_ACTIVE_SUBSPACE_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound active-direction "
    "evidence can filter orthogonal target proposals before target exploration under a matched "
    "one-call verifier budget. It is not active-subspace discovery, dimensionality-reduction "
    "performance, optimization, uncertainty quantification, robotics safety, chemistry, materials "
    "discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchActiveSubspaceCertificate:
    schema_version: str
    domain: str
    subspace_rule_id: str
    subspace_rule_version: str
    source_context_id: str
    target_context_id: str
    ambient_dimension: int
    subspace_dimension: int
    active_axis_id: str
    orthogonal_axis_id: str
    active_basis_vector: tuple[float, ...]
    orthogonal_basis_vector: tuple[float, ...]
    projection_threshold: float
    source_active_action_ids: tuple[str, ...]
    source_orthogonal_action_id: str
    static_target_action: str
    active_subspace_target_action: str
    source_active_direction_vectors: tuple[tuple[float, ...], ...]
    source_orthogonal_direction_vector: tuple[float, ...]
    static_target_direction_vector: tuple[float, ...]
    active_subspace_target_direction_vector: tuple[float, ...]
    source_active_projection_scores: tuple[float, ...]
    source_orthogonal_projection_score: float
    static_target_projection_score: float
    active_subspace_target_projection_score: float
    source_active_receipt_hashes: tuple[str, ...]
    source_orthogonal_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    active_subspace_target_receipt_hashes: tuple[str, ...]
    active_subspace_target_commit_receipt_hashes: tuple[str, ...]
    source_active_branch_selection_certificate_hashes: tuple[str, ...]
    source_orthogonal_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    active_subspace_branch_selection_certificate_hash: str
    source_active_committed_count: int
    source_orthogonal_rejected_count: int
    static_committed: bool
    active_subspace_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    active_subspace_verifier_call_count: int
    same_budget: bool
    subspace_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_ACTIVE_SUBSPACE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch active-subspace certificate schema: {self.schema_version}")
        for field_name in (
            "source_active_action_ids",
            "source_active_projection_scores",
            "source_active_receipt_hashes",
            "source_orthogonal_receipt_hashes",
            "static_target_receipt_hashes",
            "active_subspace_target_receipt_hashes",
            "active_subspace_target_commit_receipt_hashes",
            "source_active_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "active_basis_vector",
            "orthogonal_basis_vector",
            "source_orthogonal_direction_vector",
            "static_target_direction_vector",
            "active_subspace_target_direction_vector",
        ):
            object.__setattr__(self, field_name, _vector(getattr(self, field_name)))
        object.__setattr__(
            self,
            "source_active_direction_vectors",
            tuple(_vector(value) for value in self.source_active_direction_vectors),
        )
        object.__setattr__(
            self,
            "source_active_projection_scores",
            tuple(float(value) for value in self.source_active_projection_scores),
        )
        for field_name in (
            "projection_threshold",
            "source_orthogonal_projection_score",
            "static_target_projection_score",
            "active_subspace_target_projection_score",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_active_subspace_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchActiveSubspaceDomainReport:
    domain: str
    source_context: str
    target_context: str
    ambient_dimension: int
    subspace_dimension: int
    active_axis_id: str
    orthogonal_axis_id: str
    active_basis_vector: tuple[float, ...]
    orthogonal_basis_vector: tuple[float, ...]
    projection_threshold: float
    source_active_action_ids: tuple[str, ...]
    source_orthogonal_action_id: str
    static_target_action: str
    active_subspace_target_action: str
    source_active_projection_scores: tuple[float, ...]
    source_orthogonal_projection_score: float
    static_target_projection_score: float
    active_subspace_target_projection_score: float
    source_active_committed_count: int
    source_orthogonal_rejected_count: int
    static_committed: bool
    active_subspace_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    active_subspace_verifier_call_count: int
    source_active_receipt_hashes: tuple[str, ...]
    source_orthogonal_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    active_subspace_target_receipt_hashes: tuple[str, ...]
    branch_active_subspace_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchActiveSubspaceTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchActiveSubspaceDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_active_committed_count: int
    source_orthogonal_rejected_count: int
    static_success_count: int
    active_subspace_success_count: int
    same_budget_active_subspace_count: int
    branch_active_subspace_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_active_subspace_certificates_valid: bool
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
class BranchActiveSubspaceTransferCertificate:
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
    branch_active_subspace_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_active_committed_count: int
    source_orthogonal_rejected_count: int
    static_success_count: int
    active_subspace_success_count: int
    same_budget_active_subspace_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_ACTIVE_SUBSPACE_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch active-subspace transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_active_subspace_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_active_subspace_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchActiveSubspaceTransferResult(CertifiedExampleResult):
    report: BranchActiveSubspaceTransferReport
    branch_active_subspace_transfer_certificate: BranchActiveSubspaceTransferCertificate
    branch_active_subspace_certificates: tuple[BranchActiveSubspaceCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_active_subspace_transfer_experiment() -> BranchActiveSubspaceTransferReport:
    return run_branch_active_subspace_transfer_certified_experiment().report


def run_branch_active_subspace_transfer_certified_experiment() -> CertifiedBranchActiveSubspaceTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchActiveSubspaceDomainReport] = []
    subspace_certificates: list[BranchActiveSubspaceCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_active_subspace_plan(spec)
        source_context = f"{spec.domain_id}:source:active-subspace"
        target_context = f"{spec.domain_id}:target:active-subspace"

        source_active_outcomes = []
        source_active_selections = []
        for idx, active_action in enumerate(plan["source_active_actions"]):
            outcome = runtime.step(
                state,
                _make_active_subspace_traces(
                    spec,
                    context=source_context,
                    phase=f"source-active-{idx}",
                    actions=(active_action,),
                ),
            )
            state = normalize_state(outcome.state)
            selection = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), selection))
            memory.update_branch(outcome.receipts, selection)
            source_active_outcomes.append(outcome)
            source_active_selections.append(selection)

        orthogonal_outcome = runtime.step(
            state,
            _make_active_subspace_traces(
                spec,
                context=source_context,
                phase="source-orthogonal-reject",
                actions=(plan["source_orthogonal_action"],),
            ),
        )
        orthogonal_selection = build_branch_selection_certificate(
            orthogonal_outcome.receipts,
            verifier_call_count=orthogonal_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(orthogonal_outcome.receipts), orthogonal_selection))
        memory.update_branch(orthogonal_outcome.receipts, orthogonal_selection)

        static_outcome = runtime.step(
            state,
            _make_active_subspace_traces(
                spec,
                context=target_context,
                phase="target-static-orthogonal",
                actions=(plan["target_static"],),
            ),
        )
        static_selection = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        subspace_outcome = runtime.step(
            state,
            _make_active_subspace_traces(
                spec,
                context=target_context,
                phase="target-active-subspace",
                actions=(plan["target_active_subspace"],),
            ),
        )
        state = normalize_state(subspace_outcome.state)
        subspace_selection = build_branch_selection_certificate(
            subspace_outcome.receipts,
            verifier_call_count=subspace_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(subspace_outcome.receipts), subspace_selection))

        active_basis = _vector(plan["active_basis_vector"])
        certificate = build_branch_active_subspace_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            ambient_dimension=int(plan["ambient_dimension"]),
            subspace_dimension=int(plan["subspace_dimension"]),
            active_axis_id=str(plan["active_axis_id"]),
            orthogonal_axis_id=str(plan["orthogonal_axis_id"]),
            active_basis_vector=active_basis,
            orthogonal_basis_vector=_vector(plan["orthogonal_basis_vector"]),
            projection_threshold=float(plan["projection_threshold"]),
            source_active_action_ids=tuple(str(action["action"]) for action in plan["source_active_actions"]),
            source_orthogonal_action_id=str(plan["source_orthogonal_action"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            active_subspace_target_action=str(plan["target_active_subspace"]["action"]),
            source_active_direction_vectors=tuple(
                _vector(action["direction_vector"]) for action in plan["source_active_actions"]
            ),
            source_orthogonal_direction_vector=_vector(plan["source_orthogonal_action"]["direction_vector"]),
            static_target_direction_vector=_vector(plan["target_static"]["direction_vector"]),
            active_subspace_target_direction_vector=_vector(plan["target_active_subspace"]["direction_vector"]),
            source_active_projection_scores=tuple(
                _projection_score(action["direction_vector"], active_basis)
                for action in plan["source_active_actions"]
            ),
            source_orthogonal_projection_score=_projection_score(
                plan["source_orthogonal_action"]["direction_vector"],
                active_basis,
            ),
            static_target_projection_score=_projection_score(plan["target_static"]["direction_vector"], active_basis),
            active_subspace_target_projection_score=_projection_score(
                plan["target_active_subspace"]["direction_vector"],
                active_basis,
            ),
            source_active_receipt_hashes=tuple(
                receipt.receipt_hash for outcome in source_active_outcomes for receipt in outcome.receipts
            ),
            source_orthogonal_receipt_hashes=tuple(receipt.receipt_hash for receipt in orthogonal_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            active_subspace_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in subspace_outcome.receipts),
            active_subspace_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in subspace_outcome.receipts if receipt.committed
            ),
            source_active_branch_selection_certificate_hashes=tuple(
                selection.certificate_hash for selection in source_active_selections
            ),
            source_orthogonal_branch_selection_certificate_hash=orthogonal_selection.certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            active_subspace_branch_selection_certificate_hash=subspace_selection.certificate_hash,
            source_active_committed_count=sum(1 for outcome in source_active_outcomes if outcome.committed),
            source_orthogonal_rejected_count=sum(
                1 for receipt in orthogonal_outcome.receipts if receipt.hard_result.rejected
            ),
            static_committed=static_outcome.committed,
            active_subspace_committed=subspace_outcome.committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in source_active_outcomes)
            + orthogonal_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            active_subspace_verifier_call_count=subspace_outcome.verifier_calls,
        )
        subspace_certificates.append(certificate)
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

    report = BranchActiveSubspaceTransferReport(
        schema_version="trwm.example.branch_active_subspace_transfer.v1",
        experiment_id="branch_active_subspace_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_active_committed_count=sum(row.source_active_committed_count for row in rows),
        source_orthogonal_rejected_count=sum(row.source_orthogonal_rejected_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        active_subspace_success_count=sum(1 for row in rows if row.active_subspace_committed),
        same_budget_active_subspace_count=sum(1 for row in rows if row.same_budget),
        branch_active_subspace_certificate_count=len(subspace_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_active_subspace_certificates_valid=all(
            validate_branch_active_subspace_certificate(certificate, row)
            for certificate, row in zip(subspace_certificates, rows)
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
        sources=BRANCH_ACTIVE_SUBSPACE_SOURCES,
        learning=(
            "Active-subspace branch reuse separates reusable low-rank proposal directions from commit "
            "authority. Past branch receipts can filter an orthogonal target proposal, but the in-subspace "
            "target proposal still commits only through a fresh hard-verifier receipt."
        ),
    )
    transfer_certificate = build_branch_active_subspace_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_active_subspace_certificate_hashes=tuple(certificate.certificate_hash for certificate in subspace_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_active_subspace_transfer",
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
        claim_boundary=BRANCH_ACTIVE_SUBSPACE_CLAIM_BOUNDARY,
        sources=BRANCH_ACTIVE_SUBSPACE_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchActiveSubspaceTransferResult(
        report=report,
        branch_active_subspace_transfer_certificate=transfer_certificate,
        branch_active_subspace_certificates=tuple(subspace_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_active_subspace_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    ambient_dimension: int,
    subspace_dimension: int,
    active_axis_id: str,
    orthogonal_axis_id: str,
    active_basis_vector: tuple[float, ...],
    orthogonal_basis_vector: tuple[float, ...],
    projection_threshold: float,
    source_active_action_ids: tuple[str, ...],
    source_orthogonal_action_id: str,
    static_target_action: str,
    active_subspace_target_action: str,
    source_active_direction_vectors: tuple[tuple[float, ...], ...],
    source_orthogonal_direction_vector: tuple[float, ...],
    static_target_direction_vector: tuple[float, ...],
    active_subspace_target_direction_vector: tuple[float, ...],
    source_active_projection_scores: tuple[float, ...],
    source_orthogonal_projection_score: float,
    static_target_projection_score: float,
    active_subspace_target_projection_score: float,
    source_active_receipt_hashes: tuple[str, ...],
    source_orthogonal_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    active_subspace_target_receipt_hashes: tuple[str, ...],
    active_subspace_target_commit_receipt_hashes: tuple[str, ...],
    source_active_branch_selection_certificate_hashes: tuple[str, ...],
    source_orthogonal_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    active_subspace_branch_selection_certificate_hash: str,
    source_active_committed_count: int,
    source_orthogonal_rejected_count: int,
    static_committed: bool,
    active_subspace_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    active_subspace_verifier_call_count: int,
) -> BranchActiveSubspaceCertificate:
    return BranchActiveSubspaceCertificate(
        schema_version=BRANCH_ACTIVE_SUBSPACE_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        subspace_rule_id="receipt_bound_active_direction_projection",
        subspace_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        ambient_dimension=ambient_dimension,
        subspace_dimension=subspace_dimension,
        active_axis_id=active_axis_id,
        orthogonal_axis_id=orthogonal_axis_id,
        active_basis_vector=active_basis_vector,
        orthogonal_basis_vector=orthogonal_basis_vector,
        projection_threshold=projection_threshold,
        source_active_action_ids=source_active_action_ids,
        source_orthogonal_action_id=source_orthogonal_action_id,
        static_target_action=static_target_action,
        active_subspace_target_action=active_subspace_target_action,
        source_active_direction_vectors=source_active_direction_vectors,
        source_orthogonal_direction_vector=source_orthogonal_direction_vector,
        static_target_direction_vector=static_target_direction_vector,
        active_subspace_target_direction_vector=active_subspace_target_direction_vector,
        source_active_projection_scores=source_active_projection_scores,
        source_orthogonal_projection_score=source_orthogonal_projection_score,
        static_target_projection_score=static_target_projection_score,
        active_subspace_target_projection_score=active_subspace_target_projection_score,
        source_active_receipt_hashes=source_active_receipt_hashes,
        source_orthogonal_receipt_hashes=source_orthogonal_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        active_subspace_target_receipt_hashes=active_subspace_target_receipt_hashes,
        active_subspace_target_commit_receipt_hashes=active_subspace_target_commit_receipt_hashes,
        source_active_branch_selection_certificate_hashes=source_active_branch_selection_certificate_hashes,
        source_orthogonal_branch_selection_certificate_hash=source_orthogonal_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        active_subspace_branch_selection_certificate_hash=active_subspace_branch_selection_certificate_hash,
        source_active_committed_count=source_active_committed_count,
        source_orthogonal_rejected_count=source_orthogonal_rejected_count,
        static_committed=static_committed,
        active_subspace_committed=active_subspace_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        active_subspace_verifier_call_count=active_subspace_verifier_call_count,
        same_budget=static_verifier_call_count == active_subspace_verifier_call_count == 1,
        subspace_reason="target_direction_within_receipt_bound_active_subspace",
    )


def validate_branch_active_subspace_certificate(
    certificate: BranchActiveSubspaceCertificate,
    row: BranchActiveSubspaceDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_ACTIVE_SUBSPACE_CERTIFICATE_SCHEMA:
            return False
        if certificate.subspace_rule_id != "receipt_bound_active_direction_projection":
            return False
        if certificate.subspace_rule_version != "1.0":
            return False
        if certificate.ambient_dimension != 2 or certificate.subspace_dimension != 1:
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.active_axis_id):
            return False
        if not _nonempty(certificate.orthogonal_axis_id):
            return False
        if len(certificate.source_active_action_ids) != 2 or len(set(certificate.source_active_action_ids)) != 2:
            return False
        if len(certificate.source_active_direction_vectors) != 2:
            return False
        if not _close(certificate.projection_threshold, 0.75):
            return False
        if not _orthonormal(certificate.active_basis_vector, certificate.orthogonal_basis_vector):
            return False
        if len(certificate.source_active_projection_scores) != 2:
            return False
        for vector, score in zip(certificate.source_active_direction_vectors, certificate.source_active_projection_scores):
            if not _close(score, _projection_score(vector, certificate.active_basis_vector)):
                return False
            if score < certificate.projection_threshold:
                return False
        if not _close(
            certificate.source_orthogonal_projection_score,
            _projection_score(certificate.source_orthogonal_direction_vector, certificate.active_basis_vector),
        ):
            return False
        if not _close(
            certificate.static_target_projection_score,
            _projection_score(certificate.static_target_direction_vector, certificate.active_basis_vector),
        ):
            return False
        if not _close(
            certificate.active_subspace_target_projection_score,
            _projection_score(certificate.active_subspace_target_direction_vector, certificate.active_basis_vector),
        ):
            return False
        if certificate.source_orthogonal_projection_score >= certificate.projection_threshold:
            return False
        if certificate.static_target_projection_score >= certificate.projection_threshold:
            return False
        if certificate.active_subspace_target_projection_score < certificate.projection_threshold:
            return False
        if certificate.source_active_committed_count != 2 or certificate.source_orthogonal_rejected_count != 1:
            return False
        if certificate.static_committed or not certificate.active_subspace_committed:
            return False
        if certificate.source_verifier_call_count != 3:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.active_subspace_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.subspace_reason != "target_direction_within_receipt_bound_active_subspace":
            return False
        hash_groups = (
            (certificate.source_active_receipt_hashes, 2),
            (certificate.source_orthogonal_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.active_subspace_target_receipt_hashes, 1),
            (certificate.active_subspace_target_commit_receipt_hashes, 1),
            (certificate.source_active_branch_selection_certificate_hashes, 2),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_orthogonal_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.active_subspace_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.active_axis_id != certificate.active_axis_id or row.orthogonal_axis_id != certificate.orthogonal_axis_id:
                return False
            if row.source_active_action_ids != certificate.source_active_action_ids:
                return False
            if row.source_orthogonal_action_id != certificate.source_orthogonal_action_id:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.active_subspace_target_action != certificate.active_subspace_target_action:
                return False
            if row.source_active_projection_scores != certificate.source_active_projection_scores:
                return False
            if row.source_active_receipt_hashes != certificate.source_active_receipt_hashes:
                return False
            if row.source_orthogonal_receipt_hashes != certificate.source_orthogonal_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.active_subspace_target_receipt_hashes != certificate.active_subspace_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_active_subspace_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_active_subspace_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_active_subspace_transfer_certificate(
    report: BranchActiveSubspaceTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_active_subspace_certificate_hashes: tuple[str, ...],
) -> BranchActiveSubspaceTransferCertificate:
    return BranchActiveSubspaceTransferCertificate(
        schema_version=BRANCH_ACTIVE_SUBSPACE_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_active_subspace_certificate_hashes=branch_active_subspace_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_active_committed_count=report.source_active_committed_count,
        source_orthogonal_rejected_count=report.source_orthogonal_rejected_count,
        static_success_count=report.static_success_count,
        active_subspace_success_count=report.active_subspace_success_count,
        same_budget_active_subspace_count=report.same_budget_active_subspace_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_ACTIVE_SUBSPACE_CLAIM_BOUNDARY,
    )


def validate_branch_active_subspace_transfer_certificate(
    certificate: BranchActiveSubspaceTransferCertificate,
    report: BranchActiveSubspaceTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_ACTIVE_SUBSPACE_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_active_subspace_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_active_subspace_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_active_committed_count != certificate.domain_count * 2:
            return False
        if certificate.source_orthogonal_rejected_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.active_subspace_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_active_subspace_count != certificate.domain_count:
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
            if tuple(row.branch_active_subspace_certificate_hash for row in report.rows) != certificate.branch_active_subspace_certificate_hashes:
                return False
            if report.branch_active_subspace_certificate_count != len(certificate.branch_active_subspace_certificate_hashes):
                return False
            if not report.all_branch_active_subspace_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_active_committed_count != certificate.source_active_committed_count:
                return False
            if report.source_orthogonal_rejected_count != certificate.source_orthogonal_rejected_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.active_subspace_success_count != certificate.active_subspace_success_count:
                return False
            if report.same_budget_active_subspace_count != certificate.same_budget_active_subspace_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_active_subspace_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_active_subspace_certificate_hash(
    certificate: BranchActiveSubspaceCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchActiveSubspaceCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_active_subspace_transfer_certificate_hash(
    certificate: BranchActiveSubspaceTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchActiveSubspaceTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchActiveSubspaceTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchActiveSubspaceTransferReport,
    transfer_certificate: BranchActiveSubspaceTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_active_subspace_transfer_g1",
        claim_text=(
            "Receipt-bound active-direction certificates can improve local target exploration by filtering "
            "orthogonal proposals and committing only in-subspace proposals under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_active_subspace_transfer",
        requirements=(
            requirement(
                "branch_active_subspace_transfer_certificate_valid",
                validate_branch_active_subspace_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_active_subspace_certificates_valid", report.all_branch_active_subspace_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_active_commits_all_domains", report.source_active_committed_count == report.domain_count * 2),
            requirement("source_orthogonal_rejects_all_domains", report.source_orthogonal_rejected_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("active_subspace_succeeds_all_domains", report.active_subspace_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_active_subspace_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 3),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_active_committed_count": report.source_active_committed_count,
            "source_orthogonal_rejected_count": report.source_orthogonal_rejected_count,
            "static_success_count": report.static_success_count,
            "active_subspace_success_count": report.active_subspace_success_count,
        },
        boundary=BRANCH_ACTIVE_SUBSPACE_CLAIM_BOUNDARY,
        sources=BRANCH_ACTIVE_SUBSPACE_SOURCES,
    )


def _row_from_certificate(certificate: BranchActiveSubspaceCertificate) -> BranchActiveSubspaceDomainReport:
    return BranchActiveSubspaceDomainReport(
        domain=certificate.domain,
        source_context=certificate.source_context_id,
        target_context=certificate.target_context_id,
        ambient_dimension=certificate.ambient_dimension,
        subspace_dimension=certificate.subspace_dimension,
        active_axis_id=certificate.active_axis_id,
        orthogonal_axis_id=certificate.orthogonal_axis_id,
        active_basis_vector=certificate.active_basis_vector,
        orthogonal_basis_vector=certificate.orthogonal_basis_vector,
        projection_threshold=certificate.projection_threshold,
        source_active_action_ids=certificate.source_active_action_ids,
        source_orthogonal_action_id=certificate.source_orthogonal_action_id,
        static_target_action=certificate.static_target_action,
        active_subspace_target_action=certificate.active_subspace_target_action,
        source_active_projection_scores=certificate.source_active_projection_scores,
        source_orthogonal_projection_score=certificate.source_orthogonal_projection_score,
        static_target_projection_score=certificate.static_target_projection_score,
        active_subspace_target_projection_score=certificate.active_subspace_target_projection_score,
        source_active_committed_count=certificate.source_active_committed_count,
        source_orthogonal_rejected_count=certificate.source_orthogonal_rejected_count,
        static_committed=certificate.static_committed,
        active_subspace_committed=certificate.active_subspace_committed,
        source_verifier_call_count=certificate.source_verifier_call_count,
        static_verifier_call_count=certificate.static_verifier_call_count,
        active_subspace_verifier_call_count=certificate.active_subspace_verifier_call_count,
        source_active_receipt_hashes=certificate.source_active_receipt_hashes,
        source_orthogonal_receipt_hashes=certificate.source_orthogonal_receipt_hashes,
        static_target_receipt_hashes=certificate.static_target_receipt_hashes,
        active_subspace_target_receipt_hashes=certificate.active_subspace_target_receipt_hashes,
        branch_active_subspace_certificate_hash=certificate.certificate_hash,
        same_budget=certificate.same_budget,
    )


def _make_active_subspace_traces(
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
            seeds=("branch-active-subspace-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.active_subspace.transfer.v1",
        )
        for action in actions
    )


def _domain_active_subspace_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    base = {
        "ambient_dimension": 2,
        "subspace_dimension": 1,
        "active_basis_vector": (1.0, 0.0),
        "orthogonal_basis_vector": (0.0, 1.0),
        "projection_threshold": 0.75,
    }
    if spec.domain_id == "robotics_replan":
        return {
            **base,
            "active_axis_id": "detour_clearance_axis",
            "orthogonal_axis_id": "wall_cut_axis",
            "source_active_actions": (
                {"domain": spec.domain_id, "action": "subspace_source_detour_axis", "utility": 7, "direction_vector": (1.0, 0.0), "clearance": 0.34, "turn_rate": 0.42},
                {"domain": spec.domain_id, "action": "subspace_source_soft_detour_axis", "utility": 7, "direction_vector": (0.8, 0.6), "clearance": 0.32, "turn_rate": 0.48},
            ),
            "source_orthogonal_action": {
                "domain": spec.domain_id,
                "action": "subspace_source_orthogonal_cut",
                "utility": 9,
                "direction_vector": (0.0, 1.0),
                "clearance": 0.12,
                "turn_rate": 0.85,
            },
            "target_static": {
                "domain": spec.domain_id,
                "action": "subspace_target_orthogonal_replay",
                "utility": 9,
                "direction_vector": (0.6, 0.8),
                "clearance": 0.16,
                "turn_rate": 0.80,
            },
            "target_active_subspace": {
                "domain": spec.domain_id,
                "action": "subspace_target_active_detour",
                "utility": 7,
                "direction_vector": (0.96, 0.28),
                "clearance": 0.35,
                "turn_rate": 0.44,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            **base,
            "active_axis_id": "low_strain_valence_axis",
            "orthogonal_axis_id": "forced_patch_axis",
            "source_active_actions": (
                {"domain": spec.domain_id, "action": "subspace_source_low_strain_axis", "utility": 7, "direction_vector": (1.0, 0.0), "valence_ok": True, "strain": 0.18},
                {"domain": spec.domain_id, "action": "subspace_source_soft_low_strain_axis", "utility": 7, "direction_vector": (0.8, 0.6), "valence_ok": True, "strain": 0.30},
            ),
            "source_orthogonal_action": {
                "domain": spec.domain_id,
                "action": "subspace_source_orthogonal_patch",
                "utility": 9,
                "direction_vector": (0.0, 1.0),
                "valence_ok": False,
                "strain": 0.55,
            },
            "target_static": {
                "domain": spec.domain_id,
                "action": "subspace_target_orthogonal_replay",
                "utility": 9,
                "direction_vector": (0.6, 0.8),
                "valence_ok": True,
                "strain": 0.52,
            },
            "target_active_subspace": {
                "domain": spec.domain_id,
                "action": "subspace_target_active_low_strain",
                "utility": 7,
                "direction_vector": (0.96, 0.28),
                "valence_ok": True,
                "strain": 0.20,
            },
        }
    if spec.domain_id == "material_process":
        return {
            **base,
            "active_axis_id": "tempered_window_axis",
            "orthogonal_axis_id": "flash_ramp_axis",
            "source_active_actions": (
                {"domain": spec.domain_id, "action": "subspace_source_tempered_axis", "utility": 7, "direction_vector": (1.0, 0.0), "thermal_gradient": 0.35, "phase_purity": 0.96},
                {"domain": spec.domain_id, "action": "subspace_source_soft_tempered_axis", "utility": 7, "direction_vector": (0.8, 0.6), "thermal_gradient": 0.45, "phase_purity": 0.93},
            ),
            "source_orthogonal_action": {
                "domain": spec.domain_id,
                "action": "subspace_source_orthogonal_fast_ramp",
                "utility": 9,
                "direction_vector": (0.0, 1.0),
                "thermal_gradient": 0.76,
                "phase_purity": 0.84,
            },
            "target_static": {
                "domain": spec.domain_id,
                "action": "subspace_target_orthogonal_replay",
                "utility": 9,
                "direction_vector": (0.6, 0.8),
                "thermal_gradient": 0.72,
                "phase_purity": 0.85,
            },
            "target_active_subspace": {
                "domain": spec.domain_id,
                "action": "subspace_target_active_tempered",
                "utility": 7,
                "direction_vector": (0.96, 0.28),
                "thermal_gradient": 0.39,
                "phase_purity": 0.95,
            },
        }
    raise ValueError(f"unknown active-subspace domain: {spec.domain_id}")


def _vector(value: Iterable[Any]) -> tuple[float, ...]:
    return tuple(float(item) for item in value)


def _dot(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have matching dimension")
    return sum(l * r for l, r in zip(left, right))


def _norm(value: tuple[float, ...]) -> float:
    return sqrt(sum(item * item for item in value))


def _projection_score(vector: Iterable[Any], basis: Iterable[Any]) -> float:
    vector_row = _vector(vector)
    basis_row = _vector(basis)
    vector_norm = _norm(vector_row)
    basis_norm = _norm(basis_row)
    if vector_norm <= 0.0 or basis_norm <= 0.0:
        raise ValueError("projection vectors must be non-zero")
    return abs(_dot(vector_row, basis_row)) / (vector_norm * basis_norm)


def _orthonormal(left: tuple[float, ...], right: tuple[float, ...]) -> bool:
    return (
        len(left) == 2
        and len(right) == 2
        and _close(_norm(left), 1.0)
        and _close(_norm(right), 1.0)
        and _close(_dot(left, right), 0.0)
    )


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _close(left: float, right: float) -> bool:
    return isfinite(float(left)) and isfinite(float(right)) and abs(float(left) - float(right)) <= 1e-6


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_active_subspace_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
