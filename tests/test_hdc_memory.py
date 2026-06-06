from __future__ import annotations

import unittest

from trwm.experiments.hdc_memory import run_hdc_memory_benchmark


class HdcMemoryBenchmarkTests(unittest.TestCase):
    def test_hdc_memory_beats_no_memory_and_exact_match_under_context_shift(self) -> None:
        report = run_hdc_memory_benchmark(seed=19, episodes=96, label_count=24)

        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.noise_retrieval_ok)
        self.assertTrue(report.tamper_detected)
        self.assertEqual(report.exact_match_calls_per_success, report.no_memory_calls_per_success)
        self.assertLess(report.hdc_calls_per_success, report.no_memory_calls_per_success)
        self.assertLess(report.hdc_calls_per_success, report.exact_match_calls_per_success)
        self.assertGreater(report.hdc_gain_over_exact_match, 1.5)


if __name__ == "__main__":
    unittest.main()
