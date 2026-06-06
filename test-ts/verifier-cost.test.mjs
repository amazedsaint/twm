import assert from "node:assert/strict";
import test from "node:test";

import {
  CHEAP_VERIFIER_DOMAIN,
  CostAwareReceiptDomainRouter,
  EXPENSIVE_VERIFIER_DOMAIN,
  ProgrammableSubstrate,
  VERIFIER_COST_CONTEXT,
  VerifierCostAdapter,
  makeVerifierCostCandidate,
  makeVerifierCostTrace,
  runVerifierCostBenchmark,
} from "../dist/index.js";

test("cost-aware router prefers success per verifier cost", async () => {
  const router = new CostAwareReceiptDomainRouter();
  const substrate = new ProgrammableSubstrate(router);
  for (const [domainId, cost] of [[EXPENSIVE_VERIFIER_DOMAIN, 12], [CHEAP_VERIFIER_DOMAIN, 3]]) {
    substrate.register(domainId, new VerifierCostAdapter(domainId, cost));
    await substrate.submit(
      domainId,
      { committedDomains: [] },
      makeVerifierCostTrace(domainId),
      makeVerifierCostCandidate(domainId),
      { context: VERIFIER_COST_CONTEXT },
    );
  }

  assert.equal(substrate.rankDomains(VERIFIER_COST_CONTEXT, [EXPENSIVE_VERIFIER_DOMAIN, CHEAP_VERIFIER_DOMAIN])[0], CHEAP_VERIFIER_DOMAIN);
  assert.equal(router.stats(VERIFIER_COST_CONTEXT, EXPENSIVE_VERIFIER_DOMAIN).successPerCostNumerator, 1);
  assert.equal(router.stats(VERIFIER_COST_CONTEXT, EXPENSIVE_VERIFIER_DOMAIN).successPerCostDenominator, 12);
  assert.equal(router.stats(VERIFIER_COST_CONTEXT, CHEAP_VERIFIER_DOMAIN).successPerCostNumerator, 1);
  assert.equal(router.stats(VERIFIER_COST_CONTEXT, CHEAP_VERIFIER_DOMAIN).successPerCostDenominator, 3);
});

test("uniform router ties on accepted count", async () => {
  const substrate = new ProgrammableSubstrate();
  for (const [domainId, cost] of [[EXPENSIVE_VERIFIER_DOMAIN, 12], [CHEAP_VERIFIER_DOMAIN, 3]]) {
    substrate.register(domainId, new VerifierCostAdapter(domainId, cost));
    await substrate.submit(
      domainId,
      { committedDomains: [] },
      makeVerifierCostTrace(domainId),
      makeVerifierCostCandidate(domainId),
      { context: VERIFIER_COST_CONTEXT },
    );
  }

  assert.equal(substrate.rankDomains(VERIFIER_COST_CONTEXT, [EXPENSIVE_VERIFIER_DOMAIN, CHEAP_VERIFIER_DOMAIN])[0], EXPENSIVE_VERIFIER_DOMAIN);
});

test("invalid cost metadata falls back to nonzero default", async () => {
  const router = new CostAwareReceiptDomainRouter(5);
  const substrate = new ProgrammableSubstrate(router);
  substrate.register(EXPENSIVE_VERIFIER_DOMAIN, new VerifierCostAdapter(EXPENSIVE_VERIFIER_DOMAIN, 1));
  const result = await substrate.submit(
    EXPENSIVE_VERIFIER_DOMAIN,
    { committedDomains: [] },
    makeVerifierCostTrace(EXPENSIVE_VERIFIER_DOMAIN),
    makeVerifierCostCandidate(EXPENSIVE_VERIFIER_DOMAIN),
    { context: VERIFIER_COST_CONTEXT },
  );
  const tampered = {
    ...result.receipt,
    hardResult: { ...result.receipt.hardResult, metadata: { verifierCost: 0 } },
  };
  router.update(CHEAP_VERIFIER_DOMAIN, VERIFIER_COST_CONTEXT, tampered);

  assert.equal(router.stats(VERIFIER_COST_CONTEXT, CHEAP_VERIFIER_DOMAIN).verifierCost, 5);
  assert.equal(router.invalidCostMetadata.get(VERIFIER_COST_CONTEXT).get(CHEAP_VERIFIER_DOMAIN), 1);
});

test("verifier cost benchmark metrics", async () => {
  const report = await runVerifierCostBenchmark();

  assert.equal(report.domainCount, 2);
  assert.equal(report.uniformRouterTopDomain, EXPENSIVE_VERIFIER_DOMAIN);
  assert.equal(report.costAwareTopDomain, CHEAP_VERIFIER_DOMAIN);
  assert.equal(report.expensiveSuccessPerCostNumerator, 1);
  assert.equal(report.expensiveSuccessPerCostDenominator, 12);
  assert.equal(report.cheapSuccessPerCostNumerator, 1);
  assert.equal(report.cheapSuccessPerCostDenominator, 3);
  assert.equal(report.costNormalizedGain, 4);
  assert.equal(report.totalVerifierCost, 15);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
});
