import { canonicalJson, stableHash } from "./canonical.js";

import { Ledger } from "./core.js";
import { AdditiveCoupling,                 } from "./reversible.js";
import {


  defaultGridMacros,
  runPrefixSafeGridSequence,
} from "./macro.js";

export const RRLM_MACRO_SNAPSHOT_SCHEMA = "trwm.rrlm_macro_snapshot.v1";
export const RRLM_PROPOSAL_CERTIFICATE_SCHEMA = "trwm.rrlm_proposal_certificate.v1";
export const RRLM_TRANSPORT_CERTIFICATE_SCHEMA = "trwm.rrlm_transport_certificate.v1";
export const RRLM_TRANSPORT_SPEC = "rrlm_integer_additive_coupling.v1";




























































































































export class RrlmMacroProposer                 {
  acceptedGain        ;
  rejectPenalty        ;
  lengthPenalty        ;
  proposerId = "rrlm_macro_proposer";
  proposerVersion = "1.0";
  accepted = new Map                             ();
  rejectedPrefixes = new Map                             ();
  sourceReceiptHashes           = [];
  coupling                  ;

  constructor(options              = {}) {
    this.acceptedGain = options.acceptedGain ?? 64n;
    this.rejectPenalty = options.rejectPenalty ?? 32n;
    this.lengthPenalty = options.lengthPenalty ?? 1n;
    this.coupling = new AdditiveCoupling(
      (v, context) => {
        const accepted = v[0];
        const rejected = v[1];
        const length = BigInt(Number(context.length ?? 0));
        return [
          this.acceptedGain * accepted - this.rejectPenalty * rejected,
          -this.lengthPenalty * length,
        ];
      },
      () => [0n, 0n],
      2,
    );
  }

  update(receipt         )       {
    const payload = receiptPayload(receipt);
    const context = String(payload.context ?? "global");
    const token = tokenFromUnknown(payload.macro ?? []);
    let counted = false;
    if (receipt.hardResult.result === "accept" && receipt.committed) {
      increment(this.accepted, context, token);
      counted = true;
    } else if (receipt.commitDecision === "prefix_unsafe" || receipt.hardResult.result === "reject") {
      increment(this.rejectedPrefixes, context, token);
      counted = true;
    }
    if (counted && isHash(receipt.receiptHash)) {
      this.sourceReceiptHashes.push(receipt.receiptHash);
    }
  }

  propose(context        , macros                    )                    {
    const proposals = macros
      .map((macro, idx) => this.proposal(context, macro, idx))
      .sort((a, b) => {
        const scoreDiff = compareBigIntDesc(a.score, b.score);
        if (scoreDiff !== 0) return scoreDiff;
        const tieDiff = compareBigIntDesc(a.latentAfter[1], b.latentAfter[1]);
        if (tieDiff !== 0) return tieDiff;
        return a.originalIndex - b.originalIndex;
      });
    return {
      context,
      proposals,
      rankedMacros: proposals.map((proposal) => proposal.macro),
      cycleFailureCount: proposals.filter((proposal) => !proposal.cycleOk).length,
    };
  }

  rank(context        , macros                    )                     {
    return this.propose(context, macros).rankedMacros;
  }

  counts(context        , macro             )                                                 {
    const token = tokenFromUnknown(macro.steps);
    return {
      accepted: getCount(this.accepted, context, token),
      rejectedPrefixes: getCount(this.rejectedPrefixes, context, token),
    };
  }

  async snapshot()                             {
    const contexts = new Set([...this.accepted.keys(), ...this.rejectedPrefixes.keys()]);
    const rows                       = [];
    for (const context of Array.from(contexts).sort()) {
      const tokens = new Set([
        ...Array.from(this.accepted.get(context)?.keys() ?? []),
        ...Array.from(this.rejectedPrefixes.get(context)?.keys() ?? []),
      ]);
      for (const token of Array.from(tokens).sort()) {
        rows.push({
          context,
          token,
          acceptedCount: getCount(this.accepted, context, token),
          rejectedPrefixCount: getCount(this.rejectedPrefixes, context, token),
        });
      }
    }
    const pending                    = {
      schemaVersion: RRLM_MACRO_SNAPSHOT_SCHEMA,
      proposerId: this.proposerId,
      proposerVersion: this.proposerVersion,
      acceptedGain: numberTick(this.acceptedGain, "acceptedGain"),
      rejectPenalty: numberTick(this.rejectPenalty, "rejectPenalty"),
      lengthPenalty: numberTick(this.lengthPenalty, "lengthPenalty"),
      rows,
      sourceReceiptHashes: [...this.sourceReceiptHashes],
      snapshotHash: "",
    };
    return { ...pending, snapshotHash: await rrlmMacroSnapshotHash(pending) };
  }

          proposal(context        , macro             , idx        )                          {
    const token = tokenFromUnknown(macro.steps);
    const accepted = getCount(this.accepted, context, token);
    const rejected = getCount(this.rejectedPrefixes, context, token);
    const latentBefore = [0n, BigInt(-idx), BigInt(accepted), BigInt(rejected)];
    const couplingContext = { length: macro.steps.length };
    const transportParams = {
      acceptedGain: this.acceptedGain,
      rejectPenalty: this.rejectPenalty,
      lengthPenalty: this.lengthPenalty,
      length: macro.steps.length,
    };
    const latentAfter = rrlmTransportCpu(latentBefore, transportParams, "forward");
    const cycleOk = equalTicks(rrlmTransportCpu(latentAfter, transportParams, "inverse"), latentBefore)
      && equalTicks(this.coupling.inverse(latentAfter, couplingContext), latentBefore);
    return {
      macro,
      originalIndex: idx,
      token,
      latentBefore,
      latentAfter,
      score: latentAfter[0],
      acceptedCount: accepted,
      rejectedPrefixCount: rejected,
      cycleOk,
    };
  }
}

export async function buildRrlmProposalCertificate      (
  snapshot                   ,
  ranking                   ,
)                                   {
  const pending                          = {
    schemaVersion: RRLM_PROPOSAL_CERTIFICATE_SCHEMA,
    context: ranking.context,
    proposerId: snapshot.proposerId,
    proposerVersion: snapshot.proposerVersion,
    snapshotHash: snapshot.snapshotHash,
    acceptedGain: snapshot.acceptedGain,
    rejectPenalty: snapshot.rejectPenalty,
    lengthPenalty: snapshot.lengthPenalty,
    proposalCount: ranking.proposals.length,
    macroIds: ranking.proposals.map((proposal) => proposal.macro.macroId),
    proposalTokens: ranking.proposals.map((proposal) => proposal.token),
    originalIndices: ranking.proposals.map((proposal) => proposal.originalIndex),
    macroLengths: ranking.proposals.map((proposal) => proposal.macro.steps.length),
    acceptedCounts: ranking.proposals.map((proposal) => proposal.acceptedCount),
    rejectedPrefixCounts: ranking.proposals.map((proposal) => proposal.rejectedPrefixCount),
    latentBefore: ranking.proposals.map((proposal) => ticksToNumbers(proposal.latentBefore)),
    latentAfter: ranking.proposals.map((proposal) => ticksToNumbers(proposal.latentAfter)),
    scores: ranking.proposals.map((proposal) => numberTick(proposal.score, "score")),
    cycleFailureCount: ranking.cycleFailureCount,
    certificateHash: "",
  };
  return { ...pending, certificateHash: await rrlmProposalCertificateHash(pending) };
}

export async function buildRrlmTransportCertificate(
  certificate                         ,
)                                    {
  const latentRoundtrip = certificate.latentAfter.map((latent, idx) => ticksToNumbers(
    rrlmTransportCpu(
      latent.map((value) => BigInt(value)),
      transportParamsFromCertificate(certificate, idx),
      "inverse",
    ),
  ));
  const i32Flags = certificate.latentBefore.map((latent, idx) => rrlmTransportI32Admissible(
    latent.map((value) => BigInt(value)),
    transportParamsFromCertificate(certificate, idx),
  ));
  const pending                           = {
    schemaVersion: RRLM_TRANSPORT_CERTIFICATE_SCHEMA,
    transportSpec: RRLM_TRANSPORT_SPEC,
    context: certificate.context,
    proposerId: certificate.proposerId,
    proposerVersion: certificate.proposerVersion,
    snapshotHash: certificate.snapshotHash,
    proposalCertificateHash: certificate.certificateHash,
    acceptedGain: certificate.acceptedGain,
    rejectPenalty: certificate.rejectPenalty,
    lengthPenalty: certificate.lengthPenalty,
    proposalCount: certificate.proposalCount,
    macroLengths: [...certificate.macroLengths],
    latentBefore: certificate.latentBefore.map((latent) => [...latent]),
    latentAfter: certificate.latentAfter.map((latent) => [...latent]),
    latentRoundtrip,
    cycleFailureCount: certificate.latentBefore.filter((latent, idx) => !sameNumberArray(latent, latentRoundtrip[idx])).length,
    i32AdmissibleCount: i32Flags.filter(Boolean).length,
    i32RejectedCount: i32Flags.filter((flag) => !flag).length,
    certificateHash: "",
  };
  return { ...pending, certificateHash: await rrlmTransportCertificateHash(pending) };
}

export async function rrlmMacroSnapshotHash(snapshot                   )                  {
  const { snapshotHash: _snapshotHash, ...withoutHash } = snapshot;
  return stableHash(withoutHash);
}

export async function rrlmProposalCertificateHash(certificate                         )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function rrlmTransportCertificateHash(certificate                          )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function validateRrlmMacroSnapshot(snapshot                   )                   {
  try {
    if (snapshot.schemaVersion !== RRLM_MACRO_SNAPSHOT_SCHEMA) {
      return false;
    }
    if (![snapshot.proposerId, snapshot.proposerVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (![snapshot.acceptedGain, snapshot.rejectPenalty, snapshot.lengthPenalty].every(nonnegativeInteger)) {
      return false;
    }
    if (!snapshot.rows.every((row, idx) => idx === 0 || compareRow(snapshot.rows[idx - 1], row) <= 0)) {
      return false;
    }
    const keys = new Set        ();
    let evidenceCount = 0;
    for (const row of snapshot.rows) {
      if (typeof row.context !== "string" || !row.context || typeof row.token !== "string" || !row.token) {
        return false;
      }
      if (!nonnegativeInteger(row.acceptedCount) || !nonnegativeInteger(row.rejectedPrefixCount)) {
        return false;
      }
      const key = `${row.context}\u0000${row.token}`;
      if (keys.has(key)) {
        return false;
      }
      keys.add(key);
      evidenceCount += row.acceptedCount + row.rejectedPrefixCount;
    }
    if (snapshot.sourceReceiptHashes.length !== evidenceCount) {
      return false;
    }
    if (snapshot.sourceReceiptHashes.length !== new Set(snapshot.sourceReceiptHashes).size) {
      return false;
    }
    if (!snapshot.sourceReceiptHashes.every(isHash)) {
      return false;
    }
    return snapshot.snapshotHash === await rrlmMacroSnapshotHash(snapshot);
  } catch (_error) {
    return false;
  }
}

export async function validateRrlmProposalCertificate(
  certificate                         ,
  snapshot                    ,
)                   {
  try {
    if (certificate.schemaVersion !== RRLM_PROPOSAL_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (![certificate.context, certificate.proposerId, certificate.proposerVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!isHash(certificate.snapshotHash)) {
      return false;
    }
    if (![certificate.acceptedGain, certificate.rejectPenalty, certificate.lengthPenalty].every(nonnegativeInteger)) {
      return false;
    }
    if (!safeInteger(certificate.proposalCount) || certificate.proposalCount <= 0) {
      return false;
    }
    const fields = [
      certificate.macroIds,
      certificate.proposalTokens,
      certificate.originalIndices,
      certificate.macroLengths,
      certificate.acceptedCounts,
      certificate.rejectedPrefixCounts,
      certificate.latentBefore,
      certificate.latentAfter,
      certificate.scores,
    ];
    if (fields.some((field) => field.length !== certificate.proposalCount)) {
      return false;
    }
    if (certificate.macroIds.length !== new Set(certificate.macroIds).size) {
      return false;
    }
    if (certificate.proposalTokens.length !== new Set(certificate.proposalTokens).size) {
      return false;
    }
    if (certificate.originalIndices.length !== new Set(certificate.originalIndices).size) {
      return false;
    }
    const snapshotRows = new Map                            ();
    if (snapshot) {
      if (!await validateRrlmMacroSnapshot(snapshot)) {
        return false;
      }
      if (snapshot.snapshotHash !== certificate.snapshotHash) {
        return false;
      }
      if (snapshot.proposerId !== certificate.proposerId || snapshot.proposerVersion !== certificate.proposerVersion) {
        return false;
      }
      if (snapshot.acceptedGain !== certificate.acceptedGain || snapshot.rejectPenalty !== certificate.rejectPenalty || snapshot.lengthPenalty !== certificate.lengthPenalty) {
        return false;
      }
      for (const row of snapshot.rows) {
        snapshotRows.set(`${row.context}\u0000${row.token}`, row);
      }
    }
    let cycleFailures = 0;
    const orderKeys                                  = [];
    for (let idx = 0; idx < certificate.proposalCount; idx += 1) {
      if (!certificate.macroIds[idx] || !certificate.proposalTokens[idx]) {
        return false;
      }
      const numericValues = [
        certificate.originalIndices[idx],
        certificate.macroLengths[idx],
        certificate.acceptedCounts[idx],
        certificate.rejectedPrefixCounts[idx],
        certificate.scores[idx],
      ];
      if (!numericValues.every(safeInteger)) {
        return false;
      }
      if (certificate.originalIndices[idx] < 0 || certificate.macroLengths[idx] < 0 || certificate.acceptedCounts[idx] < 0 || certificate.rejectedPrefixCounts[idx] < 0) {
        return false;
      }
      const before = certificate.latentBefore[idx];
      const after = certificate.latentAfter[idx];
      if (before.length !== 4 || after.length !== 4 || ![...before, ...after].every(safeInteger)) {
        return false;
      }
      const expectedBefore = [0, -certificate.originalIndices[idx], certificate.acceptedCounts[idx], certificate.rejectedPrefixCounts[idx]];
      const expectedAfter = [
        before[0] + certificate.acceptedGain * before[2] - certificate.rejectPenalty * before[3],
        before[1] - certificate.lengthPenalty * certificate.macroLengths[idx],
        before[2],
        before[3],
      ];
      if (!sameNumberArray(before, expectedBefore) || !sameNumberArray(after, expectedAfter)) {
        return false;
      }
      if (certificate.scores[idx] !== after[0]) {
        return false;
      }
      const inverse = [
        after[0] - certificate.acceptedGain * after[2] + certificate.rejectPenalty * after[3],
        after[1] + certificate.lengthPenalty * certificate.macroLengths[idx],
        after[2],
        after[3],
      ];
      if (!sameNumberArray(inverse, before)) {
        cycleFailures += 1;
      }
      if (snapshot) {
        const row = snapshotRows.get(`${certificate.context}\u0000${certificate.proposalTokens[idx]}`);
        const accepted = row?.acceptedCount ?? 0;
        const rejected = row?.rejectedPrefixCount ?? 0;
        if (accepted !== certificate.acceptedCounts[idx] || rejected !== certificate.rejectedPrefixCounts[idx]) {
          return false;
        }
      }
      orderKeys.push([-certificate.scores[idx], -after[1], certificate.originalIndices[idx]]);
    }
    if (cycleFailures !== certificate.cycleFailureCount) {
      return false;
    }
    const sorted = [...orderKeys].sort(compareOrderKey);
    if (!orderKeys.every((key, idx) => sameNumberArray(key, sorted[idx]))) {
      return false;
    }
    return certificate.certificateHash === await rrlmProposalCertificateHash(certificate);
  } catch (_error) {
    return false;
  }
}

export async function validateRrlmTransportCertificate(
  certificate                          ,
  proposalCertificate                          ,
)                   {
  try {
    if (certificate.schemaVersion !== RRLM_TRANSPORT_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (certificate.transportSpec !== RRLM_TRANSPORT_SPEC) {
      return false;
    }
    if (![certificate.context, certificate.proposerId, certificate.proposerVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!isHash(certificate.snapshotHash) || !isHash(certificate.proposalCertificateHash)) {
      return false;
    }
    if (![certificate.acceptedGain, certificate.rejectPenalty, certificate.lengthPenalty].every(nonnegativeInteger)) {
      return false;
    }
    if (!safeInteger(certificate.proposalCount) || certificate.proposalCount <= 0) {
      return false;
    }
    if (
      certificate.macroLengths.length !== certificate.proposalCount
      || certificate.latentBefore.length !== certificate.proposalCount
      || certificate.latentAfter.length !== certificate.proposalCount
      || certificate.latentRoundtrip.length !== certificate.proposalCount
    ) {
      return false;
    }
    if (proposalCertificate) {
      if (!await validateRrlmProposalCertificate(proposalCertificate)) {
        return false;
      }
      if (proposalCertificate.certificateHash !== certificate.proposalCertificateHash) {
        return false;
      }
      if (proposalCertificate.snapshotHash !== certificate.snapshotHash) {
        return false;
      }
      if (proposalCertificate.context !== certificate.context) {
        return false;
      }
      if (proposalCertificate.proposerId !== certificate.proposerId || proposalCertificate.proposerVersion !== certificate.proposerVersion) {
        return false;
      }
      if (
        proposalCertificate.acceptedGain !== certificate.acceptedGain
        || proposalCertificate.rejectPenalty !== certificate.rejectPenalty
        || proposalCertificate.lengthPenalty !== certificate.lengthPenalty
        || proposalCertificate.proposalCount !== certificate.proposalCount
        || !sameNumberArray(proposalCertificate.macroLengths, certificate.macroLengths)
        || !sameNestedNumberArray(proposalCertificate.latentBefore, certificate.latentBefore)
        || !sameNestedNumberArray(proposalCertificate.latentAfter, certificate.latentAfter)
      ) {
        return false;
      }
    }
    let cycleFailures = 0;
    let i32AdmissibleCount = 0;
    for (let idx = 0; idx < certificate.proposalCount; idx += 1) {
      const length = certificate.macroLengths[idx];
      const before = certificate.latentBefore[idx];
      const after = certificate.latentAfter[idx];
      const roundtrip = certificate.latentRoundtrip[idx];
      if (!nonnegativeInteger(length)) {
        return false;
      }
      if (![before, after, roundtrip].every((latent) => latent.length === 4 && latent.every(safeInteger))) {
        return false;
      }
      const params = transportParamsFromCertificate(certificate, idx);
      const expectedAfter = ticksToNumbers(rrlmTransportCpu(before.map((value) => BigInt(value)), params, "forward"));
      const expectedRoundtrip = ticksToNumbers(rrlmTransportCpu(after.map((value) => BigInt(value)), params, "inverse"));
      if (!sameNumberArray(after, expectedAfter) || !sameNumberArray(roundtrip, expectedRoundtrip)) {
        return false;
      }
      if (!sameNumberArray(roundtrip, before)) {
        cycleFailures += 1;
      }
      if (rrlmTransportI32Admissible(before.map((value) => BigInt(value)), params)) {
        i32AdmissibleCount += 1;
      }
    }
    if (cycleFailures !== certificate.cycleFailureCount) {
      return false;
    }
    if (i32AdmissibleCount !== certificate.i32AdmissibleCount) {
      return false;
    }
    if (certificate.i32RejectedCount !== certificate.proposalCount - i32AdmissibleCount) {
      return false;
    }
    return certificate.certificateHash === await rrlmTransportCertificateHash(certificate);
  } catch (_error) {
    return false;
  }
}

export class NonReversibleMacroRanker                 {
  acceptedGain        ;
  rejectPenalty        ;
  lengthPenalty        ;
  accepted = new Map                             ();
  rejectedPrefixes = new Map                             ();

  constructor(options              = {}) {
    this.acceptedGain = options.acceptedGain ?? 64n;
    this.rejectPenalty = options.rejectPenalty ?? 32n;
    this.lengthPenalty = options.lengthPenalty ?? 1n;
  }

  update(receipt         )       {
    const payload = receiptPayload(receipt);
    const context = String(payload.context ?? "global");
    const token = tokenFromUnknown(payload.macro ?? []);
    if (receipt.hardResult.result === "accept" && receipt.committed) {
      increment(this.accepted, context, token);
    } else if (receipt.commitDecision === "prefix_unsafe") {
      increment(this.rejectedPrefixes, context, token);
    }
  }

  rank(context        , macros                    )                     {
    return macros
      .map((macro, idx) => {
        const token = tokenFromUnknown(macro.steps);
        const score = this.acceptedGain * BigInt(getCount(this.accepted, context, token))
          - this.rejectPenalty * BigInt(getCount(this.rejectedPrefixes, context, token));
        const tie = -this.lengthPenalty * BigInt(macro.steps.length) - BigInt(idx);
        return { macro, idx, score, tie };
      })
      .sort((a, b) => {
        const scoreDiff = compareBigIntDesc(a.score, b.score);
        if (scoreDiff !== 0) return scoreDiff;
        const tieDiff = compareBigIntDesc(a.tie, b.tie);
        if (tieDiff !== 0) return tieDiff;
        return a.idx - b.idx;
      })
      .map((row) => row.macro);
  }
}

export async function runRrlmMacroBenchmark(episodes = 32)                           {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be a positive integer");
  }
  const macros = defaultGridMacros();
  const reversibleOnly = new RrlmMacroProposer          ();
  const reversibleOnlyStats = await runRrlmLane(macros, episodes, reversibleOnly, false);

  const matchedNonReversible = new NonReversibleMacroRanker          ();
  const matchedStats = await runRankerLane(macros, episodes, (context, values) => matchedNonReversible.rank(context, values), matchedNonReversible);

  const rrlm = new RrlmMacroProposer          ();
  const rrlmStats = await runRrlmLane(macros, episodes, rrlm, true);
  const snapshot = await rrlm.snapshot();
  const proposalCertificate = await buildRrlmProposalCertificate(snapshot, rrlm.propose("grid-3x3", macros));
  const transportCertificate = await buildRrlmTransportCertificate(proposalCertificate);
  const tamperedSnapshot = {
    ...snapshot,
    rows: [{ ...snapshot.rows[0], acceptedCount: snapshot.rows[0].acceptedCount + 1 }, ...snapshot.rows.slice(1)],
    snapshotHash: "",
  };
  tamperedSnapshot.snapshotHash = await rrlmMacroSnapshotHash(tamperedSnapshot);
  const tamperedCertificate = {
    ...proposalCertificate,
    scores: [proposalCertificate.scores[0] + 1, ...proposalCertificate.scores.slice(1)],
    certificateHash: "",
  };
  tamperedCertificate.certificateHash = await rrlmProposalCertificateHash(tamperedCertificate);
  const tamperedTransport = {
    ...transportCertificate,
    latentRoundtrip: [
      [transportCertificate.latentRoundtrip[0][0] + 1, ...transportCertificate.latentRoundtrip[0].slice(1)],
      ...transportCertificate.latentRoundtrip.slice(1),
    ],
    certificateHash: "",
  };
  tamperedTransport.certificateHash = await rrlmTransportCertificateHash(tamperedTransport);

  return {
    reversibleOnlyAttemptsPerSuccess: reversibleOnlyStats.attemptsPerSuccess,
    matchedNonReversibleAttemptsPerSuccess: matchedStats.attemptsPerSuccess,
    rrlmAttemptsPerSuccess: rrlmStats.attemptsPerSuccess,
    reversibleOnlyPrefixRejectCount: reversibleOnlyStats.prefixRejects,
    matchedNonReversiblePrefixRejectCount: matchedStats.prefixRejects,
    rrlmPrefixRejectCount: rrlmStats.prefixRejects,
    rrlmReuseGain: reversibleOnlyStats.attemptsPerSuccess / rrlmStats.attemptsPerSuccess,
    rrlmVsNonReversibleGain: matchedStats.attemptsPerSuccess / rrlmStats.attemptsPerSuccess,
    rrlmCycleFailureCount: reversibleOnlyStats.cycleFailures + rrlmStats.cycleFailures,
    snapshotValid: await validateRrlmMacroSnapshot(snapshot),
    proposalCertificateValid: await validateRrlmProposalCertificate(proposalCertificate, snapshot),
    transportCertificateValid: await validateRrlmTransportCertificate(transportCertificate, proposalCertificate),
    transportCertificateI32AdmissibleCount: transportCertificate.i32AdmissibleCount,
    transportCertificateI32RejectedCount: transportCertificate.i32RejectedCount,
    snapshotTamperDetected: !await validateRrlmMacroSnapshot(tamperedSnapshot),
    proposalTamperDetected: !await validateRrlmProposalCertificate(tamperedCertificate, snapshot),
    transportTamperDetected: !await validateRrlmTransportCertificate(tamperedTransport, proposalCertificate),
    snapshotHash: snapshot.snapshotHash,
    proposalCertificateHash: proposalCertificate.certificateHash,
    transportCertificateHash: transportCertificate.certificateHash,
    ledgerAudit: await reversibleOnlyStats.ledger.audit() && await matchedStats.ledger.audit() && await rrlmStats.ledger.audit(),
    invalidCommitCount: invalidCommits([reversibleOnlyStats.ledger, matchedStats.ledger, rrlmStats.ledger]),
  };
}

export function rrlmTransportCpu(
  z            ,
  params                     ,
  direction                         = "forward",
)             {
  assertRrlmShape(z);
  const deltaScore = params.acceptedGain * z[2] - params.rejectPenalty * z[3];
  const deltaTie = -params.lengthPenalty * BigInt(params.length);
  if (direction === "forward") {
    return [z[0] + deltaScore, z[1] + deltaTie, z[2], z[3]];
  }
  return [z[0] - deltaScore, z[1] - deltaTie, z[2], z[3]];
}

export function rrlmTransportI32Admissible(
  z            ,
  params                     ,
)          {
  try {
    assertRrlmI32Safe(z, params, "forward");
    return true;
  } catch (_error) {
    return false;
  }
}

export function rrlmTransportWgsl(direction                        )         {
  if (direction === "forward") {
    return `
struct Params {
  acceptedGain: i32,
  rejectPenalty: i32,
  lengthPenalty: i32,
  length: i32,
};
@group(0) @binding(0) var<storage, read_write> data: array<i32>;
@group(0) @binding(1) var<uniform> params: Params;

@compute @workgroup_size(1)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  if (id.x > 0u) { return; }
  let deltaScore = params.acceptedGain * data[2] - params.rejectPenalty * data[3];
  let deltaTie = -(params.lengthPenalty * params.length);
  data[0] = data[0] + deltaScore;
  data[1] = data[1] + deltaTie;
}`;
  }
  return `
struct Params {
  acceptedGain: i32,
  rejectPenalty: i32,
  lengthPenalty: i32,
  length: i32,
};
@group(0) @binding(0) var<storage, read_write> data: array<i32>;
@group(0) @binding(1) var<uniform> params: Params;

@compute @workgroup_size(1)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  if (id.x > 0u) { return; }
  let deltaScore = params.acceptedGain * data[2] - params.rejectPenalty * data[3];
  let deltaTie = -(params.lengthPenalty * params.length);
  data[0] = data[0] - deltaScore;
  data[1] = data[1] - deltaTie;
}`;
}

export async function runRrlmTransportWebGpu(
  z            ,
  params                     ,
  direction                         = "forward",
)                      {
  const gpu = globalThis.navigator?.gpu;
  if (!gpu) {
    throw new Error("WebGPU is not available in this runtime");
  }
  const data = assertRrlmI32Safe(z, params, direction);
  const adapter = await gpu.requestAdapter();
  if (!adapter) {
    throw new Error("WebGPU adapter request failed");
  }
  const device = await adapter.requestDevice();
  const shader = device.createShaderModule({ code: rrlmTransportWgsl(direction) });
  const pipeline = device.createComputePipeline({
    layout: "auto",
    compute: { module: shader, entryPoint: "main" },
  });
  const storageBuffer = device.createBuffer({
    size: data.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST,
  });
  device.queue.writeBuffer(storageBuffer, 0, data);
  const paramsBuffer = device.createBuffer({
    size: 16,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  });
  const paramsData = new ArrayBuffer(16);
  const view = new DataView(paramsData);
  view.setInt32(0, Number(params.acceptedGain), true);
  view.setInt32(4, Number(params.rejectPenalty), true);
  view.setInt32(8, Number(params.lengthPenalty), true);
  view.setInt32(12, params.length, true);
  device.queue.writeBuffer(paramsBuffer, 0, paramsData);
  const outputBuffer = device.createBuffer({
    size: data.byteLength,
    usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
  });
  const bindGroup = device.createBindGroup({
    layout: pipeline.getBindGroupLayout(0),
    entries: [
      { binding: 0, resource: { buffer: storageBuffer } },
      { binding: 1, resource: { buffer: paramsBuffer } },
    ],
  });
  const encoder = device.createCommandEncoder();
  const pass = encoder.beginComputePass();
  pass.setPipeline(pipeline);
  pass.setBindGroup(0, bindGroup);
  pass.dispatchWorkgroups(1);
  pass.end();
  encoder.copyBufferToBuffer(storageBuffer, 0, outputBuffer, 0, data.byteLength);
  device.queue.submit([encoder.finish()]);
  await outputBuffer.mapAsync(GPUMapMode.READ);
  const result = new Int32Array(outputBuffer.getMappedRange().slice(0));
  outputBuffer.unmap();
  storageBuffer.destroy();
  paramsBuffer.destroy();
  outputBuffer.destroy();
  return Array.from(result, (value) => BigInt(value));
}

async function runRrlmLane(
  macros                        ,
  episodes        ,
  proposer                             ,
  updateFromReceipts         ,
)





   {
  const ledger = new Ledger();
  let attempts = 0;
  let terminalCalls = 0;
  let prefixRejects = 0;
  let successes = 0;
  let cycleFailures = 0;
  for (let idx = 0; idx < episodes; idx += 1) {
    const ranking = proposer.propose("grid-3x3", macros);
    cycleFailures += ranking.cycleFailureCount;
    const result = await runPrefixSafeGridSequence(ranking.rankedMacros, ledger, updateFromReceipts ? proposer : undefined);
    attempts += result.attempts;
    terminalCalls += result.terminalCalls;
    prefixRejects += result.prefixRejects;
    successes += result.success ? 1 : 0;
  }
  return {
    attemptsPerSuccess: attempts / successes,
    terminalCallsPerSuccess: terminalCalls / successes,
    prefixRejects,
    cycleFailures,
    ledger,
  };
}

async function runRankerLane(
  macros                        ,
  episodes        ,
  rank                                                                             ,
  learner                                    ,
)




   {
  const ledger = new Ledger();
  let attempts = 0;
  let terminalCalls = 0;
  let prefixRejects = 0;
  let successes = 0;
  for (let idx = 0; idx < episodes; idx += 1) {
    const result = await runPrefixSafeGridSequence(rank("grid-3x3", macros), ledger, learner);
    attempts += result.attempts;
    terminalCalls += result.terminalCalls;
    prefixRejects += result.prefixRejects;
    successes += result.success ? 1 : 0;
  }
  return {
    attemptsPerSuccess: attempts / successes,
    terminalCallsPerSuccess: terminalCalls / successes,
    prefixRejects,
    ledger,
  };
}

function receiptPayload(receipt         )                          {
  const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
    ? receipt.replayBundle
    : {};
  const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
    ? bundle.candidatePayload
    : {};
  return payload;
}

function tokenFromUnknown(value         )         {
  if (value && typeof value === "object") {
    return canonicalJson(value);
  }
  return String(value);
}

function increment(table                                  , context        , token        )       {
  let row = table.get(context);
  if (!row) {
    row = new Map();
    table.set(context, row);
  }
  row.set(token, (row.get(token) ?? 0) + 1);
}

function getCount(table                                  , context        , token        )         {
  return table.get(context)?.get(token) ?? 0;
}

function compareBigIntDesc(a        , b        )         {
  if (a > b) return -1;
  if (a < b) return 1;
  return 0;
}

function equalTicks(a            , b            )          {
  return a.length === b.length && a.every((value, idx) => value === b[idx]);
}

function sameNestedNumberArray(left            , right            )          {
  return left.length === right.length && left.every((row, idx) => sameNumberArray(row, right[idx]));
}

function transportParamsFromCertificate(
  certificate                                                                                                                               ,
  idx        ,
)                      {
  return {
    acceptedGain: BigInt(certificate.acceptedGain),
    rejectPenalty: BigInt(certificate.rejectPenalty),
    lengthPenalty: BigInt(certificate.lengthPenalty),
    length: certificate.macroLengths[idx],
  };
}

const I32_MIN = BigInt(-(2 ** 31));
const I32_MAX = BigInt(2 ** 31 - 1);

function assertRrlmShape(z            )       {
  if (z.length !== 4) {
    throw new RangeError("RRLM transport requires [score, tie, accepted, rejected] ticks");
  }
}

function assertRrlmI32Safe(
  z            ,
  params                     ,
  direction                        ,
)             {
  assertRrlmShape(z);
  const values = [
    ...z,
    params.acceptedGain,
    params.rejectPenalty,
    params.lengthPenalty,
    BigInt(params.length),
  ];
  values.forEach((value, idx) => assertI32(value, `RRLM i32 value ${idx}`));
  const acceptedTerm = params.acceptedGain * z[2];
  const rejectedTerm = params.rejectPenalty * z[3];
  const deltaScore = acceptedTerm - rejectedTerm;
  const deltaTie = -params.lengthPenalty * BigInt(params.length);
  [acceptedTerm, rejectedTerm, deltaScore, deltaTie].forEach((value, idx) => assertI32(value, `RRLM i32 intermediate ${idx}`));
  const output = rrlmTransportCpu(z, params, direction);
  output.forEach((value, idx) => assertI32(value, `RRLM i32 output ${idx}`));
  const roundtrip = rrlmTransportCpu(output, params, direction === "forward" ? "inverse" : "forward");
  roundtrip.forEach((value, idx) => assertI32(value, `RRLM i32 roundtrip ${idx}`));
  return new Int32Array(z.map((value) => Number(value)));
}

function assertI32(value        , label        )       {
  if (value < I32_MIN || value > I32_MAX) {
    throw new RangeError(`${label} is outside signed i32 WebGPU bounds`);
  }
}

function invalidCommits(ledgers          )         {
  return ledgers.reduce(
    (total, ledger) => total + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
    0,
  );
}

function numberTick(value        , label        )         {
  if (value < BigInt(Number.MIN_SAFE_INTEGER) || value > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new RangeError(`${label} is outside safe integer certificate bounds`);
  }
  return Number(value);
}

function ticksToNumbers(values            )           {
  return values.map((value, idx) => numberTick(value, `latent tick ${idx}`));
}

function nonnegativeInteger(value         )                  {
  return safeInteger(value) && value >= 0;
}

function safeInteger(value         )                  {
  return typeof value === "number" && Number.isSafeInteger(value);
}

function compareRow(left                    , right                    )         {
  if (left.context < right.context) return -1;
  if (left.context > right.context) return 1;
  if (left.token < right.token) return -1;
  if (left.token > right.token) return 1;
  return 0;
}

function compareOrderKey(left          , right          )         {
  for (let idx = 0; idx < left.length; idx += 1) {
    if (left[idx] < right[idx]) return -1;
    if (left[idx] > right[idx]) return 1;
  }
  return 0;
}

function sameNumberArray(left          , right          )          {
  return left.length === right.length && left.every((value, idx) => value === right[idx]);
}

function isHash(value        )          {
  return /^[0-9a-f]{64}$/.test(value);
}
