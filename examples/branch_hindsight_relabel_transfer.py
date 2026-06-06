from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Iterable, Mapping

from examples.ancestral_branch_exploration import ANCESTRAL_BRANCH_SOURCES, DOMAIN_SPECS, ExplorationDomainSpec
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
from trwm.core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


BRANCH_HINDSIGHT_RELABEL_CERTIFICATE_SCHEMA = "trwm.branch_hindsight_relabel_certificate.v1"
BRANCH_HINDSIGHT_RELABEL_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_hindsight_relabel_transfer_certificate.v1"
BRANCH_HINDSIGHT_RELABEL_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://papers.neurips.cc/paper/7090-hindsight-experience-replay",
)
BRANCH_HINDSIGHT_RELABEL_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows a rejected past branch can guide "
    "a relabeled target-goal proposal under a matched one-call verifier budget, but only after the "
    "target hard verifier creates a fresh committing receipt. It is not Hindsight Experience Replay, "
    "reinforcement learning, automatic goal discovery, robotics safety, chemistry, materials discovery, "
    "or scientific autonomy evidence."
)


@dataclass(frozen=True)
class HindsightGoalState:
    committed_goals: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class BranchHindsightRelabelCertificate:
    schema_version: str
    domain: str
    relabel_rule_id: str
    relabel_rule_version: str
    source_context_id: str
    target_context_id: str
    intended_goal: str
    achieved_goal: str
    relabeled_goal: str
    source_action: str
    static_target_action: str
    relabeled_target_action: str
    source_reject_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    relabeled_target_receipt_hashes: tuple[str, ...]
    relabeled_target_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    relabeled_branch_selection_certificate_hash: str
    source_rejected: bool
    static_committed: bool
    relabeled_committed: bool
    static_verifier_call_count: int
    relabeled_verifier_call_count: int
    same_budget: bool
    relabel_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_HINDSIGHT_RELABEL_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch hindsight relabel certificate schema: {self.schema_version}")
        for field_name in (
            "source_reject_receipt_hashes",
            "static_target_receipt_hashes",
            "relabeled_target_receipt_hashes",
            "relabeled_target_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_hindsight_relabel_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchHindsightRelabelDomainReport:
    domain: str
    source_context: str
    target_context: str
    intended_goal: str
    achieved_goal: str
    relabeled_goal: str
    source_action: str
    static_target_action: str
    relabeled_target_action: str
    source_rejected: bool
    static_committed: bool
    relabeled_committed: bool
    static_verifier_call_count: int
    relabeled_verifier_call_count: int
    source_reject_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    relabeled_target_receipt_hashes: tuple[str, ...]
    hindsight_relabel_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchHindsightRelabelTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchHindsightRelabelDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_reject_count: int
    static_success_count: int
    relabeled_success_count: int
    relabeled_goal_count: int
    same_budget_hindsight_count: int
    branch_hindsight_relabel_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_hindsight_relabel_certificates_valid: bool
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
class BranchHindsightRelabelTransferCertificate:
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
    branch_hindsight_relabel_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_reject_count: int
    static_success_count: int
    relabeled_success_count: int
    relabeled_goal_count: int
    same_budget_hindsight_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_HINDSIGHT_RELABEL_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch hindsight relabel transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_hindsight_relabel_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_hindsight_relabel_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchHindsightRelabelTransferResult(CertifiedExampleResult):
    report: BranchHindsightRelabelTransferReport
    branch_hindsight_relabel_transfer_certificate: BranchHindsightRelabelTransferCertificate
    branch_hindsight_relabel_certificates: tuple[BranchHindsightRelabelCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


class HindsightGoalAdapter:
    verifier_id = "branch_hindsight_goal_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        metadata = {
            "domain": payload["domain"],
            "context": payload["context"],
            "action": payload["action"],
            "goal": payload["goal"],
            "achieved_goal": payload["achieved_goal"],
            "utility": payload["utility"],
        }
        accepted, residual = _verify_physics(payload)
        if not accepted:
            return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual=residual, metadata=metadata)
        if payload["achieved_goal"] != payload["goal"]:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={
                    "kind": "hindsight_goal_mismatch",
                    "intended_goal": payload["goal"],
                    "achieved_goal": payload["achieved_goal"],
                },
                metadata=metadata,
            )
        return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)

    def apply_commit(self, state: HindsightGoalState, candidate: TypedCandidate) -> HindsightGoalState:
        current = normalize_hindsight_state(state)
        payload = _normalize_payload(candidate.payload)
        return HindsightGoalState(
            committed_goals=(
                *current.committed_goals,
                (payload["domain"], payload["action"], payload["goal"]),
            )
        )

    def replay(self, state: HindsightGoalState, receipt: Receipt) -> HindsightGoalState:
        candidate = TypedCandidate(
            payload=receipt.replay_bundle["candidate_payload"],
            type_name=receipt.replay_bundle["candidate_type"],
            schema_version=receipt.replay_bundle["candidate_schema"],
        )
        return self.apply_commit(state, candidate)

    def rollback(self, _state: HindsightGoalState, receipt: Receipt) -> HindsightGoalState:
        return normalize_hindsight_state(receipt.rollback_bundle["pre_state"])


class HindsightGoalProjector:
    def project(self, _state: HindsightGoalState, trace: ProposalTrace) -> TypedCandidate:
        return TypedCandidate(
            payload=_normalize_payload(trace.actions[-1]),
            type_name="branch.hindsight.goal_action",
            schema_version="branch.hindsight.goal_action.v1",
        )


def run_branch_hindsight_relabel_transfer_experiment() -> BranchHindsightRelabelTransferReport:
    return run_branch_hindsight_relabel_transfer_certified_experiment().report


def run_branch_hindsight_relabel_transfer_certified_experiment() -> CertifiedBranchHindsightRelabelTransferResult:
    seed = HindsightGoalState()
    state = seed
    engine = TransactionEngine(HindsightGoalAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, HindsightGoalProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchHindsightRelabelDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    hindsight_certificates: list[BranchHindsightRelabelCertificate] = []

    for spec in DOMAIN_SPECS:
        intended_goal, achieved_goal = _goals(spec)
        source_context = f"{spec.domain_id}:source:hindsight:{intended_goal}"
        target_context = f"{spec.domain_id}:target:hindsight:{achieved_goal}"
        source_action = _source_hindsight_action(spec, source_context, intended_goal, achieved_goal)
        static_action = _static_target_action(spec, target_context, achieved_goal)
        relabeled_action = _relabeled_target_action(source_action, target_context, achieved_goal)

        source_outcome = runtime.step(
            state,
            _make_hindsight_traces(
                spec,
                context=source_context,
                phase="source-intended-goal",
                actions=(source_action,),
            ),
        )
        source_certificate = build_branch_selection_certificate(
            source_outcome.receipts,
            verifier_call_count=source_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_outcome.receipts), source_certificate))
        memory.update_branch(source_outcome.receipts, source_certificate)

        static_outcome = runtime.step(
            state,
            _make_hindsight_traces(
                spec,
                context=target_context,
                phase="target-static-goal",
                actions=(static_action,),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        relabeled_outcome = runtime.step(
            state,
            _make_hindsight_traces(
                spec,
                context=target_context,
                phase="target-hindsight-relabel",
                actions=(relabeled_action,),
            ),
        )
        state = normalize_hindsight_state(relabeled_outcome.state)
        relabeled_certificate = build_branch_selection_certificate(
            relabeled_outcome.receipts,
            verifier_call_count=relabeled_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(relabeled_outcome.receipts), relabeled_certificate))

        certificate = build_branch_hindsight_relabel_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            intended_goal=intended_goal,
            achieved_goal=achieved_goal,
            relabeled_goal=achieved_goal,
            source_action=str(source_action["action"]),
            static_target_action=str(static_action["action"]),
            relabeled_target_action=str(relabeled_action["action"]),
            source_reject_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_outcome.receipts),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            relabeled_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in relabeled_outcome.receipts),
            relabeled_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in relabeled_outcome.receipts if receipt.committed
            ),
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            relabeled_branch_selection_certificate_hash=relabeled_certificate.certificate_hash,
            source_rejected=source_outcome.reason == "no_admissible_branch",
            static_committed=static_outcome.committed,
            relabeled_committed=relabeled_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            relabeled_verifier_call_count=relabeled_outcome.verifier_calls,
        )
        hindsight_certificates.append(certificate)

        rows.append(
            BranchHindsightRelabelDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                intended_goal=intended_goal,
                achieved_goal=achieved_goal,
                relabeled_goal=achieved_goal,
                source_action=certificate.source_action,
                static_target_action=certificate.static_target_action,
                relabeled_target_action=certificate.relabeled_target_action,
                source_rejected=certificate.source_rejected,
                static_committed=static_outcome.committed,
                relabeled_committed=relabeled_outcome.committed,
                static_verifier_call_count=static_outcome.verifier_calls,
                relabeled_verifier_call_count=relabeled_outcome.verifier_calls,
                source_reject_receipt_hashes=certificate.source_reject_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                relabeled_target_receipt_hashes=certificate.relabeled_target_receipt_hashes,
                hindsight_relabel_certificate_hash=certificate.certificate_hash,
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

    report = BranchHindsightRelabelTransferReport(
        schema_version="trwm.example.branch_hindsight_relabel_transfer.v1",
        experiment_id="branch_hindsight_relabel_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_reject_count=sum(1 for row in rows if row.source_rejected),
        static_success_count=sum(1 for row in rows if row.static_committed),
        relabeled_success_count=sum(1 for row in rows if row.relabeled_committed),
        relabeled_goal_count=sum(1 for row in rows if row.achieved_goal == row.relabeled_goal and row.relabeled_goal != row.intended_goal),
        same_budget_hindsight_count=sum(1 for row in rows if row.same_budget),
        branch_hindsight_relabel_certificate_count=len(hindsight_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_hindsight_relabel_certificates_valid=all(
            validate_branch_hindsight_relabel_certificate(certificate) for certificate in hindsight_certificates
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
        hard_gate_keys=(
            "goal",
            "achieved_goal",
            "clearance",
            "turn_rate",
            "valence_ok",
            "strain",
            "thermal_gradient",
            "phase_purity",
        ),
        residual_kinds=tuple(sorted({*{spec.residual_kind for spec in DOMAIN_SPECS}, "hindsight_goal_mismatch"})),
        sources=BRANCH_HINDSIGHT_RELABEL_SOURCES,
        learning=(
            "Rejected past branches can improve exploration when they expose an achieved goal: the target "
            "static branch fails under the same one-call budget, while the hindsight-relabeled branch "
            "commits only after fresh target hard verification."
        ),
    )
    transfer_certificate = build_branch_hindsight_relabel_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_hindsight_relabel_certificate_hashes=tuple(certificate.certificate_hash for certificate in hindsight_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_hindsight_relabel_transfer",
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
        claim_boundary=BRANCH_HINDSIGHT_RELABEL_CLAIM_BOUNDARY,
        sources=BRANCH_HINDSIGHT_RELABEL_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchHindsightRelabelTransferResult(
        report=report,
        branch_hindsight_relabel_transfer_certificate=transfer_certificate,
        branch_hindsight_relabel_certificates=tuple(hindsight_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_hindsight_relabel_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    intended_goal: str,
    achieved_goal: str,
    relabeled_goal: str,
    source_action: str,
    static_target_action: str,
    relabeled_target_action: str,
    source_reject_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    relabeled_target_receipt_hashes: tuple[str, ...],
    relabeled_target_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    relabeled_branch_selection_certificate_hash: str,
    source_rejected: bool,
    static_committed: bool,
    relabeled_committed: bool,
    static_verifier_call_count: int,
    relabeled_verifier_call_count: int,
) -> BranchHindsightRelabelCertificate:
    return BranchHindsightRelabelCertificate(
        schema_version=BRANCH_HINDSIGHT_RELABEL_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        relabel_rule_id="receipt_bound_hindsight_goal_relabel",
        relabel_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        intended_goal=intended_goal,
        achieved_goal=achieved_goal,
        relabeled_goal=relabeled_goal,
        source_action=source_action,
        static_target_action=static_target_action,
        relabeled_target_action=relabeled_target_action,
        source_reject_receipt_hashes=source_reject_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        relabeled_target_receipt_hashes=relabeled_target_receipt_hashes,
        relabeled_target_commit_receipt_hashes=relabeled_target_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        relabeled_branch_selection_certificate_hash=relabeled_branch_selection_certificate_hash,
        source_rejected=source_rejected,
        static_committed=static_committed,
        relabeled_committed=relabeled_committed,
        static_verifier_call_count=static_verifier_call_count,
        relabeled_verifier_call_count=relabeled_verifier_call_count,
        same_budget=static_verifier_call_count == relabeled_verifier_call_count == 1,
        relabel_reason="source_reject_achieved_goal_relabels_target",
    )


def validate_branch_hindsight_relabel_certificate(
    certificate: BranchHindsightRelabelCertificate,
    row: BranchHindsightRelabelDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_HINDSIGHT_RELABEL_CERTIFICATE_SCHEMA:
            return False
        if certificate.relabel_rule_id != "receipt_bound_hindsight_goal_relabel":
            return False
        if certificate.relabel_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.intended_goal,
            certificate.achieved_goal,
            certificate.relabeled_goal,
            certificate.source_action,
            certificate.static_target_action,
            certificate.relabeled_target_action,
        ):
            if not _nonempty(value):
                return False
        if certificate.achieved_goal != certificate.relabeled_goal:
            return False
        if certificate.relabeled_goal == certificate.intended_goal:
            return False
        if certificate.source_action != certificate.relabeled_target_action:
            return False
        if certificate.static_target_action == certificate.relabeled_target_action:
            return False
        if not certificate.source_rejected:
            return False
        if certificate.static_committed or not certificate.relabeled_committed:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.relabeled_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.relabel_reason != "source_reject_achieved_goal_relabels_target":
            return False
        for values in (
            certificate.source_reject_receipt_hashes,
            certificate.static_target_receipt_hashes,
            certificate.relabeled_target_receipt_hashes,
            certificate.relabeled_target_commit_receipt_hashes,
        ):
            if len(values) != 1 or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.relabeled_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.intended_goal != certificate.intended_goal:
                return False
            if row.achieved_goal != certificate.achieved_goal or row.relabeled_goal != certificate.relabeled_goal:
                return False
            if row.source_action != certificate.source_action:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.relabeled_target_action != certificate.relabeled_target_action:
                return False
            if row.source_rejected != certificate.source_rejected:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.relabeled_committed != certificate.relabeled_committed:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.relabeled_verifier_call_count != certificate.relabeled_verifier_call_count:
                return False
            if row.source_reject_receipt_hashes != certificate.source_reject_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.relabeled_target_receipt_hashes != certificate.relabeled_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.hindsight_relabel_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_hindsight_relabel_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_hindsight_relabel_transfer_certificate(
    report: BranchHindsightRelabelTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_hindsight_relabel_certificate_hashes: tuple[str, ...],
) -> BranchHindsightRelabelTransferCertificate:
    return BranchHindsightRelabelTransferCertificate(
        schema_version=BRANCH_HINDSIGHT_RELABEL_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_hindsight_relabel_certificate_hashes=branch_hindsight_relabel_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_reject_count=report.source_reject_count,
        static_success_count=report.static_success_count,
        relabeled_success_count=report.relabeled_success_count,
        relabeled_goal_count=report.relabeled_goal_count,
        same_budget_hindsight_count=report.same_budget_hindsight_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_HINDSIGHT_RELABEL_CLAIM_BOUNDARY,
    )


def validate_branch_hindsight_relabel_transfer_certificate(
    certificate: BranchHindsightRelabelTransferCertificate,
    report: BranchHindsightRelabelTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_HINDSIGHT_RELABEL_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_hindsight_relabel_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 3:
            return False
        if len(certificate.branch_hindsight_relabel_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_reject_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.relabeled_success_count != certificate.domain_count:
            return False
        if certificate.relabeled_goal_count != certificate.domain_count:
            return False
        if certificate.same_budget_hindsight_count != certificate.domain_count:
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
            if not report.all_branch_hindsight_relabel_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
        return certificate.certificate_hash == branch_hindsight_relabel_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_hindsight_relabel_certificate_hash(
    certificate: BranchHindsightRelabelCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchHindsightRelabelCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_hindsight_relabel_transfer_certificate_hash(
    certificate: BranchHindsightRelabelTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchHindsightRelabelTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchHindsightRelabelTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def normalize_hindsight_state(state: HindsightGoalState | Mapping[str, Any]) -> HindsightGoalState:
    if isinstance(state, HindsightGoalState):
        return HindsightGoalState(committed_goals=tuple(tuple(row) for row in state.committed_goals))
    if isinstance(state, Mapping):
        return HindsightGoalState(committed_goals=tuple(tuple(row) for row in state.get("committed_goals", ())))
    raise TypeError(f"unsupported hindsight state: {type(state)!r}")


def _build_claim_certificate(
    report: BranchHindsightRelabelTransferReport,
    transfer_certificate: BranchHindsightRelabelTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_hindsight_relabel_transfer_g1",
        claim_text=(
            "Rejected past branch receipts can improve local target exploration by certifying a "
            "hindsight goal relabel, while target commit authority remains with fresh hard verification."
        ),
        evidence_grade="G1",
        scope="branch_hindsight_relabel_transfer",
        requirements=(
            requirement(
                "branch_hindsight_relabel_transfer_certificate_valid",
                validate_branch_hindsight_relabel_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement(
                "all_branch_hindsight_relabel_certificates_valid",
                report.all_branch_hindsight_relabel_certificates_valid,
            ),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_rejects_all_domains", report.source_reject_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("relabeled_succeeds_all_domains", report.relabeled_success_count == report.domain_count),
            requirement("relabeled_goal_differs_all_domains", report.relabeled_goal_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_hindsight_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_reject_count": report.source_reject_count,
            "static_success_count": report.static_success_count,
            "relabeled_success_count": report.relabeled_success_count,
            "relabeled_goal_count": report.relabeled_goal_count,
        },
        boundary=BRANCH_HINDSIGHT_RELABEL_CLAIM_BOUNDARY,
        sources=BRANCH_HINDSIGHT_RELABEL_SOURCES,
    )


def _make_hindsight_traces(
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
            seeds=("branch-hindsight-relabel-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.hindsight.relabel.transfer.v1",
        )
        for action in actions
    )


def _goals(spec: ExplorationDomainSpec) -> tuple[str, str]:
    if spec.domain_id == "robotics_replan":
        return "dock_a", "survey_b"
    if spec.domain_id == "molecule_repair":
        return "functional_group_repair", "stable_intermediate"
    if spec.domain_id == "material_process":
        return "alpha_phase", "beta_seed"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _source_hindsight_action(
    spec: ExplorationDomainSpec,
    context: str,
    intended_goal: str,
    achieved_goal: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "survey_detour",
            "utility": 8,
            "goal": intended_goal,
            "achieved_goal": achieved_goal,
            "clearance": 0.34,
            "turn_rate": 0.44,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "stable_intermediate_conformer",
            "utility": 8,
            "goal": intended_goal,
            "achieved_goal": achieved_goal,
            "valence_ok": True,
            "strain": 0.22,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "beta_seeded_anneal",
            "utility": 8,
            "goal": intended_goal,
            "achieved_goal": achieved_goal,
            "thermal_gradient": 0.42,
            "phase_purity": 0.94,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _static_target_action(spec: ExplorationDomainSpec, context: str, achieved_goal: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "direct_survey_cut",
            "utility": 9,
            "goal": achieved_goal,
            "achieved_goal": achieved_goal,
            "clearance": 0.18,
            "turn_rate": 0.72,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "overstrained_intermediate_shortcut",
            "utility": 9,
            "goal": achieved_goal,
            "achieved_goal": achieved_goal,
            "valence_ok": True,
            "strain": 0.46,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "flash_beta_seed",
            "utility": 9,
            "goal": achieved_goal,
            "achieved_goal": achieved_goal,
            "thermal_gradient": 0.61,
            "phase_purity": 0.92,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _relabeled_target_action(
    source_action: Mapping[str, Any],
    target_context: str,
    relabeled_goal: str,
) -> Mapping[str, Any]:
    return {
        **dict(source_action),
        "context": target_context,
        "goal": relabeled_goal,
        "achieved_goal": relabeled_goal,
    }


def _verify_physics(payload: Mapping[str, Any]) -> tuple[bool, Mapping[str, Any] | None]:
    domain = str(payload["domain"])
    if domain == "robotics_replan":
        clearance = float(payload["clearance"])
        turn_rate = float(payload["turn_rate"])
        accepted = clearance >= 0.25 and turn_rate <= 0.60
        return accepted, None if accepted else {
            "kind": "safety_envelope_violation",
            "clearance": clearance,
            "min_clearance": 0.25,
            "turn_rate": turn_rate,
            "max_turn_rate": 0.60,
        }
    if domain == "molecule_repair":
        valence_ok = bool(payload["valence_ok"])
        strain = float(payload["strain"])
        accepted = valence_ok and strain <= 0.35
        return accepted, None if accepted else {
            "kind": "valence_strain_violation",
            "valence_ok": valence_ok,
            "strain": strain,
            "max_strain": 0.35,
        }
    if domain == "material_process":
        thermal_gradient = float(payload["thermal_gradient"])
        phase_purity = float(payload["phase_purity"])
        accepted = thermal_gradient <= 0.50 and phase_purity >= 0.90
        return accepted, None if accepted else {
            "kind": "thermal_phase_violation",
            "thermal_gradient": thermal_gradient,
            "max_thermal_gradient": 0.50,
            "phase_purity": phase_purity,
            "min_phase_purity": 0.90,
        }
    return False, {"kind": "unknown_domain", "domain": domain}


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(payload)
    row["domain"] = str(row["domain"])
    row["context"] = str(row["context"])
    row["action"] = str(row["action"])
    row["goal"] = str(row["goal"])
    row["achieved_goal"] = str(row["achieved_goal"])
    row["utility"] = int(row.get("utility", 0))
    return row


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_hindsight_relabel_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
