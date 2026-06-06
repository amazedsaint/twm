from __future__ import annotations

import unittest

from trwm.core import Ledger
from trwm.experiments.sat_csp import (
    CnfResidualRepairer,
    CnfSatAdapter,
    assignment_from_mask,
    formula_from_target,
    make_cnf_candidate,
    run_residual_sat_episode,
    run_sat_csp_benchmark,
    run_static_sat_episode,
    unsatisfied_clauses,
)


class SatCspTests(unittest.TestCase):
    def test_cnf_verifier_returns_unsatisfied_clause_residual(self) -> None:
        formula = formula_from_target((True, False, True))
        assignment = (False, False, False)
        candidate = make_cnf_candidate(formula, assignment)

        result = CnfSatAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(unsatisfied_clauses(formula, assignment), (0, 2))
        self.assertEqual(result.residual["kind"], "unsatisfied_clause")
        self.assertEqual(result.residual["repair"], {"variable": 1, "value": True})

    def test_residual_sat_episode_repairs_assignment_before_commit(self) -> None:
        formula = formula_from_target((True, False, True))
        ledger = Ledger()
        result = run_residual_sat_episode(
            formula,
            initial_assignment=(False, False, False),
            ledger=ledger,
            repairer=CnfResidualRepairer(),
            episode=1,
        )

        self.assertEqual(result.calls, 3)
        self.assertTrue(result.success)
        self.assertTrue(ledger.audit())
        self.assertEqual(len(ledger.committed_rows()), 1)

    def test_sat_csp_benchmark_improves_over_exhaustive_static_order(self) -> None:
        report = run_sat_csp_benchmark(seed=29, episodes=32, variable_count=7)

        self.assertEqual(report.variable_count, 7)
        self.assertEqual(report.assignment_space_size, 128)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.repair_success_rate, 1.0)
        self.assertLess(report.repair_calls_per_success, report.static_calls_per_success)
        self.assertGreater(report.repair_gain, 5.0)
        self.assertEqual(
            report.learned_residual_kinds.get("unsatisfied_clause"),
            int(report.repair_calls_per_success * report.episodes) - report.episodes,
        )

    def test_static_episode_uses_same_case_assignment_order(self) -> None:
        formula = formula_from_target(assignment_from_mask(5, 3))
        order = [assignment_from_mask(mask, 3) for mask in range(8)]
        result = run_static_sat_episode(formula, order, Ledger(), episode=2)

        self.assertEqual(result.calls, 6)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
