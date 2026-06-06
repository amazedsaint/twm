from __future__ import annotations

import unittest

from trwm.core import Ledger, TransactionEngine
from trwm.experiments.macro_grid import GridMacroAdapter, default_grid_state, default_macros, run_macro_grid_benchmark
from trwm.macro import MacroMemory, PrefixSafeMacroRuntime


class MacroGridTests(unittest.TestCase):
    def test_prefix_unsafe_macro_is_rejected_without_terminal_call(self) -> None:
        adapter = GridMacroAdapter()
        engine = TransactionEngine(adapter, ledger=Ledger())
        runtime = PrefixSafeMacroRuntime(engine, adapter)
        outcome = runtime.run(default_grid_state(), default_macros()[0])

        self.assertFalse(outcome.committed)
        self.assertEqual(outcome.reason, "prefix_unsafe")
        self.assertEqual(outcome.terminal_verifier_calls, 0)
        self.assertEqual(runtime.prefix_reject_count, 1)
        self.assertTrue(engine.ledger.audit())

    def test_safe_macro_commits_and_rolls_back(self) -> None:
        adapter = GridMacroAdapter()
        engine = TransactionEngine(adapter, ledger=Ledger())
        runtime = PrefixSafeMacroRuntime(engine, adapter)
        outcome = runtime.run(default_grid_state(), default_macros()[1])

        self.assertTrue(outcome.committed)
        self.assertEqual(outcome.terminal_verifier_calls, 1)
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.rollback_audit(default_grid_state()), default_grid_state())

    def test_macro_memory_reuses_accepted_macro(self) -> None:
        memory = MacroMemory()
        adapter = GridMacroAdapter()
        engine = TransactionEngine(adapter, ledger=Ledger())
        runtime = PrefixSafeMacroRuntime(engine, adapter)
        macros = default_macros()
        for macro in macros:
            outcome = runtime.run(default_grid_state(), macro)
            memory.update(outcome.receipt)
            if outcome.committed:
                break

        ranked = memory.rank("grid-3x3", macros)

        self.assertEqual(ranked[0].macro_id, "safe-around-wall")

    def test_macro_grid_benchmark_measures_prefix_and_reuse_gain(self) -> None:
        report = run_macro_grid_benchmark(episodes=16)

        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertLess(report.prefix_safe_calls_per_success, report.terminal_only_calls_per_success)
        self.assertGreater(report.macro_reuse_gain, 1.5)
        self.assertEqual(report.prefix_reject_count, 16)
        self.assertEqual(report.learned_prefix_reject_count, 1)


if __name__ == "__main__":
    unittest.main()
