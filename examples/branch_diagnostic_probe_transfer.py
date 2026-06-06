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


BRANCH_DIAGNOSTIC_PROBE_CERTIFICATE_SCHEMA = "trwm.branch_diagnostic_probe_certificate.v1"
BRANCH_DIAGNOSTIC_PROBE_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_diagnostic_probe_transfer_certificate.v1"
BRANCH_DIAGNOSTIC_PROBE_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1214/aoms/1177728069",
)
BRANCH_DIAGNOSTIC_PROBE_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source branch receipts can identify "
    "which diagnostic probe to spend verifier budget on before a target final action, but the probe and "
    "the final action both require fresh target hard verification. It is not Bayesian experimental "
    "design, active learning, value-of-information optimization, robotics safety, chemistry, materials "
    "discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class DiagnosticObservation:
    domain: str
    context: str
    probe_key: str
    observed_regime: str


@dataclass(frozen=True)
class DiagnosticProbeState:
    observations: tuple[DiagnosticObservation, ...] = ()
    committed_actions: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class BranchDiagnosticProbeCertificate:
    schema_version: str
    domain: str
    probe_rule_id: str
    probe_rule_version: str
    source_context_id: str
    target_context_id: str
    probe_key: str
    hidden_regime: str
    source_reject_probe_action: str
    source_diagnostic_probe_action: str
    static_target_actions: tuple[str, ...]
    guided_probe_action: str
    guided_final_action: str
    source_reject_probe_receipt_hashes: tuple[str, ...]
    source_diagnostic_probe_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    guided_probe_receipt_hashes: tuple[str, ...]
    guided_final_receipt_hashes: tuple[str, ...]
    guided_final_commit_receipt_hashes: tuple[str, ...]
    source_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    guided_probe_branch_selection_certificate_hash: str
    guided_final_branch_selection_certificate_hash: str
    source_probe_rejected: bool
    source_probe_committed: bool
    static_committed: bool
    guided_probe_committed: bool
    guided_final_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    guided_verifier_call_count: int
    same_budget: bool
    probe_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_DIAGNOSTIC_PROBE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch diagnostic probe certificate schema: {self.schema_version}")
        for field_name in (
            "static_target_actions",
            "source_reject_probe_receipt_hashes",
            "source_diagnostic_probe_receipt_hashes",
            "static_target_receipt_hashes",
            "guided_probe_receipt_hashes",
            "guided_final_receipt_hashes",
            "guided_final_commit_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_diagnostic_probe_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchDiagnosticProbeDomainReport:
    domain: str
    source_context: str
    target_context: str
    probe_key: str
    hidden_regime: str
    source_reject_probe_action: str
    source_diagnostic_probe_action: str
    static_target_actions: tuple[str, ...]
    guided_probe_action: str
    guided_final_action: str
    source_probe_rejected: bool
    source_probe_committed: bool
    static_committed: bool
    guided_probe_committed: bool
    guided_final_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    guided_verifier_call_count: int
    source_reject_probe_receipt_hashes: tuple[str, ...]
    source_diagnostic_probe_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    guided_probe_receipt_hashes: tuple[str, ...]
    guided_final_receipt_hashes: tuple[str, ...]
    branch_diagnostic_probe_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchDiagnosticProbeTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchDiagnosticProbeDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_probe_reject_count: int
    source_probe_success_count: int
    static_success_count: int
    guided_probe_success_count: int
    guided_final_success_count: int
    same_budget_probe_count: int
    branch_diagnostic_probe_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_diagnostic_probe_certificates_valid: bool
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
class BranchDiagnosticProbeTransferCertificate:
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
    branch_diagnostic_probe_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_probe_reject_count: int
    source_probe_success_count: int
    static_success_count: int
    guided_probe_success_count: int
    guided_final_success_count: int
    same_budget_probe_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_DIAGNOSTIC_PROBE_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch diagnostic probe transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_diagnostic_probe_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_diagnostic_probe_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchDiagnosticProbeTransferResult(CertifiedExampleResult):
    report: BranchDiagnosticProbeTransferReport
    branch_diagnostic_probe_transfer_certificate: BranchDiagnosticProbeTransferCertificate
    branch_diagnostic_probe_certificates: tuple[BranchDiagnosticProbeCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


class DiagnosticProbeAdapter:
    verifier_id = "branch_diagnostic_probe_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        metadata = {
            "domain": payload["domain"],
            "context": payload["context"],
            "action": payload["action"],
            "action_type": payload["action_type"],
            "probe_key": payload["probe_key"],
            "hidden_regime": payload["hidden_regime"],
            "observed_regime": payload["observed_regime"],
        }
        if payload["action_type"] == "probe":
            if payload["diagnostic_quality"] != "target_regime" or payload["observed_regime"] != payload["hidden_regime"]:
                return HardVerifierResult.reject(
                    self.verifier_id,
                    self.verifier_version,
                    residual={
                        "kind": "uninformative_probe",
                        "probe_key": payload["probe_key"],
                        "observed_regime": payload["observed_regime"],
                        "hidden_regime": payload["hidden_regime"],
                    },
                    metadata=metadata,
                )
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        if payload["action_type"] == "final":
            if payload["observed_regime"] == "unknown":
                return HardVerifierResult.reject(
                    self.verifier_id,
                    self.verifier_version,
                    residual={"kind": "missing_diagnostic_observation", "probe_key": payload["probe_key"]},
                    metadata=metadata,
                )
            if payload["observed_regime"] != payload["required_regime"]:
                return HardVerifierResult.reject(
                    self.verifier_id,
                    self.verifier_version,
                    residual={
                        "kind": "diagnostic_regime_mismatch",
                        "observed_regime": payload["observed_regime"],
                        "required_regime": payload["required_regime"],
                    },
                    metadata=metadata,
                )
            accepted, residual = _verify_domain_payload(payload)
            if not accepted:
                return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual=residual, metadata=metadata)
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": "unknown_action_type", "action_type": payload["action_type"]},
            metadata=metadata,
        )

    def apply_commit(self, state: DiagnosticProbeState, candidate: TypedCandidate) -> DiagnosticProbeState:
        current = normalize_probe_state(state)
        payload = _normalize_payload(candidate.payload)
        if payload["action_type"] == "probe":
            observation = DiagnosticObservation(
                domain=payload["domain"],
                context=payload["context"],
                probe_key=payload["probe_key"],
                observed_regime=payload["observed_regime"],
            )
            observations = tuple(
                row for row in current.observations
                if not (row.domain == observation.domain and row.context == observation.context and row.probe_key == observation.probe_key)
            )
            return DiagnosticProbeState(
                observations=(*observations, observation),
                committed_actions=current.committed_actions,
            )
        return DiagnosticProbeState(
            observations=current.observations,
            committed_actions=(
                *current.committed_actions,
                (payload["domain"], payload["context"], payload["action"]),
            ),
        )

    def replay(self, state: DiagnosticProbeState, receipt: Receipt) -> DiagnosticProbeState:
        candidate = TypedCandidate(
            payload=receipt.replay_bundle["candidate_payload"],
            type_name=receipt.replay_bundle["candidate_type"],
            schema_version=receipt.replay_bundle["candidate_schema"],
        )
        return self.apply_commit(state, candidate)

    def rollback(self, _state: DiagnosticProbeState, receipt: Receipt) -> DiagnosticProbeState:
        return normalize_probe_state(receipt.rollback_bundle["pre_state"])


class DiagnosticProbeProjector:
    def project(self, state: DiagnosticProbeState, trace: ProposalTrace) -> TypedCandidate:
        payload = dict(trace.actions[-1])
        normalized_state = normalize_probe_state(state)
        if str(payload.get("action_type")) == "final":
            payload["observed_regime"] = _observed_regime(
                normalized_state,
                domain=str(payload["domain"]),
                context=str(payload["context"]),
                probe_key=str(payload["probe_key"]),
            )
        return TypedCandidate(
            payload=_normalize_payload(payload),
            type_name="branch.diagnostic_probe.action",
            schema_version="branch.diagnostic_probe.action.v1",
        )


def run_branch_diagnostic_probe_transfer_experiment() -> BranchDiagnosticProbeTransferReport:
    return run_branch_diagnostic_probe_transfer_certified_experiment().report


def run_branch_diagnostic_probe_transfer_certified_experiment() -> CertifiedBranchDiagnosticProbeTransferResult:
    seed = DiagnosticProbeState()
    state = seed
    engine = TransactionEngine(DiagnosticProbeAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, DiagnosticProbeProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchDiagnosticProbeDomainReport] = []
    probe_certificates: list[BranchDiagnosticProbeCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_context = f"{spec.domain_id}:source:diagnostic_probe"
        target_context = f"{spec.domain_id}:target:diagnostic_probe"
        plan = _domain_probe_plan(spec, source_context, target_context)

        source_outcome = runtime.step(
            state,
            _make_probe_traces(
                spec,
                context=source_context,
                phase="source-probe-selection",
                actions=(plan["source_reject_probe"], plan["source_diagnostic_probe"]),
            ),
        )
        state = normalize_probe_state(source_outcome.state)
        source_certificate = build_branch_selection_certificate(
            source_outcome.receipts,
            verifier_call_count=source_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(source_outcome.receipts), source_certificate))
        memory.update_branch(source_outcome.receipts, source_certificate)

        static_outcome = runtime.step(
            state,
            _make_probe_traces(
                spec,
                context=target_context,
                phase="target-static-finals",
                actions=tuple(plan["static_targets"]),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        guided_probe_outcome = runtime.step(
            state,
            _make_probe_traces(
                spec,
                context=target_context,
                phase="target-guided-probe",
                actions=(plan["guided_probe"],),
            ),
        )
        state = normalize_probe_state(guided_probe_outcome.state)
        guided_probe_certificate = build_branch_selection_certificate(
            guided_probe_outcome.receipts,
            verifier_call_count=guided_probe_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(guided_probe_outcome.receipts), guided_probe_certificate))

        guided_final_outcome = runtime.step(
            state,
            _make_probe_traces(
                spec,
                context=target_context,
                phase="target-guided-final",
                actions=(plan["guided_final"],),
            ),
        )
        state = normalize_probe_state(guided_final_outcome.state)
        guided_final_certificate = build_branch_selection_certificate(
            guided_final_outcome.receipts,
            verifier_call_count=guided_final_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(guided_final_outcome.receipts), guided_final_certificate))

        source_reject_hashes = tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.hard_result.rejected)
        source_probe_hashes = tuple(receipt.receipt_hash for receipt in source_outcome.receipts if receipt.committed)
        static_hashes = tuple(receipt.receipt_hash for receipt in static_outcome.receipts)
        guided_probe_hashes = tuple(receipt.receipt_hash for receipt in guided_probe_outcome.receipts)
        guided_final_hashes = tuple(receipt.receipt_hash for receipt in guided_final_outcome.receipts)
        guided_final_commit_hashes = tuple(receipt.receipt_hash for receipt in guided_final_outcome.receipts if receipt.committed)

        certificate = build_branch_diagnostic_probe_certificate(
            spec,
            source_context_id=source_context,
            target_context_id=target_context,
            probe_key=str(plan["probe_key"]),
            hidden_regime=str(plan["hidden_regime"]),
            source_reject_probe_action=str(plan["source_reject_probe"]["action"]),
            source_diagnostic_probe_action=str(plan["source_diagnostic_probe"]["action"]),
            static_target_actions=tuple(str(action["action"]) for action in plan["static_targets"]),
            guided_probe_action=str(plan["guided_probe"]["action"]),
            guided_final_action=str(plan["guided_final"]["action"]),
            source_reject_probe_receipt_hashes=source_reject_hashes,
            source_diagnostic_probe_receipt_hashes=source_probe_hashes,
            static_target_receipt_hashes=static_hashes,
            guided_probe_receipt_hashes=guided_probe_hashes,
            guided_final_receipt_hashes=guided_final_hashes,
            guided_final_commit_receipt_hashes=guided_final_commit_hashes,
            source_branch_selection_certificate_hash=source_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            guided_probe_branch_selection_certificate_hash=guided_probe_certificate.certificate_hash,
            guided_final_branch_selection_certificate_hash=guided_final_certificate.certificate_hash,
            source_probe_rejected=bool(source_reject_hashes),
            source_probe_committed=source_outcome.committed,
            static_committed=static_outcome.committed,
            guided_probe_committed=guided_probe_outcome.committed,
            guided_final_committed=guided_final_outcome.committed,
            source_verifier_call_count=source_outcome.verifier_calls,
            static_verifier_call_count=static_outcome.verifier_calls,
            guided_verifier_call_count=guided_probe_outcome.verifier_calls + guided_final_outcome.verifier_calls,
        )
        probe_certificates.append(certificate)
        rows.append(
            BranchDiagnosticProbeDomainReport(
                domain=spec.domain_id,
                source_context=source_context,
                target_context=target_context,
                probe_key=certificate.probe_key,
                hidden_regime=certificate.hidden_regime,
                source_reject_probe_action=certificate.source_reject_probe_action,
                source_diagnostic_probe_action=certificate.source_diagnostic_probe_action,
                static_target_actions=certificate.static_target_actions,
                guided_probe_action=certificate.guided_probe_action,
                guided_final_action=certificate.guided_final_action,
                source_probe_rejected=certificate.source_probe_rejected,
                source_probe_committed=certificate.source_probe_committed,
                static_committed=certificate.static_committed,
                guided_probe_committed=certificate.guided_probe_committed,
                guided_final_committed=certificate.guided_final_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                guided_verifier_call_count=certificate.guided_verifier_call_count,
                source_reject_probe_receipt_hashes=certificate.source_reject_probe_receipt_hashes,
                source_diagnostic_probe_receipt_hashes=certificate.source_diagnostic_probe_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                guided_probe_receipt_hashes=certificate.guided_probe_receipt_hashes,
                guided_final_receipt_hashes=certificate.guided_final_receipt_hashes,
                branch_diagnostic_probe_certificate_hash=certificate.certificate_hash,
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

    report = BranchDiagnosticProbeTransferReport(
        schema_version="trwm.example.branch_diagnostic_probe_transfer.v1",
        experiment_id="branch_diagnostic_probe_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_probe_reject_count=sum(1 for row in rows if row.source_probe_rejected),
        source_probe_success_count=sum(1 for row in rows if row.source_probe_committed),
        static_success_count=sum(1 for row in rows if row.static_committed),
        guided_probe_success_count=sum(1 for row in rows if row.guided_probe_committed),
        guided_final_success_count=sum(1 for row in rows if row.guided_final_committed),
        same_budget_probe_count=sum(1 for row in rows if row.same_budget),
        branch_diagnostic_probe_certificate_count=len(probe_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_diagnostic_probe_certificates_valid=all(
            validate_branch_diagnostic_probe_certificate(certificate, row)
            for certificate, row in zip(probe_certificates, rows)
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
            "probe_key",
            "observed_regime",
            "required_regime",
            "clearance",
            "turn_rate",
            "valence_ok",
            "strain",
            "thermal_gradient",
            "phase_purity",
        ),
        residual_kinds=(
            "missing_diagnostic_observation",
            "uninformative_probe",
        ),
        sources=BRANCH_DIAGNOSTIC_PROBE_SOURCES,
        learning=(
            "Branches of the past can improve exploration by teaching which diagnostic probe to spend "
            "budget on before a final action. The target still needs fresh receipts for both the probe "
            "and the final action, so active probing remains evidence rather than commit authority."
        ),
    )
    transfer_certificate = build_branch_diagnostic_probe_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_diagnostic_probe_certificate_hashes=tuple(certificate.certificate_hash for certificate in probe_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_diagnostic_probe_transfer",
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
        claim_boundary=BRANCH_DIAGNOSTIC_PROBE_CLAIM_BOUNDARY,
        sources=BRANCH_DIAGNOSTIC_PROBE_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchDiagnosticProbeTransferResult(
        report=report,
        branch_diagnostic_probe_transfer_certificate=transfer_certificate,
        branch_diagnostic_probe_certificates=tuple(probe_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_diagnostic_probe_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_id: str,
    target_context_id: str,
    probe_key: str,
    hidden_regime: str,
    source_reject_probe_action: str,
    source_diagnostic_probe_action: str,
    static_target_actions: tuple[str, ...],
    guided_probe_action: str,
    guided_final_action: str,
    source_reject_probe_receipt_hashes: tuple[str, ...],
    source_diagnostic_probe_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    guided_probe_receipt_hashes: tuple[str, ...],
    guided_final_receipt_hashes: tuple[str, ...],
    guided_final_commit_receipt_hashes: tuple[str, ...],
    source_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    guided_probe_branch_selection_certificate_hash: str,
    guided_final_branch_selection_certificate_hash: str,
    source_probe_rejected: bool,
    source_probe_committed: bool,
    static_committed: bool,
    guided_probe_committed: bool,
    guided_final_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    guided_verifier_call_count: int,
) -> BranchDiagnosticProbeCertificate:
    return BranchDiagnosticProbeCertificate(
        schema_version=BRANCH_DIAGNOSTIC_PROBE_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        probe_rule_id="source_branch_selects_target_diagnostic_probe",
        probe_rule_version="1.0",
        source_context_id=source_context_id,
        target_context_id=target_context_id,
        probe_key=probe_key,
        hidden_regime=hidden_regime,
        source_reject_probe_action=source_reject_probe_action,
        source_diagnostic_probe_action=source_diagnostic_probe_action,
        static_target_actions=static_target_actions,
        guided_probe_action=guided_probe_action,
        guided_final_action=guided_final_action,
        source_reject_probe_receipt_hashes=source_reject_probe_receipt_hashes,
        source_diagnostic_probe_receipt_hashes=source_diagnostic_probe_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        guided_probe_receipt_hashes=guided_probe_receipt_hashes,
        guided_final_receipt_hashes=guided_final_receipt_hashes,
        guided_final_commit_receipt_hashes=guided_final_commit_receipt_hashes,
        source_branch_selection_certificate_hash=source_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        guided_probe_branch_selection_certificate_hash=guided_probe_branch_selection_certificate_hash,
        guided_final_branch_selection_certificate_hash=guided_final_branch_selection_certificate_hash,
        source_probe_rejected=source_probe_rejected,
        source_probe_committed=source_probe_committed,
        static_committed=static_committed,
        guided_probe_committed=guided_probe_committed,
        guided_final_committed=guided_final_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        guided_verifier_call_count=guided_verifier_call_count,
        same_budget=static_verifier_call_count == guided_verifier_call_count == 2,
        probe_reason="source_branch_probe_receipts_identify_target_diagnostic_probe",
    )


def validate_branch_diagnostic_probe_certificate(
    certificate: BranchDiagnosticProbeCertificate,
    row: BranchDiagnosticProbeDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_DIAGNOSTIC_PROBE_CERTIFICATE_SCHEMA:
            return False
        if certificate.probe_rule_id != "source_branch_selects_target_diagnostic_probe":
            return False
        if certificate.probe_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.source_context_id,
            certificate.target_context_id,
            certificate.probe_key,
            certificate.hidden_regime,
            certificate.source_reject_probe_action,
            certificate.source_diagnostic_probe_action,
            certificate.guided_probe_action,
            certificate.guided_final_action,
        ):
            if not _nonempty(value):
                return False
        if len(certificate.static_target_actions) != 2 or any(not _nonempty(value) for value in certificate.static_target_actions):
            return False
        if not certificate.source_probe_rejected or not certificate.source_probe_committed:
            return False
        if certificate.static_committed:
            return False
        if not certificate.guided_probe_committed or not certificate.guided_final_committed:
            return False
        if certificate.source_verifier_call_count != 2:
            return False
        if certificate.static_verifier_call_count != 2 or certificate.guided_verifier_call_count != 2:
            return False
        if not certificate.same_budget:
            return False
        if certificate.probe_reason != "source_branch_probe_receipts_identify_target_diagnostic_probe":
            return False
        hash_groups = (
            (certificate.source_reject_probe_receipt_hashes, 1),
            (certificate.source_diagnostic_probe_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 2),
            (certificate.guided_probe_receipt_hashes, 1),
            (certificate.guided_final_receipt_hashes, 1),
            (certificate.guided_final_commit_receipt_hashes, 1),
        )
        for values, expected_len in hash_groups:
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.source_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.guided_probe_branch_selection_certificate_hash,
            certificate.guided_final_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_context != certificate.source_context_id or row.target_context != certificate.target_context_id:
                return False
            if row.probe_key != certificate.probe_key or row.hidden_regime != certificate.hidden_regime:
                return False
            if row.source_reject_probe_action != certificate.source_reject_probe_action:
                return False
            if row.source_diagnostic_probe_action != certificate.source_diagnostic_probe_action:
                return False
            if row.static_target_actions != certificate.static_target_actions:
                return False
            if row.guided_probe_action != certificate.guided_probe_action:
                return False
            if row.guided_final_action != certificate.guided_final_action:
                return False
            if row.source_probe_rejected != certificate.source_probe_rejected:
                return False
            if row.source_probe_committed != certificate.source_probe_committed:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.guided_probe_committed != certificate.guided_probe_committed:
                return False
            if row.guided_final_committed != certificate.guided_final_committed:
                return False
            if row.source_verifier_call_count != certificate.source_verifier_call_count:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.guided_verifier_call_count != certificate.guided_verifier_call_count:
                return False
            if row.source_reject_probe_receipt_hashes != certificate.source_reject_probe_receipt_hashes:
                return False
            if row.source_diagnostic_probe_receipt_hashes != certificate.source_diagnostic_probe_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.guided_probe_receipt_hashes != certificate.guided_probe_receipt_hashes:
                return False
            if row.guided_final_receipt_hashes != certificate.guided_final_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_diagnostic_probe_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_diagnostic_probe_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_diagnostic_probe_transfer_certificate(
    report: BranchDiagnosticProbeTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_diagnostic_probe_certificate_hashes: tuple[str, ...],
) -> BranchDiagnosticProbeTransferCertificate:
    return BranchDiagnosticProbeTransferCertificate(
        schema_version=BRANCH_DIAGNOSTIC_PROBE_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_diagnostic_probe_certificate_hashes=branch_diagnostic_probe_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_probe_reject_count=report.source_probe_reject_count,
        source_probe_success_count=report.source_probe_success_count,
        static_success_count=report.static_success_count,
        guided_probe_success_count=report.guided_probe_success_count,
        guided_final_success_count=report.guided_final_success_count,
        same_budget_probe_count=report.same_budget_probe_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_DIAGNOSTIC_PROBE_CLAIM_BOUNDARY,
    )


def validate_branch_diagnostic_probe_transfer_certificate(
    certificate: BranchDiagnosticProbeTransferCertificate,
    report: BranchDiagnosticProbeTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_DIAGNOSTIC_PROBE_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_diagnostic_probe_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 4:
            return False
        if len(certificate.branch_diagnostic_probe_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_probe_reject_count != certificate.domain_count:
            return False
        if certificate.source_probe_success_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.guided_probe_success_count != certificate.domain_count:
            return False
        if certificate.guided_final_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_probe_count != certificate.domain_count:
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
            if not report.all_branch_diagnostic_probe_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
        return certificate.certificate_hash == branch_diagnostic_probe_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_diagnostic_probe_certificate_hash(
    certificate: BranchDiagnosticProbeCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchDiagnosticProbeCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_diagnostic_probe_transfer_certificate_hash(
    certificate: BranchDiagnosticProbeTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchDiagnosticProbeTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchDiagnosticProbeTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def normalize_probe_state(state: DiagnosticProbeState | Mapping[str, Any]) -> DiagnosticProbeState:
    if isinstance(state, DiagnosticProbeState):
        observations = state.observations
        committed_actions = state.committed_actions
    else:
        observations = tuple(state.get("observations", ()))
        committed_actions = tuple(state.get("committed_actions", ()))
    normalized_observations = tuple(
        observation if isinstance(observation, DiagnosticObservation) else DiagnosticObservation(**dict(observation))
        for observation in observations
    )
    return DiagnosticProbeState(
        observations=tuple(
            DiagnosticObservation(
                domain=str(row.domain),
                context=str(row.context),
                probe_key=str(row.probe_key),
                observed_regime=str(row.observed_regime),
            )
            for row in normalized_observations
        ),
        committed_actions=tuple((str(domain), str(context), str(action)) for domain, context, action in committed_actions),
    )


def _build_claim_certificate(
    report: BranchDiagnosticProbeTransferReport,
    transfer_certificate: BranchDiagnosticProbeTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_diagnostic_probe_transfer_g1",
        claim_text=(
            "Past branch receipts can improve local target exploration by certifying which diagnostic "
            "probe to run before a final action, while both probe and final commits require fresh target verification."
        ),
        evidence_grade="G1",
        scope="branch_diagnostic_probe_transfer",
        requirements=(
            requirement(
                "branch_diagnostic_probe_transfer_certificate_valid",
                validate_branch_diagnostic_probe_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_diagnostic_probe_certificates_valid", report.all_branch_diagnostic_probe_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("source_probe_rejects_all_domains", report.source_probe_reject_count == report.domain_count),
            requirement("source_probe_succeeds_all_domains", report.source_probe_success_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("guided_probe_succeeds_all_domains", report.guided_probe_success_count == report.domain_count),
            requirement("guided_final_succeeds_all_domains", report.guided_final_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_probe_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 2),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_probe_success_count": report.source_probe_success_count,
            "static_success_count": report.static_success_count,
            "guided_probe_success_count": report.guided_probe_success_count,
            "guided_final_success_count": report.guided_final_success_count,
        },
        boundary=BRANCH_DIAGNOSTIC_PROBE_CLAIM_BOUNDARY,
        sources=BRANCH_DIAGNOSTIC_PROBE_SOURCES,
    )


def _make_probe_traces(
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
            seeds=("branch-diagnostic-probe-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.diagnostic.probe.transfer.v1",
        )
        for action in actions
    )


def _domain_probe_plan(spec: ExplorationDomainSpec, source_context: str, target_context: str) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return _probe_plan(
            spec,
            source_context,
            target_context,
            probe_key="corridor_regime",
            hidden_regime="narrow_corridor",
            source_bad="cheap_clearance_prior",
            source_probe="lidar_corridor_probe",
            static_actions=("unprobed_short_cut", "unprobed_wide_turn"),
            guided_probe="target_lidar_corridor_probe",
            guided_final="narrow_corridor_detour",
            final_fields={"clearance": 0.34, "turn_rate": 0.42},
        )
    if spec.domain_id == "molecule_repair":
        return _probe_plan(
            spec,
            source_context,
            target_context,
            probe_key="site_regime",
            hidden_regime="acidic_site",
            source_bad="cheap_valence_prior",
            source_probe="spectral_site_probe",
            static_actions=("unprobed_valence_patch", "unprobed_ring_patch"),
            guided_probe="target_spectral_site_probe",
            guided_final="acidic_site_repair",
            final_fields={"valence_ok": True, "strain": 0.18},
        )
    if spec.domain_id == "material_process":
        return _probe_plan(
            spec,
            source_context,
            target_context,
            probe_key="thermal_regime",
            hidden_regime="high_thermal_mass",
            source_bad="cheap_temperature_prior",
            source_probe="calorimetry_window_probe",
            static_actions=("unprobed_flash_anneal", "unprobed_hold_anneal"),
            guided_probe="target_calorimetry_window_probe",
            guided_final="high_mass_tempered_anneal",
            final_fields={"thermal_gradient": 0.40, "phase_purity": 0.94},
        )
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _probe_plan(
    spec: ExplorationDomainSpec,
    source_context: str,
    target_context: str,
    *,
    probe_key: str,
    hidden_regime: str,
    source_bad: str,
    source_probe: str,
    static_actions: tuple[str, str],
    guided_probe: str,
    guided_final: str,
    final_fields: Mapping[str, Any],
) -> Mapping[str, Any]:
    source_reject_probe = _probe_action(
        spec.domain_id,
        source_context,
        source_bad,
        probe_key=probe_key,
        hidden_regime=hidden_regime,
        diagnostic_quality="coarse_prior",
        observed_regime="unknown",
    )
    source_diagnostic_probe = _probe_action(
        spec.domain_id,
        source_context,
        source_probe,
        probe_key=probe_key,
        hidden_regime=hidden_regime,
        diagnostic_quality="target_regime",
        observed_regime=hidden_regime,
    )
    static_targets = tuple(
        _final_action(
            spec.domain_id,
            target_context,
            action,
            probe_key=probe_key,
            hidden_regime=hidden_regime,
            required_regime=hidden_regime,
            final_fields=final_fields,
        )
        for action in static_actions
    )
    guided_probe_action = _probe_action(
        spec.domain_id,
        target_context,
        guided_probe,
        probe_key=probe_key,
        hidden_regime=hidden_regime,
        diagnostic_quality="target_regime",
        observed_regime=hidden_regime,
    )
    guided_final_action = _final_action(
        spec.domain_id,
        target_context,
        guided_final,
        probe_key=probe_key,
        hidden_regime=hidden_regime,
        required_regime=hidden_regime,
        final_fields=final_fields,
    )
    return {
        "probe_key": probe_key,
        "hidden_regime": hidden_regime,
        "source_reject_probe": source_reject_probe,
        "source_diagnostic_probe": source_diagnostic_probe,
        "static_targets": static_targets,
        "guided_probe": guided_probe_action,
        "guided_final": guided_final_action,
    }


def _probe_action(
    domain: str,
    context: str,
    action: str,
    *,
    probe_key: str,
    hidden_regime: str,
    diagnostic_quality: str,
    observed_regime: str,
) -> Mapping[str, Any]:
    return {
        "domain": domain,
        "context": context,
        "action": action,
        "action_type": "probe",
        "probe_key": probe_key,
        "hidden_regime": hidden_regime,
        "observed_regime": observed_regime,
        "required_regime": hidden_regime,
        "diagnostic_quality": diagnostic_quality,
        "utility": 1,
    }


def _final_action(
    domain: str,
    context: str,
    action: str,
    *,
    probe_key: str,
    hidden_regime: str,
    required_regime: str,
    final_fields: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        "domain": domain,
        "context": context,
        "action": action,
        "action_type": "final",
        "probe_key": probe_key,
        "hidden_regime": hidden_regime,
        "observed_regime": "unknown",
        "required_regime": required_regime,
        "diagnostic_quality": "not_applicable",
        "utility": 8,
        **dict(final_fields),
    }


def _verify_domain_payload(payload: Mapping[str, Any]) -> tuple[bool, Mapping[str, Any] | None]:
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
    for key in (
        "domain",
        "context",
        "action",
        "action_type",
        "probe_key",
        "hidden_regime",
        "observed_regime",
        "required_regime",
        "diagnostic_quality",
    ):
        row[key] = str(row.get(key, ""))
    row["utility"] = int(row.get("utility", 0))
    return row


def _observed_regime(state: DiagnosticProbeState, *, domain: str, context: str, probe_key: str) -> str:
    for observation in reversed(state.observations):
        if observation.domain == domain and observation.context == context and observation.probe_key == probe_key:
            return observation.observed_regime
    return "unknown"


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_diagnostic_probe_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
