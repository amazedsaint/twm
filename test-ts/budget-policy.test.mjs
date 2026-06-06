import assert from "node:assert/strict";
import test from "node:test";

import {
  BUDGET_POLICY_LIMIT,
  InventoryReservationAdapter,
  ReceiptBudgetPolicy,
  TransactionEngine,
  makeReservationCandidate,
  makeTrace,
  runBudgetPolicyBenchmark,
  validateBudgetPolicySnapshot,
} from "../dist/index.js";

test("budget policy selects receipt-grounded repair under budget", async () => {
  const state = seedState();
  const policy = await trainedPolicy(state);
  const plan = policy.plan(await candidates(state), BUDGET_POLICY_LIMIT);

  assert.deepEqual(plan.selected.map((row) => row.label), ["quantity-5"]);
  assert.equal(plan.spent, 3);
  assert.equal(plan.expectedUtility, 1.03271645737);
  assert.equal(policy.score("quantity-5").successLowerBound, 0.206543291474);
});

test("budget policy fails closed when only zero-utility candidates fit", async () => {
  const state = seedState();
  const policy = await trainedPolicy(state);
  const plan = policy.plan(await candidates(state), 2);

  assert.deepEqual(plan.selected, []);
  assert.equal(plan.spent, 0);
  assert.equal(plan.expectedUtility, 0);
});

test("budget policy submitter commits only after hard verification", async () => {
  const state = seedState();
  const policy = await trainedPolicy(state);
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  const outcome = await policy.submit(
    engine,
    state,
    await candidates(state),
    { budget: BUDGET_POLICY_LIMIT, tracePrefix: "budget" },
  );

  assert.equal(outcome.committed, true);
  assert.equal(outcome.committedLabel, "quantity-5");
  assert.deepEqual(outcome.selectedLabels, ["quantity-5"]);
  assert.deepEqual(outcome.submittedLabels, ["quantity-5"]);
  assert.equal(outcome.verifierCostSpent, 3);
  assert.equal(outcome.receipts.length, 1);
  assert.equal(outcome.state.stock.widget, 0);
  assert.equal(await engine.ledger.audit(), true);
  assert.deepEqual(await engine.rollbackAudit(state), state);
});

test("budget policy snapshot validation detects tampering", async () => {
  const policy = await trainedPolicy(seedState());
  const snapshot = await policy.snapshot();
  const tampered = { ...snapshot, rows: snapshot.rows.map((row) => ({ ...row, failures: 0 })) };

  assert.equal(await validateBudgetPolicySnapshot(snapshot), true);
  assert.equal(await validateBudgetPolicySnapshot(tampered), false);
});

test("invalid budget policy inputs fail closed", async () => {
  const policy = new ReceiptBudgetPolicy();

  assert.throws(() => policy.plan([], -1), /budget/);
  assert.throws(
    () => policy.plan([
      {
        label: "bad",
        token: "bad",
        candidate: {},
        verifierCost: 0,
        reward: 1,
        baseRank: 0,
      },
    ], 1),
    /verifierCost/,
  );
});

test("budget policy benchmark metrics", async () => {
  const report = await runBudgetPolicyBenchmark();

  assert.equal(report.trainingReceiptCount, 3);
  assert.equal(report.budget, BUDGET_POLICY_LIMIT);
  assert.equal(report.candidateCount, 4);
  assert.equal(report.learnedSuccessToken, "quantity-5");
  assert.equal(report.learnedSuccessLowerBound, 0.206543291474);
  assert.deepEqual(report.cheapFirstSelected, ["quantity-8", "quantity-7"]);
  assert.equal(report.cheapFirstCommitted, false);
  assert.equal(report.cheapFirstVerifierCalls, 2);
  assert.equal(report.cheapFirstCostSpent, 2);
  assert.deepEqual(report.learnedSelected, ["quantity-5"]);
  assert.equal(report.learnedCommitted, true);
  assert.equal(report.learnedCommittedLabel, "quantity-5");
  assert.equal(report.learnedVerifierCalls, 1);
  assert.equal(report.learnedCostSpent, 3);
  assert.equal(report.learnedExpectedUtility, 1.03271645737);
  assert.equal(report.verifierCallGain, 2);
  assert.equal(report.verifierCostRatio, 2 / 3);
  assert.equal(report.evaluationReceiptCount, 1);
  assert.equal(report.heldoutTraceDisjoint, true);
  assert.equal(report.snapshotValid, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
});

function seedState() {
  return { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
}

async function trainedPolicy(state) {
  const policy = new ReceiptBudgetPolicy();
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  for (const [label, quantity] of [["quantity-5", 5], ["quantity-8", 8], ["quantity-7", 7]]) {
    const receipt = (await engine.transact(
      state,
      makeTrace({ branchId: `train-${label}`, actions: [{ label }] }),
      await makeReservationCandidate(state, label, "widget", 8, quantity),
    )).receipt;
    policy.update(label, receipt);
  }
  return policy;
}

async function candidates(state) {
  const costs = new Map([[8, 1], [7, 1], [5, 3], [4, 2]]);
  const rows = [];
  for (const [baseRank, quantity] of [8, 7, 5, 4].entries()) {
    const cost = costs.get(quantity);
    rows.push({
      label: `quantity-${quantity}`,
      token: `quantity-${quantity}`,
      candidate: await makeReservationCandidate(state, `q${quantity}`, "widget", 8, quantity, "budget-policy-test", cost),
      verifierCost: cost,
      reward: quantity,
      baseRank,
    });
  }
  return rows;
}
