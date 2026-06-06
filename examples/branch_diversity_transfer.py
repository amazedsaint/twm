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


BRANCH_DIVERSITY_CERTIFICATE_SCHEMA = "trwm.branch_diversity_certificate.v1"
BRANCH_DIVERSITY_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_diversity_transfer_certificate.v1"
BRANCH_DIVERSITY_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://pubmed.ncbi.nlm.nih.gov/20868264/",
    "https://arxiv.org/abs/1504.04909",
)
BRANCH_DIVERSITY_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows same-family rejected branch "
    "receipts can certify a diversity policy that avoids repeated failure-family budget spend and "
    "covers a distinct candidate family under the same verifier budget. It is not novelty-search "
    "performance evidence, MAP-Elites, quality-diversity optimization, a planning algorithm, robotics "
    "safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchDiversityCertificate:
    schema_version: str
    domain: str
    diversity_rule_id: str
    diversity_rule_version: str
    source_context_id: str
    target_context_id: str
    saturated_family_id: str
    candidate_actions: tuple[str, ...]
    candidate_family_ids: tuple[str, ...]
    baseline_actions: tuple[str, ...]
    baseline_family_ids: tuple[str, ...]
    diverse_actions: tuple[str, ...]
    diverse_family_ids: tuple[str, ...]
    committed_target_action: str
    source_receipt_hashes: tuple[str, ...]
    source_reject_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    diverse_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    diverse_branch_selection_certificate_hash: str
    static_committed: bool
    diverse_committed: bool
    static_verifier_call_count: int
    diverse_verifier_call_count: int
    same_budget: bool
    diversity_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_DIVERSITY_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch diversity certificate schema: {self.schema_version}")
        for field_name in (
            "candidate_actions",
            "candidate_family_ids",
            "baseline_actions",
            "baseline_family_ids",
            "diverse_actions",
            "diverse_family_ids",
            "source_receipt_hashes",
            "source_reject_receipt_hashes",
            "source_commit_receipt_hashes",
            "static_receipt_hashes",
            "diverse_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_diversity_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchDiversityDomainReport:
    domain: str
    source_context: str
    target_context: str
    saturated_family_id: str
    candidate_actions: tuple[str, ...]
    candidate_family_ids: tuple[str, ...]
    baseline_actions: tuple[str, ...]
    baseline_family_ids: tuple[str, ...]
    diverse_actions: tuple[str, ...]
    diverse_family_ids: tuple[str, ...]
    committed_target_action: str
    static_budget_committed: bool
    diverse_budget_committed: bool
    source_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    diverse_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    diverse_branch_selection_certificate_hash: str
    diversity_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchDiversityTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchDiversityDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    saturated_family_count: int
    diverse_family_count: int
    static_budget_success_count: int
    diverse_budget_success_count: int
    same_budget_diversity_count: int
    branch_diversity_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_diversity_certificates_valid: bool
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
class BranchDiversityTransferCertificate:
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
    branch_diversity_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    saturated_family_count: int
    diverse_family_count: int
    static_budget_success_count: int
    diverse_budget_success_count: int
    same_budget_diversity_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_DIVERSITY_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch diversity transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_diversity_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_diversity_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchDiversityTransferResult(CertifiedExampleResult):
    report: BranchDiversityTransferReport
    branch_diversity_transfer_certificate: BranchDiversityTransferCertificate
    branch_diversity_certificates: tuple[BranchDiversityCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_diversity_transfer_experiment() -> BranchDiversityTransferReport:
    return run_branch_diversity_transfer_certified_experiment().report


def run_branch_diversity_transfer_certified_experiment() -> CertifiedBranchDiversityTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[BranchDiversityDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    diversity_certificates: list[BranchDiversityCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:diversity"
        target_context = f"{spec.domain_id}:target:diversity"
        action_map = _diversity_actions(spec)
        candidate_actions = (
            action_map["same_a"],
            action_map["same_b"],
            action_map["alternate"],
            action_map["winner"],
        )
        family_by_action = {str(action["action"]): str(action["family_id"]) for action in candidate_actions}
        source_outcome = runtime.step(
            state,
            _make_diversity_traces(
                spec,
                context=source_context,
                phase="source-diversity-evidence",
                episode=0,
                actions=(
                    _with_context(action_map["same_a"], source_context),
                    _with_context(action_map["same_b"], source_context),
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
            _make_diversity_traces(
                spec,
                context=target_context,
                phase="target-static-repeated-family-budget-two",
                episode=0,
                actions=(
                    _with_context(action_map["same_a"], target_context),
                    _with_context(action_map["same_b"], target_context),
                ),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        diverse_outcome = runtime.step(
            state,
            _make_diversity_traces(
                spec,
                context=target_context,
                phase="target-diverse-budget-two",
                episode=0,
                actions=(
                    _with_context(action_map["alternate"], target_context),
                    _with_context(action_map["winner"], target_context),
                ),
            ),
        )
        state = normalize_state(diverse_outcome.state)
        diverse_certificate = build_branch_selection_certificate(
            diverse_outcome.receipts,
            verifier_call_count=diverse_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(diverse_outcome.receipts), diverse_certificate))

        baseline_actions = (str(action_map["same_a"]["action"]), str(action_map["same_b"]["action"]))
        diverse_actions = (str(action_map["alternate"]["action"]), str(action_map["winner"]["action"]))
        diversity_certificate = build_branch_diversity_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            saturated_family_id=str(action_map["same_a"]["family_id"]),
            candidate_actions=tuple(str(action["action"]) for action in candidate_actions),
            candidate_family_ids=tuple(family_by_action[str(action["action"])] for action in candidate_actions),
            baseline_actions=baseline_actions,
            baseline_family_ids=tuple(family_by_action[action] for action in baseline_actions),
            diverse_actions=diverse_actions,
            diverse_family_ids=tuple(family_by_action[action] for action in diverse_actions),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
            source_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
            source_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed),
            static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            diverse_receipt_hashes=tuple(receipt.receipt_hash for receipt in diverse_outcome.receipts),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            diverse_branch_selection_certificate_hash=diverse_certificate.certificate_hash,
            static_committed=static_outcome.committed,
            diverse_committed=diverse_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            diverse_verifier_call_count=diverse_outcome.verifier_calls,
        )
        diversity_certificates.append(diversity_certificate)

        rows.append(
            BranchDiversityDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                saturated_family_id=diversity_certificate.saturated_family_id,
                candidate_actions=diversity_certificate.candidate_actions,
                candidate_family_ids=diversity_certificate.candidate_family_ids,
                baseline_actions=diversity_certificate.baseline_actions,
                baseline_family_ids=diversity_certificate.baseline_family_ids,
                diverse_actions=diversity_certificate.diverse_actions,
                diverse_family_ids=diversity_certificate.diverse_family_ids,
                committed_target_action=spec.committed_action,
                static_budget_committed=static_outcome.committed,
                diverse_budget_committed=diverse_outcome.committed,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
                static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
                diverse_receipt_hashes=tuple(receipt.receipt_hash for receipt in diverse_outcome.receipts),
                source_branch_selection_certificate_hash=source_certificate.certificate_hash,
                static_branch_selection_certificate_hash=static_certificate.certificate_hash,
                diverse_branch_selection_certificate_hash=diverse_certificate.certificate_hash,
                diversity_certificate_hash=diversity_certificate.certificate_hash,
                same_budget=diversity_certificate.same_budget,
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
    report = BranchDiversityTransferReport(
        schema_version="trwm.example.branch_diversity_transfer.v1",
        experiment_id="branch_diversity_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        saturated_family_count=sum(1 for row in rows if len(set(row.baseline_family_ids)) == 1),
        diverse_family_count=sum(1 for row in rows if len(set(row.diverse_family_ids)) == len(row.diverse_family_ids)),
        static_budget_success_count=sum(1 for row in rows if row.static_budget_committed),
        diverse_budget_success_count=sum(1 for row in rows if row.diverse_budget_committed),
        same_budget_diversity_count=sum(1 for row in rows if row.same_budget),
        branch_diversity_certificate_count=len(diversity_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_diversity_certificates_valid=all(
            validate_branch_diversity_certificate(certificate) for certificate in diversity_certificates
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
        sources=BRANCH_DIVERSITY_SOURCES,
        learning=(
            "Past branch failures can improve exploration by certifying coverage pressure. Repeating "
            "one saturated failure family spends the same verifier budget without a commit; a "
            "diversity-certified selection covers a distinct family and reaches a verified repair."
        ),
    )
    transfer_certificate = build_branch_diversity_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_diversity_certificate_hashes=tuple(certificate.certificate_hash for certificate in diversity_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_diversity_transfer",
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
        claim_boundary=BRANCH_DIVERSITY_CLAIM_BOUNDARY,
        sources=BRANCH_DIVERSITY_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchDiversityTransferResult(
        report=report,
        branch_diversity_transfer_certificate=transfer_certificate,
        branch_diversity_certificates=tuple(diversity_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_diversity_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    saturated_family_id: str,
    candidate_actions: tuple[str, ...],
    candidate_family_ids: tuple[str, ...],
    baseline_actions: tuple[str, ...],
    baseline_family_ids: tuple[str, ...],
    diverse_actions: tuple[str, ...],
    diverse_family_ids: tuple[str, ...],
    source_receipt_hashes: tuple[str, ...],
    source_reject_receipt_hashes: tuple[str, ...],
    source_commit_receipt_hashes: tuple[str, ...],
    static_receipt_hashes: tuple[str, ...],
    diverse_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    diverse_branch_selection_certificate_hash: str,
    static_committed: bool,
    diverse_committed: bool,
    static_verifier_call_count: int,
    diverse_verifier_call_count: int,
) -> BranchDiversityCertificate:
    return BranchDiversityCertificate(
        schema_version=BRANCH_DIVERSITY_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        diversity_rule_id="receipt_bound_family_coverage",
        diversity_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        saturated_family_id=saturated_family_id,
        candidate_actions=candidate_actions,
        candidate_family_ids=candidate_family_ids,
        baseline_actions=baseline_actions,
        baseline_family_ids=baseline_family_ids,
        diverse_actions=diverse_actions,
        diverse_family_ids=diverse_family_ids,
        committed_target_action=spec.committed_action,
        source_receipt_hashes=source_receipt_hashes,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        static_receipt_hashes=static_receipt_hashes,
        diverse_receipt_hashes=diverse_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        diverse_branch_selection_certificate_hash=diverse_branch_selection_certificate_hash,
        static_committed=static_committed,
        diverse_committed=diverse_committed,
        static_verifier_call_count=static_verifier_call_count,
        diverse_verifier_call_count=diverse_verifier_call_count,
        same_budget=static_verifier_call_count == diverse_verifier_call_count == 2,
        diversity_reason="avoid_repeated_saturated_failure_family",
    )


def validate_branch_diversity_certificate(
    certificate: BranchDiversityCertificate,
    row: BranchDiversityDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_DIVERSITY_CERTIFICATE_SCHEMA:
            return False
        if certificate.diversity_rule_id != "receipt_bound_family_coverage" or certificate.diversity_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.saturated_family_id):
            return False
        if len(certificate.candidate_actions) != 4 or len(certificate.candidate_family_ids) != 4:
            return False
        if len(certificate.baseline_actions) != 2 or len(certificate.baseline_family_ids) != 2:
            return False
        if len(certificate.diverse_actions) != 2 or len(certificate.diverse_family_ids) != 2:
            return False
        if len(set(certificate.baseline_family_ids)) != 1:
            return False
        if certificate.baseline_family_ids[0] != certificate.saturated_family_id:
            return False
        if len(set(certificate.diverse_family_ids)) != 2:
            return False
        if certificate.saturated_family_id in certificate.diverse_family_ids:
            return False
        if certificate.committed_target_action != certificate.diverse_actions[-1]:
            return False
        if certificate.static_committed or not certificate.diverse_committed:
            return False
        if not certificate.same_budget or certificate.static_verifier_call_count != 2 or certificate.diverse_verifier_call_count != 2:
            return False
        if len(certificate.source_receipt_hashes) != 3:
            return False
        if len(certificate.source_reject_receipt_hashes) != 2 or len(certificate.source_commit_receipt_hashes) != 1:
            return False
        if len(certificate.static_receipt_hashes) != 2 or len(certificate.diverse_receipt_hashes) != 2:
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_reject_receipt_hashes,
            certificate.source_commit_receipt_hashes,
            certificate.static_receipt_hashes,
            certificate.diverse_receipt_hashes,
            (
                certificate.source_branch_selection_certificate_hash,
                certificate.static_branch_selection_certificate_hash,
                certificate.diverse_branch_selection_certificate_hash,
            ),
        ):
            if any(not _is_hash(value) for value in values):
                return False
        if certificate.diversity_reason != "avoid_repeated_saturated_failure_family":
            return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.saturated_family_id != certificate.saturated_family_id:
                return False
            if row.candidate_actions != certificate.candidate_actions:
                return False
            if row.candidate_family_ids != certificate.candidate_family_ids:
                return False
            if row.baseline_actions != certificate.baseline_actions or row.baseline_family_ids != certificate.baseline_family_ids:
                return False
            if row.diverse_actions != certificate.diverse_actions or row.diverse_family_ids != certificate.diverse_family_ids:
                return False
            if row.static_budget_committed != certificate.static_committed:
                return False
            if row.diverse_budget_committed != certificate.diverse_committed:
                return False
            if row.diversity_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_diversity_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_diversity_transfer_certificate(
    report: BranchDiversityTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_diversity_certificate_hashes: tuple[str, ...],
) -> BranchDiversityTransferCertificate:
    return BranchDiversityTransferCertificate(
        schema_version=BRANCH_DIVERSITY_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_diversity_certificate_hashes=branch_diversity_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        saturated_family_count=report.saturated_family_count,
        diverse_family_count=report.diverse_family_count,
        static_budget_success_count=report.static_budget_success_count,
        diverse_budget_success_count=report.diverse_budget_success_count,
        same_budget_diversity_count=report.same_budget_diversity_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_DIVERSITY_CLAIM_BOUNDARY,
    )


def validate_branch_diversity_transfer_certificate(
    certificate: BranchDiversityTransferCertificate,
    report: BranchDiversityTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_DIVERSITY_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_diversity_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 7:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_diversity_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.saturated_family_count != certificate.domain_count:
            return False
        if certificate.diverse_family_count != certificate.domain_count:
            return False
        if certificate.static_budget_success_count != 0:
            return False
        if certificate.diverse_budget_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_diversity_count != certificate.domain_count:
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
            if not report.all_branch_diversity_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.saturated_family_count != certificate.saturated_family_count:
                return False
            if report.diverse_family_count != certificate.diverse_family_count:
                return False
            if report.static_budget_success_count != certificate.static_budget_success_count:
                return False
            if report.diverse_budget_success_count != certificate.diverse_budget_success_count:
                return False
        return certificate.certificate_hash == branch_diversity_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_diversity_certificate_hash(certificate: BranchDiversityCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchDiversityCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_diversity_transfer_certificate_hash(
    certificate: BranchDiversityTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchDiversityTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchDiversityTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchDiversityTransferReport,
    transfer_certificate: BranchDiversityTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_diversity_transfer_g1",
        claim_text=(
            "Same-family rejected branches of the past can improve local target exploration by certifying "
            "a diversity policy that covers distinct candidate families under the same verifier budget."
        ),
        evidence_grade="G1",
        scope="branch_diversity_transfer",
        requirements=(
            requirement(
                "branch_diversity_transfer_certificate_valid",
                validate_branch_diversity_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_diversity_certificates_valid", report.all_branch_diversity_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("static_budget_fails_all_domains", report.static_budget_success_count == 0),
            requirement("diverse_budget_succeeds_all_domains", report.diverse_budget_success_count == report.domain_count),
            requirement("baseline_repeats_saturated_family", report.saturated_family_count == report.domain_count),
            requirement("diverse_selection_covers_distinct_families", report.diverse_family_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_diversity_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "saturated_family_count": report.saturated_family_count,
            "diverse_family_count": report.diverse_family_count,
            "static_budget_success_count": report.static_budget_success_count,
            "diverse_budget_success_count": report.diverse_budget_success_count,
            "same_budget_diversity_count": report.same_budget_diversity_count,
        },
        boundary=BRANCH_DIVERSITY_CLAIM_BOUNDARY,
        sources=BRANCH_DIVERSITY_SOURCES,
    )


def _make_diversity_traces(
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
            seeds=("branch-diversity-transfer", spec.domain_id, context, phase, episode, action["action"]),
            model_version="branch.diversity.transfer.v1",
        )
        for action in actions
    )


def _with_context(action: Mapping[str, Any], context: str) -> dict[str, Any]:
    return {**dict(action), "context": context}


def _diversity_actions(spec: ExplorationDomainSpec) -> Mapping[str, Mapping[str, Any]]:
    winner = dict(next(action for action in spec.actions if action.get("target_commit")))
    if spec.domain_id == "robotics_replan":
        same_a = {
            "domain": spec.domain_id,
            "action": "low_clearance_cut",
            "utility": 10,
            "clearance": 0.04,
            "turn_rate": 0.40,
            "family_id": "clearance_violation",
        }
        same_b = {
            "domain": spec.domain_id,
            "action": "narrow_passage_retry",
            "utility": 9,
            "clearance": 0.06,
            "turn_rate": 0.45,
            "family_id": "clearance_violation",
        }
        alternate = {
            "domain": spec.domain_id,
            "action": "high_turn_probe",
            "utility": 8,
            "clearance": 0.33,
            "turn_rate": 0.95,
            "family_id": "turn_rate_violation",
        }
        family = "safe_repair"
    elif spec.domain_id == "molecule_repair":
        same_a = {
            "domain": spec.domain_id,
            "action": "open_valence_patch",
            "utility": 10,
            "valence_ok": False,
            "strain": 0.20,
            "family_id": "valence_violation",
        }
        same_b = {
            "domain": spec.domain_id,
            "action": "valence_retry_patch",
            "utility": 9,
            "valence_ok": False,
            "strain": 0.18,
            "family_id": "valence_violation",
        }
        alternate = {
            "domain": spec.domain_id,
            "action": "strain_spike_probe",
            "utility": 8,
            "valence_ok": True,
            "strain": 0.60,
            "family_id": "strain_violation",
        }
        family = "safe_repair"
    elif spec.domain_id == "material_process":
        same_a = {
            "domain": spec.domain_id,
            "action": "low_purity_quench",
            "utility": 10,
            "thermal_gradient": 0.35,
            "phase_purity": 0.80,
            "family_id": "phase_purity_violation",
        }
        same_b = {
            "domain": spec.domain_id,
            "action": "low_purity_retry",
            "utility": 9,
            "thermal_gradient": 0.40,
            "phase_purity": 0.84,
            "family_id": "phase_purity_violation",
        }
        alternate = {
            "domain": spec.domain_id,
            "action": "thermal_gradient_probe",
            "utility": 8,
            "thermal_gradient": 0.85,
            "phase_purity": 0.95,
            "family_id": "thermal_gradient_violation",
        }
        family = "safe_repair"
    else:
        raise ValueError(f"unknown domain: {spec.domain_id}")
    winner = {**winner, "family_id": family}
    return {
        "same_a": same_a,
        "same_b": same_b,
        "alternate": alternate,
        "winner": winner,
    }


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_diversity_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
