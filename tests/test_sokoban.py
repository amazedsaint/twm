from __future__ import annotations

import unittest

from trwm.experiments.sokoban import (
    SokobanReverseAdapter,
    SokobanState,
    make_sokoban_candidate,
    parse_sokoban,
    render_sokoban,
    replay_pushes,
    search_sokoban_predecessor,
)


SOLVED_LEVEL = (
    "#######",
    "#  @* #",
    "#     #",
    "#######",
)


class SokobanReverseTests(unittest.TestCase):
    def test_parse_render_and_forward_replay(self) -> None:
        layout, solved = parse_sokoban(SOLVED_LEVEL)
        predecessor = SokobanState(boxes=((1, 3),), player=(1, 2))
        pushes = ({"box": (1, 3), "direction": "R"},)

        self.assertEqual(render_sokoban(layout, solved), SOLVED_LEVEL)
        self.assertEqual(replay_pushes(layout, predecessor, pushes), solved)

    def test_reverse_search_commits_audited_predecessor(self) -> None:
        layout, solved = parse_sokoban(SOLVED_LEVEL)
        report = search_sokoban_predecessor(layout, solved, max_depth=1, max_candidates=8)

        self.assertTrue(report.solved)
        self.assertEqual(report.predecessor, SokobanState(boxes=((1, 3),), player=(1, 2)))
        self.assertEqual(report.pushes, ({"box": (1, 3), "direction": "R"},))
        self.assertEqual(report.verifier_calls, 1)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertGreater(report.verifier_call_reduction, 1.0)

    def test_hard_verifier_rejects_bad_certificate(self) -> None:
        layout, solved = parse_sokoban(SOLVED_LEVEL)
        predecessor = SokobanState(boxes=((1, 3),), player=(1, 2))
        candidate = make_sokoban_candidate(
            layout,
            solved,
            predecessor,
            ({"box": (1, 3), "direction": "L"},),
            cost=1,
        )

        result = SokobanReverseAdapter().verify(candidate)
        self.assertTrue(result.rejected)


if __name__ == "__main__":
    unittest.main()
