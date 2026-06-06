from __future__ import annotations

import unittest

from trwm.core import ProposalTrace, TransactionEngine
from trwm.experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate
from trwm.experiments.residual_topk import TOPK_LIMIT, run_residual_topk_benchmark
from trwm.residuals import ResidualTaxonomyMemory, residual_signal_from_receipt
from trwm.topk import ResidualRepairOption, ResidualTopKSubmitter


class ResidualTopKTests(unittest.TestCase):
    def test_rank_options_prefers_residual_hint(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        engine = TransactionEngine(InventoryReservationAdapter())
        rejected = engine.transact(
            state,
            ProposalTrace(branch_id="reject"),
            make_reservation_candidate(state, "bad", "widget", 8, 8),
        )
        signal = residual_signal_from_receipt(rejected.receipt)
        memory = ResidualTaxonomyMemory()
        memory.update(signal)
        options = (
            _option(state, "quantity-8", 8, 0),
            _option(state, "quantity-7", 7, 1),
            _option(state, "quantity-5", 5, 2),
        )

        ranked = ResidualTopKSubmitter(TransactionEngine(InventoryReservationAdapter()), memory).rank_options(
            options,
            residual_signal=signal,
        )

        self.assertEqual(ranked[0].label, "quantity-5")

    def test_submitter_commits_only_after_hard_verification(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        options = (_option(state, "quantity-5", 5, 0),)
        engine = TransactionEngine(InventoryReservationAdapter())
        outcome = ResidualTopKSubmitter(engine).submit(state, options, top_k=1, trace_prefix="direct")

        self.assertTrue(outcome.committed)
        self.assertEqual(outcome.committed_label, "quantity-5")
        self.assertEqual(outcome.state.stock["widget"], 0)
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.rollback_audit(state), state)

    def test_residual_topk_benchmark_metrics(self) -> None:
        report = run_residual_topk_benchmark()

        self.assertEqual(report.training_residual_kind, "stock_shortage")
        self.assertEqual(report.learned_repair_hint, "quantity=5")
        self.assertEqual(report.candidate_count, 4)
        self.assertEqual(report.top_k, TOPK_LIMIT)
        self.assertEqual(report.unranked_submitted, ("quantity-8", "quantity-7"))
        self.assertFalse(report.unranked_committed)
        self.assertEqual(report.unranked_verifier_calls, 2)
        self.assertEqual(report.residual_ranked_submitted, ("quantity-5",))
        self.assertTrue(report.residual_ranked_committed)
        self.assertEqual(report.residual_ranked_committed_label, "quantity-5")
        self.assertEqual(report.residual_ranked_verifier_calls, 1)
        self.assertEqual(report.calls_to_commit_gain, 2.0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)

    def test_invalid_top_k_fails_closed(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        with self.assertRaises(ValueError):
            ResidualTopKSubmitter(TransactionEngine(InventoryReservationAdapter())).submit(
                state,
                (),
                top_k=-1,
                trace_prefix="bad",
            )


def _option(state: InventoryState, label: str, quantity: int, base_rank: int) -> ResidualRepairOption:
    return ResidualRepairOption(
        label=label,
        candidate=make_reservation_candidate(state, label, "widget", 8, quantity),
        repair_hint=f"quantity={quantity}",
        base_rank=base_rank,
    )


if __name__ == "__main__":
    unittest.main()
