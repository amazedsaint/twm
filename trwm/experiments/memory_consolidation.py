from __future__ import annotations

from dataclasses import dataclass, replace

from ..core import Ledger, TransactionEngine
from ..experiments.macro_grid import GridMacroAdapter, default_grid_state
from ..macro import Macro, PrefixSafeMacroRuntime
from ..memory import (
    MACRO_MEMORY_SNAPSHOT_SCHEMA,
    BoundedMacroMemory,
    macro_token,
    validate_macro_memory_snapshot,
)


@dataclass(frozen=True)
class MemoryConsolidationReport:
    schema_version: str
    capacity_per_context: int
    raw_receipt_count: int
    stored_entry_count: int
    evicted_count: int
    safe_accepted_count: int
    unsafe_prefix_reject_count: int
    terminal_reject_count_forgotten: bool
    duplicate_safe_merged: bool
    safe_rank: int
    unsafe_rank: int
    snapshot_valid: bool
    snapshot_hash_stable: bool
    tamper_detected: bool
    ledger_audit: bool
    invalid_commit_count: int


def run_memory_consolidation_benchmark() -> MemoryConsolidationReport:
    context = "grid-3x3"
    unsafe = Macro("unsafe-through-wall", ("E", "S", "E", "S"), context=context)
    safe = Macro("safe-around-wall", ("E", "E", "S", "S"), context=context)
    safe_copy = Macro("safe-around-wall-copy", ("E", "E", "S", "S"), context=context)
    terminal_miss = Macro("terminal-miss", ("E",), context=context)
    stale_oob = Macro("stale-oob", ("N",), context=context)
    ledger = Ledger()
    memory = BoundedMacroMemory(capacity_per_context=2)

    sequence = (terminal_miss, stale_oob, unsafe, unsafe, unsafe, unsafe, safe, safe, safe_copy, safe_copy)
    for macro in sequence:
        outcome = _run_macro(ledger, macro)
        memory.update(outcome.receipt)

    snapshot = memory.snapshot()
    entries = {entry.token: entry for entry in snapshot.entries}
    safe_entry = entries[macro_token(safe.steps)]
    unsafe_entry = entries[macro_token(unsafe.steps)]
    ranked = memory.rank(context, (unsafe, terminal_miss, safe))
    tampered_entry = replace(safe_entry, accepted_count=99)
    tampered = replace(snapshot, entries=(tampered_entry, unsafe_entry))

    return MemoryConsolidationReport(
        schema_version=MACRO_MEMORY_SNAPSHOT_SCHEMA,
        capacity_per_context=memory.capacity_per_context,
        raw_receipt_count=len(sequence),
        stored_entry_count=len(snapshot.entries),
        evicted_count=snapshot.evicted_count,
        safe_accepted_count=safe_entry.accepted_count,
        unsafe_prefix_reject_count=unsafe_entry.prefix_reject_count,
        terminal_reject_count_forgotten=macro_token(terminal_miss.steps) not in entries,
        duplicate_safe_merged=safe_entry.accepted_count == 4 and safe_entry.first_seen_index == 7 and safe_entry.last_seen_index == 10,
        safe_rank=ranked.index(safe) + 1,
        unsafe_rank=ranked.index(unsafe) + 1,
        snapshot_valid=validate_macro_memory_snapshot(snapshot),
        snapshot_hash_stable=snapshot.snapshot_hash == memory.snapshot().snapshot_hash,
        tamper_detected=not validate_macro_memory_snapshot(tampered),
        ledger_audit=ledger.audit(),
        invalid_commit_count=sum(1 for row in ledger.rows if row.committed and not row.hard_result.accepted),
    )


def _run_macro(ledger: Ledger, macro: Macro):
    adapter = GridMacroAdapter()
    engine = TransactionEngine(adapter, ledger=ledger)
    runtime = PrefixSafeMacroRuntime(engine, adapter)
    return runtime.run(default_grid_state(), macro)
