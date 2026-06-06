import assert from "node:assert/strict";
import test from "node:test";

import {
  MACRO_MEMORY_SNAPSHOT_SCHEMA,
  BoundedMacroMemory,
  runMemoryConsolidationBenchmark,
  validateMacroMemorySnapshot,
} from "../dist/index.js";

test("bounded macro memory rejects invalid capacity and staleness", () => {
  assert.throws(() => new BoundedMacroMemory(0), /positive integer/);
  assert.throws(() => new BoundedMacroMemory(2, { stalenessPenalty: -1 }), /non-negative integer/);
});

test("bounded macro memory consolidates duplicates and evicts weak rows", async () => {
  const report = await runMemoryConsolidationBenchmark();

  assert.equal(report.schemaVersion, MACRO_MEMORY_SNAPSHOT_SCHEMA);
  assert.equal(report.capacityPerContext, 2);
  assert.equal(report.rawReceiptCount, 10);
  assert.equal(report.storedEntryCount, 2);
  assert.equal(report.evictedCount, 2);
  assert.equal(report.safeAcceptedCount, 4);
  assert.equal(report.unsafePrefixRejectCount, 4);
  assert.equal(report.terminalRejectCountForgotten, true);
  assert.equal(report.duplicateSafeMerged, true);
  assert.equal(report.safeRank, 1);
  assert.equal(report.unsafeRank, 3);
  assert.equal(report.snapshotValid, true);
  assert.equal(report.snapshotHashStable, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);
});

test("macro memory snapshot validation detects manifest tampering", async () => {
  const memory = new BoundedMacroMemory(2);
  const snapshot = await memory.snapshot();
  const tampered = { ...snapshot, capacityPerContext: 0 };

  assert.equal(await validateMacroMemorySnapshot(snapshot), true);
  assert.equal(await validateMacroMemorySnapshot(tampered), false);
});
