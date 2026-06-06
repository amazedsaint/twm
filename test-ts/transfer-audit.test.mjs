import assert from "node:assert/strict";
import test from "node:test";

import {
  TRANSFER_EVALUATION_CERTIFICATE_SCHEMA,
  buildTransferEvaluationCertificate,
  runCrossDomainTransferAudit,
  transferEvaluationRejectsPositiveClaim,
  transferEvaluationSupportsPositiveClaim,
  validateTransferEvaluationCertificate,
} from "../dist/index.js";

const HASH_A = "a".repeat(64);
const HASH_B = "b".repeat(64);
const HASH_C = "c".repeat(64);

test("transfer certificate rejects positive cross-domain overclaim", async () => {
  const certificate = await buildTransferEvaluationCertificate({
    claimId: "test-transfer",
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
  });

  assert.equal(certificate.schemaVersion, TRANSFER_EVALUATION_CERTIFICATE_SCHEMA);
  assert.equal(certificate.successDelta, -1);
  assert.equal(certificate.verifierCallDelta, 0);
  assert.equal(certificate.conclusion, "negative_transfer");
  assert.equal(await validateTransferEvaluationCertificate(certificate), true);
  assert.equal(await transferEvaluationRejectsPositiveClaim(certificate), true);
  assert.equal(await transferEvaluationSupportsPositiveClaim(certificate), false);
});

test("transfer certificate detects overlap and metric tamper", async () => {
  const certificate = await buildTransferEvaluationCertificate({
    claimId: "test-transfer",
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
  });
  const receiptOverlap = await buildTransferEvaluationCertificate({
    ...certificate,
    sourceReceiptHashes: [HASH_B],
    targetEvaluationReceiptHashes: [HASH_B],
    certificateHash: undefined,
  });
  const domainOverlap = await buildTransferEvaluationCertificate({
    ...certificate,
    sourceDomains: ["shared"],
    targetDomains: ["shared"],
    certificateHash: undefined,
  });
  const tampered = { ...certificate, transferSuccessCount: 1 };

  assert.equal(await validateTransferEvaluationCertificate(receiptOverlap), false);
  assert.equal(await validateTransferEvaluationCertificate(domainOverlap), false);
  assert.equal(await validateTransferEvaluationCertificate(tampered), false);
});

test("cross-domain transfer audit reports negative transfer", async () => {
  const report = await runCrossDomainTransferAudit();

  assert.equal(report.certificateValid, true);
  assert.equal(report.positiveTransferClaimSupported, false);
  assert.equal(report.positiveTransferClaimRejected, true);
  assert.equal(report.sourceDomainCount, 1);
  assert.equal(report.targetDomainCount, 1);
  assert.equal(report.sourceReceiptCount, 1);
  assert.equal(report.targetEvaluationReceiptCount, 2);
  assert.equal(report.sourceTargetDomainDisjoint, true);
  assert.equal(report.sourceTargetReceiptDisjoint, true);
  assert.equal(report.sameCaseBaseline, true);
  assert.deepEqual(report.sourceSelected, ["quantity-5"]);
  assert.deepEqual(report.transferSelected, ["quantity-5"]);
  assert.deepEqual(report.baselineSelected, ["quantity-2"]);
  assert.equal(report.transferSuccessCount, 0);
  assert.equal(report.baselineSuccessCount, 1);
  assert.equal(report.transferVerifierCalls, 1);
  assert.equal(report.baselineVerifierCalls, 1);
  assert.equal(report.successDelta, -1);
  assert.equal(report.verifierCallDelta, 0);
  assert.equal(report.conclusion, "negative_transfer");
  assert.equal(report.transferResidualKind, "stock_shortage");
  assert.equal(report.hardCommitOnly, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.overlapDetected, true);
});
