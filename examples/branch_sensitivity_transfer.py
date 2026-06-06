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
    BranchRuntime,
    BranchSelectionCertificate,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


BRANCH_SENSITIVITY_CERTIFICATE_SCHEMA = "trwm.branch_sensitivity_certificate.v1"
BRANCH_SENSITIVITY_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_sensitivity_transfer_certificate.v1"
BRANCH_SENSITIVITY_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1080/00401706.1991.10484804",
    "https://doi.org/10.1109/9.119632",
)
BRANCH_SENSITIVITY_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound one-factor "
    "perturbation evidence can filter a wrong-direction target proposal before target exploration "
    "under a matched one-call verifier budget. It is not a global sensitivity analysis result, "
    "Morris elementary-effects implementation, SPSA implementation, finite-difference accuracy "
    "claim, gradient-estimation result, optimization result, robotics safety, chemistry, materials "
    "discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchSensitivityCertificate:
    schema_version: str
    domain: str
    sensitivity_rule_id: str
    sensitivity_rule_version: str
    source_context_id: str
    target_context_id: str
    parameter_id: str
    baseline_value: float
    perturbation_delta: float
    source_negative_action_id: str
    source_positive_action_id: str
    static_target_action: str
    sensitivity_target_action: str
    source_negative_value: float
    source_positive_value: float
    static_target_value: float
    sensitivity_target_value: float
    inferred_effect_sign: str
    source_negative_receipt_hashes: tuple[str, ...]
    source_positive_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    sensitivity_target_receipt_hashes: tuple[str, ...]
    sensitivity_target_commit_receipt_hashes: tuple[str, ...]
    source_negative_branch_selection_certificate_hash: str
    source_positive_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    sensitivity_branch_selection_certificate_hash: str
    source_negative_rejected: bool
    source_positive_committed: bool
    static_committed: bool
    sensitivity_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    sensitivity_verifier_call_count: int
    same_budget: bool
    sensitivity_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SENSITIVITY_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch sensitivity certificate schema: {self.schema_version}")
        for field_name in (
            "baseline_value",
            "perturbation_delta",
            "source_negative_value",
            "source_positive_value",
            "static_target_value",
            "sensitivity_target_value",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        for field_name in (
            "source_negative_receipt_hashes",
            "source_positive_receipt_hashes",
            "static_target_receipt_hashes",
            "sensitivity_target_receipt_hashes",
            "sensitivity_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_sensitivity_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchSensitivityDomainReport:
    domain: str
    source_context: str
    target_context: str
    parameter_id: str
    baseline_value: float
    perturbation_delta: float
    inferred_effect_sign: str
    source_negative_action_id: str
    source_positive_action_id: str
    static_target_action: str
    sensitivity_target_action: str
    source_negative_value: float
    source_positive_value: float
    static_target_value: float
    sensitivity_target_value: float
    source_negative_rejected: bool
    source_positive_committed: bool
    static_committed: bool
    sensitivity_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    sensitivity_verifier_call_count: int
    source_negative_receipt_hashes: tuple[str, ...]
    source_positive_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    sensitivity_target_receipt_hashes: tuple[str, ...]
    branch_sensitivity_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchSensitivityTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchSensitivityDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_negative_rejected_count: int
    source_positive_committed_count: int
    static_success_count: int
    sensitivity_success_count: int
    same_budget_sensitivity_count: int
    branch_sensitivity_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_sensitivity_certificates_valid: bool
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
class BranchSensitivityTransferCertificate:
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
    branch_sensitivity_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_negative_rejected_count: int
    source_positive_committed_count: int
    static_success_count: int
    sensitivity_success_count: int
    same_budget_sensitivity_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SENSITIVITY_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch sensitivity transfer certificate schema: {self.schema_version}")
        for field_name in ("domains", "receipt_hashes", "branch_selection_certificate_hashes", "branch_sensitivity_certificate_hashes"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_sensitivity_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchSensitivityTransferResult(CertifiedExampleResult):
    report: BranchSensitivityTransferReport
    branch_sensitivity_transfer_certificate: BranchSensitivityTransferCertificate
    branch_sensitivity_certificates: tuple[BranchSensitivityCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_sensitivity_transfer_experiment() -> BranchSensitivityTransferReport:
    return run_branch_sensitivity_transfer_certified_experiment().report


def run_branch_sensitivity_transfer_certified_experiment() -> CertifiedBranchSensitivityTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchSensitivityDomainReport] = []
    sensitivity_certificates: list[BranchSensitivityCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_sensitivity_plan(spec)
        source_context = f"{spec.domain_id}:source:branch-sensitivity"
        target_context = f"{spec.domain_id}:target:branch-sensitivity"

        negative_outcome = runtime.step(
            state,
            _make_sensitivity_traces(spec, context=source_context, phase="source-negative", actions=(plan["source_negative"],)),
        )
        negative_selection = build_branch_selection_certificate(negative_outcome.receipts, verifier_call_count=negative_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(negative_outcome.receipts), negative_selection))
        memory.update_branch(negative_outcome.receipts, negative_selection)

        positive_outcome = runtime.step(
            state,
            _make_sensitivity_traces(spec, context=source_context, phase="source-positive", actions=(plan["source_positive"],)),
        )
        state = normalize_state(positive_outcome.state)
        positive_selection = build_branch_selection_certificate(positive_outcome.receipts, verifier_call_count=positive_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(positive_outcome.receipts), positive_selection))
        memory.update_branch(positive_outcome.receipts, positive_selection)

        static_outcome = runtime.step(
            state,
            _make_sensitivity_traces(spec, context=target_context, phase="target-static-negative", actions=(plan["target_static"],)),
        )
        static_selection = build_branch_selection_certificate(static_outcome.receipts, verifier_call_count=static_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        sensitivity_outcome = runtime.step(
            state,
            _make_sensitivity_traces(spec, context=target_context, phase="target-sensitivity-positive", actions=(plan["target_sensitivity"],)),
        )
        state = normalize_state(sensitivity_outcome.state)
        sensitivity_selection = build_branch_selection_certificate(
            sensitivity_outcome.receipts,
            verifier_call_count=sensitivity_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(sensitivity_outcome.receipts), sensitivity_selection))

        certificate = build_branch_sensitivity_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            parameter_id=str(plan["parameter_id"]),
            baseline_value=float(plan["baseline_value"]),
            perturbation_delta=float(plan["perturbation_delta"]),
            source_negative_action_id=str(plan["source_negative"]["action"]),
            source_positive_action_id=str(plan["source_positive"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            sensitivity_target_action=str(plan["target_sensitivity"]["action"]),
            source_negative_value=float(plan["source_negative"]["parameter_value"]),
            source_positive_value=float(plan["source_positive"]["parameter_value"]),
            static_target_value=float(plan["target_static"]["parameter_value"]),
            sensitivity_target_value=float(plan["target_sensitivity"]["parameter_value"]),
            source_negative_receipt_hashes=tuple(receipt.receipt_hash for receipt in negative_outcome.receipts),
            source_positive_receipt_hashes=tuple(receipt.receipt_hash for receipt in positive_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            sensitivity_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in sensitivity_outcome.receipts),
            sensitivity_target_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in sensitivity_outcome.receipts if receipt.committed),
            source_negative_branch_selection_certificate_hash=negative_selection.certificate_hash,
            source_positive_branch_selection_certificate_hash=positive_selection.certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            sensitivity_branch_selection_certificate_hash=sensitivity_selection.certificate_hash,
            source_negative_rejected=any(receipt.hard_result.rejected for receipt in negative_outcome.receipts),
            source_positive_committed=positive_outcome.committed,
            static_committed=static_outcome.committed,
            sensitivity_committed=sensitivity_outcome.committed,
            source_verifier_call_count=negative_outcome.verifier_calls + positive_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            sensitivity_verifier_call_count=sensitivity_outcome.verifier_calls,
        )
        sensitivity_certificates.append(certificate)
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

    report = BranchSensitivityTransferReport(
        schema_version="trwm.example.branch_sensitivity_transfer.v1",
        experiment_id="branch_sensitivity_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_negative_rejected_count=sum(1 for row in rows if row.source_negative_rejected),
        source_positive_committed_count=sum(1 for row in rows if row.source_positive_committed),
        static_success_count=sum(1 for row in rows if row.static_committed),
        sensitivity_success_count=sum(1 for row in rows if row.sensitivity_committed),
        same_budget_sensitivity_count=sum(1 for row in rows if row.same_budget),
        branch_sensitivity_certificate_count=len(sensitivity_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_sensitivity_certificates_valid=all(
            validate_branch_sensitivity_certificate(certificate, row)
            for certificate, row in zip(sensitivity_certificates, rows)
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
        sources=BRANCH_SENSITIVITY_SOURCES,
        learning=(
            "Sensitivity reuse separates one-factor perturbation evidence from commit authority. Source receipts "
            "can identify the useful direction of a parameter change and demote the wrong direction, but the "
            "target branch still commits only through a fresh hard-verifier receipt."
        ),
    )
    transfer_certificate = build_branch_sensitivity_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_sensitivity_certificate_hashes=tuple(certificate.certificate_hash for certificate in sensitivity_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_sensitivity_transfer",
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
        claim_boundary=BRANCH_SENSITIVITY_CLAIM_BOUNDARY,
        sources=BRANCH_SENSITIVITY_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchSensitivityTransferResult(
        report=report,
        branch_sensitivity_transfer_certificate=transfer_certificate,
        branch_sensitivity_certificates=tuple(sensitivity_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_sensitivity_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    parameter_id: str,
    baseline_value: float,
    perturbation_delta: float,
    source_negative_action_id: str,
    source_positive_action_id: str,
    static_target_action: str,
    sensitivity_target_action: str,
    source_negative_value: float,
    source_positive_value: float,
    static_target_value: float,
    sensitivity_target_value: float,
    source_negative_receipt_hashes: tuple[str, ...],
    source_positive_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    sensitivity_target_receipt_hashes: tuple[str, ...],
    sensitivity_target_commit_receipt_hashes: tuple[str, ...],
    source_negative_branch_selection_certificate_hash: str,
    source_positive_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    sensitivity_branch_selection_certificate_hash: str,
    source_negative_rejected: bool,
    source_positive_committed: bool,
    static_committed: bool,
    sensitivity_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    sensitivity_verifier_call_count: int,
) -> BranchSensitivityCertificate:
    return BranchSensitivityCertificate(
        schema_version=BRANCH_SENSITIVITY_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        sensitivity_rule_id="receipt_bound_one_factor_sensitivity",
        sensitivity_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        parameter_id=parameter_id,
        baseline_value=baseline_value,
        perturbation_delta=perturbation_delta,
        source_negative_action_id=source_negative_action_id,
        source_positive_action_id=source_positive_action_id,
        static_target_action=static_target_action,
        sensitivity_target_action=sensitivity_target_action,
        source_negative_value=source_negative_value,
        source_positive_value=source_positive_value,
        static_target_value=static_target_value,
        sensitivity_target_value=sensitivity_target_value,
        inferred_effect_sign="positive",
        source_negative_receipt_hashes=source_negative_receipt_hashes,
        source_positive_receipt_hashes=source_positive_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        sensitivity_target_receipt_hashes=sensitivity_target_receipt_hashes,
        sensitivity_target_commit_receipt_hashes=sensitivity_target_commit_receipt_hashes,
        source_negative_branch_selection_certificate_hash=source_negative_branch_selection_certificate_hash,
        source_positive_branch_selection_certificate_hash=source_positive_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        sensitivity_branch_selection_certificate_hash=sensitivity_branch_selection_certificate_hash,
        source_negative_rejected=source_negative_rejected,
        source_positive_committed=source_positive_committed,
        static_committed=static_committed,
        sensitivity_committed=sensitivity_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        sensitivity_verifier_call_count=sensitivity_verifier_call_count,
        same_budget=static_verifier_call_count == sensitivity_verifier_call_count == 1,
        sensitivity_reason="source_positive_perturbation_commits_and_negative_rejects",
    )


def validate_branch_sensitivity_certificate(
    certificate: BranchSensitivityCertificate,
    row: BranchSensitivityDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_SENSITIVITY_CERTIFICATE_SCHEMA:
            return False
        if certificate.sensitivity_rule_id != "receipt_bound_one_factor_sensitivity":
            return False
        if certificate.sensitivity_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.parameter_id):
            return False
        if not _finite(certificate.baseline_value) or not _finite(certificate.perturbation_delta):
            return False
        if certificate.perturbation_delta <= 0:
            return False
        expected_negative = certificate.baseline_value - certificate.perturbation_delta
        expected_positive = certificate.baseline_value + certificate.perturbation_delta
        if abs(certificate.source_negative_value - expected_negative) > 1e-9:
            return False
        if abs(certificate.source_positive_value - expected_positive) > 1e-9:
            return False
        if abs(certificate.static_target_value - expected_negative) > 1e-9:
            return False
        if abs(certificate.sensitivity_target_value - expected_positive) > 1e-9:
            return False
        if certificate.inferred_effect_sign != "positive":
            return False
        action_ids = (
            certificate.source_negative_action_id,
            certificate.source_positive_action_id,
            certificate.static_target_action,
            certificate.sensitivity_target_action,
        )
        if len(set(action_ids)) != len(action_ids) or any(not _nonempty(action_id) for action_id in action_ids):
            return False
        if not (
            certificate.source_negative_rejected
            and certificate.source_positive_committed
            and not certificate.static_committed
            and certificate.sensitivity_committed
        ):
            return False
        if certificate.source_verifier_call_count != 2:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.sensitivity_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.sensitivity_reason != "source_positive_perturbation_commits_and_negative_rejects":
            return False
        hash_groups = (
            (certificate.source_negative_receipt_hashes, 1),
            (certificate.source_positive_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.sensitivity_target_receipt_hashes, 1),
            (certificate.sensitivity_target_commit_receipt_hashes, 1),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_negative_branch_selection_certificate_hash,
            certificate.source_positive_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.sensitivity_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.parameter_id != certificate.parameter_id:
                return False
            if row.baseline_value != certificate.baseline_value or row.perturbation_delta != certificate.perturbation_delta:
                return False
            if row.inferred_effect_sign != certificate.inferred_effect_sign:
                return False
            if row.source_negative_action_id != certificate.source_negative_action_id:
                return False
            if row.source_positive_action_id != certificate.source_positive_action_id:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.sensitivity_target_action != certificate.sensitivity_target_action:
                return False
            if row.source_negative_receipt_hashes != certificate.source_negative_receipt_hashes:
                return False
            if row.source_positive_receipt_hashes != certificate.source_positive_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.sensitivity_target_receipt_hashes != certificate.sensitivity_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_sensitivity_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_sensitivity_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_sensitivity_transfer_certificate(
    report: BranchSensitivityTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_sensitivity_certificate_hashes: tuple[str, ...],
) -> BranchSensitivityTransferCertificate:
    return BranchSensitivityTransferCertificate(
        schema_version=BRANCH_SENSITIVITY_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_sensitivity_certificate_hashes=branch_sensitivity_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_negative_rejected_count=report.source_negative_rejected_count,
        source_positive_committed_count=report.source_positive_committed_count,
        static_success_count=report.static_success_count,
        sensitivity_success_count=report.sensitivity_success_count,
        same_budget_sensitivity_count=report.same_budget_sensitivity_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_SENSITIVITY_CLAIM_BOUNDARY,
    )


def validate_branch_sensitivity_transfer_certificate(
    certificate: BranchSensitivityTransferCertificate,
    report: BranchSensitivityTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_SENSITIVITY_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        if not _is_hash(certificate.report_hash) or not _is_hash(certificate.ledger_head):
            return False
        if not _is_hash(certificate.memory_snapshot_hash):
            return False
        for values in (certificate.receipt_hashes, certificate.branch_selection_certificate_hashes, certificate.branch_sensitivity_certificate_hashes):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_sensitivity_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_negative_rejected_count != certificate.domain_count:
            return False
        if certificate.source_positive_committed_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.sensitivity_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_sensitivity_count != certificate.domain_count:
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
            if tuple(row.branch_sensitivity_certificate_hash for row in report.rows) != certificate.branch_sensitivity_certificate_hashes:
                return False
            if report.branch_sensitivity_certificate_count != len(certificate.branch_sensitivity_certificate_hashes):
                return False
            if not report.all_branch_sensitivity_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_negative_rejected_count != certificate.source_negative_rejected_count:
                return False
            if report.source_positive_committed_count != certificate.source_positive_committed_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.sensitivity_success_count != certificate.sensitivity_success_count:
                return False
            if report.same_budget_sensitivity_count != certificate.same_budget_sensitivity_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_sensitivity_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_sensitivity_certificate_hash(certificate: BranchSensitivityCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchSensitivityCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_sensitivity_transfer_certificate_hash(certificate: BranchSensitivityTransferCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchSensitivityTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchSensitivityTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchSensitivityTransferReport,
    transfer_certificate: BranchSensitivityTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_sensitivity_transfer_g1",
        claim_text=(
            "Receipt-bound one-factor sensitivity certificates can improve local target exploration "
            "by filtering wrong-direction target perturbations and trying useful-direction branches "
            "under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_sensitivity_transfer",
        requirements=(
            requirement(
                "branch_sensitivity_transfer_certificate_valid",
                validate_branch_sensitivity_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_sensitivity_certificates_valid", report.all_branch_sensitivity_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_negative_rejects_all_domains", report.source_negative_rejected_count == report.domain_count),
            requirement("source_positive_commits_all_domains", report.source_positive_committed_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("sensitivity_succeeds_all_domains", report.sensitivity_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_sensitivity_count == report.domain_count),
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
            "sensitivity_success_count": report.sensitivity_success_count,
        },
        boundary=BRANCH_SENSITIVITY_CLAIM_BOUNDARY,
        sources=BRANCH_SENSITIVITY_SOURCES,
    )


def _row_from_certificate(certificate: BranchSensitivityCertificate) -> BranchSensitivityDomainReport:
    return BranchSensitivityDomainReport(
        domain=certificate.domain,
        source_context=certificate.source_context_id,
        target_context=certificate.target_context_id,
        parameter_id=certificate.parameter_id,
        baseline_value=certificate.baseline_value,
        perturbation_delta=certificate.perturbation_delta,
        inferred_effect_sign=certificate.inferred_effect_sign,
        source_negative_action_id=certificate.source_negative_action_id,
        source_positive_action_id=certificate.source_positive_action_id,
        static_target_action=certificate.static_target_action,
        sensitivity_target_action=certificate.sensitivity_target_action,
        source_negative_value=certificate.source_negative_value,
        source_positive_value=certificate.source_positive_value,
        static_target_value=certificate.static_target_value,
        sensitivity_target_value=certificate.sensitivity_target_value,
        source_negative_rejected=certificate.source_negative_rejected,
        source_positive_committed=certificate.source_positive_committed,
        static_committed=certificate.static_committed,
        sensitivity_committed=certificate.sensitivity_committed,
        source_verifier_call_count=certificate.source_verifier_call_count,
        static_verifier_call_count=certificate.static_verifier_call_count,
        sensitivity_verifier_call_count=certificate.sensitivity_verifier_call_count,
        source_negative_receipt_hashes=certificate.source_negative_receipt_hashes,
        source_positive_receipt_hashes=certificate.source_positive_receipt_hashes,
        static_target_receipt_hashes=certificate.static_target_receipt_hashes,
        sensitivity_target_receipt_hashes=certificate.sensitivity_target_receipt_hashes,
        branch_sensitivity_certificate_hash=certificate.certificate_hash,
        same_budget=certificate.same_budget,
    )


def _make_sensitivity_traces(
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
            seeds=("branch-sensitivity-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.sensitivity.transfer.v1",
        )
        for action in actions
    )


def _domain_sensitivity_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    base = {
        "baseline_value": 0.20,
        "perturbation_delta": 0.15,
    }
    if spec.domain_id == "robotics_replan":
        parameter_id = "detour_width"
        return {
            **base,
            "parameter_id": parameter_id,
            "source_negative": {"domain": spec.domain_id, "action": "sensitivity_source_narrow_detour", "utility": 9, "parameter_id": parameter_id, "parameter_value": 0.05, "clearance": 0.18, "turn_rate": 0.77},
            "source_positive": {"domain": spec.domain_id, "action": "sensitivity_source_widen_detour", "utility": 8, "parameter_id": parameter_id, "parameter_value": 0.35, "clearance": 0.35, "turn_rate": 0.43},
            "target_static": {"domain": spec.domain_id, "action": "sensitivity_target_narrow_detour", "utility": 9, "parameter_id": parameter_id, "parameter_value": 0.05, "clearance": 0.17, "turn_rate": 0.80},
            "target_sensitivity": {"domain": spec.domain_id, "action": "sensitivity_target_widen_detour", "utility": 8, "parameter_id": parameter_id, "parameter_value": 0.35, "clearance": 0.36, "turn_rate": 0.42},
        }
    if spec.domain_id == "molecule_repair":
        parameter_id = "relaxation_strength"
        return {
            **base,
            "parameter_id": parameter_id,
            "source_negative": {"domain": spec.domain_id, "action": "sensitivity_source_under_relax", "utility": 9, "parameter_id": parameter_id, "parameter_value": 0.05, "valence_ok": False, "strain": 0.43},
            "source_positive": {"domain": spec.domain_id, "action": "sensitivity_source_relax_repair", "utility": 8, "parameter_id": parameter_id, "parameter_value": 0.35, "valence_ok": True, "strain": 0.19},
            "target_static": {"domain": spec.domain_id, "action": "sensitivity_target_under_relax", "utility": 9, "parameter_id": parameter_id, "parameter_value": 0.05, "valence_ok": False, "strain": 0.41},
            "target_sensitivity": {"domain": spec.domain_id, "action": "sensitivity_target_relax_repair", "utility": 8, "parameter_id": parameter_id, "parameter_value": 0.35, "valence_ok": True, "strain": 0.18},
        }
    if spec.domain_id == "material_process":
        parameter_id = "anneal_time"
        return {
            **base,
            "parameter_id": parameter_id,
            "source_negative": {"domain": spec.domain_id, "action": "sensitivity_source_short_anneal", "utility": 9, "parameter_id": parameter_id, "parameter_value": 0.05, "thermal_gradient": 0.72, "phase_purity": 0.86},
            "source_positive": {"domain": spec.domain_id, "action": "sensitivity_source_long_anneal", "utility": 8, "parameter_id": parameter_id, "parameter_value": 0.35, "thermal_gradient": 0.39, "phase_purity": 0.95},
            "target_static": {"domain": spec.domain_id, "action": "sensitivity_target_short_anneal", "utility": 9, "parameter_id": parameter_id, "parameter_value": 0.05, "thermal_gradient": 0.70, "phase_purity": 0.87},
            "target_sensitivity": {"domain": spec.domain_id, "action": "sensitivity_target_long_anneal", "utility": 8, "parameter_id": parameter_id, "parameter_value": 0.35, "thermal_gradient": 0.38, "phase_purity": 0.96},
        }
    raise ValueError(f"unknown sensitivity domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _finite(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value))


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_sensitivity_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
