import assert from "node:assert/strict";
import test from "node:test";

import {
  Ledger,
  MoleculeGraphAdapter,
  MoleculeResidualRepairer,
  TransactionEngine,
  makeMoleculeCandidate,
  makeMoleculeRepairProblem,
  makeTrace,
  molecularFormula,
  replaceMoleculeEdit,
  runMoleculeRepairBenchmark,
  runRepairMoleculeEpisode,
  runStaticMoleculeEpisode,
} from "../dist/index.js";

test("molecule formula uses organic-subset valence hydrogens", () => {
  const problem = makeMoleculeRepairProblem("O", 1);
  const graph = replaceMoleculeEdit(problem.templateGraph, "a2", "O", "b1", 1);

  assert.deepEqual(molecularFormula(graph), { C: 2, H: 6, O: 1 });
});

test("molecule verifier rejects formula mismatch with unique edit repair", async () => {
  const problem = makeMoleculeRepairProblem("O", 1);
  const candidate = await makeMoleculeCandidate(problem, "C", 3);
  const result = new MoleculeGraphAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "formula_mismatch");
  assert.deepEqual(result.residual.repair, {
    atomId: "a2",
    bondId: "b1",
    element: "O",
    bondOrder: 1,
    formula: { C: 2, H: 6, O: 1 },
  });
});

test("molecule verifier rejects valence excess before formula check", async () => {
  const problem = makeMoleculeRepairProblem("O", 1);
  const candidate = await makeMoleculeCandidate(problem, "F", 2);
  const result = new MoleculeGraphAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "valence_exceeded");
  assert.equal(result.residual.violations[0].element, "F");
  assert.equal(result.residual.repair.element, "O");
});

test("residual molecule repair commits after formula feedback", async () => {
  const problem = makeMoleculeRepairProblem("N", 2);
  const ledger = new Ledger();
  const result = await runRepairMoleculeEpisode(problem, ledger, new MoleculeResidualRepairer(), 1);

  assert.equal(result.calls, 2);
  assert.equal(result.success, true);
  assert.equal(result.auditOk, true);
  assert.equal(result.replayRollbackOk, true);
  assert.equal(ledger.committedRows().length, 1);
  assert.equal(ledger.committedRows()[0].replayBundle.candidatePayload.element, "N");
  assert.equal(ledger.committedRows()[0].replayBundle.candidatePayload.bondOrder, 2);
});

test("molecule repair benchmark improves over static edit search", async () => {
  const report = await runMoleculeRepairBenchmark(53, 36);

  assert.equal(report.episodes, 36);
  assert.equal(report.candidateSpaceSize, 15);
  assert.equal(report.repairSuccessRate, 1);
  assert.equal(report.ledgerAuditRate, 1);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.ok(report.repairCallsPerSuccess < report.staticCallsPerSuccess);
  assert.ok(report.repairGain > 2.5);
  assert.equal(report.learnedResidualKinds.formula_mismatch, 36);
});

test("static molecule episode uses same edit candidates", async () => {
  const problem = makeMoleculeRepairProblem("N", 1);
  const result = await runStaticMoleculeEpisode(problem, [["C", 1], ["C", 2], ["N", 1]], new Ledger(), 4);

  assert.equal(result.calls, 3);
  assert.equal(result.success, true);
});

test("valid molecule graph for wrong problem fails closed", async () => {
  const problemA = makeMoleculeRepairProblem("O", 1);
  const problemB = makeMoleculeRepairProblem("N", 2);
  const candidate = await makeMoleculeCandidate(problemA, "O", 1);
  const engine = new TransactionEngine(new MoleculeGraphAdapter(), new Ledger());
  const outcome = await engine.transact(
    { problem: problemB, solved: false, graph: null },
    makeTrace({
      branchId: "wrong-molecule-problem",
      actions: [{ element: "O", bondOrder: 1 }],
      seeds: ["molecule", "wrong-problem"],
      modelVersion: "molecule.test.v1",
    }),
    candidate,
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason.startsWith("replay_or_rollback_error:"), true);
  assert.equal(engine.invalidCommitCount, 0);
});
