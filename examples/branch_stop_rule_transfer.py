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
    BranchOutcome,
    BranchRuntime,
    BranchSelectionCertificate,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


BRANCH_STOP_RULE_CERTIFICATE_SCHEMA = "trwm.branch_stop_rule_certificate.v1"
BRANCH_STOP_RULE_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_stop_rule_transfer_certificate.v1"
BRANCH_STOP_RULE_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://www.sciencedirect.com/science/article/pii/0004370290900463",
)
BRANCH_STOP_RULE_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source reject receipts can certify "
    "a target stop rule that records abstentions and avoids verifier calls on a matched no-good family. "
    "It is not conflict-directed backjumping, nogood learning, optimal stopping, regret minimization, "
    "robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)
TARGET_STOP_BUDGET = 2


@dataclass(frozen=True)
class BranchStopRuleCertificate:
    schema_version: str
    domain: str
    stop_rule_id: str
    stop_rule_version: str
    source_context_id: str
    target_context_id: str
    rejected_family: str
    budget: int
    source_actions: tuple[str, ...]
    static_actions: tuple[str, ...]
    stopped_actions: tuple[str, ...]
    source_receipt_hashes: tuple[str, ...]
    source_reject_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    stopped_receipt_hashes: tuple[str, ...]
    stopped_abstain_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    stopped_branch_selection_certificate_hash: str
    source_rejected_count: int
    source_committed_count: int
    static_committed: bool
    stopped_committed: bool
    static_verifier_call_count: int
    stopped_verifier_call_count: int
    unused_verifier_budget: int
    same_budget: bool
    stop_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_STOP_RULE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch stop-rule certificate schema: {self.schema_version}")
        for field_name in (
            "source_actions",
            "static_actions",
            "stopped_actions",
            "source_receipt_hashes",
            "source_reject_receipt_hashes",
            "source_commit_receipt_hashes",
            "static_receipt_hashes",
            "stopped_receipt_hashes",
            "stopped_abstain_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_stop_rule_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchStopRuleDomainReport:
    domain: str
    source_context: str
    target_context: str
    rejected_family: str
    budget: int
    source_actions: tuple[str, ...]
    static_actions: tuple[str, ...]
    stopped_actions: tuple[str, ...]
    source_rejected_count: int
    source_committed_count: int
    static_committed: bool
    stopped_committed: bool
    static_verifier_call_count: int
    stopped_verifier_call_count: int
    stopped_abstain_count: int
    avoided_verifier_call_count: int
    unused_verifier_budget: int
    source_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    stopped_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    stopped_branch_selection_certificate_hash: str
    branch_stop_rule_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchStopRuleTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchStopRuleDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_abstained_count: int
    total_rolled_back_loser_count: int
    source_commit_count: int
    source_reject_count: int
    static_success_count: int
    stopped_success_count: int
    static_verifier_call_count: int
    stopped_verifier_call_count: int
    stopped_abstain_count: int
    avoided_verifier_call_count: int
    same_budget_stop_count: int
    branch_stop_rule_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_stop_rule_certificates_valid: bool
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
class BranchStopRuleTransferCertificate:
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
    branch_stop_rule_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    budget: int
    source_commit_count: int
    source_reject_count: int
    static_success_count: int
    stopped_success_count: int
    static_verifier_call_count: int
    stopped_verifier_call_count: int
    stopped_abstain_count: int
    avoided_verifier_call_count: int
    same_budget_stop_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_STOP_RULE_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch stop-rule transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_stop_rule_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_stop_rule_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchStopRuleTransferResult(CertifiedExampleResult):
    report: BranchStopRuleTransferReport
    branch_stop_rule_transfer_certificate: BranchStopRuleTransferCertificate
    branch_stop_rule_certificates: tuple[BranchStopRuleCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_stop_rule_transfer_experiment() -> BranchStopRuleTransferReport:
    return run_branch_stop_rule_transfer_certified_experiment().report


def run_branch_stop_rule_transfer_certified_experiment() -> CertifiedBranchStopRuleTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    projector = AncestralExplorationProjector()
    memory = AncestralBranchMemory()
    rows: list[BranchStopRuleDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    stop_rule_certificates: list[BranchStopRuleCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:stop_rule"
        target_context = f"{spec.domain_id}:target:stop_rule"
        actions = _stop_rule_actions(spec)
        source_actions = (
            _with_context(actions["bad_a"], source_context),
            _with_context(actions["bad_b"], source_context),
            _with_context(actions["repair"], source_context),
        )
        target_actions = (
            _with_context(actions["bad_a"], target_context),
            _with_context(actions["bad_b"], target_context),
        )

        source_outcome = runtime.step(
            state,
            _make_stop_rule_traces(
                spec,
                context=source_context,
                phase="source-stop-evidence",
                actions=source_actions,
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
            _make_stop_rule_traces(
                spec,
                context=target_context,
                phase="target-static-spend",
                actions=target_actions,
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        stopped_outcome = _record_stop_rule_abstentions(
            engine,
            projector,
            state,
            _make_stop_rule_traces(
                spec,
                context=target_context,
                phase="target-stop-rule",
                actions=target_actions,
            ),
            spec=spec,
            source_context=source_context,
            budget=TARGET_STOP_BUDGET,
            source_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
        )
        stopped_certificate = build_branch_selection_certificate(
            stopped_outcome.receipts,
            verifier_call_count=stopped_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(stopped_outcome.receipts), stopped_certificate))

        certificate = build_branch_stop_rule_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            source_actions=tuple(str(action["action"]) for action in source_actions),
            static_actions=tuple(str(action["action"]) for action in target_actions),
            stopped_actions=tuple(str(action["action"]) for action in target_actions),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
            source_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
            source_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed),
            static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            stopped_receipt_hashes=tuple(receipt.receipt_hash for receipt in stopped_outcome.receipts),
            stopped_abstain_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in stopped_outcome.receipts if receipt.hard_result.abstained
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            stopped_branch_selection_certificate_hash=stopped_certificate.certificate_hash,
            source_rejected_count=sum(1 for receipt in source_outcome.receipts if receipt.hard_result.rejected),
            source_committed_count=sum(1 for receipt in source_outcome.receipts if receipt.committed),
            static_committed=static_outcome.committed,
            stopped_committed=stopped_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            stopped_verifier_call_count=stopped_outcome.verifier_calls,
            unused_verifier_budget=TARGET_STOP_BUDGET - stopped_outcome.verifier_calls,
        )
        stop_rule_certificates.append(certificate)

        rows.append(
            BranchStopRuleDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                rejected_family=_rejected_family(spec),
                budget=TARGET_STOP_BUDGET,
                source_actions=certificate.source_actions,
                static_actions=certificate.static_actions,
                stopped_actions=certificate.stopped_actions,
                source_rejected_count=certificate.source_rejected_count,
                source_committed_count=certificate.source_committed_count,
                static_committed=static_outcome.committed,
                stopped_committed=stopped_outcome.committed,
                static_verifier_call_count=static_outcome.verifier_calls,
                stopped_verifier_call_count=stopped_outcome.verifier_calls,
                stopped_abstain_count=stopped_outcome.abstained_count,
                avoided_verifier_call_count=static_outcome.verifier_calls - stopped_outcome.verifier_calls,
                unused_verifier_budget=TARGET_STOP_BUDGET - stopped_outcome.verifier_calls,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
                static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
                stopped_receipt_hashes=tuple(receipt.receipt_hash for receipt in stopped_outcome.receipts),
                source_branch_selection_certificate_hash=source_certificate.certificate_hash,
                static_branch_selection_certificate_hash=static_certificate.certificate_hash,
                stopped_branch_selection_certificate_hash=stopped_certificate.certificate_hash,
                branch_stop_rule_certificate_hash=certificate.certificate_hash,
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
    report = BranchStopRuleTransferReport(
        schema_version="trwm.example.branch_stop_rule_transfer.v1",
        experiment_id="branch_stop_rule_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_abstained_count=sum(1 for receipt in all_receipts if receipt.hard_result.abstained),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_commit_count=sum(row.source_committed_count for row in rows),
        source_reject_count=sum(row.source_rejected_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        stopped_success_count=sum(1 for row in rows if row.stopped_committed),
        static_verifier_call_count=sum(row.static_verifier_call_count for row in rows),
        stopped_verifier_call_count=sum(row.stopped_verifier_call_count for row in rows),
        stopped_abstain_count=sum(row.stopped_abstain_count for row in rows),
        avoided_verifier_call_count=sum(row.avoided_verifier_call_count for row in rows),
        same_budget_stop_count=sum(1 for row in rows if row.same_budget),
        branch_stop_rule_certificate_count=len(stop_rule_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_stop_rule_certificates_valid=all(
            validate_branch_stop_rule_certificate(certificate) for certificate in stop_rule_certificates
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
        sources=BRANCH_STOP_RULE_SOURCES,
        learning=(
            "Past branch receipts can improve exploration by certifying when a matched target family "
            "should stop before spending scarce verifier calls. The target does not gain a commit; it "
            "gains a receipt-bound abstention and keeps hard-verifier authority intact."
        ),
    )
    transfer_certificate = build_branch_stop_rule_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_stop_rule_certificate_hashes=tuple(certificate.certificate_hash for certificate in stop_rule_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_stop_rule_transfer",
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
        claim_boundary=BRANCH_STOP_RULE_CLAIM_BOUNDARY,
        sources=BRANCH_STOP_RULE_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchStopRuleTransferResult(
        report=report,
        branch_stop_rule_transfer_certificate=transfer_certificate,
        branch_stop_rule_certificates=tuple(stop_rule_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_stop_rule_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    source_actions: tuple[str, ...],
    static_actions: tuple[str, ...],
    stopped_actions: tuple[str, ...],
    source_receipt_hashes: tuple[str, ...],
    source_reject_receipt_hashes: tuple[str, ...],
    source_commit_receipt_hashes: tuple[str, ...],
    static_receipt_hashes: tuple[str, ...],
    stopped_receipt_hashes: tuple[str, ...],
    stopped_abstain_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    stopped_branch_selection_certificate_hash: str,
    source_rejected_count: int,
    source_committed_count: int,
    static_committed: bool,
    stopped_committed: bool,
    static_verifier_call_count: int,
    stopped_verifier_call_count: int,
    unused_verifier_budget: int,
) -> BranchStopRuleCertificate:
    return BranchStopRuleCertificate(
        schema_version=BRANCH_STOP_RULE_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        stop_rule_id="receipt_bound_no_good_stop",
        stop_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        rejected_family=_rejected_family(spec),
        budget=TARGET_STOP_BUDGET,
        source_actions=source_actions,
        static_actions=static_actions,
        stopped_actions=stopped_actions,
        source_receipt_hashes=source_receipt_hashes,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        static_receipt_hashes=static_receipt_hashes,
        stopped_receipt_hashes=stopped_receipt_hashes,
        stopped_abstain_receipt_hashes=stopped_abstain_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        stopped_branch_selection_certificate_hash=stopped_branch_selection_certificate_hash,
        source_rejected_count=source_rejected_count,
        source_committed_count=source_committed_count,
        static_committed=static_committed,
        stopped_committed=stopped_committed,
        static_verifier_call_count=static_verifier_call_count,
        stopped_verifier_call_count=stopped_verifier_call_count,
        unused_verifier_budget=unused_verifier_budget,
        same_budget=unused_verifier_budget == TARGET_STOP_BUDGET and static_verifier_call_count == TARGET_STOP_BUDGET,
        stop_reason="matched_source_no_good_family",
    )


def validate_branch_stop_rule_certificate(
    certificate: BranchStopRuleCertificate,
    row: BranchStopRuleDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_STOP_RULE_CERTIFICATE_SCHEMA:
            return False
        if certificate.stop_rule_id != "receipt_bound_no_good_stop" or certificate.stop_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.rejected_family):
            return False
        if certificate.budget != TARGET_STOP_BUDGET:
            return False
        if len(certificate.source_actions) != 3 or len(certificate.static_actions) != 2:
            return False
        if certificate.static_actions != certificate.stopped_actions:
            return False
        if len(certificate.source_receipt_hashes) != 3:
            return False
        if len(certificate.source_reject_receipt_hashes) != 2 or len(certificate.source_commit_receipt_hashes) != 1:
            return False
        if len(certificate.static_receipt_hashes) != 2 or len(certificate.stopped_receipt_hashes) != 2:
            return False
        if len(certificate.stopped_abstain_receipt_hashes) != 2:
            return False
        if certificate.source_rejected_count != 2 or certificate.source_committed_count != 1:
            return False
        if certificate.static_committed or certificate.stopped_committed:
            return False
        if certificate.static_verifier_call_count != TARGET_STOP_BUDGET:
            return False
        if certificate.stopped_verifier_call_count != 0:
            return False
        if certificate.unused_verifier_budget != TARGET_STOP_BUDGET:
            return False
        if not certificate.same_budget:
            return False
        if certificate.stop_reason != "matched_source_no_good_family":
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_reject_receipt_hashes,
            certificate.source_commit_receipt_hashes,
            certificate.static_receipt_hashes,
            certificate.stopped_receipt_hashes,
            certificate.stopped_abstain_receipt_hashes,
            (
                certificate.source_branch_selection_certificate_hash,
                certificate.static_branch_selection_certificate_hash,
                certificate.stopped_branch_selection_certificate_hash,
            ),
        ):
            if any(not _is_hash(value) for value in values):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.rejected_family != certificate.rejected_family:
                return False
            if row.source_actions != certificate.source_actions:
                return False
            if row.static_actions != certificate.static_actions or row.stopped_actions != certificate.stopped_actions:
                return False
            if row.source_rejected_count != certificate.source_rejected_count:
                return False
            if row.source_committed_count != certificate.source_committed_count:
                return False
            if row.static_committed != certificate.static_committed or row.stopped_committed != certificate.stopped_committed:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.stopped_verifier_call_count != certificate.stopped_verifier_call_count:
                return False
            if row.stopped_abstain_count != len(certificate.stopped_abstain_receipt_hashes):
                return False
            if row.avoided_verifier_call_count != TARGET_STOP_BUDGET:
                return False
            if row.branch_stop_rule_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_stop_rule_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_stop_rule_transfer_certificate(
    report: BranchStopRuleTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_stop_rule_certificate_hashes: tuple[str, ...],
) -> BranchStopRuleTransferCertificate:
    return BranchStopRuleTransferCertificate(
        schema_version=BRANCH_STOP_RULE_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_stop_rule_certificate_hashes=branch_stop_rule_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        budget=TARGET_STOP_BUDGET,
        source_commit_count=report.source_commit_count,
        source_reject_count=report.source_reject_count,
        static_success_count=report.static_success_count,
        stopped_success_count=report.stopped_success_count,
        static_verifier_call_count=report.static_verifier_call_count,
        stopped_verifier_call_count=report.stopped_verifier_call_count,
        stopped_abstain_count=report.stopped_abstain_count,
        avoided_verifier_call_count=report.avoided_verifier_call_count,
        same_budget_stop_count=report.same_budget_stop_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_STOP_RULE_CLAIM_BOUNDARY,
    )


def validate_branch_stop_rule_transfer_certificate(
    certificate: BranchStopRuleTransferCertificate,
    report: BranchStopRuleTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_STOP_RULE_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        if certificate.budget != TARGET_STOP_BUDGET:
            return False
        if not _is_hash(certificate.report_hash) or not _is_hash(certificate.ledger_head):
            return False
        if not _is_hash(certificate.memory_snapshot_hash):
            return False
        for values in (
            certificate.receipt_hashes,
            certificate.branch_selection_certificate_hashes,
            certificate.branch_stop_rule_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 7:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_stop_rule_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_commit_count != certificate.domain_count:
            return False
        if certificate.source_reject_count != certificate.domain_count * 2:
            return False
        if certificate.static_success_count != 0 or certificate.stopped_success_count != 0:
            return False
        if certificate.static_verifier_call_count != certificate.domain_count * TARGET_STOP_BUDGET:
            return False
        if certificate.stopped_verifier_call_count != 0:
            return False
        if certificate.stopped_abstain_count != certificate.domain_count * TARGET_STOP_BUDGET:
            return False
        if certificate.avoided_verifier_call_count != certificate.domain_count * TARGET_STOP_BUDGET:
            return False
        if certificate.same_budget_stop_count != certificate.domain_count:
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
            if tuple(row.branch_stop_rule_certificate_hash for row in report.rows) != certificate.branch_stop_rule_certificate_hashes:
                return False
            if not report.all_branch_stop_rule_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if report.branch_stop_rule_certificate_count != len(certificate.branch_stop_rule_certificate_hashes):
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_commit_count != certificate.source_commit_count:
                return False
            if report.source_reject_count != certificate.source_reject_count:
                return False
            if report.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if report.stopped_verifier_call_count != certificate.stopped_verifier_call_count:
                return False
            if report.stopped_abstain_count != certificate.stopped_abstain_count:
                return False
            if report.avoided_verifier_call_count != certificate.avoided_verifier_call_count:
                return False
        return certificate.certificate_hash == branch_stop_rule_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_stop_rule_certificate_hash(
    certificate: BranchStopRuleCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchStopRuleCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_stop_rule_transfer_certificate_hash(
    certificate: BranchStopRuleTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchStopRuleTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchStopRuleTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchStopRuleTransferReport,
    transfer_certificate: BranchStopRuleTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_stop_rule_transfer_g1",
        claim_text=(
            "Past negative branch receipts can improve local target exploration by certifying a stop rule "
            "that records target abstentions and avoids verifier calls on a matched no-good family."
        ),
        evidence_grade="G1",
        scope="branch_stop_rule_transfer",
        requirements=(
            requirement(
                "branch_stop_rule_transfer_certificate_valid",
                validate_branch_stop_rule_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_stop_rule_certificates_valid", report.all_branch_stop_rule_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_commits_all_domains", report.source_commit_count == report.domain_count),
            requirement("source_rejects_two_per_domain", report.source_reject_count == report.domain_count * 2),
            requirement("static_commits_no_domains", report.static_success_count == 0),
            requirement("stopped_commits_no_domains", report.stopped_success_count == 0),
            requirement("stopped_abstains_all_target_candidates", report.stopped_abstain_count == report.domain_count * 2),
            requirement("avoids_all_target_verifier_calls", report.avoided_verifier_call_count == report.domain_count * 2),
            requirement("same_budget_all_domains", report.same_budget_stop_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 3),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "total_abstained_count": report.total_abstained_count,
            "source_commit_count": report.source_commit_count,
            "source_reject_count": report.source_reject_count,
            "static_verifier_call_count": report.static_verifier_call_count,
            "stopped_verifier_call_count": report.stopped_verifier_call_count,
            "stopped_abstain_count": report.stopped_abstain_count,
            "avoided_verifier_call_count": report.avoided_verifier_call_count,
        },
        boundary=BRANCH_STOP_RULE_CLAIM_BOUNDARY,
        sources=BRANCH_STOP_RULE_SOURCES,
    )


def _record_stop_rule_abstentions(
    engine: TransactionEngine,
    projector: AncestralExplorationProjector,
    state: AncestralExplorationState,
    traces: Iterable[ProposalTrace],
    *,
    spec: ExplorationDomainSpec,
    source_context: str,
    budget: int,
    source_reject_receipt_hashes: tuple[str, ...],
) -> BranchOutcome:
    receipts: list[Receipt] = []
    trace_rows = tuple(traces)
    for trace in trace_rows:
        candidate = projector.project(state, trace)
        result = HardVerifierResult.abstain(
            engine.adapter.verifier_id,
            engine.adapter.verifier_version,
            residual={
                "kind": "branch_stop_rule_matched_no_good",
                "domain": spec.domain_id,
                "source_context": source_context,
                "rejected_family": _rejected_family(spec),
                "source_reject_receipt_hashes": source_reject_receipt_hashes,
            },
            metadata={
                "domain": spec.domain_id,
                "action": candidate.payload["action"],
                "budget": budget,
                "remaining_budget": budget,
                "verifier_cost_spent": 0,
                "stop_rule": "receipt_bound_no_good_stop",
            },
        )
        outcome = engine.record_evaluated_candidate(
            state,
            trace,
            candidate,
            result,
            force_decision="branch_stop_rule_abstain",
        )
        receipts.append(outcome.receipt)
    return BranchOutcome(
        state=state,
        committed=False,
        receipts=tuple(receipts),
        verifier_calls=0,
        reason="branch_stop_rule_abstain",
        verifier_cost=0,
        abstained_count=len(receipts),
    )


def _make_stop_rule_traces(
    spec: ExplorationDomainSpec,
    *,
    context: str,
    phase: str,
    actions: Iterable[Mapping[str, Any]],
) -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"{context}:{phase}:{action['action']}",
            actions=(dict(action),),
            seeds=("branch-stop-rule-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.stop_rule.transfer.v1",
        )
        for action in actions
    )


def _with_context(action: Mapping[str, Any], context: str) -> dict[str, Any]:
    return {**dict(action), "context": context}


def _stop_rule_actions(spec: ExplorationDomainSpec) -> Mapping[str, Mapping[str, Any]]:
    bad_a = dict(spec.actions[0])
    repair = dict(next(action for action in spec.actions if action.get("target_commit")))
    if spec.domain_id == "robotics_replan":
        bad_b = {
            "domain": spec.domain_id,
            "action": "stop_rule_high_turn_retry",
            "utility": 9,
            "clearance": 0.30,
            "turn_rate": 0.95,
        }
    elif spec.domain_id == "molecule_repair":
        bad_b = {
            "domain": spec.domain_id,
            "action": "stop_rule_high_strain_retry",
            "utility": 9,
            "valence_ok": True,
            "strain": 0.62,
        }
    elif spec.domain_id == "material_process":
        bad_b = {
            "domain": spec.domain_id,
            "action": "stop_rule_impure_retry",
            "utility": 9,
            "thermal_gradient": 0.48,
            "phase_purity": 0.82,
        }
    else:
        raise ValueError(f"unknown domain: {spec.domain_id}")
    return {"bad_a": bad_a, "bad_b": bad_b, "repair": repair}


def _rejected_family(spec: ExplorationDomainSpec) -> str:
    if spec.domain_id == "robotics_replan":
        return "unsafe_trajectory_retry"
    if spec.domain_id == "molecule_repair":
        return "invalid_chemistry_retry"
    if spec.domain_id == "material_process":
        return "invalid_process_window_retry"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_stop_rule_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
