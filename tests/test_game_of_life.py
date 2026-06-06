from __future__ import annotations

import unittest

from trwm.core import TransactionEngine
from trwm.experiments.game_of_life import LifePredecessorAdapter, LifeState, life_step, search_predecessor


class GameOfLifeTests(unittest.TestCase):
    def test_predecessor_search_commits_verified_candidate(self) -> None:
        predecessor = (
            (0, 0, 0),
            (1, 1, 1),
            (0, 0, 0),
        )
        target = life_step(predecessor)
        result = search_predecessor(target)

        self.assertTrue(result.committed)
        self.assertIsNotNone(result.predecessor)
        self.assertEqual(life_step(result.predecessor), target)
        self.assertTrue(result.ledger.audit())
        self.assertGreater(result.verifier_calls, 0)
        self.assertLess(result.verifier_calls, result.baseline_verifier_calls)
        self.assertGreater(result.verifier_call_reduction, 1.0)
        self.assertGreater(result.reversible_trace_count, 0)

    def test_life_replay_and_rollback_audit(self) -> None:
        predecessor = (
            (0, 0, 0),
            (1, 1, 1),
            (0, 0, 0),
        )
        target = life_step(predecessor)
        result = search_predecessor(target)
        adapter = LifePredecessorAdapter()
        engine = TransactionEngine(adapter=adapter, ledger=result.ledger)

        final_state = engine.replay_audit(LifeState(target=target))
        self.assertIsInstance(final_state, LifeState)
        self.assertEqual(engine.rollback_audit(LifeState(target=target)), LifeState(target=target))


if __name__ == "__main__":
    unittest.main()
