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


BRANCH_PREREQUISITE_CERTIFICATE_SCHEMA = "trwm.branch_prerequisite_certificate.v1"
BRANCH_PREREQUISITE_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_prerequisite_transfer_certificate.v1"
BRANCH_PREREQUISITE_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1016/S0004-3702(99)00052-1",
)
BRANCH_PREREQUISITE_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows past branch receipts can certify "
    "a prerequisite-before-final exploration order under a matched verifier-call budget. It is not "
    "hierarchical reinforcement learning, automatic subgoal discovery, robotics safety, chemistry, "
    "materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class PrerequisiteState:
    prerequisites: tuple[tuple[str, str], ...] = ()
    finals: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class BranchPrerequisiteCertificate:
    schema_version: str
    domain: str
    prerequisite_rule_id: str
    prerequisite_rule_version: str
    source_context_id: str
    target_context_id: str
    prerequisite_key: str
    source_prerequisite_action: str
    source_final_action: str
    target_prerequisite_action: str
    target_final_action: str
    static_actions: tuple[str, ...]
    guided_actions: tuple[str, ...]
    source_prerequisite_receipt_hashes: tuple[str, ...]
    source_final_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    guided_prerequisite_receipt_hashes: tuple[str, ...]
    guided_final_receipt_hashes: tuple[str, ...]
    source_prerequisite_branch_selection_certificate_hash: str
    source_final_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    guided_prerequisite_branch_selection_certificate_hash: str
    guided_final_branch_selection_certificate_hash: str
    static_committed: bool
    guided_prerequisite_committed: bool
    guided_final_committed: bool
    static_verifier_call_count: int
    guided_verifier_call_count: int
    same_budget: bool
    prerequisite_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PREREQUISITE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch prerequisite certificate schema: {self.schema_version}")
        for field_name in (
            "static_actions",
            "guided_actions",
            "source_prerequisite_receipt_hashes",
            "source_final_receipt_hashes",
            "static_receipt_hashes",
            "guided_prerequisite_receipt_hashes",
            "guided_final_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_prerequisite_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchPrerequisiteDomainReport:
    domain: str
    source_context: str
    target_context: str
    prerequisite_key: str
    source_prerequisite_action: str
    source_final_action: str
    target_prerequisite_action: str
    target_final_action: str
    static_actions: tuple[str, ...]
    guided_actions: tuple[str, ...]
    static_committed: bool
    guided_prerequisite_committed: bool
    guided_final_committed: bool
    static_verifier_call_count: int
    guided_verifier_call_count: int
    source_prerequisite_receipt_hashes: tuple[str, ...]
    source_final_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    guided_prerequisite_receipt_hashes: tuple[str, ...]
    guided_final_receipt_hashes: tuple[str, ...]
    prerequisite_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchPrerequisiteTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchPrerequisiteDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    static_success_count: int
    guided_prerequisite_success_count: int
    guided_final_success_count: int
    same_budget_prerequisite_count: int
    branch_prerequisite_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_prerequisite_certificates_valid: bool
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
class BranchPrerequisiteTransferCertificate:
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
    branch_prerequisite_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    static_success_count: int
    guided_prerequisite_success_count: int
    guided_final_success_count: int
    same_budget_prerequisite_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PREREQUISITE_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch prerequisite transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_prerequisite_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_prerequisite_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchPrerequisiteTransferResult(CertifiedExampleResult):
    report: BranchPrerequisiteTransferReport
    branch_prerequisite_transfer_certificate: BranchPrerequisiteTransferCertificate
    branch_prerequisite_certificates: tuple[BranchPrerequisiteCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


class PrerequisiteAdapter:
    verifier_id = "branch_prerequisite_domain_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        kind = payload["kind"]
        metadata = {
            "domain": payload["domain"],
            "context": payload["context"],
            "action": payload["action"],
            "kind": kind,
            "prerequisite_key": payload["prerequisite_key"],
        }
        if kind == "prerequisite":
            if bool(payload.get("prerequisite_gate_ok", False)):
                return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "prerequisite_gate_failed", "prerequisite_key": payload["prerequisite_key"]},
                metadata=metadata,
            )
        if kind == "final":
            required = (payload["context"], payload["prerequisite_key"])
            current = tuple(tuple(row) for row in payload.get("current_prerequisites", ()))
            if required not in current:
                return HardVerifierResult.reject(
                    self.verifier_id,
                    self.verifier_version,
                    residual={"kind": "missing_prerequisite", "required": required},
                    metadata=metadata,
                )
            accepted, residual = _verify_final_payload(payload)
            if accepted:
                return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
            return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual=residual, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": "distractor_branch", "action": payload["action"]},
            metadata=metadata,
        )

    def apply_commit(self, state: PrerequisiteState, candidate: TypedCandidate) -> PrerequisiteState:
        current = normalize_prerequisite_state(state)
        payload = _normalize_payload(candidate.payload)
        key = (payload["context"], payload["prerequisite_key"])
        if payload["kind"] == "prerequisite":
            prerequisites = tuple(sorted({*current.prerequisites, key}))
            return PrerequisiteState(prerequisites=prerequisites, finals=current.finals)
        if payload["kind"] == "final":
            finals = tuple(sorted({*current.finals, (payload["context"], payload["action"])}))
            return PrerequisiteState(prerequisites=current.prerequisites, finals=finals)
        return current

    def replay(self, state: PrerequisiteState, receipt: Receipt) -> PrerequisiteState:
        candidate = TypedCandidate(
            payload=receipt.replay_bundle["candidate_payload"],
            type_name=receipt.replay_bundle["candidate_type"],
            schema_version=receipt.replay_bundle["candidate_schema"],
        )
        return self.apply_commit(state, candidate)

    def rollback(self, _state: PrerequisiteState, receipt: Receipt) -> PrerequisiteState:
        return normalize_prerequisite_state(receipt.rollback_bundle["pre_state"])


class PrerequisiteProjector:
    def project(self, state: PrerequisiteState, trace: ProposalTrace) -> TypedCandidate:
        current = normalize_prerequisite_state(state)
        payload = _normalize_payload(trace.actions[-1])
        payload["current_prerequisites"] = current.prerequisites
        return TypedCandidate(
            payload=payload,
            type_name="branch.prerequisite.action",
            schema_version="branch.prerequisite.action.v1",
        )


def run_branch_prerequisite_transfer_experiment() -> BranchPrerequisiteTransferReport:
    return run_branch_prerequisite_transfer_certified_experiment().report


def run_branch_prerequisite_transfer_certified_experiment() -> CertifiedBranchPrerequisiteTransferResult:
    seed = PrerequisiteState()
    state = seed
    engine = TransactionEngine(PrerequisiteAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, PrerequisiteProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchPrerequisiteDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    prerequisite_certificates: list[BranchPrerequisiteCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:prerequisite"
        target_context = f"{spec.domain_id}:target:prerequisite"
        key = _prerequisite_key(spec)
        source_prerequisite = _prerequisite_action(spec, source_context, source=True)
        source_final = _final_action(spec, source_context, source=True)
        target_prerequisite = _prerequisite_action(spec, target_context, source=False)
        target_final = _final_action(spec, target_context, source=False)
        static_distractor = _static_distractor_action(spec, target_context)

        source_prerequisite_outcome = runtime.step(
            state,
            _make_prerequisite_traces(
                spec,
                context=source_context,
                phase="source-prerequisite",
                actions=(source_prerequisite,),
            ),
        )
        state = normalize_prerequisite_state(source_prerequisite_outcome.state)
        source_prerequisite_certificate = build_branch_selection_certificate(
            source_prerequisite_outcome.receipts,
            verifier_call_count=source_prerequisite_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_prerequisite_outcome.receipts), source_prerequisite_certificate))
        memory.update_branch(source_prerequisite_outcome.receipts, source_prerequisite_certificate)

        source_final_outcome = runtime.step(
            state,
            _make_prerequisite_traces(spec, context=source_context, phase="source-final", actions=(source_final,)),
        )
        state = normalize_prerequisite_state(source_final_outcome.state)
        source_final_certificate = build_branch_selection_certificate(
            source_final_outcome.receipts,
            verifier_call_count=source_final_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_final_outcome.receipts), source_final_certificate))
        memory.update_branch(source_final_outcome.receipts, source_final_certificate)

        static_outcome = runtime.step(
            state,
            _make_prerequisite_traces(
                spec,
                context=target_context,
                phase="target-static",
                actions=(target_final, static_distractor),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        guided_prerequisite_outcome = runtime.step(
            state,
            _make_prerequisite_traces(
                spec,
                context=target_context,
                phase="target-guided-prerequisite",
                actions=(target_prerequisite,),
            ),
        )
        state = normalize_prerequisite_state(guided_prerequisite_outcome.state)
        guided_prerequisite_certificate = build_branch_selection_certificate(
            guided_prerequisite_outcome.receipts,
            verifier_call_count=guided_prerequisite_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(guided_prerequisite_outcome.receipts), guided_prerequisite_certificate))

        guided_final_outcome = runtime.step(
            state,
            _make_prerequisite_traces(spec, context=target_context, phase="target-guided-final", actions=(target_final,)),
        )
        state = normalize_prerequisite_state(guided_final_outcome.state)
        guided_final_certificate = build_branch_selection_certificate(
            guided_final_outcome.receipts,
            verifier_call_count=guided_final_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(guided_final_outcome.receipts), guided_final_certificate))

        certificate = build_branch_prerequisite_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            prerequisite_key=key,
            source_prerequisite_action=str(source_prerequisite["action"]),
            source_final_action=str(source_final["action"]),
            target_prerequisite_action=str(target_prerequisite["action"]),
            target_final_action=str(target_final["action"]),
            static_actions=(str(target_final["action"]), str(static_distractor["action"])),
            guided_actions=(str(target_prerequisite["action"]), str(target_final["action"])),
            source_prerequisite_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_prerequisite_outcome.receipts),
            source_final_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_final_outcome.receipts),
            static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            guided_prerequisite_receipt_hashes=tuple(receipt.receipt_hash for receipt in guided_prerequisite_outcome.receipts),
            guided_final_receipt_hashes=tuple(receipt.receipt_hash for receipt in guided_final_outcome.receipts),
            source_prerequisite_branch_selection_certificate_hash=source_prerequisite_certificate.certificate_hash,
            source_final_branch_selection_certificate_hash=source_final_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            guided_prerequisite_branch_selection_certificate_hash=guided_prerequisite_certificate.certificate_hash,
            guided_final_branch_selection_certificate_hash=guided_final_certificate.certificate_hash,
            static_committed=static_outcome.committed,
            guided_prerequisite_committed=guided_prerequisite_outcome.committed,
            guided_final_committed=guided_final_outcome.committed,
            static_verifier_call_count=static_outcome.verifier_calls,
            guided_verifier_call_count=guided_prerequisite_outcome.verifier_calls + guided_final_outcome.verifier_calls,
        )
        prerequisite_certificates.append(certificate)

        rows.append(
            BranchPrerequisiteDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                prerequisite_key=key,
                source_prerequisite_action=certificate.source_prerequisite_action,
                source_final_action=certificate.source_final_action,
                target_prerequisite_action=certificate.target_prerequisite_action,
                target_final_action=certificate.target_final_action,
                static_actions=certificate.static_actions,
                guided_actions=certificate.guided_actions,
                static_committed=static_outcome.committed,
                guided_prerequisite_committed=guided_prerequisite_outcome.committed,
                guided_final_committed=guided_final_outcome.committed,
                static_verifier_call_count=static_outcome.verifier_calls,
                guided_verifier_call_count=guided_prerequisite_outcome.verifier_calls + guided_final_outcome.verifier_calls,
                source_prerequisite_receipt_hashes=certificate.source_prerequisite_receipt_hashes,
                source_final_receipt_hashes=certificate.source_final_receipt_hashes,
                static_receipt_hashes=certificate.static_receipt_hashes,
                guided_prerequisite_receipt_hashes=certificate.guided_prerequisite_receipt_hashes,
                guided_final_receipt_hashes=certificate.guided_final_receipt_hashes,
                prerequisite_certificate_hash=certificate.certificate_hash,
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

    report = BranchPrerequisiteTransferReport(
        schema_version="trwm.example.branch_prerequisite_transfer.v1",
        experiment_id="branch_prerequisite_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        static_success_count=sum(1 for row in rows if row.static_committed),
        guided_prerequisite_success_count=sum(1 for row in rows if row.guided_prerequisite_committed),
        guided_final_success_count=sum(1 for row in rows if row.guided_final_committed),
        same_budget_prerequisite_count=sum(1 for row in rows if row.same_budget),
        branch_prerequisite_certificate_count=len(prerequisite_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_prerequisite_certificates_valid=all(
            validate_branch_prerequisite_certificate(certificate) for certificate in prerequisite_certificates
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
        hard_gate_keys=("prerequisite_gate_ok", "prerequisite_met", "clearance", "turn_rate", "valence_ok", "strain", "thermal_gradient", "phase_purity"),
        residual_kinds=tuple(sorted({*{spec.residual_kind for spec in DOMAIN_SPECS}, "missing_prerequisite"})),
        sources=BRANCH_PREREQUISITE_SOURCES,
        learning=(
            "Past branch receipts can improve exploration by certifying a prerequisite-before-final order: "
            "the static target spends the same two calls on final/distractor branches and fails, while the "
            "guided target commits prerequisite then final through the hard verifier."
        ),
    )
    transfer_certificate = build_branch_prerequisite_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_prerequisite_certificate_hashes=tuple(certificate.certificate_hash for certificate in prerequisite_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_prerequisite_transfer",
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
        claim_boundary=BRANCH_PREREQUISITE_CLAIM_BOUNDARY,
        sources=BRANCH_PREREQUISITE_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchPrerequisiteTransferResult(
        report=report,
        branch_prerequisite_transfer_certificate=transfer_certificate,
        branch_prerequisite_certificates=tuple(prerequisite_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_prerequisite_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    prerequisite_key: str,
    source_prerequisite_action: str,
    source_final_action: str,
    target_prerequisite_action: str,
    target_final_action: str,
    static_actions: tuple[str, ...],
    guided_actions: tuple[str, ...],
    source_prerequisite_receipt_hashes: tuple[str, ...],
    source_final_receipt_hashes: tuple[str, ...],
    static_receipt_hashes: tuple[str, ...],
    guided_prerequisite_receipt_hashes: tuple[str, ...],
    guided_final_receipt_hashes: tuple[str, ...],
    source_prerequisite_branch_selection_certificate_hash: str,
    source_final_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    guided_prerequisite_branch_selection_certificate_hash: str,
    guided_final_branch_selection_certificate_hash: str,
    static_committed: bool,
    guided_prerequisite_committed: bool,
    guided_final_committed: bool,
    static_verifier_call_count: int,
    guided_verifier_call_count: int,
) -> BranchPrerequisiteCertificate:
    return BranchPrerequisiteCertificate(
        schema_version=BRANCH_PREREQUISITE_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        prerequisite_rule_id="receipt_bound_prerequisite_ordering",
        prerequisite_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        prerequisite_key=prerequisite_key,
        source_prerequisite_action=source_prerequisite_action,
        source_final_action=source_final_action,
        target_prerequisite_action=target_prerequisite_action,
        target_final_action=target_final_action,
        static_actions=static_actions,
        guided_actions=guided_actions,
        source_prerequisite_receipt_hashes=source_prerequisite_receipt_hashes,
        source_final_receipt_hashes=source_final_receipt_hashes,
        static_receipt_hashes=static_receipt_hashes,
        guided_prerequisite_receipt_hashes=guided_prerequisite_receipt_hashes,
        guided_final_receipt_hashes=guided_final_receipt_hashes,
        source_prerequisite_branch_selection_certificate_hash=source_prerequisite_branch_selection_certificate_hash,
        source_final_branch_selection_certificate_hash=source_final_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        guided_prerequisite_branch_selection_certificate_hash=guided_prerequisite_branch_selection_certificate_hash,
        guided_final_branch_selection_certificate_hash=guided_final_branch_selection_certificate_hash,
        static_committed=static_committed,
        guided_prerequisite_committed=guided_prerequisite_committed,
        guided_final_committed=guided_final_committed,
        static_verifier_call_count=static_verifier_call_count,
        guided_verifier_call_count=guided_verifier_call_count,
        same_budget=static_verifier_call_count == guided_verifier_call_count == 2,
        prerequisite_reason="source_prerequisite_orders_target_final",
    )


def validate_branch_prerequisite_certificate(
    certificate: BranchPrerequisiteCertificate,
    row: BranchPrerequisiteDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PREREQUISITE_CERTIFICATE_SCHEMA:
            return False
        if certificate.prerequisite_rule_id != "receipt_bound_prerequisite_ordering":
            return False
        if certificate.prerequisite_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.prerequisite_key,
            certificate.source_prerequisite_action,
            certificate.source_final_action,
            certificate.target_prerequisite_action,
            certificate.target_final_action,
        ):
            if not _nonempty(value):
                return False
        if len(certificate.static_actions) != 2 or len(certificate.guided_actions) != 2:
            return False
        if certificate.static_actions[0] != certificate.target_final_action:
            return False
        if certificate.guided_actions != (certificate.target_prerequisite_action, certificate.target_final_action):
            return False
        if certificate.static_committed:
            return False
        if not (certificate.guided_prerequisite_committed and certificate.guided_final_committed):
            return False
        if certificate.static_verifier_call_count != 2 or certificate.guided_verifier_call_count != 2:
            return False
        if not certificate.same_budget:
            return False
        if certificate.prerequisite_reason != "source_prerequisite_orders_target_final":
            return False
        for values, expected_len in (
            (certificate.source_prerequisite_receipt_hashes, 1),
            (certificate.source_final_receipt_hashes, 1),
            (certificate.static_receipt_hashes, 2),
            (certificate.guided_prerequisite_receipt_hashes, 1),
            (certificate.guided_final_receipt_hashes, 1),
        ):
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_prerequisite_branch_selection_certificate_hash,
            certificate.source_final_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.guided_prerequisite_branch_selection_certificate_hash,
            certificate.guided_final_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.prerequisite_key != certificate.prerequisite_key:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.guided_prerequisite_committed != certificate.guided_prerequisite_committed:
                return False
            if row.guided_final_committed != certificate.guided_final_committed:
                return False
            if row.prerequisite_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_prerequisite_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_prerequisite_transfer_certificate(
    report: BranchPrerequisiteTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_prerequisite_certificate_hashes: tuple[str, ...],
) -> BranchPrerequisiteTransferCertificate:
    return BranchPrerequisiteTransferCertificate(
        schema_version=BRANCH_PREREQUISITE_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_prerequisite_certificate_hashes=branch_prerequisite_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        static_success_count=report.static_success_count,
        guided_prerequisite_success_count=report.guided_prerequisite_success_count,
        guided_final_success_count=report.guided_final_success_count,
        same_budget_prerequisite_count=report.same_budget_prerequisite_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_PREREQUISITE_CLAIM_BOUNDARY,
    )


def validate_branch_prerequisite_transfer_certificate(
    certificate: BranchPrerequisiteTransferCertificate,
    report: BranchPrerequisiteTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PREREQUISITE_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_prerequisite_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_prerequisite_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.guided_prerequisite_success_count != certificate.domain_count:
            return False
        if certificate.guided_final_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_prerequisite_count != certificate.domain_count:
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
            if not report.all_branch_prerequisite_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
        return certificate.certificate_hash == branch_prerequisite_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_prerequisite_certificate_hash(certificate: BranchPrerequisiteCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchPrerequisiteCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_prerequisite_transfer_certificate_hash(
    certificate: BranchPrerequisiteTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchPrerequisiteTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchPrerequisiteTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchPrerequisiteTransferReport,
    transfer_certificate: BranchPrerequisiteTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_prerequisite_transfer_g1",
        claim_text=(
            "Past branch receipts can improve local target exploration by certifying prerequisite-before-final "
            "ordering under matched two-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_prerequisite_transfer",
        requirements=(
            requirement(
                "branch_prerequisite_transfer_certificate_valid",
                validate_branch_prerequisite_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_prerequisite_certificates_valid", report.all_branch_prerequisite_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("guided_prerequisite_succeeds_all_domains", report.guided_prerequisite_success_count == report.domain_count),
            requirement("guided_final_succeeds_all_domains", report.guided_final_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_prerequisite_count == report.domain_count),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "static_success_count": report.static_success_count,
            "guided_prerequisite_success_count": report.guided_prerequisite_success_count,
            "guided_final_success_count": report.guided_final_success_count,
        },
        boundary=BRANCH_PREREQUISITE_CLAIM_BOUNDARY,
        sources=BRANCH_PREREQUISITE_SOURCES,
    )


def normalize_prerequisite_state(state: PrerequisiteState | Mapping[str, Any]) -> PrerequisiteState:
    if isinstance(state, PrerequisiteState):
        return PrerequisiteState(
            prerequisites=tuple((str(context), str(key)) for context, key in state.prerequisites),
            finals=tuple((str(context), str(action)) for context, action in state.finals),
        )
    return PrerequisiteState(
        prerequisites=tuple((str(context), str(key)) for context, key in state.get("prerequisites", ())),
        finals=tuple((str(context), str(action)) for context, action in state.get("finals", ())),
    )


def _make_prerequisite_traces(
    spec: ExplorationDomainSpec,
    *,
    context: str,
    phase: str,
    actions: Iterable[Mapping[str, Any]],
) -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"{context}:{phase}:{action['action']}",
            actions=(dict(action),),
            seeds=("branch-prerequisite-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.prerequisite.transfer.v1",
        )
        for action in actions
    )


def _prerequisite_key(spec: ExplorationDomainSpec) -> str:
    if spec.domain_id == "robotics_replan":
        return "corridor_certified"
    if spec.domain_id == "molecule_repair":
        return "valence_template_bound"
    if spec.domain_id == "material_process":
        return "thermal_window_stabilized"
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _prerequisite_action(spec: ExplorationDomainSpec, context: str, *, source: bool) -> Mapping[str, Any]:
    key = _prerequisite_key(spec)
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "map_corridor" if source else "map_target_corridor",
            "kind": "prerequisite",
            "prerequisite_key": key,
            "utility": 5,
            "prerequisite_gate_ok": True,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "bind_valence_template" if source else "bind_target_valence_template",
            "kind": "prerequisite",
            "prerequisite_key": key,
            "utility": 5,
            "prerequisite_gate_ok": True,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "stabilize_thermal_window" if source else "stabilize_target_thermal_window",
            "kind": "prerequisite",
            "prerequisite_key": key,
            "utility": 5,
            "prerequisite_gate_ok": True,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _final_action(spec: ExplorationDomainSpec, context: str, *, source: bool) -> Mapping[str, Any]:
    action = {**dict(next(item for item in spec.actions if item.get("target_commit")))}
    action["context"] = context
    action["kind"] = "final"
    action["prerequisite_key"] = _prerequisite_key(spec)
    action["utility"] = 10 if source else 9
    return action


def _static_distractor_action(spec: ExplorationDomainSpec, context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "shortcut_without_map",
            "kind": "distractor",
            "prerequisite_key": _prerequisite_key(spec),
            "utility": 8,
        }
    if spec.domain_id == "molecule_repair":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "patch_without_template",
            "kind": "distractor",
            "prerequisite_key": _prerequisite_key(spec),
            "utility": 8,
        }
    if spec.domain_id == "material_process":
        return {
            "domain": spec.domain_id,
            "context": context,
            "action": "anneal_without_window",
            "kind": "distractor",
            "prerequisite_key": _prerequisite_key(spec),
            "utility": 8,
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _verify_final_payload(payload: Mapping[str, Any]) -> tuple[bool, Mapping[str, Any] | None]:
    domain = str(payload["domain"])
    if domain == "robotics_replan":
        clearance = float(payload["clearance"])
        turn_rate = float(payload["turn_rate"])
        accepted = clearance >= 0.25 and turn_rate <= 0.60
        if accepted:
            return True, None
        return False, {"kind": "safety_envelope_violation", "clearance": clearance, "turn_rate": turn_rate}
    if domain == "molecule_repair":
        valence_ok = bool(payload["valence_ok"])
        strain = float(payload["strain"])
        accepted = valence_ok and strain <= 0.35
        if accepted:
            return True, None
        return False, {"kind": "valence_strain_violation", "valence_ok": valence_ok, "strain": strain}
    if domain == "material_process":
        thermal_gradient = float(payload["thermal_gradient"])
        phase_purity = float(payload["phase_purity"])
        accepted = thermal_gradient <= 0.50 and phase_purity >= 0.90
        if accepted:
            return True, None
        return False, {"kind": "thermal_phase_violation", "thermal_gradient": thermal_gradient, "phase_purity": phase_purity}
    raise ValueError(f"unknown domain: {domain}")


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["domain"] = str(normalized["domain"])
    normalized["context"] = str(normalized["context"])
    normalized["action"] = str(normalized["action"])
    normalized["kind"] = str(normalized["kind"])
    normalized["prerequisite_key"] = str(normalized["prerequisite_key"])
    normalized["utility"] = int(normalized.get("utility", 0))
    if "current_prerequisites" in normalized:
        normalized["current_prerequisites"] = tuple(
            (str(context), str(key)) for context, key in normalized["current_prerequisites"]
        )
    return normalized


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_prerequisite_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
