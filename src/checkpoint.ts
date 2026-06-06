import {
  GENESIS_HEAD,
  type Ledger,
  type Receipt,
  type ReplayRollbackAdapter,
  captureState,
  receiptStaticValid,
  receiptHash,
} from "./core.js";
import { chainHash, stableHash } from "./canonical.js";

export const CHECKPOINT_SCHEMA = "trwm.checkpoint.v1";

export interface CheckpointCertificate<State = unknown> {
  schemaVersion: string;
  baseHead: string;
  checkpointHead: string;
  startIndex: number;
  endIndex: number;
  receiptHashes: string[];
  committedReceiptHashes: string[];
  receiptCount: number;
  committedCount: number;
  stateHash: string;
  checkpointState: State;
  adapterId: string;
  adapterVersion: string;
  stateSchemaVersion: string;
  certificateHash: string;
}

export interface CheckpointReplayResult<State = unknown> {
  state: State;
  head: string;
  suffixReceiptCount: number;
  suffixCommittedCount: number;
}

export async function checkpointCertificateHash(checkpoint: CheckpointCertificate | Record<string, unknown>): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = checkpoint as Record<string, unknown>;
  return stableHash(withoutHash);
}

export async function chainReceiptHashes(baseHead: string, receiptHashes: string[]): Promise<string> {
  assertHexHash(baseHead, "baseHead");
  let head = baseHead;
  for (const receiptHashValue of receiptHashes) {
    assertHexHash(receiptHashValue, "receiptHash");
    head = await chainHash(head, receiptHashValue);
  }
  return head;
}

export async function buildCheckpoint<State>(
  ledger: Ledger,
  adapter: ReplayRollbackAdapter<State, unknown>,
  seedState: State,
  options: { endIndex?: number; stateSchemaVersion?: string } = {},
): Promise<CheckpointCertificate<State>> {
  if (!await ledger.audit()) {
    throw new Error("ledger audit must pass before checkpointing");
  }
  const endIndex = options.endIndex ?? ledger.rows.length;
  if (!Number.isInteger(endIndex) || endIndex < 0 || endIndex > ledger.rows.length) {
    throw new RangeError("checkpoint endIndex must be within the ledger");
  }
  const stateSchemaVersion = options.stateSchemaVersion ?? "state.v1";
  let state = seedState;
  const committedReceiptHashes: string[] = [];
  for (const receipt of ledger.rows.slice(0, endIndex)) {
    if (receipt.committed) {
      state = await adapter.replay(state, receipt);
      if ((await captureState(state, stateSchemaVersion)).stateHash !== receipt.postStateHash) {
        throw new Error(`checkpoint replay hash mismatch for ${receipt.receiptId}`);
      }
      committedReceiptHashes.push(receipt.receiptHash);
    }
  }
  const receiptHashes = ledger.rows.slice(0, endIndex).map((row) => row.receiptHash);
  const snapshot = await captureState(state, stateSchemaVersion);
  const checkpoint: CheckpointCertificate<State> = {
    schemaVersion: CHECKPOINT_SCHEMA,
    baseHead: GENESIS_HEAD,
    checkpointHead: await chainReceiptHashes(GENESIS_HEAD, receiptHashes),
    startIndex: 0,
    endIndex,
    receiptHashes,
    committedReceiptHashes,
    receiptCount: receiptHashes.length,
    committedCount: committedReceiptHashes.length,
    stateHash: snapshot.stateHash,
    checkpointState: state,
    adapterId: adapter.verifierId,
    adapterVersion: adapter.verifierVersion,
    stateSchemaVersion,
    certificateHash: "",
  };
  return { ...checkpoint, certificateHash: await checkpointCertificateHash(checkpoint) };
}

export async function validateCheckpoint(checkpoint: CheckpointCertificate | Record<string, unknown>): Promise<boolean> {
  try {
    if (!isRecord(checkpoint)) {
      return false;
    }
    if (checkpoint.schemaVersion !== CHECKPOINT_SCHEMA) {
      return false;
    }
    if (checkpoint.startIndex !== 0) {
      return false;
    }
    if (!Array.isArray(checkpoint.receiptHashes) || !Array.isArray(checkpoint.committedReceiptHashes)) {
      return false;
    }
    const receiptHashes = checkpoint.receiptHashes.map(String);
    const committedReceiptHashes = checkpoint.committedReceiptHashes.map(String);
    if (checkpoint.endIndex !== receiptHashes.length || checkpoint.receiptCount !== receiptHashes.length) {
      return false;
    }
    if (checkpoint.committedCount !== committedReceiptHashes.length) {
      return false;
    }
    const receiptHashSet = new Set(receiptHashes);
    if (!committedReceiptHashes.every((item) => receiptHashSet.has(item))) {
      return false;
    }
    if (checkpoint.checkpointHead !== await chainReceiptHashes(String(checkpoint.baseHead), receiptHashes)) {
      return false;
    }
    const snapshot = await captureState(checkpoint.checkpointState, String(checkpoint.stateSchemaVersion ?? "state.v1"));
    if (checkpoint.stateHash !== snapshot.stateHash) {
      return false;
    }
    if (checkpoint.certificateHash !== await checkpointCertificateHash(checkpoint)) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

export async function replayFromCheckpoint<State>(
  checkpoint: CheckpointCertificate<State> | Record<string, unknown>,
  suffixRows: Receipt[],
  adapter: ReplayRollbackAdapter<State, unknown>,
  options: { expectedFinalHead?: string; stateSchemaVersion?: string } = {},
): Promise<CheckpointReplayResult<State>> {
  if (!await validateCheckpoint(checkpoint)) {
    throw new Error("invalid checkpoint certificate");
  }
  const view = checkpoint as CheckpointCertificate<State>;
  if (view.adapterId !== adapter.verifierId || view.adapterVersion !== adapter.verifierVersion) {
    throw new Error("checkpoint adapter identity does not match replay adapter");
  }
  const stateSchemaVersion = options.stateSchemaVersion ?? view.stateSchemaVersion ?? "state.v1";
  let state = view.checkpointState;
  let head = view.checkpointHead;
  let suffixCommittedCount = 0;
  for (const receipt of suffixRows) {
    if (!await receiptStaticValid(receipt)) {
      throw new Error(`invalid suffix receipt: ${receipt.receiptId}`);
    }
    if (receipt.parentHead !== head) {
      throw new Error(`suffix receipt parent mismatch: ${receipt.receiptId}`);
    }
    if (receipt.receiptHash !== await receiptHash(receipt)) {
      throw new Error(`suffix receipt hash mismatch: ${receipt.receiptId}`);
    }
    if (receipt.committed) {
      state = await adapter.replay(state, receipt);
      if ((await captureState(state, stateSchemaVersion)).stateHash !== receipt.postStateHash) {
        throw new Error(`suffix replay hash mismatch for ${receipt.receiptId}`);
      }
      suffixCommittedCount += 1;
    }
    head = await chainHash(head, receipt.receiptHash);
  }
  if (options.expectedFinalHead && head !== options.expectedFinalHead) {
    throw new Error("compacted replay final head mismatch");
  }
  return { state, head, suffixReceiptCount: suffixRows.length, suffixCommittedCount };
}

export async function auditCompactedView<State>(
  checkpoint: CheckpointCertificate<State> | Record<string, unknown>,
  suffixRows: Receipt[],
  adapter: ReplayRollbackAdapter<State, unknown>,
  options: { expectedFinalHead?: string } = {},
): Promise<boolean> {
  try {
    await replayFromCheckpoint(checkpoint, suffixRows, adapter, options);
    return true;
  } catch {
    return false;
  }
}

function assertHexHash(value: string, label: string): void {
  if (!/^[0-9a-f]{64}$/.test(value)) {
    throw new Error(`${label} must be a lowercase SHA-256 hex digest`);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}
