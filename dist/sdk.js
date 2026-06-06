import {





  Ledger,
  TransactionEngine,
} from "./core.js";
import { stableHash } from "./canonical.js";
import {




  TransferGuardMemory,
} from "./transfer.js";

export const SDK_DOMAIN_MANIFEST_SCHEMA = "trwm.sdk_domain_manifest.v1";
export const TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA = "trwm.transfer_guarded_domain_route.v1";



















































































export class ReceiptDomainRouter {
  accepted = new Map                             ();
  rejected = new Map                             ();

  update(domainId        , context        , receipt         )       {
    if (receipt.committed && receipt.hardResult.result === "accept") {
      increment(this.accepted, context, domainId);
    } else if (receipt.hardResult.result === "reject" || receipt.commitDecision !== "commit") {
      increment(this.rejected, context, domainId);
    }
  }

  rank(context        , domainIds          )           {
    return domainIds
      .map((domainId, idx) => ({ domainId, idx }))
      .sort((a, b) => {
        const acceptedDiff = getCount(this.accepted, context, b.domainId) - getCount(this.accepted, context, a.domainId);
        if (acceptedDiff !== 0) return acceptedDiff;
        const rejectedDiff = getCount(this.rejected, context, a.domainId) - getCount(this.rejected, context, b.domainId);
        if (rejectedDiff !== 0) return rejectedDiff;
        return a.idx - b.idx;
      })
      .map((row) => row.domainId);
  }

  counts(context        , domainId        )                                         {
    return {
      accepted: getCount(this.accepted, context, domainId),
      rejected: getCount(this.rejected, context, domainId),
    };
  }
}

export class CostAwareReceiptDomainRouter                         {
  defaultVerifierCost        ;
  rows = new Map                                               ();
  invalidCostMetadata = new Map                             ();

  constructor(defaultVerifierCost = 1) {
    if (!Number.isInteger(defaultVerifierCost) || defaultVerifierCost <= 0) {
      throw new RangeError("defaultVerifierCost must be a positive integer");
    }
    this.defaultVerifierCost = defaultVerifierCost;
  }

  update(domainId        , context        , receipt         )       {
    const row = this.mutableStats(context, domainId);
    const { cost, metadataOk } = verifierCostUnits(receipt, this.defaultVerifierCost);
    row.calls += 1;
    row.verifierCost += cost;
    if (!metadataOk) {
      increment(this.invalidCostMetadata, context, domainId);
    }
    if (receipt.committed && receipt.hardResult.result === "accept") {
      row.accepted += 1;
    } else if (receipt.hardResult.result === "abstain") {
      row.abstained += 1;
    } else if (receipt.hardResult.result === "reject" || receipt.commitDecision !== "commit") {
      row.rejected += 1;
    }
  }

  rank(context        , domainIds          )           {
    return domainIds
      .map((domainId, idx) => ({ domainId, idx }))
      .sort((a, b) => compareCostAwareRank(this.stats(context, a.domainId), this.stats(context, b.domainId), a.idx, b.idx))
      .map((row) => row.domainId);
  }

  counts(context        , domainId        )                                         {
    const row = this.stats(context, domainId);
    return { accepted: row.accepted, rejected: row.rejected };
  }

  stats(context        , domainId        )                    {
    const row = this.mutableStats(context, domainId);
    const denominator = row.verifierCost > 0 ? row.verifierCost : 1;
    return {
      accepted: row.accepted,
      rejected: row.rejected,
      abstained: row.abstained,
      verifierCost: row.verifierCost,
      calls: row.calls,
      successPerCostNumerator: row.accepted,
      successPerCostDenominator: denominator,
      successPerCost: row.verifierCost > 0 ? row.accepted / row.verifierCost : 0,
    };
  }

          mutableStats(context        , domainId        )                           {
    let contextRows = this.rows.get(context);
    if (!contextRows) {
      contextRows = new Map();
      this.rows.set(context, contextRows);
    }
    let row = contextRows.get(domainId);
    if (!row) {
      row = { accepted: 0, rejected: 0, abstained: 0, verifierCost: 0, calls: 0 };
      contextRows.set(domainId, row);
    }
    return row;
  }
}

export class TransferGuardedDomainRouter                         {
  baseRouter              ;
  transferGuard                     ;

  constructor(baseRouter               = new ReceiptDomainRouter(), transferGuard                      = new TransferGuardMemory()) {
    this.baseRouter = baseRouter;
    this.transferGuard = transferGuard;
  }

  update(domainId        , context        , receipt         )       {
    this.baseRouter.update(domainId, context, receipt);
  }

  rank(context        , domainIds          )           {
    return this.baseRouter.rank(context, domainIds);
  }

  counts(context        , domainId        )                                         {
    return this.baseRouter.counts(context, domainId);
  }

  async updateTransferCertificate(certificate                               )                                {
    return this.transferGuard.update(certificate);
  }

  async guardSnapshot()                                 {
    return this.transferGuard.snapshot();
  }

  async decideTransfer(sourceDomains          , targetDomain        )                                 {
    return this.transferGuard.decide(sourceDomains, targetDomain);
  }

  async rankWithTransferGuard(
    context        ,
    domainIds          ,
    sourceDomains          ,
    targetDomain        ,
  )                                      {
    const inputIds = uniqueOrdered(domainIds);
    const sourceRows = uniqueSorted(sourceDomains);
    const baseRanked = this.baseRouter.rank(context, inputIds);
    const decision = await this.transferGuard.decide(sourceRows, targetDomain);
    const blocked = decision.admitted ? [] : baseRanked.filter((domainId) => sourceRows.includes(domainId));
    const blockedSet = new Set(blocked);
    const ranked = [
      ...baseRanked.filter((domainId) => !blockedSet.has(domainId)),
      ...baseRanked.filter((domainId) => blockedSet.has(domainId)),
    ];
    const pending



      = {
      schemaVersion: TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA,
      context: String(context),
      sourceDomains: sourceRows,
      targetDomain: String(targetDomain),
      inputDomainIds: inputIds,
      baseRankedDomainIds: baseRanked,
      rankedDomainIds: ranked,
      blockedDomainIds: blocked,
      decisionReason: decision.reason,
      decisionAdmitted: decision.admitted,
      decisionHash: decision.decisionHash,
      routeHash: "",
      topDomainId: ranked[0] ?? "",
      sourceBlocked: blocked.length > 0,
    };
    return { ...pending, routeHash: await transferGuardedDomainRouteHash(pending) };
  }
}

export async function buildDomainManifest(runtime               )                                     {
  const rows = runtime.ledger.rows;
  const acceptedCount = rows.filter((receipt) => receipt.hardResult.result === "accept").length;
  const rejectedCount = rows.filter((receipt) => receipt.hardResult.result === "reject").length;
  const abstainedCount = rows.filter((receipt) => receipt.hardResult.result === "abstain").length;
  const committedCount = rows.filter((receipt) => receipt.committed).length;
  const certificate                            = {
    schemaVersion: SDK_DOMAIN_MANIFEST_SCHEMA,
    domainId: runtime.domainId,
    adapterType: runtime.adapter.constructor?.name || "anonymous",
    verifierId: runtime.adapter.verifierId,
    verifierVersion: runtime.adapter.verifierVersion,
    candidateTypeNames: uniqueSorted(rows.map((receipt) => receiptCandidateType(receipt))),
    projectionSchemaVersions: uniqueSorted(rows.map((receipt) => receipt.projectionSchemaVersion)),
    modelVersions: uniqueSorted(rows.map((receipt) => receipt.modelVersion)),
    receiptSchemaVersions: uniqueSorted(rows.map((receipt) => receipt.receiptSchema)),
    receiptCount: rows.length,
    acceptedCount,
    rejectedCount,
    abstainedCount,
    committedCount,
    hardVerifierCalls: runtime.hardVerifierCalls,
    verifierCost: rows.reduce((total, receipt) => total + verifierCostUnits(receipt).cost, 0),
    invalidCommitCount: rows.filter((receipt) => receipt.committed && receipt.hardResult.result !== "accept").length,
    ledgerHead: runtime.ledger.head,
    ledgerAudit: await runtime.ledger.audit(),
    receiptHashes: rows.map((receipt) => receipt.receiptHash),
    manifestHash: "",
  };
  certificate.manifestHash = await domainManifestHash(certificate);
  return certificate;
}

export async function auditDomainManifest(runtime               , certificate                           )                   {
  try {
    if (!await validateDomainManifest(certificate)) {
      return false;
    }
    if (!await runtime.ledger.audit()) {
      return false;
    }
    const rebuilt = await buildDomainManifest(runtime);
    return rebuilt.manifestHash === certificate.manifestHash;
  } catch {
    return false;
  }
}

export async function validateDomainManifest(certificate                           )                   {
  try {
    if (certificate.schemaVersion !== SDK_DOMAIN_MANIFEST_SCHEMA) {
      return false;
    }
    if (![certificate.domainId, certificate.adapterType, certificate.verifierId, certificate.verifierVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    const countValues = [
      certificate.receiptCount,
      certificate.acceptedCount,
      certificate.rejectedCount,
      certificate.abstainedCount,
      certificate.committedCount,
      certificate.hardVerifierCalls,
      certificate.verifierCost,
      certificate.invalidCommitCount,
    ];
    if (countValues.some((value) => !Number.isInteger(value) || value < 0)) {
      return false;
    }
    if (certificate.receiptCount !== certificate.acceptedCount + certificate.rejectedCount + certificate.abstainedCount) {
      return false;
    }
    if (certificate.committedCount > certificate.acceptedCount) {
      return false;
    }
    if (certificate.hardVerifierCalls < certificate.receiptCount) {
      return false;
    }
    if (certificate.invalidCommitCount !== 0 || !certificate.ledgerAudit) {
      return false;
    }
    if (!isHash(certificate.ledgerHead)) {
      return false;
    }
    if (certificate.receiptHashes.length !== certificate.receiptCount) {
      return false;
    }
    if (certificate.receiptHashes.some((value) => !isHash(value))) {
      return false;
    }
    if (!sortedUniqueNonemptyWhenReceipts(certificate.candidateTypeNames, certificate.receiptCount)) {
      return false;
    }
    if (!sortedUniqueNonemptyWhenReceipts(certificate.projectionSchemaVersions, certificate.receiptCount)) {
      return false;
    }
    if (!sortedUniqueNonemptyWhenReceipts(certificate.modelVersions, certificate.receiptCount)) {
      return false;
    }
    if (!sortedUniqueNonemptyWhenReceipts(certificate.receiptSchemaVersions, certificate.receiptCount)) {
      return false;
    }
    return certificate.manifestHash === await domainManifestHash(certificate);
  } catch {
    return false;
  }
}

export async function domainManifestHash(certificate                           )                  {
  const { manifestHash: _manifestHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function transferGuardedDomainRouteHash(route                                                      )                  {
  const { routeHash: _routeHash, ...withoutHash } = route                           ;
  return stableHash(withoutHash);
}

export async function validateTransferGuardedDomainRoute(route                            )                   {
  try {
    if (route.schemaVersion !== TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA) {
      return false;
    }
    if (typeof route.context !== "string" || !route.context) {
      return false;
    }
    if (!sortedUniqueNonempty(route.sourceDomains)) {
      return false;
    }
    if (typeof route.targetDomain !== "string" || !route.targetDomain || route.sourceDomains.includes(route.targetDomain)) {
      return false;
    }
    if (!uniqueNonempty(route.inputDomainIds)) {
      return false;
    }
    if (!sameStringSet(route.baseRankedDomainIds, route.inputDomainIds) || !sameStringSet(route.rankedDomainIds, route.inputDomainIds)) {
      return false;
    }
    if (route.baseRankedDomainIds.length !== route.inputDomainIds.length || route.rankedDomainIds.length !== route.inputDomainIds.length) {
      return false;
    }
    if (!route.blockedDomainIds.every((domainId) => route.inputDomainIds.includes(domainId) && route.sourceDomains.includes(domainId))) {
      return false;
    }
    if (route.blockedDomainIds.length !== new Set(route.blockedDomainIds).size) {
      return false;
    }
    if (typeof route.decisionAdmitted !== "boolean") {
      return false;
    }
    if (typeof route.decisionReason !== "string" || !route.decisionReason || !isHash(route.decisionHash)) {
      return false;
    }
    if (route.decisionAdmitted) {
      if (route.decisionReason !== "positive_transfer_certificate" || route.blockedDomainIds.length > 0) {
        return false;
      }
    } else if (!["no_valid_transfer_certificate", "negative_transfer_certificate", "neutral_transfer_certificate"].includes(route.decisionReason)) {
      return false;
    }
    const blockedSet = new Set(route.blockedDomainIds);
    const expectedRanked = [
      ...route.baseRankedDomainIds.filter((domainId) => !blockedSet.has(domainId)),
      ...route.baseRankedDomainIds.filter((domainId) => blockedSet.has(domainId)),
    ];
    if (JSON.stringify(route.rankedDomainIds) !== JSON.stringify(expectedRanked)) {
      return false;
    }
    if (route.topDomainId !== (route.rankedDomainIds[0] ?? "")) {
      return false;
    }
    if (route.sourceBlocked !== (route.blockedDomainIds.length > 0)) {
      return false;
    }
    return route.routeHash === await transferGuardedDomainRouteHash(route);
  } catch (_error) {
    return false;
  }
}

export class ProgrammableSubstrate {
  router              ;
  domains = new Map                                         ();

  constructor(router               = new ReceiptDomainRouter()) {
    this.router = router;
  }

  register                (
    domainId        ,
    adapter                                       ,
  )                                {
    if (this.domains.has(domainId)) {
      throw new Error(`domain already registered: ${domainId}`);
    }
    const runtime                                = {
      domainId,
      adapter,
      ledger: new Ledger(),
      hardVerifierCalls: 0,
    };
    this.domains.set(domainId, runtime                                   );
    return runtime;
  }

  async submit                (
    domainId        ,
    state       ,
    trace               ,
    candidate                         ,
    options                                                            = {},
  )                                       {
    const domain = this.domain                (domainId);
    const engine = new TransactionEngine(domain.adapter, domain.ledger);
    const outcome = await engine.transact(state, trace, candidate, { softScores: options.softScores });
    domain.hardVerifierCalls += engine.hardVerifierCalls;
    this.router.update(domainId, options.context ?? "global", outcome.receipt);
    return {
      domainId,
      outcome,
      hardVerifierCalls: engine.hardVerifierCalls,
      committed: outcome.committed,
      receipt: outcome.receipt,
    };
  }

  rankDomains(context        , domainIds           )           {
    return this.router.rank(context, domainIds ?? Array.from(this.domains.keys()));
  }

  async auditDomain       (domainId        , seedState       )                       {
    const domain = this.domain                (domainId);
    const engine = new TransactionEngine(domain.adapter, domain.ledger);
    const ledgerAudit = await domain.ledger.audit();
    let replayMatchesReceipts = false;
    let rollbackMatchesSeed = false;
    if (ledgerAudit) {
      try {
        await engine.replayAudit(seedState);
        replayMatchesReceipts = true;
        const rolledBack = await engine.rollbackAudit(seedState);
        rollbackMatchesSeed = JSON.stringify(rolledBack) === JSON.stringify(seedState);
      } catch (_error) {
        replayMatchesReceipts = false;
        rollbackMatchesSeed = false;
      }
    }
    const invalidCommitCount = this.invalidCommitCount([domainId]);
    return {
      domainId,
      ledgerAudit,
      replayMatchesReceipts,
      rollbackMatchesSeed,
      invalidCommitCount,
      ok: ledgerAudit && replayMatchesReceipts && rollbackMatchesSeed && invalidCommitCount === 0,
    };
  }

  async domainManifest(domainId        )                                     {
    return buildDomainManifest(this.domain(domainId));
  }

  async auditDomainManifest(domainId        , certificate                           )                   {
    return auditDomainManifest(this.domain(domainId), certificate);
  }

  invalidCommitCount(domainIds           )         {
    const ids = domainIds ?? Array.from(this.domains.keys());
    let count = 0;
    for (const domainId of ids) {
      const domain = this.domain(domainId);
      count += domain.ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length;
    }
    return count;
  }

  domain                                    (domainId        )                                {
    const domain = this.domains.get(domainId);
    if (!domain) {
      throw new Error(`unknown domain: ${domainId}`);
    }
    return domain                                 ;
  }
}

function increment(table                                  , context        , domainId        )       {
  let row = table.get(context);
  if (!row) {
    row = new Map();
    table.set(context, row);
  }
  row.set(domainId, (row.get(domainId) ?? 0) + 1);
}

function getCount(table                                  , context        , domainId        )         {
  return table.get(context)?.get(domainId) ?? 0;
}









export function verifierCostUnits(receipt         , defaultVerifierCost = 1)                                        {
  const spentValue = receipt.hardResult.metadata.verifier_cost_spent ?? receipt.hardResult.metadata.verifierCostSpent;
  if (typeof spentValue !== "undefined") {
    const spent = integerMetadata(spentValue);
    if (spent === null) {
      return { cost: defaultVerifierCost, metadataOk: false };
    }
    if (spent === 0 && receipt.hardResult.result === "abstain") {
      return { cost: 0, metadataOk: true };
    }
    if (spent > 0) {
      return { cost: spent, metadataOk: true };
    }
    return { cost: defaultVerifierCost, metadataOk: false };
  }

  const value = receipt.hardResult.metadata.verifier_cost ?? receipt.hardResult.metadata.verifierCost ?? defaultVerifierCost;
  const cost = integerMetadata(value);
  if (cost === null || cost <= 0) {
    return { cost: defaultVerifierCost, metadataOk: false };
  }
  return { cost, metadataOk: true };
}

function integerMetadata(value         )                {
  if (typeof value === "boolean") {
    return null;
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value : null;
  }
  if (typeof value === "string" && /^[0-9]+$/.test(value.trim())) {
    return Number(value);
  }
  return null;
}

function receiptCandidateType(receipt         )         {
  const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
    ? receipt.replayBundle
    : {};
  return String(bundle.candidateType ?? bundle.candidate_type ?? "unknown");
}

function uniqueSorted(values           )           {
  return Array.from(new Set(values.map((value) => String(value)).filter((value) => value.length > 0))).sort();
}

function uniqueOrdered(values           )           {
  const rows           = [];
  const seen = new Set        ();
  for (const value of values) {
    const row = String(value);
    if (!row) {
      continue;
    }
    if (seen.has(row)) {
      throw new Error("domain ids must be unique");
    }
    rows.push(row);
    seen.add(row);
  }
  return rows;
}

function uniqueNonempty(values          )          {
  return values.length > 0 && values.length === new Set(values).size && values.every((value) => typeof value === "string" && value.length > 0);
}

function sortedUniqueNonempty(values          )          {
  return uniqueNonempty(values) && values.every((value, idx) => idx === 0 || values[idx - 1] <= value);
}

function sameStringSet(left          , right          )          {
  return left.length === right.length && new Set(left).size === left.length && left.every((value) => right.includes(value));
}

function sortedUniqueNonemptyWhenReceipts(values          , receiptCount        )          {
  if (!values.every((value) => typeof value === "string" && value.length > 0)) {
    return false;
  }
  if (values.length !== new Set(values).size) {
    return false;
  }
  if (!values.every((value, idx) => idx === 0 || values[idx - 1] <= value)) {
    return false;
  }
  return receiptCount === 0 || values.length > 0;
}

function isHash(value        )          {
  return /^[0-9a-f]{64}$/.test(value);
}

function compareCostAwareRank(a                   , b                   , aIdx        , bIdx        )         {
  const aNumerator = a.successPerCostNumerator * b.successPerCostDenominator;
  const bNumerator = b.successPerCostNumerator * a.successPerCostDenominator;
  if (aNumerator !== bNumerator) {
    return bNumerator - aNumerator;
  }
  if (a.rejected !== b.rejected) {
    return a.rejected - b.rejected;
  }
  if (a.abstained !== b.abstained) {
    return a.abstained - b.abstained;
  }
  if (a.verifierCost !== b.verifierCost) {
    return a.verifierCost - b.verifierCost;
  }
  return aIdx - bIdx;
}
