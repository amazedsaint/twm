from __future__ import annotations

import unittest

from trwm.experiments.verifier_cost import (
    CHEAP_DOMAIN,
    CONTEXT,
    EXPENSIVE_DOMAIN,
    VerifierCostAdapter,
    VerifierCostState,
    make_verifier_cost_candidate,
    make_verifier_cost_trace,
    run_verifier_cost_benchmark,
)
from trwm.sdk import CostAwareReceiptDomainRouter, ProgrammableSubstrate, verifier_cost_units


class VerifierCostTests(unittest.TestCase):
    def test_cost_aware_router_prefers_success_per_cost(self) -> None:
        router = CostAwareReceiptDomainRouter()
        substrate = ProgrammableSubstrate(router=router)
        for domain_id, cost in ((EXPENSIVE_DOMAIN, 12), (CHEAP_DOMAIN, 3)):
            substrate.register(domain_id, VerifierCostAdapter(domain_id, cost))
            substrate.submit(domain_id, VerifierCostState(), make_verifier_cost_trace(domain_id), make_verifier_cost_candidate(domain_id), context=CONTEXT)

        self.assertEqual(substrate.rank_domains(CONTEXT, (EXPENSIVE_DOMAIN, CHEAP_DOMAIN))[0], CHEAP_DOMAIN)
        self.assertEqual(router.stats(CONTEXT, EXPENSIVE_DOMAIN).success_per_cost.numerator, 1)
        self.assertEqual(router.stats(CONTEXT, EXPENSIVE_DOMAIN).success_per_cost.denominator, 12)
        self.assertEqual(router.stats(CONTEXT, CHEAP_DOMAIN).success_per_cost.numerator, 1)
        self.assertEqual(router.stats(CONTEXT, CHEAP_DOMAIN).success_per_cost.denominator, 3)

    def test_uniform_router_ties_on_success_count(self) -> None:
        substrate = ProgrammableSubstrate()
        for domain_id, cost in ((EXPENSIVE_DOMAIN, 12), (CHEAP_DOMAIN, 3)):
            substrate.register(domain_id, VerifierCostAdapter(domain_id, cost))
            substrate.submit(domain_id, VerifierCostState(), make_verifier_cost_trace(domain_id), make_verifier_cost_candidate(domain_id), context=CONTEXT)

        self.assertEqual(substrate.rank_domains(CONTEXT, (EXPENSIVE_DOMAIN, CHEAP_DOMAIN))[0], EXPENSIVE_DOMAIN)

    def test_invalid_cost_metadata_is_not_free(self) -> None:
        substrate = ProgrammableSubstrate(router=CostAwareReceiptDomainRouter(default_verifier_cost=5))
        substrate.register(EXPENSIVE_DOMAIN, VerifierCostAdapter(EXPENSIVE_DOMAIN, 1))
        result = substrate.submit(
            EXPENSIVE_DOMAIN,
            VerifierCostState(),
            make_verifier_cost_trace(EXPENSIVE_DOMAIN),
            make_verifier_cost_candidate(EXPENSIVE_DOMAIN),
            context=CONTEXT,
        )
        tampered = result.receipt.hard_result.__class__.accept(
            result.receipt.hard_result.verifier_id,
            result.receipt.hard_result.verifier_version,
            metadata={"verifier_cost": 0},
        )
        receipt = result.receipt.__class__(
            **{
                **result.receipt.without_hash(),
                "hard_result": tampered,
                "receipt_hash": "",
            }
        )
        cost, ok = verifier_cost_units(receipt, default=5)

        self.assertEqual(cost, 5)
        self.assertFalse(ok)

    def test_verifier_cost_benchmark_metrics(self) -> None:
        report = run_verifier_cost_benchmark()

        self.assertEqual(report.domain_count, 2)
        self.assertEqual(report.uniform_router_top_domain, EXPENSIVE_DOMAIN)
        self.assertEqual(report.cost_aware_top_domain, CHEAP_DOMAIN)
        self.assertEqual(report.expensive_success_per_cost_numerator, 1)
        self.assertEqual(report.expensive_success_per_cost_denominator, 12)
        self.assertEqual(report.cheap_success_per_cost_numerator, 1)
        self.assertEqual(report.cheap_success_per_cost_denominator, 3)
        self.assertEqual(report.cost_normalized_gain, 4.0)
        self.assertEqual(report.total_verifier_cost, 15)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertEqual(report.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
