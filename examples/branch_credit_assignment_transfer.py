from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from math import isfinite
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


BRANCH_CREDIT_ASSIGNMENT_CERTIFICATE_SCHEMA = "trwm.branch_credit_assignment_certificate.v1"
BRANCH_CREDIT_ASSIGNMENT_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_credit_assignment_transfer_certificate.v1"
BRANCH_CREDIT_ASSIGNMENT_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1515/9781400881970-018",
)
BRANCH_CREDIT_ASSIGNMENT_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound marginal-credit fields "
    "can separate a causally useful source branch fragment from source-valid correlated distractors before "
    "target exploration under a matched one-call verifier budget. It is not a Shapley-value computation, "
    "causal inference result, reinforcement-learning credit-assignment result, robotics safety, chemistry, "
    "materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchCreditAssignmentCertificate:
    schema_version: str
    domain: str
    credit_rule_id: str
    credit_rule_version: str
    source_context_ids: tuple[str, ...]
    target_context_id: str
    source_actions: tuple[str, ...]
    credited_action: str
    distractor_actions: tuple[str, ...]
    static_target_action: str
    credit_target_action: str
    credit_values: tuple[float, ...]
    credited_credit_value: float
    max_distractor_credit_value: float
    minimum_credit_gap: float
    source_receipt_hashes: tuple[str, ...]
    credited_source_receipt_hashes: tuple[str, ...]
    distractor_source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    credit_target_receipt_hashes: tuple[str, ...]
    credit_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hashes: tuple[str, ...]
    static_branch_selection_certificate_hash: str
    credit_branch_selection_certificate_hash: str
    source_committed_count: int
    static_committed: bool
    credit_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    credit_verifier_call_count: int
    same_budget: bool
    credit_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CREDIT_ASSIGNMENT_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch credit-assignment certificate schema: {self.schema_version}")
        for field_name in (
            "source_context_ids",
            "source_actions",
            "distractor_actions",
            "credit_values",
            "source_receipt_hashes",
            "credited_source_receipt_hashes",
            "distractor_source_receipt_hashes",
            "static_target_receipt_hashes",
            "credit_target_receipt_hashes",
            "credit_target_commit_receipt_hashes",
            "source_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in ("credited_credit_value", "max_distractor_credit_value", "minimum_credit_gap"):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        object.__setattr__(self, "credit_values", tuple(float(value) for value in self.credit_values))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_credit_assignment_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchCreditAssignmentDomainReport:
    domain: str
    source_contexts: tuple[str, ...]
    target_context: str
    source_actions: tuple[str, ...]
    credited_action: str
    distractor_actions: tuple[str, ...]
    static_target_action: str
    credit_target_action: str
    credit_values: tuple[float, ...]
    credited_credit_value: float
    max_distractor_credit_value: float
    minimum_credit_gap: float
    source_committed_count: int
    static_committed: bool
    credit_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    credit_verifier_call_count: int
    source_receipt_hashes: tuple[str, ...]
    credited_source_receipt_hashes: tuple[str, ...]
    distractor_source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    credit_target_receipt_hashes: tuple[str, ...]
    branch_credit_assignment_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchCreditAssignmentTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchCreditAssignmentDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_success_count: int
    credited_source_count: int
    distractor_source_count: int
    static_success_count: int
    credit_success_count: int
    same_budget_credit_count: int
    branch_credit_assignment_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_credit_assignment_certificates_valid: bool
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
class BranchCreditAssignmentTransferCertificate:
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
    branch_credit_assignment_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_success_count: int
    credited_source_count: int
    distractor_source_count: int
    static_success_count: int
    credit_success_count: int
    same_budget_credit_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CREDIT_ASSIGNMENT_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch credit-assignment transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_credit_assignment_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_credit_assignment_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchCreditAssignmentTransferResult(CertifiedExampleResult):
    report: BranchCreditAssignmentTransferReport
    branch_credit_assignment_transfer_certificate: BranchCreditAssignmentTransferCertificate
    branch_credit_assignment_certificates: tuple[BranchCreditAssignmentCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_credit_assignment_transfer_experiment() -> BranchCreditAssignmentTransferReport:
    return run_branch_credit_assignment_transfer_certified_experiment().report


def run_branch_credit_assignment_transfer_certified_experiment() -> CertifiedBranchCreditAssignmentTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchCreditAssignmentDomainReport] = []
    credit_certificates: list[BranchCreditAssignmentCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_contexts = (
            f"{spec.domain_id}:source:credit:credited",
            f"{spec.domain_id}:source:credit:distractor_a",
            f"{spec.domain_id}:source:credit:distractor_b",
        )
        target_context = f"{spec.domain_id}:target:credit_assignment"
        plan = _domain_credit_assignment_plan(spec, source_contexts, target_context)

        source_outcomes = []
        source_certificates = []
        for source_context, source_action in zip(source_contexts, plan["source_actions"]):
            outcome = runtime.step(
                state,
                _make_credit_assignment_traces(
                    spec,
                    context=source_context,
                    phase="source-credit",
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
            _make_credit_assignment_traces(
                spec,
                context=target_context,
                phase="target-static-distractor",
                actions=(plan["target_static"],),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        credit_outcome = runtime.step(
            state,
            _make_credit_assignment_traces(
                spec,
                context=target_context,
                phase="target-credit-guided",
                actions=(plan["target_credit"],),
            ),
        )
        state = normalize_state(credit_outcome.state)
        credit_selection_certificate = build_branch_selection_certificate(
            credit_outcome.receipts,
            verifier_call_count=credit_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(credit_outcome.receipts), credit_selection_certificate))

        source_hashes = tuple(
            receipt.receipt_hash for outcome in source_outcomes for receipt in outcome.receipts if receipt.committed
        )
        credited_hashes = tuple(receipt.receipt_hash for receipt in source_outcomes[0].receipts if receipt.committed)
        distractor_hashes = tuple(
            receipt.receipt_hash
            for outcome in source_outcomes[1:]
            for receipt in outcome.receipts
            if receipt.committed
        )
        credit_values = tuple(float(value) for value in plan["credit_values"])
        max_distractor_credit = max(credit_values[1:])
        certificate = build_branch_credit_assignment_certificate(
            spec,
            source_context_ids=source_contexts,
            target_context_id=target_context,
            source_actions=tuple(str(action["action"]) for action in plan["source_actions"]),
            credited_action=str(plan["source_actions"][0]["action"]),
            distractor_actions=tuple(str(action["action"]) for action in plan["source_actions"][1:]),
            static_target_action=str(plan["target_static"]["action"]),
            credit_target_action=str(plan["target_credit"]["action"]),
            credit_values=credit_values,
            credited_credit_value=credit_values[0],
            max_distractor_credit_value=max_distractor_credit,
            minimum_credit_gap=float(plan["minimum_credit_gap"]),
            source_receipt_hashes=source_hashes,
            credited_source_receipt_hashes=credited_hashes,
            distractor_source_receipt_hashes=distractor_hashes,
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            credit_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in credit_outcome.receipts),
            credit_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in credit_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hashes=tuple(selection.certificate_hash for selection in source_certificates),
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            credit_branch_selection_certificate_hash=credit_selection_certificate.certificate_hash,
            source_committed_count=sum(1 for outcome in source_outcomes if outcome.committed),
            static_committed=static_outcome.committed,
            credit_committed=credit_outcome.committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in source_outcomes),
            static_verifier_call_count=static_outcome.verifier_calls,
            credit_verifier_call_count=credit_outcome.verifier_calls,
        )
        credit_certificates.append(certificate)
        rows.append(
            BranchCreditAssignmentDomainReport(
                domain=spec.domain_id,
                source_contexts=certificate.source_context_ids,
                target_context=certificate.target_context_id,
                source_actions=certificate.source_actions,
                credited_action=certificate.credited_action,
                distractor_actions=certificate.distractor_actions,
                static_target_action=certificate.static_target_action,
                credit_target_action=certificate.credit_target_action,
                credit_values=certificate.credit_values,
                credited_credit_value=certificate.credited_credit_value,
                max_distractor_credit_value=certificate.max_distractor_credit_value,
                minimum_credit_gap=certificate.minimum_credit_gap,
                source_committed_count=certificate.source_committed_count,
                static_committed=certificate.static_committed,
                credit_committed=certificate.credit_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                credit_verifier_call_count=certificate.credit_verifier_call_count,
                source_receipt_hashes=certificate.source_receipt_hashes,
                credited_source_receipt_hashes=certificate.credited_source_receipt_hashes,
                distractor_source_receipt_hashes=certificate.distractor_source_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                credit_target_receipt_hashes=certificate.credit_target_receipt_hashes,
                branch_credit_assignment_certificate_hash=certificate.certificate_hash,
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

    report = BranchCreditAssignmentTransferReport(
        schema_version="trwm.example.branch_credit_assignment_transfer.v1",
        experiment_id="branch_credit_assignment_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_success_count=sum(row.source_committed_count for row in rows),
        credited_source_count=sum(1 for row in rows if row.credited_source_receipt_hashes),
        distractor_source_count=sum(len(row.distractor_source_receipt_hashes) for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        credit_success_count=sum(1 for row in rows if row.credit_committed),
        same_budget_credit_count=sum(1 for row in rows if row.same_budget),
        branch_credit_assignment_certificate_count=len(credit_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_credit_assignment_certificates_valid=all(
            validate_branch_credit_assignment_certificate(certificate, row)
            for certificate, row in zip(credit_certificates, rows)
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
        sources=BRANCH_CREDIT_ASSIGNMENT_SOURCES,
        learning=(
            "Credit-assigned branch reuse separates source-valid correlation from useful causal proposal "
            "evidence. Low-credit source commits stay in the ledger, but a target branch is prioritized only "
            "when the certificate binds a higher marginal-credit fragment and the target hard verifier emits "
            "a fresh commit receipt."
        ),
    )
    transfer_certificate = build_branch_credit_assignment_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_credit_assignment_certificate_hashes=tuple(
            certificate.certificate_hash for certificate in credit_certificates
        ),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_credit_assignment_transfer",
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
        claim_boundary=BRANCH_CREDIT_ASSIGNMENT_CLAIM_BOUNDARY,
        sources=BRANCH_CREDIT_ASSIGNMENT_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchCreditAssignmentTransferResult(
        report=report,
        branch_credit_assignment_transfer_certificate=transfer_certificate,
        branch_credit_assignment_certificates=tuple(credit_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_credit_assignment_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_ids: tuple[str, ...],
    target_context_id: str,
    source_actions: tuple[str, ...],
    credited_action: str,
    distractor_actions: tuple[str, ...],
    static_target_action: str,
    credit_target_action: str,
    credit_values: tuple[float, ...],
    credited_credit_value: float,
    max_distractor_credit_value: float,
    minimum_credit_gap: float,
    source_receipt_hashes: tuple[str, ...],
    credited_source_receipt_hashes: tuple[str, ...],
    distractor_source_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    credit_target_receipt_hashes: tuple[str, ...],
    credit_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hashes: tuple[str, ...],
    static_branch_selection_certificate_hash: str,
    credit_branch_selection_certificate_hash: str,
    source_committed_count: int,
    static_committed: bool,
    credit_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    credit_verifier_call_count: int,
) -> BranchCreditAssignmentCertificate:
    return BranchCreditAssignmentCertificate(
        schema_version=BRANCH_CREDIT_ASSIGNMENT_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        credit_rule_id="leave_one_out_marginal_branch_credit",
        credit_rule_version="1.0",
        source_context_ids=source_context_ids,
        target_context_id=target_context_id,
        source_actions=source_actions,
        credited_action=credited_action,
        distractor_actions=distractor_actions,
        static_target_action=static_target_action,
        credit_target_action=credit_target_action,
        credit_values=credit_values,
        credited_credit_value=credited_credit_value,
        max_distractor_credit_value=max_distractor_credit_value,
        minimum_credit_gap=minimum_credit_gap,
        source_receipt_hashes=source_receipt_hashes,
        credited_source_receipt_hashes=credited_source_receipt_hashes,
        distractor_source_receipt_hashes=distractor_source_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        credit_target_receipt_hashes=credit_target_receipt_hashes,
        credit_target_commit_receipt_hashes=credit_target_commit_receipt_hashes,
        source_branch_selection_certificate_hashes=source_branch_selection_certificate_hashes,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        credit_branch_selection_certificate_hash=credit_branch_selection_certificate_hash,
        source_committed_count=source_committed_count,
        static_committed=static_committed,
        credit_committed=credit_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        credit_verifier_call_count=credit_verifier_call_count,
        same_budget=static_verifier_call_count == credit_verifier_call_count == 1,
        credit_reason="credited_source_fragment_exceeds_distractor_marginal_credit",
    )


def validate_branch_credit_assignment_certificate(
    certificate: BranchCreditAssignmentCertificate,
    row: BranchCreditAssignmentDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CREDIT_ASSIGNMENT_CERTIFICATE_SCHEMA:
            return False
        if certificate.credit_rule_id != "leave_one_out_marginal_branch_credit":
            return False
        if certificate.credit_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.target_context_id,
            certificate.credited_action,
            certificate.static_target_action,
            certificate.credit_target_action,
        ):
            if not _nonempty(value):
                return False
        if len(certificate.source_context_ids) != 3 or len(set(certificate.source_context_ids)) != 3:
            return False
        if len(certificate.source_actions) != 3 or len(set(certificate.source_actions)) != 3:
            return False
        if len(certificate.distractor_actions) != 2 or len(set(certificate.distractor_actions)) != 2:
            return False
        if certificate.credited_action not in certificate.source_actions:
            return False
        if certificate.credited_action in certificate.distractor_actions:
            return False
        if set(certificate.distractor_actions) != set(certificate.source_actions[1:]):
            return False
        if certificate.static_target_action == certificate.credit_target_action:
            return False
        if len(certificate.credit_values) != 3 or any(not _finite_number(value) for value in certificate.credit_values):
            return False
        if not _finite_number(certificate.credited_credit_value):
            return False
        if not _finite_number(certificate.max_distractor_credit_value):
            return False
        if not _finite_number(certificate.minimum_credit_gap) or certificate.minimum_credit_gap <= 0:
            return False
        if certificate.credited_credit_value != certificate.credit_values[0]:
            return False
        if certificate.max_distractor_credit_value != max(certificate.credit_values[1:]):
            return False
        if certificate.credited_credit_value - certificate.max_distractor_credit_value < certificate.minimum_credit_gap:
            return False
        if certificate.source_committed_count != 3:
            return False
        if certificate.static_committed or not certificate.credit_committed:
            return False
        if certificate.source_verifier_call_count != 3:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.credit_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.credit_reason != "credited_source_fragment_exceeds_distractor_marginal_credit":
            return False
        hash_groups = (
            (certificate.source_receipt_hashes, 3),
            (certificate.credited_source_receipt_hashes, 1),
            (certificate.distractor_source_receipt_hashes, 2),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.credit_target_receipt_hashes, 1),
            (certificate.credit_target_commit_receipt_hashes, 1),
            (certificate.source_branch_selection_certificate_hashes, 3),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.static_branch_selection_certificate_hash,
            certificate.credit_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_contexts != certificate.source_context_ids or row.target_context != certificate.target_context_id:
                return False
            if row.source_actions != certificate.source_actions:
                return False
            if row.credited_action != certificate.credited_action:
                return False
            if row.distractor_actions != certificate.distractor_actions:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.credit_target_action != certificate.credit_target_action:
                return False
            if row.credit_values != certificate.credit_values:
                return False
            if row.credited_credit_value != certificate.credited_credit_value:
                return False
            if row.max_distractor_credit_value != certificate.max_distractor_credit_value:
                return False
            if row.minimum_credit_gap != certificate.minimum_credit_gap:
                return False
            if row.source_receipt_hashes != certificate.source_receipt_hashes:
                return False
            if row.credited_source_receipt_hashes != certificate.credited_source_receipt_hashes:
                return False
            if row.distractor_source_receipt_hashes != certificate.distractor_source_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.credit_target_receipt_hashes != certificate.credit_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_credit_assignment_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_credit_assignment_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_credit_assignment_transfer_certificate(
    report: BranchCreditAssignmentTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_credit_assignment_certificate_hashes: tuple[str, ...],
) -> BranchCreditAssignmentTransferCertificate:
    return BranchCreditAssignmentTransferCertificate(
        schema_version=BRANCH_CREDIT_ASSIGNMENT_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_credit_assignment_certificate_hashes=branch_credit_assignment_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_success_count=report.source_success_count,
        credited_source_count=report.credited_source_count,
        distractor_source_count=report.distractor_source_count,
        static_success_count=report.static_success_count,
        credit_success_count=report.credit_success_count,
        same_budget_credit_count=report.same_budget_credit_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CREDIT_ASSIGNMENT_CLAIM_BOUNDARY,
    )


def validate_branch_credit_assignment_transfer_certificate(
    certificate: BranchCreditAssignmentTransferCertificate,
    report: BranchCreditAssignmentTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CREDIT_ASSIGNMENT_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_credit_assignment_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_credit_assignment_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_success_count != certificate.domain_count * 3:
            return False
        if certificate.credited_source_count != certificate.domain_count:
            return False
        if certificate.distractor_source_count != certificate.domain_count * 2:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.credit_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_credit_count != certificate.domain_count:
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
            if tuple(row.branch_credit_assignment_certificate_hash for row in report.rows) != certificate.branch_credit_assignment_certificate_hashes:
                return False
            if report.branch_credit_assignment_certificate_count != len(certificate.branch_credit_assignment_certificate_hashes):
                return False
            if not report.all_branch_credit_assignment_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_success_count != certificate.source_success_count:
                return False
            if report.credited_source_count != certificate.credited_source_count:
                return False
            if report.distractor_source_count != certificate.distractor_source_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.credit_success_count != certificate.credit_success_count:
                return False
            if report.same_budget_credit_count != certificate.same_budget_credit_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_credit_assignment_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_credit_assignment_certificate_hash(
    certificate: BranchCreditAssignmentCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCreditAssignmentCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_credit_assignment_transfer_certificate_hash(
    certificate: BranchCreditAssignmentTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCreditAssignmentTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchCreditAssignmentTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchCreditAssignmentTransferReport,
    transfer_certificate: BranchCreditAssignmentTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_credit_assignment_transfer_g1",
        claim_text=(
            "Receipt-bound marginal-credit evidence can improve local target exploration by separating "
            "useful branch fragments from source-valid distractors under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_credit_assignment_transfer",
        requirements=(
            requirement(
                "branch_credit_assignment_transfer_certificate_valid",
                validate_branch_credit_assignment_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_credit_assignment_certificates_valid", report.all_branch_credit_assignment_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_commits_all_domains", report.source_success_count == report.domain_count * 3),
            requirement("credited_sources_bound_all_domains", report.credited_source_count == report.domain_count),
            requirement("distractor_sources_bound_all_domains", report.distractor_source_count == report.domain_count * 2),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("credit_succeeds_all_domains", report.credit_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_credit_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 3),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_success_count": report.source_success_count,
            "credited_source_count": report.credited_source_count,
            "distractor_source_count": report.distractor_source_count,
            "static_success_count": report.static_success_count,
            "credit_success_count": report.credit_success_count,
        },
        boundary=BRANCH_CREDIT_ASSIGNMENT_CLAIM_BOUNDARY,
        sources=BRANCH_CREDIT_ASSIGNMENT_SOURCES,
    )


def _make_credit_assignment_traces(
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
            seeds=("branch-credit-assignment-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.credit_assignment.transfer.v1",
        )
        for action in actions
    )


def _domain_credit_assignment_plan(
    spec: ExplorationDomainSpec,
    source_contexts: tuple[str, str, str],
    target_context: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "credit_values": (0.92, 0.12, 0.04),
            "minimum_credit_gap": 0.50,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "credit_source_clearance_patch",
                    "utility": 8,
                    "clearance": 0.35,
                    "turn_rate": 0.42,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "credit_source_smooth_cosmetic",
                    "utility": 7,
                    "clearance": 0.32,
                    "turn_rate": 0.50,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "credit_source_log_tag",
                    "utility": 9,
                    "clearance": 0.30,
                    "turn_rate": 0.55,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "credit_target_log_tag",
                "utility": 9,
                "clearance": 0.14,
                "turn_rate": 0.78,
            },
            "target_credit": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "credit_target_clearance_patch",
                "utility": 8,
                "clearance": 0.33,
                "turn_rate": 0.41,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "credit_values": (0.94, 0.10, 0.03),
            "minimum_credit_gap": 0.50,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "credit_source_valence_repair",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.15,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "credit_source_label_swap",
                    "utility": 7,
                    "valence_ok": True,
                    "strain": 0.28,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "credit_source_score_tag",
                    "utility": 9,
                    "valence_ok": True,
                    "strain": 0.34,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "credit_target_score_tag",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.52,
            },
            "target_credit": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "credit_target_valence_repair",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.14,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "credit_values": (0.90, 0.08, 0.02),
            "minimum_credit_gap": 0.50,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "credit_source_phase_balance",
                    "utility": 8,
                    "thermal_gradient": 0.38,
                    "phase_purity": 0.95,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "credit_source_batch_label",
                    "utility": 7,
                    "thermal_gradient": 0.42,
                    "phase_purity": 0.92,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "credit_source_screening_tag",
                    "utility": 9,
                    "thermal_gradient": 0.49,
                    "phase_purity": 0.91,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "credit_target_screening_tag",
                "utility": 9,
                "thermal_gradient": 0.70,
                "phase_purity": 0.86,
            },
            "target_credit": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "credit_target_phase_balance",
                "utility": 8,
                "thermal_gradient": 0.39,
                "phase_purity": 0.95,
            },
        }
    raise ValueError(f"unknown credit-assignment domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value))


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_credit_assignment_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
