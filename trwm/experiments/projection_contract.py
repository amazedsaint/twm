from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from ..branch import BranchRuntime
from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate
from ..projection import (
    ProjectionContract,
    build_projection_manifest,
    projection_manifest_from_mapping,
    validate_projection_contract,
)


PROJECTOR_ID = "stopping_distance.projector"
PROJECTOR_VERSION = "1.0"
PROJECTION_CONTRACT = ProjectionContract(
    required_fields=("distance_to_obstacle", "brake_accel", "safety_clearance"),
    contract_id="stopping_distance.safety_fields",
)


@dataclass(frozen=True)
class ProjectionGuardState:
    distance_to_obstacle: int = 5
    brake_accel: int = 2
    safety_clearance: int = 2
    committed_modes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectionContractReport:
    candidate_count: int
    verifier_calls: int
    unguarded_false_positive_accepts: bool
    guarded_partial_rejected: bool
    guarded_fast_complete_rejected: bool
    guarded_safe_commit: bool
    missing_fields: tuple[str, ...]
    unsafe_margin_numerator: int
    safe_margin_numerator: int
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int


class ProjectionGuardAdapter:
    verifier_id = "projection_contract_guard"
    verifier_version = "1.0"

    def __init__(self, observed_state: ProjectionGuardState | Mapping[str, Any], *, enforce_contract: bool = True):
        self.observed_state = normalize_projection_guard_state(observed_state)
        self.enforce_contract = enforce_contract

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        source = _source_fields(self.observed_state)
        manifest = projection_manifest_from_mapping(payload["projection_manifest"])
        metadata = {
            "mode": payload["mode"],
            "speed": payload["speed"],
            "cost": payload["cost"],
            "covered_fields": manifest.covered_fields,
        }
        if self.enforce_contract:
            audit = validate_projection_contract(PROJECTION_CONTRACT, manifest, source)
            if not audit.accepted:
                return HardVerifierResult.reject(
                    self.verifier_id,
                    self.verifier_version,
                    residual=audit.residual,
                    metadata=metadata,
                )
        distance = _int_payload(payload, "distance_to_obstacle")
        brake = _int_payload(payload, "brake_accel")
        clearance = int(payload.get("safety_clearance", 0))
        margin = stopping_margin_numerator(distance=distance, speed=payload["speed"], brake=brake, clearance=clearance)
        metadata = {
            **metadata,
            "margin_numerator": margin,
            "denominator": 2 * brake,
            "required_distance_numerator": payload["speed"] * payload["speed"] + (2 * brake * clearance),
            "available_distance_numerator": 2 * brake * distance,
        }
        if margin < 0:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={
                    "kind": "stopping_distance_violation",
                    "margin_numerator": margin,
                    "denominator": 2 * brake,
                },
                metadata=metadata,
            )
        return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)

    def apply_commit(self, state: ProjectionGuardState, candidate: TypedCandidate) -> ProjectionGuardState:
        current = normalize_projection_guard_state(state)
        payload = _normalize_payload(candidate.payload)
        return ProjectionGuardState(
            distance_to_obstacle=current.distance_to_obstacle,
            brake_accel=current.brake_accel,
            safety_clearance=current.safety_clearance,
            committed_modes=(*current.committed_modes, payload["mode"]),
        )

    def replay(self, state: ProjectionGuardState, receipt: Receipt) -> ProjectionGuardState:
        current = normalize_projection_guard_state(state)
        payload = _normalize_payload(receipt.replay_bundle["candidate_payload"])
        return ProjectionGuardState(
            distance_to_obstacle=current.distance_to_obstacle,
            brake_accel=current.brake_accel,
            safety_clearance=current.safety_clearance,
            committed_modes=(*current.committed_modes, payload["mode"]),
        )

    def rollback(self, state: ProjectionGuardState, receipt: Receipt) -> ProjectionGuardState:
        return normalize_projection_guard_state(receipt.rollback_bundle["pre_state"])


class ProjectionContractProjector:
    def project(self, state: ProjectionGuardState, trace: ProposalTrace) -> TypedCandidate:
        action = dict(trace.actions[-1])
        return make_projection_guard_candidate(
            state,
            mode=str(action["mode"]),
            speed=int(action["speed"]),
            covered_fields=tuple(str(field) for field in action["covered_fields"]),
            cost=int(action.get("cost", 1)),
        )


def normalize_projection_guard_state(state: ProjectionGuardState | Mapping[str, Any]) -> ProjectionGuardState:
    if isinstance(state, ProjectionGuardState):
        return ProjectionGuardState(
            distance_to_obstacle=int(state.distance_to_obstacle),
            brake_accel=int(state.brake_accel),
            safety_clearance=int(state.safety_clearance),
            committed_modes=tuple(str(mode) for mode in state.committed_modes),
        )
    return ProjectionGuardState(
        distance_to_obstacle=int(state.get("distance_to_obstacle", 5)),
        brake_accel=int(state.get("brake_accel", 2)),
        safety_clearance=int(state.get("safety_clearance", 2)),
        committed_modes=tuple(str(mode) for mode in state.get("committed_modes", ())),
    )


def make_projection_guard_candidate(
    state: ProjectionGuardState | Mapping[str, Any],
    *,
    mode: str,
    speed: int,
    covered_fields: Iterable[str],
    cost: int = 1,
) -> TypedCandidate:
    current = normalize_projection_guard_state(state)
    source = _source_fields(current)
    manifest = build_projection_manifest(
        source,
        covered_fields,
        projector_id=PROJECTOR_ID,
        projector_version=PROJECTOR_VERSION,
    )
    payload: dict[str, Any] = {
        "mode": mode,
        "speed": int(speed),
        "cost": int(cost),
        "projection_manifest": asdict(manifest),
    }
    for field in manifest.covered_fields:
        payload[field] = source[field]
    return TypedCandidate(
        payload=payload,
        type_name="projection_guard.stop_command",
        schema_version="projection_guard.stop_command.v1",
        hashes={"projection_manifest": manifest.projection_hash},
    )


def make_projection_contract_traces() -> tuple[ProposalTrace, ...]:
    actions = (
        {
            "mode": "fast_partial",
            "speed": 4,
            "cost": 1,
            "covered_fields": ("distance_to_obstacle", "brake_accel"),
        },
        {
            "mode": "fast_complete",
            "speed": 4,
            "cost": 1,
            "covered_fields": ("distance_to_obstacle", "brake_accel", "safety_clearance"),
        },
        {
            "mode": "crawl_complete",
            "speed": 2,
            "cost": 2,
            "covered_fields": ("distance_to_obstacle", "brake_accel", "safety_clearance"),
        },
    )
    return tuple(
        ProposalTrace(
            branch_id=f"projection-contract-{action['mode']}",
            actions=(action,),
            seeds=("projection_contract", action["mode"]),
            model_version="projection.contract.v1",
        )
        for action in actions
    )


def run_projection_contract_benchmark() -> ProjectionContractReport:
    seed = ProjectionGuardState()
    traces = make_projection_contract_traces()
    projector = ProjectionContractProjector()
    partial_candidate = projector.project(seed, traces[0])
    unguarded = ProjectionGuardAdapter(seed, enforce_contract=False).verify(partial_candidate)

    engine = TransactionEngine(ProjectionGuardAdapter(seed), ledger=Ledger())
    runtime = BranchRuntime(engine, projector)
    outcome = runtime.step(seed, traces)
    replay_rollback_rate = 0.0
    ledger_audit = engine.ledger.audit()
    if ledger_audit:
        try:
            replay_state = engine.replay_audit(seed)
            rollback_state = engine.rollback_audit(seed)
            replay_rollback_rate = 1.0 if replay_state == outcome.state and rollback_state == seed else 0.0
        except Exception:
            replay_rollback_rate = 0.0
    partial_receipt = outcome.receipts[0]
    fast_receipt = outcome.receipts[1]
    safe_receipt = outcome.receipts[2]
    return ProjectionContractReport(
        candidate_count=len(traces),
        verifier_calls=outcome.verifier_calls,
        unguarded_false_positive_accepts=unguarded.accepted,
        guarded_partial_rejected=partial_receipt.hard_result.rejected,
        guarded_fast_complete_rejected=fast_receipt.hard_result.rejected,
        guarded_safe_commit=safe_receipt.committed and outcome.state.committed_modes == ("crawl_complete",),
        missing_fields=tuple(partial_receipt.hard_result.residual["missing_fields"]),
        unsafe_margin_numerator=int(fast_receipt.hard_result.metadata["margin_numerator"]),
        safe_margin_numerator=int(safe_receipt.hard_result.metadata["margin_numerator"]),
        ledger_audit=ledger_audit,
        replay_rollback_rate=replay_rollback_rate,
        invalid_commit_count=sum(1 for row in engine.ledger.rows if row.committed and not row.hard_result.accepted),
    )


def stopping_margin_numerator(*, distance: int, speed: int, brake: int, clearance: int) -> int:
    if distance < 0:
        raise ValueError("distance must be non-negative")
    if speed < 0:
        raise ValueError("speed must be non-negative")
    if brake <= 0:
        raise ValueError("brake must be positive")
    if clearance < 0:
        raise ValueError("clearance must be non-negative")
    denominator = 2 * brake
    return denominator * distance - (speed * speed + denominator * clearance)


def _source_fields(state: ProjectionGuardState) -> dict[str, int]:
    return {
        "distance_to_obstacle": state.distance_to_obstacle,
        "brake_accel": state.brake_accel,
        "safety_clearance": state.safety_clearance,
    }


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(payload["mode"])
    speed = int(payload["speed"])
    cost = int(payload.get("cost", 1))
    if not mode:
        raise ValueError("mode must be non-empty")
    if speed < 0:
        raise ValueError("speed must be non-negative")
    if cost < 0:
        raise ValueError("cost must be non-negative")
    if "projection_manifest" not in payload:
        raise ValueError("projection_manifest is required")
    return {**dict(payload), "mode": mode, "speed": speed, "cost": cost}


def _int_payload(payload: Mapping[str, Any], key: str) -> int:
    if key not in payload:
        raise ValueError(f"{key} is required")
    return int(payload[key])
