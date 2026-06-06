from __future__ import annotations

import unittest

from trwm.core import Ledger
from trwm.experiments.operations import (
    InventoryReservationAdapter,
    InventoryResidualRepairer,
    InventoryState,
    apply_inventory_reservation,
    make_reservation_candidate,
    run_operations_benchmark,
    run_repair_operations_episode,
    run_static_operations_episode,
)


class OperationsTests(unittest.TestCase):
    def test_reservation_preserves_accounting_units(self) -> None:
        state = InventoryState(stock={"A": 8}, reserved={"A": 2})
        next_state = apply_inventory_reservation(state, "o1", "A", 3)

        self.assertEqual(next_state.stock["A"], 5)
        self.assertEqual(next_state.reserved["A"], 5)
        self.assertEqual(state.stock["A"] + state.reserved["A"], next_state.stock["A"] + next_state.reserved["A"])
        self.assertEqual(next_state.committed_orders, ("o1",))

    def test_hard_verifier_rejects_stock_shortage_with_repair(self) -> None:
        state = InventoryState(stock={"A": 5}, reserved={"A": 0})
        candidate = make_reservation_candidate(state, "o2", "A", requested=9, quantity=9)

        result = InventoryReservationAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "stock_shortage")
        self.assertEqual(result.residual["repair"], {"quantity": 5})

    def test_residual_repair_commits_after_shortage_feedback(self) -> None:
        state = InventoryState(stock={"A": 5}, reserved={"A": 0})
        ledger = Ledger()
        result = run_repair_operations_episode(state, "o3", "A", requested=9, ledger=ledger, repairer=InventoryResidualRepairer(), episode=1)

        self.assertEqual(result.calls, 2)
        self.assertTrue(result.success)
        self.assertTrue(result.audit_ok)
        self.assertTrue(result.replay_rollback_ok)
        self.assertEqual(len(ledger.committed_rows()), 1)

    def test_operations_benchmark_improves_over_static_quantity_search(self) -> None:
        report = run_operations_benchmark(seed=37, episodes=48)

        self.assertEqual(report.episodes, 48)
        self.assertEqual(report.repair_success_rate, 1.0)
        self.assertEqual(report.ledger_audit_rate, 1.0)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertLess(report.repair_calls_per_success, report.static_calls_per_success)
        self.assertGreater(report.repair_gain, 2.0)
        self.assertGreater(report.learned_residual_kinds.get("stock_shortage", 0), 0)

    def test_static_episode_uses_same_quantity_candidates(self) -> None:
        state = InventoryState(stock={"A": 3}, reserved={"A": 0})
        result = run_static_operations_episode(state, "o4", "A", requested=5, ledger=Ledger(), episode=4)

        self.assertEqual(result.calls, 3)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
