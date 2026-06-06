from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.budget_policy import BudgetCandidate, ReceiptBudgetPolicy, validate_budget_policy_snapshot
from trwm.core import ProposalTrace, TransactionEngine
from trwm.experiments.budget_policy import BUDGET_POLICY_LIMIT, run_budget_policy_benchmark
from trwm.experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate


class BudgetPolicyTests(unittest.TestCase):
    def test_plan_selects_receipt_grounded_repair_under_budget(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        policy = _trained_policy(state)
        plan = policy.plan(_candidates(state), BUDGET_POLICY_LIMIT)

        self.assertEqual(tuple(row.label for row in plan.selected), ("quantity-5",))
        self.assertEqual(plan.spent, 3)
        self.assertEqual(plan.expected_utility, 1.03271645737)
        self.assertEqual(policy.score("quantity-5").success_lower_bound, 0.206543291474)

    def test_plan_is_fail_closed_when_only_zero_utility_candidates_fit(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        policy = _trained_policy(state)
        plan = policy.plan(_candidates(state), budget=2)

        self.assertEqual(plan.selected, ())
        self.assertEqual(plan.spent, 0)
        self.assertEqual(plan.expected_utility, 0.0)

    def test_submitter_commits_only_after_hard_verification(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        policy = _trained_policy(state)
        engine = TransactionEngine(InventoryReservationAdapter())
        outcome = policy.submit(engine, state, _candidates(state), budget=BUDGET_POLICY_LIMIT, trace_prefix="budget")

        self.assertTrue(outcome.committed)
        self.assertEqual(outcome.committed_label, "quantity-5")
        self.assertEqual(outcome.selected_labels, ("quantity-5",))
        self.assertEqual(outcome.submitted_labels, ("quantity-5",))
        self.assertEqual(outcome.verifier_cost_spent, 3)
        self.assertEqual(len(outcome.receipts), 1)
        self.assertEqual(outcome.state.stock["widget"], 0)
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.rollback_audit(state), state)

    def test_snapshot_validation_detects_tampering(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        policy = _trained_policy(state)
        snapshot = policy.snapshot()
        tampered = replace(snapshot, rows=tuple(replace(row, failures=0) for row in snapshot.rows))

        self.assertTrue(validate_budget_policy_snapshot(snapshot))
        self.assertFalse(validate_budget_policy_snapshot(tampered))

    def test_invalid_policy_inputs_fail_closed(self) -> None:
        state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
        policy = ReceiptBudgetPolicy()

        with self.assertRaises(ValueError):
            policy.plan((), -1)
        with self.assertRaises(ValueError):
            BudgetCandidate(
                label="bad",
                token="bad",
                candidate=make_reservation_candidate(state, "bad", "widget", 8, 1),
                verifier_cost=0,
            )

    def test_budget_policy_benchmark_metrics(self) -> None:
        report = run_budget_policy_benchmark()

        self.assertEqual(report.training_receipt_count, 3)
        self.assertEqual(report.budget, BUDGET_POLICY_LIMIT)
        self.assertEqual(report.candidate_count, 4)
        self.assertEqual(report.learned_success_token, "quantity-5")
        self.assertEqual(report.learned_success_lower_bound, 0.206543291474)
        self.assertEqual(report.cheap_first_selected, ("quantity-8", "quantity-7"))
        self.assertFalse(report.cheap_first_committed)
        self.assertEqual(report.cheap_first_verifier_calls, 2)
        self.assertEqual(report.cheap_first_cost_spent, 2)
        self.assertEqual(report.learned_selected, ("quantity-5",))
        self.assertTrue(report.learned_committed)
        self.assertEqual(report.learned_committed_label, "quantity-5")
        self.assertEqual(report.learned_verifier_calls, 1)
        self.assertEqual(report.learned_cost_spent, 3)
        self.assertEqual(report.learned_expected_utility, 1.03271645737)
        self.assertEqual(report.verifier_call_gain, 2.0)
        self.assertAlmostEqual(report.verifier_cost_ratio, 2 / 3)
        self.assertEqual(report.evaluation_receipt_count, 1)
        self.assertTrue(report.heldout_trace_disjoint)
        self.assertTrue(report.snapshot_valid)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)


def _trained_policy(state: InventoryState) -> ReceiptBudgetPolicy:
    policy = ReceiptBudgetPolicy()
    engine = TransactionEngine(InventoryReservationAdapter())
    for label, quantity in (("quantity-5", 5), ("quantity-8", 8), ("quantity-7", 7)):
        receipt = engine.transact(
            state,
            ProposalTrace(branch_id=f"train-{label}", actions=({"label": label},)),
            make_reservation_candidate(state, label, "widget", 8, quantity),
        ).receipt
        policy.update(label, receipt)
    return policy


def _candidates(state: InventoryState) -> tuple[BudgetCandidate, ...]:
    costs = {8: 1, 7: 1, 5: 3, 4: 2}
    return tuple(
        BudgetCandidate(
            label=f"quantity-{quantity}",
            token=f"quantity-{quantity}",
            candidate=make_reservation_candidate(state, f"q{quantity}", "widget", 8, quantity, cost=costs[quantity]),
            verifier_cost=costs[quantity],
            reward=float(quantity),
            base_rank=idx,
        )
        for idx, quantity in enumerate((8, 7, 5, 4))
    )


if __name__ == "__main__":
    unittest.main()
