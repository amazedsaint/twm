from __future__ import annotations

import unittest

from trwm.branch import BranchRuntime
from trwm.core import HardVerifierResult, ProposalTrace, TransactionEngine
from trwm.experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate
from trwm.experiments.verifier_guard import (
    FlawedInventoryPrimaryAdapter,
    SAFE_ORDER,
    UNSAFE_ORDER,
    VerifierGuardProjector,
    apply_permissive_inventory_reservation,
    make_verifier_guard_traces,
    run_verifier_guard_benchmark,
)
from trwm.verifier_guard import VerifierAgreementAdapter


class VerifierGuardTests(unittest.TestCase):
    def test_guard_blocks_primary_false_positive(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        candidate = make_reservation_candidate(state, UNSAFE_ORDER, "widget", 8, 8, cost=1)
        guard = VerifierAgreementAdapter(FlawedInventoryPrimaryAdapter(), InventoryReservationAdapter())
        result = guard.verify(candidate)

        self.assertEqual(result.result, "reject")
        self.assertEqual(result.verifier_id, guard.verifier_id)
        self.assertEqual(result.verifier_version, guard.verifier_version)
        self.assertEqual(result.residual["kind"], "verifier_false_positive")
        self.assertEqual(result.residual["audit_residual"]["kind"], "stock_shortage")
        self.assertEqual(guard.primary_calls, 1)
        self.assertEqual(guard.audit_calls, 1)
        self.assertEqual(guard.false_positive_count, 1)

        engine = TransactionEngine(guard)
        outcome = engine.transact(
            state,
            ProposalTrace(branch_id="unsafe", actions=({"order_id": UNSAFE_ORDER},)),
            candidate,
            result=result,
        )
        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.reason, "hard_reject")
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.invalid_commit_count, 0)

    def test_guard_accepts_when_independent_verifiers_agree(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        candidate = make_reservation_candidate(state, SAFE_ORDER, "widget", 3, 3, cost=5)
        guard = VerifierAgreementAdapter(FlawedInventoryPrimaryAdapter(), InventoryReservationAdapter())
        engine = TransactionEngine(guard)
        outcome = engine.transact(
            state,
            ProposalTrace(branch_id="safe", actions=({"order_id": SAFE_ORDER},)),
            candidate,
        )

        self.assertTrue(outcome.committed)
        self.assertEqual(outcome.state.stock["widget"], 2)
        self.assertEqual(outcome.receipt.hard_result.verifier_id, guard.verifier_id)
        self.assertEqual(guard.primary_calls, 1)
        self.assertEqual(guard.audit_calls, 1)
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.rollback_audit(state), state)

    def test_unguarded_branch_width_commits_false_positive(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        engine = TransactionEngine(FlawedInventoryPrimaryAdapter())
        outcome = BranchRuntime(engine, VerifierGuardProjector()).step(state, make_verifier_guard_traces())

        self.assertTrue(outcome.committed)
        self.assertEqual(outcome.state.committed_orders[-1], UNSAFE_ORDER)
        self.assertEqual(outcome.state.stock["widget"], -3)
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.invalid_commit_count, 0)

    def test_benchmark_metrics(self) -> None:
        report = run_verifier_guard_benchmark()

        self.assertEqual(report.branch_count, 2)
        self.assertEqual(report.unguarded_committed_action, UNSAFE_ORDER)
        self.assertEqual(report.unguarded_stock_after, -3)
        self.assertTrue(report.unguarded_negative_stock)
        self.assertTrue(report.unguarded_ledger_audit)
        self.assertEqual(report.unguarded_replay_rollback_rate, 1.0)
        self.assertEqual(report.unguarded_invalid_commit_count, 0)
        self.assertEqual(report.guarded_committed_action, SAFE_ORDER)
        self.assertEqual(report.guarded_stock_after, 2)
        self.assertTrue(report.unsafe_rejected_before_commit)
        self.assertEqual(report.false_positive_count, 1)
        self.assertEqual(report.primary_calls, 2)
        self.assertEqual(report.audit_calls, 2)
        self.assertEqual(report.false_positive_residual_kind, "verifier_false_positive")
        self.assertEqual(report.audit_residual_kind, "stock_shortage")
        self.assertEqual(report.guarded_receipt_decisions, ("hard_reject", "commit"))
        self.assertTrue(report.guarded_ledger_audit)
        self.assertEqual(report.guarded_replay_rollback_rate, 1.0)
        self.assertEqual(report.guarded_invalid_commit_count, 0)

    def test_permissive_adapter_replay_can_restore_negative_stock_path(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        next_state = apply_permissive_inventory_reservation(state, UNSAFE_ORDER, "widget", 8)
        self.assertEqual(next_state.stock["widget"], -3)


class AbstainingAudit:
    verifier_id = "abstaining_audit"
    verifier_version = "1.0"

    def verify(self, candidate):  # noqa: ANN001
        del candidate
        return HardVerifierResult.abstain(self.verifier_id, self.verifier_version, residual={"kind": "manual_review"})


class VerifierGuardAbstainTests(unittest.TestCase):
    def test_audit_abstain_blocks_primary_accept(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        candidate = make_reservation_candidate(state, SAFE_ORDER, "widget", 3, 3)
        guard = VerifierAgreementAdapter(FlawedInventoryPrimaryAdapter(), AbstainingAudit())
        result = guard.verify(candidate)

        self.assertEqual(result.result, "reject")
        self.assertEqual(result.residual["kind"], "verifier_false_positive")
        self.assertEqual(result.residual["audit_result"], "abstain")
        self.assertEqual(guard.false_positive_count, 1)


if __name__ == "__main__":
    unittest.main()
