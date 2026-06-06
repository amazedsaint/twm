from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Mapping

from examples.common import (
    CertifiedExampleResult,
    build_example_evidence_certificate,
    report_as_dict,
    validate_example_evidence_certificate,
)
from trwm.claims import certify_claim, requirement
from trwm.core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


DEFAULT_BETA = 2.0
DEFAULT_COUPLING = 1
DEFAULT_FIELD = 0
MATERIAL_LATTICE_SOURCES = (
    "https://www.osti.gov/biblio/4390578/",
)
MATERIAL_LATTICE_CLAIM_BOUNDARY = (
    "G1 local 2D Ising spin-lattice canary only; not production materials simulation, "
    "phase-diagram evidence, or materials discovery evidence."
)


@dataclass(frozen=True)
class MaterialLatticeState:
    lattice: tuple[tuple[int, ...], ...]
    accepted_flips: int = 0


@dataclass(frozen=True)
class MaterialLatticeReport:
    schema_version: str
    experiment_id: str
    source_math: tuple[str, ...]
    first_decision: str
    first_residual_kind: str
    first_delta_energy: int
    repaired_decision: str
    repaired_committed: bool
    repaired_flip: tuple[int, int]
    repaired_delta_energy: int
    energy_before: int
    energy_after: int
    magnetization_before: int
    magnetization_after: int
    metropolis_probability: float
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    ledger_head: str
    verifier_id: str
    verifier_version: str
    receipt_count: int
    committed_count: int
    rejected_count: int
    receipt_hashes: tuple[str, ...]
    learned_residual_kinds: Mapping[str, int]
    learning: str


class MaterialLatticeMetropolisAdapter:
    verifier_id = "ising_lattice_metropolis_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        pre_state = normalize_state(payload["pre_state"])
        post_state = normalize_state(payload["post_state"])
        row, col = normalize_flip(payload["flip"])
        beta = _positive_float(payload.get("beta", DEFAULT_BETA), "beta")
        coupling = _int_value(payload.get("coupling", DEFAULT_COUPLING), "coupling")
        field = _int_value(payload.get("field", DEFAULT_FIELD), "field")
        uniform01 = _unit_interval(payload.get("uniform01", 1.0), "uniform01")
        metadata = {
            "beta": beta,
            "coupling": coupling,
            "field": field,
            "uniform01": uniform01,
            "verifier_cost": 1,
        }
        shape_error = _state_shape_error(pre_state)
        if shape_error:
            return self._reject("schema_error", {"message": shape_error}, metadata)
        if _state_shape_error(post_state):
            return self._reject("schema_error", {"message": "post_state shape does not match pre_state"}, metadata)
        expected = flip_spin(pre_state, row, col)
        if post_state != expected:
            return self._reject(
                "spin_flip_mismatch",
                {"repair": state_to_payload(expected), "flip": (row, col)},
                metadata,
            )

        delta = delta_energy(pre_state.lattice, row, col, coupling=coupling, field=field)
        probability = metropolis_acceptance_probability(delta, beta=beta)
        if uniform01 > probability:
            repair = best_energy_lowering_flip(pre_state.lattice, coupling=coupling, field=field)
            return self._reject(
                "metropolis_reject",
                {
                    "delta_energy": delta,
                    "acceptance_probability": probability,
                    "uniform01": uniform01,
                    "repair": repair,
                },
                metadata,
            )

        energy_before = total_energy(pre_state.lattice, coupling=coupling, field=field)
        energy_after = total_energy(post_state.lattice, coupling=coupling, field=field)
        if energy_after - energy_before != delta:
            return self._reject(
                "energy_delta_mismatch",
                {"expected_delta": delta, "actual_delta": energy_after - energy_before},
                metadata,
            )

        return HardVerifierResult.accept(
            self.verifier_id,
            self.verifier_version,
            metadata={
                **metadata,
                "delta_energy": delta,
                "acceptance_probability": probability,
                "energy_before": energy_before,
                "energy_after": energy_after,
                "magnetization_after": magnetization(post_state.lattice),
            },
        )

    def apply_commit(self, state: MaterialLatticeState, candidate: TypedCandidate) -> MaterialLatticeState:
        current = normalize_state(state)
        pre_state = normalize_state(candidate.payload["pre_state"])
        if current != pre_state:
            raise ValueError("candidate pre_state does not match current material lattice state")
        return normalize_state(candidate.payload["post_state"])

    def replay(self, state: MaterialLatticeState, receipt: Receipt) -> MaterialLatticeState:
        current = normalize_state(state)
        payload = receipt.replay_bundle["candidate_payload"]
        pre_state = normalize_state(payload["pre_state"])
        if current != pre_state:
            raise ValueError("receipt pre_state does not match replay material lattice state")
        return normalize_state(payload["post_state"])

    def rollback(self, state: MaterialLatticeState, receipt: Receipt) -> MaterialLatticeState:
        return normalize_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


def normalize_state(state: MaterialLatticeState | Mapping[str, Any]) -> MaterialLatticeState:
    if isinstance(state, MaterialLatticeState):
        lattice = state.lattice
        accepted_flips = state.accepted_flips
    else:
        lattice = tuple(tuple(row) for row in state["lattice"])
        accepted_flips = state.get("accepted_flips", state.get("acceptedFlips", 0))
    normalized = tuple(tuple(_spin_value(value) for value in row) for row in lattice)
    accepted = _int_value(accepted_flips, "accepted_flips")
    if accepted < 0:
        raise ValueError("accepted_flips must be non-negative")
    return MaterialLatticeState(lattice=normalized, accepted_flips=accepted)


def state_to_payload(state: MaterialLatticeState) -> dict[str, Any]:
    normalized = normalize_state(state)
    return {"lattice": normalized.lattice, "accepted_flips": normalized.accepted_flips}


def normalize_flip(flip: Any) -> tuple[int, int]:
    values = tuple(flip)
    if len(values) != 2:
        raise ValueError("flip must be a row/col pair")
    row = _int_value(values[0], "row")
    col = _int_value(values[1], "col")
    if row < 0 or col < 0:
        raise ValueError("flip indices must be non-negative")
    return row, col


def flip_spin(state: MaterialLatticeState, row: int, col: int) -> MaterialLatticeState:
    current = normalize_state(state)
    rows = [list(values) for values in current.lattice]
    if row >= len(rows) or col >= len(rows[0]):
        raise ValueError("flip index is outside lattice")
    rows[row][col] = -rows[row][col]
    return MaterialLatticeState(lattice=tuple(tuple(values) for values in rows), accepted_flips=current.accepted_flips + 1)


def total_energy(
    lattice: tuple[tuple[int, ...], ...],
    *,
    coupling: int = DEFAULT_COUPLING,
    field: int = DEFAULT_FIELD,
) -> int:
    rows = normalize_lattice(lattice)
    height = len(rows)
    width = len(rows[0])
    energy = 0
    for row in range(height):
        for col in range(width):
            spin = rows[row][col]
            energy -= coupling * spin * rows[row][(col + 1) % width]
            energy -= coupling * spin * rows[(row + 1) % height][col]
            energy -= field * spin
    return energy


def delta_energy(
    lattice: tuple[tuple[int, ...], ...],
    row: int,
    col: int,
    *,
    coupling: int = DEFAULT_COUPLING,
    field: int = DEFAULT_FIELD,
) -> int:
    rows = normalize_lattice(lattice)
    height = len(rows)
    width = len(rows[0])
    if row >= height or col >= width:
        raise ValueError("flip index is outside lattice")
    spin = rows[row][col]
    neighbor_sum = (
        rows[(row - 1) % height][col]
        + rows[(row + 1) % height][col]
        + rows[row][(col - 1) % width]
        + rows[row][(col + 1) % width]
    )
    return 2 * spin * (coupling * neighbor_sum + field)


def metropolis_acceptance_probability(delta: int, *, beta: float = DEFAULT_BETA) -> float:
    if delta <= 0:
        return 1.0
    return math.exp(-_positive_float(beta, "beta") * delta)


def magnetization(lattice: tuple[tuple[int, ...], ...]) -> int:
    return sum(sum(row) for row in normalize_lattice(lattice))


def best_energy_lowering_flip(
    lattice: tuple[tuple[int, ...], ...],
    *,
    coupling: int = DEFAULT_COUPLING,
    field: int = DEFAULT_FIELD,
) -> dict[str, Any]:
    rows = normalize_lattice(lattice)
    best: tuple[int, int, int] | None = None
    for row in range(len(rows)):
        for col in range(len(rows[0])):
            delta = delta_energy(rows, row, col, coupling=coupling, field=field)
            candidate = (delta, row, col)
            if best is None or candidate < best:
                best = candidate
    if best is None:
        raise ValueError("lattice must be non-empty")
    delta, row, col = best
    return {"row": row, "col": col, "delta_energy": delta}


def make_lattice_candidate(
    pre_state: MaterialLatticeState,
    flip: tuple[int, int],
    *,
    uniform01: float,
    context: str = "material-lattice-metropolis",
) -> TypedCandidate:
    pre = normalize_state(pre_state)
    row, col = normalize_flip(flip)
    post = flip_spin(pre, row, col)
    return TypedCandidate(
        payload={
            "context": context,
            "pre_state": pre,
            "post_state": post,
            "flip": (row, col),
            "beta": DEFAULT_BETA,
            "coupling": DEFAULT_COUPLING,
            "field": DEFAULT_FIELD,
            "uniform01": _unit_interval(uniform01, "uniform01"),
        },
        type_name="material.ising_spin_flip",
        schema_version="material.ising_spin_flip.v1",
        hashes={
            "pre_state": stable_hash(pre),
            "post_state": stable_hash(post),
            "flip": stable_hash((row, col)),
        },
    )


def run_material_lattice_metropolis_experiment() -> MaterialLatticeReport:
    seed_state = MaterialLatticeState(
        lattice=(
            (1, 1, 1),
            (1, -1, 1),
            (-1, -1, -1),
        )
    )
    ledger = Ledger()
    engine = TransactionEngine(MaterialLatticeMetropolisAdapter(), ledger=ledger)

    first_flip = (0, 0)
    first_candidate = make_lattice_candidate(seed_state, first_flip, uniform01=0.9)
    first = engine.transact(
        seed_state,
        ProposalTrace(
            branch_id="material-high-energy-flip",
            actions=({"flip": first_flip, "proposal": "high_energy_surface_flip"},),
            seeds=("material-lattice", 1),
            model_version="material.metropolis_proposer.v1",
        ),
        first_candidate,
        soft_scores={"domain_wall_exploration": 1.0},
    )
    residual = first.receipt.hard_result.residual
    if not isinstance(residual, Mapping) or not isinstance(residual.get("repair"), Mapping):
        raise AssertionError("material lattice verifier expected a repair residual")

    repair = residual["repair"]
    repaired_flip = (_int_value(repair["row"], "repair.row"), _int_value(repair["col"], "repair.col"))
    repaired_candidate = make_lattice_candidate(seed_state, repaired_flip, uniform01=0.0)
    repaired = engine.transact(
        first.state,
        ProposalTrace(
            branch_id="material-energy-lowering-repair",
            actions=({"flip": repaired_flip, "proposal": "energy_lowering_repair"},),
            seeds=("material-lattice", 2),
            model_version="material.metropolis_repair.v1",
        ),
        repaired_candidate,
        soft_scores={"energy_lowering": 1.0},
    )

    replay_ok = False
    rollback_ok = False
    if ledger.audit():
        replay_ok = engine.replay_audit(seed_state) == repaired.state
        rollback_ok = engine.rollback_audit(seed_state) == seed_state

    energy_before = total_energy(seed_state.lattice)
    energy_after = total_energy(repaired.state.lattice)
    first_delta = delta_energy(seed_state.lattice, *first_flip)
    repaired_delta = delta_energy(seed_state.lattice, *repaired_flip)
    residual_kind = str(residual.get("kind"))
    return MaterialLatticeReport(
        schema_version="trwm.example.material_lattice_metropolis.v1",
        experiment_id="material_lattice_metropolis",
        source_math=(
            "2D periodic Ising Hamiltonian E = -J sum_<ij> s_i s_j - h sum_i s_i",
            "Metropolis acceptance p = min(1, exp(-beta delta_E)) with candidate randomness recorded in the receipt",
        ),
        first_decision=first.reason,
        first_residual_kind=residual_kind,
        first_delta_energy=first_delta,
        repaired_decision=repaired.reason,
        repaired_committed=repaired.committed,
        repaired_flip=repaired_flip,
        repaired_delta_energy=repaired_delta,
        energy_before=energy_before,
        energy_after=energy_after,
        magnetization_before=magnetization(seed_state.lattice),
        magnetization_after=magnetization(repaired.state.lattice),
        metropolis_probability=metropolis_acceptance_probability(repaired_delta),
        replay_audit_ok=replay_ok,
        rollback_audit_ok=rollback_ok,
        ledger_audit_ok=ledger.audit(),
        invalid_commit_count=engine.invalid_commit_count,
        ledger_head=ledger.head,
        verifier_id=MaterialLatticeMetropolisAdapter.verifier_id,
        verifier_version=MaterialLatticeMetropolisAdapter.verifier_version,
        receipt_count=len(ledger.rows),
        committed_count=sum(1 for row in ledger.rows if row.committed),
        rejected_count=sum(1 for row in ledger.rows if row.hard_result.rejected),
        receipt_hashes=tuple(row.receipt_hash for row in ledger.rows),
        learned_residual_kinds={residual_kind: 1},
        learning=(
            "For materials workloads, a proposer can explore defects or domain-wall moves, but the "
            "transaction should bind the Hamiltonian, delta-energy arithmetic, acceptance randomness, "
            "and replayable lattice update before committing a configuration."
        ),
    )


def run_material_lattice_metropolis_certified_experiment() -> CertifiedExampleResult:
    report = run_material_lattice_metropolis_experiment()
    evidence = build_example_evidence_certificate(
        report,
        domain="material_science",
        verifier_id=report.verifier_id,
        verifier_version=report.verifier_version,
        ledger_head=report.ledger_head,
        receipt_hashes=report.receipt_hashes,
        committed_count=report.committed_count,
        rejected_count=report.rejected_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        hard_gate_keys=(
            "ising_hamiltonian_delta",
            "metropolis_acceptance",
            "receipt_bound_randomness",
            "replay",
            "rollback",
            "spin_flip_update",
        ),
        residual_kinds=tuple(report.learned_residual_kinds),
        claim_boundary=MATERIAL_LATTICE_CLAIM_BOUNDARY,
        sources=MATERIAL_LATTICE_SOURCES,
    )
    claim = certify_claim(
        claim_id="material_lattice_metropolis_g1",
        claim_text=(
            "An Ising/Metropolis hard gate blocks rejected spin flips and commits an exact "
            "energy-lowering repair in the local G1 material lattice canary."
        ),
        evidence_grade="G1",
        scope="material_lattice_metropolis",
        requirements=(
            requirement("evidence_certificate_valid", validate_example_evidence_certificate(evidence, report)),
            requirement("high_energy_flip_rejected", report.first_decision == "hard_reject" and report.first_delta_energy > 0),
            requirement("energy_lowering_repair_committed", report.repaired_committed and report.repaired_delta_energy <= 0),
            requirement("energy_delta_exact", report.energy_after - report.energy_before == report.repaired_delta_energy),
            requirement("receipt_bound_randomness", report.metropolis_probability == 1.0),
            requirement("replay_and_rollback_valid", report.replay_audit_ok and report.rollback_audit_ok),
            requirement("zero_invalid_commits", report.invalid_commit_count == 0),
            requirement("source_bound", bool(evidence.sources)),
        ),
        metrics={
            "repaired_delta_energy": report.repaired_delta_energy,
            "receipt_count": report.receipt_count,
            "certificate_hash": evidence.certificate_hash,
        },
        boundary=MATERIAL_LATTICE_CLAIM_BOUNDARY,
        sources=MATERIAL_LATTICE_SOURCES,
    )
    return CertifiedExampleResult(report=report, evidence_certificate=evidence, claim_certificate=claim)


def normalize_lattice(lattice: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    rows = tuple(tuple(_spin_value(value) for value in row) for row in lattice)
    if not rows or not rows[0]:
        raise ValueError("lattice must be non-empty")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("lattice rows must have equal width")
    return rows


def _state_shape_error(state: MaterialLatticeState) -> str | None:
    try:
        normalize_lattice(state.lattice)
    except ValueError as exc:
        return str(exc)
    return None


def _spin_value(value: Any) -> int:
    if isinstance(value, bool) or int(value) not in {-1, 1}:
        raise ValueError("spin values must be -1 or 1")
    return int(value)


def _int_value(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    out = int(value)
    if out != value and not (isinstance(value, str) and value.strip() == str(out)):
        raise ValueError(f"{label} must be an integer")
    return out


def _positive_float(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out) or out <= 0:
        raise ValueError(f"{label} must be positive and finite")
    return out


def _unit_interval(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out) or out < 0.0 or out > 1.0:
        raise ValueError(f"{label} must be in [0, 1]")
    return out


def main() -> None:
    print(json.dumps(report_as_dict(run_material_lattice_metropolis_certified_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
