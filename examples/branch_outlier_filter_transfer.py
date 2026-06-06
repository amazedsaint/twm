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


BRANCH_OUTLIER_FILTER_CERTIFICATE_SCHEMA = "trwm.branch_outlier_filter_certificate.v1"
BRANCH_OUTLIER_FILTER_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_outlier_filter_transfer_certificate.v1"
BRANCH_OUTLIER_FILTER_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1145/358669.358692",
)
BRANCH_OUTLIER_FILTER_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound feature inliers can "
    "filter an anomalous but source-valid branch before target exploration under a matched one-call "
    "verifier budget. It is not a RANSAC implementation, robust estimator, outlier-detection guarantee, "
    "robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchOutlierFilterCertificate:
    schema_version: str
    domain: str
    filter_rule_id: str
    filter_rule_version: str
    source_context_ids: tuple[str, ...]
    target_context_id: str
    feature_key: str
    inlier_actions: tuple[str, ...]
    outlier_action: str
    static_target_action: str
    filtered_target_action: str
    inlier_feature_values: tuple[float, ...]
    outlier_feature_value: float
    static_target_feature_value: float
    filtered_target_feature_value: float
    inlier_centroid: float
    max_inlier_distance: float
    outlier_distance: float
    distance_threshold: float
    source_inlier_receipt_hashes: tuple[str, ...]
    source_outlier_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    filtered_target_receipt_hashes: tuple[str, ...]
    filtered_target_commit_receipt_hashes: tuple[str, ...]
    source_inlier_branch_selection_certificate_hashes: tuple[str, ...]
    source_outlier_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    filtered_branch_selection_certificate_hash: str
    source_inlier_committed_count: int
    source_outlier_committed_count: int
    static_committed: bool
    filtered_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    filtered_verifier_call_count: int
    same_budget: bool
    filter_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_OUTLIER_FILTER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch outlier filter certificate schema: {self.schema_version}")
        for field_name in (
            "source_context_ids",
            "inlier_actions",
            "inlier_feature_values",
            "source_inlier_receipt_hashes",
            "source_outlier_receipt_hashes",
            "static_target_receipt_hashes",
            "filtered_target_receipt_hashes",
            "filtered_target_commit_receipt_hashes",
            "source_inlier_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "outlier_feature_value",
            "static_target_feature_value",
            "filtered_target_feature_value",
            "inlier_centroid",
            "max_inlier_distance",
            "outlier_distance",
            "distance_threshold",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_outlier_filter_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchOutlierFilterDomainReport:
    domain: str
    source_contexts: tuple[str, ...]
    target_context: str
    feature_key: str
    inlier_actions: tuple[str, ...]
    outlier_action: str
    static_target_action: str
    filtered_target_action: str
    inlier_feature_values: tuple[float, ...]
    outlier_feature_value: float
    static_target_feature_value: float
    filtered_target_feature_value: float
    inlier_centroid: float
    max_inlier_distance: float
    outlier_distance: float
    distance_threshold: float
    source_inlier_committed_count: int
    source_outlier_committed_count: int
    static_committed: bool
    filtered_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    filtered_verifier_call_count: int
    source_inlier_receipt_hashes: tuple[str, ...]
    source_outlier_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    filtered_target_receipt_hashes: tuple[str, ...]
    branch_outlier_filter_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchOutlierFilterTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchOutlierFilterDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_inlier_success_count: int
    source_outlier_success_count: int
    static_success_count: int
    filtered_success_count: int
    same_budget_filter_count: int
    branch_outlier_filter_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_outlier_filter_certificates_valid: bool
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
class BranchOutlierFilterTransferCertificate:
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
    branch_outlier_filter_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_inlier_success_count: int
    source_outlier_success_count: int
    static_success_count: int
    filtered_success_count: int
    same_budget_filter_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_OUTLIER_FILTER_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch outlier filter transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_outlier_filter_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_outlier_filter_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchOutlierFilterTransferResult(CertifiedExampleResult):
    report: BranchOutlierFilterTransferReport
    branch_outlier_filter_transfer_certificate: BranchOutlierFilterTransferCertificate
    branch_outlier_filter_certificates: tuple[BranchOutlierFilterCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_outlier_filter_transfer_experiment() -> BranchOutlierFilterTransferReport:
    return run_branch_outlier_filter_transfer_certified_experiment().report


def run_branch_outlier_filter_transfer_certified_experiment() -> CertifiedBranchOutlierFilterTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchOutlierFilterDomainReport] = []
    outlier_filter_certificates: list[BranchOutlierFilterCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_contexts = (
            f"{spec.domain_id}:source:outlier_filter:inlier_a",
            f"{spec.domain_id}:source:outlier_filter:inlier_b",
            f"{spec.domain_id}:source:outlier_filter:outlier",
        )
        target_context = f"{spec.domain_id}:target:outlier_filter"
        plan = _domain_outlier_filter_plan(spec, source_contexts, target_context)

        source_outcomes = []
        source_certificates = []
        for source_context, source_action in zip(source_contexts, plan["source_actions"]):
            outcome = runtime.step(
                state,
                _make_outlier_filter_traces(
                    spec,
                    context=source_context,
                    phase="source-outlier-filter",
                    actions=(source_action,),
                ),
            )
            state = normalize_state(outcome.state)
            certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), certificate))
            memory.update_branch(outcome.receipts, certificate)
            source_outcomes.append(outcome)
            source_certificates.append(certificate)

        static_outcome = runtime.step(
            state,
            _make_outlier_filter_traces(
                spec,
                context=target_context,
                phase="target-unfiltered-outlier",
                actions=(plan["target_static"],),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        filtered_outcome = runtime.step(
            state,
            _make_outlier_filter_traces(
                spec,
                context=target_context,
                phase="target-inlier-filtered",
                actions=(plan["target_filtered"],),
            ),
        )
        state = normalize_state(filtered_outcome.state)
        filtered_certificate = build_branch_selection_certificate(
            filtered_outcome.receipts,
            verifier_call_count=filtered_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(filtered_outcome.receipts), filtered_certificate))

        inlier_outcomes = tuple(source_outcomes[:2])
        outlier_outcomes = tuple(source_outcomes[2:])
        inlier_certificates = tuple(source_certificates[:2])
        outlier_certificate = source_certificates[2]
        inlier_values = tuple(float(value) for value in plan["inlier_feature_values"])
        outlier_value = float(plan["outlier_feature_value"])
        centroid = sum(inlier_values) / len(inlier_values)
        inlier_distances = tuple(abs(value - centroid) for value in inlier_values)
        outlier_distance = abs(outlier_value - centroid)

        certificate = build_branch_outlier_filter_certificate(
            spec,
            source_context_ids=source_contexts,
            target_context_id=target_context,
            feature_key=str(plan["feature_key"]),
            inlier_actions=tuple(str(action["action"]) for action in plan["source_actions"][:2]),
            outlier_action=str(plan["source_actions"][2]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            filtered_target_action=str(plan["target_filtered"]["action"]),
            inlier_feature_values=inlier_values,
            outlier_feature_value=outlier_value,
            static_target_feature_value=float(plan["static_target_feature_value"]),
            filtered_target_feature_value=float(plan["filtered_target_feature_value"]),
            inlier_centroid=centroid,
            max_inlier_distance=max(inlier_distances),
            outlier_distance=outlier_distance,
            distance_threshold=float(plan["distance_threshold"]),
            source_inlier_receipt_hashes=tuple(
                receipt.receipt_hash
                for outcome in inlier_outcomes
                for receipt in outcome.receipts
                if receipt.committed
            ),
            source_outlier_receipt_hashes=tuple(
                receipt.receipt_hash
                for outcome in outlier_outcomes
                for receipt in outcome.receipts
                if receipt.committed
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            filtered_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in filtered_outcome.receipts),
            filtered_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in filtered_outcome.receipts if receipt.committed
            ),
            source_inlier_branch_selection_certificate_hashes=tuple(
                selection.certificate_hash for selection in inlier_certificates
            ),
            source_outlier_branch_selection_certificate_hash=outlier_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            filtered_branch_selection_certificate_hash=filtered_certificate.certificate_hash,
            source_inlier_committed_count=sum(1 for outcome in inlier_outcomes if outcome.committed),
            source_outlier_committed_count=sum(1 for outcome in outlier_outcomes if outcome.committed),
            static_committed=static_outcome.committed,
            filtered_committed=filtered_outcome.committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in source_outcomes),
            static_verifier_call_count=static_outcome.verifier_calls,
            filtered_verifier_call_count=filtered_outcome.verifier_calls,
        )
        outlier_filter_certificates.append(certificate)
        rows.append(
            BranchOutlierFilterDomainReport(
                domain=spec.domain_id,
                source_contexts=certificate.source_context_ids,
                target_context=certificate.target_context_id,
                feature_key=certificate.feature_key,
                inlier_actions=certificate.inlier_actions,
                outlier_action=certificate.outlier_action,
                static_target_action=certificate.static_target_action,
                filtered_target_action=certificate.filtered_target_action,
                inlier_feature_values=certificate.inlier_feature_values,
                outlier_feature_value=certificate.outlier_feature_value,
                static_target_feature_value=certificate.static_target_feature_value,
                filtered_target_feature_value=certificate.filtered_target_feature_value,
                inlier_centroid=certificate.inlier_centroid,
                max_inlier_distance=certificate.max_inlier_distance,
                outlier_distance=certificate.outlier_distance,
                distance_threshold=certificate.distance_threshold,
                source_inlier_committed_count=certificate.source_inlier_committed_count,
                source_outlier_committed_count=certificate.source_outlier_committed_count,
                static_committed=certificate.static_committed,
                filtered_committed=certificate.filtered_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                filtered_verifier_call_count=certificate.filtered_verifier_call_count,
                source_inlier_receipt_hashes=certificate.source_inlier_receipt_hashes,
                source_outlier_receipt_hashes=certificate.source_outlier_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                filtered_target_receipt_hashes=certificate.filtered_target_receipt_hashes,
                branch_outlier_filter_certificate_hash=certificate.certificate_hash,
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

    report = BranchOutlierFilterTransferReport(
        schema_version="trwm.example.branch_outlier_filter_transfer.v1",
        experiment_id="branch_outlier_filter_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_inlier_success_count=sum(row.source_inlier_committed_count for row in rows),
        source_outlier_success_count=sum(row.source_outlier_committed_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        filtered_success_count=sum(1 for row in rows if row.filtered_committed),
        same_budget_filter_count=sum(1 for row in rows if row.same_budget),
        branch_outlier_filter_certificate_count=len(outlier_filter_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_outlier_filter_certificates_valid=all(
            validate_branch_outlier_filter_certificate(certificate, row)
            for certificate, row in zip(outlier_filter_certificates, rows)
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
        sources=BRANCH_OUTLIER_FILTER_SOURCES,
        learning=(
            "Outlier-filtered branch reuse separates source validity from target usefulness. A source-valid "
            "anomalous branch can be bound as evidence without receiving target priority when its feature "
            "distance exceeds the receipt-bound inlier threshold; the selected inlier target proposal still "
            "needs a fresh hard-verifier receipt before commit."
        ),
    )
    transfer_certificate = build_branch_outlier_filter_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_outlier_filter_certificate_hashes=tuple(
            certificate.certificate_hash for certificate in outlier_filter_certificates
        ),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_outlier_filter_transfer",
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
        claim_boundary=BRANCH_OUTLIER_FILTER_CLAIM_BOUNDARY,
        sources=BRANCH_OUTLIER_FILTER_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchOutlierFilterTransferResult(
        report=report,
        branch_outlier_filter_transfer_certificate=transfer_certificate,
        branch_outlier_filter_certificates=tuple(outlier_filter_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_outlier_filter_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_ids: tuple[str, ...],
    target_context_id: str,
    feature_key: str,
    inlier_actions: tuple[str, ...],
    outlier_action: str,
    static_target_action: str,
    filtered_target_action: str,
    inlier_feature_values: tuple[float, ...],
    outlier_feature_value: float,
    static_target_feature_value: float,
    filtered_target_feature_value: float,
    inlier_centroid: float,
    max_inlier_distance: float,
    outlier_distance: float,
    distance_threshold: float,
    source_inlier_receipt_hashes: tuple[str, ...],
    source_outlier_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    filtered_target_receipt_hashes: tuple[str, ...],
    filtered_target_commit_receipt_hashes: tuple[str, ...],
    source_inlier_branch_selection_certificate_hashes: tuple[str, ...],
    source_outlier_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    filtered_branch_selection_certificate_hash: str,
    source_inlier_committed_count: int,
    source_outlier_committed_count: int,
    static_committed: bool,
    filtered_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    filtered_verifier_call_count: int,
) -> BranchOutlierFilterCertificate:
    return BranchOutlierFilterCertificate(
        schema_version=BRANCH_OUTLIER_FILTER_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        filter_rule_id="feature_inlier_distance_filter",
        filter_rule_version="1.0",
        source_context_ids=source_context_ids,
        target_context_id=target_context_id,
        feature_key=feature_key,
        inlier_actions=inlier_actions,
        outlier_action=outlier_action,
        static_target_action=static_target_action,
        filtered_target_action=filtered_target_action,
        inlier_feature_values=inlier_feature_values,
        outlier_feature_value=outlier_feature_value,
        static_target_feature_value=static_target_feature_value,
        filtered_target_feature_value=filtered_target_feature_value,
        inlier_centroid=inlier_centroid,
        max_inlier_distance=max_inlier_distance,
        outlier_distance=outlier_distance,
        distance_threshold=distance_threshold,
        source_inlier_receipt_hashes=source_inlier_receipt_hashes,
        source_outlier_receipt_hashes=source_outlier_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        filtered_target_receipt_hashes=filtered_target_receipt_hashes,
        filtered_target_commit_receipt_hashes=filtered_target_commit_receipt_hashes,
        source_inlier_branch_selection_certificate_hashes=source_inlier_branch_selection_certificate_hashes,
        source_outlier_branch_selection_certificate_hash=source_outlier_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        filtered_branch_selection_certificate_hash=filtered_branch_selection_certificate_hash,
        source_inlier_committed_count=source_inlier_committed_count,
        source_outlier_committed_count=source_outlier_committed_count,
        static_committed=static_committed,
        filtered_committed=filtered_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        filtered_verifier_call_count=filtered_verifier_call_count,
        same_budget=static_verifier_call_count == filtered_verifier_call_count == 1,
        filter_reason="source_outlier_distance_exceeds_threshold",
    )


def validate_branch_outlier_filter_certificate(
    certificate: BranchOutlierFilterCertificate,
    row: BranchOutlierFilterDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_OUTLIER_FILTER_CERTIFICATE_SCHEMA:
            return False
        if certificate.filter_rule_id != "feature_inlier_distance_filter" or certificate.filter_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.target_context_id,
            certificate.feature_key,
            certificate.outlier_action,
            certificate.static_target_action,
            certificate.filtered_target_action,
        ):
            if not _nonempty(value):
                return False
        if len(certificate.source_context_ids) != 3 or len(set(certificate.source_context_ids)) != 3:
            return False
        if len(certificate.inlier_actions) != 2 or len(set(certificate.inlier_actions)) != 2:
            return False
        if certificate.outlier_action in certificate.inlier_actions:
            return False
        if certificate.static_target_action == certificate.filtered_target_action:
            return False
        values = (
            *certificate.inlier_feature_values,
            certificate.outlier_feature_value,
            certificate.static_target_feature_value,
            certificate.filtered_target_feature_value,
            certificate.inlier_centroid,
            certificate.max_inlier_distance,
            certificate.outlier_distance,
            certificate.distance_threshold,
        )
        if any(not _finite_number(value) for value in values):
            return False
        if len(certificate.inlier_feature_values) != 2:
            return False
        expected_centroid = sum(certificate.inlier_feature_values) / 2.0
        expected_inlier_distance = max(abs(value - expected_centroid) for value in certificate.inlier_feature_values)
        expected_outlier_distance = abs(certificate.outlier_feature_value - expected_centroid)
        if abs(certificate.inlier_centroid - expected_centroid) > 1e-12:
            return False
        if abs(certificate.max_inlier_distance - expected_inlier_distance) > 1e-12:
            return False
        if abs(certificate.outlier_distance - expected_outlier_distance) > 1e-12:
            return False
        if certificate.distance_threshold <= 0:
            return False
        if certificate.max_inlier_distance > certificate.distance_threshold:
            return False
        if certificate.outlier_distance <= certificate.distance_threshold:
            return False
        filtered_target_distance = abs(certificate.filtered_target_feature_value - certificate.inlier_centroid)
        static_target_distance = abs(certificate.static_target_feature_value - certificate.inlier_centroid)
        if filtered_target_distance > certificate.distance_threshold:
            return False
        if static_target_distance <= certificate.distance_threshold:
            return False
        if certificate.source_inlier_committed_count != 2 or certificate.source_outlier_committed_count != 1:
            return False
        if certificate.static_committed or not certificate.filtered_committed:
            return False
        if certificate.source_verifier_call_count != 3:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.filtered_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.filter_reason != "source_outlier_distance_exceeds_threshold":
            return False
        hash_groups = (
            (certificate.source_inlier_receipt_hashes, 2),
            (certificate.source_outlier_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.filtered_target_receipt_hashes, 1),
            (certificate.filtered_target_commit_receipt_hashes, 1),
            (certificate.source_inlier_branch_selection_certificate_hashes, 2),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_outlier_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.filtered_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_contexts != certificate.source_context_ids or row.target_context != certificate.target_context_id:
                return False
            if row.feature_key != certificate.feature_key:
                return False
            if row.inlier_actions != certificate.inlier_actions:
                return False
            if row.outlier_action != certificate.outlier_action:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.filtered_target_action != certificate.filtered_target_action:
                return False
            if row.inlier_feature_values != certificate.inlier_feature_values:
                return False
            if row.outlier_feature_value != certificate.outlier_feature_value:
                return False
            if row.static_target_feature_value != certificate.static_target_feature_value:
                return False
            if row.filtered_target_feature_value != certificate.filtered_target_feature_value:
                return False
            if row.source_inlier_receipt_hashes != certificate.source_inlier_receipt_hashes:
                return False
            if row.source_outlier_receipt_hashes != certificate.source_outlier_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.filtered_target_receipt_hashes != certificate.filtered_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_outlier_filter_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_outlier_filter_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_outlier_filter_transfer_certificate(
    report: BranchOutlierFilterTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_outlier_filter_certificate_hashes: tuple[str, ...],
) -> BranchOutlierFilterTransferCertificate:
    return BranchOutlierFilterTransferCertificate(
        schema_version=BRANCH_OUTLIER_FILTER_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_outlier_filter_certificate_hashes=branch_outlier_filter_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_inlier_success_count=report.source_inlier_success_count,
        source_outlier_success_count=report.source_outlier_success_count,
        static_success_count=report.static_success_count,
        filtered_success_count=report.filtered_success_count,
        same_budget_filter_count=report.same_budget_filter_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_OUTLIER_FILTER_CLAIM_BOUNDARY,
    )


def validate_branch_outlier_filter_transfer_certificate(
    certificate: BranchOutlierFilterTransferCertificate,
    report: BranchOutlierFilterTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_OUTLIER_FILTER_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_outlier_filter_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_outlier_filter_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_inlier_success_count != certificate.domain_count * 2:
            return False
        if certificate.source_outlier_success_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.filtered_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_filter_count != certificate.domain_count:
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
            if tuple(row.branch_outlier_filter_certificate_hash for row in report.rows) != certificate.branch_outlier_filter_certificate_hashes:
                return False
            if report.branch_outlier_filter_certificate_count != len(certificate.branch_outlier_filter_certificate_hashes):
                return False
            if not report.all_branch_outlier_filter_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_inlier_success_count != certificate.source_inlier_success_count:
                return False
            if report.source_outlier_success_count != certificate.source_outlier_success_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.filtered_success_count != certificate.filtered_success_count:
                return False
            if report.same_budget_filter_count != certificate.same_budget_filter_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_outlier_filter_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_outlier_filter_certificate_hash(
    certificate: BranchOutlierFilterCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchOutlierFilterCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_outlier_filter_transfer_certificate_hash(
    certificate: BranchOutlierFilterTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchOutlierFilterTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchOutlierFilterTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchOutlierFilterTransferReport,
    transfer_certificate: BranchOutlierFilterTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_outlier_filter_transfer_g1",
        claim_text=(
            "Receipt-bound source inlier filtering can improve local target exploration under matched "
            "one-call verifier budgets while target commits remain hard-verifier gated."
        ),
        evidence_grade="G1",
        scope="branch_outlier_filter_transfer",
        requirements=(
            requirement(
                "branch_outlier_filter_transfer_certificate_valid",
                validate_branch_outlier_filter_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_outlier_filter_certificates_valid", report.all_branch_outlier_filter_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_inliers_commit_all_domains", report.source_inlier_success_count == report.domain_count * 2),
            requirement("source_outliers_bound_all_domains", report.source_outlier_success_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("filtered_succeeds_all_domains", report.filtered_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_filter_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 3),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_inlier_success_count": report.source_inlier_success_count,
            "source_outlier_success_count": report.source_outlier_success_count,
            "static_success_count": report.static_success_count,
            "filtered_success_count": report.filtered_success_count,
        },
        boundary=BRANCH_OUTLIER_FILTER_CLAIM_BOUNDARY,
        sources=BRANCH_OUTLIER_FILTER_SOURCES,
    )


def _make_outlier_filter_traces(
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
            seeds=("branch-outlier-filter-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.outlier_filter.transfer.v1",
        )
        for action in actions
    )


def _domain_outlier_filter_plan(
    spec: ExplorationDomainSpec,
    source_contexts: tuple[str, str, str],
    target_context: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "feature_key": "trajectory_risk",
            "inlier_feature_values": (0.20, 0.22),
            "outlier_feature_value": 0.58,
            "static_target_feature_value": 0.71,
            "filtered_target_feature_value": 0.19,
            "distance_threshold": 0.08,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "outlier_filter_source_detour_a",
                    "utility": 8,
                    "clearance": 0.34,
                    "turn_rate": 0.42,
                    "trajectory_risk": 0.20,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "outlier_filter_source_detour_b",
                    "utility": 8,
                    "clearance": 0.36,
                    "turn_rate": 0.40,
                    "trajectory_risk": 0.22,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "outlier_filter_source_aggressive_arc",
                    "utility": 9,
                    "clearance": 0.26,
                    "turn_rate": 0.58,
                    "trajectory_risk": 0.58,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "outlier_filter_target_aggressive_arc",
                "utility": 9,
                "clearance": 0.14,
                "turn_rate": 0.78,
                "trajectory_risk": 0.71,
            },
            "target_filtered": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "outlier_filter_target_verified_detour",
                "utility": 8,
                "clearance": 0.33,
                "turn_rate": 0.41,
                "trajectory_risk": 0.19,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "feature_key": "strain_risk",
            "inlier_feature_values": (0.16, 0.18),
            "outlier_feature_value": 0.34,
            "static_target_feature_value": 0.52,
            "filtered_target_feature_value": 0.15,
            "distance_threshold": 0.06,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "outlier_filter_source_relaxed_bridge_a",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.16,
                    "strain_risk": 0.16,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "outlier_filter_source_relaxed_bridge_b",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.18,
                    "strain_risk": 0.18,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "outlier_filter_source_compact_patch",
                    "utility": 9,
                    "valence_ok": True,
                    "strain": 0.34,
                    "strain_risk": 0.34,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "outlier_filter_target_compact_patch",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.52,
                "strain_risk": 0.52,
            },
            "target_filtered": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "outlier_filter_target_relaxed_bridge",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.15,
                "strain_risk": 0.15,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "feature_key": "process_window_risk",
            "inlier_feature_values": (0.24, 0.27),
            "outlier_feature_value": 0.49,
            "static_target_feature_value": 0.70,
            "filtered_target_feature_value": 0.30,
            "distance_threshold": 0.08,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "outlier_filter_source_staged_anneal_a",
                    "utility": 8,
                    "thermal_gradient": 0.38,
                    "phase_purity": 0.95,
                    "process_window_risk": 0.24,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "outlier_filter_source_staged_anneal_b",
                    "utility": 8,
                    "thermal_gradient": 0.40,
                    "phase_purity": 0.94,
                    "process_window_risk": 0.27,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "outlier_filter_source_edge_quench",
                    "utility": 9,
                    "thermal_gradient": 0.49,
                    "phase_purity": 0.91,
                    "process_window_risk": 0.49,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "outlier_filter_target_edge_quench",
                "utility": 9,
                "thermal_gradient": 0.70,
                "phase_purity": 0.86,
                "process_window_risk": 0.70,
            },
            "target_filtered": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "outlier_filter_target_staged_anneal",
                "utility": 8,
                "thermal_gradient": 0.39,
                "phase_purity": 0.95,
                "process_window_risk": 0.30,
            },
        }
    raise ValueError(f"unknown outlier-filter domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value))


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_outlier_filter_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
