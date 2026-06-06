from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from math import sqrt
from typing import Any, Iterable, Mapping

from .core import Receipt, canonical_json


@dataclass(frozen=True)
class CounterfactualActionStats:
    committed: int = 0
    rolled_back: int = 0
    rejected: int = 0
    abstained: int = 0


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
