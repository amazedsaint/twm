import {
  type HardVerifierResult,
  type ProposalTrace,
  type Receipt,
  type ReplayRollbackAdapter,
  type TypedCandidate,
  hardAccept,
  hardReject,
  makeTrace,
  TransactionEngine,
} from "./core.js";
import { BranchRuntime, type BranchProjector } from "./branch.js";
import { VerifierAgreementAdapter } from "./verifier_guard.js";
import {
  type InventoryReservationPayload,
  type InventoryState,
  InventoryReservationAdapter,
  makeReservationCandidate,
  normalizeInventoryState,
} from "./operations.js";

export const VERIFIER_GUARD_SKU = "widget";
export const UNSAFE_GUARD_ORDER = "unsafe-large";
export const SAFE_GUARD_ORDER = "safe-small";

export interface VerifierGuardReport {
  branchCount: number;
  unguardedCommittedAction: string;
  unguardedStockAfter: number;
  unguardedNegativeStock: boolean;
  unguardedLedgerAudit: boolean;
  unguardedReplayRollbackRate: number;
  unguardedInvalidCommitCount: number;
  guardedCommittedAction: string;
  guardedStockAfter: number;
  unsafeRejectedBeforeCommit: boolean;
  falsePositiveCount: number;
  primaryCalls: number;
  auditCalls: number;
  falsePositiveResidualKind: string;
  auditResidualKind: string;
  guardedReceiptDecisions: string[];
  guardedLedgerAudit: boolean;
  guardedReplayRollbackRate: number;
  guardedInvalidCommitCount: number;
}

export class FlawedInventoryPrimaryAdapter
implements ReplayRollbackAdapter<InventoryState, InventoryReservationPayload> {
  verifierId = "flawed_inventory_primary";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<InventoryReservationPayload>): HardVerifierResult {
    const payload = candidate.payload;
    const state = normalizeInventoryState(payload.preState);
    const metadata = { cost: payload.cost, requested: payload.requested, quantity: payload.quantity };
    if (!payload.orderId) {
      return this.reject("schema_error", { message: "orderId must be non-empty" }, metadata);
    }
    if (state.committedOrders.includes(payload.orderId)) {
      return this.reject("duplicate_order", { orderId: payload.orderId }, metadata);
    }
    if (!positiveInt(payload.requested) || !positiveInt(payload.quantity)) {
      return this.reject("schema_error", { message: "requested and quantity must be positive" }, metadata);
    }
    if (payload.quantity > payload.requested) {
      return this.reject("over_reservation", { requested: payload.requested, quantity: payload.quantity }, metadata);
    }
    const expected = { stockDelta: -payload.quantity, reservedDelta: payload.quantity };
    if (payload.diff.stockDelta !== expected.stockDelta || payload.diff.reservedDelta !== expected.reservedDelta) {
      return this.reject("diff_mismatch", { expected, actual: payload.diff }, metadata);
    }
    const available = state.stock[payload.sku] ?? 0;
    return hardAccept(this.verifierId, this.verifierVersion, {
      ...metadata,
      availableBefore: available,
      availableAfter: available - payload.quantity,
    });
  }

  applyCommit(state: InventoryState, candidate: TypedCandidate<InventoryReservationPayload>): InventoryState {
    const current = normalizeInventoryState(state);
    const preState = normalizeInventoryState(candidate.payload.preState);
    if (JSON.stringify(current) !== JSON.stringify(preState)) {
      throw new Error("candidate preState does not match current inventory state");
    }
    return applyPermissiveInventoryReservation(current, candidate.payload.orderId, candidate.payload.sku, candidate.payload.quantity);
  }

  replay(state: InventoryState, receipt: Receipt): InventoryState {
    const payload = (receipt.replayBundle as { candidatePayload: InventoryReservationPayload }).candidatePayload;
    return applyPermissiveInventoryReservation(normalizeInventoryState(state), payload.orderId, payload.sku, payload.quantity);
  }

  rollback(_state: InventoryState, receipt: Receipt): InventoryState {
    return normalizeInventoryState((receipt.rollbackBundle as { preState: InventoryState }).preState);
  }

  private reject(kind: string, residual: Record<string, unknown>, metadata: Record<string, unknown>): HardVerifierResult {
    return hardReject(this.verifierId, this.verifierVersion, { kind, ...residual }, metadata);
  }
}

export class VerifierGuardProjector
implements BranchProjector<InventoryState, InventoryReservationPayload> {
  async project(state: InventoryState, trace: ProposalTrace): Promise<TypedCandidate<InventoryReservationPayload>> {
    if (trace.actions.length === 0) {
      throw new RangeError("verifier guard traces must contain one action payload");
    }
    const payload = normalizeGuardPayload(trace.actions[0] as Record<string, unknown>);
    return makeReservationCandidate(
      normalizeInventoryState(state),
      payload.orderId,
      payload.sku,
      payload.requested,
      payload.quantity,
      payload.context,
      payload.cost,
    );
  }
}

export function makeVerifierGuardTraces(): ProposalTrace[] {
  return candidatePayloads().map((payload) => makeTrace({
    branchId: `verifier-guard-${payload.orderId}`,
    actions: [payload],
    seeds: ["verifier_guard", payload.orderId],
    modelVersion: "verifier.false_positive_guard.v1",
  }));
}

export async function runVerifierGuardBenchmark(): Promise<VerifierGuardReport> {
  const seedState: InventoryState = {
    stock: { [VERIFIER_GUARD_SKU]: 5 },
    reserved: { [VERIFIER_GUARD_SKU]: 0 },
    committedOrders: [],
  };
  const traces = makeVerifierGuardTraces();

  const unguardedEngine = new TransactionEngine(new FlawedInventoryPrimaryAdapter());
  const unguarded = await new BranchRuntime(unguardedEngine, new VerifierGuardProjector()).step(seedState, traces);
  const unguardedState = unguarded.state;

  const guard = new VerifierAgreementAdapter(
    new FlawedInventoryPrimaryAdapter(),
    new InventoryReservationAdapter(),
  );
  const guardedEngine = new TransactionEngine(guard);
  const guarded = await new BranchRuntime(guardedEngine, new VerifierGuardProjector()).step(seedState, traces);
  const guardedState = normalizeInventoryState(guarded.state);
  const guardedReceipts = guarded.receipts as Receipt[];
  const falsePositiveReceipt = falsePositiveReceiptFrom(guardedReceipts);
  const falsePositiveResidual = falsePositiveReceipt.hardResult.residual as {
    kind: string;
    auditResidual?: { kind?: string };
    audit_residual?: { kind?: string };
  };

  return {
    branchCount: traces.length,
    unguardedCommittedAction: unguardedState.committedOrders[unguardedState.committedOrders.length - 1],
    unguardedStockAfter: unguardedState.stock[VERIFIER_GUARD_SKU] ?? 0,
    unguardedNegativeStock: (unguardedState.stock[VERIFIER_GUARD_SKU] ?? 0) < 0,
    unguardedLedgerAudit: await unguardedEngine.ledger.audit(),
    unguardedReplayRollbackRate: await replayRollbackRate(unguardedEngine, seedState),
    unguardedInvalidCommitCount: unguardedEngine.invalidCommitCount,
    guardedCommittedAction: guardedState.committedOrders[guardedState.committedOrders.length - 1],
    guardedStockAfter: guardedState.stock[VERIFIER_GUARD_SKU] ?? 0,
    unsafeRejectedBeforeCommit: !guardedReceipts.some((receipt) => receipt.committed && orderId(receipt) === UNSAFE_GUARD_ORDER),
    falsePositiveCount: guard.falsePositiveCount,
    primaryCalls: guard.primaryCalls,
    auditCalls: guard.auditCalls,
    falsePositiveResidualKind: falsePositiveResidual.kind,
    auditResidualKind: String((falsePositiveResidual.auditResidual ?? falsePositiveResidual.audit_residual)?.kind ?? ""),
    guardedReceiptDecisions: guardedReceipts.map((receipt) => receipt.commitDecision),
    guardedLedgerAudit: await guardedEngine.ledger.audit(),
    guardedReplayRollbackRate: await replayRollbackRate(guardedEngine, seedState),
    guardedInvalidCommitCount: guardedEngine.invalidCommitCount,
  };
}

export function applyPermissiveInventoryReservation(
  stateInput: InventoryState,
  orderId: string,
  sku: string,
  quantity: number,
): InventoryState {
  const state = normalizeInventoryState(stateInput);
  const available = state.stock[sku] ?? 0;
  return {
    stock: { ...state.stock, [sku]: available - quantity },
    reserved: { ...state.reserved, [sku]: (state.reserved[sku] ?? 0) + quantity },
    committedOrders: [...state.committedOrders, orderId],
  };
}

export function normalizeGuardPayload(payload: Record<string, unknown>): {
  context: string;
  orderId: string;
  sku: string;
  requested: number;
  quantity: number;
  cost: number;
} {
  const orderId = String(payload.orderId ?? payload.order_id ?? "");
  if (!orderId) {
    throw new RangeError("orderId must be non-empty");
  }
  return {
    context: String(payload.context ?? "verifier-guard"),
    orderId,
    sku: String(payload.sku ?? VERIFIER_GUARD_SKU),
    requested: positiveInteger(payload.requested, "requested"),
    quantity: positiveInteger(payload.quantity, "quantity"),
    cost: positiveInteger(payload.cost ?? 1, "cost"),
  };
}

function candidatePayloads(): Array<ReturnType<typeof normalizeGuardPayload>> {
  return [
    { context: "verifier-guard", orderId: UNSAFE_GUARD_ORDER, sku: VERIFIER_GUARD_SKU, requested: 8, quantity: 8, cost: 1 },
    { context: "verifier-guard", orderId: SAFE_GUARD_ORDER, sku: VERIFIER_GUARD_SKU, requested: 3, quantity: 3, cost: 5 },
  ];
}

function positiveInt(value: number): boolean {
  return Number.isInteger(value) && value > 0;
}

function positiveInteger(value: unknown, field: string): number {
  if (typeof value === "boolean") {
    throw new RangeError(`${field} must be a positive integer`);
  }
  const parsed = typeof value === "string" && /^[0-9]+$/.test(value.trim()) ? Number(value) : value;
  if (typeof parsed !== "number" || !Number.isInteger(parsed) || parsed <= 0) {
    throw new RangeError(`${field} must be a positive integer`);
  }
  return parsed;
}

function falsePositiveReceiptFrom(receipts: Receipt[]): Receipt {
  const rows = receipts.filter((receipt) =>
    receipt.hardResult.residual
    && typeof receipt.hardResult.residual === "object"
    && (receipt.hardResult.residual as { kind?: unknown }).kind === "verifier_false_positive"
  );
  if (rows.length !== 1) {
    throw new Error(`expected exactly one false-positive receipt, got ${rows.length}`);
  }
  return rows[0];
}

function orderId(receipt: Receipt): string {
  const payload = (receipt.replayBundle as { candidatePayload?: { orderId?: unknown; order_id?: unknown } }).candidatePayload;
  return String(payload?.orderId ?? payload?.order_id ?? "");
}

async function replayRollbackRate(
  engine: {
    replayAudit(seed: InventoryState): Promise<InventoryState>;
    rollbackAudit(seed: InventoryState): Promise<InventoryState>;
  },
  seedState: InventoryState,
): Promise<number> {
  try {
    await engine.replayAudit(seedState);
    const rolledBack = await engine.rollbackAudit(seedState);
    return JSON.stringify(rolledBack) === JSON.stringify(seedState) ? 1 : 0;
  } catch (_error) {
    return 0;
  }
}
