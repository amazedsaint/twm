import assert from "node:assert/strict";
import test from "node:test";

import {
  BranchRuntime,
  FlawedInventoryPrimaryAdapter,
  InventoryReservationAdapter,
  SAFE_GUARD_ORDER,
  TransactionEngine,
  UNSAFE_GUARD_ORDER,
  VerifierAgreementAdapter,
  VerifierGuardProjector,
  applyPermissiveInventoryReservation,
  hardAbstain,
  makeReservationCandidate,
  makeTrace,
  makeVerifierGuardTraces,
  runVerifierGuardBenchmark,
} from "../dist/index.js";

test("verifier agreement guard blocks a primary false positive", async () => {
  const state = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const candidate = await makeReservationCandidate(state, UNSAFE_GUARD_ORDER, "widget", 8, 8, "guard-test", 1);
  const guard = new VerifierAgreementAdapter(new FlawedInventoryPrimaryAdapter(), new InventoryReservationAdapter());
  const result = await guard.verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.verifierId, guard.verifierId);
  assert.equal(result.verifierVersion, guard.verifierVersion);
  assert.equal(result.residual.kind, "verifier_false_positive");
  assert.equal(result.residual.auditResidual.kind, "stock_shortage");
  assert.equal(guard.primaryCalls, 1);
  assert.equal(guard.auditCalls, 1);
  assert.equal(guard.falsePositiveCount, 1);

  const engine = new TransactionEngine(guard);
  const outcome = await engine.transact(
    state,
    makeTrace({ branchId: "unsafe", actions: [{ orderId: UNSAFE_GUARD_ORDER }] }),
    candidate,
    { result },
  );
  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason, "hard_reject");
  assert.equal(await engine.ledger.audit(), true);
  assert.equal(engine.invalidCommitCount, 0);
});

test("verifier agreement guard accepts when both verifiers agree", async () => {
  const state = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const candidate = await makeReservationCandidate(state, SAFE_GUARD_ORDER, "widget", 3, 3, "guard-test", 5);
  const guard = new VerifierAgreementAdapter(new FlawedInventoryPrimaryAdapter(), new InventoryReservationAdapter());
  const engine = new TransactionEngine(guard);
  const outcome = await engine.transact(
    state,
    makeTrace({ branchId: "safe", actions: [{ orderId: SAFE_GUARD_ORDER }] }),
    candidate,
  );

  assert.equal(outcome.committed, true);
  assert.equal(outcome.state.stock.widget, 2);
  assert.equal(outcome.receipt.hardResult.verifierId, guard.verifierId);
  assert.equal(guard.primaryCalls, 1);
  assert.equal(guard.auditCalls, 1);
  assert.equal(await engine.ledger.audit(), true);
  assert.deepEqual(await engine.rollbackAudit(state), state);
});

test("unguarded branch width commits a verifier false positive", async () => {
  const state = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const engine = new TransactionEngine(new FlawedInventoryPrimaryAdapter());
  const outcome = await new BranchRuntime(engine, new VerifierGuardProjector()).step(state, makeVerifierGuardTraces());

  assert.equal(outcome.committed, true);
  assert.equal(outcome.state.committedOrders.at(-1), UNSAFE_GUARD_ORDER);
  assert.equal(outcome.state.stock.widget, -3);
  assert.equal(await engine.ledger.audit(), true);
  assert.equal(engine.invalidCommitCount, 0);
});

test("verifier guard benchmark metrics", async () => {
  const report = await runVerifierGuardBenchmark();

  assert.equal(report.branchCount, 2);
  assert.equal(report.unguardedCommittedAction, UNSAFE_GUARD_ORDER);
  assert.equal(report.unguardedStockAfter, -3);
  assert.equal(report.unguardedNegativeStock, true);
  assert.equal(report.unguardedLedgerAudit, true);
  assert.equal(report.unguardedReplayRollbackRate, 1);
  assert.equal(report.unguardedInvalidCommitCount, 0);
  assert.equal(report.guardedCommittedAction, SAFE_GUARD_ORDER);
  assert.equal(report.guardedStockAfter, 2);
  assert.equal(report.unsafeRejectedBeforeCommit, true);
  assert.equal(report.falsePositiveCount, 1);
  assert.equal(report.primaryCalls, 2);
  assert.equal(report.auditCalls, 2);
  assert.equal(report.falsePositiveResidualKind, "verifier_false_positive");
  assert.equal(report.auditResidualKind, "stock_shortage");
  assert.deepEqual(report.guardedReceiptDecisions, ["hard_reject", "commit"]);
  assert.equal(report.guardedLedgerAudit, true);
  assert.equal(report.guardedReplayRollbackRate, 1);
  assert.equal(report.guardedInvalidCommitCount, 0);
});

test("permissive adapter can replay the negative-stock false-positive path", () => {
  const state = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const nextState = applyPermissiveInventoryReservation(state, UNSAFE_GUARD_ORDER, "widget", 8);
  assert.equal(nextState.stock.widget, -3);
});

test("audit abstention blocks primary accept", async () => {
  const state = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const candidate = await makeReservationCandidate(state, SAFE_GUARD_ORDER, "widget", 3, 3);
  const audit = {
    verifierId: "abstaining_audit",
    verifierVersion: "1.0",
    verify: () => hardAbstain("abstaining_audit", "1.0", { kind: "manual_review" }),
  };
  const guard = new VerifierAgreementAdapter(new FlawedInventoryPrimaryAdapter(), audit);
  const result = await guard.verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "verifier_false_positive");
  assert.equal(result.residual.auditResult, "abstain");
  assert.equal(guard.falsePositiveCount, 1);
});
