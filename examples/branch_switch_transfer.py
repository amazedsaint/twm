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


BRANCH_SWITCH_CERTIFICATE_SCHEMA = "trwm.branch_switch_certificate.v1"
BRANCH_SWITCH_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_switch_transfer_certificate.v1"
BRANCH_SWITCH_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://eudml.org/doc/132842",
    "https://research.ibm.com/publications/multiparameter-parallel-search-branch-switching--1",
)
BRANCH_SWITCH_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows receipt-bound branch-switch "
    "evidence can filter stale post-switch target proposals before target exploration under a "
    "matched one-call verifier budget. It is not bifurcation analysis, branch-switching algorithm "
    "performance, numerical continuation, homotopy continuation, robotics safety, chemistry, "
    "materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchSwitchCertificate:
    schema_version: str
    domain: str
    switch_rule_id: str
    switch_rule_version: str
    source_context_id: str
    target_context_id: str
    parameter_id: str
    switch_parameter_value: float
    stale_branch_id: str
    switched_branch_id: str
    source_preswitch_action_id: str
    source_stale_action_id: str
    source_switched_action_id: str
    static_target_action: str
    switched_target_action: str
    source_preswitch_parameter_value: float
    source_stale_parameter_value: float
    source_switched_parameter_value: float
    static_target_parameter_value: float
    switched_target_parameter_value: float
    source_preswitch_receipt_hashes: tuple[str, ...]
    source_stale_receipt_hashes: tuple[str, ...]
    source_switched_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    switched_target_receipt_hashes: tuple[str, ...]
    switched_target_commit_receipt_hashes: tuple[str, ...]
    source_preswitch_branch_selection_certificate_hash: str
    source_stale_branch_selection_certificate_hash: str
    source_switched_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    switched_branch_selection_certificate_hash: str
    source_preswitch_committed: bool
    source_stale_rejected: bool
    source_switched_committed: bool
    static_committed: bool
    switched_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    switched_verifier_call_count: int
    same_budget: bool
    switch_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SWITCH_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch switch certificate schema: {self.schema_version}")
        for field_name in (
            "switch_parameter_value",
            "source_preswitch_parameter_value",
            "source_stale_parameter_value",
            "source_switched_parameter_value",
            "static_target_parameter_value",
            "switched_target_parameter_value",
        ):
            object.__setattr__(self, field_name, float(getattr(self, field_name)))
        for field_name in (
            "source_preswitch_receipt_hashes",
            "source_stale_receipt_hashes",
            "source_switched_receipt_hashes",
            "static_target_receipt_hashes",
            "switched_target_receipt_hashes",
            "switched_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_switch_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchSwitchDomainReport:
    domain: str
    source_context: str
    target_context: str
    parameter_id: str
    switch_parameter_value: float
    stale_branch_id: str
    switched_branch_id: str
    source_preswitch_action_id: str
    source_stale_action_id: str
    source_switched_action_id: str
    static_target_action: str
    switched_target_action: str
    source_preswitch_committed: bool
    source_stale_rejected: bool
    source_switched_committed: bool
    static_committed: bool
    switched_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    switched_verifier_call_count: int
    source_preswitch_receipt_hashes: tuple[str, ...]
    source_stale_receipt_hashes: tuple[str, ...]
    source_switched_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    switched_target_receipt_hashes: tuple[str, ...]
    branch_switch_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchSwitchTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchSwitchDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_preswitch_committed_count: int
    source_stale_rejected_count: int
    source_switched_committed_count: int
    static_success_count: int
    switched_success_count: int
    same_budget_switch_count: int
    branch_switch_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_switch_certificates_valid: bool
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
class BranchSwitchTransferCertificate:
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
    branch_switch_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_preswitch_committed_count: int
    source_stale_rejected_count: int
    source_switched_committed_count: int
    static_success_count: int
    switched_success_count: int
    same_budget_switch_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SWITCH_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch switch transfer certificate schema: {self.schema_version}")
        for field_name in ("domains", "receipt_hashes", "branch_selection_certificate_hashes", "branch_switch_certificate_hashes"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_switch_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchSwitchTransferResult(CertifiedExampleResult):
    report: BranchSwitchTransferReport
    branch_switch_transfer_certificate: BranchSwitchTransferCertificate
    branch_switch_certificates: tuple[BranchSwitchCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_switch_transfer_experiment() -> BranchSwitchTransferReport:
    return run_branch_switch_transfer_certified_experiment().report


def run_branch_switch_transfer_certified_experiment() -> CertifiedBranchSwitchTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchSwitchDomainReport] = []
    switch_certificates: list[BranchSwitchCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        plan = _domain_switch_plan(spec)
        source_context = f"{spec.domain_id}:source:branch-switch"
        target_context = f"{spec.domain_id}:target:branch-switch"

        preswitch_outcome = runtime.step(
            state,
            _make_switch_traces(spec, context=source_context, phase="source-preswitch", actions=(plan["source_preswitch_action"],)),
        )
        state = normalize_state(preswitch_outcome.state)
        preswitch_selection = build_branch_selection_certificate(preswitch_outcome.receipts, verifier_call_count=preswitch_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(preswitch_outcome.receipts), preswitch_selection))
        memory.update_branch(preswitch_outcome.receipts, preswitch_selection)

        stale_outcome = runtime.step(
            state,
            _make_switch_traces(spec, context=source_context, phase="source-stale-after-switch", actions=(plan["source_stale_action"],)),
        )
        stale_selection = build_branch_selection_certificate(stale_outcome.receipts, verifier_call_count=stale_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(stale_outcome.receipts), stale_selection))
        memory.update_branch(stale_outcome.receipts, stale_selection)

        switched_source_outcome = runtime.step(
            state,
            _make_switch_traces(spec, context=source_context, phase="source-switched", actions=(plan["source_switched_action"],)),
        )
        state = normalize_state(switched_source_outcome.state)
        switched_source_selection = build_branch_selection_certificate(
            switched_source_outcome.receipts,
            verifier_call_count=switched_source_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(switched_source_outcome.receipts), switched_source_selection))
        memory.update_branch(switched_source_outcome.receipts, switched_source_selection)

        static_outcome = runtime.step(
            state,
            _make_switch_traces(spec, context=target_context, phase="target-static-stale", actions=(plan["target_static"],)),
        )
        static_selection = build_branch_selection_certificate(static_outcome.receipts, verifier_call_count=static_outcome.verifier_calls)
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_selection))

        switched_target_outcome = runtime.step(
            state,
            _make_switch_traces(spec, context=target_context, phase="target-switched", actions=(plan["target_switched"],)),
        )
        state = normalize_state(switched_target_outcome.state)
        switched_target_selection = build_branch_selection_certificate(
            switched_target_outcome.receipts,
            verifier_call_count=switched_target_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(switched_target_outcome.receipts), switched_target_selection))

        certificate = build_branch_switch_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            parameter_id="lambda",
            switch_parameter_value=float(plan["switch_parameter_value"]),
            stale_branch_id=str(plan["stale_branch_id"]),
            switched_branch_id=str(plan["switched_branch_id"]),
            source_preswitch_action_id=str(plan["source_preswitch_action"]["action"]),
            source_stale_action_id=str(plan["source_stale_action"]["action"]),
            source_switched_action_id=str(plan["source_switched_action"]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            switched_target_action=str(plan["target_switched"]["action"]),
            source_preswitch_parameter_value=float(plan["source_preswitch_action"]["switch_parameter_value"]),
            source_stale_parameter_value=float(plan["source_stale_action"]["switch_parameter_value"]),
            source_switched_parameter_value=float(plan["source_switched_action"]["switch_parameter_value"]),
            static_target_parameter_value=float(plan["target_static"]["switch_parameter_value"]),
            switched_target_parameter_value=float(plan["target_switched"]["switch_parameter_value"]),
            source_preswitch_receipt_hashes=tuple(receipt.receipt_hash for receipt in preswitch_outcome.receipts),
            source_stale_receipt_hashes=tuple(receipt.receipt_hash for receipt in stale_outcome.receipts),
            source_switched_receipt_hashes=tuple(receipt.receipt_hash for receipt in switched_source_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            switched_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in switched_target_outcome.receipts),
            switched_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in switched_target_outcome.receipts if receipt.committed
            ),
            source_preswitch_branch_selection_certificate_hash=preswitch_selection.certificate_hash,
            source_stale_branch_selection_certificate_hash=stale_selection.certificate_hash,
            source_switched_branch_selection_certificate_hash=switched_source_selection.certificate_hash,
            static_branch_selection_certificate_hash=static_selection.certificate_hash,
            switched_branch_selection_certificate_hash=switched_target_selection.certificate_hash,
            source_preswitch_committed=preswitch_outcome.committed,
            source_stale_rejected=any(receipt.hard_result.rejected for receipt in stale_outcome.receipts),
            source_switched_committed=switched_source_outcome.committed,
            static_committed=static_outcome.committed,
            switched_committed=switched_target_outcome.committed,
            source_verifier_call_count=preswitch_outcome.verifier_calls + stale_outcome.verifier_calls + switched_source_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            switched_verifier_call_count=switched_target_outcome.verifier_calls,
        )
        switch_certificates.append(certificate)
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

    report = BranchSwitchTransferReport(
        schema_version="trwm.example.branch_switch_transfer.v1",
        experiment_id="branch_switch_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_preswitch_committed_count=sum(1 for row in rows if row.source_preswitch_committed),
        source_stale_rejected_count=sum(1 for row in rows if row.source_stale_rejected),
        source_switched_committed_count=sum(1 for row in rows if row.source_switched_committed),
        static_success_count=sum(1 for row in rows if row.static_committed),
        switched_success_count=sum(1 for row in rows if row.switched_committed),
        same_budget_switch_count=sum(1 for row in rows if row.same_budget),
        branch_switch_certificate_count=len(switch_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_switch_certificates_valid=all(
            validate_branch_switch_certificate(certificate, row)
            for certificate, row in zip(switch_certificates, rows)
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
        sources=BRANCH_SWITCH_SOURCES,
        learning=(
            "Branch-switch reuse separates switchpoint evidence from commit authority. Source receipts "
            "can mark a stale branch as invalid after the switch and identify a switched branch to try, "
            "but the target switched branch still commits only through a fresh hard-verifier receipt."
        ),
    )
    transfer_certificate = build_branch_switch_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_switch_certificate_hashes=tuple(certificate.certificate_hash for certificate in switch_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_switch_transfer",
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
        claim_boundary=BRANCH_SWITCH_CLAIM_BOUNDARY,
        sources=BRANCH_SWITCH_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchSwitchTransferResult(
        report=report,
        branch_switch_transfer_certificate=transfer_certificate,
        branch_switch_certificates=tuple(switch_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_switch_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    parameter_id: str,
    switch_parameter_value: float,
    stale_branch_id: str,
    switched_branch_id: str,
    source_preswitch_action_id: str,
    source_stale_action_id: str,
    source_switched_action_id: str,
    static_target_action: str,
    switched_target_action: str,
    source_preswitch_parameter_value: float,
    source_stale_parameter_value: float,
    source_switched_parameter_value: float,
    static_target_parameter_value: float,
    switched_target_parameter_value: float,
    source_preswitch_receipt_hashes: tuple[str, ...],
    source_stale_receipt_hashes: tuple[str, ...],
    source_switched_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    switched_target_receipt_hashes: tuple[str, ...],
    switched_target_commit_receipt_hashes: tuple[str, ...],
    source_preswitch_branch_selection_certificate_hash: str,
    source_stale_branch_selection_certificate_hash: str,
    source_switched_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    switched_branch_selection_certificate_hash: str,
    source_preswitch_committed: bool,
    source_stale_rejected: bool,
    source_switched_committed: bool,
    static_committed: bool,
    switched_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    switched_verifier_call_count: int,
) -> BranchSwitchCertificate:
    return BranchSwitchCertificate(
        schema_version=BRANCH_SWITCH_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        switch_rule_id="receipt_bound_branch_switchpoint",
        switch_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        parameter_id=parameter_id,
        switch_parameter_value=switch_parameter_value,
        stale_branch_id=stale_branch_id,
        switched_branch_id=switched_branch_id,
        source_preswitch_action_id=source_preswitch_action_id,
        source_stale_action_id=source_stale_action_id,
        source_switched_action_id=source_switched_action_id,
        static_target_action=static_target_action,
        switched_target_action=switched_target_action,
        source_preswitch_parameter_value=source_preswitch_parameter_value,
        source_stale_parameter_value=source_stale_parameter_value,
        source_switched_parameter_value=source_switched_parameter_value,
        static_target_parameter_value=static_target_parameter_value,
        switched_target_parameter_value=switched_target_parameter_value,
        source_preswitch_receipt_hashes=source_preswitch_receipt_hashes,
        source_stale_receipt_hashes=source_stale_receipt_hashes,
        source_switched_receipt_hashes=source_switched_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        switched_target_receipt_hashes=switched_target_receipt_hashes,
        switched_target_commit_receipt_hashes=switched_target_commit_receipt_hashes,
        source_preswitch_branch_selection_certificate_hash=source_preswitch_branch_selection_certificate_hash,
        source_stale_branch_selection_certificate_hash=source_stale_branch_selection_certificate_hash,
        source_switched_branch_selection_certificate_hash=source_switched_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        switched_branch_selection_certificate_hash=switched_branch_selection_certificate_hash,
        source_preswitch_committed=source_preswitch_committed,
        source_stale_rejected=source_stale_rejected,
        source_switched_committed=source_switched_committed,
        static_committed=static_committed,
        switched_committed=switched_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        switched_verifier_call_count=switched_verifier_call_count,
        same_budget=static_verifier_call_count == switched_verifier_call_count == 1,
        switch_reason="target_after_switch_uses_receipt_bound_switched_branch",
    )


def validate_branch_switch_certificate(
    certificate: BranchSwitchCertificate,
    row: BranchSwitchDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_SWITCH_CERTIFICATE_SCHEMA:
            return False
        if certificate.switch_rule_id != "receipt_bound_branch_switchpoint":
            return False
        if certificate.switch_rule_version != "1.0" or certificate.parameter_id != "lambda":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.stale_branch_id):
            return False
        if not _nonempty(certificate.switched_branch_id) or certificate.stale_branch_id == certificate.switched_branch_id:
            return False
        if not _probability(certificate.switch_parameter_value):
            return False
        if not certificate.source_preswitch_parameter_value < certificate.switch_parameter_value:
            return False
        for value in (
            certificate.source_stale_parameter_value,
            certificate.source_switched_parameter_value,
            certificate.static_target_parameter_value,
            certificate.switched_target_parameter_value,
        ):
            if value <= certificate.switch_parameter_value or value > 1.0:
                return False
        if not (certificate.source_preswitch_committed and certificate.source_stale_rejected and certificate.source_switched_committed):
            return False
        if certificate.static_committed or not certificate.switched_committed:
            return False
        if certificate.source_verifier_call_count != 3:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.switched_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.switch_reason != "target_after_switch_uses_receipt_bound_switched_branch":
            return False
        hash_groups = (
            (certificate.source_preswitch_receipt_hashes, 1),
            (certificate.source_stale_receipt_hashes, 1),
            (certificate.source_switched_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.switched_target_receipt_hashes, 1),
            (certificate.switched_target_commit_receipt_hashes, 1),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_preswitch_branch_selection_certificate_hash,
            certificate.source_stale_branch_selection_certificate_hash,
            certificate.source_switched_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.switched_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.parameter_id != certificate.parameter_id:
                return False
            if row.switch_parameter_value != certificate.switch_parameter_value:
                return False
            if row.stale_branch_id != certificate.stale_branch_id or row.switched_branch_id != certificate.switched_branch_id:
                return False
            if row.source_preswitch_action_id != certificate.source_preswitch_action_id:
                return False
            if row.source_stale_action_id != certificate.source_stale_action_id:
                return False
            if row.source_switched_action_id != certificate.source_switched_action_id:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.switched_target_action != certificate.switched_target_action:
                return False
            if row.source_preswitch_receipt_hashes != certificate.source_preswitch_receipt_hashes:
                return False
            if row.source_stale_receipt_hashes != certificate.source_stale_receipt_hashes:
                return False
            if row.source_switched_receipt_hashes != certificate.source_switched_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.switched_target_receipt_hashes != certificate.switched_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_switch_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_switch_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_switch_transfer_certificate(
    report: BranchSwitchTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_switch_certificate_hashes: tuple[str, ...],
) -> BranchSwitchTransferCertificate:
    return BranchSwitchTransferCertificate(
        schema_version=BRANCH_SWITCH_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_switch_certificate_hashes=branch_switch_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_preswitch_committed_count=report.source_preswitch_committed_count,
        source_stale_rejected_count=report.source_stale_rejected_count,
        source_switched_committed_count=report.source_switched_committed_count,
        static_success_count=report.static_success_count,
        switched_success_count=report.switched_success_count,
        same_budget_switch_count=report.same_budget_switch_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_SWITCH_CLAIM_BOUNDARY,
    )


def validate_branch_switch_transfer_certificate(
    certificate: BranchSwitchTransferCertificate,
    report: BranchSwitchTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_SWITCH_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        if not _is_hash(certificate.report_hash) or not _is_hash(certificate.ledger_head):
            return False
        if not _is_hash(certificate.memory_snapshot_hash):
            return False
        for values in (certificate.receipt_hashes, certificate.branch_selection_certificate_hashes, certificate.branch_switch_certificate_hashes):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_switch_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_preswitch_committed_count != certificate.domain_count:
            return False
        if certificate.source_stale_rejected_count != certificate.domain_count:
            return False
        if certificate.source_switched_committed_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.switched_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_switch_count != certificate.domain_count:
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
            if tuple(row.branch_switch_certificate_hash for row in report.rows) != certificate.branch_switch_certificate_hashes:
                return False
            if report.branch_switch_certificate_count != len(certificate.branch_switch_certificate_hashes):
                return False
            if not report.all_branch_switch_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_preswitch_committed_count != certificate.source_preswitch_committed_count:
                return False
            if report.source_stale_rejected_count != certificate.source_stale_rejected_count:
                return False
            if report.source_switched_committed_count != certificate.source_switched_committed_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.switched_success_count != certificate.switched_success_count:
                return False
            if report.same_budget_switch_count != certificate.same_budget_switch_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_switch_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_switch_certificate_hash(certificate: BranchSwitchCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchSwitchCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_switch_transfer_certificate_hash(certificate: BranchSwitchTransferCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchSwitchTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchSwitchTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchSwitchTransferReport,
    transfer_certificate: BranchSwitchTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_switch_transfer_g1",
        claim_text=(
            "Receipt-bound switchpoint certificates can improve local target exploration by filtering "
            "stale post-switch branches and trying switched branches under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_switch_transfer",
        requirements=(
            requirement(
                "branch_switch_transfer_certificate_valid",
                validate_branch_switch_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_switch_certificates_valid", report.all_branch_switch_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_preswitch_commits_all_domains", report.source_preswitch_committed_count == report.domain_count),
            requirement("source_stale_rejects_all_domains", report.source_stale_rejected_count == report.domain_count),
            requirement("source_switched_commits_all_domains", report.source_switched_committed_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("switched_succeeds_all_domains", report.switched_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_switch_count == report.domain_count),
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
            "switched_success_count": report.switched_success_count,
        },
        boundary=BRANCH_SWITCH_CLAIM_BOUNDARY,
        sources=BRANCH_SWITCH_SOURCES,
    )


def _row_from_certificate(certificate: BranchSwitchCertificate) -> BranchSwitchDomainReport:
    return BranchSwitchDomainReport(
        domain=certificate.domain,
        source_context=certificate.source_context_id,
        target_context=certificate.target_context_id,
        parameter_id=certificate.parameter_id,
        switch_parameter_value=certificate.switch_parameter_value,
        stale_branch_id=certificate.stale_branch_id,
        switched_branch_id=certificate.switched_branch_id,
        source_preswitch_action_id=certificate.source_preswitch_action_id,
        source_stale_action_id=certificate.source_stale_action_id,
        source_switched_action_id=certificate.source_switched_action_id,
        static_target_action=certificate.static_target_action,
        switched_target_action=certificate.switched_target_action,
        source_preswitch_committed=certificate.source_preswitch_committed,
        source_stale_rejected=certificate.source_stale_rejected,
        source_switched_committed=certificate.source_switched_committed,
        static_committed=certificate.static_committed,
        switched_committed=certificate.switched_committed,
        source_verifier_call_count=certificate.source_verifier_call_count,
        static_verifier_call_count=certificate.static_verifier_call_count,
        switched_verifier_call_count=certificate.switched_verifier_call_count,
        source_preswitch_receipt_hashes=certificate.source_preswitch_receipt_hashes,
        source_stale_receipt_hashes=certificate.source_stale_receipt_hashes,
        source_switched_receipt_hashes=certificate.source_switched_receipt_hashes,
        static_target_receipt_hashes=certificate.static_target_receipt_hashes,
        switched_target_receipt_hashes=certificate.switched_target_receipt_hashes,
        branch_switch_certificate_hash=certificate.certificate_hash,
        same_budget=certificate.same_budget,
    )


def _make_switch_traces(
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
            seeds=("branch-switch-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.switch.transfer.v1",
        )
        for action in actions
    )


def _domain_switch_plan(spec: ExplorationDomainSpec) -> Mapping[str, Any]:
    base = {
        "switch_parameter_value": 0.50,
        "stale_branch_id": "pre_switch_branch",
        "switched_branch_id": "post_switch_branch",
    }
    if spec.domain_id == "robotics_replan":
        return {
            **base,
            "source_preswitch_action": {"domain": spec.domain_id, "action": "switch_source_narrow_detour_l040", "utility": 6, "switch_parameter_value": 0.40, "clearance": 0.30, "turn_rate": 0.55},
            "source_stale_action": {"domain": spec.domain_id, "action": "switch_source_stale_cut_l070", "utility": 9, "switch_parameter_value": 0.70, "clearance": 0.18, "turn_rate": 0.78},
            "source_switched_action": {"domain": spec.domain_id, "action": "switch_source_wide_detour_l070", "utility": 8, "switch_parameter_value": 0.70, "clearance": 0.34, "turn_rate": 0.44},
            "target_static": {"domain": spec.domain_id, "action": "switch_target_stale_cut_l072", "utility": 9, "switch_parameter_value": 0.72, "clearance": 0.16, "turn_rate": 0.82},
            "target_switched": {"domain": spec.domain_id, "action": "switch_target_wide_detour_l072", "utility": 8, "switch_parameter_value": 0.72, "clearance": 0.35, "turn_rate": 0.43},
        }
    if spec.domain_id == "molecule_repair":
        return {
            **base,
            "source_preswitch_action": {"domain": spec.domain_id, "action": "switch_source_soft_patch_l040", "utility": 6, "switch_parameter_value": 0.40, "valence_ok": True, "strain": 0.30},
            "source_stale_action": {"domain": spec.domain_id, "action": "switch_source_stale_patch_l070", "utility": 9, "switch_parameter_value": 0.70, "valence_ok": True, "strain": 0.48},
            "source_switched_action": {"domain": spec.domain_id, "action": "switch_source_valence_relief_l070", "utility": 8, "switch_parameter_value": 0.70, "valence_ok": True, "strain": 0.20},
            "target_static": {"domain": spec.domain_id, "action": "switch_target_stale_patch_l072", "utility": 9, "switch_parameter_value": 0.72, "valence_ok": False, "strain": 0.44},
            "target_switched": {"domain": spec.domain_id, "action": "switch_target_valence_relief_l072", "utility": 8, "switch_parameter_value": 0.72, "valence_ok": True, "strain": 0.18},
        }
    if spec.domain_id == "material_process":
        return {
            **base,
            "source_preswitch_action": {"domain": spec.domain_id, "action": "switch_source_slow_ramp_l040", "utility": 6, "switch_parameter_value": 0.40, "thermal_gradient": 0.48, "phase_purity": 0.91},
            "source_stale_action": {"domain": spec.domain_id, "action": "switch_source_stale_ramp_l070", "utility": 9, "switch_parameter_value": 0.70, "thermal_gradient": 0.68, "phase_purity": 0.86},
            "source_switched_action": {"domain": spec.domain_id, "action": "switch_source_tempered_branch_l070", "utility": 8, "switch_parameter_value": 0.70, "thermal_gradient": 0.39, "phase_purity": 0.95},
            "target_static": {"domain": spec.domain_id, "action": "switch_target_stale_ramp_l072", "utility": 9, "switch_parameter_value": 0.72, "thermal_gradient": 0.70, "phase_purity": 0.86},
            "target_switched": {"domain": spec.domain_id, "action": "switch_target_tempered_branch_l072", "utility": 8, "switch_parameter_value": 0.72, "thermal_gradient": 0.38, "phase_purity": 0.96},
        }
    raise ValueError(f"unknown switch domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _probability(value: Any) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value)) and 0.0 < float(value) < 1.0


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_switch_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
