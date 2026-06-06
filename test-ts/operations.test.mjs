import assert from "node:assert/strict";
import test from "node:test";

import {
  InventoryReservationAdapter,
  InventoryResidualRepairer,
  Ledger,
  applyInventoryReservation,
  makeReservationCandidate,
  runOperationsBenchmark,
  runRepairOperationsEpisode,
  runStaticOperationsEpisode,
} from "../dist/index.js";

test("inventory reservation preserves accounting units", () => {
  const state = { stock: { A: 8 }, reserved: { A: 2 }, committedOrders: [] };
  const next = applyInventoryReservation(state, "o1", "A", 3);

  assert.equal(next.stock.A, 5);
  assert.equal(next.reserved.A, 5);
  assert.equal(state.stock.A + state.reserved.A, next.stock.A + next.reserved.A);
  assert.deepEqual(next.committedOrders, ["o1"]);
});

test("hard verifier rejects stock shortage with repair", async () => {
  const state = { stock: { A: 5 }, reserved: { A: 0 }, committedOrders: [] };
  const candidate = await makeReservationCandidate(state, "o2", "A", 9, 9);
  const result = new InventoryReservationAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "stock_shortage");
  assert.deepEqual(result.residual.repair, { quantity: 5 });
});

test("residual repair commits after shortage feedback", async () => {
  const state = { stock: { A: 5 }, reserved: { A: 0 }, committedOrders: [] };
  const ledger = new Ledger();
  const result = await runRepairOperationsEpisode(state, "o3", "A", 9, ledger, new InventoryResidualRepairer(), 1);

  assert.equal(result.calls, 2);
  assert.equal(result.success, true);
  assert.equal(result.auditOk, true);
  assert.equal(result.replayRollbackOk, true);
  assert.equal(ledger.committedRows().length, 1);
});

test("operations benchmark improves over static quantity search", async () => {
  const report = await runOperationsBenchmark(37, 48);

  assert.equal(report.episodes, 48);
  assert.equal(report.repairSuccessRate, 1);
  assert.equal(report.ledgerAuditRate, 1);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.ok(report.repairCallsPerSuccess < report.staticCallsPerSuccess);
  assert.ok(report.repairGain > 2);
  assert.ok(report.learnedResidualKinds.stock_shortage > 0);
});

test("static operations episode uses same quantity candidates", async () => {
  const state = { stock: { A: 3 }, reserved: { A: 0 }, committedOrders: [] };
  const result = await runStaticOperationsEpisode(state, "o4", "A", 5, new Ledger(), 4);

  assert.equal(result.calls, 3);
  assert.equal(result.success, true);
});
