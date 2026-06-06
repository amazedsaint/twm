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
    BudgetedBranchRuntime,
    VerifierBudget,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, Receipt, TransactionEngine, stable_hash


BRANCH_BUDGET_CERTIFICATE_SCHEMA = "trwm.branch_budget_certificate.v1"
BRANCH_BUDGET_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_budget_transfer_certificate.v1"
BRANCH_BUDGET_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://jmlr.org/papers/v18/16-558.html",
    "https://arxiv.org/abs/1603.06560",
)
BRANCH_BUDGET_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows past branch receipts can certify "
    "a budget allocation that avoids spending all verifier budget on cheap repeated failures and "
    "admits a higher-cost repair under the same budget. It is not Hyperband, successive halving, "
    "a bandit guarantee, an optimal verifier scheduler, robotics safety, chemistry, materials discovery, "
    "or scientific autonomy evidence."
)
TARGET_BUDGET = 3


@dataclass(frozen=True)
class BranchBudgetCertificate:
    schema_version: str
    domain: str
    budget_rule_id: str
    budget_rule_version: str
    source_context_id: str
    target_context_id: str
    budget: int
    static_actions: tuple[str, ...]
    allocated_actions: tuple[str, ...]
    static_action_costs: tuple[int, ...]
    allocated_action_costs: tuple[int, ...]
    committed_target_action: str
    source_receipt_hashes: tuple[str, ...]
    source_reject_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    allocated_receipt_hashes: tuple[str, ...]
    static_abstain_receipt_hashes: tuple[str, ...]
    allocated_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    allocated_branch_selection_certificate_hash: str
    static_committed: bool
    allocated_committed: bool
    static_verifier_call_count: int
    allocated_verifier_call_count: int
    static_verifier_cost: int
    allocated_verifier_cost: int
    static_abstained_count: int
    allocated_abstained_count: int
    same_budget: bool
    budget_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_BUDGET_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch budget certificate schema: {self.schema_version}")
        for field_name in (
            "static_actions",
            "allocated_actions",
            "static_action_costs",
            "allocated_action_costs",
            "source_receipt_hashes",
            "source_reject_receipt_hashes",
            "source_commit_receipt_hashes",
            "static_receipt_hashes",
            "allocated_receipt_hashes",
            "static_abstain_receipt_hashes",
            "allocated_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_budget_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchBudgetDomainReport:
    domain: str
    source_context: str
    target_context: str
    budget: int
    static_actions: tuple[str, ...]
    allocated_actions: tuple[str, ...]
    static_action_costs: tuple[int, ...]
    allocated_action_costs: tuple[int, ...]
    committed_target_action: str
    static_budget_committed: bool
    allocated_budget_committed: bool
    static_verifier_cost: int
    allocated_verifier_cost: int
    static_abstained_count: int
    allocated_abstained_count: int
    source_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    allocated_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    allocated_branch_selection_certificate_hash: str
    budget_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchBudgetTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchBudgetDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_abstained_count: int
    total_rolled_back_loser_count: int
    static_budget_success_count: int
    allocated_budget_success_count: int
    static_abstain_count: int
    allocated_abstain_count: int
    same_budget_allocation_count: int
    branch_budget_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_budget_certificates_valid: bool
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
class BranchBudgetTransferCertificate:
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
    branch_budget_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    budget: int
    static_budget_success_count: int
    allocated_budget_success_count: int
    static_abstain_count: int
    allocated_abstain_count: int
    same_budget_allocation_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_BUDGET_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch budget transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_budget_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_budget_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchBudgetTransferResult(CertifiedExampleResult):
    report: BranchBudgetTransferReport
    branch_budget_transfer_certificate: BranchBudgetTransferCertificate
    branch_budget_certificates: tuple[BranchBudgetCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_budget_transfer_experiment() -> BranchBudgetTransferReport:
    return run_branch_budget_transfer_certified_experiment().report


def run_branch_budget_transfer_certified_experiment() -> CertifiedBranchBudgetTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    source_runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    budget_runtime = BudgetedBranchRuntime(
        engine,
        AncestralExplorationProjector(),
        VerifierBudget(TARGET_BUDGET),
        HighestUtilityRanker(),
    )
    memory = AncestralBranchMemory()
    rows: list[BranchBudgetDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    budget_certificates: list[BranchBudgetCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:budget"
        target_context = f"{spec.domain_id}:target:budget"
        action_map = _budget_actions(spec)
        source_outcome = source_runtime.step(
            state,
            _make_budget_traces(
                spec,
                context=source_context,
                phase="source-budget-evidence",
                episode=0,
                actions=(
                    _with_context(action_map["cheap_a"], source_context),
                    _with_context(action_map["cheap_b"], source_context),
                    _with_context(action_map["repair"], source_context),
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

        static_outcome = budget_runtime.step(
            state,
            _make_budget_traces(
                spec,
                context=target_context,
                phase="target-static-budget",
                episode=0,
                actions=(
                    _with_context(action_map["cheap_a"], target_context),
                    _with_context(action_map["cheap_b"], target_context),
                    _with_context(action_map["repair"], target_context),
                ),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        allocated_outcome = budget_runtime.step(
            state,
            _make_budget_traces(
                spec,
                context=target_context,
                phase="target-allocated-budget",
                episode=0,
                actions=(
                    _with_context(action_map["cheap_a"], target_context),
                    _with_context(action_map["repair"], target_context),
                ),
            ),
        )
        state = normalize_state(allocated_outcome.state)
        allocated_certificate = build_branch_selection_certificate(
            allocated_outcome.receipts,
            verifier_call_count=allocated_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(allocated_outcome.receipts), allocated_certificate))

        static_actions = (
            str(action_map["cheap_a"]["action"]),
            str(action_map["cheap_b"]["action"]),
            str(action_map["repair"]["action"]),
        )
        allocated_actions = (str(action_map["cheap_a"]["action"]), str(action_map["repair"]["action"]))
        budget_certificate = build_branch_budget_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            budget=TARGET_BUDGET,
            static_actions=static_actions,
            allocated_actions=allocated_actions,
            static_action_costs=tuple(int(action_map[key]["verifier_cost"]) for key in ("cheap_a", "cheap_b", "repair")),
            allocated_action_costs=tuple(int(action_map[key]["verifier_cost"]) for key in ("cheap_a", "repair")),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
            source_reject_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected
            ),
            source_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed),
            static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            allocated_receipt_hashes=tuple(receipt.receipt_hash for receipt in allocated_outcome.receipts),
            static_abstain_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in static_outcome.receipts if receipt.hard_result.abstained
            ),
            allocated_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in allocated_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            allocated_branch_selection_certificate_hash=allocated_certificate.certificate_hash,
            static_committed=static_outcome.committed,
            allocated_committed=allocated_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            allocated_verifier_call_count=allocated_outcome.verifier_calls,
            static_verifier_cost=static_outcome.verifier_cost,
            allocated_verifier_cost=allocated_outcome.verifier_cost,
            static_abstained_count=static_outcome.abstained_count,
            allocated_abstained_count=allocated_outcome.abstained_count,
        )
        budget_certificates.append(budget_certificate)

        rows.append(
            BranchBudgetDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                budget=TARGET_BUDGET,
                static_actions=budget_certificate.static_actions,
                allocated_actions=budget_certificate.allocated_actions,
                static_action_costs=budget_certificate.static_action_costs,
                allocated_action_costs=budget_certificate.allocated_action_costs,
                committed_target_action=spec.committed_action,
                static_budget_committed=static_outcome.committed,
                allocated_budget_committed=allocated_outcome.committed,
                static_verifier_cost=static_outcome.verifier_cost,
                allocated_verifier_cost=allocated_outcome.verifier_cost,
                static_abstained_count=static_outcome.abstained_count,
                allocated_abstained_count=allocated_outcome.abstained_count,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
                static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
                allocated_receipt_hashes=tuple(receipt.receipt_hash for receipt in allocated_outcome.receipts),
                source_branch_selection_certificate_hash=source_certificate.certificate_hash,
                static_branch_selection_certificate_hash=static_certificate.certificate_hash,
                allocated_branch_selection_certificate_hash=allocated_certificate.certificate_hash,
                budget_certificate_hash=budget_certificate.certificate_hash,
                same_budget=budget_certificate.same_budget,
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
    report = BranchBudgetTransferReport(
        schema_version="trwm.example.branch_budget_transfer.v1",
        experiment_id="branch_budget_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_abstained_count=sum(1 for receipt in all_receipts if receipt.hard_result.abstained),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        static_budget_success_count=sum(1 for row in rows if row.static_budget_committed),
        allocated_budget_success_count=sum(1 for row in rows if row.allocated_budget_committed),
        static_abstain_count=sum(row.static_abstained_count for row in rows),
        allocated_abstain_count=sum(row.allocated_abstained_count for row in rows),
        same_budget_allocation_count=sum(1 for row in rows if row.same_budget),
        branch_budget_certificate_count=len(budget_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_budget_certificates_valid=all(
            validate_branch_budget_certificate(certificate) for certificate in budget_certificates
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
        sources=BRANCH_BUDGET_SOURCES,
        learning=(
            "Past branch receipts can improve exploration by changing budget allocation: cheap repeated "
            "rejects are enough evidence to stop spending the whole budget there, but the higher-cost "
            "repair still commits only after hard verification."
        ),
    )
    transfer_certificate = build_branch_budget_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_budget_certificate_hashes=tuple(certificate.certificate_hash for certificate in budget_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_budget_transfer",
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
        claim_boundary=BRANCH_BUDGET_CLAIM_BOUNDARY,
        sources=BRANCH_BUDGET_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchBudgetTransferResult(
        report=report,
        branch_budget_transfer_certificate=transfer_certificate,
        branch_budget_certificates=tuple(budget_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_budget_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    budget: int,
    static_actions: tuple[str, ...],
    allocated_actions: tuple[str, ...],
    static_action_costs: tuple[int, ...],
    allocated_action_costs: tuple[int, ...],
    source_receipt_hashes: tuple[str, ...],
    source_reject_receipt_hashes: tuple[str, ...],
    source_commit_receipt_hashes: tuple[str, ...],
    static_receipt_hashes: tuple[str, ...],
    allocated_receipt_hashes: tuple[str, ...],
    static_abstain_receipt_hashes: tuple[str, ...],
    allocated_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    allocated_branch_selection_certificate_hash: str,
    static_committed: bool,
    allocated_committed: bool,
    static_verifier_call_count: int,
    allocated_verifier_call_count: int,
    static_verifier_cost: int,
    allocated_verifier_cost: int,
    static_abstained_count: int,
    allocated_abstained_count: int,
) -> BranchBudgetCertificate:
    return BranchBudgetCertificate(
        schema_version=BRANCH_BUDGET_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        budget_rule_id="receipt_bound_budget_allocation",
        budget_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        budget=budget,
        static_actions=static_actions,
        allocated_actions=allocated_actions,
        static_action_costs=static_action_costs,
        allocated_action_costs=allocated_action_costs,
        committed_target_action=spec.committed_action,
        source_receipt_hashes=source_receipt_hashes,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        static_receipt_hashes=static_receipt_hashes,
        allocated_receipt_hashes=allocated_receipt_hashes,
        static_abstain_receipt_hashes=static_abstain_receipt_hashes,
        allocated_commit_receipt_hashes=allocated_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        allocated_branch_selection_certificate_hash=allocated_branch_selection_certificate_hash,
        static_committed=static_committed,
        allocated_committed=allocated_committed,
        static_verifier_call_count=static_verifier_call_count,
        allocated_verifier_call_count=allocated_verifier_call_count,
        static_verifier_cost=static_verifier_cost,
        allocated_verifier_cost=allocated_verifier_cost,
        static_abstained_count=static_abstained_count,
        allocated_abstained_count=allocated_abstained_count,
        same_budget=budget == TARGET_BUDGET,
        budget_reason="avoid_repeated_cheap_rejects_to_admit_repair",
    )


def validate_branch_budget_certificate(
    certificate: BranchBudgetCertificate,
    row: BranchBudgetDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_BUDGET_CERTIFICATE_SCHEMA:
            return False
        if certificate.budget_rule_id != "receipt_bound_budget_allocation" or certificate.budget_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id):
            return False
        if certificate.budget != TARGET_BUDGET:
            return False
        if len(certificate.static_actions) != 3 or len(certificate.static_action_costs) != 3:
            return False
        if len(certificate.allocated_actions) != 2 or len(certificate.allocated_action_costs) != 2:
            return False
        if certificate.static_action_costs != (1, 1, 2):
            return False
        if certificate.allocated_action_costs != (1, 2):
            return False
        if certificate.committed_target_action != certificate.allocated_actions[-1]:
            return False
        if certificate.static_committed or not certificate.allocated_committed:
            return False
        if not certificate.same_budget:
            return False
        if certificate.static_verifier_call_count != 2 or certificate.allocated_verifier_call_count != 2:
            return False
        if certificate.static_verifier_cost != 2 or certificate.allocated_verifier_cost != TARGET_BUDGET:
            return False
        if certificate.static_abstained_count != 1 or certificate.allocated_abstained_count != 0:
            return False
        if len(certificate.source_receipt_hashes) != 3:
            return False
        if len(certificate.source_reject_receipt_hashes) != 2 or len(certificate.source_commit_receipt_hashes) != 1:
            return False
        if len(certificate.static_receipt_hashes) != 3 or len(certificate.allocated_receipt_hashes) != 2:
            return False
        if len(certificate.static_abstain_receipt_hashes) != 1 or len(certificate.allocated_commit_receipt_hashes) != 1:
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_reject_receipt_hashes,
            certificate.source_commit_receipt_hashes,
            certificate.static_receipt_hashes,
            certificate.allocated_receipt_hashes,
            certificate.static_abstain_receipt_hashes,
            certificate.allocated_commit_receipt_hashes,
            (
                certificate.source_branch_selection_certificate_hash,
                certificate.static_branch_selection_certificate_hash,
                certificate.allocated_branch_selection_certificate_hash,
            ),
        ):
            if any(not _is_hash(value) for value in values):
                return False
        if certificate.budget_reason != "avoid_repeated_cheap_rejects_to_admit_repair":
            return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.budget != certificate.budget:
                return False
            if row.static_actions != certificate.static_actions or row.allocated_actions != certificate.allocated_actions:
                return False
            if row.static_action_costs != certificate.static_action_costs:
                return False
            if row.allocated_action_costs != certificate.allocated_action_costs:
                return False
            if row.static_budget_committed != certificate.static_committed:
                return False
            if row.allocated_budget_committed != certificate.allocated_committed:
                return False
            if row.static_abstained_count != certificate.static_abstained_count:
                return False
            if row.allocated_abstained_count != certificate.allocated_abstained_count:
                return False
            if row.budget_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_budget_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_budget_transfer_certificate(
    report: BranchBudgetTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_budget_certificate_hashes: tuple[str, ...],
) -> BranchBudgetTransferCertificate:
    return BranchBudgetTransferCertificate(
        schema_version=BRANCH_BUDGET_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_budget_certificate_hashes=branch_budget_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        budget=TARGET_BUDGET,
        static_budget_success_count=report.static_budget_success_count,
        allocated_budget_success_count=report.allocated_budget_success_count,
        static_abstain_count=report.static_abstain_count,
        allocated_abstain_count=report.allocated_abstain_count,
        same_budget_allocation_count=report.same_budget_allocation_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_BUDGET_CLAIM_BOUNDARY,
    )


def validate_branch_budget_transfer_certificate(
    certificate: BranchBudgetTransferCertificate,
    report: BranchBudgetTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_BUDGET_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        if certificate.budget != TARGET_BUDGET:
            return False
        if not _is_hash(certificate.report_hash) or not _is_hash(certificate.ledger_head):
            return False
        if not _is_hash(certificate.memory_snapshot_hash):
            return False
        for values in (
            certificate.receipt_hashes,
            certificate.branch_selection_certificate_hashes,
            certificate.branch_budget_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 8:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_budget_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.static_budget_success_count != 0:
            return False
        if certificate.allocated_budget_success_count != certificate.domain_count:
            return False
        if certificate.static_abstain_count != certificate.domain_count:
            return False
        if certificate.allocated_abstain_count != 0:
            return False
        if certificate.same_budget_allocation_count != certificate.domain_count:
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
            if not report.all_branch_budget_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.static_abstain_count != certificate.static_abstain_count:
                return False
            if report.allocated_abstain_count != certificate.allocated_abstain_count:
                return False
        return certificate.certificate_hash == branch_budget_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_budget_certificate_hash(certificate: BranchBudgetCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchBudgetCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_budget_transfer_certificate_hash(
    certificate: BranchBudgetTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchBudgetTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchBudgetTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchBudgetTransferReport,
    transfer_certificate: BranchBudgetTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_budget_transfer_g1",
        claim_text=(
            "Past branch receipts can improve local target exploration by certifying a same-budget "
            "allocation that stops after one cheap repeated failure and admits the higher-cost repair."
        ),
        evidence_grade="G1",
        scope="branch_budget_transfer",
        requirements=(
            requirement(
                "branch_budget_transfer_certificate_valid",
                validate_branch_budget_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_budget_certificates_valid", report.all_branch_budget_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("static_budget_fails_all_domains", report.static_budget_success_count == 0),
            requirement("allocated_budget_succeeds_all_domains", report.allocated_budget_success_count == report.domain_count),
            requirement("static_abstains_all_domains", report.static_abstain_count == report.domain_count),
            requirement("allocated_abstains_no_domains", report.allocated_abstain_count == 0),
            requirement("same_budget_all_domains", report.same_budget_allocation_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "total_abstained_count": report.total_abstained_count,
            "static_budget_success_count": report.static_budget_success_count,
            "allocated_budget_success_count": report.allocated_budget_success_count,
            "static_abstain_count": report.static_abstain_count,
            "allocated_abstain_count": report.allocated_abstain_count,
        },
        boundary=BRANCH_BUDGET_CLAIM_BOUNDARY,
        sources=BRANCH_BUDGET_SOURCES,
    )


def _make_budget_traces(
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
            seeds=("branch-budget-transfer", spec.domain_id, context, phase, episode, action["action"]),
            model_version="branch.budget.transfer.v1",
        )
        for action in actions
    )


def _with_context(action: Mapping[str, Any], context: str) -> dict[str, Any]:
    return {**dict(action), "context": context}


def _budget_actions(spec: ExplorationDomainSpec) -> Mapping[str, Mapping[str, Any]]:
    cheap_a = {**dict(spec.actions[0]), "verifier_cost": 1}
    repair = {**dict(next(action for action in spec.actions if action.get("target_commit"))), "verifier_cost": 2}
    if spec.domain_id == "robotics_replan":
        cheap_b = {
            "domain": spec.domain_id,
            "action": "cheap_corner_retry",
            "utility": 9,
            "clearance": 0.08,
            "turn_rate": 0.88,
            "verifier_cost": 1,
        }
    elif spec.domain_id == "molecule_repair":
        cheap_b = {
            "domain": spec.domain_id,
            "action": "cheap_valence_retry",
            "utility": 9,
            "valence_ok": False,
            "strain": 0.24,
            "verifier_cost": 1,
        }
    elif spec.domain_id == "material_process":
        cheap_b = {
            "domain": spec.domain_id,
            "action": "cheap_flash_retry",
            "utility": 9,
            "thermal_gradient": 0.88,
            "phase_purity": 0.86,
            "verifier_cost": 1,
        }
    else:
        raise ValueError(f"unknown domain: {spec.domain_id}")
    return {"cheap_a": cheap_a, "cheap_b": cheap_b, "repair": repair}


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_budget_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
