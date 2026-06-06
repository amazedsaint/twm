import assert from "node:assert/strict";
import test from "node:test";

import {
  PROJECTION_PROJECTOR_ID,
  PROJECTION_PROJECTOR_VERSION,
  ProjectionContractProjector,
  ProjectionGuardAdapter,
  STOPPING_PROJECTION_CONTRACT,
  buildProjectionManifest,
  makeProjectionContractTraces,
  makeProjectionGuardCandidate,
  normalizeProjectionManifest,
  runProjectionContractBenchmark,
  stoppingMarginNumerator,
  validateProjectionContract,
} from "../dist/index.js";

test("projection contract detects omitted safety field", async () => {
  const state = { distanceToObstacle: 5, brakeAccel: 2, safetyClearance: 2, committedModes: [] };
  const projector = new ProjectionContractProjector();
  const partial = await projector.project(state, makeProjectionContractTraces()[0]);

  const unguarded = await new ProjectionGuardAdapter(state, { enforceContract: false }).verify(partial);
  const guarded = await new ProjectionGuardAdapter(state).verify(partial);

  assert.equal(unguarded.result, "accept");
  assert.equal(guarded.result, "reject");
  assert.deepEqual(guarded.residual.missingFields, ["safetyClearance"]);
});

test("projection contract rejects stale manifest hashes", async () => {
  const source = { distanceToObstacle: 5, brakeAccel: 2, safetyClearance: 2 };
  const manifest = await buildProjectionManifest(source, ["distanceToObstacle", "brakeAccel", "safetyClearance"], {
    projectorId: PROJECTION_PROJECTOR_ID,
    projectorVersion: PROJECTION_PROJECTOR_VERSION,
  });
  const audit = await validateProjectionContract(
    STOPPING_PROJECTION_CONTRACT,
    manifest,
    { distanceToObstacle: 4, brakeAccel: 2, safetyClearance: 2 },
  );

  assert.equal(audit.accepted, false);
  assert.deepEqual(audit.staleFields, ["distanceToObstacle"]);
  assert.equal(audit.sourceHashMismatch, true);
});

test("projection manifest hash is recomputed", async () => {
  const source = { distanceToObstacle: 5, brakeAccel: 2, safetyClearance: 2 };
  const manifest = await buildProjectionManifest(source, ["distanceToObstacle", "brakeAccel", "safetyClearance"], {
    projectorId: PROJECTION_PROJECTOR_ID,
    projectorVersion: PROJECTION_PROJECTOR_VERSION,
  });
  const tampered = normalizeProjectionManifest({ ...manifest, projectionHash: "0".repeat(64) });
  const audit = await validateProjectionContract(STOPPING_PROJECTION_CONTRACT, tampered, source);

  assert.equal(audit.accepted, false);
  assert.equal(audit.hashMismatch, true);
});

test("exact integer stopping margin", () => {
  assert.equal(stoppingMarginNumerator({ distance: 5, speed: 4, brake: 2, clearance: 2 }), -4);
  assert.equal(stoppingMarginNumerator({ distance: 5, speed: 2, brake: 2, clearance: 2 }), 8);
});

test("projection contract benchmark metrics", async () => {
  const report = await runProjectionContractBenchmark();

  assert.equal(report.candidateCount, 3);
  assert.equal(report.verifierCalls, 3);
  assert.equal(report.unguardedFalsePositiveAccepts, true);
  assert.equal(report.guardedPartialRejected, true);
  assert.equal(report.guardedFastCompleteRejected, true);
  assert.equal(report.guardedSafeCommit, true);
  assert.deepEqual(report.missingFields, ["safetyClearance"]);
  assert.equal(report.unsafeMarginNumerator, -4);
  assert.equal(report.safeMarginNumerator, 8);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
});

test("complete safe projection verifies", async () => {
  const state = { distanceToObstacle: 5, brakeAccel: 2, safetyClearance: 2, committedModes: [] };
  const candidate = await makeProjectionGuardCandidate(state, {
    mode: "crawl_complete",
    speed: 2,
    cost: 2,
    coveredFields: ["distanceToObstacle", "brakeAccel", "safetyClearance"],
  });
  const result = await new ProjectionGuardAdapter(state).verify(candidate);

  assert.equal(result.result, "accept");
  assert.equal(result.metadata.marginNumerator, 8);
});
