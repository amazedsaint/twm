import { stableHash } from "./canonical.js";
import { DeltaToken } from "./reversible.js";

export const PARALLEL_REPLAY_CERTIFICATE_SCHEMA = "trwm.parallel_replay_certificate.v1";

export interface ReplayToken {
  readSet: Set<string>;
  writeSet: Set<string>;
  apply(state: Record<string, unknown>): Record<string, unknown>;
  inverse(): ReplayToken;
}

export interface ParallelReplayCertificate {
  schemaVersion: string;
  tokenCount: number;
  batchCount: number;
  conflictCount: number;
  maxBatchWidth: number;
  batches: number[][];
  sequentialStateHash: string;
  parallelStateHash: string;
  certificateHash: string;
}

export function tokenConflicts(left: ReplayToken, right: ReplayToken): boolean {
  return intersects(left.writeSet, right.readSet)
    || intersects(right.writeSet, left.readSet)
    || intersects(left.writeSet, right.writeSet);
}

export function parallelBatches(tokens: Iterable<ReplayToken>): number[][] {
  const rows = Array.from(tokens);
  const batches: number[][] = [];
  const assigned: number[] = [];

  for (const [idx, token] of rows.entries()) {
    let minBatch = 0;
    for (let prevIdx = 0; prevIdx < idx; prevIdx += 1) {
      if (tokenConflicts(rows[prevIdx], token)) {
        minBatch = Math.max(minBatch, assigned[prevIdx] + 1);
      }
    }

    let target = minBatch;
    while (true) {
      while (batches.length <= target) {
        batches.push([]);
      }
      if (batches[target].every((other) => !tokenConflicts(rows[other], token))) {
        batches[target].push(idx);
        assigned.push(target);
        break;
      }
      target += 1;
    }
  }

  return batches;
}

export function sequentialReplay(
  state: Record<string, unknown>,
  tokens: Iterable<ReplayToken>,
): Record<string, unknown> {
  let current = { ...state };
  for (const token of tokens) {
    current = token.apply(current);
  }
  return current;
}

export function parallelReplay(
  state: Record<string, unknown>,
  tokens: Iterable<ReplayToken>,
  batches: Iterable<Iterable<number>>,
): Record<string, unknown> {
  const rows = Array.from(tokens);
  let current = { ...state };
  for (const batch of batches) {
    const indices = Array.from(batch);
    validateBatch(rows, indices);
    for (const idx of indices) {
      current = rows[idx].apply(current);
    }
  }
  return current;
}

export async function buildParallelReplayCertificate(
  state: Record<string, unknown>,
  tokens: Iterable<ReplayToken>,
): Promise<ParallelReplayCertificate> {
  const rows = Array.from(tokens);
  const batches = parallelBatches(rows);
  const sequential = sequentialReplay(state, rows);
  const parallel = parallelReplay(state, rows, batches);
  const pending: ParallelReplayCertificate = {
    schemaVersion: PARALLEL_REPLAY_CERTIFICATE_SCHEMA,
    tokenCount: rows.length,
    batchCount: batches.length,
    conflictCount: countConflicts(rows),
    maxBatchWidth: Math.max(0, ...batches.map((batch) => batch.length)),
    batches,
    sequentialStateHash: await stableHash(sequential),
    parallelStateHash: await stableHash(parallel),
    certificateHash: "",
  };
  return { ...pending, certificateHash: await parallelReplayCertificateHash(pending) };
}

export async function auditParallelReplay(
  state: Record<string, unknown>,
  tokens: Iterable<ReplayToken>,
  certificate: ParallelReplayCertificate,
): Promise<boolean> {
  if (!await validateParallelReplayCertificate(certificate)) {
    return false;
  }
  const rows = Array.from(tokens);
  if (certificate.tokenCount !== rows.length) {
    return false;
  }
  if (certificate.conflictCount !== countConflicts(rows)) {
    return false;
  }
  const flat = certificate.batches.flat();
  if (!sameIndices(flat, rows.length)) {
    return false;
  }
  try {
    const sequential = sequentialReplay(state, rows);
    const parallel = parallelReplay(state, rows, certificate.batches);
    return await stableHash(sequential) === certificate.sequentialStateHash
      && await stableHash(parallel) === certificate.parallelStateHash
      && await stableHash(sequential) === await stableHash(parallel);
  } catch (_error) {
    return false;
  }
}

export async function validateParallelReplayCertificate(certificate: ParallelReplayCertificate): Promise<boolean> {
  if (certificate.schemaVersion !== PARALLEL_REPLAY_CERTIFICATE_SCHEMA) {
    return false;
  }
  if (!nonNegativeInteger(certificate.tokenCount)
    || !nonNegativeInteger(certificate.batchCount)
    || !nonNegativeInteger(certificate.conflictCount)
    || !nonNegativeInteger(certificate.maxBatchWidth)) {
    return false;
  }
  if (certificate.batchCount !== certificate.batches.length) {
    return false;
  }
  if (certificate.maxBatchWidth !== Math.max(0, ...certificate.batches.map((batch) => batch.length))) {
    return false;
  }
  if (!sameIndices(certificate.batches.flat(), certificate.tokenCount)) {
    return false;
  }
  if (!isHash(certificate.sequentialStateHash) || !isHash(certificate.parallelStateHash)) {
    return false;
  }
  return certificate.certificateHash === await parallelReplayCertificateHash(certificate);
}

export async function parallelReplayCertificateHash(certificate: ParallelReplayCertificate): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function randomizedParallelReplayTrials(options: {
  seed?: number;
  trials?: number;
  keyCount?: number;
  tokenCount?: number;
} = {}): Promise<{ trials: number; mismatches: number }> {
  const seed = options.seed ?? 11;
  const trials = options.trials ?? 64;
  const keyCount = options.keyCount ?? 5;
  const tokenCount = options.tokenCount ?? 12;
  if (!nonNegativeInteger(trials) || !Number.isInteger(keyCount) || keyCount <= 0 || !nonNegativeInteger(tokenCount)) {
    throw new RangeError("invalid randomized trial parameters");
  }
  const rng = mulberry32(seed >>> 0);
  let mismatches = 0;
  for (let trial = 0; trial < trials; trial += 1) {
    const state: Record<string, number> = {};
    for (let idx = 0; idx < keyCount; idx += 1) {
      state[`k${idx}`] = 0;
    }
    const current = { ...state };
    const tokens: DeltaToken[] = [];
    for (let idx = 0; idx < tokenCount; idx += 1) {
      const key = `k${Math.floor(rng() * keyCount)}`;
      const before = current[key];
      const after = before + 1 + Math.floor(rng() * 3);
      tokens.push(new DeltaToken(key, before, after));
      current[key] = after;
    }
    const certificate = await buildParallelReplayCertificate(state, tokens);
    if (!await auditParallelReplay(state, tokens, certificate)) {
      mismatches += 1;
    }
  }
  return { trials, mismatches };
}

function validateBatch(tokens: ReplayToken[], batch: number[]): void {
  for (const [offset, leftIdx] of batch.entries()) {
    if (!Number.isInteger(leftIdx) || leftIdx < 0 || leftIdx >= tokens.length) {
      throw new RangeError("parallel batch index out of range");
    }
    for (const rightIdx of batch.slice(offset + 1)) {
      if (!Number.isInteger(rightIdx) || rightIdx < 0 || rightIdx >= tokens.length) {
        throw new RangeError("parallel batch index out of range");
      }
      if (tokenConflicts(tokens[leftIdx], tokens[rightIdx])) {
        throw new Error("parallel batch contains conflicting tokens");
      }
    }
  }
}

function countConflicts(tokens: ReplayToken[]): number {
  let count = 0;
  for (let left = 0; left < tokens.length; left += 1) {
    for (let right = left + 1; right < tokens.length; right += 1) {
      if (tokenConflicts(tokens[left], tokens[right])) {
        count += 1;
      }
    }
  }
  return count;
}

function sameIndices(indices: number[], count: number): boolean {
  if (indices.length !== count) {
    return false;
  }
  const seen = new Set(indices);
  if (seen.size !== count) {
    return false;
  }
  for (let idx = 0; idx < count; idx += 1) {
    if (!seen.has(idx)) {
      return false;
    }
  }
  return indices.every((idx) => Number.isInteger(idx) && idx >= 0 && idx < count);
}

function intersects(left: Set<string>, right: Set<string>): boolean {
  for (const key of left) {
    if (right.has(key)) {
      return true;
    }
  }
  return false;
}

function nonNegativeInteger(value: number): boolean {
  return Number.isInteger(value) && value >= 0;
}

function isHash(value: string): boolean {
  return /^[0-9a-f]{64}$/.test(value);
}

function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6D2B79F5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}
