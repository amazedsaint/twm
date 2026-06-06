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
    HighestUtilityRanker,
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


BRANCH_TRUST_REGION_CERTIFICATE_SCHEMA = "trwm.branch_trust_region_certificate.v1"
BRANCH_TRUST_REGION_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_trust_region_transfer_certificate.v1"
BRANCH_TRUST_REGION_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://epubs.siam.org/doi/book/10.1137/1.9780898719857",
)
BRANCH_TRUST_REGION_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source reject/commit receipts can "
    "certify a target proposal-radius cap under a matched one-call verifier budget, while every target "
    "commit still requires fresh hard verification. It is not trust-region optimization, TRPO, policy "
    "optimization, robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchTrustRegionCertificate:
    schema_version: str
    domain: str
    trust_region_rule_id: str
    trust_region_rule_version: str
    source_context_id: str
    target_context_id: str
    radius_key: str
    rejected_family: str
    source_rejected_action: str
    source_committed_action: str
    static_target_action: str
    trust_region_target_action: str
    source_rejected_radius: float
    source_committed_radius: float
    trusted_radius_cap: float
    static_target_radius: float
    trust_region_target_radius: float
    source_receipt_hashes: tuple[str, ...]
    source_reject_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    trust_region_target_receipt_hashes: tuple[str, ...]
    trust_region_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    trust_region_branch_selection_certificate_hash: str
    source_rejected_count: int
    source_committed_count: int
    static_committed: bool
    trust_region_committed: bool
    static_verifier_call_count: int
    trust_region_verifier_call_count: int
    same_budget: bool
    trust_region_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_TRUST_REGION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch trust-region certificate schema: {self.schema_version}")
        for field_name in (
            "source_receipt_hashes",
            "source_reject_receipt_hashes",
            "source_commit_receipt_hashes",
            "static_target_receipt_hashes",
            "trust_region_target_receipt_hashes",
            "trust_region_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "source_rejected_radius",
            "source_committed_radius",
            "trusted_radius_cap",
            "static_target_radius",
            "trust_region_target_radius",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_trust_region_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchTrustRegionDomainReport:
    domain: str
    source_context: str
    target_context: str
    radius_key: str
    rejected_family: str
    source_rejected_action: str
    source_committed_action: str
    static_target_action: str
    trust_region_target_action: str
    source_rejected_radius: float
    source_committed_radius: float
    trusted_radius_cap: float
    static_target_radius: float
    trust_region_target_radius: float
    source_rejected_count: int
    source_committed_count: int
    static_committed: bool
    trust_region_committed: bool
    static_verifier_call_count: int
    trust_region_verifier_call_count: int
    source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    trust_region_target_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    trust_region_branch_selection_certificate_hash: str
    branch_trust_region_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchTrustRegionTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchTrustRegionDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_commit_count: int
    source_reject_count: int
    static_success_count: int
    trust_region_success_count: int
    same_budget_trust_region_count: int
    branch_trust_region_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_trust_region_certificates_valid: bool
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
class BranchTrustRegionTransferCertificate:
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
    branch_trust_region_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_commit_count: int
    source_reject_count: int
    static_success_count: int
    trust_region_success_count: int
    same_budget_trust_region_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_TRUST_REGION_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch trust-region transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_trust_region_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_trust_region_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchTrustRegionTransferResult(CertifiedExampleResult):
    report: BranchTrustRegionTransferReport
    branch_trust_region_transfer_certificate: BranchTrustRegionTransferCertificate
    branch_trust_region_certificates: tuple[BranchTrustRegionCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_trust_region_transfer_experiment() -> BranchTrustRegionTransferReport:
    return run_branch_trust_region_transfer_certified_experiment().report


def run_branch_trust_region_transfer_certified_experiment() -> CertifiedBranchTrustRegionTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[BranchTrustRegionDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    trust_region_certificates: list[BranchTrustRegionCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:trust_region"
        target_context = f"{spec.domain_id}:target:trust_region"
        plan = _trust_region_plan(spec, source_context, target_context)

        source_outcome = runtime.step(
            state,
            _make_trust_region_traces(
                spec,
                context=source_context,
                phase="source-trust-region",
                actions=(plan["source_rejected"], plan["source_committed"]),
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
            _make_trust_region_traces(
                spec,
                context=target_context,
                phase="target-static-overshoot",
                actions=(plan["target_static"],),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        trust_region_outcome = runtime.step(
            state,
            _make_trust_region_traces(
                spec,
                context=target_context,
                phase="target-trust-region",
                actions=(plan["target_trust_region"],),
            ),
        )
        state = normalize_state(trust_region_outcome.state)
        trust_region_certificate = build_branch_selection_certificate(
            trust_region_outcome.receipts,
            verifier_call_count=trust_region_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(trust_region_outcome.receipts), trust_region_certificate))

        certificate = build_branch_trust_region_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            radius_key=str(plan["radius_key"]),
            rejected_family=str(plan["rejected_family"]),
            source_rejected_action=str(plan["source_rejected"]["action"]),
            source_committed_action=str(plan["source_committed"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            trust_region_target_action=str(plan["target_trust_region"]["action"]),
            source_rejected_radius=float(plan["source_rejected"]["proposal_radius"]),
            source_committed_radius=float(plan["source_committed"]["proposal_radius"]),
            trusted_radius_cap=float(plan["source_committed"]["proposal_radius"]),
            static_target_radius=float(plan["target_static"]["proposal_radius"]),
            trust_region_target_radius=float(plan["target_trust_region"]["proposal_radius"]),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
            source_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
            source_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            trust_region_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in trust_region_outcome.receipts),
            trust_region_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in trust_region_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            trust_region_branch_selection_certificate_hash=trust_region_certificate.certificate_hash,
            source_rejected_count=sum(1 for receipt in source_outcome.receipts if receipt.hard_result.rejected),
            source_committed_count=sum(1 for receipt in source_outcome.receipts if receipt.committed),
            static_committed=static_outcome.committed,
            trust_region_committed=trust_region_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            trust_region_verifier_call_count=trust_region_outcome.verifier_calls,
        )
        trust_region_certificates.append(certificate)

        rows.append(
            BranchTrustRegionDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                radius_key=certificate.radius_key,
                rejected_family=certificate.rejected_family,
                source_rejected_action=certificate.source_rejected_action,
                source_committed_action=certificate.source_committed_action,
                static_target_action=certificate.static_target_action,
                trust_region_target_action=certificate.trust_region_target_action,
                source_rejected_radius=certificate.source_rejected_radius,
                source_committed_radius=certificate.source_committed_radius,
                trusted_radius_cap=certificate.trusted_radius_cap,
                static_target_radius=certificate.static_target_radius,
                trust_region_target_radius=certificate.trust_region_target_radius,
                source_rejected_count=certificate.source_rejected_count,
                source_committed_count=certificate.source_committed_count,
                static_committed=static_outcome.committed,
                trust_region_committed=trust_region_outcome.committed,
                static_verifier_call_count=static_outcome.verifier_calls,
                trust_region_verifier_call_count=trust_region_outcome.verifier_calls,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
                static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
                trust_region_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in trust_region_outcome.receipts),
                source_branch_selection_certificate_hash=source_certificate.certificate_hash,
                static_branch_selection_certificate_hash=static_certificate.certificate_hash,
                trust_region_branch_selection_certificate_hash=trust_region_certificate.certificate_hash,
                branch_trust_region_certificate_hash=certificate.certificate_hash,
                same_budget=certificate.same_budget,
            )
        )

    memory_snapshot = memory.snapshot()
    all_receipts = tuple(engine.ledger.rows)
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
    all_branch_selection_certificates_valid = all(
        validate_branch_selection_certificate(certificate) for _, certificate in branch_certificate_pairs
    )
    all_branch_selection_audits_valid = all(
        audit_branch_selection(receipts, certificate) for receipts, certificate in branch_certificate_pairs
    )
    report = BranchTrustRegionTransferReport(
        schema_version="trwm.example.branch_trust_region_transfer.v1",
        experiment_id="branch_trust_region_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_commit_count=sum(row.source_committed_count for row in rows),
        source_reject_count=sum(row.source_rejected_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        trust_region_success_count=sum(1 for row in rows if row.trust_region_committed),
        same_budget_trust_region_count=sum(1 for row in rows if row.same_budget),
        branch_trust_region_certificate_count=len(trust_region_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_trust_region_certificates_valid=all(
            validate_branch_trust_region_certificate(certificate) for certificate in trust_region_certificates
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
        sources=BRANCH_TRUST_REGION_SOURCES,
        learning=(
            "Past branch receipts can improve exploration by bounding the next proposal step: "
            "the source reject/commit radius becomes a certified target trust-region cap, but the "
            "bounded target proposal still commits only after fresh hard verification."
        ),
    )
    transfer_certificate = build_branch_trust_region_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_trust_region_certificate_hashes=tuple(certificate.certificate_hash for certificate in trust_region_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_trust_region_transfer",
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
        claim_boundary=BRANCH_TRUST_REGION_CLAIM_BOUNDARY,
        sources=BRANCH_TRUST_REGION_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchTrustRegionTransferResult(
        report=report,
        branch_trust_region_transfer_certificate=transfer_certificate,
        branch_trust_region_certificates=tuple(trust_region_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_trust_region_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    radius_key: str,
    rejected_family: str,
    source_rejected_action: str,
    source_committed_action: str,
    static_target_action: str,
    trust_region_target_action: str,
    source_rejected_radius: float,
    source_committed_radius: float,
    trusted_radius_cap: float,
    static_target_radius: float,
    trust_region_target_radius: float,
    source_receipt_hashes: tuple[str, ...],
    source_reject_receipt_hashes: tuple[str, ...],
    source_commit_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    trust_region_target_receipt_hashes: tuple[str, ...],
    trust_region_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    trust_region_branch_selection_certificate_hash: str,
    source_rejected_count: int,
    source_committed_count: int,
    static_committed: bool,
    trust_region_committed: bool,
    static_verifier_call_count: int,
    trust_region_verifier_call_count: int,
) -> BranchTrustRegionCertificate:
    return BranchTrustRegionCertificate(
        schema_version=BRANCH_TRUST_REGION_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        trust_region_rule_id="receipt_bound_radius_cap",
        trust_region_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        radius_key=radius_key,
        rejected_family=rejected_family,
        source_rejected_action=source_rejected_action,
        source_committed_action=source_committed_action,
        static_target_action=static_target_action,
        trust_region_target_action=trust_region_target_action,
        source_rejected_radius=source_rejected_radius,
        source_committed_radius=source_committed_radius,
        trusted_radius_cap=trusted_radius_cap,
        static_target_radius=static_target_radius,
        trust_region_target_radius=trust_region_target_radius,
        source_receipt_hashes=source_receipt_hashes,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        trust_region_target_receipt_hashes=trust_region_target_receipt_hashes,
        trust_region_commit_receipt_hashes=trust_region_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        trust_region_branch_selection_certificate_hash=trust_region_branch_selection_certificate_hash,
        source_rejected_count=source_rejected_count,
        source_committed_count=source_committed_count,
        static_committed=static_committed,
        trust_region_committed=trust_region_committed,
        static_verifier_call_count=static_verifier_call_count,
        trust_region_verifier_call_count=trust_region_verifier_call_count,
        same_budget=static_verifier_call_count == trust_region_verifier_call_count == 1,
        trust_region_reason="source_reject_commit_radius_cap",
    )


def validate_branch_trust_region_certificate(
    certificate: BranchTrustRegionCertificate,
    row: BranchTrustRegionDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_TRUST_REGION_CERTIFICATE_SCHEMA:
            return False
        if certificate.trust_region_rule_id != "receipt_bound_radius_cap" or certificate.trust_region_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.radius_key):
            return False
        if not _nonempty(certificate.rejected_family):
            return False
        if certificate.source_rejected_radius <= certificate.trusted_radius_cap:
            return False
        if certificate.source_committed_radius != certificate.trusted_radius_cap:
            return False
        if certificate.static_target_radius <= certificate.trusted_radius_cap:
            return False
        if certificate.trust_region_target_radius > certificate.trusted_radius_cap:
            return False
        if certificate.source_rejected_count != 1 or certificate.source_committed_count != 1:
            return False
        if certificate.static_committed or not certificate.trust_region_committed:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.trust_region_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.trust_region_reason != "source_reject_commit_radius_cap":
            return False
        if len(certificate.source_receipt_hashes) != 2:
            return False
        if len(certificate.source_reject_receipt_hashes) != 1 or len(certificate.source_commit_receipt_hashes) != 1:
            return False
        if len(certificate.static_target_receipt_hashes) != 1:
            return False
        if len(certificate.trust_region_target_receipt_hashes) != 1 or len(certificate.trust_region_commit_receipt_hashes) != 1:
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_reject_receipt_hashes,
            certificate.source_commit_receipt_hashes,
            certificate.static_target_receipt_hashes,
            certificate.trust_region_target_receipt_hashes,
            certificate.trust_region_commit_receipt_hashes,
            (
                certificate.source_branch_selection_certificate_hash,
                certificate.static_branch_selection_certificate_hash,
                certificate.trust_region_branch_selection_certificate_hash,
            ),
        ):
            if any(not _is_hash(value) for value in values):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.radius_key != certificate.radius_key or row.rejected_family != certificate.rejected_family:
                return False
            if row.source_rejected_action != certificate.source_rejected_action:
                return False
            if row.source_committed_action != certificate.source_committed_action:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.trust_region_target_action != certificate.trust_region_target_action:
                return False
            if row.source_rejected_radius != certificate.source_rejected_radius:
                return False
            if row.source_committed_radius != certificate.source_committed_radius:
                return False
            if row.trusted_radius_cap != certificate.trusted_radius_cap:
                return False
            if row.static_target_radius != certificate.static_target_radius:
                return False
            if row.trust_region_target_radius != certificate.trust_region_target_radius:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.trust_region_committed != certificate.trust_region_committed:
                return False
            if row.branch_trust_region_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_trust_region_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_trust_region_transfer_certificate(
    report: BranchTrustRegionTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_trust_region_certificate_hashes: tuple[str, ...],
) -> BranchTrustRegionTransferCertificate:
    return BranchTrustRegionTransferCertificate(
        schema_version=BRANCH_TRUST_REGION_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_trust_region_certificate_hashes=branch_trust_region_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_commit_count=report.source_commit_count,
        source_reject_count=report.source_reject_count,
        static_success_count=report.static_success_count,
        trust_region_success_count=report.trust_region_success_count,
        same_budget_trust_region_count=report.same_budget_trust_region_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_TRUST_REGION_CLAIM_BOUNDARY,
    )


def validate_branch_trust_region_transfer_certificate(
    certificate: BranchTrustRegionTransferCertificate,
    report: BranchTrustRegionTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_TRUST_REGION_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_trust_region_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_trust_region_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_commit_count != certificate.domain_count:
            return False
        if certificate.source_reject_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.trust_region_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_trust_region_count != certificate.domain_count:
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
            if tuple(row.branch_trust_region_certificate_hash for row in report.rows) != certificate.branch_trust_region_certificate_hashes:
                return False
            if not report.all_branch_trust_region_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if report.branch_trust_region_certificate_count != len(certificate.branch_trust_region_certificate_hashes):
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_commit_count != certificate.source_commit_count:
                return False
            if report.source_reject_count != certificate.source_reject_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.trust_region_success_count != certificate.trust_region_success_count:
                return False
            if report.same_budget_trust_region_count != certificate.same_budget_trust_region_count:
                return False
        return certificate.certificate_hash == branch_trust_region_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_trust_region_certificate_hash(
    certificate: BranchTrustRegionCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchTrustRegionCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_trust_region_transfer_certificate_hash(
    certificate: BranchTrustRegionTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchTrustRegionTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchTrustRegionTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchTrustRegionTransferReport,
    transfer_certificate: BranchTrustRegionTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_trust_region_transfer_g1",
        claim_text=(
            "Past reject/commit branch receipts can improve local target exploration by certifying "
            "a trust-region proposal-radius cap before target hard verification."
        ),
        evidence_grade="G1",
        scope="branch_trust_region_transfer",
        requirements=(
            requirement(
                "branch_trust_region_transfer_certificate_valid",
                validate_branch_trust_region_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_trust_region_certificates_valid", report.all_branch_trust_region_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_commits_all_domains", report.source_commit_count == report.domain_count),
            requirement("source_rejects_all_domains", report.source_reject_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("trust_region_succeeds_all_domains", report.trust_region_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_trust_region_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 2),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_commit_count": report.source_commit_count,
            "source_reject_count": report.source_reject_count,
            "static_success_count": report.static_success_count,
            "trust_region_success_count": report.trust_region_success_count,
        },
        boundary=BRANCH_TRUST_REGION_CLAIM_BOUNDARY,
        sources=BRANCH_TRUST_REGION_SOURCES,
    )


def _make_trust_region_traces(
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
            seeds=("branch-trust-region-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.trust_region.transfer.v1",
        )
        for action in actions
    )


def _trust_region_plan(spec: ExplorationDomainSpec, source_context: str, target_context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "radius_key": "turn_rate_delta",
            "rejected_family": "oversized_trajectory_update",
            "source_rejected": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "trust_source_large_turn_step",
                "utility": 10,
                "clearance": 0.18,
                "turn_rate": 0.92,
                "proposal_radius": 0.90,
            },
            "source_committed": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "trust_source_bounded_detour",
                "utility": 8,
                "clearance": 0.34,
                "turn_rate": 0.41,
                "proposal_radius": 0.40,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "trust_target_large_turn_step",
                "utility": 10,
                "clearance": 0.16,
                "turn_rate": 0.82,
                "proposal_radius": 0.78,
            },
            "target_trust_region": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "trust_target_bounded_detour",
                "utility": 8,
                "clearance": 0.33,
                "turn_rate": 0.43,
                "proposal_radius": 0.38,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "radius_key": "strain_delta",
            "rejected_family": "oversized_chemistry_update",
            "source_rejected": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "trust_source_high_strain_step",
                "utility": 10,
                "valence_ok": True,
                "strain": 0.62,
                "proposal_radius": 0.60,
            },
            "source_committed": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "trust_source_bounded_valence_step",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.18,
                "proposal_radius": 0.22,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "trust_target_high_strain_step",
                "utility": 10,
                "valence_ok": True,
                "strain": 0.58,
                "proposal_radius": 0.56,
            },
            "target_trust_region": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "trust_target_bounded_valence_step",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.20,
                "proposal_radius": 0.20,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "radius_key": "thermal_gradient_delta",
            "rejected_family": "oversized_process_update",
            "source_rejected": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "trust_source_flash_jump",
                "utility": 10,
                "thermal_gradient": 0.72,
                "phase_purity": 0.86,
                "proposal_radius": 0.70,
            },
            "source_committed": {
                "domain": spec.domain_id,
                "context": source_context,
                "action": "trust_source_bounded_anneal",
                "utility": 8,
                "thermal_gradient": 0.40,
                "phase_purity": 0.95,
                "proposal_radius": 0.35,
            },
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "trust_target_flash_jump",
                "utility": 10,
                "thermal_gradient": 0.74,
                "phase_purity": 0.87,
                "proposal_radius": 0.68,
            },
            "target_trust_region": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "trust_target_bounded_anneal",
                "utility": 8,
                "thermal_gradient": 0.43,
                "phase_purity": 0.95,
                "proposal_radius": 0.34,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_trust_region_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
