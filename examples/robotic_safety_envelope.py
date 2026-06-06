from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping

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
    receipt_count: int
    committed_count: int
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
        receipt_count=len(ledger.rows),
        committed_count=sum(1 for row in ledger.rows if row.committed),
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


def report_as_dict(report: RoboticSafetyEnvelopeReport) -> dict[str, Any]:
    return asdict(report)


def main() -> None:
    print(json.dumps(report_as_dict(run_robotic_safety_envelope_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
