import type { Receipt } from "./core.js";
import { canonicalJson, sha256Hex } from "./canonical.js";

export interface CounterfactualActionStats {
  committed: number;
  rolledBack: number;
  rejected: number;
  abstained: number;
}

export class ReceiptRanker {
  accepted = new Map<string, Map<string, number>>();
  rejected = new Map<string, Map<string, number>>();

  update(receipt: Receipt): void {
    const { context, action } = receiptContextAction(receipt);
    if (receipt.hardResult.result === "accept") {
      increment(this.accepted, context, action);
    } else if (receipt.hardResult.result === "reject") {
      increment(this.rejected, context, action);
    }
  }

  rank<T>(context: string, candidates: T[]): T[] {
    return [...candidates].sort((a, b) => {
      const aToken = tokenFromUnknown(a);
      const bToken = tokenFromUnknown(b);
      const aAccepted = getCount(this.accepted, context, aToken);
      const bAccepted = getCount(this.accepted, context, bToken);
      if (aAccepted !== bAccepted) {
        return bAccepted - aAccepted;
      }
      const aRejected = getCount(this.rejected, context, aToken);
      const bRejected = getCount(this.rejected, context, bToken);
      if (aRejected !== bRejected) {
        return aRejected - bRejected;
      }
      return aToken < bToken ? -1 : aToken > bToken ? 1 : 0;
    });
  }
}

export class CounterfactualRollbackRanker {
  commitWeight: number;
  rollbackWeight: number;
  rejectWeight: number;
  committed = new Map<string, Map<string, number>>();
  rolledBack = new Map<string, Map<string, number>>();
  rejected = new Map<string, Map<string, number>>();
  abstained = new Map<string, Map<string, number>>();

  constructor(commitWeight = 1, rollbackWeight = 1, rejectWeight = 2) {
    this.commitWeight = commitWeight;
    this.rollbackWeight = rollbackWeight;
    this.rejectWeight = rejectWeight;
  }

  update(receipt: Receipt): void {
    const { context, action } = receiptContextAction(receipt);
    if (receipt.committed && receipt.hardResult.result === "accept") {
      increment(this.committed, context, action);
    } else if (receipt.hardResult.result === "accept" && receipt.commitDecision === "rolled_back_loser") {
      increment(this.rolledBack, context, action);
    } else if (receipt.hardResult.result === "reject") {
      increment(this.rejected, context, action);
    } else if (receipt.hardResult.result === "abstain") {
      increment(this.abstained, context, action);
    }
  }

  stats(context: string, candidate: unknown): CounterfactualActionStats {
    const token = tokenFromUnknown(candidate);
    return {
      committed: getCount(this.committed, context, token),
      rolledBack: getCount(this.rolledBack, context, token),
      rejected: getCount(this.rejected, context, token),
      abstained: getCount(this.abstained, context, token),
    };
  }

  score(context: string, candidate: unknown): number {
    const row = this.stats(context, candidate);
    return this.commitWeight * row.committed
      - this.rollbackWeight * row.rolledBack
      - this.rejectWeight * row.rejected;
  }

  rank<T>(context: string, candidates: T[]): T[] {
    return [...candidates].sort((a, b) => {
      const aScore = this.score(context, a);
      const bScore = this.score(context, b);
      if (aScore !== bScore) {
        return bScore - aScore;
      }
      const aStats = this.stats(context, a);
      const bStats = this.stats(context, b);
      if (aStats.committed !== bStats.committed) {
        return bStats.committed - aStats.committed;
      }
      if (aStats.rolledBack !== bStats.rolledBack) {
        return aStats.rolledBack - bStats.rolledBack;
      }
      if (aStats.rejected !== bStats.rejected) {
        return aStats.rejected - bStats.rejected;
      }
      const aToken = tokenFromUnknown(a);
      const bToken = tokenFromUnknown(b);
      return aToken < bToken ? -1 : aToken > bToken ? 1 : 0;
    });
  }
}

export class HyperdimensionalMemory {
  dimensions: number;
  rows: Array<{ vector: Int8Array; receipt: Receipt; index: number }> = [];

  constructor(dimensions = 256) {
    if (!Number.isInteger(dimensions) || dimensions <= 0) {
      throw new RangeError("dimensions must be a positive integer");
    }
    this.dimensions = dimensions;
  }

  async add(receipt: Receipt): Promise<void> {
    this.rows.push({ vector: await this.encodeReceipt(receipt), receipt, index: this.rows.length });
  }

  async nearest(query: Record<string, unknown>, topK = 8): Promise<Receipt[]> {
    return this.nearestVector(await this.encodeQuery(query), topK);
  }

  async encodeQuery(query: Record<string, unknown>): Promise<Int8Array> {
    return bundleVectors(await Promise.all(
      Object.entries(query).map(async ([role, value]) =>
        bindVectors(await seedBits(`role:${role}`, this.dimensions), await seedBits(tokenFromUnknown(value), this.dimensions)),
      ),
    ));
  }

  nearestVector(queryVector: Int8Array, topK = 8): Receipt[] {
    return [...this.rows]
      .map((row) => ({ receipt: row.receipt, score: cosine(queryVector, row.vector), index: row.index }))
      .sort((a, b) => b.score - a.score || a.index - b.index)
      .slice(0, topK)
      .map((row) => row.receipt);
  }

  async encodeReceipt(receipt: Receipt): Promise<Int8Array> {
    const { context, action } = receiptContextAction(receipt);
    const parts = await Promise.all(
      Object.entries({
        context,
        action,
        result: receipt.hardResult.result,
        verifier: receipt.hardResult.verifierId,
        decision: receipt.commitDecision,
      }).map(async ([role, value]) =>
        bindVectors(await seedBits(`role:${role}`, this.dimensions), await seedBits(tokenFromUnknown(value), this.dimensions)),
      ),
    );
    return bundleVectors(parts);
  }
}

function receiptContextAction(receipt: Receipt): { context: string; action: string } {
  const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
    ? receipt.replayBundle as Record<string, unknown>
    : {};
  const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
    ? bundle.candidatePayload as Record<string, unknown>
    : {};
  const context = String(bundle.context ?? payload.context ?? "global");
  const action = tokenFromUnknown(bundle.action ?? payload.action ?? payload.guess ?? payload);
  return { context, action };
}

function increment(table: Map<string, Map<string, number>>, context: string, action: string): void {
  let row = table.get(context);
  if (!row) {
    row = new Map();
    table.set(context, row);
  }
  row.set(action, (row.get(action) ?? 0) + 1);
}

function getCount(table: Map<string, Map<string, number>>, context: string, action: string): number {
  return table.get(context)?.get(action) ?? 0;
}

function tokenFromUnknown(value: unknown): string {
  if (value && typeof value === "object") {
    return canonicalJson(value);
  }
  return String(value);
}

async function seedBits(token: string, dimensions: number): Promise<Int8Array> {
  const out = new Int8Array(dimensions);
  let filled = 0;
  let counter = 0;
  while (filled < dimensions) {
    const digest = await sha256Hex(`${token}:${counter}`);
    for (let idx = 0; idx < digest.length && filled < dimensions; idx += 2) {
      const byte = Number.parseInt(digest.slice(idx, idx + 2), 16);
      for (let bit = 0; bit < 8 && filled < dimensions; bit += 1) {
        out[filled] = byte & (1 << bit) ? 1 : -1;
        filled += 1;
      }
    }
    counter += 1;
  }
  return out;
}

function bindVectors(a: Int8Array, b: Int8Array): Int8Array {
  if (a.length !== b.length) {
    throw new RangeError("hypervectors must have equal dimensions");
  }
  return Int8Array.from(a, (value, idx) => value * b[idx]);
}

function bundleVectors(vectors: Int8Array[]): Int8Array {
  if (vectors.length === 0) {
    return new Int8Array();
  }
  const totals = new Int32Array(vectors[0].length);
  for (const vector of vectors) {
    for (let idx = 0; idx < vector.length; idx += 1) {
      totals[idx] += vector[idx];
    }
  }
  return Int8Array.from(totals, (value) => value >= 0 ? 1 : -1);
}

function cosine(a: Int8Array, b: Int8Array): number {
  if (a.length === 0 || a.length !== b.length) {
    return 0;
  }
  let dot = 0;
  for (let idx = 0; idx < a.length; idx += 1) {
    dot += a[idx] * b[idx];
  }
  return dot / a.length;
}
