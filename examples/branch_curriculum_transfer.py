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


BRANCH_CURRICULUM_CERTIFICATE_SCHEMA = "trwm.branch_curriculum_certificate.v1"
BRANCH_CURRICULUM_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_curriculum_transfer_certificate.v1"
BRANCH_CURRICULUM_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://icml.cc/2009/papers/119.pdf",
    "https://proceedings.mlr.press/v202/lin23n.html",
)
BRANCH_CURRICULUM_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source branch receipts can certify "
    "a monotone easy-to-hard target curriculum under a matched verifier-call budget, while every target "
    "commit remains gated by fresh hard verification. It is not curriculum learning, homotopy optimization, "
    "automatic subgoal discovery, robotics safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class CurriculumState:
    progress: tuple[tuple[str, str, int], ...] = ()
    finals: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class BranchCurriculumCertificate:
    schema_version: str
    domain: str
    curriculum_rule_id: str
    curriculum_rule_version: str
    source_context_id: str
    target_context_id: str
    curriculum_key: str
    curriculum_levels: tuple[int, ...]
    source_actions: tuple[str, ...]
    static_actions: tuple[str, ...]
    guided_actions: tuple[str, ...]
    source_receipt_hashes: tuple[str, ...]
    source_curriculum_receipt_hashes: tuple[str, ...]
    source_final_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    guided_curriculum_receipt_hashes: tuple[str, ...]
    guided_final_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hashes: tuple[str, ...]
    static_branch_selection_certificate_hash: str
    guided_branch_selection_certificate_hashes: tuple[str, ...]
    source_sequence_committed_count: int
    static_committed_count: int
    guided_curriculum_committed_count: int
    guided_final_committed: bool
    static_verifier_call_count: int
    guided_verifier_call_count: int
    same_budget: bool
    curriculum_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CURRICULUM_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch curriculum certificate schema: {self.schema_version}")
        for field_name in (
            "curriculum_levels",
            "source_actions",
            "static_actions",
            "guided_actions",
            "source_receipt_hashes",
            "source_curriculum_receipt_hashes",
            "source_final_receipt_hashes",
            "static_receipt_hashes",
            "guided_curriculum_receipt_hashes",
            "guided_final_receipt_hashes",
            "source_branch_selection_certificate_hashes",
            "guided_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_curriculum_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchCurriculumDomainReport:
    domain: str
    source_context: str
    target_context: str
    curriculum_key: str
    curriculum_levels: tuple[int, ...]
    source_actions: tuple[str, ...]
    static_actions: tuple[str, ...]
    guided_actions: tuple[str, ...]
    source_sequence_committed_count: int
    static_committed_count: int
    guided_curriculum_committed_count: int
    guided_final_committed: bool
    static_verifier_call_count: int
    guided_verifier_call_count: int
    source_receipt_hashes: tuple[str, ...]
    static_receipt_hashes: tuple[str, ...]
    guided_curriculum_receipt_hashes: tuple[str, ...]
    guided_final_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hashes: tuple[str, ...]
    static_branch_selection_certificate_hash: str
    guided_branch_selection_certificate_hashes: tuple[str, ...]
    branch_curriculum_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchCurriculumTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchCurriculumDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_sequence_success_count: int
    static_success_count: int
    guided_curriculum_success_count: int
    guided_final_success_count: int
    same_budget_curriculum_count: int
    branch_curriculum_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_curriculum_certificates_valid: bool
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
class BranchCurriculumTransferCertificate:
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
    branch_curriculum_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_sequence_success_count: int
    static_success_count: int
    guided_curriculum_success_count: int
    guided_final_success_count: int
    same_budget_curriculum_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_CURRICULUM_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch curriculum transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_curriculum_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_curriculum_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchCurriculumTransferResult(CertifiedExampleResult):
    report: BranchCurriculumTransferReport
    branch_curriculum_transfer_certificate: BranchCurriculumTransferCertificate
    branch_curriculum_certificates: tuple[BranchCurriculumCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


class CurriculumAdapter:
    verifier_id = "branch_curriculum_domain_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        metadata = {
            "domain": payload["domain"],
            "context": payload["context"],
            "action": payload["action"],
            "kind": payload["kind"],
            "curriculum_key": payload["curriculum_key"],
            "current_level": payload["current_level"],
        }
        if payload["kind"] == "step":
            expected_level = payload["current_level"] + 1
            if payload["level"] != expected_level:
                return HardVerifierResult.reject(
                    self.verifier_id,
                    self.verifier_version,
                    residual={
                        "kind": "curriculum_order_violation",
                        "expected_level": expected_level,
                        "proposed_level": payload["level"],
                    },
                    metadata=metadata,
                )
            accepted, residual = _verify_domain_payload(payload)
            if accepted:
                return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
            return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual=residual, metadata=metadata)
        if payload["kind"] == "final":
            if payload["current_level"] < payload["required_level"]:
                return HardVerifierResult.reject(
                    self.verifier_id,
                    self.verifier_version,
                    residual={
                        "kind": "missing_curriculum_level",
                        "current_level": payload["current_level"],
                        "required_level": payload["required_level"],
                    },
                    metadata=metadata,
                )
            accepted, residual = _verify_domain_payload(payload)
            if accepted:
                return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
            return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual=residual, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": "unknown_curriculum_action_kind", "action": payload["action"]},
            metadata=metadata,
        )

    def apply_commit(self, state: CurriculumState, candidate: TypedCandidate) -> CurriculumState:
        current = normalize_curriculum_state(state)
        payload = _normalize_payload(candidate.payload)
        key = (payload["context"], payload["curriculum_key"])
        if payload["kind"] == "step":
            return CurriculumState(
                progress=(*current.progress, (key[0], key[1], payload["level"])),
                finals=current.finals,
            )
        return CurriculumState(
            progress=current.progress,
            finals=(*current.finals, key),
        )

    def replay(self, state: CurriculumState, receipt: Receipt) -> CurriculumState:
        return self.apply_commit(state, TypedCandidate(
            payload=receipt.replay_bundle["candidate_payload"],
            type_name=receipt.replay_bundle["candidate_type"],
            schema_version=receipt.replay_bundle["candidate_schema"],
        ))

    def rollback(self, _state: CurriculumState, receipt: Receipt) -> CurriculumState:
        return normalize_curriculum_state(receipt.rollback_bundle["pre_state"])


class CurriculumProjector:
    def project(self, state: CurriculumState, trace: ProposalTrace) -> TypedCandidate:
        payload = _normalize_payload(trace.actions[-1])
        payload["current_level"] = _current_level(state, payload["context"], payload["curriculum_key"])
        return TypedCandidate(
            payload=payload,
            type_name="branch.curriculum.action",
            schema_version="branch.curriculum.action.v1",
        )


def run_branch_curriculum_transfer_experiment() -> BranchCurriculumTransferReport:
    return run_branch_curriculum_transfer_certified_experiment().report


def run_branch_curriculum_transfer_certified_experiment() -> CertifiedBranchCurriculumTransferResult:
    seed = CurriculumState()
    state = seed
    engine = TransactionEngine(CurriculumAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, CurriculumProjector(), HighestCurriculumUtilityRanker())
    memory = AncestralBranchMemory()
    rows: list[BranchCurriculumDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []
    curriculum_certificates: list[BranchCurriculumCertificate] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:curriculum"
        target_context = f"{spec.domain_id}:target:curriculum"
        plan = _curriculum_plan(spec, source_context, target_context)

        source_outcomes = []
        source_certificates = []
        for action in plan["source_actions"]:
            outcome = runtime.step(
                state,
                _make_curriculum_traces(spec, context=source_context, phase="source-curriculum", actions=(action,)),
            )
            state = normalize_curriculum_state(outcome.state)
            certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            source_outcomes.append(outcome)
            source_certificates.append(certificate)
            branch_certificate_pairs.append((tuple(outcome.receipts), certificate))
            memory.update_branch(outcome.receipts, certificate)

        static_outcome = runtime.step(
            state,
            _make_curriculum_traces(
                spec,
                context=target_context,
                phase="target-static-direct",
                actions=plan["static_actions"],
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        guided_outcomes = []
        guided_certificates = []
        for action in plan["guided_actions"]:
            outcome = runtime.step(
                state,
                _make_curriculum_traces(spec, context=target_context, phase="target-guided-curriculum", actions=(action,)),
            )
            state = normalize_curriculum_state(outcome.state)
            certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            guided_outcomes.append(outcome)
            guided_certificates.append(certificate)
            branch_certificate_pairs.append((tuple(outcome.receipts), certificate))

        source_receipts = tuple(receipt for outcome in source_outcomes for receipt in outcome.receipts)
        guided_receipts = tuple(receipt for outcome in guided_outcomes for receipt in outcome.receipts)
        curriculum_certificate = build_branch_curriculum_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            curriculum_key=str(plan["curriculum_key"]),
            curriculum_levels=tuple(int(level) for level in plan["curriculum_levels"]),
            source_actions=tuple(str(action["action"]) for action in plan["source_actions"]),
            static_actions=tuple(str(action["action"]) for action in plan["static_actions"]),
            guided_actions=tuple(str(action["action"]) for action in plan["guided_actions"]),
            source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_receipts),
            source_curriculum_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_receipts if receipt.committed and receipt.replay_bundle["candidate_payload"]["kind"] == "step"
            ),
            source_final_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in source_receipts if receipt.committed and receipt.replay_bundle["candidate_payload"]["kind"] == "final"
            ),
            static_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            guided_curriculum_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in guided_receipts if receipt.committed and receipt.replay_bundle["candidate_payload"]["kind"] == "step"
            ),
            guided_final_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in guided_receipts if receipt.committed and receipt.replay_bundle["candidate_payload"]["kind"] == "final"
            ),
            source_branch_selection_certificate_hashes=tuple(certificate.certificate_hash for certificate in source_certificates),
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            guided_branch_selection_certificate_hashes=tuple(certificate.certificate_hash for certificate in guided_certificates),
            source_sequence_committed_count=sum(1 for receipt in source_receipts if receipt.committed),
            static_committed_count=sum(1 for receipt in static_outcome.receipts if receipt.committed),
            guided_curriculum_committed_count=sum(
                1 for receipt in guided_receipts if receipt.committed and receipt.replay_bundle["candidate_payload"]["kind"] == "step"
            ),
            guided_final_committed=any(
                receipt.committed and receipt.replay_bundle["candidate_payload"]["kind"] == "final"
                for receipt in guided_receipts
            ),
            static_verifier_call_count=static_outcome.verifier_calls,
            guided_verifier_call_count=sum(outcome.verifier_calls for outcome in guided_outcomes),
        )
        curriculum_certificates.append(curriculum_certificate)

        rows.append(
            BranchCurriculumDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                curriculum_key=curriculum_certificate.curriculum_key,
                curriculum_levels=curriculum_certificate.curriculum_levels,
                source_actions=curriculum_certificate.source_actions,
                static_actions=curriculum_certificate.static_actions,
                guided_actions=curriculum_certificate.guided_actions,
                source_sequence_committed_count=curriculum_certificate.source_sequence_committed_count,
                static_committed_count=curriculum_certificate.static_committed_count,
                guided_curriculum_committed_count=curriculum_certificate.guided_curriculum_committed_count,
                guided_final_committed=curriculum_certificate.guided_final_committed,
                static_verifier_call_count=curriculum_certificate.static_verifier_call_count,
                guided_verifier_call_count=curriculum_certificate.guided_verifier_call_count,
                source_receipt_hashes=curriculum_certificate.source_receipt_hashes,
                static_receipt_hashes=curriculum_certificate.static_receipt_hashes,
                guided_curriculum_receipt_hashes=curriculum_certificate.guided_curriculum_receipt_hashes,
                guided_final_receipt_hashes=curriculum_certificate.guided_final_receipt_hashes,
                source_branch_selection_certificate_hashes=curriculum_certificate.source_branch_selection_certificate_hashes,
                static_branch_selection_certificate_hash=curriculum_certificate.static_branch_selection_certificate_hash,
                guided_branch_selection_certificate_hashes=curriculum_certificate.guided_branch_selection_certificate_hashes,
                branch_curriculum_certificate_hash=curriculum_certificate.certificate_hash,
                same_budget=curriculum_certificate.same_budget,
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
    report = BranchCurriculumTransferReport(
        schema_version="trwm.example.branch_curriculum_transfer.v1",
        experiment_id="branch_curriculum_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_sequence_success_count=sum(row.source_sequence_committed_count for row in rows),
        static_success_count=sum(row.static_committed_count for row in rows),
        guided_curriculum_success_count=sum(row.guided_curriculum_committed_count for row in rows),
        guided_final_success_count=sum(1 for row in rows if row.guided_final_committed),
        same_budget_curriculum_count=sum(1 for row in rows if row.same_budget),
        branch_curriculum_certificate_count=len(curriculum_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_curriculum_certificates_valid=all(
            validate_branch_curriculum_certificate(certificate) for certificate in curriculum_certificates
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
        residual_kinds=("curriculum_order_violation", "missing_curriculum_level", *tuple(sorted({spec.residual_kind for spec in DOMAIN_SPECS}))),
        sources=BRANCH_CURRICULUM_SOURCES,
        learning=(
            "Past branch receipts can improve exploration by certifying an easy-to-hard target sequence: "
            "direct target attempts fail, while the receipt-bound curriculum commits intermediate levels and "
            "then the final target under the same verifier-call budget."
        ),
    )
    transfer_certificate = build_branch_curriculum_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_curriculum_certificate_hashes=tuple(certificate.certificate_hash for certificate in curriculum_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_curriculum_transfer",
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
        claim_boundary=BRANCH_CURRICULUM_CLAIM_BOUNDARY,
        sources=BRANCH_CURRICULUM_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchCurriculumTransferResult(
        report=report,
        branch_curriculum_transfer_certificate=transfer_certificate,
        branch_curriculum_certificates=tuple(curriculum_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_curriculum_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    curriculum_key: str,
    curriculum_levels: tuple[int, ...],
    source_actions: tuple[str, ...],
    static_actions: tuple[str, ...],
    guided_actions: tuple[str, ...],
    source_receipt_hashes: tuple[str, ...],
    source_curriculum_receipt_hashes: tuple[str, ...],
    source_final_receipt_hashes: tuple[str, ...],
    static_receipt_hashes: tuple[str, ...],
    guided_curriculum_receipt_hashes: tuple[str, ...],
    guided_final_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hashes: tuple[str, ...],
    static_branch_selection_certificate_hash: str,
    guided_branch_selection_certificate_hashes: tuple[str, ...],
    source_sequence_committed_count: int,
    static_committed_count: int,
    guided_curriculum_committed_count: int,
    guided_final_committed: bool,
    static_verifier_call_count: int,
    guided_verifier_call_count: int,
) -> BranchCurriculumCertificate:
    return BranchCurriculumCertificate(
        schema_version=BRANCH_CURRICULUM_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        curriculum_rule_id="receipt_bound_easy_to_hard_sequence",
        curriculum_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        curriculum_key=curriculum_key,
        curriculum_levels=curriculum_levels,
        source_actions=source_actions,
        static_actions=static_actions,
        guided_actions=guided_actions,
        source_receipt_hashes=source_receipt_hashes,
        source_curriculum_receipt_hashes=source_curriculum_receipt_hashes,
        source_final_receipt_hashes=source_final_receipt_hashes,
        static_receipt_hashes=static_receipt_hashes,
        guided_curriculum_receipt_hashes=guided_curriculum_receipt_hashes,
        guided_final_receipt_hashes=guided_final_receipt_hashes,
        source_branch_selection_certificate_hashes=source_branch_selection_certificate_hashes,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        guided_branch_selection_certificate_hashes=guided_branch_selection_certificate_hashes,
        source_sequence_committed_count=source_sequence_committed_count,
        static_committed_count=static_committed_count,
        guided_curriculum_committed_count=guided_curriculum_committed_count,
        guided_final_committed=guided_final_committed,
        static_verifier_call_count=static_verifier_call_count,
        guided_verifier_call_count=guided_verifier_call_count,
        same_budget=static_verifier_call_count == guided_verifier_call_count == 3,
        curriculum_reason="monotone_easy_to_hard_branch_sequence",
    )


def validate_branch_curriculum_certificate(
    certificate: BranchCurriculumCertificate,
    row: BranchCurriculumDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CURRICULUM_CERTIFICATE_SCHEMA:
            return False
        if certificate.curriculum_rule_id != "receipt_bound_easy_to_hard_sequence":
            return False
        if certificate.curriculum_rule_version != "1.0":
            return False
        if not _nonempty(certificate.domain) or not _nonempty(certificate.source_context_id):
            return False
        if not _nonempty(certificate.target_context_id) or not _nonempty(certificate.curriculum_key):
            return False
        if certificate.curriculum_levels != (1, 2):
            return False
        if len(certificate.source_actions) != 3 or len(certificate.static_actions) != 3:
            return False
        if len(certificate.guided_actions) != 3:
            return False
        if len(certificate.source_receipt_hashes) != 3 or len(certificate.static_receipt_hashes) != 3:
            return False
        if len(certificate.source_curriculum_receipt_hashes) != 2 or len(certificate.source_final_receipt_hashes) != 1:
            return False
        if len(certificate.guided_curriculum_receipt_hashes) != 2 or len(certificate.guided_final_receipt_hashes) != 1:
            return False
        if len(certificate.source_branch_selection_certificate_hashes) != 3:
            return False
        if len(certificate.guided_branch_selection_certificate_hashes) != 3:
            return False
        if certificate.source_sequence_committed_count != 3:
            return False
        if certificate.static_committed_count != 0:
            return False
        if certificate.guided_curriculum_committed_count != 2 or not certificate.guided_final_committed:
            return False
        if certificate.static_verifier_call_count != 3 or certificate.guided_verifier_call_count != 3:
            return False
        if not certificate.same_budget:
            return False
        if certificate.curriculum_reason != "monotone_easy_to_hard_branch_sequence":
            return False
        for values in (
            certificate.source_receipt_hashes,
            certificate.source_curriculum_receipt_hashes,
            certificate.source_final_receipt_hashes,
            certificate.static_receipt_hashes,
            certificate.guided_curriculum_receipt_hashes,
            certificate.guided_final_receipt_hashes,
            certificate.source_branch_selection_certificate_hashes,
            certificate.guided_branch_selection_certificate_hashes,
            (
                certificate.static_branch_selection_certificate_hash,
            ),
        ):
            if any(not _is_hash(value) for value in values):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.curriculum_key != certificate.curriculum_key:
                return False
            if row.curriculum_levels != certificate.curriculum_levels:
                return False
            if row.source_actions != certificate.source_actions:
                return False
            if row.static_actions != certificate.static_actions or row.guided_actions != certificate.guided_actions:
                return False
            if row.source_sequence_committed_count != certificate.source_sequence_committed_count:
                return False
            if row.static_committed_count != certificate.static_committed_count:
                return False
            if row.guided_curriculum_committed_count != certificate.guided_curriculum_committed_count:
                return False
            if row.guided_final_committed != certificate.guided_final_committed:
                return False
            if row.branch_curriculum_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_curriculum_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_curriculum_transfer_certificate(
    report: BranchCurriculumTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_curriculum_certificate_hashes: tuple[str, ...],
) -> BranchCurriculumTransferCertificate:
    return BranchCurriculumTransferCertificate(
        schema_version=BRANCH_CURRICULUM_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_curriculum_certificate_hashes=branch_curriculum_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_sequence_success_count=report.source_sequence_success_count,
        static_success_count=report.static_success_count,
        guided_curriculum_success_count=report.guided_curriculum_success_count,
        guided_final_success_count=report.guided_final_success_count,
        same_budget_curriculum_count=report.same_budget_curriculum_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_CURRICULUM_CLAIM_BOUNDARY,
    )


def validate_branch_curriculum_transfer_certificate(
    certificate: BranchCurriculumTransferCertificate,
    report: BranchCurriculumTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_CURRICULUM_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_curriculum_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 9:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 7:
            return False
        if len(certificate.branch_curriculum_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_sequence_success_count != certificate.domain_count * 3:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.guided_curriculum_success_count != certificate.domain_count * 2:
            return False
        if certificate.guided_final_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_curriculum_count != certificate.domain_count:
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
            if tuple(row.branch_curriculum_certificate_hash for row in report.rows) != certificate.branch_curriculum_certificate_hashes:
                return False
            if not report.all_branch_curriculum_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if report.branch_curriculum_certificate_count != len(certificate.branch_curriculum_certificate_hashes):
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_sequence_success_count != certificate.source_sequence_success_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.guided_curriculum_success_count != certificate.guided_curriculum_success_count:
                return False
            if report.guided_final_success_count != certificate.guided_final_success_count:
                return False
        return certificate.certificate_hash == branch_curriculum_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_curriculum_certificate_hash(
    certificate: BranchCurriculumCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCurriculumCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_curriculum_transfer_certificate_hash(
    certificate: BranchCurriculumTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchCurriculumTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchCurriculumTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchCurriculumTransferReport,
    transfer_certificate: BranchCurriculumTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_curriculum_transfer_g1",
        claim_text=(
            "Past source branch receipts can improve local target exploration by certifying a monotone "
            "easy-to-hard curriculum sequence before target hard verification."
        ),
        evidence_grade="G1",
        scope="branch_curriculum_transfer",
        requirements=(
            requirement(
                "branch_curriculum_transfer_certificate_valid",
                validate_branch_curriculum_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_curriculum_certificates_valid", report.all_branch_curriculum_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_sequence_commits_all_domains", report.source_sequence_success_count == report.domain_count * 3),
            requirement("static_commits_no_domains", report.static_success_count == 0),
            requirement("guided_curriculum_commits_all_levels", report.guided_curriculum_success_count == report.domain_count * 2),
            requirement("guided_final_commits_all_domains", report.guided_final_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_curriculum_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 3),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_sequence_success_count": report.source_sequence_success_count,
            "static_success_count": report.static_success_count,
            "guided_curriculum_success_count": report.guided_curriculum_success_count,
            "guided_final_success_count": report.guided_final_success_count,
        },
        boundary=BRANCH_CURRICULUM_CLAIM_BOUNDARY,
        sources=BRANCH_CURRICULUM_SOURCES,
    )


class HighestCurriculumUtilityRanker:
    def choose(self, verified: list[tuple[ProposalTrace, TypedCandidate, HardVerifierResult]]) -> int:
        best_idx = 0
        best_value = float("-inf")
        for idx, (_, candidate, result) in enumerate(verified):
            payload = candidate.payload if isinstance(candidate.payload, Mapping) else {}
            value = float(result.metadata.get("utility", payload.get("utility", 0)))
            if value > best_value:
                best_idx = idx
                best_value = value
        return best_idx


def normalize_curriculum_state(state: CurriculumState | Mapping[str, Any]) -> CurriculumState:
    if isinstance(state, CurriculumState):
        return CurriculumState(
            progress=tuple((str(context), str(key), int(level)) for context, key, level in state.progress),
            finals=tuple((str(context), str(key)) for context, key in state.finals),
        )
    return CurriculumState(
        progress=tuple((str(context), str(key), int(level)) for context, key, level in state.get("progress", ())),
        finals=tuple((str(context), str(key)) for context, key in state.get("finals", ())),
    )


def _current_level(state: CurriculumState | Mapping[str, Any], context: str, key: str) -> int:
    current = normalize_curriculum_state(state)
    levels = tuple(level for row_context, row_key, level in current.progress if row_context == context and row_key == key)
    return max(levels, default=0)


def _make_curriculum_traces(
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
            seeds=("branch-curriculum-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.curriculum.transfer.v1",
        )
        for action in actions
    )


def _curriculum_plan(spec: ExplorationDomainSpec, source_context: str, target_context: str) -> Mapping[str, Any]:
    curriculum_key = f"{spec.domain_id}_easy_to_hard"
    source_step_1 = _domain_action(spec, source_context, "source_curriculum_level_1", "step", curriculum_key, 1, 5)
    source_step_2 = _domain_action(spec, source_context, "source_curriculum_level_2", "step", curriculum_key, 2, 6)
    source_final = _domain_action(spec, source_context, "source_curriculum_final", "final", curriculum_key, 2, 8)
    target_step_1 = _domain_action(spec, target_context, "target_curriculum_level_1", "step", curriculum_key, 1, 5)
    target_step_2 = _domain_action(spec, target_context, "target_curriculum_level_2", "step", curriculum_key, 2, 6)
    target_final = _domain_action(spec, target_context, "target_curriculum_final", "final", curriculum_key, 2, 8)
    static_direct_final = _domain_action(spec, target_context, "target_direct_final", "final", curriculum_key, 2, 10)
    static_level_skip = _domain_action(spec, target_context, "target_skip_level_2", "step", curriculum_key, 2, 9)
    static_bad_level_1 = _domain_action(spec, target_context, "target_bad_level_1", "step", curriculum_key, 1, 9, valid=False)
    return {
        "curriculum_key": curriculum_key,
        "curriculum_levels": (1, 2),
        "source_actions": (source_step_1, source_step_2, source_final),
        "static_actions": (static_direct_final, static_level_skip, static_bad_level_1),
        "guided_actions": (target_step_1, target_step_2, target_final),
    }


def _domain_action(
    spec: ExplorationDomainSpec,
    context: str,
    action_suffix: str,
    kind: str,
    curriculum_key: str,
    level: int,
    utility: int,
    *,
    valid: bool = True,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "domain": spec.domain_id,
        "context": context,
        "action": f"{spec.domain_id}_{action_suffix}",
        "kind": kind,
        "curriculum_key": curriculum_key,
        "level": level,
        "required_level": level if kind == "final" else 0,
        "utility": utility,
    }
    if spec.domain_id == "robotics_replan":
        base.update({"clearance": 0.32 if valid else 0.12, "turn_rate": 0.42 if valid else 0.88})
    elif spec.domain_id == "molecule_repair":
        base.update({"valence_ok": bool(valid), "strain": 0.18 if valid else 0.61})
    elif spec.domain_id == "material_process":
        base.update({"thermal_gradient": 0.42 if valid else 0.84, "phase_purity": 0.95 if valid else 0.84})
    else:
        raise ValueError(f"unknown domain: {spec.domain_id}")
    return base


def _verify_domain_payload(payload: Mapping[str, Any]) -> tuple[bool, Mapping[str, Any] | None]:
    domain = str(payload["domain"])
    if domain == "robotics_replan":
        clearance = float(payload["clearance"])
        turn_rate = float(payload["turn_rate"])
        if clearance >= 0.25 and turn_rate <= 0.60:
            return True, None
        return False, {
            "kind": "safety_envelope_violation",
            "clearance": clearance,
            "min_clearance": 0.25,
            "turn_rate": turn_rate,
            "max_turn_rate": 0.60,
        }
    if domain == "molecule_repair":
        valence_ok = bool(payload["valence_ok"])
        strain = float(payload["strain"])
        if valence_ok and strain <= 0.35:
            return True, None
        return False, {
            "kind": "valence_strain_violation",
            "valence_ok": valence_ok,
            "strain": strain,
            "max_strain": 0.35,
        }
    if domain == "material_process":
        thermal_gradient = float(payload["thermal_gradient"])
        phase_purity = float(payload["phase_purity"])
        if thermal_gradient <= 0.50 and phase_purity >= 0.90:
            return True, None
        return False, {
            "kind": "thermal_phase_violation",
            "thermal_gradient": thermal_gradient,
            "max_thermal_gradient": 0.50,
            "phase_purity": phase_purity,
            "min_phase_purity": 0.90,
        }
    raise ValueError(f"unknown curriculum domain: {domain}")


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["domain"] = str(payload["domain"])
    normalized["context"] = str(payload["context"])
    normalized["action"] = str(payload["action"])
    normalized["kind"] = str(payload["kind"])
    normalized["curriculum_key"] = str(payload["curriculum_key"])
    normalized["level"] = int(payload.get("level", 0))
    normalized["required_level"] = int(payload.get("required_level", 0))
    normalized["current_level"] = int(payload.get("current_level", 0))
    normalized["utility"] = int(payload["utility"])
    if not normalized["domain"] or not normalized["context"] or not normalized["action"]:
        raise ValueError("domain, context, and action must be non-empty")
    return normalized


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_curriculum_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
