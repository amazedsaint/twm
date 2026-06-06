from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.experiments.memory_consolidation import run_memory_consolidation_benchmark
from trwm.memory import (
    MACRO_MEMORY_SNAPSHOT_SCHEMA,
    BoundedMacroMemory,
    validate_macro_memory_snapshot,
)


class MemoryConsolidationTests(unittest.TestCase):
    def test_invalid_capacity_and_staleness_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            BoundedMacroMemory(0)
        with self.assertRaises(ValueError):
            BoundedMacroMemory(2, staleness_penalty=-1)

    def test_memory_consolidates_duplicates_and_evicts_weak_rows(self) -> None:
        report = run_memory_consolidation_benchmark()

        self.assertEqual(report.schema_version, MACRO_MEMORY_SNAPSHOT_SCHEMA)
        self.assertEqual(report.capacity_per_context, 2)
        self.assertEqual(report.raw_receipt_count, 10)
        self.assertEqual(report.stored_entry_count, 2)
        self.assertEqual(report.evicted_count, 2)
        self.assertEqual(report.safe_accepted_count, 4)
        self.assertEqual(report.unsafe_prefix_reject_count, 4)
        self.assertTrue(report.terminal_reject_count_forgotten)
        self.assertTrue(report.duplicate_safe_merged)
        self.assertEqual(report.safe_rank, 1)
        self.assertEqual(report.unsafe_rank, 3)
        self.assertTrue(report.snapshot_valid)
        self.assertTrue(report.snapshot_hash_stable)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)

    def test_snapshot_validation_detects_entry_tamper(self) -> None:
        memory = BoundedMacroMemory(2)
        report = run_memory_consolidation_benchmark()
        self.assertTrue(report.snapshot_valid)
        self.assertTrue(validate_macro_memory_snapshot(memory.snapshot()))

        snapshot = memory.snapshot()
        tampered = replace(snapshot, capacity_per_context=0)
        self.assertFalse(validate_macro_memory_snapshot(tampered))


if __name__ == "__main__":
    unittest.main()
