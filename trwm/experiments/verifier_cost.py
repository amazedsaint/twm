from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..core import HardVerifierResult, ProposalTrace, Receipt, TypedCandidate
from ..sdk import CostAwareReceiptDomainRouter, ProgrammableSubstrate


CONTEXT = "verifier-cost-route"
EXPENSIVE_DOMAIN = "expensive_exact"
CHEAP_DOMAIN = "cheap_exact"


@dataclass(frozen=True)
class VerifierCostState:
    committed_domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifierCostReport:
    domain_count: int
    expensive_verifier_cost: int
    cheap_verifier_cost: int
    uniform_router_top_domain: str
    cost_aware_top_domain: str
    expensive_success_per_cost_numerator: int
    expensive_success_per_cost_denominator: int
    cheap_success_per_cost_numerator: int
    cheap_success_per_cost_denominator: int
    cost_normalized_gain: float
    total_verifier_cost: int
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int


class VerifierCostAdapter:
    def __init__(self, domain_id: str, verifier_cost: int):
        if verifier_cost <= 0:
            raise ValueError("verifier_cost must be positive")
        self.domain_id = domain_id
        self.verifier_cost = int(verifier_cost)
        self.verifier_id = f"{domain_id}_oracle"
        self.verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        if payload["domain_id"] != self.domain_id:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "wrong_domain", "expected": self.domain_id, "actual": payload["domain_id"]},
                metadata={"verifier_cost": self.verifier_cost, "domain": self.domain_id},
            )
        return HardVerifierResult.accept(
            self.verifier_id,
            self.verifier_version,
            metadata={"verifier_cost": self.verifier_cost, "domain": self.domain_id, "reward": 1},
        )

    def apply_commit(self, state: VerifierCostState, candidate: TypedCandidate) -> VerifierCostState:
        current = normalize_verifier_cost_state(state)
        payload = _normalize_payload(candidate.payload)
        return VerifierCostState(committed_domains=(*current.committed_domains, payload["domain_id"]))

    def replay(self, state: VerifierCostState, receipt: Receipt) -> VerifierCostState:
        current = normalize_verifier_cost_state(state)
        payload = _normalize_payload(receipt.replay_bundle["candidate_payload"])
        return VerifierCostState(committed_domains=(*current.committed_domains, payload["domain_id"]))

    def rollback(self, state: VerifierCostState, receipt: Receipt) -> VerifierCostState:
        return normalize_verifier_cost_state(receipt.rollback_bundle["pre_state"])


def normalize_verifier_cost_state(state: VerifierCostState | Mapping[str, Any]) -> VerifierCostState:
    if isinstance(state, VerifierCostState):
        return VerifierCostState(committed_domains=tuple(str(domain) for domain in state.committed_domains))
    return VerifierCostState(committed_domains=tuple(str(domain) for domain in state.get("committed_domains", ())))


def make_verifier_cost_candidate(domain_id: str) -> TypedCandidate:
    return TypedCandidate(
        payload={"context": CONTEXT, "action": domain_id, "domain_id": domain_id},
        type_name="verifier_cost.probe",
        schema_version="verifier_cost.probe.v1",
    )


def make_verifier_cost_trace(domain_id: str) -> ProposalTrace:
    return ProposalTrace(
        branch_id=f"verifier-cost-{domain_id}",
        actions=({"context": CONTEXT, "action": domain_id},),
        seeds=("verifier_cost", domain_id),
        model_version="verifier.cost.v1",
    )


def run_verifier_cost_benchmark() -> VerifierCostReport:
    expensive_cost = 12
    cheap_cost = 3
    domain_order = (EXPENSIVE_DOMAIN, CHEAP_DOMAIN)
    uniform = _run_substrate(ProgrammableSubstrate(), expensive_cost, cheap_cost)
    cost_aware_router = CostAwareReceiptDomainRouter()
    cost_aware = _run_substrate(ProgrammableSubstrate(router=cost_aware_router), expensive_cost, cheap_cost)
    expensive_stats = cost_aware_router.stats(CONTEXT, EXPENSIVE_DOMAIN)
    cheap_stats = cost_aware_router.stats(CONTEXT, CHEAP_DOMAIN)
    expensive_ratio = expensive_stats.success_per_cost
    cheap_ratio = cheap_stats.success_per_cost
    return VerifierCostReport(
        domain_count=len(domain_order),
        expensive_verifier_cost=expensive_cost,
        cheap_verifier_cost=cheap_cost,
        uniform_router_top_domain=uniform.rank_domains(CONTEXT, domain_order)[0],
        cost_aware_top_domain=cost_aware.rank_domains(CONTEXT, domain_order)[0],
        expensive_success_per_cost_numerator=expensive_ratio.numerator,
        expensive_success_per_cost_denominator=expensive_ratio.denominator,
        cheap_success_per_cost_numerator=cheap_ratio.numerator,
        cheap_success_per_cost_denominator=cheap_ratio.denominator,
        cost_normalized_gain=float(cheap_ratio / expensive_ratio),
        total_verifier_cost=expensive_stats.verifier_cost + cheap_stats.verifier_cost,
        ledger_audit=all(cost_aware.audit_domain(domain_id, VerifierCostState()).ok for domain_id in domain_order),
        replay_rollback_rate=_replay_rollback_rate(cost_aware, domain_order),
        invalid_commit_count=cost_aware.invalid_commit_count(domain_order),
    )


def _run_substrate(substrate: ProgrammableSubstrate, expensive_cost: int, cheap_cost: int) -> ProgrammableSubstrate:
    for domain_id, cost in ((EXPENSIVE_DOMAIN, expensive_cost), (CHEAP_DOMAIN, cheap_cost)):
        substrate.register(domain_id, VerifierCostAdapter(domain_id, cost))
        substrate.submit(
            domain_id,
            VerifierCostState(),
            make_verifier_cost_trace(domain_id),
            make_verifier_cost_candidate(domain_id),
            context=CONTEXT,
        )
    return substrate


def _replay_rollback_rate(substrate: ProgrammableSubstrate, domain_ids: tuple[str, ...]) -> float:
    audits = [substrate.audit_domain(domain_id, VerifierCostState()) for domain_id in domain_ids]
    return 1.0 if all(audit.ledger_audit and audit.replay_matches_receipts and audit.rollback_matches_seed for audit in audits) else 0.0


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    domain_id = str(payload["domain_id"])
    if not domain_id:
        raise ValueError("domain_id must be non-empty")
    return {
        "context": str(payload.get("context", CONTEXT)),
        "action": str(payload.get("action", domain_id)),
        "domain_id": domain_id,
    }
