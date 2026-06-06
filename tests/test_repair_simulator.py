from __future__ import annotations

import unittest

from trwm.core import Ledger
from trwm.experiments.repair_simulator import (
    run_repair_episode,
    run_residual_repair_benchmark,
    run_static_episode,
)
from trwm.repair import ResidualProgramRepairer, evaluate_program


class RepairSimulatorTests(unittest.TestCase):
    def test_program_evaluator_is_exact_integer_math(self) -> None:
        self.assertEqual(evaluate_program(({"op": "set", "value": 4}, {"op": "add", "value": -9})), -5)

    def test_residual_repair_improves_calls_per_success(self) -> None:
        report = run_residual_repair_benchmark(seed=17, episodes=64, label_min=-12, label_max=12)

        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.repair_success_rate, 1.0)
        self.assertLess(report.repair_calls_per_success, report.static_calls_per_success)
        self.assertGreater(report.repair_gain, 2.0)
        self.assertEqual(report.learned_repair_kinds.get("scalar_delta"), 64)

    def test_repair_episode_commits_after_residual_patch(self) -> None:
        static_ledger = Ledger()
        repair_ledger = Ledger()
        static = run_static_episode(target=7, label_order=[0, 1, 2, 7], ledger=static_ledger, episode=1)
        repair = run_repair_episode(target=7, initial_guess=0, ledger=repair_ledger, repairer=ResidualProgramRepairer(), episode=1)

        self.assertEqual(static.calls, 4)
        self.assertEqual(repair.calls, 2)
        self.assertTrue(static_ledger.audit())
        self.assertTrue(repair_ledger.audit())


if __name__ == "__main__":
    unittest.main()
