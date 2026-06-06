from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass, replace
from hashlib import sha256
import json
import platform
import sys
import time
from typing import Any, Callable, Iterable, Mapping, Protocol
from uuid import uuid4


GENESIS_HEAD = "0" * 64
RUNTIME_SCHEMA = "trwm.runtime.v1"
RECEIPT_SCHEMA = "trwm.receipt.v1"


def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key in sorted(value, key=lambda x: str(x)):
            normalized_key = str(key)
            if normalized_key in out:
                raise ValueError(f"mapping key collision after canonicalization: {normalized_key!r}")
            out[normalized_key] = _normalize(value[key])
        return out
    if isinstance(value, tuple):
        return [_normalize(v) for v in value]
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, set):
        return sorted((_normalize(v) for v in value), key=canonical_json)
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def stable_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def chain_hash(parent_head: str, receipt_hash: str) -> str:
    return sha256((parent_head + receipt_hash).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class StateSnapshot:
    state: Any
    schema_version: str = "state.v1"
    state_hash: str = field(default="")

    def __post_init__(self) -> None:
        if not self.state_hash:
            object.__setattr__(
                self,
                "state_hash",
                stable_hash({"schema_version": self.schema_version, "state": self.state}),
            )

    @classmethod
    def capture(cls, state: Any, schema_version: str = "state.v1") -> "StateSnapshot":
        return cls(state=state, schema_version=schema_version)


@dataclass(frozen=True)
class ProposalTrace:
    branch_id: str
    actions: tuple[Any, ...] = ()
    latent_states: tuple[Any, ...] = ()
    seeds: tuple[Any, ...] = ()
    model_version: str = "manual.v1"

    @property
    def trace_hash(self) -> str:
        return stable_hash(self)


@dataclass(frozen=True)
class TypedCandidate:
    payload: Any
    type_name: str
    schema_version: str
    hashes: Mapping[str, str] = field(default_factory=dict)

    @property
    def candidate_hash(self) -> str:
        return stable_hash(self)


@dataclass(frozen=True)
class HardVerifierResult:
    result: str
    verifier_id: str
    verifier_version: str
    residual: Any = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.result not in {"accept", "reject", "abstain"}:
            raise ValueError(f"invalid hard verifier result: {self.result}")

    @classmethod
    def accept(
        cls,
        verifier_id: str,
        verifier_version: str,
        residual: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "HardVerifierResult":
        return cls("accept", verifier_id, verifier_version, residual, metadata or {})

    @classmethod
    def reject(
        cls,
        verifier_id: str,
        verifier_version: str,
        residual: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "HardVerifierResult":
        return cls("reject", verifier_id, verifier_version, residual, metadata or {})

    @classmethod
    def abstain(
        cls,
        verifier_id: str,
        verifier_version: str,
        residual: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "HardVerifierResult":
        return cls("abstain", verifier_id, verifier_version, residual, metadata or {})

    @property
    def accepted(self) -> bool:
        return self.result == "accept"

    @property
    def rejected(self) -> bool:
        return self.result == "reject"

    @property
    def abstained(self) -> bool:
        return self.result == "abstain"


@dataclass(frozen=True)
class RuntimeManifest:
    data: Mapping[str, Any]

    @classmethod
    def current(cls, **overrides: Any) -> "RuntimeManifest":
        data: dict[str, Any] = {
            "schema": RUNTIME_SCHEMA,
            "runtime": "trwm",
            "runtime_version": "0.1.0",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": platform.platform(),
            "created_ns": time.time_ns(),
        }
        data.update(overrides)
        data["manifest_hash"] = stable_hash({k: v for k, v in data.items() if k != "manifest_hash"})
        return cls(data)

    def valid(self) -> bool:
        if self.data.get("schema") != RUNTIME_SCHEMA:
            return False
        if self.data.get("runtime") != "trwm":
            return False
        expected = stable_hash({k: v for k, v in self.data.items() if k != "manifest_hash"})
        return self.data.get("manifest_hash") == expected


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    parent_head: str
    pre_state_hash: str
    post_state_hash: str | None
    rollback_state_hash: str | None
    branch_id: str
    proposal_trace_hash: str
    typed_candidate_hash: str
    hard_result: HardVerifierResult
    commit_decision: str
    committed: bool
    runtime_manifest: Mapping[str, Any]
    replay_bundle: Any
    rollback_bundle: Any
    soft_scores: Mapping[str, float] = field(default_factory=dict)
    random_seed: Any = None
    model_version: str = "manual.v1"
    projection_schema_version: str = "candidate.v1"
    artifact_hashes: Mapping[str, str] = field(default_factory=dict)
    receipt_schema: str = RECEIPT_SCHEMA
    timestamp_ns: int = field(default_factory=time.time_ns)
    receipt_hash: str = ""

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("receipt_hash", None)
        return data

    def computed_hash(self) -> str:
        return stable_hash(self.without_hash())

    def with_parent_and_hash(self, parent_head: str) -> "Receipt":
        pending = replace(self, parent_head=parent_head, receipt_hash="")
        return replace(pending, receipt_hash=pending.computed_hash())

    def static_valid(self) -> bool:
        if self.receipt_schema != RECEIPT_SCHEMA:
            return False
        if self.receipt_hash and self.receipt_hash != self.computed_hash():
            return False
        if self.committed:
            if not RuntimeManifest(self.runtime_manifest).valid():
                return False
            if not self.hard_result.accepted:
                return False
            if self.commit_decision != "commit":
                return False
            if self.post_state_hash is None or self.rollback_state_hash is None:
                return False
        if not self.committed and self.commit_decision == "commit":
            return False
        return True


class ReplayRollbackAdapter(Protocol):
    verifier_id: str
    verifier_version: str

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        ...

    def apply_commit(self, state: Any, candidate: TypedCandidate) -> Any:
        ...

    def replay(self, state: Any, receipt: Receipt) -> Any:
        ...

    def rollback(self, state: Any, receipt: Receipt) -> Any:
        ...


class Ledger:
    def __init__(self, head: str = GENESIS_HEAD, rows: Iterable[Receipt] | None = None):
        self.head = head
        self.rows: list[Receipt] = []
        if rows:
            for row in rows:
                self.append(row)

    def append(self, receipt: Receipt) -> Receipt:
        finalized = receipt.with_parent_and_hash(self.head)
        self.rows.append(finalized)
        self.head = chain_hash(finalized.parent_head, finalized.receipt_hash)
        return finalized

    def audit(self) -> bool:
        head = GENESIS_HEAD
        for receipt in self.rows:
            if not receipt.static_valid():
                return False
            if receipt.parent_head != head:
                return False
            if receipt.receipt_hash != receipt.computed_hash():
                return False
            head = chain_hash(head, receipt.receipt_hash)
        return head == self.head

    def committed_rows(self) -> list[Receipt]:
        return [row for row in self.rows if row.committed]


@dataclass(frozen=True)
class TransactionOutcome:
    state: Any
    receipt: Receipt
    committed: bool
    reason: str


class TransactionEngine:
    def __init__(
        self,
        adapter: ReplayRollbackAdapter,
        ledger: Ledger | None = None,
        manifest_factory: Callable[[], RuntimeManifest] | None = None,
    ):
        self.adapter = adapter
        self.ledger = ledger or Ledger()
        self.manifest_factory = manifest_factory or RuntimeManifest.current
        self.hard_verifier_calls = 0
        self.invalid_commit_count = 0
        self.soft_verifier_commit_count = 0
        self.verifier_mismatch_count = 0

    def transact(
        self,
        state: Any,
        trace: ProposalTrace,
        candidate: TypedCandidate,
        soft_scores: Mapping[str, float] | None = None,
        result: HardVerifierResult | None = None,
    ) -> TransactionOutcome:
        hard_result = result or self.adapter.verify(candidate)
        if result is None:
            self.hard_verifier_calls += 1
        return self.record_evaluated_candidate(state, trace, candidate, hard_result, soft_scores)

    def record_evaluated_candidate(
        self,
        state: Any,
        trace: ProposalTrace,
        candidate: TypedCandidate,
        hard_result: HardVerifierResult,
        soft_scores: Mapping[str, float] | None = None,
        force_decision: str | None = None,
    ) -> TransactionOutcome:
        pre = StateSnapshot.capture(state)
        manifest = self.manifest_factory()
        manifest_ok = manifest.valid()
        verifier_ok = self._hard_result_authorized(hard_result)
        post_state = None
        post_hash = None
        replay_ok = False
        rollback_ok = False
        commit_reason = "hard_reject"

        replay_bundle = {
            "candidate_payload": candidate.payload,
            "candidate_type": candidate.type_name,
            "candidate_schema": candidate.schema_version,
        }
        rollback_bundle = {"pre_state": pre.state}

        forced_reject = force_decision is not None and force_decision != "commit"
        if not verifier_ok:
            self.verifier_mismatch_count += 1
            commit_reason = "verifier_mismatch"
        elif forced_reject:
            commit_reason = force_decision or "forced_reject"
        elif hard_result.accepted and manifest_ok:
            try:
                post_state = self.adapter.apply_commit(state, candidate)
                post_hash = StateSnapshot.capture(post_state).state_hash
                provisional = self._make_receipt(
                    pre,
                    trace,
                    candidate,
                    hard_result,
                    manifest,
                    post_hash,
                    pre.state_hash,
                    replay_bundle,
                    rollback_bundle,
                    soft_scores or {},
                    commit_decision="provisional",
                    committed=False,
                )
                replay_state = self.adapter.replay(state, provisional)
                replay_ok = StateSnapshot.capture(replay_state).state_hash == post_hash
                rollback_state = self.adapter.rollback(post_state, provisional)
                rollback_ok = StateSnapshot.capture(rollback_state).state_hash == pre.state_hash
            except Exception as exc:  # fail closed
                commit_reason = f"replay_or_rollback_error:{type(exc).__name__}"
        elif hard_result.accepted:
            commit_reason = "manifest_invalid"
        elif hard_result.abstained:
            commit_reason = "hard_abstain"

        should_commit = verifier_ok and hard_result.accepted and manifest_ok and replay_ok and rollback_ok
        if forced_reject:
            should_commit = False
        elif should_commit:
            commit_reason = "commit"

        receipt = self._make_receipt(
            pre,
            trace,
            candidate,
            hard_result,
            manifest,
            post_hash if should_commit else None,
            pre.state_hash,
            replay_bundle,
            rollback_bundle,
            soft_scores or {},
            commit_decision=commit_reason,
            committed=should_commit,
        )
        receipt = self.ledger.append(receipt)

        if receipt.committed and not hard_result.accepted:
            self.invalid_commit_count += 1
        if receipt.committed and soft_scores and not hard_result.accepted:
            self.soft_verifier_commit_count += 1

        return TransactionOutcome(
            state=post_state if should_commit else state,
            receipt=receipt,
            committed=should_commit,
            reason=commit_reason,
        )

    def _hard_result_authorized(self, hard_result: HardVerifierResult) -> bool:
        return (
            hard_result.verifier_id == self.adapter.verifier_id
            and hard_result.verifier_version == self.adapter.verifier_version
        )

    def _make_receipt(
        self,
        pre: StateSnapshot,
        trace: ProposalTrace,
        candidate: TypedCandidate,
        hard_result: HardVerifierResult,
        manifest: RuntimeManifest,
        post_state_hash: str | None,
        rollback_state_hash: str | None,
        replay_bundle: Any,
        rollback_bundle: Any,
        soft_scores: Mapping[str, float],
        commit_decision: str,
        committed: bool,
    ) -> Receipt:
        return Receipt(
            receipt_id=str(uuid4()),
            parent_head="",
            pre_state_hash=pre.state_hash,
            post_state_hash=post_state_hash,
            rollback_state_hash=rollback_state_hash,
            branch_id=trace.branch_id,
            proposal_trace_hash=trace.trace_hash,
            typed_candidate_hash=candidate.candidate_hash,
            hard_result=hard_result,
            commit_decision=commit_decision,
            committed=committed,
            runtime_manifest=manifest.data,
            replay_bundle=replay_bundle,
            rollback_bundle=rollback_bundle,
            soft_scores=dict(soft_scores),
            random_seed=trace.seeds,
            model_version=trace.model_version,
            projection_schema_version=candidate.schema_version,
            artifact_hashes=candidate.hashes,
        )

    def replay_audit(self, seed_state: Any) -> Any:
        if not self.ledger.audit():
            raise AssertionError("ledger audit failed before replay")
        state = seed_state
        for receipt in self.ledger.rows:
            if not receipt.committed:
                continue
            next_state = self.adapter.replay(state, receipt)
            if StateSnapshot.capture(next_state).state_hash != receipt.post_state_hash:
                raise AssertionError(f"replay hash mismatch for {receipt.receipt_id}")
            state = next_state
        return state

    def rollback_audit(self, seed_state: Any) -> Any:
        if not self.ledger.audit():
            raise AssertionError("ledger audit failed before rollback")
        states = [seed_state]
        state = seed_state
        for receipt in self.ledger.rows:
            if receipt.committed:
                state = self.adapter.replay(state, receipt)
                states.append(state)

        for receipt in reversed(self.ledger.committed_rows()):
            state = self.adapter.rollback(state, receipt)
            expected = states[-2]
            if StateSnapshot.capture(state).state_hash != StateSnapshot.capture(expected).state_hash:
                raise AssertionError(f"rollback hash mismatch for {receipt.receipt_id}")
            states.pop()
        return state
