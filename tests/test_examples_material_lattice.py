from __future__ import annotations

import unittest

from examples.common import validate_example_evidence_certificate
from examples.material_lattice_metropolis import (
    MATERIAL_LATTICE_SOURCES,
    MaterialLatticeState,
    best_energy_lowering_flip,
    delta_energy,
    flip_spin,
    run_material_lattice_metropolis_certified_experiment,
    run_material_lattice_metropolis_experiment,
    total_energy,
)
from trwm.claims import validate_claim_certificate


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
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.receipt_count, 2)
        self.assertEqual(report.committed_count, 1)
        self.assertEqual(len(report.receipt_hashes), 2)
        self.assertEqual(report.learned_residual_kinds, {"metropolis_reject": 1})

    def test_metropolis_certified_result_binds_evidence_and_claim(self) -> None:
        result = run_material_lattice_metropolis_certified_experiment()
        report = result.report
        evidence = result.evidence_certificate
        claim = result.claim_certificate

        self.assertTrue(validate_example_evidence_certificate(evidence, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")
        self.assertEqual(evidence.experiment_id, report.experiment_id)
        self.assertEqual(evidence.domain, "material_science")
        self.assertEqual(evidence.evidence_grade, "G1")
        self.assertEqual(evidence.receipt_count, report.receipt_count)
        self.assertEqual(evidence.receipt_hashes, report.receipt_hashes)
        self.assertEqual(evidence.committed_count, report.committed_count)
        self.assertEqual(evidence.rejected_count, report.rejected_count)
        self.assertEqual(evidence.sources, MATERIAL_LATTICE_SOURCES)
        self.assertIn("ising_hamiltonian_delta", evidence.hard_gate_keys)
        self.assertIn("receipt_bound_randomness", evidence.hard_gate_keys)
        self.assertEqual(evidence.residual_kinds, ("metropolis_reject",))

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
