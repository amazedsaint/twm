import {
                          
               
                             
                      
  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { ReceiptRanker, HyperdimensionalMemory } from "./learning.js";
import { oneHotUpdates, shapeRankPreflight } from "./preflight.js";

                                        
                  
                 
                
                 
 

                             
                 
                  
                  
                 
                  
 

                                     
                
                   
 

                              
                                   
                                          
                                      
                                    
                                           
                                       
                         
                     
                          
                      
                          
                           
                                  
                                   
                                     
                                      
                       
                             
 

                                                                                                        

export class ShapeGuessAdapter                                                                     {
  verifierId = "shape_oracle";
  verifierVersion = "1.0";

  verify(candidate                                       )                     {
    const { guess, defect } = candidate.payload;
    if (guess === defect) {
      return hardAccept(this.verifierId, this.verifierVersion, { cost: 1 });
    }
    return hardReject(this.verifierId, this.verifierVersion, { miss: true, guess }, { cost: 1 });
  }

  applyCommit(state            , candidate                                       )             {
    const { guess, defect } = candidate.payload;
    return { ...state, solved: true, guess, defect };
  }

  replay(state            , receipt         )             {
    const payload = (receipt.replayBundle                                               ).candidatePayload;
    return { ...state, solved: true, guess: payload.guess, defect: payload.defect };
  }

  rollback(_state            , receipt         )             {
    return (receipt.rollbackBundle                            ).preState;
  }
}

export async function runShapeConditionality(seed = 7, episodes = 96, labelCount = 24)                       {
  const rng = mulberry32(seed);
  const labels = Array.from({ length: labelCount }, (_unused, idx) => idx);
  const lowMotifs = [1, 1, 1, 3, 3, 7];
  const lowDefects = Array.from({ length: episodes }, () => lowMotifs[Math.floor(rng() * lowMotifs.length)]);
  const highDefects = Array.from({ length: episodes }, () => Math.floor(rng() * labelCount));
  const randomOrder = shuffle(labels, seed + 1);
  const staticOrder               = () => randomOrder;

  const lowRandomLedger = new Ledger();
  const highRandomLedger = new Ledger();
  const lowRandomEngine = new TransactionEngine(new ShapeGuessAdapter(), lowRandomLedger);
  const highRandomEngine = new TransactionEngine(new ShapeGuessAdapter(), highRandomLedger);
  const lowRandom = await runOrder("low", lowDefects, labels, staticOrder, lowRandomEngine);
  const highRandom = await runOrder("high", highDefects, labels, staticOrder, highRandomEngine);

  const lowReceiptRanker = new ReceiptRanker();
  const highReceiptRanker = new ReceiptRanker();
  const lowReceiptLedger = new Ledger();
  const highReceiptLedger = new Ledger();
  const lowReceiptEngine = new TransactionEngine(new ShapeGuessAdapter(), lowReceiptLedger);
  const highReceiptEngine = new TransactionEngine(new ShapeGuessAdapter(), highReceiptLedger);
  const lowReceipt = await runOrder(
    "low",
    lowDefects,
    labels,
    (family, _episode, candidates) => lowReceiptRanker.rank(family, candidates),
    lowReceiptEngine,
    { ranker: lowReceiptRanker },
  );
  const highReceipt = await runOrder(
    "high",
    highDefects,
    labels,
    (family, _episode, candidates) => highReceiptRanker.rank(family, candidates),
    highReceiptEngine,
    { ranker: highReceiptRanker },
  );

  const lowHdcRanker = new ReceiptRanker();
  const highHdcRanker = new ReceiptRanker();
  const lowHdcMemory = new HyperdimensionalMemory(256);
  const highHdcMemory = new HyperdimensionalMemory(256);
  const lowHdcLedger = new Ledger();
  const highHdcLedger = new Ledger();
  const lowHdcEngine = new TransactionEngine(new ShapeGuessAdapter(), lowHdcLedger);
  const highHdcEngine = new TransactionEngine(new ShapeGuessAdapter(), highHdcLedger);
  const lowHdc = await runOrder(
    "low",
    lowDefects,
    labels,
    (family, _episode, candidates) => hdcRank(family, candidates, lowHdcMemory, lowHdcRanker),
    lowHdcEngine,
    { ranker: lowHdcRanker, memory: lowHdcMemory },
  );
  const highHdc = await runOrder(
    "high",
    highDefects,
    labels,
    (family, _episode, candidates) => hdcRank(family, candidates, highHdcMemory, highHdcRanker),
    highHdcEngine,
    { ranker: highHdcRanker, memory: highHdcMemory },
  );

  const lowRandomCps = callsPerSuccess(lowRandom);
  const lowReceiptCps = callsPerSuccess(lowReceipt);
  const lowHdcCps = callsPerSuccess(lowHdc);
  const highRandomCps = callsPerSuccess(highRandom);
  const highReceiptCps = callsPerSuccess(highReceipt);
  const highHdcCps = callsPerSuccess(highHdc);
  const lowPreflight = shapeRankPreflight(oneHotUpdates(lowDefects, labelCount), undefined, 4);
  const highPreflight = shapeRankPreflight(oneHotUpdates(highDefects, labelCount), undefined, 4);
  const ledgers = [
    lowRandomLedger,
    highRandomLedger,
    lowReceiptLedger,
    highReceiptLedger,
    lowHdcLedger,
    highHdcLedger,
  ];

  return {
    lowRandomCallsPerSuccess: lowRandomCps,
    lowReceiptMemoryCallsPerSuccess: lowReceiptCps,
    lowHdcMemoryCallsPerSuccess: lowHdcCps,
    highRandomCallsPerSuccess: highRandomCps,
    highReceiptMemoryCallsPerSuccess: highReceiptCps,
    highHdcMemoryCallsPerSuccess: highHdcCps,
    lowReceiptGain: lowRandomCps / lowReceiptCps,
    lowHdcGain: lowRandomCps / lowHdcCps,
    highReceiptGain: highRandomCps / highReceiptCps,
    highHdcGain: highRandomCps / highHdcCps,
    lowPreflightR90: lowPreflight.r90,
    highPreflightR90: highPreflight.r90,
    lowPreflightFitsBudget: lowPreflight.fitsBudget,
    highPreflightFitsBudget: highPreflight.fitsBudget,
    lowPreflightEnergyAtBudget: lowPreflight.energyAtBudget,
    highPreflightEnergyAtBudget: highPreflight.energyAtBudget,
    ledgerAudit: (await Promise.all(ledgers.map((ledger) => ledger.audit()))).every(Boolean),
    invalidCommitCount: invalidCommits(ledgers),
  };
}

async function runOrder(
  family        ,
  defects          ,
  labels          ,
  orderer              ,
  engine                                                      ,
  learners                                                              = {},
)                                {
  const results                       = [];
  for (let episode = 0; episode < defects.length; episode += 1) {
    const defect = defects[episode];
    const state             = { family, episode, solved: false };
    let calls = 0;
    let success = false;
    const order = await orderer(family, episode, labels);
    for (const guess of order) {
      calls += 1;
      const trace = makeTrace({
        branchId: `${family}-${episode}-${guess}`,
        actions: [guess],
        seeds: [episode, guess],
        modelVersion: "shape.static.v1",
      });
      const candidate = makeCandidate                       (
        { context: family, action: guess, guess, defect },
        "shape.guess",
        "shape.guess.v1",
      );
      const outcome = await engine.transact(state, trace, candidate);
      learners.ranker?.update(outcome.receipt);
      await learners.memory?.add(outcome.receipt);
      if (outcome.committed) {
        success = true;
        break;
      }
    }
    results.push({ calls, success });
  }
  return results;
}

async function hdcRank(
  context        ,
  candidates          ,
  memory                        ,
  fallback               ,
)                    {
  const fallbackOrder = fallback.rank(context, candidates);
  if (memory.rows.length === 0) {
    return fallbackOrder;
  }
  const fallbackIndex = new Map(fallbackOrder.map((candidate, idx) => [candidate, idx]));
  const accepted = new Map                ();
  const rejected = new Map                ();
  const neighbors = await memory.nearest({ context }, Math.min(memory.rows.length, 64));
  for (const receipt of neighbors) {
    const action = shapeAction(receipt);
    if (action === null) {
      continue;
    }
    if (receipt.hardResult.result === "accept") {
      accepted.set(action, (accepted.get(action) ?? 0) + 1);
    } else if (receipt.hardResult.result === "reject") {
      rejected.set(action, (rejected.get(action) ?? 0) + 1);
    }
  }
  return [...candidates].sort((a, b) => {
    const acceptedDiff = (accepted.get(b) ?? 0) - (accepted.get(a) ?? 0);
    if (acceptedDiff !== 0) {
      return acceptedDiff;
    }
    const rejectedDiff = (rejected.get(a) ?? 0) - (rejected.get(b) ?? 0);
    if (rejectedDiff !== 0) {
      return rejectedDiff;
    }
    return (fallbackIndex.get(a) ?? Number.MAX_SAFE_INTEGER) - (fallbackIndex.get(b) ?? Number.MAX_SAFE_INTEGER);
  });
}

function shapeAction(receipt         )                {
  const replayBundle = receipt.replayBundle                                                         ;
  const action = replayBundle.candidatePayload?.action ?? replayBundle.candidatePayload?.guess;
  return typeof action === "number" && Number.isInteger(action) ? action : null;
}

function callsPerSuccess(results                      )         {
  const successes = results.filter((row) => row.success).length;
  const calls = results.reduce((total, row) => total + row.calls, 0);
  return successes === 0 ? Number.POSITIVE_INFINITY : calls / successes;
}

function invalidCommits(ledgers          )         {
  return ledgers.reduce(
    (total, ledger) => total + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
    0,
  );
}

function shuffle(values          , seed        )           {
  const rng = mulberry32(seed);
  const out = [...values];
  for (let idx = out.length - 1; idx > 0; idx -= 1) {
    const swap = Math.floor(rng() * (idx + 1));
    [out[idx], out[swap]] = [out[swap], out[idx]];
  }
  return out;
}

function mulberry32(seed        )               {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let next = value;
    next = Math.imul(next ^ (next >>> 15), next | 1);
    next ^= next + Math.imul(next ^ (next >>> 7), next | 61);
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296;
  };
}
