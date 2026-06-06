from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable, Sequence

from .core import GENESIS_HEAD, Ledger, Receipt, ReplayRollbackAdapter, StateSnapshot, chain_hash, stable_hash


CHECKPOINT_SCHEMA = "trwm.checkpoint.v1"


@dataclass(frozen=True)
class CheckpointCertificate:
    base_head: str
    checkpoint_head: str
    start_index: int
    end_index: int
    receipt_hashes: tuple[str, ...]
    committed_receipt_hashes: tuple[str, ...]
    receipt_count: int
    committed_count: int
    state_hash: str
    checkpoint_state: Any
    adapter_id: str
    adapter_version: str
    state_schema_version: str = "state.v1"
    schema_version: str = CHECKPOINT_SCHEMA
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_hashes", tuple(str(item) for item in self.receipt_hashes))
        object.__setattr__(self, "committed_receipt_hashes", tuple(str(item) for item in self.committed_receipt_hashes))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", checkpoint_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data

    def computed_hash(self) -> str:
        return stable_hash(self.without_hash())

    def valid(self) -> bool:
        return validate_checkpoint(self)


@dataclass(frozen=True)
class CheckpointReplayResult:
    state: Any
    head: str
    suffix_receipt_count: int
    suffix_committed_count: int


def checkpoint_certificate_hash(checkpoint: CheckpointCertificate | dict[str, Any]) -> str:
    data = _checkpoint_without_hash(checkpoint)
    return stable_hash(data)


def chain_receipt_hashes(base_head: str, receipt_hashes: Iterable[str]) -> str:
    head = str(base_head)
    _assert_hex_hash(head, "base_head")
    for receipt_hash in receipt_hashes:
        receipt_hash = str(receipt_hash)
        _assert_hex_hash(receipt_hash, "receipt_hash")
        head = chain_hash(head, receipt_hash)
    return head


def build_checkpoint(
    ledger: Ledger,
    adapter: ReplayRollbackAdapter,
    seed_state: Any,
    *,
    end_index: int | None = None,
    state_schema_version: str = "state.v1",
) -> CheckpointCertificate:
    if not ledger.audit():
        raise ValueError("ledger audit must pass before checkpointing")
    rows = tuple(ledger.rows)
    end = len(rows) if end_index is None else int(end_index)
    if end < 0 or end > len(rows):
        raise ValueError("checkpoint end_index must be within the ledger")
    state = seed_state
    committed_hashes: list[str] = []
    for receipt in rows[:end]:
        if receipt.committed:
            state = adapter.replay(state, receipt)
            if StateSnapshot.capture(state, state_schema_version).state_hash != receipt.post_state_hash:
                raise AssertionError(f"checkpoint replay hash mismatch for {receipt.receipt_id}")
            committed_hashes.append(receipt.receipt_hash)
    receipt_hashes = tuple(row.receipt_hash for row in rows[:end])
    snapshot = StateSnapshot.capture(state, state_schema_version)
    return CheckpointCertificate(
        base_head=GENESIS_HEAD,
        checkpoint_head=chain_receipt_hashes(GENESIS_HEAD, receipt_hashes),
        start_index=0,
        end_index=end,
        receipt_hashes=receipt_hashes,
        committed_receipt_hashes=tuple(committed_hashes),
        receipt_count=len(receipt_hashes),
        committed_count=len(committed_hashes),
        state_hash=snapshot.state_hash,
        checkpoint_state=state,
        adapter_id=str(adapter.verifier_id),
        adapter_version=str(adapter.verifier_version),
        state_schema_version=state_schema_version,
    )


def validate_checkpoint(checkpoint: CheckpointCertificate | dict[str, Any]) -> bool:
    try:
        data = _checkpoint_mapping(checkpoint)
        if data.get("schema_version") != CHECKPOINT_SCHEMA:
            return False
        if int(data.get("start_index", -1)) != 0:
            return False
        receipt_hashes = tuple(str(item) for item in data.get("receipt_hashes", ()))
        committed_receipt_hashes = tuple(str(item) for item in data.get("committed_receipt_hashes", ()))
        if int(data.get("end_index", -1)) != len(receipt_hashes):
            return False
        if int(data.get("receipt_count", -1)) != len(receipt_hashes):
            return False
        if int(data.get("committed_count", -1)) != len(committed_receipt_hashes):
            return False
        if not set(committed_receipt_hashes).issubset(set(receipt_hashes)):
            return False
        if data.get("checkpoint_head") != chain_receipt_hashes(str(data.get("base_head")), receipt_hashes):
            return False
        snapshot = StateSnapshot.capture(data.get("checkpoint_state"), str(data.get("state_schema_version", "state.v1")))
        if data.get("state_hash") != snapshot.state_hash:
            return False
        if data.get("certificate_hash") != checkpoint_certificate_hash(data):
            return False
        return True
    except Exception:
        return False


def replay_from_checkpoint(
    checkpoint: CheckpointCertificate | dict[str, Any],
    suffix_rows: Sequence[Receipt],
    adapter: ReplayRollbackAdapter,
    *,
    expected_final_head: str | None = None,
    state_schema_version: str | None = None,
) -> CheckpointReplayResult:
    if not validate_checkpoint(checkpoint):
        raise ValueError("invalid checkpoint certificate")
    data = _checkpoint_mapping(checkpoint)
    if str(data.get("adapter_id")) != adapter.verifier_id or str(data.get("adapter_version")) != adapter.verifier_version:
        raise ValueError("checkpoint adapter identity does not match replay adapter")
    schema = state_schema_version or str(data.get("state_schema_version", "state.v1"))
    state = data.get("checkpoint_state")
    head = str(data.get("checkpoint_head"))
    suffix_committed = 0
    for receipt in suffix_rows:
        if not receipt.static_valid():
            raise ValueError(f"invalid suffix receipt: {receipt.receipt_id}")
        if receipt.parent_head != head:
            raise ValueError(f"suffix receipt parent mismatch: {receipt.receipt_id}")
        if receipt.receipt_hash != receipt.computed_hash():
            raise ValueError(f"suffix receipt hash mismatch: {receipt.receipt_id}")
        if receipt.committed:
            state = adapter.replay(state, receipt)
            if StateSnapshot.capture(state, schema).state_hash != receipt.post_state_hash:
                raise AssertionError(f"suffix replay hash mismatch for {receipt.receipt_id}")
            suffix_committed += 1
        head = chain_hash(head, receipt.receipt_hash)
    if expected_final_head is not None and head != expected_final_head:
        raise ValueError("compacted replay final head mismatch")
    return CheckpointReplayResult(state=state, head=head, suffix_receipt_count=len(suffix_rows), suffix_committed_count=suffix_committed)


def audit_compacted_view(
    checkpoint: CheckpointCertificate | dict[str, Any],
    suffix_rows: Sequence[Receipt],
    adapter: ReplayRollbackAdapter,
    *,
    expected_final_head: str | None = None,
) -> bool:
    try:
        replay_from_checkpoint(checkpoint, suffix_rows, adapter, expected_final_head=expected_final_head)
        return True
    except Exception:
        return False


def tamper_checkpoint_state(checkpoint: CheckpointCertificate, state: Any) -> CheckpointCertificate:
    return replace(checkpoint, checkpoint_state=state)


def _checkpoint_without_hash(checkpoint: CheckpointCertificate | dict[str, Any]) -> dict[str, Any]:
    data = dict(_checkpoint_mapping(checkpoint))
    data.pop("certificate_hash", None)
    return data


def _checkpoint_mapping(checkpoint: CheckpointCertificate | dict[str, Any]) -> dict[str, Any]:
    if isinstance(checkpoint, CheckpointCertificate):
        return asdict(checkpoint)
    if isinstance(checkpoint, dict):
        return dict(checkpoint)
    raise TypeError("checkpoint must be a CheckpointCertificate or dict")


def _assert_hex_hash(value: str, label: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
