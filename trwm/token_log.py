from __future__ import annotations

from dataclasses import asdict, dataclass
import random
from typing import Any, Iterable, Mapping

from .core import stable_hash
from .reversible import BlockToken, DeltaToken


CIRCULAR_TOKEN_LOG_CERTIFICATE_SCHEMA = "trwm.circular_token_log_certificate.v1"


@dataclass(frozen=True)
class CircularTokenLogCertificate:
    schema_version: str
    capacity: int
    total_token_count: int
    compacted_prefix_count: int
    suffix_count: int
    compacted_delta_count: int
    compacted_tokens: tuple[DeltaToken, ...]
    suffix_tokens: tuple[DeltaToken, ...]
    base_state_hash: str
    compacted_state_hash: str
    final_state_hash: str
    compacted_token_hash: str
    suffix_token_hash: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CIRCULAR_TOKEN_LOG_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid circular token log schema: {self.schema_version}")
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in (
                self.capacity,
                self.total_token_count,
                self.compacted_prefix_count,
                self.suffix_count,
                self.compacted_delta_count,
            )
        ):
            raise ValueError("circular token log counts must be non-negative integers")
        if self.capacity <= 0:
            raise ValueError("circular token log capacity must be positive")
        object.__setattr__(self, "compacted_tokens", tuple(self.compacted_tokens))
        object.__setattr__(self, "suffix_tokens", tuple(self.suffix_tokens))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", circular_token_log_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CircularTokenLog:
    capacity: int
    base_state: Mapping[str, Any]
    total_token_count: int = 0
    compacted_prefix_count: int = 0
    compacted_tokens: tuple[DeltaToken, ...] = ()
    suffix_tokens: tuple[DeltaToken, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.capacity, int) or isinstance(self.capacity, bool) or self.capacity <= 0:
            raise ValueError("circular token log capacity must be a positive integer")
        object.__setattr__(self, "base_state", dict(self.base_state))
        object.__setattr__(self, "compacted_tokens", tuple(self.compacted_tokens))
        object.__setattr__(self, "suffix_tokens", tuple(self.suffix_tokens))
        if len(self.suffix_tokens) > self.capacity:
            raise ValueError("suffix length exceeds circular token log capacity")

    @classmethod
    def from_tokens(cls, base_state: Mapping[str, Any], tokens: Iterable[DeltaToken], capacity: int) -> "CircularTokenLog":
        log = cls(capacity=capacity, base_state=base_state)
        for token in tokens:
            log = log.append(token)
        return log

    def append(self, token: DeltaToken) -> "CircularTokenLog":
        next_suffix = self.suffix_tokens + (token,)
        compacted_tokens = self.compacted_tokens
        compacted_prefix_count = self.compacted_prefix_count
        if len(next_suffix) > self.capacity:
            evicted = next_suffix[0]
            next_suffix = next_suffix[1:]
            compacted_tokens = compact_token_prefix(self.base_state, compacted_tokens + (evicted,))
            compacted_prefix_count += 1
        return CircularTokenLog(
            capacity=self.capacity,
            base_state=self.base_state,
            total_token_count=self.total_token_count + 1,
            compacted_prefix_count=compacted_prefix_count,
            compacted_tokens=compacted_tokens,
            suffix_tokens=next_suffix,
        )

    def replay(self) -> dict[str, Any]:
        return replay_circular_token_log(self.base_state, self.compacted_tokens, self.suffix_tokens)

    def compacted_state(self) -> dict[str, Any]:
        return BlockToken.of(self.compacted_tokens).apply(self.base_state) if self.compacted_tokens else dict(self.base_state)

    def certificate(self) -> CircularTokenLogCertificate:
        compacted_state = self.compacted_state()
        final_state = replay_circular_token_log(self.base_state, self.compacted_tokens, self.suffix_tokens)
        return CircularTokenLogCertificate(
            schema_version=CIRCULAR_TOKEN_LOG_CERTIFICATE_SCHEMA,
            capacity=self.capacity,
            total_token_count=self.total_token_count,
            compacted_prefix_count=self.compacted_prefix_count,
            suffix_count=len(self.suffix_tokens),
            compacted_delta_count=len(self.compacted_tokens),
            compacted_tokens=self.compacted_tokens,
            suffix_tokens=self.suffix_tokens,
            base_state_hash=stable_hash(dict(self.base_state)),
            compacted_state_hash=stable_hash(compacted_state),
            final_state_hash=stable_hash(final_state),
            compacted_token_hash=token_sequence_hash(self.compacted_tokens),
            suffix_token_hash=token_sequence_hash(self.suffix_tokens),
        )


def compact_token_prefix(base_state: Mapping[str, Any], tokens: Iterable[DeltaToken]) -> tuple[DeltaToken, ...]:
    base = dict(base_state)
    current = dict(base)
    touched: set[str] = set()
    for token in tokens:
        current = token.apply(current)
        touched.update(token.read_set)
        touched.update(token.write_set)
    compacted: list[DeltaToken] = []
    for key in sorted(touched):
        if key not in base:
            raise ValueError(f"cannot compact missing base key: {key}")
        if current[key] != base[key]:
            compacted.append(DeltaToken(key, base[key], current[key]))
    return tuple(compacted)


def replay_circular_token_log(
    base_state: Mapping[str, Any],
    compacted_tokens: Iterable[DeltaToken],
    suffix_tokens: Iterable[DeltaToken],
) -> dict[str, Any]:
    current = dict(base_state)
    for block in (tuple(compacted_tokens), tuple(suffix_tokens)):
        if block:
            current = BlockToken.of(block).apply(current)
    return current


def build_circular_token_log_certificate(
    base_state: Mapping[str, Any],
    tokens: Iterable[DeltaToken],
    *,
    capacity: int,
) -> CircularTokenLogCertificate:
    rows = tuple(tokens)
    log = CircularTokenLog.from_tokens(base_state, rows, capacity)
    full_state = BlockToken.of(rows).apply(base_state) if rows else dict(base_state)
    compacted_state = log.replay()
    if full_state != compacted_state:
        raise AssertionError("circular token log compaction changed replay state")
    return log.certificate()


def audit_circular_token_log(
    base_state: Mapping[str, Any],
    certificate: CircularTokenLogCertificate,
    original_tokens: Iterable[DeltaToken] | None = None,
) -> bool:
    if not validate_circular_token_log_certificate(certificate):
        return False
    try:
        if stable_hash(dict(base_state)) != certificate.base_state_hash:
            return False
        compacted_state = BlockToken.of(certificate.compacted_tokens).apply(base_state) if certificate.compacted_tokens else dict(base_state)
        final_state = replay_circular_token_log(base_state, certificate.compacted_tokens, certificate.suffix_tokens)
        inverse_state = _inverse_replay(final_state, certificate.compacted_tokens, certificate.suffix_tokens)
        if stable_hash(compacted_state) != certificate.compacted_state_hash:
            return False
        if stable_hash(final_state) != certificate.final_state_hash:
            return False
        if inverse_state != dict(base_state):
            return False
        if original_tokens is not None:
            rebuilt = build_circular_token_log_certificate(base_state, original_tokens, capacity=certificate.capacity)
            if rebuilt.certificate_hash != certificate.certificate_hash:
                return False
        return True
    except Exception:
        return False


def validate_circular_token_log_certificate(certificate: CircularTokenLogCertificate) -> bool:
    try:
        if certificate.schema_version != CIRCULAR_TOKEN_LOG_CERTIFICATE_SCHEMA:
            return False
        if certificate.suffix_count != len(certificate.suffix_tokens):
            return False
        if certificate.compacted_delta_count != len(certificate.compacted_tokens):
            return False
        if certificate.suffix_count > certificate.capacity:
            return False
        if certificate.total_token_count != certificate.compacted_prefix_count + certificate.suffix_count:
            return False
        if certificate.compacted_token_hash != token_sequence_hash(certificate.compacted_tokens):
            return False
        if certificate.suffix_token_hash != token_sequence_hash(certificate.suffix_tokens):
            return False
        return certificate.certificate_hash == circular_token_log_certificate_hash(certificate)
    except Exception:
        return False


def circular_token_log_certificate_hash(certificate: CircularTokenLogCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, CircularTokenLogCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def token_sequence_hash(tokens: Iterable[DeltaToken]) -> str:
    return stable_hash(tuple(tokens))


def randomized_circular_token_log_trials(
    *,
    seed: int = 17,
    trials: int = 64,
    key_count: int = 5,
    token_count: int = 14,
    capacity: int = 4,
) -> tuple[int, int]:
    if trials < 0 or key_count <= 0 or token_count < 0 or capacity <= 0:
        raise ValueError("invalid randomized circular token log trial parameters")
    rng = random.Random(seed)
    mismatches = 0
    for _trial in range(trials):
        state = {f"k{idx}": 0 for idx in range(key_count)}
        current = dict(state)
        tokens: list[DeltaToken] = []
        for _idx in range(token_count):
            key = f"k{rng.randrange(key_count)}"
            before = current[key]
            after = before + rng.randint(-2, 3)
            if after == before:
                after += 1
            tokens.append(DeltaToken(key, before, after))
            current[key] = after
        certificate = build_circular_token_log_certificate(state, tokens, capacity=capacity)
        if not audit_circular_token_log(state, certificate, tokens):
            mismatches += 1
    return trials, mismatches


def _inverse_replay(
    final_state: Mapping[str, Any],
    compacted_tokens: Iterable[DeltaToken],
    suffix_tokens: Iterable[DeltaToken],
) -> dict[str, Any]:
    current = dict(final_state)
    suffix = tuple(suffix_tokens)
    compacted = tuple(compacted_tokens)
    if suffix:
        current = BlockToken.of(suffix).inverse().apply(current)
    if compacted:
        current = BlockToken.of(compacted).inverse().apply(current)
    return current
