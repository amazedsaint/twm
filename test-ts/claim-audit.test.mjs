import assert from "node:assert/strict";
import test from "node:test";

import {
  certifyClaim,
  failedClaimKeys,
  requirement,
  runClaimAuditBenchmark,
  validateClaimCertificate,
} from "../dist/index.js";

test("claim certificate supports only when all requirements pass", async () => {
  const supported = await certifyClaim({
    claimId: "unit_supported",
    claimText: "unit claim",
    evidenceGrade: "G1",
    scope: "unit",
    requirements: [requirement("a", true), requirement("b", true)],
    metrics: { invalidCommitCount: 0 },
    boundary: "unit boundary",
  });
  const rejected = await certifyClaim({
    claimId: "unit_rejected",
    claimText: "unit overclaim",
    evidenceGrade: "G1",
    scope: "unit",
    requirements: [requirement("a", true), requirement("b", false, { reason: "missing evidence" })],
    metrics: { invalidCommitCount: 0 },
    boundary: "unit boundary",
  });

  assert.equal(supported.status, "supported");
  assert.deepEqual(failedClaimKeys(supported), []);
  assert.equal(await validateClaimCertificate(supported), true);
  assert.equal(rejected.status, "rejected");
  assert.deepEqual(failedClaimKeys(rejected), ["b"]);
  assert.equal(await validateClaimCertificate(rejected), true);
});

test("claim certificate detects tampering", async () => {
  const certificate = await certifyClaim({
    claimId: "unit_tamper",
    claimText: "unit claim",
    evidenceGrade: "G1",
    scope: "unit",
    requirements: [requirement("a", true)],
  });
  const tampered = { ...certificate, metrics: { invalidCommitCount: 1 } };

  assert.equal(await validateClaimCertificate(certificate), true);
  assert.equal(await validateClaimCertificate(tampered), false);
});

test("claim audit benchmark supports boundary and rejects overclaim", async () => {
  const report = await runClaimAuditBenchmark();

  assert.equal(report.supportedClaimId, "g1_learning_claim_boundary");
  assert.equal(report.supportedStatus, "supported");
  assert.deepEqual(report.supportedFailedKeys, []);
  assert.equal(report.supportedRequirementCount, 28);
  assert.equal(report.rejectedClaimId, "rrlm_reversibility_alone_lift_overclaim");
  assert.equal(report.rejectedStatus, "rejected");
  assert.deepEqual(report.rejectedFailedKeys, ["matched_non_reversible_lift"]);
  assert.equal(report.overclaimDetected, true);
  assert.equal(report.nullResultRecorded, true);
  assert.equal(report.mechanismAblationRecorded, true);
  assert.equal(report.heldoutTraceEvaluation, true);
  assert.equal(report.sameCaseEqualBudget, true);
  assert.equal(report.verifierCallAccounting, true);
  assert.equal(report.learningEvaluationCertificateValid, true);
  assert.equal(report.learningEvaluationSupportsClaim, true);
  assert.equal(report.transferEvaluationCertificateValid, true);
  assert.equal(report.transferPositiveOverclaimRejected, true);
  assert.equal(report.transferGuardSnapshotValid, true);
  assert.equal(report.transferGuardBlocksNegativeTransfer, true);
  assert.equal(report.rrlmProposalCertificateValid, true);
  assert.equal(report.rrlmTransportCertificateValid, true);
  assert.equal(report.worldLearnerUpdateCertificateValid, true);
  assert.equal(report.worldLearnerDeltaCertificateValid, true);
  assert.equal(report.worldLearnerLineageCertificateValid, true);
  assert.equal(report.worldLearnerMergeCertificateValid, true);
  assert.equal(report.worldLearnerPartialOverlapMergeValid, true);
  assert.equal(report.worldRrlmProposalCertificateValid, true);
  assert.equal(report.worldProgramCertificateValid, true);
  assert.equal(report.worldProgramAdmissionCertificateValid, true);
  assert.equal(report.worldProgramBundleVerificationCertificateValid, true);
  assert.equal(report.worldProgramReplayVerificationCertificateValid, true);
  assert.equal(report.supportedCertificateValid, true);
  assert.equal(report.rejectedCertificateValid, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.match(report.supportedCertificateHash, /^[0-9a-f]{64}$/);
  assert.match(report.rejectedCertificateHash, /^[0-9a-f]{64}$/);
});
