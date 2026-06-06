from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .core import Receipt, stable_hash
from .macro import Macro


MACRO_MEMORY_ENTRY_SCHEMA = "trwm.macro_memory_entry.v1"
MACRO_MEMORY_SNAPSHOT_SCHEMA = "trwm.macro_memory_snapshot.v1"


@dataclass(frozen=True)
class MacroMemoryEntry:
    context: str
    token: str
    macro_steps: tuple[Any, ...]
    accepted_count: int
    prefix_reject_count: int
    terminal_reject_count: int
    first_seen_index: int
    last_seen_index: int
    latest_receipt_hash: str
    score: int
    retention_priority: int
    schema_version: str = MACRO_MEMORY_ENTRY_SCHEMA
    entry_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "macro_steps", tuple(self.macro_steps))
        if not self.entry_hash:
            object.__setattr__(self, "entry_hash", macro_memory_entry_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("entry_hash", None)
        return data


@dataclass(frozen=True)
class MacroMemorySnapshot:
    capacity_per_context: int
    total_updates: int
    evicted_count: int
    entries: tuple[MacroMemoryEntry, ...]
    schema_version: str = MACRO_MEMORY_SNAPSHOT_SCHEMA
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", macro_memory_snapshot_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("snapshot_hash", None)
        return data


class BoundedMacroMemory:
    """Bounded macro evidence memory. It ranks proposals only; it cannot commit."""

    def __init__(self, capacity_per_context: int = 16, *, staleness_penalty: int = 0):
        if not isinstance(capacity_per_context, int) or capacity_per_context <= 0:
            raise ValueError("capacity_per_context must be a positive integer")
        if not isinstance(staleness_penalty, int) or staleness_penalty < 0:
            raise ValueError("staleness_penalty must be a non-negative integer")
        self.capacity_per_context = capacity_per_context
        self.staleness_penalty = staleness_penalty
        self.total_updates = 0
        self.evicted_count = 0
        self._entries: dict[tuple[str, str], _MutableMacroEntry] = {}

    def update(self, receipt: Receipt) -> None:
        payload = _receipt_payload(receipt)
        macro_steps = _macro_steps(payload)
        if not macro_steps:
            return
        self.total_updates += 1
        context = str(payload.get("context", "global"))
        token = macro_token(macro_steps)
        key = (context, token)
        entry = self._entries.get(key)
        if entry is None:
            entry = _MutableMacroEntry(
                context=context,
                token=token,
                macro_steps=macro_steps,
                first_seen_index=self.total_updates,
                last_seen_index=self.total_updates,
            )
            self._entries[key] = entry
        entry.last_seen_index = self.total_updates
        entry.latest_receipt_hash = receipt.receipt_hash
        if receipt.committed and receipt.hard_result.accepted:
            entry.accepted_count += 1
        elif receipt.commit_decision == "prefix_unsafe":
            entry.prefix_reject_count += 1
        elif receipt.hard_result.rejected:
            entry.terminal_reject_count += 1
        self._evict_over_capacity(context)

    def score(self, context: str, macro: Macro) -> int:
        entry = self._entries.get((context, macro_token(macro.steps)))
        return entry.score if entry else 0

    def rank(self, context: str, macros: Iterable[Macro]) -> list[Macro]:
        indexed = list(enumerate(macros))

        def key(row: tuple[int, Macro]) -> tuple[int, int, int, int]:
            idx, macro = row
            entry = self._entries.get((context, macro_token(macro.steps)))
            if entry is None:
                return (0, 0, 0, idx)
            return (-entry.score, -entry.accepted_count, entry.prefix_reject_count + entry.terminal_reject_count, idx)

        return [macro for _, macro in sorted(indexed, key=key)]

    def snapshot(self) -> MacroMemorySnapshot:
        entries = tuple(
            self._entry_snapshot(entry)
            for entry in sorted(self._entries.values(), key=lambda row: (row.context, row.token))
        )
        return MacroMemorySnapshot(
            capacity_per_context=self.capacity_per_context,
            total_updates=self.total_updates,
            evicted_count=self.evicted_count,
            entries=entries,
        )

    def _entry_snapshot(self, entry: "_MutableMacroEntry") -> MacroMemoryEntry:
        return MacroMemoryEntry(
            context=entry.context,
            token=entry.token,
            macro_steps=entry.macro_steps,
            accepted_count=entry.accepted_count,
            prefix_reject_count=entry.prefix_reject_count,
            terminal_reject_count=entry.terminal_reject_count,
            first_seen_index=entry.first_seen_index,
            last_seen_index=entry.last_seen_index,
            latest_receipt_hash=entry.latest_receipt_hash,
            score=entry.score,
            retention_priority=entry.retention_priority(self.total_updates, self.staleness_penalty),
        )

    def _evict_over_capacity(self, context: str) -> None:
        rows = [entry for entry in self._entries.values() if entry.context == context]
        while len(rows) > self.capacity_per_context:
            victim = min(
                rows,
                key=lambda entry: (
                    entry.retention_priority(self.total_updates, self.staleness_penalty),
                    entry.accepted_count,
                    -(entry.prefix_reject_count + entry.terminal_reject_count),
                    -entry.last_seen_index,
                    entry.token,
                ),
            )
            del self._entries[(victim.context, victim.token)]
            self.evicted_count += 1
            rows = [entry for entry in self._entries.values() if entry.context == context]


@dataclass
class _MutableMacroEntry:
    context: str
    token: str
    macro_steps: tuple[Any, ...]
    first_seen_index: int
    last_seen_index: int
    latest_receipt_hash: str = ""
    accepted_count: int = 0
    prefix_reject_count: int = 0
    terminal_reject_count: int = 0

    @property
    def score(self) -> int:
        return 4 * self.accepted_count - 3 * self.prefix_reject_count - 2 * self.terminal_reject_count

    def retention_priority(self, current_index: int, staleness_penalty: int) -> int:
        evidence = 4 * self.accepted_count + 3 * self.prefix_reject_count + 2 * self.terminal_reject_count
        age = max(0, current_index - self.last_seen_index)
        return max(0, evidence - staleness_penalty * age)


def macro_token(steps: Iterable[Any]) -> str:
    return stable_hash(tuple(steps))


def macro_memory_entry_hash(entry: MacroMemoryEntry | Mapping[str, Any]) -> str:
    data = _entry_mapping(entry)
    data.pop("entry_hash", None)
    return stable_hash(data)


def macro_memory_snapshot_hash(snapshot: MacroMemorySnapshot | Mapping[str, Any]) -> str:
    data = _snapshot_mapping(snapshot)
    data.pop("snapshot_hash", None)
    return stable_hash(data)


def validate_macro_memory_snapshot(snapshot: MacroMemorySnapshot | Mapping[str, Any]) -> bool:
    try:
        data = _snapshot_mapping(snapshot)
        if data.get("schema_version") != MACRO_MEMORY_SNAPSHOT_SCHEMA:
            return False
        if int(data.get("capacity_per_context", 0)) <= 0:
            return False
        entries = tuple(_coerce_entry(entry) for entry in data.get("entries", ()))
        for entry in entries:
            if entry.schema_version != MACRO_MEMORY_ENTRY_SCHEMA:
                return False
            if entry.entry_hash != macro_memory_entry_hash(entry):
                return False
        return data.get("snapshot_hash") == macro_memory_snapshot_hash(data)
    except Exception:
        return False


def _coerce_entry(value: MacroMemoryEntry | Mapping[str, Any]) -> MacroMemoryEntry:
    if isinstance(value, MacroMemoryEntry):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("macro memory entry must be a mapping")
    return MacroMemoryEntry(
        context=str(value.get("context", "")),
        token=str(value.get("token", "")),
        macro_steps=tuple(value.get("macro_steps", ())),
        accepted_count=int(value.get("accepted_count", 0)),
        prefix_reject_count=int(value.get("prefix_reject_count", 0)),
        terminal_reject_count=int(value.get("terminal_reject_count", 0)),
        first_seen_index=int(value.get("first_seen_index", 0)),
        last_seen_index=int(value.get("last_seen_index", 0)),
        latest_receipt_hash=str(value.get("latest_receipt_hash", "")),
        score=int(value.get("score", 0)),
        retention_priority=int(value.get("retention_priority", 0)),
        schema_version=str(value.get("schema_version", MACRO_MEMORY_ENTRY_SCHEMA)),
        entry_hash=str(value.get("entry_hash", "")),
    )


def _entry_mapping(entry: MacroMemoryEntry | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(entry, MacroMemoryEntry):
        return entry.without_hash() | {"entry_hash": entry.entry_hash}
    if isinstance(entry, Mapping):
        return dict(entry)
    raise TypeError("macro memory entry must be a mapping")


def _snapshot_mapping(snapshot: MacroMemorySnapshot | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(snapshot, MacroMemorySnapshot):
        return snapshot.without_hash() | {"snapshot_hash": snapshot.snapshot_hash}
    if isinstance(snapshot, Mapping):
        return dict(snapshot)
    raise TypeError("macro memory snapshot must be a mapping")


def _receipt_payload(receipt: Receipt) -> Mapping[str, Any]:
    bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
    payload = bundle.get("candidate_payload", {})
    return payload if isinstance(payload, Mapping) else {}


def _macro_steps(payload: Mapping[str, Any]) -> tuple[Any, ...]:
    value = payload.get("macro", ())
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return ()
