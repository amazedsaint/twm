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


BRANCH_CONTINUATION_CERTIFICATE_SCHEMA = "trwm.branch_continuation_certificate.v1"
BRANCH_CONTINUATION_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_continuation_transfer_certificate.v1"
BRANCH_CONTINUATION_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1137/1.9780898719154",
)
BRANCH_CONTINUATION_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound continuation paths "
    "can filter direct target jumps before target exploration under a matched three-call verifier "
    "budget. It is not numerical continuation, homotopy continuation, nonlinear root finding, "
    "path-following performance, robotics safety, chemistry, materials discovery, or scientific "
    "autonomy evidence."
)


@dataclass(frozen=True)
class BranchContinuationCertificate:
    schema_version: str
    domain: str
    continuation_rule_id: str
    continuation_rule_version: str
    source_context_id: str
    target_context_id: str
    path_parameter_id: str
    lambda_sequence: tuple[float, ...]
    max_lambda_step: float
    source_continuation_action_ids: tuple[str, ...]
    source_jump_action_id: str
    static_target_action_ids: tuple[str, ...]
    continuation_target_action_ids: tuple[str, ...]
    source_lambda_values: tuple[float, ...]
    source_jump_lambda_value: float
    static_target_lambda_values: tuple[float, ...]
    continuation_target_lambda_values: tuple[float, ...]
    source_continuation_receipt_hashes: tuple[str, ...]
    source_jump_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    continuation_target_receipt_hashes: tuple[str, ...]
    continuation_target_commit_receipt_hashes: tuple[str, ...]
    source_continuation_branch_selection_certificate_hashes: tuple[str, ...]
    source_jump_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    continuation_branch_selection_certificate_hashes: tuple[str, ...]
    source_continuation_committed_count: int
    source_jump_rejected_count: int
    static_committed_count: int
    continuation_committed_count: int
    static_final_committed: bool
    continuation_final_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    continuation_verifier_call_count: int
    same_budget: bool
    continuation_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONTINUATION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch continuation certificate schema: {self.schema_version}")
        for field_name in (
            "lambda_sequence",
            "source_lambda_values",
            "static_target_lambda_values",
            "continuation_target_lambda_values",
        ):
            object.__setattr__(self, field_name, tuple(float(value) for value in getattr(self, field_name)))
        for field_name in (
            "source_continuation_action_ids",
            "static_target_action_ids",
            "continuation_target_action_ids",
            "source_continuation_receipt_hashes",
            "source_jump_receipt_hashes",
            "static_target_receipt_hashes",
            "continuation_target_receipt_hashes",
            "continuation_target_commit_receipt_hashes",
            "source_continuation_branch_selection_certificate_hashes",
            "continuation_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "max_lambda_step", float(self.max_lambda_step))
        object.__setattr__(self, "source_jump_lambda_value", float(self.source_jump_lambda_value))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_continuation_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchContinuationDomainReport:
    domain: str
    source_context: str
    target_context: str
    path_parameter_id: str
    lambda_sequence: tuple[float, ...]
    max_lambda_step: float
    source_continuation_action_ids: tuple[str, ...]
    source_jump_action_id: str
    static_target_action_ids: tuple[str, ...]
    continuation_target_action_ids: tuple[str, ...]
    source_continuation_committed_count: int
    source_jump_rejected_count: int
    static_committed_count: int
    continuation_committed_count: int
    static_final_committed: bool
    continuation_final_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    continuation_verifier_call_count: int
    source_continuation_receipt_hashes: tuple[str, ...]
    source_jump_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    continuation_target_receipt_hashes: tuple[str, ...]
    branch_continuation_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchContinuationTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchContinuationDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_continuation_committed_count: int
    source_jump_rejected_count: int
    static_success_count: int
    continuation_success_count: int
    same_budget_continuation_count: int
    branch_continuation_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_continuation_certificates_valid: bool
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
class BranchContinuationTransferCertificate:
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
    branch_continuation_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_continuation_committed_count: int
    source_jump_rejected_count: int
    static_success_count: int
    continuation_success_count: int
    same_budget_continuation_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CONTINUATION_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch continuation transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_continuation_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_continuation_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchContinuationTransferResult(CertifiedExampleResult):
    report: BranchContinuationTransferReport
    branch_continuation_transfer_certificate: BranchContinuationTransferCertificate
    branch_continuation_certificates: tuple[BranchContinuationCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_continuation_transfer_experiment() -> BranchContinuationTransferReport:
    return run_branch_continuation_transfer_certified_experiment().report


def run_branch_continuation_transfer_certified_experiment() -> CertifiedBranchContinuationTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchContinuationDomainReport] = []
    continuation_certificates: list[BranchContinuationCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_continuation_plan(spec)
        source_context = f"{spec.domain_id}:source:continuation"
        target_context = f"{spec.domain_id}:target:continuation"

        source_outcomes = []
        source_selections = []
        for idx, action in enumerate(plan["source_continuation_actions"]):
            outcome = runtime.step(
                state,
                _make_continuation_traces(spec, context=source_context, phase=f"source-step-{idx}", actions=(action,)),
            )
            state = normalize_state(outcome.state)
            selection = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), selection))
            memory.update_branch(outcome.receipts, selection)
            source_outcomes.append(outcome)
            source_selections.append(selection)

        source_jump_outcome = runtime.step(
            state,
            _make_continuation_traces(
                spec,
                context=source_context,
                phase="source-direct-jump-reject",
                actions=(plan["source_jump_action"],),
            ),
        )
        source_jump_selection = build_branch_selection_certificate(
            source_jump_outcome.receipts,
            verifier_call_count=source_jump_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_jump_outcome.receipts), source_jump_selection))
        memory.update_branch(source_jump_outcome.receipts, source_jump_selection)

        static_outcome = runtime.step(
            state,
            _make_continuation_traces(
                spec,
                context=target_context,
                phase="target-static-direct-jumps",
                actions=plan["target_static_actions"],
            ),
        )
        static_selection = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        continuation_outcomes = []
        continuation_selections = []
        for idx, action in enumerate(plan["target_continuation_actions"]):
            outcome = runtime.step(
                state,
                _make_continuation_traces(
                    spec,
                    context=target_context,
                    phase=f"target-continuation-step-{idx}",
                    actions=(action,),
                ),
            )
            state = normalize_state(outcome.state)
            selection = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), selection))
            continuation_outcomes.append(outcome)
            continuation_selections.append(selection)

        lambda_sequence = tuple(float(action["lambda_value"]) for action in plan["target_continuation_actions"])
        certificate = build_branch_continuation_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            path_parameter_id="lambda",
            lambda_sequence=lambda_sequence,
            max_lambda_step=max(_lambda_gaps(lambda_sequence)),
            source_continuation_action_ids=tuple(str(action["action"]) for action in plan["source_continuation_actions"]),
            source_jump_action_id=str(plan["source_jump_action"]["action"]),
            static_target_action_ids=tuple(str(action["action"]) for action in plan["target_static_actions"]),
            continuation_target_action_ids=tuple(str(action["action"]) for action in plan["target_continuation_actions"]),
            source_lambda_values=tuple(float(action["lambda_value"]) for action in plan["source_continuation_actions"]),
            source_jump_lambda_value=float(plan["source_jump_action"]["lambda_value"]),
            static_target_lambda_values=tuple(float(action["lambda_value"]) for action in plan["target_static_actions"]),
            continuation_target_lambda_values=lambda_sequence,
            source_continuation_receipt_hashes=tuple(
                receipt.receipt_hash for outcome in source_outcomes for receipt in outcome.receipts
            ),
            source_jump_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_jump_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            continuation_target_receipt_hashes=tuple(
                receipt.receipt_hash for outcome in continuation_outcomes for receipt in outcome.receipts
            ),
            continuation_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash
                for outcome in continuation_outcomes
                for receipt in outcome.receipts
                if receipt.committed
            ),
            source_continuation_branch_selection_certificate_hashes=tuple(
                selection.certificate_hash for selection in source_selections
            ),
            source_jump_branch_selection_certificate_hash=source_jump_selection.certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            continuation_branch_selection_certificate_hashes=tuple(
                selection.certificate_hash for selection in continuation_selections
            ),
            source_continuation_committed_count=sum(1 for outcome in source_outcomes if outcome.committed),
            source_jump_rejected_count=sum(1 for receipt in source_jump_outcome.receipts if receipt.hard_result.rejected),
            static_committed_count=sum(1 for receipt in static_outcome.receipts if receipt.committed),
            continuation_committed_count=sum(1 for outcome in continuation_outcomes if outcome.committed),
            static_final_committed=static_outcome.committed,
            continuation_final_committed=continuation_outcomes[-1].committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in source_outcomes)
            + source_jump_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            continuation_verifier_call_count=sum(outcome.verifier_calls for outcome in continuation_outcomes),
        )
        continuation_certificates.append(certificate)
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

    report = BranchContinuationTransferReport(
        schema_version="trwm.example.branch_continuation_transfer.v1",
        experiment_id="branch_continuation_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_continuation_committed_count=sum(row.source_continuation_committed_count for row in rows),
        source_jump_rejected_count=sum(row.source_jump_rejected_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_final_committed),
        continuation_success_count=sum(1 for row in rows if row.continuation_final_committed),
        same_budget_continuation_count=sum(1 for row in rows if row.same_budget),
        branch_continuation_certificate_count=len(continuation_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_continuation_certificates_valid=all(
            validate_branch_continuation_certificate(certificate, row)
            for certificate, row in zip(continuation_certificates, rows)
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
        sources=BRANCH_CONTINUATION_SOURCES,
        learning=(
            "Continuation branch reuse separates path evidence from commit authority. Source receipts "
            "can certify that direct jumps are poor target proposals, but every intermediate target "
            "step still needs its own hard-verifier receipt."
        ),
    )
    transfer_certificate = build_branch_continuation_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_continuation_certificate_hashes=tuple(certificate.certificate_hash for certificate in continuation_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_continuation_transfer",
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
        claim_boundary=BRANCH_CONTINUATION_CLAIM_BOUNDARY,
        sources=BRANCH_CONTINUATION_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchContinuationTransferResult(
        report=report,
        branch_continuation_transfer_certificate=transfer_certificate,
        branch_continuation_certificates=tuple(continuation_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_continuation_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    path_parameter_id: str,
    lambda_sequence: tuple[float, ...],
    max_lambda_step: float,
    source_continuation_action_ids: tuple[str, ...],
    source_jump_action_id: str,
    static_target_action_ids: tuple[str, ...],
    continuation_target_action_ids: tuple[str, ...],
    source_lambda_values: tuple[float, ...],
    source_jump_lambda_value: float,
    static_target_lambda_values: tuple[float, ...],
    continuation_target_lambda_values: tuple[float, ...],
    source_continuation_receipt_hashes: tuple[str, ...],
    source_jump_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    continuation_target_receipt_hashes: tuple[str, ...],
    continuation_target_commit_receipt_hashes: tuple[str, ...],
    source_continuation_branch_selection_certificate_hashes: tuple[str, ...],
    source_jump_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    continuation_branch_selection_certificate_hashes: tuple[str, ...],
    source_continuation_committed_count: int,
    source_jump_rejected_count: int,
    static_committed_count: int,
    continuation_committed_count: int,
    static_final_committed: bool,
    continuation_final_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    continuation_verifier_call_count: int,
) -> BranchContinuationCertificate:
    return BranchContinuationCertificate(
        schema_version=BRANCH_CONTINUATION_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        continuation_rule_id="receipt_bound_continuation_path",
        continuation_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        path_parameter_id=path_parameter_id,
        lambda_sequence=lambda_sequence,
        max_lambda_step=max_lambda_step,
        source_continuation_action_ids=source_continuation_action_ids,
        source_jump_action_id=source_jump_action_id,
        static_target_action_ids=static_target_action_ids,
        continuation_target_action_ids=continuation_target_action_ids,
        source_lambda_values=source_lambda_values,
        source_jump_lambda_value=source_jump_lambda_value,
        static_target_lambda_values=static_target_lambda_values,
        continuation_target_lambda_values=continuation_target_lambda_values,
        source_continuation_receipt_hashes=source_continuation_receipt_hashes,
        source_jump_receipt_hashes=source_jump_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        continuation_target_receipt_hashes=continuation_target_receipt_hashes,
        continuation_target_commit_receipt_hashes=continuation_target_commit_receipt_hashes,
        source_continuation_branch_selection_certificate_hashes=source_continuation_branch_selection_certificate_hashes,
        source_jump_branch_selection_certificate_hash=source_jump_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        continuation_branch_selection_certificate_hashes=continuation_branch_selection_certificate_hashes,
        source_continuation_committed_count=source_continuation_committed_count,
        source_jump_rejected_count=source_jump_rejected_count,
        static_committed_count=static_committed_count,
        continuation_committed_count=continuation_committed_count,
        static_final_committed=static_final_committed,
        continuation_final_committed=continuation_final_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        continuation_verifier_call_count=continuation_verifier_call_count,
        same_budget=static_verifier_call_count == continuation_verifier_call_count == 3,
        continuation_reason="target_path_follows_receipt_bound_continuation_schedule",
    )


def validate_branch_continuation_certificate(
    certificate: BranchContinuationCertificate,
    row: BranchContinuationDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONTINUATION_CERTIFICATE_SCHEMA:
            return False
        if certificate.continuation_rule_id != "receipt_bound_continuation_path":
            return False
        if certificate.continuation_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or certificate.path_parameter_id != "lambda":
            return False
        if len(certificate.lambda_sequence) != 3 or not _strictly_increasing(certificate.lambda_sequence):
            return False
        if not _close(certificate.lambda_sequence[-1], 1.0):
            return False
        if not _close(certificate.max_lambda_step, max(_lambda_gaps(certificate.lambda_sequence))):
            return False
        if certificate.max_lambda_step > 0.34:
            return False
        if certificate.source_lambda_values != certificate.lambda_sequence:
            return False
        if certificate.continuation_target_lambda_values != certificate.lambda_sequence:
            return False
        if not _close(certificate.source_jump_lambda_value, 1.0):
            return False
        if certificate.static_target_lambda_values != (1.0, 1.0, 1.0):
            return False
        if len(certificate.source_continuation_action_ids) != 3:
            return False
        if len(certificate.static_target_action_ids) != 3 or len(certificate.continuation_target_action_ids) != 3:
            return False
        if len(set(certificate.source_continuation_action_ids)) != 3:
            return False
        if len(set(certificate.static_target_action_ids)) != 3:
            return False
        if len(set(certificate.continuation_target_action_ids)) != 3:
            return False
        if certificate.source_continuation_committed_count != 3 or certificate.source_jump_rejected_count != 1:
            return False
        if certificate.static_committed_count != 0 or certificate.continuation_committed_count != 3:
            return False
        if certificate.static_final_committed or not certificate.continuation_final_committed:
            return False
        if certificate.source_verifier_call_count != 4:
            return False
        if certificate.static_verifier_call_count != 3 or certificate.continuation_verifier_call_count != 3:
            return False
        if not certificate.same_budget:
            return False
        if certificate.continuation_reason != "target_path_follows_receipt_bound_continuation_schedule":
            return False
        hash_groups = (
            (certificate.source_continuation_receipt_hashes, 3),
            (certificate.source_jump_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 3),
            (certificate.continuation_target_receipt_hashes, 3),
            (certificate.continuation_target_commit_receipt_hashes, 3),
            (certificate.source_continuation_branch_selection_certificate_hashes, 3),
            (certificate.continuation_branch_selection_certificate_hashes, 3),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_jump_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.path_parameter_id != certificate.path_parameter_id:
                return False
            if row.lambda_sequence != certificate.lambda_sequence or row.max_lambda_step != certificate.max_lambda_step:
                return False
            if row.source_continuation_action_ids != certificate.source_continuation_action_ids:
                return False
            if row.source_jump_action_id != certificate.source_jump_action_id:
                return False
            if row.static_target_action_ids != certificate.static_target_action_ids:
                return False
            if row.continuation_target_action_ids != certificate.continuation_target_action_ids:
                return False
            if row.source_continuation_receipt_hashes != certificate.source_continuation_receipt_hashes:
                return False
            if row.source_jump_receipt_hashes != certificate.source_jump_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.continuation_target_receipt_hashes != certificate.continuation_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_continuation_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_continuation_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_continuation_transfer_certificate(
    report: BranchContinuationTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_continuation_certificate_hashes: tuple[str, ...],
) -> BranchContinuationTransferCertificate:
    return BranchContinuationTransferCertificate(
        schema_version=BRANCH_CONTINUATION_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_continuation_certificate_hashes=branch_continuation_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_continuation_committed_count=report.source_continuation_committed_count,
        source_jump_rejected_count=report.source_jump_rejected_count,
        static_success_count=report.static_success_count,
        continuation_success_count=report.continuation_success_count,
        same_budget_continuation_count=report.same_budget_continuation_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CONTINUATION_CLAIM_BOUNDARY,
    )


def validate_branch_continuation_transfer_certificate(
    certificate: BranchContinuationTransferCertificate,
    report: BranchContinuationTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CONTINUATION_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_continuation_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 10:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 8:
            return False
        if len(certificate.branch_continuation_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_continuation_committed_count != certificate.domain_count * 3:
            return False
        if certificate.source_jump_rejected_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.continuation_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_continuation_count != certificate.domain_count:
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
            if tuple(row.branch_continuation_certificate_hash for row in report.rows) != certificate.branch_continuation_certificate_hashes:
                return False
            if report.branch_continuation_certificate_count != len(certificate.branch_continuation_certificate_hashes):
                return False
            if not report.all_branch_continuation_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_continuation_committed_count != certificate.source_continuation_committed_count:
                return False
            if report.source_jump_rejected_count != certificate.source_jump_rejected_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.continuation_success_count != certificate.continuation_success_count:
                return False
            if report.same_budget_continuation_count != certificate.same_budget_continuation_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_continuation_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_continuation_certificate_hash(
    certificate: BranchContinuationCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchContinuationCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_continuation_transfer_certificate_hash(
    certificate: BranchContinuationTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchContinuationTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchContinuationTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchContinuationTransferReport,
    transfer_certificate: BranchContinuationTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_continuation_transfer_g1",
        claim_text=(
            "Receipt-bound continuation paths can improve local target exploration by replacing failed "
            "direct jumps with verified intermediate target steps under matched verifier-call budgets."
        ),
        evidence_grade="G1",
        scope="branch_continuation_transfer",
        requirements=(
            requirement(
                "branch_continuation_transfer_certificate_valid",
                validate_branch_continuation_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_continuation_certificates_valid", report.all_branch_continuation_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_continuation_commits_all_domains", report.source_continuation_committed_count == report.domain_count * 3),
            requirement("source_jump_rejects_all_domains", report.source_jump_rejected_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("continuation_succeeds_all_domains", report.continuation_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_continuation_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 4),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_continuation_committed_count": report.source_continuation_committed_count,
            "source_jump_rejected_count": report.source_jump_rejected_count,
            "static_success_count": report.static_success_count,
            "continuation_success_count": report.continuation_success_count,
        },
        boundary=BRANCH_CONTINUATION_CLAIM_BOUNDARY,
        sources=BRANCH_CONTINUATION_SOURCES,
    )


def _row_from_certificate(certificate: BranchContinuationCertificate) -> BranchContinuationDomainReport:
    return BranchContinuationDomainReport(
        domain=certificate.domain,
        source_context=certificate.source_context_id,
        target_context=certificate.target_context_id,
        path_parameter_id=certificate.path_parameter_id,
        lambda_sequence=certificate.lambda_sequence,
        max_lambda_step=certificate.max_lambda_step,
        source_continuation_action_ids=certificate.source_continuation_action_ids,
        source_jump_action_id=certificate.source_jump_action_id,
        static_target_action_ids=certificate.static_target_action_ids,
        continuation_target_action_ids=certificate.continuation_target_action_ids,
        source_continuation_committed_count=certificate.source_continuation_committed_count,
        source_jump_rejected_count=certificate.source_jump_rejected_count,
        static_committed_count=certificate.static_committed_count,
        continuation_committed_count=certificate.continuation_committed_count,
        static_final_committed=certificate.static_final_committed,
        continuation_final_committed=certificate.continuation_final_committed,
        source_verifier_call_count=certificate.source_verifier_call_count,
        static_verifier_call_count=certificate.static_verifier_call_count,
        continuation_verifier_call_count=certificate.continuation_verifier_call_count,
        source_continuation_receipt_hashes=certificate.source_continuation_receipt_hashes,
        source_jump_receipt_hashes=certificate.source_jump_receipt_hashes,
        static_target_receipt_hashes=certificate.static_target_receipt_hashes,
        continuation_target_receipt_hashes=certificate.continuation_target_receipt_hashes,
        branch_continuation_certificate_hash=certificate.certificate_hash,
        same_budget=certificate.same_budget,
    )


def _make_continuation_traces(
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
            seeds=("branch-continuation-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.continuation.transfer.v1",
        )
        for action in actions
    )


def _domain_continuation_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    lambda_values = (0.33, 0.66, 1.0)
    if spec.domain_id == "robotics_replan":
        return {
            "source_continuation_actions": (
                {"domain": spec.domain_id, "action": "continuation_source_detour_l033", "utility": 6, "lambda_value": lambda_values[0], "clearance": 0.28, "turn_rate": 0.55},
                {"domain": spec.domain_id, "action": "continuation_source_detour_l066", "utility": 7, "lambda_value": lambda_values[1], "clearance": 0.31, "turn_rate": 0.48},
                {"domain": spec.domain_id, "action": "continuation_source_detour_l100", "utility": 8, "lambda_value": lambda_values[2], "clearance": 0.35, "turn_rate": 0.42},
            ),
            "source_jump_action": {"domain": spec.domain_id, "action": "continuation_source_direct_jump", "utility": 9, "lambda_value": 1.0, "clearance": 0.13, "turn_rate": 0.82},
            "target_static_actions": (
                {"domain": spec.domain_id, "action": "continuation_target_static_jump_a", "utility": 9, "lambda_value": 1.0, "clearance": 0.12, "turn_rate": 0.85},
                {"domain": spec.domain_id, "action": "continuation_target_static_jump_b", "utility": 9, "lambda_value": 1.0, "clearance": 0.16, "turn_rate": 0.78},
                {"domain": spec.domain_id, "action": "continuation_target_static_jump_c", "utility": 9, "lambda_value": 1.0, "clearance": 0.20, "turn_rate": 0.70},
            ),
            "target_continuation_actions": (
                {"domain": spec.domain_id, "action": "continuation_target_detour_l033", "utility": 6, "lambda_value": lambda_values[0], "clearance": 0.27, "turn_rate": 0.56},
                {"domain": spec.domain_id, "action": "continuation_target_detour_l066", "utility": 7, "lambda_value": lambda_values[1], "clearance": 0.31, "turn_rate": 0.50},
                {"domain": spec.domain_id, "action": "continuation_target_detour_l100", "utility": 8, "lambda_value": lambda_values[2], "clearance": 0.34, "turn_rate": 0.44},
            ),
        }
    if spec.domain_id == "molecule_repair":
        return {
            "source_continuation_actions": (
                {"domain": spec.domain_id, "action": "continuation_source_valence_l033", "utility": 6, "lambda_value": lambda_values[0], "valence_ok": True, "strain": 0.32},
                {"domain": spec.domain_id, "action": "continuation_source_valence_l066", "utility": 7, "lambda_value": lambda_values[1], "valence_ok": True, "strain": 0.24},
                {"domain": spec.domain_id, "action": "continuation_source_valence_l100", "utility": 8, "lambda_value": lambda_values[2], "valence_ok": True, "strain": 0.16},
            ),
            "source_jump_action": {"domain": spec.domain_id, "action": "continuation_source_direct_patch", "utility": 9, "lambda_value": 1.0, "valence_ok": False, "strain": 0.55},
            "target_static_actions": (
                {"domain": spec.domain_id, "action": "continuation_target_static_patch_a", "utility": 9, "lambda_value": 1.0, "valence_ok": False, "strain": 0.50},
                {"domain": spec.domain_id, "action": "continuation_target_static_patch_b", "utility": 9, "lambda_value": 1.0, "valence_ok": True, "strain": 0.48},
                {"domain": spec.domain_id, "action": "continuation_target_static_patch_c", "utility": 9, "lambda_value": 1.0, "valence_ok": True, "strain": 0.40},
            ),
            "target_continuation_actions": (
                {"domain": spec.domain_id, "action": "continuation_target_valence_l033", "utility": 6, "lambda_value": lambda_values[0], "valence_ok": True, "strain": 0.33},
                {"domain": spec.domain_id, "action": "continuation_target_valence_l066", "utility": 7, "lambda_value": lambda_values[1], "valence_ok": True, "strain": 0.25},
                {"domain": spec.domain_id, "action": "continuation_target_valence_l100", "utility": 8, "lambda_value": lambda_values[2], "valence_ok": True, "strain": 0.18},
            ),
        }
    if spec.domain_id == "material_process":
        return {
            "source_continuation_actions": (
                {"domain": spec.domain_id, "action": "continuation_source_temper_l033", "utility": 6, "lambda_value": lambda_values[0], "thermal_gradient": 0.48, "phase_purity": 0.91},
                {"domain": spec.domain_id, "action": "continuation_source_temper_l066", "utility": 7, "lambda_value": lambda_values[1], "thermal_gradient": 0.42, "phase_purity": 0.94},
                {"domain": spec.domain_id, "action": "continuation_source_temper_l100", "utility": 8, "lambda_value": lambda_values[2], "thermal_gradient": 0.36, "phase_purity": 0.96},
            ),
            "source_jump_action": {"domain": spec.domain_id, "action": "continuation_source_direct_ramp", "utility": 9, "lambda_value": 1.0, "thermal_gradient": 0.75, "phase_purity": 0.84},
            "target_static_actions": (
                {"domain": spec.domain_id, "action": "continuation_target_static_ramp_a", "utility": 9, "lambda_value": 1.0, "thermal_gradient": 0.75, "phase_purity": 0.84},
                {"domain": spec.domain_id, "action": "continuation_target_static_ramp_b", "utility": 9, "lambda_value": 1.0, "thermal_gradient": 0.68, "phase_purity": 0.86},
                {"domain": spec.domain_id, "action": "continuation_target_static_ramp_c", "utility": 9, "lambda_value": 1.0, "thermal_gradient": 0.60, "phase_purity": 0.88},
            ),
            "target_continuation_actions": (
                {"domain": spec.domain_id, "action": "continuation_target_temper_l033", "utility": 6, "lambda_value": lambda_values[0], "thermal_gradient": 0.49, "phase_purity": 0.91},
                {"domain": spec.domain_id, "action": "continuation_target_temper_l066", "utility": 7, "lambda_value": lambda_values[1], "thermal_gradient": 0.43, "phase_purity": 0.94},
                {"domain": spec.domain_id, "action": "continuation_target_temper_l100", "utility": 8, "lambda_value": lambda_values[2], "thermal_gradient": 0.37, "phase_purity": 0.96},
            ),
        }
    raise ValueError(f"unknown continuation domain: {spec.domain_id}")


def _lambda_gaps(sequence: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(current - previous for previous, current in zip((0.0, *sequence[:-1]), sequence))


def _strictly_increasing(sequence: tuple[float, ...]) -> bool:
    return all(isfinite(value) and 0.0 < value <= 1.0 for value in sequence) and all(
        left < right for left, right in zip(sequence, sequence[1:])
    )


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _close(left: float, right: float) -> bool:
    return isfinite(float(left)) and isfinite(float(right)) and abs(float(left) - float(right)) <= 1e-6


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_continuation_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
