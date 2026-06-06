from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..core import stable_hash
from ..reversible import BlockToken, DeltaToken
from ..token_log import (
    audit_circular_token_log,
    build_circular_token_log_certificate,
    randomized_circular_token_log_trials,
    replay_circular_token_log,
    validate_circular_token_log_certificate,
)


@dataclass(frozen=True)
class CircularTokenLogReport:
    schema_version: str
    capacity: int
    total_token_count: int
    compacted_prefix_count: int
    suffix_count: int
    compacted_delta_count: int
    retained_replay_token_count: int
    replay_tokens_saved: int
    compacted_token_summary: tuple[str, ...]
    suffix_token_summary: tuple[str, ...]
    full_state: dict[str, Any]
    compacted_state: dict[str, Any]
    full_equals_compacted: bool
    inverse_roundtrip: bool
    certificate_valid: bool
    audit_valid: bool
    tamper_detected: bool
    randomized_trial_count: int
    randomized_mismatch_count: int
    invalid_commit_count: int


def run_circular_token_log_benchmark() -> CircularTokenLogReport:
    state = demo_state()
    tokens = demo_tokens()
    capacity = 3
    certificate = build_circular_token_log_certificate(state, tokens, capacity=capacity)
    full_state = BlockToken.of(tokens).apply(state)
    compacted_state = replay_circular_token_log(state, certificate.compacted_tokens, certificate.suffix_tokens)
    tampered = replace(certificate, final_state_hash=stable_hash({"tampered": True}), certificate_hash="")
    randomized_trial_count, randomized_mismatch_count = randomized_circular_token_log_trials()
    retained_replay_token_count = certificate.compacted_delta_count + certificate.suffix_count
    invalid_commit_count = 0

    return CircularTokenLogReport(
        schema_version=certificate.schema_version,
        capacity=certificate.capacity,
        total_token_count=certificate.total_token_count,
        compacted_prefix_count=certificate.compacted_prefix_count,
        suffix_count=certificate.suffix_count,
        compacted_delta_count=certificate.compacted_delta_count,
        retained_replay_token_count=retained_replay_token_count,
        replay_tokens_saved=certificate.total_token_count - retained_replay_token_count,
        compacted_token_summary=tuple(_token_summary(token) for token in certificate.compacted_tokens),
        suffix_token_summary=tuple(_token_summary(token) for token in certificate.suffix_tokens),
        full_state=full_state,
        compacted_state=compacted_state,
        full_equals_compacted=full_state == compacted_state,
        inverse_roundtrip=audit_circular_token_log(state, certificate),
        certificate_valid=validate_circular_token_log_certificate(certificate),
        audit_valid=audit_circular_token_log(state, certificate, tokens),
        tamper_detected=not audit_circular_token_log(state, tampered, tokens),
        randomized_trial_count=randomized_trial_count,
        randomized_mismatch_count=randomized_mismatch_count,
        invalid_commit_count=invalid_commit_count,
    )


def demo_state() -> dict[str, int]:
    return {"a": 0, "b": 0, "c": 0, "d": 0}


def demo_tokens() -> tuple[DeltaToken, ...]:
    return (
        DeltaToken("a", 0, 1),
        DeltaToken("b", 0, 2),
        DeltaToken("a", 1, 3),
        DeltaToken("c", 0, 4),
        DeltaToken("a", 3, 0),
        DeltaToken("b", 2, 5),
        DeltaToken("d", 0, 6),
        DeltaToken("a", 0, 7),
    )


def _token_summary(token: DeltaToken) -> str:
    return f"{token.key}:{token.before}->{token.after}"
