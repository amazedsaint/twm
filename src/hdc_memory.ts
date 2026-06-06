import {
  type Receipt,
  type TypedCandidate,
  Ledger,
  TransactionEngine,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { HyperdimensionalMemory } from "./learning.js";
import {
  type ShapeCandidatePayload,
  type ShapeEpisodeResult,
  type ShapeState,
  ShapeGuessAdapter,
} from "./shape.js";

export interface HdcMemoryReport {
  noMemoryCallsPerSuccess: number;
  exactMatchCallsPerSuccess: number;
  hdcCallsPerSuccess: number;
  hdcGainOverNoMemory: number;
  hdcGainOverExactMatch: number;
  noiseRetrievalOk: boolean;
  tamperDetected: boolean;
  ledgerAudit: boolean;
  invalidCommitCount: number;
}

class ExactContextMemory {
  accepted = new Map<string, Map<number, number>>();
  rejected = new Map<string, Map<number, number>>();

  update(receipt: Receipt): void {
    const payload = receiptPayload(receipt);
    const exactContext = String(payload.exact_context ?? payload.context ?? "global");
    const action = Number(payload.action ?? payload.guess ?? -1);
    if (receipt.committed && receipt.hardResult.result === "accept") {
      increment(this.accepted, exactContext, action);
    } else if (receipt.hardResult.result === "reject") {
      increment(this.rejected, exactContext, action);
    }
  }

  rank(exactContext: string, labels: number[], fallback: number[]): number[] {
    const fallbackIndex = new Map(fallback.map((label, idx) => [label, idx]));
    return [...labels].sort((a, b) => {
      const acceptedDiff = getCount(this.accepted, exactContext, b) - getCount(this.accepted, exactContext, a);
      if (acceptedDiff !== 0) return acceptedDiff;
      const rejectedDiff = getCount(this.rejected, exactContext, a) - getCount(this.rejected, exactContext, b);
      if (rejectedDiff !== 0) return rejectedDiff;
      return (fallbackIndex.get(a) ?? Number.MAX_SAFE_INTEGER) - (fallbackIndex.get(b) ?? Number.MAX_SAFE_INTEGER);
    });
  }
}

export async function runHdcMemoryBenchmark(seed = 19, episodes = 96, labelCount = 24): Promise<HdcMemoryReport> {
  const rng = mulberry32(seed);
  const labels = Array.from({ length: labelCount }, (_unused, idx) => idx);
  const motifs = [1, 1, 1, 3, 3, 7];
  const defects = Array.from({ length: episodes }, () => motifs[Math.floor(rng() * motifs.length)]);
  const staticOrder = shuffle(labels, seed + 1);

  const noLedger = new Ledger();
  const exactLedger = new Ledger();
  const hdcLedger = new Ledger();
  const noMemory = await runOrder(defects, labels, staticOrder, "none", noLedger);
  const exactMemory = new ExactContextMemory();
  const exact = await runOrder(defects, labels, staticOrder, "exact", exactLedger, { exactMemory });
  const hdcMemory = new HyperdimensionalMemory(512);
  const hdc = await runOrder(defects, labels, staticOrder, "hdc", hdcLedger, { hdcMemory });

  const noCps = callsPerSuccess(noMemory);
  const exactCps = callsPerSuccess(exact);
  const hdcCps = callsPerSuccess(hdc);
  const noisy = flipBits(await hdcMemory.encodeQuery({ context: "motif-low", result: "accept" }), 0.1, seed + 2);
  const noisyNeighbors = hdcMemory.nearestVector(noisy, 16);
  const noiseRetrievalOk = noisyNeighbors.some((receipt) =>
    receipt.hardResult.result === "accept" && receiptPayload(receipt).context === "motif-low",
  );
  const tampered = new Ledger();
  tampered.head = hdcLedger.head;
  tampered.rows = [...hdcLedger.rows];
  if (tampered.rows.length > 0) {
    tampered.rows[0] = { ...tampered.rows[0], branchId: "tampered" };
  }
  const ledgers = [noLedger, exactLedger, hdcLedger];
  return {
    noMemoryCallsPerSuccess: noCps,
    exactMatchCallsPerSuccess: exactCps,
    hdcCallsPerSuccess: hdcCps,
    hdcGainOverNoMemory: noCps / hdcCps,
    hdcGainOverExactMatch: exactCps / hdcCps,
    noiseRetrievalOk,
    tamperDetected: !await tampered.audit(),
    ledgerAudit: (await Promise.all(ledgers.map((ledger) => ledger.audit()))).every(Boolean),
    invalidCommitCount: invalidCommits(ledgers),
  };
}

async function runOrder(
  defects: number[],
  labels: number[],
  staticOrder: number[],
  lane: string,
  ledger: Ledger,
  learners: { exactMemory?: ExactContextMemory; hdcMemory?: HyperdimensionalMemory } = {},
): Promise<ShapeEpisodeResult[]> {
  const engine = new TransactionEngine(new ShapeGuessAdapter(), ledger);
  const results: ShapeEpisodeResult[] = [];
  for (let episode = 0; episode < defects.length; episode += 1) {
    const defect = defects[episode];
    const state: ShapeState = { family: lane, episode, solved: false };
    const exactContext = `motif-low:${episode}`;
    const order = learners.exactMemory
      ? learners.exactMemory.rank(exactContext, labels, staticOrder)
      : learners.hdcMemory
        ? await hdcRank("motif-low", labels, staticOrder, learners.hdcMemory)
        : staticOrder;
    let calls = 0;
    let success = false;
    for (const guess of order) {
      calls += 1;
      const candidate = makeShapeCandidate("motif-low", exactContext, guess, defect);
      const outcome = await engine.transact(
        state,
        makeTrace({
          branchId: `hdc-${lane}-${episode}-${guess}`,
          actions: [guess],
          seeds: [episode, guess, lane],
          modelVersion: "hdc.memory.v1",
        }),
        candidate,
      );
      learners.exactMemory?.update(outcome.receipt);
      await learners.hdcMemory?.add(outcome.receipt);
      if (outcome.committed) {
        success = true;
        break;
      }
    }
    results.push({ calls, success });
  }
  return results;
}

async function hdcRank(context: string, labels: number[], staticOrder: number[], memory: HyperdimensionalMemory): Promise<number[]> {
  if (memory.rows.length === 0) {
    return staticOrder;
  }
  const fallbackIndex = new Map(staticOrder.map((label, idx) => [label, idx]));
  const accepted = new Map<number, number>();
  const rejected = new Map<number, number>();
  const neighbors = await memory.nearest({ context }, Math.min(memory.rows.length, 96));
  for (const receipt of neighbors) {
    const payload = receiptPayload(receipt);
    const action = Number(payload.action ?? payload.guess ?? -1);
    if (receipt.committed && receipt.hardResult.result === "accept") {
      accepted.set(action, (accepted.get(action) ?? 0) + 1);
    } else if (receipt.hardResult.result === "reject") {
      rejected.set(action, (rejected.get(action) ?? 0) + 1);
    }
  }
  return [...labels].sort((a, b) => {
    const acceptedDiff = (accepted.get(b) ?? 0) - (accepted.get(a) ?? 0);
    if (acceptedDiff !== 0) return acceptedDiff;
    const rejectedDiff = (rejected.get(a) ?? 0) - (rejected.get(b) ?? 0);
    if (rejectedDiff !== 0) return rejectedDiff;
    return (fallbackIndex.get(a) ?? Number.MAX_SAFE_INTEGER) - (fallbackIndex.get(b) ?? Number.MAX_SAFE_INTEGER);
  });
}

function makeShapeCandidate(context: string, exactContext: string, guess: number, defect: number): TypedCandidate<ShapeCandidatePayload> {
  return makeCandidate(
    { context, exact_context: exactContext, action: guess, guess, defect } as ShapeCandidatePayload,
    "shape.guess",
    "shape.guess.v1",
  );
}

function receiptPayload(receipt: Receipt): Record<string, unknown> {
  const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
    ? receipt.replayBundle as Record<string, unknown>
    : {};
  return bundle.candidatePayload && typeof bundle.candidatePayload === "object"
    ? bundle.candidatePayload as Record<string, unknown>
    : {};
}

function increment(table: Map<string, Map<number, number>>, context: string, action: number): void {
  let row = table.get(context);
  if (!row) {
    row = new Map();
    table.set(context, row);
  }
  row.set(action, (row.get(action) ?? 0) + 1);
}

function getCount(table: Map<string, Map<number, number>>, context: string, action: number): number {
  return table.get(context)?.get(action) ?? 0;
}

function callsPerSuccess(results: ShapeEpisodeResult[]): number {
  const successes = results.filter((row) => row.success).length;
  const calls = results.reduce((total, row) => total + row.calls, 0);
  return successes === 0 ? Number.POSITIVE_INFINITY : calls / successes;
}

function flipBits(vector: Int8Array, rate: number, seed: number): Int8Array {
  const rng = mulberry32(seed);
  const out = Int8Array.from(vector);
  const flips = Math.max(1, Math.round(out.length * rate));
  const indices = Array.from({ length: out.length }, (_unused, idx) => idx);
  for (let idx = indices.length - 1; idx > 0; idx -= 1) {
    const swap = Math.floor(rng() * (idx + 1));
    [indices[idx], indices[swap]] = [indices[swap], indices[idx]];
  }
  for (const idx of indices.slice(0, flips)) {
    out[idx] = -out[idx];
  }
  return out;
}

function invalidCommits(ledgers: Ledger[]): number {
  return ledgers.reduce(
    (total, ledger) => total + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
    0,
  );
}

function shuffle(values: number[], seed: number): number[] {
  const rng = mulberry32(seed);
  const out = [...values];
  for (let idx = out.length - 1; idx > 0; idx -= 1) {
    const swap = Math.floor(rng() * (idx + 1));
    [out[idx], out[swap]] = [out[swap], out[idx]];
  }
  return out;
}

function mulberry32(seed: number): () => number {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let next = value;
    next = Math.imul(next ^ (next >>> 15), next | 1);
    next ^= next + Math.imul(next ^ (next >>> 7), next | 61);
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296;
  };
}
