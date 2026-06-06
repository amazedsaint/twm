import {
  type CommitDecision,
  type HardVerifierResult,
  type ProposalTrace,
  type Receipt,
  type TransactionEngine,
  type TypedCandidate,
  hardAbstain,
  receiptStaticValid,
} from "./core.js";
import { stableHash } from "./canonical.js";

export const BRANCH_SELECTION_CERTIFICATE_SCHEMA = "trwm.branch_selection_certificate.v1";

export interface BranchProjector<State, CandidatePayload> {
  project(state: State, trace: ProposalTrace): Promise<TypedCandidate<CandidatePayload>> | TypedCandidate<CandidatePayload>;
}

export interface BranchRanker<CandidatePayload> {
  choose(verified: Array<[ProposalTrace, TypedCandidate<CandidatePayload>, HardVerifierResult]>): number;
}

export interface BranchOutcome<State> {
  state: State;
  committed: boolean;
  receipts: unknown[];
  verifierCalls: number;
  reason: CommitDecision | "no_admissible_worker_receipt";
  verifierCost: number;
  abstainedCount: number;
}

export interface BranchSelectionCertificate {
  schemaVersion: typeof BRANCH_SELECTION_CERTIFICATE_SCHEMA;
  branchCount: number;
  verifierCallCount: number;
  acceptedIndices: number[];
  rejectedIndices: number[];
  abstainedIndices: number[];
  loserIndices: number[];
  selectedIndex: number | null;
  committedIndex: number | null;
  receiptHashes: string[];
  proposalTraceHashes: string[];
  typedCandidateHashes: string[];
  hardResults: Array<HardVerifierResult["result"]>;
  commitDecisions: string[];
  committedFlags: boolean[];
  certificateHash: string;
}

export class LowestCostRanker<CandidatePayload> implements BranchRanker<CandidatePayload> {
  choose(verified: Array<[ProposalTrace, TypedCandidate<CandidatePayload>, HardVerifierResult]>): number {
    let bestIdx = 0;
    let bestCost = Number.POSITIVE_INFINITY;
    for (let idx = 0; idx < verified.length; idx += 1) {
      const [_trace, candidate, result] = verified[idx];
      const cost = Number(result.metadata.cost ?? 0);
      const energy = Number(result.metadata.energy ?? 0);
      const payload = candidate.payload;
      const softRank = payload && typeof payload === "object" && "softRank" in payload
        ? Number((payload as { softRank?: unknown }).softRank ?? 0)
        : 0;
      const value = cost + energy - softRank;
      if (value < bestCost) {
        bestIdx = idx;
        bestCost = value;
      }
    }
    return bestIdx;
  }
}

export class BranchRuntime<State, CandidatePayload> {
  engine: TransactionEngine<State, CandidatePayload>;
  projector: BranchProjector<State, CandidatePayload>;
  ranker: BranchRanker<CandidatePayload>;

  constructor(
    engine: TransactionEngine<State, CandidatePayload>,
    projector: BranchProjector<State, CandidatePayload>,
    ranker: BranchRanker<CandidatePayload> = new LowestCostRanker<CandidatePayload>(),
  ) {
    this.engine = engine;
    this.projector = projector;
    this.ranker = ranker;
  }

  async step(state: State, traces: ProposalTrace[]): Promise<BranchOutcome<State>> {
    const evaluated: Array<[ProposalTrace, TypedCandidate<CandidatePayload>, HardVerifierResult]> = [];
    const receipts: unknown[] = [];
    for (const trace of traces) {
      const candidate = await this.projector.project(state, trace);
      const result = await this.engine.adapter.verify(candidate);
      this.engine.hardVerifierCalls += 1;
      evaluated.push([trace, candidate, result]);
    }
    const verified = evaluated.filter(([_trace, _candidate, result]) => result.result === "accept");
    if (verified.length === 0) {
      for (const [trace, candidate, result] of evaluated) {
        const outcome = await this.engine.recordEvaluatedCandidate(state, trace, candidate, result, {}, "no_admissible_branch");
        receipts.push(outcome.receipt);
      }
      return {
        state,
        committed: false,
        receipts,
        verifierCalls: evaluated.length,
        reason: "no_admissible_branch",
        verifierCost: 0,
        abstainedCount: 0,
      };
    }
    const winnerIdx = this.ranker.choose(verified);
    if (!Number.isInteger(winnerIdx) || winnerIdx < 0 || winnerIdx >= verified.length) {
      for (const [trace, candidate, result] of evaluated) {
        const outcome = await this.engine.recordEvaluatedCandidate(state, trace, candidate, result, {}, "ranker_invalid_choice");
        receipts.push(outcome.receipt);
      }
      return {
        state,
        committed: false,
        receipts,
        verifierCalls: evaluated.length,
        reason: "ranker_invalid_choice",
        verifierCost: 0,
        abstainedCount: 0,
      };
    }
    const winnerTrace = verified[winnerIdx][0];
    let nextState = state;
    let committed = false;
    let reason: CommitDecision = "commit";
    for (const [trace, candidate, result] of evaluated) {
      const force = result.result === "accept" && trace !== winnerTrace ? "rolled_back_loser" : undefined;
      const outcome = await this.engine.recordEvaluatedCandidate(state, trace, candidate, result, {}, force);
      receipts.push(outcome.receipt);
      if (trace === winnerTrace) {
        nextState = outcome.state;
        committed = outcome.committed;
        reason = outcome.reason;
      }
    }
    return { state: nextState, committed, receipts, verifierCalls: evaluated.length, reason, verifierCost: 0, abstainedCount: 0 };
  }
}

export class VerifierBudget {
  maxCost: number;

  constructor(maxCost: number) {
    if (!Number.isInteger(maxCost) || maxCost < 0) {
      throw new RangeError("maxCost must be a non-negative integer");
    }
    this.maxCost = maxCost;
  }
}

export class BudgetedBranchRuntime<State, CandidatePayload> {
  engine: TransactionEngine<State, CandidatePayload>;
  projector: BranchProjector<State, CandidatePayload>;
  budget: VerifierBudget;
  ranker: BranchRanker<CandidatePayload>;
  defaultVerifierCost: number;

  constructor(
    engine: TransactionEngine<State, CandidatePayload>,
    projector: BranchProjector<State, CandidatePayload>,
    budget: VerifierBudget,
    ranker: BranchRanker<CandidatePayload> = new LowestCostRanker<CandidatePayload>(),
    options: { defaultVerifierCost?: number } = {},
  ) {
    const defaultVerifierCost = options.defaultVerifierCost ?? 1;
    if (!Number.isInteger(defaultVerifierCost) || defaultVerifierCost <= 0) {
      throw new RangeError("defaultVerifierCost must be a positive integer");
    }
    this.engine = engine;
    this.projector = projector;
    this.budget = budget;
    this.ranker = ranker;
    this.defaultVerifierCost = defaultVerifierCost;
  }

  async step(state: State, traces: ProposalTrace[]): Promise<BranchOutcome<State>> {
    const evaluated: Array<[ProposalTrace, TypedCandidate<CandidatePayload>, HardVerifierResult]> = [];
    const receipts: unknown[] = [];
    let spent = 0;
    let verifierCalls = 0;
    let abstainedCount = 0;

    for (const trace of traces) {
      const candidate = await this.projector.project(state, trace);
      const cost = candidateVerifierCost(candidate, this.defaultVerifierCost);
      const remaining = this.budget.maxCost - spent;
      if (cost > remaining) {
        abstainedCount += 1;
        evaluated.push([
          trace,
          candidate,
          hardAbstain(
            this.engine.adapter.verifierId,
            this.engine.adapter.verifierVersion,
            {
              kind: "verifier_budget_exhausted",
              required_verifier_cost: cost,
              requiredVerifierCost: cost,
              remaining_budget: Math.max(0, remaining),
              remainingBudget: Math.max(0, remaining),
              budget: this.budget.maxCost,
            },
            {
              verifier_cost_spent: 0,
              verifierCostSpent: 0,
              required_verifier_cost: cost,
              requiredVerifierCost: cost,
              remaining_budget: Math.max(0, remaining),
              remainingBudget: Math.max(0, remaining),
              budget: this.budget.maxCost,
            },
          ),
        ]);
        continue;
      }

      const verified = await this.engine.adapter.verify(candidate);
      const result = withVerifierCostMetadata(verified, cost, spent + cost, this.budget.maxCost);
      spent += cost;
      verifierCalls += 1;
      this.engine.hardVerifierCalls += 1;
      evaluated.push([trace, candidate, result]);
    }

    const verified = evaluated.filter(([_trace, _candidate, result]) => result.result === "accept");
    if (verified.length === 0) {
      for (const [trace, candidate, result] of evaluated) {
        const outcome = await this.engine.recordEvaluatedCandidate(state, trace, candidate, result, {}, "no_admissible_branch");
        receipts.push(outcome.receipt);
      }
      return {
        state,
        committed: false,
        receipts,
        verifierCalls,
        reason: "no_admissible_branch",
        verifierCost: spent,
        abstainedCount,
      };
    }

    const winnerIdx = this.ranker.choose(verified);
    if (!Number.isInteger(winnerIdx) || winnerIdx < 0 || winnerIdx >= verified.length) {
      for (const [trace, candidate, result] of evaluated) {
        const outcome = await this.engine.recordEvaluatedCandidate(state, trace, candidate, result, {}, "ranker_invalid_choice");
        receipts.push(outcome.receipt);
      }
      return {
        state,
        committed: false,
        receipts,
        verifierCalls,
        reason: "ranker_invalid_choice",
        verifierCost: spent,
        abstainedCount,
      };
    }

    const winnerTrace = verified[winnerIdx][0];
    let nextState = state;
    let committed = false;
    let reason: CommitDecision = "commit";
    for (const [trace, candidate, result] of evaluated) {
      const force = result.result === "accept" && trace !== winnerTrace ? "rolled_back_loser" : undefined;
      const outcome = await this.engine.recordEvaluatedCandidate(state, trace, candidate, result, {}, force);
      receipts.push(outcome.receipt);
      if (trace === winnerTrace) {
        nextState = outcome.state;
        committed = outcome.committed;
        reason = outcome.reason;
      }
    }
    return { state: nextState, committed, receipts, verifierCalls, reason, verifierCost: spent, abstainedCount };
  }
}

export interface WorkerReceipt<CandidatePayload> {
  parentHead: string;
  trace: ProposalTrace;
  candidate: TypedCandidate<CandidatePayload>;
  result: HardVerifierResult;
}

export class DistributedCommitManager<State, CandidatePayload> {
  engine: TransactionEngine<State, CandidatePayload>;
  ranker: BranchRanker<CandidatePayload>;
  staleReceiptRejectionCount = 0;

  constructor(
    engine: TransactionEngine<State, CandidatePayload>,
    ranker: BranchRanker<CandidatePayload> = new LowestCostRanker<CandidatePayload>(),
  ) {
    this.engine = engine;
    this.ranker = ranker;
  }

  async commitOne(state: State, workerReceipts: Array<WorkerReceipt<CandidatePayload>>): Promise<BranchOutcome<State>> {
    const expectedParentHead = this.engine.ledger.head;
    const accepted: Array<WorkerReceipt<CandidatePayload>> = [];
    const receipts: unknown[] = [];
    for (const workerReceipt of workerReceipts) {
      if (workerReceipt.parentHead !== expectedParentHead) {
        this.staleReceiptRejectionCount += 1;
      } else if (workerReceipt.result.result === "accept") {
        accepted.push(workerReceipt);
      }
    }
    if (accepted.length === 0) {
      for (const workerReceipt of workerReceipts) {
        const force = workerReceipt.parentHead !== expectedParentHead ? "stale_parent" : "worker_not_accepted";
        const outcome = await this.engine.recordEvaluatedCandidate(
          state,
          workerReceipt.trace,
          workerReceipt.candidate,
          workerReceipt.result,
          {},
          force,
        );
        receipts.push(outcome.receipt);
      }
      return {
        state,
        committed: false,
        receipts,
        verifierCalls: workerReceipts.length,
        reason: "no_admissible_worker_receipt",
        verifierCost: 0,
        abstainedCount: 0,
      };
    }
    const winnerIdx = this.ranker.choose(accepted.map((row) => [row.trace, row.candidate, row.result]));
    if (!Number.isInteger(winnerIdx) || winnerIdx < 0 || winnerIdx >= accepted.length) {
      for (const workerReceipt of workerReceipts) {
        const force = workerReceipt.parentHead !== expectedParentHead ? "stale_parent" : "ranker_invalid_choice";
        const outcome = await this.engine.recordEvaluatedCandidate(
          state,
          workerReceipt.trace,
          workerReceipt.candidate,
          workerReceipt.result,
          {},
          force,
        );
        receipts.push(outcome.receipt);
      }
      return {
        state,
        committed: false,
        receipts,
        verifierCalls: workerReceipts.length,
        reason: "ranker_invalid_choice",
        verifierCost: 0,
        abstainedCount: 0,
      };
    }
    const chosen = accepted[winnerIdx];
    let nextState = state;
    let committed = false;
    let reason: CommitDecision = "commit";
    for (const workerReceipt of workerReceipts) {
      const force = workerReceipt.parentHead !== expectedParentHead
        ? "stale_parent"
        : workerReceipt.result.result !== "accept"
          ? "worker_not_accepted"
          : workerReceipt.trace !== chosen.trace
            ? "rolled_back_loser"
            : undefined;
      const outcome = await this.engine.recordEvaluatedCandidate(state, workerReceipt.trace, workerReceipt.candidate, workerReceipt.result, {}, force);
      receipts.push(outcome.receipt);
      if (workerReceipt.trace === chosen.trace) {
        nextState = outcome.state;
        committed = outcome.committed;
        reason = outcome.reason;
      }
    }
    return { state: nextState, committed, receipts, verifierCalls: workerReceipts.length, reason, verifierCost: 0, abstainedCount: 0 };
  }
}

export async function buildBranchSelectionCertificate(
  receipts: Receipt[],
  options: { verifierCallCount?: number } = {},
): Promise<BranchSelectionCertificate> {
  const acceptedIndices = receipts.flatMap((receipt, idx) => receipt.hardResult.result === "accept" ? [idx] : []);
  const rejectedIndices = receipts.flatMap((receipt, idx) => receipt.hardResult.result === "reject" ? [idx] : []);
  const abstainedIndices = receipts.flatMap((receipt, idx) => receipt.hardResult.result === "abstain" ? [idx] : []);
  const loserIndices = receipts.flatMap((receipt, idx) => receipt.commitDecision === "rolled_back_loser" ? [idx] : []);
  const committedIndices = receipts.flatMap((receipt, idx) => receipt.committed && receipt.commitDecision === "commit" ? [idx] : []);
  const selectedCandidates = acceptedIndices.filter((idx) =>
    !loserIndices.includes(idx)
    && !["ranker_invalid_choice", "no_admissible_branch"].includes(receipts[idx].commitDecision),
  );
  const certificate: BranchSelectionCertificate = {
    schemaVersion: BRANCH_SELECTION_CERTIFICATE_SCHEMA,
    branchCount: receipts.length,
    verifierCallCount: options.verifierCallCount ?? receipts.length,
    acceptedIndices,
    rejectedIndices,
    abstainedIndices,
    loserIndices,
    selectedIndex: selectedCandidates.length === 1 ? selectedCandidates[0] : null,
    committedIndex: committedIndices.length === 1 ? committedIndices[0] : null,
    receiptHashes: receipts.map((receipt) => receipt.receiptHash),
    proposalTraceHashes: receipts.map((receipt) => receipt.proposalTraceHash),
    typedCandidateHashes: receipts.map((receipt) => receipt.typedCandidateHash),
    hardResults: receipts.map((receipt) => receipt.hardResult.result),
    commitDecisions: receipts.map((receipt) => receipt.commitDecision),
    committedFlags: receipts.map((receipt) => receipt.committed),
    certificateHash: "",
  };
  certificate.certificateHash = await branchSelectionCertificateHash(certificate);
  return certificate;
}

export async function auditBranchSelection(receipts: Receipt[], certificate: BranchSelectionCertificate): Promise<boolean> {
  try {
    if (!await validateBranchSelectionCertificate(certificate)) {
      return false;
    }
    if (receipts.length !== certificate.branchCount) {
      return false;
    }
    const staticChecks = await Promise.all(receipts.map((receipt) => receiptStaticValid(receipt)));
    if (!staticChecks.every(Boolean)) {
      return false;
    }
    const rebuilt = await buildBranchSelectionCertificate(receipts, { verifierCallCount: certificate.verifierCallCount });
    return rebuilt.certificateHash === certificate.certificateHash;
  } catch {
    return false;
  }
}

export async function validateBranchSelectionCertificate(certificate: BranchSelectionCertificate): Promise<boolean> {
  try {
    const branchCount = certificate.branchCount;
    if (certificate.schemaVersion !== BRANCH_SELECTION_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (!Number.isInteger(branchCount) || branchCount < 0) {
      return false;
    }
    if (
      !Number.isInteger(certificate.verifierCallCount)
      || certificate.verifierCallCount < 0
      || certificate.verifierCallCount > branchCount
    ) {
      return false;
    }
    const lengthFields = [
      certificate.receiptHashes,
      certificate.proposalTraceHashes,
      certificate.typedCandidateHashes,
      certificate.hardResults,
      certificate.commitDecisions,
      certificate.committedFlags,
    ];
    if (lengthFields.some((field) => field.length !== branchCount)) {
      return false;
    }

    const accepted = normalizeIndices(certificate.acceptedIndices);
    const rejected = normalizeIndices(certificate.rejectedIndices);
    const abstained = normalizeIndices(certificate.abstainedIndices);
    const losers = normalizeIndices(certificate.loserIndices);
    if (
      !sameArray(accepted, certificate.acceptedIndices)
      || !sameArray(rejected, certificate.rejectedIndices)
      || !sameArray(abstained, certificate.abstainedIndices)
      || !sameArray(losers, certificate.loserIndices)
    ) {
      return false;
    }
    if (![accepted, rejected, abstained, losers].every((indices) => indicesValid(indices, branchCount))) {
      return false;
    }
    if (overlap(accepted, rejected) || overlap(accepted, abstained) || overlap(rejected, abstained)) {
      return false;
    }
    if (!sameArray([...accepted, ...rejected, ...abstained].sort((a, b) => a - b), range(branchCount))) {
      return false;
    }
    if (!sameArray(accepted, certificate.hardResults.flatMap((result, idx) => result === "accept" ? [idx] : []))) {
      return false;
    }
    if (!sameArray(rejected, certificate.hardResults.flatMap((result, idx) => result === "reject" ? [idx] : []))) {
      return false;
    }
    if (!sameArray(abstained, certificate.hardResults.flatMap((result, idx) => result === "abstain" ? [idx] : []))) {
      return false;
    }
    if (certificate.hardResults.some((result) => !["accept", "reject", "abstain"].includes(result))) {
      return false;
    }
    if (certificate.committedFlags.some((flag) => typeof flag !== "boolean")) {
      return false;
    }
    if (certificate.commitDecisions.some((decision) => typeof decision !== "string" || decision.length === 0)) {
      return false;
    }
    const hashFields = [
      certificate.receiptHashes,
      certificate.proposalTraceHashes,
      certificate.typedCandidateHashes,
    ];
    if (hashFields.some((field) => field.some((value) => !isHash(value)))) {
      return false;
    }

    const committedFlags = certificate.committedFlags.flatMap((flag, idx) => flag ? [idx] : []);
    if (committedFlags.length > 1) {
      return false;
    }
    if (certificate.committedIndex === null) {
      if (committedFlags.length > 0) {
        return false;
      }
    } else if (!sameArray(committedFlags, [certificate.committedIndex])) {
      return false;
    }
    if (certificate.committedIndex !== null) {
      if (!indexValid(certificate.committedIndex, branchCount)) {
        return false;
      }
      if (!accepted.includes(certificate.committedIndex)) {
        return false;
      }
      if (certificate.commitDecisions[certificate.committedIndex] !== "commit") {
        return false;
      }
    }
    if (certificate.commitDecisions.some((decision, idx) => decision === "commit" && !certificate.committedFlags[idx])) {
      return false;
    }

    if (certificate.selectedIndex !== null) {
      if (!indexValid(certificate.selectedIndex, branchCount)) {
        return false;
      }
      if (!accepted.includes(certificate.selectedIndex)) {
        return false;
      }
      if (losers.includes(certificate.selectedIndex)) {
        return false;
      }
      const selectedDecision = certificate.commitDecisions[certificate.selectedIndex];
      if (["ranker_invalid_choice", "no_admissible_branch", "rolled_back_loser"].includes(selectedDecision)) {
        return false;
      }
      if (certificate.committedIndex !== null && certificate.committedIndex !== certificate.selectedIndex) {
        return false;
      }
      const expectedLosers = accepted.filter((idx) => idx !== certificate.selectedIndex);
      if (!sameArray(losers, expectedLosers)) {
        return false;
      }
    } else {
      if (certificate.committedIndex !== null || losers.length > 0) {
        return false;
      }
      if (accepted.some((idx) => !["ranker_invalid_choice", "no_admissible_branch"].includes(certificate.commitDecisions[idx]))) {
        return false;
      }
    }

    if (losers.some((idx) => !accepted.includes(idx))) {
      return false;
    }
    if (losers.some((idx) => certificate.commitDecisions[idx] !== "rolled_back_loser")) {
      return false;
    }
    if (losers.some((idx) => certificate.committedFlags[idx])) {
      return false;
    }
    const blockedStatusIndices = [...rejected, ...abstained];
    if (blockedStatusIndices.some((idx) => ["commit", "rolled_back_loser"].includes(certificate.commitDecisions[idx]))) {
      return false;
    }
    if (blockedStatusIndices.some((idx) => certificate.committedFlags[idx])) {
      return false;
    }
    return certificate.certificateHash === await branchSelectionCertificateHash(certificate);
  } catch {
    return false;
  }
}

export async function branchSelectionCertificateHash(certificate: BranchSelectionCertificate): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export function candidateVerifierCost(candidate: TypedCandidate<unknown>, defaultVerifierCost = 1): number {
  if (!Number.isInteger(defaultVerifierCost) || defaultVerifierCost <= 0) {
    throw new RangeError("defaultVerifierCost must be a positive integer");
  }
  const payload = candidate.payload;
  const value = payload && typeof payload === "object"
    ? (payload as Record<string, unknown>).verifier_cost ?? (payload as Record<string, unknown>).verifierCost ?? defaultVerifierCost
    : defaultVerifierCost;
  if (typeof value === "boolean") {
    throw new RangeError("verifier cost must be a positive integer");
  }
  const cost = typeof value === "string" && /^[0-9]+$/.test(value.trim()) ? Number(value) : value;
  if (typeof cost !== "number" || !Number.isInteger(cost) || cost <= 0) {
    throw new RangeError("verifier cost must be a positive integer");
  }
  return cost;
}

function withVerifierCostMetadata(
  result: HardVerifierResult,
  verifierCost: number,
  budgetSpent: number,
  budget: number,
): HardVerifierResult {
  return {
    ...result,
    metadata: {
      ...result.metadata,
      verifier_cost: result.metadata.verifier_cost ?? verifierCost,
      verifierCost: result.metadata.verifierCost ?? verifierCost,
      verifier_cost_spent: verifierCost,
      verifierCostSpent: verifierCost,
      budget_spent: budgetSpent,
      budgetSpent,
      budget,
    },
  };
}

function normalizeIndices(indices: number[]): number[] {
  return [...indices].sort((a, b) => a - b);
}

function indicesValid(indices: number[], branchCount: number): boolean {
  return new Set(indices).size === indices.length && indices.every((index) => indexValid(index, branchCount));
}

function indexValid(index: number, branchCount: number): boolean {
  return Number.isInteger(index) && index >= 0 && index < branchCount;
}

function overlap(left: number[], right: number[]): boolean {
  const rightSet = new Set(right);
  return left.some((item) => rightSet.has(item));
}

function sameArray<T>(left: T[], right: T[]): boolean {
  return left.length === right.length && left.every((item, idx) => Object.is(item, right[idx]));
}

function range(count: number): number[] {
  return Array.from({ length: count }, (_value, idx) => idx);
}

function isHash(value: string): boolean {
  return /^[0-9a-f]{64}$/.test(value);
}
