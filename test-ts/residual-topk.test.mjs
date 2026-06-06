import assert from "node:assert/strict";
import test from "node:test";

import {
  InventoryReservationAdapter,
  ResidualTaxonomyMemory,
  ResidualTopKSubmitter,
  TransactionEngine,
  makeReservationCandidate,
  makeTrace,
  residualSignalFromReceipt,
  runResidualTopKBenchmark,
} from "../dist/index.js";

test("rank options prefer residual hint", async () => {
  const state = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  const rejected = await engine.transact(
    state,
    makeTrace({ branchId: "reject" }),
    await makeReservationCandidate(state, "bad", "widget", 8, 8),
  );
  const signal = await residualSignalFromReceipt(rejected.receipt);
  const memory = new ResidualTaxonomyMemory();
  await memory.update(signal);
  const options = [
    await option(state, "quantity-8", 8, 0),
    await option(state, "quantity-7", 7, 1),
    await option(state, "quantity-5", 5, 2),
  ];

  const ranked = new ResidualTopKSubmitter(new TransactionEngine(new InventoryReservationAdapter()), memory)
    .rankOptions(options, signal);

  assert.equal(ranked[0].label, "quantity-5");
});

test("submitter commits only after hard verification", async () => {
  const state = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  const outcome = await new ResidualTopKSubmitter(engine).submit(
    state,
    [await option(state, "quantity-5", 5, 0)],
    { topK: 1, tracePrefix: "direct" },
  );

  assert.equal(outcome.committed, true);
  assert.equal(outcome.committedLabel, "quantity-5");
  assert.equal(outcome.state.stock.widget, 0);
  assert.equal(await engine.ledger.audit(), true);
  assert.deepEqual(await engine.rollbackAudit(state), state);
});

test("residual top-k benchmark metrics", async () => {
  const report = await runResidualTopKBenchmark();

  assert.equal(report.trainingResidualKind, "stock_shortage");
  assert.equal(report.learnedRepairHint, "quantity=5");
  assert.equal(report.candidateCount, 4);
  assert.equal(report.topK, 2);
  assert.deepEqual(report.unrankedSubmitted, ["quantity-8", "quantity-7"]);
  assert.equal(report.unrankedCommitted, false);
  assert.equal(report.unrankedVerifierCalls, 2);
  assert.deepEqual(report.residualRankedSubmitted, ["quantity-5"]);
  assert.equal(report.residualRankedCommitted, true);
  assert.equal(report.residualRankedCommittedLabel, "quantity-5");
  assert.equal(report.residualRankedVerifierCalls, 1);
  assert.equal(report.callsToCommitGain, 2);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
});

test("invalid topK fails closed", async () => {
  const state = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  await assert.rejects(
    () => new ResidualTopKSubmitter(new TransactionEngine(new InventoryReservationAdapter())).submit(
      state,
      [],
      { topK: -1, tracePrefix: "bad" },
    ),
    /topK/,
  );
});

async function option(state, label, quantity, baseRank) {
  return {
    label,
    candidate: await makeReservationCandidate(state, label, "widget", 8, quantity),
    repairHint: `quantity=${quantity}`,
    baseRank,
  };
}
