from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from ..branch import BudgetedBranchRuntime, VerifierBudget
from ..core import ProposalTrace, Receipt, TransactionEngine
from ..experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate
from ..experiments.projection_contract import (
    ProjectionGuardAdapter,
    ProjectionGuardState,
    ProjectionContractProjector,
    make_projection_contract_traces,
)
from ..experiments.verifier_budget import BUDGET_LIMIT, VerifierBudgetAdapter, VerifierBudgetProjector, make_verifier_budget_traces
from ..residuals import (
    RESIDUAL_SCHEMA,
    ResidualSignal,
    ResidualTaxonomyMemory,
    normalize_residual,
    residual_learning_hash,
    residual_signal_from_receipt,
    validate_residual_signal,
)


@dataclass(frozen=True)
class ResidualTaxonomyReport:
    signal_count: int
    schema_version: str
    categories: Mapping[str, int]
    kind_order: tuple[str, ...]
    resource_kind: str
    coverage_kind: str
    budget_kind: str
    resource_category: str
    coverage_category: str
    budget_category: str
    stock_shortage_fields: tuple[str, ...]
    projection_missing_fields: tuple[str, ...]
    budget_fields: tuple[str, ...]
    top_stock_shortage_repair_hint: str
    snake_camel_learning_hash_equal: bool
    raw_residual_hash_distinct: bool
    tamper_detected: bool
    ledger_audit: bool
    invalid_commit_count: int


def run_residual_taxonomy_benchmark() -> ResidualTaxonomyReport:
    stock_receipt, stock_audit, stock_invalid = _stock_shortage_receipt()
    projection_receipt, projection_audit, projection_invalid = _projection_receipt()
    budget_receipt, budget_audit, budget_invalid = _budget_abstain_receipt()

    signals = (
        residual_signal_from_receipt(stock_receipt, source_domain="operations"),
        residual_signal_from_receipt(projection_receipt, source_domain="projection_contract"),
        residual_signal_from_receipt(budget_receipt, source_domain="verifier_budget"),
    )
    memory = ResidualTaxonomyMemory()
    for signal in signals:
        memory.update(signal)

    snake = normalize_residual(
        {"kind": "stock_shortage", "sku": "widget", "repair": {"quantity": 2}},
        status="reject",
        verifier_id="inventory_reservation_verifier",
        verifier_version="1.0",
    )
    camel = normalize_residual(
        {"kind": "stockShortage", "sku": "widget", "repair": {"quantity": 2}},
        status="reject",
        verifier_id="inventory_reservation_verifier",
        verifier_version="1.0",
    )
    tampered = replace(signals[0], category="unknown")

    return ResidualTaxonomyReport(
        signal_count=len(signals),
        schema_version=RESIDUAL_SCHEMA,
        categories=dict(memory.category_counts),
        kind_order=memory.rank_kinds(),
        resource_kind=signals[0].kind,
        coverage_kind=signals[1].kind,
        budget_kind=signals[2].kind,
        resource_category=signals[0].category,
        coverage_category=signals[1].category,
        budget_category=signals[2].category,
        stock_shortage_fields=signals[0].fields,
        projection_missing_fields=signals[1].fields,
        budget_fields=signals[2].fields,
        top_stock_shortage_repair_hint=memory.top_repair_hint("stock_shortage") or "",
        snake_camel_learning_hash_equal=residual_learning_hash(snake) == residual_learning_hash(camel),
        raw_residual_hash_distinct=snake.residual_hash != camel.residual_hash,
        tamper_detected=not validate_residual_signal(tampered),
        ledger_audit=stock_audit and projection_audit and budget_audit,
        invalid_commit_count=stock_invalid + projection_invalid + budget_invalid,
    )


def _stock_shortage_receipt() -> tuple[Receipt, bool, int]:
    state = InventoryState(stock={"widget": 2}, reserved={})
    candidate = make_reservation_candidate(state, "order-1", "widget", requested=5, quantity=5)
    engine = TransactionEngine(InventoryReservationAdapter())
    outcome = engine.transact(
        state,
        ProposalTrace(
            branch_id="residual-taxonomy-stock-shortage",
            actions=({"sku": "widget", "quantity": 5},),
            seeds=("residual_taxonomy", "stock_shortage"),
            model_version="residual.taxonomy.v1",
        ),
        candidate,
    )
    return outcome.receipt, engine.ledger.audit(), engine.invalid_commit_count


def _projection_receipt() -> tuple[Receipt, bool, int]:
    state = ProjectionGuardState()
    trace = make_projection_contract_traces()[0]
    candidate = ProjectionContractProjector().project(state, trace)
    engine = TransactionEngine(ProjectionGuardAdapter(state))
    outcome = engine.transact(state, trace, candidate)
    return outcome.receipt, engine.ledger.audit(), engine.invalid_commit_count


def _budget_abstain_receipt() -> tuple[Receipt, bool, int]:
    engine = TransactionEngine(VerifierBudgetAdapter())
    outcome = BudgetedBranchRuntime(
        engine,
        VerifierBudgetProjector(),
        VerifierBudget(BUDGET_LIMIT),
    ).step({}, make_verifier_budget_traces())
    return outcome.receipts[0], engine.ledger.audit(), engine.invalid_commit_count
