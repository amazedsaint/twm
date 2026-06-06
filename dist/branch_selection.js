import {
                          
               
                             
                      
  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import {
  BranchRuntime,
  auditBranchSelection,
  branchSelectionCertificateHash,
  buildBranchSelectionCertificate,
  validateBranchSelectionCertificate,
} from "./branch.js";

                                        
                        
                      
                        
                        
                         
                               
                                
                     
                                     
                               
                            
                      
                          
                                         
                                  
                        
                             
                       
                             
 

                              
                
                
                    
 

class CounterAdapter                                                              {
  verifierId = "branch_counter_oracle";
  verifierVersion = "1.0";

  verify(candidate                                    )                     {
    const cost = candidate.payload.cost ?? 0;
    return candidate.payload.delta <= 5
      ? hardAccept(this.verifierId, this.verifierVersion, { cost })
      : hardReject(this.verifierId, this.verifierVersion, { delta: candidate.payload.delta, limit: 5 }, { cost });
  }

  applyCommit(state        , candidate                                    )         {
    return state + candidate.payload.delta;
  }

  replay(state        , receipt         )         {
    const payload = (receipt.replayBundle                                            ).candidatePayload;
    return state + payload.delta;
  }

  rollback(_state        , receipt         )         {
    return (receipt.rollbackBundle                        ).preState;
  }
}

class CounterProjector {
  project(_state        , trace                              )                                     {
    const payload = trace.actions[trace.actions.length - 1]                      ;
    return makeCandidate({ ...payload }, "counter.delta", "counter.delta.v1");
  }
}

export async function runBranchSelectionBenchmark()                                 {
  const engine = new TransactionEngine(new CounterAdapter(), new Ledger());
  const traces = [
    makeTrace({
      branchId: "rejected-soft-favorite",
      actions: [{ delta: 9, cost: 1, softRank: 999 }],
      seeds: [1],
      modelVersion: "branch.selection.v1",
    }),
    makeTrace({
      branchId: "accepted-loser",
      actions: [{ delta: 1, cost: 4 }],
      seeds: [2],
      modelVersion: "branch.selection.v1",
    }),
    makeTrace({
      branchId: "accepted-winner",
      actions: [{ delta: 2, cost: 2 }],
      seeds: [3],
      modelVersion: "branch.selection.v1",
    }),
  ];
  const outcome = await new BranchRuntime(engine, new CounterProjector()).step(0, traces);
  const receipts = outcome.receipts             ;
  const certificate = await buildBranchSelectionCertificate(receipts, { verifierCallCount: outcome.verifierCalls });
  const tampered = { ...certificate, committedIndex: 0, certificateHash: "" };
  tampered.certificateHash = await branchSelectionCertificateHash(tampered);

  const invalidEngine = new TransactionEngine(new CounterAdapter(), new Ledger());
  const invalidOutcome = await new BranchRuntime(
    invalidEngine,
    new CounterProjector(),
    { choose: (verified) => verified.length },
  ).step(0, [
    makeTrace({ branchId: "bad-ranker-a", actions: [{ delta: 1, cost: 1 }], seeds: [4] }),
    makeTrace({ branchId: "bad-ranker-b", actions: [{ delta: 2, cost: 2 }], seeds: [5] }),
  ]);
  const invalidCertificate = await buildBranchSelectionCertificate(
    invalidOutcome.receipts             ,
    { verifierCallCount: invalidOutcome.verifierCalls },
  );
  const replayChecks = [
    await replayRollbackOk(engine, 0, outcome.state),
    await replayRollbackOk(invalidEngine, 0, invalidOutcome.state),
  ];

  return {
    schemaVersion: certificate.schemaVersion,
    branchCount: certificate.branchCount,
    acceptedCount: certificate.acceptedIndices.length,
    rejectedCount: certificate.rejectedIndices.length,
    abstainedCount: certificate.abstainedIndices.length,
    selectedIndex: certificate.selectedIndex,
    committedIndex: certificate.committedIndex,
    loserCount: certificate.loserIndices.length,
    hardRejectSoftRankBlocked: engine.ledger.rows[0].hardResult.result === "reject"
      && !engine.ledger.rows[0].committed
      && engine.ledger.rows[0].commitDecision === "hard_reject",
    rankAfterHardFilter: (
      certificate.selectedIndex !== null
      && certificate.committedIndex !== null
      && certificate.acceptedIndices.includes(certificate.selectedIndex)
      && certificate.acceptedIndices.includes(certificate.committedIndex)
      && !certificate.acceptedIndices.includes(0)
    ),
    certificateValid: await validateBranchSelectionCertificate(certificate),
    auditValid: await auditBranchSelection(receipts, certificate),
    tamperDetected: !await validateBranchSelectionCertificate(tampered),
    invalidRankerCertificateValid: await validateBranchSelectionCertificate(invalidCertificate),
    invalidRankerCommitted: invalidOutcome.committed,
    verifierCalls: outcome.verifierCalls,
    invalidCommitCount: engine.invalidCommitCount + invalidEngine.invalidCommitCount,
    ledgerAudit: await engine.ledger.audit() && await invalidEngine.ledger.audit(),
    replayRollbackRate: replayChecks.filter(Boolean).length / replayChecks.length,
  };
}

async function replayRollbackOk(
  engine                                               ,
  seedState        ,
  expectedState        ,
)                   {
  if (!await engine.ledger.audit()) {
    return false;
  }
  return await engine.replayAudit(seedState) === expectedState && await engine.rollbackAudit(seedState) === seedState;
}
