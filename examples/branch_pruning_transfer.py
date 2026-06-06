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
    BranchSelectionCertificate,
    BranchRuntime,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


BRANCH_PRUNING_CERTIFICATE_SCHEMA = "trwm.branch_pruning_certificate.v1"
BRANCH_PRUNING_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_pruning_transfer_certificate.v1"
BRANCH_PRUNING_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://www.sciencedirect.com/science/article/pii/S1572528616000062",
    "https://digitalcommons.unl.edu/csetechreports/158/",
    "https://users.aalto.fi/~tjunttil/2020-DP-AUT/notes-sat/cdcl.html",
)
BRANCH_PRUNING_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows rejected source branch receipts can "
    "certify pruning of known-dead target candidates so the same verifier budget reaches an admissible "
    "candidate. It is not branch-and-bound performance evidence, CDCL, a CSP solver, a planning "
    "algorithm, robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchPruningCertificate:
    schema_version: str
    domain: str
    pruning_rule_id: str
    pruning_rule_version: str
    source_context_id: str
    target_context_id: str
    candidate_actions: tuple[str, ...]
    pruned_actions: tuple[str, ...]
    baseline_actions: tuple[str, ...]
    pruned_candidate_actions: tuple[str, ...]
    committed_target_action: str
    source_receipt_hashes: tuple[str, ...]
    source_reject_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    pruned_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    pruned_branch_selection_certificate_hash: str
    static_committed: bool
    pruned_committed: bool
    static_verifier_call_count: int
    pruned_verifier_call_count: int
    same_budget: bool
    pruning_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PRUNING_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch pruning certificate schema: {self.schema_version}")
        for field_name in (
            "candidate_actions",
            "pruned_actions",
            "baseline_actions",
            "pruned_candidate_actions",
            "source_receipt_hashes",
            "source_reject_receipt_hashes",
            "source_commit_receipt_hashes",
            "static_receipt_hashes",
            "pruned_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_pruning_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchPruningDomainReport:
    domain: str
    source_context: str
    target_context: str
    candidate_actions: tuple[str, ...]
    pruned_actions: tuple[str, ...]
    baseline_actions: tuple[str, ...]
    pruned_candidate_actions: tuple[str, ...]
    committed_target_action: str
    static_budget_committed: bool
    pruned_budget_committed: bool
    source_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    pruned_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    pruned_branch_selection_certificate_hash: str
    pruning_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchPruningTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchPruningDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    pruned_action_count: int
    static_budget_success_count: int
    pruned_budget_success_count: int
    same_budget_pruning_count: int
    branch_pruning_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_pruning_certificates_valid: bool
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
class BranchPruningTransferCertificate:
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
    branch_pruning_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    pruned_action_count: int
    static_budget_success_count: int
    pruned_budget_success_count: int
    same_budget_pruning_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PRUNING_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch pruning transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_pruning_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_pruning_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchPruningTransferResult(CertifiedExampleResult):
    report: BranchPruningTransferReport
    branch_pruning_transfer_certificate: BranchPruningTransferCertificate
    branch_pruning_certificates: tuple[BranchPruningCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_pruning_transfer_experiment() -> BranchPruningTransferReport:
    return run_branch_pruning_transfer_certified_experiment().report


def run_branch_pruning_transfer_certified_experiment() -> CertifiedBranchPruningTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[BranchPruningDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    pruning_certificates: list[BranchPruningCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:pruning"
        target_context = f"{spec.domain_id}:target:pruning"
        action_map = _pruning_actions(spec)
        candidate_actions = (
            action_map["bad_a"],
            action_map["bad_b"],
            action_map["winner"],
            action_map["safe_loser"],
        )
        pruned_actions = (str(action_map["bad_a"]["action"]), str(action_map["bad_b"]["action"]))
        source_outcome = runtime.step(
            state,
            _make_pruning_traces(
                spec,
                context=source_context,
                phase="source-pruning-evidence",
                episode=0,
                actions=(
                    _with_context(action_map["bad_a"], source_context),
                    _with_context(action_map["bad_b"], source_context),
                    _with_context(action_map["winner"], source_context),
                ),
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
            _make_pruning_traces(
                spec,
                context=target_context,
                phase="target-static-budget-two",
                episode=0,
                actions=(
                    _with_context(action_map["bad_a"], target_context),
                    _with_context(action_map["bad_b"], target_context),
                ),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        pruned_outcome = runtime.step(
            state,
            _make_pruning_traces(
                spec,
                context=target_context,
                phase="target-pruned-budget-two",
                episode=0,
                actions=(
                    _with_context(action_map["winner"], target_context),
                    _with_context(action_map["safe_loser"], target_context),
                ),
            ),
        )
        state = normalize_state(pruned_outcome.state)
        pruned_certificate = build_branch_selection_certificate(
            pruned_outcome.receipts,
            verifier_call_count=pruned_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(pruned_outcome.receipts), pruned_certificate))

        pruning_certificate = build_branch_pruning_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            candidate_actions=tuple(str(action["action"]) for action in candidate_actions),
            pruned_actions=pruned_actions,
            baseline_actions=pruned_actions,
            pruned_candidate_actions=(str(action_map["winner"]["action"]), str(action_map["safe_loser"]["action"])),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
            source_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
            source_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed),
            static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            pruned_receipt_hashes=tuple(receipt.receipt_hash for receipt in pruned_outcome.receipts),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            pruned_branch_selection_certificate_hash=pruned_certificate.certificate_hash,
            static_committed=static_outcome.committed,
            pruned_committed=pruned_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            pruned_verifier_call_count=pruned_outcome.verifier_calls,
        )
        pruning_certificates.append(pruning_certificate)

        rows.append(
            BranchPruningDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                candidate_actions=pruning_certificate.candidate_actions,
                pruned_actions=pruning_certificate.pruned_actions,
                baseline_actions=pruning_certificate.baseline_actions,
                pruned_candidate_actions=pruning_certificate.pruned_candidate_actions,
                committed_target_action=spec.committed_action,
                static_budget_committed=static_outcome.committed,
                pruned_budget_committed=pruned_outcome.committed,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
                static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
                pruned_receipt_hashes=tuple(receipt.receipt_hash for receipt in pruned_outcome.receipts),
                source_branch_selection_certificate_hash=source_certificate.certificate_hash,
                static_branch_selection_certificate_hash=static_certificate.certificate_hash,
                pruned_branch_selection_certificate_hash=pruned_certificate.certificate_hash,
                pruning_certificate_hash=pruning_certificate.certificate_hash,
                same_budget=pruning_certificate.same_budget,
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
    report = BranchPruningTransferReport(
        schema_version="trwm.example.branch_pruning_transfer.v1",
        experiment_id="branch_pruning_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        pruned_action_count=sum(len(row.pruned_actions) for row in rows),
        static_budget_success_count=sum(1 for row in rows if row.static_budget_committed),
        pruned_budget_success_count=sum(1 for row in rows if row.pruned_budget_committed),
        same_budget_pruning_count=sum(1 for row in rows if row.same_budget),
        branch_pruning_certificate_count=len(pruning_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_pruning_certificates_valid=all(
            validate_branch_pruning_certificate(certificate) for certificate in pruning_certificates
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
        sources=BRANCH_PRUNING_SOURCES,
        learning=(
            "Rejected branches can improve exploration by pruning known-dead candidates before scarce "
            "verifier budget is spent. The pruning certificate is only an admission filter; the remaining "
            "candidate still commits solely through the hard verifier and branch-selection audit."
        ),
    )
    transfer_certificate = build_branch_pruning_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_pruning_certificate_hashes=tuple(certificate.certificate_hash for certificate in pruning_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_pruning_transfer",
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
        claim_boundary=BRANCH_PRUNING_CLAIM_BOUNDARY,
        sources=BRANCH_PRUNING_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchPruningTransferResult(
        report=report,
        branch_pruning_transfer_certificate=transfer_certificate,
        branch_pruning_certificates=tuple(pruning_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_pruning_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    candidate_actions: tuple[str, ...],
    pruned_actions: tuple[str, ...],
    baseline_actions: tuple[str, ...],
    pruned_candidate_actions: tuple[str, ...],
    source_receipt_hashes: tuple[str, ...],
    source_reject_receipt_hashes: tuple[str, ...],
    source_commit_receipt_hashes: tuple[str, ...],
    static_receipt_hashes: tuple[str, ...],
    pruned_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    pruned_branch_selection_certificate_hash: str,
    static_committed: bool,
    pruned_committed: bool,
    static_verifier_call_count: int,
    pruned_verifier_call_count: int,
) -> BranchPruningCertificate:
    return BranchPruningCertificate(
        schema_version=BRANCH_PRUNING_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        pruning_rule_id="receipt_bound_nogood_pruning",
        pruning_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        candidate_actions=candidate_actions,
        pruned_actions=pruned_actions,
        baseline_actions=baseline_actions,
        pruned_candidate_actions=pruned_candidate_actions,
        committed_target_action=spec.committed_action,
        source_receipt_hashes=source_receipt_hashes,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        static_receipt_hashes=static_receipt_hashes,
        pruned_receipt_hashes=pruned_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        pruned_branch_selection_certificate_hash=pruned_branch_selection_certificate_hash,
        static_committed=static_committed,
        pruned_committed=pruned_committed,
        static_verifier_call_count=static_verifier_call_count,
        pruned_verifier_call_count=pruned_verifier_call_count,
        same_budget=static_verifier_call_count == pruned_verifier_call_count == 2,
        pruning_reason="source_reject_receipts_mark_known_dead_actions",
    )


def validate_branch_pruning_certificate(
    certificate: BranchPruningCertificate,
    row: BranchPruningDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PRUNING_CERTIFICATE_SCHEMA:
            return False
        if certificate.pruning_rule_id != "receipt_bound_nogood_pruning" or certificate.pruning_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id):
            return False
        if len(certificate.candidate_actions) != 4:
            return False
        if len(certificate.pruned_actions) != 2 or len(certificate.baseline_actions) != 2:
            return False
        if certificate.pruned_actions != certificate.baseline_actions:
            return False
        if len(certificate.pruned_candidate_actions) != 2:
            return False
        if certificate.committed_target_action != certificate.pruned_candidate_actions[0]:
            return False
        if set(certificate.pruned_actions) & set(certificate.pruned_candidate_actions):
            return False
        if not set(certificate.pruned_actions).issubset(set(certificate.candidate_actions)):
            return False
        if not set(certificate.pruned_candidate_actions).issubset(set(certificate.candidate_actions)):
            return False
        if certificate.static_committed:
            return False
        if not certificate.pruned_committed:
            return False
        if not certificate.same_budget or certificate.static_verifier_call_count != 2 or certificate.pruned_verifier_call_count != 2:
            return False
        if len(certificate.source_receipt_hashes) != 3:
            return False
        if len(certificate.source_reject_receipt_hashes) != 2 or len(certificate.source_commit_receipt_hashes) != 1:
            return False
        if len(certificate.static_receipt_hashes) != 2 or len(certificate.pruned_receipt_hashes) != 2:
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_reject_receipt_hashes,
            certificate.source_commit_receipt_hashes,
            certificate.static_receipt_hashes,
            certificate.pruned_receipt_hashes,
            (
                certificate.source_branch_selection_certificate_hash,
                certificate.static_branch_selection_certificate_hash,
                certificate.pruned_branch_selection_certificate_hash,
            ),
        ):
            if any(not _is_hash(value) for value in values):
                return False
        if certificate.pruning_reason != "source_reject_receipts_mark_known_dead_actions":
            return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.candidate_actions != certificate.candidate_actions:
                return False
            if row.pruned_actions != certificate.pruned_actions:
                return False
            if row.baseline_actions != certificate.baseline_actions:
                return False
            if row.pruned_candidate_actions != certificate.pruned_candidate_actions:
                return False
            if row.static_budget_committed != certificate.static_committed:
                return False
            if row.pruned_budget_committed != certificate.pruned_committed:
                return False
            if row.pruning_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_pruning_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_pruning_transfer_certificate(
    report: BranchPruningTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_pruning_certificate_hashes: tuple[str, ...],
) -> BranchPruningTransferCertificate:
    return BranchPruningTransferCertificate(
        schema_version=BRANCH_PRUNING_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_pruning_certificate_hashes=branch_pruning_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        pruned_action_count=report.pruned_action_count,
        static_budget_success_count=report.static_budget_success_count,
        pruned_budget_success_count=report.pruned_budget_success_count,
        same_budget_pruning_count=report.same_budget_pruning_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_PRUNING_CLAIM_BOUNDARY,
    )


def validate_branch_pruning_transfer_certificate(
    certificate: BranchPruningTransferCertificate,
    report: BranchPruningTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PRUNING_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_pruning_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 7:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_pruning_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.pruned_action_count != certificate.domain_count * 2:
            return False
        if certificate.static_budget_success_count != 0:
            return False
        if certificate.pruned_budget_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_pruning_count != certificate.domain_count:
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
            if not report.all_branch_pruning_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.pruned_action_count != certificate.pruned_action_count:
                return False
            if report.static_budget_success_count != certificate.static_budget_success_count:
                return False
            if report.pruned_budget_success_count != certificate.pruned_budget_success_count:
                return False
        return certificate.certificate_hash == branch_pruning_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_pruning_certificate_hash(certificate: BranchPruningCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchPruningCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_pruning_transfer_certificate_hash(
    certificate: BranchPruningTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchPruningTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchPruningTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchPruningTransferReport,
    transfer_certificate: BranchPruningTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_pruning_transfer_g1",
        claim_text=(
            "Rejected branches of the past can improve local target exploration by certifying pruning "
            "of known-dead candidates before the same verifier budget is spent."
        ),
        evidence_grade="G1",
        scope="branch_pruning_transfer",
        requirements=(
            requirement(
                "branch_pruning_transfer_certificate_valid",
                validate_branch_pruning_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_pruning_certificates_valid", report.all_branch_pruning_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("static_budget_fails_all_domains", report.static_budget_success_count == 0),
            requirement("pruned_budget_succeeds_all_domains", report.pruned_budget_success_count == report.domain_count),
            requirement("two_actions_pruned_per_domain", report.pruned_action_count == report.domain_count * 2),
            requirement("same_budget_all_domains", report.same_budget_pruning_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "pruned_action_count": report.pruned_action_count,
            "static_budget_success_count": report.static_budget_success_count,
            "pruned_budget_success_count": report.pruned_budget_success_count,
            "same_budget_pruning_count": report.same_budget_pruning_count,
        },
        boundary=BRANCH_PRUNING_CLAIM_BOUNDARY,
        sources=BRANCH_PRUNING_SOURCES,
    )


def _make_pruning_traces(
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
            actions=(dict(action),),
            seeds=("branch-pruning-transfer", spec.domain_id, context, phase, episode, action["action"]),
            model_version="branch.pruning.transfer.v1",
        )
        for action in actions
    )


def _with_context(action: Mapping[str, Any], context: str) -> dict[str, Any]:
    return {**dict(action), "context": context}


def _pruning_actions(spec: ExplorationDomainSpec) -> Mapping[str, Mapping[str, Any]]:
    bad_a = dict(spec.actions[0])
    safe_loser = dict(spec.actions[1])
    winner = dict(next(action for action in spec.actions if action.get("target_commit")))
    if spec.domain_id == "robotics_replan":
        bad_b = {
            "domain": spec.domain_id,
            "action": "aggressive_corner_cut",
            "utility": 9,
            "clearance": 0.10,
            "turn_rate": 0.85,
        }
    elif spec.domain_id == "molecule_repair":
        bad_b = {
            "domain": spec.domain_id,
            "action": "compressed_ring_patch",
            "utility": 9,
            "valence_ok": True,
            "strain": 0.60,
        }
    elif spec.domain_id == "material_process":
        bad_b = {
            "domain": spec.domain_id,
            "action": "thermal_spike_hold",
            "utility": 9,
            "thermal_gradient": 0.80,
            "phase_purity": 0.88,
        }
    else:
        raise ValueError(f"unknown domain: {spec.domain_id}")
    return {
        "bad_a": bad_a,
        "bad_b": bad_b,
        "winner": winner,
        "safe_loser": safe_loser,
    }


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_pruning_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
