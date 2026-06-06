import assert from "node:assert/strict";
import test from "node:test";

import {
  Ledger,
  RobotResidualRepairer,
  RobotTrajectoryAdapter,
  TransactionEngine,
  diagnoseTrajectoryRepair,
  makeRobotTrajectoryCandidate,
  makeRobotTrajectoryProblem,
  makeTrace,
  minClearance,
  runRepairRobotEpisode,
  runRobotTrajectoryBenchmark,
  runStaticRobotEpisode,
  segmentDistance,
} from "../dist/index.js";

test("robot segment distance uses exact projection", () => {
  const point = { x: 0.5, y: 0.5 };
  const start = { x: 0.35, y: 0.22 };
  const end = { x: 0.65, y: 0.22 };

  assert.equal(segmentDistance(point, start, end), 0.28);
});

test("robot verifier rejects collision with shield repair", async () => {
  const problem = makeRobotTrajectoryProblem(0.24);
  const candidate = await makeRobotTrajectoryCandidate(problem, 0.5);
  const result = new RobotTrajectoryAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "collision");
  assert.equal(result.residual.obstacleId, "obs0");
  assert.equal(result.residual.requiredDistance, 0.24);
  assert.equal(result.residual.repair.detourY, 0.22);
  assert.ok(Math.abs(result.residual.repair.minClearance - 0.04) < 1e-9);
});

test("robot verifier rejects speed limit before collision", async () => {
  const problem = makeRobotTrajectoryProblem(0.24, 0.20);
  const candidate = await makeRobotTrajectoryCandidate(problem, 0.5);
  const result = new RobotTrajectoryAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "speed_limit_exceeded");
  assert.equal(result.residual.segmentIndex, 0);
  assert.equal(result.residual.distance, 0.24999999999999997);
});

test("diagnosed robot detour is safe and cleared", () => {
  const problem = makeRobotTrajectoryProblem(0.24);
  const repair = diagnoseTrajectoryRepair(problem);

  assert.equal(repair.detourY, 0.22);
  assert.ok(minClearance(problem, repair.trajectory) >= 0.04);
});

test("residual robot repair commits after collision feedback", async () => {
  const problem = makeRobotTrajectoryProblem(0.28);
  const ledger = new Ledger();
  const result = await runRepairRobotEpisode(problem, ledger, new RobotResidualRepairer(), 1);

  assert.equal(result.calls, 2);
  assert.equal(result.success, true);
  assert.equal(result.auditOk, true);
  assert.equal(result.replayRollbackOk, true);
  assert.equal(ledger.committedRows().length, 1);
  assert.equal(ledger.committedRows()[0].replayBundle.candidatePayload.detourY, 0.22);
});

test("robot trajectory benchmark improves over static shield search", async () => {
  const report = await runRobotTrajectoryBenchmark(67, 45);

  assert.equal(report.episodes, 45);
  assert.equal(report.candidateSpaceSize, 11);
  assert.equal(report.staticCallsPerSuccess, 8);
  assert.equal(report.repairCallsPerSuccess, 2);
  assert.equal(report.repairGain, 4);
  assert.equal(report.repairSuccessRate, 1);
  assert.equal(report.ledgerAuditRate, 1);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.learnedResidualKinds.collision, 45);
});

test("static robot episode uses same detour candidates", async () => {
  const problem = makeRobotTrajectoryProblem(0.24);
  const result = await runStaticRobotEpisode(problem, [0.5, 0.46, 0.54, 0.22], new Ledger(), 4);

  assert.equal(result.calls, 4);
  assert.equal(result.success, true);
});

test("valid robot trajectory for wrong problem fails closed", async () => {
  const problemA = makeRobotTrajectoryProblem(0.24);
  const problemB = makeRobotTrajectoryProblem(0.31);
  const candidate = await makeRobotTrajectoryCandidate(problemA, 0.22);
  const engine = new TransactionEngine(new RobotTrajectoryAdapter(), new Ledger());
  const outcome = await engine.transact(
    { problem: problemB, solved: false, trajectory: null },
    makeTrace({
      branchId: "wrong-robot-problem",
      actions: [{ detourY: 0.22 }],
      seeds: ["robot", "wrong-problem"],
      modelVersion: "robot.test.v1",
    }),
    candidate,
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason.startsWith("replay_or_rollback_error:"), true);
  assert.equal(engine.invalidCommitCount, 0);
});
