from __future__ import annotations

import unittest

from trwm.experiments.counterfactual_learning import (
    CONTEXT,
    CounterfactualChoiceAdapter,
    CounterfactualChoiceState,
    CounterfactualChoiceProjector,
    make_counterfactual_traces,
    run_counterfactual_rollback_benchmark,
)
from trwm.branch import BranchRuntime
from trwm.core import Ledger, TransactionEngine
from trwm.learning import CounterfactualRollbackRanker, ReceiptRanker


class CounterfactualLearningTests(unittest.TestCase):
    def test_branch_receipts_expose_rolled_back_loser_evidence(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        runtime = BranchRuntime(engine, CounterfactualChoiceProjector())
        outcome = runtime.step(CounterfactualChoiceState(), make_counterfactual_traces(0))

        decisions = [receipt.commit_decision for receipt in outcome.receipts]

        self.assertTrue(outcome.committed)
        self.assertEqual(outcome.state.committed_actions, ("b_fast",))
        self.assertEqual(decisions, ["rolled_back_loser", "commit", "hard_reject"])
        self.assertTrue(engine.ledger.audit())

    def test_counterfactual_ranker_uses_rollback_evidence_where_receipt_ranker_ties(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        runtime = BranchRuntime(engine, CounterfactualChoiceProjector())
        outcome = runtime.step(CounterfactualChoiceState(), make_counterfactual_traces(0))
        receipt_ranker = ReceiptRanker()
        counterfactual_ranker = CounterfactualRollbackRanker()
        for receipt in outcome.receipts:
            receipt_ranker.update(receipt)
            counterfactual_ranker.update(receipt)

        candidates = ("a_slow", "b_fast", "c_unsafe")

        self.assertEqual(receipt_ranker.rank(CONTEXT, candidates)[0], "a_slow")
        self.assertEqual(counterfactual_ranker.rank(CONTEXT, candidates)[0], "b_fast")
        self.assertEqual(counterfactual_ranker.stats(CONTEXT, "a_slow").rolled_back, 1)

    def test_counterfactual_rollback_benchmark_metrics(self) -> None:
        report = run_counterfactual_rollback_benchmark(episodes=12)

        self.assertEqual(report.episodes, 12)
        self.assertEqual(report.candidate_count, 3)
        self.assertEqual(report.committed_action, "b_fast")
        self.assertEqual(report.static_top_action, "a_slow")
        self.assertEqual(report.receipt_ranker_top_action, "a_slow")
        self.assertEqual(report.counterfactual_top_action, "b_fast")
        self.assertEqual(report.receipt_ranker_winner_rank, 2)
        self.assertEqual(report.counterfactual_winner_rank, 1)
        self.assertEqual(report.rolled_back_loser_count, 12)
        self.assertEqual(report.hard_reject_count, 12)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
