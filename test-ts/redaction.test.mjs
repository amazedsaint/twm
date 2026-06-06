import assert from "node:assert/strict";
import test from "node:test";

import {
  REDACTION_DEMO_PATHS,
  REDACTION_DEMO_SALT,
  REDACTION_SCHEMA,
  InventoryReservationAdapter,
  TransactionEngine,
  makeRedactionPolicy,
  makeReservationCandidate,
  makeTrace,
  receiptStaticValid,
  redactReceipt,
  redactedReceiptCannotReplay,
  runRedactedReceiptBenchmark,
  validateRedactedReceipt,
  verifyRedactedPath,
} from "../dist/index.js";

test("redaction policy rejects duplicate, empty, and audit-critical paths", () => {
  assert.throws(
    () => makeRedactionPolicy(["replayBundle.candidatePayload.orderId", "replayBundle.candidatePayload.orderId"]),
    /unique/,
  );
  assert.throws(() => makeRedactionPolicy([""]), /non-empty/);
  assert.throws(() => makeRedactionPolicy(["receiptHash"]), /auditability/);
});

test("redacted receipt validates commitments and selective disclosure", async () => {
  const [receipt, engine] = await committedReceipt();
  const view = await redactReceipt(receipt, makeRedactionPolicy(REDACTION_DEMO_PATHS), REDACTION_DEMO_SALT);
  const tampered = {
    ...view,
    redactedPayload: {
      ...view.redactedPayload,
      commitDecision: "hard_reject",
    },
  };

  assert.equal(view.schemaVersion, REDACTION_SCHEMA);
  assert.equal(view.originalReceiptHash, receipt.receiptHash);
  assert.equal(await validateRedactedReceipt(view), true);
  assert.equal(await validateRedactedReceipt(tampered), false);
  assert.equal(await verifyRedactedPath(view, REDACTION_DEMO_PATHS[0], "order-private-1", REDACTION_DEMO_SALT), true);
  assert.equal(await verifyRedactedPath(view, REDACTION_DEMO_PATHS[0], "order-private-2", REDACTION_DEMO_SALT), false);
  assert.equal(redactedReceiptCannotReplay(view), true);
  assert.equal(await receiptStaticValid(view), false);
  assert.equal(await engine.ledger.audit(), true);
});

test("missing redaction paths fail closed", async () => {
  const [receipt] = await committedReceipt();

  await assert.rejects(
    () => redactReceipt(receipt, makeRedactionPolicy(["replayBundle.candidatePayload.notHere"]), REDACTION_DEMO_SALT),
    /not found/,
  );
});

test("redacted receipt benchmark uses a live committed inventory receipt", async () => {
  const report = await runRedactedReceiptBenchmark();

  assert.equal(report.schemaVersion, REDACTION_SCHEMA);
  assert.equal(report.redactedPathCount, 3);
  assert.equal(report.visibleCommitDecision, "commit");
  assert.equal(report.visibleVerifierResult, "accept");
  assert.equal(report.orderIdRedacted, true);
  assert.equal(report.preStateRedacted, true);
  assert.equal(report.selectiveDisclosureOk, true);
  assert.equal(report.wrongDisclosureRejected, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.redactedHashStable, true);
  assert.equal(report.originalReceiptStillAudits, true);
  assert.equal(report.redactedViewIsNotReplayable, true);
  assert.equal(report.invalidCommitCount, 0);
});

async function committedReceipt() {
  const state = { stock: { widget: 5 }, reserved: {}, committedOrders: [] };
  const candidate = await makeReservationCandidate(state, "order-private-1", "widget", 3, 3, "redaction-demo");
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  const outcome = await engine.transact(
    state,
    makeTrace({
      branchId: "redaction-test",
      actions: [{ sku: "widget", quantity: 3 }],
      seeds: ["redaction", "test"],
      modelVersion: "redaction.test.v1",
    }),
    candidate,
  );
  assert.equal(outcome.committed, true);
  return [outcome.receipt, engine];
}
