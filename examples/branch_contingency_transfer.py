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


BRANCH_CONTINGENCY_CERTIFICATE_SCHEMA = "trwm.branch_contingency_certificate.v1"
BRANCH_CONTINGENCY_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_contingency_transfer_certificate.v1"
BRANCH_CONTINGENCY_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://papers.nips.cc/paper/3178-the-epoch-greedy-algorithm-for-multi-armed-bandits-with-side-information",
)
BRANCH_CONTINGENCY_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows past branch receipts can certify "
    "a target-context regime switch that avoids stale unconditional branch reuse under a matched "
    "one-call verifier budget. It is not contextual-bandit regret evidence, automatic policy learning, "
    "robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchContingencyCertificate:
    schema_version: str
    domain: str
    contingency_rule_id: str
    contingency_rule_version: str
    context_feature_key: str
    stale_regime: str
    target_regime: str
    stale_source_context_id: str
    matched_source_context_id: str
    target_context_id: str
    stale_action: str
    contingent_action: str
    stale_source_receipt_hashes: tuple[str, ...]
    matched_source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    contingent_target_receipt_hashes: tuple[str, ...]
    contingent_target_commit_receipt_hashes: tuple[str, ...]
    stale_source_branch_selection_certificate_hash: str
    matched_source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    contingent_branch_selection_certificate_hash: str
    selected_source_context_id: str
    rejected_source_context_ids: tuple[str, ...]
    static_committed: bool
    contingent_committed: bool
    static_verifier_call_count: int
    contingent_verifier_call_count: int
    same_budget: bool
    contingency_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONTINGENCY_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch contingency certificate schema: {self.schema_version}")
        for field_name in (
            "stale_source_receipt_hashes",
            "matched_source_receipt_hashes",
            "static_target_receipt_hashes",
            "contingent_target_receipt_hashes",
            "contingent_target_commit_receipt_hashes",
            "rejected_source_context_ids",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_contingency_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchContingencyDomainReport:
    domain: str
    context_feature_key: str
    stale_regime: str
    target_regime: str
    stale_source_context: str
    matched_source_context: str
    target_context: str
    stale_action: str
    contingent_action: str
    selected_source_context: str
    rejected_source_contexts: tuple[str, ...]
    static_committed: bool
    contingent_committed: bool
    static_verifier_call_count: int
    contingent_verifier_call_count: int
    stale_source_receipt_hashes: tuple[str, ...]
    matched_source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    contingent_target_receipt_hashes: tuple[str, ...]
    contingency_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchContingencyTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchContingencyDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    static_success_count: int
    contingent_success_count: int
    selected_context_count: int
    rejected_context_count: int
    same_budget_contingency_count: int
    branch_contingency_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_contingency_certificates_valid: bool
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
class BranchContingencyTransferCertificate:
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
    branch_contingency_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    static_success_count: int
    contingent_success_count: int
    selected_context_count: int
    rejected_context_count: int
    same_budget_contingency_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONTINGENCY_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch contingency transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_contingency_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_contingency_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchContingencyTransferResult(CertifiedExampleResult):
    report: BranchContingencyTransferReport
    branch_contingency_transfer_certificate: BranchContingencyTransferCertificate
    branch_contingency_certificates: tuple[BranchContingencyCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_contingency_transfer_experiment() -> BranchContingencyTransferReport:
    return run_branch_contingency_transfer_certified_experiment().report


def run_branch_contingency_transfer_certified_experiment() -> CertifiedBranchContingencyTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[BranchContingencyDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    contingency_certificates: list[BranchContingencyCertificate] = []

    for spec in DOMAIN_SPECS:
        stale_regime, target_regime = _regimes(spec)
        stale_source_context = f"{spec.domain_id}:source:contingency:{stale_regime}"
        matched_source_context = f"{spec.domain_id}:source:contingency:{target_regime}"
        target_context = f"{spec.domain_id}:target:contingency:{target_regime}"
        stale_source_action = _source_action(spec, stale_source_context, stale_regime)
        matched_source_action = _source_action(spec, matched_source_context, target_regime)
        static_target_action = _stale_target_action(spec, target_context, stale_regime, target_regime)
        contingent_target_action = _contingent_target_action(spec, target_context, target_regime)

        stale_source_outcome = runtime.step(
            state,
            _make_contingency_traces(
                spec,
                context=stale_source_context,
                phase="source-stale-regime",
                actions=(stale_source_action,),
            ),
        )
        state = normalize_state(stale_source_outcome.state)
        stale_source_certificate = build_branch_selection_certificate(
            stale_source_outcome.receipts,
            verifier_call_count=stale_source_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(stale_source_outcome.receipts), stale_source_certificate))
        memory.update_branch(stale_source_outcome.receipts, stale_source_certificate)

        matched_source_outcome = runtime.step(
            state,
            _make_contingency_traces(
                spec,
                context=matched_source_context,
                phase="source-target-regime",
                actions=(matched_source_action,),
            ),
        )
        state = normalize_state(matched_source_outcome.state)
        matched_source_certificate = build_branch_selection_certificate(
            matched_source_outcome.receipts,
            verifier_call_count=matched_source_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(matched_source_outcome.receipts), matched_source_certificate))
        memory.update_branch(matched_source_outcome.receipts, matched_source_certificate)

        static_outcome = runtime.step(
            state,
            _make_contingency_traces(
                spec,
                context=target_context,
                phase="target-stale-unconditional",
                actions=(static_target_action,),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        contingent_outcome = runtime.step(
            state,
            _make_contingency_traces(
                spec,
                context=target_context,
                phase="target-contingent-regime",
                actions=(contingent_target_action,),
            ),
        )
        state = normalize_state(contingent_outcome.state)
        contingent_certificate = build_branch_selection_certificate(
            contingent_outcome.receipts,
            verifier_call_count=contingent_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(contingent_outcome.receipts), contingent_certificate))

        certificate = build_branch_contingency_certificate(
            spec,
            context_feature_key="regime",
            stale_regime=stale_regime,
            target_regime=target_regime,
            stale_source_context_id=stale_source_context,
            matched_source_context_id=matched_source_context,
            target_context_id=target_context,
            stale_action=str(static_target_action["action"]),
            contingent_action=str(contingent_target_action["action"]),
            stale_source_receipt_hashes=tuple(receipt.receipt_hash for receipt in stale_source_outcome.receipts),
            matched_source_receipt_hashes=tuple(receipt.receipt_hash for receipt in matched_source_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            contingent_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in contingent_outcome.receipts),
            contingent_target_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in contingent_outcome.receipts if receipt.committed),
            stale_source_branch_selection_certificate_hash=stale_source_certificate.certificate_hash,
            matched_source_branch_selection_certificate_hash=matched_source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            contingent_branch_selection_certificate_hash=contingent_certificate.certificate_hash,
            static_committed=static_outcome.committed,
            contingent_committed=contingent_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            contingent_verifier_call_count=contingent_outcome.verifier_calls,
        )
        contingency_certificates.append(certificate)

        rows.append(
            BranchContingencyDomainReport(
                domain=spec.domain_id,
                context_feature_key=certificate.context_feature_key,
                stale_regime=stale_regime,
                target_regime=target_regime,
                stale_source_context=stale_source_context,
                matched_source_context=matched_source_context,
                target_context=target_context,
                stale_action=certificate.stale_action,
                contingent_action=certificate.contingent_action,
                selected_source_context=certificate.selected_source_context_id,
                rejected_source_contexts=certificate.rejected_source_context_ids,
                static_committed=static_outcome.committed,
                contingent_committed=contingent_outcome.committed,
                static_verifier_call_count=static_outcome.verifier_calls,
                contingent_verifier_call_count=contingent_outcome.verifier_calls,
                stale_source_receipt_hashes=certificate.stale_source_receipt_hashes,
                matched_source_receipt_hashes=certificate.matched_source_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                contingent_target_receipt_hashes=certificate.contingent_target_receipt_hashes,
                contingency_certificate_hash=certificate.certificate_hash,
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

    report = BranchContingencyTransferReport(
        schema_version="trwm.example.branch_contingency_transfer.v1",
        experiment_id="branch_contingency_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        static_success_count=sum(1 for row in rows if row.static_committed),
        contingent_success_count=sum(1 for row in rows if row.contingent_committed),
        selected_context_count=sum(1 for row in rows if row.selected_source_context == row.matched_source_context),
        rejected_context_count=sum(len(row.rejected_source_contexts) for row in rows),
        same_budget_contingency_count=sum(1 for row in rows if row.same_budget),
        branch_contingency_certificate_count=len(contingency_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_contingency_certificates_valid=all(
            validate_branch_contingency_certificate(certificate) for certificate in contingency_certificates
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
        hard_gate_keys=("regime", "clearance", "turn_rate", "valence_ok", "strain", "thermal_gradient", "phase_purity"),
        residual_kinds=tuple(sorted({spec.residual_kind for spec in DOMAIN_SPECS})),
        sources=BRANCH_CONTINGENCY_SOURCES,
        learning=(
            "Past branch receipts can improve exploration through a certified context switchpoint: the "
            "target rejects stale unconditional reuse but commits the branch supported by the matching "
            "source regime under the same one-call budget."
        ),
    )
    transfer_certificate = build_branch_contingency_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_contingency_certificate_hashes=tuple(certificate.certificate_hash for certificate in contingency_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_contingency_transfer",
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
        claim_boundary=BRANCH_CONTINGENCY_CLAIM_BOUNDARY,
        sources=BRANCH_CONTINGENCY_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchContingencyTransferResult(
        report=report,
        branch_contingency_transfer_certificate=transfer_certificate,
        branch_contingency_certificates=tuple(contingency_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_contingency_certificate(
    spec: ExplorationDomainSpec,
    *,
    context_feature_key: str,
    stale_regime: str,
    target_regime: str,
    stale_source_context_id: str,
    matched_source_context_id: str,
    target_context_id: str,
    stale_action: str,
    contingent_action: str,
    stale_source_receipt_hashes: tuple[str, ...],
    matched_source_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    contingent_target_receipt_hashes: tuple[str, ...],
    contingent_target_commit_receipt_hashes: tuple[str, ...],
    stale_source_branch_selection_certificate_hash: str,
    matched_source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    contingent_branch_selection_certificate_hash: str,
    static_committed: bool,
    contingent_committed: bool,
    static_verifier_call_count: int,
    contingent_verifier_call_count: int,
) -> BranchContingencyCertificate:
    return BranchContingencyCertificate(
        schema_version=BRANCH_CONTINGENCY_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        contingency_rule_id="receipt_bound_regime_switchpoint",
        contingency_rule_version="1.0",
        context_feature_key=context_feature_key,
        stale_regime=stale_regime,
        target_regime=target_regime,
        stale_source_context_id=stale_source_context_id,
        matched_source_context_id=matched_source_context_id,
        target_context_id=target_context_id,
        stale_action=stale_action,
        contingent_action=contingent_action,
        stale_source_receipt_hashes=stale_source_receipt_hashes,
        matched_source_receipt_hashes=matched_source_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        contingent_target_receipt_hashes=contingent_target_receipt_hashes,
        contingent_target_commit_receipt_hashes=contingent_target_commit_receipt_hashes,
        stale_source_branch_selection_certificate_hash=stale_source_branch_selection_certificate_hash,
        matched_source_branch_selection_certificate_hash=matched_source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        contingent_branch_selection_certificate_hash=contingent_branch_selection_certificate_hash,
        selected_source_context_id=matched_source_context_id,
        rejected_source_context_ids=(stale_source_context_id,),
        static_committed=static_committed,
        contingent_committed=contingent_committed,
        static_verifier_call_count=static_verifier_call_count,
        contingent_verifier_call_count=contingent_verifier_call_count,
        same_budget=static_verifier_call_count == contingent_verifier_call_count == 1,
        contingency_reason="target_regime_selects_matching_source_branch",
    )


def validate_branch_contingency_certificate(
    certificate: BranchContingencyCertificate,
    row: BranchContingencyDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONTINGENCY_CERTIFICATE_SCHEMA:
            return False
        if certificate.contingency_rule_id != "receipt_bound_regime_switchpoint":
            return False
        if certificate.contingency_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.context_feature_key,
            certificate.stale_regime,
            certificate.target_regime,
            certificate.stale_source_context_id,
            certificate.matched_source_context_id,
            certificate.target_context_id,
            certificate.stale_action,
            certificate.contingent_action,
        ):
            if not _nonempty(value):
                return False
        if certificate.stale_regime == certificate.target_regime:
            return False
        if certificate.selected_source_context_id != certificate.matched_source_context_id:
            return False
        if certificate.rejected_source_context_ids != (certificate.stale_source_context_id,):
            return False
        if certificate.stale_action == certificate.contingent_action:
            return False
        if certificate.static_committed or not certificate.contingent_committed:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.contingent_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.contingency_reason != "target_regime_selects_matching_source_branch":
            return False
        for values in (
            certificate.stale_source_receipt_hashes,
            certificate.matched_source_receipt_hashes,
            certificate.static_target_receipt_hashes,
            certificate.contingent_target_receipt_hashes,
            certificate.contingent_target_commit_receipt_hashes,
        ):
            if len(values) != 1 or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.stale_source_branch_selection_certificate_hash,
            certificate.matched_source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.contingent_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.context_feature_key != certificate.context_feature_key:
                return False
            if row.stale_regime != certificate.stale_regime or row.target_regime != certificate.target_regime:
                return False
            if row.stale_source_context != certificate.stale_source_context_id:
                return False
            if row.matched_source_context != certificate.matched_source_context_id:
                return False
            if row.target_context != certificate.target_context_id:
                return False
            if row.stale_action != certificate.stale_action or row.contingent_action != certificate.contingent_action:
                return False
            if row.selected_source_context != certificate.selected_source_context_id:
                return False
            if row.rejected_source_contexts != certificate.rejected_source_context_ids:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.contingent_committed != certificate.contingent_committed:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.contingent_verifier_call_count != certificate.contingent_verifier_call_count:
                return False
            if row.stale_source_receipt_hashes != certificate.stale_source_receipt_hashes:
                return False
            if row.matched_source_receipt_hashes != certificate.matched_source_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.contingent_target_receipt_hashes != certificate.contingent_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.contingency_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_contingency_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_contingency_transfer_certificate(
    report: BranchContingencyTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_contingency_certificate_hashes: tuple[str, ...],
) -> BranchContingencyTransferCertificate:
    return BranchContingencyTransferCertificate(
        schema_version=BRANCH_CONTINGENCY_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_contingency_certificate_hashes=branch_contingency_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        static_success_count=report.static_success_count,
        contingent_success_count=report.contingent_success_count,
        selected_context_count=report.selected_context_count,
        rejected_context_count=report.rejected_context_count,
        same_budget_contingency_count=report.same_budget_contingency_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CONTINGENCY_CLAIM_BOUNDARY,
    )


def validate_branch_contingency_transfer_certificate(
    certificate: BranchContingencyTransferCertificate,
    report: BranchContingencyTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONTINGENCY_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_contingency_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_contingency_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.contingent_success_count != certificate.domain_count:
            return False
        if certificate.selected_context_count != certificate.domain_count:
            return False
        if certificate.rejected_context_count != certificate.domain_count:
            return False
        if certificate.same_budget_contingency_count != certificate.domain_count:
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
            if not report.all_branch_contingency_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
        return certificate.certificate_hash == branch_contingency_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_contingency_certificate_hash(certificate: BranchContingencyCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchContingencyCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_contingency_transfer_certificate_hash(
    certificate: BranchContingencyTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchContingencyTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchContingencyTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchContingencyTransferReport,
    transfer_certificate: BranchContingencyTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_contingency_transfer_g1",
        claim_text=(
            "Past branch receipts can improve local target exploration by certifying a target-regime "
            "switchpoint under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_contingency_transfer",
        requirements=(
            requirement(
                "branch_contingency_transfer_certificate_valid",
                validate_branch_contingency_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_contingency_certificates_valid", report.all_branch_contingency_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("contingent_succeeds_all_domains", report.contingent_success_count == report.domain_count),
            requirement("matching_context_selected_all_domains", report.selected_context_count == report.domain_count),
            requirement("stale_context_rejected_all_domains", report.rejected_context_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_contingency_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "static_success_count": report.static_success_count,
            "contingent_success_count": report.contingent_success_count,
            "selected_context_count": report.selected_context_count,
            "rejected_context_count": report.rejected_context_count,
        },
        boundary=BRANCH_CONTINGENCY_CLAIM_BOUNDARY,
        sources=BRANCH_CONTINGENCY_SOURCES,
    )


def _make_contingency_traces(
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
            seeds=("branch-contingency-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.contingency.transfer.v1",
        )
        for action in actions
    )


def _regimes(spec: ExplorationDomainSpec) -> tuple[str, str]:
    if spec.domain_id == "robotics_replan":
        return "open_corridor", "narrow_corridor"
    if spec.domain_id == "molecule_repair":
        return "low_strain", "strained_ring"
    if spec.domain_id == "material_process":
        return "slow_cool", "thermal_spike"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _source_action(spec: ExplorationDomainSpec, context: str, regime: str) -> Mapping[str, Any]:
    stale_regime, target_regime = _regimes(spec)
    if regime == stale_regime:
        action = {**dict(spec.actions[1]), "context": context, "regime": regime, "target_commit": True}
        action["utility"] = 8
        return action
    if regime == target_regime:
        action = {**dict(next(item for item in spec.actions if item.get("target_commit"))), "context": context, "regime": regime}
        action["utility"] = 8
        return action
    raise ValueError(f"unknown regime: {regime}")


def _stale_target_action(
    spec: ExplorationDomainSpec,
    context: str,
    stale_regime: str,
    target_regime: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "straight_corridor",
            "utility": 9,
            "clearance": 0.18,
            "turn_rate": 0.72,
            "regime": target_regime,
            "source_regime": stale_regime,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "single_bond_pad",
            "utility": 9,
            "valence_ok": True,
            "strain": 0.44,
            "regime": target_regime,
            "source_regime": stale_regime,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "slow_anneal",
            "utility": 9,
            "thermal_gradient": 0.58,
            "phase_purity": 0.91,
            "regime": target_regime,
            "source_regime": stale_regime,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _contingent_target_action(spec: ExplorationDomainSpec, context: str, target_regime: str) -> Mapping[str, Any]:
    action = {**dict(next(item for item in spec.actions if item.get("target_commit"))), "context": context, "regime": target_regime}
    action["utility"] = 8
    return action


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_contingency_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
