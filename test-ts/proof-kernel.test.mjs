import assert from "node:assert/strict";
import test from "node:test";

import {
  HornProofAdapter,
  Ledger,
  ProofResidualRepairer,
  TransactionEngine,
  chainProofProblem,
  makeProofCandidate,
  makeTrace,
  runProofKernelBenchmark,
  runRepairProofEpisode,
  runStaticProofEpisode,
} from "../dist/index.js";

test("proof verifier rejects missing premise with repair hint", async () => {
  const { problem } = chainProofProblem(3);
  const candidate = await makeProofCandidate(problem, ["r2"]);
  const result = new HornProofAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "missing_premise");
  assert.deepEqual(result.residual.missing, ["p1"]);
  assert.deepEqual(result.residual.repair, { ruleId: "r1", conclusion: "p1" });
});

test("residual repair builds proof script before commit", async () => {
  const { problem, correctScript } = chainProofProblem(3);
  const ledger = new Ledger();
  const result = await runRepairProofEpisode(problem, ledger, new ProofResidualRepairer(), 1);

  assert.equal(result.calls, correctScript.length + 1);
  assert.equal(result.success, true);
  assert.equal(result.auditOk, true);
  assert.equal(result.replayRollbackOk, true);
  assert.equal(ledger.committedRows().length, 1);
  assert.deepEqual(ledger.committedRows()[0].replayBundle.candidatePayload.script, correctScript);
});

test("proof kernel benchmark improves over static permutations", async () => {
  const report = await runProofKernelBenchmark(41, 12, 6);

  assert.equal(report.episodes, 12);
  assert.equal(report.ruleCount, 6);
  assert.equal(report.repairSuccessRate, 1);
  assert.equal(report.ledgerAuditRate, 1);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.ok(report.repairCallsPerSuccess < report.staticCallsPerSuccess);
  assert.ok(report.repairGain > 2);
  assert.equal(report.learnedResidualKinds.goal_not_derived, 72);
});

test("static proof episode uses same script candidates", async () => {
  const { problem, correctScript } = chainProofProblem(3);
  const result = await runStaticProofEpisode(problem, [["r3", "r2", "r1"], correctScript], new Ledger(), 4);

  assert.equal(result.calls, 2);
  assert.equal(result.success, true);
});

test("valid proof script for wrong problem fails closed", async () => {
  const { problem: problemA, correctScript } = chainProofProblem(1, "a");
  const { problem: problemB } = chainProofProblem(1, "b");
  const candidate = await makeProofCandidate(problemA, correctScript);
  const engine = new TransactionEngine(new HornProofAdapter(), new Ledger());
  const outcome = await engine.transact(
    { problem: problemB, proven: false, derived: [], proof: [] },
    makeTrace({
      branchId: "wrong-proof-problem",
      actions: [{ script: correctScript }],
      seeds: ["proof", "wrong-problem"],
      modelVersion: "proof.test.v1",
    }),
    candidate,
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason.startsWith("replay_or_rollback_error:"), true);
  assert.equal(engine.invalidCommitCount, 0);
});
