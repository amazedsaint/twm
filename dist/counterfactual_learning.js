import {
                          
                     
               
                             
                      
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

                                              
                  
                 
               
               
 

                                            
                             
 

                                               
                   
                         
                          
                          
                                 
                                  
                                  
                                   
                               
                          
                       
                             
                             
 

export const DEFAULT_COUNTERFACTUAL_ACTIONS                                = [
  { context: COUNTERFACTUAL_CONTEXT, action: "a_slow", cost: 2, risk: 0.10 },
  { context: COUNTERFACTUAL_CONTEXT, action: "b_fast", cost: 1, risk: 0.20 },
  { context: COUNTERFACTUAL_CONTEXT, action: "c_unsafe", cost: 0, risk: 1.20 },
];

export class CounterfactualChoiceAdapter                                                                                          {
  verifierId = "counterfactual_choice_oracle";
  verifierVersion = "1.0";

  verify(candidate                                             )                     {
    const payload = normalizeCounterfactualChoicePayload(candidate.payload);
    const metadata = { cost: payload.cost, risk: payload.risk, action: payload.action };
    if (payload.risk > 1) {
      return hardReject(this.verifierId, this.verifierVersion, { kind: "risk_limit", risk: payload.risk, limit: 1 }, metadata);
    }
    return hardAccept(this.verifierId, this.verifierVersion, metadata);
  }

  applyCommit(state                           , candidate                                             )                            {
    const current = normalizeCounterfactualChoiceState(state);
    const payload = normalizeCounterfactualChoicePayload(candidate.payload);
    return { committedActions: [...current.committedActions, payload.action] };
  }

  replay(state                           , receipt         )                            {
    const current = normalizeCounterfactualChoiceState(state);
    const payload = normalizeCounterfactualChoicePayload((receipt.replayBundle                                                     ).candidatePayload);
    return { committedActions: [...current.committedActions, payload.action] };
  }

  rollback(_state                           , receipt         )                            {
    return normalizeCounterfactualChoiceState((receipt.rollbackBundle                                           ).preState);
  }
}

export class CounterfactualChoiceProjector {
  project(_state                           , trace               )                                              {
    return makeCounterfactualChoiceCandidate(trace.actions.at(-1)                               );
  }
}

export function normalizeCounterfactualChoiceState(state                                                     )                            {
  const raw = state                           ;
  const committedActions = raw.committedActions ?? raw.committed_actions ?? [];
  if (!Array.isArray(committedActions)) {
    throw new RangeError("committedActions must be an array");
  }
  return { committedActions: committedActions.map((action) => String(action)) };
}

export function normalizeCounterfactualChoicePayload(payload                                                       )                              {
  const raw = payload                           ;
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

export function makeCounterfactualChoiceCandidate(payload                                                       )                                              {
  return makeCandidate(
    normalizeCounterfactualChoicePayload(payload),
    "counterfactual.choice",
    "counterfactual.choice.v1",
  );
}

export function makeCounterfactualTraces(episode        , actions = DEFAULT_COUNTERFACTUAL_ACTIONS)                  {
  return actions.map((action) => makeTrace({
    branchId: `counterfactual-${episode}-${action.action}`,
    actions: [action],
    seeds: ["counterfactual", episode, action.action],
    modelVersion: "counterfactual.rollback.v1",
  }));
}

export async function runCounterfactualRollbackBenchmark(episodes = 32)                                        {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  const engine = new TransactionEngine(new CounterfactualChoiceAdapter(), new Ledger());
  const runtime = new BranchRuntime(engine, new CounterfactualChoiceProjector());
  const receiptRanker = new ReceiptRanker();
  const counterfactualRanker = new CounterfactualRollbackRanker();
  const seed                            = { committedActions: [] };
  let state = seed;
  for (let episode = 0; episode < episodes; episode += 1) {
    const outcome = await runtime.step(state, makeCounterfactualTraces(episode));
    state = normalizeCounterfactualChoiceState(outcome.state);
    for (const receipt of outcome.receipts             ) {
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
