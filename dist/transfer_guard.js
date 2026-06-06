import {                       ReceiptBudgetPolicy } from "./budget_policy.js";
import {               TransactionEngine, makeTrace } from "./core.js";
import {
                                   
                      
  InventoryReservationAdapter,
  makeReservationCandidate,
} from "./operations.js";
import {
  TRANSFER_GUARD_SNAPSHOT_SCHEMA,
  TransferGuardMemory,
  buildTransferEvaluationCertificate,
  validateTransferGuardDecision,
  validateTransferGuardSnapshot,
} from "./transfer.js";

export const TRANSFER_GUARD_BUDGET = 1;

                                      
                        
                         
                         
                                   
                                 
                              
                            
                           
                              
                              
                                
                            
                            
                                     
                                   
                                
                          
                       
                          
                             
                       
                             
 

export async function runTransferGuardBenchmark()                               {
  const sourceState                 = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const targetState                 = { stock: { widget: 2 }, reserved: { widget: 0 }, committedOrders: [] };

  const policy = new ReceiptBudgetPolicy();
  const sourceEngine = new TransactionEngine(new InventoryReservationAdapter());
  const sourceReceipt = (await sourceEngine.transact(
    sourceState,
    makeTrace({
      branchId: "transfer-guard-source-quantity-5",
      actions: [{ label: "quantity-5" }],
      modelVersion: "transfer.guard.source.v1",
    }),
    await makeReservationCandidate(sourceState, "guard-source-q5", "widget", 5, 5, "transfer-guard-source", 1),
  )).receipt;
  policy.update("quantity-5", sourceReceipt);
  const candidates = await targetCandidates(targetState);

  const evalTransferEngine = new TransactionEngine(new InventoryReservationAdapter());
  const evalTransfer = await policy.submit(evalTransferEngine, targetState, candidates, {
    budget: TRANSFER_GUARD_BUDGET,
    tracePrefix: "transfer-guard-eval-transfer",
    modelVersion: "transfer.guard.eval_transfer.v1",
  });
  const evalBaselineEngine = new TransactionEngine(new InventoryReservationAdapter());
  const evalBaseline = await targetLocalSubmit(evalBaselineEngine, targetState, candidates, TRANSFER_GUARD_BUDGET);
  const evaluationReceipts = [...evalTransfer.receipts, ...evalBaseline.receipts];
  const certificate = await buildTransferEvaluationCertificate({
    claimId: "transfer_guard_blocks_source_inventory_negative_transfer",
    learnerId: "receipt_budget_policy_source_only",
    learnerSnapshotHash: (await policy.snapshot()).snapshotHash,
    sourceDomains: ["source_inventory"],
    targetDomains: ["target_inventory"],
    sourceReceiptHashes: [sourceReceipt.receiptHash],
    targetEvaluationReceiptHashes: evaluationReceipts.map((receipt) => receipt.receiptHash),
    baselineName: "target_local_quantity_2",
    transferName: "source_only_quantity_5",
    baselineSuccessCount: evalBaseline.committed ? 1 : 0,
    transferSuccessCount: evalTransfer.committed ? 1 : 0,
    baselineVerifierCalls: evalBaseline.receipts.length,
    transferVerifierCalls: evalTransfer.receipts.length,
    sameCaseBaseline: true,
    hardCommitOnly: [sourceReceipt, ...evaluationReceipts].every((receipt) => receipt.committed === (receipt.hardResult.result === "accept")),
    invalidCommitCount: sourceEngine.invalidCommitCount + evalTransferEngine.invalidCommitCount + evalBaselineEngine.invalidCommitCount,
    ledgerAudit: await sourceEngine.ledger.audit() && await evalTransferEngine.ledger.audit() && await evalBaselineEngine.ledger.audit(),
    replayRollbackRate: await replayRollbackRateFor([
      [sourceEngine, sourceState],
      [evalTransferEngine, targetState],
      [evalBaselineEngine, targetState],
    ]),
  });

  const guard = new TransferGuardMemory();
  await guard.updateValidated(certificate);
  const decision = await guard.decide(["source_inventory"], "target_inventory");
  const snapshot = await guard.snapshot();
  const tampered = {
    ...snapshot,
    entries: [{ ...snapshot.entries[0], conclusion: "positive_transfer" }],
    snapshotHash: "",
  };

  const unguardedEngine = new TransactionEngine(new InventoryReservationAdapter());
  const unguarded = await policy.submit(unguardedEngine, targetState, candidates, {
    budget: TRANSFER_GUARD_BUDGET,
    tracePrefix: "transfer-guard-unguarded",
    modelVersion: "transfer.guard.unguarded.v1",
  });
  const guardedEngine = new TransactionEngine(new InventoryReservationAdapter());
  let guardedSelected          ;
  let guardedCommitted         ;
  let guardedUsedTargetBaseline         ;
  if (decision.admitted) {
    const guarded = await policy.submit(guardedEngine, targetState, candidates, {
      budget: TRANSFER_GUARD_BUDGET,
      tracePrefix: "transfer-guard-admitted",
      modelVersion: "transfer.guard.admitted.v1",
    });
    guardedSelected = guarded.selectedLabels;
    guardedCommitted = guarded.committed;
    guardedUsedTargetBaseline = false;
  } else {
    const guarded = await targetLocalSubmit(guardedEngine, targetState, candidates, TRANSFER_GUARD_BUDGET);
    guardedSelected = guarded.submittedLabels;
    guardedCommitted = guarded.committed;
    guardedUsedTargetBaseline = true;
  }

  const unguardedResidual = unguarded.receipts[0]?.hardResult.residual;
  const unguardedResidualKind = unguardedResidual && typeof unguardedResidual === "object"
    ? String((unguardedResidual                      ).kind ?? "")
    : "";
  const engines                                                                                          = [
    [sourceEngine, sourceState],
    [evalTransferEngine, targetState],
    [evalBaselineEngine, targetState],
    [unguardedEngine, targetState],
    [guardedEngine, targetState],
  ];
  const ledgerAudit = (await Promise.all(engines.map(([engine]) => engine.ledger.audit()))).every(Boolean);
  return {
    schemaVersion: TRANSFER_GUARD_SNAPSHOT_SCHEMA,
    snapshotValid: await validateTransferGuardSnapshot(snapshot),
    decisionValid: await validateTransferGuardDecision(decision),
    guardBlocksSourcePolicy: !decision.admitted && decision.reason === "negative_transfer_certificate",
    guardDecisionAdmitted: decision.admitted,
    guardDecisionReason: decision.reason,
    guardDecisionHash: decision.decisionHash,
    sourceSelected: ["quantity-5"],
    unguardedSelected: unguarded.selectedLabels,
    unguardedCommitted: unguarded.committed,
    unguardedResidualKind,
    guardedSelected,
    guardedCommitted,
    guardedUsedTargetBaseline,
    avoidedNegativeTransfer: !unguarded.committed && guardedCommitted && guardedUsedTargetBaseline,
    certificateConclusion: certificate.conclusion,
    certificateHash: certificate.certificateHash,
    snapshotHash: snapshot.snapshotHash,
    tamperDetected: !await validateTransferGuardSnapshot(tampered),
    invalidCommitCount: sourceEngine.invalidCommitCount
      + evalTransferEngine.invalidCommitCount
      + evalBaselineEngine.invalidCommitCount
      + unguardedEngine.invalidCommitCount
      + guardedEngine.invalidCommitCount,
    ledgerAudit,
    replayRollbackRate: await replayRollbackRateFor(engines),
  };
}

async function targetCandidates(state                )                                                               {
  const quantities = [5, 2];
  const rows                                                      = [];
  for (let idx = 0; idx < quantities.length; idx += 1) {
    const quantity = quantities[idx];
    rows.push({
      label: `quantity-${quantity}`,
      token: `quantity-${quantity}`,
      candidate: await makeReservationCandidate(state, `guard-target-q${quantity}`, "widget", 5, quantity, "transfer-guard-target", 1),
      verifierCost: 1,
      reward: quantity,
      baseRank: idx,
    });
  }
  return rows;
}

async function targetLocalSubmit(
  engine                                                                ,
  state                ,
  candidates                                                     ,
  budget        ,
)                                                                                  {
  const receipts            = [];
  const submittedLabels           = [];
  let spent = 0;
  const sorted = [...candidates].sort((a, b) => (a.label === "quantity-2" ? 0 : 1) - (b.label === "quantity-2" ? 0 : 1) || (a.label < b.label ? -1 : a.label > b.label ? 1 : 0));
  for (let idx = 0; idx < sorted.length; idx += 1) {
    const row = sorted[idx];
    if (spent + row.verifierCost > budget) {
      continue;
    }
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `transfer-guard-target-baseline-${idx}-${row.label}`,
        actions: [{ label: row.label }],
        modelVersion: "transfer.guard.target.v1",
      }),
      row.candidate,
    );
    receipts.push(outcome.receipt);
    submittedLabels.push(row.label);
    spent += row.verifierCost;
    if (outcome.committed) {
      return { committed: true, submittedLabels, receipts };
    }
  }
  return { committed: false, submittedLabels, receipts };
}

async function replayRollbackRateFor(rows                                                                                         )                  {
  let ok = 0;
  for (const [engine, state] of rows) {
    try {
      if (await engine.ledger.audit()) {
        await engine.replayAudit(state);
        if (JSON.stringify(await engine.rollbackAudit(state)) === JSON.stringify(state)) {
          ok += 1;
        }
      }
    } catch (_error) {
      // Leave this row failed.
    }
  }
  return ok / rows.length;
}
