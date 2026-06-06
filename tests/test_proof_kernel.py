from __future__ import annotations

import unittest

from trwm.core import Ledger, ProposalTrace, TransactionEngine
from trwm.experiments.proof_kernel import (
    HornProofAdapter,
    ProofResidualRepairer,
    ProofState,
    chain_proof_problem,
    make_proof_candidate,
    run_proof_kernel_benchmark,
    run_repair_proof_episode,
    run_static_proof_episode,
)


class ProofKernelTests(unittest.TestCase):
    def test_verifier_rejects_missing_premise_with_repair_hint(self) -> None:
        problem, _correct = chain_proof_problem(rule_count=3)
        candidate = make_proof_candidate(problem, ("r2",))

        result = HornProofAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "missing_premise")
        self.assertEqual(result.residual["missing"], ("p1",))
        self.assertEqual(result.residual["repair"], {"rule_id": "r1", "conclusion": "p1"})

    def test_residual_repair_builds_script_before_commit(self) -> None:
        problem, correct = chain_proof_problem(rule_count=3)
        ledger = Ledger()
        result = run_repair_proof_episode(problem, ledger=ledger, repairer=ProofResidualRepairer(), episode=1)

        self.assertEqual(result.calls, len(correct) + 1)
        self.assertTrue(result.success)
        self.assertTrue(result.audit_ok)
        self.assertTrue(result.replay_rollback_ok)
        self.assertEqual(len(ledger.committed_rows()), 1)
        self.assertEqual(ledger.committed_rows()[0].replay_bundle["candidate_payload"]["script"], correct)

    def test_proof_kernel_benchmark_improves_over_static_permutations(self) -> None:
        report = run_proof_kernel_benchmark(seed=41, episodes=12, rule_count=6)

        self.assertEqual(report.episodes, 12)
        self.assertEqual(report.rule_count, 6)
        self.assertEqual(report.repair_success_rate, 1.0)
        self.assertEqual(report.ledger_audit_rate, 1.0)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertLess(report.repair_calls_per_success, report.static_calls_per_success)
        self.assertGreater(report.repair_gain, 5.0)
        self.assertEqual(report.learned_residual_kinds.get("goal_not_derived"), 72)

    def test_static_episode_uses_same_script_candidates(self) -> None:
        problem, correct = chain_proof_problem(rule_count=3)
        scripts = (("r3", "r2", "r1"), correct)
        result = run_static_proof_episode(problem, scripts, ledger=Ledger(), episode=4)

        self.assertEqual(result.calls, 2)
        self.assertTrue(result.success)

    def test_valid_script_for_wrong_problem_fails_closed(self) -> None:
        problem_a, correct_a = chain_proof_problem(rule_count=1, prefix="a")
        problem_b, _correct_b = chain_proof_problem(rule_count=1, prefix="b")
        candidate = make_proof_candidate(problem_a, correct_a)
        engine = TransactionEngine(HornProofAdapter(), ledger=Ledger())

        outcome = engine.transact(
            ProofState(problem=problem_b),
            ProposalTrace(
                branch_id="wrong-proof-problem",
                actions=({"script": correct_a},),
                seeds=("proof", "wrong-problem"),
                model_version="proof.test.v1",
            ),
            candidate,
        )

        self.assertFalse(outcome.committed)
        self.assertTrue(outcome.reason.startswith("replay_or_rollback_error:"))
        self.assertEqual(engine.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
