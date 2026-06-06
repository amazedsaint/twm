from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Protocol

from .core import HardVerifierResult, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


BRANCH_SELECTION_CERTIFICATE_SCHEMA = "trwm.branch_selection_certificate.v1"


class BranchProjector(Protocol):
    def project(self, state: Any, trace: ProposalTrace) -> TypedCandidate:
        ...


class BranchRanker(Protocol):
    def choose(self, verified: list[tuple[ProposalTrace, TypedCandidate, HardVerifierResult]]) -> int:
        ...


class LowestCostRanker:
    def choose(self, verified: list[tuple[ProposalTrace, TypedCandidate, HardVerifierResult]]) -> int:
        best_idx = 0
        best_cost = float("inf")
        for idx, (_, candidate, result) in enumerate(verified):
            cost = result.metadata.get("cost", 0)
            energy = result.metadata.get("energy", 0)
            soft_rank = 0
            if isinstance(candidate.payload, dict):
                soft_rank = candidate.payload.get("soft_rank", 0)
            value = cost + energy - soft_rank
            if value < best_cost:
                best_idx = idx
                best_cost = value
        return best_idx


@dataclass(frozen=True)
class BranchOutcome:
    state: Any
    committed: bool
    receipts: tuple[Any, ...]
    verifier_calls: int
    reason: str
    verifier_cost: int = 0
    abstained_count: int = 0


@dataclass(frozen=True)
class BranchSelectionCertificate:
    schema_version: str
    branch_count: int
    verifier_call_count: int
    accepted_indices: tuple[int, ...]
    rejected_indices: tuple[int, ...]
    abstained_indices: tuple[int, ...]
    loser_indices: tuple[int, ...]
    selected_index: int | None
    committed_index: int | None
    receipt_hashes: tuple[str, ...]
    proposal_trace_hashes: tuple[str, ...]
    typed_candidate_hashes: tuple[str, ...]
    hard_results: tuple[str, ...]
    commit_decisions: tuple[str, ...]
    committed_flags: tuple[bool, ...]
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BRANCH_SELECTION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid branch selection certificate schema: {self.schema_version}")
        if not isinstance(self.branch_count, int) or isinstance(self.branch_count, bool) or self.branch_count < 0:
            raise ValueError("branch_count must be a non-negative integer")
        if (
            not isinstance(self.verifier_call_count, int)
            or isinstance(self.verifier_call_count, bool)
            or self.verifier_call_count < 0
        ):
            raise ValueError("verifier_call_count must be a non-negative integer")
        for field_name in (
            "accepted_indices",
            "rejected_indices",
            "abstained_indices",
            "loser_indices",
            "receipt_hashes",
            "proposal_trace_hashes",
            "typed_candidate_hashes",
            "hard_results",
            "commit_decisions",
            "committed_flags",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        for field_name in ("selected_index", "committed_index"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                raise ValueError(f"{field_name} must be an integer or None")
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", branch_selection_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class VerifierBudget:
    max_cost: int

    def __post_init__(self) -> None:
        if not isinstance(self.max_cost, int) or isinstance(self.max_cost, bool) or self.max_cost < 0:
            raise ValueError("max_cost must be a non-negative integer")


class BranchRuntime:
    def __init__(
        self,
        engine: TransactionEngine,
        projector: BranchProjector,
        ranker: BranchRanker | None = None,
    ):
        self.engine = engine
        self.projector = projector
        self.ranker = ranker or LowestCostRanker()

    def step(self, state: Any, traces: Iterable[ProposalTrace]) -> BranchOutcome:
        evaluated: list[tuple[ProposalTrace, TypedCandidate, HardVerifierResult]] = []
        receipts = []
        for trace in traces:
            candidate = self.projector.project(state, trace)
            result = self.engine.adapter.verify(candidate)
            self.engine.hard_verifier_calls += 1
            evaluated.append((trace, candidate, result))

        verified = [row for row in evaluated if row[2].accepted]
        if not verified:
            for trace, candidate, result in evaluated:
                outcome = self.engine.record_evaluated_candidate(
                    state,
                    trace,
                    candidate,
                    result,
                    force_decision="no_admissible_branch",
                )
                receipts.append(outcome.receipt)
            return BranchOutcome(state, False, tuple(receipts), len(evaluated), "no_admissible_branch")

        winner_idx = self.ranker.choose(verified)
        if not isinstance(winner_idx, int) or not 0 <= winner_idx < len(verified):
            for trace, candidate, result in evaluated:
                outcome = self.engine.record_evaluated_candidate(
                    state,
                    trace,
                    candidate,
                    result,
                    force_decision="ranker_invalid_choice",
                )
                receipts.append(outcome.receipt)
            return BranchOutcome(state, False, tuple(receipts), len(evaluated), "ranker_invalid_choice")
        winner = verified[winner_idx]
        winner_trace_hash = winner[0].trace_hash
        final_state = state
        committed = False
        reason = "commit"

        for trace, candidate, result in evaluated:
            force = None
            if result.accepted and trace.trace_hash != winner_trace_hash:
                force = "rolled_back_loser"
            outcome = self.engine.record_evaluated_candidate(state, trace, candidate, result, force_decision=force)
            receipts.append(outcome.receipt)
            if trace.trace_hash == winner_trace_hash:
                final_state = outcome.state
                committed = outcome.committed
                reason = outcome.reason

        return BranchOutcome(final_state, committed, tuple(receipts), len(evaluated), reason)


class BudgetedBranchRuntime:
    def __init__(
        self,
        engine: TransactionEngine,
        projector: BranchProjector,
        budget: VerifierBudget,
        ranker: BranchRanker | None = None,
        *,
        default_verifier_cost: int = 1,
    ):
        if not isinstance(default_verifier_cost, int) or isinstance(default_verifier_cost, bool) or default_verifier_cost <= 0:
            raise ValueError("default_verifier_cost must be a positive integer")
        self.engine = engine
        self.projector = projector
        self.budget = budget
        self.ranker = ranker or LowestCostRanker()
        self.default_verifier_cost = default_verifier_cost

    def step(self, state: Any, traces: Iterable[ProposalTrace]) -> BranchOutcome:
        evaluated: list[tuple[ProposalTrace, TypedCandidate, HardVerifierResult]] = []
        receipts = []
        spent = 0
        verifier_calls = 0
        abstained_count = 0
        for trace in traces:
            candidate = self.projector.project(state, trace)
            cost = candidate_verifier_cost(candidate, default=self.default_verifier_cost)
            remaining = self.budget.max_cost - spent
            if cost > remaining:
                abstained_count += 1
                result = HardVerifierResult.abstain(
                    self.engine.adapter.verifier_id,
                    self.engine.adapter.verifier_version,
                    residual={
                        "kind": "verifier_budget_exhausted",
                        "required_verifier_cost": cost,
                        "remaining_budget": max(0, remaining),
                        "budget": self.budget.max_cost,
                    },
                    metadata={
                        "verifier_cost_spent": 0,
                        "required_verifier_cost": cost,
                        "remaining_budget": max(0, remaining),
                        "budget": self.budget.max_cost,
                    },
                )
            else:
                result = self.engine.adapter.verify(candidate)
                result = _with_verifier_cost_metadata(result, cost, spent + cost, self.budget.max_cost)
                spent += cost
                verifier_calls += 1
                self.engine.hard_verifier_calls += 1
            evaluated.append((trace, candidate, result))

        verified = [row for row in evaluated if row[2].accepted]
        if not verified:
            for trace, candidate, result in evaluated:
                outcome = self.engine.record_evaluated_candidate(
                    state,
                    trace,
                    candidate,
                    result,
                    force_decision="no_admissible_branch",
                )
                receipts.append(outcome.receipt)
            return BranchOutcome(state, False, tuple(receipts), verifier_calls, "no_admissible_branch", spent, abstained_count)

        winner_idx = self.ranker.choose(verified)
        if not isinstance(winner_idx, int) or not 0 <= winner_idx < len(verified):
            for trace, candidate, result in evaluated:
                outcome = self.engine.record_evaluated_candidate(
                    state,
                    trace,
                    candidate,
                    result,
                    force_decision="ranker_invalid_choice",
                )
                receipts.append(outcome.receipt)
            return BranchOutcome(state, False, tuple(receipts), verifier_calls, "ranker_invalid_choice", spent, abstained_count)

        winner = verified[winner_idx]
        winner_trace_hash = winner[0].trace_hash
        final_state = state
        committed = False
        reason = "commit"
        for trace, candidate, result in evaluated:
            force = None
            if result.accepted and trace.trace_hash != winner_trace_hash:
                force = "rolled_back_loser"
            outcome = self.engine.record_evaluated_candidate(state, trace, candidate, result, force_decision=force)
            receipts.append(outcome.receipt)
            if trace.trace_hash == winner_trace_hash:
                final_state = outcome.state
                committed = outcome.committed
                reason = outcome.reason

        return BranchOutcome(final_state, committed, tuple(receipts), verifier_calls, reason, spent, abstained_count)


@dataclass(frozen=True)
class WorkerReceipt:
    parent_head: str
    trace: ProposalTrace
    candidate: TypedCandidate
    result: HardVerifierResult


class DistributedCommitManager:
    def __init__(self, engine: TransactionEngine, ranker: BranchRanker | None = None):
        self.engine = engine
        self.ranker = ranker or LowestCostRanker()
        self.stale_receipt_rejection_count = 0

    def commit_one(self, state: Any, worker_receipts: Iterable[WorkerReceipt]) -> BranchOutcome:
        expected_parent_head = self.engine.ledger.head
        worker_receipts = list(worker_receipts)
        accepted: list[WorkerReceipt] = []
        receipts = []
        for worker_receipt in worker_receipts:
            if worker_receipt.parent_head != expected_parent_head:
                self.stale_receipt_rejection_count += 1
                continue
            if worker_receipt.result.accepted:
                accepted.append(worker_receipt)

        if not accepted:
            for worker_receipt in worker_receipts:
                force = "stale_parent" if worker_receipt.parent_head != expected_parent_head else "worker_not_accepted"
                outcome = self.engine.record_evaluated_candidate(
                    state,
                    worker_receipt.trace,
                    worker_receipt.candidate,
                    worker_receipt.result,
                    force_decision=force,
                )
                receipts.append(outcome.receipt)
            return BranchOutcome(state, False, tuple(receipts), len(worker_receipts), "no_admissible_worker_receipt")

        winner_idx = self.ranker.choose([(row.trace, row.candidate, row.result) for row in accepted])
        if not isinstance(winner_idx, int) or not 0 <= winner_idx < len(accepted):
            for worker_receipt in worker_receipts:
                force = "stale_parent" if worker_receipt.parent_head != expected_parent_head else "ranker_invalid_choice"
                outcome = self.engine.record_evaluated_candidate(
                    state,
                    worker_receipt.trace,
                    worker_receipt.candidate,
                    worker_receipt.result,
                    force_decision=force,
                )
                receipts.append(outcome.receipt)
            return BranchOutcome(state, False, tuple(receipts), len(worker_receipts), "ranker_invalid_choice")

        chosen = accepted[winner_idx]
        chosen_hash = chosen.trace.trace_hash
        final_state = state
        committed = False
        reason = "commit"
        for worker_receipt in worker_receipts:
            force = None
            if worker_receipt.parent_head != expected_parent_head:
                force = "stale_parent"
            elif not worker_receipt.result.accepted:
                force = "worker_not_accepted"
            elif worker_receipt.trace.trace_hash != chosen_hash:
                force = "rolled_back_loser"
            outcome = self.engine.record_evaluated_candidate(
                state,
                worker_receipt.trace,
                worker_receipt.candidate,
                worker_receipt.result,
                force_decision=force,
            )
            receipts.append(outcome.receipt)
            if worker_receipt.trace.trace_hash == chosen_hash:
                final_state = outcome.state
                committed = outcome.committed
                reason = outcome.reason
        return BranchOutcome(final_state, committed, tuple(receipts), len(worker_receipts), reason)


def build_branch_selection_certificate(
    receipts: Iterable[Receipt],
    *,
    verifier_call_count: int | None = None,
) -> BranchSelectionCertificate:
    rows = tuple(receipts)
    accepted_indices = tuple(idx for idx, receipt in enumerate(rows) if receipt.hard_result.accepted)
    rejected_indices = tuple(idx for idx, receipt in enumerate(rows) if receipt.hard_result.rejected)
    abstained_indices = tuple(idx for idx, receipt in enumerate(rows) if receipt.hard_result.abstained)
    loser_indices = tuple(idx for idx, receipt in enumerate(rows) if receipt.commit_decision == "rolled_back_loser")
    committed_indices = tuple(
        idx for idx, receipt in enumerate(rows) if receipt.committed and receipt.commit_decision == "commit"
    )
    selected_candidates = tuple(
        idx
        for idx in accepted_indices
        if idx not in loser_indices
        and rows[idx].commit_decision not in {"ranker_invalid_choice", "no_admissible_branch"}
    )
    selected_index = selected_candidates[0] if len(selected_candidates) == 1 else None
    committed_index = committed_indices[0] if len(committed_indices) == 1 else None
    return BranchSelectionCertificate(
        schema_version=BRANCH_SELECTION_CERTIFICATE_SCHEMA,
        branch_count=len(rows),
        verifier_call_count=len(rows) if verifier_call_count is None else verifier_call_count,
        accepted_indices=accepted_indices,
        rejected_indices=rejected_indices,
        abstained_indices=abstained_indices,
        loser_indices=loser_indices,
        selected_index=selected_index,
        committed_index=committed_index,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in rows),
        proposal_trace_hashes=tuple(receipt.proposal_trace_hash for receipt in rows),
        typed_candidate_hashes=tuple(receipt.typed_candidate_hash for receipt in rows),
        hard_results=tuple(receipt.hard_result.result for receipt in rows),
        commit_decisions=tuple(receipt.commit_decision for receipt in rows),
        committed_flags=tuple(receipt.committed for receipt in rows),
    )


def audit_branch_selection(receipts: Iterable[Receipt], certificate: BranchSelectionCertificate) -> bool:
    try:
        rows = tuple(receipts)
        if not validate_branch_selection_certificate(certificate):
            return False
        if len(rows) != certificate.branch_count:
            return False
        if any(not receipt.static_valid() for receipt in rows):
            return False
        rebuilt = build_branch_selection_certificate(rows, verifier_call_count=certificate.verifier_call_count)
        return rebuilt.certificate_hash == certificate.certificate_hash
    except Exception:
        return False


def validate_branch_selection_certificate(certificate: BranchSelectionCertificate) -> bool:
    try:
        if certificate.schema_version != BRANCH_SELECTION_CERTIFICATE_SCHEMA:
            return False
        branch_count = certificate.branch_count
        if not isinstance(branch_count, int) or isinstance(branch_count, bool) or branch_count < 0:
            return False
        if (
            not isinstance(certificate.verifier_call_count, int)
            or isinstance(certificate.verifier_call_count, bool)
            or not 0 <= certificate.verifier_call_count <= branch_count
        ):
            return False
        length_fields = (
            certificate.receipt_hashes,
            certificate.proposal_trace_hashes,
            certificate.typed_candidate_hashes,
            certificate.hard_results,
            certificate.commit_decisions,
            certificate.committed_flags,
        )
        if any(len(field) != branch_count for field in length_fields):
            return False

        accepted = _normalize_indices(certificate.accepted_indices)
        rejected = _normalize_indices(certificate.rejected_indices)
        abstained = _normalize_indices(certificate.abstained_indices)
        losers = _normalize_indices(certificate.loser_indices)
        if (
            accepted != certificate.accepted_indices
            or rejected != certificate.rejected_indices
            or abstained != certificate.abstained_indices
            or losers != certificate.loser_indices
        ):
            return False
        if not all(_indices_valid(indices, branch_count) for indices in (accepted, rejected, abstained, losers)):
            return False
        if _overlap(accepted, rejected) or _overlap(accepted, abstained) or _overlap(rejected, abstained):
            return False
        if tuple(sorted((*accepted, *rejected, *abstained))) != tuple(range(branch_count)):
            return False
        if certificate.accepted_indices != tuple(
            idx for idx, result in enumerate(certificate.hard_results) if result == "accept"
        ):
            return False
        if certificate.rejected_indices != tuple(
            idx for idx, result in enumerate(certificate.hard_results) if result == "reject"
        ):
            return False
        if certificate.abstained_indices != tuple(
            idx for idx, result in enumerate(certificate.hard_results) if result == "abstain"
        ):
            return False
        if any(result not in {"accept", "reject", "abstain"} for result in certificate.hard_results):
            return False
        if any(not isinstance(flag, bool) for flag in certificate.committed_flags):
            return False
        if any(not isinstance(decision, str) or not decision for decision in certificate.commit_decisions):
            return False
        if any(not _is_hash(value) for value in certificate.receipt_hashes):
            return False
        if any(not _is_hash(value) for value in certificate.proposal_trace_hashes):
            return False
        if any(not _is_hash(value) for value in certificate.typed_candidate_hashes):
            return False

        committed_flags = tuple(idx for idx, flag in enumerate(certificate.committed_flags) if flag)
        if len(committed_flags) > 1:
            return False
        if certificate.committed_index is None:
            if committed_flags:
                return False
        elif committed_flags != (certificate.committed_index,):
            return False
        if certificate.committed_index is not None:
            if not _index_valid(certificate.committed_index, branch_count):
                return False
            if certificate.committed_index not in accepted:
                return False
            if certificate.commit_decisions[certificate.committed_index] != "commit":
                return False
        if any(
            decision == "commit" and not flag
            for decision, flag in zip(certificate.commit_decisions, certificate.committed_flags)
        ):
            return False

        if certificate.selected_index is not None:
            if not _index_valid(certificate.selected_index, branch_count):
                return False
            if certificate.selected_index not in accepted:
                return False
            if certificate.selected_index in losers:
                return False
            selected_decision = certificate.commit_decisions[certificate.selected_index]
            if selected_decision in {"ranker_invalid_choice", "no_admissible_branch", "rolled_back_loser"}:
                return False
            if certificate.committed_index is not None and certificate.committed_index != certificate.selected_index:
                return False
            expected_losers = tuple(idx for idx in accepted if idx != certificate.selected_index)
            if losers != expected_losers:
                return False
        else:
            if certificate.committed_index is not None:
                return False
            if losers:
                return False
            if any(
                certificate.commit_decisions[idx] not in {"ranker_invalid_choice", "no_admissible_branch"}
                for idx in accepted
            ):
                return False

        if any(idx not in accepted for idx in losers):
            return False
        if any(certificate.commit_decisions[idx] != "rolled_back_loser" for idx in losers):
            return False
        if any(certificate.committed_flags[idx] for idx in losers):
            return False
        blocked_status_indices = (*rejected, *abstained)
        if any(certificate.commit_decisions[idx] in {"commit", "rolled_back_loser"} for idx in blocked_status_indices):
            return False
        if any(certificate.committed_flags[idx] for idx in blocked_status_indices):
            return False
        return certificate.certificate_hash == branch_selection_certificate_hash(certificate)
    except Exception:
        return False


def branch_selection_certificate_hash(certificate: BranchSelectionCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, BranchSelectionCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def candidate_verifier_cost(candidate: TypedCandidate, *, default: int = 1) -> int:
    if not isinstance(default, int) or isinstance(default, bool) or default <= 0:
        raise ValueError("default must be a positive integer")
    payload = candidate.payload if isinstance(candidate.payload, Mapping) else {}
    value = payload.get("verifier_cost", payload.get("verifierCost", default))
    try:
        cost = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("verifier cost must be a positive integer") from exc
    if isinstance(value, bool) or cost <= 0:
        raise ValueError("verifier cost must be a positive integer")
    return cost


def _with_verifier_cost_metadata(
    result: HardVerifierResult,
    verifier_cost: int,
    budget_spent: int,
    budget: int,
) -> HardVerifierResult:
    metadata = dict(result.metadata)
    metadata.setdefault("verifier_cost", verifier_cost)
    metadata["verifier_cost_spent"] = verifier_cost
    metadata["budget_spent"] = budget_spent
    metadata["budget"] = budget
    return HardVerifierResult(
        result=result.result,
        verifier_id=result.verifier_id,
        verifier_version=result.verifier_version,
        residual=result.residual,
        metadata=metadata,
    )


def _normalize_indices(indices: Iterable[int]) -> tuple[int, ...]:
    rows = tuple(indices)
    return tuple(sorted(rows))


def _indices_valid(indices: Iterable[int], branch_count: int) -> bool:
    rows = tuple(indices)
    return len(rows) == len(set(rows)) and all(_index_valid(idx, branch_count) for idx in rows)


def _index_valid(index: int, branch_count: int) -> bool:
    return isinstance(index, int) and not isinstance(index, bool) and 0 <= index < branch_count


def _overlap(left: Iterable[int], right: Iterable[int]) -> bool:
    return bool(set(left).intersection(right))


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
