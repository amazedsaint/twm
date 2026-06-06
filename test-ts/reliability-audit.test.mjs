import assert from "node:assert/strict";
import test from "node:test";

import {
  FLAWED_RELIABILITY_PRIMARY_ID,
  STRICT_RELIABILITY_PRIMARY_ID,
  VerifierReliabilityMemory,
  runReliabilityAuditBenchmark,
  validateVerifierReliabilitySnapshot,
  wilsonLowerBound,
} from "../dist/index.js";

test("wilson lower bound is conservative for small clean samples", () => {
  assert.equal(Number(wilsonLowerBound(3, 0).toFixed(12)), 0.438493919551);
  assert.equal(wilsonLowerBound(1, 2) < wilsonLowerBound(3, 0), true);
  assert.equal(wilsonLowerBound(0, 0), 0);
});

test("reliability memory ranks false-positive subject for audit", () => {
  const memory = new VerifierReliabilityMemory();
  for (let idx = 0; idx < 3; idx += 1) {
    memory.update(STRICT_RELIABILITY_PRIMARY_ID, true);
  }
  memory.update(FLAWED_RELIABILITY_PRIMARY_ID, true);
  memory.update(FLAWED_RELIABILITY_PRIMARY_ID, false);
  memory.update(FLAWED_RELIABILITY_PRIMARY_ID, false);

  assert.equal(memory.rankForAudit([STRICT_RELIABILITY_PRIMARY_ID, FLAWED_RELIABILITY_PRIMARY_ID])[0], FLAWED_RELIABILITY_PRIMARY_ID);
  assert.deepEqual(memory.selectForAudit([STRICT_RELIABILITY_PRIMARY_ID, FLAWED_RELIABILITY_PRIMARY_ID], 1), [FLAWED_RELIABILITY_PRIMARY_ID]);
  assert.equal(memory.score(STRICT_RELIABILITY_PRIMARY_ID).auditedFailures, 0);
  assert.equal(memory.score(FLAWED_RELIABILITY_PRIMARY_ID).auditedFailures, 2);
});

test("reliability snapshot detects tampering", async () => {
  const memory = new VerifierReliabilityMemory();
  memory.update(FLAWED_RELIABILITY_PRIMARY_ID, false);
  const snapshot = await memory.snapshot();
  const tampered = { ...snapshot, rows: snapshot.rows.map((row) => ({ ...row, auditedFailures: 0 })) };

  assert.equal(await validateVerifierReliabilitySnapshot(snapshot), true);
  assert.equal(await validateVerifierReliabilitySnapshot(tampered), false);
});

test("reliability audit benchmark metrics", async () => {
  const report = await runReliabilityAuditBenchmark();

  assert.equal(report.trainingReceiptCount, 6);
  assert.equal(report.strictSuccesses, 3);
  assert.equal(report.strictFailures, 0);
  assert.equal(report.flawedSuccesses, 1);
  assert.equal(report.flawedFailures, 2);
  assert.equal(report.riskOrder[0], FLAWED_RELIABILITY_PRIMARY_ID);
  assert.equal(report.auditBudget, 1);
  assert.equal(report.naiveAuditedSubject, STRICT_RELIABILITY_PRIMARY_ID);
  assert.equal(report.reliabilityAuditedSubject, FLAWED_RELIABILITY_PRIMARY_ID);
  assert.equal(report.naiveFalsePositiveDetected, false);
  assert.equal(report.reliabilityFalsePositiveDetected, true);
  assert.equal(report.reliabilityResidualKind, "verifier_false_positive");
  assert.equal(report.reliabilityAuditResidualKind, "stock_shortage");
  assert.equal(report.snapshotValid, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.invalidCommitCount, 0);
});
