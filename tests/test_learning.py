from __future__ import annotations

import unittest

from trwm import AdditiveCoupling, BranchRuntime, CounterfactualRollbackRanker, HyperdimensionalMemory, ReceiptRanker
from trwm.core import HardVerifierResult, ProposalTrace, TransactionEngine, TypedCandidate


class ObjectActionAdapter:
    verifier_id = "object_action"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        if candidate.payload["action"] == candidate.payload["defect"]:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version)
        return HardVerifierResult.reject(self.verifier_id, self.verifier_version)

    def apply_commit(self, state, candidate: TypedCandidate):
        return {**state, "solved": True, "action": candidate.payload["action"]}

    def replay(self, state, receipt):
        return {**state, "solved": True, "action": receipt.replay_bundle["candidate_payload"]["action"]}

    def rollback(self, state, receipt):
        return receipt.rollback_bundle["pre_state"]


class LearningTests(unittest.TestCase):
    def test_package_exports_learning_reversible_and_branch_symbols(self) -> None:
        self.assertIsNotNone(ReceiptRanker)
        self.assertIsNotNone(CounterfactualRollbackRanker)
        self.assertIsNotNone(HyperdimensionalMemory)
        self.assertIsNotNone(AdditiveCoupling)
        self.assertIsNotNone(BranchRuntime)

    def test_receipt_ranker_uses_canonical_tokens_for_structured_actions(self) -> None:
        engine = TransactionEngine(ObjectActionAdapter())
        ranker = ReceiptRanker()
        accepted_action = {"b": 2, "a": 1}
        outcome = engine.transact(
            {"context": "objects", "solved": False},
            ProposalTrace(branch_id="object-action", actions=(accepted_action,)),
            TypedCandidate(
                payload={"context": "objects", "action": accepted_action, "defect": {"a": 1, "b": 2}},
                type_name="object.action",
                schema_version="object.action.v1",
            ),
        )
        ranker.update(outcome.receipt)

        ranked = ranker.rank("objects", [{"a": 0}, {"a": 1, "b": 2}])

        self.assertEqual(ranked[0], {"a": 1, "b": 2})
        self.assertTrue(engine.ledger.audit())

    def test_hdc_memory_uses_canonical_tokens_for_structured_queries(self) -> None:
        engine = TransactionEngine(ObjectActionAdapter())
        memory = HyperdimensionalMemory(dimensions=128)
        accepted_action = {"b": 2, "a": 1}
        accepted = engine.transact(
            {"context": "objects", "solved": False},
            ProposalTrace(branch_id="accepted-object", actions=(accepted_action,)),
            TypedCandidate(
                payload={"context": "objects", "action": accepted_action, "defect": {"a": 1, "b": 2}},
                type_name="object.action",
                schema_version="object.action.v1",
            ),
        )
        memory.add(accepted.receipt)

        nearest = memory.nearest({"context": "objects", "action": {"a": 1, "b": 2}}, top_k=1)

        self.assertEqual(nearest[0].branch_id, "accepted-object")

    def test_counterfactual_ranker_penalizes_rolled_back_losers(self) -> None:
        engine = TransactionEngine(ObjectActionAdapter())
        ranker = CounterfactualRollbackRanker()
        state = {"context": "objects", "solved": False}
        committed = engine.transact(
            state,
            ProposalTrace(branch_id="committed", actions=("b_fast",)),
            TypedCandidate(
                payload={"context": "objects", "action": "b_fast", "defect": "b_fast"},
                type_name="object.action",
                schema_version="object.action.v1",
            ),
        )
        loser = engine.record_evaluated_candidate(
            state,
            ProposalTrace(branch_id="loser", actions=("a_slow",)),
            TypedCandidate(
                payload={"context": "objects", "action": "a_slow", "defect": "a_slow"},
                type_name="object.action",
                schema_version="object.action.v1",
            ),
            HardVerifierResult.accept("object_action", "1.0"),
            force_decision="rolled_back_loser",
        )
        rejected = engine.transact(
            state,
            ProposalTrace(branch_id="rejected", actions=("c_unsafe",)),
            TypedCandidate(
                payload={"context": "objects", "action": "c_unsafe", "defect": "other"},
                type_name="object.action",
                schema_version="object.action.v1",
            ),
        )
        for receipt in (committed.receipt, loser.receipt, rejected.receipt):
            ranker.update(receipt)

        self.assertEqual(ranker.rank("objects", ("a_slow", "b_fast", "c_unsafe"))[0], "b_fast")
        self.assertEqual(ranker.stats("objects", "b_fast").committed, 1)
        self.assertEqual(ranker.stats("objects", "a_slow").rolled_back, 1)
        self.assertEqual(ranker.stats("objects", "c_unsafe").rejected, 1)
        self.assertGreater(ranker.score("objects", "b_fast"), ranker.score("objects", "a_slow"))


if __name__ == "__main__":
    unittest.main()
