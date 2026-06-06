from __future__ import annotations

import unittest

from trwm.core import Ledger, ProposalTrace, TransactionEngine
from trwm.experiments.circuit_repair import (
    BooleanCircuitAdapter,
    CircuitRepairState,
    CircuitResidualRepairer,
    eval_op_mask,
    make_circuit_candidate,
    make_circuit_repair_problem,
    run_circuit_repair_benchmark,
    run_repair_circuit_episode,
    run_static_circuit_episode,
)


class CircuitRepairTests(unittest.TestCase):
    def test_boolean_op_masks_match_common_functions(self) -> None:
        self.assertEqual(eval_op_mask(6, 0, 0), 0)
        self.assertEqual(eval_op_mask(6, 0, 1), 1)
        self.assertEqual(eval_op_mask(6, 1, 0), 1)
        self.assertEqual(eval_op_mask(6, 1, 1), 0)
        self.assertEqual(eval_op_mask(8, 1, 1), 1)
        self.assertEqual(eval_op_mask(14, 0, 1), 1)

    def test_verifier_rejects_mismatch_with_unique_gate_repair(self) -> None:
        problem = make_circuit_repair_problem(target_op_mask=6)
        candidate = make_circuit_candidate(problem, op_mask=0)

        result = BooleanCircuitAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "truth_table_mismatch")
        self.assertEqual(result.residual["repair"], {"gate_id": "g1", "op_mask": 6, "op_name": "XOR"})

    def test_residual_repair_commits_after_truth_table_feedback(self) -> None:
        problem = make_circuit_repair_problem(target_op_mask=14)
        ledger = Ledger()
        result = run_repair_circuit_episode(problem, ledger=ledger, repairer=CircuitResidualRepairer(), episode=1)

        self.assertEqual(result.calls, 2)
        self.assertTrue(result.success)
        self.assertTrue(result.audit_ok)
        self.assertTrue(result.replay_rollback_ok)
        self.assertEqual(len(ledger.committed_rows()), 1)
        self.assertEqual(ledger.committed_rows()[0].replay_bundle["candidate_payload"]["op_mask"], 14)

    def test_circuit_repair_benchmark_improves_over_static_op_search(self) -> None:
        report = run_circuit_repair_benchmark(seed=47, episodes=45)

        self.assertEqual(report.episodes, 45)
        self.assertEqual(report.op_count, 16)
        self.assertEqual(report.repair_success_rate, 1.0)
        self.assertEqual(report.ledger_audit_rate, 1.0)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertLess(report.repair_calls_per_success, report.static_calls_per_success)
        self.assertGreater(report.repair_gain, 4.0)
        self.assertEqual(report.learned_residual_kinds.get("truth_table_mismatch"), 45)

    def test_static_episode_uses_same_gate_candidates(self) -> None:
        problem = make_circuit_repair_problem(target_op_mask=3)
        result = run_static_circuit_episode(problem, (0, 1, 2, 3), ledger=Ledger(), episode=4)

        self.assertEqual(result.calls, 4)
        self.assertTrue(result.success)

    def test_valid_netlist_for_wrong_problem_fails_closed(self) -> None:
        problem_a = make_circuit_repair_problem(target_op_mask=6)
        problem_b = make_circuit_repair_problem(target_op_mask=14)
        candidate = make_circuit_candidate(problem_a, op_mask=6)
        engine = TransactionEngine(BooleanCircuitAdapter(), ledger=Ledger())

        outcome = engine.transact(
            CircuitRepairState(problem=problem_b),
            ProposalTrace(
                branch_id="wrong-circuit-problem",
                actions=({"gate_id": "g1", "op_mask": 6},),
                seeds=("circuit", "wrong-problem"),
                model_version="circuit.test.v1",
            ),
            candidate,
        )

        self.assertFalse(outcome.committed)
        self.assertTrue(outcome.reason.startswith("replay_or_rollback_error:"))
        self.assertEqual(engine.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
