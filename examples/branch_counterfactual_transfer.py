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


BRANCH_COUNTERFACTUAL_CERTIFICATE_SCHEMA = "trwm.branch_counterfactual_certificate.v1"
BRANCH_COUNTERFACTUAL_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_counterfactual_transfer_certificate.v1"
BRANCH_COUNTERFACTUAL_SOURCES = ANCESTRAL_BRANCH_SOURCES
BRANCH_COUNTERFACTUAL_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows accepted but rolled-back "
    "branch losers can become certified proposal evidence when a previously committed winner "
    "is stale in a target context. It is not counterfactual-regret optimization, off-policy "
    "evaluation, robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchCounterfactualCertificate:
    schema_version: str
    domain: str
    counterfactual_rule_id: str
    counterfactual_rule_version: str
    source_context_id: str
    target_context_id: str
    source_winner_action: str
    counterfactual_action: str
    stale_target_action: str
    source_receipt_hashes: tuple[str, ...]
    source_committed_receipt_hashes: tuple[str, ...]
    source_rolled_back_receipt_hashes: tuple[str, ...]
    stale_target_receipt_hashes: tuple[str, ...]
    counterfactual_target_receipt_hashes: tuple[str, ...]
    counterfactual_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    stale_branch_selection_certificate_hash: str
    counterfactual_branch_selection_certificate_hash: str
    stale_winner_committed: bool
    counterfactual_committed: bool
    source_has_rolled_back_counterfactual: bool
    stale_verifier_call_count: int
    counterfactual_verifier_call_count: int
    same_budget: bool
    counterfactual_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_COUNTERFACTUAL_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch counterfactual certificate schema: {self.schema_version}")
        for field_name in (
            "source_receipt_hashes",
            "source_committed_receipt_hashes",
            "source_rolled_back_receipt_hashes",
            "stale_target_receipt_hashes",
            "counterfactual_target_receipt_hashes",
            "counterfactual_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_counterfactual_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchCounterfactualDomainReport:
    domain: str
    source_context: str
    target_context: str
    source_winner_action: str
    counterfactual_action: str
    stale_target_action: str
    stale_winner_committed: bool
    counterfactual_committed: bool
    source_rolled_back_counterfactual_count: int
    stale_verifier_call_count: int
    counterfactual_verifier_call_count: int
    source_receipt_hashes: tuple[str, ...]
    source_committed_receipt_hashes: tuple[str, ...]
    source_rolled_back_receipt_hashes: tuple[str, ...]
    stale_target_receipt_hashes: tuple[str, ...]
    counterfactual_target_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    stale_branch_selection_certificate_hash: str
    counterfactual_branch_selection_certificate_hash: str
    counterfactual_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchCounterfactualTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchCounterfactualDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    stale_winner_success_count: int
    counterfactual_success_count: int
    rolled_back_counterfactual_count: int
    same_budget_comparison_count: int
    counterfactual_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_counterfactual_certificates_valid: bool
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
class BranchCounterfactualTransferCertificate:
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
    branch_counterfactual_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    stale_winner_success_count: int
    counterfactual_success_count: int
    rolled_back_counterfactual_count: int
    same_budget_comparison_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_COUNTERFACTUAL_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch counterfactual transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_counterfactual_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_counterfactual_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchCounterfactualTransferResult(CertifiedExampleResult):
    report: BranchCounterfactualTransferReport
    branch_counterfactual_transfer_certificate: BranchCounterfactualTransferCertificate
    branch_counterfactual_certificates: tuple[BranchCounterfactualCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_counterfactual_transfer_experiment() -> BranchCounterfactualTransferReport:
    return run_branch_counterfactual_transfer_certified_experiment().report


def run_branch_counterfactual_transfer_certified_experiment() -> CertifiedBranchCounterfactualTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[BranchCounterfactualDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    counterfactual_certificates: list[BranchCounterfactualCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:counterfactual"
        target_context = f"{spec.domain_id}:target:counterfactual"
        source_actions = _source_actions(spec, source_context)
        stale_action = _stale_winner_action(spec, target_context)
        counterfactual_action = _counterfactual_action(spec, target_context)

        source_outcome = runtime.step(
            state,
            _make_counterfactual_traces(spec, context=source_context, phase="source-counterfactual", actions=source_actions),
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
            _make_counterfactual_traces(spec, context=target_context, phase="target-stale-winner", actions=(stale_action,)),
        )
        stale_certificate = build_branch_selection_certificate(
            stale_outcome.receipts,
            verifier_call_count=stale_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(stale_outcome.receipts), stale_certificate))

        counterfactual_outcome = runtime.step(
            state,
            _make_counterfactual_traces(
                spec,
                context=target_context,
                phase="target-rolled-back-counterfactual",
                actions=(counterfactual_action,),
            ),
        )
        state = normalize_state(counterfactual_outcome.state)
        counterfactual_certificate = build_branch_selection_certificate(
            counterfactual_outcome.receipts,
            verifier_call_count=counterfactual_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(counterfactual_outcome.receipts), counterfactual_certificate))

        certificate = build_branch_counterfactual_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            source_winner_action=spec.committed_action,
            counterfactual_action=str(counterfactual_action["action"]),
            stale_target_action=str(stale_action["action"]),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
            source_committed_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed),
            source_rolled_back_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.commit_decision == "rolled_back_loser"
            ),
            stale_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in stale_outcome.receipts),
            counterfactual_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in counterfactual_outcome.receipts),
            counterfactual_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in counterfactual_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            stale_branch_selection_certificate_hash=stale_certificate.certificate_hash,
            counterfactual_branch_selection_certificate_hash=counterfactual_certificate.certificate_hash,
            stale_winner_committed=stale_outcome.committed,
            counterfactual_committed=counterfactual_outcome.committed,
            source_has_rolled_back_counterfactual=any(
                receipt.commit_decision == "rolled_back_loser"
                and str(receipt.replay_bundle["candidate_payload"]["action"]) == str(counterfactual_action["action"])
                for receipt in source_outcome.receipts
            ),
            stale_verifier_call_count=stale_outcome.verifier_calls,
            counterfactual_verifier_call_count=counterfactual_outcome.verifier_calls,
        )
        counterfactual_certificates.append(certificate)

        rows.append(
            BranchCounterfactualDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                source_winner_action=spec.committed_action,
                counterfactual_action=certificate.counterfactual_action,
                stale_target_action=certificate.stale_target_action,
                stale_winner_committed=stale_outcome.committed,
                counterfactual_committed=counterfactual_outcome.committed,
                source_rolled_back_counterfactual_count=len(certificate.source_rolled_back_receipt_hashes),
                stale_verifier_call_count=stale_outcome.verifier_calls,
                counterfactual_verifier_call_count=counterfactual_outcome.verifier_calls,
                source_receipt_hashes=certificate.source_receipt_hashes,
                source_committed_receipt_hashes=certificate.source_committed_receipt_hashes,
                source_rolled_back_receipt_hashes=certificate.source_rolled_back_receipt_hashes,
                stale_target_receipt_hashes=certificate.stale_target_receipt_hashes,
                counterfactual_target_receipt_hashes=certificate.counterfactual_target_receipt_hashes,
                source_branch_selection_certificate_hash=source_certificate.certificate_hash,
                stale_branch_selection_certificate_hash=stale_certificate.certificate_hash,
                counterfactual_branch_selection_certificate_hash=counterfactual_certificate.certificate_hash,
                counterfactual_certificate_hash=certificate.certificate_hash,
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

    report = BranchCounterfactualTransferReport(
        schema_version="trwm.example.branch_counterfactual_transfer.v1",
        experiment_id="branch_counterfactual_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        stale_winner_success_count=sum(1 for row in rows if row.stale_winner_committed),
        counterfactual_success_count=sum(1 for row in rows if row.counterfactual_committed),
        rolled_back_counterfactual_count=sum(row.source_rolled_back_counterfactual_count for row in rows),
        same_budget_comparison_count=sum(1 for row in rows if row.same_budget),
        counterfactual_certificate_count=len(counterfactual_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_counterfactual_certificates_valid=all(
            validate_branch_counterfactual_certificate(certificate) for certificate in counterfactual_certificates
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
        sources=BRANCH_COUNTERFACTUAL_SOURCES,
        learning=(
            "Accepted-but-rolled-back branch losers are useful counterfactual evidence: when the old "
            "winner becomes stale, the target can try the previously valid loser under the same one-call "
            "budget, but it still commits only through the hard verifier."
        ),
    )
    transfer_certificate = build_branch_counterfactual_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_counterfactual_certificate_hashes=tuple(certificate.certificate_hash for certificate in counterfactual_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_counterfactual_transfer",
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
        claim_boundary=BRANCH_COUNTERFACTUAL_CLAIM_BOUNDARY,
        sources=BRANCH_COUNTERFACTUAL_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchCounterfactualTransferResult(
        report=report,
        branch_counterfactual_transfer_certificate=transfer_certificate,
        branch_counterfactual_certificates=tuple(counterfactual_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_counterfactual_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    source_winner_action: str,
    counterfactual_action: str,
    stale_target_action: str,
    source_receipt_hashes: tuple[str, ...],
    source_committed_receipt_hashes: tuple[str, ...],
    source_rolled_back_receipt_hashes: tuple[str, ...],
    stale_target_receipt_hashes: tuple[str, ...],
    counterfactual_target_receipt_hashes: tuple[str, ...],
    counterfactual_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    stale_branch_selection_certificate_hash: str,
    counterfactual_branch_selection_certificate_hash: str,
    stale_winner_committed: bool,
    counterfactual_committed: bool,
    source_has_rolled_back_counterfactual: bool,
    stale_verifier_call_count: int,
    counterfactual_verifier_call_count: int,
) -> BranchCounterfactualCertificate:
    return BranchCounterfactualCertificate(
        schema_version=BRANCH_COUNTERFACTUAL_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        counterfactual_rule_id="accepted_loser_counterfactual_reuse",
        counterfactual_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        source_winner_action=source_winner_action,
        counterfactual_action=counterfactual_action,
        stale_target_action=stale_target_action,
        source_receipt_hashes=source_receipt_hashes,
        source_committed_receipt_hashes=source_committed_receipt_hashes,
        source_rolled_back_receipt_hashes=source_rolled_back_receipt_hashes,
        stale_target_receipt_hashes=stale_target_receipt_hashes,
        counterfactual_target_receipt_hashes=counterfactual_target_receipt_hashes,
        counterfactual_target_commit_receipt_hashes=counterfactual_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        stale_branch_selection_certificate_hash=stale_branch_selection_certificate_hash,
        counterfactual_branch_selection_certificate_hash=counterfactual_branch_selection_certificate_hash,
        stale_winner_committed=stale_winner_committed,
        counterfactual_committed=counterfactual_committed,
        source_has_rolled_back_counterfactual=source_has_rolled_back_counterfactual,
        stale_verifier_call_count=stale_verifier_call_count,
        counterfactual_verifier_call_count=counterfactual_verifier_call_count,
        same_budget=stale_verifier_call_count == counterfactual_verifier_call_count == 1,
        counterfactual_reason="accepted_rolled_back_loser_beats_stale_prior_winner",
    )


def validate_branch_counterfactual_certificate(
    certificate: BranchCounterfactualCertificate,
    row: BranchCounterfactualDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_COUNTERFACTUAL_CERTIFICATE_SCHEMA:
            return False
        if certificate.counterfactual_rule_id != "accepted_loser_counterfactual_reuse":
            return False
        if certificate.counterfactual_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id):
            return False
        if not _nonempty(certificate.source_winner_action) or not _nonempty(certificate.counterfactual_action):
            return False
        if certificate.counterfactual_action == certificate.source_winner_action:
            return False
        if certificate.stale_target_action != certificate.source_winner_action:
            return False
        if len(certificate.source_receipt_hashes) != 3:
            return False
        if len(certificate.source_committed_receipt_hashes) != 1:
            return False
        if len(certificate.source_rolled_back_receipt_hashes) != 1:
            return False
        if len(certificate.stale_target_receipt_hashes) != 1:
            return False
        if len(certificate.counterfactual_target_receipt_hashes) != 1:
            return False
        if len(certificate.counterfactual_target_commit_receipt_hashes) != 1:
            return False
        if certificate.stale_winner_committed or not certificate.counterfactual_committed:
            return False
        if not certificate.source_has_rolled_back_counterfactual:
            return False
        if certificate.stale_verifier_call_count != 1 or certificate.counterfactual_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.counterfactual_reason != "accepted_rolled_back_loser_beats_stale_prior_winner":
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_committed_receipt_hashes,
            certificate.source_rolled_back_receipt_hashes,
            certificate.stale_target_receipt_hashes,
            certificate.counterfactual_target_receipt_hashes,
            certificate.counterfactual_target_commit_receipt_hashes,
            (
                certificate.source_branch_selection_certificate_hash,
                certificate.stale_branch_selection_certificate_hash,
                certificate.counterfactual_branch_selection_certificate_hash,
            ),
        ):
            if any(not _is_hash(value) for value in values):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.source_winner_action != certificate.source_winner_action:
                return False
            if row.counterfactual_action != certificate.counterfactual_action:
                return False
            if row.stale_target_action != certificate.stale_target_action:
                return False
            if row.stale_winner_committed != certificate.stale_winner_committed:
                return False
            if row.counterfactual_committed != certificate.counterfactual_committed:
                return False
            if row.source_rolled_back_counterfactual_count != len(certificate.source_rolled_back_receipt_hashes):
                return False
            if row.counterfactual_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_counterfactual_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_counterfactual_transfer_certificate(
    report: BranchCounterfactualTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_counterfactual_certificate_hashes: tuple[str, ...],
) -> BranchCounterfactualTransferCertificate:
    return BranchCounterfactualTransferCertificate(
        schema_version=BRANCH_COUNTERFACTUAL_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_counterfactual_certificate_hashes=branch_counterfactual_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        stale_winner_success_count=report.stale_winner_success_count,
        counterfactual_success_count=report.counterfactual_success_count,
        rolled_back_counterfactual_count=report.rolled_back_counterfactual_count,
        same_budget_comparison_count=report.same_budget_comparison_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_COUNTERFACTUAL_CLAIM_BOUNDARY,
    )


def validate_branch_counterfactual_transfer_certificate(
    certificate: BranchCounterfactualTransferCertificate,
    report: BranchCounterfactualTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_COUNTERFACTUAL_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_counterfactual_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_counterfactual_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.stale_winner_success_count != 0:
            return False
        if certificate.counterfactual_success_count != certificate.domain_count:
            return False
        if certificate.rolled_back_counterfactual_count != certificate.domain_count:
            return False
        if certificate.same_budget_comparison_count != certificate.domain_count:
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
            if not report.all_counterfactual_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.rolled_back_counterfactual_count != certificate.rolled_back_counterfactual_count:
                return False
        return certificate.certificate_hash == branch_counterfactual_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_counterfactual_certificate_hash(certificate: BranchCounterfactualCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchCounterfactualCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_counterfactual_transfer_certificate_hash(
    certificate: BranchCounterfactualTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCounterfactualTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchCounterfactualTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchCounterfactualTransferReport,
    transfer_certificate: BranchCounterfactualTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_counterfactual_transfer_g1",
        claim_text=(
            "Accepted-but-rolled-back past branch losers can improve local target exploration when "
            "a previously committed winner is stale, under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_counterfactual_transfer",
        requirements=(
            requirement(
                "branch_counterfactual_transfer_certificate_valid",
                validate_branch_counterfactual_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_counterfactual_certificates_valid", report.all_counterfactual_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("stale_winner_fails_all_domains", report.stale_winner_success_count == 0),
            requirement("counterfactual_succeeds_all_domains", report.counterfactual_success_count == report.domain_count),
            requirement("rolled_back_counterfactuals_present", report.rolled_back_counterfactual_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_comparison_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "total_rolled_back_loser_count": report.total_rolled_back_loser_count,
            "stale_winner_success_count": report.stale_winner_success_count,
            "counterfactual_success_count": report.counterfactual_success_count,
            "rolled_back_counterfactual_count": report.rolled_back_counterfactual_count,
        },
        boundary=BRANCH_COUNTERFACTUAL_CLAIM_BOUNDARY,
        sources=BRANCH_COUNTERFACTUAL_SOURCES,
    )


def _make_counterfactual_traces(
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
            seeds=("branch-counterfactual-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.counterfactual.transfer.v1",
        )
        for action in actions
    )


def _source_actions(spec: ExplorationDomainSpec, context: str) -> tuple[Mapping[str, Any], ...]:
    reject = {**dict(spec.actions[0]), "context": context}
    winner = {**dict(next(action for action in spec.actions if action.get("target_commit"))), "context": context}
    counterfactual = {**dict(spec.actions[1]), "context": context}
    return (reject, winner, counterfactual)


def _counterfactual_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    return {**dict(spec.actions[1]), "context": context}


def _stale_winner_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": spec.committed_action,
            "utility": 10,
            "clearance": 0.12,
            "turn_rate": 0.72,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": spec.committed_action,
            "utility": 10,
            "valence_ok": False,
            "strain": 0.44,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": spec.committed_action,
            "utility": 10,
            "thermal_gradient": 0.66,
            "phase_purity": 0.86,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_counterfactual_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
