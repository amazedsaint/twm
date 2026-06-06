from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.ancestral import AncestralBranchMemory, validate_ancestral_branch_memory_snapshot
from trwm.branch import BranchRuntime, build_branch_selection_certificate
from trwm.core import Ledger, TransactionEngine
from trwm.experiments.counterfactual_learning import (
    CONTEXT,
    CounterfactualChoiceAdapter,
    CounterfactualChoiceProjector,
    CounterfactualChoiceState,
    make_counterfactual_traces,
)


class AncestralBranchMemoryTests(unittest.TestCase):
    def test_memory_learns_from_audited_branch_receipts(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0),
        )
        certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        memory = AncestralBranchMemory()

        memory.update_branch(outcome.receipts, certificate)
        memory.update_branch(outcome.receipts, certificate)
        snapshot = memory.snapshot()

        self.assertEqual(memory.rank(CONTEXT, ("a_slow", "b_fast", "c_unsafe"))[0], "b_fast")
        self.assertEqual(memory.stats(CONTEXT, "b_fast").committed, 1)
        self.assertEqual(memory.stats(CONTEXT, "a_slow").rolled_back, 1)
        self.assertEqual(memory.stats(CONTEXT, "c_unsafe").rejected, 1)
        self.assertEqual(snapshot.receipt_hashes, tuple(receipt.receipt_hash for receipt in outcome.receipts))
        self.assertEqual(snapshot.branch_selection_certificate_hashes, (certificate.certificate_hash,))
        self.assertEqual(len(snapshot.rows), 3)
        self.assertTrue(validate_ancestral_branch_memory_snapshot(snapshot))

    def test_invalid_branch_selection_certificate_is_rejected_before_learning(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0),
        )
        certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        tampered = replace(certificate, committed_index=0, certificate_hash="")
        memory = AncestralBranchMemory()

        with self.assertRaises(ValueError):
            memory.update_branch(outcome.receipts, tampered)

    def test_memory_ranks_from_explicit_ancestor_contexts(self) -> None:
        source_context = "source-route"
        target_candidates = ("a_slow", "b_fast", "c_unsafe")
        actions = tuple(
            {**dict(action), "context": source_context}
            for action in (
                {"action": "a_slow", "cost": 2, "risk": 0.10},
                {"action": "b_fast", "cost": 1, "risk": 0.20},
                {"action": "c_unsafe", "cost": 0, "risk": 1.20},
            )
        )
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0, actions),
        )
        certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        memory = AncestralBranchMemory()
        memory.update_branch(outcome.receipts, certificate)

        ranked = memory.rank_from_contexts((source_context,), target_candidates)
        stats = memory.stats_from_contexts((source_context,), "b_fast")

        self.assertEqual(ranked[0], "b_fast")
        self.assertEqual(stats.committed, 1)
        self.assertEqual(stats.rolled_back, 0)
        self.assertEqual(len(stats.receipt_hashes), 1)

    def test_missing_ancestor_context_preserves_candidate_order(self) -> None:
        memory = AncestralBranchMemory()

        self.assertEqual(memory.rank_from_contexts(("missing-context",), ("z", "a", "m")), ["z", "a", "m"])

    def test_empty_ancestor_context_fails_closed(self) -> None:
        memory = AncestralBranchMemory()

        with self.assertRaises(ValueError):
            memory.rank_from_contexts(("",), ("a", "b"))

    def test_snapshot_tampering_fails_validation(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0),
        )
        certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        memory = AncestralBranchMemory()
        memory.update_branch(outcome.receipts, certificate)
        snapshot = memory.snapshot()
        first_row = replace(snapshot.rows[0], committed=snapshot.rows[0].committed + 1)
        tampered = replace(snapshot, rows=(first_row, *snapshot.rows[1:]), snapshot_hash="")

        self.assertFalse(validate_ancestral_branch_memory_snapshot(tampered))


if __name__ == "__main__":
    unittest.main()
