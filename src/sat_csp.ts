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
import { stableHash } from "./canonical.js";

export type Clause = number[];
export type Assignment = boolean[];

export interface CnfFormula {
  variableCount: number;
  clauses: Clause[];
}

export interface CnfState {
  formula: CnfFormula;
  solved: boolean;
  assignment?: Assignment | null;
}

export interface CnfCandidatePayload {
  context: string;
  formula: CnfFormula;
  assignment: Assignment;
  cost: number;
  unsatisfiedCount: number;
}

export interface CnfResidual {
  kind: "unsatisfied_clause";
  firstIndex: number;
  firstClause: Clause;
  unsatisfiedCount: number;
  unsatisfiedIndices: number[];
  repair: { variable: number; value: boolean };
}

export interface SatEpisodeResult {
  calls: number;
  success: boolean;
}

export interface SatCspReport {
  variableCount: number;
  episodes: number;
  assignmentSpaceSize: number;
  staticCallsPerSuccess: number;
  repairCallsPerSuccess: number;
  repairGain: number;
  repairSuccessRate: number;
  ledgerAudit: boolean;
  invalidCommitCount: number;
  learnedResidualKinds: Record<string, number>;
}

export class CnfSatAdapter implements ReplayRollbackAdapter<CnfState, CnfCandidatePayload> {
  verifierId = "cnf_sat_verifier";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<CnfCandidatePayload>): HardVerifierResult {
    const formula = normalizeFormula(candidate.payload.formula);
    const assignment = normalizeAssignment(candidate.payload.assignment, formula.variableCount);
    const unsatisfied = unsatisfiedClauses(formula, assignment);
    const metadata = {
      cost: candidate.payload.cost,
      clauseCount: formula.clauses.length,
      unsatisfiedCount: unsatisfied.length,
    };
    if (unsatisfied.length === 0) {
      return hardAccept(this.verifierId, this.verifierVersion, metadata);
    }
    const firstIndex = unsatisfied[0];
    const firstClause = formula.clauses[firstIndex];
    const literal = firstClause[0];
    return hardReject(
      this.verifierId,
      this.verifierVersion,
      {
        kind: "unsatisfied_clause",
        firstIndex,
        firstClause,
        unsatisfiedCount: unsatisfied.length,
        unsatisfiedIndices: unsatisfied,
        repair: { variable: Math.abs(literal), value: literal > 0 },
      } satisfies CnfResidual,
      metadata,
    );
  }

  applyCommit(_state: CnfState, candidate: TypedCandidate<CnfCandidatePayload>): CnfState {
    const formula = normalizeFormula(candidate.payload.formula);
    return {
      formula,
      solved: true,
      assignment: normalizeAssignment(candidate.payload.assignment, formula.variableCount),
    };
  }

  replay(_state: CnfState, receipt: Receipt): CnfState {
    const payload = (receipt.replayBundle as { candidatePayload: CnfCandidatePayload }).candidatePayload;
    const formula = normalizeFormula(payload.formula);
    return { formula, solved: true, assignment: normalizeAssignment(payload.assignment, formula.variableCount) };
  }

  rollback(_state: CnfState, receipt: Receipt): CnfState {
    return normalizeState((receipt.rollbackBundle as { preState: CnfState }).preState);
  }
}

export class CnfResidualRepairer {
  rejectedResiduals = new Map<string, number>();
  acceptedAssignments = new Map<string, number>();
  repairVariables = new Map<number, number>();

  update(receipt: Receipt): void {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle as Record<string, unknown>
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload as Partial<CnfCandidatePayload>
      : {};
    if (receipt.hardResult.result === "accept") {
      const key = JSON.stringify(payload.assignment ?? []);
      this.acceptedAssignments.set(key, (this.acceptedAssignments.get(key) ?? 0) + 1);
      return;
    }
    if (receipt.hardResult.result === "reject" && isCnfResidual(receipt.hardResult.residual)) {
      const residual = receipt.hardResult.residual;
      this.rejectedResiduals.set(residual.kind, (this.rejectedResiduals.get(residual.kind) ?? 0) + 1);
      this.repairVariables.set(residual.repair.variable, (this.repairVariables.get(residual.repair.variable) ?? 0) + 1);
    }
  }

  async propose(candidate: TypedCandidate<CnfCandidatePayload>, residual: CnfResidual): Promise<TypedCandidate<CnfCandidatePayload> | null> {
    if (!isCnfResidual(residual)) {
      return null;
    }
    const formula = normalizeFormula(candidate.payload.formula);
    const assignment = normalizeAssignment(candidate.payload.assignment, formula.variableCount);
    const variable = residual.repair.variable;
    if (variable < 1 || variable > formula.variableCount) {
      return null;
    }
    const repaired = [...assignment];
    repaired[variable - 1] = residual.repair.value;
    return makeCnfCandidate(formula, repaired, candidate.payload.context, candidate.payload.cost + 1);
  }
}

export function normalizeFormula(formula: CnfFormula): CnfFormula {
  if (!Number.isInteger(formula.variableCount) || formula.variableCount <= 0) {
    throw new RangeError("variableCount must be positive");
  }
  if (!Array.isArray(formula.clauses) || formula.clauses.length === 0) {
    throw new RangeError("formula must contain at least one clause");
  }
  return {
    variableCount: formula.variableCount,
    clauses: formula.clauses.map((clause) => {
      if (!Array.isArray(clause) || clause.length === 0) {
        throw new RangeError("empty clauses are not supported in this G1 canary");
      }
      return clause.map((literal) => {
        if (!Number.isInteger(literal) || literal === 0 || Math.abs(literal) > formula.variableCount) {
          throw new RangeError(`literal outside variable range: ${literal}`);
        }
        return literal;
      });
    }),
  };
}

export function normalizeAssignment(assignment: Assignment, variableCount: number): Assignment {
  if (!Array.isArray(assignment) || assignment.length !== variableCount) {
    throw new RangeError("assignment length must match variableCount");
  }
  return assignment.map(Boolean);
}

export function literalSatisfied(literal: number, assignment: Assignment): boolean {
  const value = assignment[Math.abs(literal) - 1];
  return literal > 0 ? value : !value;
}

export function clauseSatisfied(clause: Clause, assignment: Assignment): boolean {
  return clause.some((literal) => literalSatisfied(literal, assignment));
}

export function unsatisfiedClauses(formulaInput: CnfFormula, assignmentInput: Assignment): number[] {
  const formula = normalizeFormula(formulaInput);
  const assignment = normalizeAssignment(assignmentInput, formula.variableCount);
  const out: number[] = [];
  for (let idx = 0; idx < formula.clauses.length; idx += 1) {
    if (!clauseSatisfied(formula.clauses[idx], assignment)) {
      out.push(idx);
    }
  }
  return out;
}

export async function makeCnfCandidate(
  formulaInput: CnfFormula,
  assignmentInput: Assignment,
  context = "cnf",
  cost = 1,
): Promise<TypedCandidate<CnfCandidatePayload>> {
  const formula = normalizeFormula(formulaInput);
  const assignment = normalizeAssignment(assignmentInput, formula.variableCount);
  return makeCandidate(
    {
      context,
      formula,
      assignment,
      cost,
      unsatisfiedCount: unsatisfiedClauses(formula, assignment).length,
    },
    "cnf.assignment",
    "cnf.assignment.v1",
    {
      formula: await stableHash(formula),
      assignment: await stableHash(assignment),
    },
  );
}

export function formulaFromTarget(targetInput: Assignment): CnfFormula {
  const target = normalizeAssignment(targetInput, targetInput.length);
  const clauses: Clause[] = target.map((value, idx) => [value ? idx + 1 : -(idx + 1)]);
  for (let idx = 0; idx < target.length - 1; idx += 1) {
    clauses.push([
      target[idx] ? idx + 1 : -(idx + 1),
      target[idx + 1] ? idx + 2 : -(idx + 2),
    ]);
  }
  return { variableCount: target.length, clauses };
}

export function assignmentFromMask(mask: number, variableCount: number): Assignment {
  if (!Number.isInteger(mask) || mask < 0) {
    throw new RangeError("mask must be a non-negative integer");
  }
  return Array.from({ length: variableCount }, (_unused, idx) => Boolean((mask >> idx) & 1));
}

export async function runStaticSatEpisode(
  formula: CnfFormula,
  assignmentOrder: Assignment[],
  ledger: Ledger,
  episode: number,
): Promise<SatEpisodeResult> {
  const engine = new TransactionEngine(new CnfSatAdapter(), ledger);
  const state: CnfState = { formula: normalizeFormula(formula), solved: false, assignment: null };
  for (let idx = 0; idx < assignmentOrder.length; idx += 1) {
    const candidate = await makeCnfCandidate(formula, assignmentOrder[idx], "cnf-static", idx + 1);
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `cnf-static-${episode}-${idx}`,
        actions: [{ assignment: assignmentOrder[idx], cost: idx + 1 }],
        seeds: [episode, idx],
        modelVersion: "cnf.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return { calls: idx + 1, success: true };
    }
  }
  return { calls: assignmentOrder.length, success: false };
}

export async function runResidualSatEpisode(
  formula: CnfFormula,
  initialAssignment: Assignment,
  ledger: Ledger,
  repairer: CnfResidualRepairer,
  episode: number,
  maxRepairs?: number,
): Promise<SatEpisodeResult> {
  const normalized = normalizeFormula(formula);
  const maxAttempts = (maxRepairs ?? normalized.variableCount) + 1;
  const engine = new TransactionEngine(new CnfSatAdapter(), ledger);
  const state: CnfState = { formula: normalized, solved: false, assignment: null };
  let candidate = await makeCnfCandidate(normalized, initialAssignment, "cnf-repair", 1);
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `cnf-repair-${episode}-${attempt}`,
        actions: [{ assignment: candidate.payload.assignment, cost: candidate.payload.cost }],
        seeds: [episode, attempt],
        modelVersion: "cnf.residual_repair.v1",
      }),
      candidate,
    );
    repairer.update(outcome.receipt);
    if (outcome.committed) {
      return { calls: attempt + 1, success: true };
    }
    if (!isCnfResidual(outcome.receipt.hardResult.residual)) {
      return { calls: attempt + 1, success: false };
    }
    const repaired = await repairer.propose(candidate, outcome.receipt.hardResult.residual);
    if (!repaired) {
      return { calls: attempt + 1, success: false };
    }
    candidate = repaired;
  }
  return { calls: maxAttempts, success: false };
}

export async function runSatCspBenchmark(seed = 23, episodes = 48, variableCount = 8): Promise<SatCspReport> {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  if (!Number.isInteger(variableCount) || variableCount <= 0 || variableCount > 12) {
    throw new RangeError("variableCount must be in [1, 12] for this G1 canary");
  }
  const masks = shuffle(Array.from({ length: 2 ** variableCount - 1 }, (_unused, idx) => idx + 1), seed);
  const targets = Array.from({ length: episodes }, (_unused, idx) => assignmentFromMask(masks[idx % masks.length], variableCount));
  const staticOrder = Array.from({ length: 2 ** variableCount }, (_unused, mask) => assignmentFromMask(mask, variableCount));
  const initial = Array.from({ length: variableCount }, () => false);
  const staticLedger = new Ledger();
  const repairLedger = new Ledger();
  const repairer = new CnfResidualRepairer();
  const staticResults: SatEpisodeResult[] = [];
  const repairResults: SatEpisodeResult[] = [];
  for (let idx = 0; idx < targets.length; idx += 1) {
    const formula = formulaFromTarget(targets[idx]);
    staticResults.push(await runStaticSatEpisode(formula, staticOrder, staticLedger, idx));
    repairResults.push(await runResidualSatEpisode(formula, initial, repairLedger, repairer, idx));
  }
  const staticCps = callsPerSuccess(staticResults);
  const repairCps = callsPerSuccess(repairResults);
  const successes = repairResults.filter((row) => row.success).length;
  return {
    variableCount,
    episodes,
    assignmentSpaceSize: 2 ** variableCount,
    staticCallsPerSuccess: staticCps,
    repairCallsPerSuccess: repairCps,
    repairGain: staticCps / repairCps,
    repairSuccessRate: successes / repairResults.length,
    ledgerAudit: await staticLedger.audit() && await repairLedger.audit(),
    invalidCommitCount: invalidCommits([staticLedger, repairLedger]),
    learnedResidualKinds: Object.fromEntries(repairer.rejectedResiduals),
  };
}

function normalizeState(state: CnfState): CnfState {
  const formula = normalizeFormula(state.formula);
  return {
    formula,
    solved: Boolean(state.solved),
    assignment: state.assignment ? normalizeAssignment(state.assignment, formula.variableCount) : null,
  };
}

function isCnfResidual(value: unknown): value is CnfResidual {
  if (!value || typeof value !== "object") {
    return false;
  }
  const residual = value as Partial<CnfResidual>;
  return residual.kind === "unsatisfied_clause"
    && Array.isArray(residual.firstClause)
    && Array.isArray(residual.unsatisfiedIndices)
    && typeof residual.repair?.variable === "number"
    && typeof residual.repair.value === "boolean";
}

function callsPerSuccess(results: SatEpisodeResult[]): number {
  const successes = results.filter((row) => row.success).length;
  const calls = results.reduce((sum, row) => sum + row.calls, 0);
  return successes === 0 ? Number.POSITIVE_INFINITY : calls / successes;
}

function invalidCommits(ledgers: Ledger[]): number {
  return ledgers.reduce((sum, ledger) =>
    sum + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  0);
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
  let t = seed >>> 0;
  return () => {
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}
