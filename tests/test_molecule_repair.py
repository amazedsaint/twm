from __future__ import annotations

import unittest

from trwm.core import Ledger, ProposalTrace, TransactionEngine
from trwm.experiments.molecule_repair import (
    MoleculeGraphAdapter,
    MoleculeRepairState,
    MoleculeResidualRepairer,
    make_molecule_candidate,
    make_molecule_repair_problem,
    molecular_formula,
    replace_molecule_edit,
    run_molecule_repair_benchmark,
    run_repair_molecule_episode,
    run_static_molecule_episode,
)


class MoleculeRepairTests(unittest.TestCase):
    def test_formula_uses_organic_subset_valence_hydrogens(self) -> None:
        problem = make_molecule_repair_problem("O", 1)
        graph = replace_molecule_edit(problem.template_graph, "a2", "O", "b1", 1)

        self.assertEqual(molecular_formula(graph), {"C": 2, "H": 6, "O": 1})

    def test_verifier_rejects_formula_mismatch_with_unique_edit_repair(self) -> None:
        problem = make_molecule_repair_problem("O", 1)
        candidate = make_molecule_candidate(problem, "C", 3)

        result = MoleculeGraphAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "formula_mismatch")
        self.assertEqual(
            result.residual["repair"],
            {"atom_id": "a2", "bond_id": "b1", "element": "O", "bond_order": 1, "formula": {"C": 2, "H": 6, "O": 1}},
        )

    def test_verifier_rejects_valence_excess_before_formula_check(self) -> None:
        problem = make_molecule_repair_problem("O", 1)
        candidate = make_molecule_candidate(problem, "F", 2)

        result = MoleculeGraphAdapter().verify(candidate)

        self.assertTrue(result.rejected)
        self.assertEqual(result.residual["kind"], "valence_exceeded")
        self.assertEqual(result.residual["violations"][0]["element"], "F")
        self.assertEqual(result.residual["repair"]["element"], "O")

    def test_residual_repair_commits_after_formula_feedback(self) -> None:
        problem = make_molecule_repair_problem("N", 2)
        ledger = Ledger()
        result = run_repair_molecule_episode(problem, ledger=ledger, repairer=MoleculeResidualRepairer(), episode=1)

        self.assertEqual(result.calls, 2)
        self.assertTrue(result.success)
        self.assertTrue(result.audit_ok)
        self.assertTrue(result.replay_rollback_ok)
        self.assertEqual(len(ledger.committed_rows()), 1)
        self.assertEqual(ledger.committed_rows()[0].replay_bundle["candidate_payload"]["element"], "N")
        self.assertEqual(ledger.committed_rows()[0].replay_bundle["candidate_payload"]["bond_order"], 2)

    def test_molecule_repair_benchmark_improves_over_static_edit_search(self) -> None:
        report = run_molecule_repair_benchmark(seed=53, episodes=36)

        self.assertEqual(report.episodes, 36)
        self.assertEqual(report.candidate_space_size, 15)
        self.assertEqual(report.repair_success_rate, 1.0)
        self.assertEqual(report.ledger_audit_rate, 1.0)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertLess(report.repair_calls_per_success, report.static_calls_per_success)
        self.assertGreater(report.repair_gain, 2.5)
        self.assertEqual(report.learned_residual_kinds.get("formula_mismatch"), 36)

    def test_static_episode_uses_same_edit_candidates(self) -> None:
        problem = make_molecule_repair_problem("N", 1)
        result = run_static_molecule_episode(problem, (("C", 1), ("C", 2), ("N", 1)), ledger=Ledger(), episode=4)

        self.assertEqual(result.calls, 3)
        self.assertTrue(result.success)

    def test_valid_graph_for_wrong_problem_fails_closed(self) -> None:
        problem_a = make_molecule_repair_problem("O", 1)
        problem_b = make_molecule_repair_problem("N", 2)
        candidate = make_molecule_candidate(problem_a, "O", 1)
        engine = TransactionEngine(MoleculeGraphAdapter(), ledger=Ledger())

        outcome = engine.transact(
            MoleculeRepairState(problem=problem_b),
            ProposalTrace(
                branch_id="wrong-molecule-problem",
                actions=({"element": "O", "bond_order": 1},),
                seeds=("molecule", "wrong-problem"),
                model_version="molecule.test.v1",
            ),
            candidate,
        )

        self.assertFalse(outcome.committed)
        self.assertTrue(outcome.reason.startswith("replay_or_rollback_error:"))
        self.assertEqual(engine.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
