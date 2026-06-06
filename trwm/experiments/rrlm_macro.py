from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable

from ..core import Ledger
from ..macro import Macro
from ..rrlm import (
    NonReversibleMacroRanker,
    RrlmMacroProposer,
    build_rrlm_proposal_certificate,
    build_rrlm_transport_certificate,
    validate_rrlm_macro_snapshot,
    validate_rrlm_proposal_certificate,
    validate_rrlm_transport_certificate,
)
from .macro_grid import default_macros, run_prefix_safe_sequence


@dataclass(frozen=True)
class RrlmMacroReport:
    reversible_only_attempts_per_success: float
    matched_non_reversible_attempts_per_success: float
    rrlm_attempts_per_success: float
    reversible_only_prefix_reject_count: int
    matched_non_reversible_prefix_reject_count: int
    rrlm_prefix_reject_count: int
    rrlm_reuse_gain: float
    rrlm_vs_non_reversible_gain: float
    rrlm_cycle_failure_count: int
    snapshot_valid: bool
    proposal_certificate_valid: bool
    transport_certificate_valid: bool
    transport_certificate_i32_admissible_count: int
    transport_certificate_i32_rejected_count: int
    snapshot_tamper_detected: bool
    proposal_tamper_detected: bool
    transport_tamper_detected: bool
    snapshot_hash: str
    proposal_certificate_hash: str
    transport_certificate_hash: str
    ledger_audit: bool
    invalid_commit_count: int


def run_rrlm_macro_benchmark(episodes: int = 32) -> RrlmMacroReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    macros = default_macros()

    reversible_only = RrlmMacroProposer()
    reversible_only_stats = _run_rrlm_lane(macros, episodes, reversible_only, update_from_receipts=False)

    matched_non_reversible = NonReversibleMacroRanker()
    matched_stats = _run_ranker_lane(macros, episodes, matched_non_reversible.rank, matched_non_reversible)

    rrlm = RrlmMacroProposer()
    rrlm_stats = _run_rrlm_lane(macros, episodes, rrlm, update_from_receipts=True)
    snapshot = rrlm.snapshot()
    proposal_certificate = build_rrlm_proposal_certificate(snapshot, rrlm.propose("grid-3x3", macros))
    transport_certificate = build_rrlm_transport_certificate(proposal_certificate)
    tampered_snapshot = replace(
        snapshot,
        rows=(replace(snapshot.rows[0], accepted_count=snapshot.rows[0].accepted_count + 1), *snapshot.rows[1:]),
        snapshot_hash="",
    )
    tampered_certificate = replace(
        proposal_certificate,
        scores=(proposal_certificate.scores[0] + 1, *proposal_certificate.scores[1:]),
        certificate_hash="",
    )
    tampered_transport = replace(
        transport_certificate,
        latent_roundtrip=((transport_certificate.latent_roundtrip[0][0] + 1, *transport_certificate.latent_roundtrip[0][1:]), *transport_certificate.latent_roundtrip[1:]),
        certificate_hash="",
    )

    return RrlmMacroReport(
        reversible_only_attempts_per_success=reversible_only_stats["attempts_per_success"],
        matched_non_reversible_attempts_per_success=matched_stats["attempts_per_success"],
        rrlm_attempts_per_success=rrlm_stats["attempts_per_success"],
        reversible_only_prefix_reject_count=reversible_only_stats["prefix_rejects"],
        matched_non_reversible_prefix_reject_count=matched_stats["prefix_rejects"],
        rrlm_prefix_reject_count=rrlm_stats["prefix_rejects"],
        rrlm_reuse_gain=reversible_only_stats["attempts_per_success"] / rrlm_stats["attempts_per_success"],
        rrlm_vs_non_reversible_gain=matched_stats["attempts_per_success"] / rrlm_stats["attempts_per_success"],
        rrlm_cycle_failure_count=reversible_only_stats["cycle_failures"] + rrlm_stats["cycle_failures"],
        snapshot_valid=validate_rrlm_macro_snapshot(snapshot),
        proposal_certificate_valid=validate_rrlm_proposal_certificate(proposal_certificate, snapshot),
        transport_certificate_valid=validate_rrlm_transport_certificate(transport_certificate, proposal_certificate),
        transport_certificate_i32_admissible_count=transport_certificate.i32_admissible_count,
        transport_certificate_i32_rejected_count=transport_certificate.i32_rejected_count,
        snapshot_tamper_detected=not validate_rrlm_macro_snapshot(tampered_snapshot),
        proposal_tamper_detected=not validate_rrlm_proposal_certificate(tampered_certificate, snapshot),
        transport_tamper_detected=not validate_rrlm_transport_certificate(tampered_transport, proposal_certificate),
        snapshot_hash=snapshot.snapshot_hash,
        proposal_certificate_hash=proposal_certificate.certificate_hash,
        transport_certificate_hash=transport_certificate.certificate_hash,
        ledger_audit=reversible_only_stats["ledger"].audit() and matched_stats["ledger"].audit() and rrlm_stats["ledger"].audit(),
        invalid_commit_count=_invalid_commits((reversible_only_stats["ledger"], matched_stats["ledger"], rrlm_stats["ledger"])),
    )


def _run_rrlm_lane(
    macros: tuple[Macro, ...],
    episodes: int,
    proposer: RrlmMacroProposer,
    update_from_receipts: bool,
) -> dict[str, Any]:
    ledger = Ledger()
    attempts = 0
    terminal_calls = 0
    prefix_rejects = 0
    successes = 0
    cycle_failures = 0
    for _episode in range(episodes):
        ranking = proposer.propose("grid-3x3", macros)
        cycle_failures += ranking.cycle_failure_count
        run_attempts, run_terminal_calls, run_rejects, success = run_prefix_safe_sequence(
            ranking.ranked_macros,
            ledger,
            proposer if update_from_receipts else None,
        )
        attempts += run_attempts
        terminal_calls += run_terminal_calls
        prefix_rejects += run_rejects
        successes += int(success)
    return {
        "attempts_per_success": attempts / successes,
        "terminal_calls_per_success": terminal_calls / successes,
        "prefix_rejects": prefix_rejects,
        "cycle_failures": cycle_failures,
        "ledger": ledger,
    }


def _run_ranker_lane(
    macros: tuple[Macro, ...],
    episodes: int,
    rank: Callable[[str, Iterable[Macro]], list[Macro]],
    learner: Any,
) -> dict[str, Any]:
    ledger = Ledger()
    attempts = 0
    terminal_calls = 0
    prefix_rejects = 0
    successes = 0
    for _episode in range(episodes):
        ranked = rank("grid-3x3", macros)
        run_attempts, run_terminal_calls, run_rejects, success = run_prefix_safe_sequence(ranked, ledger, learner)
        attempts += run_attempts
        terminal_calls += run_terminal_calls
        prefix_rejects += run_rejects
        successes += int(success)
    return {
        "attempts_per_success": attempts / successes,
        "terminal_calls_per_success": terminal_calls / successes,
        "prefix_rejects": prefix_rejects,
        "ledger": ledger,
    }


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
