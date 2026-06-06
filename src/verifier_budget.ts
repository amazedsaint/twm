import {
  type HardVerifierResult,
  type ProposalTrace,
  type Receipt,
  type ReplayRollbackAdapter,
  type TypedCandidate,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
  TransactionEngine,
} from "./core.js";
import { BranchRuntime, BudgetedBranchRuntime, VerifierBudget, type BranchProjector } from "./branch.js";

export const VERIFIER_BUDGET_CONTEXT = "verifier-budget-route";
export const VERIFIER_BUDGET_LIMIT = 4;
export const EXPENSIVE_BUDGET_SOLUTION = "expensive_solution";
export const CHEAP_BUDGET_DECOY = "cheap_decoy";
export const CHEAP_BUDGET_SOLUTION = "cheap_solution";

export interface VerifierBudgetState {
  committedActions: string[];
}

export interface VerifierBudgetPayload {
  context: string;
  action: string;
  planCost: number;
  verifierCost: number;
  accepted: boolean;
}

export interface VerifierBudgetReport {
  candidateCount: number;
  budget: number;
  unbudgetedVerifierCalls: number;
  unbudgetedCommittedAction: string;
  verifierCalls: number;
  verifierCost: number;
  abstainedCount: number;
  committedAction: string;
  skippedAction: string;
  verifiedRejectedAction: string;
  budgetResidualKind: string;
  expensiveRequiredCost: number;
  remainingBudgetBeforeExpensive: number;
  receiptDecisions: string[];
  ledgerAudit: boolean;
  replayRollbackRate: number;
  invalidCommitCount: number;
}

export class VerifierBudgetAdapter implements ReplayRollbackAdapter<VerifierBudgetState, VerifierBudgetPayload> {
  verifierId = "verifier_budget_oracle";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<VerifierBudgetPayload>): HardVerifierResult {
    const payload = normalizeVerifierBudgetPayload(candidate.payload);
    const metadata = {
      action: payload.action,
      cost: payload.planCost,
      verifierCost: payload.verifierCost,
      verifier_cost: payload.verifierCost,
      context: payload.context,
    };
    if (payload.accepted) {
      return hardAccept(this.verifierId, this.verifierVersion, metadata);
    }
    return hardReject(
      this.verifierId,
      this.verifierVersion,
      { kind: "candidate_rejected", action: payload.action },
      metadata,
    );
  }

  applyCommit(state: VerifierBudgetState, candidate: TypedCandidate<VerifierBudgetPayload>): VerifierBudgetState {
    const current = normalizeVerifierBudgetState(state);
    const payload = normalizeVerifierBudgetPayload(candidate.payload);
    return { committedActions: [...current.committedActions, payload.action] };
  }

  replay(state: VerifierBudgetState, receipt: Receipt): VerifierBudgetState {
    const current = normalizeVerifierBudgetState(state);
    const payload = normalizeVerifierBudgetPayload((receipt.replayBundle as { candidatePayload: VerifierBudgetPayload }).candidatePayload);
    return { committedActions: [...current.committedActions, payload.action] };
  }

  rollback(_state: VerifierBudgetState, receipt: Receipt): VerifierBudgetState {
    return normalizeVerifierBudgetState((receipt.rollbackBundle as { preState: VerifierBudgetState }).preState);
  }
}

export class VerifierBudgetProjector implements BranchProjector<VerifierBudgetState, VerifierBudgetPayload> {
  project(_state: VerifierBudgetState, trace: ProposalTrace): TypedCandidate<VerifierBudgetPayload> {
    if (trace.actions.length === 0) {
      throw new RangeError("verifier budget traces must contain one action payload");
    }
    return makeVerifierBudgetCandidate(normalizeVerifierBudgetPayload(trace.actions[0] as Record<string, unknown>));
  }
}

export function makeVerifierBudgetCandidate(payload: VerifierBudgetPayload | Record<string, unknown>): TypedCandidate<VerifierBudgetPayload> {
  return makeCandidate(
    normalizeVerifierBudgetPayload(payload),
    "verifier_budget.plan",
    "verifier_budget.plan.v1",
  );
}

export function makeVerifierBudgetTraces(): ProposalTrace[] {
  return candidatePayloads().map((payload) => makeTrace({
    branchId: `verifier-budget-${payload.action}`,
    actions: [payload],
    seeds: ["verifier_budget", payload.action],
    modelVersion: "verifier.budget.v1",
  }));
}

export async function runVerifierBudgetBenchmark(): Promise<VerifierBudgetReport> {
  const traces = makeVerifierBudgetTraces();
  const unbudgetedEngine = new TransactionEngine(new VerifierBudgetAdapter());
  const unbudgeted = await new BranchRuntime(unbudgetedEngine, new VerifierBudgetProjector()).step({ committedActions: [] }, traces);

  const engine = new TransactionEngine(new VerifierBudgetAdapter());
  const budgeted = await new BudgetedBranchRuntime(
    engine,
    new VerifierBudgetProjector(),
    new VerifierBudget(VERIFIER_BUDGET_LIMIT),
  ).step({ committedActions: [] }, traces);

  const receipts = budgeted.receipts as Receipt[];
  const abstainReceipt = singleReceipt(receipts, "abstain");
  const rejectReceipt = singleReceipt(receipts, "reject");
  const abstainPayload = normalizeVerifierBudgetPayload((abstainReceipt.replayBundle as { candidatePayload: VerifierBudgetPayload }).candidatePayload);
  const committed = normalizeVerifierBudgetState(budgeted.state);
  const unbudgetedCommitted = normalizeVerifierBudgetState(unbudgeted.state);

  return {
    candidateCount: traces.length,
    budget: VERIFIER_BUDGET_LIMIT,
    unbudgetedVerifierCalls: unbudgeted.verifierCalls,
    unbudgetedCommittedAction: unbudgetedCommitted.committedActions[unbudgetedCommitted.committedActions.length - 1],
    verifierCalls: budgeted.verifierCalls,
    verifierCost: budgeted.verifierCost,
    abstainedCount: budgeted.abstainedCount,
    committedAction: committed.committedActions[committed.committedActions.length - 1],
    skippedAction: abstainPayload.action,
    verifiedRejectedAction: String(rejectReceipt.hardResult.metadata.action),
    budgetResidualKind: String((abstainReceipt.hardResult.residual as { kind: string }).kind),
    expensiveRequiredCost: Number((abstainReceipt.hardResult.residual as { requiredVerifierCost: number }).requiredVerifierCost),
    remainingBudgetBeforeExpensive: Number((abstainReceipt.hardResult.residual as { remainingBudget: number }).remainingBudget),
    receiptDecisions: receipts.map((receipt) => receipt.commitDecision),
    ledgerAudit: await engine.ledger.audit(),
    replayRollbackRate: await replayRollbackRate(engine),
    invalidCommitCount: engine.invalidCommitCount,
  };
}

export function normalizeVerifierBudgetState(state: VerifierBudgetState | Record<string, unknown>): VerifierBudgetState {
  const raw = state as Record<string, unknown>;
  const committedActions = raw.committedActions ?? raw.committed_actions ?? [];
  if (!Array.isArray(committedActions)) {
    throw new RangeError("committedActions must be an array");
  }
  return { committedActions: committedActions.map((action) => String(action)) };
}

export function normalizeVerifierBudgetPayload(payload: VerifierBudgetPayload | Record<string, unknown>): VerifierBudgetPayload {
  const raw = payload as Record<string, unknown>;
  const action = String(raw.action ?? "");
  if (!action) {
    throw new RangeError("action must be non-empty");
  }
  const accepted = raw.accepted ?? false;
  if (typeof accepted !== "boolean") {
    throw new RangeError("accepted must be a boolean");
  }
  return {
    context: String(raw.context ?? VERIFIER_BUDGET_CONTEXT),
    action,
    planCost: positiveInteger(raw.planCost ?? raw.plan_cost ?? 1, "planCost"),
    verifierCost: positiveInteger(raw.verifierCost ?? raw.verifier_cost ?? 1, "verifierCost"),
    accepted,
  };
}

function candidatePayloads(): VerifierBudgetPayload[] {
  return [
    { context: VERIFIER_BUDGET_CONTEXT, action: EXPENSIVE_BUDGET_SOLUTION, planCost: 1, verifierCost: 7, accepted: true },
    { context: VERIFIER_BUDGET_CONTEXT, action: CHEAP_BUDGET_DECOY, planCost: 1, verifierCost: 2, accepted: false },
    { context: VERIFIER_BUDGET_CONTEXT, action: CHEAP_BUDGET_SOLUTION, planCost: 2, verifierCost: 2, accepted: true },
  ];
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

function singleReceipt(receipts: Receipt[], status: "accept" | "reject" | "abstain"): Receipt {
  const rows = receipts.filter((receipt) => receipt.hardResult.result === status);
  if (rows.length !== 1) {
    throw new Error(`expected exactly one ${status} receipt, got ${rows.length}`);
  }
  return rows[0];
}

async function replayRollbackRate(engine: { replayAudit(seed: VerifierBudgetState): Promise<VerifierBudgetState>; rollbackAudit(seed: VerifierBudgetState): Promise<VerifierBudgetState> }): Promise<number> {
  try {
    await engine.replayAudit({ committedActions: [] });
    const rolledBack = await engine.rollbackAudit({ committedActions: [] });
    return JSON.stringify(rolledBack) === JSON.stringify({ committedActions: [] }) ? 1 : 0;
  } catch (_error) {
    return 0;
  }
}
