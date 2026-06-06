from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.core import Ledger, TransactionEngine
from trwm.experiments.repair_simulator import ScalarProgramAdapter
from trwm.experiments.world_loop import ResidualRepairLearner, ResidualRepairProposer, ScalarProgramProjector
from trwm.world import TransactionalWorldModelRuntime
from trwm.world_program import (
    audit_world_program_admission,
    audit_world_program_bundle_verification,
    audit_world_program_certificate,
    audit_world_program_evidence_bundle,
    audit_world_program_replay_package,
    audit_world_program_replay_verification,
    build_world_program_admission_certificate,
    build_world_program_admission_policy,
    build_world_program_bundle_verification_certificate,
    build_world_program_certificate,
    build_world_program_evidence_bundle,
    build_world_program_manifest,
    build_world_program_replay_package,
    build_world_program_replay_verification_certificate,
    tamper_world_program_admission_certificate,
    tamper_world_program_bundle_verification_certificate,
    tamper_world_program_certificate,
    tamper_world_program_evidence_bundle,
    tamper_world_program_replay_package,
    tamper_world_program_replay_verification_certificate,
    validate_world_program_admission_certificate,
    validate_world_program_admission_policy,
    validate_world_program_bundle_verification_certificate,
    validate_world_program_certificate,
    validate_world_program_evidence_bundle,
    validate_world_program_manifest,
    validate_world_program_replay_package,
    validate_world_program_replay_step,
    validate_world_program_replay_verification_certificate,
    world_program_manifest_hash,
    world_program_replay_package_body_hash,
    world_program_replay_package_hash,
    world_program_replay_step_hash,
)


class WorldProgramTests(unittest.TestCase):
    def test_world_program_certificate_binds_manifest_steps_ledger_and_artifacts(self) -> None:
        state = {"episode": 0, "target": 5, "solved": False}
        proposer = ResidualRepairProposer(target=5, initial_guess=0)
        projector = ScalarProgramProjector(target=5)
        learner = ResidualRepairLearner(proposer)
        engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
        runtime = TransactionalWorldModelRuntime(engine, proposer, projector, learner)

        first = runtime.step(state)
        second = runtime.step(first.state)
        manifest = build_world_program_manifest(
            program_id="test_scalar_world_program",
            program_version="1.0",
            proposer=proposer,
            projector=projector,
            learner=learner,
            verifier_id=engine.adapter.verifier_id,
            verifier_version=engine.adapter.verifier_version,
            input_schema="scalar.program.state.v1",
            candidate_schema="scalar.program.v1",
            external_parameters={"target": 5, "initial_guess": 0},
            resolved_dependencies=("trwm.world_model_step_certificate.v1",),
        )
        certificate = build_world_program_certificate(
            manifest,
            (first, second),
            ledger_head=engine.ledger.head,
            invalid_commit_count=engine.invalid_commit_count,
            replay_rollback_rate=1.0,
        )

        self.assertTrue(validate_world_program_manifest(manifest))
        self.assertTrue(validate_world_program_certificate(certificate, manifest))
        self.assertTrue(
            audit_world_program_certificate(
                manifest,
                (first, second),
                certificate,
                ledger_head=engine.ledger.head,
                invalid_commit_count=engine.invalid_commit_count,
                replay_rollback_rate=1.0,
            )
        )
        self.assertEqual(certificate.step_count, 2)
        self.assertEqual(certificate.committed_count, 1)
        self.assertEqual(certificate.rejected_count, 1)
        self.assertEqual(certificate.learner_update_count, 2)
        self.assertEqual(certificate.step_certificate_hashes, (first.certificate.certificate_hash, second.certificate.certificate_hash))
        self.assertEqual(certificate.receipt_hashes, (first.receipt.receipt_hash, second.receipt.receipt_hash))
        self.assertEqual(certificate.final_learner_snapshot_hash, second.learner_snapshot.snapshot_hash)
        self.assertEqual(certificate.ledger_head, engine.ledger.head)

    def test_world_program_admission_policy_gates_execution_certificate(self) -> None:
        state = {"episode": 0, "target": 5, "solved": False}
        proposer = ResidualRepairProposer(target=5, initial_guess=0)
        projector = ScalarProgramProjector(target=5)
        learner = ResidualRepairLearner(proposer)
        engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
        runtime = TransactionalWorldModelRuntime(engine, proposer, projector, learner)
        first = runtime.step(state)
        second = runtime.step(first.state)
        manifest = build_world_program_manifest(
            program_id="test_scalar_world_program",
            program_version="1.0",
            proposer=proposer,
            projector=projector,
            learner=learner,
            verifier_id=engine.adapter.verifier_id,
            verifier_version=engine.adapter.verifier_version,
            input_schema="scalar.program.state.v1",
            candidate_schema="scalar.program.v1",
            resolved_dependencies=("trwm.world_model_step_certificate.v1",),
        )
        certificate = build_world_program_certificate(
            manifest,
            (first, second),
            ledger_head=engine.ledger.head,
            invalid_commit_count=engine.invalid_commit_count,
            replay_rollback_rate=1.0,
        )
        policy = build_world_program_admission_policy(
            policy_id="test_scalar_world_policy",
            policy_version="1.0",
            allowed_program_ids=("test_scalar_world_program",),
            allowed_program_versions=("1.0",),
            allowed_proposer_ids=("scalar_residual_repair_proposer",),
            allowed_projector_ids=("scalar_program_projector",),
            allowed_learner_ids=("scalar_residual_repair_learner",),
            allowed_verifier_ids=("scalar_program_oracle",),
            allowed_input_schemas=("scalar.program.state.v1",),
            allowed_candidate_schemas=("scalar.program.v1",),
            required_dependencies=("trwm.world_model_step_certificate.v1",),
            min_step_count=2,
            min_committed_count=1,
            min_rejected_count=1,
        )
        admission = build_world_program_admission_certificate(policy, manifest, certificate)

        self.assertTrue(validate_world_program_admission_policy(policy))
        self.assertTrue(validate_world_program_admission_certificate(admission, policy, manifest, certificate))
        self.assertTrue(audit_world_program_admission(policy, manifest, certificate, admission))
        self.assertTrue(admission.admitted)
        self.assertEqual(admission.failed_requirements, ())
        self.assertEqual(admission.requirement_count, 19)
        self.assertIn("required_dependencies_present", admission.passed_requirements)
        self.assertIn("min_committed_count", admission.passed_requirements)

        stricter = build_world_program_admission_policy(
            policy_id="test_scalar_world_policy_strict",
            policy_version="1.0",
            allowed_program_ids=("test_scalar_world_program",),
            required_artifact_keys=("rrlm_snapshot_hash",),
            min_committed_count=2,
        )
        rejected = build_world_program_admission_certificate(stricter, manifest, certificate)
        self.assertTrue(validate_world_program_admission_certificate(rejected, stricter, manifest, certificate))
        self.assertFalse(rejected.admitted)
        self.assertEqual(rejected.failed_requirements, ("required_artifacts_present", "min_committed_count"))

        tampered = tamper_world_program_admission_certificate(admission)
        self.assertFalse(validate_world_program_admission_certificate(tampered, policy, manifest, certificate))
        self.assertFalse(audit_world_program_admission(policy, manifest, certificate, tampered))

    def test_world_program_evidence_bundle_verifies_attestations_against_policy(self) -> None:
        state = {"episode": 0, "target": 5, "solved": False}
        proposer = ResidualRepairProposer(target=5, initial_guess=0)
        projector = ScalarProgramProjector(target=5)
        learner = ResidualRepairLearner(proposer)
        engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
        runtime = TransactionalWorldModelRuntime(engine, proposer, projector, learner)
        first = runtime.step(state)
        second = runtime.step(first.state)
        manifest = build_world_program_manifest(
            program_id="test_scalar_world_program",
            program_version="1.0",
            proposer=proposer,
            projector=projector,
            learner=learner,
            verifier_id=engine.adapter.verifier_id,
            verifier_version=engine.adapter.verifier_version,
            input_schema="scalar.program.state.v1",
            candidate_schema="scalar.program.v1",
            resolved_dependencies=("trwm.world_model_step_certificate.v1",),
        )
        certificate = build_world_program_certificate(
            manifest,
            (first, second),
            ledger_head=engine.ledger.head,
            invalid_commit_count=engine.invalid_commit_count,
            replay_rollback_rate=1.0,
        )
        policy = build_world_program_admission_policy(
            policy_id="test_scalar_world_policy",
            policy_version="1.0",
            allowed_program_ids=("test_scalar_world_program",),
            allowed_proposer_ids=("scalar_residual_repair_proposer",),
            allowed_projector_ids=("scalar_program_projector",),
            allowed_learner_ids=("scalar_residual_repair_learner",),
            allowed_verifier_ids=("scalar_program_oracle",),
            min_step_count=2,
            min_committed_count=1,
            min_rejected_count=1,
        )
        admission = build_world_program_admission_certificate(policy, manifest, certificate)
        bundle = build_world_program_evidence_bundle(
            manifest,
            certificate,
            policy,
            admission,
            bundle_id="test_scalar_world_program_bundle",
        )
        verification = build_world_program_bundle_verification_certificate(bundle)

        self.assertTrue(validate_world_program_evidence_bundle(bundle))
        self.assertTrue(audit_world_program_evidence_bundle(manifest, certificate, policy, admission, bundle))
        self.assertEqual(bundle.bundle_id, "test_scalar_world_program_bundle")
        self.assertEqual(bundle.step_certificate_hashes, certificate.step_certificate_hashes)
        self.assertEqual(bundle.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(bundle.final_learner_snapshot_hash, certificate.final_learner_snapshot_hash)
        self.assertEqual(bundle.artifact_hash_groups, certificate.artifact_hash_groups)
        self.assertTrue(validate_world_program_bundle_verification_certificate(verification, bundle))
        self.assertTrue(audit_world_program_bundle_verification(bundle, verification))
        self.assertTrue(verification.verified)
        self.assertEqual(verification.failed_requirements, ())
        self.assertIn("admission_certificate_admitted", verification.passed_requirements)
        self.assertEqual(verification.requirement_count, 11)
        self.assertEqual(verification.input_attestation_hashes[0], manifest.manifest_hash)
        self.assertEqual(verification.input_attestation_hashes[1], certificate.certificate_hash)
        self.assertEqual(verification.input_attestation_hashes[2], policy.policy_hash)
        self.assertEqual(verification.input_attestation_hashes[3], admission.certificate_hash)

        tampered_bundle = tamper_world_program_evidence_bundle(bundle)
        self.assertFalse(validate_world_program_evidence_bundle(tampered_bundle))
        self.assertFalse(audit_world_program_bundle_verification(tampered_bundle, verification))
        tampered_verification = tamper_world_program_bundle_verification_certificate(verification)
        self.assertFalse(validate_world_program_bundle_verification_certificate(tampered_verification, bundle))

        rejected_policy = build_world_program_admission_policy(
            policy_id="test_scalar_world_policy_reject",
            policy_version="1.0",
            allowed_program_ids=("test_scalar_world_program",),
            min_committed_count=2,
        )
        rejected_admission = build_world_program_admission_certificate(rejected_policy, manifest, certificate)
        rejected_bundle = build_world_program_evidence_bundle(manifest, certificate, rejected_policy, rejected_admission)
        rejected_verification = build_world_program_bundle_verification_certificate(rejected_bundle)
        self.assertTrue(validate_world_program_evidence_bundle(rejected_bundle))
        self.assertTrue(validate_world_program_bundle_verification_certificate(rejected_verification, rejected_bundle))
        self.assertFalse(rejected_verification.verified)
        self.assertEqual(rejected_verification.failed_requirements, ("admission_certificate_admitted",))

    def test_world_program_replay_package_verifies_step_bodies_against_bundle(self) -> None:
        state = {"episode": 0, "target": 5, "solved": False}
        proposer = ResidualRepairProposer(target=5, initial_guess=0)
        projector = ScalarProgramProjector(target=5)
        learner = ResidualRepairLearner(proposer)
        engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
        runtime = TransactionalWorldModelRuntime(engine, proposer, projector, learner)
        first = runtime.step(state)
        second = runtime.step(first.state)
        manifest = build_world_program_manifest(
            program_id="test_scalar_world_program",
            program_version="1.0",
            proposer=proposer,
            projector=projector,
            learner=learner,
            verifier_id=engine.adapter.verifier_id,
            verifier_version=engine.adapter.verifier_version,
            input_schema="scalar.program.state.v1",
            candidate_schema="scalar.program.v1",
            resolved_dependencies=("trwm.world_model_step_certificate.v1",),
        )
        certificate = build_world_program_certificate(
            manifest,
            (first, second),
            ledger_head=engine.ledger.head,
            invalid_commit_count=engine.invalid_commit_count,
            replay_rollback_rate=1.0,
        )
        policy = build_world_program_admission_policy(
            policy_id="test_scalar_world_policy",
            policy_version="1.0",
            allowed_program_ids=("test_scalar_world_program",),
            allowed_proposer_ids=("scalar_residual_repair_proposer",),
            allowed_projector_ids=("scalar_program_projector",),
            allowed_learner_ids=("scalar_residual_repair_learner",),
            allowed_verifier_ids=("scalar_program_oracle",),
            min_step_count=2,
            min_committed_count=1,
            min_rejected_count=1,
        )
        admission = build_world_program_admission_certificate(policy, manifest, certificate)
        bundle = build_world_program_evidence_bundle(manifest, certificate, policy, admission)
        replay_package = build_world_program_replay_package(
            bundle,
            (first, second),
            package_id="test_scalar_world_program_replay",
        )
        replay_verification = build_world_program_replay_verification_certificate(replay_package)

        self.assertTrue(validate_world_program_replay_step(replay_package.steps[0], expected_index=0))
        self.assertTrue(validate_world_program_replay_package(replay_package))
        self.assertTrue(audit_world_program_replay_package(bundle, (first, second), replay_package))
        self.assertTrue(validate_world_program_replay_verification_certificate(replay_verification, replay_package))
        self.assertTrue(audit_world_program_replay_verification(replay_package, replay_verification))
        self.assertTrue(replay_verification.replay_verified)
        self.assertEqual(replay_verification.requirement_count, 16)
        self.assertIn("trace_hashes_bound", replay_verification.passed_requirements)
        self.assertIn("learner_deltas_valid", replay_verification.passed_requirements)
        self.assertEqual(replay_package.receipt_hashes, certificate.receipt_hashes)
        self.assertEqual(replay_package.step_certificate_hashes, certificate.step_certificate_hashes)
        self.assertEqual(replay_package.final_learner_snapshot_hash, certificate.final_learner_snapshot_hash)
        self.assertEqual(replay_package.ledger_head, certificate.ledger_head)

        tampered_package = tamper_world_program_replay_package(replay_package)
        self.assertFalse(validate_world_program_replay_package(tampered_package))
        self.assertFalse(audit_world_program_replay_verification(tampered_package, replay_verification))
        tampered_verification = tamper_world_program_replay_verification_certificate(replay_verification)
        self.assertFalse(validate_world_program_replay_verification_certificate(tampered_verification, replay_package))

        tampered_trace = replace(replay_package.steps[0].trace, branch_id="tampered-branch")
        tampered_step = replace(replay_package.steps[0], trace=tampered_trace, step_hash="")
        tampered_step = replace(tampered_step, step_hash=world_program_replay_step_hash(tampered_step))
        tampered_steps = (tampered_step, *replay_package.steps[1:])
        tampered_body = replace(
            replay_package,
            steps=tampered_steps,
            step_hashes=tuple(step.step_hash for step in tampered_steps),
            package_body_hash="",
            package_hash="",
        )
        tampered_body = replace(tampered_body, package_body_hash=world_program_replay_package_body_hash(tampered_body))
        tampered_body = replace(tampered_body, package_hash=world_program_replay_package_hash(tampered_body))
        body_verification = build_world_program_replay_verification_certificate(tampered_body)

        self.assertFalse(validate_world_program_replay_package(tampered_body))
        self.assertFalse(body_verification.replay_verified)
        self.assertIn("replay_package_valid", body_verification.failed_requirements)
        self.assertIn("trace_hashes_bound", body_verification.failed_requirements)

    def test_world_program_certificate_detects_tampering(self) -> None:
        state = {"episode": 0, "target": 5, "solved": False}
        proposer = ResidualRepairProposer(target=5, initial_guess=0)
        projector = ScalarProgramProjector(target=5)
        learner = ResidualRepairLearner(proposer)
        engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
        runtime = TransactionalWorldModelRuntime(engine, proposer, projector, learner)
        first = runtime.step(state)
        second = runtime.step(first.state)
        manifest = build_world_program_manifest(
            program_id="test_scalar_world_program",
            program_version="1.0",
            proposer=proposer,
            projector=projector,
            learner=learner,
            verifier_id=engine.adapter.verifier_id,
            verifier_version=engine.adapter.verifier_version,
            input_schema="scalar.program.state.v1",
            candidate_schema="scalar.program.v1",
        )
        certificate = build_world_program_certificate(
            manifest,
            (first, second),
            ledger_head=engine.ledger.head,
            invalid_commit_count=engine.invalid_commit_count,
            replay_rollback_rate=1.0,
        )
        tampered_certificate = tamper_world_program_certificate(certificate)
        tampered_manifest = replace(manifest, verifier_version="9.9", manifest_hash="")
        tampered_manifest = replace(tampered_manifest, manifest_hash=world_program_manifest_hash(tampered_manifest))

        self.assertFalse(validate_world_program_certificate(tampered_certificate, manifest))
        self.assertFalse(
            audit_world_program_certificate(
                manifest,
                (first, second),
                tampered_certificate,
                ledger_head=engine.ledger.head,
                invalid_commit_count=engine.invalid_commit_count,
                replay_rollback_rate=1.0,
            )
        )
        self.assertFalse(validate_world_program_certificate(certificate, tampered_manifest))
        self.assertFalse(
            audit_world_program_certificate(
                tampered_manifest,
                (first, second),
                certificate,
                ledger_head=engine.ledger.head,
                invalid_commit_count=engine.invalid_commit_count,
                replay_rollback_rate=1.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
