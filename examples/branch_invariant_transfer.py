from __future__ import annotations

from dataclasses import asdict, dataclass
import json
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


BRANCH_INVARIANT_CERTIFICATE_SCHEMA = "trwm.branch_invariant_certificate.v1"
BRANCH_INVARIANT_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_invariant_transfer_certificate.v1"
BRANCH_INVARIANT_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://www.ijcai.org/Proceedings/77-1/Papers/048.pdf",
)
BRANCH_INVARIANT_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows positive and negative source branch "
    "receipts can identify a contrastive invariant signature for target proposal ranking under a matched "
    "one-call verifier budget, but the invariant target candidate still commits only through fresh hard "
    "verification. It is not version-space learning, candidate elimination, classifier learning, robotics "
    "safety, chemistry, materials discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchInvariantCertificate:
    schema_version: str
    domain: str
    invariant_rule_id: str
    invariant_rule_version: str
    source_context_ids: tuple[str, ...]
    target_context_id: str
    invariant_id: str
    invariant_version: str
    invariant_field_keys: tuple[str, ...]
    positive_action_ids: tuple[str, ...]
    negative_action_ids: tuple[str, ...]
    static_target_action: str
    invariant_target_action: str
    source_positive_receipt_hashes: tuple[str, ...]
    source_negative_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    invariant_target_receipt_hashes: tuple[str, ...]
    invariant_target_commit_receipt_hashes: tuple[str, ...]
    source_positive_branch_selection_certificate_hashes: tuple[str, ...]
    source_negative_branch_selection_certificate_hashes: tuple[str, ...]
    static_branch_selection_certificate_hash: str
    invariant_branch_selection_certificate_hash: str
    source_positive_committed_count: int
    source_negative_rejected_count: int
    static_committed: bool
    invariant_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    invariant_verifier_call_count: int
    same_budget: bool
    invariant_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_INVARIANT_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch invariant certificate schema: {self.schema_version}")
        for field_name in (
            "source_context_ids",
            "invariant_field_keys",
            "positive_action_ids",
            "negative_action_ids",
            "source_positive_receipt_hashes",
            "source_negative_receipt_hashes",
            "static_target_receipt_hashes",
            "invariant_target_receipt_hashes",
            "invariant_target_commit_receipt_hashes",
            "source_positive_branch_selection_certificate_hashes",
            "source_negative_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_invariant_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchInvariantDomainReport:
    domain: str
    source_contexts: tuple[str, ...]
    target_context: str
    invariant_id: str
    invariant_field_keys: tuple[str, ...]
    positive_action_ids: tuple[str, ...]
    negative_action_ids: tuple[str, ...]
    static_target_action: str
    invariant_target_action: str
    source_positive_committed_count: int
    source_negative_rejected_count: int
    static_committed: bool
    invariant_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    invariant_verifier_call_count: int
    source_positive_receipt_hashes: tuple[str, ...]
    source_negative_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    invariant_target_receipt_hashes: tuple[str, ...]
    branch_invariant_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchInvariantTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchInvariantDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_positive_success_count: int
    source_negative_reject_count: int
    static_success_count: int
    invariant_success_count: int
    same_budget_invariant_count: int
    branch_invariant_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_invariant_certificates_valid: bool
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
class BranchInvariantTransferCertificate:
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
    branch_invariant_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_positive_success_count: int
    source_negative_reject_count: int
    static_success_count: int
    invariant_success_count: int
    same_budget_invariant_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_INVARIANT_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch invariant transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_invariant_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_invariant_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchInvariantTransferResult(CertifiedExampleResult):
    report: BranchInvariantTransferReport
    branch_invariant_transfer_certificate: BranchInvariantTransferCertificate
    branch_invariant_certificates: tuple[BranchInvariantCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_invariant_transfer_experiment() -> BranchInvariantTransferReport:
    return run_branch_invariant_transfer_certified_experiment().report


def run_branch_invariant_transfer_certified_experiment() -> CertifiedBranchInvariantTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchInvariantDomainReport] = []
    invariant_certificates: list[BranchInvariantCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_contexts = (
            f"{spec.domain_id}:source:invariant:positive_a",
            f"{spec.domain_id}:source:invariant:positive_b",
            f"{spec.domain_id}:source:invariant:negative_a",
            f"{spec.domain_id}:source:invariant:negative_b",
        )
        target_context = f"{spec.domain_id}:target:invariant"
        plan = _domain_invariant_plan(spec, source_contexts, target_context)

        source_outcomes = []
        source_certificates = []
        for source_context, source_action in zip(source_contexts, plan["source_actions"]):
            outcome = runtime.step(
                state,
                _make_invariant_traces(
                    spec,
                    context=source_context,
                    phase="source-invariant",
                    actions=(source_action,),
                ),
            )
            state = normalize_state(outcome.state)
            certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), certificate))
            memory.update_branch(outcome.receipts, certificate)
            source_outcomes.append(outcome)
            source_certificates.append(certificate)

        static_outcome = runtime.step(
            state,
            _make_invariant_traces(
                spec,
                context=target_context,
                phase="target-static",
                actions=(plan["target_static"],),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        invariant_outcome = runtime.step(
            state,
            _make_invariant_traces(
                spec,
                context=target_context,
                phase="target-invariant",
                actions=(plan["target_invariant"],),
            ),
        )
        state = normalize_state(invariant_outcome.state)
        invariant_selection_certificate = build_branch_selection_certificate(
            invariant_outcome.receipts,
            verifier_call_count=invariant_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(invariant_outcome.receipts), invariant_selection_certificate))

        positive_outcomes = tuple(source_outcomes[:2])
        negative_outcomes = tuple(source_outcomes[2:])
        positive_certificates = tuple(source_certificates[:2])
        negative_certificates = tuple(source_certificates[2:])
        source_positive_hashes = tuple(receipt.receipt_hash for outcome in positive_outcomes for receipt in outcome.receipts if receipt.committed)
        source_negative_hashes = tuple(receipt.receipt_hash for outcome in negative_outcomes for receipt in outcome.receipts if receipt.hard_result.rejected)
        static_hashes = tuple(receipt.receipt_hash for receipt in static_outcome.receipts)
        invariant_hashes = tuple(receipt.receipt_hash for receipt in invariant_outcome.receipts)
        invariant_commit_hashes = tuple(receipt.receipt_hash for receipt in invariant_outcome.receipts if receipt.committed)

        certificate = build_branch_invariant_certificate(
            spec,
            source_context_ids=source_contexts,
            target_context_id=target_context,
            invariant_id=str(plan["invariant_id"]),
            invariant_field_keys=tuple(str(key) for key in plan["invariant_field_keys"]),
            positive_action_ids=tuple(str(action["action"]) for action in plan["source_actions"][:2]),
            negative_action_ids=tuple(str(action["action"]) for action in plan["source_actions"][2:]),
            static_target_action=str(plan["target_static"]["action"]),
            invariant_target_action=str(plan["target_invariant"]["action"]),
            source_positive_receipt_hashes=source_positive_hashes,
            source_negative_receipt_hashes=source_negative_hashes,
            static_target_receipt_hashes=static_hashes,
            invariant_target_receipt_hashes=invariant_hashes,
            invariant_target_commit_receipt_hashes=invariant_commit_hashes,
            source_positive_branch_selection_certificate_hashes=tuple(c.certificate_hash for c in positive_certificates),
            source_negative_branch_selection_certificate_hashes=tuple(c.certificate_hash for c in negative_certificates),
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            invariant_branch_selection_certificate_hash=invariant_selection_certificate.certificate_hash,
            source_positive_committed_count=sum(1 for outcome in positive_outcomes if outcome.committed),
            source_negative_rejected_count=sum(1 for outcome in negative_outcomes if not outcome.committed),
            static_committed=static_outcome.committed,
            invariant_committed=invariant_outcome.committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in source_outcomes),
            static_verifier_call_count=static_outcome.verifier_calls,
            invariant_verifier_call_count=invariant_outcome.verifier_calls,
        )
        invariant_certificates.append(certificate)
        rows.append(
            BranchInvariantDomainReport(
                domain=spec.domain_id,
                source_contexts=certificate.source_context_ids,
                target_context=certificate.target_context_id,
                invariant_id=certificate.invariant_id,
                invariant_field_keys=certificate.invariant_field_keys,
                positive_action_ids=certificate.positive_action_ids,
                negative_action_ids=certificate.negative_action_ids,
                static_target_action=certificate.static_target_action,
                invariant_target_action=certificate.invariant_target_action,
                source_positive_committed_count=certificate.source_positive_committed_count,
                source_negative_rejected_count=certificate.source_negative_rejected_count,
                static_committed=certificate.static_committed,
                invariant_committed=certificate.invariant_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                invariant_verifier_call_count=certificate.invariant_verifier_call_count,
                source_positive_receipt_hashes=certificate.source_positive_receipt_hashes,
                source_negative_receipt_hashes=certificate.source_negative_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                invariant_target_receipt_hashes=certificate.invariant_target_receipt_hashes,
                branch_invariant_certificate_hash=certificate.certificate_hash,
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

    report = BranchInvariantTransferReport(
        schema_version="trwm.example.branch_invariant_transfer.v1",
        experiment_id="branch_invariant_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_positive_success_count=sum(row.source_positive_committed_count for row in rows),
        source_negative_reject_count=sum(row.source_negative_rejected_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        invariant_success_count=sum(1 for row in rows if row.invariant_committed),
        same_budget_invariant_count=sum(1 for row in rows if row.same_budget),
        branch_invariant_certificate_count=len(invariant_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_invariant_certificates_valid=all(
            validate_branch_invariant_certificate(certificate, row)
            for certificate, row in zip(invariant_certificates, rows)
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
        sources=BRANCH_INVARIANT_SOURCES,
        learning=(
            "Positive and negative source branch receipts can identify an invariant signature for target "
            "proposal ranking, but the invariant is still a proposal filter. Target commits remain owned "
            "by the hard verifier, ledger audit, replay audit, rollback audit, and claim certificate."
        ),
    )
    transfer_certificate = build_branch_invariant_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_invariant_certificate_hashes=tuple(certificate.certificate_hash for certificate in invariant_certificates),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_invariant_transfer",
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
        claim_boundary=BRANCH_INVARIANT_CLAIM_BOUNDARY,
        sources=BRANCH_INVARIANT_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchInvariantTransferResult(
        report=report,
        branch_invariant_transfer_certificate=transfer_certificate,
        branch_invariant_certificates=tuple(invariant_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_invariant_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_ids: tuple[str, ...],
    target_context_id: str,
    invariant_id: str,
    invariant_field_keys: tuple[str, ...],
    positive_action_ids: tuple[str, ...],
    negative_action_ids: tuple[str, ...],
    static_target_action: str,
    invariant_target_action: str,
    source_positive_receipt_hashes: tuple[str, ...],
    source_negative_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    invariant_target_receipt_hashes: tuple[str, ...],
    invariant_target_commit_receipt_hashes: tuple[str, ...],
    source_positive_branch_selection_certificate_hashes: tuple[str, ...],
    source_negative_branch_selection_certificate_hashes: tuple[str, ...],
    static_branch_selection_certificate_hash: str,
    invariant_branch_selection_certificate_hash: str,
    source_positive_committed_count: int,
    source_negative_rejected_count: int,
    static_committed: bool,
    invariant_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    invariant_verifier_call_count: int,
) -> BranchInvariantCertificate:
    return BranchInvariantCertificate(
        schema_version=BRANCH_INVARIANT_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        invariant_rule_id="positive_negative_branch_invariant",
        invariant_rule_version="1.0",
        source_context_ids=source_context_ids,
        target_context_id=target_context_id,
        invariant_id=invariant_id,
        invariant_version="1.0",
        invariant_field_keys=invariant_field_keys,
        positive_action_ids=positive_action_ids,
        negative_action_ids=negative_action_ids,
        static_target_action=static_target_action,
        invariant_target_action=invariant_target_action,
        source_positive_receipt_hashes=source_positive_receipt_hashes,
        source_negative_receipt_hashes=source_negative_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        invariant_target_receipt_hashes=invariant_target_receipt_hashes,
        invariant_target_commit_receipt_hashes=invariant_target_commit_receipt_hashes,
        source_positive_branch_selection_certificate_hashes=source_positive_branch_selection_certificate_hashes,
        source_negative_branch_selection_certificate_hashes=source_negative_branch_selection_certificate_hashes,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        invariant_branch_selection_certificate_hash=invariant_branch_selection_certificate_hash,
        source_positive_committed_count=source_positive_committed_count,
        source_negative_rejected_count=source_negative_rejected_count,
        static_committed=static_committed,
        invariant_committed=invariant_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        invariant_verifier_call_count=invariant_verifier_call_count,
        same_budget=static_verifier_call_count == invariant_verifier_call_count == 1,
        invariant_reason="positive_negative_source_receipts_define_target_invariant",
    )


def validate_branch_invariant_certificate(
    certificate: BranchInvariantCertificate,
    row: BranchInvariantDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_INVARIANT_CERTIFICATE_SCHEMA:
            return False
        if certificate.invariant_rule_id != "positive_negative_branch_invariant":
            return False
        if certificate.invariant_rule_version != "1.0" or certificate.invariant_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.target_context_id,
            certificate.invariant_id,
            certificate.static_target_action,
            certificate.invariant_target_action,
        ):
            if not _nonempty(value):
                return False
        if len(certificate.source_context_ids) != 4 or len(set(certificate.source_context_ids)) != 4:
            return False
        if not certificate.invariant_field_keys or len(set(certificate.invariant_field_keys)) != len(certificate.invariant_field_keys):
            return False
        if len(certificate.positive_action_ids) != 2 or len(certificate.negative_action_ids) != 2:
            return False
        if any(
            not _nonempty(value)
            for value in (
                *certificate.source_context_ids,
                *certificate.invariant_field_keys,
                *certificate.positive_action_ids,
                *certificate.negative_action_ids,
            )
        ):
            return False
        if certificate.source_positive_committed_count != 2 or certificate.source_negative_rejected_count != 2:
            return False
        if certificate.static_committed or not certificate.invariant_committed:
            return False
        if certificate.source_verifier_call_count != 4:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.invariant_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.invariant_reason != "positive_negative_source_receipts_define_target_invariant":
            return False
        hash_groups = (
            (certificate.source_positive_receipt_hashes, 2),
            (certificate.source_negative_receipt_hashes, 2),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.invariant_target_receipt_hashes, 1),
            (certificate.invariant_target_commit_receipt_hashes, 1),
            (certificate.source_positive_branch_selection_certificate_hashes, 2),
            (certificate.source_negative_branch_selection_certificate_hashes, 2),
        )
        for values, expected_len in hash_groups:
            if len(values) != expected_len or any(not _is_hash(value) for value in values):
                return False
        for value in (
            certificate.static_branch_selection_certificate_hash,
            certificate.invariant_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_contexts != certificate.source_context_ids or row.target_context != certificate.target_context_id:
                return False
            if row.invariant_id != certificate.invariant_id:
                return False
            if row.invariant_field_keys != certificate.invariant_field_keys:
                return False
            if row.positive_action_ids != certificate.positive_action_ids:
                return False
            if row.negative_action_ids != certificate.negative_action_ids:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.invariant_target_action != certificate.invariant_target_action:
                return False
            if row.source_positive_committed_count != certificate.source_positive_committed_count:
                return False
            if row.source_negative_rejected_count != certificate.source_negative_rejected_count:
                return False
            if row.static_committed != certificate.static_committed:
                return False
            if row.invariant_committed != certificate.invariant_committed:
                return False
            if row.source_verifier_call_count != certificate.source_verifier_call_count:
                return False
            if row.static_verifier_call_count != certificate.static_verifier_call_count:
                return False
            if row.invariant_verifier_call_count != certificate.invariant_verifier_call_count:
                return False
            if row.source_positive_receipt_hashes != certificate.source_positive_receipt_hashes:
                return False
            if row.source_negative_receipt_hashes != certificate.source_negative_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.invariant_target_receipt_hashes != certificate.invariant_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_invariant_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_invariant_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_invariant_transfer_certificate(
    report: BranchInvariantTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_invariant_certificate_hashes: tuple[str, ...],
) -> BranchInvariantTransferCertificate:
    return BranchInvariantTransferCertificate(
        schema_version=BRANCH_INVARIANT_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_invariant_certificate_hashes=branch_invariant_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_positive_success_count=report.source_positive_success_count,
        source_negative_reject_count=report.source_negative_reject_count,
        static_success_count=report.static_success_count,
        invariant_success_count=report.invariant_success_count,
        same_budget_invariant_count=report.same_budget_invariant_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_INVARIANT_CLAIM_BOUNDARY,
    )


def validate_branch_invariant_transfer_certificate(
    certificate: BranchInvariantTransferCertificate,
    report: BranchInvariantTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_INVARIANT_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_invariant_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 6:
            return False
        if len(certificate.branch_invariant_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_positive_success_count != certificate.domain_count * 2:
            return False
        if certificate.source_negative_reject_count != certificate.domain_count * 2:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.invariant_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_invariant_count != certificate.domain_count:
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
            if tuple(row.branch_invariant_certificate_hash for row in report.rows) != certificate.branch_invariant_certificate_hashes:
                return False
            if report.branch_invariant_certificate_count != len(certificate.branch_invariant_certificate_hashes):
                return False
            if not report.all_branch_invariant_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_positive_success_count != certificate.source_positive_success_count:
                return False
            if report.source_negative_reject_count != certificate.source_negative_reject_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.invariant_success_count != certificate.invariant_success_count:
                return False
            if report.same_budget_invariant_count != certificate.same_budget_invariant_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_invariant_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_invariant_certificate_hash(
    certificate: BranchInvariantCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchInvariantCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_invariant_transfer_certificate_hash(
    certificate: BranchInvariantTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchInvariantTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchInvariantTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchInvariantTransferReport,
    transfer_certificate: BranchInvariantTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_invariant_transfer_g1",
        claim_text=(
            "Positive and negative past source branch receipts can improve local target exploration by "
            "certifying an invariant proposal signature, while target commit authority remains with fresh hard verification."
        ),
        evidence_grade="G1",
        scope="branch_invariant_transfer",
        requirements=(
            requirement(
                "branch_invariant_transfer_certificate_valid",
                validate_branch_invariant_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_invariant_certificates_valid", report.all_branch_invariant_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("positive_sources_commit_all_domains", report.source_positive_success_count == report.domain_count * 2),
            requirement("negative_sources_reject_all_domains", report.source_negative_reject_count == report.domain_count * 2),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("invariants_succeed_all_domains", report.invariant_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_invariant_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 4),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_positive_success_count": report.source_positive_success_count,
            "source_negative_reject_count": report.source_negative_reject_count,
            "static_success_count": report.static_success_count,
            "invariant_success_count": report.invariant_success_count,
        },
        boundary=BRANCH_INVARIANT_CLAIM_BOUNDARY,
        sources=BRANCH_INVARIANT_SOURCES,
    )


def _make_invariant_traces(
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
            seeds=("branch-invariant-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.invariant.transfer.v1",
        )
        for action in actions
    )


def _domain_invariant_plan(
    spec: ExplorationDomainSpec,
    source_contexts: tuple[str, str, str, str],
    target_context: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        return {
            "invariant_id": "clearance_turn_safe_signature",
            "invariant_field_keys": ("clearance", "turn_rate"),
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "invariant_source_safe_detour_a",
                    "utility": 8,
                    "clearance": 0.34,
                    "turn_rate": 0.42,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "invariant_source_safe_detour_b",
                    "utility": 8,
                    "clearance": 0.38,
                    "turn_rate": 0.38,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "invariant_source_low_clearance",
                    "utility": 9,
                    "clearance": 0.12,
                    "turn_rate": 0.42,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[3],
                    "action": "invariant_source_high_turn",
                    "utility": 9,
                    "clearance": 0.34,
                    "turn_rate": 0.78,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "invariant_target_short_cut",
                "utility": 9,
                "clearance": 0.18,
                "turn_rate": 0.70,
            },
            "target_invariant": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "invariant_target_safe_detour",
                "utility": 8,
                "clearance": 0.33,
                "turn_rate": 0.41,
            },
        }
    if spec.domain_id == "molecule_repair":
        return {
            "invariant_id": "valence_strain_safe_signature",
            "invariant_field_keys": ("valence_ok", "strain"),
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "invariant_source_valence_relax_a",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.18,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "invariant_source_valence_relax_b",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.24,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "invariant_source_bad_valence",
                    "utility": 9,
                    "valence_ok": False,
                    "strain": 0.20,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[3],
                    "action": "invariant_source_high_strain",
                    "utility": 9,
                    "valence_ok": True,
                    "strain": 0.46,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "invariant_target_forced_valence",
                "utility": 9,
                "valence_ok": False,
                "strain": 0.42,
            },
            "target_invariant": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "invariant_target_valence_relax",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.20,
            },
        }
    if spec.domain_id == "material_process":
        return {
            "invariant_id": "thermal_phase_safe_signature",
            "invariant_field_keys": ("thermal_gradient", "phase_purity"),
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "action": "invariant_source_tempered_phase_a",
                    "utility": 8,
                    "thermal_gradient": 0.39,
                    "phase_purity": 0.94,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "action": "invariant_source_tempered_phase_b",
                    "utility": 8,
                    "thermal_gradient": 0.43,
                    "phase_purity": 0.92,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "action": "invariant_source_hot_phase",
                    "utility": 9,
                    "thermal_gradient": 0.78,
                    "phase_purity": 0.93,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[3],
                    "action": "invariant_source_impure_phase",
                    "utility": 9,
                    "thermal_gradient": 0.44,
                    "phase_purity": 0.86,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "invariant_target_flash_quench",
                "utility": 9,
                "thermal_gradient": 0.70,
                "phase_purity": 0.88,
            },
            "target_invariant": {
                "domain": spec.domain_id,
                "context": target_context,
                "action": "invariant_target_tempered_phase",
                "utility": 8,
                "thermal_gradient": 0.41,
                "phase_purity": 0.94,
            },
        }
    raise ValueError(f"unknown domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_invariant_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
