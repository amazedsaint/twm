from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import random
from typing import Iterable, Mapping

from ..core import Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate
from ..experiments.shape_simulator import EpisodeResult, ShapeGuessAdapter
from ..learning import HyperdimensionalMemory


@dataclass(frozen=True)
class HdcMemoryReport:
    no_memory_calls_per_success: float
    exact_match_calls_per_success: float
    hdc_calls_per_success: float
    hdc_gain_over_no_memory: float
    hdc_gain_over_exact_match: float
    noise_retrieval_ok: bool
    tamper_detected: bool
    ledger_audit: bool
    invalid_commit_count: int


class ExactContextMemory:
    def __init__(self) -> None:
        self.accepted: defaultdict[str, Counter[int]] = defaultdict(Counter)
        self.rejected: defaultdict[str, Counter[int]] = defaultdict(Counter)

    def update(self, receipt: Receipt) -> None:
        payload = _payload(receipt)
        exact_context = str(payload.get("exact_context", payload.get("context", "global")))
        action = int(payload.get("action", payload.get("guess", -1)))
        if receipt.committed and receipt.hard_result.accepted:
            self.accepted[exact_context][action] += 1
        elif receipt.hard_result.rejected:
            self.rejected[exact_context][action] += 1

    def rank(self, exact_context: str, labels: list[int], fallback: list[int]) -> list[int]:
        fallback_index = {label: idx for idx, label in enumerate(fallback)}
        return sorted(
            labels,
            key=lambda label: (
                -self.accepted[exact_context][label],
                self.rejected[exact_context][label],
                fallback_index[label],
            ),
        )


def run_hdc_memory_benchmark(seed: int = 19, episodes: int = 96, label_count: int = 24) -> HdcMemoryReport:
    rng = random.Random(seed)
    labels = list(range(label_count))
    motifs = [1, 1, 1, 3, 3, 7]
    defects = [rng.choice(motifs) for _ in range(episodes)]
    static_order = labels[:]
    random.Random(seed + 1).shuffle(static_order)

    no_ledger = Ledger()
    exact_ledger = Ledger()
    hdc_ledger = Ledger()

    no_memory = _run_order(defects, labels, static_order, "none", no_ledger)
    exact_memory = ExactContextMemory()
    exact = _run_order(defects, labels, static_order, "exact", exact_ledger, exact_memory=exact_memory)
    hdc_memory = HyperdimensionalMemory(dimensions=512)
    hdc = _run_order(defects, labels, static_order, "hdc", hdc_ledger, hdc_memory=hdc_memory)

    no_cps = _calls_per_success(no_memory)
    exact_cps = _calls_per_success(exact)
    hdc_cps = _calls_per_success(hdc)
    noisy = _flip_bits(hdc_memory.encode_query({"context": "motif-low", "result": "accept"}), rate=0.1, seed=seed + 2)
    noisy_neighbors = hdc_memory.nearest_vector(noisy, top_k=16)
    noise_retrieval_ok = any(
        receipt.hard_result.accepted and _payload(receipt).get("context") == "motif-low"
        for receipt in noisy_neighbors
    )
    tampered = Ledger()
    tampered.head = hdc_ledger.head
    tampered.rows = list(hdc_ledger.rows)
    if tampered.rows:
        tampered.rows[0] = replace(tampered.rows[0], branch_id="tampered")
    ledgers = (no_ledger, exact_ledger, hdc_ledger)
    return HdcMemoryReport(
        no_memory_calls_per_success=no_cps,
        exact_match_calls_per_success=exact_cps,
        hdc_calls_per_success=hdc_cps,
        hdc_gain_over_no_memory=no_cps / hdc_cps,
        hdc_gain_over_exact_match=exact_cps / hdc_cps,
        noise_retrieval_ok=noise_retrieval_ok,
        tamper_detected=not tampered.audit(),
        ledger_audit=all(ledger.audit() for ledger in ledgers),
        invalid_commit_count=_invalid_commits(ledgers),
    )


def _run_order(
    defects: list[int],
    labels: list[int],
    static_order: list[int],
    lane: str,
    ledger: Ledger,
    exact_memory: ExactContextMemory | None = None,
    hdc_memory: HyperdimensionalMemory | None = None,
) -> list[EpisodeResult]:
    engine = TransactionEngine(ShapeGuessAdapter(), ledger=ledger)
    results: list[EpisodeResult] = []
    for episode, defect in enumerate(defects):
        state = {"family": lane, "episode": episode, "solved": False}
        exact_context = f"motif-low:{episode}"
        if exact_memory is not None:
            order = exact_memory.rank(exact_context, labels, static_order)
        elif hdc_memory is not None:
            order = _hdc_rank("motif-low", labels, static_order, hdc_memory)
        else:
            order = static_order
        calls = 0
        success = False
        for guess in order:
            calls += 1
            trace = ProposalTrace(
                branch_id=f"hdc-{lane}-{episode}-{guess}",
                actions=(guess,),
                seeds=(episode, guess, lane),
                model_version="hdc.memory.v1",
            )
            candidate = TypedCandidate(
                payload={
                    "context": "motif-low",
                    "exact_context": exact_context,
                    "action": guess,
                    "guess": guess,
                    "defect": defect,
                },
                type_name="shape.guess",
                schema_version="shape.guess.v1",
            )
            outcome = engine.transact(state, trace, candidate)
            exact_memory and exact_memory.update(outcome.receipt)
            hdc_memory and hdc_memory.add(outcome.receipt)
            if outcome.committed:
                success = True
                break
        results.append(EpisodeResult(calls=calls, success=success))
    return results


def _hdc_rank(context: str, labels: list[int], static_order: list[int], memory: HyperdimensionalMemory) -> list[int]:
    if not memory.rows:
        return static_order
    fallback_index = {label: idx for idx, label in enumerate(static_order)}
    accepted: Counter[int] = Counter()
    rejected: Counter[int] = Counter()
    for receipt in memory.nearest({"context": context}, top_k=min(len(memory.rows), 96)):
        payload = _payload(receipt)
        action = int(payload.get("action", payload.get("guess", -1)))
        if receipt.committed and receipt.hard_result.accepted:
            accepted[action] += 1
        elif receipt.hard_result.rejected:
            rejected[action] += 1
    return sorted(labels, key=lambda label: (-accepted[label], rejected[label], fallback_index[label]))


def _calls_per_success(results: Iterable[EpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _payload(receipt: Receipt) -> Mapping[str, object]:
    bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
    payload = bundle.get("candidate_payload", {})
    return payload if isinstance(payload, Mapping) else {}


def _flip_bits(vector: tuple[int, ...], rate: float, seed: int) -> tuple[int, ...]:
    rng = random.Random(seed)
    out = list(vector)
    flips = max(1, round(len(out) * rate))
    for idx in rng.sample(range(len(out)), flips):
        out[idx] = -out[idx]
    return tuple(out)


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
