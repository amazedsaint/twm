import assert from "node:assert/strict";
import test from "node:test";

import {
  DeltaToken,
  auditParallelReplay,
  buildParallelReplayCertificate,
  parallelBatches,
  parallelReplay,
  randomizedParallelReplayTrials,
  runParallelReplayBenchmark,
  stableHash,
  tokenConflicts,
  validateParallelReplayCertificate,
} from "../dist/index.js";

const demoState = () => ({ a: 0, b: 0, c: 0, d: 0 });
const demoTokens = () => [
  new DeltaToken("a", 0, 1),
  new DeltaToken("b", 0, 2),
  new DeltaToken("a", 1, 3),
  new DeltaToken("c", 0, 4),
  new DeltaToken("b", 2, 5),
  new DeltaToken("d", 0, 6),
];

test("token conflicts use Bernstein read/write conditions", () => {
  const x0 = new DeltaToken("x", 0, 1);
  const y0 = new DeltaToken("y", 0, 1);
  const x1 = new DeltaToken("x", 1, 2);

  assert.equal(tokenConflicts(x0, y0), false);
  assert.equal(tokenConflicts(x0, x1), true);
});

test("parallel batches preserve conflict order", () => {
  assert.deepEqual(parallelBatches(demoTokens()), [[0, 1, 3, 5], [2, 4]]);
});

test("parallel replay certificate audits and detects tampering", async () => {
  const state = demoState();
  const tokens = demoTokens();
  const certificate = await buildParallelReplayCertificate(state, tokens);
  const tampered = { ...certificate, parallelStateHash: await stableHash({ tampered: true }) };
  const wrongConflictCount = {
    ...certificate,
    conflictCount: certificate.conflictCount + 1,
    certificateHash: "",
  };
  wrongConflictCount.certificateHash = await stableHash({
    schemaVersion: wrongConflictCount.schemaVersion,
    tokenCount: wrongConflictCount.tokenCount,
    batchCount: wrongConflictCount.batchCount,
    conflictCount: wrongConflictCount.conflictCount,
    maxBatchWidth: wrongConflictCount.maxBatchWidth,
    batches: wrongConflictCount.batches,
    sequentialStateHash: wrongConflictCount.sequentialStateHash,
    parallelStateHash: wrongConflictCount.parallelStateHash,
  });

  assert.equal(await validateParallelReplayCertificate(certificate), true);
  assert.equal(await auditParallelReplay(state, tokens, certificate), true);
  assert.equal(await validateParallelReplayCertificate(tampered), false);
  assert.equal(await auditParallelReplay(state, tokens, tampered), false);
  assert.equal(await validateParallelReplayCertificate(wrongConflictCount), true);
  assert.equal(await auditParallelReplay(state, tokens, wrongConflictCount), false);
});

test("parallel replay rejects conflicting batch", () => {
  assert.throws(() => parallelReplay(demoState(), demoTokens(), [[0, 2]]), /conflicting tokens/);
});

test("randomized parallel replay trials have no mismatches", async () => {
  const result = await randomizedParallelReplayTrials({ seed: 7, trials: 48, keyCount: 4, tokenCount: 10 });

  assert.equal(result.trials, 48);
  assert.equal(result.mismatches, 0);
});

test("parallel replay benchmark reports exact gate metrics", async () => {
  const report = await runParallelReplayBenchmark();

  assert.equal(report.schemaVersion, "trwm.parallel_replay_certificate.v1");
  assert.equal(report.tokenCount, 6);
  assert.equal(report.batchCount, 2);
  assert.equal(report.maxBatchWidth, 4);
  assert.equal(report.conflictCount, 2);
  assert.deepEqual(report.batches, [[0, 1, 3, 5], [2, 4]]);
  assert.deepEqual(report.sequentialState, { a: 3, b: 5, c: 4, d: 6 });
  assert.deepEqual(report.parallelState, report.sequentialState);
  assert.equal(report.parallelEqualsSequential, true);
  assert.equal(report.inverseRoundtrip, true);
  assert.equal(report.certificateValid, true);
  assert.equal(report.auditValid, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.randomizedTrialCount, 64);
  assert.equal(report.randomizedMismatchCount, 0);
  assert.equal(report.invalidCommitCount, 0);
});
