from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from math import sqrt
from typing import Any, Iterable, Mapping

from .core import Receipt, TypedCandidate, canonical_json, stable_hash


RECEIPT_TRAINED_REVERSIBLE_PROPOSER_SNAPSHOT_SCHEMA = "trwm.receipt_trained_reversible_proposer_snapshot.v1"


@dataclass(frozen=True)
class CounterfactualActionStats:
    committed: int = 0
    rolled_back: int = 0
    rejected: int = 0
    abstained: int = 0


@dataclass(frozen=True)
class ReversibleProposerSnapshotRow:
    context: str
    action: str
    committed: int
    rejected: int
    observations: int
    score: float


@dataclass(frozen=True)
class ReceiptTrainedReversibleProposerSnapshot:
    schema_version: str
    learner_id: str
    learner_version: str
    receipt_hashes: tuple[str, ...]
    rows: tuple[ReversibleProposerSnapshotRow, ...]
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != RECEIPT_TRAINED_REVERSIBLE_PROPOSER_SNAPSHOT_SCHEMA:
            raise ValueError(f"invalid reversible proposer snapshot schema: {self.schema_version}")
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(self, "rows", tuple(sorted(self.rows, key=lambda row: (row.context, row.action))))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", receipt_trained_reversible_proposer_snapshot_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("snapshot_hash", None)
        return data


class ReceiptTrainedReversibleProposer:
    """Receipt-trained reversible proposal ranker.

    The proposer only reorders typed candidates. It never supplies hard-verifier
    authority, and its transferable key is the candidate action signature rather
    than a task id or receipt hash.
    """

    def __init__(
        self,
        *,
        learner_id: str = "receipt_trained_reversible_proposer",
        learner_version: str = "1.0",
        commit_weight: float = 1.0,
        reject_weight: float = 1.0,
    ) -> None:
        if not learner_id or not learner_version:
            raise ValueError("learner id and version must be non-empty")
        if commit_weight <= 0 or reject_weight < 0:
            raise ValueError("weights must be non-negative and commit_weight must be positive")
        self.learner_id = learner_id
        self.learner_version = learner_version
        self.commit_weight = float(commit_weight)
        self.reject_weight = float(reject_weight)
        self.committed: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rejected: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.receipt_hashes: list[str] = []

    def update(self, receipt: Receipt) -> None:
        if not receipt.static_valid():
            raise ValueError("receipt-trained proposer only accepts statically valid receipts")
        context, action = _receipt_context_action(receipt)
        if receipt.committed and receipt.hard_result.accepted:
            self.committed[context][action] += 1
        elif receipt.hard_result.rejected:
            self.rejected[context][action] += 1
        if receipt.receipt_hash and receipt.receipt_hash not in self.receipt_hashes:
            self.receipt_hashes.append(receipt.receipt_hash)

    def score(self, context: str, candidate: Any) -> float:
        action = _candidate_action_token(candidate)
        return (
            self.commit_weight * self.committed[context][action]
            - self.reject_weight * self.rejected[context][action]
        )

    def rank(self, context: str, candidates: Iterable[Any]) -> list[Any]:
        rows = list(candidates)

        def key(row: tuple[int, Any]) -> tuple[float, int, int, int, str]:
            index, candidate = row
            action = _candidate_action_token(candidate)
            return (
                -self.score(context, candidate),
                -self.committed[context][action],
                self.rejected[context][action],
                index,
                action,
            )

        return [candidate for _, candidate in sorted(enumerate(rows), key=key)]

    def snapshot(self) -> ReceiptTrainedReversibleProposerSnapshot:
        contexts = set(self.committed) | set(self.rejected)
        rows: list[ReversibleProposerSnapshotRow] = []
        for context in sorted(contexts):
            actions = set(self.committed[context]) | set(self.rejected[context])
            for action in sorted(actions):
                committed = self.committed[context][action]
                rejected = self.rejected[context][action]
                rows.append(
                    ReversibleProposerSnapshotRow(
                        context=context,
                        action=action,
                        committed=committed,
                        rejected=rejected,
                        observations=committed + rejected,
                        score=round(self.commit_weight * committed - self.reject_weight * rejected, 12),
                    )
                )
        return ReceiptTrainedReversibleProposerSnapshot(
            schema_version=RECEIPT_TRAINED_REVERSIBLE_PROPOSER_SNAPSHOT_SCHEMA,
            learner_id=self.learner_id,
            learner_version=self.learner_version,
            receipt_hashes=tuple(self.receipt_hashes),
            rows=tuple(rows),
        )


class ReceiptRanker:
    """Receipt-only ranker. It never supplies commit authority."""

    def __init__(self) -> None:
        self.accepted: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rejected: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def update(self, receipt: Receipt) -> None:
        context, action = _receipt_context_action(receipt)
        if receipt.hard_result.accepted:
            self.accepted[context][action] += 1
        elif receipt.hard_result.rejected:
            self.rejected[context][action] += 1

    def rank(self, context: str, candidates: Iterable[Any]) -> list[Any]:
        def key(candidate: Any) -> tuple[int, int, str]:
            token = _token(candidate)
            return (
                -self.accepted[context][token],
                self.rejected[context][token],
                token,
            )

        return sorted(candidates, key=key)


class CounterfactualRollbackRanker:
    """Ranks with branch loser evidence while keeping hard verifiers authoritative."""

    def __init__(self, commit_weight: float = 1.0, rollback_weight: float = 1.0, reject_weight: float = 2.0):
        self.commit_weight = float(commit_weight)
        self.rollback_weight = float(rollback_weight)
        self.reject_weight = float(reject_weight)
        self.committed: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rolled_back: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rejected: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.abstained: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def update(self, receipt: Receipt) -> None:
        context, action = _receipt_context_action(receipt)
        if receipt.committed and receipt.hard_result.accepted:
            self.committed[context][action] += 1
        elif receipt.hard_result.accepted and receipt.commit_decision == "rolled_back_loser":
            self.rolled_back[context][action] += 1
        elif receipt.hard_result.rejected:
            self.rejected[context][action] += 1
        elif receipt.hard_result.abstained:
            self.abstained[context][action] += 1

    def stats(self, context: str, candidate: Any) -> CounterfactualActionStats:
        token = _token(candidate)
        return CounterfactualActionStats(
            committed=self.committed[context][token],
            rolled_back=self.rolled_back[context][token],
            rejected=self.rejected[context][token],
            abstained=self.abstained[context][token],
        )

    def score(self, context: str, candidate: Any) -> float:
        row = self.stats(context, candidate)
        return (
            self.commit_weight * row.committed
            - self.rollback_weight * row.rolled_back
            - self.reject_weight * row.rejected
        )

    def rank(self, context: str, candidates: Iterable[Any]) -> list[Any]:
        def key(candidate: Any) -> tuple[float, int, int, int, str]:
            token = _token(candidate)
            row = self.stats(context, candidate)
            return (
                -self.score(context, candidate),
                -row.committed,
                row.rolled_back,
                row.rejected,
                token,
            )

        return sorted(candidates, key=key)


def _seed_bits(token: str, dimensions: int) -> tuple[int, ...]:
    values: list[int] = []
    counter = 0
    while len(values) < dimensions:
        digest = sha256(f"{token}:{counter}".encode("utf-8")).digest()
        for byte in digest:
            for bit in range(8):
                values.append(1 if byte & (1 << bit) else -1)
                if len(values) == dimensions:
                    break
            if len(values) == dimensions:
                break
        counter += 1
    return tuple(values)


def bind(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(x * y for x, y in zip(a, b))


def bundle(vectors: Iterable[tuple[int, ...]]) -> tuple[int, ...]:
    vectors = list(vectors)
    if not vectors:
        return ()
    totals = [0] * len(vectors[0])
    for vector in vectors:
        for idx, value in enumerate(vector):
            totals[idx] += value
    return tuple(1 if value >= 0 else -1 for value in totals)


def cosine(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot / sqrt(len(a) * len(b))


@dataclass
class HyperdimensionalMemory:
    dimensions: int = 256
    rows: list[tuple[tuple[int, ...], Receipt]] = field(default_factory=list)

    def encode_receipt(self, receipt: Receipt) -> tuple[int, ...]:
        bundle_data = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
        payload = bundle_data.get("candidate_payload", {})
        payload = payload if isinstance(payload, Mapping) else {}
        parts = []
        for role, value in {
            "context": bundle_data.get("context", payload.get("context", "global")),
            "action": _token(bundle_data.get("action", payload.get("action", payload.get("guess", payload)))),
            "result": receipt.hard_result.result,
            "verifier": receipt.hard_result.verifier_id,
            "decision": receipt.commit_decision,
        }.items():
            parts.append(bind(_seed_bits(f"role:{role}", self.dimensions), _seed_bits(str(value), self.dimensions)))
        return bundle(parts)

    def encode_query(self, query: Mapping[str, Any]) -> tuple[int, ...]:
        q_parts = []
        for role, value in query.items():
            q_parts.append(bind(_seed_bits(f"role:{role}", self.dimensions), _seed_bits(_token(value), self.dimensions)))
        return bundle(q_parts)

    def add(self, receipt: Receipt) -> None:
        self.rows.append((self.encode_receipt(receipt), receipt))

    def nearest(self, query: Mapping[str, Any], top_k: int = 8) -> list[Receipt]:
        return self.nearest_vector(self.encode_query(query), top_k)

    def nearest_vector(self, query_vector: tuple[int, ...], top_k: int = 8) -> list[Receipt]:
        scored = sorted(
            ((cosine(query_vector, vector), idx, receipt) for idx, (vector, receipt) in enumerate(self.rows)),
            key=lambda row: (-row[0], row[1]),
        )
        return [receipt for _, _, receipt in scored[:top_k]]


def _token(value: Any) -> str:
    if isinstance(value, (Mapping, list, tuple, set, bytes)):
        return canonical_json(value)
    return str(value)


def _receipt_context_action(receipt: Receipt) -> tuple[str, str]:
    bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
    payload = bundle.get("candidate_payload", {})
    payload = payload if isinstance(payload, Mapping) else {}
    context = str(bundle.get("context", payload.get("context", "global")))
    action = _token(bundle.get("action", payload.get("action", payload.get("guess", payload))))
    return context, action


def receipt_trained_reversible_proposer_snapshot_hash(snapshot: ReceiptTrainedReversibleProposerSnapshot) -> str:
    return stable_hash(snapshot.without_hash())


def validate_receipt_trained_reversible_proposer_snapshot(snapshot: ReceiptTrainedReversibleProposerSnapshot) -> bool:
    try:
        if snapshot.schema_version != RECEIPT_TRAINED_REVERSIBLE_PROPOSER_SNAPSHOT_SCHEMA:
            return False
        if not snapshot.learner_id or not snapshot.learner_version:
            return False
        if any(not _is_hash(receipt_hash) for receipt_hash in snapshot.receipt_hashes):
            return False
        if len(set(snapshot.receipt_hashes)) != len(snapshot.receipt_hashes):
            return False
        if tuple(sorted(snapshot.rows, key=lambda row: (row.context, row.action))) != snapshot.rows:
            return False
        for row in snapshot.rows:
            if not row.context or not row.action:
                return False
            values = (row.committed, row.rejected, row.observations)
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
                return False
            if row.observations != row.committed + row.rejected:
                return False
            if not isinstance(row.score, float):
                return False
        return snapshot.snapshot_hash == receipt_trained_reversible_proposer_snapshot_hash(snapshot)
    except Exception:
        return False


def _candidate_action_token(candidate: Any) -> str:
    payload: Any = candidate
    if isinstance(candidate, TypedCandidate):
        payload = candidate.payload
    elif hasattr(candidate, "payload"):
        payload = getattr(candidate, "payload")
    if isinstance(payload, Mapping):
        return _token(payload.get("action", payload.get("proposal_signature", payload.get("guess", payload))))
    return _token(payload)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
