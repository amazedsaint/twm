import assert from "node:assert/strict";
import test from "node:test";

import {
  BranchRuntime,
  DistributedCommitManager,
  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
  runDistributedCounterBenchmark,
} from "../dist/index.js";

class CounterAdapter {
  verifierId = "counter_limit";
  verifierVersion = "1.0";

  verify(candidate) {
    return candidate.payload.delta <= 5
      ? hardAccept(this.verifierId, this.verifierVersion, { cost: candidate.payload.cost ?? 0 })
      : hardReject(this.verifierId, this.verifierVersion, { delta: candidate.payload.delta });
  }

  applyCommit(state, candidate) {
    return state + candidate.payload.delta;
  }

  replay(state, receipt) {
    return state + receipt.replayBundle.candidatePayload.delta;
  }

  rollback(_state, receipt) {
    return receipt.rollbackBundle.preState;
  }
}

class DeltaProjector {
  project(_state, trace) {
    return makeCandidate(trace.actions.at(-1), "counter.delta", "counter.delta.v1");
  }
}

test("branch runtime commits only after hard filtering", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const runtime = new BranchRuntime(engine, new DeltaProjector());
  const outcome = await runtime.step(0, [
    makeTrace({ branchId: "reject", actions: [{ delta: 9, cost: 1 }] }),
    makeTrace({ branchId: "accept", actions: [{ delta: 2, cost: 2 }] }),
  ]);

  assert.equal(outcome.committed, true);
  assert.equal(outcome.state, 2);
  assert.equal(outcome.verifierCalls, 2);
  assert.equal(engine.ledger.rows.length, 2);
  assert.equal(await engine.ledger.audit(), true);
});

test("invalid ranker choice fails closed", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const runtime = new BranchRuntime(engine, new DeltaProjector(), { choose: (verified) => verified.length });
  const outcome = await runtime.step(0, [
    makeTrace({ branchId: "a", actions: [{ delta: 1 }] }),
    makeTrace({ branchId: "b", actions: [{ delta: 2 }] }),
  ]);

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason, "ranker_invalid_choice");
  assert.equal(engine.ledger.rows.every((row) => row.commitDecision === "ranker_invalid_choice"), true);
  assert.equal(await engine.ledger.audit(), true);
});

test("distributed commit manager records stale and rejected worker receipts", async () => {
  const engine = new TransactionEngine(new CounterAdapter(), new Ledger());
  const manager = new DistributedCommitManager(engine);
  const currentRejected = {
    parentHead: engine.ledger.head,
    trace: makeTrace({ branchId: "reject", actions: [{ delta: 9 }] }),
    candidate: makeCandidate({ delta: 9 }, "counter.delta", "counter.delta.v1"),
    result: hardReject("counter_limit", "1.0", { delta: 9 }),
  };
  const staleAccepted = {
    parentHead: "f".repeat(64),
    trace: makeTrace({ branchId: "stale", actions: [{ delta: 1 }] }),
    candidate: makeCandidate({ delta: 1 }, "counter.delta", "counter.delta.v1"),
    result: hardAccept("counter_limit", "1.0"),
  };
  const outcome = await manager.commitOne(0, [currentRejected, staleAccepted]);

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason, "no_admissible_worker_receipt");
  assert.equal(manager.staleReceiptRejectionCount, 1);
  assert.deepEqual(engine.ledger.rows.map((row) => row.commitDecision).sort(), ["stale_parent", "worker_not_accepted"]);
  assert.equal(await engine.ledger.audit(), true);
});

test("distributed execution matches local canonical result under deterministic seeds", async () => {
  const report = await runDistributedCounterBenchmark();

  assert.equal(report.canonicalStateEqual, true);
  assert.equal(report.canonicalDeltaEqual, true);
  assert.equal(report.localState, 2);
  assert.equal(report.distributedState, 2);
  assert.equal(report.localCommittedDelta, 2);
  assert.equal(report.distributedCommittedDelta, 2);
  assert.equal(report.localVerifierCalls, 3);
  assert.equal(report.distributedWorkerReceipts, 3);
  assert.equal(report.staleParentRejections, 1);
  assert.equal(report.staleProbeCommitted, false);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
});

test("distributed invalid ranker choice fails closed", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const manager = new DistributedCommitManager(engine, { choose: (verified) => verified.length });
  const outcome = await manager.commitOne(0, [{
    parentHead: engine.ledger.head,
    trace: makeTrace({ branchId: "accepted", actions: [{ delta: 1 }] }),
    candidate: makeCandidate({ delta: 1 }, "counter.delta", "counter.delta.v1"),
    result: hardAccept("counter_limit", "1.0"),
  }]);

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason, "ranker_invalid_choice");
  assert.equal(engine.ledger.rows[0].commitDecision, "ranker_invalid_choice");
  assert.equal(await engine.ledger.audit(), true);
});
