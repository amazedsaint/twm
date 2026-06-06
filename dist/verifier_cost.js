import {





  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { CostAwareReceiptDomainRouter, ProgrammableSubstrate } from "./sdk.js";

export const VERIFIER_COST_CONTEXT = "verifier-cost-route";
export const EXPENSIVE_VERIFIER_DOMAIN = "expensive_exact";
export const CHEAP_VERIFIER_DOMAIN = "cheap_exact";




























export class VerifierCostAdapter                                                                          {
  domainId        ;
  verifierCost        ;
  verifierId        ;
  verifierVersion = "1.0";

  constructor(domainId        , verifierCost        ) {
    if (!Number.isInteger(verifierCost) || verifierCost <= 0) {
      throw new RangeError("verifierCost must be a positive integer");
    }
    this.domainId = domainId;
    this.verifierCost = verifierCost;
    this.verifierId = `${domainId}_oracle`;
  }

  verify(candidate                                     )                     {
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

  applyCommit(state                   , candidate                                     )                    {
    const current = normalizeVerifierCostState(state);
    const payload = normalizeVerifierCostPayload(candidate.payload);
    return { committedDomains: [...current.committedDomains, payload.domainId] };
  }

  replay(state                   , receipt         )                    {
    const current = normalizeVerifierCostState(state);
    const payload = normalizeVerifierCostPayload((receipt.replayBundle                                             ).candidatePayload);
    return { committedDomains: [...current.committedDomains, payload.domainId] };
  }

  rollback(_state                   , receipt         )                    {
    return normalizeVerifierCostState((receipt.rollbackBundle                                   ).preState);
  }
}

export function normalizeVerifierCostState(state                                             )                    {
  const raw = state                           ;
  const committedDomains = raw.committedDomains ?? raw.committed_domains ?? [];
  if (!Array.isArray(committedDomains)) {
    throw new RangeError("committedDomains must be an array");
  }
  return { committedDomains: committedDomains.map((domain) => String(domain)) };
}

export function makeVerifierCostCandidate(domainId        )                                      {
  return makeCandidate(
    { context: VERIFIER_COST_CONTEXT, action: domainId, domainId },
    "verifier_cost.probe",
    "verifier_cost.probe.v1",
  );
}

export function makeVerifierCostTrace(domainId        )                {
  return makeTrace({
    branchId: `verifier-cost-${domainId}`,
    actions: [{ context: VERIFIER_COST_CONTEXT, action: domainId }],
    seeds: ["verifier_cost", domainId],
    modelVersion: "verifier.cost.v1",
  });
}

export async function runVerifierCostBenchmark()                              {
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

async function runSubstrate(substrate                       , expensiveCost        , cheapCost        )                                 {
  for (const [domainId, verifierCost] of [
    [EXPENSIVE_VERIFIER_DOMAIN, expensiveCost],
    [CHEAP_VERIFIER_DOMAIN, cheapCost],
  ]         ) {
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

async function allAuditsOk(substrate                       , domainIds          )                   {
  const audits = await Promise.all(domainIds.map((domainId) => substrate.auditDomain(domainId, { committedDomains: [] })));
  return audits.every((audit) => audit.ok);
}

async function replayRollbackRate(substrate                       , domainIds          )                  {
  const audits = await Promise.all(domainIds.map((domainId) => substrate.auditDomain(domainId, { committedDomains: [] })));
  return audits.every((audit) => audit.ledgerAudit && audit.replayMatchesReceipts && audit.rollbackMatchesSeed) ? 1 : 0;
}

function normalizeVerifierCostPayload(payload                                               )                      {
  const raw = payload                           ;
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
