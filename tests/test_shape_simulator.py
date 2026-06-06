from __future__ import annotations

import unittest

from trwm.experiments.shape_simulator import run_shape_conditionality


class ShapeSimulatorTests(unittest.TestCase):
    def test_memory_lift_is_shape_conditional(self) -> None:
        report = run_shape_conditionality(seed=11, episodes=96, label_count=24)

        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertLess(report.low_memory_calls_per_success, report.low_random_calls_per_success)
        self.assertGreater(report.low_gain, report.high_gain)
        self.assertGreater(report.low_random_calls_per_success, 1.0)
        self.assertLess(report.low_preflight_r90, report.high_preflight_r90)
        self.assertTrue(report.low_preflight_fits_budget)
        self.assertFalse(report.high_preflight_fits_budget)
        self.assertGreater(report.low_preflight_energy_at_budget, report.high_preflight_energy_at_budget)


if __name__ == "__main__":
    unittest.main()
