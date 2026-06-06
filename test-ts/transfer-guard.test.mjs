import assert from "node:assert/strict";
import test from "node:test";

import {
  TRANSFER_GUARD_SNAPSHOT_SCHEMA,
  TransferGuardMemory,
  buildTransferEvaluationCertificate,
  buildTransferGuardDecision,
  runTransferGuardBenchmark,
  transferGuardSnapshotHash,
  validateTransferEvaluationCertificate,
  validateTransferGuardDecision,
  validateTransferGuardSnapshot,
} from "../dist/index.js";

const HASH_A = "a".repeat(64);
const HASH_B = "b".repeat(64);
const HASH_C = "c".repeat(64);

async function certificate(overrides = {}) {
  return buildTransferEvaluationCertificate({
    claimId: "transfer-guard-test",
    learnerId: "source-policy",
    learnerSnapshotHash: HASH_A,
    sourceDomains: ["source"],
    targetDomains: ["target"],
    sourceReceiptHashes: [HASH_B],
    targetEvaluationReceiptHashes: [HASH_C],
    baselineName: "target-baseline",
    transferName: "source-transfer",
    baselineSuccessCount: 1,
    transferSuccessCount: 0,
    baselineVerifierCalls: 1,
    transferVerifierCalls: 1,
    sameCaseBaseline: true,
    hardCommitOnly: true,
    invalidCommitCount: 0,
    ledgerAudit: true,
    replayRollbackRate: 1,
    ...overrides,
  });
}

test("transfer guard blocks negative evidence and admits validated positive evidence", async () => {
  const negative = await certificate();
  const positive = await certificate({
    claimId: "positive-transfer",
    targetDomains: ["other-target"],
    baselineVerifierCalls: 2,
    transferVerifierCalls: 1,
    transferSuccessCount: 1,
  });
  const guard = new TransferGuardMemory();
  await guard.update(negative);
  await guard.update(positive);

  const blocked = await guard.decide(["source"], "target");
  const admitted = await guard.decide(["source"], "other-target");
  const missing = await guard.decide(["source"], "missing-target");
  const snapshot = await guard.snapshot();
  const negativeEntry = snapshot.entries.find((entry) => entry.targetDomain === "target");
  assert.equal(negativeEntry?.conclusion, "negative_transfer");
  const mismatchedSnapshot = {
    ...snapshot,
    entries: snapshot.entries.map((entry) => entry.targetDomain === "target"
      ? { ...entry, conclusion: "positive_transfer" }
      : entry),
    snapshotHash: "",
  };
  mismatchedSnapshot.snapshotHash = await transferGuardSnapshotHash(mismatchedSnapshot);
  const mismatchedDecision = await buildTransferGuardDecision({
    sourceDomains: ["source"],
    targetDomain: "target",
    admitted: false,
    reason: "positive_transfer_certificate",
    conclusion: "positive_transfer",
    certificateHash: negative.certificateHash,
  });
  const boolReplayRate = await certificate({ replayRollbackRate: true });

  assert.equal(blocked.admitted, false);
  assert.equal(blocked.reason, "negative_transfer_certificate");
  assert.equal(await validateTransferGuardDecision(blocked), true);
  assert.equal(admitted.admitted, true);
  assert.equal(admitted.reason, "positive_transfer_certificate");
  assert.equal(await validateTransferGuardDecision(admitted), true);
  assert.equal(missing.admitted, false);
  assert.equal(missing.reason, "no_valid_transfer_certificate");
  assert.equal(await validateTransferGuardDecision(missing), true);
  assert.equal(snapshot.schemaVersion, TRANSFER_GUARD_SNAPSHOT_SCHEMA);
  assert.equal(await validateTransferGuardSnapshot(snapshot), true);
  assert.equal(await validateTransferGuardSnapshot(mismatchedSnapshot), false);
  assert.equal(await validateTransferGuardDecision(mismatchedDecision), false);
  assert.equal(await validateTransferEvaluationCertificate(boolReplayRate), false);
  await assert.rejects(
    () => guard.update({ ...negative, transferSuccessCount: 1 }),
    /must validate/,
  );
});

test("transfer guard benchmark blocks source policy and falls back", async () => {
  const report = await runTransferGuardBenchmark();

  assert.equal(report.schemaVersion, TRANSFER_GUARD_SNAPSHOT_SCHEMA);
  assert.equal(report.snapshotValid, true);
  assert.equal(report.decisionValid, true);
  assert.equal(report.guardBlocksSourcePolicy, true);
  assert.equal(report.guardDecisionAdmitted, false);
  assert.equal(report.guardDecisionReason, "negative_transfer_certificate");
  assert.deepEqual(report.sourceSelected, ["quantity-5"]);
  assert.deepEqual(report.unguardedSelected, ["quantity-5"]);
  assert.equal(report.unguardedCommitted, false);
  assert.equal(report.unguardedResidualKind, "stock_shortage");
  assert.deepEqual(report.guardedSelected, ["quantity-2"]);
  assert.equal(report.guardedCommitted, true);
  assert.equal(report.guardedUsedTargetBaseline, true);
  assert.equal(report.avoidedNegativeTransfer, true);
  assert.equal(report.certificateConclusion, "negative_transfer");
  assert.equal(report.tamperDetected, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
});
