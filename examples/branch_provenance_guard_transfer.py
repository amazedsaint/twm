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


BRANCH_PROVENANCE_GUARD_CERTIFICATE_SCHEMA = "trwm.branch_provenance_guard_certificate.v1"
BRANCH_PROVENANCE_GUARD_TRANSFER_CERTIFICATE_SCHEMA = "trwm.branch_provenance_guard_transfer_certificate.v1"
BRANCH_PROVENANCE_GUARD_SOURCES = (
    *ANCESTRAL_BRANCH_SOURCES,
    "https://doi.org/10.1145/357172.357176",
)
BRANCH_PROVENANCE_GUARD_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. The example shows source-valid branch receipts can be "
    "quarantined from target proposal priority when their provenance id is not allowed for the target, "
    "while a trusted source branch still needs fresh target hard verification. It is not a Byzantine "
    "fault-tolerant protocol, consensus algorithm, security proof, robotics safety, chemistry, materials "
    "discovery, or scientific autonomy evidence."
)


@dataclass(frozen=True)
class BranchProvenanceGuardCertificate:
    schema_version: str
    domain: str
    provenance_rule_id: str
    provenance_rule_version: str
    source_context_ids: tuple[str, ...]
    target_context_id: str
    trusted_source_ids: tuple[str, ...]
    quarantined_source_id: str
    allowed_source_ids: tuple[str, ...]
    trusted_actions: tuple[str, ...]
    quarantined_action: str
    static_target_action: str
    guarded_target_action: str
    source_trusted_receipt_hashes: tuple[str, ...]
    source_quarantined_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    guarded_target_receipt_hashes: tuple[str, ...]
    guarded_target_commit_receipt_hashes: tuple[str, ...]
    source_trusted_branch_selection_certificate_hashes: tuple[str, ...]
    source_quarantined_branch_selection_certificate_hash: str
    static_branch_selection_certificate_hash: str
    guarded_branch_selection_certificate_hash: str
    source_trusted_committed_count: int
    source_quarantined_committed_count: int
    static_committed: bool
    guarded_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    guarded_verifier_call_count: int
    same_budget: bool
    quarantine_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PROVENANCE_GUARD_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch provenance guard certificate schema: {self.schema_version}")
        for field_name in (
            "source_context_ids",
            "trusted_source_ids",
            "allowed_source_ids",
            "trusted_actions",
            "source_trusted_receipt_hashes",
            "source_quarantined_receipt_hashes",
            "static_target_receipt_hashes",
            "guarded_target_receipt_hashes",
            "guarded_target_commit_receipt_hashes",
            "source_trusted_branch_selection_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_provenance_guard_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class BranchProvenanceGuardDomainReport:
    domain: str
    source_contexts: tuple[str, ...]
    target_context: str
    trusted_source_ids: tuple[str, ...]
    quarantined_source_id: str
    allowed_source_ids: tuple[str, ...]
    trusted_actions: tuple[str, ...]
    quarantined_action: str
    static_target_action: str
    guarded_target_action: str
    source_trusted_committed_count: int
    source_quarantined_committed_count: int
    static_committed: bool
    guarded_committed: bool
    source_verifier_call_count: int
    static_verifier_call_count: int
    guarded_verifier_call_count: int
    source_trusted_receipt_hashes: tuple[str, ...]
    source_quarantined_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    guarded_target_receipt_hashes: tuple[str, ...]
    branch_provenance_guard_certificate_hash: str
    same_budget: bool


@dataclass(frozen=True)
class BranchProvenanceGuardTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[BranchProvenanceGuardDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    source_trusted_success_count: int
    source_quarantined_success_count: int
    static_success_count: int
    guarded_success_count: int
    same_budget_guard_count: int
    branch_provenance_guard_certificate_count: int
    memory_snapshot_hash: str
    memory_snapshot_valid: bool
    memory_row_count: int
    memory_receipt_count: int
    all_branch_provenance_guard_certificates_valid: bool
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
class BranchProvenanceGuardTransferCertificate:
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
    branch_provenance_guard_certificate_hashes: tuple[str, ...]
    memory_snapshot_hash: str
    source_trusted_success_count: int
    source_quarantined_success_count: int
    static_success_count: int
    guarded_success_count: int
    same_budget_guard_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_PROVENANCE_GUARD_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch provenance guard transfer certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "branch_provenance_guard_certificate_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_provenance_guard_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedBranchProvenanceGuardTransferResult(CertifiedExampleResult):
    report: BranchProvenanceGuardTransferReport
    branch_provenance_guard_transfer_certificate: BranchProvenanceGuardTransferCertificate
    branch_provenance_guard_certificates: tuple[BranchProvenanceGuardCertificate, ...]
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_branch_provenance_guard_transfer_experiment() -> BranchProvenanceGuardTransferReport:
    return run_branch_provenance_guard_transfer_certified_experiment().report


def run_branch_provenance_guard_transfer_certified_experiment() -> CertifiedBranchProvenanceGuardTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector())
    memory = AncestralBranchMemory()
    rows: list[BranchProvenanceGuardDomainReport] = []
    provenance_certificates: list[BranchProvenanceGuardCertificate] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_contexts = (
            f"{spec.domain_id}:source:provenance:trusted_a",
            f"{spec.domain_id}:source:provenance:trusted_b",
            f"{spec.domain_id}:source:provenance:quarantined",
        )
        target_context = f"{spec.domain_id}:target:provenance_guard"
        plan = _domain_provenance_guard_plan(spec, source_contexts, target_context)

        source_outcomes = []
        source_certificates = []
        for source_context, source_action in zip(source_contexts, plan["source_actions"]):
            outcome = runtime.step(
                state,
                _make_provenance_guard_traces(
                    spec,
                    context=source_context,
                    phase="source-provenance",
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
            _make_provenance_guard_traces(
                spec,
                context=target_context,
                phase="target-static-quarantined",
                actions=(plan["target_static"],),
            ),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        guarded_outcome = runtime.step(
            state,
            _make_provenance_guard_traces(
                spec,
                context=target_context,
                phase="target-provenance-guarded",
                actions=(plan["target_guarded"],),
            ),
        )
        state = normalize_state(guarded_outcome.state)
        guarded_certificate = build_branch_selection_certificate(
            guarded_outcome.receipts,
            verifier_call_count=guarded_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(guarded_outcome.receipts), guarded_certificate))

        trusted_outcomes = tuple(source_outcomes[:2])
        quarantined_outcomes = tuple(source_outcomes[2:])
        trusted_certificates = tuple(source_certificates[:2])
        quarantined_certificate = source_certificates[2]
        certificate = build_branch_provenance_guard_certificate(
            spec,
            source_context_ids=source_contexts,
            target_context_id=target_context,
            trusted_source_ids=tuple(str(source_id) for source_id in plan["trusted_source_ids"]),
            quarantined_source_id=str(plan["quarantined_source_id"]),
            trusted_actions=tuple(str(action["action"]) for action in plan["source_actions"][:2]),
            quarantined_action=str(plan["source_actions"][2]["action"]),
            static_target_action=str(plan["target_static"]["action"]),
            guarded_target_action=str(plan["target_guarded"]["action"]),
            source_trusted_receipt_hashes=tuple(
                receipt.receipt_hash
                for outcome in trusted_outcomes
                for receipt in outcome.receipts
                if receipt.committed
            ),
            source_quarantined_receipt_hashes=tuple(
                receipt.receipt_hash
                for outcome in quarantined_outcomes
                for receipt in outcome.receipts
                if receipt.committed
            ),
            static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
            guarded_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in guarded_outcome.receipts),
            guarded_target_commit_receipt_hashes=tuple(
                receipt.receipt_hash for receipt in guarded_outcome.receipts if receipt.committed
            ),
            source_trusted_branch_selection_certificate_hashes=tuple(
                selection.certificate_hash for selection in trusted_certificates
            ),
            source_quarantined_branch_selection_certificate_hash=quarantined_certificate.certificate_hash,
            static_branch_selection_certificate_hash=static_certificate.certificate_hash,
            guarded_branch_selection_certificate_hash=guarded_certificate.certificate_hash,
            source_trusted_committed_count=sum(1 for outcome in trusted_outcomes if outcome.committed),
            source_quarantined_committed_count=sum(1 for outcome in quarantined_outcomes if outcome.committed),
            static_committed=static_outcome.committed,
            guarded_committed=guarded_outcome.committed,
            source_verifier_call_count=sum(outcome.verifier_calls for outcome in source_outcomes),
            static_verifier_call_count=static_outcome.verifier_calls,
            guarded_verifier_call_count=guarded_outcome.verifier_calls,
        )
        provenance_certificates.append(certificate)
        rows.append(
            BranchProvenanceGuardDomainReport(
                domain=spec.domain_id,
                source_contexts=certificate.source_context_ids,
                target_context=certificate.target_context_id,
                trusted_source_ids=certificate.trusted_source_ids,
                quarantined_source_id=certificate.quarantined_source_id,
                allowed_source_ids=certificate.allowed_source_ids,
                trusted_actions=certificate.trusted_actions,
                quarantined_action=certificate.quarantined_action,
                static_target_action=certificate.static_target_action,
                guarded_target_action=certificate.guarded_target_action,
                source_trusted_committed_count=certificate.source_trusted_committed_count,
                source_quarantined_committed_count=certificate.source_quarantined_committed_count,
                static_committed=certificate.static_committed,
                guarded_committed=certificate.guarded_committed,
                source_verifier_call_count=certificate.source_verifier_call_count,
                static_verifier_call_count=certificate.static_verifier_call_count,
                guarded_verifier_call_count=certificate.guarded_verifier_call_count,
                source_trusted_receipt_hashes=certificate.source_trusted_receipt_hashes,
                source_quarantined_receipt_hashes=certificate.source_quarantined_receipt_hashes,
                static_target_receipt_hashes=certificate.static_target_receipt_hashes,
                guarded_target_receipt_hashes=certificate.guarded_target_receipt_hashes,
                branch_provenance_guard_certificate_hash=certificate.certificate_hash,
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

    report = BranchProvenanceGuardTransferReport(
        schema_version="trwm.example.branch_provenance_guard_transfer.v1",
        experiment_id="branch_provenance_guard_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        source_trusted_success_count=sum(row.source_trusted_committed_count for row in rows),
        source_quarantined_success_count=sum(row.source_quarantined_committed_count for row in rows),
        static_success_count=sum(1 for row in rows if row.static_committed),
        guarded_success_count=sum(1 for row in rows if row.guarded_committed),
        same_budget_guard_count=sum(1 for row in rows if row.same_budget),
        branch_provenance_guard_certificate_count=len(provenance_certificates),
        memory_snapshot_hash=memory_snapshot.snapshot_hash,
        memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        memory_row_count=len(memory_snapshot.rows),
        memory_receipt_count=len(memory_snapshot.receipt_hashes),
        all_branch_provenance_guard_certificates_valid=all(
            validate_branch_provenance_guard_certificate(certificate, row)
            for certificate, row in zip(provenance_certificates, rows)
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
        sources=BRANCH_PROVENANCE_GUARD_SOURCES,
        learning=(
            "Provenance-guarded branch reuse separates source validity from target admissibility. A "
            "source-valid branch from a quarantined provenance id can remain in the ledger without being "
            "allowed to rank the target proposal list; the trusted target proposal still needs fresh hard "
            "verification before commit."
        ),
    )
    transfer_certificate = build_branch_provenance_guard_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        branch_provenance_guard_certificate_hashes=tuple(
            certificate.certificate_hash for certificate in provenance_certificates
        ),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="branch_provenance_guard_transfer",
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
        claim_boundary=BRANCH_PROVENANCE_GUARD_CLAIM_BOUNDARY,
        sources=BRANCH_PROVENANCE_GUARD_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, transfer_certificate, evidence_certificate)
    return CertifiedBranchProvenanceGuardTransferResult(
        report=report,
        branch_provenance_guard_transfer_certificate=transfer_certificate,
        branch_provenance_guard_certificates=tuple(provenance_certificates),
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_branch_provenance_guard_certificate(
    spec: ExplorationDomainSpec,
    *,
    source_context_ids: tuple[str, ...],
    target_context_id: str,
    trusted_source_ids: tuple[str, ...],
    quarantined_source_id: str,
    trusted_actions: tuple[str, ...],
    quarantined_action: str,
    static_target_action: str,
    guarded_target_action: str,
    source_trusted_receipt_hashes: tuple[str, ...],
    source_quarantined_receipt_hashes: tuple[str, ...],
    static_target_receipt_hashes: tuple[str, ...],
    guarded_target_receipt_hashes: tuple[str, ...],
    guarded_target_commit_receipt_hashes: tuple[str, ...],
    source_trusted_branch_selection_certificate_hashes: tuple[str, ...],
    source_quarantined_branch_selection_certificate_hash: str,
    static_branch_selection_certificate_hash: str,
    guarded_branch_selection_certificate_hash: str,
    source_trusted_committed_count: int,
    source_quarantined_committed_count: int,
    static_committed: bool,
    guarded_committed: bool,
    source_verifier_call_count: int,
    static_verifier_call_count: int,
    guarded_verifier_call_count: int,
) -> BranchProvenanceGuardCertificate:
    return BranchProvenanceGuardCertificate(
        schema_version=BRANCH_PROVENANCE_GUARD_CERTIFICATE_SCHEMA,
        domain=spec.domain_id,
        provenance_rule_id="target_allowed_source_id_guard",
        provenance_rule_version="1.0",
        source_context_ids=source_context_ids,
        target_context_id=target_context_id,
        trusted_source_ids=trusted_source_ids,
        quarantined_source_id=quarantined_source_id,
        allowed_source_ids=trusted_source_ids,
        trusted_actions=trusted_actions,
        quarantined_action=quarantined_action,
        static_target_action=static_target_action,
        guarded_target_action=guarded_target_action,
        source_trusted_receipt_hashes=source_trusted_receipt_hashes,
        source_quarantined_receipt_hashes=source_quarantined_receipt_hashes,
        static_target_receipt_hashes=static_target_receipt_hashes,
        guarded_target_receipt_hashes=guarded_target_receipt_hashes,
        guarded_target_commit_receipt_hashes=guarded_target_commit_receipt_hashes,
        source_trusted_branch_selection_certificate_hashes=source_trusted_branch_selection_certificate_hashes,
        source_quarantined_branch_selection_certificate_hash=source_quarantined_branch_selection_certificate_hash,
        static_branch_selection_certificate_hash=static_branch_selection_certificate_hash,
        guarded_branch_selection_certificate_hash=guarded_branch_selection_certificate_hash,
        source_trusted_committed_count=source_trusted_committed_count,
        source_quarantined_committed_count=source_quarantined_committed_count,
        static_committed=static_committed,
        guarded_committed=guarded_committed,
        source_verifier_call_count=source_verifier_call_count,
        static_verifier_call_count=static_verifier_call_count,
        guarded_verifier_call_count=guarded_verifier_call_count,
        same_budget=static_verifier_call_count == guarded_verifier_call_count == 1,
        quarantine_reason="source_provenance_not_allowed_for_target_context",
    )


def validate_branch_provenance_guard_certificate(
    certificate: BranchProvenanceGuardCertificate,
    row: BranchProvenanceGuardDomainReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PROVENANCE_GUARD_CERTIFICATE_SCHEMA:
            return False
        if certificate.provenance_rule_id != "target_allowed_source_id_guard":
            return False
        if certificate.provenance_rule_version != "1.0":
            return False
        for value in (
            certificate.domain,
            certificate.target_context_id,
            certificate.quarantined_source_id,
            certificate.quarantined_action,
            certificate.static_target_action,
            certificate.guarded_target_action,
        ):
            if not _nonempty(value):
                return False
        if len(certificate.source_context_ids) != 3 or len(set(certificate.source_context_ids)) != 3:
            return False
        if len(certificate.trusted_source_ids) != 2 or len(set(certificate.trusted_source_ids)) != 2:
            return False
        if certificate.allowed_source_ids != certificate.trusted_source_ids:
            return False
        if certificate.quarantined_source_id in certificate.allowed_source_ids:
            return False
        if len(certificate.trusted_actions) != 2 or len(set(certificate.trusted_actions)) != 2:
            return False
        if certificate.quarantined_action in certificate.trusted_actions:
            return False
        if certificate.static_target_action == certificate.guarded_target_action:
            return False
        if certificate.source_trusted_committed_count != 2 or certificate.source_quarantined_committed_count != 1:
            return False
        if certificate.static_committed or not certificate.guarded_committed:
            return False
        if certificate.source_verifier_call_count != 3:
            return False
        if certificate.static_verifier_call_count != 1 or certificate.guarded_verifier_call_count != 1:
            return False
        if not certificate.same_budget:
            return False
        if certificate.quarantine_reason != "source_provenance_not_allowed_for_target_context":
            return False
        hash_groups = (
            (certificate.source_trusted_receipt_hashes, 2),
            (certificate.source_quarantined_receipt_hashes, 1),
            (certificate.static_target_receipt_hashes, 1),
            (certificate.guarded_target_receipt_hashes, 1),
            (certificate.guarded_target_commit_receipt_hashes, 1),
            (certificate.source_trusted_branch_selection_certificate_hashes, 2),
        )
        for hashes, expected_len in hash_groups:
            if len(hashes) != expected_len or any(not _is_hash(value) for value in hashes):
                return False
        for value in (
            certificate.source_quarantined_branch_selection_certificate_hash,
            certificate.static_branch_selection_certificate_hash,
            certificate.guarded_branch_selection_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if row is not None:
            if row.domain != certificate.domain:
                return False
            if row.source_contexts != certificate.source_context_ids or row.target_context != certificate.target_context_id:
                return False
            if row.trusted_source_ids != certificate.trusted_source_ids:
                return False
            if row.quarantined_source_id != certificate.quarantined_source_id:
                return False
            if row.allowed_source_ids != certificate.allowed_source_ids:
                return False
            if row.trusted_actions != certificate.trusted_actions:
                return False
            if row.quarantined_action != certificate.quarantined_action:
                return False
            if row.static_target_action != certificate.static_target_action:
                return False
            if row.guarded_target_action != certificate.guarded_target_action:
                return False
            if row.source_trusted_receipt_hashes != certificate.source_trusted_receipt_hashes:
                return False
            if row.source_quarantined_receipt_hashes != certificate.source_quarantined_receipt_hashes:
                return False
            if row.static_target_receipt_hashes != certificate.static_target_receipt_hashes:
                return False
            if row.guarded_target_receipt_hashes != certificate.guarded_target_receipt_hashes:
                return False
            if row.same_budget != certificate.same_budget:
                return False
            if row.branch_provenance_guard_certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == branch_provenance_guard_certificate_hash(certificate)
    except Exception:
        return False


def build_branch_provenance_guard_transfer_certificate(
    report: BranchProvenanceGuardTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    branch_provenance_guard_certificate_hashes: tuple[str, ...],
) -> BranchProvenanceGuardTransferCertificate:
    return BranchProvenanceGuardTransferCertificate(
        schema_version=BRANCH_PROVENANCE_GUARD_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        branch_provenance_guard_certificate_hashes=branch_provenance_guard_certificate_hashes,
        memory_snapshot_hash=report.memory_snapshot_hash,
        source_trusted_success_count=report.source_trusted_success_count,
        source_quarantined_success_count=report.source_quarantined_success_count,
        static_success_count=report.static_success_count,
        guarded_success_count=report.guarded_success_count,
        same_budget_guard_count=report.same_budget_guard_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=BRANCH_PROVENANCE_GUARD_CLAIM_BOUNDARY,
    )


def validate_branch_provenance_guard_transfer_certificate(
    certificate: BranchProvenanceGuardTransferCertificate,
    report: BranchProvenanceGuardTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != BRANCH_PROVENANCE_GUARD_TRANSFER_CERTIFICATE_SCHEMA:
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
            certificate.branch_provenance_guard_certificate_hashes,
        ):
            if not values or any(not _is_hash(value) for value in values):
                return False
        if len(certificate.receipt_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_selection_certificate_hashes) != certificate.domain_count * 5:
            return False
        if len(certificate.branch_provenance_guard_certificate_hashes) != certificate.domain_count:
            return False
        if certificate.source_trusted_success_count != certificate.domain_count * 2:
            return False
        if certificate.source_quarantined_success_count != certificate.domain_count:
            return False
        if certificate.static_success_count != 0:
            return False
        if certificate.guarded_success_count != certificate.domain_count:
            return False
        if certificate.same_budget_guard_count != certificate.domain_count:
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
            if tuple(row.branch_provenance_guard_certificate_hash for row in report.rows) != certificate.branch_provenance_guard_certificate_hashes:
                return False
            if report.branch_provenance_guard_certificate_count != len(certificate.branch_provenance_guard_certificate_hashes):
                return False
            if not report.all_branch_provenance_guard_certificates_valid:
                return False
            if not report.all_branch_selection_certificates_valid or not report.all_branch_selection_audits_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.total_receipt_count != len(certificate.receipt_hashes):
                return False
            if report.source_trusted_success_count != certificate.source_trusted_success_count:
                return False
            if report.source_quarantined_success_count != certificate.source_quarantined_success_count:
                return False
            if report.static_success_count != certificate.static_success_count:
                return False
            if report.guarded_success_count != certificate.guarded_success_count:
                return False
            if report.same_budget_guard_count != certificate.same_budget_guard_count:
                return False
            if report.replay_audit_ok != certificate.replay_audit_ok:
                return False
            if report.rollback_audit_ok != certificate.rollback_audit_ok:
                return False
            if report.ledger_audit_ok != certificate.ledger_audit_ok:
                return False
            if report.invalid_commit_count != certificate.invalid_commit_count:
                return False
        return certificate.certificate_hash == branch_provenance_guard_transfer_certificate_hash(certificate)
    except Exception:
        return False


def branch_provenance_guard_certificate_hash(
    certificate: BranchProvenanceGuardCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchProvenanceGuardCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def branch_provenance_guard_transfer_certificate_hash(
    certificate: BranchProvenanceGuardTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, BranchProvenanceGuardTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedBranchProvenanceGuardTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: BranchProvenanceGuardTransferReport,
    transfer_certificate: BranchProvenanceGuardTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="branch_provenance_guard_transfer_g1",
        claim_text=(
            "Receipt-bound source provenance can improve local target exploration by quarantining "
            "source-valid but target-untrusted branch evidence under matched one-call verifier budgets."
        ),
        evidence_grade="G1",
        scope="branch_provenance_guard_transfer",
        requirements=(
            requirement(
                "branch_provenance_guard_transfer_certificate_valid",
                validate_branch_provenance_guard_transfer_certificate(transfer_certificate, report),
                certificate_hash=transfer_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("all_branch_provenance_guard_certificates_valid", report.all_branch_provenance_guard_certificates_valid),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("trusted_sources_commit_all_domains", report.source_trusted_success_count == report.domain_count * 2),
            requirement("quarantined_sources_bound_all_domains", report.source_quarantined_success_count == report.domain_count),
            requirement("static_fails_all_domains", report.static_success_count == 0),
            requirement("guarded_succeeds_all_domains", report.guarded_success_count == report.domain_count),
            requirement("same_budget_all_domains", report.same_budget_guard_count == report.domain_count),
            requirement("memory_snapshot_bound", report.memory_snapshot_valid and report.memory_receipt_count == report.domain_count * 3),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "source_trusted_success_count": report.source_trusted_success_count,
            "source_quarantined_success_count": report.source_quarantined_success_count,
            "static_success_count": report.static_success_count,
            "guarded_success_count": report.guarded_success_count,
        },
        boundary=BRANCH_PROVENANCE_GUARD_CLAIM_BOUNDARY,
        sources=BRANCH_PROVENANCE_GUARD_SOURCES,
    )


def _make_provenance_guard_traces(
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
            seeds=("branch-provenance-guard-transfer", spec.domain_id, context, phase, action["action"]),
            model_version="branch.provenance_guard.transfer.v1",
        )
        for action in actions
    )


def _domain_provenance_guard_plan(
    spec: ExplorationDomainSpec,
    source_contexts: tuple[str, str, str],
    target_context: str,
) -> Mapping[str, Any]:
    if spec.domain_id == "robotics_replan":
        trusted_source_ids = ("audited_map_lab", "field_replay_lab")
        quarantined_source_id = "untrusted_fast_planner"
        return {
            "trusted_source_ids": trusted_source_ids,
            "quarantined_source_id": quarantined_source_id,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "source_id": trusted_source_ids[0],
                    "action": "provenance_source_detour_a",
                    "utility": 8,
                    "clearance": 0.34,
                    "turn_rate": 0.42,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "source_id": trusted_source_ids[1],
                    "action": "provenance_source_detour_b",
                    "utility": 8,
                    "clearance": 0.35,
                    "turn_rate": 0.39,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "source_id": quarantined_source_id,
                    "action": "provenance_source_aggressive_arc",
                    "utility": 9,
                    "clearance": 0.26,
                    "turn_rate": 0.58,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "source_id": quarantined_source_id,
                "action": "provenance_target_aggressive_arc",
                "utility": 9,
                "clearance": 0.14,
                "turn_rate": 0.78,
            },
            "target_guarded": {
                "domain": spec.domain_id,
                "context": target_context,
                "source_id": trusted_source_ids[0],
                "action": "provenance_target_verified_detour",
                "utility": 8,
                "clearance": 0.33,
                "turn_rate": 0.41,
            },
        }
    if spec.domain_id == "molecule_repair":
        trusted_source_ids = ("audited_graph_lab", "validated_synthesis_log")
        quarantined_source_id = "untrusted_graph_generator"
        return {
            "trusted_source_ids": trusted_source_ids,
            "quarantined_source_id": quarantined_source_id,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "source_id": trusted_source_ids[0],
                    "action": "provenance_source_relaxed_bridge_a",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.16,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "source_id": trusted_source_ids[1],
                    "action": "provenance_source_relaxed_bridge_b",
                    "utility": 8,
                    "valence_ok": True,
                    "strain": 0.18,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "source_id": quarantined_source_id,
                    "action": "provenance_source_compact_patch",
                    "utility": 9,
                    "valence_ok": True,
                    "strain": 0.34,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "source_id": quarantined_source_id,
                "action": "provenance_target_compact_patch",
                "utility": 9,
                "valence_ok": True,
                "strain": 0.52,
            },
            "target_guarded": {
                "domain": spec.domain_id,
                "context": target_context,
                "source_id": trusted_source_ids[0],
                "action": "provenance_target_relaxed_bridge",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.15,
            },
        }
    if spec.domain_id == "material_process":
        trusted_source_ids = ("audited_furnace_log", "validated_phase_scan")
        quarantined_source_id = "untrusted_rapid_screen"
        return {
            "trusted_source_ids": trusted_source_ids,
            "quarantined_source_id": quarantined_source_id,
            "source_actions": (
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[0],
                    "source_id": trusted_source_ids[0],
                    "action": "provenance_source_staged_anneal_a",
                    "utility": 8,
                    "thermal_gradient": 0.38,
                    "phase_purity": 0.95,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[1],
                    "source_id": trusted_source_ids[1],
                    "action": "provenance_source_staged_anneal_b",
                    "utility": 8,
                    "thermal_gradient": 0.40,
                    "phase_purity": 0.94,
                },
                {
                    "domain": spec.domain_id,
                    "context": source_contexts[2],
                    "source_id": quarantined_source_id,
                    "action": "provenance_source_edge_quench",
                    "utility": 9,
                    "thermal_gradient": 0.49,
                    "phase_purity": 0.91,
                },
            ),
            "target_static": {
                "domain": spec.domain_id,
                "context": target_context,
                "source_id": quarantined_source_id,
                "action": "provenance_target_edge_quench",
                "utility": 9,
                "thermal_gradient": 0.70,
                "phase_purity": 0.86,
            },
            "target_guarded": {
                "domain": spec.domain_id,
                "context": target_context,
                "source_id": trusted_source_ids[0],
                "action": "provenance_target_staged_anneal",
                "utility": 8,
                "thermal_gradient": 0.39,
                "phase_purity": 0.95,
            },
        }
    raise ValueError(f"unknown provenance-guard domain: {spec.domain_id}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_branch_provenance_guard_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
