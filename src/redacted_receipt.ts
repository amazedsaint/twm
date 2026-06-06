import { TransactionEngine, makeTrace } from "./core.js";
import {
  InventoryReservationAdapter,
  makeReservationCandidate,
  type InventoryState,
} from "./operations.js";
import {
  REDACTION_SCHEMA,
  makeRedactionPolicy,
  redactReceipt,
  redactedReceiptCannotReplay,
  validateRedactedReceipt,
  verifyRedactedPath,
} from "./redaction.js";

export const REDACTION_DEMO_SALT = "redaction-demo-salt";
export const REDACTION_DEMO_PATHS = [
  "replayBundle.candidatePayload.orderId",
  "replayBundle.candidatePayload.preState",
  "rollbackBundle.preState",
];

export interface RedactedReceiptReport {
  schemaVersion: string;
  originalReceiptHash: string;
  redactedHash: string;
  policyHash: string;
  redactedPathCount: number;
  visibleCommitDecision: string;
  visibleVerifierResult: string;
  orderIdRedacted: boolean;
  preStateRedacted: boolean;
  selectiveDisclosureOk: boolean;
  wrongDisclosureRejected: boolean;
  tamperDetected: boolean;
  redactedHashStable: boolean;
  originalReceiptStillAudits: boolean;
  redactedViewIsNotReplayable: boolean;
  invalidCommitCount: number;
}

export async function runRedactedReceiptBenchmark(): Promise<RedactedReceiptReport> {
  const state: InventoryState = { stock: { widget: 5 }, reserved: {}, committedOrders: [] };
  const candidate = await makeReservationCandidate(
    state,
    "order-private-1",
    "widget",
    3,
    3,
    "redaction-demo",
  );
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  const outcome = await engine.transact(
    state,
    makeTrace({
      branchId: "redacted-receipt-demo",
      actions: [{ sku: "widget", quantity: 3 }],
      seeds: ["redaction", "inventory"],
      modelVersion: "redaction.demo.v1",
    }),
    candidate,
  );
  if (!outcome.committed) {
    throw new Error("redaction demo requires a committed receipt");
  }
  const policy = makeRedactionPolicy(REDACTION_DEMO_PATHS);
  const view = await redactReceipt(outcome.receipt, policy, REDACTION_DEMO_SALT);
  const repeatView = await redactReceipt(outcome.receipt, policy, REDACTION_DEMO_SALT);
  const tampered = {
    ...view,
    redactedPayload: {
      ...view.redactedPayload,
      commitDecision: "hard_reject",
    },
  };
  return {
    schemaVersion: REDACTION_SCHEMA,
    originalReceiptHash: view.originalReceiptHash,
    redactedHash: view.redactedHash,
    policyHash: view.policyHash,
    redactedPathCount: view.commitments.length,
    visibleCommitDecision: String(view.redactedPayload.commitDecision),
    visibleVerifierResult: String((view.redactedPayload.hardResult as { result?: unknown }).result),
    orderIdRedacted: redactionMarkerPresent(view.redactedPayload, REDACTION_DEMO_PATHS[0]),
    preStateRedacted: redactionMarkerPresent(view.redactedPayload, REDACTION_DEMO_PATHS[1])
      && redactionMarkerPresent(view.redactedPayload, REDACTION_DEMO_PATHS[2]),
    selectiveDisclosureOk: await verifyRedactedPath(
      view,
      REDACTION_DEMO_PATHS[0],
      "order-private-1",
      REDACTION_DEMO_SALT,
    ),
    wrongDisclosureRejected: !await verifyRedactedPath(
      view,
      REDACTION_DEMO_PATHS[0],
      "order-private-2",
      REDACTION_DEMO_SALT,
    ),
    tamperDetected: !await validateRedactedReceipt(tampered),
    redactedHashStable: view.redactedHash === repeatView.redactedHash,
    originalReceiptStillAudits: await engine.ledger.audit(),
    redactedViewIsNotReplayable: redactedReceiptCannotReplay(view),
    invalidCommitCount: engine.invalidCommitCount,
  };
}

function redactionMarkerPresent(payload: Record<string, unknown>, path: string): boolean {
  let current: unknown = payload;
  for (const part of path.split(".")) {
    if (!current || typeof current !== "object" || Array.isArray(current) || !Object.prototype.hasOwnProperty.call(current, part)) {
      return false;
    }
    current = (current as Record<string, unknown>)[part];
  }
  return Boolean(current && typeof current === "object" && !Array.isArray(current) && (current as { redacted?: unknown }).redacted === true);
}
