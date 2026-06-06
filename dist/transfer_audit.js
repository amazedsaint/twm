import {                       ReceiptBudgetPolicy } from "./budget_policy.js";
import {               TransactionEngine, makeTrace } from "./core.js";
import {


  InventoryReservationAdapter,
  makeReservationCandidate,
} from "./operations.js";
import {
  TRANSFER_EVALUATION_CERTIFICATE_SCHEMA,
  buildTransferEvaluationCertificate,
  transferEvaluationRejectsPositiveClaim,
  transferEvaluationSupportsPositiveClaim,
  validateTransferEvaluationCertificate,
} from "./transfer.js";

export const TRANSFER_AUDIT_BUDGET = 1;





































export async function runCrossDomainTransferAudit()                                     {
  const sourceState                 = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const targetState                 = { stock: { widget: 2 }, reserved: { widget: 0 }, committedOrders: [] };

  const policy = new ReceiptBudgetPolicy();
  const sourceEngine = new TransactionEngine(new InventoryReservationAdapter());
  const sourceReceipt = (await sourceEngine.transact(
    sourceState,
    makeTrace({
      branchId: "transfer-source-quantity-5",
      actions: [{ label: "quantity-5" }],
      modelVersion: "transfer.source.v1",
    }),
    await makeReservationCandidate(sourceState, "source-q5", "widget", 5, 5, "transfer-source", 1),
  )).receipt;
  policy.update("quantity-5", sourceReceipt);

  const candidates = await targetCandidates(targetState);
  const transferEngine = new TransactionEngine(new InventoryReservationAdapter());
  const transfer = await policy.submit(transferEngine, targetState, candidates, {
    budget: TRANSFER_AUDIT_BUDGET,
    tracePrefix: "transfer-source-policy",
    modelVersion: "transfer.source_policy.v1",
  });

  const baselineEngine = new TransactionEngine(new InventoryReservationAdapter());
  const baseline = await targetLocalSubmit(baselineEngine, targetState, candidates, TRANSFER_AUDIT_BUDGET);
  const snapshot = await policy.snapshot();
  const evaluationReceipts = [...transfer.receipts, ...baseline.receipts];
  const ledgerAudit = await sourceEngine.ledger.audit()
    && await transferEngine.ledger.audit()
    && await baselineEngine.ledger.audit();
  const replayRollbackRate = await replayRollbackRateFor([
    [sourceEngine, sourceState],
    [transferEngine, targetState],
    [baselineEngine, targetState],
  ]);
  const certificate = await buildTransferEvaluationCertificate({
    claimId: "source_inventory_policy_transfers_to_target_inventory",
    learnerId: "receipt_budget_policy_source_only",
    learnerSnapshotHash: snapshot.snapshotHash,
    sourceDomains: ["source_inventory"],
    targetDomains: ["target_inventory"],
    sourceReceiptHashes: [sourceReceipt.receiptHash],
    targetEvaluationReceiptHashes: evaluationReceipts.map((receipt) => receipt.receiptHash),
    baselineName: "target_local_quantity_2",
    transferName: "source_only_quantity_5",
    baselineSuccessCount: baseline.committed ? 1 : 0,
    transferSuccessCount: transfer.committed ? 1 : 0,
    baselineVerifierCalls: baseline.receipts.length,
    transferVerifierCalls: transfer.receipts.length,
    sameCaseBaseline: true,
    hardCommitOnly: [sourceReceipt, ...evaluationReceipts].every((receipt) => receipt.committed === (receipt.hardResult.result === "accept")),
    invalidCommitCount: sourceEngine.invalidCommitCount + transferEngine.invalidCommitCount + baselineEngine.invalidCommitCount,
    ledgerAudit,
    replayRollbackRate,
    metrics: {
      sourceSelected: ["quantity-5"],
      transferSelected: transfer.selectedLabels,
      baselineSelected: baseline.submittedLabels,
      targetStock: 2,
      budget: TRANSFER_AUDIT_BUDGET,
    },
  });
  const tampered = { ...certificate, transferSuccessCount: 1, certificateHash: "" };
  const overlapping = await buildTransferEvaluationCertificate({
    claimId: certificate.claimId,
    learnerId: certificate.learnerId,
    learnerSnapshotHash: certificate.learnerSnapshotHash,
    sourceDomains: certificate.sourceDomains,
    targetDomains: certificate.targetDomains,
    sourceReceiptHashes: certificate.sourceReceiptHashes,
    targetEvaluationReceiptHashes: [certificate.sourceReceiptHashes[0]],
    baselineName: certificate.baselineName,
    transferName: certificate.transferName,
    baselineSuccessCount: certificate.baselineSuccessCount,
    transferSuccessCount: certificate.transferSuccessCount,
    baselineVerifierCalls: certificate.baselineVerifierCalls,
    transferVerifierCalls: certificate.transferVerifierCalls,
    sameCaseBaseline: certificate.sameCaseBaseline,
    hardCommitOnly: certificate.hardCommitOnly,
    invalidCommitCount: certificate.invalidCommitCount,
    ledgerAudit: certificate.ledgerAudit,
    replayRollbackRate: certificate.replayRollbackRate,
    metrics: certificate.metrics,
  });
  const transferResidual = transfer.receipts[0]?.hardResult.residual;
  const transferResidualKind = transferResidual && typeof transferResidual === "object"
    ? String((transferResidual                      ).kind ?? "")
    : "";

  return {
    schemaVersion: TRANSFER_EVALUATION_CERTIFICATE_SCHEMA,
    certificateValid: await validateTransferEvaluationCertificate(certificate),
    positiveTransferClaimSupported: await transferEvaluationSupportsPositiveClaim(certificate),
    positiveTransferClaimRejected: await transferEvaluationRejectsPositiveClaim(certificate),
    claimId: certificate.claimId,
    sourceDomainCount: certificate.sourceDomains.length,
    targetDomainCount: certificate.targetDomains.length,
    sourceReceiptCount: certificate.sourceReceiptHashes.length,
    targetEvaluationReceiptCount: certificate.targetEvaluationReceiptHashes.length,
    sourceTargetDomainDisjoint: certificate.sourceTargetDomainDisjoint,
    sourceTargetReceiptDisjoint: certificate.sourceTargetReceiptDisjoint,
    sameCaseBaseline: certificate.sameCaseBaseline,
    transferName: certificate.transferName,
    baselineName: certificate.baselineName,
    sourceSelected: ["quantity-5"],
    transferSelected: transfer.selectedLabels,
    baselineSelected: baseline.submittedLabels,
    transferSuccessCount: certificate.transferSuccessCount,
    baselineSuccessCount: certificate.baselineSuccessCount,
    transferVerifierCalls: certificate.transferVerifierCalls,
    baselineVerifierCalls: certificate.baselineVerifierCalls,
    successDelta: certificate.successDelta,
    verifierCallDelta: certificate.verifierCallDelta,
    conclusion: certificate.conclusion,
    transferResidualKind,
    hardCommitOnly: certificate.hardCommitOnly,
    invalidCommitCount: certificate.invalidCommitCount,
    ledgerAudit: certificate.ledgerAudit,
    replayRollbackRate: certificate.replayRollbackRate,
    learnerSnapshotHash: certificate.learnerSnapshotHash,
    certificateHash: certificate.certificateHash,
    tamperDetected: !await validateTransferEvaluationCertificate(tampered),
    overlapDetected: !await validateTransferEvaluationCertificate(overlapping),
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
      candidate: await makeReservationCandidate(state, `target-q${quantity}`, "widget", 5, quantity, "transfer-target", 1),
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
  let spent = 0;
  const submittedLabels           = [];
  const receipts            = [];
  const sorted = [...candidates].sort((a, b) => (a.label === "quantity-2" ? 0 : 1) - (b.label === "quantity-2" ? 0 : 1) || (a.label < b.label ? -1 : a.label > b.label ? 1 : 0));
  for (let idx = 0; idx < sorted.length; idx += 1) {
    const row = sorted[idx];
    if (spent + row.verifierCost > budget) {
      continue;
    }
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `transfer-target-baseline-${idx}-${row.label}`,
        actions: [{ label: row.label }],
        modelVersion: "transfer.target.v1",
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
