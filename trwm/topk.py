from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .core import ProposalTrace, Receipt, TransactionEngine, TypedCandidate
from .residuals import ResidualSignal, ResidualTaxonomyMemory


@dataclass(frozen=True)
class ResidualRepairOption:
    label: str
    candidate: TypedCandidate
    repair_hint: str = ""
    base_rank: int = 0


@dataclass(frozen=True)
class ResidualTopKOutcome:
    state: Any
    committed: bool
    committed_label: str
    submitted_labels: tuple[str, ...]
    receipts: tuple[Receipt, ...]
    verifier_calls: int
    reason: str


class ResidualTopKSubmitter:
    """Rank and submit bounded repair candidates; hard verifiers still own commits."""

    def __init__(self, engine: TransactionEngine, memory: ResidualTaxonomyMemory | None = None):
        self.engine = engine
        self.memory = memory or ResidualTaxonomyMemory()

    def rank_options(
        self,
        options: Iterable[ResidualRepairOption],
        *,
        residual_signal: ResidualSignal | None = None,
    ) -> tuple[ResidualRepairOption, ...]:
        rows = tuple(options)
        preferred = self._preferred_hints(residual_signal)
        return tuple(
            sorted(
                rows,
                key=lambda option: (
                    0 if option.repair_hint and option.repair_hint in preferred else 1,
                    option.base_rank,
                    option.label,
                ),
            )
        )

    def submit(
        self,
        state: Any,
        options: Iterable[ResidualRepairOption],
        *,
        top_k: int,
        trace_prefix: str,
        residual_signal: ResidualSignal | None = None,
        model_version: str = "residual.topk.v1",
    ) -> ResidualTopKOutcome:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 0:
            raise ValueError("top_k must be a non-negative integer")
        ranked = self.rank_options(options, residual_signal=residual_signal)
        receipts: list[Receipt] = []
        submitted: list[str] = []
        current = state
        for idx, option in enumerate(ranked[:top_k]):
            submitted.append(option.label)
            outcome = self.engine.transact(
                state,
                ProposalTrace(
                    branch_id=f"{trace_prefix}-{idx}-{option.label}",
                    actions=({"label": option.label, "repair_hint": option.repair_hint},),
                    model_version=model_version,
                ),
                option.candidate,
            )
            receipts.append(outcome.receipt)
            if outcome.committed:
                current = outcome.state
                return ResidualTopKOutcome(
                    state=current,
                    committed=True,
                    committed_label=option.label,
                    submitted_labels=tuple(submitted),
                    receipts=tuple(receipts),
                    verifier_calls=len(receipts),
                    reason="commit",
                )
        return ResidualTopKOutcome(
            state=current,
            committed=False,
            committed_label="",
            submitted_labels=tuple(submitted),
            receipts=tuple(receipts),
            verifier_calls=len(receipts),
            reason="top_k_exhausted",
        )

    def _preferred_hints(self, residual_signal: ResidualSignal | None) -> set[str]:
        preferred: set[str] = set()
        if residual_signal is not None:
            preferred.update(residual_signal.repair_hints)
            top_hint = self.memory.top_repair_hint(residual_signal.kind)
            if top_hint:
                preferred.add(top_hint)
        return preferred
