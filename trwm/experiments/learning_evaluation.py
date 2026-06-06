from __future__ import annotations

from dataclasses import dataclass, replace

from ..budget_policy import BudgetCandidate, ReceiptBudgetPolicy
from ..core import ProposalTrace, Receipt, TransactionEngine
from ..evaluation import (
    LEARNING_EVALUATION_CERTIFICATE_SCHEMA,
    LearningEvaluationCertificate,
    build_learning_evaluation_certificate,
    learning_evaluation_supports_claim,
    validate_learning_evaluation_certificate,
)
from .budget_policy import BUDGET_POLICY_LIMIT, BUDGET_POLICY_ORDER
from .operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate


@dataclass(frozen=True)
class LearningEvaluationReport:
    schema_version: str
    certificate_valid: bool
    certificate_supports_claim: bool
    claim_id: str
    training_receipt_count: int
    evaluation_receipt_count: int
    train_eval_disjoint: bool
    same_case_baseline: bool
    baseline_name: str
    learned_name: str
    baseline_success_count: int
    learned_success_count: int
    baseline_verifier_calls: int
    learned_verifier_calls: int
    verifier_budget: int
    candidate_count: int
    verifier_call_gain_numerator: int
    verifier_call_gain_denominator: int
    hard_commit_only: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float
    learner_snapshot_hash: str
    certificate_hash: str
    tamper_detected: bool
    overlap_detected: bool


def run_learning_evaluation_benchmark() -> LearningEvaluationReport:
    state = InventoryState(stock={"widget": 5}, reserved={"widget": 0})
    policy = ReceiptBudgetPolicy()
    training_engine = TransactionEngine(InventoryReservationAdapter())
    training_receipts: list[Receipt] = []
    for label, quantity in (("quantity-5", 5), ("quantity-8", 8), ("quantity-7", 7)):
        receipt = training_engine.transact(
            state,
            ProposalTrace(branch_id=f"learning-eval-train-{label}", actions=({"label": label},)),
            make_reservation_candidate(state, f"learning-train-{label}", "widget", 8, quantity, context="learning-eval-train"),
        ).receipt
        policy.update(label, receipt)
        training_receipts.append(receipt)

    candidates = _learning_eval_candidates(state)
    baseline_engine = TransactionEngine(InventoryReservationAdapter())
    baseline = _cheap_first_submit(baseline_engine, state, candidates, BUDGET_POLICY_LIMIT)
    learned_engine = TransactionEngine(InventoryReservationAdapter())
    learned = policy.submit(learned_engine, state, candidates, budget=BUDGET_POLICY_LIMIT, trace_prefix="learning-eval-learned")
    snapshot = policy.snapshot()

    ledger_audit = training_engine.ledger.audit() and baseline_engine.ledger.audit() and learned_engine.ledger.audit()
    replay_rollback_rate = _replay_rollback_rate(
        (
            (training_engine, state),
            (baseline_engine, state),
            (learned_engine, state),
        )
    )
    certificate = build_learning_evaluation_certificate(
        claim_id="budget_policy_trace_disjoint_eval",
        learner_id="receipt_budget_policy",
        learner_snapshot_hash=snapshot.snapshot_hash,
        training_receipt_hashes=tuple(receipt.receipt_hash for receipt in training_receipts),
        evaluation_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned.receipts),
        baseline_name="cheap_first_same_budget",
        learned_name="receipt_budget_policy",
        baseline_verifier_calls=len(baseline.receipts),
        learned_verifier_calls=len(learned.receipts),
        baseline_success_count=1 if baseline.committed else 0,
        learned_success_count=1 if learned.committed else 0,
        verifier_budget=BUDGET_POLICY_LIMIT,
        candidate_count=len(candidates),
        same_case_baseline=True,
        hard_commit_only=all(receipt.committed == receipt.hard_result.accepted for receipt in learned.receipts),
        invalid_commit_count=training_engine.invalid_commit_count + baseline_engine.invalid_commit_count + learned_engine.invalid_commit_count,
        ledger_audit=ledger_audit,
        replay_rollback_rate=replay_rollback_rate,
        metrics={
            "baseline_selected": baseline.submitted_labels,
            "learned_selected": learned.selected_labels,
            "baseline_cost_spent": baseline.verifier_cost_spent,
            "learned_cost_spent": learned.verifier_cost_spent,
        },
    )
    tampered = replace(certificate, metrics={**certificate.metrics, "learned_verifier_calls": 99})
    overlapping = build_learning_evaluation_certificate(
        claim_id=certificate.claim_id,
        learner_id=certificate.learner_id,
        learner_snapshot_hash=certificate.learner_snapshot_hash,
        training_receipt_hashes=certificate.training_receipt_hashes,
        evaluation_receipt_hashes=(certificate.training_receipt_hashes[0],),
        baseline_name=certificate.baseline_name,
        learned_name=certificate.learned_name,
        baseline_verifier_calls=certificate.baseline_verifier_calls,
        learned_verifier_calls=1,
        baseline_success_count=certificate.baseline_success_count,
        learned_success_count=certificate.learned_success_count,
        verifier_budget=certificate.verifier_budget,
        candidate_count=certificate.candidate_count,
        same_case_baseline=certificate.same_case_baseline,
        hard_commit_only=certificate.hard_commit_only,
        invalid_commit_count=certificate.invalid_commit_count,
        ledger_audit=certificate.ledger_audit,
        replay_rollback_rate=certificate.replay_rollback_rate,
        metrics=certificate.metrics,
    )

    return LearningEvaluationReport(
        schema_version=LEARNING_EVALUATION_CERTIFICATE_SCHEMA,
        certificate_valid=validate_learning_evaluation_certificate(certificate),
        certificate_supports_claim=learning_evaluation_supports_claim(certificate),
        claim_id=certificate.claim_id,
        training_receipt_count=len(certificate.training_receipt_hashes),
        evaluation_receipt_count=len(certificate.evaluation_receipt_hashes),
        train_eval_disjoint=certificate.train_eval_disjoint,
        same_case_baseline=certificate.same_case_baseline,
        baseline_name=certificate.baseline_name,
        learned_name=certificate.learned_name,
        baseline_success_count=certificate.baseline_success_count,
        learned_success_count=certificate.learned_success_count,
        baseline_verifier_calls=certificate.baseline_verifier_calls,
        learned_verifier_calls=certificate.learned_verifier_calls,
        verifier_budget=certificate.verifier_budget,
        candidate_count=certificate.candidate_count,
        verifier_call_gain_numerator=certificate.verifier_call_gain_numerator,
        verifier_call_gain_denominator=certificate.verifier_call_gain_denominator,
        hard_commit_only=certificate.hard_commit_only,
        invalid_commit_count=certificate.invalid_commit_count,
        ledger_audit=certificate.ledger_audit,
        replay_rollback_rate=certificate.replay_rollback_rate,
        learner_snapshot_hash=certificate.learner_snapshot_hash,
        certificate_hash=certificate.certificate_hash,
        tamper_detected=not validate_learning_evaluation_certificate(tampered),
        overlap_detected=not validate_learning_evaluation_certificate(overlapping),
    )


@dataclass(frozen=True)
class _BaselineOutcome:
    committed: bool
    submitted_labels: tuple[str, ...]
    verifier_cost_spent: int
    receipts: tuple[Receipt, ...]


def _learning_eval_candidates(state: InventoryState) -> tuple[BudgetCandidate, ...]:
    cost_by_quantity = {8: 1, 7: 1, 5: 3, 4: 2}
    return tuple(
        BudgetCandidate(
            label=f"quantity-{quantity}",
            token=f"quantity-{quantity}",
            candidate=make_reservation_candidate(
                state,
                f"learning-eval-q{quantity}",
                "widget",
                8,
                quantity,
                context="learning-eval",
                cost=cost_by_quantity[quantity],
            ),
            verifier_cost=cost_by_quantity[quantity],
            reward=float(quantity),
            base_rank=idx,
        )
        for idx, quantity in enumerate(BUDGET_POLICY_ORDER)
    )


def _cheap_first_submit(engine: TransactionEngine, state: InventoryState, candidates: tuple[BudgetCandidate, ...], budget: int) -> _BaselineOutcome:
    spent = 0
    submitted: list[str] = []
    receipts: list[Receipt] = []
    for idx, row in enumerate(sorted(candidates, key=lambda item: (item.verifier_cost, item.base_rank, item.label))):
        if spent + row.verifier_cost > budget:
            continue
        outcome = engine.transact(
            state,
            ProposalTrace(branch_id=f"learning-eval-baseline-{idx}-{row.label}", actions=({"label": row.label},)),
            row.candidate,
        )
        receipts.append(outcome.receipt)
        submitted.append(row.label)
        spent += row.verifier_cost
        if outcome.committed:
            return _BaselineOutcome(True, tuple(submitted), spent, tuple(receipts))
    return _BaselineOutcome(False, tuple(submitted), spent, tuple(receipts))


def _replay_rollback_rate(rows: tuple[tuple[TransactionEngine, InventoryState], ...]) -> float:
    ok = 0
    for engine, state in rows:
        try:
            if engine.ledger.audit() and engine.rollback_audit(state) == state:
                engine.replay_audit(state)
                ok += 1
        except Exception:
            pass
    return ok / len(rows)
