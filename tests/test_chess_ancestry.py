from __future__ import annotations

import math
import unittest

from trwm.core import Ledger, ProposalTrace, TransactionEngine
from trwm.experiments.chess_ancestry import (
    ChessAncestryAdapter,
    ChessAncestryProblem,
    ChessAncestryState,
    ChessResidualRepairer,
    coord,
    enumerate_chess_ancestry,
    make_default_chess_ancestry_problem,
    path_clear,
    reverse_chess_candidates,
    run_chess_ancestry_benchmark,
    run_repair_chess_episode,
)


class ChessAncestryTests(unittest.TestCase):
    def test_rook_path_clear_uses_rule_geometry(self) -> None:
        problem = make_default_chess_ancestry_problem()
        candidate = next(row for row in reverse_chess_candidates(problem) if row.payload["move"].from_square == "e5")

        self.assertEqual(coord("e4"), (4, 3))
        self.assertFalse(path_clear(problem.target_board, "a4", "e4"))
        self.assertTrue(path_clear(candidate.payload["predecessor"], "e5", "e4"))

    def test_verifier_rejects_blocked_rook_with_repair(self) -> None:
        problem = make_default_chess_ancestry_problem()
        candidate = reverse_chess_candidates(problem)[0]

        result = ChessAncestryAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "illegal_move")
        self.assertEqual(result.residual["message"], "rook path is blocked")
        self.assertEqual(result.residual["repair"]["move"].from_square, "e5")
        self.assertEqual(result.residual["repair"]["move"].to_square, "e4")

    def test_enumeration_finds_all_legal_histories(self) -> None:
        problem = make_default_chess_ancestry_problem()
        state, engine = enumerate_chess_ancestry(problem)

        self.assertEqual(engine.hard_verifier_calls, 7)
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(
            tuple((move.from_square, move.to_square) for move in state.histories),
            (("e5", "e4"), ("e6", "e4"), ("e7", "e4")),
        )

    def test_residual_repair_commits_after_illegal_move_feedback(self) -> None:
        problem = make_default_chess_ancestry_problem()
        ledger = Ledger()
        result = run_repair_chess_episode(problem, ledger, ChessResidualRepairer(), episode=1)

        self.assertEqual(result.calls, 2)
        self.assertTrue(result.success)
        self.assertTrue(result.audit_ok)
        self.assertTrue(result.replay_rollback_ok)
        self.assertEqual(len(ledger.committed_rows()), 1)
        self.assertEqual(ledger.committed_rows()[0].replay_bundle["candidate_payload"]["move"].from_square, "e5")

    def test_chess_ancestry_benchmark_metrics(self) -> None:
        report = run_chess_ancestry_benchmark()

        self.assertEqual(report.candidate_space_size, 7)
        self.assertEqual(report.history_count, 3)
        self.assertAlmostEqual(report.ambiguity_entropy, math.log2(3))
        self.assertEqual(report.verifier_calls, 7)
        self.assertEqual(report.forward_replay_success_rate, 1.0)
        self.assertEqual(report.static_calls_per_success, 3)
        self.assertEqual(report.repair_calls_per_success, 2)
        self.assertEqual(report.repair_gain, 1.5)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.learned_residual_kinds["illegal_move"], 1)

    def test_valid_history_for_wrong_problem_fails_closed(self) -> None:
        problem_a = make_default_chess_ancestry_problem()
        problem_b = ChessAncestryProblem(target_board=problem_a.target_board, moved_piece_id="WK")
        candidate = next(row for row in reverse_chess_candidates(problem_a) if row.payload["move"].from_square == "e5")
        engine = TransactionEngine(ChessAncestryAdapter(), ledger=Ledger())

        outcome = engine.transact(
            ChessAncestryState(problem=problem_b),
            ProposalTrace(
                branch_id="wrong-chess-problem",
                actions=(candidate.payload["move"],),
                seeds=("chess", "wrong-problem"),
                model_version="chess.test.v1",
            ),
            candidate,
        )

        self.assertFalse(outcome.committed)
        self.assertTrue(outcome.reason.startswith("replay_or_rollback_error:"))
        self.assertEqual(engine.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
