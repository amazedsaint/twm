import assert from "node:assert/strict";
import test from "node:test";

import {
  CHECKPOINT_COMPACTION_END_INDEX,
  CHECKPOINT_SCHEMA,
  GENESIS_HEAD,
  InventoryReservationAdapter,
  TransactionEngine,
  auditCompactedView,
  buildCheckpoint,
  captureState,
  makeReservationCandidate,
  makeTrace,
  replayFromCheckpoint,
  runCheckpointCompactionBenchmark,
  validateCheckpoint,
} from "../dist/index.js";

test("checkpoint replays suffix to same final head and state", async () => {
  const [seedState, finalState, engine] = await makeLedger();
  const adapter = new InventoryReservationAdapter();
  const checkpoint = await buildCheckpoint(engine.ledger, adapter, seedState, { endIndex: CHECKPOINT_COMPACTION_END_INDEX });
  const suffix = engine.ledger.rows.slice(CHECKPOINT_COMPACTION_END_INDEX);
  const replay = await replayFromCheckpoint(checkpoint, suffix, adapter, { expectedFinalHead: engine.ledger.head });

  assert.equal(checkpoint.schemaVersion, CHECKPOINT_SCHEMA);
  assert.equal(await validateCheckpoint(checkpoint), true);
  assert.equal(replay.head, engine.ledger.head);
  assert.equal((await captureState(replay.state)).stateHash, (await captureState(finalState)).stateHash);
  assert.equal(replay.suffixCommittedCount, 2);
  assert.equal(await auditCompactedView(checkpoint, suffix, adapter, { expectedFinalHead: engine.ledger.head }), true);
});

test("checkpoint detects state tamper and stale suffix parent", async () => {
  const [seedState, _finalState, engine] = await makeLedger();
  const adapter = new InventoryReservationAdapter();
  const checkpoint = await buildCheckpoint(engine.ledger, adapter, seedState, { endIndex: CHECKPOINT_COMPACTION_END_INDEX });
  const suffix = engine.ledger.rows.slice(CHECKPOINT_COMPACTION_END_INDEX);
  const tampered = { ...checkpoint, checkpointState: { stock: { widget: 99 }, reserved: {}, committedOrders: [] } };
  const staleSuffix = [{ ...suffix[0], parentHead: GENESIS_HEAD }, ...suffix.slice(1)];

  assert.equal(await validateCheckpoint(tampered), false);
  assert.equal(await auditCompactedView(checkpoint, staleSuffix, adapter, { expectedFinalHead: engine.ledger.head }), false);
});

test("checkpoint requires an audited source ledger", async () => {
  const [seedState, _finalState, engine] = await makeLedger();
  engine.ledger.rows[0] = { ...engine.ledger.rows[0], commitDecision: "hard_reject" };

  await assert.rejects(
    () => buildCheckpoint(engine.ledger, new InventoryReservationAdapter(), seedState, { endIndex: CHECKPOINT_COMPACTION_END_INDEX }),
    /ledger audit/,
  );
});

test("checkpoint compaction benchmark proves replay savings without head drift", async () => {
  const report = await runCheckpointCompactionBenchmark();

  assert.equal(report.schemaVersion, CHECKPOINT_SCHEMA);
  assert.equal(report.receiptCount, 6);
  assert.equal(report.committedCount, 4);
  assert.equal(report.checkpointReceiptCount, 3);
  assert.equal(report.checkpointCommittedCount, 2);
  assert.equal(report.suffixReceiptCount, 3);
  assert.equal(report.fullReplayCommits, 4);
  assert.equal(report.checkpointReplayCommits, 2);
  assert.equal(report.replayCallsSaved, 2);
  assert.equal(report.finalStateHashEqual, true);
  assert.equal(report.finalHeadEqual, true);
  assert.equal(report.checkpointValid, true);
  assert.equal(report.compactedAudit, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.staleSuffixRejected, true);
  assert.equal(report.originalLedgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);
});

async function makeLedger() {
  const seedState = { stock: { widget: 10 }, reserved: { widget: 0 }, committedOrders: [] };
  let state = seedState;
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  const specs = [
    ["order-1", 2, 2],
    ["order-too-large", 12, 12],
    ["order-2", 3, 3],
    ["order-2", 1, 1],
    ["order-3", 1, 1],
    ["order-4", 2, 2],
  ];
  for (let idx = 0; idx < specs.length; idx += 1) {
    const [orderId, requested, quantity] = specs[idx];
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `checkpoint-test-${idx}`,
        actions: [{ orderId, quantity }],
        seeds: ["checkpoint-test", idx],
        modelVersion: "checkpoint.test.v1",
      }),
      await makeReservationCandidate(state, orderId, "widget", requested, quantity, "checkpoint-test"),
    );
    state = outcome.state;
  }
  return [seedState, state, engine];
}
