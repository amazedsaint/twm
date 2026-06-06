import {
  type HardVerifierResult,
  type ProposalTrace,
  type Receipt,
  type ReplayRollbackAdapter,
  type TypedCandidate,
  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { BranchRuntime } from "./branch.js";
import { CounterfactualRollbackRanker, ReceiptRanker } from "./learning.js";

export const COUNTERFACTUAL_CONTEXT = "counterfactual-route";

export interface CounterfactualChoicePayload {
  context: string;
  action: string;
  cost: number;
  risk: number;
}

export interface CounterfactualChoiceState {
  committedActions: string[];
}

export interface CounterfactualRollbackReport {
  episodes: number;
  candidateCount: number;
  committedAction: string;
  staticTopAction: string;
  receiptRankerTopAction: string;
  counterfactualTopAction: string;
  receiptRankerWinnerRank: number;
  counterfactualWinnerRank: number;
  rolledBackLoserCount: number;
  hardRejectCount: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
  invalidCommitCount: number;
}

export const DEFAULT_COUNTERFACTUAL_ACTIONS: CounterfactualChoicePayload[] = [
  { context: COUNTERFACTUAL_CONTEXT, action: "a_slow", cost: 2, risk: 0.10 },
  { context: COUNTERFACTUAL_CONTEXT, action: "b_fast", cost: 1, risk: 0.20 },
  { context: COUNTERFACTUAL_CONTEXT, action: "c_unsafe", cost: 0, risk: 1.20 },
];

export class CounterfactualChoiceAdapter implements ReplayRollbackAdapter<CounterfactualChoiceState, CounterfactualChoicePayload> {
  verifierId = "counterfactual_choice_oracle";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<CounterfactualChoicePayload>): HardVerifierResult {
    const payload = normalizeCounterfactualChoicePayload(candidate.payload);
    const metadata = { cost: payload.cost, risk: payload.risk, action: payload.action };
    if (payload.risk > 1) {
      return hardReject(this.verifierId, this.verifierVersion, { kind: "risk_limit", risk: payload.risk, limit: 1 }, metadata);
    }
    return hardAccept(this.verifierId, this.verifierVersion, metadata);
  }

  applyCommit(state: CounterfactualChoiceState, candidate: TypedCandidate<CounterfactualChoicePayload>): CounterfactualChoiceState {
    const current = normalizeCounterfactualChoiceState(state);
    const payload = normalizeCounterfactualChoicePayload(candidate.payload);
    return { committedActions: [...current.committedActions, payload.action] };
  }

  replay(state: CounterfactualChoiceState, receipt: Receipt): CounterfactualChoiceState {
    const current = normalizeCounterfactualChoiceState(state);
    const payload = normalizeCounterfactualChoicePayload((receipt.replayBundle as { candidatePayload: CounterfactualChoicePayload }).candidatePayload);
    return { committedActions: [...current.committedActions, payload.action] };
  }

  rollback(_state: CounterfactualChoiceState, receipt: Receipt): CounterfactualChoiceState {
    return normalizeCounterfactualChoiceState((receipt.rollbackBundle as { preState: CounterfactualChoiceState }).preState);
  }
}

export class CounterfactualChoiceProjector {
  project(_state: CounterfactualChoiceState, trace: ProposalTrace): TypedCandidate<CounterfactualChoicePayload> {
    return makeCounterfactualChoiceCandidate(trace.actions.at(-1) as CounterfactualChoicePayload);
  }
}

export function normalizeCounterfactualChoiceState(state: CounterfactualChoiceState | Record<string, unknown>): CounterfactualChoiceState {
  const raw = state as Record<string, unknown>;
  const committedActions = raw.committedActions ?? raw.committed_actions ?? [];
  if (!Array.isArray(committedActions)) {
    throw new RangeError("committedActions must be an array");
  }
  return { committedActions: committedActions.map((action) => String(action)) };
}

export function normalizeCounterfactualChoicePayload(payload: CounterfactualChoicePayload | Record<string, unknown>): CounterfactualChoicePayload {
  const raw = payload as Record<string, unknown>;
  const action = String(raw.action);
  const context = String(raw.context ?? COUNTERFACTUAL_CONTEXT);
  const cost = Number(raw.cost);
  const risk = Number(raw.risk);
  if (!action) {
    throw new RangeError("action must be non-empty");
  }
  if (!Number.isInteger(cost) || cost < 0) {
    throw new RangeError("cost must be a non-negative integer");
  }
  if (!Number.isFinite(risk) || risk < 0) {
    throw new RangeError("risk must be a non-negative number");
  }
  return { context, action, cost, risk };
}

export function makeCounterfactualChoiceCandidate(payload: CounterfactualChoicePayload | Record<string, unknown>): TypedCandidate<CounterfactualChoicePayload> {
  return makeCandidate(
    normalizeCounterfactualChoicePayload(payload),
    "counterfactual.choice",
    "counterfactual.choice.v1",
  );
}

export function makeCounterfactualTraces(episode: number, actions = DEFAULT_COUNTERFACTUAL_ACTIONS): ProposalTrace[] {
  return actions.map((action) => makeTrace({
    branchId: `counterfactual-${episode}-${action.action}`,
    actions: [action],
    seeds: ["counterfactual", episode, action.action],
    modelVersion: "counterfactual.rollback.v1",
  }));
}

export async function runCounterfactualRollbackBenchmark(episodes = 32): Promise<CounterfactualRollbackReport> {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  const engine = new TransactionEngine(new CounterfactualChoiceAdapter(), new Ledger());
  const runtime = new BranchRuntime(engine, new CounterfactualChoiceProjector());
  const receiptRanker = new ReceiptRanker();
  const counterfactualRanker = new CounterfactualRollbackRanker();
  const seed: CounterfactualChoiceState = { committedActions: [] };
  let state = seed;
  for (let episode = 0; episode < episodes; episode += 1) {
    const outcome = await runtime.step(state, makeCounterfactualTraces(episode));
    state = normalizeCounterfactualChoiceState(outcome.state);
    for (const receipt of outcome.receipts as Receipt[]) {
      receiptRanker.update(receipt);
      counterfactualRanker.update(receipt);
    }
  }
  const actions = DEFAULT_COUNTERFACTUAL_ACTIONS.map((action) => action.action);
  const committedAction = "b_fast";
  const receiptOrder = receiptRanker.rank(COUNTERFACTUAL_CONTEXT, actions);
  const counterfactualOrder = counterfactualRanker.rank(COUNTERFACTUAL_CONTEXT, actions);
  const ledgerAudit = await engine.ledger.audit();
  let replayRollbackRate = 0;
  if (ledgerAudit) {
    try {
      const replayState = normalizeCounterfactualChoiceState(await engine.replayAudit(seed));
      const rollbackState = normalizeCounterfactualChoiceState(await engine.rollbackAudit(seed));
      replayRollbackRate = JSON.stringify(replayState) === JSON.stringify(state) && JSON.stringify(rollbackState) === JSON.stringify(seed) ? 1 : 0;
    } catch (_error) {
      replayRollbackRate = 0;
    }
  }
  return {
    episodes,
    candidateCount: actions.length,
    committedAction,
    staticTopAction: actions[0],
    receiptRankerTopAction: receiptOrder[0],
    counterfactualTopAction: counterfactualOrder[0],
    receiptRankerWinnerRank: receiptOrder.indexOf(committedAction) + 1,
    counterfactualWinnerRank: counterfactualOrder.indexOf(committedAction) + 1,
    rolledBackLoserCount: counterfactualRanker.stats(COUNTERFACTUAL_CONTEXT, "a_slow").rolledBack,
    hardRejectCount: counterfactualRanker.stats(COUNTERFACTUAL_CONTEXT, "c_unsafe").rejected,
    ledgerAudit,
    replayRollbackRate,
    invalidCommitCount: engine.ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  };
}
