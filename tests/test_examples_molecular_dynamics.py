from __future__ import annotations

import unittest

from examples.molecular_dynamics_verlet import (
    DEFAULT_ENERGY_TOLERANCE,
    DEFAULT_MOMENTUM_TOLERANCE,
    euler_step,
    max_state_error,
    run_molecular_dynamics_verlet_experiment,
    velocity_verlet_step,
    MolecularDynamicsState,
)


class TestMolecularDynamicsVerletExample(unittest.TestCase):
    def test_verlet_repair_uses_transactional_physics_gate(self) -> None:
        report = run_molecular_dynamics_verlet_experiment()

        self.assertEqual(report.schema_version, "trwm.example.molecular_dynamics_verlet.v1")
        self.assertEqual(report.first_decision, "hard_reject")
        self.assertEqual(report.first_residual_kind, "integrator_mismatch")
        self.assertEqual(report.repaired_decision, "commit")
        self.assertTrue(report.repaired_committed)
        self.assertEqual(report.integrator, "velocity_verlet")
        self.assertLessEqual(report.energy_drift, DEFAULT_ENERGY_TOLERANCE)
        self.assertLessEqual(report.momentum_drift, DEFAULT_MOMENTUM_TOLERANCE)
        self.assertGreaterEqual(report.min_separation, 0.78)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.receipt_count, 2)
        self.assertEqual(report.committed_count, 1)
        self.assertEqual(len(report.receipt_hashes), 2)
        self.assertEqual(report.learned_residual_kinds, {"integrator_mismatch": 1})

    def test_euler_and_verlet_steps_are_distinct(self) -> None:
        seed = MolecularDynamicsState(positions=(-0.56, 0.56), velocities=(0.015, -0.015))
        self.assertGreater(max_state_error(euler_step(seed), velocity_verlet_step(seed)), 1e-11)
