from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from math import isfinite
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


BRANCH_PARETO_CERTIFICATE_SCHEMA = "trwm.branch_pareto_certificate.v1"
BRANCH_PARETO_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_pareto_transfer_certificate.v1"
BRANCH_PARETO_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1109/4235.996017",
)
BRANCH_PARETO_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source receipts can certify a "
    "multi-objective dominance relation so the target spends the same one-call verifier budget on a "
    "nondominated branch instead of scalar replay. It is not a multiobjective optimizer, NSGA-II "
    "implementation, Pareto-front approximation guarantee, robotics safety, chemistry, materials "
    "discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchParetoCertificate:
    schema_version: str
    domain: str
    pareto_rule_id: str
    pareto_rule_version: str
    source_context_id: str
    target_context_id: str
    dominated_action: str
    pareto_action: str
    dominated_objectives: Mapping[str, float]
    pareto_objectives: Mapping[str, float]
    source_dominated_reject_receipt_hashes: tuple[str, ...]
    source_pareto_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    pareto_target_receipt_hashes: tuple[str, ...]
    pareto_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    pareto_branch_selection_certificate_hash: str
    dominance_margin_sum: float
    static_committed: bool
    pareto_committed: bool
    static_verifier_call_count: int
    pareto_verifier_call_count: int
    same_budget: bool
    pareto_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PARETO_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch pareto certificate schema: {self.schema_version}")
        object.__setattr__(self, "dominated_objectives", _normalize_objectives(self.dominated_objectives))
        object.__setattr__(self, "pareto_objectives", _normalize_objectives(self.pareto_objectives))
        for field_name in (
            "source_dominated_reject_receipt_hashes",
            "source_pareto_commit_receipt_hashes",
            "static_target_receipt_hashes",
            "pareto_target_receipt_hashes",
            "pareto_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "dominance_margin_sum", float(self.dominance_margin_sum))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_pareto_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchParetoDomainReport:
    domain: str
    source_context: str
    target_context: str
    dominated_action: str
    pareto_action: str
    dominated_objectives: Mapping[str, float]
    pareto_objectives: Mapping[str, float]
    dominance_margin_sum: float
    static_committed: bool
    pareto_committed: bool
    static_verifier_call_count: int
    pareto_verifier_call_count: int
    source_dominated_reject_receipt_hashes: tuple[str, ...]
    source_pareto_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    pareto_target_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    pareto_branch_selection_certificate_hash: str
    pareto_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchParetoTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchParetoDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_dominated_reject_count: int
    source_pareto_commit_count: int
    static_success_count: int
    pareto_success_count: int
    same_budget_pareto_count: int
    branch_pareto_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_pareto_certificates_valid: bool
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
class BranchParetoTransferCertificate:
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
    branch_pareto_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_dominated_reject_count: int
    source_pareto_commit_count: int
    static_success_count: int
    pareto_success_count: int
    same_budget_pareto_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PARETO_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch pareto transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_pareto_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_pareto_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchParetoTransferResult(CertifiedExampleResult):
    report: BranchParetoTransferReport
    branch_pareto_transfer_certificate: BranchParetoTransferCertificate
    branch_pareto_certificates: tuple[BranchParetoCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_pareto_transfer_experiment() -> BranchParetoTransferReport:
    return run_branch_pareto_transfer_certified_experiment().report


def run_branch_pareto_transfer_certified_experiment() -> CertifiedBranchParetoTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchParetoDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    pareto_certificates: list[BranchParetoCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:pareto"
        target_context = f"{spec.domain_id}:target:pareto"
        action_map = _pareto_actions(spec)
        dominated_source = _with_context(action_map["dominated_source"], source_context)
        pareto_source = _with_context(action_map["pareto_source"], source_context)
        dominated_target = _with_context(action_map["dominated_target"], target_context)
        pareto_target = _with_context(action_map["pareto_target"], target_context)

        source_outcome = runtime.step(
            state,
            _make_pareto_traces(
                spec,
                context=source_context,
                phase="source-pareto-front",
                actions=(dominated_source, pareto_source),
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
            _make_pareto_traces(
                spec,
                context=target_context,
                phase="target-scalar-replay",
                actions=(dominated_target,),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        pareto_outcome = runtime.step(
            state,
            _make_pareto_traces(
                spec,
                context=target_context,
                phase="target-pareto-front",
                actions=(pareto_target,),
            ),
        )
        state = normalize_state(pareto_outcome.state)
        pareto_branch_certificate = build_branch_selection_certificate(
            pareto_outcome.receipts,
            verifier_call_count=pareto_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(pareto_outcome.receipts), pareto_branch_certificate))

        certificate = build_branch_pareto_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            dominated_action=str(dominated_source["action"]),
            pareto_action=str(pareto_source["action"]),
            dominated_objectives=dict(dominated_source["objectives"]),
            pareto_objectives=dict(pareto_source["objectives"]),
            source_dominated_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
            source_pareto_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            pareto_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in pareto_outcome.receipts),
            pareto_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in pareto_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            pareto_branch_selection_certificate_hash=pareto_branch_certificate.certificate_hash,
            static_committed=static_outcome.committed,
            pareto_committed=pareto_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            pareto_verifier_call_count=pareto_outcome.verifier_calls,
        )
        pareto_certificates.append(certificate)
        rows.append(
            BranchParetoDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                dominated_action=certificate.dominated_action,
                pareto_action=certificate.pareto_action,
                dominated_objectives=certificate.dominated_objectives,
                pareto_objectives=certificate.pareto_objectives,
                dominance_margin_sum=certificate.dominance_margin_sum,
                static_committed=certificate.static_committed,
                pareto_committed=certificate.pareto_committed,
                static_verifier_call_count=certificate.static_verifier_call_count,
                pareto_verifier_call_count=certificate.pareto_verifier_call_count,
                source_dominated_reject_receipt_hashes=certificate.source_dominated_reject_receipt_hashes,
                source_pareto_commit_receipt_hashes=certificate.source_pareto_commit_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                pareto_target_receipt_hashes=certificate.pareto_target_receipt_hashes,
                source_branch_selection_certificate_hash=certificate.source_branch_selection_certificate_hash,
                static_branch_selection_certificate_hash=certificate.static_branch_selection_certificate_hash,
                pareto_branch_selection_certificate_hash=certificate.pareto_branch_selection_certificate_hash,
                pareto_certificate_hash=certificate.certificate_hash,
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

    report = BranchParetoTransferReport(
        schema_version="trwm.example.branch_pareto_transfer.v1",
        experiment_id="branch_pareto_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_dominated_reject_count=sum(len(row.source_dominated_reject_receipt_hashes) for row in rows),
        source_pareto_commit_count=sum(len(row.source_pareto_commit_receipt_hashes) for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        pareto_success_count=sum(1 for row in rows if row.pareto_committed),
        same_budget_pareto_count=sum(1 for row in rows if row.same_budget),
        branch_pareto_certificate_count=len(pareto_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_pareto_certificates_valid=all(
            validate_branch_pareto_certificate(certificate, row)
            for certificate, row in zip(pareto_certificates, rows)
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
        sources=BRANCH_PARETO_SOURCES,
        learning=(
            "Branch history can improve exploration by binding multi-objective dominance. A scalar "
            "replay target repeats the dominated source failure, while the Pareto-guided target tries "
            "the nondominated candidate under the same verifier budget and still requires fresh commit authority."
        ),
    )
    transfer_certificate = build_branch_pareto_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_pareto_certificate_hashes=tuple(certificate.certificate_hash for certificate in pareto_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_pareto_transfer",
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
        claim_boundary=BRANCH_PARETO_CLAIM_BOUNDARY,
        sources=BRANCH_PARETO_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchParetoTransferResult(
        report=report,
        branch_pareto_transfer_certificate=transfer_certificate,
        branch_pareto_certificates=tuple(pareto_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_pareto_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    dominated_action: str,
    pareto_action: str,
    dominated_objectives: Mapping[str, float],
    pareto_objectives: Mapping[str, float],
    source_dominated_reject_receipt_hashes: tuple[str, ...],
    source_pareto_commit_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    pareto_target_receipt_hashes: tuple[str, ...],
    pareto_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    pareto_branch_selection_certificate_hash: str,
    static_committed: bool,
    pareto_committed: bool,
    static_verifier_call_count: int,
    pareto_verifier_call_count: int,
) -> BranchParetoCertificate:
    return BranchParetoCertificate(
        schema_version=BRANCH_PARETO_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        pareto_rule_id="receipt_bound_pareto_dominance",
        pareto_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        dominated_action=dominated_action,
        pareto_action=pareto_action,
        dominated_objectives=dominated_objectives,
        pareto_objectives=pareto_objectives,
        source_dominated_reject_receipt_hashes=source_dominated_reject_receipt_hashes,
        source_pareto_commit_receipt_hashes=source_pareto_commit_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        pareto_target_receipt_hashes=pareto_target_receipt_hashes,
        pareto_target_commit_receipt_hashes=pareto_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        pareto_branch_selection_certificate_hash=pareto_branch_selection_certificate_hash,
        dominance_margin_sum=_dominance_margin_sum(dominated_objectives, pareto_objectives),
        static_committed=static_committed,
        pareto_committed=pareto_committed,
        static_verifier_call_count=static_verifier_call_count,
        pareto_verifier_call_count=pareto_verifier_call_count,
        same_budget=static_verifier_call_count == pareto_verifier_call_count == 1,
        pareto_reason="source_receipts_certify_pareto_dominance",
    )


def validate_branch_pareto_certificate(
    certificate: BranchParetoCertificate,
    row: BranchParetoDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PARETO_CERTIFICATE_SCHEMA:
            return False
        if certificate.pareto_rule_id != "receipt_bound_pareto_dominance":
            return False
        if certificate.pareto_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.dominated_action,
            certificate.pareto_action,
            certificate.pareto_reason,
        ):
            if not _nonempty(value):
                return False
        if certificate.dominated_action == certificate.pareto_action:
            return False
        if not _pareto_dominates(certificate.dominated_objectives, certificate.pareto_objectives):
            return False
        if certificate.dominance_margin_sum <= 0:
            return False
        expected_margin = _dominance_margin_sum(certificate.dominated_objectives, certificate.pareto_objectives)
        if abs(certificate.dominance_margin_sum - expected_margin) > 1e-12:
            return False
        if certificate.static_committed or not certificate.pareto_committed:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.pareto_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.pareto_reason != "source_receipts_certify_pareto_dominance":
            return False
        for values, expected_len in (
            (certificate.source_dominated_reject_receipt_hashes, 1),
            (certificate.source_pareto_commit_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.pareto_target_receipt_hashes, 1),
            (certificate.pareto_target_commit_receipt_hashes, 1),
        ):
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.pareto_branch_selection_certificate_hash,
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
            if row.dominated_action != certificate.dominated_action:
                return False
            if row.pareto_action != certificate.pareto_action:
                return False
            if _normalize_objectives(row.dominated_objectives) != certificate.dominated_objectives:
                return False
            if _normalize_objectives(row.pareto_objectives) != certificate.pareto_objectives:
                return False
            if row.dominance_margin_sum != certificate.dominance_margin_sum:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.pareto_committed != certificate.pareto_committed:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.pareto_verifier_call_count != certificate.pareto_verifier_call_count:
                return False
            if row.source_dominated_reject_receipt_hashes != certificate.source_dominated_reject_receipt_hashes:
                return False
            if row.source_pareto_commit_receipt_hashes != certificate.source_pareto_commit_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.pareto_target_receipt_hashes != certificate.pareto_target_receipt_hashes:
                return False
            if row.source_branch_selection_certificate_hash != certificate.source_branch_selection_certificate_hash:
                return False
            if row.static_branch_selection_certificate_hash != certificate.static_branch_selection_certificate_hash:
                return False
            if row.pareto_branch_selection_certificate_hash != certificate.pareto_branch_selection_certificate_hash:
                return False
            if row.pareto_certificate_hash != certificate.certificate_hash:
                return False
            if row.same_budget != certificate.same_budget:
                return False
        return certificate.certificate_hash == branch_pareto_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_pareto_transfer_certificate(
    report: BranchParetoTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_pareto_certificate_hashes: tuple[str, ...],
) -> BranchParetoTransferCertificate:
    return BranchParetoTransferCertificate(
        schema_version=BRANCH_PARETO_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_pareto_certificate_hashes=branch_pareto_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_dominated_reject_count=report.source_dominated_reject_count,
        source_pareto_commit_count=report.source_pareto_commit_count,
        static_success_count=report.static_success_count,
        pareto_success_count=report.pareto_success_count,
        same_budget_pareto_count=report.same_budget_pareto_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_PARETO_CLAIM_BOUNDARY,
    )


def validate_branch_pareto_transfer_certificate(
    certificate: BranchParetoTransferCertificate,
    report: BranchParetoTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PARETO_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_pareto_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_pareto_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_dominated_reject_count != certificate.domain_count:
            return False
        if certificate.source_pareto_commit_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.pareto_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_pareto_count != certificate.domain_count:
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
            if not report.all_branch_pareto_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_dominated_reject_count != certificate.source_dominated_reject_count:
                return False
            if report.source_pareto_commit_count != certificate.source_pareto_commit_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.pareto_success_count != certificate.pareto_success_count:
                return False
            if report.same_budget_pareto_count != certificate.same_budget_pareto_count:
                return False
        return certificate.certificate_hash == branch_pareto_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_pareto_certificate_hash(certificate: BranchParetoCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchParetoCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_pareto_transfer_certificate_hash(
    certificate: BranchParetoTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchParetoTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchParetoTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchParetoTransferReport,
    transfer_certificate: BranchParetoTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_pareto_transfer_g1",
        claim_text=(
            "Receipt-bound Pareto dominance can improve local target exploration under matched one-call "
            "verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_pareto_transfer",
        requirements=(
            requirement(
                "branch_pareto_transfer_certificate_valid",
                validate_branch_pareto_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid),
            requirement("all_branch_pareto_certificates_valid", report.all_branch_pareto_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_dominated_rejects_bound", report.source_dominated_reject_count == report.domain_count),
            requirement("source_pareto_commits_bound", report.source_pareto_commit_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("pareto_succeeds_all_domains", report.pareto_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_pareto_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_dominated_reject_count": report.source_dominated_reject_count,
            "source_pareto_commit_count": report.source_pareto_commit_count,
            "static_success_count": report.static_success_count,
            "pareto_success_count": report.pareto_success_count,
        },
        boundary=BRANCH_PARETO_CLAIM_BOUNDARY,
        sources=BRANCH_PARETO_SOURCES,
    )


def _make_pareto_traces(
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
            seeds=("branch-pareto-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.pareto.transfer.v1",
        )
        for action in actions
    )


def _pareto_actions(spec: ExplorationDomainSpec) -> Mapping[str, Mapping[str, Any]]:
    if spec.domain_id == "robotics_replan":
        return {
            "dominated_source": {
                "domain": spec.domain_id,
                "action": "scalar_fast_inner_skim",
                "utility": 9,
                "clearance": 0.18,
                "turn_rate": 0.70,
                "objectives": {"clearance_score": 0.18, "smoothness_score": 0.30},
            },
            "pareto_source": {
                "domain": spec.domain_id,
                "action": "pareto_balanced_clearance_arc",
                "utility": 7,
                "clearance": 0.34,
                "turn_rate": 0.42,
                "objectives": {"clearance_score": 0.34, "smoothness_score": 0.58},
                "target_commit": True,
            },
            "dominated_target": {
                "domain": spec.domain_id,
                "action": "scalar_fast_inner_skim",
                "utility": 9,
                "clearance": 0.13,
                "turn_rate": 0.76,
                "objectives": {"clearance_score": 0.13, "smoothness_score": 0.24},
            },
            "pareto_target": {
                "domain": spec.domain_id,
                "action": "pareto_balanced_clearance_arc",
                "utility": 7,
                "clearance": 0.35,
                "turn_rate": 0.40,
                "objectives": {"clearance_score": 0.35, "smoothness_score": 0.60},
                "target_commit": True,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "dominated_source": {
                "domain": spec.domain_id,
                "action": "scalar_compact_yield_patch",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.48,
                "objectives": {"stability_score": 0.52, "synthesis_score": 0.42},
            },
            "pareto_source": {
                "domain": spec.domain_id,
                "action": "pareto_relaxed_valence_bridge",
                "utility": 7,
                "valence_ok": True,
                "strain": 0.16,
                "objectives": {"stability_score": 0.84, "synthesis_score": 0.68},
                "target_commit": True,
            },
            "dominated_target": {
                "domain": spec.domain_id,
                "action": "scalar_compact_yield_patch",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.53,
                "objectives": {"stability_score": 0.47, "synthesis_score": 0.39},
            },
            "pareto_target": {
                "domain": spec.domain_id,
                "action": "pareto_relaxed_valence_bridge",
                "utility": 7,
                "valence_ok": True,
                "strain": 0.15,
                "objectives": {"stability_score": 0.85, "synthesis_score": 0.70},
                "target_commit": True,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "dominated_source": {
                "domain": spec.domain_id,
                "action": "scalar_high_throughput_quench",
                "utility": 9,
                "thermal_gradient": 0.66,
                "phase_purity": 0.87,
                "objectives": {"phase_score": 0.87, "throughput_score": 0.45},
            },
            "pareto_source": {
                "domain": spec.domain_id,
                "action": "pareto_staged_phase_balance",
                "utility": 7,
                "thermal_gradient": 0.38,
                "phase_purity": 0.95,
                "objectives": {"phase_score": 0.95, "throughput_score": 0.62},
                "target_commit": True,
            },
            "dominated_target": {
                "domain": spec.domain_id,
                "action": "scalar_high_throughput_quench",
                "utility": 9,
                "thermal_gradient": 0.70,
                "phase_purity": 0.86,
                "objectives": {"phase_score": 0.86, "throughput_score": 0.43},
            },
            "pareto_target": {
                "domain": spec.domain_id,
                "action": "pareto_staged_phase_balance",
                "utility": 7,
                "thermal_gradient": 0.39,
                "phase_purity": 0.95,
                "objectives": {"phase_score": 0.95, "throughput_score": 0.63},
                "target_commit": True,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _with_context(action: Mapping[str, Any], context: str) -> Mapping[str, Any]:
    return {**dict(action), "context": context}


def _pareto_dominates(dominated: Mapping[str, float], pareto: Mapping[str, float]) -> bool:
    left = _normalize_objectives(dominated)
    right = _normalize_objectives(pareto)
    if set(left) != set(right) or not left:
        return False
    return all(right[key] >= left[key] for key in left) and any(right[key] > left[key] for key in left)


def _dominance_margin_sum(dominated: Mapping[str, float], pareto: Mapping[str, float]) -> float:
    left = _normalize_objectives(dominated)
    right = _normalize_objectives(pareto)
    if set(left) != set(right):
        raise ValueError("objective keys must match")
    return sum(right[key] - left[key] for key in left)


def _normalize_objectives(values: Mapping[str, float]) -> dict[str, float]:
    normalized = {str(key): float(value) for key, value in values.items()}
    if not normalized or any(not key or not isfinite(value) for key, value in normalized.items()):
        raise ValueError("objectives must be finite and non-empty")
    return {key: normalized[key] for key in sorted(normalized)}


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_pareto_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
