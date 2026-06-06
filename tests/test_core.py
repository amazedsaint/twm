from __future__ import annotations

from dataclasses import replace
import unittest
from uuid import uuid4

from trwm.branch import DistributedCommitManager, WorkerReceipt
from trwm.core import (
    HardVerifierResult,
    Ledger,
    ProposalTrace,
    Receipt,
    RuntimeManifest,
    StateSnapshot,
    TransactionEngine,
    TypedCandidate,
    stable_hash,
)


class CounterAdapter:
    verifier_id = "counter_limit"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        delta = candidate.payload["delta"]
        if delta <= 5:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version)
        return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual={"delta": delta})

    def apply_commit(self, state: int, candidate: TypedCandidate) -> int:
        return state + candidate.payload["delta"]

    def replay(self, state: int, receipt) -> int:
        return state + receipt.replay_bundle["candidate_payload"]["delta"]

    def rollback(self, state: int, receipt) -> int:
        return receipt.rollback_bundle["pre_state"]


class CountingAdapter(CounterAdapter):
    def __init__(self) -> None:
        self.apply_commit_calls = 0

    def apply_commit(self, state: int, candidate: TypedCandidate) -> int:
        self.apply_commit_calls += 1
        return super().apply_commit(state, candidate)


def candidate(delta: int) -> TypedCandidate:
    return TypedCandidate({"delta": delta}, "counter.delta", "counter.delta.v1")


def direct_receipt(
    *,
    committed: bool,
    hard_result: HardVerifierResult,
    commit_decision: str,
    manifest: RuntimeManifest | None = None,
) -> Receipt:
    manifest = manifest or RuntimeManifest.current()
    pre = StateSnapshot.capture(0)
    trace = ProposalTrace("direct", actions=({"delta": 1},))
    typed = candidate(1)
    return Receipt(
        receipt_id=str(uuid4()),
        parent_head="",
        pre_state_hash=pre.state_hash,
        post_state_hash=StateSnapshot.capture(1).state_hash if committed else None,
        rollback_state_hash=pre.state_hash,
        branch_id=trace.branch_id,
        proposal_trace_hash=trace.trace_hash,
        typed_candidate_hash=typed.candidate_hash,
        hard_result=hard_result,
        commit_decision=commit_decision,
        committed=committed,
        runtime_manifest=manifest.data,
        replay_bundle={"candidate_payload": typed.payload},
        rollback_bundle={"pre_state": 0},
    )


class CoreTests(unittest.TestCase):
    def test_accepted_transaction_commits_and_audits(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        trace = ProposalTrace("b0", actions=({"delta": 3},))
        outcome = engine.transact(10, trace, candidate(3))

        self.assertTrue(outcome.committed)
        self.assertEqual(outcome.state, 13)
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.replay_audit(10), 13)
        self.assertEqual(engine.rollback_audit(10), 10)

    def test_hard_reject_cannot_commit_even_with_soft_score(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        trace = ProposalTrace("b0", actions=({"delta": 9},))
        outcome = engine.transact(10, trace, candidate(9), soft_scores={"soft": 1.0})

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.state, 10)
        self.assertEqual(engine.invalid_commit_count, 0)
        self.assertEqual(engine.soft_verifier_commit_count, 0)
        self.assertEqual(engine.ledger.rows[0].commit_decision, "hard_reject")

    def test_manifest_mismatch_fails_closed(self) -> None:
        bad_manifest = RuntimeManifest({"schema": "wrong", "runtime": "trwm", "manifest_hash": "bad"})
        engine = TransactionEngine(CounterAdapter(), manifest_factory=lambda: bad_manifest)
        trace = ProposalTrace("b0", actions=({"delta": 1},))
        outcome = engine.transact(10, trace, candidate(1))

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.reason, "manifest_invalid")
        self.assertTrue(engine.ledger.audit())

    def test_verifier_identity_mismatch_fails_closed(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        trace = ProposalTrace("b0", actions=({"delta": 1},))
        fake_accept = HardVerifierResult.accept("soft_proxy", "1.0")
        outcome = engine.transact(10, trace, candidate(1), result=fake_accept)

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.state, 10)
        self.assertEqual(outcome.reason, "verifier_mismatch")
        self.assertEqual(engine.verifier_mismatch_count, 1)
        self.assertTrue(engine.ledger.audit())

    def test_forced_reject_does_not_apply_commit(self) -> None:
        adapter = CountingAdapter()
        engine = TransactionEngine(adapter)
        trace = ProposalTrace("b0", actions=({"delta": 1},))
        outcome = engine.record_evaluated_candidate(
            10,
            trace,
            candidate(1),
            HardVerifierResult.accept("counter_limit", "1.0"),
            force_decision="rolled_back_loser",
        )

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.state, 10)
        self.assertEqual(adapter.apply_commit_calls, 0)
        self.assertEqual(engine.ledger.rows[0].commit_decision, "rolled_back_loser")

    def test_ledger_tamper_detection(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        trace = ProposalTrace("b0", actions=({"delta": 2},))
        engine.transact(10, trace, candidate(2))
        self.assertTrue(engine.ledger.audit())

        engine.ledger.rows[0] = replace(engine.ledger.rows[0], commit_decision="tampered")
        self.assertFalse(engine.ledger.audit())

    def test_canonical_hash_rejects_mapping_key_collision(self) -> None:
        with self.assertRaisesRegex(ValueError, "mapping key collision"):
            stable_hash({1: "integer-key", "1": "string-key"})

    def test_ledger_audit_rejects_self_consistent_invalid_commit(self) -> None:
        ledger = Ledger()
        invalid = direct_receipt(
            committed=True,
            hard_result=HardVerifierResult.reject("counter_limit", "1.0"),
            commit_decision="commit",
        )
        ledger.append(invalid)

        self.assertFalse(ledger.audit())

    def test_replay_audit_refuses_tampered_ledger(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        trace = ProposalTrace("b0", actions=({"delta": 2},))
        engine.transact(10, trace, candidate(2))
        engine.ledger.rows[0] = replace(engine.ledger.rows[0], commit_decision="tampered")

        with self.assertRaisesRegex(AssertionError, "ledger audit failed"):
            engine.replay_audit(10)

    def test_stale_worker_receipt_rejected(self) -> None:
        engine = TransactionEngine(CounterAdapter(), ledger=Ledger())
        manager = DistributedCommitManager(engine)
        trace = ProposalTrace("worker", actions=({"delta": 2},))
        worker = WorkerReceipt(
            parent_head="not-current",
            trace=trace,
            candidate=candidate(2),
            result=HardVerifierResult.accept("counter_limit", "1.0"),
        )
        outcome = manager.commit_one(0, [worker])

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.reason, "no_admissible_worker_receipt")
        self.assertEqual(manager.stale_receipt_rejection_count, 1)
        self.assertEqual(engine.ledger.rows[0].commit_decision, "stale_parent")
        self.assertTrue(engine.ledger.audit())

    def test_current_rejected_worker_receipt_is_recorded(self) -> None:
        engine = TransactionEngine(CounterAdapter(), ledger=Ledger())
        manager = DistributedCommitManager(engine)
        trace = ProposalTrace("worker", actions=({"delta": 9},))
        worker = WorkerReceipt(
            parent_head=engine.ledger.head,
            trace=trace,
            candidate=candidate(9),
            result=HardVerifierResult.reject("counter_limit", "1.0"),
        )
        outcome = manager.commit_one(0, [worker])

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.reason, "no_admissible_worker_receipt")
        self.assertEqual(len(engine.ledger.rows), 1)
        self.assertEqual(engine.ledger.rows[0].commit_decision, "worker_not_accepted")
        self.assertTrue(engine.ledger.audit())


if __name__ == "__main__":
    unittest.main()
