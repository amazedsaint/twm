import { stableHash } from "./canonical.js";
import type { Receipt } from "./core.js";

export const REDACTION_SCHEMA = "trwm.redacted_receipt.v1";
export const REDACTION_POLICY_SCHEMA = "trwm.redaction_policy.v1";
export const REDACTION_COMMITMENT_SCHEMA = "trwm.redaction_commitment.v1";
export const REDACTION_MARKER_SCHEMA = "trwm.redaction_marker.v1";

export interface RedactionPolicy {
  schemaVersion: string;
  policyId: string;
  paths: string[];
}

export interface RedactionCommitment {
  schemaVersion: string;
  path: string;
  commitmentHash: string;
  markerHash: string;
}

export interface RedactionMarker {
  schemaVersion: string;
  redacted: true;
  path: string;
  commitmentHash: string;
}

export interface RedactedReceiptView {
  schemaVersion: string;
  originalReceiptHash: string;
  redactionPolicy: RedactionPolicy;
  policyHash: string;
  redactedPayload: Record<string, unknown>;
  commitments: RedactionCommitment[];
  redactedHash: string;
}

const disallowedRedactionPaths = new Set([
  "receipt_hash",
  "receiptHash",
  "parent_head",
  "parentHead",
  "commit_decision",
  "commitDecision",
  "committed",
  "hard_result.result",
  "hardResult.result",
  "hard_result.verifier_id",
  "hardResult.verifierId",
  "hard_result.verifier_version",
  "hardResult.verifierVersion",
  "receipt_schema",
  "receiptSchema",
]);

export function makeRedactionPolicy(paths: string[], policyId = "receipt.redaction"): RedactionPolicy {
  return normalizeRedactionPolicy({ schemaVersion: REDACTION_POLICY_SCHEMA, policyId, paths });
}

export function normalizeRedactionPolicy(policy: Partial<RedactionPolicy>): RedactionPolicy {
  const normalized: RedactionPolicy = {
    schemaVersion: String(policy.schemaVersion ?? REDACTION_POLICY_SCHEMA),
    policyId: String(policy.policyId ?? "receipt.redaction"),
    paths: (policy.paths ?? []).map(String),
  };
  if (normalized.schemaVersion !== REDACTION_POLICY_SCHEMA) {
    throw new Error(`invalid redaction policy schema: ${normalized.schemaVersion}`);
  }
  if (normalized.paths.length === 0) {
    throw new Error("redaction policy requires at least one path");
  }
  if (new Set(normalized.paths).size !== normalized.paths.length) {
    throw new Error("redaction policy paths must be unique");
  }
  for (const path of normalized.paths) {
    validateRedactionPath(path);
  }
  return normalized;
}

export async function redactionPolicyHash(policy: RedactionPolicy): Promise<string> {
  return stableHash(normalizeRedactionPolicy(policy));
}

export async function redactionCommitmentHash(path: string, value: unknown, salt: string): Promise<string> {
  validateRedactionPath(path);
  return stableHash({
    schemaVersion: REDACTION_COMMITMENT_SCHEMA,
    path,
    salt: String(salt),
    value,
  });
}

export async function redactReceipt(
  receipt: Receipt | Record<string, unknown>,
  policyInput: RedactionPolicy,
  salt: string,
): Promise<RedactedReceiptView> {
  const policy = normalizeRedactionPolicy(policyInput);
  const payload = cloneRecord(receipt as Record<string, unknown>);
  const originalReceiptHash = originalReceiptHashFromPayload(payload);
  const commitments: RedactionCommitment[] = [];
  for (const path of policy.paths) {
    const found = getPath(payload, path);
    if (!found.exists) {
      throw new Error(`redaction path not found: ${path}`);
    }
    const commitmentHash = await redactionCommitmentHash(path, found.value, salt);
    const marker = redactionMarker(path, commitmentHash);
    setPath(payload, path, marker);
    commitments.push({
      schemaVersion: REDACTION_COMMITMENT_SCHEMA,
      path,
      commitmentHash,
      markerHash: await stableHash(marker),
    });
  }
  const view: RedactedReceiptView = {
    schemaVersion: REDACTION_SCHEMA,
    originalReceiptHash,
    redactionPolicy: policy,
    policyHash: await redactionPolicyHash(policy),
    redactedPayload: payload,
    commitments,
    redactedHash: "",
  };
  return { ...view, redactedHash: await redactedReceiptHash(view) };
}

export async function redactedReceiptHash(view: RedactedReceiptView | Record<string, unknown>): Promise<string> {
  const { redactedHash: _redactedHash, ...withoutHash } = view as Record<string, unknown>;
  return stableHash(withoutHash);
}

export async function validateRedactedReceipt(view: RedactedReceiptView | Record<string, unknown>): Promise<boolean> {
  try {
    if (!isRecord(view)) {
      return false;
    }
    if (view.schemaVersion !== REDACTION_SCHEMA) {
      return false;
    }
    if (!isHexHash(String(view.originalReceiptHash ?? ""))) {
      return false;
    }
    if (!isRecord(view.redactionPolicy)) {
      return false;
    }
    const policy = normalizeRedactionPolicy(view.redactionPolicy as Partial<RedactionPolicy>);
    if (view.policyHash !== await redactionPolicyHash(policy)) {
      return false;
    }
    if (!Array.isArray(view.commitments)) {
      return false;
    }
    const commitments = view.commitments.map(coerceCommitment);
    if (commitments.map((item) => item.path).join("\n") !== policy.paths.join("\n")) {
      return false;
    }
    if (view.redactedHash !== await redactedReceiptHash(view)) {
      return false;
    }
    if (!isRecord(view.redactedPayload)) {
      return false;
    }
    for (const commitment of commitments) {
      const found = getPath(view.redactedPayload as Record<string, unknown>, commitment.path);
      if (!found.exists || !isRecord(found.value)) {
        return false;
      }
      const marker = redactionMarker(commitment.path, commitment.commitmentHash);
      if (await stableHash(found.value) !== await stableHash(marker)) {
        return false;
      }
      if (commitment.markerHash !== await stableHash(marker)) {
        return false;
      }
    }
    return true;
  } catch {
    return false;
  }
}

export async function verifyRedactedPath(
  view: RedactedReceiptView | Record<string, unknown>,
  path: string,
  value: unknown,
  salt: string,
): Promise<boolean> {
  if (!await validateRedactedReceipt(view)) {
    return false;
  }
  const commitments = ((view as RedactedReceiptView).commitments ?? []).map(coerceCommitment);
  const commitment = commitments.find((item) => item.path === path);
  if (!commitment) {
    return false;
  }
  return commitment.commitmentHash === await redactionCommitmentHash(path, value, salt);
}

export function redactedReceiptCannotReplay(view: RedactedReceiptView | Record<string, unknown>): boolean {
  const payload = (view as RedactedReceiptView).redactedPayload;
  if (!isRecord(payload)) {
    return true;
  }
  for (const key of ["replay_bundle", "replayBundle", "rollback_bundle", "rollbackBundle"]) {
    if (Object.prototype.hasOwnProperty.call(payload, key) && containsRedactionMarker(payload[key])) {
      return true;
    }
  }
  return false;
}

function validateRedactionPath(path: string): void {
  if (!path || path.trim() !== path) {
    throw new Error("redaction paths must be non-empty and trimmed");
  }
  if (path.includes("..") || path.split(".").some((part) => !part)) {
    throw new Error(`invalid redaction path: ${path}`);
  }
  if (disallowedRedactionPaths.has(path)) {
    throw new Error(`redaction path must stay visible for auditability: ${path}`);
  }
}

function redactionMarker(path: string, commitmentHash: string): RedactionMarker {
  return {
    schemaVersion: REDACTION_MARKER_SCHEMA,
    redacted: true,
    path,
    commitmentHash,
  };
}

function originalReceiptHashFromPayload(payload: Record<string, unknown>): string {
  const value = String(payload.receiptHash ?? payload.receipt_hash ?? "");
  if (!isHexHash(value)) {
    throw new Error("redacted receipt view requires a finalized original receipt hash");
  }
  return value;
}

function coerceCommitment(value: unknown): RedactionCommitment {
  if (!isRecord(value)) {
    throw new Error("redaction commitment must be an object");
  }
  const commitment = {
    schemaVersion: String(value.schemaVersion ?? REDACTION_COMMITMENT_SCHEMA),
    path: String(value.path ?? ""),
    commitmentHash: String(value.commitmentHash ?? ""),
    markerHash: String(value.markerHash ?? ""),
  };
  if (commitment.schemaVersion !== REDACTION_COMMITMENT_SCHEMA) {
    throw new Error(`invalid redaction commitment schema: ${commitment.schemaVersion}`);
  }
  return commitment;
}

function getPath(root: unknown, path: string): { exists: boolean; value?: unknown } {
  let current = root;
  for (const part of path.split(".")) {
    if (Array.isArray(current)) {
      if (!/^\d+$/.test(part)) {
        return { exists: false };
      }
      const idx = Number(part);
      if (idx < 0 || idx >= current.length) {
        return { exists: false };
      }
      current = current[idx];
    } else if (isRecord(current)) {
      if (!Object.prototype.hasOwnProperty.call(current, part)) {
        return { exists: false };
      }
      current = current[part];
    } else {
      return { exists: false };
    }
  }
  return { exists: true, value: current };
}

function setPath(root: unknown, path: string, value: unknown): void {
  const parts = path.split(".");
  let current = root;
  for (const part of parts.slice(0, -1)) {
    current = Array.isArray(current) ? current[Number(part)] : (current as Record<string, unknown>)[part];
  }
  const leaf = parts[parts.length - 1];
  if (Array.isArray(current)) {
    current[Number(leaf)] = value;
    return;
  }
  if (isRecord(current)) {
    current[leaf] = value;
    return;
  }
  throw new Error(`redaction path not settable: ${path}`);
}

function containsRedactionMarker(value: unknown): boolean {
  if (isRecord(value)) {
    if (value.schemaVersion === REDACTION_MARKER_SCHEMA && value.redacted === true) {
      return true;
    }
    return Object.values(value).some((item) => containsRedactionMarker(item));
  }
  if (Array.isArray(value)) {
    return value.some((item) => containsRedactionMarker(item));
  }
  return false;
}

function cloneRecord(value: Record<string, unknown>): Record<string, unknown> {
  if (typeof globalThis.structuredClone === "function") {
    return globalThis.structuredClone(value) as Record<string, unknown>;
  }
  return JSON.parse(JSON.stringify(value)) as Record<string, unknown>;
}

function isHexHash(value: string): boolean {
  return /^[0-9a-f]{64}$/.test(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
