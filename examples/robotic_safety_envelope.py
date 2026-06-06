from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from examples.common import (
    CertifiedExampleResult,
    build_example_evidence_certificate,
    report_as_dict,
    validate_example_evidence_certificate,
)
from trwm.claims import certify_claim, requirement
from trwm.core import Ledger, ProposalTrace, TransactionEngine
from trwm.experiments.robotics import (
    RobotResidualRepairer,
    RobotTrajectoryAdapter,
    RobotTrajectoryState,
    diagnose_trajectory_repair,
    make_robot_trajectory_candidate,
    make_robot_trajectory_problem,
    min_clearance,
    path_length,
)
from trwm.sdk import (
    ProgrammableSubstrate,
    audit_domain_manifest,
    build_domain_manifest,
    validate_domain_manifest,
)


ROBOTIC_SAFETY_SOURCES = (
    "https://arxiv.org/abs/1903.11199",
)
ROBOTIC_SAFETY_CLAIM_BOUNDARY = (
    "G1 local 2D point-robot canary only; not a real robotics safety case, "
    "controller proof, hardware guarantee, or deployment claim."
)


@dataclass(frozen=True)
class RoboticSafetyEnvelopeReport:
    schema_version: str
    experiment_id: str
    source_math: tuple[str, ...]
    first_decision: str
    first_residual_kind: str
    repaired_decision: str
    repaired_committed: bool
    repaired_detour_y: float
    repaired_min_clearance: float
    repaired_path_length: float
    soft_score_trap_blocked: bool
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    ledger_head: str
    verifier_id: str
    verifier_version: str
    receipt_count: int
    committed_count: int
    rejected_count: int
    receipt_hashes: tuple[str, ...]
    sdk_manifest_valid: bool
    sdk_manifest_audit_ok: bool
    sdk_hard_verifier_calls: int
    learned_residual_kinds: Mapping[str, int]
    learning: str


def run_robotic_safety_envelope_experiment() -> RoboticSafetyEnvelopeReport:
    """Run a small robot safety-envelope experiment on the real TRWM substrate.

    The verifier checks the same geometric barrier used by the robotics canary:
    segment-to-obstacle distance must exceed obstacle radius plus robot radius
    plus clearance, and every segment must respect the max-step bound.
    """

    problem = make_robot_trajectory_problem(effective_radius=0.28, max_step=0.46)
    seed_state = RobotTrajectoryState(problem=problem)
    ledger = Ledger()
    engine = TransactionEngine(RobotTrajectoryAdapter(), ledger=ledger)
    repairer = RobotResidualRepairer()

    unsafe_candidate = make_robot_trajectory_candidate(
        problem,
        0.5,
        context="robotic-safety-envelope",
        cost=1,
    )
    first = engine.transact(
        seed_state,
        ProposalTrace(
            branch_id="robotic-envelope-straight-line",
            actions=({"detour_y": 0.5, "proposal": "straight_line"},),
            seeds=("robotic-envelope", 1),
            model_version="robotic.safety_envelope.v1",
        ),
        unsafe_candidate,
        soft_scores={"short_path_preference": 1.0},
    )
    repairer.update(first.receipt)

    residual = first.receipt.hard_result.residual
    if not isinstance(residual, Mapping):
        raise AssertionError("robot safety envelope expected a structured residual")
    repaired_candidate = repairer.propose(unsafe_candidate, residual)
    if repaired_candidate is None:
        repair = diagnose_trajectory_repair(problem)
        if not isinstance(repair, Mapping):
            raise AssertionError("robot safety envelope expected a feasible shield repair")
        repaired_candidate = make_robot_trajectory_candidate(
            problem,
            float(repair["detour_y"]),
            context="robotic-safety-envelope",
            cost=2,
        )

    repaired = engine.transact(
        first.state,
        ProposalTrace(
            branch_id="robotic-envelope-repaired-detour",
            actions=({"detour_y": repaired_candidate.payload["detour_y"], "proposal": "residual_repair"},),
            seeds=("robotic-envelope", 2),
            model_version="robotic.safety_envelope.v1",
        ),
        repaired_candidate,
        soft_scores={"short_path_preference": 0.62, "residual_repair": 1.0},
    )
    repairer.update(repaired.receipt)

    substrate = ProgrammableSubstrate()
    runtime = substrate.register("robotic_safety_envelope", RobotTrajectoryAdapter())
    sdk_result = substrate.submit(
        "robotic_safety_envelope",
        seed_state,
        ProposalTrace(
            branch_id="robotic-envelope-sdk-manifest-probe",
            actions=({"detour_y": repaired_candidate.payload["detour_y"], "proposal": "sdk_manifest_probe"},),
            seeds=("robotic-envelope", "sdk"),
            model_version="robotic.safety_envelope.sdk.v1",
        ),
        repaired_candidate,
        context="robotic_safety_envelope",
    )
    manifest = build_domain_manifest(runtime)

    replay_ok = False
    rollback_ok = False
    if ledger.audit():
        replay_ok = engine.replay_audit(seed_state) == repaired.state
        rollback_ok = engine.rollback_audit(seed_state) == seed_state

    trajectory = repaired_candidate.payload["trajectory"]
    receipt_hashes = tuple(row.receipt_hash for row in ledger.rows)
    return RoboticSafetyEnvelopeReport(
        schema_version="trwm.example.robotic_safety_envelope.v1",
        experiment_id="robotic_safety_envelope",
        source_math=(
            "control-barrier-style signed distance h(x) = d(segment, obstacle_center) - required_radius",
            "hard transaction commit iff h(x) >= 0 for all obstacle segments and step_length <= max_step",
        ),
        first_decision=first.reason,
        first_residual_kind=str(residual.get("kind")),
        repaired_decision=repaired.reason,
        repaired_committed=repaired.committed,
        repaired_detour_y=float(repaired_candidate.payload["detour_y"]),
        repaired_min_clearance=min_clearance(problem, trajectory),
        repaired_path_length=path_length(trajectory),
        soft_score_trap_blocked=not first.committed and first.receipt.soft_scores.get("short_path_preference") == 1.0,
        replay_audit_ok=replay_ok,
        rollback_audit_ok=rollback_ok,
        ledger_audit_ok=ledger.audit(),
        invalid_commit_count=engine.invalid_commit_count,
        ledger_head=ledger.head,
        verifier_id=RobotTrajectoryAdapter.verifier_id,
        verifier_version=RobotTrajectoryAdapter.verifier_version,
        receipt_count=len(ledger.rows),
        committed_count=sum(1 for row in ledger.rows if row.committed),
        rejected_count=sum(1 for row in ledger.rows if row.hard_result.rejected),
        receipt_hashes=receipt_hashes,
        sdk_manifest_valid=validate_domain_manifest(manifest),
        sdk_manifest_audit_ok=audit_domain_manifest(runtime, manifest),
        sdk_hard_verifier_calls=sdk_result.hard_verifier_calls,
        learned_residual_kinds=dict(repairer.rejected_residuals),
        learning=(
            "The useful frontier is to let a proposer optimize path length, but keep signed-distance "
            "barriers and max-step physics as transactional hard gates. Residuals are enough to "
            "repair the proposal without granting the learner commit authority."
        ),
    )


def run_robotic_safety_envelope_certified_experiment() -> CertifiedExampleResult:
    report = run_robotic_safety_envelope_experiment()
    evidence = build_example_evidence_certificate(
        report,
        domain="robotics",
        verifier_id=report.verifier_id,
        verifier_version=report.verifier_version,
        ledger_head=report.ledger_head,
        receipt_hashes=report.receipt_hashes,
        committed_count=report.committed_count,
        rejected_count=report.rejected_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        hard_gate_keys=(
            "hard_verifier_accept",
            "max_step",
            "replay",
            "rollback",
            "signed_distance_clearance",
        ),
        residual_kinds=tuple(report.learned_residual_kinds),
        claim_boundary=ROBOTIC_SAFETY_CLAIM_BOUNDARY,
        sources=ROBOTIC_SAFETY_SOURCES,
    )
    claim = certify_claim(
        claim_id="robotic_safety_envelope_g1",
        claim_text=(
            "Signed-distance and max-step gates block unsafe path proposals, and residual repair "
            "can commit a safe detour in the local G1 robot envelope canary."
        ),
        evidence_grade="G1",
        scope="robotic_safety_envelope",
        requirements=(
            requirement("evidence_certificate_valid", validate_example_evidence_certificate(evidence, report)),
            requirement("unsafe_soft_score_blocked", report.soft_score_trap_blocked),
            requirement("residual_repair_committed", report.repaired_committed and report.repaired_decision == "commit"),
            requirement("replay_and_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok),
            requirement("zero_invalid_commits", report.invalid_commit_count == 0),
            requirement("source_bound", bool(evidence.sources)),
        ),
        metrics={
            "repaired_min_clearance": report.repaired_min_clearance,
            "receipt_count": report.receipt_count,
            "certificate_hash": evidence.certificate_hash,
        },
        boundary=ROBOTIC_SAFETY_CLAIM_BOUNDARY,
        sources=ROBOTIC_SAFETY_SOURCES,
    )
    return CertifiedExampleResult(report=report, evidence_certificate=evidence, claim_certificate=claim)


def main() -> None:
    print(json.dumps(report_as_dict(run_robotic_safety_envelope_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
