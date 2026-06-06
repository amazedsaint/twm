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

export interface ProofRule {
  ruleId: string;
  premises: string[];
  conclusion: string;
}

export interface ProofProblem {
  hypotheses: string[];
  rules: ProofRule[];
  goal: string;
}

export interface ProofState {
  problem: ProofProblem;
  proven: boolean;
  derived: string[];
  proof: string[];
}

export interface ProofCandidatePayload {
  context: string;
  problem: ProofProblem;
  script: string[];
  cost: number;
}

export interface ProofEpisodeResult {
  calls: number;
  success: boolean;
  auditOk: boolean;
  replayRollbackOk: boolean;
}

export interface ProofKernelReport {
  episodes: number;
  ruleCount: number;
  staticCallsPerSuccess: number;
  repairCallsPerSuccess: number;
  repairGain: number;
  repairSuccessRate: number;
  ledgerAuditRate: number;
  replayRollbackRate: number;
  invalidCommitCount: number;
  learnedResidualKinds: Record<string, number>;
}

export interface ProofRepairHint {
  ruleId: string;
  conclusion: string;
}

export interface ProofResidual {
  kind: "unknown_rule" | "duplicate_rule" | "missing_premise" | "goal_not_derived";
  ruleId?: string;
  step?: number;
  missing?: string[];
  goal?: string;
  derived?: string[];
  repair?: ProofRepairHint | null;
}

export class HornProofAdapter implements ReplayRollbackAdapter<ProofState, ProofCandidatePayload> {
  verifierId = "horn_proof_kernel";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<ProofCandidatePayload>): HardVerifierResult {
    const problem = normalizeProofProblem(candidate.payload.problem);
    const script = normalizeScript(candidate.payload.script);
    const metadata = { cost: candidate.payload.cost ?? script.length, scriptLength: script.length };
    const rules = new Map(problem.rules.map((rule) => [rule.ruleId, rule]));
    const facts = new Set(problem.hypotheses);
    const used = new Set<string>();
    for (let index = 0; index < script.length; index += 1) {
      const ruleId = script[index];
      const rule = rules.get(ruleId);
      if (!rule) {
        return this.reject("unknown_rule", { ruleId, step: index }, metadata);
      }
      if (used.has(ruleId)) {
        return this.reject("duplicate_rule", { ruleId, step: index, repair: nextApplicableRule(problem, facts, used) }, metadata);
      }
      const missing = rule.premises.filter((premise) => !facts.has(premise));
      if (missing.length > 0) {
        return this.reject(
          "missing_premise",
          { ruleId, step: index, missing, repair: nextApplicableRule(problem, facts, used) },
          metadata,
        );
      }
      facts.add(rule.conclusion);
      used.add(ruleId);
    }
    if (facts.has(problem.goal)) {
      return hardAccept(this.verifierId, this.verifierVersion, { ...metadata, derivedCount: facts.size });
    }
    return this.reject(
      "goal_not_derived",
      { goal: problem.goal, derived: Array.from(facts).sort(), repair: nextApplicableRule(problem, facts, used) },
      metadata,
    );
  }

  applyCommit(state: ProofState, candidate: TypedCandidate<ProofCandidatePayload>): ProofState {
    const current = normalizeProofState(state);
    const problem = normalizeProofProblem(candidate.payload.problem);
    if (!proofProblemsEqual(current.problem, problem)) {
      throw new Error("candidate problem does not match current proof state");
    }
    const script = normalizeScript(candidate.payload.script);
    return { problem, proven: true, derived: Array.from(deriveFacts(problem, script)).sort(), proof: script };
  }

  replay(state: ProofState, receipt: Receipt): ProofState {
    const current = normalizeProofState(state);
    const payload = (receipt.replayBundle as { candidatePayload: ProofCandidatePayload }).candidatePayload;
    const problem = normalizeProofProblem(payload.problem);
    if (!proofProblemsEqual(current.problem, problem)) {
      throw new Error("receipt problem does not match replay proof state");
    }
    const script = normalizeScript(payload.script);
    return { problem, proven: true, derived: Array.from(deriveFacts(problem, script)).sort(), proof: script };
  }

  rollback(_state: ProofState, receipt: Receipt): ProofState {
    return normalizeProofState((receipt.rollbackBundle as { preState: ProofState }).preState);
  }

  private reject(kind: ProofResidual["kind"], residual: Omit<ProofResidual, "kind">, metadata: Record<string, unknown>): HardVerifierResult {
    return hardReject(this.verifierId, this.verifierVersion, { kind, ...residual }, metadata);
  }
}

export class ProofResidualRepairer {
  rejectedResiduals = new Map<string, number>();
  acceptedScripts = new Map<string, number>();

  update(receipt: Receipt): void {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle as Record<string, unknown>
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload as Partial<ProofCandidatePayload>
      : {};
    if (receipt.hardResult.result === "accept") {
      const key = JSON.stringify(payload.script ?? []);
      this.acceptedScripts.set(key, (this.acceptedScripts.get(key) ?? 0) + 1);
      return;
    }
    if (receipt.hardResult.result === "reject" && isProofResidual(receipt.hardResult.residual)) {
      const kind = receipt.hardResult.residual.kind;
      this.rejectedResiduals.set(kind, (this.rejectedResiduals.get(kind) ?? 0) + 1);
    }
  }

  async propose(candidate: TypedCandidate<ProofCandidatePayload>, residual: unknown): Promise<TypedCandidate<ProofCandidatePayload> | null> {
    if (!isProofResidual(residual) || !residual.repair?.ruleId) {
      return null;
    }
    const script = normalizeScript(candidate.payload.script);
    if (script.includes(residual.repair.ruleId)) {
      return null;
    }
    return makeProofCandidate(
      normalizeProofProblem(candidate.payload.problem),
      [...script, residual.repair.ruleId],
      candidate.payload.context || "proof-repair",
      candidate.payload.cost + 1,
    );
  }
}

export function normalizeProofRule(ruleInput: ProofRule | Record<string, unknown>): ProofRule {
  const raw = ruleInput as Record<string, unknown>;
  const ruleId = raw.ruleId ?? raw.rule_id;
  if (typeof ruleId !== "string" || ruleId.length === 0) {
    throw new RangeError("proof ruleId must be a non-empty string");
  }
  if (!Array.isArray(raw.premises)) {
    throw new RangeError("proof rule premises must be an array");
  }
  if (typeof raw.conclusion !== "string" || raw.conclusion.length === 0) {
    throw new RangeError("proof rule conclusion must be a non-empty string");
  }
  return {
    ruleId,
    premises: raw.premises.map(String),
    conclusion: raw.conclusion,
  };
}

export function normalizeProofProblem(problemInput: ProofProblem | Record<string, unknown>): ProofProblem {
  const raw = problemInput as Record<string, unknown>;
  if (!Array.isArray(raw.hypotheses)) {
    throw new RangeError("proof problem hypotheses must be an array");
  }
  if (!Array.isArray(raw.rules) || raw.rules.length === 0) {
    throw new RangeError("proof problem must contain at least one rule");
  }
  if (typeof raw.goal !== "string" || raw.goal.length === 0) {
    throw new RangeError("proof problem goal must be a non-empty string");
  }
  const rules = raw.rules.map((rule) => normalizeProofRule(rule as ProofRule | Record<string, unknown>));
  const ids = new Set(rules.map((rule) => rule.ruleId));
  if (ids.size !== rules.length) {
    throw new RangeError("proof rule ids must be unique");
  }
  return {
    hypotheses: raw.hypotheses.map(String),
    rules,
    goal: raw.goal,
  };
}

export function normalizeProofState(stateInput: Partial<ProofState> & { problem: ProofProblem }): ProofState {
  return {
    problem: normalizeProofProblem(stateInput.problem),
    proven: Boolean(stateInput.proven),
    derived: (stateInput.derived ?? []).map(String),
    proof: normalizeScript(stateInput.proof ?? []),
  };
}

export function deriveFacts(problemInput: ProofProblem, scriptInput: string[]): Set<string> {
  const problem = normalizeProofProblem(problemInput);
  const script = normalizeScript(scriptInput);
  const rules = new Map(problem.rules.map((rule) => [rule.ruleId, rule]));
  const facts = new Set(problem.hypotheses);
  const used = new Set<string>();
  for (const ruleId of script) {
    const rule = rules.get(ruleId);
    if (!rule || used.has(ruleId) || rule.premises.some((premise) => !facts.has(premise))) {
      throw new Error(`invalid proof script step: ${ruleId}`);
    }
    facts.add(rule.conclusion);
    used.add(ruleId);
  }
  return facts;
}

export async function makeProofCandidate(
  problemInput: ProofProblem,
  scriptInput: string[],
  context = "proof",
  cost?: number,
): Promise<TypedCandidate<ProofCandidatePayload>> {
  const problem = normalizeProofProblem(problemInput);
  const script = normalizeScript(scriptInput);
  return makeCandidate(
    {
      context,
      problem,
      script,
      cost: cost ?? script.length,
    },
    "proof.horn_script",
    "proof.horn_script.v1",
    {
      problem: await stableHash(problem),
      script: await stableHash(script),
    },
  );
}

export function chainProofProblem(ruleCount = 6, prefix = "p"): { problem: ProofProblem; correctScript: string[] } {
  if (!Number.isInteger(ruleCount) || ruleCount <= 0) {
    throw new RangeError("ruleCount must be positive");
  }
  const rules: ProofRule[] = [];
  for (let idx = 0; idx < ruleCount; idx += 1) {
    rules.push({
      ruleId: `r${idx + 1}`,
      premises: [`${prefix}${idx}`],
      conclusion: `${prefix}${idx + 1}`,
    });
  }
  return {
    problem: { hypotheses: [`${prefix}0`], rules, goal: `${prefix}${ruleCount}` },
    correctScript: rules.map((rule) => rule.ruleId),
  };
}

export async function runStaticProofEpisode(
  problemInput: ProofProblem,
  scripts: string[][],
  ledger: Ledger,
  episode: number,
): Promise<ProofEpisodeResult> {
  const problem = normalizeProofProblem(problemInput);
  const engine = new TransactionEngine(new HornProofAdapter(), ledger);
  const state: ProofState = { problem, proven: false, derived: [], proof: [] };
  for (let idx = 0; idx < scripts.length; idx += 1) {
    const script = normalizeScript(scripts[idx]);
    const candidate = await makeProofCandidate(problem, script, "proof-static", idx + 1);
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `proof-static-${episode}-${idx + 1}`,
        actions: [{ script }],
        seeds: [episode, idx + 1],
        modelVersion: "proof.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return episodeResult(idx + 1, true, engine, state);
    }
  }
  return episodeResult(scripts.length, false, engine, state);
}

export async function runRepairProofEpisode(
  problemInput: ProofProblem,
  ledger: Ledger,
  repairer: ProofResidualRepairer,
  episode: number,
): Promise<ProofEpisodeResult> {
  const problem = normalizeProofProblem(problemInput);
  const engine = new TransactionEngine(new HornProofAdapter(), ledger);
  const state: ProofState = { problem, proven: false, derived: [], proof: [] };
  let candidate = await makeProofCandidate(problem, [], "proof-repair", 1);
  for (let attempt = 0; attempt < problem.rules.length + 2; attempt += 1) {
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `proof-repair-${episode}-${attempt}`,
        actions: [{ script: candidate.payload.script }],
        seeds: [episode, attempt],
        modelVersion: "proof.residual_repair.v1",
      }),
      candidate,
    );
    repairer.update(outcome.receipt);
    if (outcome.committed) {
      return episodeResult(attempt + 1, true, engine, state);
    }
    const repaired = await repairer.propose(candidate, outcome.receipt.hardResult.residual);
    if (!repaired) {
      return episodeResult(attempt + 1, false, engine, state);
    }
    candidate = repaired;
  }
  return episodeResult(problem.rules.length + 2, false, engine, state);
}

export async function runProofKernelBenchmark(seed = 41, episodes = 24, ruleCount = 6): Promise<ProofKernelReport> {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  const { problem, correctScript } = chainProofProblem(ruleCount);
  const scripts = shuffle(permutations(correctScript), seed);
  const staticLedgers: Ledger[] = [];
  const repairLedgers: Ledger[] = [];
  const repairer = new ProofResidualRepairer();
  const staticResults: ProofEpisodeResult[] = [];
  const repairResults: ProofEpisodeResult[] = [];
  for (let episode = 0; episode < episodes; episode += 1) {
    const staticLedger = new Ledger();
    const repairLedger = new Ledger();
    staticLedgers.push(staticLedger);
    repairLedgers.push(repairLedger);
    staticResults.push(await runStaticProofEpisode(problem, scripts, staticLedger, episode));
    repairResults.push(await runRepairProofEpisode(problem, repairLedger, repairer, episode));
  }
  const allResults = [...staticResults, ...repairResults];
  const staticCps = callsPerSuccess(staticResults);
  const repairCps = callsPerSuccess(repairResults);
  return {
    episodes,
    ruleCount,
    staticCallsPerSuccess: staticCps,
    repairCallsPerSuccess: repairCps,
    repairGain: staticCps / repairCps,
    repairSuccessRate: repairResults.filter((row) => row.success).length / repairResults.length,
    ledgerAuditRate: allResults.filter((row) => row.auditOk).length / allResults.length,
    replayRollbackRate: allResults.filter((row) => row.replayRollbackOk).length / allResults.length,
    invalidCommitCount: invalidCommits([...staticLedgers, ...repairLedgers]),
    learnedResidualKinds: Object.fromEntries(repairer.rejectedResiduals),
  };
}

function normalizeScript(scriptInput: unknown[]): string[] {
  if (!Array.isArray(scriptInput)) {
    throw new RangeError("proof script must be an array");
  }
  return scriptInput.map(String);
}

function nextApplicableRule(problem: ProofProblem, facts: Set<string>, used: Set<string>): ProofRepairHint | null {
  for (const rule of problem.rules) {
    if (!used.has(rule.ruleId) && rule.premises.every((premise) => facts.has(premise))) {
      return { ruleId: rule.ruleId, conclusion: rule.conclusion };
    }
  }
  return null;
}

async function episodeResult(
  calls: number,
  success: boolean,
  engine: TransactionEngine<ProofState, ProofCandidatePayload>,
  seedState: ProofState,
): Promise<ProofEpisodeResult> {
  const auditOk = await engine.ledger.audit();
  let replayRollbackOk = false;
  if (auditOk) {
    try {
      await engine.replayAudit(seedState);
      replayRollbackOk = proofStatesEqual(await engine.rollbackAudit(seedState), seedState);
    } catch (_error) {
      replayRollbackOk = false;
    }
  }
  return { calls, success, auditOk, replayRollbackOk };
}

function proofProblemsEqual(a: ProofProblem, b: ProofProblem): boolean {
  return JSON.stringify(normalizeProofProblem(a)) === JSON.stringify(normalizeProofProblem(b));
}

function proofStatesEqual(a: ProofState, b: ProofState): boolean {
  return JSON.stringify(normalizeProofState(a)) === JSON.stringify(normalizeProofState(b));
}

function isProofResidual(value: unknown): value is ProofResidual {
  if (!value || typeof value !== "object") {
    return false;
  }
  const residual = value as Partial<ProofResidual>;
  return residual.kind === "unknown_rule"
    || residual.kind === "duplicate_rule"
    || residual.kind === "missing_premise"
    || residual.kind === "goal_not_derived";
}

function callsPerSuccess(results: ProofEpisodeResult[]): number {
  const successes = results.filter((row) => row.success).length;
  const calls = results.reduce((sum, row) => sum + row.calls, 0);
  return successes === 0 ? Number.POSITIVE_INFINITY : calls / successes;
}

function invalidCommits(ledgers: Ledger[]): number {
  return ledgers.reduce((sum, ledger) =>
    sum + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  0);
}

function permutations<T>(values: T[]): T[][] {
  if (values.length === 0) {
    return [[]];
  }
  const out: T[][] = [];
  for (let idx = 0; idx < values.length; idx += 1) {
    const head = values[idx];
    const rest = [...values.slice(0, idx), ...values.slice(idx + 1)];
    for (const tail of permutations(rest)) {
      out.push([head, ...tail]);
    }
  }
  return out;
}

function shuffle<T>(values: T[], seed: number): T[] {
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
