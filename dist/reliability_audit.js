import {



  Ledger,
  TransactionEngine,
  makeTrace,
} from "./core.js";
import {


  InventoryReservationAdapter,
  makeReservationCandidate,
} from "./operations.js";
import { VerifierAgreementAdapter } from "./verifier_guard.js";
import { FlawedInventoryPrimaryAdapter, UNSAFE_GUARD_ORDER } from "./verifier_guard_benchmark.js";
import { VerifierReliabilityMemory, validateVerifierReliabilitySnapshot } from "./reliability.js";

export const STRICT_RELIABILITY_PRIMARY_ID = "strict_inventory_primary";
export const FLAWED_RELIABILITY_PRIMARY_ID = "flawed_inventory_primary";






















export class StrictInventoryPrimaryAdapter extends InventoryReservationAdapter {
  verifierId = STRICT_RELIABILITY_PRIMARY_ID;

  verify(candidate                                             )                     {
    const result = super.verify(candidate);
    return { ...result, verifierId: this.verifierId };
  }
}

export async function runReliabilityAuditBenchmark()                                  {
  const memory = new VerifierReliabilityMemory();
  const trainingReceipts            = [];
  for (let idx = 0; idx < 3; idx += 1) {
    const receipt = await guardReceipt(new StrictInventoryPrimaryAdapter(), seedState(), `strict-safe-${idx}`, 1, 1);
    trainingReceipts.push(receipt);
    memory.updateFromReceipt(receipt);
  }
  for (const [orderId, requested, quantity] of [
    ["flawed-safe", 2, 2],
    ["flawed-unsafe-a", 8, 8],
    ["flawed-unsafe-b", 7, 7],
  ]                                   ) {
    const receipt = await guardReceipt(new FlawedInventoryPrimaryAdapter(), seedState(), orderId, requested, quantity);
    trainingReceipts.push(receipt);
    memory.updateFromReceipt(receipt);
  }

  const riskOrder = memory.rankForAudit([STRICT_RELIABILITY_PRIMARY_ID, FLAWED_RELIABILITY_PRIMARY_ID]);
  const auditBudget = 1;
  const naiveAudited = [STRICT_RELIABILITY_PRIMARY_ID];
  const reliabilityAudited = memory.selectForAudit([STRICT_RELIABILITY_PRIMARY_ID, FLAWED_RELIABILITY_PRIMARY_ID], auditBudget);
  const naiveReceipts = await auditSelected(naiveAudited, seedState());
  const reliabilityReceipts = await auditSelected(reliabilityAudited, seedState());
  const snapshot = await memory.snapshot();
  const tampered = {
    ...snapshot,
    rows: snapshot.rows.map((row) => ({ ...row, auditedFailures: 0 })),
  };
  const strict = memory.score(STRICT_RELIABILITY_PRIMARY_ID);
  const flawed = memory.score(FLAWED_RELIABILITY_PRIMARY_ID);
  const reliabilityFalsePositive = falsePositiveReceipt(reliabilityReceipts);
  const reliabilityResidual = reliabilityFalsePositive?.hardResult.residual



   ;

  return {
    trainingReceiptCount: trainingReceipts.length,
    strictSuccesses: strict.auditedSuccesses,
    strictFailures: strict.auditedFailures,
    flawedSuccesses: flawed.auditedSuccesses,
    flawedFailures: flawed.auditedFailures,
    strictLowerBound: strict.wilsonLowerBound,
    flawedLowerBound: flawed.wilsonLowerBound,
    riskOrder,
    auditBudget,
    naiveAuditedSubject: naiveAudited[0],
    reliabilityAuditedSubject: reliabilityAudited[0],
    naiveFalsePositiveDetected: Boolean(falsePositiveReceipt(naiveReceipts)),
    reliabilityFalsePositiveDetected: Boolean(reliabilityFalsePositive),
    reliabilityResidualKind: String(reliabilityResidual.kind),
    reliabilityAuditResidualKind: String((reliabilityResidual.auditResidual ?? reliabilityResidual.audit_residual)?.kind ?? ""),
    snapshotValid: await validateVerifierReliabilitySnapshot(snapshot),
    tamperDetected: !await validateVerifierReliabilitySnapshot(tampered),
    invalidCommitCount: [...trainingReceipts, ...naiveReceipts, ...reliabilityReceipts]
      .filter((receipt) => receipt.committed && receipt.hardResult.result !== "accept").length,
  };
}

async function guardReceipt(
  primary                             ,
  state                ,
  orderId        ,
  requested        ,
  quantity        ,
)                   {
  const engine = new TransactionEngine(
    new VerifierAgreementAdapter(primary, new InventoryReservationAdapter()),
    new Ledger(),
  );
  const candidate = await makeReservationCandidate(state, orderId, "widget", requested, quantity);
  return (await engine.transact(
    state,
    makeTrace({ branchId: `reliability-train-${orderId}`, actions: [{ orderId }] }),
    candidate,
  )).receipt;
}

async function auditSelected(subjects          , state                )                     {
  const receipts            = [];
  if (subjects.includes(STRICT_RELIABILITY_PRIMARY_ID)) {
    receipts.push(await guardReceipt(new StrictInventoryPrimaryAdapter(), state, "future-safe", 2, 2));
  }
  if (subjects.includes(FLAWED_RELIABILITY_PRIMARY_ID)) {
    receipts.push(await guardReceipt(new FlawedInventoryPrimaryAdapter(), state, UNSAFE_GUARD_ORDER, 8, 8));
  }
  return receipts;
}

function seedState()                 {
  return { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
}

function falsePositiveReceipt(receipts           )                 {
  return receipts.find((receipt) =>
    receipt.hardResult.residual
    && typeof receipt.hardResult.residual === "object"
    && (receipt.hardResult.residual                      ).kind === "verifier_false_positive"
  ) ?? null;
}
