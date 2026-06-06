import {
  type HardVerifierResult,
  type ProposalTrace,
  type Receipt,
  type ReplayRollbackAdapter,
  type TypedCandidate,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { CostAwareReceiptDomainRouter, ProgrammableSubstrate } from "./sdk.js";

export const VERIFIER_COST_CONTEXT = "verifier-cost-route";
export const EXPENSIVE_VERIFIER_DOMAIN = "expensive_exact";
export const CHEAP_VERIFIER_DOMAIN = "cheap_exact";

export interface VerifierCostState {
  committedDomains: string[];
}

export interface VerifierCostPayload {
  context: string;
  action: string;
  domainId: string;
}

export interface VerifierCostReport {
  domainCount: number;
  expensiveVerifierCost: number;
  cheapVerifierCost: number;
  uniformRouterTopDomain: string;
  costAwareTopDomain: string;
  expensiveSuccessPerCostNumerator: number;
  expensiveSuccessPerCostDenominator: number;
  cheapSuccessPerCostNumerator: number;
  cheapSuccessPerCostDenominator: number;
  costNormalizedGain: number;
  totalVerifierCost: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
  invalidCommitCount: number;
}

export class VerifierCostAdapter implements ReplayRollbackAdapter<VerifierCostState, VerifierCostPayload> {
  domainId: string;
  verifierCost: number;
  verifierId: string;
  verifierVersion = "1.0";

  constructor(domainId: string, verifierCost: number) {
    if (!Number.isInteger(verifierCost) || verifierCost <= 0) {
      throw new RangeError("verifierCost must be a positive integer");
    }
    this.domainId = domainId;
    this.verifierCost = verifierCost;
    this.verifierId = `${domainId}_oracle`;
  }

  verify(candidate: TypedCandidate<VerifierCostPayload>): HardVerifierResult {
    const payload = normalizeVerifierCostPayload(candidate.payload);
    const metadata = { verifierCost: this.verifierCost, verifier_cost: this.verifierCost, domain: this.domainId };
    if (payload.domainId !== this.domainId) {
      return hardReject(
        this.verifierId,
        this.verifierVersion,
        { kind: "wrong_domain", expected: this.domainId, actual: payload.domainId },
        metadata,
      );
    }
    return hardAccept(this.verifierId, this.verifierVersion, { ...metadata, reward: 1 });
  }

  applyCommit(state: VerifierCostState, candidate: TypedCandidate<VerifierCostPayload>): VerifierCostState {
    const current = normalizeVerifierCostState(state);
    const payload = normalizeVerifierCostPayload(candidate.payload);
    return { committedDomains: [...current.committedDomains, payload.domainId] };
  }

  replay(state: VerifierCostState, receipt: Receipt): VerifierCostState {
    const current = normalizeVerifierCostState(state);
    const payload = normalizeVerifierCostPayload((receipt.replayBundle as { candidatePayload: VerifierCostPayload }).candidatePayload);
    return { committedDomains: [...current.committedDomains, payload.domainId] };
  }

  rollback(_state: VerifierCostState, receipt: Receipt): VerifierCostState {
    return normalizeVerifierCostState((receipt.rollbackBundle as { preState: VerifierCostState }).preState);
  }
}

export function normalizeVerifierCostState(state: VerifierCostState | Record<string, unknown>): VerifierCostState {
  const raw = state as Record<string, unknown>;
  const committedDomains = raw.committedDomains ?? raw.committed_domains ?? [];
  if (!Array.isArray(committedDomains)) {
    throw new RangeError("committedDomains must be an array");
  }
  return { committedDomains: committedDomains.map((domain) => String(domain)) };
}

export function makeVerifierCostCandidate(domainId: string): TypedCandidate<VerifierCostPayload> {
  return makeCandidate(
    { context: VERIFIER_COST_CONTEXT, action: domainId, domainId },
    "verifier_cost.probe",
    "verifier_cost.probe.v1",
  );
}

export function makeVerifierCostTrace(domainId: string): ProposalTrace {
  return makeTrace({
    branchId: `verifier-cost-${domainId}`,
    actions: [{ context: VERIFIER_COST_CONTEXT, action: domainId }],
    seeds: ["verifier_cost", domainId],
    modelVersion: "verifier.cost.v1",
  });
}

export async function runVerifierCostBenchmark(): Promise<VerifierCostReport> {
  const expensiveCost = 12;
  const cheapCost = 3;
  const domainOrder = [EXPENSIVE_VERIFIER_DOMAIN, CHEAP_VERIFIER_DOMAIN];
  const uniform = await runSubstrate(new ProgrammableSubstrate(), expensiveCost, cheapCost);
  const costAwareRouter = new CostAwareReceiptDomainRouter();
  const costAware = await runSubstrate(new ProgrammableSubstrate(costAwareRouter), expensiveCost, cheapCost);
  const expensiveStats = costAwareRouter.stats(VERIFIER_COST_CONTEXT, EXPENSIVE_VERIFIER_DOMAIN);
  const cheapStats = costAwareRouter.stats(VERIFIER_COST_CONTEXT, CHEAP_VERIFIER_DOMAIN);
  return {
    domainCount: domainOrder.length,
    expensiveVerifierCost: expensiveCost,
    cheapVerifierCost: cheapCost,
    uniformRouterTopDomain: uniform.rankDomains(VERIFIER_COST_CONTEXT, domainOrder)[0],
    costAwareTopDomain: costAware.rankDomains(VERIFIER_COST_CONTEXT, domainOrder)[0],
    expensiveSuccessPerCostNumerator: expensiveStats.successPerCostNumerator,
    expensiveSuccessPerCostDenominator: expensiveStats.successPerCostDenominator,
    cheapSuccessPerCostNumerator: cheapStats.successPerCostNumerator,
    cheapSuccessPerCostDenominator: cheapStats.successPerCostDenominator,
    costNormalizedGain: cheapStats.successPerCost / expensiveStats.successPerCost,
    totalVerifierCost: expensiveStats.verifierCost + cheapStats.verifierCost,
    ledgerAudit: await allAuditsOk(costAware, domainOrder),
    replayRollbackRate: await replayRollbackRate(costAware, domainOrder),
    invalidCommitCount: costAware.invalidCommitCount(domainOrder),
  };
}

async function runSubstrate(substrate: ProgrammableSubstrate, expensiveCost: number, cheapCost: number): Promise<ProgrammableSubstrate> {
  for (const [domainId, verifierCost] of [
    [EXPENSIVE_VERIFIER_DOMAIN, expensiveCost],
    [CHEAP_VERIFIER_DOMAIN, cheapCost],
  ] as const) {
    substrate.register(domainId, new VerifierCostAdapter(domainId, verifierCost));
    await substrate.submit(
      domainId,
      { committedDomains: [] },
      makeVerifierCostTrace(domainId),
      makeVerifierCostCandidate(domainId),
      { context: VERIFIER_COST_CONTEXT },
    );
  }
  return substrate;
}

async function allAuditsOk(substrate: ProgrammableSubstrate, domainIds: string[]): Promise<boolean> {
  const audits = await Promise.all(domainIds.map((domainId) => substrate.auditDomain(domainId, { committedDomains: [] })));
  return audits.every((audit) => audit.ok);
}

async function replayRollbackRate(substrate: ProgrammableSubstrate, domainIds: string[]): Promise<number> {
  const audits = await Promise.all(domainIds.map((domainId) => substrate.auditDomain(domainId, { committedDomains: [] })));
  return audits.every((audit) => audit.ledgerAudit && audit.replayMatchesReceipts && audit.rollbackMatchesSeed) ? 1 : 0;
}

function normalizeVerifierCostPayload(payload: VerifierCostPayload | Record<string, unknown>): VerifierCostPayload {
  const raw = payload as Record<string, unknown>;
  const domainId = String(raw.domainId ?? raw.domain_id ?? "");
  if (!domainId) {
    throw new RangeError("domainId must be non-empty");
  }
  return {
    context: String(raw.context ?? VERIFIER_COST_CONTEXT),
    action: String(raw.action ?? domainId),
    domainId,
  };
}
