from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, TransactionEngine, TypedCandidate
from ..repair import ResidualProgramRepairer, attach_residual, evaluate_program, program_cost


@dataclass(frozen=True)
class RepairEpisodeResult:
    calls: int
    success: bool


@dataclass(frozen=True)
class RepairReport:
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    repair_success_rate: float
    ledger_audit: bool
    invalid_commit_count: int
    learned_repair_kinds: Mapping[str, int]


class ScalarProgramAdapter:
    verifier_id = "scalar_program_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        if not isinstance(payload, Mapping):
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "schema_error", "message": "payload must be a mapping"},
            )
        start = int(payload.get("start", 0))
        target = int(payload["target"])
        output = evaluate_program(payload.get("program", ()), start)
        if output == target:
            return HardVerifierResult.accept(
                self.verifier_id,
                self.verifier_version,
                metadata={"cost": program_cost(payload.get("program", ()))},
            )
        delta = target - output
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={
                "kind": "scalar_delta",
                "target": target,
                "output": output,
                "delta": delta,
                "repair": {"op": "add", "value": delta},
            },
            metadata={"cost": program_cost(payload.get("program", ()))},
        )

    def apply_commit(self, state: dict[str, Any], candidate: TypedCandidate) -> dict[str, Any]:
        payload = candidate.payload
        value = evaluate_program(payload["program"], int(payload.get("start", 0)))
        return {**state, "solved": True, "value": value, "program": tuple(payload["program"])}

    def replay(self, state: dict[str, Any], receipt) -> dict[str, Any]:
        payload = receipt.replay_bundle["candidate_payload"]
        value = evaluate_program(payload["program"], int(payload.get("start", 0)))
        return {**state, "solved": True, "value": value, "program": tuple(payload["program"])}

    def rollback(self, state: dict[str, Any], receipt) -> dict[str, Any]:
        return dict(receipt.rollback_bundle["pre_state"])


def make_scalar_candidate(context: str, target: int, program: Iterable[Mapping[str, Any]], start: int = 0) -> TypedCandidate:
    steps = tuple(dict(step) for step in program)
    return TypedCandidate(
        payload={
            "context": context,
            "start": start,
            "target": target,
            "program": steps,
            "output": evaluate_program(steps, start),
        },
        type_name="scalar.program",
        schema_version="scalar.program.v1",
    )


def run_static_episode(target: int, label_order: Iterable[int], ledger: Ledger, episode: int) -> RepairEpisodeResult:
    engine = TransactionEngine(ScalarProgramAdapter(), ledger=ledger)
    state = {"episode": episode, "target": target, "solved": False}
    calls = 0
    for guess in label_order:
        calls += 1
        candidate = make_scalar_candidate("scalar-static", target, ({"op": "set", "value": guess},))
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"static-{episode}-{guess}",
                actions=({"op": "set", "value": guess},),
                seeds=(episode, guess),
                model_version="scalar.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return RepairEpisodeResult(calls, True)
    return RepairEpisodeResult(calls, False)


def run_repair_episode(target: int, initial_guess: int, ledger: Ledger, repairer: ResidualProgramRepairer, episode: int) -> RepairEpisodeResult:
    engine = TransactionEngine(ScalarProgramAdapter(), ledger=ledger)
    state = {"episode": episode, "target": target, "solved": False}
    candidate = make_scalar_candidate("scalar-repair", target, ({"op": "set", "value": initial_guess},))
    calls = 0
    for attempt in range(3):
        calls += 1
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"repair-{episode}-{attempt}",
                actions=tuple(candidate.payload["program"]),
                seeds=(episode, attempt),
                model_version="residual.program.repair.v1",
            ),
            candidate,
        )
        repairer.update(outcome.receipt)
        if outcome.committed:
            return RepairEpisodeResult(calls, True)
        residual = outcome.receipt.hard_result.residual
        if not isinstance(residual, Mapping):
            return RepairEpisodeResult(calls, False)
        proposal = repairer.propose(attach_residual(candidate, residual))
        if proposal is None:
            return RepairEpisodeResult(calls, False)
        candidate = proposal.candidate
    return RepairEpisodeResult(calls, False)


def run_residual_repair_benchmark(seed: int = 13, episodes: int = 64, label_min: int = -12, label_max: int = 12) -> RepairReport:
    rng = random.Random(seed)
    labels = list(range(label_min, label_max + 1))
    static_order = labels[:]
    random.Random(seed + 1).shuffle(static_order)
    targets = [rng.choice([-8, -3, 0, 5, 9]) for _ in range(episodes // 2)]
    targets.extend(rng.randrange(label_min, label_max + 1) for _ in range(episodes - len(targets)))
    rng.shuffle(targets)

    static_ledger = Ledger()
    repair_ledger = Ledger()
    repairer = ResidualProgramRepairer()
    static_results = [run_static_episode(target, static_order, static_ledger, idx) for idx, target in enumerate(targets)]
    first_guess = label_min - 1
    repair_results = [
        run_repair_episode(target, first_guess, repair_ledger, repairer, idx)
        for idx, target in enumerate(targets)
    ]
    static_cps = _calls_per_success(static_results)
    repair_cps = _calls_per_success(repair_results)
    successes = sum(1 for row in repair_results if row.success)
    return RepairReport(
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        repair_success_rate=successes / len(repair_results) if repair_results else 0.0,
        ledger_audit=static_ledger.audit() and repair_ledger.audit(),
        invalid_commit_count=_invalid_commits((static_ledger, repair_ledger)),
        learned_repair_kinds=dict(repairer.rejected_residuals),
    )


def _calls_per_success(results: Iterable[RepairEpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
