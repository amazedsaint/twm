from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.ancestral import (
    AncestralBranchMemory,
    AncestralContextDescriptor,
    build_ancestral_branch_influence_certificate,
    build_ancestral_branch_retention_certificate,
    build_ancestral_context_refinement_certificate,
    build_ancestral_context_selection_certificate,
    validate_ancestral_branch_influence_certificate,
    validate_ancestral_branch_retention_certificate,
    validate_ancestral_branch_memory_snapshot,
    validate_ancestral_context_refinement_certificate,
    validate_ancestral_context_selection_certificate,
)
from trwm.branch import BranchRuntime, build_branch_selection_certificate
from trwm.core import HardVerifierResult, Ledger, ProposalTrace, TransactionEngine, TypedCandidate
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

    def test_context_selection_certificate_selects_compatible_ancestors(self) -> None:
        target = _context("robotics:target", regime="narrow")
        compatible = _context("robotics:ancestor", regime="narrow")
        misleading = _context("robotics:misleading", regime="wide")

        certificate = build_ancestral_context_selection_certificate(
            target,
            (compatible, misleading),
            required_tag_keys=("regime",),
        )

        self.assertEqual(certificate.selected_context_ids, ("robotics:ancestor",))
        self.assertEqual(certificate.rejected_context_ids, ("robotics:misleading",))
        self.assertEqual(certificate.rejected_reasons, {"robotics:misleading": "tag_mismatch:regime"})
        self.assertTrue(
            validate_ancestral_context_selection_certificate(
                certificate,
                target=target,
                candidates=(compatible, misleading),
            )
        )

    def test_context_selection_certificate_rejects_tampering(self) -> None:
        target = _context("robotics:target", regime="narrow")
        compatible = _context("robotics:ancestor", regime="narrow")
        certificate = build_ancestral_context_selection_certificate(
            target,
            (compatible,),
            required_tag_keys=("regime",),
        )
        tampered = replace(certificate, selected_context_ids=(), certificate_hash="")

        self.assertFalse(
            validate_ancestral_context_selection_certificate(
                tampered,
                target=target,
                candidates=(compatible,),
            )
        )

    def test_context_refinement_certificate_binds_rejected_counterexample(self) -> None:
        target = _context("robotics:target", regime="narrow")
        compatible = _context("robotics:ancestor", regime="narrow")
        misleading = _context("robotics:misleading", regime="wide")
        candidates = (compatible, misleading)
        base = build_ancestral_context_selection_certificate(target, candidates, required_tag_keys=())
        refined = build_ancestral_context_selection_certificate(target, candidates, required_tag_keys=("regime",))
        engine = TransactionEngine(_RejectingAdapter(), ledger=Ledger())
        outcome = engine.transact(
            {"context": "robotics:target"},
            ProposalTrace("counterexample", actions=({"context": "robotics:target", "action": "unsafe"},)),
            TypedCandidate(
                payload={"context": "robotics:target", "action": "unsafe"},
                type_name="refinement.counterexample",
                schema_version="refinement.counterexample.v1",
            ),
        )

        certificate = build_ancestral_context_refinement_certificate(
            target=target,
            candidates=candidates,
            base_selection=base,
            refined_selection=refined,
            counterexample_receipt=outcome.receipt,
            added_required_tag_keys=("regime",),
            refinement_reason="target_reject_from_misleading_context",
        )

        self.assertEqual(base.selected_context_ids, ("robotics:ancestor", "robotics:misleading"))
        self.assertEqual(refined.selected_context_ids, ("robotics:ancestor",))
        self.assertEqual(certificate.newly_rejected_context_ids, ("robotics:misleading",))
        self.assertTrue(
            validate_ancestral_context_refinement_certificate(
                certificate,
                target=target,
                candidates=candidates,
                base_selection=base,
                refined_selection=refined,
                counterexample_receipt=outcome.receipt,
            )
        )

    def test_context_refinement_certificate_rejects_tampering(self) -> None:
        target = _context("robotics:target", regime="narrow")
        compatible = _context("robotics:ancestor", regime="narrow")
        misleading = _context("robotics:misleading", regime="wide")
        candidates = (compatible, misleading)
        base = build_ancestral_context_selection_certificate(target, candidates, required_tag_keys=())
        refined = build_ancestral_context_selection_certificate(target, candidates, required_tag_keys=("regime",))
        engine = TransactionEngine(_RejectingAdapter(), ledger=Ledger())
        outcome = engine.transact(
            {"context": "robotics:target"},
            ProposalTrace("counterexample", actions=({"context": "robotics:target", "action": "unsafe"},)),
            TypedCandidate(
                payload={"context": "robotics:target", "action": "unsafe"},
                type_name="refinement.counterexample",
                schema_version="refinement.counterexample.v1",
            ),
        )
        certificate = build_ancestral_context_refinement_certificate(
            target=target,
            candidates=candidates,
            base_selection=base,
            refined_selection=refined,
            counterexample_receipt=outcome.receipt,
            added_required_tag_keys=("regime",),
            refinement_reason="target_reject_from_misleading_context",
        )
        tampered = replace(certificate, newly_rejected_context_ids=(), certificate_hash="")

        self.assertFalse(
            validate_ancestral_context_refinement_certificate(
                tampered,
                target=target,
                candidates=candidates,
                base_selection=base,
                refined_selection=refined,
                counterexample_receipt=outcome.receipt,
            )
        )

    def test_branch_retention_certificate_binds_memory_delta(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0),
        )
        branch_certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        memory = AncestralBranchMemory()
        retained_context = _branch_context(CONTEXT)
        pre_snapshot = memory.snapshot()
        memory.update_branch(outcome.receipts, branch_certificate)
        post_snapshot = memory.snapshot()

        certificate = build_ancestral_branch_retention_certificate(
            retained_context=retained_context,
            pre_memory_snapshot=pre_snapshot,
            post_memory_snapshot=post_snapshot,
            receipts=outcome.receipts,
            branch_selection_certificate=branch_certificate,
            retention_reason="retain_counterfactual_training_branch",
        )

        self.assertEqual(certificate.retained_context_id, CONTEXT)
        self.assertEqual(certificate.pre_receipt_count, 0)
        self.assertEqual(certificate.post_receipt_count, 3)
        self.assertEqual(certificate.added_receipt_count, 3)
        self.assertEqual(certificate.pre_row_count, 0)
        self.assertEqual(certificate.post_row_count, 3)
        self.assertEqual(certificate.added_row_count, 3)
        self.assertEqual(len(certificate.committed_receipt_hashes), 1)
        self.assertEqual(len(certificate.rejected_receipt_hashes), 1)
        self.assertEqual(len(certificate.rolled_back_receipt_hashes), 1)
        self.assertTrue(
            validate_ancestral_branch_retention_certificate(
                certificate,
                retained_context=retained_context,
                pre_memory_snapshot=pre_snapshot,
                post_memory_snapshot=post_snapshot,
                receipts=outcome.receipts,
                branch_selection_certificate=branch_certificate,
            )
        )

    def test_memory_retain_branch_returns_valid_certificate(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0),
        )
        branch_certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        memory = AncestralBranchMemory()

        certificate = memory.retain_branch(
            _branch_context(CONTEXT),
            outcome.receipts,
            branch_certificate,
            retention_reason="retain_counterfactual_training_branch",
        )

        self.assertTrue(validate_ancestral_branch_retention_certificate(certificate))
        self.assertEqual(memory.rank(CONTEXT, ("a_slow", "b_fast", "c_unsafe"))[0], "b_fast")

    def test_branch_retention_certificate_rejects_tampering(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0),
        )
        branch_certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        memory = AncestralBranchMemory()
        retained_context = _branch_context(CONTEXT)
        pre_snapshot = memory.snapshot()
        memory.update_branch(outcome.receipts, branch_certificate)
        post_snapshot = memory.snapshot()
        certificate = build_ancestral_branch_retention_certificate(
            retained_context=retained_context,
            pre_memory_snapshot=pre_snapshot,
            post_memory_snapshot=post_snapshot,
            receipts=outcome.receipts,
            branch_selection_certificate=branch_certificate,
            retention_reason="retain_counterfactual_training_branch",
        )
        tampered = replace(certificate, post_memory_snapshot_hash="0" * 64, certificate_hash="")

        self.assertFalse(
            validate_ancestral_branch_retention_certificate(
                tampered,
                retained_context=retained_context,
                pre_memory_snapshot=pre_snapshot,
                post_memory_snapshot=post_snapshot,
                receipts=outcome.receipts,
                branch_selection_certificate=branch_certificate,
            )
        )

    def test_branch_influence_certificate_binds_snapshot_ranking(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0),
        )
        branch_certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        memory = AncestralBranchMemory()
        retention = memory.retain_branch(
            _branch_context(CONTEXT),
            outcome.receipts,
            branch_certificate,
            retention_reason="retain_counterfactual_training_branch",
        )
        target_context = _branch_context("counterfactual-target")

        certificate = memory.certify_influence(
            target_context=target_context,
            query_context_ids=(CONTEXT,),
            candidates=("a_slow", "b_fast", "c_unsafe"),
            retention_certificates=(retention,),
            influence_reason="rank_target_candidates_from_retained_branch",
        )

        self.assertEqual(certificate.top_action, "b_fast")
        self.assertEqual(certificate.ranked_actions[0], "b_fast")
        self.assertEqual(certificate.top_action_receipt_hashes, retention.committed_receipt_hashes)
        self.assertEqual(certificate.retention_certificate_hashes, (retention.certificate_hash,))
        self.assertTrue(validate_ancestral_branch_influence_certificate(certificate))
        self.assertTrue(
            validate_ancestral_branch_influence_certificate(
                certificate,
                target_context=target_context,
                memory_snapshot=memory.snapshot(),
                retention_certificates=(retention,),
            )
        )

    def test_branch_influence_certificate_rejects_tampering(self) -> None:
        engine = TransactionEngine(CounterfactualChoiceAdapter(), ledger=Ledger())
        outcome = BranchRuntime(engine, CounterfactualChoiceProjector()).step(
            CounterfactualChoiceState(),
            make_counterfactual_traces(0),
        )
        branch_certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        memory = AncestralBranchMemory()
        retention = memory.retain_branch(
            _branch_context(CONTEXT),
            outcome.receipts,
            branch_certificate,
            retention_reason="retain_counterfactual_training_branch",
        )
        target_context = _branch_context("counterfactual-target")
        certificate = build_ancestral_branch_influence_certificate(
            target_context=target_context,
            memory_snapshot=memory.snapshot(),
            query_context_ids=(CONTEXT,),
            candidates=("a_slow", "b_fast", "c_unsafe"),
            retention_certificates=(retention,),
            influence_reason="rank_target_candidates_from_retained_branch",
        )
        tampered = replace(certificate, ranked_actions=("a_slow", "b_fast", "c_unsafe"), certificate_hash="")

        self.assertFalse(
            validate_ancestral_branch_influence_certificate(
                tampered,
                target_context=target_context,
                memory_snapshot=memory.snapshot(),
                retention_certificates=(retention,),
            )
        )

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


def _context(context_id: str, *, regime: str) -> AncestralContextDescriptor:
    return AncestralContextDescriptor(
        context_id=context_id,
        domain="robotics_replan",
        family="trajectory",
        hard_gate_keys=("clearance", "turn_rate"),
        residual_kinds=("safety_envelope_violation",),
        tags={"regime": regime},
    )


def _branch_context(context_id: str) -> AncestralContextDescriptor:
    return AncestralContextDescriptor(
        context_id=context_id,
        domain="counterfactual_choice",
        family="route_choice",
        hard_gate_keys=("risk",),
        residual_kinds=("risk_limit",),
        tags={"regime": "toy"},
    )


class _RejectingAdapter:
    verifier_id = "refinement_rejecting_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": "target_reject_from_misleading_context"},
        )

    def apply_commit(self, state, candidate: TypedCandidate):
        return state

    def replay(self, state, receipt):
        return state

    def rollback(self, state, receipt):
        return receipt.rollback_bundle["pre_state"]
