import { TransactionEngine, makeTrace } from "./core.js";
import { stableHash } from "./canonical.js";
import {
  TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA,
  ProgrammableSubstrate,
  TransferGuardedDomainRouter,
  transferGuardedDomainRouteHash,
  validateTransferGuardedDomainRoute,
} from "./sdk.js";
import {


  InventoryReservationAdapter,
  makeReservationCandidate,
} from "./operations.js";
import { buildTransferEvaluationCertificate, validateTransferGuardSnapshot } from "./transfer.js";






























export async function runSdkTransferGuardBenchmark()                                  {
  const router = new TransferGuardedDomainRouter();
  const substrate = new ProgrammableSubstrate(router);
  substrate.register("source_policy", new InventoryReservationAdapter());
  substrate.register("target_policy", new InventoryReservationAdapter());

  const sourceSeed                 = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const targetSeed                 = { stock: { widget: 2 }, reserved: { widget: 0 }, committedOrders: [] };
  const sourceResult = await substrate.submit(
    "source_policy",
    sourceSeed,
    makeTrace({
      branchId: "sdk-transfer-source-policy",
      actions: [{ label: "quantity-5" }],
      seeds: ["sdk-transfer", "source"],
      modelVersion: "sdk.transfer.source.v1",
    }),
    await makeReservationCandidate(sourceSeed, "sdk-transfer-source-q5", "widget", 5, 5, "sdk-transfer", 1),
    { context: "sdk-transfer" },
  );
  const sourceReceipt = sourceResult.receipt;
  const baseRanked = router.rank("sdk-transfer", ["source_policy", "target_policy"]);

  const evalTransferEngine = new TransactionEngine(new InventoryReservationAdapter());
  const evalTransfer = await evalTransferEngine.transact(
    targetSeed,
    makeTrace({
      branchId: "sdk-transfer-eval-source-policy",
      actions: [{ label: "quantity-5" }],
      seeds: ["sdk-transfer", "eval-source"],
      modelVersion: "sdk.transfer.eval_source.v1",
    }),
    await makeReservationCandidate(targetSeed, "sdk-transfer-eval-q5", "widget", 5, 5, "sdk-transfer-eval", 1),
  );
  const evalBaselineEngine = new TransactionEngine(new InventoryReservationAdapter());
  const evalBaseline = await evalBaselineEngine.transact(
    targetSeed,
    makeTrace({
      branchId: "sdk-transfer-eval-target-policy",
      actions: [{ label: "quantity-2" }],
      seeds: ["sdk-transfer", "eval-target"],
      modelVersion: "sdk.transfer.eval_target.v1",
    }),
    await makeReservationCandidate(targetSeed, "sdk-transfer-eval-q2", "widget", 5, 2, "sdk-transfer-eval", 1),
  );
  const sourceLedger = substrate.domain                                             ("source_policy").ledger;
  const certificate = await buildTransferEvaluationCertificate({
    claimId: "sdk_transfer_guard_blocks_source_policy",
    learnerId: "sdk_receipt_router_source_policy",
    learnerSnapshotHash: await stableHash({ sourcePolicyReceipt: sourceReceipt.receiptHash }),
    sourceDomains: ["source_policy"],
    targetDomains: ["target_inventory"],
    sourceReceiptHashes: [sourceReceipt.receiptHash],
    targetEvaluationReceiptHashes: [evalTransfer.receipt.receiptHash, evalBaseline.receipt.receiptHash],
    baselineName: "target_policy_quantity_2",
    transferName: "source_policy_quantity_5",
    baselineSuccessCount: evalBaseline.committed ? 1 : 0,
    transferSuccessCount: evalTransfer.committed ? 1 : 0,
    baselineVerifierCalls: evalBaselineEngine.hardVerifierCalls,
    transferVerifierCalls: evalTransferEngine.hardVerifierCalls,
    sameCaseBaseline: true,
    hardCommitOnly: [sourceReceipt, evalTransfer.receipt, evalBaseline.receipt].every((receipt) => receipt.committed === (receipt.hardResult.result === "accept")),
    invalidCommitCount: substrate.invalidCommitCount() + evalTransferEngine.invalidCommitCount + evalBaselineEngine.invalidCommitCount,
    ledgerAudit: await sourceLedger.audit() && await evalTransferEngine.ledger.audit() && await evalBaselineEngine.ledger.audit(),
    replayRollbackRate: await replayRollbackRateFor([
      [new TransactionEngine(new InventoryReservationAdapter(), sourceLedger), sourceSeed],
      [evalTransferEngine, targetSeed],
      [evalBaselineEngine, targetSeed],
    ]),
  });
  await router.updateTransferCertificate(certificate);
  const route = await router.rankWithTransferGuard(
    "sdk-transfer",
    ["source_policy", "target_policy"],
    ["source_policy"],
    "target_inventory",
  );
  const snapshot = await router.guardSnapshot();
  const tampered = {
    ...route,
    blockedDomainIds: [],
    sourceBlocked: false,
    routeHash: "",
  };
  tampered.routeHash = await transferGuardedDomainRouteHash(tampered);

  const unguardedEngine = new TransactionEngine(new InventoryReservationAdapter());
  const unguardedSelected = selectionForDomain(baseRanked[0]);
  const unguarded = await unguardedEngine.transact(
    targetSeed,
    makeTrace({
      branchId: "sdk-transfer-unguarded",
      actions: [{ label: unguardedSelected }],
      seeds: ["sdk-transfer", "unguarded"],
      modelVersion: "sdk.transfer.unguarded.v1",
    }),
    await candidateForSelection(targetSeed, "sdk-transfer-unguarded", unguardedSelected),
  );
  const guardedEngine = new TransactionEngine(new InventoryReservationAdapter());
  const guardedSelected = selectionForDomain(route.topDomainId);
  const guarded = await guardedEngine.transact(
    targetSeed,
    makeTrace({
      branchId: "sdk-transfer-guarded",
      actions: [{ label: guardedSelected }],
      seeds: ["sdk-transfer", "guarded"],
      modelVersion: "sdk.transfer.guarded.v1",
    }),
    await candidateForSelection(targetSeed, "sdk-transfer-guarded", guardedSelected),
  );
  const residual = unguarded.receipt.hardResult.residual;
  const unguardedResidualKind = residual && typeof residual === "object"
    ? String((residual                      ).kind ?? "")
    : "";
  const engines                                                                                          = [
    [new TransactionEngine(new InventoryReservationAdapter(), sourceLedger), sourceSeed],
    [evalTransferEngine, targetSeed],
    [evalBaselineEngine, targetSeed],
    [unguardedEngine, targetSeed],
    [guardedEngine, targetSeed],
  ];
  const ledgerAudit = await sourceLedger.audit()
    && await evalTransferEngine.ledger.audit()
    && await evalBaselineEngine.ledger.audit()
    && await unguardedEngine.ledger.audit()
    && await guardedEngine.ledger.audit();

  return {
    schemaVersion: TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA,
    routeValid: await validateTransferGuardedDomainRoute(route),
    snapshotValid: await validateTransferGuardSnapshot(snapshot),
    baseRouterTopDomain: baseRanked[0],
    guardedRouterTopDomain: route.topDomainId,
    baseRankedDomainIds: baseRanked,
    guardedRankedDomainIds: route.rankedDomainIds,
    blockedDomainIds: route.blockedDomainIds,
    sourceBlocked: route.sourceBlocked,
    guardReorderedToTarget: baseRanked[0] === "source_policy" && route.topDomainId === "target_policy",
    decisionReason: route.decisionReason,
    decisionAdmitted: route.decisionAdmitted,
    unguardedSelected,
    unguardedCommitted: unguarded.committed,
    unguardedResidualKind,
    guardedSelected,
    guardedCommitted: guarded.committed,
    avoidedNegativeTransfer: !unguarded.committed && guarded.committed && route.topDomainId === "target_policy",
    certificateConclusion: certificate.conclusion,
    routeHash: route.routeHash,
    decisionHash: route.decisionHash,
    snapshotHash: snapshot.snapshotHash,
    tamperDetected: !await validateTransferGuardedDomainRoute(tampered),
    invalidCommitCount: substrate.invalidCommitCount()
      + evalTransferEngine.invalidCommitCount
      + evalBaselineEngine.invalidCommitCount
      + unguardedEngine.invalidCommitCount
      + guardedEngine.invalidCommitCount,
    ledgerAudit,
    replayRollbackRate: await replayRollbackRateFor(engines),
  };
}

function selectionForDomain(domainId        )         {
  return domainId === "source_policy" ? "quantity-5" : "quantity-2";
}

async function candidateForSelection(state                , prefix        , selection        ) {
  const quantity = selection === "quantity-5" ? 5 : 2;
  return makeReservationCandidate(state, `${prefix}-${selection}`, "widget", 5, quantity, "sdk-transfer", 1);
}

async function replayRollbackRateFor(rows                                                                                         )                  {
  let ok = 0;
  for (const [engine, state] of rows) {
    try {
      if (await engine.ledger.audit()) {
        await engine.replayAudit(state);
        if (JSON.stringify(await engine.rollbackAudit(state)) === JSON.stringify(state)) {
          ok += 1;
        }
      }
    } catch (_error) {
      // Leave this row failed.
    }
  }
  return ok / rows.length;
}
