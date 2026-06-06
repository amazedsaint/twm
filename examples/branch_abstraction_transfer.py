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


BRANCH_ABSTRACTION_CERTIFICATE_SCHEMA = "trwm.branch_abstraction_certificate.v1"
BRANCH_ABSTRACTION_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_abstraction_transfer_certificate.v1"
BRANCH_ABSTRACTION_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1016/S0004-3702(99)00052-1",
)
BRANCH_ABSTRACTION_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows a source branch's abstract "
    "option family can certify trying a different target-specific action when exact source-action "
    "replay is stale. It is not hierarchical reinforcement learning, an options-framework result, "
    "automatic abstraction learning, robotics safety, chemistry, materials discovery, or scientific "
    "autonomy evidence."
)


@dataclass(frozen=True)
class BranchAbstractionCertificate:
    schema_version: str
    domain: str
    abstraction_rule_id: str
    abstraction_rule_version: str
    source_context_id: str
    target_context_id: str
    abstract_family: str
    source_action: str
    stale_exact_action: str
    abstract_target_action: str
    source_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    source_reject_receipt_hashes: tuple[str, ...]
    source_rolled_back_receipt_hashes: tuple[str, ...]
    stale_exact_receipt_hashes: tuple[str, ...]
    abstract_target_receipt_hashes: tuple[str, ...]
    abstract_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    stale_branch_selection_certificate_hash: str
    abstract_branch_selection_certificate_hash: str
    exact_replay_committed: bool
    abstraction_committed: bool
    exact_verifier_call_count: int
    abstraction_verifier_call_count: int
    same_budget: bool
    abstraction_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_ABSTRACTION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch abstraction certificate schema: {self.schema_version}")
        for field_name in (
            "source_receipt_hashes",
            "source_commit_receipt_hashes",
            "source_reject_receipt_hashes",
            "source_rolled_back_receipt_hashes",
            "stale_exact_receipt_hashes",
            "abstract_target_receipt_hashes",
            "abstract_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_abstraction_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchAbstractionDomainReport:
    domain: str
    source_context: str
    target_context: str
    abstract_family: str
    source_action: str
    stale_exact_action: str
    abstract_target_action: str
    exact_replay_committed: bool
    abstraction_committed: bool
    exact_verifier_call_count: int
    abstraction_verifier_call_count: int
    source_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    source_reject_receipt_hashes: tuple[str, ...]
    source_rolled_back_receipt_hashes: tuple[str, ...]
    stale_exact_receipt_hashes: tuple[str, ...]
    abstract_target_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    stale_branch_selection_certificate_hash: str
    abstract_branch_selection_certificate_hash: str
    abstraction_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchAbstractionTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchAbstractionDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    exact_replay_success_count: int
    abstraction_success_count: int
    same_budget_abstraction_count: int
    branch_abstraction_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_abstraction_certificates_valid: bool
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
class BranchAbstractionTransferCertificate:
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
    branch_abstraction_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    exact_replay_success_count: int
    abstraction_success_count: int
    same_budget_abstraction_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_ABSTRACTION_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch abstraction transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_abstraction_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_abstraction_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchAbstractionTransferResult(CertifiedExampleResult):
    report: BranchAbstractionTransferReport
    branch_abstraction_transfer_certificate: BranchAbstractionTransferCertificate
    branch_abstraction_certificates: tuple[BranchAbstractionCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_abstraction_transfer_experiment() -> BranchAbstractionTransferReport:
    return run_branch_abstraction_transfer_certified_experiment().report


def run_branch_abstraction_transfer_certified_experiment() -> CertifiedBranchAbstractionTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[BranchAbstractionDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    abstraction_certificates: list[BranchAbstractionCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:abstraction"
        target_context = f"{spec.domain_id}:target:abstraction"
        family = _abstract_family(spec)
        source_actions = _source_actions(spec, source_context, family)
        stale_exact_action = _stale_exact_action(spec, target_context, family)
        abstract_target_action = _abstract_target_action(spec, target_context, family)

        source_outcome = runtime.step(
            state,
            _make_abstraction_traces(spec, context=source_context, phase="source-abstraction", actions=source_actions),
        )
        state = normalize_state(source_outcome.state)
        source_certificate = build_branch_selection_certificate(
            source_outcome.receipts,
            verifier_call_count=source_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_outcome.receipts), source_certificate))
        memory.update_branch(source_outcome.receipts, source_certificate)

        stale_outcome = runtime.step(
            state,
            _make_abstraction_traces(spec, context=target_context, phase="target-exact-replay", actions=(stale_exact_action,)),
        )
        stale_certificate = build_branch_selection_certificate(
            stale_outcome.receipts,
            verifier_call_count=stale_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(stale_outcome.receipts), stale_certificate))

        abstract_outcome = runtime.step(
            state,
            _make_abstraction_traces(
                spec,
                context=target_context,
                phase="target-family-abstraction",
                actions=(abstract_target_action,),
            ),
        )
        state = normalize_state(abstract_outcome.state)
        abstract_certificate = build_branch_selection_certificate(
            abstract_outcome.receipts,
            verifier_call_count=abstract_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(abstract_outcome.receipts), abstract_certificate))

        certificate = build_branch_abstraction_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            abstract_family=family,
            source_action=spec.committed_action,
            stale_exact_action=str(stale_exact_action["action"]),
            abstract_target_action=str(abstract_target_action["action"]),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
            source_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed),
            source_reject_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected),
            source_rolled_back_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.commit_decision == "rolled_back_loser"
            ),
            stale_exact_receipt_hashes=tuple(receipt.receipt_hash for receipt in stale_outcome.receipts),
            abstract_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in abstract_outcome.receipts),
            abstract_target_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in abstract_outcome.receipts if receipt.committed),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            stale_branch_selection_certificate_hash=stale_certificate.certificate_hash,
            abstract_branch_selection_certificate_hash=abstract_certificate.certificate_hash,
            exact_replay_committed=stale_outcome.committed,
            abstraction_committed=abstract_outcome.committed,
            exact_verifier_call_count=stale_outcome.verifier_calls,
            abstraction_verifier_call_count=abstract_outcome.verifier_calls,
        )
        abstraction_certificates.append(certificate)

        rows.append(
            BranchAbstractionDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                abstract_family=family,
                source_action=certificate.source_action,
                stale_exact_action=certificate.stale_exact_action,
                abstract_target_action=certificate.abstract_target_action,
                exact_replay_committed=stale_outcome.committed,
                abstraction_committed=abstract_outcome.committed,
                exact_verifier_call_count=stale_outcome.verifier_calls,
                abstraction_verifier_call_count=abstract_outcome.verifier_calls,
                source_receipt_hashes=certificate.source_receipt_hashes,
                source_commit_receipt_hashes=certificate.source_commit_receipt_hashes,
                source_reject_receipt_hashes=certificate.source_reject_receipt_hashes,
                source_rolled_back_receipt_hashes=certificate.source_rolled_back_receipt_hashes,
                stale_exact_receipt_hashes=certificate.stale_exact_receipt_hashes,
                abstract_target_receipt_hashes=certificate.abstract_target_receipt_hashes,
                source_branch_selection_certificate_hash=source_certificate.certificate_hash,
                stale_branch_selection_certificate_hash=stale_certificate.certificate_hash,
                abstract_branch_selection_certificate_hash=abstract_certificate.certificate_hash,
                abstraction_certificate_hash=certificate.certificate_hash,
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

    report = BranchAbstractionTransferReport(
        schema_version="trwm.example.branch_abstraction_transfer.v1",
        experiment_id="branch_abstraction_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        exact_replay_success_count=sum(1 for row in rows if row.exact_replay_committed),
        abstraction_success_count=sum(1 for row in rows if row.abstraction_committed),
        same_budget_abstraction_count=sum(1 for row in rows if row.same_budget),
        branch_abstraction_certificate_count=len(abstraction_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_abstraction_certificates_valid=all(
            validate_branch_abstraction_certificate(certificate) for certificate in abstraction_certificates
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
        sources=BRANCH_ABSTRACTION_SOURCES,
        learning=(
            "Past branch receipts can improve exploration at an abstract option-family level: exact "
            "source-action replay can be stale, while a target-specific same-family action commits only "
            "after hard verification."
        ),
    )
    transfer_certificate = build_branch_abstraction_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_abstraction_certificate_hashes=tuple(certificate.certificate_hash for certificate in abstraction_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_abstraction_transfer",
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
        claim_boundary=BRANCH_ABSTRACTION_CLAIM_BOUNDARY,
        sources=BRANCH_ABSTRACTION_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchAbstractionTransferResult(
        report=report,
        branch_abstraction_transfer_certificate=transfer_certificate,
        branch_abstraction_certificates=tuple(abstraction_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_abstraction_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    abstract_family: str,
    source_action: str,
    stale_exact_action: str,
    abstract_target_action: str,
    source_receipt_hashes: tuple[str, ...],
    source_commit_receipt_hashes: tuple[str, ...],
    source_reject_receipt_hashes: tuple[str, ...],
    source_rolled_back_receipt_hashes: tuple[str, ...],
    stale_exact_receipt_hashes: tuple[str, ...],
    abstract_target_receipt_hashes: tuple[str, ...],
    abstract_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    stale_branch_selection_certificate_hash: str,
    abstract_branch_selection_certificate_hash: str,
    exact_replay_committed: bool,
    abstraction_committed: bool,
    exact_verifier_call_count: int,
    abstraction_verifier_call_count: int,
) -> BranchAbstractionCertificate:
    return BranchAbstractionCertificate(
        schema_version=BRANCH_ABSTRACTION_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        abstraction_rule_id="option_family_target_adaptation",
        abstraction_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        abstract_family=abstract_family,
        source_action=source_action,
        stale_exact_action=stale_exact_action,
        abstract_target_action=abstract_target_action,
        source_receipt_hashes=source_receipt_hashes,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_rolled_back_receipt_hashes=source_rolled_back_receipt_hashes,
        stale_exact_receipt_hashes=stale_exact_receipt_hashes,
        abstract_target_receipt_hashes=abstract_target_receipt_hashes,
        abstract_target_commit_receipt_hashes=abstract_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        stale_branch_selection_certificate_hash=stale_branch_selection_certificate_hash,
        abstract_branch_selection_certificate_hash=abstract_branch_selection_certificate_hash,
        exact_replay_committed=exact_replay_committed,
        abstraction_committed=abstraction_committed,
        exact_verifier_call_count=exact_verifier_call_count,
        abstraction_verifier_call_count=abstraction_verifier_call_count,
        same_budget=exact_verifier_call_count == abstraction_verifier_call_count == 1,
        abstraction_reason="exact_action_stale_but_option_family_adapts",
    )


def validate_branch_abstraction_certificate(
    certificate: BranchAbstractionCertificate,
    row: BranchAbstractionDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_ABSTRACTION_CERTIFICATE_SCHEMA:
            return False
        if certificate.abstraction_rule_id != "option_family_target_adaptation":
            return False
        if certificate.abstraction_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.abstract_family,
            certificate.source_action,
            certificate.stale_exact_action,
            certificate.abstract_target_action,
        ):
            if not _nonempty(value):
                return False
        if certificate.stale_exact_action != certificate.source_action:
            return False
        if certificate.abstract_target_action == certificate.source_action:
            return False
        if len(certificate.source_receipt_hashes) != 3:
            return False
        if len(certificate.source_commit_receipt_hashes) != 1:
            return False
        if len(certificate.source_reject_receipt_hashes) != 1:
            return False
        if len(certificate.source_rolled_back_receipt_hashes) != 1:
            return False
        if len(certificate.stale_exact_receipt_hashes) != 1:
            return False
        if len(certificate.abstract_target_receipt_hashes) != 1:
            return False
        if len(certificate.abstract_target_commit_receipt_hashes) != 1:
            return False
        if certificate.exact_replay_committed or not certificate.abstraction_committed:
            return False
        if certificate.exact_verifier_call_count != 1 or certificate.abstraction_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.abstraction_reason != "exact_action_stale_but_option_family_adapts":
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_commit_receipt_hashes,
            certificate.source_reject_receipt_hashes,
            certificate.source_rolled_back_receipt_hashes,
            certificate.stale_exact_receipt_hashes,
            certificate.abstract_target_receipt_hashes,
            certificate.abstract_target_commit_receipt_hashes,
            (
                certificate.source_branch_selection_certificate_hash,
                certificate.stale_branch_selection_certificate_hash,
                certificate.abstract_branch_selection_certificate_hash,
            ),
        ):
            if any(not _is_hash(value) for value in values):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.abstract_family != certificate.abstract_family:
                return False
            if row.source_action != certificate.source_action:
                return False
            if row.stale_exact_action != certificate.stale_exact_action:
                return False
            if row.abstract_target_action != certificate.abstract_target_action:
                return False
            if row.exact_replay_committed != certificate.exact_replay_committed:
                return False
            if row.abstraction_committed != certificate.abstraction_committed:
                return False
            if row.abstraction_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_abstraction_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_abstraction_transfer_certificate(
    report: BranchAbstractionTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_abstraction_certificate_hashes: tuple[str, ...],
) -> BranchAbstractionTransferCertificate:
    return BranchAbstractionTransferCertificate(
        schema_version=BRANCH_ABSTRACTION_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_abstraction_certificate_hashes=branch_abstraction_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        exact_replay_success_count=report.exact_replay_success_count,
        abstraction_success_count=report.abstraction_success_count,
        same_budget_abstraction_count=report.same_budget_abstraction_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_ABSTRACTION_CLAIM_BOUNDARY,
    )


def validate_branch_abstraction_transfer_certificate(
    certificate: BranchAbstractionTransferCertificate,
    report: BranchAbstractionTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_ABSTRACTION_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_abstraction_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_abstraction_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.exact_replay_success_count != 0:
            return False
        if certificate.abstraction_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_abstraction_count != certificate.domain_count:
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
            if not report.all_branch_abstraction_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.exact_replay_success_count != certificate.exact_replay_success_count:
                return False
            if report.abstraction_success_count != certificate.abstraction_success_count:
                return False
        return certificate.certificate_hash == branch_abstraction_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_abstraction_certificate_hash(certificate: BranchAbstractionCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchAbstractionCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_abstraction_transfer_certificate_hash(
    certificate: BranchAbstractionTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchAbstractionTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchAbstractionTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchAbstractionTransferReport,
    transfer_certificate: BranchAbstractionTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_abstraction_transfer_g1",
        claim_text=(
            "Past branch receipts can improve local target exploration through a certified abstract "
            "option family when exact source-action replay is stale under matched one-call budgets."
        ),
        evidence_grade="G1",
        scope="branch_abstraction_transfer",
        requirements=(
            requirement(
                "branch_abstraction_transfer_certificate_valid",
                validate_branch_abstraction_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_abstraction_certificates_valid", report.all_branch_abstraction_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("exact_replay_fails_all_domains", report.exact_replay_success_count == 0),
            requirement("abstraction_succeeds_all_domains", report.abstraction_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_abstraction_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "total_rolled_back_loser_count": report.total_rolled_back_loser_count,
            "exact_replay_success_count": report.exact_replay_success_count,
            "abstraction_success_count": report.abstraction_success_count,
        },
        boundary=BRANCH_ABSTRACTION_CLAIM_BOUNDARY,
        sources=BRANCH_ABSTRACTION_SOURCES,
    )


def _make_abstraction_traces(
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
            seeds=("branch-abstraction-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.abstraction.transfer.v1",
        )
        for action in actions
    )


def _source_actions(
    spec: ExplorationDomainSpec,
    context: str,
    abstract_family: str,
) -> tuple[Mapping[str, Any], ...]:
    reject = {**dict(spec.actions[0]), "context": context, "abstract_family": "known_bad"}
    winner = {**dict(next(action for action in spec.actions if action.get("target_commit"))), "context": context}
    winner["abstract_family"] = abstract_family
    accepted_loser = {**dict(spec.actions[1]), "context": context, "abstract_family": "fallback_safe"}
    return (reject, winner, accepted_loser)


def _abstract_family(spec: ExplorationDomainSpec) -> str:
    if spec.domain_id == "robotics_replan":
        return "safety_detour_option"
    if spec.domain_id == "molecule_repair":
        return "valence_strain_option"
    if spec.domain_id == "material_process":
        return "anneal_window_option"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _stale_exact_action(
    spec: ExplorationDomainSpec,
    context: str,
    abstract_family: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": spec.committed_action,
            "utility": 10,
            "clearance": 0.12,
            "turn_rate": 0.74,
            "abstract_family": abstract_family,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": spec.committed_action,
            "utility": 10,
            "valence_ok": False,
            "strain": 0.46,
            "abstract_family": abstract_family,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": spec.committed_action,
            "utility": 10,
            "thermal_gradient": 0.68,
            "phase_purity": 0.86,
            "abstract_family": abstract_family,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _abstract_target_action(
    spec: ExplorationDomainSpec,
    context: str,
    abstract_family: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "retimed_certified_detour",
            "utility": 8,
            "clearance": 0.31,
            "turn_rate": 0.46,
            "abstract_family": abstract_family,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "resonance_shift_repair",
            "utility": 8,
            "valence_ok": True,
            "strain": 0.18,
            "abstract_family": abstract_family,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "adaptive_tempered_anneal",
            "utility": 8,
            "thermal_gradient": 0.41,
            "phase_purity": 0.95,
            "abstract_family": abstract_family,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_abstraction_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
