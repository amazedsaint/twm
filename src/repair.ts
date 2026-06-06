import {
  type HardVerifierResult,
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

export type ProgramOp = "set" | "add";

export interface ProgramStep {
  op: ProgramOp;
  value: number;
}

export interface ScalarProgramPayload {
  context: string;
  start: number;
  target: number;
  program: ProgramStep[];
  output: number;
  residual?: ScalarResidual;
}

export interface ScalarResidual {
  kind: "scalar_delta";
  target: number;
  output: number;
  delta: number;
  repair: ProgramStep;
}

export interface ScalarProgramState {
  episode: number;
  target: number;
  solved: boolean;
  value?: number;
  program?: ProgramStep[];
}

export interface RepairEpisodeResult {
  calls: number;
  success: boolean;
}

export interface RepairReport {
  staticCallsPerSuccess: number;
  repairCallsPerSuccess: number;
  repairGain: number;
  repairSuccessRate: number;
  ledgerAudit: boolean;
  invalidCommitCount: number;
  learnedRepairKinds: Record<string, number>;
}

export function evaluateProgram(steps: ProgramStep[], start = 0): number {
  return steps.reduce((value, step) => {
    assertStep(step);
    return step.op === "set" ? step.value : value + step.value;
  }, start);
}

export function programCost(steps: ProgramStep[]): number {
  return steps.length;
}

export class ScalarProgramAdapter implements ReplayRollbackAdapter<ScalarProgramState, ScalarProgramPayload> {
  verifierId = "scalar_program_oracle";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<ScalarProgramPayload>): HardVerifierResult {
    const payload = candidate.payload;
    const output = evaluateProgram(payload.program, payload.start);
    if (output === payload.target) {
      return hardAccept(this.verifierId, this.verifierVersion, { cost: programCost(payload.program) });
    }
    const delta = payload.target - output;
    return hardReject(
      this.verifierId,
      this.verifierVersion,
      {
        kind: "scalar_delta",
        target: payload.target,
        output,
        delta,
        repair: { op: "add", value: delta },
      } satisfies ScalarResidual,
      { cost: programCost(payload.program) },
    );
  }

  applyCommit(state: ScalarProgramState, candidate: TypedCandidate<ScalarProgramPayload>): ScalarProgramState {
    const value = evaluateProgram(candidate.payload.program, candidate.payload.start);
    return { ...state, solved: true, value, program: candidate.payload.program };
  }

  replay(state: ScalarProgramState, receipt: Receipt): ScalarProgramState {
    const payload = (receipt.replayBundle as { candidatePayload: ScalarProgramPayload }).candidatePayload;
    return { ...state, solved: true, value: evaluateProgram(payload.program, payload.start), program: payload.program };
  }

  rollback(_state: ScalarProgramState, receipt: Receipt): ScalarProgramState {
    return (receipt.rollbackBundle as { preState: ScalarProgramState }).preState;
  }
}

export class ResidualProgramRepairer {
  acceptedPrograms = new Map<string, Map<string, number>>();
  repairActions = new Map<string, Map<string, number>>();
  rejectedResiduals = new Map<string, number>();

  update(receipt: Receipt): void {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle as Record<string, unknown>
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload as Partial<ScalarProgramPayload>
      : {};
    const context = String(payload.context ?? "global");
    if (receipt.hardResult.result === "accept") {
      increment(this.acceptedPrograms, context, JSON.stringify(payload.program ?? []));
      return;
    }
    if (receipt.hardResult.result === "reject" && isScalarResidual(receipt.hardResult.residual)) {
      this.rejectedResiduals.set(
        receipt.hardResult.residual.kind,
        (this.rejectedResiduals.get(receipt.hardResult.residual.kind) ?? 0) + 1,
      );
      increment(this.repairActions, context, JSON.stringify(receipt.hardResult.residual.repair));
    }
  }

  propose(candidate: TypedCandidate<ScalarProgramPayload>): TypedCandidate<ScalarProgramPayload> | null {
    const residual = candidate.payload.residual;
    if (!isScalarResidual(residual)) {
      return null;
    }
    const repairedProgram = [...candidate.payload.program, residual.repair];
    const payload = {
      ...candidate.payload,
      program: repairedProgram,
      output: evaluateProgram(repairedProgram, candidate.payload.start),
    };
    delete payload.residual;
    return makeScalarCandidate(payload.context, payload.target, payload.program, payload.start);
  }
}

export function makeScalarCandidate(
  context: string,
  target: number,
  program: ProgramStep[],
  start = 0,
): TypedCandidate<ScalarProgramPayload> {
  const normalized = program.map((step) => {
    assertStep(step);
    return { op: step.op, value: step.value };
  });
  return makeCandidate(
    {
      context,
      start,
      target,
      program: normalized,
      output: evaluateProgram(normalized, start),
    },
    "scalar.program",
    "scalar.program.v1",
  );
}

export function attachResidual(
  candidate: TypedCandidate<ScalarProgramPayload>,
  residual: ScalarResidual,
): TypedCandidate<ScalarProgramPayload> {
  return {
    ...candidate,
    payload: { ...candidate.payload, residual },
  };
}

export async function runStaticRepairEpisode(
  target: number,
  labelOrder: number[],
  ledger: Ledger,
  episode: number,
): Promise<RepairEpisodeResult> {
  const engine = new TransactionEngine(new ScalarProgramAdapter(), ledger);
  const state: ScalarProgramState = { episode, target, solved: false };
  let calls = 0;
  for (const guess of labelOrder) {
    calls += 1;
    const candidate = makeScalarCandidate("scalar-static", target, [{ op: "set", value: guess }]);
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `static-${episode}-${guess}`,
        actions: [{ op: "set", value: guess }],
        seeds: [episode, guess],
        modelVersion: "scalar.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return { calls, success: true };
    }
  }
  return { calls, success: false };
}

export async function runRepairEpisode(
  target: number,
  initialGuess: number,
  ledger: Ledger,
  repairer: ResidualProgramRepairer,
  episode: number,
): Promise<RepairEpisodeResult> {
  const engine = new TransactionEngine(new ScalarProgramAdapter(), ledger);
  const state: ScalarProgramState = { episode, target, solved: false };
  let candidate = makeScalarCandidate("scalar-repair", target, [{ op: "set", value: initialGuess }]);
  let calls = 0;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    calls += 1;
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `repair-${episode}-${attempt}`,
        actions: candidate.payload.program,
        seeds: [episode, attempt],
        modelVersion: "residual.program.repair.v1",
      }),
      candidate,
    );
    repairer.update(outcome.receipt);
    if (outcome.committed) {
      return { calls, success: true };
    }
    if (!isScalarResidual(outcome.receipt.hardResult.residual)) {
      return { calls, success: false };
    }
    const repaired = repairer.propose(attachResidual(candidate, outcome.receipt.hardResult.residual));
    if (!repaired) {
      return { calls, success: false };
    }
    candidate = repaired;
  }
  return { calls, success: false };
}

export async function runResidualRepairBenchmark(seed = 13, episodes = 64, labelMin = -12, labelMax = 12): Promise<RepairReport> {
  const rng = mulberry32(seed);
  const labels = Array.from({ length: labelMax - labelMin + 1 }, (_unused, idx) => labelMin + idx);
  const staticOrder = shuffle(labels, seed + 1);
  const motifs = [-8, -3, 0, 5, 9];
  const targets: number[] = [];
  for (let idx = 0; idx < Math.floor(episodes / 2); idx += 1) {
    targets.push(motifs[Math.floor(rng() * motifs.length)]);
  }
  while (targets.length < episodes) {
    targets.push(labelMin + Math.floor(rng() * labels.length));
  }
  shuffleInPlace(targets, rng);

  const staticLedger = new Ledger();
  const repairLedger = new Ledger();
  const repairer = new ResidualProgramRepairer();
  const staticResults: RepairEpisodeResult[] = [];
  const repairResults: RepairEpisodeResult[] = [];
  for (let idx = 0; idx < targets.length; idx += 1) {
    staticResults.push(await runStaticRepairEpisode(targets[idx], staticOrder, staticLedger, idx));
    repairResults.push(await runRepairEpisode(targets[idx], labelMin - 1, repairLedger, repairer, idx));
  }
  const staticCps = callsPerSuccess(staticResults);
  const repairCps = callsPerSuccess(repairResults);
  const successes = repairResults.filter((row) => row.success).length;
  return {
    staticCallsPerSuccess: staticCps,
    repairCallsPerSuccess: repairCps,
    repairGain: staticCps / repairCps,
    repairSuccessRate: repairResults.length === 0 ? 0 : successes / repairResults.length,
    ledgerAudit: await staticLedger.audit() && await repairLedger.audit(),
    invalidCommitCount: invalidCommits([staticLedger, repairLedger]),
    learnedRepairKinds: Object.fromEntries(repairer.rejectedResiduals),
  };
}

function isScalarResidual(value: unknown): value is ScalarResidual {
  if (!value || typeof value !== "object") {
    return false;
  }
  const residual = value as Partial<ScalarResidual>;
  return residual.kind === "scalar_delta"
    && typeof residual.delta === "number"
    && residual.repair?.op === "add"
    && typeof residual.repair.value === "number";
}

function assertStep(step: ProgramStep): void {
  if ((step.op !== "set" && step.op !== "add") || !Number.isInteger(step.value)) {
    throw new TypeError("program step must be { op: 'set' | 'add', value: integer }");
  }
}

function increment(table: Map<string, Map<string, number>>, context: string, action: string): void {
  let row = table.get(context);
  if (!row) {
    row = new Map();
    table.set(context, row);
  }
  row.set(action, (row.get(action) ?? 0) + 1);
}

function callsPerSuccess(results: RepairEpisodeResult[]): number {
  const successes = results.filter((row) => row.success).length;
  const calls = results.reduce((total, row) => total + row.calls, 0);
  return successes === 0 ? Number.POSITIVE_INFINITY : calls / successes;
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
  shuffleInPlace(out, rng);
  return out;
}

function shuffleInPlace(values: number[], rng: () => number): void {
  for (let idx = values.length - 1; idx > 0; idx -= 1) {
    const swap = Math.floor(rng() * (idx + 1));
    [values[idx], values[swap]] = [values[swap], values[idx]];
  }
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
