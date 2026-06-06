from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol

from .core import HardVerifierResult, ProposalTrace, TransactionEngine, TypedCandidate, canonical_json


@dataclass(frozen=True)
class Macro:
    macro_id: str
    steps: tuple[Any, ...]
    context: str = "global"
    model_version: str = "macro.manual.v1"


@dataclass(frozen=True)
class MacroOutcome:
    state: Any
    committed: bool
    receipt: Any
    reason: str
    prefix_checks: int
    terminal_verifier_calls: int


class PrefixMacroAdapter(Protocol):
    verifier_id: str
    verifier_version: str

    def apply_step(self, state: Any, step: Any) -> Any:
        ...

    def prefix_safe(self, state: Any, step: Any, step_index: int) -> HardVerifierResult:
        ...

    def project_macro(self, pre_state: Any, macro: Macro, final_state: Any) -> TypedCandidate:
        ...


class PrefixSafeMacroRuntime:
    def __init__(self, engine: TransactionEngine, adapter: PrefixMacroAdapter):
        self.engine = engine
        self.adapter = adapter
        self.prefix_checks = 0
        self.prefix_reject_count = 0
        self.terminal_verifier_calls = 0

    def run(self, state: Any, macro: Macro) -> MacroOutcome:
        current = state
        visited = [state]
        prefix_checks = 0
        for idx, step in enumerate(macro.steps):
            next_state = self.adapter.apply_step(current, step)
            prefix_checks += 1
            self.prefix_checks += 1
            result = self.adapter.prefix_safe(next_state, step, idx)
            visited.append(next_state)
            if not result.accepted:
                self.prefix_reject_count += 1
                trace = ProposalTrace(
                    branch_id=f"{macro.macro_id}:prefix:{idx}",
                    actions=tuple(macro.steps[: idx + 1]),
                    latent_states=tuple(visited),
                    model_version=macro.model_version,
                )
                candidate = TypedCandidate(
                    payload={
                        "context": macro.context,
                        "macro_id": macro.macro_id,
                        "macro": macro.steps,
                        "unsafe_prefix": macro.steps[: idx + 1],
                        "step_index": idx,
                        "state": next_state,
                    },
                    type_name="macro.prefix",
                    schema_version="macro.prefix.v1",
                )
                outcome = self.engine.record_evaluated_candidate(
                    state,
                    trace,
                    candidate,
                    result,
                    force_decision="prefix_unsafe",
                )
                return MacroOutcome(state, False, outcome.receipt, outcome.reason, prefix_checks, 0)
            current = next_state

        trace = ProposalTrace(
            branch_id=macro.macro_id,
            actions=macro.steps,
            latent_states=tuple(visited),
            model_version=macro.model_version,
        )
        candidate = self.adapter.project_macro(state, macro, current)
        outcome = self.engine.transact(state, trace, candidate)
        self.terminal_verifier_calls += 1
        return MacroOutcome(outcome.state, outcome.committed, outcome.receipt, outcome.reason, prefix_checks, 1)


class MacroMemory:
    """Receipt-grounded macro ranker. It ranks only; hard verifiers still commit."""

    def __init__(self) -> None:
        self.accepted: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rejected_prefixes: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def update(self, receipt: Any) -> None:
        bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
        payload = bundle.get("candidate_payload", {})
        payload = payload if isinstance(payload, Mapping) else {}
        context = str(payload.get("context", "global"))
        macro_value = payload.get("macro", ())
        token = _token(macro_value)
        if receipt.hard_result.accepted and receipt.committed:
            self.accepted[context][token] += 1
            return
        if receipt.commit_decision == "prefix_unsafe":
            self.rejected_prefixes[context][token] += 1

    def rank(self, context: str, macros: Iterable[Macro]) -> list[Macro]:
        indexed = list(enumerate(macros))

        def key(row: tuple[int, Macro]) -> tuple[int, int, int]:
            idx, macro = row
            token = _token(macro.steps)
            return (-self.accepted[context][token], self.rejected_prefixes[context][token], idx)

        return [macro for _, macro in sorted(indexed, key=key)]


def _token(value: Any) -> str:
    if isinstance(value, (Mapping, list, tuple, set, bytes)):
        return canonical_json(value)
    return str(value)
