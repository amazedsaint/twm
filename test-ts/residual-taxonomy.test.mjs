import assert from "node:assert/strict";
import test from "node:test";

import {
  RESIDUAL_SCHEMA,
  ResidualTaxonomyMemory,
  normalizeResidual,
  residualLearningHash,
  runResidualTaxonomyBenchmark,
  validateResidualSignal,
} from "../dist/index.js";

test("snake and camel residuals share a normalized learning hash", async () => {
  const snake = await normalizeResidual(
    { kind: "stock_shortage", sku: "widget", repair: { quantity: 2 } },
    { status: "reject", verifierId: "inventory_reservation_verifier", verifierVersion: "1.0" },
  );
  const camel = await normalizeResidual(
    { kind: "stockShortage", sku: "widget", repair: { quantity: 2 } },
    { status: "reject", verifierId: "inventory_reservation_verifier", verifierVersion: "1.0" },
  );

  assert.equal(snake.kind, "stock_shortage");
  assert.equal(camel.kind, "stock_shortage");
  assert.equal(await residualLearningHash(snake), await residualLearningHash(camel));
  assert.notEqual(snake.residualHash, camel.residualHash);
});

test("duplicate aliases are allowed only when equal", async () => {
  const signal = await normalizeResidual(
    { kind: "verifier_budget_exhausted", required_verifier_cost: 7, requiredVerifierCost: 7 },
    { status: "abstain", verifierId: "v", verifierVersion: "1" },
  );

  assert.equal(signal.fields.includes("7"), true);
  await assert.rejects(
    () => normalizeResidual(
      { kind: "verifier_budget_exhausted", required_verifier_cost: 7, requiredVerifierCost: 9 },
      { status: "abstain", verifierId: "v", verifierVersion: "1" },
    ),
    /collision/,
  );
});

test("signal hash detects residual envelope tampering", async () => {
  const signal = await normalizeResidual(
    { kind: "projection_contract_violation", missingFields: ["safetyClearance"] },
    { status: "reject", verifierId: "projection_contract_guard", verifierVersion: "1.0" },
  );
  const tampered = { ...signal, category: "unknown" };

  assert.equal(await validateResidualSignal(signal), true);
  assert.equal(await validateResidualSignal(tampered), false);
});

test("residual taxonomy benchmark uses three real receipt residuals", async () => {
  const report = await runResidualTaxonomyBenchmark();

  assert.equal(report.signalCount, 3);
  assert.equal(report.schemaVersion, RESIDUAL_SCHEMA);
  assert.deepEqual(report.categories, { resource: 1, coverage: 1, budget: 1 });
  assert.equal(report.resourceKind, "stock_shortage");
  assert.equal(report.coverageKind, "projection_contract_violation");
  assert.equal(report.budgetKind, "verifier_budget_exhausted");
  assert.equal(report.resourceCategory, "resource");
  assert.equal(report.coverageCategory, "coverage");
  assert.equal(report.budgetCategory, "budget");
  assert.deepEqual(report.stockShortageFields, ["widget"]);
  assert.deepEqual(report.projectionMissingFields, ["safetyClearance"]);
  assert.deepEqual(report.budgetFields, ["7", "4"]);
  assert.equal(report.topStockShortageRepairHint, "quantity=2");
  assert.equal(report.snakeCamelLearningHashEqual, true);
  assert.equal(report.rawResidualHashDistinct, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);

  const memory = new ResidualTaxonomyMemory();
  await memory.update(await normalizeResidual(
    { kind: "stock_shortage", sku: "widget", repair: { quantity: 2 } },
    { status: "reject", verifierId: "v", verifierVersion: "1" },
  ));
  assert.equal(memory.topRepairHint("stockShortage"), "quantity=2");
});
