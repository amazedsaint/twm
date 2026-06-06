import assert from "node:assert/strict";
import test from "node:test";

import {
  CodePatchAdapter,
  CodeResidualRepairer,
  Ledger,
  TransactionEngine,
  evaluateOperator,
  makeCodePatchCandidate,
  makeCodeRepairProblem,
  makeTrace,
  runCodeRepairBenchmark,
  runRepairCodeEpisode,
  runStaticCodeRepairEpisode,
} from "../dist/index.js";

test("code patch operator semantics are exact integers", () => {
  assert.equal(evaluateOperator("+", 3, -2), 1);
  assert.equal(evaluateOperator("-", 3, -2), 5);
  assert.equal(evaluateOperator("*", 3, -2), -6);
  assert.equal(evaluateOperator("max", 3, -2), 3);
  assert.equal(evaluateOperator("min", 3, -2), -2);
  assert.equal(evaluateOperator("left", 3, -2), 3);
  assert.equal(evaluateOperator("right", 3, -2), -2);
  assert.equal(evaluateOperator("absdiff", 3, -2), 5);
});

test("code verifier rejects failing test with unique operator repair", async () => {
  const problem = await makeCodeRepairProblem("+");
  const candidate = await makeCodePatchCandidate(problem, "left");
  const result = await new CodePatchAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "test_failure");
  assert.equal(result.residual.testIndex, 1);
  assert.equal(result.residual.expected, 3);
  assert.equal(result.residual.actual, 1);
  assert.equal(result.residual.repair.operator, "+");
  assert.equal(result.residual.repair.baseHash, problem.sourceHash);
});

test("code verifier rejects base hash mismatch", async () => {
  const problem = await makeCodeRepairProblem("+");
  const candidate = await makeCodePatchCandidate({ ...problem, sourceHash: "0".repeat(64) }, "+");
  const result = await new CodePatchAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "schema_error");
  assert.match(result.residual.message, /sourceHash/);
});

test("residual code repair commits after test feedback", async () => {
  const problem = await makeCodeRepairProblem("absdiff");
  const ledger = new Ledger();
  const result = await runRepairCodeEpisode(problem, ledger, new CodeResidualRepairer(), 1);

  assert.equal(result.calls, 2);
  assert.equal(result.success, true);
  assert.equal(result.auditOk, true);
  assert.equal(result.replayRollbackOk, true);
  assert.equal(ledger.committedRows().length, 1);
  assert.equal(ledger.committedRows()[0].replayBundle.candidatePayload.patch.operator, "absdiff");
});

test("code repair benchmark improves over static patch search", async () => {
  const report = await runCodeRepairBenchmark(59, 42);

  assert.equal(report.episodes, 42);
  assert.equal(report.candidateSpaceSize, 8);
  assert.equal(report.repairSuccessRate, 1);
  assert.equal(report.ledgerAuditRate, 1);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.staticCallsPerSuccess, 5);
  assert.equal(report.repairCallsPerSuccess, 2);
  assert.equal(report.repairGain, 2.5);
  assert.equal(report.learnedResidualKinds.test_failure, 42);
});

test("static code episode uses same patch candidates", async () => {
  const problem = await makeCodeRepairProblem("*");
  const result = await runStaticCodeRepairEpisode(problem, ["left", "+", "*"], new Ledger(), 4);

  assert.equal(result.calls, 3);
  assert.equal(result.success, true);
});

test("valid code patch for wrong problem fails closed", async () => {
  const problemA = await makeCodeRepairProblem("+");
  const problemB = await makeCodeRepairProblem("-");
  const candidate = await makeCodePatchCandidate(problemA, "+");
  const engine = new TransactionEngine(new CodePatchAdapter(), new Ledger());
  const outcome = await engine.transact(
    { problem: problemB, solved: false, operator: null, sourceAfter: null },
    makeTrace({
      branchId: "wrong-code-problem",
      actions: [{ nodeId: "op0", operator: "+" }],
      seeds: ["code", "wrong-problem"],
      modelVersion: "code.test.v1",
    }),
    candidate,
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason.startsWith("replay_or_rollback_error:"), true);
  assert.equal(engine.invalidCommitCount, 0);
});
