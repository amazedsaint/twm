from __future__ import annotations

import unittest

from trwm.preflight import one_hot_updates, shape_rank_preflight


class ShapeRankPreflightTests(unittest.TestCase):
    def test_low_rank_updates_fit_budget(self) -> None:
        updates = one_hot_updates([1, 1, 1, 3, 3, 7] * 8, 24)
        report = shape_rank_preflight(updates, rank_budget=4)

        self.assertLessEqual(report.r90, 3)
        self.assertTrue(report.fits_budget)
        self.assertEqual(report.energy_at_budget, 1.0)

    def test_high_rank_updates_refuse_compact_budget(self) -> None:
        updates = one_hot_updates(list(range(24)) * 4, 24)
        report = shape_rank_preflight(updates, rank_budget=4)

        self.assertGreater(report.r90, 4)
        self.assertFalse(report.fits_budget)
        self.assertLess(report.energy_at_budget, 0.5)

    def test_output_map_weights_energy(self) -> None:
        updates = ((1.0, 0.0), (0.0, 1.0))
        output_map = ((2.0, 0.0), (0.0, 1.0))
        report = shape_rank_preflight(updates, output_map=output_map, rank_budget=1)

        self.assertEqual(report.r90, 2)
        self.assertAlmostEqual(report.energy_at_budget, 0.8)

    def test_preflight_rejects_non_finite_values(self) -> None:
        with self.assertRaises(ValueError):
            shape_rank_preflight(((1.0, float("nan")),), rank_budget=1)
        with self.assertRaises(ValueError):
            shape_rank_preflight(((1.0, 0.0),), output_map=((1.0, float("inf")),), rank_budget=1)
        with self.assertRaises(ValueError):
            shape_rank_preflight(((1.0, 0.0),), rank_budget=1.5)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
