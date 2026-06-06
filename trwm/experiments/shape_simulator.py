from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable

from ..core import (
    HardVerifierResult,
    Ledger,
    ProposalTrace,
    TransactionEngine,
    TypedCandidate,
)
from ..learning import ReceiptRanker
from ..preflight import one_hot_updates, shape_rank_preflight


@dataclass(frozen=True)
class EpisodeResult:
    calls: int
    success: bool


@dataclass(frozen=True)
class ShapeReport:
    low_random_calls_per_success: float
    low_memory_calls_per_success: float
    high_random_calls_per_success: float
    high_memory_calls_per_success: float
    low_gain: float
    high_gain: float
    low_preflight_r90: int
    high_preflight_r90: int
    low_preflight_fits_budget: bool
    high_preflight_fits_budget: bool
    low_preflight_energy_at_budget: float
    high_preflight_energy_at_budget: float
    ledger_audit: bool
    invalid_commit_count: int


class ShapeGuessAdapter:
    verifier_id = "shape_oracle"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        guess = payload["guess"]
        defect = payload["defect"]
        metadata = {"cost": 1}
        if guess == defect:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"miss": True, "guess": guess},
            metadata=metadata,
        )

    def apply_commit(self, state: dict, candidate: TypedCandidate) -> dict:
        payload = candidate.payload
        return {**state, "solved": True, "guess": payload["guess"], "defect": payload["defect"]}

    def replay(self, state: dict, receipt) -> dict:
        payload = receipt.replay_bundle["candidate_payload"]
        return {**state, "solved": True, "guess": payload["guess"], "defect": payload["defect"]}

    def rollback(self, state: dict, receipt) -> dict:
        return dict(receipt.rollback_bundle["pre_state"])


def _run_order(
    family: str,
    defects: Iterable[int],
    labels: list[int],
    orderer,
    engine: TransactionEngine,
    ranker: ReceiptRanker | None = None,
) -> list[EpisodeResult]:
    results = []
    for episode, defect in enumerate(defects):
        state = {"family": family, "episode": episode, "solved": False}
        calls = 0
        success = False
        for guess in orderer(family, episode, labels):
            calls += 1
            trace = ProposalTrace(
                branch_id=f"{family}-{episode}-{guess}",
                actions=(guess,),
                seeds=(episode, guess),
                model_version="shape.static.v1",
            )
            candidate = TypedCandidate(
                payload={"context": family, "action": guess, "guess": guess, "defect": defect},
                type_name="shape.guess",
                schema_version="shape.guess.v1",
            )
            outcome = engine.transact(state, trace, candidate)
            receipt = outcome.receipt
            if ranker is not None:
                ranker.update(receipt)
            if outcome.committed:
                success = True
                break
        results.append(EpisodeResult(calls=calls, success=success))
    return results


def _calls_per_success(results: list[EpisodeResult]) -> float:
    successes = sum(1 for row in results if row.success)
    calls = sum(row.calls for row in results)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(
        1
        for ledger in ledgers
        for row in ledger.rows
        if row.committed and not row.hard_result.accepted
    )


def run_shape_conditionality(seed: int = 7, episodes: int = 96, label_count: int = 24) -> ShapeReport:
    rng = random.Random(seed)
    labels = list(range(label_count))
    low_motifs = [1, 1, 1, 3, 3, 7]
    low_defects = [rng.choice(low_motifs) for _ in range(episodes)]
    high_defects = [rng.randrange(label_count) for _ in range(episodes)]
    random_order = labels[:]
    random.Random(seed + 1).shuffle(random_order)

    def static_order(_family: str, _episode: int, _labels: list[int]) -> list[int]:
        return random_order

    low_random_ledger = Ledger()
    high_random_ledger = Ledger()
    low_random_engine = TransactionEngine(ShapeGuessAdapter(), ledger=low_random_ledger)
    high_random_engine = TransactionEngine(ShapeGuessAdapter(), ledger=high_random_ledger)
    low_random = _run_order("low", low_defects, labels, static_order, low_random_engine)
    high_random = _run_order("high", high_defects, labels, static_order, high_random_engine)

    low_ranker = ReceiptRanker()
    high_ranker = ReceiptRanker()
    low_memory_ledger = Ledger()
    high_memory_ledger = Ledger()
    low_memory_engine = TransactionEngine(ShapeGuessAdapter(), ledger=low_memory_ledger)
    high_memory_engine = TransactionEngine(ShapeGuessAdapter(), ledger=high_memory_ledger)

    def memory_order_low(family: str, _episode: int, candidates: list[int]) -> list[int]:
        return low_ranker.rank(family, candidates)

    def memory_order_high(family: str, _episode: int, candidates: list[int]) -> list[int]:
        return high_ranker.rank(family, candidates)

    low_memory = _run_order("low", low_defects, labels, memory_order_low, low_memory_engine, low_ranker)
    high_memory = _run_order("high", high_defects, labels, memory_order_high, high_memory_engine, high_ranker)

    low_random_cps = _calls_per_success(low_random)
    low_memory_cps = _calls_per_success(low_memory)
    high_random_cps = _calls_per_success(high_random)
    high_memory_cps = _calls_per_success(high_memory)
    low_preflight = shape_rank_preflight(one_hot_updates(low_defects, label_count), rank_budget=4)
    high_preflight = shape_rank_preflight(one_hot_updates(high_defects, label_count), rank_budget=4)

    return ShapeReport(
        low_random_calls_per_success=low_random_cps,
        low_memory_calls_per_success=low_memory_cps,
        high_random_calls_per_success=high_random_cps,
        high_memory_calls_per_success=high_memory_cps,
        low_gain=low_random_cps / low_memory_cps,
        high_gain=high_random_cps / high_memory_cps,
        low_preflight_r90=low_preflight.r90,
        high_preflight_r90=high_preflight.r90,
        low_preflight_fits_budget=low_preflight.fits_budget,
        high_preflight_fits_budget=high_preflight.fits_budget,
        low_preflight_energy_at_budget=low_preflight.energy_at_budget,
        high_preflight_energy_at_budget=high_preflight.energy_at_budget,
        ledger_audit=all(
            ledger.audit()
            for ledger in (low_random_ledger, high_random_ledger, low_memory_ledger, high_memory_ledger)
        ),
        invalid_commit_count=_invalid_commits(
            (low_random_ledger, high_random_ledger, low_memory_ledger, high_memory_ledger)
        ),
    )
