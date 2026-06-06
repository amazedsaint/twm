from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, TransactionEngine, TypedCandidate
from ..macro import Macro, MacroMemory, PrefixSafeMacroRuntime


GridPoint = tuple[int, int]
GridState = Mapping[str, Any]


@dataclass(frozen=True)
class MacroGridReport:
    terminal_only_calls_per_success: float
    prefix_safe_calls_per_success: float
    static_macro_attempts_per_success: float
    learned_macro_attempts_per_success: float
    prefix_reject_count: int
    learned_prefix_reject_count: int
    macro_reuse_gain: float
    ledger_audit: bool
    invalid_commit_count: int


class GridMacroAdapter:
    verifier_id = "grid_macro_oracle"
    verifier_version = "1.0"

    def apply_step(self, state: GridState, step: str) -> GridState:
        x, y = state["position"]
        if step == "E":
            x += 1
        elif step == "W":
            x -= 1
        elif step == "N":
            y -= 1
        elif step == "S":
            y += 1
        else:
            raise ValueError(f"unsupported grid step: {step!r}")
        return {**state, "position": (x, y)}

    def prefix_safe(self, state: GridState, step: str, step_index: int) -> HardVerifierResult:
        x, y = state["position"]
        width, height = state["bounds"]
        walls = set(state.get("walls", ()))
        if not (0 <= x < width and 0 <= y < height):
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "out_of_bounds", "position": (x, y), "step": step, "step_index": step_index},
            )
        if (x, y) in walls:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "wall", "position": (x, y), "step": step, "step_index": step_index},
            )
        return HardVerifierResult.accept(self.verifier_id, self.verifier_version)

    def project_macro(self, pre_state: GridState, macro: Macro, final_state: GridState) -> TypedCandidate:
        return TypedCandidate(
            payload={
                "context": macro.context,
                "macro_id": macro.macro_id,
                "macro": macro.steps,
                "start": pre_state["position"],
                "goal": pre_state["goal"],
                "final": final_state["position"],
                "bounds": pre_state["bounds"],
                "walls": tuple(sorted(pre_state.get("walls", ()))),
                "cost": len(macro.steps),
            },
            type_name="grid.macro",
            schema_version="grid.macro.v1",
        )

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        if payload["final"] == payload["goal"]:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata={"cost": payload["cost"]})
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": "missed_goal", "final": payload["final"], "goal": payload["goal"]},
            metadata={"cost": payload["cost"]},
        )

    def apply_commit(self, state: GridState, candidate: TypedCandidate) -> GridState:
        return {**state, "position": candidate.payload["final"], "solved": True, "macro_id": candidate.payload["macro_id"]}

    def replay(self, state: GridState, receipt) -> GridState:
        payload = receipt.replay_bundle["candidate_payload"]
        return {**state, "position": payload["final"], "solved": True, "macro_id": payload["macro_id"]}

    def rollback(self, state: GridState, receipt) -> GridState:
        return dict(receipt.rollback_bundle["pre_state"])


def default_grid_state() -> dict[str, Any]:
    return {
        "position": (0, 0),
        "goal": (2, 2),
        "bounds": (3, 3),
        "walls": ((1, 1),),
        "solved": False,
    }


def default_macros() -> tuple[Macro, ...]:
    return (
        Macro("unsafe-through-wall", ("E", "S", "E", "S"), context="grid-3x3"),
        Macro("safe-around-wall", ("E", "E", "S", "S"), context="grid-3x3"),
    )


def run_prefix_safe_sequence(macros: Iterable[Macro], ledger: Ledger, memory: MacroMemory | None = None) -> tuple[int, int, int, bool]:
    adapter = GridMacroAdapter()
    engine = TransactionEngine(adapter, ledger=ledger)
    runtime = PrefixSafeMacroRuntime(engine, adapter)
    attempts = 0
    terminal_calls = 0
    state = default_grid_state()
    for macro in macros:
        attempts += 1
        outcome = runtime.run(state, macro)
        terminal_calls += outcome.terminal_verifier_calls
        if memory is not None:
            memory.update(outcome.receipt)
        if outcome.committed:
            return attempts, terminal_calls, runtime.prefix_reject_count, True
    return attempts, terminal_calls, runtime.prefix_reject_count, False


def run_macro_grid_benchmark(episodes: int = 32) -> MacroGridReport:
    macros = default_macros()
    terminal_only_calls = len(macros) * episodes
    prefix_ledger = Ledger()
    learned_ledger = Ledger()
    static_attempts = 0
    static_terminal_calls = 0
    static_successes = 0
    static_prefix_rejects = 0
    for _episode in range(episodes):
        attempts, terminal_calls, rejects, success = run_prefix_safe_sequence(macros, prefix_ledger)
        static_attempts += attempts
        static_terminal_calls += terminal_calls
        static_prefix_rejects += rejects
        static_successes += int(success)

    memory = MacroMemory()
    learned_attempts = 0
    learned_terminal_calls = 0
    learned_successes = 0
    learned_prefix_rejects = 0
    for _episode in range(episodes):
        ranked = memory.rank("grid-3x3", macros)
        attempts, terminal_calls, rejects, success = run_prefix_safe_sequence(ranked, learned_ledger, memory)
        learned_attempts += attempts
        learned_terminal_calls += terminal_calls
        learned_prefix_rejects += rejects
        learned_successes += int(success)

    static_cps = static_terminal_calls / static_successes
    learned_attempts_per_success = learned_attempts / learned_successes
    static_attempts_per_success = static_attempts / static_successes
    return MacroGridReport(
        terminal_only_calls_per_success=terminal_only_calls / episodes,
        prefix_safe_calls_per_success=static_cps,
        static_macro_attempts_per_success=static_attempts_per_success,
        learned_macro_attempts_per_success=learned_attempts_per_success,
        prefix_reject_count=static_prefix_rejects,
        learned_prefix_reject_count=learned_prefix_rejects,
        macro_reuse_gain=static_attempts_per_success / learned_attempts_per_success,
        ledger_audit=prefix_ledger.audit() and learned_ledger.audit(),
        invalid_commit_count=_invalid_commits((prefix_ledger, learned_ledger)),
    )


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
