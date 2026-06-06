from __future__ import annotations

import unittest

from examples.material_lattice_metropolis import (
    MaterialLatticeState,
    best_energy_lowering_flip,
    delta_energy,
    flip_spin,
    run_material_lattice_metropolis_experiment,
    total_energy,
)


class TestMaterialLatticeMetropolisExample(unittest.TestCase):
    def test_metropolis_repair_uses_hamiltonian_transaction_gate(self) -> None:
        report = run_material_lattice_metropolis_experiment()

        self.assertEqual(report.schema_version, "trwm.example.material_lattice_metropolis.v1")
        self.assertEqual(report.first_decision, "hard_reject")
        self.assertEqual(report.first_residual_kind, "metropolis_reject")
        self.assertGreater(report.first_delta_energy, 0)
        self.assertEqual(report.repaired_decision, "commit")
        self.assertTrue(report.repaired_committed)
        self.assertLessEqual(report.repaired_delta_energy, 0)
        self.assertEqual(report.energy_after - report.energy_before, report.repaired_delta_energy)
        self.assertEqual(report.metropolis_probability, 1.0)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.receipt_count, 2)
        self.assertEqual(report.committed_count, 1)
        self.assertEqual(len(report.receipt_hashes), 2)
        self.assertEqual(report.learned_residual_kinds, {"metropolis_reject": 1})

    def test_delta_energy_matches_total_energy_difference(self) -> None:
        state = MaterialLatticeState(
            lattice=(
                (1, 1, 1),
                (1, -1, 1),
                (-1, -1, -1),
            )
        )
        repair = best_energy_lowering_flip(state.lattice)
        row = repair["row"]
        col = repair["col"]
        post = flip_spin(state, row, col)
        self.assertEqual(
            total_energy(post.lattice) - total_energy(state.lattice),
            delta_energy(state.lattice, row, col),
        )
