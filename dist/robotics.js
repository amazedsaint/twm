import {




  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { stableHash } from "./canonical.js";

export const ROBOT_EPSILON = 1e-9;
export const DEFAULT_DETOUR_Y = [0.5, 0.46, 0.54, 0.42, 0.58, 0.34, 0.66, 0.22, 0.78, 0.12, 0.88];
export const DEFAULT_EFFECTIVE_RADII = [0.16, 0.20, 0.24, 0.28, 0.31];










































































export class RobotTrajectoryAdapter                                                                                {
  verifierId = "point_robot_trajectory_tube_verifier";
  verifierVersion = "1.0";

  verify(candidate                                        )                     {
    const problem = normalizeRobotProblem(candidate.payload.problem);
    const trajectory = normalizeTrajectory(candidate.payload.trajectory);
    const detourY = numberValue(candidate.payload.detourY ?? (candidate.payload                                      ).detour_y, "detourY");
    const metadata = {
      cost: candidate.payload.cost,
      waypoints: trajectory.length,
      detourY,
      maxStep: problem.maxStep,
    };
    const shapeError = candidateShapeError(problem, trajectory, detourY);
    if (shapeError) {
      return this.reject("schema_error", { message: shapeError }, metadata);
    }
    const speed = firstSpeedViolation(problem, trajectory);
    if (speed) {
      return this.reject("speed_limit_exceeded", { ...speed, repair: diagnoseTrajectoryRepair(problem) }, metadata);
    }
    const collision = firstCollisionViolation(problem, trajectory);
    if (collision) {
      return this.reject("collision", { ...collision, repair: diagnoseTrajectoryRepair(problem) }, metadata);
    }
    return hardAccept(this.verifierId, this.verifierVersion, {
      ...metadata,
      minClearance: minClearance(problem, trajectory),
      pathLength: pathLength(trajectory),
    });
  }

  applyCommit(state                      , candidate                                        )                       {
    const current = normalizeRobotState(state);
    const problem = normalizeRobotProblem(candidate.payload.problem);
    if (!robotProblemsEqual(current.problem, problem)) {
      throw new Error("candidate problem does not match current robot trajectory state");
    }
    return { problem, solved: true, trajectory: normalizeTrajectory(candidate.payload.trajectory) };
  }

  replay(state                      , receipt         )                       {
    const current = normalizeRobotState(state);
    const payload = (receipt.replayBundle                                                ).candidatePayload;
    const problem = normalizeRobotProblem(payload.problem);
    if (!robotProblemsEqual(current.problem, problem)) {
      throw new Error("receipt problem does not match replay robot trajectory state");
    }
    return { problem, solved: true, trajectory: normalizeTrajectory(payload.trajectory) };
  }

  rollback(_state                      , receipt         )                       {
    return normalizeRobotState((receipt.rollbackBundle                                      ).preState);
  }

          reject(kind                       , residual                             , metadata                         )                     {
    return hardReject(this.verifierId, this.verifierVersion, { kind, ...residual }, metadata);
  }
}

export class RobotResidualRepairer {
  rejectedResiduals = new Map                ();
  acceptedDetours = new Map                ();

  update(receipt         )       {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload
      : {};
    if (receipt.hardResult.result === "accept") {
      const key = String(payload.detourY ?? "unknown");
      this.acceptedDetours.set(key, (this.acceptedDetours.get(key) ?? 0) + 1);
      return;
    }
    if (receipt.hardResult.result === "reject" && isRobotResidual(receipt.hardResult.residual)) {
      const kind = receipt.hardResult.residual.kind;
      this.rejectedResiduals.set(kind, (this.rejectedResiduals.get(kind) ?? 0) + 1);
    }
  }

  async propose(candidate                                        , residual         )                                                         {
    if (!isRobotResidual(residual) || !residual.repair) {
      return null;
    }
    const currentDetour = numberValue(candidate.payload.detourY, "detourY");
    if (Math.abs(residual.repair.detourY - currentDetour) <= ROBOT_EPSILON) {
      return null;
    }
    return makeRobotTrajectoryCandidate(
      normalizeRobotProblem(candidate.payload.problem),
      residual.repair.detourY,
      candidate.payload.context || "robot-repair",
      candidate.payload.cost + 1,
    );
  }
}

export function normalizePoint(pointInput                                                     )         {
  if (Array.isArray(pointInput)) {
    if (pointInput.length !== 2) {
      throw new RangeError("point must have two coordinates");
    }
    return { x: numberValue(pointInput[0], "point.x"), y: numberValue(pointInput[1], "point.y") };
  }
  const raw = pointInput                           ;
  return { x: numberValue(raw.x, "point.x"), y: numberValue(raw.y, "point.y") };
}

export function normalizeObstacle(obstacleInput                                          )                 {
  const raw = obstacleInput                           ;
  const obstacleId = raw.obstacleId ?? raw.obstacle_id;
  if (typeof obstacleId !== "string" || obstacleId.length === 0) {
    throw new RangeError("obstacleId must be non-empty");
  }
  const radius = numberValue(raw.radius, "obstacle radius");
  if (radius <= 0) {
    throw new RangeError("obstacle radius must be positive");
  }
  return { obstacleId, center: normalizePoint(raw.center                                                       ), radius };
}

export function normalizeRobotProblem(problemInput                                                  )                         {
  const raw = problemInput                           ;
  const boundsInput = raw.bounds;
  if (!Array.isArray(boundsInput) || boundsInput.length !== 4) {
    throw new RangeError("bounds must be [minX, minY, maxX, maxY]");
  }
  const bounds = boundsInput.map((value) => numberValue(value, "bounds"))                                    ;
  const [minX, minY, maxX, maxY] = bounds;
  if (!(minX < maxX) || !(minY < maxY)) {
    throw new RangeError("bounds must define a positive rectangle");
  }
  const robotRadius = numberValue(raw.robotRadius ?? raw.robot_radius, "robotRadius");
  const clearance = numberValue(raw.clearance, "clearance");
  const maxStep = numberValue(raw.maxStep ?? raw.max_step, "maxStep");
  if (robotRadius <= 0 || clearance < 0 || maxStep <= 0) {
    throw new RangeError("robotRadius and maxStep must be positive; clearance must be non-negative");
  }
  const allowedInput = raw.allowedDetourY ?? raw.allowed_detour_y ?? DEFAULT_DETOUR_Y;
  if (!Array.isArray(allowedInput) || allowedInput.length === 0) {
    throw new RangeError("allowedDetourY must be a non-empty array");
  }
  const allowedDetourY = allowedInput.map((value) => numberValue(value, "detourY"));
  if (new Set(allowedDetourY).size !== allowedDetourY.length) {
    throw new RangeError("allowedDetourY must be unique");
  }
  const obstaclesInput = raw.obstacles;
  if (!Array.isArray(obstaclesInput) || obstaclesInput.length === 0) {
    throw new RangeError("at least one obstacle is required for this G1 canary");
  }
  const out                         = {
    start: normalizePoint(raw.start                                                       ),
    goal: normalizePoint(raw.goal                                                       ),
    obstacles: obstaclesInput.map((obstacle) => normalizeObstacle(obstacle                                            )),
    robotRadius,
    clearance,
    maxStep,
    bounds,
    allowedDetourY,
  };
  if (!pointInBounds(out.start, out.bounds) || !pointInBounds(out.goal, out.bounds)) {
    throw new RangeError("start and goal must be inside bounds");
  }
  return out;
}

export function normalizeRobotState(stateInput                                                )                       {
  const raw = stateInput                           ;
  return {
    problem: normalizeRobotProblem(raw.problem                                                    ),
    solved: Boolean(raw.solved),
    trajectory: raw.trajectory == null ? null : normalizeTrajectory(raw.trajectory                                             ),
  };
}

export function normalizeTrajectory(trajectoryInput                                                            )           {
  if (!Array.isArray(trajectoryInput) || trajectoryInput.length < 2) {
    throw new RangeError("trajectory must contain at least start and goal");
  }
  return trajectoryInput.map((point) => normalizePoint(point));
}

export function canonicalTrajectory(problemInput                        , detourYInput        )           {
  const problem = normalizeRobotProblem(problemInput);
  const detourY = numberValue(detourYInput, "detourY");
  return [
    problem.start,
    { x: 0.35, y: detourY },
    { x: 0.65, y: detourY },
    problem.goal,
  ];
}

export function distance(aInput        , bInput        )         {
  const a = normalizePoint(aInput);
  const b = normalizePoint(bInput);
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function segmentDistance(pointInput        , startInput        , endInput        )         {
  const point = normalizePoint(pointInput);
  const start = normalizePoint(startInput);
  const end = normalizePoint(endInput);
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSq = dx * dx + dy * dy;
  if (lengthSq <= ROBOT_EPSILON) {
    return distance(point, start);
  }
  const rawT = ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSq;
  const t = Math.max(0, Math.min(1, rawT));
  const nearest = { x: start.x + t * dx, y: start.y + t * dy };
  return distance(point, nearest);
}

export function pathLength(trajectoryInput          )         {
  const trajectory = normalizeTrajectory(trajectoryInput);
  let total = 0;
  for (let idx = 0; idx < trajectory.length - 1; idx += 1) {
    total += distance(trajectory[idx], trajectory[idx + 1]);
  }
  return total;
}

export function effectiveObstacleRadius(problemInput                        , obstacleInput                )         {
  const problem = normalizeRobotProblem(problemInput);
  const obstacle = normalizeObstacle(obstacleInput);
  return problem.robotRadius + problem.clearance + obstacle.radius;
}

export function minClearance(problemInput                        , trajectoryInput          )         {
  const problem = normalizeRobotProblem(problemInput);
  const trajectory = normalizeTrajectory(trajectoryInput);
  let best = Number.POSITIVE_INFINITY;
  for (let idx = 0; idx < trajectory.length - 1; idx += 1) {
    for (const obstacle of problem.obstacles) {
      const clearance = segmentDistance(obstacle.center, trajectory[idx], trajectory[idx + 1]) - effectiveObstacleRadius(problem, obstacle);
      best = Math.min(best, clearance);
    }
  }
  return best;
}

export function firstSpeedViolation(problemInput                        , trajectoryInput          )                                                {
  const problem = normalizeRobotProblem(problemInput);
  const trajectory = normalizeTrajectory(trajectoryInput);
  for (let idx = 0; idx < trajectory.length - 1; idx += 1) {
    const step = distance(trajectory[idx], trajectory[idx + 1]);
    if (step > problem.maxStep + ROBOT_EPSILON) {
      return { segmentIndex: idx, distance: step, maxStep: problem.maxStep };
    }
  }
  return null;
}

export function firstCollisionViolation(problemInput                        , trajectoryInput          )                                                {
  const problem = normalizeRobotProblem(problemInput);
  const trajectory = normalizeTrajectory(trajectoryInput);
  for (let idx = 0; idx < trajectory.length - 1; idx += 1) {
    for (const obstacle of problem.obstacles) {
      const observed = segmentDistance(obstacle.center, trajectory[idx], trajectory[idx + 1]);
      const required = effectiveObstacleRadius(problem, obstacle);
      if (observed < required - ROBOT_EPSILON) {
        return {
          segmentIndex: idx,
          obstacleId: obstacle.obstacleId,
          distance: observed,
          requiredDistance: required,
          penetration: required - observed,
        };
      }
    }
  }
  return null;
}

export function trajectoryIsSafe(problemInput                        , trajectoryInput          )          {
  const problem = normalizeRobotProblem(problemInput);
  const trajectory = normalizeTrajectory(trajectoryInput);
  const detourY = trajectory[1]?.y;
  return (
    typeof detourY === "number"
    && candidateShapeError(problem, trajectory, detourY) === null
    && firstSpeedViolation(problem, trajectory) === null
    && firstCollisionViolation(problem, trajectory) === null
  );
}

export function diagnoseTrajectoryRepair(problemInput                        )                          {
  const problem = normalizeRobotProblem(problemInput);
  for (const detourY of problem.allowedDetourY) {
    const trajectory = canonicalTrajectory(problem, detourY);
    if (firstSpeedViolation(problem, trajectory) === null && firstCollisionViolation(problem, trajectory) === null) {
      return {
        detourY,
        trajectory,
        minClearance: minClearance(problem, trajectory),
        pathLength: pathLength(trajectory),
      };
    }
  }
  return null;
}

export async function makeRobotTrajectoryCandidate(
  problemInput                        ,
  detourYInput        ,
  context = "robot-trajectory",
  cost = 1,
)                                                  {
  const problem = normalizeRobotProblem(problemInput);
  const detourY = numberValue(detourYInput, "detourY");
  const trajectory = canonicalTrajectory(problem, detourY);
  return makeCandidate(
    {
      context,
      problem,
      trajectory,
      detourY,
      cost,
    },
    "robot.point2_trajectory_tube",
    "robot.point2_trajectory_tube.v1",
    {
      problem: await stableHash(problem),
      trajectory: await stableHash(trajectory),
      detourY: await stableHash(detourY),
    },
  );
}

export function makeRobotTrajectoryProblem(effectiveRadiusInput = 0.24, maxStepInput = 0.46)                         {
  const effectiveRadius = numberValue(effectiveRadiusInput, "effectiveRadius");
  const robotRadius = 0.04;
  const clearance = 0.02;
  const obstacleRadius = effectiveRadius - robotRadius - clearance;
  if (obstacleRadius <= 0) {
    throw new RangeError("effective radius must exceed robot radius plus clearance");
  }
  return {
    start: { x: 0.10, y: 0.50 },
    goal: { x: 0.90, y: 0.50 },
    obstacles: [{ obstacleId: "obs0", center: { x: 0.50, y: 0.50 }, radius: obstacleRadius }],
    robotRadius,
    clearance,
    maxStep: maxStepInput,
    bounds: [0, 0, 1, 1],
    allowedDetourY: [...DEFAULT_DETOUR_Y],
  };
}

export async function runStaticRobotEpisode(
  problemInput                        ,
  detourOrder          ,
  ledger        ,
  episode        ,
)                                        {
  const problem = normalizeRobotProblem(problemInput);
  const engine = new TransactionEngine(new RobotTrajectoryAdapter(), ledger);
  const state                       = { problem, solved: false, trajectory: null };
  for (let idx = 0; idx < detourOrder.length; idx += 1) {
    const detourY = numberValue(detourOrder[idx], "detourY");
    const candidate = await makeRobotTrajectoryCandidate(problem, detourY, "robot-static", idx + 1);
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `robot-static-${episode}-${idx + 1}`,
        actions: [{ detourY }],
        seeds: [episode, idx + 1],
        modelVersion: "robot.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return episodeResult(idx + 1, true, engine, state);
    }
  }
  return episodeResult(detourOrder.length, false, engine, state);
}

export async function runRepairRobotEpisode(
  problemInput                        ,
  ledger        ,
  repairer                       ,
  episode        ,
  initialDetourY = 0.5,
)                                        {
  const problem = normalizeRobotProblem(problemInput);
  const engine = new TransactionEngine(new RobotTrajectoryAdapter(), ledger);
  const state                       = { problem, solved: false, trajectory: null };
  let candidate = await makeRobotTrajectoryCandidate(problem, initialDetourY, "robot-repair", 1);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `robot-repair-${episode}-${attempt}`,
        actions: [{ detourY: candidate.payload.detourY }],
        seeds: [episode, attempt],
        modelVersion: "robot.residual_repair.v1",
      }),
      candidate,
    );
    repairer.update(outcome.receipt);
    if (outcome.committed) {
      return episodeResult(attempt + 1, true, engine, state);
    }
    const repaired = await repairer.propose(candidate, outcome.receipt.hardResult.residual);
    if (!repaired) {
      return episodeResult(attempt + 1, false, engine, state);
    }
    candidate = repaired;
  }
  return episodeResult(3, false, engine, state);
}

export async function runRobotTrajectoryBenchmark(seed = 67, episodes = 45)                                 {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  const radii = shuffle([...DEFAULT_EFFECTIVE_RADII], seed);
  const staticResults                                 = [];
  const repairResults                                 = [];
  const staticLedgers           = [];
  const repairLedgers           = [];
  const repairer = new RobotResidualRepairer();
  for (let episode = 0; episode < episodes; episode += 1) {
    const problem = makeRobotTrajectoryProblem(radii[episode % radii.length]);
    const staticLedger = new Ledger();
    const repairLedger = new Ledger();
    staticLedgers.push(staticLedger);
    repairLedgers.push(repairLedger);
    staticResults.push(await runStaticRobotEpisode(problem, DEFAULT_DETOUR_Y, staticLedger, episode));
    repairResults.push(await runRepairRobotEpisode(problem, repairLedger, repairer, episode));
  }
  const allResults = [...staticResults, ...repairResults];
  const staticCps = callsPerSuccess(staticResults);
  const repairCps = callsPerSuccess(repairResults);
  return {
    episodes,
    candidateSpaceSize: DEFAULT_DETOUR_Y.length,
    staticCallsPerSuccess: staticCps,
    repairCallsPerSuccess: repairCps,
    repairGain: staticCps / repairCps,
    repairSuccessRate: repairResults.filter((row) => row.success).length / repairResults.length,
    ledgerAuditRate: allResults.filter((row) => row.auditOk).length / allResults.length,
    replayRollbackRate: allResults.filter((row) => row.replayRollbackOk).length / allResults.length,
    invalidCommitCount: invalidCommits([...staticLedgers, ...repairLedgers]),
    learnedResidualKinds: Object.fromEntries(repairer.rejectedResiduals),
  };
}

function candidateShapeError(problem                        , trajectory          , detourY        )                {
  if (!problem.allowedDetourY.includes(detourY)) {
    return "detourY is not in the allowed shield action set";
  }
  const expected = canonicalTrajectory(problem, detourY);
  if (trajectory.length !== expected.length || !trajectory.every((point, idx) => distance(point, expected[idx]) <= ROBOT_EPSILON)) {
    return "trajectory must match the canonical detour corridor for detourY";
  }
  if (distance(trajectory[0], problem.start) > ROBOT_EPSILON) {
    return "trajectory must start at the problem start";
  }
  if (distance(trajectory[trajectory.length - 1], problem.goal) > ROBOT_EPSILON) {
    return "trajectory must end at the problem goal";
  }
  for (const point of trajectory) {
    if (!pointInBounds(point, problem.bounds)) {
      return "all waypoints must stay inside bounds";
    }
  }
  return null;
}

async function episodeResult(
  calls        ,
  success         ,
  engine                                                                 ,
  seedState                      ,
)                                        {
  const auditOk = await engine.ledger.audit();
  let replayRollbackOk = false;
  if (auditOk) {
    try {
      await engine.replayAudit(seedState);
      replayRollbackOk = robotStatesEqual(await engine.rollbackAudit(seedState), seedState);
    } catch (_error) {
      replayRollbackOk = false;
    }
  }
  return { calls, success, auditOk, replayRollbackOk };
}

function pointInBounds(point        , bounds                                  )          {
  const [minX, minY, maxX, maxY] = bounds;
  return minX - ROBOT_EPSILON <= point.x && point.x <= maxX + ROBOT_EPSILON
    && minY - ROBOT_EPSILON <= point.y && point.y <= maxY + ROBOT_EPSILON;
}

function numberValue(value         , label        )         {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new RangeError(`${label} must be finite numeric`);
  }
  return value;
}

function isRobotResidual(value         )                         {
  if (!value || typeof value !== "object") {
    return false;
  }
  const residual = value                          ;
  return residual.kind === "schema_error" || residual.kind === "speed_limit_exceeded" || residual.kind === "collision";
}

function robotProblemsEqual(a                        , b                        )          {
  return JSON.stringify(normalizeRobotProblem(a)) === JSON.stringify(normalizeRobotProblem(b));
}

function robotStatesEqual(a                      , b                      )          {
  return JSON.stringify(normalizeRobotState(a)) === JSON.stringify(normalizeRobotState(b));
}

function callsPerSuccess(results                                )         {
  const successes = results.filter((row) => row.success).length;
  const calls = results.reduce((sum, row) => sum + row.calls, 0);
  return successes === 0 ? Number.POSITIVE_INFINITY : calls / successes;
}

function invalidCommits(ledgers          )         {
  return ledgers.reduce((sum, ledger) =>
    sum + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  0);
}

function shuffle   (values     , seed        )      {
  const rng = mulberry32(seed);
  const out = [...values];
  for (let idx = out.length - 1; idx > 0; idx -= 1) {
    const swap = Math.floor(rng() * (idx + 1));
    [out[idx], out[swap]] = [out[swap], out[idx]];
  }
  return out;
}

function mulberry32(seed        )               {
  let t = seed >>> 0;
  return () => {
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}
