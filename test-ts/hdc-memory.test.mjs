import assert from "node:assert/strict";
import test from "node:test";

import { runHdcMemoryBenchmark } from "../dist/index.js";

test("HDC memory beats no-memory and exact-match baselines under context shift", async () => {
  const report = await runHdcMemoryBenchmark(19, 96, 24);

  assert.equal(report.ledgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.noiseRetrievalOk, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.exactMatchCallsPerSuccess, report.noMemoryCallsPerSuccess);
  assert.ok(report.hdcCallsPerSuccess < report.noMemoryCallsPerSuccess);
  assert.ok(report.hdcCallsPerSuccess < report.exactMatchCallsPerSuccess);
  assert.ok(report.hdcGainOverExactMatch > 1.5);
});
