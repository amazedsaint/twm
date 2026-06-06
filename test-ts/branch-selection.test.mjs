import assert from "node:assert/strict";
import test from "node:test";

import {
  BranchRuntime,
  TransactionEngine,
  auditBranchSelection,
  buildBranchSelectionCertificate,
  branchSelectionCertificateHash,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
  runBranchSelectionBenchmark,
  validateBranchSelectionCertificate,
} from "../dist/index.js";

class CounterAdapter {
  verifierId = "branch_counter_oracle";
  verifierVersion = "1.0";

  verify(candidate) {
    const cost = candidate.payload.cost ?? 0;
    return candidate.payload.delta <= 5
      ? hardAccept(this.verifierId, this.verifierVersion, { cost })
      : hardReject(this.verifierId, this.verifierVersion, { delta: candidate.payload.delta, limit: 5 }, { cost });
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

class CounterProjector {
  project(_state, trace) {
    return makeCandidate({ ...trace.actions.at(-1) }, "counter.delta", "counter.delta.v1");
  }
}

test("branch selection certificate records selected branch after hard filter", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const outcome = await new BranchRuntime(engine, new CounterProjector()).step(0, [
    makeTrace({ branchId: "reject", actions: [{ delta: 9, cost: 1, softRank: 999 }] }),
    makeTrace({ branchId: "loser", actions: [{ delta: 1, cost: 4 }] }),
    makeTrace({ branchId: "winner", actions: [{ delta: 2, cost: 2 }] }),
  ]);
  const certificate = await buildBranchSelectionCertificate(outcome.receipts, { verifierCallCount: outcome.verifierCalls });

  assert.deepEqual(certificate.acceptedIndices, [1, 2]);
  assert.deepEqual(certificate.rejectedIndices, [0]);
  assert.deepEqual(certificate.abstainedIndices, []);
  assert.deepEqual(certificate.loserIndices, [1]);
  assert.equal(certificate.selectedIndex, 2);
  assert.equal(certificate.committedIndex, 2);
  assert.equal(await validateBranchSelectionCertificate(certificate), true);
  assert.equal(await auditBranchSelection(outcome.receipts, certificate), true);
});

test("branch selection certificate rejects a committed rejected branch", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const outcome = await new BranchRuntime(engine, new CounterProjector()).step(0, [
    makeTrace({ branchId: "reject", actions: [{ delta: 9, cost: 1 }] }),
    makeTrace({ branchId: "winner", actions: [{ delta: 2, cost: 2 }] }),
  ]);
  const certificate = await buildBranchSelectionCertificate(outcome.receipts, { verifierCallCount: outcome.verifierCalls });
  const tampered = { ...certificate, committedIndex: 0, certificateHash: "" };
  tampered.certificateHash = await branchSelectionCertificateHash(tampered);

  assert.equal(await validateBranchSelectionCertificate(tampered), false);
});

test("invalid ranker receipts still have a valid fail-closed certificate", async () => {
  const engine = new TransactionEngine(new CounterAdapter());
  const outcome = await new BranchRuntime(
    engine,
    new CounterProjector(),
    { choose: (verified) => verified.length },
  ).step(0, [
    makeTrace({ branchId: "a", actions: [{ delta: 1, cost: 1 }] }),
    makeTrace({ branchId: "b", actions: [{ delta: 2, cost: 2 }] }),
  ]);
  const certificate = await buildBranchSelectionCertificate(outcome.receipts, { verifierCallCount: outcome.verifierCalls });

  assert.equal(outcome.committed, false);
  assert.equal(certificate.selectedIndex, null);
  assert.equal(certificate.committedIndex, null);
  assert.deepEqual(certificate.loserIndices, []);
  assert.equal(await validateBranchSelectionCertificate(certificate), true);
  assert.equal(await auditBranchSelection(outcome.receipts, certificate), true);
});

test("branch selection benchmark exposes exact certificate metrics", async () => {
  const report = await runBranchSelectionBenchmark();

  assert.equal(report.branchCount, 3);
  assert.equal(report.acceptedCount, 2);
  assert.equal(report.rejectedCount, 1);
  assert.equal(report.selectedIndex, 2);
  assert.equal(report.committedIndex, 2);
  assert.equal(report.loserCount, 1);
  assert.equal(report.hardRejectSoftRankBlocked, true);
  assert.equal(report.rankAfterHardFilter, true);
  assert.equal(report.certificateValid, true);
  assert.equal(report.auditValid, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.invalidRankerCertificateValid, true);
  assert.equal(report.invalidRankerCommitted, false);
  assert.equal(report.verifierCalls, 3);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
});
