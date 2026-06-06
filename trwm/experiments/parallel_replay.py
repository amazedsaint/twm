from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from ..core import stable_hash
from ..parallel import (
    audit_parallel_replay,
    build_parallel_replay_certificate,
    parallel_replay,
    randomized_parallel_replay_trials,
    sequential_replay,
    validate_parallel_replay_certificate,
)
from ..reversible import BlockToken, DeltaToken


@dataclass(frozen=True)
class ParallelReplayReport:
    schema_version: str
    token_count: int
    batch_count: int
    max_batch_width: int
    conflict_count: int
    batches: tuple[tuple[int, ...], ...]
    sequential_state: dict[str, Any]
    parallel_state: dict[str, Any]
    parallel_equals_sequential: bool
    inverse_roundtrip: bool
    certificate_valid: bool
    audit_valid: bool
    tamper_detected: bool
    randomized_trial_count: int
    randomized_mismatch_count: int
    invalid_commit_count: int


def run_parallel_replay_benchmark() -> ParallelReplayReport:
    state = demo_state()
    tokens = demo_tokens()
    certificate = build_parallel_replay_certificate(state, tokens)
    sequential_state = sequential_replay(state, tokens)
    parallel_state = parallel_replay(state, tokens, certificate.batches)
    tampered = replace(certificate, parallel_state_hash=stable_hash({"tampered": True}))
    randomized_trial_count, randomized_mismatch_count = randomized_parallel_replay_trials()
    invalid_commit_count = 0

    return ParallelReplayReport(
        schema_version=certificate.schema_version,
        token_count=certificate.token_count,
        batch_count=certificate.batch_count,
        max_batch_width=certificate.max_batch_width,
        conflict_count=certificate.conflict_count,
        batches=certificate.batches,
        sequential_state=sequential_state,
        parallel_state=parallel_state,
        parallel_equals_sequential=sequential_state == parallel_state,
        inverse_roundtrip=BlockToken.of(tokens).inverse().apply(sequential_state) == state,
        certificate_valid=validate_parallel_replay_certificate(certificate),
        audit_valid=audit_parallel_replay(state, tokens, certificate),
        tamper_detected=not audit_parallel_replay(state, tokens, tampered),
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
        DeltaToken("b", 2, 5),
        DeltaToken("d", 0, 6),
    )
