import { compareCodePoint, stableHash } from "./canonical.js";

export const TRANSFER_EVALUATION_CERTIFICATE_SCHEMA = "trwm.transfer_evaluation_certificate.v1";
export const TRANSFER_EVALUATION_CONCLUSIONS = ["positive_transfer", "negative_transfer", "neutral"]         ;
export const TRANSFER_GUARD_SNAPSHOT_SCHEMA = "trwm.transfer_guard_snapshot.v1";

























































export class TransferGuardMemory {
          entries = new Map                            ();

  async update(certificate                               )                                {
    if (!await validateTransferEvaluationCertificate(certificate)) {
      throw new Error("transfer certificate must validate before guard update");
    }
    return this.applyUpdate(certificate);
  }

  async updateValidated(certificate                               )                                {
    return this.update(certificate);
  }

          applyUpdate(certificate                               )                       {
    const rows                       = [];
    for (const targetDomain of certificate.targetDomains) {
      const entry                     = {
        sourceDomains: [...certificate.sourceDomains],
        targetDomain,
        conclusion: certificate.conclusion,
        certificateHash: certificate.certificateHash,
        successDelta: certificate.successDelta,
        verifierCallDelta: certificate.verifierCallDelta,
      };
      const key = guardKey(entry.sourceDomains, entry.targetDomain);
      const existing = this.entries.get(key);
      if (!existing || moreConservative(entry, existing)) {
        this.entries.set(key, entry);
      }
      rows.push(this.entries.get(key) ?? entry);
    }
    return rows;
  }

  async decide(sourceDomains          , targetDomain        )                                 {
    const sourceRows = uniqueSorted(sourceDomains);
    const target = String(targetDomain);
    const entry = this.entries.get(guardKey(sourceRows, target));
    if (!entry) {
      return buildTransferGuardDecision({
        sourceDomains: sourceRows,
        targetDomain: target,
        admitted: false,
        reason: "no_valid_transfer_certificate",
        conclusion: "",
        certificateHash: "",
      });
    }
    if (entry.conclusion === "positive_transfer") {
      return buildTransferGuardDecision({
        sourceDomains: sourceRows,
        targetDomain: target,
        admitted: true,
        reason: "positive_transfer_certificate",
        conclusion: entry.conclusion,
        certificateHash: entry.certificateHash,
      });
    }
    return buildTransferGuardDecision({
      sourceDomains: sourceRows,
      targetDomain: target,
      admitted: false,
      reason: entry.conclusion === "negative_transfer" ? "negative_transfer_certificate" : "neutral_transfer_certificate",
      conclusion: entry.conclusion,
      certificateHash: entry.certificateHash,
    });
  }

  async snapshot()                                 {
    const pending                        = {
      schemaVersion: TRANSFER_GUARD_SNAPSHOT_SCHEMA,
      entries: Array.from(this.entries.values()).sort(compareEntry),
      snapshotHash: "",
    };
    return { ...pending, snapshotHash: await transferGuardSnapshotHash(pending) };
  }
}

export async function buildTransferEvaluationCertificate(params



















 )                                         {
  const sourceDomains = uniqueSorted(params.sourceDomains);
  const targetDomains = uniqueSorted(params.targetDomains);
  const successDelta = params.transferSuccessCount - params.baselineSuccessCount;
  const verifierCallDelta = params.transferVerifierCalls - params.baselineVerifierCalls;
  const pending                                = {
    schemaVersion: TRANSFER_EVALUATION_CERTIFICATE_SCHEMA,
    claimId: params.claimId,
    learnerId: params.learnerId,
    learnerSnapshotHash: params.learnerSnapshotHash,
    sourceDomains,
    targetDomains,
    sourceReceiptHashes: params.sourceReceiptHashes.map(String),
    targetEvaluationReceiptHashes: params.targetEvaluationReceiptHashes.map(String),
    baselineName: params.baselineName,
    transferName: params.transferName,
    baselineSuccessCount: params.baselineSuccessCount,
    transferSuccessCount: params.transferSuccessCount,
    baselineVerifierCalls: params.baselineVerifierCalls,
    transferVerifierCalls: params.transferVerifierCalls,
    sameCaseBaseline: Boolean(params.sameCaseBaseline),
    hardCommitOnly: Boolean(params.hardCommitOnly),
    invalidCommitCount: params.invalidCommitCount,
    ledgerAudit: Boolean(params.ledgerAudit),
    replayRollbackRate: params.replayRollbackRate,
    sourceTargetDomainDisjoint: disjoint(sourceDomains, targetDomains),
    sourceTargetReceiptDisjoint: disjoint(params.sourceReceiptHashes, params.targetEvaluationReceiptHashes),
    successDelta,
    verifierCallDelta,
    conclusion: transferConclusion(successDelta, verifierCallDelta),
    metrics: params.metrics ?? {},
    certificateHash: "",
  };
  return { ...pending, certificateHash: await transferEvaluationCertificateHash(pending) };
}

export async function buildTransferGuardDecision(params






 )                                 {
  const pending                        = {
    sourceDomains: uniqueSorted(params.sourceDomains),
    targetDomain: String(params.targetDomain),
    admitted: Boolean(params.admitted),
    reason: params.reason,
    conclusion: params.conclusion ?? "",
    certificateHash: params.certificateHash ?? "",
    decisionHash: "",
  };
  return { ...pending, decisionHash: await transferGuardDecisionHash(pending) };
}

export async function transferEvaluationCertificateHash(certificate                               )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function transferGuardSnapshotHash(snapshot                       )                  {
  const { snapshotHash: _snapshotHash, ...withoutHash } = snapshot;
  return stableHash(withoutHash);
}

export async function transferGuardDecisionHash(decision                       )                  {
  const { decisionHash: _decisionHash, ...withoutHash } = decision;
  return stableHash(withoutHash);
}

export async function validateTransferEvaluationCertificate(certificate                               )                   {
  try {
    if (certificate.schemaVersion !== TRANSFER_EVALUATION_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (!TRANSFER_EVALUATION_CONCLUSIONS.includes(certificate.conclusion)) {
      return false;
    }
    if (![certificate.claimId, certificate.learnerId, certificate.baselineName, certificate.transferName].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!isHash(certificate.learnerSnapshotHash)) {
      return false;
    }
    if (!sortedUniqueNonempty(certificate.sourceDomains) || !sortedUniqueNonempty(certificate.targetDomains)) {
      return false;
    }
    if (!disjoint(certificate.sourceDomains, certificate.targetDomains) || !certificate.sourceTargetDomainDisjoint) {
      return false;
    }
    if (!uniqueHashes(certificate.sourceReceiptHashes) || !uniqueHashes(certificate.targetEvaluationReceiptHashes)) {
      return false;
    }
    if (!disjoint(certificate.sourceReceiptHashes, certificate.targetEvaluationReceiptHashes) || !certificate.sourceTargetReceiptDisjoint) {
      return false;
    }
    const counts = [
      certificate.baselineSuccessCount,
      certificate.transferSuccessCount,
      certificate.baselineVerifierCalls,
      certificate.transferVerifierCalls,
      certificate.invalidCommitCount,
    ];
    if (counts.some((value) => !Number.isInteger(value) || value < 0)) {
      return false;
    }
    if (certificate.baselineVerifierCalls <= 0 || certificate.transferVerifierCalls <= 0) {
      return false;
    }
    if (certificate.baselineSuccessCount > certificate.baselineVerifierCalls || certificate.transferSuccessCount > certificate.transferVerifierCalls) {
      return false;
    }
    if (typeof certificate.sameCaseBaseline !== "boolean" || typeof certificate.hardCommitOnly !== "boolean" || typeof certificate.ledgerAudit !== "boolean") {
      return false;
    }
    if (!Number.isFinite(certificate.replayRollbackRate) || certificate.replayRollbackRate < 0 || certificate.replayRollbackRate > 1) {
      return false;
    }
    const successDelta = certificate.transferSuccessCount - certificate.baselineSuccessCount;
    const verifierCallDelta = certificate.transferVerifierCalls - certificate.baselineVerifierCalls;
    if (certificate.successDelta !== successDelta || certificate.verifierCallDelta !== verifierCallDelta) {
      return false;
    }
    if (certificate.conclusion !== transferConclusion(successDelta, verifierCallDelta)) {
      return false;
    }
    return certificate.certificateHash === await transferEvaluationCertificateHash(certificate);
  } catch (_error) {
    return false;
  }
}

export async function validateTransferGuardSnapshot(snapshot                       )                   {
  try {
    if (snapshot.schemaVersion !== TRANSFER_GUARD_SNAPSHOT_SCHEMA) {
      return false;
    }
    if (!snapshot.entries.every((entry, idx) => idx === 0 || compareEntry(snapshot.entries[idx - 1], entry) <= 0)) {
      return false;
    }
    const keys = new Set        ();
    for (const entry of snapshot.entries) {
      if (!sortedUniqueNonempty(entry.sourceDomains)) {
        return false;
      }
      if (typeof entry.targetDomain !== "string" || !entry.targetDomain || entry.sourceDomains.includes(entry.targetDomain)) {
        return false;
      }
      if (!TRANSFER_EVALUATION_CONCLUSIONS.includes(entry.conclusion)) {
        return false;
      }
      if (!isHash(entry.certificateHash)) {
        return false;
      }
      if (!Number.isInteger(entry.successDelta) || !Number.isInteger(entry.verifierCallDelta)) {
        return false;
      }
      if (entry.conclusion !== transferConclusion(entry.successDelta, entry.verifierCallDelta)) {
        return false;
      }
      const key = guardKey(entry.sourceDomains, entry.targetDomain);
      if (keys.has(key)) {
        return false;
      }
      keys.add(key);
    }
    return snapshot.snapshotHash === await transferGuardSnapshotHash(snapshot);
  } catch (_error) {
    return false;
  }
}

export async function validateTransferGuardDecision(decision                       )                   {
  try {
    if (!sortedUniqueNonempty(decision.sourceDomains)) {
      return false;
    }
    if (typeof decision.targetDomain !== "string" || !decision.targetDomain || decision.sourceDomains.includes(decision.targetDomain)) {
      return false;
    }
    if (typeof decision.admitted !== "boolean") {
      return false;
    }
    if (typeof decision.reason !== "string" || !decision.reason) {
      return false;
    }
    if (decision.conclusion && !TRANSFER_EVALUATION_CONCLUSIONS.includes(decision.conclusion)) {
      return false;
    }
    if (decision.certificateHash && !isHash(decision.certificateHash)) {
      return false;
    }
    if (decision.reason === "no_valid_transfer_certificate") {
      if (decision.admitted || decision.conclusion || decision.certificateHash) {
        return false;
      }
    } else if (decision.reason === "positive_transfer_certificate") {
      if (!decision.admitted || decision.conclusion !== "positive_transfer" || !decision.certificateHash) {
        return false;
      }
    } else if (decision.reason === "negative_transfer_certificate") {
      if (decision.admitted || decision.conclusion !== "negative_transfer" || !decision.certificateHash) {
        return false;
      }
    } else if (decision.reason === "neutral_transfer_certificate") {
      if (decision.admitted || decision.conclusion !== "neutral" || !decision.certificateHash) {
        return false;
      }
    } else {
      return false;
    }
    return decision.decisionHash === await transferGuardDecisionHash(decision);
  } catch (_error) {
    return false;
  }
}

export async function transferEvaluationSupportsPositiveClaim(certificate                               )                   {
  return await validateTransferEvaluationCertificate(certificate)
    && certificate.conclusion === "positive_transfer"
    && certificate.sameCaseBaseline
    && certificate.hardCommitOnly
    && certificate.invalidCommitCount === 0
    && certificate.ledgerAudit
    && certificate.replayRollbackRate === 1;
}

export async function transferEvaluationRejectsPositiveClaim(certificate                               )                   {
  return await validateTransferEvaluationCertificate(certificate)
    && certificate.conclusion === "negative_transfer"
    && certificate.sameCaseBaseline
    && certificate.hardCommitOnly
    && certificate.invalidCommitCount === 0
    && certificate.ledgerAudit
    && certificate.replayRollbackRate === 1;
}

function transferConclusion(successDelta        , verifierCallDelta        )                               {
  if (successDelta > 0 || (successDelta === 0 && verifierCallDelta < 0)) {
    return "positive_transfer";
  }
  if (successDelta < 0 || (successDelta === 0 && verifierCallDelta > 0)) {
    return "negative_transfer";
  }
  return "neutral";
}

function guardKey(sourceDomains          , targetDomain        )         {
  return `${sourceDomains.join("\u0000")}\u0001${targetDomain}`;
}

function compareEntry(left                    , right                    )         {
  return compareCodePoint(left.targetDomain, right.targetDomain)
    || compareCodePoint(left.sourceDomains.join("\u0000"), right.sourceDomains.join("\u0000"))
    || compareCodePoint(left.certificateHash, right.certificateHash);
}

function moreConservative(candidate                    , existing                    )          {
  const candidatePriority = conclusionPriority(candidate.conclusion);
  const existingPriority = conclusionPriority(existing.conclusion);
  if (candidatePriority !== existingPriority) {
    return candidatePriority > existingPriority;
  }
  if (Math.abs(candidate.successDelta) !== Math.abs(existing.successDelta)) {
    return Math.abs(candidate.successDelta) > Math.abs(existing.successDelta);
  }
  if (Math.abs(candidate.verifierCallDelta) !== Math.abs(existing.verifierCallDelta)) {
    return Math.abs(candidate.verifierCallDelta) > Math.abs(existing.verifierCallDelta);
  }
  return compareCodePoint(candidate.certificateHash, existing.certificateHash) < 0;
}

function conclusionPriority(conclusion        )         {
  if (conclusion === "negative_transfer") {
    return 3;
  }
  if (conclusion === "neutral") {
    return 2;
  }
  if (conclusion === "positive_transfer") {
    return 1;
  }
  return 0;
}

function uniqueSorted(values          )           {
  const rows = values.map(String).filter((value) => value.length > 0).sort(compareCodePoint);
  if (new Set(rows).size !== rows.length) {
    throw new Error("domains must be unique");
  }
  return rows;
}

function sortedUniqueNonempty(values          )          {
  return values.length > 0
    && values.every((value) => typeof value === "string" && value.length > 0)
    && values.every((value, idx) => idx === 0 || compareCodePoint(values[idx - 1], value) < 0);
}

function uniqueHashes(values          )          {
  return values.length > 0 && new Set(values).size === values.length && values.every(isHash);
}

function disjoint(left          , right          )          {
  const rightSet = new Set(right);
  return left.every((value) => !rightSet.has(value));
}

function isHash(value        )          {
  return /^[0-9a-f]{64}$/.test(value);
}
