import { BudgetedBranchRuntime, VerifierBudget } from "./branch.js";
import { TransactionEngine, makeTrace,              } from "./core.js";
import {
  InventoryReservationAdapter,
  makeReservationCandidate,

} from "./operations.js";
import {
  ProjectionContractProjector,
  ProjectionGuardAdapter,
  makeProjectionContractTraces,

} from "./projection_contract.js";
import {
  VERIFIER_BUDGET_LIMIT,
  VerifierBudgetAdapter,
  VerifierBudgetProjector,
  makeVerifierBudgetTraces,
} from "./verifier_budget.js";
import {
  RESIDUAL_SCHEMA,
  ResidualTaxonomyMemory,
  normalizeResidual,
  residualLearningHash,
  residualSignalFromReceipt,
  validateResidualSignal,
} from "./residuals.js";























export async function runResidualTaxonomyBenchmark()                                  {
  const [stockReceipt, stockAudit, stockInvalid] = await stockShortageReceipt();
  const [projectionResidualReceipt, projectionAudit, projectionInvalid] = await makeProjectionResidualReceipt();
  const [budgetReceipt, budgetAudit, budgetInvalid] = await budgetAbstainReceipt();

  const signals = [
    await residualSignalFromReceipt(stockReceipt, { sourceDomain: "operations" }),
    await residualSignalFromReceipt(projectionResidualReceipt, { sourceDomain: "projection_contract" }),
    await residualSignalFromReceipt(budgetReceipt, { sourceDomain: "verifier_budget" }),
  ];
  const memory = new ResidualTaxonomyMemory();
  for (const signal of signals) {
    await memory.update(signal);
  }

  const snake = await normalizeResidual(
    { kind: "stock_shortage", sku: "widget", repair: { quantity: 2 } },
    { status: "reject", verifierId: "inventory_reservation_verifier", verifierVersion: "1.0" },
  );
  const camel = await normalizeResidual(
    { kind: "stockShortage", sku: "widget", repair: { quantity: 2 } },
    { status: "reject", verifierId: "inventory_reservation_verifier", verifierVersion: "1.0" },
  );
  const tampered = { ...signals[0], category: "unknown"          };

  return {
    signalCount: signals.length,
    schemaVersion: RESIDUAL_SCHEMA,
    categories: Object.fromEntries(memory.categoryCounts.entries()),
    kindOrder: memory.rankKinds(),
    resourceKind: signals[0].kind,
    coverageKind: signals[1].kind,
    budgetKind: signals[2].kind,
    resourceCategory: signals[0].category,
    coverageCategory: signals[1].category,
    budgetCategory: signals[2].category,
    stockShortageFields: signals[0].fields,
    projectionMissingFields: signals[1].fields,
    budgetFields: signals[2].fields,
    topStockShortageRepairHint: memory.topRepairHint("stock_shortage") ?? "",
    snakeCamelLearningHashEqual: await residualLearningHash(snake) === await residualLearningHash(camel),
    rawResidualHashDistinct: snake.residualHash !== camel.residualHash,
    tamperDetected: !await validateResidualSignal(tampered),
    ledgerAudit: stockAudit && projectionAudit && budgetAudit,
    invalidCommitCount: stockInvalid + projectionInvalid + budgetInvalid,
  };
}

async function stockShortageReceipt()                                      {
  const state                 = { stock: { widget: 2 }, reserved: {}, committedOrders: [] };
  const candidate = await makeReservationCandidate(state, "order-1", "widget", 5, 5);
  const engine = new TransactionEngine(new InventoryReservationAdapter());
  const outcome = await engine.transact(
    state,
    makeTrace({
      branchId: "residual-taxonomy-stock-shortage",
      actions: [{ sku: "widget", quantity: 5 }],
      seeds: ["residual_taxonomy", "stock_shortage"],
      modelVersion: "residual.taxonomy.v1",
    }),
    candidate,
  );
  return [outcome.receipt, await engine.ledger.audit(), engine.invalidCommitCount];
}

async function makeProjectionResidualReceipt()                                      {
  const state                       = { distanceToObstacle: 5, brakeAccel: 2, safetyClearance: 2, committedModes: [] };
  const trace = makeProjectionContractTraces()[0];
  const candidate = await new ProjectionContractProjector().project(state, trace);
  const engine = new TransactionEngine(new ProjectionGuardAdapter(state));
  const outcome = await engine.transact(state, trace, candidate);
  return [outcome.receipt, await engine.ledger.audit(), engine.invalidCommitCount];
}

async function budgetAbstainReceipt()                                      {
  const engine = new TransactionEngine(new VerifierBudgetAdapter());
  const outcome = await new BudgetedBranchRuntime(
    engine,
    new VerifierBudgetProjector(),
    new VerifierBudget(VERIFIER_BUDGET_LIMIT),
  ).step({ committedActions: [] }, makeVerifierBudgetTraces());
  return [outcome.receipts[0]           , await engine.ledger.audit(), engine.invalidCommitCount];
}
