import {
  type HardVerifierResult,
  type Receipt,
  type ReplayRollbackAdapter,
  type TypedCandidate,
  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import {
  BranchRuntime,
  auditBranchSelection,
  branchSelectionCertificateHash,
  buildBranchSelectionCertificate,
  validateBranchSelectionCertificate,
} from "./branch.js";

export interface BranchSelectionReport {
  schemaVersion: string;
  branchCount: number;
  acceptedCount: number;
  rejectedCount: number;
  abstainedCount: number;
  selectedIndex: number | null;
  committedIndex: number | null;
  loserCount: number;
  hardRejectSoftRankBlocked: boolean;
  rankAfterHardFilter: boolean;
  certificateValid: boolean;
  auditValid: boolean;
  tamperDetected: boolean;
  invalidRankerCertificateValid: boolean;
  invalidRankerCommitted: boolean;
  verifierCalls: number;
  invalidCommitCount: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
}

interface BranchDeltaPayload {
  delta: number;
  cost?: number;
  softRank?: number;
}

class CounterAdapter implements ReplayRollbackAdapter<number, BranchDeltaPayload> {
  verifierId = "branch_counter_oracle";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<BranchDeltaPayload>): HardVerifierResult {
    const cost = candidate.payload.cost ?? 0;
    return candidate.payload.delta <= 5
      ? hardAccept(this.verifierId, this.verifierVersion, { cost })
      : hardReject(this.verifierId, this.verifierVersion, { delta: candidate.payload.delta, limit: 5 }, { cost });
  }

  applyCommit(state: number, candidate: TypedCandidate<BranchDeltaPayload>): number {
    return state + candidate.payload.delta;
  }

  replay(state: number, receipt: Receipt): number {
    const payload = (receipt.replayBundle as { candidatePayload: BranchDeltaPayload }).candidatePayload;
    return state + payload.delta;
  }

  rollback(_state: number, receipt: Receipt): number {
    return (receipt.rollbackBundle as { preState: number }).preState;
  }
}

class CounterProjector {
  project(_state: number, trace: ReturnType<typeof makeTrace>): TypedCandidate<BranchDeltaPayload> {
    const payload = trace.actions[trace.actions.length - 1] as BranchDeltaPayload;
    return makeCandidate({ ...payload }, "counter.delta", "counter.delta.v1");
  }
}

export async function runBranchSelectionBenchmark(): Promise<BranchSelectionReport> {
  const engine = new TransactionEngine(new CounterAdapter(), new Ledger());
  const traces = [
    makeTrace({
      branchId: "rejected-soft-favorite",
      actions: [{ delta: 9, cost: 1, softRank: 999 }],
      seeds: [1],
      modelVersion: "branch.selection.v1",
    }),
    makeTrace({
      branchId: "accepted-loser",
      actions: [{ delta: 1, cost: 4 }],
      seeds: [2],
      modelVersion: "branch.selection.v1",
    }),
    makeTrace({
      branchId: "accepted-winner",
      actions: [{ delta: 2, cost: 2 }],
      seeds: [3],
      modelVersion: "branch.selection.v1",
    }),
  ];
  const outcome = await new BranchRuntime(engine, new CounterProjector()).step(0, traces);
  const receipts = outcome.receipts as Receipt[];
  const certificate = await buildBranchSelectionCertificate(receipts, { verifierCallCount: outcome.verifierCalls });
  const tampered = { ...certificate, committedIndex: 0, certificateHash: "" };
  tampered.certificateHash = await branchSelectionCertificateHash(tampered);

  const invalidEngine = new TransactionEngine(new CounterAdapter(), new Ledger());
  const invalidOutcome = await new BranchRuntime(
    invalidEngine,
    new CounterProjector(),
    { choose: (verified) => verified.length },
  ).step(0, [
    makeTrace({ branchId: "bad-ranker-a", actions: [{ delta: 1, cost: 1 }], seeds: [4] }),
    makeTrace({ branchId: "bad-ranker-b", actions: [{ delta: 2, cost: 2 }], seeds: [5] }),
  ]);
  const invalidCertificate = await buildBranchSelectionCertificate(
    invalidOutcome.receipts as Receipt[],
    { verifierCallCount: invalidOutcome.verifierCalls },
  );
  const replayChecks = [
    await replayRollbackOk(engine, 0, outcome.state),
    await replayRollbackOk(invalidEngine, 0, invalidOutcome.state),
  ];

  return {
    schemaVersion: certificate.schemaVersion,
    branchCount: certificate.branchCount,
    acceptedCount: certificate.acceptedIndices.length,
    rejectedCount: certificate.rejectedIndices.length,
    abstainedCount: certificate.abstainedIndices.length,
    selectedIndex: certificate.selectedIndex,
    committedIndex: certificate.committedIndex,
    loserCount: certificate.loserIndices.length,
    hardRejectSoftRankBlocked: engine.ledger.rows[0].hardResult.result === "reject"
      && !engine.ledger.rows[0].committed
      && engine.ledger.rows[0].commitDecision === "hard_reject",
    rankAfterHardFilter: (
      certificate.selectedIndex !== null
      && certificate.committedIndex !== null
      && certificate.acceptedIndices.includes(certificate.selectedIndex)
      && certificate.acceptedIndices.includes(certificate.committedIndex)
      && !certificate.acceptedIndices.includes(0)
    ),
    certificateValid: await validateBranchSelectionCertificate(certificate),
    auditValid: await auditBranchSelection(receipts, certificate),
    tamperDetected: !await validateBranchSelectionCertificate(tampered),
    invalidRankerCertificateValid: await validateBranchSelectionCertificate(invalidCertificate),
    invalidRankerCommitted: invalidOutcome.committed,
    verifierCalls: outcome.verifierCalls,
    invalidCommitCount: engine.invalidCommitCount + invalidEngine.invalidCommitCount,
    ledgerAudit: await engine.ledger.audit() && await invalidEngine.ledger.audit(),
    replayRollbackRate: replayChecks.filter(Boolean).length / replayChecks.length,
  };
}

async function replayRollbackOk(
  engine: TransactionEngine<number, BranchDeltaPayload>,
  seedState: number,
  expectedState: number,
): Promise<boolean> {
  if (!await engine.ledger.audit()) {
    return false;
  }
  return await engine.replayAudit(seedState) === expectedState && await engine.rollbackAudit(seedState) === seedState;
}
