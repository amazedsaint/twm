import { canonicalJson, stableHash } from "./canonical.js";
import { BlockToken, DeltaToken } from "./reversible.js";
import {
  auditCircularTokenLog,
  buildCircularTokenLogCertificate,
  randomizedCircularTokenLogTrials,
  replayCircularTokenLog,
  validateCircularTokenLogCertificate,
} from "./token_log.js";

                                         
                        
                   
                          
                               
                      
                              
                                   
                            
                                  
                               
                                     
                                          
                               
                            
                            
                      
                          
                               
                                  
                             
 

export async function runCircularTokenLogBenchmark()                                  {
  const state = demoCircularLogState();
  const tokens = demoCircularLogTokens();
  const capacity = 3;
  const certificate = await buildCircularTokenLogCertificate(state, tokens, { capacity });
  const fullState = BlockToken.of(tokens).apply(state);
  const compactedState = replayCircularTokenLog(state, certificate.compactedTokens, certificate.suffixTokens);
  const tampered = {
    ...certificate,
    finalStateHash: await stableHash({ tampered: true }),
    certificateHash: "",
  };
  tampered.certificateHash = await stableHash({
    schemaVersion: tampered.schemaVersion,
    capacity: tampered.capacity,
    totalTokenCount: tampered.totalTokenCount,
    compactedPrefixCount: tampered.compactedPrefixCount,
    suffixCount: tampered.suffixCount,
    compactedDeltaCount: tampered.compactedDeltaCount,
    compactedTokens: tampered.compactedTokens,
    suffixTokens: tampered.suffixTokens,
    baseStateHash: tampered.baseStateHash,
    compactedStateHash: tampered.compactedStateHash,
    finalStateHash: tampered.finalStateHash,
    compactedTokenHash: tampered.compactedTokenHash,
    suffixTokenHash: tampered.suffixTokenHash,
  });
  const randomized = await randomizedCircularTokenLogTrials();
  const retainedReplayTokenCount = certificate.compactedDeltaCount + certificate.suffixCount;

  return {
    schemaVersion: certificate.schemaVersion,
    capacity: certificate.capacity,
    totalTokenCount: certificate.totalTokenCount,
    compactedPrefixCount: certificate.compactedPrefixCount,
    suffixCount: certificate.suffixCount,
    compactedDeltaCount: certificate.compactedDeltaCount,
    retainedReplayTokenCount,
    replayTokensSaved: certificate.totalTokenCount - retainedReplayTokenCount,
    compactedTokenSummary: certificate.compactedTokens.map(tokenSummary),
    suffixTokenSummary: certificate.suffixTokens.map(tokenSummary),
    fullState,
    compactedState,
    fullEqualsCompacted: canonicalJson(fullState) === canonicalJson(compactedState),
    inverseRoundtrip: await auditCircularTokenLog(state, certificate),
    certificateValid: await validateCircularTokenLogCertificate(certificate),
    auditValid: await auditCircularTokenLog(state, certificate, tokens),
    tamperDetected: !await auditCircularTokenLog(state, tampered, tokens),
    randomizedTrialCount: randomized.trials,
    randomizedMismatchCount: randomized.mismatches,
    invalidCommitCount: 0,
  };
}

export function demoCircularLogState()                         {
  return { a: 0, b: 0, c: 0, d: 0 };
}

export function demoCircularLogTokens()               {
  return [
    new DeltaToken("a", 0, 1),
    new DeltaToken("b", 0, 2),
    new DeltaToken("a", 1, 3),
    new DeltaToken("c", 0, 4),
    new DeltaToken("a", 3, 0),
    new DeltaToken("b", 2, 5),
    new DeltaToken("d", 0, 6),
    new DeltaToken("a", 0, 7),
  ];
}

function tokenSummary(token            )         {
  return `${token.key}:${String(token.before)}->${String(token.after)}`;
}
