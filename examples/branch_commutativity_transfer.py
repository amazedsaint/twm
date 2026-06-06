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


BRANCH_COMMUTATIVITY_CERTIFICATE_SCHEMA = "trwm.branch_commutativity_certificate.v1"
BRANCH_COMMUTATIVITY_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_commutativity_transfer_certificate.v1"
BRANCH_COMMUTATIVITY_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://lics.siglog.org/1996/WillemsWolper-PartialOrderMethods.html",
    "https://patricegodefroid.github.io/public_psfiles/popl2005.pdf",
)
BRANCH_COMMUTATIVITY_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound commutativity "
    "evidence can filter a non-canonical target order before target exploration under a matched "
    "one-call verifier budget. It is not a partial-order reduction algorithm, model-checking "
    "correctness proof, dynamic partial-order reduction result, concurrency verification result, "
    "state-space reduction guarantee, robotics safety, chemistry, materials discovery, or "
    "scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchCommutativityCertificate:
    schema_version: str
    domain: str
    commutativity_rule_id: str
    commutativity_rule_version: str
    source_context_id: str
    target_context_id: str
    canonical_order_key: str
    conflict_order_key: str
    source_ab_action_id: str
    source_ba_action_id: str
    source_conflict_action_id: str
    static_target_action: str
    commutative_target_action: str
    source_ab_receipt_hashes: tuple[str, ...]
    source_ba_receipt_hashes: tuple[str, ...]
    source_conflict_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    commutative_target_receipt_hashes: tuple[str, ...]
    commutative_target_commit_receipt_hashes: tuple[str, ...]
    source_ab_branch_selection_certificate_hash: str
    source_ba_branch_selection_certificate_hash: str
    source_conflict_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    commutative_branch_selection_certificate_hash: str
    source_ab_committed: bool
    source_ba_committed: bool
    source_conflict_rejected: bool
    static_committed: bool
    commutative_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    commutative_verifier_call_count: int
    same_budget: bool
    commutativity_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_COMMUTATIVITY_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch commutativity certificate schema: {self.schema_version}")
        for field_name in (
            "source_ab_receipt_hashes",
            "source_ba_receipt_hashes",
            "source_conflict_receipt_hashes",
            "static_target_receipt_hashes",
            "commutative_target_receipt_hashes",
            "commutative_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_commutativity_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchCommutativityDomainReport:
    domain: str
    source_context: str
    target_context: str
    canonical_order_key: str
    conflict_order_key: str
    source_ab_action_id: str
    source_ba_action_id: str
    source_conflict_action_id: str
    static_target_action: str
    commutative_target_action: str
    source_ab_committed: bool
    source_ba_committed: bool
    source_conflict_rejected: bool
    static_committed: bool
    commutative_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    commutative_verifier_call_count: int
    source_ab_receipt_hashes: tuple[str, ...]
    source_ba_receipt_hashes: tuple[str, ...]
    source_conflict_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    commutative_target_receipt_hashes: tuple[str, ...]
    branch_commutativity_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchCommutativityTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchCommutativityDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_ab_committed_count: int
    source_ba_committed_count: int
    source_conflict_rejected_count: int
    static_success_count: int
    commutative_success_count: int
    same_budget_commutativity_count: int
    branch_commutativity_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_commutativity_certificates_valid: bool
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
class BranchCommutativityTransferCertificate:
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
    branch_commutativity_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_ab_committed_count: int
    source_ba_committed_count: int
    source_conflict_rejected_count: int
    static_success_count: int
    commutative_success_count: int
    same_budget_commutativity_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_COMMUTATIVITY_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch commutativity transfer certificate schema: {self.schema_version}")
        for field_name in ("domains", "receipt_hashes", "branch_selection_certificate_hashes", "branch_commutativity_certificate_hashes"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_commutativity_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchCommutativityTransferResult(CertifiedExampleResult):
    report: BranchCommutativityTransferReport
    branch_commutativity_transfer_certificate: BranchCommutativityTransferCertificate
    branch_commutativity_certificates: tuple[BranchCommutativityCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_commutativity_transfer_experiment() -> BranchCommutativityTransferReport:
    return run_branch_commutativity_transfer_certified_experiment().report


def run_branch_commutativity_transfer_certified_experiment() -> CertifiedBranchCommutativityTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchCommutativityDomainReport] = []
    commutativity_certificates: list[BranchCommutativityCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_commutativity_plan(spec)
        source_context = f"{spec.domain_id}:source:branch-commutativity"
        target_context = f"{spec.domain_id}:target:branch-commutativity"

        source_ab_outcome = runtime.step(
            state,
            _make_commutativity_traces(spec, context=source_context, phase="source-ab", actions=(plan["source_ab"],)),
        )
        state = normalize_state(source_ab_outcome.state)
        source_ab_selection = build_branch_selection_certificate(source_ab_outcome.receipts, verifier_call_count=source_ab_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(source_ab_outcome.receipts), source_ab_selection))
        memory.update_branch(source_ab_outcome.receipts, source_ab_selection)

        source_ba_outcome = runtime.step(
            state,
            _make_commutativity_traces(spec, context=source_context, phase="source-ba", actions=(plan["source_ba"],)),
        )
        state = normalize_state(source_ba_outcome.state)
        source_ba_selection = build_branch_selection_certificate(source_ba_outcome.receipts, verifier_call_count=source_ba_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(source_ba_outcome.receipts), source_ba_selection))
        memory.update_branch(source_ba_outcome.receipts, source_ba_selection)

        source_conflict_outcome = runtime.step(
            state,
            _make_commutativity_traces(spec, context=source_context, phase="source-conflict", actions=(plan["source_conflict"],)),
        )
        source_conflict_selection = build_branch_selection_certificate(
            source_conflict_outcome.receipts,
            verifier_call_count=source_conflict_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_conflict_outcome.receipts), source_conflict_selection))
        memory.update_branch(source_conflict_outcome.receipts, source_conflict_selection)

        static_outcome = runtime.step(
            state,
            _make_commutativity_traces(spec, context=target_context, phase="target-static-conflict", actions=(plan["target_static"],)),
        )
        static_selection = build_branch_selection_certificate(static_outcome.receipts, verifier_call_count=static_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        commutative_outcome = runtime.step(
            state,
            _make_commutativity_traces(spec, context=target_context, phase="target-canonical", actions=(plan["target_commutative"],)),
        )
        state = normalize_state(commutative_outcome.state)
        commutative_selection = build_branch_selection_certificate(
            commutative_outcome.receipts,
            verifier_call_count=commutative_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(commutative_outcome.receipts), commutative_selection))

        certificate = build_branch_commutativity_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            canonical_order_key=str(plan["canonical_order_key"]),
            conflict_order_key=str(plan["conflict_order_key"]),
            source_ab_action_id=str(plan["source_ab"]["action"]),
            source_ba_action_id=str(plan["source_ba"]["action"]),
            source_conflict_action_id=str(plan["source_conflict"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            commutative_target_action=str(plan["target_commutative"]["action"]),
            source_ab_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_ab_outcome.receipts),
            source_ba_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_ba_outcome.receipts),
            source_conflict_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_conflict_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            commutative_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in commutative_outcome.receipts),
            commutative_target_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in commutative_outcome.receipts if receipt.committed),
            source_ab_branch_selection_certificate_hash=source_ab_selection.certificate_hash,
            source_ba_branch_selection_certificate_hash=source_ba_selection.certificate_hash,
            source_conflict_branch_selection_certificate_hash=source_conflict_selection.certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            commutative_branch_selection_certificate_hash=commutative_selection.certificate_hash,
            source_ab_committed=source_ab_outcome.committed,
            source_ba_committed=source_ba_outcome.committed,
            source_conflict_rejected=any(receipt.hard_result.rejected for receipt in source_conflict_outcome.receipts),
            static_committed=static_outcome.committed,
            commutative_committed=commutative_outcome.committed,
            source_verifier_call_count=source_ab_outcome.verifier_calls + source_ba_outcome.verifier_calls + source_conflict_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            commutative_verifier_call_count=commutative_outcome.verifier_calls,
        )
        commutativity_certificates.append(certificate)
        rows.append(_row_from_certificate(certificate))

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

    report = BranchCommutativityTransferReport(
        schema_version="trwm.example.branch_commutativity_transfer.v1",
        experiment_id="branch_commutativity_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_ab_committed_count=sum(1 for row in rows if row.source_ab_committed),
        source_ba_committed_count=sum(1 for row in rows if row.source_ba_committed),
        source_conflict_rejected_count=sum(1 for row in rows if row.source_conflict_rejected),
        static_success_count=sum(1 for row in rows if row.static_committed),
        commutative_success_count=sum(1 for row in rows if row.commutative_committed),
        same_budget_commutativity_count=sum(1 for row in rows if row.same_budget),
        branch_commutativity_certificate_count=len(commutativity_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_commutativity_certificates_valid=all(
            validate_branch_commutativity_certificate(certificate, row)
            for certificate, row in zip(commutativity_certificates, rows)
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
        sources=BRANCH_COMMUTATIVITY_SOURCES,
        learning=(
            "Commutativity reuse separates independent-order evidence from commit authority. Source receipts "
            "can show two orders share a canonical key and that a conflicting order rejects, but the target "
            "canonical order still commits only through a fresh hard-verifier receipt."
        ),
    )
    transfer_certificate = build_branch_commutativity_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_commutativity_certificate_hashes=tuple(certificate.certificate_hash for certificate in commutativity_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_commutativity_transfer",
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
        claim_boundary=BRANCH_COMMUTATIVITY_CLAIM_BOUNDARY,
        sources=BRANCH_COMMUTATIVITY_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchCommutativityTransferResult(
        report=report,
        branch_commutativity_transfer_certificate=transfer_certificate,
        branch_commutativity_certificates=tuple(commutativity_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_commutativity_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    canonical_order_key: str,
    conflict_order_key: str,
    source_ab_action_id: str,
    source_ba_action_id: str,
    source_conflict_action_id: str,
    static_target_action: str,
    commutative_target_action: str,
    source_ab_receipt_hashes: tuple[str, ...],
    source_ba_receipt_hashes: tuple[str, ...],
    source_conflict_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    commutative_target_receipt_hashes: tuple[str, ...],
    commutative_target_commit_receipt_hashes: tuple[str, ...],
    source_ab_branch_selection_certificate_hash: str,
    source_ba_branch_selection_certificate_hash: str,
    source_conflict_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    commutative_branch_selection_certificate_hash: str,
    source_ab_committed: bool,
    source_ba_committed: bool,
    source_conflict_rejected: bool,
    static_committed: bool,
    commutative_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    commutative_verifier_call_count: int,
) -> BranchCommutativityCertificate:
    return BranchCommutativityCertificate(
        schema_version=BRANCH_COMMUTATIVITY_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        commutativity_rule_id="receipt_bound_partial_order_commutativity",
        commutativity_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        canonical_order_key=canonical_order_key,
        conflict_order_key=conflict_order_key,
        source_ab_action_id=source_ab_action_id,
        source_ba_action_id=source_ba_action_id,
        source_conflict_action_id=source_conflict_action_id,
        static_target_action=static_target_action,
        commutative_target_action=commutative_target_action,
        source_ab_receipt_hashes=source_ab_receipt_hashes,
        source_ba_receipt_hashes=source_ba_receipt_hashes,
        source_conflict_receipt_hashes=source_conflict_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        commutative_target_receipt_hashes=commutative_target_receipt_hashes,
        commutative_target_commit_receipt_hashes=commutative_target_commit_receipt_hashes,
        source_ab_branch_selection_certificate_hash=source_ab_branch_selection_certificate_hash,
        source_ba_branch_selection_certificate_hash=source_ba_branch_selection_certificate_hash,
        source_conflict_branch_selection_certificate_hash=source_conflict_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        commutative_branch_selection_certificate_hash=commutative_branch_selection_certificate_hash,
        source_ab_committed=source_ab_committed,
        source_ba_committed=source_ba_committed,
        source_conflict_rejected=source_conflict_rejected,
        static_committed=static_committed,
        commutative_committed=commutative_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        commutative_verifier_call_count=commutative_verifier_call_count,
        same_budget=static_verifier_call_count == commutative_verifier_call_count == 1,
        commutativity_reason="source_orders_share_canonical_key_and_conflict_rejects",
    )


def validate_branch_commutativity_certificate(
    certificate: BranchCommutativityCertificate,
    row: BranchCommutativityDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_COMMUTATIVITY_CERTIFICATE_SCHEMA:
            return False
        if certificate.commutativity_rule_id != "receipt_bound_partial_order_commutativity":
            return False
        if certificate.commutativity_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.canonical_order_key):
            return False
        if not _nonempty(certificate.conflict_order_key) or certificate.canonical_order_key == certificate.conflict_order_key:
            return False
        action_ids = (
            certificate.source_ab_action_id,
            certificate.source_ba_action_id,
            certificate.source_conflict_action_id,
            certificate.static_target_action,
            certificate.commutative_target_action,
        )
        if len(set(action_ids)) != len(action_ids) or any(not _nonempty(action_id) for action_id in action_ids):
            return False
        if not (
            certificate.source_ab_committed
            and certificate.source_ba_committed
            and certificate.source_conflict_rejected
            and not certificate.static_committed
            and certificate.commutative_committed
        ):
            return False
        if certificate.source_verifier_call_count != 3:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.commutative_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.commutativity_reason != "source_orders_share_canonical_key_and_conflict_rejects":
            return False
        hash_groups = (
            (certificate.source_ab_receipt_hashes, 1),
            (certificate.source_ba_receipt_hashes, 1),
            (certificate.source_conflict_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.commutative_target_receipt_hashes, 1),
            (certificate.commutative_target_commit_receipt_hashes, 1),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_ab_branch_selection_certificate_hash,
            certificate.source_ba_branch_selection_certificate_hash,
            certificate.source_conflict_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.commutative_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.canonical_order_key != certificate.canonical_order_key or row.conflict_order_key != certificate.conflict_order_key:
                return False
            if row.source_ab_action_id != certificate.source_ab_action_id:
                return False
            if row.source_ba_action_id != certificate.source_ba_action_id:
                return False
            if row.source_conflict_action_id != certificate.source_conflict_action_id:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.commutative_target_action != certificate.commutative_target_action:
                return False
            if row.source_ab_receipt_hashes != certificate.source_ab_receipt_hashes:
                return False
            if row.source_ba_receipt_hashes != certificate.source_ba_receipt_hashes:
                return False
            if row.source_conflict_receipt_hashes != certificate.source_conflict_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.commutative_target_receipt_hashes != certificate.commutative_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_commutativity_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_commutativity_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_commutativity_transfer_certificate(
    report: BranchCommutativityTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_commutativity_certificate_hashes: tuple[str, ...],
) -> BranchCommutativityTransferCertificate:
    return BranchCommutativityTransferCertificate(
        schema_version=BRANCH_COMMUTATIVITY_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_commutativity_certificate_hashes=branch_commutativity_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_ab_committed_count=report.source_ab_committed_count,
        source_ba_committed_count=report.source_ba_committed_count,
        source_conflict_rejected_count=report.source_conflict_rejected_count,
        static_success_count=report.static_success_count,
        commutative_success_count=report.commutative_success_count,
        same_budget_commutativity_count=report.same_budget_commutativity_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_COMMUTATIVITY_CLAIM_BOUNDARY,
    )


def validate_branch_commutativity_transfer_certificate(
    certificate: BranchCommutativityTransferCertificate,
    report: BranchCommutativityTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_COMMUTATIVITY_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        if not _is_hash(certificate.report_hash) or not _is_hash(certificate.ledger_head):
            return False
        if not _is_hash(certificate.memory_snapshot_hash):
            return False
        for values in (certificate.receipt_hashes, certificate.branch_selection_certificate_hashes, certificate.branch_commutativity_certificate_hashes):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_commutativity_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_ab_committed_count != certificate.domain_count:
            return False
        if certificate.source_ba_committed_count != certificate.domain_count:
            return False
        if certificate.source_conflict_rejected_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.commutative_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_commutativity_count != certificate.domain_count:
            return False
        if not (certificate.replay_audit_ok and certificate.rollback_audit_ok and certificate.ledger_audit_ok):
            return False
        if certificate.invalid_commit_count != 0 or not certificate.claim_boundary:
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
            if tuple(row.branch_commutativity_certificate_hash for row in report.rows) != certificate.branch_commutativity_certificate_hashes:
                return False
            if report.branch_commutativity_certificate_count != len(certificate.branch_commutativity_certificate_hashes):
                return False
            if not report.all_branch_commutativity_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_ab_committed_count != certificate.source_ab_committed_count:
                return False
            if report.source_ba_committed_count != certificate.source_ba_committed_count:
                return False
            if report.source_conflict_rejected_count != certificate.source_conflict_rejected_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.commutative_success_count != certificate.commutative_success_count:
                return False
            if report.same_budget_commutativity_count != certificate.same_budget_commutativity_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_commutativity_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_commutativity_certificate_hash(certificate: BranchCommutativityCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchCommutativityCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_commutativity_transfer_certificate_hash(certificate: BranchCommutativityTransferCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchCommutativityTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchCommutativityTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchCommutativityTransferReport,
    transfer_certificate: BranchCommutativityTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_commutativity_transfer_g1",
        claim_text=(
            "Receipt-bound commutativity certificates can improve local target exploration by "
            "filtering non-canonical target orders and trying canonical independent-order branches "
            "under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_commutativity_transfer",
        requirements=(
            requirement(
                "branch_commutativity_transfer_certificate_valid",
                validate_branch_commutativity_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_commutativity_certificates_valid", report.all_branch_commutativity_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_ab_commits_all_domains", report.source_ab_committed_count == report.domain_count),
            requirement("source_ba_commits_all_domains", report.source_ba_committed_count == report.domain_count),
            requirement("source_conflicts_reject_all_domains", report.source_conflict_rejected_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("commutative_succeeds_all_domains", report.commutative_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_commutativity_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 3),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "static_success_count": report.static_success_count,
            "commutative_success_count": report.commutative_success_count,
        },
        boundary=BRANCH_COMMUTATIVITY_CLAIM_BOUNDARY,
        sources=BRANCH_COMMUTATIVITY_SOURCES,
    )


def _row_from_certificate(certificate: BranchCommutativityCertificate) -> BranchCommutativityDomainReport:
    return BranchCommutativityDomainReport(
        domain=certificate.domain,
        source_context=certificate.source_context_id,
        target_context=certificate.target_context_id,
        canonical_order_key=certificate.canonical_order_key,
        conflict_order_key=certificate.conflict_order_key,
        source_ab_action_id=certificate.source_ab_action_id,
        source_ba_action_id=certificate.source_ba_action_id,
        source_conflict_action_id=certificate.source_conflict_action_id,
        static_target_action=certificate.static_target_action,
        commutative_target_action=certificate.commutative_target_action,
        source_ab_committed=certificate.source_ab_committed,
        source_ba_committed=certificate.source_ba_committed,
        source_conflict_rejected=certificate.source_conflict_rejected,
        static_committed=certificate.static_committed,
        commutative_committed=certificate.commutative_committed,
        source_verifier_call_count=certificate.source_verifier_call_count,
        static_verifier_call_count=certificate.static_verifier_call_count,
        commutative_verifier_call_count=certificate.commutative_verifier_call_count,
        source_ab_receipt_hashes=certificate.source_ab_receipt_hashes,
        source_ba_receipt_hashes=certificate.source_ba_receipt_hashes,
        source_conflict_receipt_hashes=certificate.source_conflict_receipt_hashes,
        static_target_receipt_hashes=certificate.static_target_receipt_hashes,
        commutative_target_receipt_hashes=certificate.commutative_target_receipt_hashes,
        branch_commutativity_certificate_hash=certificate.certificate_hash,
        same_budget=certificate.same_budget,
    )


def _make_commutativity_traces(
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
            seeds=("branch-commutativity-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.commutativity.transfer.v1",
        )
        for action in actions
    )


def _domain_commutativity_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    canonical_order_key = f"{spec.domain_id}:independent_ab_ba"
    conflict_order_key = f"{spec.domain_id}:dependent_conflict_order"
    if spec.domain_id == "robotics_replan":
        return {
            "canonical_order_key": canonical_order_key,
            "conflict_order_key": conflict_order_key,
            "source_ab": {"domain": spec.domain_id, "action": "commute_source_sensor_then_detour", "utility": 7, "canonical_order_key": canonical_order_key, "operation_order": "sensor>detour", "clearance": 0.33, "turn_rate": 0.42},
            "source_ba": {"domain": spec.domain_id, "action": "commute_source_detour_then_sensor", "utility": 7, "canonical_order_key": canonical_order_key, "operation_order": "detour>sensor", "clearance": 0.34, "turn_rate": 0.41},
            "source_conflict": {"domain": spec.domain_id, "action": "commute_source_cut_before_sensor", "utility": 9, "canonical_order_key": conflict_order_key, "operation_order": "cut>sensor", "clearance": 0.17, "turn_rate": 0.82},
            "target_static": {"domain": spec.domain_id, "action": "commute_target_cut_before_sensor", "utility": 9, "canonical_order_key": conflict_order_key, "operation_order": "cut>sensor", "clearance": 0.16, "turn_rate": 0.80},
            "target_commutative": {"domain": spec.domain_id, "action": "commute_target_sensor_then_detour", "utility": 8, "canonical_order_key": canonical_order_key, "operation_order": "sensor>detour", "clearance": 0.36, "turn_rate": 0.43},
        }
    if spec.domain_id == "molecule_repair":
        return {
            "canonical_order_key": canonical_order_key,
            "conflict_order_key": conflict_order_key,
            "source_ab": {"domain": spec.domain_id, "action": "commute_source_cap_then_relax", "utility": 7, "canonical_order_key": canonical_order_key, "operation_order": "cap>relax", "valence_ok": True, "strain": 0.24},
            "source_ba": {"domain": spec.domain_id, "action": "commute_source_relax_then_cap", "utility": 7, "canonical_order_key": canonical_order_key, "operation_order": "relax>cap", "valence_ok": True, "strain": 0.22},
            "source_conflict": {"domain": spec.domain_id, "action": "commute_source_force_before_cap", "utility": 9, "canonical_order_key": conflict_order_key, "operation_order": "force>cap", "valence_ok": False, "strain": 0.40},
            "target_static": {"domain": spec.domain_id, "action": "commute_target_force_before_cap", "utility": 9, "canonical_order_key": conflict_order_key, "operation_order": "force>cap", "valence_ok": False, "strain": 0.39},
            "target_commutative": {"domain": spec.domain_id, "action": "commute_target_cap_then_relax", "utility": 8, "canonical_order_key": canonical_order_key, "operation_order": "cap>relax", "valence_ok": True, "strain": 0.18},
        }
    if spec.domain_id == "material_process":
        return {
            "canonical_order_key": canonical_order_key,
            "conflict_order_key": conflict_order_key,
            "source_ab": {"domain": spec.domain_id, "action": "commute_source_seed_then_ramp", "utility": 7, "canonical_order_key": canonical_order_key, "operation_order": "seed>ramp", "thermal_gradient": 0.42, "phase_purity": 0.94},
            "source_ba": {"domain": spec.domain_id, "action": "commute_source_ramp_then_seed", "utility": 7, "canonical_order_key": canonical_order_key, "operation_order": "ramp>seed", "thermal_gradient": 0.41, "phase_purity": 0.95},
            "source_conflict": {"domain": spec.domain_id, "action": "commute_source_quench_before_seed", "utility": 9, "canonical_order_key": conflict_order_key, "operation_order": "quench>seed", "thermal_gradient": 0.72, "phase_purity": 0.86},
            "target_static": {"domain": spec.domain_id, "action": "commute_target_quench_before_seed", "utility": 9, "canonical_order_key": conflict_order_key, "operation_order": "quench>seed", "thermal_gradient": 0.70, "phase_purity": 0.87},
            "target_commutative": {"domain": spec.domain_id, "action": "commute_target_seed_then_ramp", "utility": 8, "canonical_order_key": canonical_order_key, "operation_order": "seed>ramp", "thermal_gradient": 0.38, "phase_purity": 0.96},
        }
    raise ValueError(f"unknown commutativity domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_commutativity_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
