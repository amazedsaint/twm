from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Iterable, Mapping

from examples.common import (
    CertifiedExampleResult,
    ExampleEvidenceCertificate,
    build_example_evidence_certificate,
    example_report_hash,
    report_as_dict,
    validate_example_evidence_certificate,
)
from trwm.branch import (
    BranchRuntime,
    BranchSelectionCertificate,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement, validate_claim_certificate
from trwm.core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash
from trwm.ancestral import AncestralBranchMemory, validate_ancestral_branch_memory_snapshot


ANCESTRAL_BRANCH_EXPLORATION_CERTIFICATE_SCHEMA = "trwm.ancestral_branch_exploration_certificate.v1"
ANCESTRAL_BRANCH_SOURCES = (
    "https://link.springer.com/article/10.1007/BF00992699",
    "https://papers.nips.cc/paper/3306-regret-minimization-in-games-with-incomplete-information",
    "https://doi.org/10.1007/11871842_29",
)
ANCESTRAL_BRANCH_CLAIM_BOUNDARY = (
    "G1 local toy-domain evidence only. The result shows receipt-bound past branch evidence can "
    "reorder later budgeted exploration in this controlled benchmark; it is not a robotics, "
    "molecular-design, materials-discovery, regret-minimization, or MCTS performance claim."
)


@dataclass(frozen=True)
class AncestralExplorationState:
    committed_actions: tuple[tuple[str, str, int], ...] = ()


@dataclass(frozen=True)
class ExplorationDomainSpec:
    domain_id: str
    verifier_law: str
    rejected_proposal_type: str
    residual_kind: str
    committed_repair: str
    next_substrate_requirement: str
    actions: tuple[Mapping[str, Any], ...]

    @property
    def committed_action(self) -> str:
        winners = tuple(str(action["action"]) for action in self.actions if bool(action.get("target_commit")))
        if len(winners) != 1:
            raise ValueError(f"domain {self.domain_id} must define exactly one target commit action")
        return winners[0]


@dataclass(frozen=True)
class AncestralDomainReport:
    domain: str
    verifier_law: str
    static_top_action: str
    learned_top_action: str
    committed_training_action: str
    static_winner_rank: int
    learned_winner_rank: int
    static_budget_committed: bool
    learned_budget_committed: bool
    training_receipt_hashes: tuple[str, ...]
    static_budget_receipt_hashes: tuple[str, ...]
    learned_budget_receipt_hashes: tuple[str, ...]
    training_branch_certificate_hashes: tuple[str, ...]
    static_branch_certificate_hash: str
    learned_branch_certificate_hash: str
    rejected_proposal_type: str
    residual_kind: str
    committed_repair: str
    next_substrate_requirement: str


@dataclass(frozen=True)
class AncestralBranchExplorationReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    training_episodes_per_domain: int
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[AncestralDomainReport, ...]
    total_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_rolled_back_loser_count: int
    ancestral_memory_snapshot_hash: str
    ancestral_memory_snapshot_valid: bool
    ancestral_memory_row_count: int
    ancestral_memory_receipt_count: int
    static_budget_success_count: int
    learned_budget_success_count: int
    static_winner_rank_sum: int
    learned_winner_rank_sum: int
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
class AncestralBranchExplorationCertificate:
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
    ancestral_memory_snapshot_hash: str
    static_budget_success_count: int
    learned_budget_success_count: int
    static_winner_rank_sum: int
    learned_winner_rank_sum: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    hard_gate_keys: tuple[str, ...]
    residual_kinds: tuple[str, ...]
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != ANCESTRAL_BRANCH_EXPLORATION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid ancestral exploration certificate schema: {self.schema_version}")
        for field_name in (
            "domains",
            "receipt_hashes",
            "branch_selection_certificate_hashes",
            "hard_gate_keys",
            "residual_kinds",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", ancestral_branch_exploration_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedAncestralBranchExplorationResult(CertifiedExampleResult):
    report: AncestralBranchExplorationReport
    exploration_certificate: AncestralBranchExplorationCertificate
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


class AncestralExplorationAdapter:
    verifier_id = "ancestral_branch_domain_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        domain = payload["domain"]
        accepted, residual = _verify_payload(payload)
        metadata = {
            "domain": domain,
            "action": payload["action"],
            "utility": payload["utility"],
        }
        if accepted:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual=residual, metadata=metadata)

    def apply_commit(self, state: AncestralExplorationState, candidate: TypedCandidate) -> AncestralExplorationState:
        current = normalize_state(state)
        payload = _normalize_payload(candidate.payload)
        return AncestralExplorationState(
            committed_actions=(
                *current.committed_actions,
                (payload["domain"], payload["action"], payload["utility"]),
            )
        )

    def replay(self, state: AncestralExplorationState, receipt: Receipt) -> AncestralExplorationState:
        current = normalize_state(state)
        payload = _normalize_payload(receipt.replay_bundle["candidate_payload"])
        return AncestralExplorationState(
            committed_actions=(
                *current.committed_actions,
                (payload["domain"], payload["action"], payload["utility"]),
            )
        )

    def rollback(self, _state: AncestralExplorationState, receipt: Receipt) -> AncestralExplorationState:
        return normalize_state(receipt.rollback_bundle["pre_state"])


class AncestralExplorationProjector:
    def project(self, _state: AncestralExplorationState, trace: ProposalTrace) -> TypedCandidate:
        return TypedCandidate(
            payload=_normalize_payload(trace.actions[-1]),
            type_name="ancestral.branch.exploration.action",
            schema_version="ancestral.branch.exploration.action.v1",
        )


class HighestUtilityRanker:
    def choose(self, verified: list[tuple[ProposalTrace, TypedCandidate, HardVerifierResult]]) -> int:
        best_idx = 0
        best_value = float("-inf")
        for idx, (_, candidate, result) in enumerate(verified):
            payload = _normalize_payload(candidate.payload)
            value = float(result.metadata.get("utility", payload["utility"]))
            if value > best_value:
                best_idx = idx
                best_value = value
        return best_idx


DOMAIN_SPECS = (
    ExplorationDomainSpec(
        domain_id="robotics_replan",
        verifier_law="clearance >= 0.25 and turn_rate <= 0.60",
        rejected_proposal_type="short wall cut with low clearance",
        residual_kind="safety_envelope_violation",
        committed_repair="certified_detour",
        next_substrate_requirement="branch-local safety residual memory for trajectory families",
        actions=(
            {
                "domain": "robotics_replan",
                "context": "robotics_replan",
                "action": "short_wall_cut",
                "utility": 10,
                "clearance": 0.05,
                "turn_rate": 0.90,
            },
            {
                "domain": "robotics_replan",
                "context": "robotics_replan",
                "action": "wide_patrol",
                "utility": 4,
                "clearance": 0.40,
                "turn_rate": 0.35,
            },
            {
                "domain": "robotics_replan",
                "context": "robotics_replan",
                "action": "certified_detour",
                "utility": 8,
                "clearance": 0.32,
                "turn_rate": 0.40,
                "target_commit": True,
            },
        ),
    ),
    ExplorationDomainSpec(
        domain_id="molecule_repair",
        verifier_law="valence_ok and strain <= 0.35",
        rejected_proposal_type="forced valence patch",
        residual_kind="valence_strain_violation",
        committed_repair="valence_strain_repair",
        next_substrate_requirement="ancestral edit memory over typed chemical-graph residuals",
        actions=(
            {
                "domain": "molecule_repair",
                "context": "molecule_repair",
                "action": "force_valence_patch",
                "utility": 10,
                "valence_ok": False,
                "strain": 0.20,
            },
            {
                "domain": "molecule_repair",
                "context": "molecule_repair",
                "action": "single_bond_pad",
                "utility": 3,
                "valence_ok": True,
                "strain": 0.28,
            },
            {
                "domain": "molecule_repair",
                "context": "molecule_repair",
                "action": "valence_strain_repair",
                "utility": 8,
                "valence_ok": True,
                "strain": 0.12,
                "target_commit": True,
            },
        ),
    ),
    ExplorationDomainSpec(
        domain_id="material_process",
        verifier_law="thermal_gradient <= 0.50 and phase_purity >= 0.90",
        rejected_proposal_type="flash quench with poor phase purity",
        residual_kind="thermal_phase_violation",
        committed_repair="tempered_anneal",
        next_substrate_requirement="branch certificates for stochastic process-window exploration",
        actions=(
            {
                "domain": "material_process",
                "context": "material_process",
                "action": "flash_quench",
                "utility": 10,
                "thermal_gradient": 0.95,
                "phase_purity": 0.85,
            },
            {
                "domain": "material_process",
                "context": "material_process",
                "action": "slow_anneal",
                "utility": 4,
                "thermal_gradient": 0.35,
                "phase_purity": 0.91,
            },
            {
                "domain": "material_process",
                "context": "material_process",
                "action": "tempered_anneal",
                "utility": 8,
                "thermal_gradient": 0.42,
                "phase_purity": 0.96,
                "target_commit": True,
            },
        ),
    ),
)


def run_ancestral_branch_exploration_experiment(training_episodes_per_domain: int = 3) -> AncestralBranchExplorationReport:
    return _run_ancestral_branch_exploration(training_episodes_per_domain).report


def run_ancestral_branch_exploration_certified_experiment(
    training_episodes_per_domain: int = 3,
) -> CertifiedAncestralBranchExplorationResult:
    return _run_ancestral_branch_exploration(training_episodes_per_domain)


def _run_ancestral_branch_exploration(
    training_episodes_per_domain: int,
) -> CertifiedAncestralBranchExplorationResult:
    if training_episodes_per_domain <= 0:
        raise ValueError("training_episodes_per_domain must be positive")

    seed = AncestralExplorationState()
    state = seed
    engine = TransactionEngine(AncestralExplorationAdapter(), ledger=Ledger())
    runtime = BranchRuntime(engine, AncestralExplorationProjector(), HighestUtilityRanker())
    past_branch_memory = AncestralBranchMemory()
    rows: list[AncestralDomainReport] = []
    branch_certificate_pairs: list[tuple[tuple[Receipt, ...], BranchSelectionCertificate]] = []

    for spec in DOMAIN_SPECS:
        training_receipts: list[Receipt] = []
        training_cert_hashes: list[str] = []
        for episode in range(training_episodes_per_domain):
            outcome = runtime.step(state, _make_traces(spec, phase="train", episode=episode, actions=spec.actions))
            state = normalize_state(outcome.state)
            training_receipts.extend(outcome.receipts)
            certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
            branch_certificate_pairs.append((tuple(outcome.receipts), certificate))
            training_cert_hashes.append(certificate.certificate_hash)
            past_branch_memory.update_branch(outcome.receipts, certificate)

        action_tokens = tuple(str(action["action"]) for action in spec.actions)
        learned_order = tuple(str(action) for action in past_branch_memory.rank(spec.domain_id, action_tokens))
        committed_action = spec.committed_action

        static_outcome = runtime.step(
            state,
            _make_traces(spec, phase="static-budget-one", episode=0, actions=(spec.actions[0],)),
        )
        static_certificate = build_branch_selection_certificate(
            static_outcome.receipts,
            verifier_call_count=static_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(static_outcome.receipts), static_certificate))

        learned_action = _action_by_name(spec, learned_order[0])
        learned_outcome = runtime.step(
            state,
            _make_traces(spec, phase="learned-budget-one", episode=0, actions=(learned_action,)),
        )
        state = normalize_state(learned_outcome.state)
        learned_certificate = build_branch_selection_certificate(
            learned_outcome.receipts,
            verifier_call_count=learned_outcome.verifier_calls,
        )
        branch_certificate_pairs.append((tuple(learned_outcome.receipts), learned_certificate))

        rows.append(
            AncestralDomainReport(
                domain=spec.domain_id,
                verifier_law=spec.verifier_law,
                static_top_action=action_tokens[0],
                learned_top_action=learned_order[0],
                committed_training_action=committed_action,
                static_winner_rank=action_tokens.index(committed_action) + 1,
                learned_winner_rank=learned_order.index(committed_action) + 1,
                static_budget_committed=static_outcome.committed,
                learned_budget_committed=learned_outcome.committed,
                training_receipt_hashes=tuple(receipt.receipt_hash for receipt in training_receipts),
                static_budget_receipt_hashes=tuple(receipt.receipt_hash for receipt in static_outcome.receipts),
                learned_budget_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned_outcome.receipts),
                training_branch_certificate_hashes=tuple(training_cert_hashes),
                static_branch_certificate_hash=static_certificate.certificate_hash,
                learned_branch_certificate_hash=learned_certificate.certificate_hash,
                rejected_proposal_type=spec.rejected_proposal_type,
                residual_kind=spec.residual_kind,
                committed_repair=spec.committed_repair,
                next_substrate_requirement=spec.next_substrate_requirement,
            )
        )

    memory_snapshot = past_branch_memory.snapshot()
    all_receipts = tuple(engine.ledger.rows)
    all_branch_certificates_valid = all(
        validate_branch_selection_certificate(certificate) for _, certificate in branch_certificate_pairs
    )
    all_branch_audits_valid = all(
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

    report = AncestralBranchExplorationReport(
        schema_version="trwm.example.ancestral_branch_exploration.v1",
        experiment_id="ancestral_branch_exploration",
        evidence_grade="G1",
        training_episodes_per_domain=training_episodes_per_domain,
        domain_count=len(DOMAIN_SPECS),
        domains=tuple(spec.domain_id for spec in DOMAIN_SPECS),
        rows=tuple(rows),
        total_receipt_count=len(all_receipts),
        total_committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        total_rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        total_rolled_back_loser_count=sum(1 for receipt in all_receipts if receipt.commit_decision == "rolled_back_loser"),
        ancestral_memory_snapshot_hash=memory_snapshot.snapshot_hash,
        ancestral_memory_snapshot_valid=validate_ancestral_branch_memory_snapshot(memory_snapshot),
        ancestral_memory_row_count=len(memory_snapshot.rows),
        ancestral_memory_receipt_count=len(memory_snapshot.receipt_hashes),
        static_budget_success_count=sum(1 for row in rows if row.static_budget_committed),
        learned_budget_success_count=sum(1 for row in rows if row.learned_budget_committed),
        static_winner_rank_sum=sum(row.static_winner_rank for row in rows),
        learned_winner_rank_sum=sum(row.learned_winner_rank for row in rows),
        all_branch_selection_certificates_valid=all_branch_certificates_valid,
        all_branch_selection_audits_valid=all_branch_audits_valid,
        replay_audit_ok=replay_audit_ok,
        rollback_audit_ok=rollback_audit_ok,
        ledger_audit_ok=ledger_audit_ok,
        invalid_commit_count=engine.invalid_commit_count,
        verifier_id=engine.adapter.verifier_id,
        verifier_version=engine.adapter.verifier_version,
        ledger_head=engine.ledger.head,
        hard_gate_keys=(
            "clearance",
            "turn_rate",
            "valence_ok",
            "strain",
            "thermal_gradient",
            "phase_purity",
        ),
        residual_kinds=tuple(sorted({spec.residual_kind for spec in DOMAIN_SPECS})),
        sources=ANCESTRAL_BRANCH_SOURCES,
        learning=(
            "Past branch receipts make exploration stateful: hard rejects identify branches to avoid, "
            "rolled-back accepted losers identify safe but dominated branches, and committed receipts "
            "identify the next budgeted proposal to try first. The hard verifier still owns every commit."
        ),
    )
    exploration_certificate = build_ancestral_branch_exploration_certificate(
        report,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        branch_selection_certificate_hashes=tuple(certificate.certificate_hash for _, certificate in branch_certificate_pairs),
        ancestral_memory_snapshot_hash=memory_snapshot.snapshot_hash,
    )
    evidence_certificate = build_example_evidence_certificate(
        report,
        domain="cross_domain_ancestral_exploration",
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
        claim_boundary=ANCESTRAL_BRANCH_CLAIM_BOUNDARY,
        sources=ANCESTRAL_BRANCH_SOURCES,
    )
    claim_certificate = _build_claim_certificate(report, exploration_certificate, evidence_certificate)
    return CertifiedAncestralBranchExplorationResult(
        report=report,
        exploration_certificate=exploration_certificate,
        evidence_certificate=evidence_certificate,
        claim_certificate=claim_certificate,
    )


def build_ancestral_branch_exploration_certificate(
    report: AncestralBranchExplorationReport,
    *,
    receipt_hashes: tuple[str, ...],
    branch_selection_certificate_hashes: tuple[str, ...],
    ancestral_memory_snapshot_hash: str,
) -> AncestralBranchExplorationCertificate:
    return AncestralBranchExplorationCertificate(
        schema_version=ANCESTRAL_BRANCH_EXPLORATION_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        evidence_grade=report.evidence_grade,
        report_schema_version=report.schema_version,
        report_hash=example_report_hash(report),
        domain_count=report.domain_count,
        domains=report.domains,
        ledger_head=report.ledger_head,
        receipt_hashes=receipt_hashes,
        branch_selection_certificate_hashes=branch_selection_certificate_hashes,
        ancestral_memory_snapshot_hash=ancestral_memory_snapshot_hash,
        static_budget_success_count=report.static_budget_success_count,
        learned_budget_success_count=report.learned_budget_success_count,
        static_winner_rank_sum=report.static_winner_rank_sum,
        learned_winner_rank_sum=report.learned_winner_rank_sum,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        hard_gate_keys=report.hard_gate_keys,
        residual_kinds=report.residual_kinds,
        claim_boundary=ANCESTRAL_BRANCH_CLAIM_BOUNDARY,
    )


def validate_ancestral_branch_exploration_certificate(
    certificate: AncestralBranchExplorationCertificate,
    report: AncestralBranchExplorationReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != ANCESTRAL_BRANCH_EXPLORATION_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if not _nonempty(certificate.experiment_id) or not _nonempty(certificate.report_schema_version):
            return False
        if certificate.domain_count != len(certificate.domains) or certificate.domain_count <= 0:
            return False
        if any(not _nonempty(domain) for domain in certificate.domains):
            return False
        if not _is_hash(certificate.report_hash) or not _is_hash(certificate.ledger_head):
            return False
        if any(not _is_hash(value) for value in certificate.receipt_hashes):
            return False
        if any(not _is_hash(value) for value in certificate.branch_selection_certificate_hashes):
            return False
        if not _is_hash(certificate.ancestral_memory_snapshot_hash):
            return False
        if not certificate.receipt_hashes or not certificate.branch_selection_certificate_hashes:
            return False
        if certificate.static_budget_success_count != 0:
            return False
        if certificate.learned_budget_success_count != certificate.domain_count:
            return False
        if certificate.learned_winner_rank_sum >= certificate.static_winner_rank_sum:
            return False
        if certificate.learned_winner_rank_sum != certificate.domain_count:
            return False
        if not (certificate.replay_audit_ok and certificate.rollback_audit_ok and certificate.ledger_audit_ok):
            return False
        if certificate.invalid_commit_count != 0:
            return False
        if not certificate.hard_gate_keys or any(not _nonempty(key) for key in certificate.hard_gate_keys):
            return False
        if not certificate.residual_kinds or any(not _nonempty(kind) for kind in certificate.residual_kinds):
            return False
        if not _nonempty(certificate.claim_boundary):
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
            if report.ancestral_memory_snapshot_hash != certificate.ancestral_memory_snapshot_hash:
                return False
            if not report.ancestral_memory_snapshot_valid:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
            if report.static_budget_success_count != certificate.static_budget_success_count:
                return False
            if report.learned_budget_success_count != certificate.learned_budget_success_count:
                return False
        return certificate.certificate_hash == ancestral_branch_exploration_certificate_hash(certificate)
    except Exception:
        return False


def ancestral_branch_exploration_certificate_hash(
    certificate: AncestralBranchExplorationCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, AncestralBranchExplorationCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def normalize_state(state: AncestralExplorationState | Mapping[str, Any]) -> AncestralExplorationState:
    if isinstance(state, AncestralExplorationState):
        return AncestralExplorationState(
            committed_actions=tuple(
                (str(domain), str(action), int(utility)) for domain, action, utility in state.committed_actions
            )
        )
    return AncestralExplorationState(
        committed_actions=tuple(
            (str(row[0]), str(row[1]), int(row[2])) for row in state.get("committed_actions", ())
        )
    )


def result_as_dict(result: CertifiedAncestralBranchExplorationResult) -> dict[str, Any]:
    return report_as_dict(result)


def _build_claim_certificate(
    report: AncestralBranchExplorationReport,
    exploration_certificate: AncestralBranchExplorationCertificate,
    evidence_certificate: ExampleEvidenceCertificate,
) -> ClaimCertificate:
    return certify_claim(
        claim_id="ancestral_branch_exploration_g1",
        claim_text=(
            "Past branch receipts can improve later budgeted exploration across the robotics, "
            "molecule-repair, and material-process toy domains while hard verification keeps commit authority."
        ),
        evidence_grade="G1",
        scope="ancestral_branch_exploration",
        requirements=(
            requirement(
                "exploration_certificate_valid",
                validate_ancestral_branch_exploration_certificate(exploration_certificate, report),
                certificate_hash=exploration_certificate.certificate_hash,
            ),
            requirement(
                "evidence_certificate_valid",
                validate_example_evidence_certificate(evidence_certificate, report),
                certificate_hash=evidence_certificate.certificate_hash,
            ),
            requirement(
                "ancestral_memory_snapshot_bound",
                report.ancestral_memory_snapshot_valid
                and report.ancestral_memory_snapshot_hash == exploration_certificate.ancestral_memory_snapshot_hash,
                snapshot_hash=report.ancestral_memory_snapshot_hash,
            ),
            requirement("all_branch_selection_certificates_valid", report.all_branch_selection_certificates_valid),
            requirement("all_branch_selection_audits_valid", report.all_branch_selection_audits_valid),
            requirement("static_budget_fails_all_domains", report.static_budget_success_count == 0),
            requirement("learned_budget_succeeds_all_domains", report.learned_budget_success_count == report.domain_count),
            requirement("winner_rank_improves", report.learned_winner_rank_sum < report.static_winner_rank_sum),
            requirement("ledger_replay_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
            requirement("no_invalid_commits", report.invalid_commit_count == 0),
        ),
        metrics={
            "domain_count": report.domain_count,
            "total_receipt_count": report.total_receipt_count,
            "total_committed_count": report.total_committed_count,
            "total_rejected_count": report.total_rejected_count,
            "static_budget_success_count": report.static_budget_success_count,
            "learned_budget_success_count": report.learned_budget_success_count,
            "static_winner_rank_sum": report.static_winner_rank_sum,
            "learned_winner_rank_sum": report.learned_winner_rank_sum,
        },
        boundary=ANCESTRAL_BRANCH_CLAIM_BOUNDARY,
        sources=ANCESTRAL_BRANCH_SOURCES,
    )


def _make_traces(
    spec: ExplorationDomainSpec,
    *,
    phase: str,
    episode: int,
    actions: Iterable[Mapping[str, Any]],
) -> tuple[ProposalTrace, ...]:
    return tuple(
        ProposalTrace(
            branch_id=f"{spec.domain_id}:{phase}:{episode}:{action['action']}",
            actions=(_normalize_payload({**dict(action), "phase": phase}),),
            seeds=("ancestral-branch-exploration", spec.domain_id, phase, episode, action["action"]),
            model_version="ancestral.branch.exploration.v1",
        )
        for action in actions
    )


def _action_by_name(spec: ExplorationDomainSpec, action_name: str) -> Mapping[str, Any]:
    for action in spec.actions:
        if str(action["action"]) == action_name:
            return action
    raise ValueError(f"unknown action {action_name!r} for domain {spec.domain_id}")


def _verify_payload(payload: Mapping[str, Any]) -> tuple[bool, Mapping[str, Any] | None]:
    domain = str(payload["domain"])
    if domain == "robotics_replan":
        clearance = float(payload["clearance"])
        turn_rate = float(payload["turn_rate"])
        accepted = clearance >= 0.25 and turn_rate <= 0.60
        if accepted:
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
        accepted = valence_ok and strain <= 0.35
        if accepted:
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
        accepted = thermal_gradient <= 0.50 and phase_purity >= 0.90
        if accepted:
            return True, None
        return False, {
            "kind": "thermal_phase_violation",
            "thermal_gradient": thermal_gradient,
            "max_thermal_gradient": 0.50,
            "phase_purity": phase_purity,
            "min_phase_purity": 0.90,
        }
    raise ValueError(f"unknown ancestral exploration domain: {domain}")


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    domain = str(payload["domain"])
    action = str(payload["action"])
    if not domain or not action:
        raise ValueError("domain and action must be non-empty")
    normalized = dict(payload)
    normalized["domain"] = domain
    normalized["context"] = str(payload.get("context", domain))
    normalized["action"] = action
    normalized["utility"] = int(payload["utility"])
    if normalized["utility"] < 0:
        raise ValueError("utility must be non-negative")
    if "target_commit" in normalized:
        normalized["target_commit"] = bool(normalized["target_commit"])
    return normalized


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def main() -> None:
    print(json.dumps(result_as_dict(run_ancestral_branch_exploration_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
