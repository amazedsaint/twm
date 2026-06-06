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


BRANCH_ROBUSTNESS_CERTIFICATE_SCHEMA = "trwm.branch_robustness_certificate.v1"
BRANCH_ROBUSTNESS_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_robustness_transfer_certificate.v1"
BRANCH_ROBUSTNESS_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1287/moor.23.4.769",
)
BRANCH_ROBUSTNESS_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound uncertainty-set "
    "coverage can separate brittle source-valid branches from robust source branches before target "
    "exploration under a matched one-call verifier budget. It is not robust optimization, a worst-case "
    "guarantee, distributional robustness, robotics safety, chemistry, materials discovery, or scientific "
    "autonomy evidence."
)


@dataclass(frozen=True)
class BranchRobustnessCertificate:
    schema_version: str
    domain: str
    robustness_rule_id: str
    robustness_rule_version: str
    uncertainty_set_id: str
    variant_ids: tuple[str, ...]
    source_context_ids: tuple[str, ...]
    target_context_id: str
    brittle_source_action: str
    robust_source_action: str
    static_target_action: str
    robust_target_action: str
    brittle_source_margin: float
    robust_source_margins: tuple[float, ...]
    min_robust_source_margin: float
    static_target_margin: float
    robust_target_margin: float
    source_brittle_receipt_hashes: tuple[str, ...]
    source_robust_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    robust_target_receipt_hashes: tuple[str, ...]
    robust_target_commit_receipt_hashes: tuple[str, ...]
    source_brittle_branch_selection_certificate_hash: str
    source_robust_branch_selection_certificate_hashes: tuple[str, ...]
    static_branch_selection_certificate_hash: str
    robust_branch_selection_certificate_hash: str
    source_brittle_committed_count: int
    source_robust_variant_success_count: int
    static_committed: bool
    robust_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    robust_verifier_call_count: int
    same_budget: bool
    robustness_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_ROBUSTNESS_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch robustness certificate schema: {self.schema_version}")
        for field_name in (
            "variant_ids",
            "source_context_ids",
            "robust_source_margins",
            "source_brittle_receipt_hashes",
            "source_robust_receipt_hashes",
            "static_target_receipt_hashes",
            "robust_target_receipt_hashes",
            "robust_target_commit_receipt_hashes",
            "source_robust_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "brittle_source_margin",
            "min_robust_source_margin",
            "static_target_margin",
            "robust_target_margin",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        object.__setattr__(self, "robust_source_margins", tuple(float(value) for value in self.robust_source_margins))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_robustness_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchRobustnessDomainReport:
    domain: str
    uncertainty_set_id: str
    variant_ids: tuple[str, ...]
    source_contexts: tuple[str, ...]
    target_context: str
    brittle_source_action: str
    robust_source_action: str
    static_target_action: str
    robust_target_action: str
    brittle_source_margin: float
    robust_source_margins: tuple[float, ...]
    min_robust_source_margin: float
    static_target_margin: float
    robust_target_margin: float
    source_brittle_committed_count: int
    source_robust_variant_success_count: int
    static_committed: bool
    robust_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    robust_verifier_call_count: int
    source_brittle_receipt_hashes: tuple[str, ...]
    source_robust_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    robust_target_receipt_hashes: tuple[str, ...]
    branch_robustness_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchRobustnessTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchRobustnessDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_brittle_success_count: int
    source_robust_variant_success_count: int
    static_success_count: int
    robust_success_count: int
    same_budget_robust_count: int
    branch_robustness_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_robustness_certificates_valid: bool
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
class BranchRobustnessTransferCertificate:
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
    branch_robustness_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_brittle_success_count: int
    source_robust_variant_success_count: int
    static_success_count: int
    robust_success_count: int
    same_budget_robust_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_ROBUSTNESS_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch robustness transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_robustness_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_robustness_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchRobustnessTransferResult(CertifiedExampleResult):
    report: BranchRobustnessTransferReport
    branch_robustness_transfer_certificate: BranchRobustnessTransferCertificate
    branch_robustness_certificates: tuple[BranchRobustnessCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_robustness_transfer_experiment() -> BranchRobustnessTransferReport:
    return run_branch_robustness_transfer_certified_experiment().report


def run_branch_robustness_transfer_certified_experiment() -> CertifiedBranchRobustnessTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchRobustnessDomainReport] = []
    robustness_certificates: list[BranchRobustnessCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_robustness_plan(spec)
        variant_ids = tuple(str(value) for value in plan["variant_ids"])
        source_contexts = (
            f"{spec.domain_id}:source:robustness:brittle",
            *(f"{spec.domain_id}:source:robustness:{variant_id}" for variant_id in variant_ids),
        )
        target_context = f"{spec.domain_id}:target:robustness"

        brittle_outcome = runtime.step(
            state,
            _make_robustness_traces(
                spec,
                context=source_contexts[0],
                phase="source-brittle",
                actions=(plan["source_brittle"],),
            ),
        )
        state = normalize_state(brittle_outcome.state)
        brittle_selection = build_branch_selection_certificate(
            brittle_outcome.receipts,
            verifier_call_count=brittle_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(brittle_outcome.receipts), brittle_selection))
        memory.update_branch(brittle_outcome.receipts, brittle_selection)

        robust_outcomes = []
        robust_selections = []
        for source_context, robust_action in zip(source_contexts[1:], plan["source_robust_variants"]):
            outcome = runtime.step(
                state,
                _make_robustness_traces(
                    spec,
                    context=source_context,
                    phase="source-robust-variant",
                    actions=(robust_action,),
                ),
            )
            state = normalize_state(outcome.state)
            selection = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), selection))
            memory.update_branch(outcome.receipts, selection)
            robust_outcomes.append(outcome)
            robust_selections.append(selection)

        static_outcome = runtime.step(
            state,
            _make_robustness_traces(
                spec,
                context=target_context,
                phase="target-static-brittle",
                actions=(plan["target_static"],),
            ),
        )
        static_selection = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        robust_outcome = runtime.step(
            state,
            _make_robustness_traces(
                spec,
                context=target_context,
                phase="target-robust",
                actions=(plan["target_robust"],),
            ),
        )
        state = normalize_state(robust_outcome.state)
        robust_selection = build_branch_selection_certificate(
            robust_outcome.receipts,
            verifier_call_count=robust_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(robust_outcome.receipts), robust_selection))

        robust_margins = tuple(_domain_margin(spec, action) for action in plan["source_robust_variants"])
        certificate = build_branch_robustness_certificate(
            spec,
            uncertainty_set_id=str(plan["uncertainty_set_id"]),
            variant_ids=variant_ids,
            source_context_ids=source_contexts,
            target_context_id=target_context,
            brittle_source_action=str(plan["source_brittle"]["action"]),
            robust_source_action=str(plan["robust_source_action"]),
            static_target_action=str(plan["target_static"]["action"]),
            robust_target_action=str(plan["target_robust"]["action"]),
            brittle_source_margin=_domain_margin(spec, plan["source_brittle"]),
            robust_source_margins=robust_margins,
            min_robust_source_margin=min(robust_margins),
            static_target_margin=_domain_margin(spec, plan["target_static"]),
            robust_target_margin=_domain_margin(spec, plan["target_robust"]),
            source_brittle_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in brittle_outcome.receipts if receipt.committed
            ),
            source_robust_receipt_hashes=tuple(
                receipt.receipt_hash
                for outcome in robust_outcomes
                for receipt in outcome.receipts
                if receipt.committed
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            robust_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in robust_outcome.receipts),
            robust_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in robust_outcome.receipts if receipt.committed
            ),
            source_brittle_branch_selection_certificate_hash=brittle_selection.certificate_hash,
            source_robust_branch_selection_certificate_hashes=tuple(
                selection.certificate_hash for selection in robust_selections
            ),
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            robust_branch_selection_certificate_hash=robust_selection.certificate_hash,
            source_brittle_committed_count=1 if brittle_outcome.committed else 0,
            source_robust_variant_success_count=sum(1 for outcome in robust_outcomes if outcome.committed),
            static_committed=static_outcome.committed,
            robust_committed=robust_outcome.committed,
            source_verifier_call_count=brittle_outcome.verifier_calls + sum(outcome.verifier_calls for outcome in robust_outcomes),
            static_verifier_call_count=static_outcome.verifier_calls,
            robust_verifier_call_count=robust_outcome.verifier_calls,
        )
        robustness_certificates.append(certificate)
        rows.append(
            BranchRobustnessDomainReport(
                domain=spec.domain_id,
                uncertainty_set_id=certificate.uncertainty_set_id,
                variant_ids=certificate.variant_ids,
                source_contexts=certificate.source_context_ids,
                target_context=certificate.target_context_id,
                brittle_source_action=certificate.brittle_source_action,
                robust_source_action=certificate.robust_source_action,
                static_target_action=certificate.static_target_action,
                robust_target_action=certificate.robust_target_action,
                brittle_source_margin=certificate.brittle_source_margin,
                robust_source_margins=certificate.robust_source_margins,
                min_robust_source_margin=certificate.min_robust_source_margin,
                static_target_margin=certificate.static_target_margin,
                robust_target_margin=certificate.robust_target_margin,
                source_brittle_committed_count=certificate.source_brittle_committed_count,
                source_robust_variant_success_count=certificate.source_robust_variant_success_count,
                static_committed=certificate.static_committed,
                robust_committed=certificate.robust_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                robust_verifier_call_count=certificate.robust_verifier_call_count,
                source_brittle_receipt_hashes=certificate.source_brittle_receipt_hashes,
                source_robust_receipt_hashes=certificate.source_robust_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                robust_target_receipt_hashes=certificate.robust_target_receipt_hashes,
                branch_robustness_certificate_hash=certificate.certificate_hash,
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

    report = BranchRobustnessTransferReport(
        schema_version="trwm.example.branch_robustness_transfer.v1",
        experiment_id="branch_robustness_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_brittle_success_count=sum(row.source_brittle_committed_count for row in rows),
        source_robust_variant_success_count=sum(row.source_robust_variant_success_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        robust_success_count=sum(1 for row in rows if row.robust_committed),
        same_budget_robust_count=sum(1 for row in rows if row.same_budget),
        branch_robustness_certificate_count=len(robustness_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_robustness_certificates_valid=all(
            validate_branch_robustness_certificate(certificate, row)
            for certificate, row in zip(robustness_certificates, rows)
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
        sources=BRANCH_ROBUSTNESS_SOURCES,
        learning=(
            "Robust branch reuse separates nominal source validity from uncertainty-set coverage. A brittle "
            "source commit stays in memory, but target priority comes only from a certificate that binds "
            "variant receipts, positive margins across the uncertainty set, and a fresh target commit receipt."
        ),
    )
    transfer_certificate = build_branch_robustness_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_robustness_certificate_hashes=tuple(
            certificate.certificate_hash for certificate in robustness_certificates
        ),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_robustness_transfer",
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
        claim_boundary=BRANCH_ROBUSTNESS_CLAIM_BOUNDARY,
        sources=BRANCH_ROBUSTNESS_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchRobustnessTransferResult(
        report=report,
        branch_robustness_transfer_certificate=transfer_certificate,
        branch_robustness_certificates=tuple(robustness_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_robustness_certificate(
    spec: ExplorationDomainSpec,
    *,
    uncertainty_set_id: str,
    variant_ids: tuple[str, ...],
    source_context_ids: tuple[str, ...],
    target_context_id: str,
    brittle_source_action: str,
    robust_source_action: str,
    static_target_action: str,
    robust_target_action: str,
    brittle_source_margin: float,
    robust_source_margins: tuple[float, ...],
    min_robust_source_margin: float,
    static_target_margin: float,
    robust_target_margin: float,
    source_brittle_receipt_hashes: tuple[str, ...],
    source_robust_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    robust_target_receipt_hashes: tuple[str, ...],
    robust_target_commit_receipt_hashes: tuple[str, ...],
    source_brittle_branch_selection_certificate_hash: str,
    source_robust_branch_selection_certificate_hashes: tuple[str, ...],
    static_branch_selection_certificate_hash: str,
    robust_branch_selection_certificate_hash: str,
    source_brittle_committed_count: int,
    source_robust_variant_success_count: int,
    static_committed: bool,
    robust_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    robust_verifier_call_count: int,
) -> BranchRobustnessCertificate:
    return BranchRobustnessCertificate(
        schema_version=BRANCH_ROBUSTNESS_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        robustness_rule_id="receipt_bound_uncertainty_set_coverage",
        robustness_rule_version="1.0",
        uncertainty_set_id=uncertainty_set_id,
        variant_ids=variant_ids,
        source_context_ids=source_context_ids,
        target_context_id=target_context_id,
        brittle_source_action=brittle_source_action,
        robust_source_action=robust_source_action,
        static_target_action=static_target_action,
        robust_target_action=robust_target_action,
        brittle_source_margin=brittle_source_margin,
        robust_source_margins=robust_source_margins,
        min_robust_source_margin=min_robust_source_margin,
        static_target_margin=static_target_margin,
        robust_target_margin=robust_target_margin,
        source_brittle_receipt_hashes=source_brittle_receipt_hashes,
        source_robust_receipt_hashes=source_robust_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        robust_target_receipt_hashes=robust_target_receipt_hashes,
        robust_target_commit_receipt_hashes=robust_target_commit_receipt_hashes,
        source_brittle_branch_selection_certificate_hash=source_brittle_branch_selection_certificate_hash,
        source_robust_branch_selection_certificate_hashes=source_robust_branch_selection_certificate_hashes,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        robust_branch_selection_certificate_hash=robust_branch_selection_certificate_hash,
        source_brittle_committed_count=source_brittle_committed_count,
        source_robust_variant_success_count=source_robust_variant_success_count,
        static_committed=static_committed,
        robust_committed=robust_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        robust_verifier_call_count=robust_verifier_call_count,
        same_budget=static_verifier_call_count == robust_verifier_call_count == 1,
        robustness_reason="robust_source_covers_all_uncertainty_variants",
    )


def validate_branch_robustness_certificate(
    certificate: BranchRobustnessCertificate,
    row: BranchRobustnessDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_ROBUSTNESS_CERTIFICATE_SCHEMA:
            return False
        if certificate.robustness_rule_id != "receipt_bound_uncertainty_set_coverage":
            return False
        if certificate.robustness_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.uncertainty_set_id,
            certificate.target_context_id,
            certificate.brittle_source_action,
            certificate.robust_source_action,
            certificate.static_target_action,
            certificate.robust_target_action,
        ):
            if not _nonempty(value):
                return False
        if len(certificate.variant_ids) != 3 or len(set(certificate.variant_ids)) != 3:
            return False
        if len(certificate.source_context_ids) != 4 or len(set(certificate.source_context_ids)) != 4:
            return False
        if certificate.brittle_source_action == certificate.robust_source_action:
            return False
        if certificate.static_target_action == certificate.robust_target_action:
            return False
        margins = (
            certificate.brittle_source_margin,
            *certificate.robust_source_margins,
            certificate.min_robust_source_margin,
            certificate.static_target_margin,
            certificate.robust_target_margin,
        )
        if any(not _finite_number(value) for value in margins):
            return False
        if len(certificate.robust_source_margins) != 3:
            return False
        if not _close(certificate.min_robust_source_margin, min(certificate.robust_source_margins)):
            return False
        if certificate.brittle_source_margin <= 0:
            return False
        if certificate.min_robust_source_margin <= 0:
            return False
        if certificate.static_target_margin >= 0:
            return False
        if certificate.robust_target_margin <= 0:
            return False
        if certificate.source_brittle_committed_count != 1:
            return False
        if certificate.source_robust_variant_success_count != 3:
            return False
        if certificate.static_committed or not certificate.robust_committed:
            return False
        if certificate.source_verifier_call_count != 4:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.robust_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.robustness_reason != "robust_source_covers_all_uncertainty_variants":
            return False
        hash_groups = (
            (certificate.source_brittle_receipt_hashes, 1),
            (certificate.source_robust_receipt_hashes, 3),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.robust_target_receipt_hashes, 1),
            (certificate.robust_target_commit_receipt_hashes, 1),
            (certificate.source_robust_branch_selection_certificate_hashes, 3),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_brittle_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.robust_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.uncertainty_set_id != certificate.uncertainty_set_id:
                return False
            if row.variant_ids != certificate.variant_ids:
                return False
            if row.source_contexts != certificate.source_context_ids or row.target_context != certificate.target_context_id:
                return False
            if row.brittle_source_action != certificate.brittle_source_action:
                return False
            if row.robust_source_action != certificate.robust_source_action:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.robust_target_action != certificate.robust_target_action:
                return False
            if row.robust_source_margins != certificate.robust_source_margins:
                return False
            if row.source_brittle_receipt_hashes != certificate.source_brittle_receipt_hashes:
                return False
            if row.source_robust_receipt_hashes != certificate.source_robust_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.robust_target_receipt_hashes != certificate.robust_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_robustness_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_robustness_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_robustness_transfer_certificate(
    report: BranchRobustnessTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_robustness_certificate_hashes: tuple[str, ...],
) -> BranchRobustnessTransferCertificate:
    return BranchRobustnessTransferCertificate(
        schema_version=BRANCH_ROBUSTNESS_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_robustness_certificate_hashes=branch_robustness_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_brittle_success_count=report.source_brittle_success_count,
        source_robust_variant_success_count=report.source_robust_variant_success_count,
        static_success_count=report.static_success_count,
        robust_success_count=report.robust_success_count,
        same_budget_robust_count=report.same_budget_robust_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_ROBUSTNESS_CLAIM_BOUNDARY,
    )


def validate_branch_robustness_transfer_certificate(
    certificate: BranchRobustnessTransferCertificate,
    report: BranchRobustnessTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_ROBUSTNESS_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_robustness_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_robustness_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_brittle_success_count != certificate.domain_count:
            return False
        if certificate.source_robust_variant_success_count != certificate.domain_count * 3:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.robust_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_robust_count != certificate.domain_count:
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
            if tuple(row.branch_robustness_certificate_hash for row in report.rows) != certificate.branch_robustness_certificate_hashes:
                return False
            if report.branch_robustness_certificate_count != len(certificate.branch_robustness_certificate_hashes):
                return False
            if not report.all_branch_robustness_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_brittle_success_count != certificate.source_brittle_success_count:
                return False
            if report.source_robust_variant_success_count != certificate.source_robust_variant_success_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.robust_success_count != certificate.robust_success_count:
                return False
            if report.same_budget_robust_count != certificate.same_budget_robust_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_robustness_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_robustness_certificate_hash(
    certificate: BranchRobustnessCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchRobustnessCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_robustness_transfer_certificate_hash(
    certificate: BranchRobustnessTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchRobustnessTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchRobustnessTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchRobustnessTransferReport,
    transfer_certificate: BranchRobustnessTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_robustness_transfer_g1",
        claim_text=(
            "Receipt-bound uncertainty-set coverage can improve local target exploration by separating "
            "robust source branches from brittle nominal source branches under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_robustness_transfer",
        requirements=(
            requirement(
                "branch_robustness_transfer_certificate_valid",
                validate_branch_robustness_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_robustness_certificates_valid", report.all_branch_robustness_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("brittle_sources_bound_all_domains", report.source_brittle_success_count == report.domain_count),
            requirement("robust_variants_bound_all_domains", report.source_robust_variant_success_count == report.domain_count * 3),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("robust_succeeds_all_domains", report.robust_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_robust_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 4),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_brittle_success_count": report.source_brittle_success_count,
            "source_robust_variant_success_count": report.source_robust_variant_success_count,
            "static_success_count": report.static_success_count,
            "robust_success_count": report.robust_success_count,
        },
        boundary=BRANCH_ROBUSTNESS_CLAIM_BOUNDARY,
        sources=BRANCH_ROBUSTNESS_SOURCES,
    )


def _make_robustness_traces(
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
            seeds=("branch-robustness-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.robustness.transfer.v1",
        )
        for action in actions
    )


def _domain_robustness_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        robust_action = "robust_source_margin_detour"
        return {
            "uncertainty_set_id": "robotics_replan.pose_density_uncertainty.v1",
            "variant_ids": ("pose_noise", "crowd_shift", "sensor_dropout"),
            "source_brittle": {
                "domain": spec.domain_id,
                "action": "robustness_source_nominal_shortcut",
                "utility": 9,
                "clearance": 0.31,
                "turn_rate": 0.44,
            },
            "robust_source_action": robust_action,
            "source_robust_variants": (
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "clearance": 0.38, "turn_rate": 0.39},
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "clearance": 0.35, "turn_rate": 0.42},
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "clearance": 0.36, "turn_rate": 0.40},
            ),
            "target_static": {
                "domain": spec.domain_id,
                "action": "robustness_target_nominal_shortcut_replay",
                "utility": 9,
                "clearance": 0.12,
                "turn_rate": 0.82,
            },
            "target_robust": {
                "domain": spec.domain_id,
                "action": "robustness_target_margin_detour",
                "utility": 8,
                "clearance": 0.34,
                "turn_rate": 0.43,
            },
        }
    if spec.domain_id == "molecule_repair":
        robust_action = "robust_source_low_strain_valence_repair"
        return {
            "uncertainty_set_id": "molecule_repair.conformer_uncertainty.v1",
            "variant_ids": ("rotamer_a", "rotamer_b", "solvent_shift"),
            "source_brittle": {
                "domain": spec.domain_id,
                "action": "robustness_source_nominal_patch",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.24,
            },
            "robust_source_action": robust_action,
            "source_robust_variants": (
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "valence_ok": True, "strain": 0.12},
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "valence_ok": True, "strain": 0.16},
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "valence_ok": True, "strain": 0.18},
            ),
            "target_static": {
                "domain": spec.domain_id,
                "action": "robustness_target_nominal_patch_replay",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.55,
            },
            "target_robust": {
                "domain": spec.domain_id,
                "action": "robustness_target_low_strain_valence_repair",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.15,
            },
        }
    if spec.domain_id == "material_process":
        robust_action = "robust_source_tempered_process_window"
        return {
            "uncertainty_set_id": "material_process.furnace_batch_uncertainty.v1",
            "variant_ids": ("low_impurity", "nominal_batch", "high_impurity"),
            "source_brittle": {
                "domain": spec.domain_id,
                "action": "robustness_source_nominal_fast_ramp",
                "utility": 9,
                "thermal_gradient": 0.42,
                "phase_purity": 0.92,
            },
            "robust_source_action": robust_action,
            "source_robust_variants": (
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "thermal_gradient": 0.34, "phase_purity": 0.96},
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "thermal_gradient": 0.39, "phase_purity": 0.95},
                {"domain": spec.domain_id, "action": robust_action, "utility": 8, "thermal_gradient": 0.45, "phase_purity": 0.94},
            ),
            "target_static": {
                "domain": spec.domain_id,
                "action": "robustness_target_nominal_fast_replay",
                "utility": 9,
                "thermal_gradient": 0.73,
                "phase_purity": 0.84,
            },
            "target_robust": {
                "domain": spec.domain_id,
                "action": "robustness_target_tempered_process_window",
                "utility": 8,
                "thermal_gradient": 0.40,
                "phase_purity": 0.95,
            },
        }
    raise ValueError(f"unknown robustness domain: {spec.domain_id}")


def _domain_margin(spec: ExplorationDomainSpec, action: Mapping[str, Any]) -> float:
    if spec.domain_id == "robotics_replan":
        return round(min(float(action["clearance"]) - 0.25, 0.60 - float(action["turn_rate"])), 6)
    if spec.domain_id == "molecule_repair":
        if not bool(action["valence_ok"]):
            return -1.0
        return round(0.35 - float(action["strain"]), 6)
    if spec.domain_id == "material_process":
        return round(min(0.50 - float(action["thermal_gradient"]), float(action["phase_purity"]) - 0.90), 6)
    raise ValueError(f"unknown robustness domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _finite_number(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value))


def _close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 1e-12


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_robustness_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
