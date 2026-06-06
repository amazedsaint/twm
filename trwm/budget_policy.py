from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable

from .core import ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash
from .reliability import wilson_lower_bound


BUDGET_POLICY_SNAPSHOT_SCHEMA = "trwm.budget_policy_snapshot.v1"


@dataclass(frozen=True)
class BudgetPolicyRow:
    token: str
    successes: int = 0
    failures: int = 0
    observations: int = 0
    success_lower_bound: float = 0.0


@dataclass(frozen=True)
class BudgetCandidate:
    label: str
    token: str
    candidate: TypedCandidate
    verifier_cost: int
    reward: float = 1.0
    base_rank: int = 0

    def __post_init__(self) -> None:
        if not self.label:
            raise ValueError("label must be non-empty")
        if not self.token:
            raise ValueError("token must be non-empty")
        if not isinstance(self.verifier_cost, int) or isinstance(self.verifier_cost, bool) or self.verifier_cost <= 0:
            raise ValueError("verifier_cost must be a positive integer")
        if self.reward < 0:
            raise ValueError("reward must be non-negative")


@dataclass(frozen=True)
class BudgetPlan:
    budget: int
    selected: tuple[BudgetCandidate, ...]
    spent: int
    expected_utility: float


@dataclass(frozen=True)
class BudgetPolicyOutcome:
    state: Any
    committed: bool
    committed_label: str
    selected_labels: tuple[str, ...]
    submitted_labels: tuple[str, ...]
    verifier_cost_spent: int
    receipts: tuple[Receipt, ...]
    reason: str


@dataclass(frozen=True)
class BudgetPolicySnapshot:
    schema_version: str
    rows: tuple[BudgetPolicyRow, ...]
    z: float = 1.96
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != BUDGET_POLICY_SNAPSHOT_SCHEMA:
            raise ValueError(f"invalid budget policy snapshot schema: {self.schema_version}")
        object.__setattr__(self, "rows", tuple(sorted(self.rows, key=lambda row: row.token)))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", budget_policy_snapshot_hash(self))


class ReceiptBudgetPolicy:
    def __init__(self, *, z: float = 1.96) -> None:
        if z <= 0:
            raise ValueError("z must be positive")
        self.z = float(z)
        self._rows: dict[str, BudgetPolicyRow] = {}

    def update(self, token: str, receipt: Receipt) -> BudgetPolicyRow:
        subject = str(token)
        if not subject:
            raise ValueError("token must be non-empty")
        row = self._rows.get(subject, BudgetPolicyRow(token=subject))
        if receipt.committed and receipt.hard_result.accepted:
            row = replace(row, successes=row.successes + 1, observations=row.observations + 1)
        elif receipt.hard_result.rejected or receipt.commit_decision != "commit":
            row = replace(row, failures=row.failures + 1, observations=row.observations + 1)
        else:
            row = replace(row, observations=row.observations + 1)
        row = self._scored(row)
        self._rows[subject] = row
        return row

    def score(self, token: str) -> BudgetPolicyRow:
        subject = str(token)
        return self._rows.get(subject, self._scored(BudgetPolicyRow(token=subject)))

    def utility(self, candidate: BudgetCandidate) -> float:
        row = self.score(candidate.token)
        return round(float(candidate.reward) * row.success_lower_bound, 12)

    def plan(self, candidates: Iterable[BudgetCandidate], budget: int) -> BudgetPlan:
        if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
            raise ValueError("budget must be a non-negative integer")
        rows = tuple(candidates)
        cells: list[tuple[float, tuple[BudgetCandidate, ...]] | None] = [None] * (budget + 1)
        cells[0] = (0.0, ())
        for row in rows:
            row_utility = self.utility(row)
            for spent_before in range(budget - row.verifier_cost, -1, -1):
                current = cells[spent_before]
                if current is None:
                    continue
                next_spent = spent_before + row.verifier_cost
                candidate_utility = round(current[0] + row_utility, 12)
                candidate_subset = (*current[1], row)
                existing = cells[next_spent]
                if existing is None or self._better(candidate_subset, candidate_utility, next_spent, existing[1], existing[0], next_spent):
                    cells[next_spent] = (candidate_utility, candidate_subset)

        best_subset: tuple[BudgetCandidate, ...] = ()
        best_utility = 0.0
        best_spent = 0
        for spent, cell in enumerate(cells):
            if cell is None:
                continue
            utility, subset = cell
            if self._better(subset, utility, spent, best_subset, best_utility, best_spent):
                best_subset = subset
                best_utility = utility
                best_spent = spent
        selected = tuple(sorted(best_subset, key=lambda row: (row.base_rank, row.label)))
        return BudgetPlan(budget=budget, selected=selected, spent=best_spent, expected_utility=best_utility)

    def submit(
        self,
        engine: TransactionEngine,
        state: Any,
        candidates: Iterable[BudgetCandidate],
        *,
        budget: int,
        trace_prefix: str,
        model_version: str = "budget.policy.v1",
    ) -> BudgetPolicyOutcome:
        plan = self.plan(candidates, budget)
        receipts: list[Receipt] = []
        submitted: list[str] = []
        spent = 0
        current = state
        for idx, row in enumerate(plan.selected):
            if spent + row.verifier_cost > budget:
                break
            outcome = engine.transact(
                state,
                ProposalTrace(
                    branch_id=f"{trace_prefix}-{idx}-{row.label}",
                    actions=({"label": row.label, "token": row.token, "verifier_cost": row.verifier_cost},),
                    model_version=model_version,
                ),
                row.candidate,
            )
            receipts.append(outcome.receipt)
            submitted.append(row.label)
            spent += row.verifier_cost
            if outcome.committed:
                current = outcome.state
                return BudgetPolicyOutcome(
                    state=current,
                    committed=True,
                    committed_label=row.label,
                    selected_labels=tuple(item.label for item in plan.selected),
                    submitted_labels=tuple(submitted),
                    verifier_cost_spent=spent,
                    receipts=tuple(receipts),
                    reason="commit",
                )
        return BudgetPolicyOutcome(
            state=current,
            committed=False,
            committed_label="",
            selected_labels=tuple(item.label for item in plan.selected),
            submitted_labels=tuple(submitted),
            verifier_cost_spent=spent,
            receipts=tuple(receipts),
            reason="budget_exhausted",
        )

    def snapshot(self) -> BudgetPolicySnapshot:
        return BudgetPolicySnapshot(schema_version=BUDGET_POLICY_SNAPSHOT_SCHEMA, rows=tuple(self._rows.values()), z=self.z)

    def _scored(self, row: BudgetPolicyRow) -> BudgetPolicyRow:
        lower = wilson_lower_bound(row.successes, row.failures, z=self.z)
        return replace(row, success_lower_bound=round(lower, 12))

    def _better(
        self,
        subset: tuple[BudgetCandidate, ...],
        utility: float,
        spent: int,
        best_subset: tuple[BudgetCandidate, ...],
        best_utility: float,
        best_spent: int,
    ) -> bool:
        if utility != best_utility:
            return utility > best_utility
        if spent != best_spent:
            return spent < best_spent
        return _label_tuple(subset) < _label_tuple(best_subset)


def budget_policy_snapshot_hash(snapshot: BudgetPolicySnapshot) -> str:
    data = asdict(snapshot)
    data.pop("snapshot_hash", None)
    return stable_hash(data)


def validate_budget_policy_snapshot(snapshot: BudgetPolicySnapshot) -> bool:
    if snapshot.schema_version != BUDGET_POLICY_SNAPSHOT_SCHEMA:
        return False
    if snapshot.z <= 0:
        return False
    if len({row.token for row in snapshot.rows}) != len(snapshot.rows):
        return False
    for row in snapshot.rows:
        if not row.token:
            return False
        values = (row.successes, row.failures, row.observations)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
            return False
        if row.observations < row.successes + row.failures:
            return False
        expected = round(wilson_lower_bound(row.successes, row.failures, z=snapshot.z), 12)
        if row.success_lower_bound != expected:
            return False
    return snapshot.snapshot_hash == budget_policy_snapshot_hash(snapshot)


def _label_tuple(rows: tuple[BudgetCandidate, ...]) -> tuple[str, ...]:
    return tuple(sorted((row.label for row in rows)))
