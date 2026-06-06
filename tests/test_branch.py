from __future__ import annotations

import unittest

from trwm.branch import BranchRuntime, DistributedCommitManager, WorkerReceipt
from trwm.core import HardVerifierResult, ProposalTrace, TransactionEngine, TypedCandidate
from trwm.experiments.distributed_counter import run_distributed_counter_benchmark
from tests.test_core import CounterAdapter


class DeltaProjector:
    def project(self, _state, trace: ProposalTrace) -> TypedCandidate:
        return TypedCandidate({"delta": trace.actions[-1]["delta"]}, "counter.delta", "counter.delta.v1")


class BadRanker:
    def choose(self, verified):
        return len(verified)


class BranchTests(unittest.TestCase):
    def test_invalid_ranker_choice_fails_closed(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        runtime = BranchRuntime(engine, DeltaProjector(), BadRanker())
        traces = (
            ProposalTrace("a", actions=({"delta": 1},)),
            ProposalTrace("b", actions=({"delta": 2},)),
        )
        outcome = runtime.step(0, traces)

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.reason, "ranker_invalid_choice")
        self.assertEqual(len(engine.ledger.rows), 2)
        self.assertTrue(all(row.commit_decision == "ranker_invalid_choice" for row in engine.ledger.rows))
        self.assertTrue(engine.ledger.audit())

    def test_distributed_execution_matches_local_canonical_result(self) -> None:
        report = run_distributed_counter_benchmark()

        self.assertTrue(report.canonical_state_equal)
        self.assertTrue(report.canonical_delta_equal)
        self.assertEqual(report.local_state, 2)
        self.assertEqual(report.distributed_state, 2)
        self.assertEqual(report.local_committed_delta, 2)
        self.assertEqual(report.distributed_committed_delta, 2)
        self.assertEqual(report.local_verifier_calls, 3)
        self.assertEqual(report.distributed_worker_receipts, 3)
        self.assertEqual(report.stale_parent_rejections, 1)
        self.assertFalse(report.stale_probe_committed)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)

    def test_distributed_ranker_choice_fails_closed(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        manager = DistributedCommitManager(engine, ranker=BadRanker())
        receipt = WorkerReceipt(
            parent_head=engine.ledger.head,
            trace=ProposalTrace("accepted", actions=({"delta": 1},)),
            candidate=TypedCandidate({"delta": 1}, "counter.delta", "counter.delta.v1"),
            result=HardVerifierResult.accept("counter_limit", "1.0"),
        )
        outcome = manager.commit_one(0, (receipt,))

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.reason, "ranker_invalid_choice")
        self.assertEqual(engine.ledger.rows[0].commit_decision, "ranker_invalid_choice")
        self.assertTrue(engine.ledger.audit())


if __name__ == "__main__":
    unittest.main()
