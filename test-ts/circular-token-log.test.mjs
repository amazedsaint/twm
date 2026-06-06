import assert from "node:assert/strict";
import test from "node:test";

import {
  BlockToken,
  CircularTokenLog,
  DeltaToken,
  auditCircularTokenLog,
  buildCircularTokenLogCertificate,
  compactTokenPrefix,
  demoCircularLogState,
  demoCircularLogTokens,
  replayCircularTokenLog,
  runCircularTokenLogBenchmark,
  stableHash,
  validateCircularTokenLogCertificate,
  randomizedCircularTokenLogTrials,
} from "../dist/index.js";

test("compact token prefix collapses overwritten keys", () => {
  const compacted = compactTokenPrefix(demoCircularLogState(), demoCircularLogTokens().slice(0, 5));

  assert.deepEqual(compacted.map((token) => token.key), ["b", "c"]);
  assert.deepEqual(compacted.map((token) => [token.before, token.after]), [[0, 2], [0, 4]]);
});

test("circular log keeps bounded suffix", () => {
  const log = CircularTokenLog.fromTokens(demoCircularLogState(), demoCircularLogTokens(), 3);

  assert.equal(log.totalTokenCount, 8);
  assert.equal(log.compactedPrefixCount, 5);
  assert.equal(log.suffixTokens.length, 3);
  assert.deepEqual(log.compactedTokens.map((token) => token.key), ["b", "c"]);
  assert.deepEqual(log.replay(), { a: 7, b: 5, c: 4, d: 6 });
});

test("circular log certificate audits and detects tampering", async () => {
  const state = demoCircularLogState();
  const tokens = demoCircularLogTokens();
  const certificate = await buildCircularTokenLogCertificate(state, tokens, { capacity: 3 });
  const tampered = { ...certificate, finalStateHash: await stableHash({ tampered: true }), certificateHash: "" };
  tampered.certificateHash = await stableHash({
    schemaVersion: tampered.schemaVersion,
    capacity: tampered.capacity,
    totalTokenCount: tampered.totalTokenCount,
    compactedPrefixCount: tampered.compactedPrefixCount,
    suffixCount: tampered.suffixCount,
    compactedDeltaCount: tampered.compactedDeltaCount,
    compactedTokens: tampered.compactedTokens,
    suffixTokens: tampered.suffixTokens,
    baseStateHash: tampered.baseStateHash,
    compactedStateHash: tampered.compactedStateHash,
    finalStateHash: tampered.finalStateHash,
    compactedTokenHash: tampered.compactedTokenHash,
    suffixTokenHash: tampered.suffixTokenHash,
  });
  const wrongOriginal = [...tokens.slice(0, -1), new DeltaToken("a", 0, 8)];

  assert.equal(await validateCircularTokenLogCertificate(certificate), true);
  assert.equal(await auditCircularTokenLog(state, certificate, tokens), true);
  assert.equal(await validateCircularTokenLogCertificate(tampered), true);
  assert.equal(await auditCircularTokenLog(state, tampered, tokens), false);
  assert.equal(await auditCircularTokenLog(state, certificate, wrongOriginal), false);
});

test("circular log replay matches full replay and inverse", async () => {
  const state = demoCircularLogState();
  const tokens = demoCircularLogTokens();
  const certificate = await buildCircularTokenLogCertificate(state, tokens, { capacity: 3 });
  const compacted = replayCircularTokenLog(state, certificate.compactedTokens, certificate.suffixTokens);
  const full = BlockToken.of(tokens).apply(state);
  let restored = BlockToken.of(certificate.suffixTokens).inverse().apply(compacted);
  restored = BlockToken.of(certificate.compactedTokens).inverse().apply(restored);

  assert.deepEqual(compacted, full);
  assert.deepEqual(restored, state);
});

test("randomized circular log trials have no mismatches", async () => {
  const result = await randomizedCircularTokenLogTrials({ seed: 5, trials: 48, keyCount: 4, tokenCount: 12, capacity: 3 });

  assert.equal(result.trials, 48);
  assert.equal(result.mismatches, 0);
});

test("circular token log benchmark reports exact gate metrics", async () => {
  const report = await runCircularTokenLogBenchmark();

  assert.equal(report.schemaVersion, "trwm.circular_token_log_certificate.v1");
  assert.equal(report.capacity, 3);
  assert.equal(report.totalTokenCount, 8);
  assert.equal(report.compactedPrefixCount, 5);
  assert.equal(report.suffixCount, 3);
  assert.equal(report.compactedDeltaCount, 2);
  assert.equal(report.retainedReplayTokenCount, 5);
  assert.equal(report.replayTokensSaved, 3);
  assert.deepEqual(report.compactedTokenSummary, ["b:0->2", "c:0->4"]);
  assert.deepEqual(report.suffixTokenSummary, ["b:2->5", "d:0->6", "a:0->7"]);
  assert.deepEqual(report.fullState, { a: 7, b: 5, c: 4, d: 6 });
  assert.deepEqual(report.compactedState, report.fullState);
  assert.equal(report.fullEqualsCompacted, true);
  assert.equal(report.inverseRoundtrip, true);
  assert.equal(report.certificateValid, true);
  assert.equal(report.auditValid, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.randomizedTrialCount, 64);
  assert.equal(report.randomizedMismatchCount, 0);
  assert.equal(report.invalidCommitCount, 0);
});
