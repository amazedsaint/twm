import {
  CHECKPOINT_SCHEMA,
  auditCompactedView,
  buildCheckpoint,
  replayFromCheckpoint,
  validateCheckpoint,
} from "./checkpoint.js";
import { GENESIS_HEAD, TransactionEngine, captureState, makeTrace } from "./core.js";
import {
  InventoryReservationAdapter,
  makeReservationCandidate,


} from "./operations.js";

export const CHECKPOINT_COMPACTION_END_INDEX = 3;





















export async function runCheckpointCompactionBenchmark()                                      {
  const [seedState, finalState, engine] = await makeCheckpointLedger();
  const adapter = new InventoryReservationAdapter();
  const checkpoint = await buildCheckpoint(engine.ledger, adapter, seedState, { endIndex: CHECKPOINT_COMPACTION_END_INDEX });
  const suffix = engine.ledger.rows.slice(CHECKPOINT_COMPACTION_END_INDEX);
  const replay = await replayFromCheckpoint(checkpoint, suffix, adapter, { expectedFinalHead: engine.ledger.head });
  const fullState = await engine.replayAudit(seedState);
  const tampered = {
    ...checkpoint,
    checkpointState: { stock: { widget: 99 }, reserved: {}, committedOrders: [] },
  };
  const staleSuffix = [{ ...suffix[0], parentHead: GENESIS_HEAD }, ...suffix.slice(1)];
  const replayHash = (await captureState(replay.state)).stateHash;
  const fullHash = (await captureState(fullState)).stateHash;
  const finalHash = (await captureState(finalState)).stateHash;
  const fullReplayCommits = engine.ledger.committedRows().length;
  const checkpointReplayCommits = replay.suffixCommittedCount;
  return {
    schemaVersion: CHECKPOINT_SCHEMA,
    receiptCount: engine.ledger.rows.length,
    committedCount: fullReplayCommits,
    checkpointReceiptCount: checkpoint.receiptCount,
    checkpointCommittedCount: checkpoint.committedCount,
    suffixReceiptCount: replay.suffixReceiptCount,
    fullReplayCommits,
    checkpointReplayCommits,
    replayCallsSaved: fullReplayCommits - checkpointReplayCommits,
    finalStateHashEqual: replayHash === fullHash && replayHash === finalHash,
    finalHeadEqual: replay.head === engine.ledger.head,
    checkpointValid: await validateCheckpoint(checkpoint),
    compactedAudit: await auditCompactedView(checkpoint, suffix, adapter, { expectedFinalHead: engine.ledger.head }),
    tamperDetected: !await validateCheckpoint(tampered),
    staleSuffixRejected: !await auditCompactedView(checkpoint, staleSuffix, adapter, { expectedFinalHead: engine.ledger.head }),
    originalLedgerAudit: await engine.ledger.audit(),
    invalidCommitCount: engine.invalidCommitCount,
  };
}

async function makeCheckpointLedger()                                                                                                            {
  const seedState                 = { stock: { widget: 10 }, reserved: { widget: 0 }, committedOrders: [] };
  let state = seedState;
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  const specs                                  = [
    ["order-1", 2, 2],
    ["order-too-large", 12, 12],
    ["order-2", 3, 3],
    ["order-2", 1, 1],
    ["order-3", 1, 1],
    ["order-4", 2, 2],
  ];
  for (let idx = 0; idx < specs.length; idx += 1) {
    const [orderId, requested, quantity] = specs[idx];
    const candidate = await makeReservationCandidate(
      state,
      orderId,
      "widget",
      requested,
      quantity,
      "checkpoint-compaction",
    );
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `checkpoint-compaction-${idx}`,
        actions: [{ orderId, quantity }],
        seeds: ["checkpoint", idx],
        modelVersion: "checkpoint.compaction.v1",
      }),
      candidate,
    );
    state = outcome.state;
  }
  return [seedState, state, engine];
}
