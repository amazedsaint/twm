from __future__ import annotations

from dataclasses import asdict, dataclass
import random
from typing import Any, Iterable, Mapping, Protocol

from .core import stable_hash
from .reversible import DeltaToken


PARALLEL_REPLAY_CERTIFICATE_SCHEMA = "trwm.parallel_replay_certificate.v1"


class ReplayToken(Protocol):
    read_set: frozenset[str]
    write_set: frozenset[str]

    def apply(self, state: Mapping[str, Any]) -> dict[str, Any]:
        ...

    def inverse(self) -> "ReplayToken":
        ...


@dataclass(frozen=True)
class ParallelReplayCertificate:
    schema_version: str
    token_count: int
    batch_count: int
    conflict_count: int
    max_batch_width: int
    batches: tuple[tuple[int, ...], ...]
    sequential_state_hash: str
    parallel_state_hash: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != PARALLEL_REPLAY_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid parallel replay certificate schema: {self.schema_version}")
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in (self.token_count, self.batch_count, self.conflict_count, self.max_batch_width)
        ):
            raise ValueError("certificate counts must be non-negative")
        object.__setattr__(self, "batches", _normalize_batches(self.batches))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", parallel_replay_certificate_hash(self))


def token_conflicts(left: ReplayToken, right: ReplayToken) -> bool:
    return bool(
        left.write_set.intersection(right.read_set)
        or right.write_set.intersection(left.read_set)
        or left.write_set.intersection(right.write_set)
    )


def parallel_batches(tokens: Iterable[ReplayToken]) -> tuple[tuple[int, ...], ...]:
    rows = tuple(tokens)
    batches: list[list[int]] = []
    assigned: list[int] = []
    for idx, token in enumerate(rows):
        min_batch = 0
        for prev_idx, prev in enumerate(rows[:idx]):
            if token_conflicts(prev, token):
                min_batch = max(min_batch, assigned[prev_idx] + 1)
        target = min_batch
        while True:
            while len(batches) <= target:
                batches.append([])
            if all(not token_conflicts(rows[other], token) for other in batches[target]):
                batches[target].append(idx)
                assigned.append(target)
                break
            target += 1
    return tuple(tuple(batch) for batch in batches)


def sequential_replay(state: Mapping[str, Any], tokens: Iterable[ReplayToken]) -> dict[str, Any]:
    current = dict(state)
    for token in tokens:
        current = token.apply(current)
    return current


def parallel_replay(state: Mapping[str, Any], tokens: Iterable[ReplayToken], batches: Iterable[Iterable[int]]) -> dict[str, Any]:
    rows = tuple(tokens)
    current = dict(state)
    for batch in batches:
        batch_rows = tuple(batch)
        _validate_batch(rows, batch_rows)
        for idx in batch_rows:
            current = rows[idx].apply(current)
    return current


def build_parallel_replay_certificate(state: Mapping[str, Any], tokens: Iterable[ReplayToken]) -> ParallelReplayCertificate:
    rows = tuple(tokens)
    batches = parallel_batches(rows)
    sequential = sequential_replay(state, rows)
    parallel = parallel_replay(state, rows, batches)
    return ParallelReplayCertificate(
        schema_version=PARALLEL_REPLAY_CERTIFICATE_SCHEMA,
        token_count=len(rows),
        batch_count=len(batches),
        conflict_count=_count_conflicts(rows),
        max_batch_width=max((len(batch) for batch in batches), default=0),
        batches=batches,
        sequential_state_hash=stable_hash(sequential),
        parallel_state_hash=stable_hash(parallel),
    )


def audit_parallel_replay(state: Mapping[str, Any], tokens: Iterable[ReplayToken], certificate: ParallelReplayCertificate) -> bool:
    if not validate_parallel_replay_certificate(certificate):
        return False
    rows = tuple(tokens)
    if certificate.token_count != len(rows):
        return False
    if certificate.conflict_count != _count_conflicts(rows):
        return False
    flat = tuple(idx for batch in certificate.batches for idx in batch)
    if sorted(flat) != list(range(len(rows))):
        return False
    try:
        sequential = sequential_replay(state, rows)
        parallel = parallel_replay(state, rows, certificate.batches)
    except Exception:
        return False
    return (
        stable_hash(sequential) == certificate.sequential_state_hash
        and stable_hash(parallel) == certificate.parallel_state_hash
        and sequential == parallel
    )


def validate_parallel_replay_certificate(certificate: ParallelReplayCertificate) -> bool:
    if certificate.schema_version != PARALLEL_REPLAY_CERTIFICATE_SCHEMA:
        return False
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (certificate.token_count, certificate.batch_count, certificate.conflict_count, certificate.max_batch_width)
    ):
        return False
    if certificate.batch_count != len(certificate.batches):
        return False
    if certificate.max_batch_width != max((len(batch) for batch in certificate.batches), default=0):
        return False
    flat = tuple(idx for batch in certificate.batches for idx in batch)
    if sorted(flat) != list(range(certificate.token_count)):
        return False
    if not _is_hash(certificate.sequential_state_hash) or not _is_hash(certificate.parallel_state_hash):
        return False
    return certificate.certificate_hash == parallel_replay_certificate_hash(certificate)


def parallel_replay_certificate_hash(certificate: ParallelReplayCertificate) -> str:
    data = asdict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def randomized_parallel_replay_trials(
    *,
    seed: int = 11,
    trials: int = 64,
    key_count: int = 5,
    token_count: int = 12,
) -> tuple[int, int]:
    if trials < 0 or key_count <= 0 or token_count < 0:
        raise ValueError("invalid randomized trial parameters")
    rng = random.Random(seed)
    mismatches = 0
    for _trial in range(trials):
        state = {f"k{idx}": 0 for idx in range(key_count)}
        current = dict(state)
        tokens = []
        for _idx in range(token_count):
            key = f"k{rng.randrange(key_count)}"
            before = current[key]
            after = before + rng.randint(1, 3)
            tokens.append(DeltaToken(key, before, after))
            current[key] = after
        certificate = build_parallel_replay_certificate(state, tokens)
        if not audit_parallel_replay(state, tokens, certificate):
            mismatches += 1
    return trials, mismatches


def _validate_batch(tokens: tuple[ReplayToken, ...], batch: tuple[int, ...]) -> None:
    for offset, left_idx in enumerate(batch):
        if left_idx < 0 or left_idx >= len(tokens):
            raise ValueError("parallel batch index out of range")
        for right_idx in batch[offset + 1 :]:
            if right_idx < 0 or right_idx >= len(tokens):
                raise ValueError("parallel batch index out of range")
            if token_conflicts(tokens[left_idx], tokens[right_idx]):
                raise ValueError("parallel batch contains conflicting tokens")


def _count_conflicts(tokens: tuple[ReplayToken, ...]) -> int:
    return sum(
        1
        for left_idx in range(len(tokens))
        for right_idx in range(left_idx + 1, len(tokens))
        if token_conflicts(tokens[left_idx], tokens[right_idx])
    )


def _normalize_batches(batches: Iterable[Iterable[int]]) -> tuple[tuple[int, ...], ...]:
    normalized: list[tuple[int, ...]] = []
    for batch in batches:
        row: list[int] = []
        for idx in batch:
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise ValueError("parallel batch indices must be integers")
            row.append(idx)
        normalized.append(tuple(row))
    return tuple(normalized)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)
