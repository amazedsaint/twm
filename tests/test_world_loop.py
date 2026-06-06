from __future__ import annotations

import unittest
from dataclasses import replace

from trwm.core import Ledger, TransactionEngine
from trwm.experiments.repair_simulator import ScalarProgramAdapter
from trwm.experiments.world_loop import (
    ResidualRepairLearner,
    ResidualRepairProposer,
    ScalarProgramProjector,
    run_world_loop_benchmark,
)
from trwm.world import (
    TransactionalWorldModelRuntime,
    apply_world_learner_delta,
    audit_world_learner_delta,
    audit_world_learner_lineage,
    audit_world_learner_merge,
    audit_world_learner_update,
    audit_world_model_step,
    build_world_learner_delta_certificate,
    build_world_learner_lineage_certificate,
    merge_world_learner_snapshots,
    validate_world_learner_delta_certificate,
    validate_world_learner_lineage_certificate,
    validate_world_learner_merge_certificate,
    validate_world_learner_snapshot,
    validate_world_learner_update_certificate,
    validate_world_model_step_certificate,
    world_learner_delta_certificate_hash,
    world_learner_lineage_certificate_hash,
    world_learner_merge_certificate_hash,
    world_learner_update_certificate_hash,
)


class WorldLoopTests(unittest.TestCase):
    def test_world_model_runtime_learns_from_residual_receipt(self) -> None:
        state = {"episode": 0, "target": 5, "solved": False}
        proposer = ResidualRepairProposer(target=5, initial_guess=0)
        projector = ScalarProgramProjector(target=5)
        learner = ResidualRepairLearner(proposer)
        engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
        runtime = TransactionalWorldModelRuntime(engine, proposer, projector, learner)

        first = runtime.step(state)

        self.assertFalse(first.committed)
        self.assertEqual(first.reason, "hard_reject")
        self.assertEqual(first.certificate.proposer_id, "scalar_residual_repair_proposer")
        self.assertEqual(first.certificate.proposer_version, "1.0")
        self.assertEqual(first.certificate.projector_id, "scalar_program_projector")
        self.assertEqual(first.certificate.projector_version, "1.0")
        self.assertEqual(first.certificate.learner_id, "scalar_residual_repair_learner")
        self.assertEqual(first.certificate.learner_version, "1.0")
        self.assertEqual(first.learner_update_count, 1)
        self.assertEqual(proposer.learned_repair, {"op": "add", "value": 5})
        self.assertTrue(validate_world_model_step_certificate(first.certificate))
        self.assertTrue(validate_world_learner_snapshot(first.learner_snapshot))
        self.assertTrue(validate_world_learner_snapshot(first.pre_learner_snapshot))
        self.assertTrue(validate_world_learner_update_certificate(first.learner_update_certificate))
        self.assertTrue(validate_world_learner_delta_certificate(first.learner_delta_certificate))
        self.assertTrue(audit_world_learner_update(first.receipt, first.pre_learner_snapshot, first.learner_snapshot, first.learner_update_certificate))
        self.assertTrue(audit_world_learner_delta(first.pre_learner_snapshot, first.learner_snapshot, first.learner_update_certificate, first.learner_delta_certificate))
        self.assertEqual(
            apply_world_learner_delta(first.pre_learner_snapshot.learner_state, first.learner_delta_certificate.learner_delta),
            first.learner_snapshot.learner_state,
        )
        self.assertEqual(first.pre_learner_snapshot.update_count, 0)
        self.assertEqual(first.learner_update_certificate.source_receipt_hash, first.receipt.receipt_hash)
        self.assertEqual(first.learner_update_certificate.pre_update_count, 0)
        self.assertEqual(first.learner_update_certificate.post_update_count, 1)
        self.assertEqual(first.learner_update_certificate.pre_learner_snapshot_hash, first.pre_learner_snapshot.snapshot_hash)
        self.assertEqual(first.learner_update_certificate.learner_snapshot_hash, first.learner_snapshot.snapshot_hash)
        self.assertEqual(first.certificate.learner_update_certificate_hash, first.learner_update_certificate.certificate_hash)
        self.assertEqual(first.certificate.learner_state_hash, first.learner_snapshot.learner_state_hash)
        self.assertEqual(first.certificate.learner_snapshot_hash, first.learner_snapshot.snapshot_hash)
        self.assertTrue(audit_world_model_step(first.receipt, first.certificate, learner_snapshot=first.learner_snapshot, learner_update_certificate=first.learner_update_certificate))

        second = runtime.step(first.state)

        self.assertTrue(second.committed)
        self.assertEqual(second.reason, "commit")
        self.assertEqual(second.state["value"], 5)
        self.assertEqual(second.learner_update_count, 2)
        self.assertEqual(second.receipt.hard_result.result, "accept")
        self.assertTrue(validate_world_model_step_certificate(second.certificate))
        self.assertTrue(validate_world_learner_snapshot(second.learner_snapshot))
        self.assertTrue(validate_world_learner_update_certificate(second.learner_update_certificate))
        self.assertTrue(validate_world_learner_delta_certificate(second.learner_delta_certificate))
        self.assertEqual(second.learner_snapshot.source_receipt_hashes, (first.receipt.receipt_hash, second.receipt.receipt_hash))
        self.assertEqual(second.pre_learner_snapshot.source_receipt_hashes, (first.receipt.receipt_hash,))
        self.assertEqual(second.learner_update_certificate.source_receipt_hash, second.receipt.receipt_hash)
        self.assertEqual(second.learner_update_certificate.pre_update_count, 1)
        self.assertEqual(second.learner_update_certificate.post_update_count, 2)
        self.assertEqual(second.learner_update_certificate.pre_learner_snapshot_hash, second.pre_learner_snapshot.snapshot_hash)
        self.assertEqual(second.learner_update_certificate.learner_snapshot_hash, second.learner_snapshot.snapshot_hash)
        self.assertEqual(second.certificate.learner_update_certificate_hash, second.learner_update_certificate.certificate_hash)
        self.assertEqual(second.learner_snapshot.learner_state["accepted_count"], 1)
        self.assertEqual(second.learner_snapshot.learner_state["rejected_count"], 1)
        self.assertTrue(audit_world_learner_update(second.receipt, second.pre_learner_snapshot, second.learner_snapshot, second.learner_update_certificate))
        self.assertTrue(audit_world_learner_delta(second.pre_learner_snapshot, second.learner_snapshot, second.learner_update_certificate, second.learner_delta_certificate))
        self.assertEqual(
            apply_world_learner_delta(second.pre_learner_snapshot.learner_state, second.learner_delta_certificate.learner_delta),
            second.learner_snapshot.learner_state,
        )
        self.assertTrue(audit_world_model_step(second.receipt, second.certificate, learner_snapshot=second.learner_snapshot, learner_update_certificate=second.learner_update_certificate))
        lineage = build_world_learner_lineage_certificate(
            first.pre_learner_snapshot,
            second.learner_snapshot,
            (first.learner_update_certificate, second.learner_update_certificate),
        )
        self.assertTrue(validate_world_learner_lineage_certificate(lineage))
        self.assertTrue(
            audit_world_learner_lineage(
                first.pre_learner_snapshot,
                second.learner_snapshot,
                (first.learner_update_certificate, second.learner_update_certificate),
                lineage,
            )
        )
        self.assertEqual(lineage.initial_snapshot_hash, first.pre_learner_snapshot.snapshot_hash)
        self.assertEqual(lineage.final_snapshot_hash, second.learner_snapshot.snapshot_hash)
        self.assertEqual(lineage.applied_update_count, 2)
        self.assertEqual(lineage.source_receipt_hashes, (first.receipt.receipt_hash, second.receipt.receipt_hash))
        self.assertEqual(
            lineage.update_certificate_hashes,
            (first.learner_update_certificate.certificate_hash, second.learner_update_certificate.certificate_hash),
        )
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.replay_audit(state), second.state)
        self.assertEqual(engine.rollback_audit(state), state)
        self.assertEqual(engine.invalid_commit_count, 0)

    def test_world_model_step_certificate_rejects_self_consistent_impossible_commit(self) -> None:
        state = {"episode": 0, "target": 5, "solved": False}
        proposer = ResidualRepairProposer(target=5, initial_guess=0)
        projector = ScalarProgramProjector(target=5)
        learner = ResidualRepairLearner(proposer)
        engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
        runtime = TransactionalWorldModelRuntime(engine, proposer, projector, learner)

        first = runtime.step(state)
        second = runtime.step(first.state)
        tampered = replace(second.certificate, committed=False, certificate_hash="")

        self.assertFalse(validate_world_model_step_certificate(tampered))
        self.assertFalse(audit_world_model_step(second.receipt, tampered))
        tampered_snapshot = replace(second.learner_snapshot, update_count=99, snapshot_hash="")
        self.assertFalse(validate_world_learner_snapshot(tampered_snapshot))
        self.assertFalse(audit_world_model_step(second.receipt, second.certificate, learner_snapshot=tampered_snapshot))
        tampered_update = replace(second.learner_update_certificate, post_update_count=4, certificate_hash="")
        tampered_update = replace(tampered_update, certificate_hash=world_learner_update_certificate_hash(tampered_update))
        self.assertFalse(validate_world_learner_update_certificate(tampered_update))
        self.assertFalse(audit_world_learner_update(second.receipt, second.pre_learner_snapshot, second.learner_snapshot, tampered_update))
        self.assertFalse(audit_world_model_step(second.receipt, second.certificate, learner_update_certificate=tampered_update))
        tampered_delta = replace(second.learner_delta_certificate, delta_op_count=9, certificate_hash="")
        tampered_delta = replace(tampered_delta, certificate_hash=world_learner_delta_certificate_hash(tampered_delta))
        self.assertFalse(validate_world_learner_delta_certificate(tampered_delta))
        self.assertFalse(audit_world_learner_delta(second.pre_learner_snapshot, second.learner_snapshot, second.learner_update_certificate, tampered_delta))
        lineage = build_world_learner_lineage_certificate(
            first.pre_learner_snapshot,
            second.learner_snapshot,
            (first.learner_update_certificate, second.learner_update_certificate),
        )
        tampered_lineage = replace(lineage, applied_update_count=3, certificate_hash="")
        tampered_lineage = replace(tampered_lineage, certificate_hash=world_learner_lineage_certificate_hash(tampered_lineage))
        self.assertFalse(validate_world_learner_lineage_certificate(tampered_lineage))
        self.assertFalse(
            audit_world_learner_lineage(
                first.pre_learner_snapshot,
                second.learner_snapshot,
                (first.learner_update_certificate, second.learner_update_certificate),
                tampered_lineage,
            )
        )

    def test_world_learner_snapshots_merge_disjoint_evidence_and_reject_conflicts(self) -> None:
        def run_episode(episode: int):
            state = {"episode": episode, "target": 5, "solved": False}
            proposer = ResidualRepairProposer(target=5, initial_guess=0)
            projector = ScalarProgramProjector(target=5)
            learner = ResidualRepairLearner(proposer)
            runtime = TransactionalWorldModelRuntime(
                TransactionEngine(ScalarProgramAdapter(), ledger=Ledger()),
                proposer,
                projector,
                learner,
            )
            first = runtime.step(state)
            second = runtime.step(first.state)
            return first, second

        def fork_from(base_step, episode: int):
            state = {"episode": episode, "target": 5, "solved": False}
            proposer = ResidualRepairProposer(target=5, initial_guess=0)
            proposer.learned_repair = dict(base_step.learner_snapshot.learner_state["learned_repair"])
            learner = ResidualRepairLearner(proposer)
            learner.accepted_count = base_step.learner_snapshot.learner_state["accepted_count"]
            learner.rejected_count = base_step.learner_snapshot.learner_state["rejected_count"]
            learner.update_count = base_step.learner_snapshot.learner_state["update_count"]
            runtime = TransactionalWorldModelRuntime(
                TransactionEngine(ScalarProgramAdapter(), ledger=Ledger()),
                proposer,
                ScalarProgramProjector(target=5),
                learner,
            )
            runtime.learner_update_count = base_step.learner_snapshot.update_count
            runtime.learner_receipt_hashes = list(base_step.learner_snapshot.source_receipt_hashes)
            return runtime.step(state)

        _left_base, left_final = run_episode(0)
        _right_base, right_final = run_episode(1)
        left = left_final.learner_snapshot
        right = right_final.learner_snapshot
        result = merge_world_learner_snapshots(left, right)
        reverse = merge_world_learner_snapshots(right, left)
        duplicate = merge_world_learner_snapshots(left, left)
        tampered = replace(result.certificate, merged_update_count=3, certificate_hash="")
        tampered = replace(tampered, certificate_hash=world_learner_merge_certificate_hash(tampered))
        conflicting_right = replace(
            right,
            learner_state={**right.learner_state, "learned_repair": {"op": "add", "value": 7}},
            learner_state_hash="",
            snapshot_hash="",
        )

        self.assertTrue(validate_world_learner_merge_certificate(result.certificate))
        self.assertTrue(audit_world_learner_merge(left, right, result.merged_snapshot, result.certificate))
        self.assertEqual(result.merged_snapshot.update_count, 4)
        self.assertEqual(result.merged_snapshot.learner_state["accepted_count"], 2)
        self.assertEqual(result.merged_snapshot.learner_state["rejected_count"], 2)
        self.assertEqual(result.merged_snapshot.learner_state["learned_repair"], {"op": "add", "value": 5})
        self.assertEqual(result.merged_snapshot.snapshot_hash, reverse.merged_snapshot.snapshot_hash)
        self.assertEqual(duplicate.merged_snapshot.snapshot_hash, left.snapshot_hash)
        self.assertFalse(validate_world_learner_merge_certificate(tampered))
        self.assertFalse(audit_world_learner_merge(left, right, result.merged_snapshot, tampered))
        with self.assertRaises(ValueError):
            merge_world_learner_snapshots(left, conflicting_right)

        base, partial_left = run_episode(10)
        partial_right = fork_from(base, episode=11)
        partial = merge_world_learner_snapshots(
            partial_left.learner_snapshot,
            partial_right.learner_snapshot,
            base_snapshot=base.learner_snapshot,
            left_delta_certificates=(partial_left.learner_delta_certificate,),
            right_delta_certificates=(partial_right.learner_delta_certificate,),
        )
        self.assertEqual(partial.certificate.merge_basis, "delta_common_prefix")
        self.assertEqual(partial.certificate.base_snapshot_hash, base.learner_snapshot.snapshot_hash)
        self.assertEqual(partial.certificate.shared_receipt_count, 1)
        self.assertEqual(partial.certificate.common_prefix_receipt_count, 1)
        self.assertEqual(partial.merged_snapshot.update_count, 3)
        self.assertEqual(partial.merged_snapshot.learner_state["accepted_count"], 2)
        self.assertEqual(partial.merged_snapshot.learner_state["rejected_count"], 1)
        self.assertEqual(partial.merged_snapshot.learner_state["update_count"], 3)
        self.assertEqual(partial.merged_snapshot.source_receipt_hashes[0], base.receipt.receipt_hash)
        self.assertTrue(validate_world_learner_merge_certificate(partial.certificate))
        self.assertTrue(
            audit_world_learner_merge(
                partial_left.learner_snapshot,
                partial_right.learner_snapshot,
                partial.merged_snapshot,
                partial.certificate,
                base_snapshot=base.learner_snapshot,
                left_delta_certificates=(partial_left.learner_delta_certificate,),
                right_delta_certificates=(partial_right.learner_delta_certificate,),
            )
        )
        with self.assertRaises(ValueError):
            merge_world_learner_snapshots(partial_left.learner_snapshot, partial_right.learner_snapshot)
        tampered_partial_delta = replace(partial_right.learner_delta_certificate, delta_op_count=9, certificate_hash="")
        tampered_partial_delta = replace(
            tampered_partial_delta,
            certificate_hash=world_learner_delta_certificate_hash(tampered_partial_delta),
        )
        self.assertFalse(
            audit_world_learner_merge(
                partial_left.learner_snapshot,
                partial_right.learner_snapshot,
                partial.merged_snapshot,
                partial.certificate,
                base_snapshot=base.learner_snapshot,
                left_delta_certificates=(partial_left.learner_delta_certificate,),
                right_delta_certificates=(tampered_partial_delta,),
            )
        )

        left_conflict = replace(
            partial_left.learner_snapshot,
            learner_state={**partial_left.learner_snapshot.learner_state, "learned_repair": {"op": "add", "value": 6}},
            learner_state_hash="",
            snapshot_hash="",
        )
        right_conflict = replace(
            partial_right.learner_snapshot,
            learner_state={**partial_right.learner_snapshot.learner_state, "learned_repair": {"op": "add", "value": 7}},
            learner_state_hash="",
            snapshot_hash="",
        )
        left_conflict_delta = build_world_learner_delta_certificate(
            base.learner_snapshot,
            left_conflict,
            partial_left.learner_update_certificate,
        )
        right_conflict_delta = build_world_learner_delta_certificate(
            base.learner_snapshot,
            right_conflict,
            partial_right.learner_update_certificate,
        )
        with self.assertRaises(ValueError):
            merge_world_learner_snapshots(
                left_conflict,
                right_conflict,
                base_snapshot=base.learner_snapshot,
                left_delta_certificates=(left_conflict_delta,),
                right_delta_certificates=(right_conflict_delta,),
            )

    def test_world_loop_benchmark_reports_checked_learning_loop(self) -> None:
        report = run_world_loop_benchmark()

        self.assertEqual(report.step_count, 2)
        self.assertFalse(report.first_committed)
        self.assertTrue(report.second_committed)
        self.assertEqual(report.first_decision, "hard_reject")
        self.assertEqual(report.second_decision, "commit")
        self.assertEqual(report.learner_update_count, 2)
        self.assertEqual(report.accepted_count, 1)
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.certificate_valid_count, 2)
        self.assertEqual(report.audit_valid_count, 2)
        self.assertTrue(report.proposer_improved_from_residual)
        self.assertTrue(report.hard_verifier_owned_commit)
        self.assertEqual(report.learner_snapshot_valid_count, 2)
        self.assertTrue(report.step_certificate_binds_learner_state)
        self.assertEqual(report.learner_update_certificate_valid_count, 2)
        self.assertEqual(report.learner_update_audit_valid_count, 2)
        self.assertTrue(report.step_certificate_binds_learner_update)
        self.assertTrue(report.learner_update_tamper_detected)
        self.assertEqual(report.learner_delta_certificate_valid_count, 2)
        self.assertEqual(report.learner_delta_audit_valid_count, 2)
        self.assertTrue(report.learner_delta_binds_updates)
        self.assertTrue(report.learner_delta_tamper_detected)
        self.assertTrue(report.learner_lineage_certificate_valid)
        self.assertTrue(report.learner_lineage_audit_valid)
        self.assertTrue(report.learner_lineage_binds_updates)
        self.assertTrue(report.learner_lineage_tamper_detected)
        self.assertTrue(report.learner_merge_certificate_valid)
        self.assertTrue(report.learner_merge_audit_valid)
        self.assertTrue(report.learner_merge_disjoint_receipts)
        self.assertTrue(report.learner_merge_partial_overlap_valid)
        self.assertTrue(report.learner_merge_partial_overlap_audit_valid)
        self.assertTrue(report.learner_merge_partial_overlap_counts_shared_once)
        self.assertTrue(report.learner_merge_partial_overlap_requires_deltas)
        self.assertTrue(report.learner_merge_tamper_detected)
        self.assertTrue(report.learner_merge_conflict_detected)
        self.assertFalse(report.rrlm_world_first_committed)
        self.assertTrue(report.rrlm_world_second_committed)
        self.assertTrue(report.rrlm_world_selected_repair_macro)
        self.assertTrue(report.rrlm_world_proposal_certificate_valid)
        self.assertTrue(report.rrlm_world_transport_certificate_valid)
        self.assertTrue(report.rrlm_world_artifacts_bound_to_receipts)
        self.assertTrue(report.rrlm_world_rejected_macro_penalized)
        self.assertTrue(report.rrlm_world_tamper_detected)
        self.assertTrue(report.world_program_manifest_valid)
        self.assertTrue(report.world_program_certificate_valid)
        self.assertTrue(report.world_program_audit_valid)
        self.assertTrue(report.world_program_binds_rrlm_artifacts)
        self.assertTrue(report.world_program_tamper_detected)
        self.assertTrue(report.world_program_admission_policy_valid)
        self.assertTrue(report.world_program_admission_certificate_valid)
        self.assertTrue(report.world_program_admission_audit_valid)
        self.assertTrue(report.world_program_admitted)
        self.assertTrue(report.world_program_admission_rejects_unmet_requirements)
        self.assertTrue(report.world_program_admission_tamper_detected)
        self.assertTrue(report.world_program_evidence_bundle_valid)
        self.assertTrue(report.world_program_evidence_bundle_audit_valid)
        self.assertTrue(report.world_program_bundle_verification_certificate_valid)
        self.assertTrue(report.world_program_bundle_verified)
        self.assertTrue(report.world_program_bundle_tamper_detected)
        self.assertTrue(report.world_program_replay_package_valid)
        self.assertTrue(report.world_program_replay_package_audit_valid)
        self.assertTrue(report.world_program_replay_verification_certificate_valid)
        self.assertTrue(report.world_program_replay_verified)
        self.assertTrue(report.world_program_replay_tamper_detected)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.learner_snapshot_tamper_detected)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
