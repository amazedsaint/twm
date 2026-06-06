import assert from "node:assert/strict";
import test from "node:test";

import {
  Ledger,
  ScalarProgramAdapter,
  TransactionEngine,
  TransactionalWorldModelRuntime,
  applyWorldLearnerDelta,
  auditWorldLearnerDelta,
  auditWorldLearnerLineage,
  auditWorldLearnerMerge,
  auditWorldLearnerUpdate,
  auditWorldModelStep,
  buildWorldLearnerDeltaCertificate,
  buildWorldLearnerLineageCertificate,
  makeScalarCandidate,
  makeTrace,
  mergeWorldLearnerSnapshots,
  runWorldLoopBenchmark,
  validateWorldLearnerDeltaCertificate,
  validateWorldLearnerLineageCertificate,
  validateWorldLearnerMergeCertificate,
  validateWorldLearnerSnapshot,
  validateWorldLearnerUpdateCertificate,
  validateWorldModelStepCertificate,
  worldLearnerDeltaCertificateHash,
  worldLearnerLineageCertificateHash,
  worldLearnerMergeCertificateHash,
  worldLearnerSnapshotHash,
  worldLearnerStateHash,
  worldLearnerUpdateCertificateHash,
  worldModelStepCertificateHash,
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
      branchId: `test-world-${program.length}`,
      actions: program,
      seeds: ["test-world", program.length],
      modelVersion: this.proposerVersion,
    });
  }
}

class TestScalarProjector {
  projectorId = "test_scalar_projector";
  projectorVersion = "3.0";

  project(_state, trace) {
    return makeScalarCandidate("test-world", 5, trace.actions);
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

test("transactional world model runtime binds proposer, projector, receipt, and learner", async () => {
  const state = { episode: 0, target: 5, solved: false };
  const proposer = new TestResidualProposer();
  const projector = new TestScalarProjector();
  const learner = new TestResidualLearner(proposer);
  const engine = new TransactionEngine(new ScalarProgramAdapter(), new Ledger());
  const runtime = new TransactionalWorldModelRuntime(engine, proposer, projector, learner);

  const first = await runtime.step(state);

  assert.equal(first.committed, false);
  assert.equal(first.reason, "hard_reject");
  assert.equal(first.certificate.proposerId, "test_residual_proposer");
  assert.equal(first.certificate.proposerVersion, "2.0");
  assert.equal(first.certificate.projectorId, "test_scalar_projector");
  assert.equal(first.certificate.projectorVersion, "3.0");
  assert.equal(first.certificate.learnerId, "test_residual_learner");
  assert.equal(first.certificate.learnerVersion, "4.0");
  assert.equal(first.learnerUpdateCount, 1);
  assert.deepEqual(proposer.learnedRepair, { op: "add", value: 5 });
  assert.equal(await validateWorldModelStepCertificate(first.certificate), true);
  assert.equal(await validateWorldLearnerSnapshot(first.learnerSnapshot), true);
  assert.equal(await validateWorldLearnerSnapshot(first.preLearnerSnapshot), true);
  assert.equal(await validateWorldLearnerUpdateCertificate(first.learnerUpdateCertificate), true);
  assert.equal(await validateWorldLearnerDeltaCertificate(first.learnerDeltaCertificate), true);
  assert.equal(await auditWorldLearnerUpdate(first.receipt, first.preLearnerSnapshot, first.learnerSnapshot, first.learnerUpdateCertificate), true);
  assert.equal(await auditWorldLearnerDelta(first.preLearnerSnapshot, first.learnerSnapshot, first.learnerUpdateCertificate, first.learnerDeltaCertificate), true);
  assert.deepEqual(
    applyWorldLearnerDelta(first.preLearnerSnapshot.learnerState, first.learnerDeltaCertificate.learnerDelta),
    first.learnerSnapshot.learnerState,
  );
  assert.equal(first.preLearnerSnapshot.updateCount, 0);
  assert.equal(first.learnerUpdateCertificate.sourceReceiptHash, first.receipt.receiptHash);
  assert.equal(first.learnerUpdateCertificate.preUpdateCount, 0);
  assert.equal(first.learnerUpdateCertificate.postUpdateCount, 1);
  assert.equal(first.learnerUpdateCertificate.preLearnerSnapshotHash, first.preLearnerSnapshot.snapshotHash);
  assert.equal(first.learnerUpdateCertificate.learnerSnapshotHash, first.learnerSnapshot.snapshotHash);
  assert.equal(first.certificate.learnerUpdateCertificateHash, first.learnerUpdateCertificate.certificateHash);
  assert.equal(first.certificate.learnerStateHash, first.learnerSnapshot.learnerStateHash);
  assert.equal(first.certificate.learnerSnapshotHash, first.learnerSnapshot.snapshotHash);
  assert.equal(await auditWorldModelStep(first.receipt, first.certificate, {
    learnerSnapshot: first.learnerSnapshot,
    learnerUpdateCertificate: first.learnerUpdateCertificate,
  }), true);

  const second = await runtime.step(first.state);

  assert.equal(second.committed, true);
  assert.equal(second.reason, "commit");
  assert.equal(second.state.value, 5);
  assert.equal(second.learnerUpdateCount, 2);
  assert.equal(second.receipt.hardResult.result, "accept");
  assert.equal(await validateWorldModelStepCertificate(second.certificate), true);
  assert.equal(await validateWorldLearnerSnapshot(second.learnerSnapshot), true);
  assert.equal(await validateWorldLearnerUpdateCertificate(second.learnerUpdateCertificate), true);
  assert.equal(await validateWorldLearnerDeltaCertificate(second.learnerDeltaCertificate), true);
  assert.deepEqual(second.learnerSnapshot.sourceReceiptHashes, [first.receipt.receiptHash, second.receipt.receiptHash]);
  assert.deepEqual(second.preLearnerSnapshot.sourceReceiptHashes, [first.receipt.receiptHash]);
  assert.equal(second.learnerUpdateCertificate.sourceReceiptHash, second.receipt.receiptHash);
  assert.equal(second.learnerUpdateCertificate.preUpdateCount, 1);
  assert.equal(second.learnerUpdateCertificate.postUpdateCount, 2);
  assert.equal(second.learnerUpdateCertificate.preLearnerSnapshotHash, second.preLearnerSnapshot.snapshotHash);
  assert.equal(second.learnerUpdateCertificate.learnerSnapshotHash, second.learnerSnapshot.snapshotHash);
  assert.equal(second.certificate.learnerUpdateCertificateHash, second.learnerUpdateCertificate.certificateHash);
  assert.equal(second.learnerSnapshot.learnerState.acceptedCount, 1);
  assert.equal(second.learnerSnapshot.learnerState.rejectedCount, 1);
  assert.equal(await auditWorldLearnerUpdate(second.receipt, second.preLearnerSnapshot, second.learnerSnapshot, second.learnerUpdateCertificate), true);
  assert.equal(await auditWorldLearnerDelta(second.preLearnerSnapshot, second.learnerSnapshot, second.learnerUpdateCertificate, second.learnerDeltaCertificate), true);
  assert.deepEqual(
    applyWorldLearnerDelta(second.preLearnerSnapshot.learnerState, second.learnerDeltaCertificate.learnerDelta),
    second.learnerSnapshot.learnerState,
  );
  assert.equal(await auditWorldModelStep(second.receipt, second.certificate, {
    learnerSnapshot: second.learnerSnapshot,
    learnerUpdateCertificate: second.learnerUpdateCertificate,
  }), true);
  const lineage = await buildWorldLearnerLineageCertificate(
    first.preLearnerSnapshot,
    second.learnerSnapshot,
    [first.learnerUpdateCertificate, second.learnerUpdateCertificate],
  );
  assert.equal(await validateWorldLearnerLineageCertificate(lineage), true);
  assert.equal(await auditWorldLearnerLineage(
    first.preLearnerSnapshot,
    second.learnerSnapshot,
    [first.learnerUpdateCertificate, second.learnerUpdateCertificate],
    lineage,
  ), true);
  assert.equal(lineage.initialSnapshotHash, first.preLearnerSnapshot.snapshotHash);
  assert.equal(lineage.finalSnapshotHash, second.learnerSnapshot.snapshotHash);
  assert.equal(lineage.appliedUpdateCount, 2);
  assert.deepEqual(lineage.sourceReceiptHashes, [first.receipt.receiptHash, second.receipt.receiptHash]);
  assert.deepEqual(lineage.updateCertificateHashes, [
    first.learnerUpdateCertificate.certificateHash,
    second.learnerUpdateCertificate.certificateHash,
  ]);
  assert.equal(await engine.ledger.audit(), true);
  assert.deepEqual(await engine.replayAudit(state), second.state);
  assert.deepEqual(await engine.rollbackAudit(state), state);
  assert.equal(engine.invalidCommitCount, 0);
});

test("world model certificate rejects self-consistent impossible commit mutation", async () => {
  const state = { episode: 0, target: 5, solved: false };
  const proposer = new TestResidualProposer();
  const projector = new TestScalarProjector();
  const learner = new TestResidualLearner(proposer);
  const runtime = new TransactionalWorldModelRuntime(
    new TransactionEngine(new ScalarProgramAdapter(), new Ledger()),
    proposer,
    projector,
    learner,
  );

  const first = await runtime.step(state);
  const second = await runtime.step(state);
  const tampered = { ...second.certificate, committed: false, certificateHash: "" };
  tampered.certificateHash = await worldModelStepCertificateHash(tampered);
  const tamperedSnapshot = { ...second.learnerSnapshot, updateCount: 99, snapshotHash: "" };
  const tamperedUpdate = { ...second.learnerUpdateCertificate, postUpdateCount: 4, certificateHash: "" };
  tamperedUpdate.certificateHash = await worldLearnerUpdateCertificateHash(tamperedUpdate);
  const tamperedDelta = { ...second.learnerDeltaCertificate, deltaOpCount: 9, certificateHash: "" };
  tamperedDelta.certificateHash = await worldLearnerDeltaCertificateHash(tamperedDelta);
  const lineage = await buildWorldLearnerLineageCertificate(
    first.preLearnerSnapshot,
    second.learnerSnapshot,
    [first.learnerUpdateCertificate, second.learnerUpdateCertificate],
  );
  const tamperedLineage = { ...lineage, appliedUpdateCount: 3, certificateHash: "" };
  tamperedLineage.certificateHash = await worldLearnerLineageCertificateHash(tamperedLineage);

  assert.equal(await validateWorldModelStepCertificate(tampered), false);
  assert.equal(await auditWorldModelStep(second.receipt, tampered), false);
  assert.equal(await validateWorldLearnerSnapshot(tamperedSnapshot), false);
  assert.equal(await auditWorldModelStep(second.receipt, second.certificate, { learnerSnapshot: tamperedSnapshot }), false);
  assert.equal(await validateWorldLearnerUpdateCertificate(tamperedUpdate), false);
  assert.equal(await auditWorldLearnerUpdate(second.receipt, second.preLearnerSnapshot, second.learnerSnapshot, tamperedUpdate), false);
  assert.equal(await auditWorldModelStep(second.receipt, second.certificate, { learnerUpdateCertificate: tamperedUpdate }), false);
  assert.equal(await validateWorldLearnerDeltaCertificate(tamperedDelta), false);
  assert.equal(await auditWorldLearnerDelta(second.preLearnerSnapshot, second.learnerSnapshot, second.learnerUpdateCertificate, tamperedDelta), false);
  assert.equal(await validateWorldLearnerLineageCertificate(tamperedLineage), false);
  assert.equal(await auditWorldLearnerLineage(
    first.preLearnerSnapshot,
    second.learnerSnapshot,
    [first.learnerUpdateCertificate, second.learnerUpdateCertificate],
    tamperedLineage,
  ), false);
});

test("world learner snapshots merge disjoint evidence and reject conflicts", async () => {
  async function runEpisode(episode) {
    const state = { episode, target: 5, solved: false };
    const proposer = new TestResidualProposer();
    const projector = new TestScalarProjector();
    const learner = new TestResidualLearner(proposer);
    const runtime = new TransactionalWorldModelRuntime(
      new TransactionEngine(new ScalarProgramAdapter(), new Ledger()),
      proposer,
      projector,
      learner,
    );
    const first = await runtime.step(state);
    const second = await runtime.step(first.state);
    return { first, second };
  }

  async function forkFrom(baseStep, episode) {
    const state = { episode, target: 5, solved: false };
    const proposer = new TestResidualProposer();
    proposer.learnedRepair = { ...baseStep.learnerSnapshot.learnerState.learnedRepair };
    const learner = new TestResidualLearner(proposer);
    learner.acceptedCount = baseStep.learnerSnapshot.learnerState.acceptedCount;
    learner.rejectedCount = baseStep.learnerSnapshot.learnerState.rejectedCount;
    learner.updateCount = baseStep.learnerSnapshot.learnerState.updateCount;
    const runtime = new TransactionalWorldModelRuntime(
      new TransactionEngine(new ScalarProgramAdapter(), new Ledger()),
      proposer,
      new TestScalarProjector(),
      learner,
    );
    runtime.learnerUpdateCount = baseStep.learnerSnapshot.updateCount;
    runtime.learnerReceiptHashes = [...baseStep.learnerSnapshot.sourceReceiptHashes];
    return runtime.step(state);
  }

  const leftRun = await runEpisode(0);
  const rightRun = await runEpisode(1);
  const left = leftRun.second.learnerSnapshot;
  const right = rightRun.second.learnerSnapshot;
  const result = await mergeWorldLearnerSnapshots(left, right);
  const reverse = await mergeWorldLearnerSnapshots(right, left);
  const duplicate = await mergeWorldLearnerSnapshots(left, left);
  const tampered = { ...result.certificate, mergedUpdateCount: 3, certificateHash: "" };
  tampered.certificateHash = await worldLearnerMergeCertificateHash(tampered);
  const conflictingRight = {
    ...right,
    learnerState: { ...right.learnerState, learnedRepair: { op: "add", value: 7 } },
    learnerStateHash: "",
    snapshotHash: "",
  };
  conflictingRight.learnerStateHash = await worldLearnerStateHash(conflictingRight.learnerState);
  conflictingRight.snapshotHash = await worldLearnerSnapshotHash(conflictingRight);

  assert.equal(await validateWorldLearnerMergeCertificate(result.certificate), true);
  assert.equal(await auditWorldLearnerMerge(left, right, result.mergedSnapshot, result.certificate), true);
  assert.equal(result.mergedSnapshot.updateCount, 4);
  assert.equal(result.mergedSnapshot.learnerState.acceptedCount, 2);
  assert.equal(result.mergedSnapshot.learnerState.rejectedCount, 2);
  assert.deepEqual(result.mergedSnapshot.learnerState.learnedRepair, { op: "add", value: 5 });
  assert.equal(result.mergedSnapshot.snapshotHash, reverse.mergedSnapshot.snapshotHash);
  assert.equal(duplicate.mergedSnapshot.snapshotHash, left.snapshotHash);
  assert.equal(await validateWorldLearnerMergeCertificate(tampered), false);
  assert.equal(await auditWorldLearnerMerge(left, right, result.mergedSnapshot, tampered), false);
  await assert.rejects(() => mergeWorldLearnerSnapshots(left, conflictingRight), /conflicting learner state/);

  const partialRun = await runEpisode(10);
  const partialRight = await forkFrom(partialRun.first, 11);
  const partial = await mergeWorldLearnerSnapshots(
    partialRun.second.learnerSnapshot,
    partialRight.learnerSnapshot,
    {
      baseSnapshot: partialRun.first.learnerSnapshot,
      leftDeltaCertificates: [partialRun.second.learnerDeltaCertificate],
      rightDeltaCertificates: [partialRight.learnerDeltaCertificate],
    },
  );
  assert.equal(partial.certificate.mergeBasis, "delta_common_prefix");
  assert.equal(partial.certificate.baseSnapshotHash, partialRun.first.learnerSnapshot.snapshotHash);
  assert.equal(partial.certificate.sharedReceiptCount, 1);
  assert.equal(partial.certificate.commonPrefixReceiptCount, 1);
  assert.equal(partial.mergedSnapshot.updateCount, 3);
  assert.equal(partial.mergedSnapshot.learnerState.acceptedCount, 2);
  assert.equal(partial.mergedSnapshot.learnerState.rejectedCount, 1);
  assert.equal(partial.mergedSnapshot.learnerState.updateCount, 3);
  assert.equal(partial.mergedSnapshot.sourceReceiptHashes[0], partialRun.first.receipt.receiptHash);
  assert.equal(await validateWorldLearnerMergeCertificate(partial.certificate), true);
  assert.equal(await auditWorldLearnerMerge(
    partialRun.second.learnerSnapshot,
    partialRight.learnerSnapshot,
    partial.mergedSnapshot,
    partial.certificate,
    {
      baseSnapshot: partialRun.first.learnerSnapshot,
      leftDeltaCertificates: [partialRun.second.learnerDeltaCertificate],
      rightDeltaCertificates: [partialRight.learnerDeltaCertificate],
    },
  ), true);
  await assert.rejects(
    () => mergeWorldLearnerSnapshots(partialRun.second.learnerSnapshot, partialRight.learnerSnapshot),
    /partially overlapping learner snapshots require base snapshot and per-receipt deltas/,
  );
  const tamperedPartialDelta = { ...partialRight.learnerDeltaCertificate, deltaOpCount: 9, certificateHash: "" };
  tamperedPartialDelta.certificateHash = await worldLearnerDeltaCertificateHash(tamperedPartialDelta);
  assert.equal(await auditWorldLearnerMerge(
    partialRun.second.learnerSnapshot,
    partialRight.learnerSnapshot,
    partial.mergedSnapshot,
    partial.certificate,
    {
      baseSnapshot: partialRun.first.learnerSnapshot,
      leftDeltaCertificates: [partialRun.second.learnerDeltaCertificate],
      rightDeltaCertificates: [tamperedPartialDelta],
    },
  ), false);

  const leftConflict = {
    ...partialRun.second.learnerSnapshot,
    learnerState: { ...partialRun.second.learnerSnapshot.learnerState, learnedRepair: { op: "add", value: 6 } },
    learnerStateHash: "",
    snapshotHash: "",
  };
  leftConflict.learnerStateHash = await worldLearnerStateHash(leftConflict.learnerState);
  leftConflict.snapshotHash = await worldLearnerSnapshotHash(leftConflict);
  const rightConflict = {
    ...partialRight.learnerSnapshot,
    learnerState: { ...partialRight.learnerSnapshot.learnerState, learnedRepair: { op: "add", value: 7 } },
    learnerStateHash: "",
    snapshotHash: "",
  };
  rightConflict.learnerStateHash = await worldLearnerStateHash(rightConflict.learnerState);
  rightConflict.snapshotHash = await worldLearnerSnapshotHash(rightConflict);
  const leftConflictDelta = await buildWorldLearnerDeltaCertificate(
    partialRun.first.learnerSnapshot,
    leftConflict,
    partialRun.second.learnerUpdateCertificate,
  );
  const rightConflictDelta = await buildWorldLearnerDeltaCertificate(
    partialRun.first.learnerSnapshot,
    rightConflict,
    partialRight.learnerUpdateCertificate,
  );
  await assert.rejects(
    () => mergeWorldLearnerSnapshots(leftConflict, rightConflict, {
      baseSnapshot: partialRun.first.learnerSnapshot,
      leftDeltaCertificates: [leftConflictDelta],
      rightDeltaCertificates: [rightConflictDelta],
    }),
    /conflicting partial-overlap learner state keys/,
  );
});

test("world loop benchmark reports checked residual learning loop", async () => {
  const report = await runWorldLoopBenchmark();

  assert.equal(report.stepCount, 2);
  assert.equal(report.firstCommitted, false);
  assert.equal(report.secondCommitted, true);
  assert.equal(report.firstDecision, "hard_reject");
  assert.equal(report.secondDecision, "commit");
  assert.equal(report.learnerUpdateCount, 2);
  assert.equal(report.acceptedCount, 1);
  assert.equal(report.rejectedCount, 1);
  assert.equal(report.certificateValidCount, 2);
  assert.equal(report.auditValidCount, 2);
  assert.equal(report.proposerImprovedFromResidual, true);
  assert.equal(report.hardVerifierOwnedCommit, true);
  assert.equal(report.learnerSnapshotValidCount, 2);
  assert.equal(report.stepCertificateBindsLearnerState, true);
  assert.equal(report.learnerUpdateCertificateValidCount, 2);
  assert.equal(report.learnerUpdateAuditValidCount, 2);
  assert.equal(report.stepCertificateBindsLearnerUpdate, true);
  assert.equal(report.learnerUpdateTamperDetected, true);
  assert.equal(report.learnerDeltaCertificateValidCount, 2);
  assert.equal(report.learnerDeltaAuditValidCount, 2);
  assert.equal(report.learnerDeltaBindsUpdates, true);
  assert.equal(report.learnerDeltaTamperDetected, true);
  assert.equal(report.learnerLineageCertificateValid, true);
  assert.equal(report.learnerLineageAuditValid, true);
  assert.equal(report.learnerLineageBindsUpdates, true);
  assert.equal(report.learnerLineageTamperDetected, true);
  assert.equal(report.learnerMergeCertificateValid, true);
  assert.equal(report.learnerMergeAuditValid, true);
  assert.equal(report.learnerMergeDisjointReceipts, true);
  assert.equal(report.learnerMergePartialOverlapValid, true);
  assert.equal(report.learnerMergePartialOverlapAuditValid, true);
  assert.equal(report.learnerMergePartialOverlapCountsSharedOnce, true);
  assert.equal(report.learnerMergePartialOverlapRequiresDeltas, true);
  assert.equal(report.learnerMergeTamperDetected, true);
  assert.equal(report.learnerMergeConflictDetected, true);
  assert.equal(report.rrlmWorldFirstCommitted, false);
  assert.equal(report.rrlmWorldSecondCommitted, true);
  assert.equal(report.rrlmWorldSelectedRepairMacro, true);
  assert.equal(report.rrlmWorldProposalCertificateValid, true);
  assert.equal(report.rrlmWorldTransportCertificateValid, true);
  assert.equal(report.rrlmWorldArtifactsBoundToReceipts, true);
  assert.equal(report.rrlmWorldRejectedMacroPenalized, true);
  assert.equal(report.rrlmWorldTamperDetected, true);
  assert.equal(report.worldProgramManifestValid, true);
  assert.equal(report.worldProgramCertificateValid, true);
  assert.equal(report.worldProgramAuditValid, true);
  assert.equal(report.worldProgramBindsRrlmArtifacts, true);
  assert.equal(report.worldProgramTamperDetected, true);
  assert.equal(report.worldProgramAdmissionPolicyValid, true);
  assert.equal(report.worldProgramAdmissionCertificateValid, true);
  assert.equal(report.worldProgramAdmissionAuditValid, true);
  assert.equal(report.worldProgramAdmitted, true);
  assert.equal(report.worldProgramAdmissionRejectsUnmetRequirements, true);
  assert.equal(report.worldProgramAdmissionTamperDetected, true);
  assert.equal(report.worldProgramEvidenceBundleValid, true);
  assert.equal(report.worldProgramEvidenceBundleAuditValid, true);
  assert.equal(report.worldProgramBundleVerificationCertificateValid, true);
  assert.equal(report.worldProgramBundleVerified, true);
  assert.equal(report.worldProgramBundleTamperDetected, true);
  assert.equal(report.worldProgramReplayPackageValid, true);
  assert.equal(report.worldProgramReplayPackageAuditValid, true);
  assert.equal(report.worldProgramReplayVerificationCertificateValid, true);
  assert.equal(report.worldProgramReplayVerified, true);
  assert.equal(report.worldProgramReplayTamperDetected, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.learnerSnapshotTamperDetected, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
});
