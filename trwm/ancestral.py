from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .branch import BranchSelectionCertificate, audit_branch_selection, validate_branch_selection_certificate
from .core import Receipt, canonical_json, stable_hash


ANCESTRAL_BRANCH_MEMORY_SNAPSHOT_SCHEMA = "trwm.ancestral_branch_memory_snapshot.v1"


@dataclass(frozen=True)
class AncestralBranchActionStats:
    context: str
    action: str
    committed: int
    rolled_back: int
    rejected: int
    abstained: int
    receipt_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.context or not self.action:
            raise ValueError("context and action must be non-empty")
        for field_name in ("committed", "rolled_back", "rejected", "abstained"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))


@dataclass(frozen=True)
class AncestralBranchMemorySnapshot:
    schema_version: str
    learning_policy: Mapping[str, float]
    receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]
    rows: tuple[AncestralBranchActionStats, ...]
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != ANCESTRAL_BRANCH_MEMORY_SNAPSHOT_SCHEMA:
            raise ValueError(f"invalid ancestral memory snapshot schema: {self.schema_version}")
        object.__setattr__(self, "learning_policy", dict(self.learning_policy))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(
            self,
            "branch_selection_certificate_hashes",
            tuple(self.branch_selection_certificate_hashes),
        )
        object.__setattr__(self, "rows", tuple(self.rows))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", ancestral_branch_memory_snapshot_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("snapshot_hash", None)
        return data


class AncestralBranchMemory:
    """Receipt-bound proposal-ordering memory for past branch outcomes.

    The memory can rank candidates, but it never supplies commit authority.
    Receipts should come from audited branch selections; every ranked candidate
    still needs to pass the hard verifier and transaction replay/rollback gates.
    """

    def __init__(
        self,
        *,
        commit_weight: float = 1.0,
        rollback_weight: float = 1.0,
        reject_weight: float = 2.0,
        abstain_weight: float = 1.5,
    ) -> None:
        self.commit_weight = float(commit_weight)
        self.rollback_weight = float(rollback_weight)
        self.reject_weight = float(reject_weight)
        self.abstain_weight = float(abstain_weight)
        self._rows: defaultdict[tuple[str, str], _MutableActionStats] = defaultdict(_MutableActionStats)
        self._seen_receipt_hashes: set[str] = set()
        self._receipt_hashes: list[str] = []
        self._branch_selection_certificate_hashes: list[str] = []

    def update_branch(
        self,
        receipts: Iterable[Receipt],
        certificate: BranchSelectionCertificate,
    ) -> None:
        rows = tuple(receipts)
        if not validate_branch_selection_certificate(certificate):
            raise ValueError("branch selection certificate must validate before memory update")
        if not audit_branch_selection(rows, certificate):
            raise ValueError("branch selection certificate must audit against receipts before memory update")
        if certificate.certificate_hash not in self._branch_selection_certificate_hashes:
            self._branch_selection_certificate_hashes.append(certificate.certificate_hash)
        for receipt in rows:
            self.update_receipt(receipt)

    def update_receipt(self, receipt: Receipt) -> None:
        if not receipt.static_valid():
            raise ValueError("receipt must be statically valid before memory update")
        if receipt.receipt_hash in self._seen_receipt_hashes:
            return
        context, action = _receipt_context_action(receipt)
        row = self._rows[(context, action)]
        if receipt.committed and receipt.hard_result.accepted:
            row.committed += 1
        elif receipt.hard_result.accepted and receipt.commit_decision == "rolled_back_loser":
            row.rolled_back += 1
        elif receipt.hard_result.rejected:
            row.rejected += 1
        elif receipt.hard_result.abstained:
            row.abstained += 1
        row.receipt_hashes.append(receipt.receipt_hash)
        self._seen_receipt_hashes.add(receipt.receipt_hash)
        self._receipt_hashes.append(receipt.receipt_hash)

    def stats(self, context: str, candidate: Any) -> AncestralBranchActionStats:
        context_token = str(context)
        action_token = _token(candidate)
        row = self._rows.get((context_token, action_token), _MutableActionStats())
        return row.to_frozen(context_token, action_token)

    def score(self, context: str, candidate: Any) -> float:
        row = self.stats(context, candidate)
        return (
            self.commit_weight * row.committed
            - self.rollback_weight * row.rolled_back
            - self.reject_weight * row.rejected
            - self.abstain_weight * row.abstained
        )

    def rank(self, context: str, candidates: Iterable[Any]) -> list[Any]:
        indexed = tuple(enumerate(candidates))

        def key(row_candidate: tuple[int, Any]) -> tuple[float, int, int, int, int, int]:
            idx, candidate = row_candidate
            row = self.stats(context, candidate)
            return (
                -self.score(context, candidate),
                -row.committed,
                row.rolled_back,
                row.rejected,
                row.abstained,
                idx,
            )

        return [candidate for _, candidate in sorted(indexed, key=key)]

    def stats_from_contexts(self, contexts: Iterable[str], candidate: Any) -> AncestralBranchActionStats:
        context_tokens = _unique_contexts(contexts)
        action_token = _token(candidate)
        committed = 0
        rolled_back = 0
        rejected = 0
        abstained = 0
        receipt_hashes: list[str] = []
        for context in context_tokens:
            row = self._rows.get((context, action_token), _MutableActionStats())
            committed += row.committed
            rolled_back += row.rolled_back
            rejected += row.rejected
            abstained += row.abstained
            receipt_hashes.extend(row.receipt_hashes or ())
        return AncestralBranchActionStats(
            context="+".join(context_tokens) if context_tokens else "none",
            action=action_token,
            committed=committed,
            rolled_back=rolled_back,
            rejected=rejected,
            abstained=abstained,
            receipt_hashes=tuple(receipt_hashes),
        )

    def score_from_contexts(self, contexts: Iterable[str], candidate: Any) -> float:
        row = self.stats_from_contexts(contexts, candidate)
        return (
            self.commit_weight * row.committed
            - self.rollback_weight * row.rolled_back
            - self.reject_weight * row.rejected
            - self.abstain_weight * row.abstained
        )

    def rank_from_contexts(self, contexts: Iterable[str], candidates: Iterable[Any]) -> list[Any]:
        context_tokens = _unique_contexts(contexts)
        indexed = tuple(enumerate(candidates))

        def key(row_candidate: tuple[int, Any]) -> tuple[float, int, int, int, int, int]:
            idx, candidate = row_candidate
            row = self.stats_from_contexts(context_tokens, candidate)
            return (
                -self.score_from_contexts(context_tokens, candidate),
                -row.committed,
                row.rolled_back,
                row.rejected,
                row.abstained,
                idx,
            )

        return [candidate for _, candidate in sorted(indexed, key=key)]

    def snapshot(self) -> AncestralBranchMemorySnapshot:
        rows = tuple(
            self._rows[key].to_frozen(*key)
            for key in sorted(self._rows.keys())
        )
        return AncestralBranchMemorySnapshot(
            schema_version=ANCESTRAL_BRANCH_MEMORY_SNAPSHOT_SCHEMA,
            learning_policy={
                "commit_weight": self.commit_weight,
                "rollback_weight": self.rollback_weight,
                "reject_weight": self.reject_weight,
                "abstain_weight": self.abstain_weight,
            },
            receipt_hashes=tuple(self._receipt_hashes),
            branch_selection_certificate_hashes=tuple(self._branch_selection_certificate_hashes),
            rows=rows,
        )


def validate_ancestral_branch_memory_snapshot(snapshot: AncestralBranchMemorySnapshot) -> bool:
    try:
        if snapshot.schema_version != ANCESTRAL_BRANCH_MEMORY_SNAPSHOT_SCHEMA:
            return False
        for key in ("commit_weight", "rollback_weight", "reject_weight", "abstain_weight"):
            value = snapshot.learning_policy.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                return False
        if any(not _is_hash(value) for value in snapshot.receipt_hashes):
            return False
        if len(snapshot.receipt_hashes) != len(set(snapshot.receipt_hashes)):
            return False
        if any(not _is_hash(value) for value in snapshot.branch_selection_certificate_hashes):
            return False
        if len(snapshot.branch_selection_certificate_hashes) != len(set(snapshot.branch_selection_certificate_hashes)):
            return False
        row_keys = tuple((row.context, row.action) for row in snapshot.rows)
        if row_keys != tuple(sorted(row_keys)):
            return False
        if len(row_keys) != len(set(row_keys)):
            return False
        bound_receipts: list[str] = []
        for row in snapshot.rows:
            if not isinstance(row, AncestralBranchActionStats):
                return False
            if not row.context or not row.action:
                return False
            counts = (row.committed, row.rolled_back, row.rejected, row.abstained)
            if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts):
                return False
            if sum(counts) != len(row.receipt_hashes):
                return False
            if any(not _is_hash(value) for value in row.receipt_hashes):
                return False
            if len(row.receipt_hashes) != len(set(row.receipt_hashes)):
                return False
            bound_receipts.extend(row.receipt_hashes)
        if tuple(sorted(bound_receipts)) != tuple(sorted(snapshot.receipt_hashes)):
            return False
        return snapshot.snapshot_hash == ancestral_branch_memory_snapshot_hash(snapshot)
    except Exception:
        return False


def ancestral_branch_memory_snapshot_hash(snapshot: AncestralBranchMemorySnapshot | Mapping[str, Any]) -> str:
    if isinstance(snapshot, AncestralBranchMemorySnapshot):
        data = snapshot.without_hash()
    else:
        data = dict(snapshot)
        data.pop("snapshot_hash", None)
    return stable_hash(data)


@dataclass
class _MutableActionStats:
    committed: int = 0
    rolled_back: int = 0
    rejected: int = 0
    abstained: int = 0
    receipt_hashes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.receipt_hashes is None:
            self.receipt_hashes = []

    def to_frozen(self, context: str, action: str) -> AncestralBranchActionStats:
        return AncestralBranchActionStats(
            context=context,
            action=action,
            committed=self.committed,
            rolled_back=self.rolled_back,
            rejected=self.rejected,
            abstained=self.abstained,
            receipt_hashes=tuple(self.receipt_hashes or ()),
        )


def _receipt_context_action(receipt: Receipt) -> tuple[str, str]:
    bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
    payload = bundle.get("candidate_payload", {})
    payload = payload if isinstance(payload, Mapping) else {}
    context = str(bundle.get("context", payload.get("context", "global")))
    action = _token(bundle.get("action", payload.get("action", payload.get("guess", payload))))
    return context, action


def _token(value: Any) -> str:
    if isinstance(value, (Mapping, list, tuple, set, bytes)):
        return canonical_json(value)
    return str(value)


def _unique_contexts(contexts: Iterable[str]) -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for context in contexts:
        token = str(context)
        if not token:
            raise ValueError("ancestor context must be non-empty")
        if token not in seen:
            rows.append(token)
            seen.add(token)
    return tuple(rows)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)
