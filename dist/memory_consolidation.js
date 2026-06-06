import { Ledger, TransactionEngine } from "./core.js";
import {
  GridMacroAdapter,
  PrefixSafeMacroRuntime,
  defaultGridState,


} from "./macro.js";
import {
  MACRO_MEMORY_SNAPSHOT_SCHEMA,
  BoundedMacroMemory,
  macroToken,
  validateMacroMemorySnapshot,
} from "./memory.js";




















export async function runMemoryConsolidationBenchmark()                                     {
  const context = "grid-3x3";
  const unsafe                  = { macroId: "unsafe-through-wall", steps: ["E", "S", "E", "S"], context, modelVersion: "macro.grid.v1" };
  const safe                  = { macroId: "safe-around-wall", steps: ["E", "E", "S", "S"], context, modelVersion: "macro.grid.v1" };
  const safeCopy                  = { macroId: "safe-around-wall-copy", steps: ["E", "E", "S", "S"], context, modelVersion: "macro.grid.v1" };
  const terminalMiss                  = { macroId: "terminal-miss", steps: ["E"], context, modelVersion: "macro.grid.v1" };
  const staleOob                  = { macroId: "stale-oob", steps: ["N"], context, modelVersion: "macro.grid.v1" };
  const ledger = new Ledger();
  const memory = new BoundedMacroMemory          (2);
  const sequence = [terminalMiss, staleOob, unsafe, unsafe, unsafe, unsafe, safe, safe, safeCopy, safeCopy];
  for (const macro of sequence) {
    const outcome = await runMacro(ledger, macro);
    await memory.update(outcome.receipt);
  }

  const snapshot = await memory.snapshot();
  const entries = new Map(snapshot.entries.map((entry) => [entry.token, entry]));
  const safeEntry = entries.get(await macroToken(safe.steps));
  const unsafeEntry = entries.get(await macroToken(unsafe.steps));
  if (!safeEntry || !unsafeEntry) {
    throw new Error("expected safe and unsafe entries to be retained");
  }
  const ranked = await memory.rank(context, [unsafe, terminalMiss, safe]);
  const tampered = {
    ...snapshot,
    entries: [{ ...safeEntry, acceptedCount: 99 }, unsafeEntry],
  };
  return {
    schemaVersion: MACRO_MEMORY_SNAPSHOT_SCHEMA,
    capacityPerContext: memory.capacityPerContext,
    rawReceiptCount: sequence.length,
    storedEntryCount: snapshot.entries.length,
    evictedCount: snapshot.evictedCount,
    safeAcceptedCount: safeEntry.acceptedCount,
    unsafePrefixRejectCount: unsafeEntry.prefixRejectCount,
    terminalRejectCountForgotten: !entries.has(await macroToken(terminalMiss.steps)),
    duplicateSafeMerged: safeEntry.acceptedCount === 4 && safeEntry.firstSeenIndex === 7 && safeEntry.lastSeenIndex === 10,
    safeRank: ranked.indexOf(safe) + 1,
    unsafeRank: ranked.indexOf(unsafe) + 1,
    snapshotValid: await validateMacroMemorySnapshot(snapshot),
    snapshotHashStable: snapshot.snapshotHash === (await memory.snapshot()).snapshotHash,
    tamperDetected: !await validateMacroMemorySnapshot(tampered),
    ledgerAudit: await ledger.audit(),
    invalidCommitCount: ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  };
}

async function runMacro(ledger        , macro                 ) {
  const adapter = new GridMacroAdapter();
  const engine = new TransactionEngine(adapter, ledger);
  const runtime = new PrefixSafeMacroRuntime(engine, adapter);
  return runtime.run(defaultGridState(), macro);
}
