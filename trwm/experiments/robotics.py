from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


EPSILON = 1e-9
DEFAULT_DETOUR_Y = (0.5, 0.46, 0.54, 0.42, 0.58, 0.34, 0.66, 0.22, 0.78, 0.12, 0.88)
DEFAULT_EFFECTIVE_RADII = (0.16, 0.20, 0.24, 0.28, 0.31)


@dataclass(frozen=True)
class Point2:
    x: float
    y: float


@dataclass(frozen=True)
class CircleObstacle:
    obstacle_id: str
    center: Point2
    radius: float


@dataclass(frozen=True)
class RobotTrajectoryProblem:
    start: Point2
    goal: Point2
    obstacles: tuple[CircleObstacle, ...]
    robot_radius: float
    clearance: float
    max_step: float
    bounds: tuple[float, float, float, float]
    allowed_detour_y: tuple[float, ...] = DEFAULT_DETOUR_Y


@dataclass(frozen=True)
class RobotTrajectoryState:
    problem: RobotTrajectoryProblem
    solved: bool = False
    trajectory: tuple[Point2, ...] | None = None


@dataclass(frozen=True)
class RobotTrajectoryEpisodeResult:
    calls: int
    success: bool
    audit_ok: bool
    replay_rollback_ok: bool


@dataclass(frozen=True)
class RobotTrajectoryReport:
    episodes: int
    candidate_space_size: int
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    repair_success_rate: float
    ledger_audit_rate: float
    replay_rollback_rate: float
    invalid_commit_count: int
    learned_residual_kinds: Mapping[str, int]


class RobotTrajectoryAdapter:
    verifier_id = "point_robot_trajectory_tube_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        problem = normalize_problem(payload["problem"])
        trajectory = normalize_trajectory(payload["trajectory"])
        detour_y = _float_value(payload.get("detour_y", payload.get("detourY")), "detour_y")
        metadata = {
            "cost": payload.get("cost", 1),
            "waypoints": len(trajectory),
            "detour_y": detour_y,
            "max_step": problem.max_step,
        }
        shape_error = _candidate_shape_error(problem, trajectory, detour_y)
        if shape_error:
            return self._reject("schema_error", {"message": shape_error}, metadata)

        speed = first_speed_violation(problem, trajectory)
        if speed:
            return self._reject("speed_limit_exceeded", {**speed, "repair": diagnose_trajectory_repair(problem)}, metadata)

        collision = first_collision_violation(problem, trajectory)
        if collision:
            return self._reject("collision", {**collision, "repair": diagnose_trajectory_repair(problem)}, metadata)

        return HardVerifierResult.accept(
            self.verifier_id,
            self.verifier_version,
            metadata={
                **metadata,
                "min_clearance": min_clearance(problem, trajectory),
                "path_length": path_length(trajectory),
            },
        )

    def apply_commit(self, state: RobotTrajectoryState, candidate: TypedCandidate) -> RobotTrajectoryState:
        current = normalize_state(state)
        problem = normalize_problem(candidate.payload["problem"])
        if current.problem != problem:
            raise ValueError("candidate problem does not match current robot trajectory state")
        return RobotTrajectoryState(problem=problem, solved=True, trajectory=normalize_trajectory(candidate.payload["trajectory"]))

    def replay(self, state: RobotTrajectoryState, receipt: Receipt) -> RobotTrajectoryState:
        current = normalize_state(state)
        payload = receipt.replay_bundle["candidate_payload"]
        problem = normalize_problem(payload["problem"])
        if current.problem != problem:
            raise ValueError("receipt problem does not match replay robot trajectory state")
        return RobotTrajectoryState(problem=problem, solved=True, trajectory=normalize_trajectory(payload["trajectory"]))

    def rollback(self, state: RobotTrajectoryState, receipt: Receipt) -> RobotTrajectoryState:
        return normalize_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


class RobotResidualRepairer:
    def __init__(self) -> None:
        self.rejected_residuals: dict[str, int] = {}
        self.accepted_detours: dict[str, int] = {}

    def update(self, receipt: Receipt) -> None:
        if receipt.hard_result.accepted:
            payload = receipt.replay_bundle.get("candidate_payload", {}) if isinstance(receipt.replay_bundle, Mapping) else {}
            detour_y = payload.get("detour_y", payload.get("detourY", "unknown")) if isinstance(payload, Mapping) else "unknown"
            key = f"{detour_y}"
            self.accepted_detours[key] = self.accepted_detours.get(key, 0) + 1
            return
        residual = receipt.hard_result.residual
        if receipt.hard_result.rejected and isinstance(residual, Mapping):
            kind = str(residual.get("kind", "unknown"))
            self.rejected_residuals[kind] = self.rejected_residuals.get(kind, 0) + 1

    def propose(self, candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate | None:
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        detour_y = repair.get("detour_y", repair.get("detourY"))
        if detour_y is None:
            return None
        current_detour = _float_value(candidate.payload.get("detour_y", candidate.payload.get("detourY")), "detour_y")
        detour_y = _float_value(detour_y, "detour_y")
        if abs(detour_y - current_detour) <= EPSILON:
            return None
        return make_robot_trajectory_candidate(
            normalize_problem(candidate.payload["problem"]),
            detour_y,
            context=str(candidate.payload.get("context", "robot-repair")),
            cost=int(candidate.payload.get("cost", 1)) + 1,
        )


def normalize_point(point: Point2 | Mapping[str, Any] | Iterable[Any]) -> Point2:
    if isinstance(point, Point2):
        x = point.x
        y = point.y
    elif isinstance(point, Mapping):
        x = point["x"]
        y = point["y"]
    else:
        values = tuple(point)
        if len(values) != 2:
            raise ValueError("point must have two coordinates")
        x, y = values
    return Point2(_float_value(x, "point.x"), _float_value(y, "point.y"))


def normalize_obstacle(obstacle: CircleObstacle | Mapping[str, Any]) -> CircleObstacle:
    if isinstance(obstacle, CircleObstacle):
        obstacle_id = obstacle.obstacle_id
        center = obstacle.center
        radius = obstacle.radius
    else:
        obstacle_id = obstacle.get("obstacle_id", obstacle.get("obstacleId"))
        center = obstacle["center"]
        radius = obstacle["radius"]
    obstacle_id = str(obstacle_id)
    if not obstacle_id:
        raise ValueError("obstacle_id must be non-empty")
    radius = _float_value(radius, "obstacle radius")
    if radius <= 0:
        raise ValueError("obstacle radius must be positive")
    return CircleObstacle(obstacle_id=obstacle_id, center=normalize_point(center), radius=radius)


def normalize_problem(problem: RobotTrajectoryProblem | Mapping[str, Any]) -> RobotTrajectoryProblem:
    if isinstance(problem, RobotTrajectoryProblem):
        start = problem.start
        goal = problem.goal
        obstacles = problem.obstacles
        robot_radius = problem.robot_radius
        clearance = problem.clearance
        max_step = problem.max_step
        bounds = problem.bounds
        allowed_detour_y = problem.allowed_detour_y
    else:
        start = problem["start"]
        goal = problem["goal"]
        obstacles = problem["obstacles"]
        robot_radius = problem.get("robot_radius", problem.get("robotRadius"))
        clearance = problem["clearance"]
        max_step = problem.get("max_step", problem.get("maxStep"))
        bounds = problem["bounds"]
        allowed_detour_y = problem.get("allowed_detour_y", problem.get("allowedDetourY", DEFAULT_DETOUR_Y))
    normalized_bounds = tuple(_float_value(value, "bounds") for value in bounds)
    if len(normalized_bounds) != 4:
        raise ValueError("bounds must be (min_x, min_y, max_x, max_y)")
    min_x, min_y, max_x, max_y = normalized_bounds
    if not min_x < max_x or not min_y < max_y:
        raise ValueError("bounds must define a positive rectangle")
    robot_radius = _float_value(robot_radius, "robot_radius")
    clearance = _float_value(clearance, "clearance")
    max_step = _float_value(max_step, "max_step")
    if robot_radius <= 0 or clearance < 0 or max_step <= 0:
        raise ValueError("robot_radius and max_step must be positive; clearance must be non-negative")
    detours = tuple(_float_value(value, "detour_y") for value in allowed_detour_y)
    if not detours or len(set(detours)) != len(detours):
        raise ValueError("allowed_detour_y must be unique and non-empty")
    out = RobotTrajectoryProblem(
        start=normalize_point(start),
        goal=normalize_point(goal),
        obstacles=tuple(normalize_obstacle(obstacle) for obstacle in obstacles),
        robot_radius=robot_radius,
        clearance=clearance,
        max_step=max_step,
        bounds=normalized_bounds,
        allowed_detour_y=detours,
    )
    if not _point_in_bounds(out.start, out.bounds) or not _point_in_bounds(out.goal, out.bounds):
        raise ValueError("start and goal must be inside bounds")
    if not out.obstacles:
        raise ValueError("at least one obstacle is required for this G1 canary")
    return out


def normalize_state(state: RobotTrajectoryState | Mapping[str, Any]) -> RobotTrajectoryState:
    if isinstance(state, RobotTrajectoryState):
        return RobotTrajectoryState(
            problem=normalize_problem(state.problem),
            solved=bool(state.solved),
            trajectory=normalize_trajectory(state.trajectory) if state.trajectory is not None else None,
        )
    return RobotTrajectoryState(
        problem=normalize_problem(state["problem"]),
        solved=bool(state.get("solved", False)),
        trajectory=normalize_trajectory(state["trajectory"]) if state.get("trajectory") is not None else None,
    )


def normalize_trajectory(trajectory: Iterable[Any]) -> tuple[Point2, ...]:
    points = tuple(normalize_point(point) for point in trajectory)
    if len(points) < 2:
        raise ValueError("trajectory must contain at least start and goal")
    return points


def canonical_trajectory(problem_input: RobotTrajectoryProblem, detour_y: float) -> tuple[Point2, ...]:
    problem = normalize_problem(problem_input)
    detour_y = _float_value(detour_y, "detour_y")
    return (
        problem.start,
        Point2(0.35, detour_y),
        Point2(0.65, detour_y),
        problem.goal,
    )


def segment_distance(point_input: Point2, start_input: Point2, end_input: Point2) -> float:
    point = normalize_point(point_input)
    start = normalize_point(start_input)
    end = normalize_point(end_input)
    dx = end.x - start.x
    dy = end.y - start.y
    length_sq = dx * dx + dy * dy
    if length_sq <= EPSILON:
        return distance(point, start)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    nearest = Point2(start.x + t * dx, start.y + t * dy)
    return distance(point, nearest)


def distance(a_input: Point2, b_input: Point2) -> float:
    a = normalize_point(a_input)
    b = normalize_point(b_input)
    return math.hypot(a.x - b.x, a.y - b.y)


def path_length(trajectory_input: Iterable[Any]) -> float:
    trajectory = normalize_trajectory(trajectory_input)
    return sum(distance(a, b) for a, b in zip(trajectory, trajectory[1:]))


def effective_obstacle_radius(problem: RobotTrajectoryProblem, obstacle: CircleObstacle) -> float:
    problem = normalize_problem(problem)
    obstacle = normalize_obstacle(obstacle)
    return problem.robot_radius + problem.clearance + obstacle.radius


def min_clearance(problem_input: RobotTrajectoryProblem, trajectory_input: Iterable[Any]) -> float:
    problem = normalize_problem(problem_input)
    trajectory = normalize_trajectory(trajectory_input)
    best = float("inf")
    for segment_start, segment_end in zip(trajectory, trajectory[1:]):
        for obstacle in problem.obstacles:
            clearance = segment_distance(obstacle.center, segment_start, segment_end) - effective_obstacle_radius(problem, obstacle)
            best = min(best, clearance)
    return best


def first_speed_violation(problem_input: RobotTrajectoryProblem, trajectory_input: Iterable[Any]) -> dict[str, Any] | None:
    problem = normalize_problem(problem_input)
    trajectory = normalize_trajectory(trajectory_input)
    for idx, (start, end) in enumerate(zip(trajectory, trajectory[1:])):
        step = distance(start, end)
        if step > problem.max_step + EPSILON:
            return {"segment_index": idx, "distance": step, "max_step": problem.max_step}
    return None


def first_collision_violation(problem_input: RobotTrajectoryProblem, trajectory_input: Iterable[Any]) -> dict[str, Any] | None:
    problem = normalize_problem(problem_input)
    trajectory = normalize_trajectory(trajectory_input)
    for idx, (start, end) in enumerate(zip(trajectory, trajectory[1:])):
        for obstacle in problem.obstacles:
            observed = segment_distance(obstacle.center, start, end)
            required = effective_obstacle_radius(problem, obstacle)
            if observed < required - EPSILON:
                return {
                    "segment_index": idx,
                    "obstacle_id": obstacle.obstacle_id,
                    "distance": observed,
                    "required_distance": required,
                    "penetration": required - observed,
                }
    return None


def trajectory_is_safe(problem_input: RobotTrajectoryProblem, trajectory_input: Iterable[Any]) -> bool:
    problem = normalize_problem(problem_input)
    trajectory = normalize_trajectory(trajectory_input)
    if _candidate_shape_error(problem, trajectory, trajectory[1].y) is not None:
        return False
    return first_speed_violation(problem, trajectory) is None and first_collision_violation(problem, trajectory) is None


def diagnose_trajectory_repair(problem_input: RobotTrajectoryProblem) -> dict[str, Any] | None:
    problem = normalize_problem(problem_input)
    for detour_y in problem.allowed_detour_y:
        trajectory = canonical_trajectory(problem, detour_y)
        if first_speed_violation(problem, trajectory) is None and first_collision_violation(problem, trajectory) is None:
            return {
                "detour_y": detour_y,
                "trajectory": trajectory,
                "min_clearance": min_clearance(problem, trajectory),
                "path_length": path_length(trajectory),
            }
    return None


def make_robot_trajectory_candidate(
    problem: RobotTrajectoryProblem,
    detour_y: float,
    context: str = "robot-trajectory",
    cost: int = 1,
) -> TypedCandidate:
    problem = normalize_problem(problem)
    detour_y = _float_value(detour_y, "detour_y")
    trajectory = canonical_trajectory(problem, detour_y)
    return TypedCandidate(
        payload={
            "context": context,
            "problem": problem,
            "trajectory": trajectory,
            "detour_y": detour_y,
            "cost": cost,
        },
        type_name="robot.point2_trajectory_tube",
        schema_version="robot.point2_trajectory_tube.v1",
        hashes={
            "problem": stable_hash(problem),
            "trajectory": stable_hash(trajectory),
            "detour_y": stable_hash(detour_y),
        },
    )


def make_robot_trajectory_problem(effective_radius: float = 0.24, max_step: float = 0.46) -> RobotTrajectoryProblem:
    effective_radius = _float_value(effective_radius, "effective_radius")
    robot_radius = 0.04
    clearance = 0.02
    obstacle_radius = effective_radius - robot_radius - clearance
    if obstacle_radius <= 0:
        raise ValueError("effective radius must exceed robot radius plus clearance")
    return RobotTrajectoryProblem(
        start=Point2(0.10, 0.50),
        goal=Point2(0.90, 0.50),
        obstacles=(CircleObstacle("obs0", Point2(0.50, 0.50), obstacle_radius),),
        robot_radius=robot_radius,
        clearance=clearance,
        max_step=max_step,
        bounds=(0.0, 0.0, 1.0, 1.0),
    )


def run_static_robot_episode(
    problem: RobotTrajectoryProblem,
    detour_order: Iterable[float],
    ledger: Ledger,
    episode: int,
) -> RobotTrajectoryEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(RobotTrajectoryAdapter(), ledger=ledger)
    state = RobotTrajectoryState(problem=problem)
    calls = 0
    for detour_y in detour_order:
        calls += 1
        candidate = make_robot_trajectory_candidate(problem, detour_y, context="robot-static", cost=calls)
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"robot-static-{episode}-{calls}",
                actions=({"detour_y": detour_y},),
                seeds=(episode, calls),
                model_version="robot.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return _episode_result(calls, True, engine, state)
    return _episode_result(calls, False, engine, state)


def run_repair_robot_episode(
    problem: RobotTrajectoryProblem,
    ledger: Ledger,
    repairer: RobotResidualRepairer,
    episode: int,
    initial_detour_y: float = 0.5,
) -> RobotTrajectoryEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(RobotTrajectoryAdapter(), ledger=ledger)
    state = RobotTrajectoryState(problem=problem)
    candidate = make_robot_trajectory_candidate(problem, initial_detour_y, context="robot-repair", cost=1)
    for attempt in range(3):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"robot-repair-{episode}-{attempt}",
                actions=({"detour_y": candidate.payload["detour_y"]},),
                seeds=(episode, attempt),
                model_version="robot.residual_repair.v1",
            ),
            candidate,
        )
        repairer.update(outcome.receipt)
        if outcome.committed:
            return _episode_result(attempt + 1, True, engine, state)
        residual = outcome.receipt.hard_result.residual
        if not isinstance(residual, Mapping):
            return _episode_result(attempt + 1, False, engine, state)
        repaired = repairer.propose(candidate, residual)
        if repaired is None:
            return _episode_result(attempt + 1, False, engine, state)
        candidate = repaired
    return _episode_result(3, False, engine, state)


def run_robot_trajectory_benchmark(seed: int = 67, episodes: int = 45) -> RobotTrajectoryReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    radii = list(DEFAULT_EFFECTIVE_RADII)
    rng = random.Random(seed)
    rng.shuffle(radii)
    static_results: list[RobotTrajectoryEpisodeResult] = []
    repair_results: list[RobotTrajectoryEpisodeResult] = []
    static_ledgers: list[Ledger] = []
    repair_ledgers: list[Ledger] = []
    repairer = RobotResidualRepairer()
    for episode in range(episodes):
        problem = make_robot_trajectory_problem(radii[episode % len(radii)])
        static_ledger = Ledger()
        repair_ledger = Ledger()
        static_ledgers.append(static_ledger)
        repair_ledgers.append(repair_ledger)
        static_results.append(run_static_robot_episode(problem, DEFAULT_DETOUR_Y, static_ledger, episode))
        repair_results.append(run_repair_robot_episode(problem, repair_ledger, repairer, episode))
    all_results = (*static_results, *repair_results)
    static_cps = _calls_per_success(static_results)
    repair_cps = _calls_per_success(repair_results)
    return RobotTrajectoryReport(
        episodes=episodes,
        candidate_space_size=len(DEFAULT_DETOUR_Y),
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        repair_success_rate=sum(1 for row in repair_results if row.success) / len(repair_results),
        ledger_audit_rate=sum(1 for row in all_results if row.audit_ok) / len(all_results),
        replay_rollback_rate=sum(1 for row in all_results if row.replay_rollback_ok) / len(all_results),
        invalid_commit_count=_invalid_commits((*static_ledgers, *repair_ledgers)),
        learned_residual_kinds=dict(repairer.rejected_residuals),
    )


def _candidate_shape_error(problem: RobotTrajectoryProblem, trajectory: tuple[Point2, ...], detour_y: float) -> str | None:
    if detour_y not in problem.allowed_detour_y:
        return "detour_y is not in the allowed shield action set"
    expected = canonical_trajectory(problem, detour_y)
    if len(trajectory) != len(expected) or any(distance(a, b) > EPSILON for a, b in zip(trajectory, expected)):
        return "trajectory must match the canonical detour corridor for detour_y"
    if distance(trajectory[0], problem.start) > EPSILON:
        return "trajectory must start at the problem start"
    if distance(trajectory[-1], problem.goal) > EPSILON:
        return "trajectory must end at the problem goal"
    for point in trajectory:
        if not _point_in_bounds(point, problem.bounds):
            return "all waypoints must stay inside bounds"
    return None


def _point_in_bounds(point: Point2, bounds: tuple[float, float, float, float]) -> bool:
    min_x, min_y, max_x, max_y = bounds
    return min_x - EPSILON <= point.x <= max_x + EPSILON and min_y - EPSILON <= point.y <= max_y + EPSILON


def _episode_result(calls: int, success: bool, engine: TransactionEngine, seed_state: RobotTrajectoryState) -> RobotTrajectoryEpisodeResult:
    audit_ok = engine.ledger.audit()
    replay_rollback_ok = False
    if audit_ok:
        try:
            engine.replay_audit(seed_state)
            replay_rollback_ok = engine.rollback_audit(seed_state) == seed_state
        except Exception:
            replay_rollback_ok = False
    return RobotTrajectoryEpisodeResult(calls=calls, success=success, audit_ok=audit_ok, replay_rollback_ok=replay_rollback_ok)


def _calls_per_success(results: Iterable[RobotTrajectoryEpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)


def _float_value(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{label} must be finite")
    return out
