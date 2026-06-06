import {




  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { BranchRuntime, DistributedCommitManager,                    } from "./branch.js";






















export class DistributedCounterAdapter                                                               {
  verifierId = "counter_limit";
  verifierVersion = "1.0";

  verify(candidate                                     )                     {
    const { delta, cost } = candidate.payload;
    return delta <= 5
      ? hardAccept(this.verifierId, this.verifierVersion, { cost })
      : hardReject(this.verifierId, this.verifierVersion, { delta }, { cost });
  }

  applyCommit(state        , candidate                                     )         {
    return state + candidate.payload.delta;
  }

  replay(state        , receipt         )         {
    const payload = (receipt.replayBundle                                             ).candidatePayload;
    return state + payload.delta;
  }

  rollback(_state        , receipt         )         {
    return (receipt.rollbackBundle                        ).preState;
  }
}

class CounterProjector {
  project(_state        , trace                              )                                      {
    const payload = trace.actions[trace.actions.length - 1]                       ;
    return makeCandidate({ delta: payload.delta, cost: payload.cost }, "counter.delta", "counter.delta.v1");
  }
}

export async function runDistributedCounterBenchmark()                                    {
  const traces = [
    makeTrace({ branchId: "worker-accept-high-cost", actions: [{ delta: 4, cost: 9 }], seeds: [1], modelVersion: "counter.worker.v1" }),
    makeTrace({ branchId: "worker-reject", actions: [{ delta: 9, cost: 1 }], seeds: [2], modelVersion: "counter.worker.v1" }),
    makeTrace({ branchId: "worker-accept-low-cost", actions: [{ delta: 2, cost: 1 }], seeds: [3], modelVersion: "counter.worker.v1" }),
  ];
  const localEngine = new TransactionEngine(new DistributedCounterAdapter(), new Ledger());
  const local = await new BranchRuntime(localEngine, new CounterProjector()).step(0, traces);

  const distributedEngine = new TransactionEngine(new DistributedCounterAdapter(), new Ledger());
  const manager = new DistributedCommitManager(distributedEngine);
  const workerReceipts = traces.map((trace) => workerReceipt(distributedEngine.ledger.head, trace));
  const distributed = await manager.commitOne(0, workerReceipts);

  const staleEngine = new TransactionEngine(new DistributedCounterAdapter(), new Ledger());
  const staleManager = new DistributedCommitManager(staleEngine);
  const staleProbe = await staleManager.commitOne(0, [
    {
      parentHead: staleEngine.ledger.head,
      trace: makeTrace({ branchId: "stale-current-reject", actions: [{ delta: 8, cost: 2 }], seeds: [4] }),
      candidate: makeCandidate({ delta: 8, cost: 2 }, "counter.delta", "counter.delta.v1"),
      result: hardReject("counter_limit", "1.0", { delta: 8 }, { cost: 2 }),
    },
    {
      parentHead: "f".repeat(64),
      trace: makeTrace({ branchId: "stale-accepted", actions: [{ delta: 1, cost: 1 }], seeds: [5] }),
      candidate: makeCandidate({ delta: 1, cost: 1 }, "counter.delta", "counter.delta.v1"),
      result: hardAccept("counter_limit", "1.0", { cost: 1 }),
    },
  ]);
  const ledgers = [localEngine.ledger, distributedEngine.ledger, staleEngine.ledger];
  const replayChecks = [
    await replayRollbackOk(localEngine, 0, local.state),
    await replayRollbackOk(distributedEngine, 0, distributed.state),
    await staleEngine.ledger.audit(),
  ];
  const localDelta = committedDelta(localEngine.ledger.rows);
  const distributedDelta = committedDelta(distributedEngine.ledger.rows);
  return {
    canonicalStateEqual: local.state === distributed.state,
    canonicalDeltaEqual: localDelta === distributedDelta,
    localState: local.state,
    distributedState: distributed.state,
    localCommittedDelta: localDelta,
    distributedCommittedDelta: distributedDelta,
    localVerifierCalls: local.verifierCalls,
    distributedWorkerReceipts: distributed.verifierCalls,
    staleParentRejections: staleManager.staleReceiptRejectionCount,
    staleProbeCommitted: staleProbe.committed,
    ledgerAudit: (await Promise.all(ledgers.map((ledger) => ledger.audit()))).every(Boolean),
    replayRollbackRate: replayChecks.filter(Boolean).length / replayChecks.length,
    invalidCommitCount: invalidCommits(ledgers),
  };
}

function workerReceipt(parentHead        , trace                              )                                     {
  const adapter = new DistributedCounterAdapter();
  const candidate = new CounterProjector().project(0, trace);
  return { parentHead, trace, candidate, result: adapter.verify(candidate) };
}

function committedDelta(receipts           )                {
  const receipt = receipts.find((row) => row.committed);
  if (!receipt) return null;
  const payload = (receipt.replayBundle                                             ).candidatePayload;
  return payload.delta;
}

async function replayRollbackOk(engine                                                , seedState        , expectedState        )                   {
  if (!await engine.ledger.audit()) {
    return false;
  }
  return await engine.replayAudit(seedState) === expectedState && await engine.rollbackAudit(seedState) === seedState;
}

function invalidCommits(ledgers          )         {
  return ledgers.reduce(
    (total, ledger) => total + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
    0,
  );
}
