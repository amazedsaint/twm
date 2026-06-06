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


BRANCH_RECENCY_CERTIFICATE_SCHEMA = "trwm.branch_recency_certificate.v1"
BRANCH_RECENCY_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_recency_transfer_certificate.v1"
BRANCH_RECENCY_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://arxiv.org/abs/0805.3415",
)
BRANCH_RECENCY_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows recent source receipts can override "
    "older stale branch commits before target verifier budget is spent under a matched one-call budget. "
    "It is not a non-stationary bandit regret result, adaptive control result, production memory-policy "
    "claim, robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchRecencyCertificate:
    schema_version: str
    domain: str
    recency_rule_id: str
    recency_rule_version: str
    source_context_ids: tuple[str, ...]
    recent_context_id: str
    target_context_id: str
    stale_action: str
    adapted_action: str
    old_stale_commit_receipt_hashes: tuple[str, ...]
    recent_stale_reject_receipt_hashes: tuple[str, ...]
    recent_adapted_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    recency_target_receipt_hashes: tuple[str, ...]
    recency_target_commit_receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]
    cumulative_top_action: str
    recency_top_action: str
    cumulative_stale_commit_count: int
    recent_stale_reject_count: int
    recent_adapted_commit_count: int
    static_committed: bool
    recency_committed: bool
    static_verifier_call_count: int
    recency_verifier_call_count: int
    same_budget: bool
    recency_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_RECENCY_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch recency certificate schema: {self.schema_version}")
        for field_name in (
            "source_context_ids",
            "old_stale_commit_receipt_hashes",
            "recent_stale_reject_receipt_hashes",
            "recent_adapted_commit_receipt_hashes",
            "static_target_receipt_hashes",
            "recency_target_receipt_hashes",
            "recency_target_commit_receipt_hashes",
            "branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_recency_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchRecencyDomainReport:
    domain: str
    source_contexts: tuple[str, ...]
    recent_context: str
    target_context: str
    stale_action: str
    adapted_action: str
    cumulative_top_action: str
    recency_top_action: str
    cumulative_stale_commit_count: int
    recent_stale_reject_count: int
    recent_adapted_commit_count: int
    static_committed: bool
    recency_committed: bool
    static_verifier_call_count: int
    recency_verifier_call_count: int
    old_stale_commit_receipt_hashes: tuple[str, ...]
    recent_stale_reject_receipt_hashes: tuple[str, ...]
    recent_adapted_commit_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    recency_target_receipt_hashes: tuple[str, ...]
    recency_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchRecencyTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchRecencyDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    old_stale_commit_count: int
    recent_stale_reject_count: int
    recent_adapted_commit_count: int
    static_success_count: int
    recency_success_count: int
    same_budget_recency_count: int
    branch_recency_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_recency_certificates_valid: bool
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
class BranchRecencyTransferCertificate:
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
    branch_recency_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    old_stale_commit_count: int
    recent_stale_reject_count: int
    recent_adapted_commit_count: int
    static_success_count: int
    recency_success_count: int
    same_budget_recency_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_RECENCY_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch recency transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_recency_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_recency_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchRecencyTransferResult(CertifiedExampleResult):
    report: BranchRecencyTransferReport
    branch_recency_transfer_certificate: BranchRecencyTransferCertificate
    branch_recency_certificates: tuple[BranchRecencyCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_recency_weight_transfer_experiment() -> BranchRecencyTransferReport:
    return run_branch_recency_weight_transfer_certified_experiment().report


def run_branch_recency_weight_transfer_certified_experiment() -> CertifiedBranchRecencyTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchRecencyDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    recency_certificates: list[BranchRecencyCertificate] = []

    for spec in DOMAIN_SPECS:
        stale_action = _stale_action_name(spec)
        adapted_action = _adapted_action_name(spec)
        old_contexts = (
            f"{spec.domain_id}:source:recency:old:0",
            f"{spec.domain_id}:source:recency:old:1",
        )
        recent_context = f"{spec.domain_id}:source:recency:recent"
        target_context = f"{spec.domain_id}:target:recency"

        old_outcomes = []
        old_certificates = []
        for idx, old_context in enumerate(old_contexts):
            old_outcome = runtime.step(
                state,
                _make_recency_traces(
                    spec,
                    context=old_context,
                    phase=f"source-old-{idx}",
                    actions=(_old_stale_source_action(spec, old_context),),
                ),
            )
            state = normalize_state(old_outcome.state)
            old_certificate = build_branch_selection_certificate(
                old_outcome.receipts,
                verifier_call_count=old_outcome.verifier_calls,
            )
            branch_certificate_pairs.append((tuple(old_outcome.receipts), old_certificate))
            memory.update_branch(old_outcome.receipts, old_certificate)
            old_outcomes.append(old_outcome)
            old_certificates.append(old_certificate)

        recent_outcome = runtime.step(
            state,
            _make_recency_traces(
                spec,
                context=recent_context,
                phase="source-recent-window",
                actions=(
                    _recent_stale_source_action(spec, recent_context),
                    _adapted_source_action(spec, recent_context),
                ),
            ),
        )
        state = normalize_state(recent_outcome.state)
        recent_certificate = build_branch_selection_certificate(
            recent_outcome.receipts,
            verifier_call_count=recent_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(recent_outcome.receipts), recent_certificate))
        memory.update_branch(recent_outcome.receipts, recent_certificate)

        static_outcome = runtime.step(
            state,
            _make_recency_traces(
                spec,
                context=target_context,
                phase="target-cumulative-stale",
                actions=(_stale_target_action(spec, target_context),),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        recency_outcome = runtime.step(
            state,
            _make_recency_traces(
                spec,
                context=target_context,
                phase="target-recency-window",
                actions=(_adapted_target_action(spec, target_context),),
            ),
        )
        state = normalize_state(recency_outcome.state)
        recency_certificate = build_branch_selection_certificate(
            recency_outcome.receipts,
            verifier_call_count=recency_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(recency_outcome.receipts), recency_certificate))

        old_commit_hashes = tuple(
            receipt.receipt_hash
            for outcome in old_outcomes
            for receipt in outcome.receipts
            if receipt.committed
        )
        recent_stale_reject_hashes = tuple(
            receipt.receipt_hash
            for receipt in recent_outcome.receipts
            if receipt.hard_result.rejected
        )
        recent_adapted_commit_hashes = tuple(
            receipt.receipt_hash
            for receipt in recent_outcome.receipts
            if receipt.committed
        )
        certificate = build_branch_recency_certificate(
            spec,
            source_context_ids=(*old_contexts, recent_context),
            recent_context_id=recent_context,
            target_context_id=target_context,
            stale_action=stale_action,
            adapted_action=adapted_action,
            old_stale_commit_receipt_hashes=old_commit_hashes,
            recent_stale_reject_receipt_hashes=recent_stale_reject_hashes,
            recent_adapted_commit_receipt_hashes=recent_adapted_commit_hashes,
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            recency_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in recency_outcome.receipts),
            recency_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in recency_outcome.receipts if receipt.committed
            ),
            branch_selection_certificate_hashes=tuple(
                certificate.certificate_hash
                for certificate in (
                    *old_certificates,
                    recent_certificate,
                    static_certificate,
                    recency_certificate,
                )
            ),
            static_committed=static_outcome.committed,
            recency_committed=recency_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            recency_verifier_call_count=recency_outcome.verifier_calls,
        )
        recency_certificates.append(certificate)
        rows.append(
            BranchRecencyDomainReport(
                domain=spec.domain_id,
                source_contexts=certificate.source_context_ids,
                recent_context=certificate.recent_context_id,
                target_context=certificate.target_context_id,
                stale_action=certificate.stale_action,
                adapted_action=certificate.adapted_action,
                cumulative_top_action=certificate.cumulative_top_action,
                recency_top_action=certificate.recency_top_action,
                cumulative_stale_commit_count=certificate.cumulative_stale_commit_count,
                recent_stale_reject_count=certificate.recent_stale_reject_count,
                recent_adapted_commit_count=certificate.recent_adapted_commit_count,
                static_committed=certificate.static_committed,
                recency_committed=certificate.recency_committed,
                static_verifier_call_count=certificate.static_verifier_call_count,
                recency_verifier_call_count=certificate.recency_verifier_call_count,
                old_stale_commit_receipt_hashes=certificate.old_stale_commit_receipt_hashes,
                recent_stale_reject_receipt_hashes=certificate.recent_stale_reject_receipt_hashes,
                recent_adapted_commit_receipt_hashes=certificate.recent_adapted_commit_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                recency_target_receipt_hashes=certificate.recency_target_receipt_hashes,
                recency_certificate_hash=certificate.certificate_hash,
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

    report = BranchRecencyTransferReport(
        schema_version="trwm.example.branch_recency_weight_transfer.v1",
        experiment_id="branch_recency_weight_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        old_stale_commit_count=sum(row.cumulative_stale_commit_count for row in rows),
        recent_stale_reject_count=sum(row.recent_stale_reject_count for row in rows),
        recent_adapted_commit_count=sum(row.recent_adapted_commit_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        recency_success_count=sum(1 for row in rows if row.recency_committed),
        same_budget_recency_count=sum(1 for row in rows if row.same_budget),
        branch_recency_certificate_count=len(recency_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_recency_certificates_valid=all(
            validate_branch_recency_certificate(certificate, row)
            for certificate, row in zip(recency_certificates, rows)
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
        sources=BRANCH_RECENCY_SOURCES,
        learning=(
            "Branches of the past can improve exploration through receipt freshness: old commits make a "
            "stale action look attractive under cumulative history, while recent reject/commit evidence "
            "selects the adapted action before the target spends its one verifier call."
        ),
    )
    transfer_certificate = build_branch_recency_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_recency_certificate_hashes=tuple(certificate.certificate_hash for certificate in recency_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_recency_weight_transfer",
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
        claim_boundary=BRANCH_RECENCY_CLAIM_BOUNDARY,
        sources=BRANCH_RECENCY_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchRecencyTransferResult(
        report=report,
        branch_recency_transfer_certificate=transfer_certificate,
        branch_recency_certificates=tuple(recency_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_recency_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_ids: tuple[str, ...],
    recent_context_id: str,
    target_context_id: str,
    stale_action: str,
    adapted_action: str,
    old_stale_commit_receipt_hashes: tuple[str, ...],
    recent_stale_reject_receipt_hashes: tuple[str, ...],
    recent_adapted_commit_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    recency_target_receipt_hashes: tuple[str, ...],
    recency_target_commit_receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    static_committed: bool,
    recency_committed: bool,
    static_verifier_call_count: int,
    recency_verifier_call_count: int,
) -> BranchRecencyCertificate:
    return BranchRecencyCertificate(
        schema_version=BRANCH_RECENCY_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        recency_rule_id="latest_valid_window_overrides_cumulative_stale_commit_majority",
        recency_rule_version="1.0",
        source_context_ids=source_context_ids,
        recent_context_id=recent_context_id,
        target_context_id=target_context_id,
        stale_action=stale_action,
        adapted_action=adapted_action,
        old_stale_commit_receipt_hashes=old_stale_commit_receipt_hashes,
        recent_stale_reject_receipt_hashes=recent_stale_reject_receipt_hashes,
        recent_adapted_commit_receipt_hashes=recent_adapted_commit_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        recency_target_receipt_hashes=recency_target_receipt_hashes,
        recency_target_commit_receipt_hashes=recency_target_commit_receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        cumulative_top_action=stale_action,
        recency_top_action=adapted_action,
        cumulative_stale_commit_count=len(old_stale_commit_receipt_hashes),
        recent_stale_reject_count=len(recent_stale_reject_receipt_hashes),
        recent_adapted_commit_count=len(recent_adapted_commit_receipt_hashes),
        static_committed=static_committed,
        recency_committed=recency_committed,
        static_verifier_call_count=static_verifier_call_count,
        recency_verifier_call_count=recency_verifier_call_count,
        same_budget=static_verifier_call_count == recency_verifier_call_count == 1,
        recency_reason="latest_valid_window_overrides_cumulative_stale_commit_majority",
    )


def validate_branch_recency_certificate(
    certificate: BranchRecencyCertificate,
    row: BranchRecencyDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_RECENCY_CERTIFICATE_SCHEMA:
            return False
        if certificate.recency_rule_id != "latest_valid_window_overrides_cumulative_stale_commit_majority":
            return False
        if certificate.recency_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.recent_context_id,
            certificate.target_context_id,
            certificate.stale_action,
            certificate.adapted_action,
            certificate.cumulative_top_action,
            certificate.recency_top_action,
            certificate.recency_reason,
        ):
            if not _nonempty(value):
                return False
        if certificate.stale_action == certificate.adapted_action:
            return False
        if certificate.cumulative_top_action != certificate.stale_action:
            return False
        if certificate.recency_top_action != certificate.adapted_action:
            return False
        if certificate.cumulative_stale_commit_count != 2:
            return False
        if certificate.recent_stale_reject_count != 1 or certificate.recent_adapted_commit_count != 1:
            return False
        if certificate.static_committed or not certificate.recency_committed:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.recency_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if len(certificate.source_context_ids) != 3:
            return False
        if certificate.recent_context_id not in certificate.source_context_ids:
            return False
        for values, expected_len in (
            (certificate.old_stale_commit_receipt_hashes, 2),
            (certificate.recent_stale_reject_receipt_hashes, 1),
            (certificate.recent_adapted_commit_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.recency_target_receipt_hashes, 1),
            (certificate.recency_target_commit_receipt_hashes, 1),
            (certificate.branch_selection_certificate_hashes, 5),
        ):
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_contexts != certificate.source_context_ids:
                return False
            if row.recent_context != certificate.recent_context_id:
                return False
            if row.target_context != certificate.target_context_id:
                return False
            if row.stale_action != certificate.stale_action or row.adapted_action != certificate.adapted_action:
                return False
            if row.cumulative_top_action != certificate.cumulative_top_action:
                return False
            if row.recency_top_action != certificate.recency_top_action:
                return False
            if row.cumulative_stale_commit_count != certificate.cumulative_stale_commit_count:
                return False
            if row.recent_stale_reject_count != certificate.recent_stale_reject_count:
                return False
            if row.recent_adapted_commit_count != certificate.recent_adapted_commit_count:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.recency_committed != certificate.recency_committed:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.recency_verifier_call_count != certificate.recency_verifier_call_count:
                return False
            if row.old_stale_commit_receipt_hashes != certificate.old_stale_commit_receipt_hashes:
                return False
            if row.recent_stale_reject_receipt_hashes != certificate.recent_stale_reject_receipt_hashes:
                return False
            if row.recent_adapted_commit_receipt_hashes != certificate.recent_adapted_commit_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.recency_target_receipt_hashes != certificate.recency_target_receipt_hashes:
                return False
            if row.recency_certificate_hash != certificate.certificate_hash:
                return False
            if row.same_budget != certificate.same_budget:
                return False
        return certificate.certificate_hash == branch_recency_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_recency_transfer_certificate(
    report: BranchRecencyTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_recency_certificate_hashes: tuple[str, ...],
) -> BranchRecencyTransferCertificate:
    return BranchRecencyTransferCertificate(
        schema_version=BRANCH_RECENCY_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_recency_certificate_hashes=branch_recency_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        old_stale_commit_count=report.old_stale_commit_count,
        recent_stale_reject_count=report.recent_stale_reject_count,
        recent_adapted_commit_count=report.recent_adapted_commit_count,
        static_success_count=report.static_success_count,
        recency_success_count=report.recency_success_count,
        same_budget_recency_count=report.same_budget_recency_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_RECENCY_CLAIM_BOUNDARY,
    )


def validate_branch_recency_transfer_certificate(
    certificate: BranchRecencyTransferCertificate,
    report: BranchRecencyTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_RECENCY_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_recency_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_recency_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.old_stale_commit_count != certificate.domain_count * 2:
            return False
        if certificate.recent_stale_reject_count != certificate.domain_count:
            return False
        if certificate.recent_adapted_commit_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.recency_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_recency_count != certificate.domain_count:
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
            if not report.all_branch_recency_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.old_stale_commit_count != certificate.old_stale_commit_count:
                return False
            if report.recent_stale_reject_count != certificate.recent_stale_reject_count:
                return False
            if report.recent_adapted_commit_count != certificate.recent_adapted_commit_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.recency_success_count != certificate.recency_success_count:
                return False
        return certificate.certificate_hash == branch_recency_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_recency_certificate_hash(certificate: BranchRecencyCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchRecencyCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_recency_transfer_certificate_hash(
    certificate: BranchRecencyTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchRecencyTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchRecencyTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchRecencyTransferReport,
    transfer_certificate: BranchRecencyTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_recency_weight_transfer_g1",
        claim_text=(
            "Recent source receipts can improve local target exploration by overriding older stale "
            "branch commits under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_recency_weight_transfer",
        requirements=(
            requirement(
                "branch_recency_transfer_certificate_valid",
                validate_branch_recency_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid),
            requirement("all_branch_recency_certificates_valid", report.all_branch_recency_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("old_stale_commits_bound", report.old_stale_commit_count == report.domain_count * 2),
            requirement("recent_stale_rejects_bound", report.recent_stale_reject_count == report.domain_count),
            requirement("recent_adapted_commits_bound", report.recent_adapted_commit_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("recency_succeeds_all_domains", report.recency_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_recency_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "old_stale_commit_count": report.old_stale_commit_count,
            "recent_stale_reject_count": report.recent_stale_reject_count,
            "recent_adapted_commit_count": report.recent_adapted_commit_count,
            "static_success_count": report.static_success_count,
            "recency_success_count": report.recency_success_count,
        },
        boundary=BRANCH_RECENCY_CLAIM_BOUNDARY,
        sources=BRANCH_RECENCY_SOURCES,
    )


def _make_recency_traces(
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
            seeds=("branch-recency-weight-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.recency.weight.transfer.v1",
        )
        for action in actions
    )


def _stale_action_name(spec: ExplorationDomainSpec) -> str:
    if spec.domain_id == "robotics_replan":
        return "legacy_corridor_cut"
    if spec.domain_id == "molecule_repair":
        return "legacy_valence_patch"
    if spec.domain_id == "material_process":
        return "legacy_fast_quench"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _adapted_action_name(spec: ExplorationDomainSpec) -> str:
    if spec.domain_id == "robotics_replan":
        return "recency_wide_detour"
    if spec.domain_id == "molecule_repair":
        return "recency_strain_relief"
    if spec.domain_id == "material_process":
        return "recency_tempered_window"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _old_stale_source_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _stale_action_name(spec),
            "utility": 9,
            "clearance": 0.31,
            "turn_rate": 0.42,
            "target_commit": True,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _stale_action_name(spec),
            "utility": 9,
            "valence_ok": True,
            "strain": 0.24,
            "target_commit": True,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _stale_action_name(spec),
            "utility": 9,
            "thermal_gradient": 0.44,
            "phase_purity": 0.94,
            "target_commit": True,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _recent_stale_source_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    action = dict(_stale_target_action(spec, context))
    action["phase"] = "source-recent-window"
    return action


def _adapted_source_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    action = dict(_adapted_target_action(spec, context))
    action["phase"] = "source-recent-window"
    return action


def _stale_target_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _stale_action_name(spec),
            "utility": 9,
            "clearance": 0.12,
            "turn_rate": 0.84,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _stale_action_name(spec),
            "utility": 9,
            "valence_ok": False,
            "strain": 0.44,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _stale_action_name(spec),
            "utility": 9,
            "thermal_gradient": 0.78,
            "phase_purity": 0.86,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _adapted_target_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _adapted_action_name(spec),
            "utility": 8,
            "clearance": 0.36,
            "turn_rate": 0.38,
            "target_commit": True,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _adapted_action_name(spec),
            "utility": 8,
            "valence_ok": True,
            "strain": 0.14,
            "target_commit": True,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": _adapted_action_name(spec),
            "utility": 8,
            "thermal_gradient": 0.38,
            "phase_purity": 0.96,
            "target_commit": True,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_recency_weight_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
