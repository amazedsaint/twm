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
    BranchSelectionCertificate,
    BranchRuntime,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


BRANCH_CONFIDENCE_CERTIFICATE_SCHEMA = "trwm.branch_confidence_certificate.v1"
BRANCH_CONFIDENCE_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_confidence_transfer_certificate.v1"
BRANCH_CONFIDENCE_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm",
)
BRANCH_CONFIDENCE_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source receipt support can be "
    "summarized by a fixed Wilson-style lower bound before a target spends the same one-call verifier "
    "budget on a better-supported action instead of a thin optimistic replay. It is not statistical "
    "validation, production calibration, a bandit confidence-bound result, robotics safety, chemistry, "
    "materials discovery, or scientific autonomy evidence."
)
CONFIDENCE_Z = 1.0


@dataclass(frozen=True)
class BranchConfidenceCertificate:
    schema_version: str
    domain: str
    confidence_rule_id: str
    confidence_rule_version: str
    source_context_id: str
    target_context_id: str
    optimistic_action: str
    supported_action: str
    optimistic_source_commit_receipt_hashes: tuple[str, ...]
    supported_source_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    confidence_target_receipt_hashes: tuple[str, ...]
    confidence_target_commit_receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]
    optimistic_support_count: int
    supported_support_count: int
    optimistic_lower_bound: float
    supported_lower_bound: float
    confidence_z: float
    static_committed: bool
    confidence_committed: bool
    static_verifier_call_count: int
    confidence_verifier_call_count: int
    same_budget: bool
    confidence_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONFIDENCE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch confidence certificate schema: {self.schema_version}")
        for field_name in (
            "optimistic_source_commit_receipt_hashes",
            "supported_source_commit_receipt_hashes",
            "static_target_receipt_hashes",
            "confidence_target_receipt_hashes",
            "confidence_target_commit_receipt_hashes",
            "branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "optimistic_lower_bound", float(self.optimistic_lower_bound))
        object.__setattr__(self, "supported_lower_bound", float(self.supported_lower_bound))
        object.__setattr__(self, "confidence_z", float(self.confidence_z))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_confidence_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchConfidenceDomainReport:
    domain: str
    source_context: str
    target_context: str
    optimistic_action: str
    supported_action: str
    optimistic_support_count: int
    supported_support_count: int
    optimistic_lower_bound: float
    supported_lower_bound: float
    static_committed: bool
    confidence_committed: bool
    static_verifier_call_count: int
    confidence_verifier_call_count: int
    optimistic_source_commit_receipt_hashes: tuple[str, ...]
    supported_source_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    confidence_target_receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]
    confidence_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchConfidenceTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchConfidenceDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    optimistic_source_commit_count: int
    supported_source_commit_count: int
    static_success_count: int
    confidence_success_count: int
    same_budget_confidence_count: int
    branch_confidence_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_confidence_certificates_valid: bool
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
class BranchConfidenceTransferCertificate:
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
    branch_confidence_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    optimistic_source_commit_count: int
    supported_source_commit_count: int
    static_success_count: int
    confidence_success_count: int
    same_budget_confidence_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONFIDENCE_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch confidence transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_confidence_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_confidence_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchConfidenceTransferResult(CertifiedExampleResult):
    report: BranchConfidenceTransferReport
    branch_confidence_transfer_certificate: BranchConfidenceTransferCertificate
    branch_confidence_certificates: tuple[BranchConfidenceCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_confidence_transfer_experiment() -> BranchConfidenceTransferReport:
    return run_branch_confidence_transfer_certified_experiment().report


def run_branch_confidence_transfer_certified_experiment() -> CertifiedBranchConfidenceTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchConfidenceDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    confidence_certificates: list[BranchConfidenceCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:confidence"
        target_context = f"{spec.domain_id}:target:confidence"
        action_map = _confidence_actions(spec)
        optimistic_source = _with_context(action_map["optimistic_source"], source_context)
        supported_source = _with_context(action_map["supported_source"], source_context)
        optimistic_target = _with_context(action_map["optimistic_target"], target_context)
        supported_target = _with_context(action_map["supported_target"], target_context)

        optimistic_receipts: list[Receipt] = []
        supported_receipts: list[Receipt] = []
        source_certificate_hashes: list[str] = []

        optimistic_outcome = runtime.step(
            state,
            _make_confidence_traces(
                spec,
                context=source_context,
                phase="source-optimistic-thin",
                episode=0,
                actions=(optimistic_source,),
            ),
        )
        state = normalize_state(optimistic_outcome.state)
        optimistic_certificate = build_branch_selection_certificate(
            optimistic_outcome.receipts,
            verifier_call_count=optimistic_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(optimistic_outcome.receipts), optimistic_certificate))
        memory.update_branch(optimistic_outcome.receipts, optimistic_certificate)
        optimistic_receipts.extend(optimistic_outcome.receipts)
        source_certificate_hashes.append(optimistic_certificate.certificate_hash)

        for episode in range(3):
            supported_outcome = runtime.step(
                state,
                _make_confidence_traces(
                    spec,
                    context=source_context,
                    phase="source-supported",
                    episode=episode,
                    actions=(supported_source,),
                ),
            )
            state = normalize_state(supported_outcome.state)
            supported_certificate = build_branch_selection_certificate(
                supported_outcome.receipts,
                verifier_call_count=supported_outcome.verifier_calls,
            )
            branch_certificate_pairs.append((tuple(supported_outcome.receipts), supported_certificate))
            memory.update_branch(supported_outcome.receipts, supported_certificate)
            supported_receipts.extend(supported_outcome.receipts)
            source_certificate_hashes.append(supported_certificate.certificate_hash)

        static_outcome = runtime.step(
            state,
            _make_confidence_traces(
                spec,
                context=target_context,
                phase="target-optimistic-replay",
                episode=0,
                actions=(optimistic_target,),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        confidence_outcome = runtime.step(
            state,
            _make_confidence_traces(
                spec,
                context=target_context,
                phase="target-confidence-bound",
                episode=0,
                actions=(supported_target,),
            ),
        )
        state = normalize_state(confidence_outcome.state)
        confidence_branch_certificate = build_branch_selection_certificate(
            confidence_outcome.receipts,
            verifier_call_count=confidence_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(confidence_outcome.receipts), confidence_branch_certificate))

        optimistic_commit_hashes = tuple(receipt.receipt_hash for receipt in optimistic_receipts if receipt.committed)
        supported_commit_hashes = tuple(receipt.receipt_hash for receipt in supported_receipts if receipt.committed)
        optimistic_lower = wilson_lower_bound(len(optimistic_commit_hashes), len(optimistic_receipts), CONFIDENCE_Z)
        supported_lower = wilson_lower_bound(len(supported_commit_hashes), len(supported_receipts), CONFIDENCE_Z)
        all_certificate_hashes = (
            *source_certificate_hashes,
            static_certificate.certificate_hash,
            confidence_branch_certificate.certificate_hash,
        )

        certificate = build_branch_confidence_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            optimistic_action=str(optimistic_source["action"]),
            supported_action=str(supported_source["action"]),
            optimistic_source_commit_receipt_hashes=optimistic_commit_hashes,
            supported_source_commit_receipt_hashes=supported_commit_hashes,
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            confidence_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in confidence_outcome.receipts),
            confidence_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in confidence_outcome.receipts if receipt.committed
            ),
            branch_selection_certificate_hashes=tuple(all_certificate_hashes),
            optimistic_lower_bound=optimistic_lower,
            supported_lower_bound=supported_lower,
            static_committed=static_outcome.committed,
            confidence_committed=confidence_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            confidence_verifier_call_count=confidence_outcome.verifier_calls,
        )
        confidence_certificates.append(certificate)
        rows.append(
            BranchConfidenceDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                optimistic_action=certificate.optimistic_action,
                supported_action=certificate.supported_action,
                optimistic_support_count=certificate.optimistic_support_count,
                supported_support_count=certificate.supported_support_count,
                optimistic_lower_bound=certificate.optimistic_lower_bound,
                supported_lower_bound=certificate.supported_lower_bound,
                static_committed=certificate.static_committed,
                confidence_committed=certificate.confidence_committed,
                static_verifier_call_count=certificate.static_verifier_call_count,
                confidence_verifier_call_count=certificate.confidence_verifier_call_count,
                optimistic_source_commit_receipt_hashes=certificate.optimistic_source_commit_receipt_hashes,
                supported_source_commit_receipt_hashes=certificate.supported_source_commit_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                confidence_target_receipt_hashes=certificate.confidence_target_receipt_hashes,
                branch_selection_certificate_hashes=certificate.branch_selection_certificate_hashes,
                confidence_certificate_hash=certificate.certificate_hash,
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

    report = BranchConfidenceTransferReport(
        schema_version="trwm.example.branch_confidence_transfer.v1",
        experiment_id="branch_confidence_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        optimistic_source_commit_count=sum(len(row.optimistic_source_commit_receipt_hashes) for row in rows),
        supported_source_commit_count=sum(len(row.supported_source_commit_receipt_hashes) for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        confidence_success_count=sum(1 for row in rows if row.confidence_committed),
        same_budget_confidence_count=sum(1 for row in rows if row.same_budget),
        branch_confidence_certificate_count=len(confidence_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_confidence_certificates_valid=all(
            validate_branch_confidence_certificate(certificate, row)
            for certificate, row in zip(confidence_certificates, rows)
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
        sources=BRANCH_CONFIDENCE_SOURCES,
        learning=(
            "Branch history can improve exploration by carrying support strength. A thin source commit "
            "is not enough to outrank a better-supported branch; the target still verifies the chosen "
            "candidate under the same one-call budget before any commit is admitted."
        ),
    )
    transfer_certificate = build_branch_confidence_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_confidence_certificate_hashes=tuple(certificate.certificate_hash for certificate in confidence_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_confidence_transfer",
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
        claim_boundary=BRANCH_CONFIDENCE_CLAIM_BOUNDARY,
        sources=BRANCH_CONFIDENCE_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchConfidenceTransferResult(
        report=report,
        branch_confidence_transfer_certificate=transfer_certificate,
        branch_confidence_certificates=tuple(confidence_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_confidence_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    optimistic_action: str,
    supported_action: str,
    optimistic_source_commit_receipt_hashes: tuple[str, ...],
    supported_source_commit_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    confidence_target_receipt_hashes: tuple[str, ...],
    confidence_target_commit_receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    optimistic_lower_bound: float,
    supported_lower_bound: float,
    static_committed: bool,
    confidence_committed: bool,
    static_verifier_call_count: int,
    confidence_verifier_call_count: int,
) -> BranchConfidenceCertificate:
    return BranchConfidenceCertificate(
        schema_version=BRANCH_CONFIDENCE_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        confidence_rule_id="wilson_lower_bound_support",
        confidence_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        optimistic_action=optimistic_action,
        supported_action=supported_action,
        optimistic_source_commit_receipt_hashes=optimistic_source_commit_receipt_hashes,
        supported_source_commit_receipt_hashes=supported_source_commit_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        confidence_target_receipt_hashes=confidence_target_receipt_hashes,
        confidence_target_commit_receipt_hashes=confidence_target_commit_receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        optimistic_support_count=len(optimistic_source_commit_receipt_hashes),
        supported_support_count=len(supported_source_commit_receipt_hashes),
        optimistic_lower_bound=optimistic_lower_bound,
        supported_lower_bound=supported_lower_bound,
        confidence_z=CONFIDENCE_Z,
        static_committed=static_committed,
        confidence_committed=confidence_committed,
        static_verifier_call_count=static_verifier_call_count,
        confidence_verifier_call_count=confidence_verifier_call_count,
        same_budget=static_verifier_call_count == confidence_verifier_call_count == 1,
        confidence_reason="supported_source_receipts_raise_lower_bound",
    )


def validate_branch_confidence_certificate(
    certificate: BranchConfidenceCertificate,
    row: BranchConfidenceDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONFIDENCE_CERTIFICATE_SCHEMA:
            return False
        if certificate.confidence_rule_id != "wilson_lower_bound_support":
            return False
        if certificate.confidence_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.optimistic_action,
            certificate.supported_action,
            certificate.confidence_reason,
        ):
            if not _nonempty(value):
                return False
        if certificate.optimistic_action == certificate.supported_action:
            return False
        if certificate.optimistic_support_count != 1:
            return False
        if certificate.supported_support_count != 3:
            return False
        if not _valid_probability(certificate.optimistic_lower_bound):
            return False
        if not _valid_probability(certificate.supported_lower_bound):
            return False
        if certificate.confidence_z != CONFIDENCE_Z:
            return False
        expected_optimistic = wilson_lower_bound(certificate.optimistic_support_count, certificate.optimistic_support_count, CONFIDENCE_Z)
        expected_supported = wilson_lower_bound(certificate.supported_support_count, certificate.supported_support_count, CONFIDENCE_Z)
        if abs(certificate.optimistic_lower_bound - expected_optimistic) > 1e-12:
            return False
        if abs(certificate.supported_lower_bound - expected_supported) > 1e-12:
            return False
        if certificate.supported_lower_bound <= certificate.optimistic_lower_bound:
            return False
        if certificate.static_committed or not certificate.confidence_committed:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.confidence_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.confidence_reason != "supported_source_receipts_raise_lower_bound":
            return False
        for values, expected_len in (
            (certificate.optimistic_source_commit_receipt_hashes, 1),
            (certificate.supported_source_commit_receipt_hashes, 3),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.confidence_target_receipt_hashes, 1),
            (certificate.confidence_target_commit_receipt_hashes, 1),
            (certificate.branch_selection_certificate_hashes, 6),
        ):
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id:
                return False
            if row.target_context != certificate.target_context_id:
                return False
            if row.optimistic_action != certificate.optimistic_action:
                return False
            if row.supported_action != certificate.supported_action:
                return False
            if row.optimistic_support_count != certificate.optimistic_support_count:
                return False
            if row.supported_support_count != certificate.supported_support_count:
                return False
            if row.optimistic_lower_bound != certificate.optimistic_lower_bound:
                return False
            if row.supported_lower_bound != certificate.supported_lower_bound:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.confidence_committed != certificate.confidence_committed:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.confidence_verifier_call_count != certificate.confidence_verifier_call_count:
                return False
            if row.optimistic_source_commit_receipt_hashes != certificate.optimistic_source_commit_receipt_hashes:
                return False
            if row.supported_source_commit_receipt_hashes != certificate.supported_source_commit_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.confidence_target_receipt_hashes != certificate.confidence_target_receipt_hashes:
                return False
            if row.branch_selection_certificate_hashes != certificate.branch_selection_certificate_hashes:
                return False
            if row.confidence_certificate_hash != certificate.certificate_hash:
                return False
            if row.same_budget != certificate.same_budget:
                return False
        return certificate.certificate_hash == branch_confidence_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_confidence_transfer_certificate(
    report: BranchConfidenceTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_confidence_certificate_hashes: tuple[str, ...],
) -> BranchConfidenceTransferCertificate:
    return BranchConfidenceTransferCertificate(
        schema_version=BRANCH_CONFIDENCE_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_confidence_certificate_hashes=branch_confidence_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        optimistic_source_commit_count=report.optimistic_source_commit_count,
        supported_source_commit_count=report.supported_source_commit_count,
        static_success_count=report.static_success_count,
        confidence_success_count=report.confidence_success_count,
        same_budget_confidence_count=report.same_budget_confidence_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CONFIDENCE_CLAIM_BOUNDARY,
    )


def validate_branch_confidence_transfer_certificate(
    certificate: BranchConfidenceTransferCertificate,
    report: BranchConfidenceTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONFIDENCE_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_confidence_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_confidence_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.optimistic_source_commit_count != certificate.domain_count:
            return False
        if certificate.supported_source_commit_count != certificate.domain_count * 3:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.confidence_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_confidence_count != certificate.domain_count:
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
            if not report.all_branch_confidence_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.optimistic_source_commit_count != certificate.optimistic_source_commit_count:
                return False
            if report.supported_source_commit_count != certificate.supported_source_commit_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.confidence_success_count != certificate.confidence_success_count:
                return False
            if report.same_budget_confidence_count != certificate.same_budget_confidence_count:
                return False
        return certificate.certificate_hash == branch_confidence_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_confidence_certificate_hash(certificate: BranchConfidenceCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchConfidenceCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_confidence_transfer_certificate_hash(
    certificate: BranchConfidenceTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchConfidenceTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def wilson_lower_bound(successes: int, observations: int, z: float = CONFIDENCE_Z) -> float:
    if observations <= 0:
        raise ValueError("observations must be positive")
    if successes < 0 or successes > observations:
        raise ValueError("successes must be between zero and observations")
    p_hat = successes / observations
    z2 = z * z
    denominator = 1.0 + z2 / observations
    center = p_hat + z2 / (2.0 * observations)
    margin = z * sqrt((p_hat * (1.0 - p_hat) / observations) + (z2 / (4.0 * observations * observations)))
    return (center - margin) / denominator


def result_as_dict(result: CertifiedBranchConfidenceTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchConfidenceTransferReport,
    transfer_certificate: BranchConfidenceTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_confidence_transfer_g1",
        claim_text=(
            "Source receipt support strength can improve local target exploration under matched one-call "
            "verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_confidence_transfer",
        requirements=(
            requirement(
                "branch_confidence_transfer_certificate_valid",
                validate_branch_confidence_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid),
            requirement("all_branch_confidence_certificates_valid", report.all_branch_confidence_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("optimistic_support_bound", report.optimistic_source_commit_count == report.domain_count),
            requirement("supported_support_bound", report.supported_source_commit_count == report.domain_count * 3),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("confidence_succeeds_all_domains", report.confidence_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_confidence_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "optimistic_source_commit_count": report.optimistic_source_commit_count,
            "supported_source_commit_count": report.supported_source_commit_count,
            "static_success_count": report.static_success_count,
            "confidence_success_count": report.confidence_success_count,
        },
        boundary=BRANCH_CONFIDENCE_CLAIM_BOUNDARY,
        sources=BRANCH_CONFIDENCE_SOURCES,
    )


def _make_confidence_traces(
    spec: ExplorationDomainSpec,
    *,
    context: str,
    phase: str,
    episode: int,
    actions: Iterable[Mapping[str, Any]],
) -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"{context}:{phase}:{episode}:{action['action']}",
            actions=({**dict(action), "context": context, "phase": phase},),
            seeds=("branch-confidence-transfer", spec.domain_id, context, phase, episode, action["action"]),
            model_version="branch.confidence.transfer.v1",
        )
        for action in actions
    )


def _confidence_actions(spec: ExplorationDomainSpec) -> Mapping[str, Mapping[str, Any]]:
    if spec.domain_id == "robotics_replan":
        return {
            "optimistic_source": {
                "domain": spec.domain_id,
                "action": "aggressive_gap_thread",
                "utility": 9,
                "clearance": 0.31,
                "turn_rate": 0.55,
                "target_commit": True,
            },
            "supported_source": {
                "domain": spec.domain_id,
                "action": "steady_clearance_arc",
                "utility": 7,
                "clearance": 0.36,
                "turn_rate": 0.38,
                "target_commit": True,
            },
            "optimistic_target": {
                "domain": spec.domain_id,
                "action": "aggressive_gap_thread",
                "utility": 9,
                "clearance": 0.14,
                "turn_rate": 0.72,
            },
            "supported_target": {
                "domain": spec.domain_id,
                "action": "steady_clearance_arc",
                "utility": 7,
                "clearance": 0.35,
                "turn_rate": 0.39,
                "target_commit": True,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "optimistic_source": {
                "domain": spec.domain_id,
                "action": "compact_strain_lock",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.31,
                "target_commit": True,
            },
            "supported_source": {
                "domain": spec.domain_id,
                "action": "relaxed_valence_bridge",
                "utility": 7,
                "valence_ok": True,
                "strain": 0.14,
                "target_commit": True,
            },
            "optimistic_target": {
                "domain": spec.domain_id,
                "action": "compact_strain_lock",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.50,
            },
            "supported_target": {
                "domain": spec.domain_id,
                "action": "relaxed_valence_bridge",
                "utility": 7,
                "valence_ok": True,
                "strain": 0.16,
                "target_commit": True,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "optimistic_source": {
                "domain": spec.domain_id,
                "action": "fast_phase_trim",
                "utility": 9,
                "thermal_gradient": 0.48,
                "phase_purity": 0.91,
                "target_commit": True,
            },
            "supported_source": {
                "domain": spec.domain_id,
                "action": "staged_phase_balance",
                "utility": 7,
                "thermal_gradient": 0.37,
                "phase_purity": 0.96,
                "target_commit": True,
            },
            "optimistic_target": {
                "domain": spec.domain_id,
                "action": "fast_phase_trim",
                "utility": 9,
                "thermal_gradient": 0.65,
                "phase_purity": 0.88,
            },
            "supported_target": {
                "domain": spec.domain_id,
                "action": "staged_phase_balance",
                "utility": 7,
                "thermal_gradient": 0.39,
                "phase_purity": 0.95,
                "target_commit": True,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _with_context(action: Mapping[str, Any], context: str) -> Mapping[str, Any]:
    return {**dict(action), "context": context}


def _valid_probability(value: float) -> bool:
    return isinstance(value, float) and isfinite(value) and 0.0 <= value <= 1.0


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_confidence_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
