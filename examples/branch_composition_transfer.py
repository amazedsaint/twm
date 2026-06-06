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


BRANCH_COMPOSITION_CERTIFICATE_SCHEMA = "trwm.branch_composition_certificate.v1"
BRANCH_COMPOSITION_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_composition_transfer_certificate.v1"
BRANCH_COMPOSITION_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://direct.mit.edu/books/monograph/2574/Adaptation-in-Natural-and-Artificial-SystemsAn",
    "https://journals.sagepub.com/doi/10.3233/AIC-1994-7104",
)
BRANCH_COMPOSITION_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows two receipt-bound past source "
    "branches can be used as auditable proposal-building blocks, and that a composed target proposal "
    "can beat static and single-fragment target proposals under the same one-call verifier budget. "
    "It is not a genetic-algorithm performance result, automatic program synthesis, statistical "
    "transfer learning, robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchCompositionCertificate:
    schema_version: str
    domain: str
    composition_rule_id: str
    composition_rule_version: str
    source_context_ids: tuple[str, ...]
    target_context_id: str
    fragment_keys: tuple[str, ...]
    source_committed_actions: tuple[str, ...]
    static_top_action: str
    component_only_actions: tuple[str, ...]
    composed_action: str
    committed_target_action: str
    source_receipt_hashes: tuple[str, ...]
    source_commit_receipt_hashes: tuple[str, ...]
    source_reject_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    component_a_receipt_hashes: tuple[str, ...]
    component_b_receipt_hashes: tuple[str, ...]
    composed_receipt_hashes: tuple[str, ...]
    target_branch_selection_certificate_hashes: tuple[str, ...]
    static_committed: bool
    component_a_committed: bool
    component_b_committed: bool
    composed_committed: bool
    static_verifier_call_count: int
    component_a_verifier_call_count: int
    component_b_verifier_call_count: int
    composed_verifier_call_count: int
    same_budget: bool
    composition_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_COMPOSITION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch composition certificate schema: {self.schema_version}")
        for field_name in (
            "source_context_ids",
            "fragment_keys",
            "source_committed_actions",
            "component_only_actions",
            "source_receipt_hashes",
            "source_commit_receipt_hashes",
            "source_reject_receipt_hashes",
            "source_branch_selection_certificate_hashes",
            "static_receipt_hashes",
            "component_a_receipt_hashes",
            "component_b_receipt_hashes",
            "composed_receipt_hashes",
            "target_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_composition_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchCompositionDomainReport:
    domain: str
    source_contexts: tuple[str, ...]
    target_context: str
    fragment_keys: tuple[str, ...]
    source_committed_actions: tuple[str, ...]
    static_top_action: str
    component_a_top_action: str
    component_b_top_action: str
    composed_top_action: str
    committed_target_action: str
    static_budget_committed: bool
    component_a_budget_committed: bool
    component_b_budget_committed: bool
    composed_budget_committed: bool
    source_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    component_a_receipt_hashes: tuple[str, ...]
    component_b_receipt_hashes: tuple[str, ...]
    composed_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hashes: tuple[str, ...]
    target_branch_selection_certificate_hashes: tuple[str, ...]
    composition_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchCompositionTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchCompositionDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_branch_pair_count: int
    static_budget_success_count: int
    component_only_budget_success_count: int
    composed_budget_success_count: int
    same_budget_composition_count: int
    branch_composition_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_composition_certificates_valid: bool
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
class BranchCompositionTransferCertificate:
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
    branch_composition_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_branch_pair_count: int
    static_budget_success_count: int
    component_only_budget_success_count: int
    composed_budget_success_count: int
    same_budget_composition_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_COMPOSITION_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch composition transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_composition_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_composition_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchCompositionTransferResult(CertifiedExampleResult):
    report: BranchCompositionTransferReport
    branch_composition_transfer_certificate: BranchCompositionTransferCertificate
    branch_composition_certificates: tuple[BranchCompositionCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_composition_transfer_experiment() -> BranchCompositionTransferReport:
    return run_branch_composition_transfer_certified_experiment().report


def run_branch_composition_transfer_certified_experiment() -> CertifiedBranchCompositionTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[BranchCompositionDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    composition_certificates: list[BranchCompositionCertificate] = []

    for spec in DOMAIN_SPECS:
        spec_actions = _composition_actions(spec)
        source_receipts: list[Receipt] = []
        source_commit_receipts: list[Receipt] = []
        source_reject_receipts: list[Receipt] = []
        source_branch_cert_hashes: list[str] = []
        source_context_ids = (
            f"{spec.domain_id}:source:fragment_a",
            f"{spec.domain_id}:source:fragment_b",
        )

        for context_id, source_action in zip(source_context_ids, (spec_actions["source_a"], spec_actions["source_b"])):
            outcome = runtime.step(
                state,
                _make_composition_traces(
                    spec,
                    context=context_id,
                    phase="source-fragment",
                    episode=0,
                    actions=(_with_context(spec.actions[0], context_id), _with_context(source_action, context_id)),
                ),
            )
            state = normalize_state(outcome.state)
            certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), certificate))
            source_branch_cert_hashes.append(certificate.certificate_hash)
            memory.update_branch(outcome.receipts, certificate)
            source_receipts.extend(outcome.receipts)
            source_commit_receipts.extend(receipt for receipt in outcome.receipts if receipt.committed)
            source_reject_receipts.extend(receipt for receipt in outcome.receipts if receipt.hard_result.rejected)

        target_context = f"{spec.domain_id}:target:composition"
        target_runs = []
        for phase, action in (
            ("target-static-budget-one", spec.actions[0]),
            ("target-component-a-budget-one", spec_actions["component_a"]),
            ("target-component-b-budget-one", spec_actions["component_b"]),
            ("target-composed-budget-one", spec_actions["composed"]),
        ):
            outcome = runtime.step(
                state,
                _make_composition_traces(
                    spec,
                    context=target_context,
                    phase=phase,
                    episode=0,
                    actions=(_with_context(action, target_context),),
                ),
            )
            if phase == "target-composed-budget-one":
                state = normalize_state(outcome.state)
            certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), certificate))
            target_runs.append((outcome, certificate))

        static_run, component_a_run, component_b_run, composed_run = target_runs
        composition_certificate = build_branch_composition_certificate(
            spec,
            source_context_ids=source_context_ids,
            target_context_id=target_context,
            fragment_keys=spec_actions["fragment_keys"],
            source_committed_actions=(
                str(spec_actions["source_a"]["action"]),
                str(spec_actions["source_b"]["action"]),
            ),
            static_top_action=str(spec.actions[0]["action"]),
            component_only_actions=(
                str(spec_actions["component_a"]["action"]),
                str(spec_actions["component_b"]["action"]),
            ),
            composed_action=str(spec_actions["composed"]["action"]),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_receipts),
            source_commit_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_commit_receipts),
            source_reject_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_reject_receipts),
            source_branch_selection_certificate_hashes=tuple(source_branch_cert_hashes),
            static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_run[0].receipts),
            component_a_receipt_hashes=tuple(receipt.receipt_hash for receipt in component_a_run[0].receipts),
            component_b_receipt_hashes=tuple(receipt.receipt_hash for receipt in component_b_run[0].receipts),
            composed_receipt_hashes=tuple(receipt.receipt_hash for receipt in composed_run[0].receipts),
            target_branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in target_runs),
            static_committed=static_run[0].committed,
            component_a_committed=component_a_run[0].committed,
            component_b_committed=component_b_run[0].committed,
            composed_committed=composed_run[0].committed,
            static_verifier_call_count=static_run[0].verifier_calls,
            component_a_verifier_call_count=component_a_run[0].verifier_calls,
            component_b_verifier_call_count=component_b_run[0].verifier_calls,
            composed_verifier_call_count=composed_run[0].verifier_calls,
        )
        composition_certificates.append(composition_certificate)

        rows.append(
            BranchCompositionDomainReport(
                domain=spec.domain_id,
                source_contexts=source_context_ids,
                target_context=target_context,
                fragment_keys=composition_certificate.fragment_keys,
                source_committed_actions=composition_certificate.source_committed_actions,
                static_top_action=composition_certificate.static_top_action,
                component_a_top_action=composition_certificate.component_only_actions[0],
                component_b_top_action=composition_certificate.component_only_actions[1],
                composed_top_action=composition_certificate.composed_action,
                committed_target_action=composition_certificate.committed_target_action,
                static_budget_committed=static_run[0].committed,
                component_a_budget_committed=component_a_run[0].committed,
                component_b_budget_committed=component_b_run[0].committed,
                composed_budget_committed=composed_run[0].committed,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_receipts),
                static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_run[0].receipts),
                component_a_receipt_hashes=tuple(receipt.receipt_hash for receipt in component_a_run[0].receipts),
                component_b_receipt_hashes=tuple(receipt.receipt_hash for receipt in component_b_run[0].receipts),
                composed_receipt_hashes=tuple(receipt.receipt_hash for receipt in composed_run[0].receipts),
                source_branch_selection_certificate_hashes=tuple(source_branch_cert_hashes),
                target_branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in target_runs),
                composition_certificate_hash=composition_certificate.certificate_hash,
                same_budget=composition_certificate.same_budget,
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
    report = BranchCompositionTransferReport(
        schema_version="trwm.example.branch_composition_transfer.v1",
        experiment_id="branch_composition_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_branch_pair_count=len(DOMAIN_SPECS),
        static_budget_success_count=sum(1 for row in rows if row.static_budget_committed),
        component_only_budget_success_count=sum(
            int(row.component_a_budget_committed) + int(row.component_b_budget_committed) for row in rows
        ),
        composed_budget_success_count=sum(1 for row in rows if row.composed_budget_committed),
        same_budget_composition_count=sum(1 for row in rows if row.same_budget),
        branch_composition_certificate_count=len(composition_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_composition_certificates_valid=all(
            validate_branch_composition_certificate(certificate) for certificate in composition_certificates
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
        sources=BRANCH_COMPOSITION_SOURCES,
        learning=(
            "Composition needs a substrate boundary between proposal construction and commit authority: "
            "past branch receipts can justify combining two compatible fragments, but static and "
            "single-fragment proposals still fail until the composed candidate passes the hard verifier."
        ),
    )
    transfer_certificate = build_branch_composition_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_composition_certificate_hashes=tuple(certificate.certificate_hash for certificate in composition_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_composition_transfer",
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
        claim_boundary=BRANCH_COMPOSITION_CLAIM_BOUNDARY,
        sources=BRANCH_COMPOSITION_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchCompositionTransferResult(
        report=report,
        branch_composition_transfer_certificate=transfer_certificate,
        branch_composition_certificates=tuple(composition_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_composition_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_ids: tuple[str, ...],
    target_context_id: str,
    fragment_keys: tuple[str, ...],
    source_committed_actions: tuple[str, ...],
    static_top_action: str,
    component_only_actions: tuple[str, ...],
    composed_action: str,
    source_receipt_hashes: tuple[str, ...],
    source_commit_receipt_hashes: tuple[str, ...],
    source_reject_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hashes: tuple[str, ...],
    static_receipt_hashes: tuple[str, ...],
    component_a_receipt_hashes: tuple[str, ...],
    component_b_receipt_hashes: tuple[str, ...],
    composed_receipt_hashes: tuple[str, ...],
    target_branch_selection_certificate_hashes: tuple[str, ...],
    static_committed: bool,
    component_a_committed: bool,
    component_b_committed: bool,
    composed_committed: bool,
    static_verifier_call_count: int,
    component_a_verifier_call_count: int,
    component_b_verifier_call_count: int,
    composed_verifier_call_count: int,
) -> BranchCompositionCertificate:
    return BranchCompositionCertificate(
        schema_version=BRANCH_COMPOSITION_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        composition_rule_id="receipt_bound_fragment_pair",
        composition_rule_version="1.0",
        source_context_ids=source_context_ids,
        target_context_id=target_context_id,
        fragment_keys=fragment_keys,
        source_committed_actions=source_committed_actions,
        static_top_action=static_top_action,
        component_only_actions=component_only_actions,
        composed_action=composed_action,
        committed_target_action=spec.committed_action,
        source_receipt_hashes=source_receipt_hashes,
        source_commit_receipt_hashes=source_commit_receipt_hashes,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        source_branch_selection_certificate_hashes=source_branch_selection_certificate_hashes,
        static_receipt_hashes=static_receipt_hashes,
        component_a_receipt_hashes=component_a_receipt_hashes,
        component_b_receipt_hashes=component_b_receipt_hashes,
        composed_receipt_hashes=composed_receipt_hashes,
        target_branch_selection_certificate_hashes=target_branch_selection_certificate_hashes,
        static_committed=static_committed,
        component_a_committed=component_a_committed,
        component_b_committed=component_b_committed,
        composed_committed=composed_committed,
        static_verifier_call_count=static_verifier_call_count,
        component_a_verifier_call_count=component_a_verifier_call_count,
        component_b_verifier_call_count=component_b_verifier_call_count,
        composed_verifier_call_count=composed_verifier_call_count,
        same_budget=(
            static_verifier_call_count
            == component_a_verifier_call_count
            == component_b_verifier_call_count
            == composed_verifier_call_count
            == 1
        ),
        composition_reason="two_source_fragments_cover_distinct_hard_gate_keys",
    )


def validate_branch_composition_certificate(
    certificate: BranchCompositionCertificate,
    row: BranchCompositionDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_COMPOSITION_CERTIFICATE_SCHEMA:
            return False
        if not _nonempty(certificate.domain):
            return False
        if certificate.composition_rule_id != "receipt_bound_fragment_pair" or certificate.composition_rule_version != "1.0":
            return False
        if len(certificate.source_context_ids) != 2 or len(certificate.fragment_keys) != 2:
            return False
        if len(certificate.source_committed_actions) != 2 or len(certificate.component_only_actions) != 2:
            return False
        if len(set(certificate.fragment_keys)) != 2:
            return False
        if any(not _nonempty(value) for value in (*certificate.source_context_ids, certificate.target_context_id)):
            return False
        if any(not _nonempty(value) for value in (*certificate.source_committed_actions, *certificate.component_only_actions)):
            return False
        if not _nonempty(certificate.static_top_action) or not _nonempty(certificate.composed_action):
            return False
        if certificate.composed_action != certificate.committed_target_action:
            return False
        if certificate.static_committed or certificate.component_a_committed or certificate.component_b_committed:
            return False
        if not certificate.composed_committed:
            return False
        if not certificate.same_budget:
            return False
        if (
            certificate.static_verifier_call_count,
            certificate.component_a_verifier_call_count,
            certificate.component_b_verifier_call_count,
            certificate.composed_verifier_call_count,
        ) != (1, 1, 1, 1):
            return False
        if len(certificate.source_receipt_hashes) != 4:
            return False
        if len(certificate.source_commit_receipt_hashes) != 2 or len(certificate.source_reject_receipt_hashes) != 2:
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_commit_receipt_hashes,
            certificate.source_reject_receipt_hashes,
            certificate.source_branch_selection_certificate_hashes,
            certificate.static_receipt_hashes,
            certificate.component_a_receipt_hashes,
            certificate.component_b_receipt_hashes,
            certificate.composed_receipt_hashes,
            certificate.target_branch_selection_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.source_branch_selection_certificate_hashes) != 2:
            return False
        if len(certificate.target_branch_selection_certificate_hashes) != 4:
            return False
        if len(certificate.static_receipt_hashes) != 1:
            return False
        if len(certificate.component_a_receipt_hashes) != 1:
            return False
        if len(certificate.component_b_receipt_hashes) != 1:
            return False
        if len(certificate.composed_receipt_hashes) != 1:
            return False
        if certificate.composition_reason != "two_source_fragments_cover_distinct_hard_gate_keys":
            return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_contexts != certificate.source_context_ids or row.target_context != certificate.target_context_id:
                return False
            if row.fragment_keys != certificate.fragment_keys:
                return False
            if row.source_committed_actions != certificate.source_committed_actions:
                return False
            if row.static_top_action != certificate.static_top_action:
                return False
            if (row.component_a_top_action, row.component_b_top_action) != certificate.component_only_actions:
                return False
            if row.composed_top_action != certificate.composed_action:
                return False
            if row.committed_target_action != certificate.committed_target_action:
                return False
            if row.static_budget_committed != certificate.static_committed:
                return False
            if row.component_a_budget_committed != certificate.component_a_committed:
                return False
            if row.component_b_budget_committed != certificate.component_b_committed:
                return False
            if row.composed_budget_committed != certificate.composed_committed:
                return False
            if row.composition_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_composition_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_composition_transfer_certificate(
    report: BranchCompositionTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_composition_certificate_hashes: tuple[str, ...],
) -> BranchCompositionTransferCertificate:
    return BranchCompositionTransferCertificate(
        schema_version=BRANCH_COMPOSITION_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_composition_certificate_hashes=branch_composition_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_branch_pair_count=report.source_branch_pair_count,
        static_budget_success_count=report.static_budget_success_count,
        component_only_budget_success_count=report.component_only_budget_success_count,
        composed_budget_success_count=report.composed_budget_success_count,
        same_budget_composition_count=report.same_budget_composition_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_COMPOSITION_CLAIM_BOUNDARY,
    )


def validate_branch_composition_transfer_certificate(
    certificate: BranchCompositionTransferCertificate,
    report: BranchCompositionTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_COMPOSITION_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_composition_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.branch_composition_certificate_hashes) != certificate.domain_count:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 8:
            return False
        if certificate.source_branch_pair_count != certificate.domain_count:
            return False
        if certificate.static_budget_success_count != 0:
            return False
        if certificate.component_only_budget_success_count != 0:
            return False
        if certificate.composed_budget_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_composition_count != certificate.domain_count:
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
            if not report.all_branch_composition_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.static_budget_success_count != certificate.static_budget_success_count:
                return False
            if report.component_only_budget_success_count != certificate.component_only_budget_success_count:
                return False
            if report.composed_budget_success_count != certificate.composed_budget_success_count:
                return False
        return certificate.certificate_hash == branch_composition_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_composition_certificate_hash(
    certificate: BranchCompositionCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCompositionCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_composition_transfer_certificate_hash(
    certificate: BranchCompositionTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCompositionTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchCompositionTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchCompositionTransferReport,
    transfer_certificate: BranchCompositionTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_composition_transfer_g1",
        claim_text=(
            "Two receipt-bound branches of the past can improve local target exploration by composing "
            "distinct verifier-relevant fragments, while static and single-fragment branches fail under "
            "the same verifier budget."
        ),
        evidence_grade="G1",
        scope="branch_composition_transfer",
        requirements=(
            requirement(
                "branch_composition_transfer_certificate_valid",
                validate_branch_composition_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_composition_certificates_valid", report.all_branch_composition_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_branch_pair_per_domain", report.source_branch_pair_count == report.domain_count),
            requirement("static_budget_fails_all_domains", report.static_budget_success_count == 0),
            requirement("component_only_budget_fails_all_domains", report.component_only_budget_success_count == 0),
            requirement("composed_budget_succeeds_all_domains", report.composed_budget_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_composition_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_branch_pair_count": report.source_branch_pair_count,
            "static_budget_success_count": report.static_budget_success_count,
            "component_only_budget_success_count": report.component_only_budget_success_count,
            "composed_budget_success_count": report.composed_budget_success_count,
            "same_budget_composition_count": report.same_budget_composition_count,
        },
        boundary=BRANCH_COMPOSITION_CLAIM_BOUNDARY,
        sources=BRANCH_COMPOSITION_SOURCES,
    )


def _make_composition_traces(
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
            seeds=("branch-composition-transfer", spec.domain_id, context, phase, episode, action["action"]),
            model_version="branch.composition.transfer.v1",
        )
        for action in actions
    )


def _with_context(action: Mapping[str, Any], context: str) -> dict[str, Any]:
    return {**dict(action), "context": context}


def _composition_actions(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "fragment_keys": ("clearance", "turn_rate"),
            "source_a": {
                "domain": spec.domain_id,
                "action": "clearance_fragment_branch",
                "utility": 8,
                "clearance": 0.34,
                "turn_rate": 0.50,
            },
            "source_b": {
                "domain": spec.domain_id,
                "action": "turn_rate_fragment_branch",
                "utility": 8,
                "clearance": 0.31,
                "turn_rate": 0.40,
            },
            "component_a": {
                "domain": spec.domain_id,
                "action": "clearance_only_target",
                "utility": 9,
                "clearance": 0.34,
                "turn_rate": 0.90,
            },
            "component_b": {
                "domain": spec.domain_id,
                "action": "turn_rate_only_target",
                "utility": 9,
                "clearance": 0.05,
                "turn_rate": 0.40,
            },
            "composed": {
                "domain": spec.domain_id,
                "action": spec.committed_action,
                "utility": 9,
                "clearance": 0.34,
                "turn_rate": 0.40,
                "target_commit": True,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "fragment_keys": ("valence_ok", "strain"),
            "source_a": {
                "domain": spec.domain_id,
                "action": "valence_fragment_branch",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.22,
            },
            "source_b": {
                "domain": spec.domain_id,
                "action": "strain_fragment_branch",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.12,
            },
            "component_a": {
                "domain": spec.domain_id,
                "action": "valence_only_target",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.55,
            },
            "component_b": {
                "domain": spec.domain_id,
                "action": "strain_only_target",
                "utility": 9,
                "valence_ok": False,
                "strain": 0.12,
            },
            "composed": {
                "domain": spec.domain_id,
                "action": spec.committed_action,
                "utility": 9,
                "valence_ok": True,
                "strain": 0.12,
                "target_commit": True,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "fragment_keys": ("thermal_gradient", "phase_purity"),
            "source_a": {
                "domain": spec.domain_id,
                "action": "thermal_fragment_branch",
                "utility": 8,
                "thermal_gradient": 0.42,
                "phase_purity": 0.93,
            },
            "source_b": {
                "domain": spec.domain_id,
                "action": "phase_fragment_branch",
                "utility": 8,
                "thermal_gradient": 0.35,
                "phase_purity": 0.96,
            },
            "component_a": {
                "domain": spec.domain_id,
                "action": "thermal_only_target",
                "utility": 9,
                "thermal_gradient": 0.42,
                "phase_purity": 0.82,
            },
            "component_b": {
                "domain": spec.domain_id,
                "action": "phase_only_target",
                "utility": 9,
                "thermal_gradient": 0.90,
                "phase_purity": 0.96,
            },
            "composed": {
                "domain": spec.domain_id,
                "action": spec.committed_action,
                "utility": 9,
                "thermal_gradient": 0.42,
                "phase_purity": 0.96,
                "target_commit": True,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_composition_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
