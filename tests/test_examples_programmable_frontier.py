from __future__ import annotations

import unittest

from examples.material_lattice_metropolis import run_material_lattice_metropolis_certified_experiment
from examples.molecular_dynamics_verlet import run_molecular_dynamics_verlet_certified_experiment
from examples.programmable_world_model_frontier import (
    build_programmable_world_model_frontier_result,
    run_programmable_world_model_frontier_experiment,
    tamper_first_child_certificate,
)
from examples.robotic_safety_envelope import run_robotic_safety_envelope_certified_experiment
from trwm.claims import validate_claim_certificate


class TestProgrammableWorldModelFrontierExample(unittest.TestCase):
    def test_frontier_report_aggregates_three_certified_domains(self) -> None:
        result = run_programmable_world_model_frontier_experiment()
        report = result.report
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.example.programmable_world_model_frontier.v1")
        self.assertEqual(report.domain_count, 3)
        self.assertEqual(
            set(report.child_experiment_ids),
            {"robotic_safety_envelope", "molecular_dynamics_verlet", "material_lattice_metropolis"},
        )
        self.assertEqual(len(report.rows), 3)
        self.assertTrue(report.all_evidence_valid)
        self.assertTrue(report.all_claims_supported)
        self.assertEqual(report.total_invalid_commit_count, 0)
        self.assertEqual(report.total_receipt_count, 6)
        self.assertEqual(report.total_committed_count, 3)
        self.assertEqual(report.total_rejected_count, 3)
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "supported")

    def test_frontier_claim_rejects_tampered_child_certificate(self) -> None:
        children = (
            run_robotic_safety_envelope_certified_experiment(),
            run_molecular_dynamics_verlet_certified_experiment(),
            run_material_lattice_metropolis_certified_experiment(),
        )
        result = build_programmable_world_model_frontier_result(tamper_first_child_certificate(children))

        self.assertFalse(result.report.all_evidence_valid)
        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertIn("all_evidence_certificates_valid", result.claim_certificate.failed_keys)
