import assert from "node:assert/strict";
import test from "node:test";

import {
  BooleanCircuitAdapter,
  CircuitResidualRepairer,
  Ledger,
  TransactionEngine,
  evalOpMask,
  makeCircuitCandidate,
  makeCircuitRepairProblem,
  makeTrace,
  runCircuitRepairBenchmark,
  runRepairCircuitEpisode,
  runStaticCircuitEpisode,
} from "../dist/index.js";

test("Boolean op masks match common functions", () => {
  assert.equal(evalOpMask(6, 0, 0), 0);
  assert.equal(evalOpMask(6, 0, 1), 1);
  assert.equal(evalOpMask(6, 1, 0), 1);
  assert.equal(evalOpMask(6, 1, 1), 0);
  assert.equal(evalOpMask(8, 1, 1), 1);
  assert.equal(evalOpMask(14, 0, 1), 1);
});

test("circuit verifier rejects mismatch with unique gate repair", async () => {
  const problem = makeCircuitRepairProblem(6);
  const candidate = await makeCircuitCandidate(problem, 0);
  const result = new BooleanCircuitAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "truth_table_mismatch");
  assert.deepEqual(result.residual.repair, { gateId: "g1", opMask: 6, opName: "XOR" });
});

test("residual circuit repair commits after truth-table feedback", async () => {
  const problem = makeCircuitRepairProblem(14);
  const ledger = new Ledger();
  const result = await runRepairCircuitEpisode(problem, ledger, new CircuitResidualRepairer(), 1);

  assert.equal(result.calls, 2);
  assert.equal(result.success, true);
  assert.equal(result.auditOk, true);
  assert.equal(result.replayRollbackOk, true);
  assert.equal(ledger.committedRows().length, 1);
  assert.equal(ledger.committedRows()[0].replayBundle.candidatePayload.opMask, 14);
});

test("circuit repair benchmark improves over static op search", async () => {
  const report = await runCircuitRepairBenchmark(47, 45);

  assert.equal(report.episodes, 45);
  assert.equal(report.opCount, 16);
  assert.equal(report.repairSuccessRate, 1);
  assert.equal(report.ledgerAuditRate, 1);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.ok(report.repairCallsPerSuccess < report.staticCallsPerSuccess);
  assert.ok(report.repairGain > 4);
  assert.equal(report.learnedResidualKinds.truth_table_mismatch, 45);
});

test("static circuit episode uses same gate candidates", async () => {
  const problem = makeCircuitRepairProblem(3);
  const result = await runStaticCircuitEpisode(problem, [0, 1, 2, 3], new Ledger(), 4);

  assert.equal(result.calls, 4);
  assert.equal(result.success, true);
});

test("valid netlist for wrong problem fails closed", async () => {
  const problemA = makeCircuitRepairProblem(6);
  const problemB = makeCircuitRepairProblem(14);
  const candidate = await makeCircuitCandidate(problemA, 6);
  const engine = new TransactionEngine(new BooleanCircuitAdapter(), new Ledger());
  const outcome = await engine.transact(
    { problem: problemB, solved: false, netlist: null },
    makeTrace({
      branchId: "wrong-circuit-problem",
      actions: [{ gateId: "g1", opMask: 6 }],
      seeds: ["circuit", "wrong-problem"],
      modelVersion: "circuit.test.v1",
    }),
    candidate,
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason.startsWith("replay_or_rollback_error:"), true);
  assert.equal(engine.invalidCommitCount, 0);
});
