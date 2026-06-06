import {
  type HardVerifierResult,
  type ProposalTrace,
  type Receipt,
  type ReplayRollbackAdapter,
  type TypedCandidate,
  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { BranchRuntime } from "./branch.js";
import {
  type ProjectionContract,
  buildProjectionManifest,
  makeProjectionContract,
  normalizeProjectionManifest,
  validateProjectionContract,
} from "./projection.js";

export const PROJECTION_PROJECTOR_ID = "stopping_distance.projector";
export const PROJECTION_PROJECTOR_VERSION = "1.0";
export const STOPPING_PROJECTION_CONTRACT: ProjectionContract = makeProjectionContract(
  ["distanceToObstacle", "brakeAccel", "safetyClearance"],
  { contractId: "stopping_distance.safety_fields" },
);

export interface ProjectionGuardState {
  distanceToObstacle: number;
  brakeAccel: number;
  safetyClearance: number;
  committedModes: string[];
}

export interface ProjectionGuardPayload {
  mode: string;
  speed: number;
  cost: number;
  projectionManifest: Record<string, unknown>;
  distanceToObstacle?: number;
  brakeAccel?: number;
  safetyClearance?: number;
}

export interface ProjectionContractReport {
  candidateCount: number;
  verifierCalls: number;
  unguardedFalsePositiveAccepts: boolean;
  guardedPartialRejected: boolean;
  guardedFastCompleteRejected: boolean;
  guardedSafeCommit: boolean;
  missingFields: string[];
  unsafeMarginNumerator: number;
  safeMarginNumerator: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
  invalidCommitCount: number;
}

export class ProjectionGuardAdapter implements ReplayRollbackAdapter<ProjectionGuardState, ProjectionGuardPayload> {
  verifierId = "projection_contract_guard";
  verifierVersion = "1.0";
  observedState: ProjectionGuardState;
  enforceContract: boolean;

  constructor(observedState: ProjectionGuardState | Record<string, unknown>, options: { enforceContract?: boolean } = {}) {
    this.observedState = normalizeProjectionGuardState(observedState);
    this.enforceContract = options.enforceContract ?? true;
  }

  async verify(candidate: TypedCandidate<ProjectionGuardPayload>): Promise<HardVerifierResult> {
    const payload = normalizeProjectionGuardPayload(candidate.payload);
    const source = sourceFields(this.observedState);
    const manifest = normalizeProjectionManifest(payload.projectionManifest);
    let metadata: Record<string, unknown> = {
      mode: payload.mode,
      speed: payload.speed,
      cost: payload.cost,
      coveredFields: manifest.coveredFields,
    };
    if (this.enforceContract) {
      const audit = await validateProjectionContract(STOPPING_PROJECTION_CONTRACT, manifest, source);
      if (!audit.accepted) {
        return hardReject(this.verifierId, this.verifierVersion, audit.residual, metadata);
      }
    }
    const distance = requiredIntegerPayload(payload, "distanceToObstacle");
    const brake = requiredIntegerPayload(payload, "brakeAccel");
    const clearance = Number(payload.safetyClearance ?? 0);
    if (!Number.isInteger(clearance) || clearance < 0) {
      throw new RangeError("safetyClearance must be a non-negative integer");
    }
    const margin = stoppingMarginNumerator({ distance, speed: payload.speed, brake, clearance });
    metadata = {
      ...metadata,
      marginNumerator: margin,
      denominator: 2 * brake,
      requiredDistanceNumerator: payload.speed * payload.speed + (2 * brake * clearance),
      availableDistanceNumerator: 2 * brake * distance,
    };
    if (margin < 0) {
      return hardReject(
        this.verifierId,
        this.verifierVersion,
        { kind: "stopping_distance_violation", marginNumerator: margin, denominator: 2 * brake },
        metadata,
      );
    }
    return hardAccept(this.verifierId, this.verifierVersion, metadata);
  }

  applyCommit(state: ProjectionGuardState, candidate: TypedCandidate<ProjectionGuardPayload>): ProjectionGuardState {
    const current = normalizeProjectionGuardState(state);
    const payload = normalizeProjectionGuardPayload(candidate.payload);
    return { ...current, committedModes: [...current.committedModes, payload.mode] };
  }

  replay(state: ProjectionGuardState, receipt: Receipt): ProjectionGuardState {
    const current = normalizeProjectionGuardState(state);
    const payload = normalizeProjectionGuardPayload((receipt.replayBundle as { candidatePayload: ProjectionGuardPayload }).candidatePayload);
    return { ...current, committedModes: [...current.committedModes, payload.mode] };
  }

  rollback(_state: ProjectionGuardState, receipt: Receipt): ProjectionGuardState {
    return normalizeProjectionGuardState((receipt.rollbackBundle as { preState: ProjectionGuardState }).preState);
  }
}

export class ProjectionContractProjector {
  async project(state: ProjectionGuardState, trace: ProposalTrace): Promise<TypedCandidate<ProjectionGuardPayload>> {
    const action = trace.actions.at(-1) as Record<string, unknown>;
    const covered = action.coveredFields ?? action.covered_fields;
    if (!Array.isArray(covered)) {
      throw new RangeError("coveredFields must be an array");
    }
    return makeProjectionGuardCandidate(state, {
      mode: String(action.mode),
      speed: Number(action.speed),
      cost: Number(action.cost ?? 1),
      coveredFields: covered.map((field) => String(field)),
    });
  }
}

export function normalizeProjectionGuardState(state: ProjectionGuardState | Record<string, unknown>): ProjectionGuardState {
  const raw = state as Record<string, unknown>;
  const committedModes = raw.committedModes ?? raw.committed_modes ?? [];
  if (!Array.isArray(committedModes)) {
    throw new RangeError("committedModes must be an array");
  }
  const normalized = {
    distanceToObstacle: Number(raw.distanceToObstacle ?? raw.distance_to_obstacle ?? 5),
    brakeAccel: Number(raw.brakeAccel ?? raw.brake_accel ?? 2),
    safetyClearance: Number(raw.safetyClearance ?? raw.safety_clearance ?? 2),
    committedModes: committedModes.map((mode) => String(mode)),
  };
  for (const [key, value] of Object.entries(normalized)) {
    if (key !== "committedModes" && (!Number.isInteger(value) || Number(value) < 0)) {
      throw new RangeError(`${key} must be a non-negative integer`);
    }
  }
  if (normalized.brakeAccel <= 0) {
    throw new RangeError("brakeAccel must be positive");
  }
  return normalized;
}

export async function makeProjectionGuardCandidate(
  state: ProjectionGuardState | Record<string, unknown>,
  options: { mode: string; speed: number; coveredFields: string[]; cost?: number },
): Promise<TypedCandidate<ProjectionGuardPayload>> {
  const current = normalizeProjectionGuardState(state);
  const source = sourceFields(current);
  const manifest = await buildProjectionManifest(source, options.coveredFields, {
    projectorId: PROJECTION_PROJECTOR_ID,
    projectorVersion: PROJECTION_PROJECTOR_VERSION,
  });
  const payload: ProjectionGuardPayload = {
    mode: options.mode,
    speed: options.speed,
    cost: options.cost ?? 1,
    projectionManifest: manifest,
  };
  for (const field of manifest.coveredFields) {
    (payload as Record<string, unknown>)[field] = source[field];
  }
  return makeCandidate(payload, "projection_guard.stop_command", "projection_guard.stop_command.v1", {
    projectionManifest: manifest.projectionHash,
  });
}

export function makeProjectionContractTraces(): ProposalTrace[] {
  const actions = [
    {
      mode: "fast_partial",
      speed: 4,
      cost: 1,
      coveredFields: ["distanceToObstacle", "brakeAccel"],
    },
    {
      mode: "fast_complete",
      speed: 4,
      cost: 1,
      coveredFields: ["distanceToObstacle", "brakeAccel", "safetyClearance"],
    },
    {
      mode: "crawl_complete",
      speed: 2,
      cost: 2,
      coveredFields: ["distanceToObstacle", "brakeAccel", "safetyClearance"],
    },
  ];
  return actions.map((action) => makeTrace({
    branchId: `projection-contract-${action.mode}`,
    actions: [action],
    seeds: ["projection_contract", action.mode],
    modelVersion: "projection.contract.v1",
  }));
}

export async function runProjectionContractBenchmark(): Promise<ProjectionContractReport> {
  const seed: ProjectionGuardState = { distanceToObstacle: 5, brakeAccel: 2, safetyClearance: 2, committedModes: [] };
  const traces = makeProjectionContractTraces();
  const projector = new ProjectionContractProjector();
  const partialCandidate = await projector.project(seed, traces[0]);
  const unguarded = await new ProjectionGuardAdapter(seed, { enforceContract: false }).verify(partialCandidate);

  const engine = new TransactionEngine(new ProjectionGuardAdapter(seed), new Ledger());
  const runtime = new BranchRuntime(engine, projector);
  const outcome = await runtime.step(seed, traces);
  const ledgerAudit = await engine.ledger.audit();
  let replayRollbackRate = 0;
  if (ledgerAudit) {
    try {
      const replayState = normalizeProjectionGuardState(await engine.replayAudit(seed));
      const rollbackState = normalizeProjectionGuardState(await engine.rollbackAudit(seed));
      replayRollbackRate = JSON.stringify(replayState) === JSON.stringify(outcome.state)
        && JSON.stringify(rollbackState) === JSON.stringify(seed)
        ? 1
        : 0;
    } catch (_error) {
      replayRollbackRate = 0;
    }
  }
  const partialReceipt = outcome.receipts[0] as Receipt;
  const fastReceipt = outcome.receipts[1] as Receipt;
  const safeReceipt = outcome.receipts[2] as Receipt;
  return {
    candidateCount: traces.length,
    verifierCalls: outcome.verifierCalls,
    unguardedFalsePositiveAccepts: unguarded.result === "accept",
    guardedPartialRejected: partialReceipt.hardResult.result === "reject",
    guardedFastCompleteRejected: fastReceipt.hardResult.result === "reject",
    guardedSafeCommit: safeReceipt.committed && normalizeProjectionGuardState(outcome.state).committedModes.join(",") === "crawl_complete",
    missingFields: (partialReceipt.hardResult.residual as { missingFields: string[] }).missingFields,
    unsafeMarginNumerator: Number(fastReceipt.hardResult.metadata.marginNumerator),
    safeMarginNumerator: Number(safeReceipt.hardResult.metadata.marginNumerator),
    ledgerAudit,
    replayRollbackRate,
    invalidCommitCount: engine.ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  };
}

export function stoppingMarginNumerator(params: { distance: number; speed: number; brake: number; clearance: number }): number {
  const { distance, speed, brake, clearance } = params;
  if (!Number.isInteger(distance) || distance < 0) {
    throw new RangeError("distance must be a non-negative integer");
  }
  if (!Number.isInteger(speed) || speed < 0) {
    throw new RangeError("speed must be a non-negative integer");
  }
  if (!Number.isInteger(brake) || brake <= 0) {
    throw new RangeError("brake must be a positive integer");
  }
  if (!Number.isInteger(clearance) || clearance < 0) {
    throw new RangeError("clearance must be a non-negative integer");
  }
  const denominator = 2 * brake;
  return denominator * distance - (speed * speed + denominator * clearance);
}

function sourceFields(state: ProjectionGuardState): Record<string, number> {
  return {
    distanceToObstacle: state.distanceToObstacle,
    brakeAccel: state.brakeAccel,
    safetyClearance: state.safetyClearance,
  };
}

function normalizeProjectionGuardPayload(payload: ProjectionGuardPayload | Record<string, unknown>): ProjectionGuardPayload {
  const raw = payload as Record<string, unknown>;
  const mode = String(raw.mode);
  const speed = Number(raw.speed);
  const cost = Number(raw.cost ?? 1);
  if (!mode) {
    throw new RangeError("mode must be non-empty");
  }
  if (!Number.isInteger(speed) || speed < 0) {
    throw new RangeError("speed must be a non-negative integer");
  }
  if (!Number.isInteger(cost) || cost < 0) {
    throw new RangeError("cost must be a non-negative integer");
  }
  if (!raw.projectionManifest && !raw.projection_manifest) {
    throw new RangeError("projectionManifest is required");
  }
  return {
    ...(raw as ProjectionGuardPayload),
    mode,
    speed,
    cost,
    projectionManifest: (raw.projectionManifest ?? raw.projection_manifest) as Record<string, unknown>,
  };
}

function requiredIntegerPayload(payload: ProjectionGuardPayload, key: "distanceToObstacle" | "brakeAccel"): number {
  const value = payload[key];
  if (!Number.isInteger(value) || Number(value) < 0) {
    throw new RangeError(`${key} is required as a non-negative integer`);
  }
  if (key === "brakeAccel" && Number(value) <= 0) {
    throw new RangeError("brakeAccel must be positive");
  }
  return Number(value);
}
