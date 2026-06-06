import assert from "node:assert/strict";
import test from "node:test";

import {
  LifePredecessorAdapter,
  ProgrammableSubstrate,
  ScalarProgramAdapter,
  TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA,
  TransferGuardedDomainRouter,
  buildTransferEvaluationCertificate,
  lifeStep,
  makeLifeCandidate,
  makeScalarCandidate,
  makeTrace,
  runSdkTransferGuardBenchmark,
  runSdkManifestBenchmark,
  runMultiDomainSdkBenchmark,
  validateDomainManifest,
  validateTransferGuardedDomainRoute,
} from "../dist/index.js";

const HASH_A = "a".repeat(64);
const HASH_B = "b".repeat(64);
const HASH_C = "c".repeat(64);

test("multi-domain SDK meets Phase 9 exit gate", async () => {
  const report = await runMultiDomainSdkBenchmark();

  assert.equal(report.domainsSupported, 11);
  assert.equal(report.committedDomains, 11);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.scalarHardCalls, 2);
  assert.equal(report.lifeHardCalls, 2);
  assert.equal(report.gridHardCalls, 1);
  assert.equal(report.sokobanHardCalls, 1);
  assert.equal(report.operationsHardCalls, 1);
  assert.equal(report.proofHardCalls, 1);
  assert.equal(report.circuitHardCalls, 1);
  assert.equal(report.moleculeHardCalls, 1);
  assert.equal(report.codeHardCalls, 1);
  assert.equal(report.robotHardCalls, 1);
  assert.equal(report.chessHardCalls, 1);
  assert.equal(report.routerTopDomain, "scalar");
  assert.deepEqual(report.routerScalarCounts, { accepted: 2, rejected: 0 });
  assert.deepEqual(report.routerLifeCounts, { accepted: 1, rejected: 1 });
  assert.deepEqual(report.routerSokobanCounts, { accepted: 1, rejected: 0 });
  assert.deepEqual(report.routerOperationsCounts, { accepted: 1, rejected: 0 });
  assert.deepEqual(report.routerProofCounts, { accepted: 1, rejected: 0 });
  assert.deepEqual(report.routerCircuitCounts, { accepted: 1, rejected: 0 });
  assert.deepEqual(report.routerMoleculeCounts, { accepted: 1, rejected: 0 });
  assert.deepEqual(report.routerCodeCounts, { accepted: 1, rejected: 0 });
  assert.deepEqual(report.routerRobotCounts, { accepted: 1, rejected: 0 });
  assert.deepEqual(report.routerChessCounts, { accepted: 1, rejected: 0 });
});

test("SDK router ranks domains from receipts without commit authority", async () => {
  const substrate = new ProgrammableSubstrate();
  substrate.register("scalar", new ScalarProgramAdapter());
  substrate.register("life", new LifePredecessorAdapter());

  const scalarState = { episode: 0, target: 7, solved: false };
  const scalar = await substrate.submit(
    "scalar",
    scalarState,
    makeTrace({
      branchId: "router-scalar",
      actions: [{ op: "set", value: 7 }],
      seeds: ["router", "scalar"],
      modelVersion: "sdk.scalar.v1",
    }),
    makeScalarCandidate("router", 7, [{ op: "set", value: 7 }]),
    { context: "router" },
  );

  const target = lifeStep([[0, 0, 0], [1, 1, 1], [0, 0, 0]]);
  const lifeState = { target };
  const badPredecessor = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  const life = await substrate.submit(
    "life",
    lifeState,
    makeTrace({
      branchId: "router-life-reject",
      actions: [{ predecessor: badPredecessor, cost: 1 }],
      seeds: ["router", "life"],
      modelVersion: "sdk.life.v1",
    }),
    await makeLifeCandidate(target, badPredecessor, 1),
    { context: "router" },
  );

  assert.equal(scalar.committed, true);
  assert.equal(life.committed, false);
  assert.deepEqual(substrate.rankDomains("router", ["life", "scalar"]), ["scalar", "life"]);
  assert.equal((await substrate.auditDomain("scalar", scalarState)).ok, true);
  assert.equal(await substrate.domain("life").ledger.audit(), true);
  assert.equal(substrate.invalidCommitCount(), 0);
});

test("transfer guarded router admits positive transfer route", async () => {
  const router = new TransferGuardedDomainRouter();
  const certificate = await buildTransferEvaluationCertificate({
    claimId: "positive-sdk-transfer",
    learnerId: "source-policy",
    learnerSnapshotHash: HASH_A,
    sourceDomains: ["source_policy"],
    targetDomains: ["target_inventory"],
    sourceReceiptHashes: [HASH_B],
    targetEvaluationReceiptHashes: [HASH_C],
    baselineName: "target-baseline",
    transferName: "source-transfer",
    baselineSuccessCount: 1,
    transferSuccessCount: 1,
    baselineVerifierCalls: 2,
    transferVerifierCalls: 1,
    sameCaseBaseline: true,
    hardCommitOnly: true,
    invalidCommitCount: 0,
    ledgerAudit: true,
    replayRollbackRate: 1,
  });
  await router.updateTransferCertificate(certificate);
  const route = await router.rankWithTransferGuard(
    "sdk-transfer",
    ["source_policy", "target_policy"],
    ["source_policy"],
    "target_inventory",
  );

  assert.equal(route.schemaVersion, TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA);
  assert.equal(route.decisionAdmitted, true);
  assert.equal(route.decisionReason, "positive_transfer_certificate");
  assert.deepEqual(route.blockedDomainIds, []);
  assert.equal(route.topDomainId, "source_policy");
  assert.equal(route.sourceBlocked, false);
  assert.equal(await validateTransferGuardedDomainRoute(route), true);
});

test("SDK transfer guard benchmark blocks source policy route", async () => {
  const report = await runSdkTransferGuardBenchmark();

  assert.equal(report.schemaVersion, TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA);
  assert.equal(report.routeValid, true);
  assert.equal(report.snapshotValid, true);
  assert.equal(report.baseRouterTopDomain, "source_policy");
  assert.equal(report.guardedRouterTopDomain, "target_policy");
  assert.deepEqual(report.blockedDomainIds, ["source_policy"]);
  assert.equal(report.sourceBlocked, true);
  assert.equal(report.guardReorderedToTarget, true);
  assert.equal(report.decisionReason, "negative_transfer_certificate");
  assert.equal(report.decisionAdmitted, false);
  assert.equal(report.unguardedSelected, "quantity-5");
  assert.equal(report.unguardedCommitted, false);
  assert.equal(report.unguardedResidualKind, "stock_shortage");
  assert.equal(report.guardedSelected, "quantity-2");
  assert.equal(report.guardedCommitted, true);
  assert.equal(report.avoidedNegativeTransfer, true);
  assert.equal(report.certificateConclusion, "negative_transfer");
  assert.equal(report.tamperDetected, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
});

test("SDK domain manifest binds schema and ledger surface", async () => {
  const substrate = new ProgrammableSubstrate();
  substrate.register("scalar", new ScalarProgramAdapter());
  const state = { episode: 0, target: 7, solved: false };
  await substrate.submit(
    "scalar",
    state,
    makeTrace({
      branchId: "manifest-scalar",
      actions: [{ op: "set", value: 7 }],
      seeds: ["manifest", "scalar"],
      modelVersion: "manifest.scalar.v1",
    }),
    makeScalarCandidate("manifest", 7, [{ op: "set", value: 7 }]),
    { context: "manifest" },
  );

  const manifest = await substrate.domainManifest("scalar");
  const tampered = { ...manifest, verifierId: "tampered", manifestHash: "" };

  assert.equal(manifest.domainId, "scalar");
  assert.equal(manifest.adapterType, "ScalarProgramAdapter");
  assert.equal(manifest.verifierId, "scalar_program_oracle");
  assert.deepEqual(manifest.candidateTypeNames, ["scalar.program"]);
  assert.deepEqual(manifest.projectionSchemaVersions, ["scalar.program.v1"]);
  assert.equal(manifest.receiptCount, 1);
  assert.equal(manifest.committedCount, 1);
  assert.equal(manifest.invalidCommitCount, 0);
  assert.equal(await validateDomainManifest(manifest), true);
  assert.equal(await substrate.auditDomainManifest("scalar", manifest), true);
  assert.equal(await substrate.auditDomainManifest("scalar", tampered), false);
});

test("SDK manifest benchmark reports programmable domain evidence", async () => {
  const report = await runSdkManifestBenchmark();

  assert.equal(report.domainCount, 2);
  assert.equal(report.manifestValidCount, 2);
  assert.equal(report.manifestAuditCount, 2);
  assert.deepEqual(report.scalarCandidateTypes, ["scalar.program"]);
  assert.deepEqual(report.lifeProjectionSchemas, ["game_of_life.predecessor.v1"]);
  assert.equal(report.scalarVerifierId, "scalar_program_oracle");
  assert.equal(report.lifeVerifierId, "life_forward_verifier");
  assert.equal(report.scalarReceiptCount, 1);
  assert.equal(report.lifeReceiptCount, 2);
  assert.equal(report.totalReceiptCount, 3);
  assert.equal(report.acceptedCount, 2);
  assert.equal(report.rejectedCount, 1);
  assert.equal(report.hardVerifierCalls, 3);
  assert.equal(report.totalVerifierCost, 3);
  assert.equal(report.manifestHashesStable, true);
  assert.equal(report.tamperDetected, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
});
