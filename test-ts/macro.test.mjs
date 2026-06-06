import assert from "node:assert/strict";
import test from "node:test";

import {
  GridMacroAdapter,
  Ledger,
  MacroMemory,
  PrefixSafeMacroRuntime,
  TransactionEngine,
  defaultGridMacros,
  defaultGridState,
  runMacroGridBenchmark,
} from "../dist/index.js";

test("prefix-unsafe macro is rejected before terminal verifier", async () => {
  const adapter = new GridMacroAdapter();
  const engine = new TransactionEngine(adapter, new Ledger());
  const runtime = new PrefixSafeMacroRuntime(engine, adapter);
  const outcome = await runtime.run(defaultGridState(), defaultGridMacros()[0]);

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason, "prefix_unsafe");
  assert.equal(outcome.terminalVerifierCalls, 0);
  assert.equal(runtime.prefixRejectCount, 1);
  assert.equal(await engine.ledger.audit(), true);
});

test("safe macro commits and rollback audit returns seed state", async () => {
  const adapter = new GridMacroAdapter();
  const engine = new TransactionEngine(adapter, new Ledger());
  const runtime = new PrefixSafeMacroRuntime(engine, adapter);
  const outcome = await runtime.run(defaultGridState(), defaultGridMacros()[1]);

  assert.equal(outcome.committed, true);
  assert.equal(outcome.terminalVerifierCalls, 1);
  assert.equal(await engine.ledger.audit(), true);
  assert.deepEqual(await engine.rollbackAudit(defaultGridState()), defaultGridState());
});

test("macro memory ranks accepted macro ahead of unsafe prefix", async () => {
  const memory = new MacroMemory();
  const adapter = new GridMacroAdapter();
  const engine = new TransactionEngine(adapter, new Ledger());
  const runtime = new PrefixSafeMacroRuntime(engine, adapter);
  const macros = defaultGridMacros();
  for (const macro of macros) {
    const outcome = await runtime.run(defaultGridState(), macro);
    memory.update(outcome.receipt);
    if (outcome.committed) break;
  }

  assert.equal(memory.rank("grid-3x3", macros)[0].macroId, "safe-around-wall");
});

test("macro grid benchmark measures prefix and reuse lift", async () => {
  const report = await runMacroGridBenchmark(16);

  assert.equal(report.ledgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.ok(report.prefixSafeCallsPerSuccess < report.terminalOnlyCallsPerSuccess);
  assert.ok(report.macroReuseGain > 1.5);
  assert.equal(report.prefixRejectCount, 16);
  assert.equal(report.learnedPrefixRejectCount, 1);
});
