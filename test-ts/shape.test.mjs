import assert from "node:assert/strict";
import test from "node:test";

import { runShapeConditionality } from "../dist/index.js";

test("shape conditionality report uses receipt and HDC memory under audited ledgers", async () => {
  const report = await runShapeConditionality(11, 96, 24);

  assert.equal(report.ledgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.ok(report.lowReceiptMemoryCallsPerSuccess < report.lowRandomCallsPerSuccess);
  assert.ok(report.lowHdcMemoryCallsPerSuccess < report.lowRandomCallsPerSuccess);
  assert.ok(report.lowReceiptGain > report.highReceiptGain);
  assert.ok(report.lowHdcGain > report.highHdcGain);
  assert.ok(report.lowPreflightR90 < report.highPreflightR90);
  assert.equal(report.lowPreflightFitsBudget, true);
  assert.equal(report.highPreflightFitsBudget, false);
  assert.ok(report.lowPreflightEnergyAtBudget > report.highPreflightEnergyAtBudget);
});
