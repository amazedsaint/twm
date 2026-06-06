from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from math import ceil, isfinite
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


BRANCH_CONFORMAL_CERTIFICATE_SCHEMA = "trwm.branch_conformal_certificate.v1"
BRANCH_CONFORMAL_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_conformal_transfer_certificate.v1"
BRANCH_CONFORMAL_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://arxiv.org/abs/1604.04173",
)
BRANCH_CONFORMAL_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound nonconformity "
    "quantiles can separate out-of-envelope source replays from in-envelope target proposals before "
    "target exploration under a matched one-call verifier budget. It is not conformal prediction, "
    "distribution-free coverage, conditional coverage, uncertainty quantification, robotics safety, "
    "chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchConformalCertificate:
    schema_version: str
    domain: str
    conformal_rule_id: str
    conformal_rule_version: str
    alpha: float
    quantile_rank: int
    calibration_context_id: str
    target_context_id: str
    calibration_action_ids: tuple[str, ...]
    rejected_calibration_action_id: str
    static_target_action: str
    conformal_target_action: str
    calibration_nonconformity_scores: tuple[float, ...]
    rejected_calibration_nonconformity_score: float
    nonconformity_quantile: float
    static_target_nonconformity_score: float
    conformal_target_nonconformity_score: float
    calibration_receipt_hashes: tuple[str, ...]
    rejected_calibration_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    conformal_target_receipt_hashes: tuple[str, ...]
    conformal_target_commit_receipt_hashes: tuple[str, ...]
    calibration_branch_selection_certificate_hashes: tuple[str, ...]
    rejected_calibration_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    conformal_branch_selection_certificate_hash: str
    calibration_committed_count: int
    calibration_rejected_count: int
    static_committed: bool
    conformal_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    conformal_verifier_call_count: int
    same_budget: bool
    conformal_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONFORMAL_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch conformal certificate schema: {self.schema_version}")
        for field_name in (
            "calibration_action_ids",
            "calibration_nonconformity_scores",
            "calibration_receipt_hashes",
            "rejected_calibration_receipt_hashes",
            "static_target_receipt_hashes",
            "conformal_target_receipt_hashes",
            "conformal_target_commit_receipt_hashes",
            "calibration_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "alpha",
            "rejected_calibration_nonconformity_score",
            "nonconformity_quantile",
            "static_target_nonconformity_score",
            "conformal_target_nonconformity_score",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        object.__setattr__(
            self,
            "calibration_nonconformity_scores",
            tuple(float(value) for value in self.calibration_nonconformity_scores),
        )
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_conformal_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchConformalDomainReport:
    domain: str
    alpha: float
    quantile_rank: int
    calibration_context: str
    target_context: str
    calibration_action_ids: tuple[str, ...]
    rejected_calibration_action_id: str
    static_target_action: str
    conformal_target_action: str
    calibration_nonconformity_scores: tuple[float, ...]
    rejected_calibration_nonconformity_score: float
    nonconformity_quantile: float
    static_target_nonconformity_score: float
    conformal_target_nonconformity_score: float
    calibration_committed_count: int
    calibration_rejected_count: int
    static_committed: bool
    conformal_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    conformal_verifier_call_count: int
    calibration_receipt_hashes: tuple[str, ...]
    rejected_calibration_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    conformal_target_receipt_hashes: tuple[str, ...]
    branch_conformal_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchConformalTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchConformalDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_calibration_committed_count: int
    source_calibration_rejected_count: int
    static_success_count: int
    conformal_success_count: int
    same_budget_conformal_count: int
    branch_conformal_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_conformal_certificates_valid: bool
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
class BranchConformalTransferCertificate:
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
    branch_conformal_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_calibration_committed_count: int
    source_calibration_rejected_count: int
    static_success_count: int
    conformal_success_count: int
    same_budget_conformal_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONFORMAL_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch conformal transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_conformal_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_conformal_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchConformalTransferResult(CertifiedExampleResult):
    report: BranchConformalTransferReport
    branch_conformal_transfer_certificate: BranchConformalTransferCertificate
    branch_conformal_certificates: tuple[BranchConformalCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_conformal_transfer_experiment() -> BranchConformalTransferReport:
    return run_branch_conformal_transfer_certified_experiment().report


def run_branch_conformal_transfer_certified_experiment() -> CertifiedBranchConformalTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchConformalDomainReport] = []
    conformal_certificates: list[BranchConformalCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_conformal_plan(spec)
        calibration_context = f"{spec.domain_id}:source:conformal:calibration"
        target_context = f"{spec.domain_id}:target:conformal"

        calibration_outcomes = []
        calibration_selections = []
        for idx, calibration_action in enumerate(plan["calibration_actions"]):
            outcome = runtime.step(
                state,
                _make_conformal_traces(
                    spec,
                    context=calibration_context,
                    phase=f"source-calibration-{idx}",
                    actions=(calibration_action,),
                ),
            )
            state = normalize_state(outcome.state)
            selection = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), selection))
            memory.update_branch(outcome.receipts, selection)
            calibration_outcomes.append(outcome)
            calibration_selections.append(selection)

        rejected_outcome = runtime.step(
            state,
            _make_conformal_traces(
                spec,
                context=calibration_context,
                phase="source-calibration-reject",
                actions=(plan["rejected_calibration_action"],),
            ),
        )
        rejected_selection = build_branch_selection_certificate(
            rejected_outcome.receipts,
            verifier_call_count=rejected_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(rejected_outcome.receipts), rejected_selection))
        memory.update_branch(rejected_outcome.receipts, rejected_selection)

        static_outcome = runtime.step(
            state,
            _make_conformal_traces(
                spec,
                context=target_context,
                phase="target-static-out-of-envelope",
                actions=(plan["target_static"],),
            ),
        )
        static_selection = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        conformal_outcome = runtime.step(
            state,
            _make_conformal_traces(
                spec,
                context=target_context,
                phase="target-conformal",
                actions=(plan["target_conformal"],),
            ),
        )
        state = normalize_state(conformal_outcome.state)
        conformal_selection = build_branch_selection_certificate(
            conformal_outcome.receipts,
            verifier_call_count=conformal_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(conformal_outcome.receipts), conformal_selection))

        calibration_scores = tuple(float(action["nonconformity_score"]) for action in plan["calibration_actions"])
        alpha = float(plan["alpha"])
        quantile_rank = _quantile_rank(len(calibration_scores), alpha)
        nonconformity_quantile = sorted(calibration_scores)[quantile_rank - 1]
        certificate = build_branch_conformal_certificate(
            spec,
            alpha=alpha,
            quantile_rank=quantile_rank,
            calibration_context_id=calibration_context,
            target_context_id=target_context,
            calibration_action_ids=tuple(str(action["action"]) for action in plan["calibration_actions"]),
            rejected_calibration_action_id=str(plan["rejected_calibration_action"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            conformal_target_action=str(plan["target_conformal"]["action"]),
            calibration_nonconformity_scores=calibration_scores,
            rejected_calibration_nonconformity_score=float(plan["rejected_calibration_action"]["nonconformity_score"]),
            nonconformity_quantile=nonconformity_quantile,
            static_target_nonconformity_score=float(plan["target_static"]["nonconformity_score"]),
            conformal_target_nonconformity_score=float(plan["target_conformal"]["nonconformity_score"]),
            calibration_receipt_hashes=tuple(
                receipt.receipt_hash for outcome in calibration_outcomes for receipt in outcome.receipts
            ),
            rejected_calibration_receipt_hashes=tuple(receipt.receipt_hash for receipt in rejected_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            conformal_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in conformal_outcome.receipts),
            conformal_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in conformal_outcome.receipts if receipt.committed
            ),
            calibration_branch_selection_certificate_hashes=tuple(
                selection.certificate_hash for selection in calibration_selections
            ),
            rejected_calibration_branch_selection_certificate_hash=rejected_selection.certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            conformal_branch_selection_certificate_hash=conformal_selection.certificate_hash,
            calibration_committed_count=sum(1 for outcome in calibration_outcomes if outcome.committed),
            calibration_rejected_count=sum(
                1 for receipt in rejected_outcome.receipts if receipt.hard_result.rejected
            ),
            static_committed=static_outcome.committed,
            conformal_committed=conformal_outcome.committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in calibration_outcomes)
            + rejected_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            conformal_verifier_call_count=conformal_outcome.verifier_calls,
        )
        conformal_certificates.append(certificate)
        rows.append(
            BranchConformalDomainReport(
                domain=spec.domain_id,
                alpha=certificate.alpha,
                quantile_rank=certificate.quantile_rank,
                calibration_context=certificate.calibration_context_id,
                target_context=certificate.target_context_id,
                calibration_action_ids=certificate.calibration_action_ids,
                rejected_calibration_action_id=certificate.rejected_calibration_action_id,
                static_target_action=certificate.static_target_action,
                conformal_target_action=certificate.conformal_target_action,
                calibration_nonconformity_scores=certificate.calibration_nonconformity_scores,
                rejected_calibration_nonconformity_score=certificate.rejected_calibration_nonconformity_score,
                nonconformity_quantile=certificate.nonconformity_quantile,
                static_target_nonconformity_score=certificate.static_target_nonconformity_score,
                conformal_target_nonconformity_score=certificate.conformal_target_nonconformity_score,
                calibration_committed_count=certificate.calibration_committed_count,
                calibration_rejected_count=certificate.calibration_rejected_count,
                static_committed=certificate.static_committed,
                conformal_committed=certificate.conformal_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                conformal_verifier_call_count=certificate.conformal_verifier_call_count,
                calibration_receipt_hashes=certificate.calibration_receipt_hashes,
                rejected_calibration_receipt_hashes=certificate.rejected_calibration_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                conformal_target_receipt_hashes=certificate.conformal_target_receipt_hashes,
                branch_conformal_certificate_hash=certificate.certificate_hash,
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

    report = BranchConformalTransferReport(
        schema_version="trwm.example.branch_conformal_transfer.v1",
        experiment_id="branch_conformal_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_calibration_committed_count=sum(row.calibration_committed_count for row in rows),
        source_calibration_rejected_count=sum(row.calibration_rejected_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        conformal_success_count=sum(1 for row in rows if row.conformal_committed),
        same_budget_conformal_count=sum(1 for row in rows if row.same_budget),
        branch_conformal_certificate_count=len(conformal_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_conformal_certificates_valid=all(
            validate_branch_conformal_certificate(certificate, row)
            for certificate, row in zip(conformal_certificates, rows)
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
        sources=BRANCH_CONFORMAL_SOURCES,
        learning=(
            "Conformal-style branch reuse separates soft nonconformity scores from commit authority. "
            "The source quantile can exclude an out-of-envelope replay candidate, but the in-envelope "
            "target proposal still commits only through a fresh hard-verifier receipt."
        ),
    )
    transfer_certificate = build_branch_conformal_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_conformal_certificate_hashes=tuple(certificate.certificate_hash for certificate in conformal_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_conformal_transfer",
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
        claim_boundary=BRANCH_CONFORMAL_CLAIM_BOUNDARY,
        sources=BRANCH_CONFORMAL_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchConformalTransferResult(
        report=report,
        branch_conformal_transfer_certificate=transfer_certificate,
        branch_conformal_certificates=tuple(conformal_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_conformal_certificate(
    spec: ExplorationDomainSpec,
    *,
    alpha: float,
    quantile_rank: int,
    calibration_context_id: str,
    target_context_id: str,
    calibration_action_ids: tuple[str, ...],
    rejected_calibration_action_id: str,
    static_target_action: str,
    conformal_target_action: str,
    calibration_nonconformity_scores: tuple[float, ...],
    rejected_calibration_nonconformity_score: float,
    nonconformity_quantile: float,
    static_target_nonconformity_score: float,
    conformal_target_nonconformity_score: float,
    calibration_receipt_hashes: tuple[str, ...],
    rejected_calibration_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    conformal_target_receipt_hashes: tuple[str, ...],
    conformal_target_commit_receipt_hashes: tuple[str, ...],
    calibration_branch_selection_certificate_hashes: tuple[str, ...],
    rejected_calibration_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    conformal_branch_selection_certificate_hash: str,
    calibration_committed_count: int,
    calibration_rejected_count: int,
    static_committed: bool,
    conformal_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    conformal_verifier_call_count: int,
) -> BranchConformalCertificate:
    return BranchConformalCertificate(
        schema_version=BRANCH_CONFORMAL_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        conformal_rule_id="receipt_bound_nonconformity_quantile",
        conformal_rule_version="1.0",
        alpha=alpha,
        quantile_rank=quantile_rank,
        calibration_context_id=calibration_context_id,
        target_context_id=target_context_id,
        calibration_action_ids=calibration_action_ids,
        rejected_calibration_action_id=rejected_calibration_action_id,
        static_target_action=static_target_action,
        conformal_target_action=conformal_target_action,
        calibration_nonconformity_scores=calibration_nonconformity_scores,
        rejected_calibration_nonconformity_score=rejected_calibration_nonconformity_score,
        nonconformity_quantile=nonconformity_quantile,
        static_target_nonconformity_score=static_target_nonconformity_score,
        conformal_target_nonconformity_score=conformal_target_nonconformity_score,
        calibration_receipt_hashes=calibration_receipt_hashes,
        rejected_calibration_receipt_hashes=rejected_calibration_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        conformal_target_receipt_hashes=conformal_target_receipt_hashes,
        conformal_target_commit_receipt_hashes=conformal_target_commit_receipt_hashes,
        calibration_branch_selection_certificate_hashes=calibration_branch_selection_certificate_hashes,
        rejected_calibration_branch_selection_certificate_hash=rejected_calibration_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        conformal_branch_selection_certificate_hash=conformal_branch_selection_certificate_hash,
        calibration_committed_count=calibration_committed_count,
        calibration_rejected_count=calibration_rejected_count,
        static_committed=static_committed,
        conformal_committed=conformal_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        conformal_verifier_call_count=conformal_verifier_call_count,
        same_budget=static_verifier_call_count == conformal_verifier_call_count == 1,
        conformal_reason="target_candidate_score_within_receipt_bound_nonconformity_quantile",
    )


def validate_branch_conformal_certificate(
    certificate: BranchConformalCertificate,
    row: BranchConformalDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONFORMAL_CERTIFICATE_SCHEMA:
            return False
        if certificate.conformal_rule_id != "receipt_bound_nonconformity_quantile":
            return False
        if certificate.conformal_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.calibration_context_id,
            certificate.target_context_id,
            certificate.rejected_calibration_action_id,
            certificate.static_target_action,
            certificate.conformal_target_action,
        ):
            if not _nonempty(value):
                return False
        if not _probability(certificate.alpha) or not _close(certificate.alpha, 0.25):
            return False
        if len(certificate.calibration_action_ids) != 3 or len(set(certificate.calibration_action_ids)) != 3:
            return False
        if len(certificate.calibration_nonconformity_scores) != 3:
            return False
        if any(not _finite_nonnegative(value) for value in certificate.calibration_nonconformity_scores):
            return False
        if certificate.quantile_rank != _quantile_rank(len(certificate.calibration_nonconformity_scores), certificate.alpha):
            return False
        expected_quantile = sorted(certificate.calibration_nonconformity_scores)[certificate.quantile_rank - 1]
        if not _close(certificate.nonconformity_quantile, expected_quantile):
            return False
        if not _finite_nonnegative(certificate.rejected_calibration_nonconformity_score):
            return False
        if certificate.rejected_calibration_nonconformity_score <= certificate.nonconformity_quantile:
            return False
        if certificate.static_target_nonconformity_score <= certificate.nonconformity_quantile:
            return False
        if certificate.conformal_target_nonconformity_score > certificate.nonconformity_quantile:
            return False
        if certificate.calibration_committed_count != 3 or certificate.calibration_rejected_count != 1:
            return False
        if certificate.static_committed or not certificate.conformal_committed:
            return False
        if certificate.source_verifier_call_count != 4:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.conformal_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.conformal_reason != "target_candidate_score_within_receipt_bound_nonconformity_quantile":
            return False
        hash_groups = (
            (certificate.calibration_receipt_hashes, 3),
            (certificate.rejected_calibration_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.conformal_target_receipt_hashes, 1),
            (certificate.conformal_target_commit_receipt_hashes, 1),
            (certificate.calibration_branch_selection_certificate_hashes, 3),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.rejected_calibration_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.conformal_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.alpha != certificate.alpha or row.quantile_rank != certificate.quantile_rank:
                return False
            if row.calibration_context != certificate.calibration_context_id:
                return False
            if row.target_context != certificate.target_context_id:
                return False
            if row.calibration_action_ids != certificate.calibration_action_ids:
                return False
            if row.rejected_calibration_action_id != certificate.rejected_calibration_action_id:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.conformal_target_action != certificate.conformal_target_action:
                return False
            if row.calibration_nonconformity_scores != certificate.calibration_nonconformity_scores:
                return False
            if row.calibration_receipt_hashes != certificate.calibration_receipt_hashes:
                return False
            if row.rejected_calibration_receipt_hashes != certificate.rejected_calibration_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.conformal_target_receipt_hashes != certificate.conformal_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_conformal_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_conformal_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_conformal_transfer_certificate(
    report: BranchConformalTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_conformal_certificate_hashes: tuple[str, ...],
) -> BranchConformalTransferCertificate:
    return BranchConformalTransferCertificate(
        schema_version=BRANCH_CONFORMAL_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_conformal_certificate_hashes=branch_conformal_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_calibration_committed_count=report.source_calibration_committed_count,
        source_calibration_rejected_count=report.source_calibration_rejected_count,
        static_success_count=report.static_success_count,
        conformal_success_count=report.conformal_success_count,
        same_budget_conformal_count=report.same_budget_conformal_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CONFORMAL_CLAIM_BOUNDARY,
    )


def validate_branch_conformal_transfer_certificate(
    certificate: BranchConformalTransferCertificate,
    report: BranchConformalTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONFORMAL_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_conformal_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_conformal_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_calibration_committed_count != certificate.domain_count * 3:
            return False
        if certificate.source_calibration_rejected_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.conformal_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_conformal_count != certificate.domain_count:
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
            if tuple(row.branch_conformal_certificate_hash for row in report.rows) != certificate.branch_conformal_certificate_hashes:
                return False
            if report.branch_conformal_certificate_count != len(certificate.branch_conformal_certificate_hashes):
                return False
            if not report.all_branch_conformal_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_calibration_committed_count != certificate.source_calibration_committed_count:
                return False
            if report.source_calibration_rejected_count != certificate.source_calibration_rejected_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.conformal_success_count != certificate.conformal_success_count:
                return False
            if report.same_budget_conformal_count != certificate.same_budget_conformal_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_conformal_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_conformal_certificate_hash(
    certificate: BranchConformalCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchConformalCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_conformal_transfer_certificate_hash(
    certificate: BranchConformalTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchConformalTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchConformalTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchConformalTransferReport,
    transfer_certificate: BranchConformalTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_conformal_transfer_g1",
        claim_text=(
            "Receipt-bound nonconformity quantiles can improve local target exploration by separating "
            "out-of-envelope source replays from in-envelope target proposals under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_conformal_transfer",
        requirements=(
            requirement(
                "branch_conformal_transfer_certificate_valid",
                validate_branch_conformal_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_conformal_certificates_valid", report.all_branch_conformal_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_calibration_commits_all_domains", report.source_calibration_committed_count == report.domain_count * 3),
            requirement("source_out_of_envelope_rejects_all_domains", report.source_calibration_rejected_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("conformal_succeeds_all_domains", report.conformal_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_conformal_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 4),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_calibration_committed_count": report.source_calibration_committed_count,
            "source_calibration_rejected_count": report.source_calibration_rejected_count,
            "static_success_count": report.static_success_count,
            "conformal_success_count": report.conformal_success_count,
        },
        boundary=BRANCH_CONFORMAL_CLAIM_BOUNDARY,
        sources=BRANCH_CONFORMAL_SOURCES,
    )


def _make_conformal_traces(
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
            seeds=("branch-conformal-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.conformal.transfer.v1",
        )
        for action in actions
    )


def _domain_conformal_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    alpha = 0.25
    if spec.domain_id == "robotics_replan":
        return {
            "alpha": alpha,
            "calibration_actions": (
                {"domain": spec.domain_id, "action": "conformal_source_detour_low", "utility": 7, "nonconformity_score": 0.10, "clearance": 0.36, "turn_rate": 0.42},
                {"domain": spec.domain_id, "action": "conformal_source_detour_mid", "utility": 7, "nonconformity_score": 0.16, "clearance": 0.34, "turn_rate": 0.45},
                {"domain": spec.domain_id, "action": "conformal_source_detour_high", "utility": 7, "nonconformity_score": 0.21, "clearance": 0.32, "turn_rate": 0.50},
            ),
            "rejected_calibration_action": {
                "domain": spec.domain_id,
                "action": "conformal_source_out_of_envelope_cut",
                "utility": 9,
                "nonconformity_score": 0.63,
                "clearance": 0.10,
                "turn_rate": 0.84,
            },
            "target_static": {
                "domain": spec.domain_id,
                "action": "conformal_target_out_of_envelope_replay",
                "utility": 9,
                "nonconformity_score": 0.58,
                "clearance": 0.12,
                "turn_rate": 0.82,
            },
            "target_conformal": {
                "domain": spec.domain_id,
                "action": "conformal_target_in_envelope_detour",
                "utility": 7,
                "nonconformity_score": 0.19,
                "clearance": 0.35,
                "turn_rate": 0.44,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "alpha": alpha,
            "calibration_actions": (
                {"domain": spec.domain_id, "action": "conformal_source_low_strain_low", "utility": 7, "nonconformity_score": 0.09, "valence_ok": True, "strain": 0.18},
                {"domain": spec.domain_id, "action": "conformal_source_low_strain_mid", "utility": 7, "nonconformity_score": 0.15, "valence_ok": True, "strain": 0.22},
                {"domain": spec.domain_id, "action": "conformal_source_low_strain_high", "utility": 7, "nonconformity_score": 0.20, "valence_ok": True, "strain": 0.30},
            ),
            "rejected_calibration_action": {
                "domain": spec.domain_id,
                "action": "conformal_source_out_of_envelope_patch",
                "utility": 9,
                "nonconformity_score": 0.61,
                "valence_ok": False,
                "strain": 0.52,
            },
            "target_static": {
                "domain": spec.domain_id,
                "action": "conformal_target_out_of_envelope_replay",
                "utility": 9,
                "nonconformity_score": 0.56,
                "valence_ok": True,
                "strain": 0.54,
            },
            "target_conformal": {
                "domain": spec.domain_id,
                "action": "conformal_target_in_envelope_low_strain",
                "utility": 7,
                "nonconformity_score": 0.18,
                "valence_ok": True,
                "strain": 0.19,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "alpha": alpha,
            "calibration_actions": (
                {"domain": spec.domain_id, "action": "conformal_source_tempered_low", "utility": 7, "nonconformity_score": 0.11, "thermal_gradient": 0.35, "phase_purity": 0.96},
                {"domain": spec.domain_id, "action": "conformal_source_tempered_mid", "utility": 7, "nonconformity_score": 0.17, "thermal_gradient": 0.40, "phase_purity": 0.94},
                {"domain": spec.domain_id, "action": "conformal_source_tempered_high", "utility": 7, "nonconformity_score": 0.22, "thermal_gradient": 0.45, "phase_purity": 0.93},
            ),
            "rejected_calibration_action": {
                "domain": spec.domain_id,
                "action": "conformal_source_out_of_envelope_fast_ramp",
                "utility": 9,
                "nonconformity_score": 0.66,
                "thermal_gradient": 0.74,
                "phase_purity": 0.85,
            },
            "target_static": {
                "domain": spec.domain_id,
                "action": "conformal_target_out_of_envelope_replay",
                "utility": 9,
                "nonconformity_score": 0.60,
                "thermal_gradient": 0.73,
                "phase_purity": 0.84,
            },
            "target_conformal": {
                "domain": spec.domain_id,
                "action": "conformal_target_in_envelope_tempered",
                "utility": 7,
                "nonconformity_score": 0.20,
                "thermal_gradient": 0.38,
                "phase_purity": 0.95,
            },
        }
    raise ValueError(f"unknown conformal domain: {spec.domain_id}")


def _quantile_rank(n: int, alpha: float) -> int:
    if n <= 0:
        raise ValueError("n must be positive")
    return min(n, max(1, ceil((n + 1) * (1.0 - alpha))))


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _probability(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value)) and 0.0 < float(value) < 1.0


def _finite_nonnegative(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value)) and float(value) >= 0.0


def _close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 1e-6


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_conformal_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
