from __future__ import annotations

from dataclasses import dataclass, replace

from ..branch import (
    BranchRuntime,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from ..core import HardVerifierResult, Ledger, ProposalTrace, TransactionEngine, TypedCandidate


@dataclass(frozen=True)
class BranchSelectionReport:
    schema_version: str
    branch_count: int
    accepted_count: int
    rejected_count: int
    abstained_count: int
    selected_index: int | None
    committed_index: int | None
    loser_count: int
    hard_reject_soft_rank_blocked: bool
    rank_after_hard_filter: bool
    certificate_valid: bool
    audit_valid: bool
    tamper_detected: bool
    invalid_ranker_certificate_valid: bool
    invalid_ranker_committed: bool
    verifier_calls: int
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float


class CounterAdapter:
    verifier_id = "branch_counter_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        delta = int(candidate.payload["delta"])
        cost = int(candidate.payload.get("cost", 0))
        if delta <= 5:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata={"cost": cost})
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"delta": delta, "limit": 5},
            metadata={"cost": cost},
        )

    def apply_commit(self, state: int, candidate: TypedCandidate) -> int:
        return state + int(candidate.payload["delta"])

    def replay(self, state: int, receipt) -> int:
        return state + int(receipt.replay_bundle["candidate_payload"]["delta"])

    def rollback(self, _state: int, receipt) -> int:
        return int(receipt.rollback_bundle["pre_state"])


class CounterProjector:
    def project(self, _state: int, trace: ProposalTrace) -> TypedCandidate:
        return TypedCandidate(dict(trace.actions[-1]), "counter.delta", "counter.delta.v1")


class BadRanker:
    def choose(self, verified) -> int:
        return len(verified)


def run_branch_selection_benchmark() -> BranchSelectionReport:
    engine = TransactionEngine(CounterAdapter(), ledger=Ledger())
    traces = (
        ProposalTrace(
            "rejected-soft-favorite",
            actions=({"delta": 9, "cost": 1, "soft_rank": 999},),
            seeds=(1,),
            model_version="branch.selection.v1",
        ),
        ProposalTrace(
            "accepted-loser",
            actions=({"delta": 1, "cost": 4},),
            seeds=(2,),
            model_version="branch.selection.v1",
        ),
        ProposalTrace(
            "accepted-winner",
            actions=({"delta": 2, "cost": 2},),
            seeds=(3,),
            model_version="branch.selection.v1",
        ),
    )
    outcome = BranchRuntime(engine, CounterProjector()).step(0, traces)
    certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
    tampered = replace(certificate, committed_index=0, certificate_hash="")

    invalid_engine = TransactionEngine(CounterAdapter(), ledger=Ledger())
    invalid_outcome = BranchRuntime(invalid_engine, CounterProjector(), BadRanker()).step(
        0,
        (
            ProposalTrace("bad-ranker-a", actions=({"delta": 1, "cost": 1},), seeds=(4,)),
            ProposalTrace("bad-ranker-b", actions=({"delta": 2, "cost": 2},), seeds=(5,)),
        ),
    )
    invalid_certificate = build_branch_selection_certificate(
        invalid_outcome.receipts,
        verifier_call_count=invalid_outcome.verifier_calls,
    )
    replay_checks = (
        _replay_rollback_ok(engine, 0, outcome.state),
        _replay_rollback_ok(invalid_engine, 0, invalid_outcome.state),
    )

    return BranchSelectionReport(
        schema_version=certificate.schema_version,
        branch_count=certificate.branch_count,
        accepted_count=len(certificate.accepted_indices),
        rejected_count=len(certificate.rejected_indices),
        abstained_count=len(certificate.abstained_indices),
        selected_index=certificate.selected_index,
        committed_index=certificate.committed_index,
        loser_count=len(certificate.loser_indices),
        hard_reject_soft_rank_blocked=(
            engine.ledger.rows[0].hard_result.rejected
            and not engine.ledger.rows[0].committed
            and engine.ledger.rows[0].commit_decision == "hard_reject"
        ),
        rank_after_hard_filter=(
            certificate.selected_index in certificate.accepted_indices
            and certificate.committed_index in certificate.accepted_indices
            and 0 not in certificate.accepted_indices
        ),
        certificate_valid=validate_branch_selection_certificate(certificate),
        audit_valid=audit_branch_selection(outcome.receipts, certificate),
        tamper_detected=not validate_branch_selection_certificate(tampered),
        invalid_ranker_certificate_valid=validate_branch_selection_certificate(invalid_certificate),
        invalid_ranker_committed=invalid_outcome.committed,
        verifier_calls=outcome.verifier_calls,
        invalid_commit_count=engine.invalid_commit_count + invalid_engine.invalid_commit_count,
        ledger_audit=engine.ledger.audit() and invalid_engine.ledger.audit(),
        replay_rollback_rate=sum(1 for ok in replay_checks if ok) / len(replay_checks),
    )


def _replay_rollback_ok(engine: TransactionEngine, seed_state: int, expected_state: int) -> bool:
    if not engine.ledger.audit():
        return False
    return engine.replay_audit(seed_state) == expected_state and engine.rollback_audit(seed_state) == seed_state
