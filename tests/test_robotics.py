from __future__ import annotations

import unittest

from trwm.core import Ledger, ProposalTrace, TransactionEngine
from trwm.experiments.robotics import (
    Point2,
    RobotResidualRepairer,
    RobotTrajectoryAdapter,
    RobotTrajectoryState,
    diagnose_trajectory_repair,
    make_robot_trajectory_candidate,
    make_robot_trajectory_problem,
    min_clearance,
    run_repair_robot_episode,
    run_robot_trajectory_benchmark,
    run_static_robot_episode,
    segment_distance,
)


class RobotTrajectoryTests(unittest.TestCase):
    def test_segment_distance_uses_exact_projection(self) -> None:
        point = Point2(0.5, 0.5)
        start = Point2(0.35, 0.22)
        end = Point2(0.65, 0.22)

        self.assertAlmostEqual(segment_distance(point, start, end), 0.28)

    def test_verifier_rejects_collision_with_shield_repair(self) -> None:
        problem = make_robot_trajectory_problem(0.24)
        candidate = make_robot_trajectory_candidate(problem, 0.5)

        result = RobotTrajectoryAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "collision")
        self.assertEqual(result.residual["obstacle_id"], "obs0")
        self.assertAlmostEqual(result.residual["required_distance"], 0.24)
        self.assertEqual(result.residual["repair"]["detour_y"], 0.22)
        self.assertAlmostEqual(result.residual["repair"]["min_clearance"], 0.04)

    def test_verifier_rejects_speed_limit_before_collision(self) -> None:
        problem = make_robot_trajectory_problem(0.24, max_step=0.20)
        candidate = make_robot_trajectory_candidate(problem, 0.5)

        result = RobotTrajectoryAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "speed_limit_exceeded")
        self.assertEqual(result.residual["segment_index"], 0)
        self.assertAlmostEqual(result.residual["distance"], 0.25)

    def test_diagnosed_detour_is_safe_and_cleared(self) -> None:
        problem = make_robot_trajectory_problem(0.24)
        repair = diagnose_trajectory_repair(problem)

        self.assertIsNotNone(repair)
        self.assertEqual(repair["detour_y"], 0.22)
        self.assertGreaterEqual(min_clearance(problem, repair["trajectory"]), 0.04)

    def test_residual_repair_commits_after_collision_feedback(self) -> None:
        problem = make_robot_trajectory_problem(0.28)
        ledger = Ledger()
        result = run_repair_robot_episode(problem, ledger=ledger, repairer=RobotResidualRepairer(), episode=1)

        self.assertEqual(result.calls, 2)
        self.assertTrue(result.success)
        self.assertTrue(result.audit_ok)
        self.assertTrue(result.replay_rollback_ok)
        self.assertEqual(len(ledger.committed_rows()), 1)
        self.assertEqual(ledger.committed_rows()[0].replay_bundle["candidate_payload"]["detour_y"], 0.22)

    def test_robot_trajectory_benchmark_improves_over_static_shield_search(self) -> None:
        report = run_robot_trajectory_benchmark(seed=67, episodes=45)

        self.assertEqual(report.episodes, 45)
        self.assertEqual(report.candidate_space_size, 11)
        self.assertEqual(report.static_calls_per_success, 8.0)
        self.assertEqual(report.repair_calls_per_success, 2.0)
        self.assertEqual(report.repair_gain, 4.0)
        self.assertEqual(report.repair_success_rate, 1.0)
        self.assertEqual(report.ledger_audit_rate, 1.0)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.learned_residual_kinds.get("collision"), 45)

    def test_static_robot_episode_uses_same_detour_candidates(self) -> None:
        problem = make_robot_trajectory_problem(0.24)
        result = run_static_robot_episode(problem, (0.5, 0.46, 0.54, 0.22), ledger=Ledger(), episode=4)

        self.assertEqual(result.calls, 4)
        self.assertTrue(result.success)

    def test_valid_trajectory_for_wrong_problem_fails_closed(self) -> None:
        problem_a = make_robot_trajectory_problem(0.24)
        problem_b = make_robot_trajectory_problem(0.31)
        candidate = make_robot_trajectory_candidate(problem_a, 0.22)
        engine = TransactionEngine(RobotTrajectoryAdapter(), ledger=Ledger())

        outcome = engine.transact(
            RobotTrajectoryState(problem=problem_b),
            ProposalTrace(
                branch_id="wrong-robot-problem",
                actions=({"detour_y": 0.22},),
                seeds=("robot", "wrong-problem"),
                model_version="robot.test.v1",
            ),
            candidate,
        )

        self.assertFalse(outcome.committed)
        self.assertTrue(outcome.reason.startswith("replay_or_rollback_error:"))
        self.assertEqual(engine.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
