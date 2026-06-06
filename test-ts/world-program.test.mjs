import assert from "node:assert/strict";
import test from "node:test";

import {
  Ledger,
  ScalarProgramAdapter,
  TransactionEngine,
  TransactionalWorldModelRuntime,
  auditWorldProgramAdmission,
  auditWorldProgramBundleVerification,
  auditWorldProgramCertificate,
  auditWorldProgramEvidenceBundle,
  auditWorldProgramReplayPackage,
  auditWorldProgramReplayVerification,
  buildWorldProgramAdmissionCertificate,
  buildWorldProgramAdmissionPolicy,
  buildWorldProgramBundleVerificationCertificate,
  buildWorldProgramCertificate,
  buildWorldProgramEvidenceBundle,
  buildWorldProgramManifest,
  buildWorldProgramReplayPackage,
  buildWorldProgramReplayVerificationCertificate,
  makeScalarCandidate,
  makeTrace,
  tamperWorldProgramAdmissionCertificate,
  tamperWorldProgramBundleVerificationCertificate,
  tamperWorldProgramCertificate,
  tamperWorldProgramEvidenceBundle,
  tamperWorldProgramReplayPackage,
  tamperWorldProgramReplayVerificationCertificate,
  validateWorldProgramAdmissionCertificate,
  validateWorldProgramAdmissionPolicy,
  validateWorldProgramBundleVerificationCertificate,
  validateWorldProgramCertificate,
  validateWorldProgramEvidenceBundle,
  validateWorldProgramManifest,
  validateWorldProgramReplayPackage,
  validateWorldProgramReplayStep,
  validateWorldProgramReplayVerificationCertificate,
  worldProgramManifestHash,
  worldProgramReplayPackageBodyHash,
  worldProgramReplayPackageHash,
  worldProgramReplayStepHash,
} from "../dist/index.js";

class TestResidualProposer {
  proposerId = "test_residual_proposer";
  proposerVersion = "2.0";
  learnedRepair = null;

  propose(_state, _budget) {
    const program = [{ op: "set", value: 0 }];
    if (this.learnedRepair) {
      program.push(this.learnedRepair);
    }
    return makeTrace({
      branchId: `test-world-program-${program.length}`,
      actions: program,
      seeds: ["test-world-program", program.length],
      modelVersion: this.proposerVersion,
    });
  }
}

class TestScalarProjector {
  projectorId = "test_scalar_projector";
  projectorVersion = "3.0";

  project(_state, trace) {
    return makeScalarCandidate("test-world-program", 5, trace.actions);
  }
}

class TestResidualLearner {
  learnerId = "test_residual_learner";
  learnerVersion = "4.0";
  updateCount = 0;
  acceptedCount = 0;
  rejectedCount = 0;

  constructor(proposer) {
    this.proposer = proposer;
  }

  update(receipt) {
    this.updateCount += 1;
    if (receipt.hardResult.result === "accept" && receipt.committed) {
      this.acceptedCount += 1;
      return;
    }
    if (receipt.hardResult.result !== "reject") {
      return;
    }
    this.rejectedCount += 1;
    const residual = receipt.hardResult.residual;
    if (residual && typeof residual === "object" && residual.repair) {
      this.proposer.learnedRepair = residual.repair;
    }
  }

  snapshotState() {
    return {
      acceptedCount: this.acceptedCount,
      rejectedCount: this.rejectedCount,
      learnedRepair: this.proposer.learnedRepair,
      updateCount: this.updateCount,
    };
  }
}

async function runProgramFixture() {
  const state = { episode: 0, target: 5, solved: false };
  const proposer = new TestResidualProposer();
  const projector = new TestScalarProjector();
  const learner = new TestResidualLearner(proposer);
  const engine = new TransactionEngine(new ScalarProgramAdapter(), new Ledger());
  const runtime = new TransactionalWorldModelRuntime(engine, proposer, projector, learner);
  const first = await runtime.step(state);
  const second = await runtime.step(first.state);
  const manifest = await buildWorldProgramManifest({
    programId: "test_scalar_world_program",
    programVersion: "1.0",
    proposer,
    projector,
    learner,
    verifierId: engine.adapter.verifierId,
    verifierVersion: engine.adapter.verifierVersion,
    inputSchema: "scalar.program.state.v1",
    candidateSchema: "scalar.program.v1",
    externalParameters: { target: 5, initialGuess: 0 },
    resolvedDependencies: ["trwm.world_model_step_certificate.v1"],
  });
  const certificate = await buildWorldProgramCertificate(manifest, [first, second], {
    ledgerHead: engine.ledger.head,
    invalidCommitCount: engine.invalidCommitCount,
    replayRollbackRate: 1,
  });
  return { engine, first, second, manifest, certificate };
}

test("world program certificate binds manifest, steps, ledger, and artifacts", async () => {
  const { engine, first, second, manifest, certificate } = await runProgramFixture();

  assert.equal(await validateWorldProgramManifest(manifest), true);
  assert.equal(await validateWorldProgramCertificate(certificate, manifest), true);
  assert.equal(await auditWorldProgramCertificate(manifest, [first, second], certificate, {
    ledgerHead: engine.ledger.head,
    invalidCommitCount: engine.invalidCommitCount,
    replayRollbackRate: 1,
  }), true);
  assert.equal(certificate.stepCount, 2);
  assert.equal(certificate.committedCount, 1);
  assert.equal(certificate.rejectedCount, 1);
  assert.equal(certificate.learnerUpdateCount, 2);
  assert.deepEqual(certificate.stepCertificateHashes, [
    first.certificate.certificateHash,
    second.certificate.certificateHash,
  ]);
  assert.deepEqual(certificate.receiptHashes, [first.receipt.receiptHash, second.receipt.receiptHash]);
  assert.equal(certificate.finalLearnerSnapshotHash, second.learnerSnapshot.snapshotHash);
  assert.equal(certificate.ledgerHead, engine.ledger.head);
});

test("world program admission policy gates execution certificate", async () => {
  const { manifest, certificate } = await runProgramFixture();
  const policy = await buildWorldProgramAdmissionPolicy({
    policyId: "test_scalar_world_policy",
    policyVersion: "1.0",
    allowedProgramIds: ["test_scalar_world_program"],
    allowedProgramVersions: ["1.0"],
    allowedProposerIds: ["test_residual_proposer"],
    allowedProjectorIds: ["test_scalar_projector"],
    allowedLearnerIds: ["test_residual_learner"],
    allowedVerifierIds: ["scalar_program_oracle"],
    allowedInputSchemas: ["scalar.program.state.v1"],
    allowedCandidateSchemas: ["scalar.program.v1"],
    requiredDependencies: ["trwm.world_model_step_certificate.v1"],
    minStepCount: 2,
    minCommittedCount: 1,
    minRejectedCount: 1,
  });
  const admission = await buildWorldProgramAdmissionCertificate(policy, manifest, certificate);

  assert.equal(await validateWorldProgramAdmissionPolicy(policy), true);
  assert.equal(await validateWorldProgramAdmissionCertificate(admission, policy, manifest, certificate), true);
  assert.equal(await auditWorldProgramAdmission(policy, manifest, certificate, admission), true);
  assert.equal(admission.admitted, true);
  assert.deepEqual(admission.failedRequirements, []);
  assert.equal(admission.requirementCount, 19);
  assert.equal(admission.passedRequirements.includes("required_dependencies_present"), true);
  assert.equal(admission.passedRequirements.includes("min_committed_count"), true);

  const stricter = await buildWorldProgramAdmissionPolicy({
    policyId: "test_scalar_world_policy_strict",
    policyVersion: "1.0",
    allowedProgramIds: ["test_scalar_world_program"],
    requiredArtifactKeys: ["rrlmSnapshotHash"],
    minCommittedCount: 2,
  });
  const rejected = await buildWorldProgramAdmissionCertificate(stricter, manifest, certificate);
  assert.equal(await validateWorldProgramAdmissionCertificate(rejected, stricter, manifest, certificate), true);
  assert.equal(rejected.admitted, false);
  assert.deepEqual(rejected.failedRequirements, ["required_artifacts_present", "min_committed_count"]);

  const tampered = await tamperWorldProgramAdmissionCertificate(admission);
  assert.equal(await validateWorldProgramAdmissionCertificate(tampered, policy, manifest, certificate), false);
  assert.equal(await auditWorldProgramAdmission(policy, manifest, certificate, tampered), false);
});

test("world program evidence bundle verifies attestations against policy", async () => {
  const { manifest, certificate } = await runProgramFixture();
  const policy = await buildWorldProgramAdmissionPolicy({
    policyId: "test_scalar_world_policy",
    policyVersion: "1.0",
    allowedProgramIds: ["test_scalar_world_program"],
    allowedProposerIds: ["test_residual_proposer"],
    allowedProjectorIds: ["test_scalar_projector"],
    allowedLearnerIds: ["test_residual_learner"],
    allowedVerifierIds: ["scalar_program_oracle"],
    minStepCount: 2,
    minCommittedCount: 1,
    minRejectedCount: 1,
  });
  const admission = await buildWorldProgramAdmissionCertificate(policy, manifest, certificate);
  const bundle = await buildWorldProgramEvidenceBundle(
    manifest,
    certificate,
    policy,
    admission,
    { bundleId: "test_scalar_world_program_bundle" },
  );
  const verification = await buildWorldProgramBundleVerificationCertificate(bundle);

  assert.equal(await validateWorldProgramEvidenceBundle(bundle), true);
  assert.equal(await auditWorldProgramEvidenceBundle(manifest, certificate, policy, admission, bundle), true);
  assert.equal(bundle.bundleId, "test_scalar_world_program_bundle");
  assert.deepEqual(bundle.stepCertificateHashes, certificate.stepCertificateHashes);
  assert.deepEqual(bundle.receiptHashes, certificate.receiptHashes);
  assert.equal(bundle.finalLearnerSnapshotHash, certificate.finalLearnerSnapshotHash);
  assert.deepEqual(bundle.artifactHashGroups, certificate.artifactHashGroups);
  assert.equal(await validateWorldProgramBundleVerificationCertificate(verification, bundle), true);
  assert.equal(await auditWorldProgramBundleVerification(bundle, verification), true);
  assert.equal(verification.verified, true);
  assert.deepEqual(verification.failedRequirements, []);
  assert.equal(verification.passedRequirements.includes("admission_certificate_admitted"), true);
  assert.equal(verification.requirementCount, 11);
  assert.equal(verification.inputAttestationHashes[0], manifest.manifestHash);
  assert.equal(verification.inputAttestationHashes[1], certificate.certificateHash);
  assert.equal(verification.inputAttestationHashes[2], policy.policyHash);
  assert.equal(verification.inputAttestationHashes[3], admission.certificateHash);

  const tamperedBundle = await tamperWorldProgramEvidenceBundle(bundle);
  assert.equal(await validateWorldProgramEvidenceBundle(tamperedBundle), false);
  assert.equal(await auditWorldProgramBundleVerification(tamperedBundle, verification), false);
  const tamperedVerification = await tamperWorldProgramBundleVerificationCertificate(verification);
  assert.equal(await validateWorldProgramBundleVerificationCertificate(tamperedVerification, bundle), false);

  const rejectedPolicy = await buildWorldProgramAdmissionPolicy({
    policyId: "test_scalar_world_policy_reject",
    policyVersion: "1.0",
    allowedProgramIds: ["test_scalar_world_program"],
    minCommittedCount: 2,
  });
  const rejectedAdmission = await buildWorldProgramAdmissionCertificate(rejectedPolicy, manifest, certificate);
  const rejectedBundle = await buildWorldProgramEvidenceBundle(manifest, certificate, rejectedPolicy, rejectedAdmission);
  const rejectedVerification = await buildWorldProgramBundleVerificationCertificate(rejectedBundle);
  assert.equal(await validateWorldProgramEvidenceBundle(rejectedBundle), true);
  assert.equal(await validateWorldProgramBundleVerificationCertificate(rejectedVerification, rejectedBundle), true);
  assert.equal(rejectedVerification.verified, false);
  assert.deepEqual(rejectedVerification.failedRequirements, ["admission_certificate_admitted"]);
});

test("world program replay package verifies step bodies against bundle", async () => {
  const { engine, first, second, manifest, certificate } = await runProgramFixture();
  const policy = await buildWorldProgramAdmissionPolicy({
    policyId: "test_scalar_world_policy",
    policyVersion: "1.0",
    allowedProgramIds: ["test_scalar_world_program"],
    allowedProposerIds: ["test_residual_proposer"],
    allowedProjectorIds: ["test_scalar_projector"],
    allowedLearnerIds: ["test_residual_learner"],
    allowedVerifierIds: ["scalar_program_oracle"],
    minStepCount: 2,
    minCommittedCount: 1,
    minRejectedCount: 1,
  });
  const admission = await buildWorldProgramAdmissionCertificate(policy, manifest, certificate);
  const bundle = await buildWorldProgramEvidenceBundle(manifest, certificate, policy, admission);
  const replayPackage = await buildWorldProgramReplayPackage(
    bundle,
    [first, second],
    { packageId: "test_scalar_world_program_replay" },
  );
  const replayVerification = await buildWorldProgramReplayVerificationCertificate(replayPackage);

  assert.equal(await validateWorldProgramReplayStep(replayPackage.steps[0], { expectedIndex: 0 }), true);
  assert.equal(await validateWorldProgramReplayPackage(replayPackage), true);
  assert.equal(await auditWorldProgramReplayPackage(bundle, [first, second], replayPackage), true);
  assert.equal(await validateWorldProgramReplayVerificationCertificate(replayVerification, replayPackage), true);
  assert.equal(await auditWorldProgramReplayVerification(replayPackage, replayVerification), true);
  assert.equal(replayVerification.replayVerified, true);
  assert.equal(replayVerification.requirementCount, 16);
  assert.equal(replayVerification.passedRequirements.includes("trace_hashes_bound"), true);
  assert.equal(replayVerification.passedRequirements.includes("learner_deltas_valid"), true);
  assert.deepEqual(replayPackage.receiptHashes, certificate.receiptHashes);
  assert.deepEqual(replayPackage.stepCertificateHashes, certificate.stepCertificateHashes);
  assert.equal(replayPackage.finalLearnerSnapshotHash, certificate.finalLearnerSnapshotHash);
  assert.equal(replayPackage.ledgerHead, engine.ledger.head);

  const tamperedPackage = await tamperWorldProgramReplayPackage(replayPackage);
  assert.equal(await validateWorldProgramReplayPackage(tamperedPackage), false);
  assert.equal(await auditWorldProgramReplayVerification(tamperedPackage, replayVerification), false);
  const tamperedVerification = await tamperWorldProgramReplayVerificationCertificate(replayVerification);
  assert.equal(await validateWorldProgramReplayVerificationCertificate(tamperedVerification, replayPackage), false);

  const tamperedStepPending = {
    ...replayPackage.steps[0],
    trace: { ...replayPackage.steps[0].trace, branchId: "tampered-branch" },
    stepHash: "",
  };
  const tamperedStep = { ...tamperedStepPending, stepHash: await worldProgramReplayStepHash(tamperedStepPending) };
  const tamperedSteps = [tamperedStep, ...replayPackage.steps.slice(1)];
  const tamperedBodyPending = {
    ...replayPackage,
    steps: tamperedSteps,
    stepHashes: tamperedSteps.map((step) => step.stepHash),
    packageBodyHash: "",
    packageHash: "",
  };
  const tamperedBodyWithHash = {
    ...tamperedBodyPending,
    packageBodyHash: await worldProgramReplayPackageBodyHash(tamperedBodyPending),
  };
  const tamperedBody = {
    ...tamperedBodyWithHash,
    packageHash: await worldProgramReplayPackageHash(tamperedBodyWithHash),
  };
  const bodyVerification = await buildWorldProgramReplayVerificationCertificate(tamperedBody);

  assert.equal(await validateWorldProgramReplayPackage(tamperedBody), false);
  assert.equal(bodyVerification.replayVerified, false);
  assert.equal(bodyVerification.failedRequirements.includes("replay_package_valid"), true);
  assert.equal(bodyVerification.failedRequirements.includes("trace_hashes_bound"), true);
});

test("world program certificate detects tampering", async () => {
  const { engine, first, second, manifest, certificate } = await runProgramFixture();
  const tamperedCertificate = await tamperWorldProgramCertificate(certificate);
  const tamperedManifest = {
    ...manifest,
    verifierVersion: "9.9",
    manifestHash: "",
  };
  tamperedManifest.manifestHash = await worldProgramManifestHash(tamperedManifest);

  assert.equal(await validateWorldProgramCertificate(tamperedCertificate, manifest), false);
  assert.equal(await auditWorldProgramCertificate(manifest, [first, second], tamperedCertificate, {
    ledgerHead: engine.ledger.head,
    invalidCommitCount: engine.invalidCommitCount,
    replayRollbackRate: 1,
  }), false);
  assert.equal(await validateWorldProgramCertificate(certificate, tamperedManifest), false);
  assert.equal(await auditWorldProgramCertificate(tamperedManifest, [first, second], certificate, {
    ledgerHead: engine.ledger.head,
    invalidCommitCount: engine.invalidCommitCount,
    replayRollbackRate: 1,
  }), false);
});
