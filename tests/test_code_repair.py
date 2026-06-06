from __future__ import annotations

import unittest

from trwm.core import Ledger, ProposalTrace, TransactionEngine
from trwm.experiments.code_repair import (
    CodePatchAdapter,
    CodeRepairState,
    CodeResidualRepairer,
    evaluate_operator,
    make_code_patch_candidate,
    make_code_repair_problem,
    run_code_repair_benchmark,
    run_repair_code_episode,
    run_static_code_repair_episode,
)


class CodeRepairTests(unittest.TestCase):
    def test_operator_semantics_are_exact_integers(self) -> None:
        self.assertEqual(evaluate_operator("+", 3, -2), 1)
        self.assertEqual(evaluate_operator("-", 3, -2), 5)
        self.assertEqual(evaluate_operator("*", 3, -2), -6)
        self.assertEqual(evaluate_operator("max", 3, -2), 3)
        self.assertEqual(evaluate_operator("min", 3, -2), -2)
        self.assertEqual(evaluate_operator("left", 3, -2), 3)
        self.assertEqual(evaluate_operator("right", 3, -2), -2)
        self.assertEqual(evaluate_operator("absdiff", 3, -2), 5)

    def test_verifier_rejects_failing_test_with_unique_operator_repair(self) -> None:
        problem = make_code_repair_problem("+")
        candidate = make_code_patch_candidate(problem, "left")

        result = CodePatchAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "test_failure")
        self.assertEqual(result.residual["test_index"], 1)
        self.assertEqual(result.residual["expected"], 3)
        self.assertEqual(result.residual["actual"], 1)
        self.assertEqual(result.residual["repair"]["operator"], "+")
        self.assertEqual(result.residual["repair"]["base_hash"], problem.source_hash)

    def test_verifier_rejects_base_hash_mismatch(self) -> None:
        problem = make_code_repair_problem("+")
        broken = {
            **problem.__dict__,
            "source_hash": "0" * 64,
        }
        candidate = make_code_patch_candidate(broken, "+")

        result = CodePatchAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "schema_error")
        self.assertIn("source_hash", result.residual["message"])

    def test_residual_repair_commits_after_test_feedback(self) -> None:
        problem = make_code_repair_problem("absdiff")
        ledger = Ledger()
        result = run_repair_code_episode(problem, ledger=ledger, repairer=CodeResidualRepairer(), episode=1)

        self.assertEqual(result.calls, 2)
        self.assertTrue(result.success)
        self.assertTrue(result.audit_ok)
        self.assertTrue(result.replay_rollback_ok)
        self.assertEqual(len(ledger.committed_rows()), 1)
        self.assertEqual(ledger.committed_rows()[0].replay_bundle["candidate_payload"]["patch"].operator, "absdiff")

    def test_code_repair_benchmark_improves_over_static_patch_search(self) -> None:
        report = run_code_repair_benchmark(seed=59, episodes=42)

        self.assertEqual(report.episodes, 42)
        self.assertEqual(report.candidate_space_size, 8)
        self.assertEqual(report.repair_success_rate, 1.0)
        self.assertEqual(report.ledger_audit_rate, 1.0)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.static_calls_per_success, 5.0)
        self.assertEqual(report.repair_calls_per_success, 2.0)
        self.assertEqual(report.repair_gain, 2.5)
        self.assertEqual(report.learned_residual_kinds.get("test_failure"), 42)

    def test_static_episode_uses_same_patch_candidates(self) -> None:
        problem = make_code_repair_problem("*")
        result = run_static_code_repair_episode(problem, ("left", "+", "*"), ledger=Ledger(), episode=4)

        self.assertEqual(result.calls, 3)
        self.assertTrue(result.success)

    def test_valid_patch_for_wrong_problem_fails_closed(self) -> None:
        problem_a = make_code_repair_problem("+")
        problem_b = make_code_repair_problem("-")
        candidate = make_code_patch_candidate(problem_a, "+")
        engine = TransactionEngine(CodePatchAdapter(), ledger=Ledger())

        outcome = engine.transact(
            CodeRepairState(problem=problem_b),
            ProposalTrace(
                branch_id="wrong-code-problem",
                actions=({"node_id": "op0", "operator": "+"},),
                seeds=("code", "wrong-problem"),
                model_version="code.test.v1",
            ),
            candidate,
        )

        self.assertFalse(outcome.committed)
        self.assertTrue(outcome.reason.startswith("replay_or_rollback_error:"))
        self.assertEqual(engine.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
