import assert from "node:assert/strict";
import test from "node:test";

import {
  Ledger,
  TransactionEngine,
  captureState,
  finalizeReceipt,
  RECEIPT_SCHEMA,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
  receiptStaticValid,
  stableHash,
  createRuntimeManifest,
} from "../dist/index.js";

class CounterAdapter {
  verifierId = "counter_limit";
  verifierVersion = "1.0";
  applyCommitCalls = 0;

  verify(candidate) {
    const delta = candidate.payload.delta;
    return delta <= 5
      ? hardAccept(this.verifierId, this.verifierVersion)
      : hardReject(this.verifierId, this.verifierVersion, { delta });
  }

  applyCommit(state, candidate) {
    this.applyCommitCalls += 1;
    return state + candidate.payload.delta;
  }

  replay(state, receipt) {
    return state + receipt.replayBundle.candidatePayload.delta;
  }

  rollback(_state, receipt) {
    return receipt.rollbackBundle.preState;
  }
}

function deltaCandidate(delta) {
  return makeCandidate({ delta }, "counter.delta", "counter.delta.v1");
}

test("accepted transaction commits and audits", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const outcome = await engine.transact(10, makeTrace({ branchId: "b0", actions: [{ delta: 3 }] }), deltaCandidate(3));

  assert.equal(outcome.committed, true);
  assert.equal(outcome.state, 13);
  assert.equal(await engine.ledger.audit(), true);
  assert.equal(await engine.replayAudit(10), 13);
  assert.equal(await engine.rollbackAudit(10), 10);
});

test("hard reject cannot commit even with soft score", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const outcome = await engine.transact(
    10,
    makeTrace({ branchId: "b0", actions: [{ delta: 9 }] }),
    deltaCandidate(9),
    { softScores: { proxy: 1 } },
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.state, 10);
  assert.equal(engine.invalidCommitCount, 0);
  assert.equal(engine.softVerifierCommitCount, 0);
  assert.equal(engine.ledger.rows[0].commitDecision, "hard_reject");
});

test("external fake verifier accept fails closed", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const outcome = await engine.transact(
    10,
    makeTrace({ branchId: "b0", actions: [{ delta: 1 }] }),
    deltaCandidate(1),
    { result: hardAccept("soft_proxy", "1.0") },
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.state, 10);
  assert.equal(outcome.reason, "verifier_mismatch");
  assert.equal(engine.verifierMismatchCount, 1);
  assert.equal(await engine.ledger.audit(), true);
});

test("forced reject does not call applyCommit", async () => {
  const adapter = new CounterAdapter();
  const engine = new TransactionEngine(adapter);
  const outcome = await engine.recordEvaluatedCandidate(
    10,
    makeTrace({ branchId: "loser", actions: [{ delta: 1 }] }),
    deltaCandidate(1),
    hardAccept("counter_limit", "1.0"),
    {},
    "rolled_back_loser",
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.state, 10);
  assert.equal(adapter.applyCommitCalls, 0);
  assert.equal(engine.ledger.rows[0].commitDecision, "rolled_back_loser");
});

test("manifest mismatch fails closed but rejected receipt remains auditable", async () => {
  const badManifest = {
    schema: "wrong",
    runtime: "trwm-browser",
    runtimeVersion: "0.1.0",
    createdMs: "0",
    userAgent: "test",
    manifestHash: "bad",
  };
  const engine = new TransactionEngine(new CounterAdapter(), new Ledger(), () => badManifest);
  const outcome = await engine.transact(10, makeTrace({ branchId: "b0" }), deltaCandidate(1));

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason, "manifest_invalid");
  assert.equal(await engine.ledger.audit(), true);
});

test("canonical hashing rejects key collisions", async () => {
  await assert.rejects(
    () => stableHash(new Map([[1, "integer-key"], ["1", "string-key"]])),
    /mapping key collision/,
  );
});

test("ledger rejects self-consistent invalid committed receipt", async () => {
  const pre = await captureState(0);
  const receipt = {
    receiptId: "invalid",
    parentHead: "",
    preStateHash: pre.stateHash,
    postStateHash: (await captureState(1)).stateHash,
    rollbackStateHash: pre.stateHash,
    branchId: "bad",
    proposalTraceHash: await stableHash(makeTrace({ branchId: "bad" })),
    typedCandidateHash: await stableHash(deltaCandidate(1)),
    hardResult: hardReject("counter_limit", "1.0"),
    commitDecision: "commit",
    committed: true,
    runtimeManifest: await createRuntimeManifest(),
    replayBundle: { candidatePayload: { delta: 1 } },
    rollbackBundle: { preState: 0 },
    softScores: {},
    randomSeed: [],
    modelVersion: "manual.v1",
    projectionSchemaVersion: "counter.delta.v1",
    artifactHashes: {},
    receiptSchema: RECEIPT_SCHEMA,
    timestampMs: "0",
    receiptHash: "",
  };
  const finalized = await finalizeReceipt(receipt, "0".repeat(64));

  assert.equal(await receiptStaticValid(finalized), false);
});

test("replay audit refuses tampered ledger", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  await engine.transact(10, makeTrace({ branchId: "b0", actions: [{ delta: 2 }] }), deltaCandidate(2));
  engine.ledger.rows[0] = { ...engine.ledger.rows[0], commitDecision: "hard_reject" };

  await assert.rejects(() => engine.replayAudit(10), /ledger audit failed/);
});
