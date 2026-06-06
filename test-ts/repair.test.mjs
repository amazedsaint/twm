import assert from "node:assert/strict";
import test from "node:test";

import {
  Ledger,
  ResidualProgramRepairer,
  evaluateProgram,
  runRepairEpisode,
  runResidualRepairBenchmark,
  runStaticRepairEpisode,
} from "../dist/index.js";

test("program evaluator uses exact integer steps", () => {
  assert.equal(evaluateProgram([{ op: "set", value: 4 }, { op: "add", value: -9 }]), -5);
});

test("residual repair improves calls per verified program", async () => {
  const report = await runResidualRepairBenchmark(17, 64, -12, 12);

  assert.equal(report.ledgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.repairSuccessRate, 1);
  assert.ok(report.repairCallsPerSuccess < report.staticCallsPerSuccess);
  assert.ok(report.repairGain > 2);
  assert.equal(report.learnedRepairKinds.scalar_delta, 64);
});

test("repair episode commits after hard-verifier residual patch", async () => {
  const staticLedger = new Ledger();
  const repairLedger = new Ledger();
  const staticResult = await runStaticRepairEpisode(7, [0, 1, 2, 7], staticLedger, 1);
  const repairResult = await runRepairEpisode(7, 0, repairLedger, new ResidualProgramRepairer(), 1);

  assert.equal(staticResult.calls, 4);
  assert.equal(repairResult.calls, 2);
  assert.equal(await staticLedger.audit(), true);
  assert.equal(await repairLedger.audit(), true);
});
