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


BRANCH_CALIBRATION_CERTIFICATE_SCHEMA = "trwm.branch_calibration_certificate.v1"
BRANCH_CALIBRATION_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_calibration_transfer_certificate.v1"
BRANCH_CALIBRATION_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://arxiv.org/abs/1706.04599",
)
BRANCH_CALIBRATION_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound calibration bins can "
    "separate overconfident unreliable source branches from lower-confidence calibrated source branches "
    "before target exploration under a matched one-call verifier budget. It is not neural-network "
    "calibration, statistical calibration, probability estimation, model reliability assurance, robotics "
    "safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchCalibrationCertificate:
    schema_version: str
    domain: str
    calibration_rule_id: str
    calibration_rule_version: str
    overconfident_bin_id: str
    calibrated_bin_id: str
    target_context_id: str
    overconfident_source_actions: tuple[str, ...]
    calibrated_source_actions: tuple[str, ...]
    static_target_action: str
    calibrated_target_action: str
    overconfident_predicted_confidences: tuple[float, ...]
    calibrated_predicted_confidences: tuple[float, ...]
    overconfident_empirical_accept_rate: float
    calibrated_empirical_accept_rate: float
    overconfident_calibration_gap: float
    calibrated_calibration_gap: float
    source_expected_calibration_error: float
    overconfident_source_receipt_hashes: tuple[str, ...]
    calibrated_source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    calibrated_target_receipt_hashes: tuple[str, ...]
    calibrated_target_commit_receipt_hashes: tuple[str, ...]
    overconfident_branch_selection_certificate_hash: str
    calibrated_branch_selection_certificate_hashes: tuple[str, ...]
    static_branch_selection_certificate_hash: str
    calibrated_branch_selection_certificate_hash: str
    overconfident_source_rejected_count: int
    calibrated_source_committed_count: int
    calibrated_source_rejected_count: int
    static_committed: bool
    calibrated_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    calibrated_verifier_call_count: int
    same_budget: bool
    calibration_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CALIBRATION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch calibration certificate schema: {self.schema_version}")
        for field_name in (
            "overconfident_source_actions",
            "calibrated_source_actions",
            "overconfident_predicted_confidences",
            "calibrated_predicted_confidences",
            "overconfident_source_receipt_hashes",
            "calibrated_source_receipt_hashes",
            "static_target_receipt_hashes",
            "calibrated_target_receipt_hashes",
            "calibrated_target_commit_receipt_hashes",
            "calibrated_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in (
            "overconfident_empirical_accept_rate",
            "calibrated_empirical_accept_rate",
            "overconfident_calibration_gap",
            "calibrated_calibration_gap",
            "source_expected_calibration_error",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        object.__setattr__(
            self,
            "overconfident_predicted_confidences",
            tuple(float(value) for value in self.overconfident_predicted_confidences),
        )
        object.__setattr__(
            self,
            "calibrated_predicted_confidences",
            tuple(float(value) for value in self.calibrated_predicted_confidences),
        )
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_calibration_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchCalibrationDomainReport:
    domain: str
    overconfident_bin_id: str
    calibrated_bin_id: str
    target_context: str
    overconfident_source_actions: tuple[str, ...]
    calibrated_source_actions: tuple[str, ...]
    static_target_action: str
    calibrated_target_action: str
    overconfident_empirical_accept_rate: float
    calibrated_empirical_accept_rate: float
    overconfident_calibration_gap: float
    calibrated_calibration_gap: float
    source_expected_calibration_error: float
    overconfident_source_rejected_count: int
    calibrated_source_committed_count: int
    calibrated_source_rejected_count: int
    static_committed: bool
    calibrated_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    calibrated_verifier_call_count: int
    overconfident_source_receipt_hashes: tuple[str, ...]
    calibrated_source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    calibrated_target_receipt_hashes: tuple[str, ...]
    branch_calibration_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchCalibrationTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchCalibrationDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_overconfident_rejected_count: int
    source_calibrated_committed_count: int
    source_calibrated_rejected_count: int
    static_success_count: int
    calibrated_success_count: int
    same_budget_calibrated_count: int
    branch_calibration_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_calibration_certificates_valid: bool
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
class BranchCalibrationTransferCertificate:
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
    branch_calibration_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_overconfident_rejected_count: int
    source_calibrated_committed_count: int
    source_calibrated_rejected_count: int
    static_success_count: int
    calibrated_success_count: int
    same_budget_calibrated_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CALIBRATION_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch calibration transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_calibration_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_calibration_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchCalibrationTransferResult(CertifiedExampleResult):
    report: BranchCalibrationTransferReport
    branch_calibration_transfer_certificate: BranchCalibrationTransferCertificate
    branch_calibration_certificates: tuple[BranchCalibrationCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_calibration_transfer_experiment() -> BranchCalibrationTransferReport:
    return run_branch_calibration_transfer_certified_experiment().report


def run_branch_calibration_transfer_certified_experiment() -> CertifiedBranchCalibrationTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchCalibrationDomainReport] = []
    calibration_certificates: list[BranchCalibrationCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_calibration_plan(spec)
        target_context = f"{spec.domain_id}:target:calibration"

        overconfident_outcome = runtime.step(
            state,
            _make_calibration_traces(
                spec,
                context=f"{spec.domain_id}:source:calibration:overconfident",
                phase="source-overconfident",
                actions=(plan["source_overconfident"],),
            ),
        )
        overconfident_selection = build_branch_selection_certificate(
            overconfident_outcome.receipts,
            verifier_call_count=overconfident_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(overconfident_outcome.receipts), overconfident_selection))
        memory.update_branch(overconfident_outcome.receipts, overconfident_selection)

        calibrated_outcomes = []
        calibrated_selections = []
        for idx, calibrated_action in enumerate(plan["source_calibrated_actions"]):
            outcome = runtime.step(
                state,
                _make_calibration_traces(
                    spec,
                    context=f"{spec.domain_id}:source:calibration:calibrated:{idx}",
                    phase="source-calibrated-bin",
                    actions=(calibrated_action,),
                ),
            )
            if outcome.committed:
                state = normalize_state(outcome.state)
            selection = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), selection))
            memory.update_branch(outcome.receipts, selection)
            calibrated_outcomes.append(outcome)
            calibrated_selections.append(selection)

        static_outcome = runtime.step(
            state,
            _make_calibration_traces(
                spec,
                context=target_context,
                phase="target-static-overconfident",
                actions=(plan["target_static"],),
            ),
        )
        static_selection = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        calibrated_outcome = runtime.step(
            state,
            _make_calibration_traces(
                spec,
                context=target_context,
                phase="target-calibrated",
                actions=(plan["target_calibrated"],),
            ),
        )
        state = normalize_state(calibrated_outcome.state)
        calibrated_selection = build_branch_selection_certificate(
            calibrated_outcome.receipts,
            verifier_call_count=calibrated_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(calibrated_outcome.receipts), calibrated_selection))

        calibration_stats = _calibration_stats(
            tuple(overconfident_outcome.receipts),
            tuple(outcome.receipts[0] for outcome in calibrated_outcomes),
        )
        certificate = build_branch_calibration_certificate(
            spec,
            overconfident_bin_id=str(plan["overconfident_bin_id"]),
            calibrated_bin_id=str(plan["calibrated_bin_id"]),
            target_context_id=target_context,
            overconfident_source_actions=(str(plan["source_overconfident"]["action"]),),
            calibrated_source_actions=tuple(str(action["action"]) for action in plan["source_calibrated_actions"]),
            static_target_action=str(plan["target_static"]["action"]),
            calibrated_target_action=str(plan["target_calibrated"]["action"]),
            overconfident_predicted_confidences=tuple(
                float(action["predicted_confidence"]) for action in (plan["source_overconfident"],)
            ),
            calibrated_predicted_confidences=tuple(
                float(action["predicted_confidence"]) for action in plan["source_calibrated_actions"]
            ),
            overconfident_empirical_accept_rate=calibration_stats["overconfident_rate"],
            calibrated_empirical_accept_rate=calibration_stats["calibrated_rate"],
            overconfident_calibration_gap=calibration_stats["overconfident_gap"],
            calibrated_calibration_gap=calibration_stats["calibrated_gap"],
            source_expected_calibration_error=calibration_stats["ece"],
            overconfident_source_receipt_hashes=tuple(receipt.receipt_hash for receipt in overconfident_outcome.receipts),
            calibrated_source_receipt_hashes=tuple(
                receipt.receipt_hash for outcome in calibrated_outcomes for receipt in outcome.receipts
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            calibrated_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in calibrated_outcome.receipts),
            calibrated_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in calibrated_outcome.receipts if receipt.committed
            ),
            overconfident_branch_selection_certificate_hash=overconfident_selection.certificate_hash,
            calibrated_branch_selection_certificate_hashes=tuple(
                selection.certificate_hash for selection in calibrated_selections
            ),
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            calibrated_branch_selection_certificate_hash=calibrated_selection.certificate_hash,
            overconfident_source_rejected_count=sum(
                1 for receipt in overconfident_outcome.receipts if receipt.hard_result.rejected
            ),
            calibrated_source_committed_count=sum(1 for outcome in calibrated_outcomes if outcome.committed),
            calibrated_source_rejected_count=sum(
                1 for outcome in calibrated_outcomes for receipt in outcome.receipts if receipt.hard_result.rejected
            ),
            static_committed=static_outcome.committed,
            calibrated_committed=calibrated_outcome.committed,
            source_verifier_call_count=overconfident_outcome.verifier_calls
            + sum(outcome.verifier_calls for outcome in calibrated_outcomes),
            static_verifier_call_count=static_outcome.verifier_calls,
            calibrated_verifier_call_count=calibrated_outcome.verifier_calls,
        )
        calibration_certificates.append(certificate)
        rows.append(
            BranchCalibrationDomainReport(
                domain=spec.domain_id,
                overconfident_bin_id=certificate.overconfident_bin_id,
                calibrated_bin_id=certificate.calibrated_bin_id,
                target_context=certificate.target_context_id,
                overconfident_source_actions=certificate.overconfident_source_actions,
                calibrated_source_actions=certificate.calibrated_source_actions,
                static_target_action=certificate.static_target_action,
                calibrated_target_action=certificate.calibrated_target_action,
                overconfident_empirical_accept_rate=certificate.overconfident_empirical_accept_rate,
                calibrated_empirical_accept_rate=certificate.calibrated_empirical_accept_rate,
                overconfident_calibration_gap=certificate.overconfident_calibration_gap,
                calibrated_calibration_gap=certificate.calibrated_calibration_gap,
                source_expected_calibration_error=certificate.source_expected_calibration_error,
                overconfident_source_rejected_count=certificate.overconfident_source_rejected_count,
                calibrated_source_committed_count=certificate.calibrated_source_committed_count,
                calibrated_source_rejected_count=certificate.calibrated_source_rejected_count,
                static_committed=certificate.static_committed,
                calibrated_committed=certificate.calibrated_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                calibrated_verifier_call_count=certificate.calibrated_verifier_call_count,
                overconfident_source_receipt_hashes=certificate.overconfident_source_receipt_hashes,
                calibrated_source_receipt_hashes=certificate.calibrated_source_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                calibrated_target_receipt_hashes=certificate.calibrated_target_receipt_hashes,
                branch_calibration_certificate_hash=certificate.certificate_hash,
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

    report = BranchCalibrationTransferReport(
        schema_version="trwm.example.branch_calibration_transfer.v1",
        experiment_id="branch_calibration_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_overconfident_rejected_count=sum(row.overconfident_source_rejected_count for row in rows),
        source_calibrated_committed_count=sum(row.calibrated_source_committed_count for row in rows),
        source_calibrated_rejected_count=sum(row.calibrated_source_rejected_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        calibrated_success_count=sum(1 for row in rows if row.calibrated_committed),
        same_budget_calibrated_count=sum(1 for row in rows if row.same_budget),
        branch_calibration_certificate_count=len(calibration_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_calibration_certificates_valid=all(
            validate_branch_calibration_certificate(certificate, row)
            for certificate, row in zip(calibration_certificates, rows)
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
        sources=BRANCH_CALIBRATION_SOURCES,
        learning=(
            "Calibration-aware branch reuse separates proposer confidence from verified reliability. "
            "An overconfident source bin is retained as evidence, but target priority comes only from "
            "a certificate that binds source bin accuracy, calibration gaps, and a fresh target commit receipt."
        ),
    )
    transfer_certificate = build_branch_calibration_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_calibration_certificate_hashes=tuple(certificate.certificate_hash for certificate in calibration_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_calibration_transfer",
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
        claim_boundary=BRANCH_CALIBRATION_CLAIM_BOUNDARY,
        sources=BRANCH_CALIBRATION_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchCalibrationTransferResult(
        report=report,
        branch_calibration_transfer_certificate=transfer_certificate,
        branch_calibration_certificates=tuple(calibration_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_calibration_certificate(
    spec: ExplorationDomainSpec,
    *,
    overconfident_bin_id: str,
    calibrated_bin_id: str,
    target_context_id: str,
    overconfident_source_actions: tuple[str, ...],
    calibrated_source_actions: tuple[str, ...],
    static_target_action: str,
    calibrated_target_action: str,
    overconfident_predicted_confidences: tuple[float, ...],
    calibrated_predicted_confidences: tuple[float, ...],
    overconfident_empirical_accept_rate: float,
    calibrated_empirical_accept_rate: float,
    overconfident_calibration_gap: float,
    calibrated_calibration_gap: float,
    source_expected_calibration_error: float,
    overconfident_source_receipt_hashes: tuple[str, ...],
    calibrated_source_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    calibrated_target_receipt_hashes: tuple[str, ...],
    calibrated_target_commit_receipt_hashes: tuple[str, ...],
    overconfident_branch_selection_certificate_hash: str,
    calibrated_branch_selection_certificate_hashes: tuple[str, ...],
    static_branch_selection_certificate_hash: str,
    calibrated_branch_selection_certificate_hash: str,
    overconfident_source_rejected_count: int,
    calibrated_source_committed_count: int,
    calibrated_source_rejected_count: int,
    static_committed: bool,
    calibrated_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    calibrated_verifier_call_count: int,
) -> BranchCalibrationCertificate:
    return BranchCalibrationCertificate(
        schema_version=BRANCH_CALIBRATION_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        calibration_rule_id="receipt_bound_confidence_bin_calibration",
        calibration_rule_version="1.0",
        overconfident_bin_id=overconfident_bin_id,
        calibrated_bin_id=calibrated_bin_id,
        target_context_id=target_context_id,
        overconfident_source_actions=overconfident_source_actions,
        calibrated_source_actions=calibrated_source_actions,
        static_target_action=static_target_action,
        calibrated_target_action=calibrated_target_action,
        overconfident_predicted_confidences=overconfident_predicted_confidences,
        calibrated_predicted_confidences=calibrated_predicted_confidences,
        overconfident_empirical_accept_rate=overconfident_empirical_accept_rate,
        calibrated_empirical_accept_rate=calibrated_empirical_accept_rate,
        overconfident_calibration_gap=overconfident_calibration_gap,
        calibrated_calibration_gap=calibrated_calibration_gap,
        source_expected_calibration_error=source_expected_calibration_error,
        overconfident_source_receipt_hashes=overconfident_source_receipt_hashes,
        calibrated_source_receipt_hashes=calibrated_source_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        calibrated_target_receipt_hashes=calibrated_target_receipt_hashes,
        calibrated_target_commit_receipt_hashes=calibrated_target_commit_receipt_hashes,
        overconfident_branch_selection_certificate_hash=overconfident_branch_selection_certificate_hash,
        calibrated_branch_selection_certificate_hashes=calibrated_branch_selection_certificate_hashes,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        calibrated_branch_selection_certificate_hash=calibrated_branch_selection_certificate_hash,
        overconfident_source_rejected_count=overconfident_source_rejected_count,
        calibrated_source_committed_count=calibrated_source_committed_count,
        calibrated_source_rejected_count=calibrated_source_rejected_count,
        static_committed=static_committed,
        calibrated_committed=calibrated_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        calibrated_verifier_call_count=calibrated_verifier_call_count,
        same_budget=static_verifier_call_count == calibrated_verifier_call_count == 1,
        calibration_reason="calibrated_bin_empirical_rate_matches_confidence_and_overconfident_bin_rejects",
    )


def validate_branch_calibration_certificate(
    certificate: BranchCalibrationCertificate,
    row: BranchCalibrationDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CALIBRATION_CERTIFICATE_SCHEMA:
            return False
        if certificate.calibration_rule_id != "receipt_bound_confidence_bin_calibration":
            return False
        if certificate.calibration_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.overconfident_bin_id,
            certificate.calibrated_bin_id,
            certificate.target_context_id,
            certificate.static_target_action,
            certificate.calibrated_target_action,
        ):
            if not _nonempty(value):
                return False
        if certificate.overconfident_bin_id == certificate.calibrated_bin_id:
            return False
        if len(certificate.overconfident_source_actions) != 1:
            return False
        if len(certificate.calibrated_source_actions) != 3 or len(set(certificate.calibrated_source_actions)) != 3:
            return False
        if certificate.static_target_action == certificate.calibrated_target_action:
            return False
        for values in (
            certificate.overconfident_predicted_confidences,
            certificate.calibrated_predicted_confidences,
        ):
            if not values or any(not _probability(value) for value in values):
                return False
        if len(certificate.overconfident_predicted_confidences) != 1:
            return False
        if len(certificate.calibrated_predicted_confidences) != 3:
            return False
        if not _close(_mean(certificate.overconfident_predicted_confidences), 0.95):
            return False
        if not _close(_mean(certificate.calibrated_predicted_confidences), 2.0 / 3.0):
            return False
        if not _close(certificate.overconfident_empirical_accept_rate, 0.0):
            return False
        if not _close(certificate.calibrated_empirical_accept_rate, 2.0 / 3.0):
            return False
        if certificate.overconfident_calibration_gap < 0.90:
            return False
        if certificate.calibrated_calibration_gap > 1e-6:
            return False
        if not _close(certificate.source_expected_calibration_error, 0.2375):
            return False
        if certificate.overconfident_source_rejected_count != 1:
            return False
        if certificate.calibrated_source_committed_count != 2:
            return False
        if certificate.calibrated_source_rejected_count != 1:
            return False
        if certificate.static_committed or not certificate.calibrated_committed:
            return False
        if certificate.source_verifier_call_count != 4:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.calibrated_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.calibration_reason != "calibrated_bin_empirical_rate_matches_confidence_and_overconfident_bin_rejects":
            return False
        hash_groups = (
            (certificate.overconfident_source_receipt_hashes, 1),
            (certificate.calibrated_source_receipt_hashes, 3),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.calibrated_target_receipt_hashes, 1),
            (certificate.calibrated_target_commit_receipt_hashes, 1),
            (certificate.calibrated_branch_selection_certificate_hashes, 3),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.overconfident_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.calibrated_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.overconfident_bin_id != certificate.overconfident_bin_id:
                return False
            if row.calibrated_bin_id != certificate.calibrated_bin_id:
                return False
            if row.target_context != certificate.target_context_id:
                return False
            if row.overconfident_source_actions != certificate.overconfident_source_actions:
                return False
            if row.calibrated_source_actions != certificate.calibrated_source_actions:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.calibrated_target_action != certificate.calibrated_target_action:
                return False
            if row.overconfident_source_receipt_hashes != certificate.overconfident_source_receipt_hashes:
                return False
            if row.calibrated_source_receipt_hashes != certificate.calibrated_source_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.calibrated_target_receipt_hashes != certificate.calibrated_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_calibration_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_calibration_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_calibration_transfer_certificate(
    report: BranchCalibrationTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_calibration_certificate_hashes: tuple[str, ...],
) -> BranchCalibrationTransferCertificate:
    return BranchCalibrationTransferCertificate(
        schema_version=BRANCH_CALIBRATION_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_calibration_certificate_hashes=branch_calibration_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_overconfident_rejected_count=report.source_overconfident_rejected_count,
        source_calibrated_committed_count=report.source_calibrated_committed_count,
        source_calibrated_rejected_count=report.source_calibrated_rejected_count,
        static_success_count=report.static_success_count,
        calibrated_success_count=report.calibrated_success_count,
        same_budget_calibrated_count=report.same_budget_calibrated_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CALIBRATION_CLAIM_BOUNDARY,
    )


def validate_branch_calibration_transfer_certificate(
    certificate: BranchCalibrationTransferCertificate,
    report: BranchCalibrationTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CALIBRATION_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_calibration_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_calibration_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_overconfident_rejected_count != certificate.domain_count:
            return False
        if certificate.source_calibrated_committed_count != certificate.domain_count * 2:
            return False
        if certificate.source_calibrated_rejected_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.calibrated_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_calibrated_count != certificate.domain_count:
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
            if tuple(row.branch_calibration_certificate_hash for row in report.rows) != certificate.branch_calibration_certificate_hashes:
                return False
            if report.branch_calibration_certificate_count != len(certificate.branch_calibration_certificate_hashes):
                return False
            if not report.all_branch_calibration_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_overconfident_rejected_count != certificate.source_overconfident_rejected_count:
                return False
            if report.source_calibrated_committed_count != certificate.source_calibrated_committed_count:
                return False
            if report.source_calibrated_rejected_count != certificate.source_calibrated_rejected_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.calibrated_success_count != certificate.calibrated_success_count:
                return False
            if report.same_budget_calibrated_count != certificate.same_budget_calibrated_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_calibration_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_calibration_certificate_hash(
    certificate: BranchCalibrationCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCalibrationCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_calibration_transfer_certificate_hash(
    certificate: BranchCalibrationTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCalibrationTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchCalibrationTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchCalibrationTransferReport,
    transfer_certificate: BranchCalibrationTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_calibration_transfer_g1",
        claim_text=(
            "Receipt-bound confidence-bin calibration can improve local target exploration by separating "
            "overconfident unreliable source branches from calibrated source branches under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_calibration_transfer",
        requirements=(
            requirement(
                "branch_calibration_transfer_certificate_valid",
                validate_branch_calibration_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_calibration_certificates_valid", report.all_branch_calibration_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("overconfident_sources_reject_all_domains", report.source_overconfident_rejected_count == report.domain_count),
            requirement("calibrated_sources_bound_all_domains", report.source_calibrated_committed_count == report.domain_count * 2),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("calibrated_succeeds_all_domains", report.calibrated_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_calibrated_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 4),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_overconfident_rejected_count": report.source_overconfident_rejected_count,
            "source_calibrated_committed_count": report.source_calibrated_committed_count,
            "source_calibrated_rejected_count": report.source_calibrated_rejected_count,
            "static_success_count": report.static_success_count,
            "calibrated_success_count": report.calibrated_success_count,
        },
        boundary=BRANCH_CALIBRATION_CLAIM_BOUNDARY,
        sources=BRANCH_CALIBRATION_SOURCES,
    )


def _make_calibration_traces(
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
            seeds=("branch-calibration-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.calibration.transfer.v1",
        )
        for action in actions
    )


def _domain_calibration_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    calibrated_confidence = 2.0 / 3.0
    if spec.domain_id == "robotics_replan":
        return {
            "overconfident_bin_id": "robotics_replan.confidence_bin.0.90_1.00",
            "calibrated_bin_id": "robotics_replan.confidence_bin.0.60_0.70",
            "source_overconfident": {
                "domain": spec.domain_id,
                "action": "calibration_source_overconfident_shortcut",
                "utility": 9,
                "predicted_confidence": 0.95,
                "clearance": 0.08,
                "turn_rate": 0.88,
            },
            "source_calibrated_actions": (
                {"domain": spec.domain_id, "action": "calibration_source_detour_a", "utility": 7, "predicted_confidence": calibrated_confidence, "clearance": 0.34, "turn_rate": 0.45},
                {"domain": spec.domain_id, "action": "calibration_source_thin_gap", "utility": 7, "predicted_confidence": calibrated_confidence, "clearance": 0.18, "turn_rate": 0.48},
                {"domain": spec.domain_id, "action": "calibration_source_detour_b", "utility": 7, "predicted_confidence": calibrated_confidence, "clearance": 0.37, "turn_rate": 0.42},
            ),
            "target_static": {
                "domain": spec.domain_id,
                "action": "calibration_target_overconfident_shortcut_replay",
                "utility": 9,
                "predicted_confidence": 0.96,
                "clearance": 0.12,
                "turn_rate": 0.82,
            },
            "target_calibrated": {
                "domain": spec.domain_id,
                "action": "calibration_target_calibrated_detour",
                "utility": 7,
                "predicted_confidence": calibrated_confidence,
                "clearance": 0.35,
                "turn_rate": 0.43,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "overconfident_bin_id": "molecule_repair.confidence_bin.0.90_1.00",
            "calibrated_bin_id": "molecule_repair.confidence_bin.0.60_0.70",
            "source_overconfident": {
                "domain": spec.domain_id,
                "action": "calibration_source_overconfident_patch",
                "utility": 9,
                "predicted_confidence": 0.95,
                "valence_ok": False,
                "strain": 0.50,
            },
            "source_calibrated_actions": (
                {"domain": spec.domain_id, "action": "calibration_source_low_strain_a", "utility": 7, "predicted_confidence": calibrated_confidence, "valence_ok": True, "strain": 0.22},
                {"domain": spec.domain_id, "action": "calibration_source_high_strain_probe", "utility": 7, "predicted_confidence": calibrated_confidence, "valence_ok": True, "strain": 0.47},
                {"domain": spec.domain_id, "action": "calibration_source_low_strain_b", "utility": 7, "predicted_confidence": calibrated_confidence, "valence_ok": True, "strain": 0.18},
            ),
            "target_static": {
                "domain": spec.domain_id,
                "action": "calibration_target_overconfident_patch_replay",
                "utility": 9,
                "predicted_confidence": 0.96,
                "valence_ok": True,
                "strain": 0.55,
            },
            "target_calibrated": {
                "domain": spec.domain_id,
                "action": "calibration_target_calibrated_low_strain",
                "utility": 7,
                "predicted_confidence": calibrated_confidence,
                "valence_ok": True,
                "strain": 0.16,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "overconfident_bin_id": "material_process.confidence_bin.0.90_1.00",
            "calibrated_bin_id": "material_process.confidence_bin.0.60_0.70",
            "source_overconfident": {
                "domain": spec.domain_id,
                "action": "calibration_source_overconfident_fast_ramp",
                "utility": 9,
                "predicted_confidence": 0.95,
                "thermal_gradient": 0.80,
                "phase_purity": 0.86,
            },
            "source_calibrated_actions": (
                {"domain": spec.domain_id, "action": "calibration_source_tempered_a", "utility": 7, "predicted_confidence": calibrated_confidence, "thermal_gradient": 0.41, "phase_purity": 0.95},
                {"domain": spec.domain_id, "action": "calibration_source_hot_probe", "utility": 7, "predicted_confidence": calibrated_confidence, "thermal_gradient": 0.60, "phase_purity": 0.86},
                {"domain": spec.domain_id, "action": "calibration_source_tempered_b", "utility": 7, "predicted_confidence": calibrated_confidence, "thermal_gradient": 0.35, "phase_purity": 0.93},
            ),
            "target_static": {
                "domain": spec.domain_id,
                "action": "calibration_target_overconfident_fast_replay",
                "utility": 9,
                "predicted_confidence": 0.96,
                "thermal_gradient": 0.78,
                "phase_purity": 0.84,
            },
            "target_calibrated": {
                "domain": spec.domain_id,
                "action": "calibration_target_calibrated_tempered",
                "utility": 7,
                "predicted_confidence": calibrated_confidence,
                "thermal_gradient": 0.39,
                "phase_purity": 0.94,
            },
        }
    raise ValueError(f"unknown calibration domain: {spec.domain_id}")


def _calibration_stats(
    overconfident_receipts: tuple[Receipt, ...],
    calibrated_receipts: tuple[Receipt, ...],
) -> dict[str, float]:
    overconfident_confidences = tuple(
        float(receipt.replay_bundle["candidate_payload"]["predicted_confidence"]) for receipt in overconfident_receipts
    )
    calibrated_confidences = tuple(
        float(receipt.replay_bundle["candidate_payload"]["predicted_confidence"]) for receipt in calibrated_receipts
    )
    overconfident_rate = _accept_rate(overconfident_receipts)
    calibrated_rate = _accept_rate(calibrated_receipts)
    overconfident_gap = abs(_mean(overconfident_confidences) - overconfident_rate)
    calibrated_gap = abs(_mean(calibrated_confidences) - calibrated_rate)
    total = len(overconfident_receipts) + len(calibrated_receipts)
    ece = (len(overconfident_receipts) * overconfident_gap + len(calibrated_receipts) * calibrated_gap) / total
    return {
        "overconfident_rate": round(overconfident_rate, 6),
        "calibrated_rate": round(calibrated_rate, 6),
        "overconfident_gap": round(overconfident_gap, 6),
        "calibrated_gap": round(calibrated_gap, 6),
        "ece": round(ece, 6),
    }


def _accept_rate(receipts: tuple[Receipt, ...]) -> float:
    if not receipts:
        raise ValueError("receipts must be non-empty")
    return sum(1 for receipt in receipts if receipt.committed) / len(receipts)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _probability(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value)) and 0.0 <= float(value) <= 1.0


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        raise ValueError("values must be non-empty")
    return sum(float(value) for value in values) / len(values)


def _close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= 1e-6


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_calibration_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
