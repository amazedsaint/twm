import assert from "node:assert/strict";
import test from "node:test";

import {
  CnfResidualRepairer,
  CnfSatAdapter,
  Ledger,
  assignmentFromMask,
  formulaFromTarget,
  makeCnfCandidate,
  runResidualSatEpisode,
  runSatCspBenchmark,
  runStaticSatEpisode,
  unsatisfiedClauses,
} from "../dist/index.js";

test("CNF verifier returns unsatisfied-clause residual", async () => {
  const formula = formulaFromTarget([true, false, true]);
  const assignment = [false, false, false];
  const result = new CnfSatAdapter().verify(await makeCnfCandidate(formula, assignment));

  assert.equal(result.result, "reject");
  assert.deepEqual(unsatisfiedClauses(formula, assignment), [0, 2]);
  assert.equal(result.residual.kind, "unsatisfied_clause");
  assert.deepEqual(result.residual.repair, { variable: 1, value: true });
});

test("residual SAT episode repairs assignment before commit", async () => {
  const formula = formulaFromTarget([true, false, true]);
  const ledger = new Ledger();
  const result = await runResidualSatEpisode(
    formula,
    [false, false, false],
    ledger,
    new CnfResidualRepairer(),
    1,
  );

  assert.equal(result.calls, 3);
  assert.equal(result.success, true);
  assert.equal(await ledger.audit(), true);
  assert.equal(ledger.committedRows().length, 1);
});

test("SAT/CSP benchmark improves over exhaustive static order", async () => {
  const report = await runSatCspBenchmark(29, 32, 7);

  assert.equal(report.variableCount, 7);
  assert.equal(report.assignmentSpaceSize, 128);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.repairSuccessRate, 1);
  assert.ok(report.repairCallsPerSuccess < report.staticCallsPerSuccess);
  assert.ok(report.repairGain > 5);
  assert.equal(
    report.learnedResidualKinds.unsatisfied_clause,
    Math.round(report.repairCallsPerSuccess * report.episodes) - report.episodes,
  );
});

test("static SAT episode uses same-case assignment order", async () => {
  const formula = formulaFromTarget(assignmentFromMask(5, 3));
  const order = Array.from({ length: 8 }, (_unused, mask) => assignmentFromMask(mask, 3));
  const result = await runStaticSatEpisode(formula, order, new Ledger(), 2);

  assert.equal(result.calls, 6);
  assert.equal(result.success, true);
});
