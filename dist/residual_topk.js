import { TransactionEngine, makeTrace } from "./core.js";
import {
                      
  InventoryReservationAdapter,
  makeReservationCandidate,
  normalizeInventoryState,
} from "./operations.js";
import {
                      
  ResidualTaxonomyMemory,
  residualSignalFromReceipt,
} from "./residuals.js";
import {                            ResidualTopKSubmitter } from "./topk.js";

export const RESIDUAL_TOPK_ORDER = [8, 7, 5, 4]         ;
export const RESIDUAL_TOPK_LIMIT = 2;

                                     
                               
                            
                         
               
                              
                             
                                
                                    
                                   
                                       
                                      
                            
                       
                             
                             
 

export async function runResidualTopKBenchmark()                              {
  const seedState                 = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const memory = new ResidualTaxonomyMemory();

  const trainingEngine = new TransactionEngine(new InventoryReservationAdapter());
  const trainingCandidate = await makeReservationCandidate(seedState, "train-over", "widget", 8, 8, "topk-train");
  const training = await trainingEngine.transact(
    seedState,
    makeTrace({ branchId: "topk-train", actions: [{ quantity: 8 }], modelVersion: "residual.topk.train.v1" }),
    trainingCandidate,
  );
  const signal = await residualSignalFromReceipt(training.receipt, { sourceDomain: "operations" });
  await memory.update(signal);

  const unrankedEngine = new TransactionEngine(new InventoryReservationAdapter());
  const unranked = await new ResidualTopKSubmitter(unrankedEngine).submit(
    seedState,
    await repairOptions(seedState, "unranked"),
    { topK: RESIDUAL_TOPK_LIMIT, tracePrefix: "topk-unranked" },
  );

  const rankedEngine = new TransactionEngine(new InventoryReservationAdapter());
  const residualRanked = await new ResidualTopKSubmitter(rankedEngine, memory).submit(
    seedState,
    await repairOptions(seedState, "ranked"),
    { topK: RESIDUAL_TOPK_LIMIT, tracePrefix: "topk-ranked", residualSignal: signal },
  );
  const committedState = normalizeInventoryState(residualRanked.state);

  let replayRollbackRate = 0;
  if (await rankedEngine.ledger.audit()) {
    try {
      await rankedEngine.replayAudit(seedState);
      replayRollbackRate = JSON.stringify(await rankedEngine.rollbackAudit(seedState)) === JSON.stringify(seedState) ? 1 : 0;
    } catch (_error) {
      replayRollbackRate = 0;
    }
  }

  return {
    trainingResidualKind: signal.kind,
    learnedRepairHint: memory.topRepairHint(signal.kind) ?? "",
    candidateCount: RESIDUAL_TOPK_ORDER.length,
    topK: RESIDUAL_TOPK_LIMIT,
    unrankedSubmitted: unranked.submittedLabels,
    unrankedCommitted: unranked.committed,
    unrankedVerifierCalls: unranked.verifierCalls,
    residualRankedSubmitted: residualRanked.submittedLabels,
    residualRankedCommitted: residualRanked.committed,
    residualRankedCommittedLabel: residualRanked.committedLabel,
    residualRankedVerifierCalls: residualRanked.verifierCalls,
    callsToCommitGain: unranked.verifierCalls / residualRanked.verifierCalls,
    ledgerAudit: await rankedEngine.ledger.audit() && committedState.stock.widget === 0,
    replayRollbackRate,
    invalidCommitCount: rankedEngine.invalidCommitCount + unrankedEngine.invalidCommitCount + trainingEngine.invalidCommitCount,
  };
}

async function repairOptions(
  state                ,
  prefix        ,
)                                                                                                                       {
  const rows                                   = [];
  for (let idx = 0; idx < RESIDUAL_TOPK_ORDER.length; idx += 1) {
    const quantity = RESIDUAL_TOPK_ORDER[idx];
    rows.push({
      label: `quantity-${quantity}`,
      candidate: await makeReservationCandidate(
        state,
        `${prefix}-q${quantity}`,
        "widget",
        8,
        quantity,
        "topk-repair",
        idx + 1,
      ),
      repairHint: `quantity=${quantity}`,
      baseRank: idx,
    });
  }
  return rows;
}
