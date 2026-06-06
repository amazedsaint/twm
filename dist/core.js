import { chainHash, stableHash } from "./canonical.js";

export const GENESIS_HEAD = "0".repeat(64);
export const RUNTIME_SCHEMA = "trwm.browser.runtime.v1";
export const RECEIPT_SCHEMA = "trwm.browser.receipt.v1";
































































































export function hardAccept(verifierId        , verifierVersion        , metadata                          = {})                     {
  return { result: "accept", verifierId, verifierVersion, metadata };
}

export function hardReject(
  verifierId        ,
  verifierVersion        ,
  residual          ,
  metadata                          = {},
)                     {
  const result                     = { result: "reject", verifierId, verifierVersion, metadata };
  if (typeof residual !== "undefined") {
    result.residual = residual;
  }
  return result;
}

export function hardAbstain(
  verifierId        ,
  verifierVersion        ,
  residual          ,
  metadata                          = {},
)                     {
  const result                     = { result: "abstain", verifierId, verifierVersion, metadata };
  if (typeof residual !== "undefined") {
    result.residual = residual;
  }
  return result;
}

export async function captureState   (state   , schemaVersion = "state.v1")                            {
  return {
    state,
    schemaVersion,
    stateHash: await stableHash({ schemaVersion, state }),
  };
}

export function makeTrace(partial                                               )                {
  return {
    branchId: partial.branchId,
    actions: partial.actions ?? [],
    latentStates: partial.latentStates ?? [],
    seeds: partial.seeds ?? [],
    modelVersion: partial.modelVersion ?? "manual.v1",
  };
}

export function makeCandidate   (
  payload   ,
  typeName        ,
  schemaVersion        ,
  hashes                         = {},
)                    {
  return { payload, typeName, schemaVersion, hashes };
}

export async function traceHash(trace               )                  {
  return stableHash(trace);
}

export async function candidateHash(candidate                )                  {
  return stableHash(candidate);
}

export async function createRuntimeManifest(overrides                          = {})                           {
  const manifest                  = {
    schema: RUNTIME_SCHEMA,
    runtime: "trwm-browser",
    runtimeVersion: "0.1.0",
    createdMs: String(Date.now()),
    userAgent: globalThis.navigator?.userAgent ?? "node",
    manifestHash: "",
    ...overrides,
  };
  manifest.manifestHash = await stableHash(omitKey(manifest, "manifestHash"));
  return manifest;
}

export async function manifestValid(manifest                 )                   {
  if (manifest.schema !== RUNTIME_SCHEMA || manifest.runtime !== "trwm-browser") {
    return false;
  }
  return manifest.manifestHash === await stableHash(omitKey(manifest, "manifestHash"));
}

export async function receiptWithoutHash(receipt         )                                        {
  const { receiptHash: _receiptHash, ...withoutHash } = receipt;
  return withoutHash;
}

export async function receiptHash(receipt         )                  {
  return stableHash(await receiptWithoutHash(receipt));
}

export async function finalizeReceipt(receipt         , parentHead        )                   {
  const pending = { ...receipt, parentHead, receiptHash: "" };
  return { ...pending, receiptHash: await receiptHash(pending) };
}

export async function receiptStaticValid(receipt         )                   {
  if (receipt.receiptSchema !== RECEIPT_SCHEMA) {
    return false;
  }
  if (receipt.receiptHash && receipt.receiptHash !== await receiptHash(receipt)) {
    return false;
  }
  if (receipt.committed) {
    if (!await manifestValid(receipt.runtimeManifest)) {
      return false;
    }
    if (receipt.hardResult.result !== "accept") {
      return false;
    }
    if (receipt.commitDecision !== "commit") {
      return false;
    }
    if (!receipt.postStateHash || !receipt.rollbackStateHash) {
      return false;
    }
  }
  if (!receipt.committed && receipt.commitDecision === "commit") {
    return false;
  }
  return true;
}

export class Ledger {
  head        ;
  rows           ;

  constructor(head = GENESIS_HEAD, rows            = []) {
    this.head = head;
    this.rows = [];
    this.pendingRows = rows;
  }

          pendingRows           ;

  async initialize()                {
    for (const row of this.pendingRows) {
      await this.append(row);
    }
    this.pendingRows = [];
    return this;
  }

  async append(receipt         )                   {
    const finalized = await finalizeReceipt(receipt, this.head);
    this.rows.push(finalized);
    this.head = await chainHash(finalized.parentHead, finalized.receiptHash);
    return finalized;
  }

  async audit()                   {
    let head = GENESIS_HEAD;
    for (const receipt of this.rows) {
      if (!await receiptStaticValid(receipt)) {
        return false;
      }
      if (receipt.parentHead !== head) {
        return false;
      }
      if (receipt.receiptHash !== await receiptHash(receipt)) {
        return false;
      }
      head = await chainHash(head, receipt.receiptHash);
    }
    return head === this.head;
  }

  committedRows()            {
    return this.rows.filter((row) => row.committed);
  }
}

export class TransactionEngine                                    {
  adapter                                                ;
  ledger        ;
  manifestFactory                                                  ;
  hardVerifierCalls = 0;
  invalidCommitCount = 0;
  softVerifierCommitCount = 0;
  verifierMismatchCount = 0;

  constructor(
    adapter                                                ,
    ledger = new Ledger(),
    manifestFactory                                                   = () => createRuntimeManifest(),
  ) {
    this.adapter = adapter;
    this.ledger = ledger;
    this.manifestFactory = manifestFactory;
  }

  async transact(
    state       ,
    trace               ,
    candidate                                  ,
    options                                                                       = {},
  )                                     {
    const hardResult = options.result ?? await this.adapter.verify(candidate);
    if (!options.result) {
      this.hardVerifierCalls += 1;
    }
    return this.recordEvaluatedCandidate(state, trace, candidate, hardResult, options.softScores);
  }

  async recordEvaluatedCandidate(
    state       ,
    trace               ,
    candidate                                  ,
    hardResult                    ,
    softScores                         = {},
    forceDecision                                    ,
  )                                     {
    assertVerifierStatus(hardResult.result);
    const pre = await captureState(state);
    const manifest = await this.manifestFactory();
    const manifestOk = await manifestValid(manifest);
    const verifierOk = this.hardResultAuthorized(hardResult);
    let postState               = null;
    let postHash                = null;
    let replayOk = false;
    let rollbackOk = false;
    let commitReason                 = "hard_reject";
    const replayBundle = {
      candidatePayload: candidate.payload,
      candidateType: candidate.typeName,
      candidateSchema: candidate.schemaVersion,
    };
    const rollbackBundle = { preState: pre.state };

    if (!verifierOk) {
      this.verifierMismatchCount += 1;
      commitReason = "verifier_mismatch";
    } else if (forceDecision) {
      commitReason = forceDecision;
    } else if (hardResult.result === "accept" && manifestOk) {
      try {
        postState = await this.adapter.applyCommit(state, candidate);
        postHash = (await captureState(postState)).stateHash;
        const provisional = await this.makeReceipt({
          pre,
          trace,
          candidate,
          hardResult,
          manifest,
          postStateHash: postHash,
          rollbackStateHash: pre.stateHash,
          replayBundle,
          rollbackBundle,
          softScores,
          commitDecision: "hard_reject",
          committed: false,
        });
        const replayState = await this.adapter.replay(state, provisional);
        replayOk = (await captureState(replayState)).stateHash === postHash;
        const rollbackState = await this.adapter.rollback(postState, provisional);
        rollbackOk = (await captureState(rollbackState)).stateHash === pre.stateHash;
      } catch (error) {
        commitReason = `replay_or_rollback_error:${error instanceof Error ? error.name : "unknown"}`;
      }
    } else if (hardResult.result === "accept") {
      commitReason = "manifest_invalid";
    } else if (hardResult.result === "abstain") {
      commitReason = "hard_abstain";
    }

    const shouldCommit = verifierOk && !forceDecision && hardResult.result === "accept" && manifestOk && replayOk && rollbackOk;
    if (shouldCommit) {
      commitReason = "commit";
    }
    const receipt = await this.makeReceipt({
      pre,
      trace,
      candidate,
      hardResult,
      manifest,
      postStateHash: shouldCommit ? postHash : null,
      rollbackStateHash: pre.stateHash,
      replayBundle,
      rollbackBundle,
      softScores,
      commitDecision: commitReason,
      committed: shouldCommit,
    });
    const finalized = await this.ledger.append(receipt);
    if (finalized.committed && hardResult.result !== "accept") {
      this.invalidCommitCount += 1;
    }
    if (finalized.committed && Object.keys(softScores).length > 0 && hardResult.result !== "accept") {
      this.softVerifierCommitCount += 1;
    }
    return {
      state: shouldCommit ? postState          : state,
      receipt: finalized,
      committed: shouldCommit,
      reason: commitReason,
    };
  }

  async replayAudit(seedState       )                 {
    if (!await this.ledger.audit()) {
      throw new Error("ledger audit failed before replay");
    }
    let state = seedState;
    for (const receipt of this.ledger.rows) {
      if (!receipt.committed) {
        continue;
      }
      const next = await this.adapter.replay(state, receipt);
      if ((await captureState(next)).stateHash !== receipt.postStateHash) {
        throw new Error(`replay hash mismatch for ${receipt.receiptId}`);
      }
      state = next;
    }
    return state;
  }

  async rollbackAudit(seedState       )                 {
    if (!await this.ledger.audit()) {
      throw new Error("ledger audit failed before rollback");
    }
    const states          = [seedState];
    let state = seedState;
    for (const receipt of this.ledger.rows) {
      if (receipt.committed) {
        state = await this.adapter.replay(state, receipt);
        states.push(state);
      }
    }
    for (const receipt of [...this.ledger.committedRows()].reverse()) {
      state = await this.adapter.rollback(state, receipt);
      const expected = states[states.length - 2];
      if ((await captureState(state)).stateHash !== (await captureState(expected)).stateHash) {
        throw new Error(`rollback hash mismatch for ${receipt.receiptId}`);
      }
      states.pop();
    }
    return state;
  }

          hardResultAuthorized(result                    )          {
    return result.verifierId === this.adapter.verifierId && result.verifierVersion === this.adapter.verifierVersion;
  }

          async makeReceipt(params












   )                   {
    return {
      receiptId: crypto.randomUUID(),
      parentHead: "",
      preStateHash: params.pre.stateHash,
      postStateHash: params.postStateHash,
      rollbackStateHash: params.rollbackStateHash,
      branchId: params.trace.branchId,
      proposalTraceHash: await traceHash(params.trace),
      typedCandidateHash: await candidateHash(params.candidate),
      hardResult: params.hardResult,
      commitDecision: params.commitDecision,
      committed: params.committed,
      runtimeManifest: params.manifest,
      replayBundle: params.replayBundle,
      rollbackBundle: params.rollbackBundle,
      softScores: params.softScores,
      randomSeed: params.trace.seeds,
      modelVersion: params.trace.modelVersion,
      projectionSchemaVersion: params.candidate.schemaVersion,
      artifactHashes: params.candidate.hashes,
      receiptSchema: RECEIPT_SCHEMA,
      timestampMs: String(Date.now()),
      receiptHash: "",
    };
  }
}

function assertVerifierStatus(status        )                                   {
  if (status !== "accept" && status !== "reject" && status !== "abstain") {
    throw new TypeError(`invalid hard verifier result: ${status}`);
  }
}

function omitKey                                                      (object   , key   )             {
  const { [key]: _omitted, ...rest } = object;
  return rest;
}
