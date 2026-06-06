import assert from "node:assert/strict";
import test from "node:test";

import {
  BudgetedBranchRuntime,
  CHEAP_BUDGET_DECOY,
  CHEAP_BUDGET_SOLUTION,
  CostAwareReceiptDomainRouter,
  EXPENSIVE_BUDGET_SOLUTION,
  TransactionEngine,
  VerifierBudget,
  VerifierBudgetAdapter,
  VerifierBudgetProjector,
  candidateVerifierCost,
  makeCandidate,
  makeVerifierBudgetTraces,
  normalizeVerifierBudgetPayload,
  runVerifierBudgetBenchmark,
} from "../dist/index.js";

test("budgeted branch runtime abstains before an expensive verifier call", async () => {
  const engine = new TransactionEngine(new VerifierBudgetAdapter());
  const outcome = await new BudgetedBranchRuntime(
    engine,
    new VerifierBudgetProjector(),
    new VerifierBudget(4),
  ).step({ committedActions: [] }, makeVerifierBudgetTraces());

  assert.equal(outcome.committed, true);
  assert.deepEqual(outcome.state.committedActions, [CHEAP_BUDGET_SOLUTION]);
  assert.equal(outcome.verifierCalls, 2);
  assert.equal(outcome.verifierCost, 4);
  assert.equal(outcome.abstainedCount, 1);
  assert.equal(engine.hardVerifierCalls, 2);
  assert.deepEqual(outcome.receipts.map((receipt) => receipt.commitDecision), ["hard_abstain", "hard_reject", "commit"]);
  assert.equal(outcome.receipts[0].hardResult.result, "abstain");
  assert.equal(outcome.receipts[0].hardResult.residual.kind, "verifier_budget_exhausted");
  assert.equal(outcome.receipts[0].hardResult.residual.requiredVerifierCost, 7);
  assert.equal(outcome.receipts[0].hardResult.residual.remainingBudget, 4);
  assert.equal(await engine.ledger.audit(), true);
  assert.deepEqual(await engine.replayAudit({ committedActions: [] }), { committedActions: [CHEAP_BUDGET_SOLUTION] });
  assert.deepEqual(await engine.rollbackAudit({ committedActions: [] }), { committedActions: [] });
});

test("candidate verifier cost accepts integer strings and rejects invalid values", () => {
  assert.equal(candidateVerifierCost(makeCandidate({ verifierCost: "3" }, "x", "x.v1")), 3);
  assert.throws(() => candidateVerifierCost(makeCandidate({ verifierCost: 0 }, "x", "x.v1")), /positive integer/);
  assert.throws(() => candidateVerifierCost(makeCandidate({ verifierCost: true }, "x", "x.v1")), /positive integer/);
});

test("verifier budget payload requires boolean acceptance flag", () => {
  assert.throws(
    () => normalizeVerifierBudgetPayload({ action: "x", planCost: 1, verifierCost: 1, accepted: "false" }),
    /boolean/,
  );
});

test("budget abstain receipt is free for the cost-aware router", async () => {
  const engine = new TransactionEngine(new VerifierBudgetAdapter());
  const outcome = await new BudgetedBranchRuntime(
    engine,
    new VerifierBudgetProjector(),
    new VerifierBudget(4),
  ).step({ committedActions: [] }, makeVerifierBudgetTraces());
  const router = new CostAwareReceiptDomainRouter(5);
  for (const receipt of outcome.receipts) {
    router.update("budgeted_branch", "ctx", receipt);
  }

  const stats = router.stats("ctx", "budgeted_branch");
  assert.equal(stats.verifierCost, 4);
  assert.equal(stats.accepted, 1);
  assert.equal(stats.rejected, 1);
  assert.equal(stats.abstained, 1);
});

test("verifier budget benchmark metrics", async () => {
  const report = await runVerifierBudgetBenchmark();

  assert.equal(report.candidateCount, 3);
  assert.equal(report.budget, 4);
  assert.equal(report.unbudgetedVerifierCalls, 3);
  assert.equal(report.unbudgetedCommittedAction, EXPENSIVE_BUDGET_SOLUTION);
  assert.equal(report.verifierCalls, 2);
  assert.equal(report.verifierCost, 4);
  assert.equal(report.abstainedCount, 1);
  assert.equal(report.committedAction, CHEAP_BUDGET_SOLUTION);
  assert.equal(report.skippedAction, EXPENSIVE_BUDGET_SOLUTION);
  assert.equal(report.verifiedRejectedAction, CHEAP_BUDGET_DECOY);
  assert.equal(report.budgetResidualKind, "verifier_budget_exhausted");
  assert.equal(report.expensiveRequiredCost, 7);
  assert.equal(report.remainingBudgetBeforeExpensive, 4);
  assert.deepEqual(report.receiptDecisions, ["hard_abstain", "hard_reject", "commit"]);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
});
