from __future__ import annotations

import unittest

from trwm.branch import BudgetedBranchRuntime, VerifierBudget, candidate_verifier_cost
from trwm.core import TransactionEngine, TypedCandidate
from trwm.experiments.verifier_budget import (
    BUDGET_LIMIT,
    CHEAP_DECOY as CHEAP_BUDGET_DECOY,
    CHEAP_SOLUTION as CHEAP_BUDGET_SOLUTION,
    EXPENSIVE_SOLUTION as EXPENSIVE_BUDGET_SOLUTION,
    VerifierBudgetAdapter,
    VerifierBudgetProjector,
    VerifierBudgetState,
    make_verifier_budget_traces,
    normalize_verifier_budget_payload,
    run_verifier_budget_benchmark,
)
from trwm.sdk import CostAwareReceiptDomainRouter


class VerifierBudgetTests(unittest.TestCase):
    def test_budgeted_runtime_abstains_before_expensive_verifier(self) -> None:
        engine = TransactionEngine(VerifierBudgetAdapter())
        outcome = BudgetedBranchRuntime(
            engine,
            VerifierBudgetProjector(),
            VerifierBudget(BUDGET_LIMIT),
        ).step(VerifierBudgetState(), make_verifier_budget_traces())

        self.assertTrue(outcome.committed)
        self.assertEqual(outcome.state.committed_actions, (CHEAP_BUDGET_SOLUTION,))
        self.assertEqual(outcome.verifier_calls, 2)
        self.assertEqual(outcome.verifier_cost, 4)
        self.assertEqual(outcome.abstained_count, 1)
        self.assertEqual(engine.hard_verifier_calls, 2)
        self.assertEqual([receipt.commit_decision for receipt in outcome.receipts], ["hard_abstain", "hard_reject", "commit"])
        self.assertEqual(outcome.receipts[0].hard_result.result, "abstain")
        self.assertEqual(outcome.receipts[0].hard_result.residual["kind"], "verifier_budget_exhausted")
        self.assertEqual(outcome.receipts[0].hard_result.residual["required_verifier_cost"], 7)
        self.assertEqual(outcome.receipts[0].hard_result.residual["remaining_budget"], 4)
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.replay_audit(VerifierBudgetState()).committed_actions, (CHEAP_BUDGET_SOLUTION,))
        self.assertEqual(engine.rollback_audit(VerifierBudgetState()), VerifierBudgetState())

    def test_candidate_verifier_cost_validation(self) -> None:
        self.assertEqual(
            candidate_verifier_cost(TypedCandidate(payload={"verifier_cost": "3"}, type_name="x", schema_version="x.v1")),
            3,
        )
        with self.assertRaises(ValueError):
            candidate_verifier_cost(TypedCandidate(payload={"verifier_cost": 0}, type_name="x", schema_version="x.v1"))
        with self.assertRaises(ValueError):
            candidate_verifier_cost(TypedCandidate(payload={"verifier_cost": True}, type_name="x", schema_version="x.v1"))

    def test_payload_requires_boolean_acceptance_flag(self) -> None:
        with self.assertRaises(ValueError):
            normalize_verifier_budget_payload({"action": "x", "plan_cost": 1, "verifier_cost": 1, "accepted": "false"})

    def test_budget_abstain_receipt_is_free_for_cost_router(self) -> None:
        engine = TransactionEngine(VerifierBudgetAdapter())
        outcome = BudgetedBranchRuntime(
            engine,
            VerifierBudgetProjector(),
            VerifierBudget(BUDGET_LIMIT),
        ).step(VerifierBudgetState(), make_verifier_budget_traces())
        router = CostAwareReceiptDomainRouter(default_verifier_cost=5)
        for receipt in outcome.receipts:
            router.update("budgeted_branch", "ctx", receipt)

        stats = router.stats("ctx", "budgeted_branch")
        self.assertEqual(stats.verifier_cost, 4)
        self.assertEqual(stats.accepted, 1)
        self.assertEqual(stats.rejected, 1)
        self.assertEqual(stats.abstained, 1)

    def test_verifier_budget_benchmark_metrics(self) -> None:
        report = run_verifier_budget_benchmark()

        self.assertEqual(report.candidate_count, 3)
        self.assertEqual(report.budget, 4)
        self.assertEqual(report.unbudgeted_verifier_calls, 3)
        self.assertEqual(report.unbudgeted_committed_action, EXPENSIVE_BUDGET_SOLUTION)
        self.assertEqual(report.verifier_calls, 2)
        self.assertEqual(report.verifier_cost, 4)
        self.assertEqual(report.abstained_count, 1)
        self.assertEqual(report.committed_action, CHEAP_BUDGET_SOLUTION)
        self.assertEqual(report.skipped_action, EXPENSIVE_BUDGET_SOLUTION)
        self.assertEqual(report.verified_rejected_action, CHEAP_BUDGET_DECOY)
        self.assertEqual(report.budget_residual_kind, "verifier_budget_exhausted")
        self.assertEqual(report.expensive_required_cost, 7)
        self.assertEqual(report.remaining_budget_before_expensive, 4)
        self.assertEqual(report.receipt_decisions, ("hard_abstain", "hard_reject", "commit"))
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
