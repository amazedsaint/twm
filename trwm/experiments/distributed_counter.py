from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..branch import BranchRuntime, DistributedCommitManager, WorkerReceipt
from ..core import HardVerifierResult, Ledger, ProposalTrace, TransactionEngine, TypedCandidate


@dataclass(frozen=True)
class DistributedCounterReport:
    canonical_state_equal: bool
    canonical_delta_equal: bool
    local_state: int
    distributed_state: int
    local_committed_delta: int | None
    distributed_committed_delta: int | None
    local_verifier_calls: int
    distributed_worker_receipts: int
    stale_parent_rejections: int
    stale_probe_committed: bool
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int


class CounterAdapter:
    verifier_id = "counter_limit"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        delta = int(candidate.payload["delta"])
        cost = int(candidate.payload.get("cost", 0))
        if delta <= 5:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata={"cost": cost})
        return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual={"delta": delta}, metadata={"cost": cost})

    def apply_commit(self, state: int, candidate: TypedCandidate) -> int:
        return state + int(candidate.payload["delta"])

    def replay(self, state: int, receipt) -> int:
        return state + int(receipt.replay_bundle["candidate_payload"]["delta"])

    def rollback(self, state: int, receipt) -> int:
        return int(receipt.rollback_bundle["pre_state"])


class CounterProjector:
    def project(self, _state: int, trace: ProposalTrace) -> TypedCandidate:
        payload = dict(trace.actions[-1])
        return TypedCandidate(payload, "counter.delta", "counter.delta.v1")


def run_distributed_counter_benchmark() -> DistributedCounterReport:
    traces = (
        ProposalTrace("worker-accept-high-cost", actions=({"delta": 4, "cost": 9},), seeds=(1,), model_version="counter.worker.v1"),
        ProposalTrace("worker-reject", actions=({"delta": 9, "cost": 1},), seeds=(2,), model_version="counter.worker.v1"),
        ProposalTrace("worker-accept-low-cost", actions=({"delta": 2, "cost": 1},), seeds=(3,), model_version="counter.worker.v1"),
    )
    local_engine = TransactionEngine(CounterAdapter(), ledger=Ledger())
    local = BranchRuntime(local_engine, CounterProjector()).step(0, traces)

    distributed_engine = TransactionEngine(CounterAdapter(), ledger=Ledger())
    manager = DistributedCommitManager(distributed_engine)
    worker_receipts = tuple(_worker_receipt(distributed_engine.ledger.head, trace) for trace in traces)
    distributed = manager.commit_one(0, worker_receipts)

    stale_engine = TransactionEngine(CounterAdapter(), ledger=Ledger())
    stale_manager = DistributedCommitManager(stale_engine)
    stale_probe = stale_manager.commit_one(
        0,
        (
            WorkerReceipt(
                parent_head=stale_engine.ledger.head,
                trace=ProposalTrace("stale-current-reject", actions=({"delta": 8, "cost": 2},), seeds=(4,)),
                candidate=TypedCandidate({"delta": 8, "cost": 2}, "counter.delta", "counter.delta.v1"),
                result=HardVerifierResult.reject("counter_limit", "1.0", residual={"delta": 8}, metadata={"cost": 2}),
            ),
            WorkerReceipt(
                parent_head="f" * 64,
                trace=ProposalTrace("stale-accepted", actions=({"delta": 1, "cost": 1},), seeds=(5,)),
                candidate=TypedCandidate({"delta": 1, "cost": 1}, "counter.delta", "counter.delta.v1"),
                result=HardVerifierResult.accept("counter_limit", "1.0", metadata={"cost": 1}),
            ),
        ),
    )
    ledgers = (local_engine.ledger, distributed_engine.ledger, stale_engine.ledger)
    replay_checks = (
        _replay_rollback_ok(local_engine, 0, local.state),
        _replay_rollback_ok(distributed_engine, 0, distributed.state),
        stale_engine.ledger.audit(),
    )
    local_delta = _committed_delta(local_engine.ledger.rows)
    distributed_delta = _committed_delta(distributed_engine.ledger.rows)
    return DistributedCounterReport(
        canonical_state_equal=local.state == distributed.state,
        canonical_delta_equal=local_delta == distributed_delta,
        local_state=local.state,
        distributed_state=distributed.state,
        local_committed_delta=local_delta,
        distributed_committed_delta=distributed_delta,
        local_verifier_calls=local.verifier_calls,
        distributed_worker_receipts=distributed.verifier_calls,
        stale_parent_rejections=stale_manager.stale_receipt_rejection_count,
        stale_probe_committed=stale_probe.committed,
        ledger_audit=all(ledger.audit() for ledger in ledgers),
        replay_rollback_rate=sum(1 for ok in replay_checks if ok) / len(replay_checks),
        invalid_commit_count=_invalid_commits(ledgers),
    )


def _worker_receipt(parent_head: str, trace: ProposalTrace) -> WorkerReceipt:
    projector = CounterProjector()
    adapter = CounterAdapter()
    candidate = projector.project(0, trace)
    return WorkerReceipt(parent_head=parent_head, trace=trace, candidate=candidate, result=adapter.verify(candidate))


def _committed_delta(receipts: Iterable) -> int | None:
    for receipt in receipts:
        if receipt.committed:
            return int(receipt.replay_bundle["candidate_payload"]["delta"])
    return None


def _replay_rollback_ok(engine: TransactionEngine, seed_state: int, expected_state: int) -> bool:
    if not engine.ledger.audit():
        return False
    return engine.replay_audit(seed_state) == expected_state and engine.rollback_audit(seed_state) == seed_state


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
