from __future__ import annotations

import unittest
from dataclasses import replace

from trwm.core import ProposalTrace
from trwm.experiments.game_of_life import LifePredecessorAdapter, LifeProjector, LifeState, life_step
from trwm.experiments.repair_simulator import ScalarProgramAdapter, make_scalar_candidate
from trwm.experiments.sdk_manifest import run_sdk_manifest_benchmark
from trwm.experiments.sdk_multi_domain import run_multi_domain_sdk_benchmark
from trwm.experiments.sdk_transfer_guard import run_sdk_transfer_guard_benchmark
from trwm.sdk import (
    TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA,
    ProgrammableSubstrate,
    TransferGuardedDomainRouter,
    validate_domain_manifest,
    validate_transfer_guarded_domain_route,
)
from trwm.transfer import build_transfer_evaluation_certificate


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
NO_INVALID_COMMITS = 0


class MultiDomainSdkTests(unittest.TestCase):
    def test_multi_domain_sdk_exit_gate(self) -> None:
        report = run_multi_domain_sdk_benchmark()

        self.assertEqual(report.domains_supported, 11)
        self.assertEqual(report.committed_domains, 11)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.scalar_hard_calls, 2)
        self.assertEqual(report.life_hard_calls, 2)
        self.assertEqual(report.grid_hard_calls, 1)
        self.assertEqual(report.sokoban_hard_calls, 1)
        self.assertEqual(report.operations_hard_calls, 1)
        self.assertEqual(report.proof_hard_calls, 1)
        self.assertEqual(report.circuit_hard_calls, 1)
        self.assertEqual(report.molecule_hard_calls, 1)
        self.assertEqual(report.code_hard_calls, 1)
        self.assertEqual(report.robot_hard_calls, 1)
        self.assertEqual(report.chess_hard_calls, 1)
        self.assertEqual(report.router_top_domain, "scalar")
        self.assertEqual(report.router_scalar_counts, (2, 0))
        self.assertEqual(report.router_life_counts, (1, 1))
        self.assertEqual(report.router_sokoban_counts, (1, 0))
        self.assertEqual(report.router_operations_counts, (1, 0))
        self.assertEqual(report.router_proof_counts, (1, 0))
        self.assertEqual(report.router_circuit_counts, (1, 0))
        self.assertEqual(report.router_molecule_counts, (1, 0))
        self.assertEqual(report.router_code_counts, (1, 0))
        self.assertEqual(report.router_robot_counts, (1, 0))
        self.assertEqual(report.router_chess_counts, (1, 0))

    def test_router_learns_from_receipts_without_commit_authority(self) -> None:
        substrate = ProgrammableSubstrate()
        substrate.register("scalar", ScalarProgramAdapter())
        substrate.register("life", LifePredecessorAdapter())

        scalar_state = {"episode": 0, "target": 7, "solved": False}
        scalar = substrate.submit(
            "scalar",
            scalar_state,
            ProposalTrace(
                branch_id="router-scalar",
                actions=({"op": "set", "value": 7},),
                seeds=("router", "scalar"),
                model_version="sdk.scalar.v1",
            ),
            make_scalar_candidate("router", 7, ({"op": "set", "value": 7},)),
            context="router",
        )

        target = life_step(((0, 0, 0), (1, 1, 1), (0, 0, 0)))
        life_state = LifeState(target=target)
        bad_trace = ProposalTrace(
            branch_id="router-life-reject",
            actions=({"predecessor": ((0, 0, 0), (0, 0, 0), (0, 0, 0)), "cost": 1},),
            seeds=("router", "life"),
            model_version="sdk.life.v1",
        )
        life = substrate.submit(
            "life",
            life_state,
            bad_trace,
            LifeProjector().project(life_state, bad_trace),
            context="router",
        )

        self.assertTrue(scalar.committed)
        self.assertFalse(life.committed)
        self.assertEqual(substrate.rank_domains("router", ("life", "scalar")), ["scalar", "life"])
        self.assertTrue(substrate.audit_domain("scalar", scalar_state).ok)
        self.assertTrue(substrate.domains["life"].ledger.audit())
        self.assertEqual(substrate.invalid_commit_count(), 0)

    def test_transfer_guarded_router_admits_positive_transfer_route(self) -> None:
        router = TransferGuardedDomainRouter()
        certificate = build_transfer_evaluation_certificate(
            claim_id="positive-sdk-transfer",
            learner_id="source-policy",
            learner_snapshot_hash=HASH_A,
            source_domains=("source_policy",),
            target_domains=("target_inventory",),
            source_receipt_hashes=(HASH_B,),
            target_evaluation_receipt_hashes=(HASH_C,),
            baseline_name="target-baseline",
            transfer_name="source-transfer",
            baseline_success_count=1,
            transfer_success_count=1,
            baseline_verifier_calls=2,
            transfer_verifier_calls=1,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=NO_INVALID_COMMITS,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )
        router.update_transfer_certificate(certificate)
        route = router.rank_with_transfer_guard(
            "sdk-transfer",
            ("source_policy", "target_policy"),
            ("source_policy",),
            "target_inventory",
        )

        self.assertEqual(route.schema_version, TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA)
        self.assertTrue(route.decision_admitted)
        self.assertEqual(route.decision_reason, "positive_transfer_certificate")
        self.assertEqual(route.blocked_domain_ids, ())
        self.assertEqual(route.top_domain_id, "source_policy")
        self.assertFalse(route.source_blocked)
        self.assertTrue(validate_transfer_guarded_domain_route(route))

    def test_sdk_transfer_guard_benchmark_blocks_source_policy_route(self) -> None:
        report = run_sdk_transfer_guard_benchmark()

        self.assertEqual(report.schema_version, TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA)
        self.assertTrue(report.route_valid)
        self.assertTrue(report.snapshot_valid)
        self.assertEqual(report.base_router_top_domain, "source_policy")
        self.assertEqual(report.guarded_router_top_domain, "target_policy")
        self.assertEqual(report.blocked_domain_ids, ("source_policy",))
        self.assertTrue(report.source_blocked)
        self.assertTrue(report.guard_reordered_to_target)
        self.assertEqual(report.decision_reason, "negative_transfer_certificate")
        self.assertFalse(report.decision_admitted)
        self.assertEqual(report.unguarded_selected, "quantity-5")
        self.assertFalse(report.unguarded_committed)
        self.assertEqual(report.unguarded_residual_kind, "stock_shortage")
        self.assertEqual(report.guarded_selected, "quantity-2")
        self.assertTrue(report.guarded_committed)
        self.assertTrue(report.avoided_negative_transfer)
        self.assertEqual(report.certificate_conclusion, "negative_transfer")
        self.assertTrue(report.tamper_detected)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)

    def test_domain_manifest_binds_schema_and_ledger_surface(self) -> None:
        substrate = ProgrammableSubstrate()
        substrate.register("scalar", ScalarProgramAdapter())
        state = {"episode": 0, "target": 7, "solved": False}
        substrate.submit(
            "scalar",
            state,
            ProposalTrace(
                branch_id="manifest-scalar",
                actions=({"op": "set", "value": 7},),
                seeds=("manifest", "scalar"),
                model_version="manifest.scalar.v1",
            ),
            make_scalar_candidate("manifest", 7, ({"op": "set", "value": 7},)),
            context="manifest",
        )

        manifest = substrate.domain_manifest("scalar")
        tampered = replace(manifest, verifier_id="tampered", manifest_hash="")

        self.assertEqual(manifest.domain_id, "scalar")
        self.assertEqual(manifest.adapter_type, "ScalarProgramAdapter")
        self.assertEqual(manifest.verifier_id, "scalar_program_oracle")
        self.assertEqual(manifest.candidate_type_names, ("scalar.program",))
        self.assertEqual(manifest.projection_schema_versions, ("scalar.program.v1",))
        self.assertEqual(manifest.receipt_count, 1)
        self.assertEqual(manifest.committed_count, 1)
        self.assertEqual(manifest.invalid_commit_count, 0)
        self.assertTrue(validate_domain_manifest(manifest))
        self.assertTrue(substrate.audit_domain_manifest("scalar", manifest))
        self.assertFalse(substrate.audit_domain_manifest("scalar", tampered))

    def test_sdk_manifest_benchmark_metrics(self) -> None:
        report = run_sdk_manifest_benchmark()

        self.assertEqual(report.domain_count, 2)
        self.assertEqual(report.manifest_valid_count, 2)
        self.assertEqual(report.manifest_audit_count, 2)
        self.assertEqual(report.scalar_candidate_types, ("scalar.program",))
        self.assertEqual(report.life_projection_schemas, ("game_of_life.predecessor.v1",))
        self.assertEqual(report.scalar_verifier_id, "scalar_program_oracle")
        self.assertEqual(report.life_verifier_id, "life_forward_verifier")
        self.assertEqual(report.scalar_receipt_count, 1)
        self.assertEqual(report.life_receipt_count, 2)
        self.assertEqual(report.total_receipt_count, 3)
        self.assertEqual(report.accepted_count, 2)
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.hard_verifier_calls, 3)
        self.assertEqual(report.total_verifier_cost, 3)
        self.assertTrue(report.manifest_hashes_stable)
        self.assertTrue(report.tamper_detected)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
