from __future__ import annotations

import unittest

from examples.common import validate_example_evidence_certificate
from examples.molecular_dynamics_verlet import (
    DEFAULT_ENERGY_TOLERANCE,
    DEFAULT_MOMENTUM_TOLERANCE,
    MOLECULAR_DYNAMICS_SOURCES,
    euler_step,
    max_state_error,
    run_molecular_dynamics_verlet_certified_experiment,
    run_molecular_dynamics_verlet_experiment,
    velocity_verlet_step,
    MolecularDynamicsState,
)
from trwm.claims import validate_claim_certificate


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
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.receipt_count, 2)
        self.assertEqual(report.committed_count, 1)
        self.assertEqual(len(report.receipt_hashes), 2)
        self.assertEqual(report.learned_residual_kinds, {"integrator_mismatch": 1})

    def test_verlet_certified_result_binds_evidence_and_claim(self) -> None:
        result = run_molecular_dynamics_verlet_certified_experiment()
        report = result.report
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.experiment_id, report.experiment_id)
        self.assertEqual(evidence.domain, "molecular_dynamics")
        self.assertEqual(evidence.evidence_grade, "G1")
        self.assertEqual(evidence.receipt_count, report.receipt_count)
        self.assertEqual(evidence.receipt_hashes, report.receipt_hashes)
        self.assertEqual(evidence.committed_count, report.committed_count)
        self.assertEqual(evidence.rejected_count, report.rejected_count)
        self.assertEqual(evidence.sources, MOLECULAR_DYNAMICS_SOURCES)
        self.assertIn("velocity_verlet_integrator", evidence.hard_gate_keys)
        self.assertIn("energy_drift", evidence.hard_gate_keys)
        self.assertEqual(evidence.residual_kinds, ("integrator_mismatch",))

    def test_euler_and_verlet_steps_are_distinct(self) -> None:
        seed = MolecularDynamicsState(positions=(-0.56, 0.56), velocities=(0.015, -0.015))
        self.assertGreater(max_state_error(euler_step(seed), velocity_verlet_step(seed)), 1e-11)
