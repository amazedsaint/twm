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
    BranchRuntime,
    BranchSelectionCertificate,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


BRANCH_CONSENSUS_CERTIFICATE_SCHEMA = "trwm.branch_consensus_certificate.v1"
BRANCH_CONSENSUS_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_consensus_transfer_certificate.v1"
BRANCH_CONSENSUS_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1145/130385.130417",
)
BRANCH_CONSENSUS_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows multiple source branch receipts can "
    "identify a majority-supported target proposal family under a matched one-call verifier budget, but "
    "the consensus target candidate still commits only through fresh hard verification. It is not "
    "query-by-committee, ensemble learning, statistical active learning, robotics safety, chemistry, "
    "materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchConsensusCertificate:
    schema_version: str
    domain: str
    consensus_rule_id: str
    consensus_rule_version: str
    source_context_ids: tuple[str, ...]
    target_context_id: str
    selected_family_id: str
    singleton_family_id: str
    majority_support_count: int
    singleton_support_count: int
    required_support_count: int
    source_majority_actions: tuple[str, ...]
    source_singleton_actions: tuple[str, ...]
    static_target_action: str
    consensus_target_action: str
    source_majority_receipt_hashes: tuple[str, ...]
    source_singleton_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    consensus_target_receipt_hashes: tuple[str, ...]
    consensus_target_commit_receipt_hashes: tuple[str, ...]
    source_majority_branch_selection_certificate_hashes: tuple[str, ...]
    source_singleton_branch_selection_certificate_hashes: tuple[str, ...]
    static_branch_selection_certificate_hash: str
    consensus_branch_selection_certificate_hash: str
    source_majority_committed_count: int
    source_singleton_committed_count: int
    static_committed: bool
    consensus_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    consensus_verifier_call_count: int
    same_budget: bool
    consensus_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONSENSUS_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch consensus certificate schema: {self.schema_version}")
        for field_name in (
            "source_context_ids",
            "source_majority_actions",
            "source_singleton_actions",
            "source_majority_receipt_hashes",
            "source_singleton_receipt_hashes",
            "static_target_receipt_hashes",
            "consensus_target_receipt_hashes",
            "consensus_target_commit_receipt_hashes",
            "source_majority_branch_selection_certificate_hashes",
            "source_singleton_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_consensus_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchConsensusDomainReport:
    domain: str
    source_contexts: tuple[str, ...]
    target_context: str
    selected_family_id: str
    singleton_family_id: str
    majority_support_count: int
    singleton_support_count: int
    required_support_count: int
    source_majority_actions: tuple[str, ...]
    source_singleton_actions: tuple[str, ...]
    static_target_action: str
    consensus_target_action: str
    source_majority_committed_count: int
    source_singleton_committed_count: int
    static_committed: bool
    consensus_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    consensus_verifier_call_count: int
    source_majority_receipt_hashes: tuple[str, ...]
    source_singleton_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    consensus_target_receipt_hashes: tuple[str, ...]
    branch_consensus_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchConsensusTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchConsensusDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_majority_success_count: int
    source_singleton_success_count: int
    static_success_count: int
    consensus_success_count: int
    same_budget_consensus_count: int
    branch_consensus_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_consensus_certificates_valid: bool
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
class BranchConsensusTransferCertificate:
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
    branch_consensus_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_majority_success_count: int
    source_singleton_success_count: int
    static_success_count: int
    consensus_success_count: int
    same_budget_consensus_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONSENSUS_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch consensus transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_consensus_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_consensus_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchConsensusTransferResult(CertifiedExampleResult):
    report: BranchConsensusTransferReport
    branch_consensus_transfer_certificate: BranchConsensusTransferCertificate
    branch_consensus_certificates: tuple[BranchConsensusCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_consensus_transfer_experiment() -> BranchConsensusTransferReport:
    return run_branch_consensus_transfer_certified_experiment().report


def run_branch_consensus_transfer_certified_experiment() -> CertifiedBranchConsensusTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchConsensusDomainReport] = []
    consensus_certificates: list[BranchConsensusCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_contexts = (
            f"{spec.domain_id}:source:consensus:majority_a",
            f"{spec.domain_id}:source:consensus:majority_b",
            f"{spec.domain_id}:source:consensus:singleton",
        )
        target_context = f"{spec.domain_id}:target:consensus"
        plan = _domain_consensus_plan(spec, source_contexts, target_context)

        source_outcomes = []
        source_certificates = []
        for source_context, source_action in zip(source_contexts, plan["source_actions"]):
            outcome = runtime.step(
                state,
                _make_consensus_traces(
                    spec,
                    context=source_context,
                    phase="source-consensus",
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
            _make_consensus_traces(
                spec,
                context=target_context,
                phase="target-static",
                actions=(plan["target_static"],),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        consensus_outcome = runtime.step(
            state,
            _make_consensus_traces(
                spec,
                context=target_context,
                phase="target-consensus",
                actions=(plan["target_consensus"],),
            ),
        )
        state = normalize_state(consensus_outcome.state)
        consensus_selection_certificate = build_branch_selection_certificate(
            consensus_outcome.receipts,
            verifier_call_count=consensus_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(consensus_outcome.receipts), consensus_selection_certificate))

        majority_outcomes = tuple(source_outcomes[:2])
        singleton_outcomes = tuple(source_outcomes[2:])
        majority_certificates = tuple(source_certificates[:2])
        singleton_certificates = tuple(source_certificates[2:])
        source_majority_hashes = tuple(receipt.receipt_hash for outcome in majority_outcomes for receipt in outcome.receipts if receipt.committed)
        source_singleton_hashes = tuple(receipt.receipt_hash for outcome in singleton_outcomes for receipt in outcome.receipts if receipt.committed)
        static_hashes = tuple(receipt.receipt_hash for receipt in static_outcome.receipts)
        consensus_hashes = tuple(receipt.receipt_hash for receipt in consensus_outcome.receipts)
        consensus_commit_hashes = tuple(receipt.receipt_hash for receipt in consensus_outcome.receipts if receipt.committed)

        certificate = build_branch_consensus_certificate(
            spec,
            source_context_ids=source_contexts,
            target_context_id=target_context,
            selected_family_id=str(plan["selected_family_id"]),
            singleton_family_id=str(plan["singleton_family_id"]),
            source_majority_actions=tuple(str(action["action"]) for action in plan["source_actions"][:2]),
            source_singleton_actions=tuple(str(action["action"]) for action in plan["source_actions"][2:]),
            static_target_action=str(plan["target_static"]["action"]),
            consensus_target_action=str(plan["target_consensus"]["action"]),
            source_majority_receipt_hashes=source_majority_hashes,
            source_singleton_receipt_hashes=source_singleton_hashes,
            static_target_receipt_hashes=static_hashes,
            consensus_target_receipt_hashes=consensus_hashes,
            consensus_target_commit_receipt_hashes=consensus_commit_hashes,
            source_majority_branch_selection_certificate_hashes=tuple(c.certificate_hash for c in majority_certificates),
            source_singleton_branch_selection_certificate_hashes=tuple(c.certificate_hash for c in singleton_certificates),
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            consensus_branch_selection_certificate_hash=consensus_selection_certificate.certificate_hash,
            source_majority_committed_count=sum(1 for outcome in majority_outcomes if outcome.committed),
            source_singleton_committed_count=sum(1 for outcome in singleton_outcomes if outcome.committed),
            static_committed=static_outcome.committed,
            consensus_committed=consensus_outcome.committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in source_outcomes),
            static_verifier_call_count=static_outcome.verifier_calls,
            consensus_verifier_call_count=consensus_outcome.verifier_calls,
        )
        consensus_certificates.append(certificate)
        rows.append(
            BranchConsensusDomainReport(
                domain=spec.domain_id,
                source_contexts=certificate.source_context_ids,
                target_context=certificate.target_context_id,
                selected_family_id=certificate.selected_family_id,
                singleton_family_id=certificate.singleton_family_id,
                majority_support_count=certificate.majority_support_count,
                singleton_support_count=certificate.singleton_support_count,
                required_support_count=certificate.required_support_count,
                source_majority_actions=certificate.source_majority_actions,
                source_singleton_actions=certificate.source_singleton_actions,
                static_target_action=certificate.static_target_action,
                consensus_target_action=certificate.consensus_target_action,
                source_majority_committed_count=certificate.source_majority_committed_count,
                source_singleton_committed_count=certificate.source_singleton_committed_count,
                static_committed=certificate.static_committed,
                consensus_committed=certificate.consensus_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                consensus_verifier_call_count=certificate.consensus_verifier_call_count,
                source_majority_receipt_hashes=certificate.source_majority_receipt_hashes,
                source_singleton_receipt_hashes=certificate.source_singleton_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                consensus_target_receipt_hashes=certificate.consensus_target_receipt_hashes,
                branch_consensus_certificate_hash=certificate.certificate_hash,
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

    report = BranchConsensusTransferReport(
        schema_version="trwm.example.branch_consensus_transfer.v1",
        experiment_id="branch_consensus_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_majority_success_count=sum(row.source_majority_committed_count for row in rows),
        source_singleton_success_count=sum(row.source_singleton_committed_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        consensus_success_count=sum(1 for row in rows if row.consensus_committed),
        same_budget_consensus_count=sum(1 for row in rows if row.same_budget),
        branch_consensus_certificate_count=len(consensus_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_consensus_certificates_valid=all(
            validate_branch_consensus_certificate(certificate, row)
            for certificate, row in zip(consensus_certificates, rows)
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
        sources=BRANCH_CONSENSUS_SOURCES,
        learning=(
            "Source branch consensus can make past-branch reuse less brittle by requiring multiple "
            "source receipts for the selected target family. The consensus certificate can rank a target "
            "proposal, but singleton support and majority support both remain proposal evidence until "
            "the target hard verifier emits a fresh receipt."
        ),
    )
    transfer_certificate = build_branch_consensus_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_consensus_certificate_hashes=tuple(certificate.certificate_hash for certificate in consensus_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_consensus_transfer",
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
        claim_boundary=BRANCH_CONSENSUS_CLAIM_BOUNDARY,
        sources=BRANCH_CONSENSUS_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchConsensusTransferResult(
        report=report,
        branch_consensus_transfer_certificate=transfer_certificate,
        branch_consensus_certificates=tuple(consensus_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_consensus_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_ids: tuple[str, ...],
    target_context_id: str,
    selected_family_id: str,
    singleton_family_id: str,
    source_majority_actions: tuple[str, ...],
    source_singleton_actions: tuple[str, ...],
    static_target_action: str,
    consensus_target_action: str,
    source_majority_receipt_hashes: tuple[str, ...],
    source_singleton_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    consensus_target_receipt_hashes: tuple[str, ...],
    consensus_target_commit_receipt_hashes: tuple[str, ...],
    source_majority_branch_selection_certificate_hashes: tuple[str, ...],
    source_singleton_branch_selection_certificate_hashes: tuple[str, ...],
    static_branch_selection_certificate_hash: str,
    consensus_branch_selection_certificate_hash: str,
    source_majority_committed_count: int,
    source_singleton_committed_count: int,
    static_committed: bool,
    consensus_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    consensus_verifier_call_count: int,
) -> BranchConsensusCertificate:
    return BranchConsensusCertificate(
        schema_version=BRANCH_CONSENSUS_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        consensus_rule_id="majority_source_family_consensus",
        consensus_rule_version="1.0",
        source_context_ids=source_context_ids,
        target_context_id=target_context_id,
        selected_family_id=selected_family_id,
        singleton_family_id=singleton_family_id,
        majority_support_count=2,
        singleton_support_count=1,
        required_support_count=2,
        source_majority_actions=source_majority_actions,
        source_singleton_actions=source_singleton_actions,
        static_target_action=static_target_action,
        consensus_target_action=consensus_target_action,
        source_majority_receipt_hashes=source_majority_receipt_hashes,
        source_singleton_receipt_hashes=source_singleton_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        consensus_target_receipt_hashes=consensus_target_receipt_hashes,
        consensus_target_commit_receipt_hashes=consensus_target_commit_receipt_hashes,
        source_majority_branch_selection_certificate_hashes=source_majority_branch_selection_certificate_hashes,
        source_singleton_branch_selection_certificate_hashes=source_singleton_branch_selection_certificate_hashes,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        consensus_branch_selection_certificate_hash=consensus_branch_selection_certificate_hash,
        source_majority_committed_count=source_majority_committed_count,
        source_singleton_committed_count=source_singleton_committed_count,
        static_committed=static_committed,
        consensus_committed=consensus_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        consensus_verifier_call_count=consensus_verifier_call_count,
        same_budget=static_verifier_call_count == consensus_verifier_call_count == 1,
        consensus_reason="two_source_receipts_outvote_singleton_for_target_family",
    )


def validate_branch_consensus_certificate(
    certificate: BranchConsensusCertificate,
    row: BranchConsensusDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONSENSUS_CERTIFICATE_SCHEMA:
            return False
        if certificate.consensus_rule_id != "majority_source_family_consensus":
            return False
        if certificate.consensus_rule_version != "1.0":
            return False
        if certificate.majority_support_count != 2 or certificate.singleton_support_count != 1:
            return False
        if certificate.required_support_count != 2 or certificate.majority_support_count < certificate.required_support_count:
            return False
        if certificate.singleton_support_count >= certificate.required_support_count:
            return False
        for value in (
            certificate.domain,
            certificate.target_context_id,
            certificate.selected_family_id,
            certificate.singleton_family_id,
            certificate.static_target_action,
            certificate.consensus_target_action,
        ):
            if not _nonempty(value):
                return False
        if certificate.selected_family_id == certificate.singleton_family_id:
            return False
        if len(certificate.source_context_ids) != 3 or len(set(certificate.source_context_ids)) != 3:
            return False
        if len(certificate.source_majority_actions) != 2 or len(certificate.source_singleton_actions) != 1:
            return False
        if any(not _nonempty(value) for value in (*certificate.source_context_ids, *certificate.source_majority_actions, *certificate.source_singleton_actions)):
            return False
        if certificate.source_majority_committed_count != 2 or certificate.source_singleton_committed_count != 1:
            return False
        if certificate.static_committed or not certificate.consensus_committed:
            return False
        if certificate.source_verifier_call_count != 3:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.consensus_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.consensus_reason != "two_source_receipts_outvote_singleton_for_target_family":
            return False
        hash_groups = (
            (certificate.source_majority_receipt_hashes, 2),
            (certificate.source_singleton_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.consensus_target_receipt_hashes, 1),
            (certificate.consensus_target_commit_receipt_hashes, 1),
            (certificate.source_majority_branch_selection_certificate_hashes, 2),
            (certificate.source_singleton_branch_selection_certificate_hashes, 1),
        )
        for values, expected_len in hash_groups:
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.static_branch_selection_certificate_hash,
            certificate.consensus_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_contexts != certificate.source_context_ids or row.target_context != certificate.target_context_id:
                return False
            if row.selected_family_id != certificate.selected_family_id:
                return False
            if row.singleton_family_id != certificate.singleton_family_id:
                return False
            if row.majority_support_count != certificate.majority_support_count:
                return False
            if row.singleton_support_count != certificate.singleton_support_count:
                return False
            if row.required_support_count != certificate.required_support_count:
                return False
            if row.source_majority_actions != certificate.source_majority_actions:
                return False
            if row.source_singleton_actions != certificate.source_singleton_actions:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.consensus_target_action != certificate.consensus_target_action:
                return False
            if row.source_majority_committed_count != certificate.source_majority_committed_count:
                return False
            if row.source_singleton_committed_count != certificate.source_singleton_committed_count:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.consensus_committed != certificate.consensus_committed:
                return False
            if row.source_verifier_call_count != certificate.source_verifier_call_count:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.consensus_verifier_call_count != certificate.consensus_verifier_call_count:
                return False
            if row.source_majority_receipt_hashes != certificate.source_majority_receipt_hashes:
                return False
            if row.source_singleton_receipt_hashes != certificate.source_singleton_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.consensus_target_receipt_hashes != certificate.consensus_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_consensus_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_consensus_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_consensus_transfer_certificate(
    report: BranchConsensusTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_consensus_certificate_hashes: tuple[str, ...],
) -> BranchConsensusTransferCertificate:
    return BranchConsensusTransferCertificate(
        schema_version=BRANCH_CONSENSUS_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_consensus_certificate_hashes=branch_consensus_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_majority_success_count=report.source_majority_success_count,
        source_singleton_success_count=report.source_singleton_success_count,
        static_success_count=report.static_success_count,
        consensus_success_count=report.consensus_success_count,
        same_budget_consensus_count=report.same_budget_consensus_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CONSENSUS_CLAIM_BOUNDARY,
    )


def validate_branch_consensus_transfer_certificate(
    certificate: BranchConsensusTransferCertificate,
    report: BranchConsensusTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONSENSUS_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_consensus_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_consensus_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_majority_success_count != certificate.domain_count * 2:
            return False
        if certificate.source_singleton_success_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.consensus_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_consensus_count != certificate.domain_count:
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
            if tuple(row.branch_consensus_certificate_hash for row in report.rows) != certificate.branch_consensus_certificate_hashes:
                return False
            if report.branch_consensus_certificate_count != len(certificate.branch_consensus_certificate_hashes):
                return False
            if not report.all_branch_consensus_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_majority_success_count != certificate.source_majority_success_count:
                return False
            if report.source_singleton_success_count != certificate.source_singleton_success_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.consensus_success_count != certificate.consensus_success_count:
                return False
            if report.same_budget_consensus_count != certificate.same_budget_consensus_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_consensus_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_consensus_certificate_hash(
    certificate: BranchConsensusCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchConsensusCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_consensus_transfer_certificate_hash(
    certificate: BranchConsensusTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchConsensusTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchConsensusTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchConsensusTransferReport,
    transfer_certificate: BranchConsensusTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_consensus_transfer_g1",
        claim_text=(
            "Multiple past source branch receipts can improve local target exploration by certifying a "
            "majority-supported proposal family, while target commit authority remains with fresh hard verification."
        ),
        evidence_grade="G1",
        scope="branch_consensus_transfer",
        requirements=(
            requirement(
                "branch_consensus_transfer_certificate_valid",
                validate_branch_consensus_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_consensus_certificates_valid", report.all_branch_consensus_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("majority_sources_commit_all_domains", report.source_majority_success_count == report.domain_count * 2),
            requirement("singleton_sources_bound_all_domains", report.source_singleton_success_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("consensus_succeeds_all_domains", report.consensus_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_consensus_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 3),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_majority_success_count": report.source_majority_success_count,
            "source_singleton_success_count": report.source_singleton_success_count,
            "static_success_count": report.static_success_count,
            "consensus_success_count": report.consensus_success_count,
        },
        boundary=BRANCH_CONSENSUS_CLAIM_BOUNDARY,
        sources=BRANCH_CONSENSUS_SOURCES,
    )


def _make_consensus_traces(
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
            seeds=("branch-consensus-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.consensus.transfer.v1",
        )
        for action in actions
    )


def _domain_consensus_plan(
    spec: ExplorationDomainSpec,
    source_contexts: tuple[str, str, str],
    target_context: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "selected_family_id": "detour_family",
            "singleton_family_id": "aggressive_cut_family",
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "consensus_source_detour_a",
                    "utility": 8,
                    "clearance": 0.34,
                    "turn_rate": 0.44,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "consensus_source_detour_b",
                    "utility": 8,
                    "clearance": 0.36,
                    "turn_rate": 0.40,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "consensus_source_aggressive_cut",
                    "utility": 9,
                    "clearance": 0.27,
                    "turn_rate": 0.56,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "consensus_target_aggressive_cut",
                "utility": 9,
                "clearance": 0.14,
                "turn_rate": 0.72,
            },
            "target_consensus": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "consensus_target_detour",
                "utility": 8,
                "clearance": 0.33,
                "turn_rate": 0.42,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "selected_family_id": "valence_relax_family",
            "singleton_family_id": "high_strain_family",
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "consensus_source_valence_relax_a",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.18,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "consensus_source_valence_relax_b",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.22,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "consensus_source_high_strain",
                    "utility": 9,
                    "valence_ok": True,
                    "strain": 0.34,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "consensus_target_high_strain",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.43,
            },
            "target_consensus": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "consensus_target_valence_relax",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.20,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "selected_family_id": "tempered_phase_family",
            "singleton_family_id": "flash_quench_family",
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "consensus_source_tempered_phase_a",
                    "utility": 8,
                    "thermal_gradient": 0.38,
                    "phase_purity": 0.94,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "consensus_source_tempered_phase_b",
                    "utility": 8,
                    "thermal_gradient": 0.42,
                    "phase_purity": 0.93,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "consensus_source_flash_quench",
                    "utility": 9,
                    "thermal_gradient": 0.49,
                    "phase_purity": 0.91,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "consensus_target_flash_quench",
                "utility": 9,
                "thermal_gradient": 0.69,
                "phase_purity": 0.88,
            },
            "target_consensus": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "consensus_target_tempered_phase",
                "utility": 8,
                "thermal_gradient": 0.41,
                "phase_purity": 0.94,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_consensus_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
