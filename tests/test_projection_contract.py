from __future__ import annotations

import unittest

from trwm.experiments.projection_contract import (
    PROJECTION_CONTRACT,
    ProjectionContractProjector,
    ProjectionGuardAdapter,
    ProjectionGuardState,
    make_projection_contract_traces,
    make_projection_guard_candidate,
    run_projection_contract_benchmark,
    stopping_margin_numerator,
)
from trwm.projection import (
    build_projection_manifest,
    projection_manifest_from_mapping,
    validate_projection_contract,
)


class ProjectionContractTests(unittest.TestCase):
    def test_projection_contract_detects_omitted_safety_field(self) -> None:
        state = ProjectionGuardState()
        projector = ProjectionContractProjector()
        partial = projector.project(state, make_projection_contract_traces()[0])

        unguarded = ProjectionGuardAdapter(state, enforce_contract=False).verify(partial)
        guarded = ProjectionGuardAdapter(state).verify(partial)

        self.assertTrue(unguarded.accepted)
        self.assertTrue(guarded.rejected)
        self.assertEqual(guarded.residual["missing_fields"], ("safety_clearance",))

    def test_projection_contract_rejects_stale_manifest_hashes(self) -> None:
        source = {"distance_to_obstacle": 5, "brake_accel": 2, "safety_clearance": 2}
        manifest = build_projection_manifest(
            source,
            ("distance_to_obstacle", "brake_accel", "safety_clearance"),
            projector_id="test.projector",
            projector_version="1.0",
        )
        stale_source = {"distance_to_obstacle": 4, "brake_accel": 2, "safety_clearance": 2}

        audit = validate_projection_contract(PROJECTION_CONTRACT, manifest, stale_source)

        self.assertFalse(audit.accepted)
        self.assertEqual(audit.stale_fields, ("distance_to_obstacle",))
        self.assertTrue(audit.source_hash_mismatch)

    def test_projection_manifest_hash_is_recomputed(self) -> None:
        source = {"distance_to_obstacle": 5, "brake_accel": 2, "safety_clearance": 2}
        manifest = build_projection_manifest(
            source,
            ("distance_to_obstacle", "brake_accel", "safety_clearance"),
            projector_id="test.projector",
            projector_version="1.0",
        )
        tampered = {**manifest.__dict__, "projection_hash": "0" * 64}

        audit = validate_projection_contract(PROJECTION_CONTRACT, projection_manifest_from_mapping(tampered), source)

        self.assertFalse(audit.accepted)
        self.assertTrue(audit.hash_mismatch)

    def test_exact_integer_stopping_margin(self) -> None:
        self.assertEqual(stopping_margin_numerator(distance=5, speed=4, brake=2, clearance=2), -4)
        self.assertEqual(stopping_margin_numerator(distance=5, speed=2, brake=2, clearance=2), 8)

    def test_projection_contract_benchmark_metrics(self) -> None:
        report = run_projection_contract_benchmark()

        self.assertEqual(report.candidate_count, 3)
        self.assertEqual(report.verifier_calls, 3)
        self.assertTrue(report.unguarded_false_positive_accepts)
        self.assertTrue(report.guarded_partial_rejected)
        self.assertTrue(report.guarded_fast_complete_rejected)
        self.assertTrue(report.guarded_safe_commit)
        self.assertEqual(report.missing_fields, ("safety_clearance",))
        self.assertEqual(report.unsafe_margin_numerator, -4)
        self.assertEqual(report.safe_margin_numerator, 8)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)

    def test_complete_safe_projection_commits(self) -> None:
        state = ProjectionGuardState()
        candidate = make_projection_guard_candidate(
            state,
            mode="crawl_complete",
            speed=2,
            covered_fields=("distance_to_obstacle", "brake_accel", "safety_clearance"),
            cost=2,
        )
        result = ProjectionGuardAdapter(state).verify(candidate)

        self.assertTrue(result.accepted)
        self.assertEqual(result.metadata["margin_numerator"], 8)


if __name__ == "__main__":
    unittest.main()
