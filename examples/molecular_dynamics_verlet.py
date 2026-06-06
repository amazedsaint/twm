from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from typing import Any, Mapping

from trwm.core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


DEFAULT_DT = 0.0025
DEFAULT_EPSILON = 1.0
DEFAULT_SIGMA = 1.0
DEFAULT_MASS = 1.0
DEFAULT_STEP_TOLERANCE = 1e-11
DEFAULT_ENERGY_TOLERANCE = 1e-5
DEFAULT_MOMENTUM_TOLERANCE = 1e-12
DEFAULT_MIN_SEPARATION = 0.78


@dataclass(frozen=True)
class MolecularDynamicsState:
    positions: tuple[float, ...]
    velocities: tuple[float, ...]


@dataclass(frozen=True)
class MolecularDynamicsReport:
    schema_version: str
    experiment_id: str
    source_math: tuple[str, ...]
    first_decision: str
    first_residual_kind: str
    repaired_decision: str
    repaired_committed: bool
    integrator: str
    particle_count: int
    dt: float
    energy_before: float
    energy_after: float
    energy_drift: float
    momentum_before: float
    momentum_after: float
    momentum_drift: float
    min_separation: float
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    receipt_count: int
    committed_count: int
    receipt_hashes: tuple[str, ...]
    learned_residual_kinds: Mapping[str, int]
    learning: str


class MolecularDynamicsVerletAdapter:
    verifier_id = "lennard_jones_velocity_verlet_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        pre_state = normalize_state(payload["pre_state"])
        proposed = normalize_state(payload["post_state"])
        dt = _positive_float(payload.get("dt", DEFAULT_DT), "dt")
        epsilon = _positive_float(payload.get("epsilon", DEFAULT_EPSILON), "epsilon")
        sigma = _positive_float(payload.get("sigma", DEFAULT_SIGMA), "sigma")
        mass = _positive_float(payload.get("mass", DEFAULT_MASS), "mass")
        step_tolerance = _positive_float(payload.get("step_tolerance", DEFAULT_STEP_TOLERANCE), "step_tolerance")
        energy_tolerance = _positive_float(payload.get("energy_tolerance", DEFAULT_ENERGY_TOLERANCE), "energy_tolerance")
        momentum_tolerance = _positive_float(payload.get("momentum_tolerance", DEFAULT_MOMENTUM_TOLERANCE), "momentum_tolerance")
        min_required_separation = _positive_float(payload.get("min_separation", DEFAULT_MIN_SEPARATION), "min_separation")
        metadata = {
            "integrator": payload.get("integrator", "unknown"),
            "dt": dt,
            "particle_count": len(pre_state.positions),
            "verifier_cost": 2,
        }
        shape_error = _state_shape_error(pre_state)
        if shape_error:
            return self._reject("schema_error", {"message": shape_error}, metadata)
        if _state_shape_error(proposed):
            return self._reject("schema_error", {"message": "post_state shape does not match pre_state"}, metadata)

        expected = velocity_verlet_step(pre_state, dt=dt, epsilon=epsilon, sigma=sigma, mass=mass)
        integrator_error = max_state_error(proposed, expected)
        if integrator_error > step_tolerance:
            return self._reject(
                "integrator_mismatch",
                {
                    "max_state_error": integrator_error,
                    "tolerance": step_tolerance,
                    "repair": state_to_payload(expected),
                },
                metadata,
            )

        separation = min_pairwise_separation(proposed)
        if separation < min_required_separation:
            return self._reject(
                "close_contact",
                {"observed": separation, "required": min_required_separation},
                metadata,
            )

        energy_before = total_energy(pre_state, epsilon=epsilon, sigma=sigma, mass=mass)
        energy_after = total_energy(proposed, epsilon=epsilon, sigma=sigma, mass=mass)
        energy_drift = abs(energy_after - energy_before)
        if energy_drift > energy_tolerance:
            return self._reject(
                "energy_drift",
                {"observed": energy_drift, "tolerance": energy_tolerance},
                metadata,
            )

        momentum_before = total_momentum(pre_state, mass=mass)
        momentum_after = total_momentum(proposed, mass=mass)
        momentum_drift = abs(momentum_after - momentum_before)
        if momentum_drift > momentum_tolerance:
            return self._reject(
                "momentum_drift",
                {"observed": momentum_drift, "tolerance": momentum_tolerance},
                metadata,
            )

        return HardVerifierResult.accept(
            self.verifier_id,
            self.verifier_version,
            metadata={
                **metadata,
                "energy_before": energy_before,
                "energy_after": energy_after,
                "energy_drift": energy_drift,
                "momentum_drift": momentum_drift,
                "min_separation": separation,
            },
        )

    def apply_commit(self, state: MolecularDynamicsState, candidate: TypedCandidate) -> MolecularDynamicsState:
        current = normalize_state(state)
        pre_state = normalize_state(candidate.payload["pre_state"])
        if max_state_error(current, pre_state) > DEFAULT_STEP_TOLERANCE:
            raise ValueError("candidate pre_state does not match current molecular dynamics state")
        return normalize_state(candidate.payload["post_state"])

    def replay(self, state: MolecularDynamicsState, receipt: Receipt) -> MolecularDynamicsState:
        current = normalize_state(state)
        payload = receipt.replay_bundle["candidate_payload"]
        pre_state = normalize_state(payload["pre_state"])
        if max_state_error(current, pre_state) > DEFAULT_STEP_TOLERANCE:
            raise ValueError("receipt pre_state does not match replay molecular dynamics state")
        return normalize_state(payload["post_state"])

    def rollback(self, state: MolecularDynamicsState, receipt: Receipt) -> MolecularDynamicsState:
        return normalize_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


def normalize_state(state: MolecularDynamicsState | Mapping[str, Any]) -> MolecularDynamicsState:
    if isinstance(state, MolecularDynamicsState):
        positions = state.positions
        velocities = state.velocities
    else:
        positions = tuple(state["positions"])
        velocities = tuple(state["velocities"])
    return MolecularDynamicsState(
        positions=tuple(_finite_float(value, "position") for value in positions),
        velocities=tuple(_finite_float(value, "velocity") for value in velocities),
    )


def state_to_payload(state: MolecularDynamicsState) -> dict[str, tuple[float, ...]]:
    normalized = normalize_state(state)
    return {"positions": normalized.positions, "velocities": normalized.velocities}


def lennard_jones_potential(distance: float, *, epsilon: float = DEFAULT_EPSILON, sigma: float = DEFAULT_SIGMA) -> float:
    r = _positive_float(distance, "distance")
    inv = sigma / r
    inv6 = inv**6
    inv12 = inv6 * inv6
    return 4.0 * epsilon * (inv12 - inv6)


def lennard_jones_forces_1d(
    positions: tuple[float, ...],
    *,
    epsilon: float = DEFAULT_EPSILON,
    sigma: float = DEFAULT_SIGMA,
) -> tuple[float, ...]:
    xs = tuple(_finite_float(value, "position") for value in positions)
    forces = [0.0 for _ in xs]
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            dx = xs[i] - xs[j]
            r = abs(dx)
            if r <= 0:
                raise ValueError("particles must not overlap")
            inv = sigma / r
            inv6 = inv**6
            inv12 = inv6 * inv6
            coefficient = 24.0 * epsilon * (2.0 * inv12 - inv6) / (r * r)
            force = coefficient * dx
            forces[i] += force
            forces[j] -= force
    return tuple(forces)


def velocity_verlet_step(
    state: MolecularDynamicsState,
    *,
    dt: float = DEFAULT_DT,
    epsilon: float = DEFAULT_EPSILON,
    sigma: float = DEFAULT_SIGMA,
    mass: float = DEFAULT_MASS,
) -> MolecularDynamicsState:
    current = normalize_state(state)
    dt = _positive_float(dt, "dt")
    mass = _positive_float(mass, "mass")
    forces = lennard_jones_forces_1d(current.positions, epsilon=epsilon, sigma=sigma)
    accelerations = tuple(force / mass for force in forces)
    next_positions = tuple(
        x + v * dt + 0.5 * a * dt * dt
        for x, v, a in zip(current.positions, current.velocities, accelerations)
    )
    next_forces = lennard_jones_forces_1d(next_positions, epsilon=epsilon, sigma=sigma)
    next_accelerations = tuple(force / mass for force in next_forces)
    next_velocities = tuple(
        v + 0.5 * (a0 + a1) * dt
        for v, a0, a1 in zip(current.velocities, accelerations, next_accelerations)
    )
    return MolecularDynamicsState(positions=next_positions, velocities=next_velocities)


def euler_step(
    state: MolecularDynamicsState,
    *,
    dt: float = DEFAULT_DT,
    epsilon: float = DEFAULT_EPSILON,
    sigma: float = DEFAULT_SIGMA,
    mass: float = DEFAULT_MASS,
) -> MolecularDynamicsState:
    current = normalize_state(state)
    forces = lennard_jones_forces_1d(current.positions, epsilon=epsilon, sigma=sigma)
    accelerations = tuple(force / mass for force in forces)
    return MolecularDynamicsState(
        positions=tuple(x + v * dt for x, v in zip(current.positions, current.velocities)),
        velocities=tuple(v + a * dt for v, a in zip(current.velocities, accelerations)),
    )


def total_energy(
    state: MolecularDynamicsState,
    *,
    epsilon: float = DEFAULT_EPSILON,
    sigma: float = DEFAULT_SIGMA,
    mass: float = DEFAULT_MASS,
) -> float:
    current = normalize_state(state)
    kinetic = 0.5 * mass * sum(v * v for v in current.velocities)
    potential = 0.0
    for i in range(len(current.positions)):
        for j in range(i + 1, len(current.positions)):
            potential += lennard_jones_potential(abs(current.positions[i] - current.positions[j]), epsilon=epsilon, sigma=sigma)
    return kinetic + potential


def total_momentum(state: MolecularDynamicsState, *, mass: float = DEFAULT_MASS) -> float:
    current = normalize_state(state)
    return mass * sum(current.velocities)


def min_pairwise_separation(state: MolecularDynamicsState) -> float:
    current = normalize_state(state)
    best = float("inf")
    for i in range(len(current.positions)):
        for j in range(i + 1, len(current.positions)):
            best = min(best, abs(current.positions[i] - current.positions[j]))
    return best


def max_state_error(a: MolecularDynamicsState, b: MolecularDynamicsState) -> float:
    left = normalize_state(a)
    right = normalize_state(b)
    if len(left.positions) != len(right.positions) or len(left.velocities) != len(right.velocities):
        return float("inf")
    values = (
        *(abs(x - y) for x, y in zip(left.positions, right.positions)),
        *(abs(x - y) for x, y in zip(left.velocities, right.velocities)),
    )
    return max(values) if values else 0.0


def make_md_candidate(
    pre_state: MolecularDynamicsState,
    post_state: MolecularDynamicsState,
    *,
    integrator: str,
    context: str = "molecular-dynamics-verlet",
    dt: float = DEFAULT_DT,
) -> TypedCandidate:
    pre = normalize_state(pre_state)
    post = normalize_state(post_state)
    return TypedCandidate(
        payload={
            "context": context,
            "pre_state": pre,
            "post_state": post,
            "integrator": integrator,
            "dt": dt,
            "epsilon": DEFAULT_EPSILON,
            "sigma": DEFAULT_SIGMA,
            "mass": DEFAULT_MASS,
            "step_tolerance": DEFAULT_STEP_TOLERANCE,
            "energy_tolerance": DEFAULT_ENERGY_TOLERANCE,
            "momentum_tolerance": DEFAULT_MOMENTUM_TOLERANCE,
            "min_separation": DEFAULT_MIN_SEPARATION,
        },
        type_name="molecular.lennard_jones_step",
        schema_version="molecular.lennard_jones_step.v1",
        hashes={
            "pre_state": stable_hash(pre),
            "post_state": stable_hash(post),
            "integrator": stable_hash(integrator),
        },
    )


def run_molecular_dynamics_verlet_experiment() -> MolecularDynamicsReport:
    seed_state = MolecularDynamicsState(positions=(-0.56, 0.56), velocities=(0.015, -0.015))
    euler = euler_step(seed_state)
    verlet = velocity_verlet_step(seed_state)
    ledger = Ledger()
    engine = TransactionEngine(MolecularDynamicsVerletAdapter(), ledger=ledger)

    first_candidate = make_md_candidate(seed_state, euler, integrator="forward_euler")
    first = engine.transact(
        seed_state,
        ProposalTrace(
            branch_id="md-forward-euler-proposal",
            actions=({"integrator": "forward_euler"},),
            seeds=("molecular-dynamics-verlet", 1),
            model_version="md.proposer.euler.v1",
        ),
        first_candidate,
        soft_scores={"cheap_integrator": 1.0},
    )
    residual = first.receipt.hard_result.residual
    if not isinstance(residual, Mapping) or not isinstance(residual.get("repair"), Mapping):
        raise AssertionError("molecular dynamics verifier expected a repair residual")

    repaired_candidate = make_md_candidate(seed_state, normalize_state(residual["repair"]), integrator="velocity_verlet")
    repaired = engine.transact(
        first.state,
        ProposalTrace(
            branch_id="md-velocity-verlet-repair",
            actions=({"integrator": "velocity_verlet"},),
            seeds=("molecular-dynamics-verlet", 2),
            model_version="md.proposer.verlet_repair.v1",
        ),
        repaired_candidate,
        soft_scores={"cheap_integrator": 0.2, "physics_residual_repair": 1.0},
    )

    replay_ok = False
    rollback_ok = False
    if ledger.audit():
        replay_ok = engine.replay_audit(seed_state) == repaired.state
        rollback_ok = engine.rollback_audit(seed_state) == seed_state

    energy_before = total_energy(seed_state)
    energy_after = total_energy(repaired.state)
    momentum_before = total_momentum(seed_state)
    momentum_after = total_momentum(repaired.state)
    residual_kind = str(residual.get("kind"))
    return MolecularDynamicsReport(
        schema_version="trwm.example.molecular_dynamics_verlet.v1",
        experiment_id="molecular_dynamics_verlet",
        source_math=(
            "Lennard-Jones pair potential U(r) = 4 epsilon ((sigma/r)^12 - (sigma/r)^6)",
            "velocity Verlet: x1 = x0 + v0 dt + 0.5 a0 dt^2; v1 = v0 + 0.5 (a0 + a1) dt",
        ),
        first_decision=first.reason,
        first_residual_kind=residual_kind,
        repaired_decision=repaired.reason,
        repaired_committed=repaired.committed,
        integrator=str(repaired_candidate.payload["integrator"]),
        particle_count=len(seed_state.positions),
        dt=DEFAULT_DT,
        energy_before=energy_before,
        energy_after=energy_after,
        energy_drift=abs(energy_after - energy_before),
        momentum_before=momentum_before,
        momentum_after=momentum_after,
        momentum_drift=abs(momentum_after - momentum_before),
        min_separation=min_pairwise_separation(repaired.state),
        replay_audit_ok=replay_ok,
        rollback_audit_ok=rollback_ok,
        ledger_audit_ok=ledger.audit(),
        invalid_commit_count=engine.invalid_commit_count,
        receipt_count=len(ledger.rows),
        committed_count=sum(1 for row in ledger.rows if row.committed),
        receipt_hashes=tuple(row.receipt_hash for row in ledger.rows),
        learned_residual_kinds={residual_kind: 1},
        learning=(
            "A cheap dynamics proposer can be useful for exploration, but the transaction must verify "
            "the symplectic step, contact bound, energy drift, and momentum drift before state changes."
        ),
    )


def _state_shape_error(state: MolecularDynamicsState) -> str | None:
    if len(state.positions) != len(state.velocities):
        return "positions and velocities must have the same length"
    if len(state.positions) < 2:
        return "at least two particles are required"
    return None


def _finite_float(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{label} must be finite")
    return out


def _positive_float(value: Any, label: str) -> float:
    out = _finite_float(value, label)
    if out <= 0:
        raise ValueError(f"{label} must be positive")
    return out


def report_as_dict(report: MolecularDynamicsReport) -> dict[str, Any]:
    return asdict(report)


def main() -> None:
    print(json.dumps(report_as_dict(run_molecular_dynamics_verlet_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
