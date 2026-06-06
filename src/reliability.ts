import { stableHash } from "./canonical.js";
import type { Receipt } from "./core.js";

export const RELIABILITY_SNAPSHOT_SCHEMA = "trwm.reliability_snapshot.v1";

export interface VerifierReliabilityRow {
  subjectId: string;
  auditedSuccesses: number;
  auditedFailures: number;
  blockedUnknown: number;
  observations: number;
  posteriorMean: number;
  wilsonLowerBound: number;
  riskScore: number;
}

export interface VerifierReliabilitySnapshot {
  schemaVersion: string;
  rows: VerifierReliabilityRow[];
  priorSuccess: number;
  priorFailure: number;
  z: number;
  snapshotHash: string;
}

export class VerifierReliabilityMemory {
  priorSuccess: number;
  priorFailure: number;
  z: number;
  private rows = new Map<string, VerifierReliabilityRow>();

  constructor(options: { priorSuccess?: number; priorFailure?: number; z?: number } = {}) {
    this.priorSuccess = options.priorSuccess ?? 1;
    this.priorFailure = options.priorFailure ?? 1;
    this.z = options.z ?? 1.96;
    if (this.priorSuccess <= 0 || this.priorFailure <= 0) {
      throw new RangeError("priors must be positive");
    }
    if (this.z <= 0) {
      throw new RangeError("z must be positive");
    }
  }

  update(subjectId: string, auditedSuccess: boolean | null): VerifierReliabilityRow {
    const subject = String(subjectId);
    if (!subject) {
      throw new RangeError("subjectId must be non-empty");
    }
    const current = this.rows.get(subject) ?? this.score(subject);
    const pending = { ...current };
    pending.observations += 1;
    if (auditedSuccess === true) {
      pending.auditedSuccesses += 1;
    } else if (auditedSuccess === false) {
      pending.auditedFailures += 1;
    } else {
      pending.blockedUnknown += 1;
    }
    const scored = this.scored(pending);
    this.rows.set(subject, scored);
    return scored;
  }

  updateFromReceipt(receipt: Receipt): VerifierReliabilityRow | null {
    const residual = receipt.hardResult.residual;
    const metadata = receipt.hardResult.metadata;
    if (isRecord(residual) && valueAt(residual, "kind") === "verifier_false_positive") {
      const subject = valueAt(residual, "primaryVerifierId", "primary_verifier_id");
      const auditResult = String(valueAt(residual, "auditResult", "audit_result") ?? "");
      if (subject) {
        return this.update(String(subject), auditResult === "reject" ? false : null);
      }
    }
    const primaryResult = String(valueAt(metadata, "primaryResult", "primary_result") ?? "");
    const auditResult = String(valueAt(metadata, "auditResult", "audit_result") ?? "");
    const subject = valueAt(metadata, "primaryVerifierId", "primary_verifier_id");
    if (receipt.hardResult.result === "accept" && primaryResult === "accept" && auditResult === "accept" && subject) {
      return this.update(String(subject), true);
    }
    return null;
  }

  score(subjectId: string): VerifierReliabilityRow {
    const subject = String(subjectId);
    return this.rows.get(subject) ?? this.scored({
      subjectId: subject,
      auditedSuccesses: 0,
      auditedFailures: 0,
      blockedUnknown: 0,
      observations: 0,
      posteriorMean: 0.5,
      wilsonLowerBound: 0,
      riskScore: 1,
    });
  }

  rankForAudit(subjectIds: string[]): string[] {
    return Array.from(new Set(subjectIds.map(String).filter(Boolean)))
      .map((subject) => this.score(subject))
      .sort((a, b) =>
        b.riskScore - a.riskScore
        || b.auditedFailures - a.auditedFailures
        || compareCodePoint(a.subjectId, b.subjectId)
      )
      .map((row) => row.subjectId);
  }

  selectForAudit(subjectIds: string[], maxAudits: number): string[] {
    if (!Number.isInteger(maxAudits) || maxAudits < 0) {
      throw new RangeError("maxAudits must be a non-negative integer");
    }
    return this.rankForAudit(subjectIds).slice(0, maxAudits);
  }

  async snapshot(): Promise<VerifierReliabilitySnapshot> {
    const pending: VerifierReliabilitySnapshot = {
      schemaVersion: RELIABILITY_SNAPSHOT_SCHEMA,
      rows: Array.from(this.rows.values()).sort((a, b) => compareCodePoint(a.subjectId, b.subjectId)),
      priorSuccess: this.priorSuccess,
      priorFailure: this.priorFailure,
      z: this.z,
      snapshotHash: "",
    };
    return { ...pending, snapshotHash: await verifierReliabilitySnapshotHash(pending) };
  }

  private scored(row: VerifierReliabilityRow): VerifierReliabilityRow {
    const n = row.auditedSuccesses + row.auditedFailures;
    const posteriorMean = (this.priorSuccess + row.auditedSuccesses)
      / (this.priorSuccess + this.priorFailure + n);
    const lower = wilsonLowerBound(row.auditedSuccesses, row.auditedFailures, this.z);
    return {
      ...row,
      posteriorMean: roundFloat(posteriorMean),
      wilsonLowerBound: roundFloat(lower),
      riskScore: roundFloat(1 - lower),
    };
  }
}

export function wilsonLowerBound(successes: number, failures: number, z = 1.96): number {
  if (!Number.isInteger(successes) || !Number.isInteger(failures) || successes < 0 || failures < 0) {
    throw new RangeError("successes and failures must be non-negative integers");
  }
  const n = successes + failures;
  if (n === 0) {
    return 0;
  }
  const phat = successes / n;
  const z2 = z * z;
  const denominator = 1 + z2 / n;
  const center = phat + z2 / (2 * n);
  const margin = z * Math.sqrt((phat * (1 - phat) / n) + (z2 / (4 * n * n)));
  return Math.max(0, (center - margin) / denominator);
}

export async function verifierReliabilitySnapshotHash(snapshot: VerifierReliabilitySnapshot): Promise<string> {
  const { snapshotHash: _snapshotHash, ...withoutHash } = snapshot;
  return stableHash(withoutHash);
}

export async function validateVerifierReliabilitySnapshot(snapshot: VerifierReliabilitySnapshot): Promise<boolean> {
  if (snapshot.schemaVersion !== RELIABILITY_SNAPSHOT_SCHEMA) {
    return false;
  }
  if (snapshot.rows.some((row) => !row.subjectId)) {
    return false;
  }
  if (new Set(snapshot.rows.map((row) => row.subjectId)).size !== snapshot.rows.length) {
    return false;
  }
  return snapshot.snapshotHash === await verifierReliabilitySnapshotHash(snapshot);
}

function valueAt(record: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(record, key)) {
      return record[key];
    }
  }
  return undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function compareCodePoint(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function roundFloat(value: number): number {
  return Math.round(value * 1_000_000_000_000) / 1_000_000_000_000;
}
