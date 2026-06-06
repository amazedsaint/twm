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


BRANCH_PROPENSITY_MATCH_CERTIFICATE_SCHEMA = "trwm.branch_propensity_match_certificate.v1"
BRANCH_PROPENSITY_MATCH_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_propensity_match_transfer_certificate.v1"
BRANCH_PROPENSITY_MATCH_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1093/biomet/70.1.41",
)
BRANCH_PROPENSITY_MATCH_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound covariate and "
    "propensity-score-like matching can stop a source-valid but context-mismatched branch from ranking "
    "a target proposal while a matched source branch still needs fresh target hard verification. It is "
    "not a propensity-score estimator, causal-inference result, covariate-balance proof, treatment-effect "
    "estimate, robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchPropensityMatchCertificate:
    schema_version: str
    domain: str
    matching_rule_id: str
    matching_rule_version: str
    source_context_ids: tuple[str, ...]
    target_context_id: str
    covariate_keys: tuple[str, ...]
    target_covariates: tuple[float, ...]
    mismatched_source_covariates: tuple[float, ...]
    matched_source_covariates: tuple[float, ...]
    target_propensity_score: float
    mismatched_propensity_score: float
    matched_propensity_score: float
    mismatched_score_distance: float
    matched_score_distance: float
    caliper: float
    mismatched_covariate_l1: float
    matched_covariate_l1: float
    max_covariate_l1: float
    mismatched_source_action: str
    matched_source_action: str
    static_target_action: str
    matched_target_action: str
    source_mismatched_receipt_hashes: tuple[str, ...]
    source_matched_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    matched_target_receipt_hashes: tuple[str, ...]
    matched_target_commit_receipt_hashes: tuple[str, ...]
    source_mismatched_branch_selection_certificate_hash: str
    source_matched_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    matched_branch_selection_certificate_hash: str
    source_mismatched_committed_count: int
    source_matched_committed_count: int
    static_committed: bool
    matched_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    matched_verifier_call_count: int
    same_budget: bool
    match_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PROPENSITY_MATCH_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch propensity-match certificate schema: {self.schema_version}")
        for field_name in (
            "source_context_ids",
            "covariate_keys",
            "target_covariates",
            "mismatched_source_covariates",
            "matched_source_covariates",
            "source_mismatched_receipt_hashes",
            "source_matched_receipt_hashes",
            "static_target_receipt_hashes",
            "matched_target_receipt_hashes",
            "matched_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "target_propensity_score",
            "mismatched_propensity_score",
            "matched_propensity_score",
            "mismatched_score_distance",
            "matched_score_distance",
            "caliper",
            "mismatched_covariate_l1",
            "matched_covariate_l1",
            "max_covariate_l1",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_propensity_match_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchPropensityMatchDomainReport:
    domain: str
    source_contexts: tuple[str, ...]
    target_context: str
    covariate_keys: tuple[str, ...]
    target_covariates: tuple[float, ...]
    mismatched_source_covariates: tuple[float, ...]
    matched_source_covariates: tuple[float, ...]
    target_propensity_score: float
    mismatched_propensity_score: float
    matched_propensity_score: float
    mismatched_score_distance: float
    matched_score_distance: float
    caliper: float
    mismatched_covariate_l1: float
    matched_covariate_l1: float
    max_covariate_l1: float
    mismatched_source_action: str
    matched_source_action: str
    static_target_action: str
    matched_target_action: str
    source_mismatched_committed_count: int
    source_matched_committed_count: int
    static_committed: bool
    matched_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    matched_verifier_call_count: int
    source_mismatched_receipt_hashes: tuple[str, ...]
    source_matched_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    matched_target_receipt_hashes: tuple[str, ...]
    branch_propensity_match_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchPropensityMatchTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchPropensityMatchDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_mismatched_success_count: int
    source_matched_success_count: int
    static_success_count: int
    matched_success_count: int
    same_budget_match_count: int
    branch_propensity_match_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_propensity_match_certificates_valid: bool
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
class BranchPropensityMatchTransferCertificate:
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
    branch_propensity_match_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_mismatched_success_count: int
    source_matched_success_count: int
    static_success_count: int
    matched_success_count: int
    same_budget_match_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PROPENSITY_MATCH_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch propensity-match transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_propensity_match_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_propensity_match_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchPropensityMatchTransferResult(CertifiedExampleResult):
    report: BranchPropensityMatchTransferReport
    branch_propensity_match_transfer_certificate: BranchPropensityMatchTransferCertificate
    branch_propensity_match_certificates: tuple[BranchPropensityMatchCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_propensity_match_transfer_experiment() -> BranchPropensityMatchTransferReport:
    return run_branch_propensity_match_transfer_certified_experiment().report


def run_branch_propensity_match_transfer_certified_experiment() -> CertifiedBranchPropensityMatchTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchPropensityMatchDomainReport] = []
    propensity_certificates: list[BranchPropensityMatchCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_contexts = (
            f"{spec.domain_id}:source:propensity:mismatched",
            f"{spec.domain_id}:source:propensity:matched",
        )
        target_context = f"{spec.domain_id}:target:propensity_match"
        plan = _domain_propensity_match_plan(spec, source_contexts, target_context)

        source_outcomes = []
        source_certificates = []
        for source_context, source_action in zip(source_contexts, plan["source_actions"]):
            outcome = runtime.step(
                state,
                _make_propensity_match_traces(
                    spec,
                    context=source_context,
                    phase="source-propensity",
                    actions=(source_action,),
                ),
            )
            state = normalize_state(outcome.state)
            selection = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), selection))
            memory.update_branch(outcome.receipts, selection)
            source_outcomes.append(outcome)
            source_certificates.append(selection)

        static_outcome = runtime.step(
            state,
            _make_propensity_match_traces(
                spec,
                context=target_context,
                phase="target-static-mismatched",
                actions=(plan["target_static"],),
            ),
        )
        static_selection = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        matched_outcome = runtime.step(
            state,
            _make_propensity_match_traces(
                spec,
                context=target_context,
                phase="target-propensity-matched",
                actions=(plan["target_matched"],),
            ),
        )
        state = normalize_state(matched_outcome.state)
        matched_selection = build_branch_selection_certificate(
            matched_outcome.receipts,
            verifier_call_count=matched_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(matched_outcome.receipts), matched_selection))

        target_covariates = tuple(float(value) for value in plan["target_covariates"])
        mismatched_covariates = tuple(float(value) for value in plan["mismatched_source_covariates"])
        matched_covariates = tuple(float(value) for value in plan["matched_source_covariates"])
        target_score = _propensity_score(target_covariates)
        mismatched_score = _propensity_score(mismatched_covariates)
        matched_score = _propensity_score(matched_covariates)
        certificate = build_branch_propensity_match_certificate(
            spec,
            source_context_ids=source_contexts,
            target_context_id=target_context,
            covariate_keys=tuple(str(key) for key in plan["covariate_keys"]),
            target_covariates=target_covariates,
            mismatched_source_covariates=mismatched_covariates,
            matched_source_covariates=matched_covariates,
            target_propensity_score=target_score,
            mismatched_propensity_score=mismatched_score,
            matched_propensity_score=matched_score,
            mismatched_score_distance=abs(target_score - mismatched_score),
            matched_score_distance=abs(target_score - matched_score),
            caliper=float(plan["caliper"]),
            mismatched_covariate_l1=_l1_distance(target_covariates, mismatched_covariates),
            matched_covariate_l1=_l1_distance(target_covariates, matched_covariates),
            max_covariate_l1=float(plan["max_covariate_l1"]),
            mismatched_source_action=str(plan["source_actions"][0]["action"]),
            matched_source_action=str(plan["source_actions"][1]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            matched_target_action=str(plan["target_matched"]["action"]),
            source_mismatched_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcomes[0].receipts if receipt.committed
            ),
            source_matched_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_outcomes[1].receipts if receipt.committed
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            matched_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in matched_outcome.receipts),
            matched_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in matched_outcome.receipts if receipt.committed
            ),
            source_mismatched_branch_selection_certificate_hash=source_certificates[0].certificate_hash,
            source_matched_branch_selection_certificate_hash=source_certificates[1].certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            matched_branch_selection_certificate_hash=matched_selection.certificate_hash,
            source_mismatched_committed_count=1 if source_outcomes[0].committed else 0,
            source_matched_committed_count=1 if source_outcomes[1].committed else 0,
            static_committed=static_outcome.committed,
            matched_committed=matched_outcome.committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in source_outcomes),
            static_verifier_call_count=static_outcome.verifier_calls,
            matched_verifier_call_count=matched_outcome.verifier_calls,
        )
        propensity_certificates.append(certificate)
        rows.append(
            BranchPropensityMatchDomainReport(
                domain=spec.domain_id,
                source_contexts=certificate.source_context_ids,
                target_context=certificate.target_context_id,
                covariate_keys=certificate.covariate_keys,
                target_covariates=certificate.target_covariates,
                mismatched_source_covariates=certificate.mismatched_source_covariates,
                matched_source_covariates=certificate.matched_source_covariates,
                target_propensity_score=certificate.target_propensity_score,
                mismatched_propensity_score=certificate.mismatched_propensity_score,
                matched_propensity_score=certificate.matched_propensity_score,
                mismatched_score_distance=certificate.mismatched_score_distance,
                matched_score_distance=certificate.matched_score_distance,
                caliper=certificate.caliper,
                mismatched_covariate_l1=certificate.mismatched_covariate_l1,
                matched_covariate_l1=certificate.matched_covariate_l1,
                max_covariate_l1=certificate.max_covariate_l1,
                mismatched_source_action=certificate.mismatched_source_action,
                matched_source_action=certificate.matched_source_action,
                static_target_action=certificate.static_target_action,
                matched_target_action=certificate.matched_target_action,
                source_mismatched_committed_count=certificate.source_mismatched_committed_count,
                source_matched_committed_count=certificate.source_matched_committed_count,
                static_committed=certificate.static_committed,
                matched_committed=certificate.matched_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                matched_verifier_call_count=certificate.matched_verifier_call_count,
                source_mismatched_receipt_hashes=certificate.source_mismatched_receipt_hashes,
                source_matched_receipt_hashes=certificate.source_matched_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                matched_target_receipt_hashes=certificate.matched_target_receipt_hashes,
                branch_propensity_match_certificate_hash=certificate.certificate_hash,
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

    report = BranchPropensityMatchTransferReport(
        schema_version="trwm.example.branch_propensity_match_transfer.v1",
        experiment_id="branch_propensity_match_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_mismatched_success_count=sum(row.source_mismatched_committed_count for row in rows),
        source_matched_success_count=sum(row.source_matched_committed_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        matched_success_count=sum(1 for row in rows if row.matched_committed),
        same_budget_match_count=sum(1 for row in rows if row.same_budget),
        branch_propensity_match_certificate_count=len(propensity_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_propensity_match_certificates_valid=all(
            validate_branch_propensity_match_certificate(certificate, row)
            for certificate, row in zip(propensity_certificates, rows)
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
        sources=BRANCH_PROPENSITY_MATCH_SOURCES,
        learning=(
            "Propensity-matched branch reuse separates source validity from context comparability. A "
            "mismatched source commit remains useful ledger evidence, but it cannot rank a target proposal "
            "unless the certificate binds a close scalar match, bounded covariate imbalance, and a fresh "
            "target commit receipt."
        ),
    )
    transfer_certificate = build_branch_propensity_match_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_propensity_match_certificate_hashes=tuple(
            certificate.certificate_hash for certificate in propensity_certificates
        ),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_propensity_match_transfer",
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
        claim_boundary=BRANCH_PROPENSITY_MATCH_CLAIM_BOUNDARY,
        sources=BRANCH_PROPENSITY_MATCH_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchPropensityMatchTransferResult(
        report=report,
        branch_propensity_match_transfer_certificate=transfer_certificate,
        branch_propensity_match_certificates=tuple(propensity_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_propensity_match_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_ids: tuple[str, ...],
    target_context_id: str,
    covariate_keys: tuple[str, ...],
    target_covariates: tuple[float, ...],
    mismatched_source_covariates: tuple[float, ...],
    matched_source_covariates: tuple[float, ...],
    target_propensity_score: float,
    mismatched_propensity_score: float,
    matched_propensity_score: float,
    mismatched_score_distance: float,
    matched_score_distance: float,
    caliper: float,
    mismatched_covariate_l1: float,
    matched_covariate_l1: float,
    max_covariate_l1: float,
    mismatched_source_action: str,
    matched_source_action: str,
    static_target_action: str,
    matched_target_action: str,
    source_mismatched_receipt_hashes: tuple[str, ...],
    source_matched_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    matched_target_receipt_hashes: tuple[str, ...],
    matched_target_commit_receipt_hashes: tuple[str, ...],
    source_mismatched_branch_selection_certificate_hash: str,
    source_matched_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    matched_branch_selection_certificate_hash: str,
    source_mismatched_committed_count: int,
    source_matched_committed_count: int,
    static_committed: bool,
    matched_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    matched_verifier_call_count: int,
) -> BranchPropensityMatchCertificate:
    return BranchPropensityMatchCertificate(
        schema_version=BRANCH_PROPENSITY_MATCH_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        matching_rule_id="receipt_bound_propensity_caliper_match",
        matching_rule_version="1.0",
        source_context_ids=source_context_ids,
        target_context_id=target_context_id,
        covariate_keys=covariate_keys,
        target_covariates=target_covariates,
        mismatched_source_covariates=mismatched_source_covariates,
        matched_source_covariates=matched_source_covariates,
        target_propensity_score=target_propensity_score,
        mismatched_propensity_score=mismatched_propensity_score,
        matched_propensity_score=matched_propensity_score,
        mismatched_score_distance=mismatched_score_distance,
        matched_score_distance=matched_score_distance,
        caliper=caliper,
        mismatched_covariate_l1=mismatched_covariate_l1,
        matched_covariate_l1=matched_covariate_l1,
        max_covariate_l1=max_covariate_l1,
        mismatched_source_action=mismatched_source_action,
        matched_source_action=matched_source_action,
        static_target_action=static_target_action,
        matched_target_action=matched_target_action,
        source_mismatched_receipt_hashes=source_mismatched_receipt_hashes,
        source_matched_receipt_hashes=source_matched_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        matched_target_receipt_hashes=matched_target_receipt_hashes,
        matched_target_commit_receipt_hashes=matched_target_commit_receipt_hashes,
        source_mismatched_branch_selection_certificate_hash=source_mismatched_branch_selection_certificate_hash,
        source_matched_branch_selection_certificate_hash=source_matched_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        matched_branch_selection_certificate_hash=matched_branch_selection_certificate_hash,
        source_mismatched_committed_count=source_mismatched_committed_count,
        source_matched_committed_count=source_matched_committed_count,
        static_committed=static_committed,
        matched_committed=matched_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        matched_verifier_call_count=matched_verifier_call_count,
        same_budget=static_verifier_call_count == matched_verifier_call_count == 1,
        match_reason="matched_source_within_propensity_caliper_and_covariate_balance",
    )


def validate_branch_propensity_match_certificate(
    certificate: BranchPropensityMatchCertificate,
    row: BranchPropensityMatchDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PROPENSITY_MATCH_CERTIFICATE_SCHEMA:
            return False
        if certificate.matching_rule_id != "receipt_bound_propensity_caliper_match":
            return False
        if certificate.matching_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.target_context_id,
            certificate.mismatched_source_action,
            certificate.matched_source_action,
            certificate.static_target_action,
            certificate.matched_target_action,
        ):
            if not _nonempty(value):
                return False
        if len(certificate.source_context_ids) != 2 or len(set(certificate.source_context_ids)) != 2:
            return False
        if len(certificate.covariate_keys) < 2 or len(set(certificate.covariate_keys)) != len(certificate.covariate_keys):
            return False
        covariate_sets = (
            certificate.target_covariates,
            certificate.mismatched_source_covariates,
            certificate.matched_source_covariates,
        )
        if any(len(values) != len(certificate.covariate_keys) for values in covariate_sets):
            return False
        if any(not _unit_number(value) for values in covariate_sets for value in values):
            return False
        if certificate.mismatched_source_action == certificate.matched_source_action:
            return False
        if certificate.static_target_action == certificate.matched_target_action:
            return False
        expected_target_score = _propensity_score(certificate.target_covariates)
        expected_mismatched_score = _propensity_score(certificate.mismatched_source_covariates)
        expected_matched_score = _propensity_score(certificate.matched_source_covariates)
        if not _close(certificate.target_propensity_score, expected_target_score):
            return False
        if not _close(certificate.mismatched_propensity_score, expected_mismatched_score):
            return False
        if not _close(certificate.matched_propensity_score, expected_matched_score):
            return False
        if not _close(certificate.mismatched_score_distance, abs(expected_target_score - expected_mismatched_score)):
            return False
        if not _close(certificate.matched_score_distance, abs(expected_target_score - expected_matched_score)):
            return False
        if not _close(certificate.mismatched_covariate_l1, _l1_distance(certificate.target_covariates, certificate.mismatched_source_covariates)):
            return False
        if not _close(certificate.matched_covariate_l1, _l1_distance(certificate.target_covariates, certificate.matched_source_covariates)):
            return False
        if certificate.caliper <= 0 or certificate.max_covariate_l1 <= 0:
            return False
        if certificate.matched_score_distance > certificate.caliper:
            return False
        if certificate.mismatched_score_distance <= certificate.caliper:
            return False
        if certificate.matched_covariate_l1 > certificate.max_covariate_l1:
            return False
        if certificate.mismatched_covariate_l1 <= certificate.max_covariate_l1:
            return False
        if certificate.source_mismatched_committed_count != 1 or certificate.source_matched_committed_count != 1:
            return False
        if certificate.static_committed or not certificate.matched_committed:
            return False
        if certificate.source_verifier_call_count != 2:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.matched_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.match_reason != "matched_source_within_propensity_caliper_and_covariate_balance":
            return False
        hash_groups = (
            (certificate.source_mismatched_receipt_hashes, 1),
            (certificate.source_matched_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.matched_target_receipt_hashes, 1),
            (certificate.matched_target_commit_receipt_hashes, 1),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_mismatched_branch_selection_certificate_hash,
            certificate.source_matched_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.matched_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_contexts != certificate.source_context_ids or row.target_context != certificate.target_context_id:
                return False
            if row.covariate_keys != certificate.covariate_keys:
                return False
            if row.target_covariates != certificate.target_covariates:
                return False
            if row.mismatched_source_covariates != certificate.mismatched_source_covariates:
                return False
            if row.matched_source_covariates != certificate.matched_source_covariates:
                return False
            if row.target_propensity_score != certificate.target_propensity_score:
                return False
            if row.mismatched_propensity_score != certificate.mismatched_propensity_score:
                return False
            if row.matched_propensity_score != certificate.matched_propensity_score:
                return False
            if row.mismatched_score_distance != certificate.mismatched_score_distance:
                return False
            if row.matched_score_distance != certificate.matched_score_distance:
                return False
            if row.caliper != certificate.caliper:
                return False
            if row.mismatched_covariate_l1 != certificate.mismatched_covariate_l1:
                return False
            if row.matched_covariate_l1 != certificate.matched_covariate_l1:
                return False
            if row.max_covariate_l1 != certificate.max_covariate_l1:
                return False
            if row.mismatched_source_action != certificate.mismatched_source_action:
                return False
            if row.matched_source_action != certificate.matched_source_action:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.matched_target_action != certificate.matched_target_action:
                return False
            if row.source_mismatched_receipt_hashes != certificate.source_mismatched_receipt_hashes:
                return False
            if row.source_matched_receipt_hashes != certificate.source_matched_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.matched_target_receipt_hashes != certificate.matched_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_propensity_match_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_propensity_match_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_propensity_match_transfer_certificate(
    report: BranchPropensityMatchTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_propensity_match_certificate_hashes: tuple[str, ...],
) -> BranchPropensityMatchTransferCertificate:
    return BranchPropensityMatchTransferCertificate(
        schema_version=BRANCH_PROPENSITY_MATCH_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_propensity_match_certificate_hashes=branch_propensity_match_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_mismatched_success_count=report.source_mismatched_success_count,
        source_matched_success_count=report.source_matched_success_count,
        static_success_count=report.static_success_count,
        matched_success_count=report.matched_success_count,
        same_budget_match_count=report.same_budget_match_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_PROPENSITY_MATCH_CLAIM_BOUNDARY,
    )


def validate_branch_propensity_match_transfer_certificate(
    certificate: BranchPropensityMatchTransferCertificate,
    report: BranchPropensityMatchTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PROPENSITY_MATCH_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_propensity_match_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_propensity_match_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_mismatched_success_count != certificate.domain_count:
            return False
        if certificate.source_matched_success_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.matched_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_match_count != certificate.domain_count:
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
            if tuple(row.branch_propensity_match_certificate_hash for row in report.rows) != certificate.branch_propensity_match_certificate_hashes:
                return False
            if report.branch_propensity_match_certificate_count != len(certificate.branch_propensity_match_certificate_hashes):
                return False
            if not report.all_branch_propensity_match_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_mismatched_success_count != certificate.source_mismatched_success_count:
                return False
            if report.source_matched_success_count != certificate.source_matched_success_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.matched_success_count != certificate.matched_success_count:
                return False
            if report.same_budget_match_count != certificate.same_budget_match_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_propensity_match_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_propensity_match_certificate_hash(
    certificate: BranchPropensityMatchCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchPropensityMatchCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_propensity_match_transfer_certificate_hash(
    certificate: BranchPropensityMatchTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchPropensityMatchTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchPropensityMatchTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchPropensityMatchTransferReport,
    transfer_certificate: BranchPropensityMatchTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_propensity_match_transfer_g1",
        claim_text=(
            "Receipt-bound propensity-style context matching can improve local target exploration by "
            "rejecting source-valid but context-mismatched branch reuse under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_propensity_match_transfer",
        requirements=(
            requirement(
                "branch_propensity_match_transfer_certificate_valid",
                validate_branch_propensity_match_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_propensity_match_certificates_valid", report.all_branch_propensity_match_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("mismatched_sources_bound_all_domains", report.source_mismatched_success_count == report.domain_count),
            requirement("matched_sources_bound_all_domains", report.source_matched_success_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("matched_succeeds_all_domains", report.matched_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_match_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 2),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_mismatched_success_count": report.source_mismatched_success_count,
            "source_matched_success_count": report.source_matched_success_count,
            "static_success_count": report.static_success_count,
            "matched_success_count": report.matched_success_count,
        },
        boundary=BRANCH_PROPENSITY_MATCH_CLAIM_BOUNDARY,
        sources=BRANCH_PROPENSITY_MATCH_SOURCES,
    )


def _make_propensity_match_traces(
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
            seeds=("branch-propensity-match-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.propensity_match.transfer.v1",
        )
        for action in actions
    )


def _domain_propensity_match_plan(
    spec: ExplorationDomainSpec,
    source_contexts: tuple[str, str],
    target_context: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "covariate_keys": ("corridor_openness", "pedestrian_density"),
            "target_covariates": (0.20, 0.80),
            "mismatched_source_covariates": (1.00, 0.00),
            "matched_source_covariates": (0.25, 0.75),
            "caliper": 0.15,
            "max_covariate_l1": 0.20,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "propensity_source_open_corridor_shortcut",
                    "utility": 9,
                    "clearance": 0.36,
                    "turn_rate": 0.40,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "propensity_source_crowded_detour",
                    "utility": 8,
                    "clearance": 0.34,
                    "turn_rate": 0.44,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "propensity_target_open_shortcut_replay",
                "utility": 9,
                "clearance": 0.13,
                "turn_rate": 0.82,
            },
            "target_matched": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "propensity_target_crowded_detour",
                "utility": 8,
                "clearance": 0.33,
                "turn_rate": 0.43,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "covariate_keys": ("steric_exposure", "polar_site_load"),
            "target_covariates": (0.82, 0.70),
            "mismatched_source_covariates": (0.18, 0.18),
            "matched_source_covariates": (0.78, 0.73),
            "caliper": 0.15,
            "max_covariate_l1": 0.20,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "propensity_source_low_steric_patch",
                    "utility": 9,
                    "valence_ok": True,
                    "strain": 0.18,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "propensity_source_hindered_valence_repair",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.16,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "propensity_target_low_steric_replay",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.55,
            },
            "target_matched": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "propensity_target_hindered_valence_repair",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.15,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "covariate_keys": ("thermal_load", "impurity_pressure"),
            "target_covariates": (0.80, 0.76),
            "mismatched_source_covariates": (0.22, 0.12),
            "matched_source_covariates": (0.75, 0.72),
            "caliper": 0.15,
            "max_covariate_l1": 0.20,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "propensity_source_clean_fast_ramp",
                    "utility": 9,
                    "thermal_gradient": 0.40,
                    "phase_purity": 0.94,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "propensity_source_dirty_tempered_ramp",
                    "utility": 8,
                    "thermal_gradient": 0.39,
                    "phase_purity": 0.95,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "propensity_target_clean_fast_replay",
                "utility": 9,
                "thermal_gradient": 0.72,
                "phase_purity": 0.84,
            },
            "target_matched": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "propensity_target_dirty_tempered_ramp",
                "utility": 8,
                "thermal_gradient": 0.40,
                "phase_purity": 0.95,
            },
        }
    raise ValueError(f"unknown propensity-match domain: {spec.domain_id}")


def _propensity_score(covariates: tuple[float, ...]) -> float:
    if len(covariates) != 2:
        raise ValueError("propensity score helper expects exactly two covariates")
    return round(0.6 * float(covariates[0]) + 0.4 * float(covariates[1]), 6)


def _l1_distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("covariate vectors must have the same length")
    return round(sum(abs(float(a) - float(b)) for a, b in zip(left, right)), 6)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _unit_number(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value)) and 0.0 <= float(value) <= 1.0


def _close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 1e-12


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_propensity_match_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
