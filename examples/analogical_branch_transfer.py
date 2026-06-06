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
    HighestUtilityRanker,
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


ANALOGICAL_BRANCH_TRANSFER_CERTIFICATE_SCHEMA = "trwm.analogical_branch_transfer_certificate.v1"
ANALOGICAL_BRANCH_TRANSFER_CLAIM_BOUNDARY = (
    "G1 deterministic toy-domain evidence only. Explicit ancestor contexts can reorder target "
    "exploration under the same hard verifier, and misleading ancestor evidence is shown to fail "
    "closed. This is not a statistical transfer-learning, robotics, chemistry, materials, or "
    "scientific-discovery claim."
)


@dataclass(frozen=True)
class AnalogicalDomainReport:
    domain: str
    ancestor_contexts: tuple[str, ...]
    target_context: str
    misleading_context: str
    static_top_action: str
    ancestor_top_action: str
    committed_target_action: str
    misleading_top_action: str
    static_budget_committed: bool
    ancestor_budget_committed: bool
    misleading_budget_committed: bool
    misleading_transfer_blocked: bool
    source_receipt_hashes: tuple[str, ...]
    static_target_receipt_hashes: tuple[str, ...]
    ancestor_target_receipt_hashes: tuple[str, ...]
    misleading_source_receipt_hashes: tuple[str, ...]
    misleading_target_receipt_hashes: tuple[str, ...]
    source_branch_certificate_hashes: tuple[str, ...]
    static_branch_certificate_hash: str
    ancestor_branch_certificate_hash: str
    misleading_source_branch_certificate_hash: str
    misleading_target_branch_certificate_hash: str
    residual_kind: str
    next_substrate_requirement: str


@dataclass(frozen=True)
class AnalogicalBranchTransferReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[AnalogicalDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    static_budget_success_count: int
    ancestor_budget_success_count: int
    misleading_transfer_blocked_count: int
    ancestor_memory_snapshot_hash: str
    misleading_memory_snapshot_hash: str
    ancestor_memory_snapshot_valid: bool
    misleading_memory_snapshot_valid: bool
    ancestor_memory_row_count: int
    misleading_memory_row_count: int
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
class AnalogicalBranchTransferCertificate:
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
    ancestor_memory_snapshot_hash: str
    misleading_memory_snapshot_hash: str
    static_budget_success_count: int
    ancestor_budget_success_count: int
    misleading_transfer_blocked_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != ANALOGICAL_BRANCH_TRANSFER_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid analogical branch transfer certificate schema: {self.schema_version}")
        for field_name in ("domains", "receipt_hashes", "branch_selection_certificate_hashes"):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", analogical_branch_transfer_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedAnalogicalBranchTransferResult(CertifiedExampleResult):
    report: AnalogicalBranchTransferReport
    analogical_certificate: AnalogicalBranchTransferCertificate
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def run_analogical_branch_transfer_experiment() -> AnalogicalBranchTransferReport:
    return run_analogical_branch_transfer_certified_experiment().report


def run_analogical_branch_transfer_certified_experiment() -> CertifiedAnalogicalBranchTransferResult:
    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    ancestor_memory = AncestralBranchMemory()
    misleading_memory = AncestralBranchMemory()
    rows: list[AnalogicalDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        source_receipts: list[Receipt] = []
        source_certificate_hashes: list[str] = []
        ancestor_contexts = (f"{spec.domain_id}:ancestor_a", f"{spec.domain_id}:ancestor_b")
        for episode, context in enumerate(ancestor_contexts):
            source_actions = tuple(_with_context(action, context) for action in spec.actions)
            outcome = runtime.step(state, _make_traces(spec, context=context, phase="ancestor-source", episode=episode, actions=source_actions))
            state = normalize_state(outcome.state)
            certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), certificate))
            ancestor_memory.update_branch(outcome.receipts, certificate)
            source_receipts.extend(outcome.receipts)
            source_certificate_hashes.append(certificate.certificate_hash)

        target_context = f"{spec.domain_id}:target"
        target_actions = tuple(_with_context(action, target_context) for action in spec.actions)
        action_tokens = tuple(str(action["action"]) for action in target_actions)
        committed_action = spec.committed_action

        static_outcome = runtime.step(
            state,
            _make_traces(spec, context=target_context, phase="target-static-budget-one", episode=0, actions=(target_actions[0],)),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        ancestor_order = tuple(str(action) for action in ancestor_memory.rank_from_contexts(ancestor_contexts, action_tokens))
        ancestor_action = _action_by_name(target_actions, ancestor_order[0])
        ancestor_outcome = runtime.step(
            state,
            _make_traces(spec, context=target_context, phase="target-ancestor-budget-one", episode=0, actions=(ancestor_action,)),
        )
        state = normalize_state(ancestor_outcome.state)
        ancestor_certificate = build_branch_selection_certificate(
            ancestor_outcome.receipts,
            verifier_call_count=ancestor_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(ancestor_outcome.receipts), ancestor_certificate))

        misleading_context = f"{spec.domain_id}:misleading_ancestor"
        misleading_source_actions = tuple(_make_misleading_source_action(spec, action, misleading_context) for action in spec.actions)
        misleading_source_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=misleading_context,
                phase="misleading-source",
                episode=0,
                actions=misleading_source_actions,
            ),
        )
        state = normalize_state(misleading_source_outcome.state)
        misleading_source_certificate = build_branch_selection_certificate(
            misleading_source_outcome.receipts,
            verifier_call_count=misleading_source_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(misleading_source_outcome.receipts), misleading_source_certificate))
        misleading_memory.update_branch(misleading_source_outcome.receipts, misleading_source_certificate)

        misleading_order = tuple(str(action) for action in misleading_memory.rank_from_contexts((misleading_context,), action_tokens))
        misleading_action = _action_by_name(target_actions, misleading_order[0])
        misleading_target_outcome = runtime.step(
            state,
            _make_traces(
                spec,
                context=target_context,
                phase="target-misleading-budget-one",
                episode=0,
                actions=(misleading_action,),
            ),
        )
        misleading_target_certificate = build_branch_selection_certificate(
            misleading_target_outcome.receipts,
            verifier_call_count=misleading_target_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(misleading_target_outcome.receipts), misleading_target_certificate))

        rows.append(
            AnalogicalDomainReport(
                domain=spec.domain_id,
                ancestor_contexts=ancestor_contexts,
                target_context=target_context,
                misleading_context=misleading_context,
                static_top_action=action_tokens[0],
                ancestor_top_action=ancestor_order[0],
                committed_target_action=committed_action,
                misleading_top_action=misleading_order[0],
                static_budget_committed=static_outcome.committed,
                ancestor_budget_committed=ancestor_outcome.committed,
                misleading_budget_committed=misleading_target_outcome.committed,
                misleading_transfer_blocked=not misleading_target_outcome.committed,
                source_receipt_hashes=tuple(receipt.receipt_hash for receipt in source_receipts),
                static_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
                ancestor_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in ancestor_outcome.receipts),
                misleading_source_receipt_hashes=tuple(receipt.receipt_hash for receipt in misleading_source_outcome.receipts),
                misleading_target_receipt_hashes=tuple(receipt.receipt_hash for receipt in misleading_target_outcome.receipts),
                source_branch_certificate_hashes=tuple(source_certificate_hashes),
                static_branch_certificate_hash=static_certificate.certificate_hash,
                ancestor_branch_certificate_hash=ancestor_certificate.certificate_hash,
                misleading_source_branch_certificate_hash=misleading_source_certificate.certificate_hash,
                misleading_target_branch_certificate_hash=misleading_target_certificate.certificate_hash,
                residual_kind=spec.residual_kind,
                next_substrate_requirement="certified context-neighborhood selection before ancestor reuse",
            )
        )

    ancestor_snapshot = ancestor_memory.snapshot()
    misleading_snapshot = misleading_memory.snapshot()
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
    all_branch_certificates_valid = all(
        validate_branch_selection_certificate(certificate) for _, certificate in branch_certificate_pairs
    )
    all_branch_audits_valid = all(
        audit_branch_selection(receipts, certificate) for receipts, certificate in branch_certificate_pairs
    )
    report = AnalogicalBranchTransferReport(
        schema_version="trwm.example.analogical_branch_transfer.v1",
        experiment_id="analogical_branch_transfer",
        evidence_grade="G1",
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        static_budget_success_count=sum(1 for row in rows if row.static_budget_committed),
        ancestor_budget_success_count=sum(1 for row in rows if row.ancestor_budget_committed),
        misleading_transfer_blocked_count=sum(1 for row in rows if row.misleading_transfer_blocked),
        ancestor_memory_snapshot_hash=ancestor_snapshot.snapshot_hash,
        misleading_memory_snapshot_hash=misleading_snapshot.snapshot_hash,
        ancestor_memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(ancestor_snapshot),
        misleading_memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(misleading_snapshot),
        ancestor_memory_row_count=len(ancestor_snapshot.rows),
        misleading_memory_row_count=len(misleading_snapshot.rows),
        all_branch_selection_certificates_valid=all_branch_certificates_valid,
        all_branch_selection_audits_valid=all_branch_audits_valid,
        replay_audit_ok=replay_audit_ok,
        rollback_audit_ok=rollback_audit_ok,
        ledger_audit_ok=ledger_audit_ok,
        invalid_commit_count=engine.invalid_commit_count,
        verifier_id=engine.adapter.verifier_id,
        verifier_version=engine.adapter.verifier_version,
        ledger_head=engine.ledger.head,
        hard_gate_keys=("clearance", "turn_rate", "valence_ok", "strain", "thermal_gradient", "phase_purity"),
        residual_kinds=tuple(sorted({spec.residual_kind for spec in DOMAIN_SPECS})),
        sources=ANCESTRAL_BRANCH_SOURCES,
        learning=(
            "Explicit ancestor contexts can improve target exploration under scarce verifier budget, "
            "but misleading ancestor contexts remain proposal evidence only: the target hard verifier "
            "blocks their unsafe first choice."
        ),
    )
    analogical_certificate = build_analogical_branch_transfer_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="cross_context_analogical_branch_transfer",
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
        claim_boundary=ANALOGICAL_BRANCH_TRANSFER_CLAIM_BOUNDARY,
        sources=ANCESTRAL_BRANCH_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, analogical_certificate, evidence_certificate)
    return CertifiedAnalogicalBranchTransferResult(
        report=report,
        analogical_certificate=analogical_certificate,
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_analogical_branch_transfer_certificate(
    report: AnalogicalBranchTransferReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
) -> AnalogicalBranchTransferCertificate:
    return AnalogicalBranchTransferCertificate(
        schema_version=ANALOGICAL_BRANCH_TRANSFER_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        ancestor_memory_snapshot_hash=report.ancestor_memory_snapshot_hash,
        misleading_memory_snapshot_hash=report.misleading_memory_snapshot_hash,
        static_budget_success_count=report.static_budget_success_count,
        ancestor_budget_success_count=report.ancestor_budget_success_count,
        misleading_transfer_blocked_count=report.misleading_transfer_blocked_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        claim_boundary=ANALOGICAL_BRANCH_TRANSFER_CLAIM_BOUNDARY,
    )


def validate_analogical_branch_transfer_certificate(
    certificate: AnalogicalBranchTransferCertificate,
    report: AnalogicalBranchTransferReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != ANALOGICAL_BRANCH_TRANSFER_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if certificate.domain_count <= 0 or certificate.domain_count != len(certificate.domains):
            return False
        for value in (
            certificate.report_hash,
            certificate.ledger_head,
            certificate.ancestor_memory_snapshot_hash,
            certificate.misleading_memory_snapshot_hash,
        ):
            if not _is_hash(value):
                return False
        if any(not _is_hash(value) for value in certificate.receipt_hashes):
            return False
        if any(not _is_hash(value) for value in certificate.branch_selection_certificate_hashes):
            return False
        if not certificate.receipt_hashes or not certificate.branch_selection_certificate_hashes:
            return False
        if certificate.static_budget_success_count != 0:
            return False
        if certificate.ancestor_budget_success_count != certificate.domain_count:
            return False
        if certificate.misleading_transfer_blocked_count != certificate.domain_count:
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
            if report.ancestor_memory_snapshot_hash != certificate.ancestor_memory_snapshot_hash:
                return False
            if report.misleading_memory_snapshot_hash != certificate.misleading_memory_snapshot_hash:
                return False
            if not (report.ancestor_memory_snapshot_valid and report.misleading_memory_snapshot_valid):
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
        return certificate.certificate_hash == analogical_branch_transfer_certificate_hash(certificate)
    except Exception:
        return False


def analogical_branch_transfer_certificate_hash(
    certificate: AnalogicalBranchTransferCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, AnalogicalBranchTransferCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def result_as_dict(result: CertifiedAnalogicalBranchTransferResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: AnalogicalBranchTransferReport,
    analogical_certificate: AnalogicalBranchTransferCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="analogical_branch_transfer_g1",
        claim_text=(
            "Explicit ancestor branch contexts can improve target exploration across three toy "
            "domains, while misleading ancestor evidence is blocked by target hard verification."
        ),
        evidence_grade="G1",
        scope="analogical_branch_transfer",
        requirements=(
            requirement(
                "analogical_certificate_valid",
                validate_analogical_branch_transfer_certificate(analogical_certificate, report),
                certificate_hash=analogical_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement("ancestor_memory_valid", report.ancestor_memory_snapshot_valid),
            requirement("misleading_memory_valid", report.misleading_memory_snapshot_valid),
            requirement("static_budget_fails_all_domains", report.static_budget_success_count == 0),
            requirement("ancestor_budget_succeeds_all_domains", report.ancestor_budget_success_count == report.domain_count),
            requirement(
                "misleading_transfer_blocked_all_domains",
                report.misleading_transfer_blocked_count == report.domain_count,
            ),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "static_budget_success_count": report.static_budget_success_count,
            "ancestor_budget_success_count": report.ancestor_budget_success_count,
            "misleading_transfer_blocked_count": report.misleading_transfer_blocked_count,
        },
        boundary=ANALOGICAL_BRANCH_TRANSFER_CLAIM_BOUNDARY,
        sources=ANCESTRAL_BRANCH_SOURCES,
    )


def _make_traces(
    spec: ExplorationDomainSpec,
    *,
    context: str,
    phase: str,
    episode: int,
    actions: Iterable[Mapping[str, Any]],
) -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"{context}:{phase}:{episode}:{action['action']}",
            actions=(dict(action),),
            seeds=("analogical-branch-transfer", spec.domain_id, context, phase, episode, action["action"]),
            model_version="analogical.branch.transfer.v1",
        )
        for action in actions
    )


def _with_context(action: Mapping[str, Any], context: str) -> dict[str, Any]:
    return {**dict(action), "context": context}


def _action_by_name(actions: Iterable[Mapping[str, Any]], action_name: str) -> Mapping[str, Any]:
    for action in actions:
        if str(action["action"]) == action_name:
            return action
    raise ValueError(f"unknown action {action_name!r}")


def _make_misleading_source_action(
    spec: ExplorationDomainSpec,
    action: Mapping[str, Any],
    context: str,
) -> dict[str, Any]:
    row = _with_context(action, context)
    first_action = str(spec.actions[0]["action"])
    if str(row["action"]) != first_action:
        return row
    if spec.domain_id == "robotics_replan":
        row.update({"clearance": 0.35, "turn_rate": 0.30})
    elif spec.domain_id == "molecule_repair":
        row.update({"valence_ok": True, "strain": 0.10})
    elif spec.domain_id == "material_process":
        row.update({"thermal_gradient": 0.30, "phase_purity": 0.95})
    else:
        raise ValueError(f"unknown domain: {spec.domain_id}")
    row["utility"] = 10
    return row


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def main() -> None:
    print(json.dumps(result_as_dict(run_analogical_branch_transfer_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
