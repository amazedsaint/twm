import {
  auditParallelReplay,
  buildParallelReplayCertificate,
  parallelReplay,
  randomizedParallelReplayTrials,
  sequentialReplay,
  validateParallelReplayCertificate,
} from "./parallel.js";
import { canonicalJson, stableHash } from "./canonical.js";
import { BlockToken, DeltaToken } from "./reversible.js";

                                       
                        
                     
                     
                        
                        
                      
                                           
                                         
                                    
                            
                            
                      
                          
                               
                                  
                             
 

export async function runParallelReplayBenchmark()                                {
  const state = demoState();
  const tokens = demoTokens();
  const certificate = await buildParallelReplayCertificate(state, tokens);
  const sequentialState = sequentialReplay(state, tokens);
  const parallelState = parallelReplay(state, tokens, certificate.batches);
  const inverseRoundtrip = canonicalJson(BlockToken.of(tokens).inverse().apply(sequentialState)) === canonicalJson(state);
  const tampered = {
    ...certificate,
    parallelStateHash: await stableHash({ tampered: true }),
  };
  const randomized = await randomizedParallelReplayTrials();

  return {
    schemaVersion: certificate.schemaVersion,
    tokenCount: certificate.tokenCount,
    batchCount: certificate.batchCount,
    maxBatchWidth: certificate.maxBatchWidth,
    conflictCount: certificate.conflictCount,
    batches: certificate.batches,
    sequentialState,
    parallelState,
    parallelEqualsSequential: canonicalJson(sequentialState) === canonicalJson(parallelState),
    inverseRoundtrip,
    certificateValid: await validateParallelReplayCertificate(certificate),
    auditValid: await auditParallelReplay(state, tokens, certificate),
    tamperDetected: !await auditParallelReplay(state, tokens, tampered),
    randomizedTrialCount: randomized.trials,
    randomizedMismatchCount: randomized.mismatches,
    invalidCommitCount: 0,
  };
}

export function demoState()                         {
  return { a: 0, b: 0, c: 0, d: 0 };
}

export function demoTokens()               {
  return [
    new DeltaToken("a", 0, 1),
    new DeltaToken("b", 0, 2),
    new DeltaToken("a", 1, 3),
    new DeltaToken("c", 0, 4),
    new DeltaToken("b", 2, 5),
    new DeltaToken("d", 0, 6),
  ];
}
