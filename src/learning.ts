import { receiptStaticValid, type Receipt, type TypedCandidate } from "./core.js";
import { canonicalJson, sha256Hex, stableHash } from "./canonical.js";

export const RECEIPT_TRAINED_REVERSIBLE_PROPOSER_SNAPSHOT_SCHEMA = "trwm.receipt_trained_reversible_proposer_snapshot.v1";

export interface CounterfactualActionStats {
  committed: number;
  rolledBack: number;
  rejected: number;
  abstained: number;
}

export interface ReversibleProposerSnapshotRow {
  context: string;
  action: string;
  committed: number;
  rejected: number;
  observations: number;
  score: number;
}

export interface ReceiptTrainedReversibleProposerSnapshot {
  schemaVersion: typeof RECEIPT_TRAINED_REVERSIBLE_PROPOSER_SNAPSHOT_SCHEMA;
  learnerId: string;
  learnerVersion: string;
  receiptHashes: string[];
  rows: ReversibleProposerSnapshotRow[];
  snapshotHash: string;
}

export class ReceiptTrainedReversibleProposer {
  learnerId: string;
  learnerVersion: string;
  commitWeight: number;
  rejectWeight: number;
  committed = new Map<string, Map<string, number>>();
  rejected = new Map<string, Map<string, number>>();
  receiptHashes: string[] = [];

  constructor(options: {
    learnerId?: string;
    learnerVersion?: string;
    commitWeight?: number;
    rejectWeight?: number;
  } = {}) {
    this.learnerId = options.learnerId ?? "receipt_trained_reversible_proposer";
    this.learnerVersion = options.learnerVersion ?? "1.0";
    this.commitWeight = options.commitWeight ?? 1;
    this.rejectWeight = options.rejectWeight ?? 1;
    if (!this.learnerId || !this.learnerVersion) {
      throw new RangeError("learner id and version must be non-empty");
    }
    if (this.commitWeight <= 0 || this.rejectWeight < 0) {
      throw new RangeError("weights must be non-negative and commitWeight must be positive");
    }
  }

  async update(receipt: Receipt): Promise<void> {
    if (!await receiptStaticValid(receipt)) {
      throw new Error("receipt-trained proposer only accepts statically valid receipts");
    }
    const { context, action } = receiptContextAction(receipt);
    if (receipt.committed && receipt.hardResult.result === "accept") {
      increment(this.committed, context, action);
    } else if (receipt.hardResult.result === "reject") {
      increment(this.rejected, context, action);
    }
    if (isHash(receipt.receiptHash) && !this.receiptHashes.includes(receipt.receiptHash)) {
      this.receiptHashes.push(receipt.receiptHash);
    }
  }

  score(context: string, candidate: unknown): number {
    const action = candidateActionToken(candidate);
    return this.commitWeight * getCount(this.committed, context, action)
      - this.rejectWeight * getCount(this.rejected, context, action);
  }

  rank<T>(context: string, candidates: T[]): T[] {
    return candidates
      .map((candidate, index) => ({ candidate, index }))
      .sort((a, b) => {
        const aAction = candidateActionToken(a.candidate);
        const bAction = candidateActionToken(b.candidate);
        const aScore = this.score(context, a.candidate);
        const bScore = this.score(context, b.candidate);
        if (aScore !== bScore) {
          return bScore - aScore;
        }
        const aCommitted = getCount(this.committed, context, aAction);
        const bCommitted = getCount(this.committed, context, bAction);
        if (aCommitted !== bCommitted) {
          return bCommitted - aCommitted;
        }
        const aRejected = getCount(this.rejected, context, aAction);
        const bRejected = getCount(this.rejected, context, bAction);
        if (aRejected !== bRejected) {
          return aRejected - bRejected;
        }
        if (a.index !== b.index) {
          return a.index - b.index;
        }
        return aAction < bAction ? -1 : aAction > bAction ? 1 : 0;
      })
      .map((row) => row.candidate);
  }

  async snapshot(): Promise<ReceiptTrainedReversibleProposerSnapshot> {
    const contexts = new Set([...this.committed.keys(), ...this.rejected.keys()]);
    const rows: ReversibleProposerSnapshotRow[] = [];
    for (const context of [...contexts].sort()) {
      const actions = new Set([
        ...(this.committed.get(context)?.keys() ?? []),
        ...(this.rejected.get(context)?.keys() ?? []),
      ]);
      for (const action of [...actions].sort()) {
        const committed = getCount(this.committed, context, action);
        const rejected = getCount(this.rejected, context, action);
        rows.push({
          context,
          action,
          committed,
          rejected,
          observations: committed + rejected,
          score: roundFloat(this.commitWeight * committed - this.rejectWeight * rejected),
        });
      }
    }
    const pending: ReceiptTrainedReversibleProposerSnapshot = {
      schemaVersion: RECEIPT_TRAINED_REVERSIBLE_PROPOSER_SNAPSHOT_SCHEMA,
      learnerId: this.learnerId,
      learnerVersion: this.learnerVersion,
      receiptHashes: [...this.receiptHashes],
      rows,
      snapshotHash: "",
    };
    return { ...pending, snapshotHash: await receiptTrainedReversibleProposerSnapshotHash(pending) };
  }
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

export async function receiptTrainedReversibleProposerSnapshotHash(
  snapshot: ReceiptTrainedReversibleProposerSnapshot,
): Promise<string> {
  const { snapshotHash: _snapshotHash, ...withoutHash } = snapshot;
  return stableHash(withoutHash);
}

export async function validateReceiptTrainedReversibleProposerSnapshot(
  snapshot: ReceiptTrainedReversibleProposerSnapshot,
): Promise<boolean> {
  try {
    if (snapshot.schemaVersion !== RECEIPT_TRAINED_REVERSIBLE_PROPOSER_SNAPSHOT_SCHEMA) {
      return false;
    }
    if (!snapshot.learnerId || !snapshot.learnerVersion) {
      return false;
    }
    if (!snapshot.receiptHashes.every(isHash)) {
      return false;
    }
    if (new Set(snapshot.receiptHashes).size !== snapshot.receiptHashes.length) {
      return false;
    }
    const sortedRows = [...snapshot.rows].sort((a, b) =>
      a.context.localeCompare(b.context) || a.action.localeCompare(b.action),
    );
    if (JSON.stringify(sortedRows) !== JSON.stringify(snapshot.rows)) {
      return false;
    }
    for (const row of snapshot.rows) {
      if (!row.context || !row.action) {
        return false;
      }
      const values = [row.committed, row.rejected, row.observations];
      if (values.some((value) => !Number.isInteger(value) || value < 0)) {
        return false;
      }
      if (row.observations !== row.committed + row.rejected) {
        return false;
      }
      if (!Number.isFinite(row.score)) {
        return false;
      }
    }
    return snapshot.snapshotHash === await receiptTrainedReversibleProposerSnapshotHash(snapshot);
  } catch {
    return false;
  }
}

function candidateActionToken(candidate: unknown): string {
  let payload = candidate;
  if (candidate && typeof candidate === "object" && "payload" in candidate) {
    payload = (candidate as TypedCandidate<Record<string, unknown>>).payload;
  }
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const row = payload as Record<string, unknown>;
    return tokenFromUnknown(row.action ?? row.proposalSignature ?? row.guess ?? row);
  }
  return tokenFromUnknown(payload);
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

function isHash(value: string): boolean {
  return /^[0-9a-f]{64}$/.test(value);
}

function roundFloat(value: number): number {
  return Number(value.toFixed(12));
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
