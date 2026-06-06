import assert from "node:assert/strict";
import test from "node:test";

import {
  GridMacroAdapter,
  Ledger,
  PrefixSafeMacroRuntime,
  RrlmMacroProposer,
  TransactionEngine,
  buildRrlmProposalCertificate,
  buildRrlmTransportCertificate,
  defaultGridMacros,
  defaultGridState,
  rrlmMacroSnapshotHash,
  rrlmProposalCertificateHash,
  rrlmTransportCertificateHash,
  rrlmTransportCpu,
  rrlmTransportI32Admissible,
  rrlmTransportWgsl,
  runRrlmMacroBenchmark,
  validateRrlmMacroSnapshot,
  validateRrlmProposalCertificate,
  validateRrlmTransportCertificate,
} from "../dist/index.js";

test("RRLM transport helper matches exact inverse formula", () => {
  const z = [0n, -1n, 2n, 1n];
  const params = { acceptedGain: 64n, rejectPenalty: 32n, lengthPenalty: 1n, length: 4 };
  const forward = rrlmTransportCpu(z, params, "forward");

  assert.deepEqual(forward, [96n, -5n, 2n, 1n]);
  assert.deepEqual(rrlmTransportCpu(forward, params, "inverse"), z);
  assert.equal(rrlmTransportI32Admissible(z, params), true);
  assert.equal(
    rrlmTransportI32Admissible([0n, 0n, 2n ** 30n, 0n], {
      acceptedGain: 4n,
      rejectPenalty: 0n,
      lengthPenalty: 1n,
      length: 1,
    }),
    false,
  );
  assert.match(rrlmTransportWgsl("forward"), /deltaScore/);
  assert.match(rrlmTransportWgsl("inverse"), /data\[0\] = data\[0\] - deltaScore/);
});

test("RRLM macro latent proposals cycle exactly", () => {
  const proposer = new RrlmMacroProposer();
  const ranking = proposer.propose("grid-3x3", defaultGridMacros());

  assert.equal(ranking.cycleFailureCount, 0);
  assert.equal(ranking.rankedMacros[0].macroId, "unsafe-through-wall");
  for (const proposal of ranking.proposals) {
    assert.deepEqual(
      proposer.coupling.inverse(proposal.latentAfter, { length: proposal.macro.steps.length }),
      proposal.latentBefore,
    );
  }
});

test("RRLM learns from receipts without commit authority", async () => {
  const proposer = new RrlmMacroProposer();
  const adapter = new GridMacroAdapter();
  const engine = new TransactionEngine(adapter, new Ledger());
  const runtime = new PrefixSafeMacroRuntime(engine, adapter);

  for (const macro of defaultGridMacros()) {
    const outcome = await runtime.run(defaultGridState(), macro);
    proposer.update(outcome.receipt);
    if (outcome.committed) break;
  }

  const ranking = proposer.propose("grid-3x3", defaultGridMacros());

  assert.equal(ranking.cycleFailureCount, 0);
  assert.equal(ranking.rankedMacros[0].macroId, "safe-around-wall");
  assert.equal(await engine.ledger.audit(), true);
  assert.equal(engine.invalidCommitCount, 0);
  assert.equal(engine.hardVerifierCalls, 1);
});

test("RRLM snapshot and proposal certificate validate exact transport", async () => {
  const proposer = new RrlmMacroProposer();
  const adapter = new GridMacroAdapter();
  const engine = new TransactionEngine(adapter, new Ledger());
  const runtime = new PrefixSafeMacroRuntime(engine, adapter);
  for (const macro of defaultGridMacros()) {
    const outcome = await runtime.run(defaultGridState(), macro);
    proposer.update(outcome.receipt);
    if (outcome.committed) break;
  }

  const snapshot = await proposer.snapshot();
  const ranking = proposer.propose("grid-3x3", defaultGridMacros());
  const certificate = await buildRrlmProposalCertificate(snapshot, ranking);
  const transportCertificate = await buildRrlmTransportCertificate(certificate);
  const tamperedSnapshot = {
    ...snapshot,
    rows: [{ ...snapshot.rows[0], acceptedCount: snapshot.rows[0].acceptedCount + 1 }, ...snapshot.rows.slice(1)],
    snapshotHash: "",
  };
  tamperedSnapshot.snapshotHash = await rrlmMacroSnapshotHash(tamperedSnapshot);
  const tamperedCertificate = {
    ...certificate,
    scores: [certificate.scores[0] + 1, ...certificate.scores.slice(1)],
    certificateHash: "",
  };
  tamperedCertificate.certificateHash = await rrlmProposalCertificateHash(tamperedCertificate);
  const duplicateMacroCertificate = {
    ...certificate,
    macroIds: [certificate.macroIds[1], ...certificate.macroIds.slice(1)],
    certificateHash: "",
  };
  duplicateMacroCertificate.certificateHash = await rrlmProposalCertificateHash(duplicateMacroCertificate);
  const duplicateTokenCertificate = {
    ...certificate,
    proposalTokens: [certificate.proposalTokens[1], ...certificate.proposalTokens.slice(1)],
    certificateHash: "",
  };
  duplicateTokenCertificate.certificateHash = await rrlmProposalCertificateHash(duplicateTokenCertificate);
  const unsafeAccepted = Number.MAX_SAFE_INTEGER + 1;
  const unsafeScore = certificate.acceptedGain * unsafeAccepted
    - certificate.rejectPenalty * certificate.rejectedPrefixCounts[0];
  const unsafeCertificate = {
    ...certificate,
    proposalCount: Number.MAX_SAFE_INTEGER + 1,
    acceptedCounts: [unsafeAccepted, ...certificate.acceptedCounts.slice(1)],
    latentBefore: [
      [0, -certificate.originalIndices[0], unsafeAccepted, certificate.rejectedPrefixCounts[0]],
      ...certificate.latentBefore.slice(1),
    ],
    latentAfter: [
      [
        unsafeScore,
        -certificate.originalIndices[0] - certificate.lengthPenalty * certificate.macroLengths[0],
        unsafeAccepted,
        certificate.rejectedPrefixCounts[0],
      ],
      ...certificate.latentAfter.slice(1),
    ],
    scores: [unsafeScore, ...certificate.scores.slice(1)],
    certificateHash: "",
  };
  unsafeCertificate.certificateHash = await rrlmProposalCertificateHash(unsafeCertificate);
  const tamperedTransport = {
    ...transportCertificate,
    latentRoundtrip: [
      [transportCertificate.latentRoundtrip[0][0] + 1, ...transportCertificate.latentRoundtrip[0].slice(1)],
      ...transportCertificate.latentRoundtrip.slice(1),
    ],
    certificateHash: "",
  };
  tamperedTransport.certificateHash = await rrlmTransportCertificateHash(tamperedTransport);

  assert.equal(await validateRrlmMacroSnapshot(snapshot), true);
  assert.equal(await validateRrlmProposalCertificate(certificate, snapshot), true);
  assert.equal(await validateRrlmTransportCertificate(transportCertificate, certificate), true);
  assert.equal(certificate.snapshotHash, snapshot.snapshotHash);
  assert.equal(certificate.cycleFailureCount, 0);
  assert.equal(transportCertificate.proposalCertificateHash, certificate.certificateHash);
  assert.equal(transportCertificate.cycleFailureCount, 0);
  assert.equal(transportCertificate.i32AdmissibleCount, transportCertificate.proposalCount);
  assert.equal(transportCertificate.i32RejectedCount, 0);
  assert.equal(certificate.macroIds[0], "safe-around-wall");
  assert.equal(await validateRrlmMacroSnapshot(tamperedSnapshot), false);
  assert.equal(await validateRrlmProposalCertificate(tamperedCertificate, snapshot), false);
  assert.equal(await validateRrlmTransportCertificate(tamperedTransport, certificate), false);
  assert.equal(await validateRrlmProposalCertificate(duplicateMacroCertificate, snapshot), false);
  assert.equal(await validateRrlmProposalCertificate(duplicateTokenCertificate, snapshot), false);
  assert.equal(await validateRrlmProposalCertificate(unsafeCertificate), false);
});

test("RRLM benchmark carries matched non-reversible baseline", async () => {
  const report = await runRrlmMacroBenchmark(16);

  assert.equal(report.ledgerAudit, true);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.rrlmCycleFailureCount, 0);
  assert.equal(report.snapshotValid, true);
  assert.equal(report.proposalCertificateValid, true);
  assert.equal(report.transportCertificateValid, true);
  assert.ok(report.transportCertificateI32AdmissibleCount > 0);
  assert.equal(report.transportCertificateI32RejectedCount, 0);
  assert.equal(report.snapshotTamperDetected, true);
  assert.equal(report.proposalTamperDetected, true);
  assert.equal(report.transportTamperDetected, true);
  assert.match(report.snapshotHash, /^[0-9a-f]{64}$/);
  assert.match(report.proposalCertificateHash, /^[0-9a-f]{64}$/);
  assert.match(report.transportCertificateHash, /^[0-9a-f]{64}$/);
  assert.ok(report.rrlmAttemptsPerSuccess < report.reversibleOnlyAttemptsPerSuccess);
  assert.equal(report.rrlmVsNonReversibleGain, 1);
  assert.ok(report.rrlmReuseGain > 1.5);
  assert.equal(report.reversibleOnlyPrefixRejectCount, 16);
  assert.equal(report.rrlmPrefixRejectCount, 1);
});
