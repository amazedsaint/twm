import { compareCodePoint, canonicalJson, stableHash } from "./canonical.js";
import { BlockToken, DeltaToken } from "./reversible.js";

export const CIRCULAR_TOKEN_LOG_CERTIFICATE_SCHEMA = "trwm.circular_token_log_certificate.v1";

export interface CircularTokenLogCertificate {
  schemaVersion: string;
  capacity: number;
  totalTokenCount: number;
  compactedPrefixCount: number;
  suffixCount: number;
  compactedDeltaCount: number;
  compactedTokens: DeltaToken[];
  suffixTokens: DeltaToken[];
  baseStateHash: string;
  compactedStateHash: string;
  finalStateHash: string;
  compactedTokenHash: string;
  suffixTokenHash: string;
  certificateHash: string;
}

export class CircularTokenLog {
  capacity: number;
  baseState: Record<string, unknown>;
  totalTokenCount: number;
  compactedPrefixCount: number;
  compactedTokens: DeltaToken[];
  suffixTokens: DeltaToken[];

  constructor(params: {
    capacity: number;
    baseState: Record<string, unknown>;
    totalTokenCount?: number;
    compactedPrefixCount?: number;
    compactedTokens?: DeltaToken[];
    suffixTokens?: DeltaToken[];
  }) {
    if (!positiveInteger(params.capacity)) {
      throw new RangeError("circular token log capacity must be a positive integer");
    }
    this.capacity = params.capacity;
    this.baseState = { ...params.baseState };
    this.totalTokenCount = params.totalTokenCount ?? 0;
    this.compactedPrefixCount = params.compactedPrefixCount ?? 0;
    this.compactedTokens = [...(params.compactedTokens ?? [])];
    this.suffixTokens = [...(params.suffixTokens ?? [])];
    if (this.suffixTokens.length > this.capacity) {
      throw new RangeError("suffix length exceeds circular token log capacity");
    }
  }

  static fromTokens(baseState: Record<string, unknown>, tokens: Iterable<DeltaToken>, capacity: number): CircularTokenLog {
    let log = new CircularTokenLog({ capacity, baseState });
    for (const token of tokens) {
      log = log.append(token);
    }
    return log;
  }

  append(token: DeltaToken): CircularTokenLog {
    let nextSuffix = [...this.suffixTokens, token];
    let compactedTokens = this.compactedTokens;
    let compactedPrefixCount = this.compactedPrefixCount;
    if (nextSuffix.length > this.capacity) {
      const evicted = nextSuffix[0];
      nextSuffix = nextSuffix.slice(1);
      compactedTokens = compactTokenPrefix(this.baseState, [...compactedTokens, evicted]);
      compactedPrefixCount += 1;
    }
    return new CircularTokenLog({
      capacity: this.capacity,
      baseState: this.baseState,
      totalTokenCount: this.totalTokenCount + 1,
      compactedPrefixCount,
      compactedTokens,
      suffixTokens: nextSuffix,
    });
  }

  replay(): Record<string, unknown> {
    return replayCircularTokenLog(this.baseState, this.compactedTokens, this.suffixTokens);
  }

  compactedState(): Record<string, unknown> {
    return this.compactedTokens.length > 0 ? BlockToken.of(this.compactedTokens).apply(this.baseState) : { ...this.baseState };
  }

  async certificate(): Promise<CircularTokenLogCertificate> {
    const compactedState = this.compactedState();
    const finalState = this.replay();
    const pending: CircularTokenLogCertificate = {
      schemaVersion: CIRCULAR_TOKEN_LOG_CERTIFICATE_SCHEMA,
      capacity: this.capacity,
      totalTokenCount: this.totalTokenCount,
      compactedPrefixCount: this.compactedPrefixCount,
      suffixCount: this.suffixTokens.length,
      compactedDeltaCount: this.compactedTokens.length,
      compactedTokens: this.compactedTokens,
      suffixTokens: this.suffixTokens,
      baseStateHash: await stableHash(this.baseState),
      compactedStateHash: await stableHash(compactedState),
      finalStateHash: await stableHash(finalState),
      compactedTokenHash: await tokenSequenceHash(this.compactedTokens),
      suffixTokenHash: await tokenSequenceHash(this.suffixTokens),
      certificateHash: "",
    };
    return { ...pending, certificateHash: await circularTokenLogCertificateHash(pending) };
  }
}

export function compactTokenPrefix(baseState: Record<string, unknown>, tokens: Iterable<DeltaToken>): DeltaToken[] {
  const base = { ...baseState };
  let current: Record<string, unknown> = { ...base };
  const touched = new Set<string>();
  for (const token of tokens) {
    current = token.apply(current);
    for (const key of token.readSet) touched.add(key);
    for (const key of token.writeSet) touched.add(key);
  }
  const compacted: DeltaToken[] = [];
  for (const key of Array.from(touched).sort(compareCodePoint)) {
    if (!Object.prototype.hasOwnProperty.call(base, key)) {
      throw new Error(`cannot compact missing base key: ${key}`);
    }
    if (canonicalJson(current[key]) !== canonicalJson(base[key])) {
      compacted.push(new DeltaToken(key, base[key], current[key]));
    }
  }
  return compacted;
}

export function replayCircularTokenLog(
  baseState: Record<string, unknown>,
  compactedTokens: Iterable<DeltaToken>,
  suffixTokens: Iterable<DeltaToken>,
): Record<string, unknown> {
  let current = { ...baseState };
  const compacted = Array.from(compactedTokens);
  const suffix = Array.from(suffixTokens);
  if (compacted.length > 0) {
    current = BlockToken.of(compacted).apply(current);
  }
  if (suffix.length > 0) {
    current = BlockToken.of(suffix).apply(current);
  }
  return current;
}

export async function buildCircularTokenLogCertificate(
  baseState: Record<string, unknown>,
  tokens: Iterable<DeltaToken>,
  options: { capacity: number },
): Promise<CircularTokenLogCertificate> {
  const rows = Array.from(tokens);
  const log = CircularTokenLog.fromTokens(baseState, rows, options.capacity);
  const fullState = rows.length > 0 ? BlockToken.of(rows).apply(baseState) : { ...baseState };
  const compactedState = log.replay();
  if (canonicalJson(fullState) !== canonicalJson(compactedState)) {
    throw new Error("circular token log compaction changed replay state");
  }
  return log.certificate();
}

export async function auditCircularTokenLog(
  baseState: Record<string, unknown>,
  certificate: CircularTokenLogCertificate,
  originalTokens?: Iterable<DeltaToken>,
): Promise<boolean> {
  if (!await validateCircularTokenLogCertificate(certificate)) {
    return false;
  }
  try {
    if (await stableHash(baseState) !== certificate.baseStateHash) {
      return false;
    }
    const compactedState = certificate.compactedTokens.length > 0
      ? BlockToken.of(certificate.compactedTokens).apply(baseState)
      : { ...baseState };
    const finalState = replayCircularTokenLog(baseState, certificate.compactedTokens, certificate.suffixTokens);
    const inverseState = inverseReplay(finalState, certificate.compactedTokens, certificate.suffixTokens);
    if (await stableHash(compactedState) !== certificate.compactedStateHash) {
      return false;
    }
    if (await stableHash(finalState) !== certificate.finalStateHash) {
      return false;
    }
    if (canonicalJson(inverseState) !== canonicalJson(baseState)) {
      return false;
    }
    if (originalTokens) {
      const rebuilt = await buildCircularTokenLogCertificate(baseState, originalTokens, { capacity: certificate.capacity });
      if (rebuilt.certificateHash !== certificate.certificateHash) {
        return false;
      }
    }
    return true;
  } catch (_error) {
    return false;
  }
}

export async function validateCircularTokenLogCertificate(certificate: CircularTokenLogCertificate): Promise<boolean> {
  try {
    if (certificate.schemaVersion !== CIRCULAR_TOKEN_LOG_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (!positiveInteger(certificate.capacity)
      || !nonNegativeInteger(certificate.totalTokenCount)
      || !nonNegativeInteger(certificate.compactedPrefixCount)
      || !nonNegativeInteger(certificate.suffixCount)
      || !nonNegativeInteger(certificate.compactedDeltaCount)) {
      return false;
    }
    if (certificate.suffixCount !== certificate.suffixTokens.length) {
      return false;
    }
    if (certificate.compactedDeltaCount !== certificate.compactedTokens.length) {
      return false;
    }
    if (certificate.suffixCount > certificate.capacity) {
      return false;
    }
    if (certificate.totalTokenCount !== certificate.compactedPrefixCount + certificate.suffixCount) {
      return false;
    }
    if (certificate.compactedTokenHash !== await tokenSequenceHash(certificate.compactedTokens)) {
      return false;
    }
    if (certificate.suffixTokenHash !== await tokenSequenceHash(certificate.suffixTokens)) {
      return false;
    }
    return certificate.certificateHash === await circularTokenLogCertificateHash(certificate);
  } catch (_error) {
    return false;
  }
}

export async function circularTokenLogCertificateHash(
  certificate: CircularTokenLogCertificate | Record<string, unknown>,
): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function tokenSequenceHash(tokens: Iterable<DeltaToken>): Promise<string> {
  return stableHash(Array.from(tokens));
}

export async function randomizedCircularTokenLogTrials(options: {
  seed?: number;
  trials?: number;
  keyCount?: number;
  tokenCount?: number;
  capacity?: number;
} = {}): Promise<{ trials: number; mismatches: number }> {
  const seed = options.seed ?? 17;
  const trials = options.trials ?? 64;
  const keyCount = options.keyCount ?? 5;
  const tokenCount = options.tokenCount ?? 14;
  const capacity = options.capacity ?? 4;
  if (!nonNegativeInteger(trials) || !positiveInteger(keyCount) || !nonNegativeInteger(tokenCount) || !positiveInteger(capacity)) {
    throw new RangeError("invalid randomized circular token log trial parameters");
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
      let after = before + Math.floor(rng() * 6) - 2;
      if (after === before) {
        after += 1;
      }
      tokens.push(new DeltaToken(key, before, after));
      current[key] = after;
    }
    const certificate = await buildCircularTokenLogCertificate(state, tokens, { capacity });
    if (!await auditCircularTokenLog(state, certificate, tokens)) {
      mismatches += 1;
    }
  }
  return { trials, mismatches };
}

function inverseReplay(
  finalState: Record<string, unknown>,
  compactedTokens: Iterable<DeltaToken>,
  suffixTokens: Iterable<DeltaToken>,
): Record<string, unknown> {
  let current = { ...finalState };
  const suffix = Array.from(suffixTokens);
  const compacted = Array.from(compactedTokens);
  if (suffix.length > 0) {
    current = BlockToken.of(suffix).inverse().apply(current);
  }
  if (compacted.length > 0) {
    current = BlockToken.of(compacted).inverse().apply(current);
  }
  return current;
}

function positiveInteger(value: number): boolean {
  return Number.isInteger(value) && value > 0;
}

function nonNegativeInteger(value: number): boolean {
  return Number.isInteger(value) && value >= 0;
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
