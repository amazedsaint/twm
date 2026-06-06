import assert from "node:assert/strict";
import test from "node:test";

import {
  LEARNING_EVALUATION_CERTIFICATE_SCHEMA,
  buildLearningEvaluationCertificate,
  learningEvaluationSupportsClaim,
  runLearningEvaluationBenchmark,
  validateLearningEvaluationCertificate,
} from "../dist/index.js";

const HASH_A = "a".repeat(64);
const HASH_B = "b".repeat(64);
const HASH_C = "c".repeat(64);

test("learning evaluation certificate validates trace-disjoint same-case evidence", async () => {
  const certificate = await buildLearningEvaluationCertificate({
    claimId: "test",
    learnerId: "learner",
    learnerSnapshotHash: HASH_A,
    trainingReceiptHashes: [HASH_B],
    evaluationReceiptHashes: [HASH_C],
    baselineName: "baseline",
    learnedName: "learned",
    baselineVerifierCalls: 2,
    learnedVerifierCalls: 1,
    baselineSuccessCount: 0,
    learnedSuccessCount: 1,
    verifierBudget: 1,
    candidateCount: 2,
    sameCaseBaseline: true,
    hardCommitOnly: true,
    invalidCommitCount: 0,
    ledgerAudit: true,
    replayRollbackRate: 1,
  });

  assert.equal(certificate.schemaVersion, LEARNING_EVALUATION_CERTIFICATE_SCHEMA);
  assert.equal(certificate.trainEvalDisjoint, true);
  assert.equal(certificate.verifierCallGainNumerator, 2);
  assert.equal(certificate.verifierCallGainDenominator, 1);
  assert.equal(await validateLearningEvaluationCertificate(certificate), true);
  assert.equal(await learningEvaluationSupportsClaim(certificate), true);
});

test("learning evaluation certificate rejects overlap, duplicate, and tamper", async () => {
  const overlap = await buildLearningEvaluationCertificate({
    claimId: "test",
    learnerId: "learner",
    learnerSnapshotHash: HASH_A,
    trainingReceiptHashes: [HASH_B],
    evaluationReceiptHashes: [HASH_B],
    baselineName: "baseline",
    learnedName: "learned",
    baselineVerifierCalls: 2,
    learnedVerifierCalls: 1,
    baselineSuccessCount: 0,
    learnedSuccessCount: 1,
    verifierBudget: 1,
    candidateCount: 2,
    sameCaseBaseline: true,
    hardCommitOnly: true,
    invalidCommitCount: 0,
    ledgerAudit: true,
    replayRollbackRate: 1,
  });
  const duplicate = {
    ...overlap,
    evaluationReceiptHashes: [HASH_C, HASH_C],
    trainEvalDisjoint: true,
    certificateHash: "",
  };
  duplicate.certificateHash = (await buildLearningEvaluationCertificate({
    ...duplicate,
    evaluationReceiptHashes: duplicate.evaluationReceiptHashes,
  })).certificateHash;
  const tampered = { ...duplicate, baselineVerifierCalls: 9 };

  assert.equal(await validateLearningEvaluationCertificate(overlap), false);
  assert.equal(await validateLearningEvaluationCertificate(duplicate), false);
  assert.equal(await validateLearningEvaluationCertificate(tampered), false);
});

test("learning evaluation certificate supports call reduction when success is preserved", async () => {
  const certificate = await buildLearningEvaluationCertificate({
    claimId: "test_call_reduction",
    learnerId: "learner",
    learnerSnapshotHash: HASH_A,
    trainingReceiptHashes: [HASH_B],
    evaluationReceiptHashes: [HASH_C],
    baselineName: "baseline",
    learnedName: "learned",
    baselineVerifierCalls: 2,
    learnedVerifierCalls: 1,
    baselineSuccessCount: 1,
    learnedSuccessCount: 1,
    verifierBudget: 1,
    candidateCount: 2,
    sameCaseBaseline: true,
    hardCommitOnly: true,
    invalidCommitCount: 0,
    ledgerAudit: true,
    replayRollbackRate: 1,
  });

  assert.equal(await validateLearningEvaluationCertificate(certificate), true);
  assert.equal(await learningEvaluationSupportsClaim(certificate), true);
});

test("learning evaluation benchmark certifies budget-policy claim boundary", async () => {
  const report = await runLearningEvaluationBenchmark();

  assert.equal(report.schemaVersion, LEARNING_EVALUATION_CERTIFICATE_SCHEMA);
  assert.equal(report.certificateValid, true);
  assert.equal(report.certificateSupportsClaim, true);
  assert.equal(report.claimId, "budget_policy_trace_disjoint_eval");
  assert.equal(report.trainingReceiptCount, 3);
  assert.equal(report.evaluationReceiptCount, 1);
  assert.equal(report.trainEvalDisjoint, true);
  assert.equal(report.sameCaseBaseline, true);
  assert.equal(report.baselineSuccessCount, 0);
  assert.equal(report.learnedSuccessCount, 1);
  assert.equal(report.baselineVerifierCalls, 2);
  assert.equal(report.learnedVerifierCalls, 1);
  assert.equal(report.verifierCallGainNumerator, 2);
  assert.equal(report.verifierCallGainDenominator, 1);
  assert.equal(report.hardCommitOnly, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.overlapDetected, true);
});
