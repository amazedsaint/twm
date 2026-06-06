import assert from "node:assert/strict";
import test from "node:test";

import {
  BranchRuntime,
  COUNTERFACTUAL_CONTEXT,
  CounterfactualChoiceAdapter,
  CounterfactualChoiceProjector,
  CounterfactualRollbackRanker,
  Ledger,
  ReceiptRanker,
  TransactionEngine,
  makeCounterfactualTraces,
  runCounterfactualRollbackBenchmark,
} from "../dist/index.js";

test("branch receipts expose rolled-back loser evidence", async () => {
  const engine = new TransactionEngine(new CounterfactualChoiceAdapter(), new Ledger());
  const runtime = new BranchRuntime(engine, new CounterfactualChoiceProjector());
  const outcome = await runtime.step({ committedActions: [] }, makeCounterfactualTraces(0));

  assert.equal(outcome.committed, true);
  assert.deepEqual(outcome.state.committedActions, ["b_fast"]);
  assert.deepEqual(outcome.receipts.map((receipt) => receipt.commitDecision), ["rolled_back_loser", "commit", "hard_reject"]);
  assert.equal(await engine.ledger.audit(), true);
});

test("counterfactual ranker uses rollback evidence where receipt ranker ties", async () => {
  const engine = new TransactionEngine(new CounterfactualChoiceAdapter(), new Ledger());
  const runtime = new BranchRuntime(engine, new CounterfactualChoiceProjector());
  const outcome = await runtime.step({ committedActions: [] }, makeCounterfactualTraces(0));
  const receiptRanker = new ReceiptRanker();
  const counterfactualRanker = new CounterfactualRollbackRanker();
  for (const receipt of outcome.receipts) {
    receiptRanker.update(receipt);
    counterfactualRanker.update(receipt);
  }

  assert.equal(receiptRanker.rank(COUNTERFACTUAL_CONTEXT, ["a_slow", "b_fast", "c_unsafe"])[0], "a_slow");
  assert.equal(counterfactualRanker.rank(COUNTERFACTUAL_CONTEXT, ["a_slow", "b_fast", "c_unsafe"])[0], "b_fast");
  assert.equal(counterfactualRanker.stats(COUNTERFACTUAL_CONTEXT, "a_slow").rolledBack, 1);
});

test("counterfactual rollback benchmark metrics", async () => {
  const report = await runCounterfactualRollbackBenchmark(12);

  assert.equal(report.episodes, 12);
  assert.equal(report.candidateCount, 3);
  assert.equal(report.committedAction, "b_fast");
  assert.equal(report.staticTopAction, "a_slow");
  assert.equal(report.receiptRankerTopAction, "a_slow");
  assert.equal(report.counterfactualTopAction, "b_fast");
  assert.equal(report.receiptRankerWinnerRank, 2);
  assert.equal(report.counterfactualWinnerRank, 1);
  assert.equal(report.rolledBackLoserCount, 12);
  assert.equal(report.hardRejectCount, 12);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
});
