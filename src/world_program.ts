import { chainHash, stableHash } from "./canonical.js";
import {
  GENESIS_HEAD,
  receiptStaticValid,
  type ProposalTrace,
  type Receipt,
  type TypedCandidate,
} from "./core.js";
import {
  auditWorldLearnerDelta,
  auditWorldLearnerUpdate,
  auditWorldModelStep,
  validateWorldLearnerDeltaCertificate,
  validateWorldLearnerSnapshot,
  validateWorldLearnerUpdateCertificate,
  validateWorldModelStepCertificate,
  type WorldLearnerDeltaCertificate,
  type WorldLearnerSnapshot,
  type WorldLearnerUpdateCertificate,
  type WorldModelStepCertificate,
  type WorldModelStepResult,
} from "./world.js";

export const WORLD_PROGRAM_MANIFEST_SCHEMA = "trwm.world_program_manifest.v1";
export const WORLD_PROGRAM_CERTIFICATE_SCHEMA = "trwm.world_program_certificate.v1";
export const WORLD_PROGRAM_ADMISSION_POLICY_SCHEMA = "trwm.world_program_admission_policy.v1";
export const WORLD_PROGRAM_ADMISSION_CERTIFICATE_SCHEMA = "trwm.world_program_admission_certificate.v1";
export const WORLD_PROGRAM_EVIDENCE_BUNDLE_SCHEMA = "trwm.world_program_evidence_bundle.v1";
export const WORLD_PROGRAM_BUNDLE_VERIFICATION_CERTIFICATE_SCHEMA = "trwm.world_program_bundle_verification_certificate.v1";
export const WORLD_PROGRAM_REPLAY_STEP_SCHEMA = "trwm.world_program_replay_step.v1";
export const WORLD_PROGRAM_REPLAY_PACKAGE_SCHEMA = "trwm.world_program_replay_package.v1";
export const WORLD_PROGRAM_REPLAY_VERIFICATION_CERTIFICATE_SCHEMA = "trwm.world_program_replay_verification_certificate.v1";
export const WORLD_PROGRAM_BUILD_TYPE = "trwm.world_program_execution.v1";

export interface WorldProgramManifest {
  schemaVersion: typeof WORLD_PROGRAM_MANIFEST_SCHEMA;
  programId: string;
  programVersion: string;
  buildType: typeof WORLD_PROGRAM_BUILD_TYPE;
  proposerId: string;
  proposerVersion: string;
  projectorId: string;
  projectorVersion: string;
  learnerId: string;
  learnerVersion: string;
  verifierId: string;
  verifierVersion: string;
  inputSchema: string;
  candidateSchema: string;
  externalParameters: Record<string, unknown>;
  resolvedDependencies: string[];
  manifestHash: string;
}

export interface WorldProgramCertificate {
  schemaVersion: typeof WORLD_PROGRAM_CERTIFICATE_SCHEMA;
  programId: string;
  programVersion: string;
  manifestHash: string;
  stepCount: number;
  committedCount: number;
  rejectedCount: number;
  learnerUpdateCount: number;
  stepCertificateHashes: string[];
  receiptHashes: string[];
  finalLearnerSnapshotHash: string;
  ledgerHead: string;
  invalidCommitCount: number;
  replayRollbackRate: number;
  artifactHashGroups: Record<string, string[]>;
  certificateHash: string;
}

export interface WorldProgramAdmissionPolicy {
  schemaVersion: typeof WORLD_PROGRAM_ADMISSION_POLICY_SCHEMA;
  policyId: string;
  policyVersion: string;
  allowedBuildTypes: string[];
  allowedProgramIds: string[];
  allowedProgramVersions: string[];
  allowedProposerIds: string[];
  allowedProjectorIds: string[];
  allowedLearnerIds: string[];
  allowedVerifierIds: string[];
  allowedInputSchemas: string[];
  allowedCandidateSchemas: string[];
  requiredDependencies: string[];
  requiredArtifactKeys: string[];
  minStepCount: number;
  minCommittedCount: number;
  minRejectedCount: number;
  maxInvalidCommitCount: number;
  minReplayRollbackRate: number;
  policyHash: string;
}

export interface WorldProgramAdmissionCertificate {
  schemaVersion: typeof WORLD_PROGRAM_ADMISSION_CERTIFICATE_SCHEMA;
  policyId: string;
  policyVersion: string;
  policyHash: string;
  manifestHash: string;
  executionCertificateHash: string;
  programId: string;
  programVersion: string;
  externalParametersHash: string;
  resolvedDependencyHash: string;
  artifactHashGroupsHash: string;
  requirementCount: number;
  passedRequirements: string[];
  failedRequirements: string[];
  admitted: boolean;
  certificateHash: string;
}

export interface WorldProgramEvidenceBundle {
  schemaVersion: typeof WORLD_PROGRAM_EVIDENCE_BUNDLE_SCHEMA;
  bundleId: string;
  bundleVersion: string;
  manifest: WorldProgramManifest;
  executionCertificate: WorldProgramCertificate;
  admissionPolicy: WorldProgramAdmissionPolicy;
  admissionCertificate: WorldProgramAdmissionCertificate;
  stepCertificateHashes: string[];
  receiptHashes: string[];
  finalLearnerSnapshotHash: string;
  artifactHashGroups: Record<string, string[]>;
  sourceBundleHashes: string[];
  bundleHash: string;
}

export interface WorldProgramBundleVerificationCertificate {
  schemaVersion: typeof WORLD_PROGRAM_BUNDLE_VERIFICATION_CERTIFICATE_SCHEMA;
  bundleHash: string;
  verifierId: string;
  verifierVersion: string;
  policyHash: string;
  manifestHash: string;
  executionCertificateHash: string;
  admissionCertificateHash: string;
  inputAttestationHashes: string[];
  requirementCount: number;
  passedRequirements: string[];
  failedRequirements: string[];
  verified: boolean;
  certificateHash: string;
}

export interface WorldProgramReplayStep {
  schemaVersion: typeof WORLD_PROGRAM_REPLAY_STEP_SCHEMA;
  stepIndex: number;
  trace: ProposalTrace;
  candidate: TypedCandidate;
  receipt: Receipt;
  certificate: WorldModelStepCertificate;
  preLearnerSnapshot: WorldLearnerSnapshot;
  learnerSnapshot: WorldLearnerSnapshot;
  learnerUpdateCertificate: WorldLearnerUpdateCertificate;
  learnerDeltaCertificate: WorldLearnerDeltaCertificate;
  stepHash: string;
}

export interface WorldProgramReplayPackage {
  schemaVersion: typeof WORLD_PROGRAM_REPLAY_PACKAGE_SCHEMA;
  packageId: string;
  packageVersion: string;
  evidenceBundle: WorldProgramEvidenceBundle;
  steps: WorldProgramReplayStep[];
  stepHashes: string[];
  stepCertificateHashes: string[];
  receiptHashes: string[];
  learnerUpdateCertificateHashes: string[];
  learnerDeltaCertificateHashes: string[];
  finalLearnerSnapshotHash: string;
  ledgerHead: string;
  packageBodyHash: string;
  packageHash: string;
}

export interface WorldProgramReplayVerificationCertificate {
  schemaVersion: typeof WORLD_PROGRAM_REPLAY_VERIFICATION_CERTIFICATE_SCHEMA;
  packageHash: string;
  evidenceBundleHash: string;
  verifierId: string;
  verifierVersion: string;
  packageBodyHash: string;
  ledgerHead: string;
  finalLearnerSnapshotHash: string;
  stepHashes: string[];
  stepCertificateHashes: string[];
  receiptHashes: string[];
  learnerUpdateCertificateHashes: string[];
  learnerDeltaCertificateHashes: string[];
  requirementCount: number;
  passedRequirements: string[];
  failedRequirements: string[];
  replayVerified: boolean;
  certificateHash: string;
}

export async function buildWorldProgramManifest(params: {
  programId: string;
  programVersion: string;
  proposer: unknown;
  projector: unknown;
  learner?: unknown;
  verifierId: string;
  verifierVersion: string;
  inputSchema: string;
  candidateSchema: string;
  externalParameters?: Record<string, unknown>;
  resolvedDependencies?: string[];
}): Promise<WorldProgramManifest> {
  const pending: WorldProgramManifest = {
    schemaVersion: WORLD_PROGRAM_MANIFEST_SCHEMA,
    programId: params.programId,
    programVersion: params.programVersion,
    buildType: WORLD_PROGRAM_BUILD_TYPE,
    proposerId: componentValue(params.proposer, "proposerId", "proposer_id", "proposer"),
    proposerVersion: componentValue(params.proposer, "proposerVersion", "proposer_version", "0"),
    projectorId: componentValue(params.projector, "projectorId", "projector_id", "projector"),
    projectorVersion: componentValue(params.projector, "projectorVersion", "projector_version", "0"),
    learnerId: componentValue(params.learner, "learnerId", "learner_id", "none"),
    learnerVersion: componentValue(params.learner, "learnerVersion", "learner_version", "0"),
    verifierId: params.verifierId,
    verifierVersion: params.verifierVersion,
    inputSchema: params.inputSchema,
    candidateSchema: params.candidateSchema,
    externalParameters: { ...(params.externalParameters ?? {}) },
    resolvedDependencies: [...(params.resolvedDependencies ?? [])],
    manifestHash: "",
  };
  return { ...pending, manifestHash: await worldProgramManifestHash(pending) };
}

export async function buildWorldProgramAdmissionPolicy(params: {
  policyId: string;
  policyVersion: string;
  allowedBuildTypes?: string[];
  allowedProgramIds?: string[];
  allowedProgramVersions?: string[];
  allowedProposerIds?: string[];
  allowedProjectorIds?: string[];
  allowedLearnerIds?: string[];
  allowedVerifierIds?: string[];
  allowedInputSchemas?: string[];
  allowedCandidateSchemas?: string[];
  requiredDependencies?: string[];
  requiredArtifactKeys?: string[];
  minStepCount?: number;
  minCommittedCount?: number;
  minRejectedCount?: number;
  maxInvalidCommitCount?: number;
  minReplayRollbackRate?: number;
}): Promise<WorldProgramAdmissionPolicy> {
  const pending: WorldProgramAdmissionPolicy = {
    schemaVersion: WORLD_PROGRAM_ADMISSION_POLICY_SCHEMA,
    policyId: params.policyId,
    policyVersion: params.policyVersion,
    allowedBuildTypes: dedupeStrings(params.allowedBuildTypes ?? [WORLD_PROGRAM_BUILD_TYPE]),
    allowedProgramIds: dedupeStrings(params.allowedProgramIds ?? []),
    allowedProgramVersions: dedupeStrings(params.allowedProgramVersions ?? []),
    allowedProposerIds: dedupeStrings(params.allowedProposerIds ?? []),
    allowedProjectorIds: dedupeStrings(params.allowedProjectorIds ?? []),
    allowedLearnerIds: dedupeStrings(params.allowedLearnerIds ?? []),
    allowedVerifierIds: dedupeStrings(params.allowedVerifierIds ?? []),
    allowedInputSchemas: dedupeStrings(params.allowedInputSchemas ?? []),
    allowedCandidateSchemas: dedupeStrings(params.allowedCandidateSchemas ?? []),
    requiredDependencies: dedupeStrings(params.requiredDependencies ?? []),
    requiredArtifactKeys: dedupeStrings(params.requiredArtifactKeys ?? []),
    minStepCount: params.minStepCount ?? 1,
    minCommittedCount: params.minCommittedCount ?? 0,
    minRejectedCount: params.minRejectedCount ?? 0,
    maxInvalidCommitCount: params.maxInvalidCommitCount ?? 0,
    minReplayRollbackRate: params.minReplayRollbackRate ?? 1,
    policyHash: "",
  };
  return { ...pending, policyHash: await worldProgramAdmissionPolicyHash(pending) };
}

export async function buildWorldProgramCertificate(
  manifest: WorldProgramManifest,
  steps: Array<WorldModelStepResult>,
  params: {
    ledgerHead: string;
    invalidCommitCount: number;
    replayRollbackRate: number;
  },
): Promise<WorldProgramCertificate> {
  if (steps.length === 0) {
    throw new Error("world program certificate requires at least one step");
  }
  const artifactHashGroups: Record<string, string[]> = {};
  for (const step of steps) {
    for (const [key, value] of Object.entries(step.receipt.artifactHashes)) {
      if (!artifactHashGroups[key]) {
        artifactHashGroups[key] = [];
      }
      if (!artifactHashGroups[key].includes(value)) {
        artifactHashGroups[key].push(value);
      }
    }
  }
  const finalSnapshot = steps[steps.length - 1].learnerSnapshot;
  const pending: WorldProgramCertificate = {
    schemaVersion: WORLD_PROGRAM_CERTIFICATE_SCHEMA,
    programId: manifest.programId,
    programVersion: manifest.programVersion,
    manifestHash: manifest.manifestHash,
    stepCount: steps.length,
    committedCount: steps.filter((step) => step.committed).length,
    rejectedCount: steps.filter((step) => step.receipt.hardResult.result === "reject").length,
    learnerUpdateCount: finalSnapshot.updateCount,
    stepCertificateHashes: steps.map((step) => step.certificate.certificateHash),
    receiptHashes: steps.map((step) => step.receipt.receiptHash),
    finalLearnerSnapshotHash: finalSnapshot.snapshotHash,
    ledgerHead: params.ledgerHead,
    invalidCommitCount: params.invalidCommitCount,
    replayRollbackRate: params.replayRollbackRate,
    artifactHashGroups,
    certificateHash: "",
  };
  return { ...pending, certificateHash: await worldProgramCertificateHash(pending) };
}

export async function buildWorldProgramAdmissionCertificate(
  policy: WorldProgramAdmissionPolicy,
  manifest: WorldProgramManifest,
  executionCertificate: WorldProgramCertificate,
): Promise<WorldProgramAdmissionCertificate> {
  const { passed, failed } = await evaluateWorldProgramAdmission(policy, manifest, executionCertificate);
  const pending: WorldProgramAdmissionCertificate = {
    schemaVersion: WORLD_PROGRAM_ADMISSION_CERTIFICATE_SCHEMA,
    policyId: policy.policyId,
    policyVersion: policy.policyVersion,
    policyHash: policy.policyHash,
    manifestHash: manifest.manifestHash,
    executionCertificateHash: executionCertificate.certificateHash,
    programId: manifest.programId,
    programVersion: manifest.programVersion,
    externalParametersHash: await stableHash(manifest.externalParameters),
    resolvedDependencyHash: await stableHash(manifest.resolvedDependencies),
    artifactHashGroupsHash: await stableHash(executionCertificate.artifactHashGroups),
    requirementCount: passed.length + failed.length,
    passedRequirements: passed,
    failedRequirements: failed,
    admitted: failed.length === 0,
    certificateHash: "",
  };
  return { ...pending, certificateHash: await worldProgramAdmissionCertificateHash(pending) };
}

export async function buildWorldProgramEvidenceBundle(
  manifest: WorldProgramManifest,
  executionCertificate: WorldProgramCertificate,
  admissionPolicy: WorldProgramAdmissionPolicy,
  admissionCertificate: WorldProgramAdmissionCertificate,
  params: {
    bundleId?: string;
    bundleVersion?: string;
    sourceBundleHashes?: string[];
  } = {},
): Promise<WorldProgramEvidenceBundle> {
  const pending: WorldProgramEvidenceBundle = {
    schemaVersion: WORLD_PROGRAM_EVIDENCE_BUNDLE_SCHEMA,
    bundleId: params.bundleId ?? `${manifest.programId}.evidence`,
    bundleVersion: params.bundleVersion ?? "1.0",
    manifest,
    executionCertificate,
    admissionPolicy,
    admissionCertificate,
    stepCertificateHashes: [...executionCertificate.stepCertificateHashes],
    receiptHashes: [...executionCertificate.receiptHashes],
    finalLearnerSnapshotHash: executionCertificate.finalLearnerSnapshotHash,
    artifactHashGroups: sortedHashGroups(executionCertificate.artifactHashGroups),
    sourceBundleHashes: [...(params.sourceBundleHashes ?? [])],
    bundleHash: "",
  };
  return { ...pending, bundleHash: await worldProgramEvidenceBundleHash(pending) };
}

export async function buildWorldProgramBundleVerificationCertificate(
  bundle: WorldProgramEvidenceBundle,
  params: {
    verifierId?: string;
    verifierVersion?: string;
  } = {},
): Promise<WorldProgramBundleVerificationCertificate> {
  const { passed, failed } = await evaluateWorldProgramBundleVerification(bundle);
  const pending: WorldProgramBundleVerificationCertificate = {
    schemaVersion: WORLD_PROGRAM_BUNDLE_VERIFICATION_CERTIFICATE_SCHEMA,
    bundleHash: bundle.bundleHash,
    verifierId: params.verifierId ?? "trwm.world_program_bundle_verifier",
    verifierVersion: params.verifierVersion ?? "1.0",
    policyHash: bundle.admissionPolicy.policyHash,
    manifestHash: bundle.manifest.manifestHash,
    executionCertificateHash: bundle.executionCertificate.certificateHash,
    admissionCertificateHash: bundle.admissionCertificate.certificateHash,
    inputAttestationHashes: await bundleInputAttestationHashes(bundle),
    requirementCount: passed.length + failed.length,
    passedRequirements: passed,
    failedRequirements: failed,
    verified: failed.length === 0,
    certificateHash: "",
  };
  return { ...pending, certificateHash: await worldProgramBundleVerificationCertificateHash(pending) };
}

export async function buildWorldProgramReplayStep(
  step: WorldModelStepResult,
  params: { stepIndex: number },
): Promise<WorldProgramReplayStep> {
  const pending: WorldProgramReplayStep = {
    schemaVersion: WORLD_PROGRAM_REPLAY_STEP_SCHEMA,
    stepIndex: params.stepIndex,
    trace: step.trace,
    candidate: step.candidate,
    receipt: step.receipt,
    certificate: step.certificate,
    preLearnerSnapshot: step.preLearnerSnapshot,
    learnerSnapshot: step.learnerSnapshot,
    learnerUpdateCertificate: step.learnerUpdateCertificate,
    learnerDeltaCertificate: step.learnerDeltaCertificate,
    stepHash: "",
  };
  return { ...pending, stepHash: await worldProgramReplayStepHash(pending) };
}

export async function buildWorldProgramReplayPackage(
  evidenceBundle: WorldProgramEvidenceBundle,
  steps: Array<WorldModelStepResult | WorldProgramReplayStep>,
  params: {
    packageId?: string;
    packageVersion?: string;
  } = {},
): Promise<WorldProgramReplayPackage> {
  if (steps.length === 0) {
    throw new Error("world program replay package requires at least one step");
  }
  const replaySteps = await Promise.all(steps.map((step, index) => {
    if (isReplayStep(step)) {
      return step;
    }
    return buildWorldProgramReplayStep(step, { stepIndex: index });
  }));
  const pending: WorldProgramReplayPackage = {
    schemaVersion: WORLD_PROGRAM_REPLAY_PACKAGE_SCHEMA,
    packageId: params.packageId ?? `${evidenceBundle.bundleId}.replay`,
    packageVersion: params.packageVersion ?? "1.0",
    evidenceBundle,
    steps: replaySteps,
    stepHashes: replaySteps.map((step) => step.stepHash),
    stepCertificateHashes: replaySteps.map((step) => step.certificate.certificateHash),
    receiptHashes: replaySteps.map((step) => step.receipt.receiptHash),
    learnerUpdateCertificateHashes: replaySteps.map((step) => step.learnerUpdateCertificate.certificateHash),
    learnerDeltaCertificateHashes: replaySteps.map((step) => step.learnerDeltaCertificate.certificateHash),
    finalLearnerSnapshotHash: replaySteps[replaySteps.length - 1].learnerSnapshot.snapshotHash,
    ledgerHead: await ledgerHeadFromReplaySteps(replaySteps),
    packageBodyHash: "",
    packageHash: "",
  };
  const withBody = { ...pending, packageBodyHash: await worldProgramReplayPackageBodyHash(pending) };
  return { ...withBody, packageHash: await worldProgramReplayPackageHash(withBody) };
}

export async function buildWorldProgramReplayVerificationCertificate(
  replayPackage: WorldProgramReplayPackage,
  params: {
    verifierId?: string;
    verifierVersion?: string;
  } = {},
): Promise<WorldProgramReplayVerificationCertificate> {
  const { passed, failed } = await evaluateWorldProgramReplayVerification(replayPackage);
  const pending: WorldProgramReplayVerificationCertificate = {
    schemaVersion: WORLD_PROGRAM_REPLAY_VERIFICATION_CERTIFICATE_SCHEMA,
    packageHash: replayPackage.packageHash,
    evidenceBundleHash: replayPackage.evidenceBundle.bundleHash,
    verifierId: params.verifierId ?? "trwm.world_program_replay_verifier",
    verifierVersion: params.verifierVersion ?? "1.0",
    packageBodyHash: replayPackage.packageBodyHash,
    ledgerHead: replayPackage.ledgerHead,
    finalLearnerSnapshotHash: replayPackage.finalLearnerSnapshotHash,
    stepHashes: [...replayPackage.stepHashes],
    stepCertificateHashes: [...replayPackage.stepCertificateHashes],
    receiptHashes: [...replayPackage.receiptHashes],
    learnerUpdateCertificateHashes: [...replayPackage.learnerUpdateCertificateHashes],
    learnerDeltaCertificateHashes: [...replayPackage.learnerDeltaCertificateHashes],
    requirementCount: passed.length + failed.length,
    passedRequirements: passed,
    failedRequirements: failed,
    replayVerified: failed.length === 0,
    certificateHash: "",
  };
  return { ...pending, certificateHash: await worldProgramReplayVerificationCertificateHash(pending) };
}

export async function auditWorldProgramCertificate(
  manifest: WorldProgramManifest,
  steps: Array<WorldModelStepResult>,
  certificate: WorldProgramCertificate,
  params: {
    ledgerHead: string;
    invalidCommitCount: number;
    replayRollbackRate: number;
  },
): Promise<boolean> {
  try {
    const expected = await buildWorldProgramCertificate(manifest, steps, params);
    return sameCertificate(certificate, expected) && await validateWorldProgramCertificate(certificate, manifest);
  } catch (_error) {
    return false;
  }
}

export async function auditWorldProgramAdmission(
  policy: WorldProgramAdmissionPolicy,
  manifest: WorldProgramManifest,
  executionCertificate: WorldProgramCertificate,
  admissionCertificate: WorldProgramAdmissionCertificate,
): Promise<boolean> {
  try {
    const expected = await buildWorldProgramAdmissionCertificate(policy, manifest, executionCertificate);
    return sameAdmissionCertificate(admissionCertificate, expected)
      && await validateWorldProgramAdmissionCertificate(admissionCertificate, policy, manifest, executionCertificate);
  } catch (_error) {
    return false;
  }
}

export async function auditWorldProgramEvidenceBundle(
  manifest: WorldProgramManifest,
  executionCertificate: WorldProgramCertificate,
  admissionPolicy: WorldProgramAdmissionPolicy,
  admissionCertificate: WorldProgramAdmissionCertificate,
  bundle: WorldProgramEvidenceBundle,
): Promise<boolean> {
  try {
    const expected = await buildWorldProgramEvidenceBundle(
      manifest,
      executionCertificate,
      admissionPolicy,
      admissionCertificate,
      {
        bundleId: bundle.bundleId,
        bundleVersion: bundle.bundleVersion,
        sourceBundleHashes: bundle.sourceBundleHashes,
      },
    );
    return sameEvidenceBundle(bundle, expected) && await validateWorldProgramEvidenceBundle(bundle);
  } catch (_error) {
    return false;
  }
}

export async function auditWorldProgramBundleVerification(
  bundle: WorldProgramEvidenceBundle,
  certificate: WorldProgramBundleVerificationCertificate,
): Promise<boolean> {
  try {
    const expected = await buildWorldProgramBundleVerificationCertificate(bundle, {
      verifierId: certificate.verifierId,
      verifierVersion: certificate.verifierVersion,
    });
    return sameBundleVerificationCertificate(certificate, expected)
      && await validateWorldProgramBundleVerificationCertificate(certificate, bundle);
  } catch (_error) {
    return false;
  }
}

export async function auditWorldProgramReplayPackage(
  evidenceBundle: WorldProgramEvidenceBundle,
  steps: Array<WorldModelStepResult | WorldProgramReplayStep>,
  replayPackage: WorldProgramReplayPackage,
): Promise<boolean> {
  try {
    const expected = await buildWorldProgramReplayPackage(evidenceBundle, steps, {
      packageId: replayPackage.packageId,
      packageVersion: replayPackage.packageVersion,
    });
    return sameReplayPackage(replayPackage, expected) && await validateWorldProgramReplayPackage(replayPackage);
  } catch (_error) {
    return false;
  }
}

export async function auditWorldProgramReplayVerification(
  replayPackage: WorldProgramReplayPackage,
  certificate: WorldProgramReplayVerificationCertificate,
): Promise<boolean> {
  try {
    const expected = await buildWorldProgramReplayVerificationCertificate(replayPackage, {
      verifierId: certificate.verifierId,
      verifierVersion: certificate.verifierVersion,
    });
    return sameReplayVerificationCertificate(certificate, expected)
      && await validateWorldProgramReplayVerificationCertificate(certificate, replayPackage);
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramManifest(manifest: WorldProgramManifest): Promise<boolean> {
  try {
    if (manifest.schemaVersion !== WORLD_PROGRAM_MANIFEST_SCHEMA || manifest.buildType !== WORLD_PROGRAM_BUILD_TYPE) {
      return false;
    }
    const required = [
      manifest.programId,
      manifest.programVersion,
      manifest.proposerId,
      manifest.proposerVersion,
      manifest.projectorId,
      manifest.projectorVersion,
      manifest.learnerId,
      manifest.learnerVersion,
      manifest.verifierId,
      manifest.verifierVersion,
      manifest.inputSchema,
      manifest.candidateSchema,
    ];
    if (!required.every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!manifest.externalParameters || typeof manifest.externalParameters !== "object" || Array.isArray(manifest.externalParameters)) {
      return false;
    }
    if (!manifest.resolvedDependencies.every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    return manifest.manifestHash === await worldProgramManifestHash(manifest);
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramAdmissionPolicy(policy: WorldProgramAdmissionPolicy): Promise<boolean> {
  try {
    if (policy.schemaVersion !== WORLD_PROGRAM_ADMISSION_POLICY_SCHEMA) {
      return false;
    }
    if (![policy.policyId, policy.policyVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    const stringLists = [
      policy.allowedBuildTypes,
      policy.allowedProgramIds,
      policy.allowedProgramVersions,
      policy.allowedProposerIds,
      policy.allowedProjectorIds,
      policy.allowedLearnerIds,
      policy.allowedVerifierIds,
      policy.allowedInputSchemas,
      policy.allowedCandidateSchemas,
      policy.requiredDependencies,
      policy.requiredArtifactKeys,
    ];
    for (const values of stringLists) {
      if (!Array.isArray(values) || !values.every((value) => typeof value === "string" && value.length > 0)) {
        return false;
      }
      if (new Set(values).size !== values.length) {
        return false;
      }
    }
    if (policy.allowedBuildTypes.length === 0) {
      return false;
    }
    const counts = [
      policy.minStepCount,
      policy.minCommittedCount,
      policy.minRejectedCount,
      policy.maxInvalidCommitCount,
    ];
    if (!counts.every(nonnegativeInteger) || policy.minStepCount <= 0) {
      return false;
    }
    if (typeof policy.minReplayRollbackRate !== "number" || policy.minReplayRollbackRate < 0 || policy.minReplayRollbackRate > 1) {
      return false;
    }
    return policy.policyHash === await worldProgramAdmissionPolicyHash(policy);
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramCertificate(
  certificate: WorldProgramCertificate,
  manifest?: WorldProgramManifest,
): Promise<boolean> {
  try {
    if (certificate.schemaVersion !== WORLD_PROGRAM_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (![certificate.programId, certificate.programVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!isHash(certificate.manifestHash) || !isHash(certificate.finalLearnerSnapshotHash) || !isHash(certificate.ledgerHead)) {
      return false;
    }
    if (!positiveInteger(certificate.stepCount)) {
      return false;
    }
    if (certificate.stepCertificateHashes.length !== certificate.stepCount || certificate.receiptHashes.length !== certificate.stepCount) {
      return false;
    }
    const counts = [
      certificate.committedCount,
      certificate.rejectedCount,
      certificate.learnerUpdateCount,
      certificate.invalidCommitCount,
    ];
    if (!counts.every(nonnegativeInteger)) {
      return false;
    }
    if (certificate.committedCount + certificate.rejectedCount > certificate.stepCount) {
      return false;
    }
    if (typeof certificate.replayRollbackRate !== "number" || certificate.replayRollbackRate < 0 || certificate.replayRollbackRate > 1) {
      return false;
    }
    if (!certificate.stepCertificateHashes.every(isHash) || !certificate.receiptHashes.every(isHash)) {
      return false;
    }
    if (new Set(certificate.receiptHashes).size !== certificate.receiptHashes.length) {
      return false;
    }
    for (const [key, values] of Object.entries(certificate.artifactHashGroups)) {
      if (!key || !Array.isArray(values) || !values.every(isHash)) {
        return false;
      }
    }
    if (manifest) {
      if (!await validateWorldProgramManifest(manifest)) {
        return false;
      }
      if (certificate.manifestHash !== manifest.manifestHash) {
        return false;
      }
      if (certificate.programId !== manifest.programId || certificate.programVersion !== manifest.programVersion) {
        return false;
      }
    }
    return certificate.certificateHash === await worldProgramCertificateHash(certificate);
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramAdmissionCertificate(
  admissionCertificate: WorldProgramAdmissionCertificate,
  policy?: WorldProgramAdmissionPolicy,
  manifest?: WorldProgramManifest,
  executionCertificate?: WorldProgramCertificate,
): Promise<boolean> {
  try {
    if (admissionCertificate.schemaVersion !== WORLD_PROGRAM_ADMISSION_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (![admissionCertificate.policyId, admissionCertificate.policyVersion, admissionCertificate.programId, admissionCertificate.programVersion]
      .every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    const hashes = [
      admissionCertificate.policyHash,
      admissionCertificate.manifestHash,
      admissionCertificate.executionCertificateHash,
      admissionCertificate.externalParametersHash,
      admissionCertificate.resolvedDependencyHash,
      admissionCertificate.artifactHashGroupsHash,
    ];
    if (!hashes.every(isHash)) {
      return false;
    }
    if (!positiveInteger(admissionCertificate.requirementCount)) {
      return false;
    }
    if (typeof admissionCertificate.admitted !== "boolean") {
      return false;
    }
    if (!Array.isArray(admissionCertificate.passedRequirements) || !Array.isArray(admissionCertificate.failedRequirements)) {
      return false;
    }
    const allRequirements = [...admissionCertificate.passedRequirements, ...admissionCertificate.failedRequirements];
    if (allRequirements.length !== admissionCertificate.requirementCount) {
      return false;
    }
    if (!allRequirements.every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (new Set(allRequirements).size !== allRequirements.length) {
      return false;
    }
    if (admissionCertificate.admitted !== (admissionCertificate.failedRequirements.length === 0)) {
      return false;
    }
    if (policy) {
      if (!await validateWorldProgramAdmissionPolicy(policy)) {
        return false;
      }
      if (
        admissionCertificate.policyId !== policy.policyId
        || admissionCertificate.policyVersion !== policy.policyVersion
        || admissionCertificate.policyHash !== policy.policyHash
      ) {
        return false;
      }
    }
    if (manifest) {
      if (!await validateWorldProgramManifest(manifest)) {
        return false;
      }
      if (
        admissionCertificate.manifestHash !== manifest.manifestHash
        || admissionCertificate.programId !== manifest.programId
        || admissionCertificate.programVersion !== manifest.programVersion
        || admissionCertificate.externalParametersHash !== await stableHash(manifest.externalParameters)
        || admissionCertificate.resolvedDependencyHash !== await stableHash(manifest.resolvedDependencies)
      ) {
        return false;
      }
    }
    if (executionCertificate) {
      if (!await validateWorldProgramCertificate(executionCertificate, manifest)) {
        return false;
      }
      if (
        admissionCertificate.executionCertificateHash !== executionCertificate.certificateHash
        || admissionCertificate.artifactHashGroupsHash !== await stableHash(executionCertificate.artifactHashGroups)
      ) {
        return false;
      }
    }
    if (policy && manifest && executionCertificate) {
      const expected = await buildWorldProgramAdmissionCertificate(policy, manifest, executionCertificate);
      if (!sameAdmissionCertificate(admissionCertificate, expected)) {
        return false;
      }
    }
    return admissionCertificate.certificateHash === await worldProgramAdmissionCertificateHash(admissionCertificate);
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramEvidenceBundle(bundle: WorldProgramEvidenceBundle): Promise<boolean> {
  try {
    if (bundle.schemaVersion !== WORLD_PROGRAM_EVIDENCE_BUNDLE_SCHEMA) {
      return false;
    }
    if (![bundle.bundleId, bundle.bundleVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!await validateWorldProgramManifest(bundle.manifest)) {
      return false;
    }
    if (!await validateWorldProgramCertificate(bundle.executionCertificate, bundle.manifest)) {
      return false;
    }
    if (!await validateWorldProgramAdmissionPolicy(bundle.admissionPolicy)) {
      return false;
    }
    if (!await validateWorldProgramAdmissionCertificate(
      bundle.admissionCertificate,
      bundle.admissionPolicy,
      bundle.manifest,
      bundle.executionCertificate,
    )) {
      return false;
    }
    if (!Array.isArray(bundle.stepCertificateHashes) || !Array.isArray(bundle.receiptHashes)) {
      return false;
    }
    if (!sameStringArray(bundle.stepCertificateHashes, bundle.executionCertificate.stepCertificateHashes)) {
      return false;
    }
    if (!sameStringArray(bundle.receiptHashes, bundle.executionCertificate.receiptHashes)) {
      return false;
    }
    if (bundle.finalLearnerSnapshotHash !== bundle.executionCertificate.finalLearnerSnapshotHash) {
      return false;
    }
    if (!sameHashGroups(bundle.artifactHashGroups, bundle.executionCertificate.artifactHashGroups)) {
      return false;
    }
    if (!bundle.stepCertificateHashes.every(isHash) || !bundle.receiptHashes.every(isHash)) {
      return false;
    }
    if (new Set(bundle.receiptHashes).size !== bundle.receiptHashes.length) {
      return false;
    }
    if (!isHash(bundle.finalLearnerSnapshotHash)) {
      return false;
    }
    for (const [key, values] of Object.entries(bundle.artifactHashGroups)) {
      if (!key || !Array.isArray(values) || !values.every(isHash)) {
        return false;
      }
    }
    if (!Array.isArray(bundle.sourceBundleHashes) || !bundle.sourceBundleHashes.every(isHash)) {
      return false;
    }
    return bundle.bundleHash === await worldProgramEvidenceBundleHash(bundle);
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramBundleVerificationCertificate(
  certificate: WorldProgramBundleVerificationCertificate,
  bundle?: WorldProgramEvidenceBundle,
): Promise<boolean> {
  try {
    if (certificate.schemaVersion !== WORLD_PROGRAM_BUNDLE_VERIFICATION_CERTIFICATE_SCHEMA) {
      return false;
    }
    const hashes = [
      certificate.bundleHash,
      certificate.policyHash,
      certificate.manifestHash,
      certificate.executionCertificateHash,
      certificate.admissionCertificateHash,
    ];
    if (!hashes.every(isHash)) {
      return false;
    }
    if (![certificate.verifierId, certificate.verifierVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!Array.isArray(certificate.inputAttestationHashes) || !certificate.inputAttestationHashes.every(isHash)) {
      return false;
    }
    if (!positiveInteger(certificate.requirementCount) || typeof certificate.verified !== "boolean") {
      return false;
    }
    if (!Array.isArray(certificate.passedRequirements) || !Array.isArray(certificate.failedRequirements)) {
      return false;
    }
    const allRequirements = [...certificate.passedRequirements, ...certificate.failedRequirements];
    if (allRequirements.length !== certificate.requirementCount) {
      return false;
    }
    if (!allRequirements.every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (new Set(allRequirements).size !== allRequirements.length) {
      return false;
    }
    if (certificate.verified !== (certificate.failedRequirements.length === 0)) {
      return false;
    }
    if (bundle) {
      if (!await validateWorldProgramEvidenceBundle(bundle)) {
        return false;
      }
      if (
        certificate.bundleHash !== bundle.bundleHash
        || certificate.policyHash !== bundle.admissionPolicy.policyHash
        || certificate.manifestHash !== bundle.manifest.manifestHash
        || certificate.executionCertificateHash !== bundle.executionCertificate.certificateHash
        || certificate.admissionCertificateHash !== bundle.admissionCertificate.certificateHash
      ) {
        return false;
      }
      if (!sameStringArray(certificate.inputAttestationHashes, await bundleInputAttestationHashes(bundle))) {
        return false;
      }
      const expected = await buildWorldProgramBundleVerificationCertificate(bundle, {
        verifierId: certificate.verifierId,
        verifierVersion: certificate.verifierVersion,
      });
      if (!sameBundleVerificationCertificate(certificate, expected)) {
        return false;
      }
    }
    return certificate.certificateHash === await worldProgramBundleVerificationCertificateHash(certificate);
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramReplayStep(
  step: WorldProgramReplayStep,
  options: {
    expectedIndex?: number;
    ledgerHead?: string;
    previousLearnerSnapshot?: WorldLearnerSnapshot;
  } = {},
): Promise<boolean> {
  try {
    if (step.schemaVersion !== WORLD_PROGRAM_REPLAY_STEP_SCHEMA) {
      return false;
    }
    if (!nonnegativeInteger(step.stepIndex)) {
      return false;
    }
    if (typeof options.expectedIndex !== "undefined" && step.stepIndex !== options.expectedIndex) {
      return false;
    }
    if (!isHash(step.stepHash) || step.stepHash !== await worldProgramReplayStepHash(step)) {
      return false;
    }
    if (await stableHash(step.trace) !== step.receipt.proposalTraceHash) {
      return false;
    }
    if (await stableHash(step.candidate) !== step.receipt.typedCandidateHash) {
      return false;
    }
    if (!await receiptStaticValid(step.receipt)) {
      return false;
    }
    if (!await validateWorldModelStepCertificate(step.certificate)) {
      return false;
    }
    if (!await validateWorldLearnerSnapshot(step.preLearnerSnapshot) || !await validateWorldLearnerSnapshot(step.learnerSnapshot)) {
      return false;
    }
    if (!await validateWorldLearnerUpdateCertificate(step.learnerUpdateCertificate)) {
      return false;
    }
    if (!await validateWorldLearnerDeltaCertificate(step.learnerDeltaCertificate)) {
      return false;
    }
    if (options.previousLearnerSnapshot && step.preLearnerSnapshot.snapshotHash !== options.previousLearnerSnapshot.snapshotHash) {
      return false;
    }
    if (!await auditWorldModelStep(step.receipt, step.certificate, {
      ledgerHead: options.ledgerHead,
      learnerSnapshot: step.learnerSnapshot,
      learnerUpdateCertificate: step.learnerUpdateCertificate,
    })) {
      return false;
    }
    if (!await auditWorldLearnerUpdate(
      step.receipt,
      step.preLearnerSnapshot,
      step.learnerSnapshot,
      step.learnerUpdateCertificate,
    )) {
      return false;
    }
    return auditWorldLearnerDelta(
      step.preLearnerSnapshot,
      step.learnerSnapshot,
      step.learnerUpdateCertificate,
      step.learnerDeltaCertificate,
    );
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramReplayPackage(replayPackage: WorldProgramReplayPackage): Promise<boolean> {
  try {
    if (replayPackage.schemaVersion !== WORLD_PROGRAM_REPLAY_PACKAGE_SCHEMA) {
      return false;
    }
    if (![replayPackage.packageId, replayPackage.packageVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!await validateWorldProgramEvidenceBundle(replayPackage.evidenceBundle)) {
      return false;
    }
    if (!Array.isArray(replayPackage.steps) || replayPackage.steps.length === 0) {
      return false;
    }
    const executionCertificate = replayPackage.evidenceBundle.executionCertificate;
    if (replayPackage.steps.length !== executionCertificate.stepCount) {
      return false;
    }
    const hashLists = [
      replayPackage.stepHashes,
      replayPackage.stepCertificateHashes,
      replayPackage.receiptHashes,
      replayPackage.learnerUpdateCertificateHashes,
      replayPackage.learnerDeltaCertificateHashes,
    ];
    if (!hashLists.every((values) => Array.isArray(values) && values.every(isHash))) {
      return false;
    }
    if (![
      replayPackage.stepHashes,
      replayPackage.learnerUpdateCertificateHashes,
      replayPackage.learnerDeltaCertificateHashes,
    ].every((values) => values.length === replayPackage.steps.length)) {
      return false;
    }
    if (!sameStringArray(replayPackage.stepCertificateHashes, executionCertificate.stepCertificateHashes)) {
      return false;
    }
    if (!sameStringArray(replayPackage.receiptHashes, executionCertificate.receiptHashes)) {
      return false;
    }
    if (replayPackage.finalLearnerSnapshotHash !== executionCertificate.finalLearnerSnapshotHash) {
      return false;
    }

    let head = GENESIS_HEAD;
    let previousSnapshot: WorldLearnerSnapshot | undefined;
    for (const [index, step] of replayPackage.steps.entries()) {
      if (step.receipt.parentHead !== head) {
        return false;
      }
      head = await chainHash(head, step.receipt.receiptHash);
      if (!await validateWorldProgramReplayStep(step, {
        expectedIndex: index,
        ledgerHead: head,
        previousLearnerSnapshot: previousSnapshot,
      })) {
        return false;
      }
      previousSnapshot = step.learnerSnapshot;
    }

    if (replayPackage.ledgerHead !== head || replayPackage.ledgerHead !== executionCertificate.ledgerHead) {
      return false;
    }
    if (!sameStringArray(replayPackage.stepHashes, replayPackage.steps.map((step) => step.stepHash))) {
      return false;
    }
    if (!sameStringArray(replayPackage.stepCertificateHashes, replayPackage.steps.map((step) => step.certificate.certificateHash))) {
      return false;
    }
    if (!sameStringArray(replayPackage.receiptHashes, replayPackage.steps.map((step) => step.receipt.receiptHash))) {
      return false;
    }
    if (!sameStringArray(
      replayPackage.learnerUpdateCertificateHashes,
      replayPackage.steps.map((step) => step.learnerUpdateCertificate.certificateHash),
    )) {
      return false;
    }
    if (!sameStringArray(
      replayPackage.learnerDeltaCertificateHashes,
      replayPackage.steps.map((step) => step.learnerDeltaCertificate.certificateHash),
    )) {
      return false;
    }
    if (replayPackage.finalLearnerSnapshotHash !== replayPackage.steps[replayPackage.steps.length - 1].learnerSnapshot.snapshotHash) {
      return false;
    }
    if (!isHash(replayPackage.packageBodyHash) || replayPackage.packageBodyHash !== await worldProgramReplayPackageBodyHash(replayPackage)) {
      return false;
    }
    if (!isHash(replayPackage.packageHash)) {
      return false;
    }
    return replayPackage.packageHash === await worldProgramReplayPackageHash(replayPackage);
  } catch (_error) {
    return false;
  }
}

export async function validateWorldProgramReplayVerificationCertificate(
  certificate: WorldProgramReplayVerificationCertificate,
  replayPackage?: WorldProgramReplayPackage,
): Promise<boolean> {
  try {
    if (certificate.schemaVersion !== WORLD_PROGRAM_REPLAY_VERIFICATION_CERTIFICATE_SCHEMA) {
      return false;
    }
    const hashes = [
      certificate.packageHash,
      certificate.evidenceBundleHash,
      certificate.packageBodyHash,
      certificate.ledgerHead,
      certificate.finalLearnerSnapshotHash,
      certificate.certificateHash,
    ];
    if (!hashes.every(isHash)) {
      return false;
    }
    if (![certificate.verifierId, certificate.verifierVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    const hashLists = [
      certificate.stepHashes,
      certificate.stepCertificateHashes,
      certificate.receiptHashes,
      certificate.learnerUpdateCertificateHashes,
      certificate.learnerDeltaCertificateHashes,
    ];
    if (!hashLists.every((values) => Array.isArray(values) && values.every(isHash))) {
      return false;
    }
    if (!positiveInteger(certificate.requirementCount) || typeof certificate.replayVerified !== "boolean") {
      return false;
    }
    if (!Array.isArray(certificate.passedRequirements) || !Array.isArray(certificate.failedRequirements)) {
      return false;
    }
    const allRequirements = [...certificate.passedRequirements, ...certificate.failedRequirements];
    if (allRequirements.length !== certificate.requirementCount) {
      return false;
    }
    if (!allRequirements.every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (new Set(allRequirements).size !== allRequirements.length) {
      return false;
    }
    if (certificate.replayVerified !== (certificate.failedRequirements.length === 0)) {
      return false;
    }
    if (replayPackage) {
      if (!await validateWorldProgramReplayPackage(replayPackage)) {
        return false;
      }
      if (
        certificate.packageHash !== replayPackage.packageHash
        || certificate.evidenceBundleHash !== replayPackage.evidenceBundle.bundleHash
        || certificate.packageBodyHash !== replayPackage.packageBodyHash
        || certificate.ledgerHead !== replayPackage.ledgerHead
        || certificate.finalLearnerSnapshotHash !== replayPackage.finalLearnerSnapshotHash
      ) {
        return false;
      }
      if (!sameStringArray(certificate.stepHashes, replayPackage.stepHashes)
        || !sameStringArray(certificate.stepCertificateHashes, replayPackage.stepCertificateHashes)
        || !sameStringArray(certificate.receiptHashes, replayPackage.receiptHashes)
        || !sameStringArray(certificate.learnerUpdateCertificateHashes, replayPackage.learnerUpdateCertificateHashes)
        || !sameStringArray(certificate.learnerDeltaCertificateHashes, replayPackage.learnerDeltaCertificateHashes)) {
        return false;
      }
      const expected = await buildWorldProgramReplayVerificationCertificate(replayPackage, {
        verifierId: certificate.verifierId,
        verifierVersion: certificate.verifierVersion,
      });
      if (!sameReplayVerificationCertificate(certificate, expected)) {
        return false;
      }
    }
    return certificate.certificateHash === await worldProgramReplayVerificationCertificateHash(certificate);
  } catch (_error) {
    return false;
  }
}

export async function worldProgramManifestHash(manifest: WorldProgramManifest): Promise<string> {
  const { manifestHash: _manifestHash, ...withoutHash } = manifest;
  return stableHash(withoutHash);
}

export async function worldProgramAdmissionPolicyHash(policy: WorldProgramAdmissionPolicy): Promise<string> {
  const { policyHash: _policyHash, ...withoutHash } = policy;
  return stableHash(withoutHash);
}

export async function worldProgramCertificateHash(certificate: WorldProgramCertificate): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function worldProgramAdmissionCertificateHash(certificate: WorldProgramAdmissionCertificate): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function worldProgramEvidenceBundleHash(bundle: WorldProgramEvidenceBundle): Promise<string> {
  const { bundleHash: _bundleHash, ...withoutHash } = bundle;
  return stableHash(withoutHash);
}

export async function worldProgramBundleVerificationCertificateHash(
  certificate: WorldProgramBundleVerificationCertificate,
): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function worldProgramReplayStepHash(step: WorldProgramReplayStep): Promise<string> {
  const { stepHash: _stepHash, ...withoutHash } = step;
  return stableHash(withoutHash);
}

export async function worldProgramReplayPackageBodyHash(replayPackage: WorldProgramReplayPackage): Promise<string> {
  return stableHash({
    evidenceBundleHash: replayPackage.evidenceBundle.bundleHash,
    steps: replayPackage.steps,
  });
}

export async function worldProgramReplayPackageHash(replayPackage: WorldProgramReplayPackage): Promise<string> {
  const { packageHash: _packageHash, ...withoutHash } = replayPackage;
  return stableHash(withoutHash);
}

export async function worldProgramReplayVerificationCertificateHash(
  certificate: WorldProgramReplayVerificationCertificate,
): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function tamperWorldProgramCertificate(certificate: WorldProgramCertificate): Promise<WorldProgramCertificate> {
  const tampered = { ...certificate, stepCount: certificate.stepCount + 1, certificateHash: "" };
  return { ...tampered, certificateHash: await worldProgramCertificateHash(tampered) };
}

export async function tamperWorldProgramAdmissionCertificate(
  certificate: WorldProgramAdmissionCertificate,
): Promise<WorldProgramAdmissionCertificate> {
  const tampered = { ...certificate, admitted: !certificate.admitted, certificateHash: "" };
  return { ...tampered, certificateHash: await worldProgramAdmissionCertificateHash(tampered) };
}

export async function tamperWorldProgramEvidenceBundle(bundle: WorldProgramEvidenceBundle): Promise<WorldProgramEvidenceBundle> {
  const tampered = { ...bundle, receiptHashes: [...bundle.receiptHashes].reverse(), bundleHash: "" };
  return { ...tampered, bundleHash: await worldProgramEvidenceBundleHash(tampered) };
}

export async function tamperWorldProgramBundleVerificationCertificate(
  certificate: WorldProgramBundleVerificationCertificate,
): Promise<WorldProgramBundleVerificationCertificate> {
  const tampered = { ...certificate, verified: !certificate.verified, certificateHash: "" };
  return { ...tampered, certificateHash: await worldProgramBundleVerificationCertificateHash(tampered) };
}

export async function tamperWorldProgramReplayPackage(replayPackage: WorldProgramReplayPackage): Promise<WorldProgramReplayPackage> {
  const tampered = {
    ...replayPackage,
    receiptHashes: [...replayPackage.receiptHashes].reverse(),
    packageHash: "",
  };
  const withBody = { ...tampered, packageBodyHash: await worldProgramReplayPackageBodyHash(tampered) };
  return { ...withBody, packageHash: await worldProgramReplayPackageHash(withBody) };
}

export async function tamperWorldProgramReplayVerificationCertificate(
  certificate: WorldProgramReplayVerificationCertificate,
): Promise<WorldProgramReplayVerificationCertificate> {
  const tampered = { ...certificate, replayVerified: !certificate.replayVerified, certificateHash: "" };
  return { ...tampered, certificateHash: await worldProgramReplayVerificationCertificateHash(tampered) };
}

function componentValue(component: unknown, camelName: string, snakeName: string, fallback: string): string {
  if (!component || typeof component !== "object") {
    return fallback;
  }
  const row = component as Record<string, unknown>;
  const value = row[camelName] ?? row[snakeName] ?? fallback;
  return String(value);
}

function isHash(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
}

function positiveInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) > 0;
}

function nonnegativeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}

function sameCertificate(left: WorldProgramCertificate, right: WorldProgramCertificate): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

async function evaluateWorldProgramAdmission(
  policy: WorldProgramAdmissionPolicy,
  manifest: WorldProgramManifest,
  executionCertificate: WorldProgramCertificate,
): Promise<{ passed: string[]; failed: string[] }> {
  const dependencySet = new Set(manifest.resolvedDependencies);
  const artifactGroups = executionCertificate.artifactHashGroups;
  const checks: Array<[string, boolean]> = [
    ["policy_valid", await validateWorldProgramAdmissionPolicy(policy)],
    ["manifest_valid", await validateWorldProgramManifest(manifest)],
    ["execution_certificate_valid", await validateWorldProgramCertificate(executionCertificate, manifest)],
    ["build_type_allowed", allowed(policy.allowedBuildTypes, manifest.buildType)],
    ["program_id_allowed", allowed(policy.allowedProgramIds, manifest.programId)],
    ["program_version_allowed", allowed(policy.allowedProgramVersions, manifest.programVersion)],
    ["proposer_allowed", allowed(policy.allowedProposerIds, manifest.proposerId)],
    ["projector_allowed", allowed(policy.allowedProjectorIds, manifest.projectorId)],
    ["learner_allowed", allowed(policy.allowedLearnerIds, manifest.learnerId)],
    ["verifier_allowed", allowed(policy.allowedVerifierIds, manifest.verifierId)],
    ["input_schema_allowed", allowed(policy.allowedInputSchemas, manifest.inputSchema)],
    ["candidate_schema_allowed", allowed(policy.allowedCandidateSchemas, manifest.candidateSchema)],
    ["required_dependencies_present", policy.requiredDependencies.every((dependency) => dependencySet.has(dependency))],
    [
      "required_artifacts_present",
      policy.requiredArtifactKeys.every((key) => Array.isArray(artifactGroups[key]) && artifactGroups[key].length > 0),
    ],
    ["min_step_count", executionCertificate.stepCount >= policy.minStepCount],
    ["min_committed_count", executionCertificate.committedCount >= policy.minCommittedCount],
    ["min_rejected_count", executionCertificate.rejectedCount >= policy.minRejectedCount],
    ["invalid_commit_bound", executionCertificate.invalidCommitCount <= policy.maxInvalidCommitCount],
    ["replay_rollback_rate_bound", executionCertificate.replayRollbackRate >= policy.minReplayRollbackRate],
  ];
  return {
    passed: checks.filter(([_key, ok]) => ok).map(([key]) => key),
    failed: checks.filter(([_key, ok]) => !ok).map(([key]) => key),
  };
}

async function evaluateWorldProgramBundleVerification(
  bundle: WorldProgramEvidenceBundle,
): Promise<{ passed: string[]; failed: string[] }> {
  const checks: Array<[string, boolean]> = [
    ["bundle_valid", await validateWorldProgramEvidenceBundle(bundle)],
    ["manifest_valid", await validateWorldProgramManifest(bundle.manifest)],
    ["execution_certificate_valid", await validateWorldProgramCertificate(bundle.executionCertificate, bundle.manifest)],
    ["admission_policy_valid", await validateWorldProgramAdmissionPolicy(bundle.admissionPolicy)],
    [
      "admission_certificate_valid",
      await validateWorldProgramAdmissionCertificate(
        bundle.admissionCertificate,
        bundle.admissionPolicy,
        bundle.manifest,
        bundle.executionCertificate,
      ),
    ],
    ["admission_certificate_admitted", bundle.admissionCertificate.admitted],
    ["step_hashes_bound", sameStringArray(bundle.stepCertificateHashes, bundle.executionCertificate.stepCertificateHashes)],
    ["receipt_hashes_bound", sameStringArray(bundle.receiptHashes, bundle.executionCertificate.receiptHashes)],
    ["learner_snapshot_bound", bundle.finalLearnerSnapshotHash === bundle.executionCertificate.finalLearnerSnapshotHash],
    ["artifact_groups_bound", sameHashGroups(bundle.artifactHashGroups, bundle.executionCertificate.artifactHashGroups)],
    ["input_attestations_bound", (await bundleInputAttestationHashes(bundle)).every(isHash)],
  ];
  return {
    passed: checks.filter(([_key, ok]) => ok).map(([key]) => key),
    failed: checks.filter(([_key, ok]) => !ok).map(([key]) => key),
  };
}

async function evaluateWorldProgramReplayVerification(
  replayPackage: WorldProgramReplayPackage,
): Promise<{ passed: string[]; failed: string[] }> {
  const executionCertificate = replayPackage.evidenceBundle.executionCertificate;
  const traceHashesBound = (await Promise.all(
    replayPackage.steps.map(async (step) => await stableHash(step.trace) === step.receipt.proposalTraceHash),
  )).every(Boolean);
  const candidateHashesBound = (await Promise.all(
    replayPackage.steps.map(async (step) => await stableHash(step.candidate) === step.receipt.typedCandidateHash),
  )).every(Boolean);
  const receiptsValid = (await Promise.all(replayPackage.steps.map((step) => receiptStaticValid(step.receipt)))).every(Boolean);
  const stepCertificatesValid = (await Promise.all(
    replayPackage.steps.map((step) => validateWorldModelStepCertificate(step.certificate)),
  )).every(Boolean);
  const learnerUpdatesValid = (await Promise.all(
    replayPackage.steps.map((step) => validateWorldLearnerUpdateCertificate(step.learnerUpdateCertificate)),
  )).every(Boolean);
  const learnerDeltasValid = (await Promise.all(
    replayPackage.steps.map((step) => validateWorldLearnerDeltaCertificate(step.learnerDeltaCertificate)),
  )).every(Boolean);
  const learnerLineageBound = replayPackage.steps.length > 0
    && replayPackage.finalLearnerSnapshotHash === replayPackage.steps[replayPackage.steps.length - 1].learnerSnapshot.snapshotHash;
  const checks: Array<[string, boolean]> = [
    ["replay_package_valid", await validateWorldProgramReplayPackage(replayPackage)],
    ["evidence_bundle_valid", await validateWorldProgramEvidenceBundle(replayPackage.evidenceBundle)],
    ["admission_certificate_admitted", replayPackage.evidenceBundle.admissionCertificate.admitted],
    ["step_count_matches_execution", replayPackage.steps.length === executionCertificate.stepCount],
    ["receipt_hashes_bound", sameStringArray(replayPackage.receiptHashes, executionCertificate.receiptHashes)],
    ["step_certificate_hashes_bound", sameStringArray(replayPackage.stepCertificateHashes, executionCertificate.stepCertificateHashes)],
    ["final_learner_snapshot_bound", replayPackage.finalLearnerSnapshotHash === executionCertificate.finalLearnerSnapshotHash],
    ["ledger_head_bound", replayPackage.ledgerHead === executionCertificate.ledgerHead],
    ["trace_hashes_bound", traceHashesBound],
    ["candidate_hashes_bound", candidateHashesBound],
    ["receipts_valid", receiptsValid],
    ["step_certificates_valid", stepCertificatesValid],
    ["learner_updates_valid", learnerUpdatesValid],
    ["learner_deltas_valid", learnerDeltasValid],
    ["learner_lineage_bound", learnerLineageBound],
    ["package_body_hash_bound", replayPackage.packageBodyHash === await worldProgramReplayPackageBodyHash(replayPackage)],
  ];
  return {
    passed: checks.filter(([_key, ok]) => ok).map(([key]) => key),
    failed: checks.filter(([_key, ok]) => !ok).map(([key]) => key),
  };
}

async function bundleInputAttestationHashes(bundle: WorldProgramEvidenceBundle): Promise<string[]> {
  return [
    bundle.manifest.manifestHash,
    bundle.executionCertificate.certificateHash,
    bundle.admissionPolicy.policyHash,
    bundle.admissionCertificate.certificateHash,
    await stableHash(bundle.stepCertificateHashes),
    await stableHash(bundle.receiptHashes),
    bundle.finalLearnerSnapshotHash,
    await stableHash(bundle.artifactHashGroups),
  ];
}

function allowed(allowedValues: string[], value: string): boolean {
  return allowedValues.length === 0 || allowedValues.includes(value);
}

function dedupeStrings(values: string[]): string[] {
  const result: string[] = [];
  for (const value of values) {
    const text = String(value);
    if (!result.includes(text)) {
      result.push(text);
    }
  }
  return result;
}

function sameAdmissionCertificate(left: WorldProgramAdmissionCertificate, right: WorldProgramAdmissionCertificate): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function sameEvidenceBundle(left: WorldProgramEvidenceBundle, right: WorldProgramEvidenceBundle): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function sameBundleVerificationCertificate(
  left: WorldProgramBundleVerificationCertificate,
  right: WorldProgramBundleVerificationCertificate,
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function sameReplayPackage(left: WorldProgramReplayPackage, right: WorldProgramReplayPackage): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function sameReplayVerificationCertificate(
  left: WorldProgramReplayVerificationCertificate,
  right: WorldProgramReplayVerificationCertificate,
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function sameStringArray(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value, idx) => value === right[idx]);
}

function sortedHashGroups(groups: Record<string, string[]>): Record<string, string[]> {
  const result: Record<string, string[]> = {};
  for (const key of Object.keys(groups).sort()) {
    result[key] = [...groups[key]];
  }
  return result;
}

function sameHashGroups(left: Record<string, string[]>, right: Record<string, string[]>): boolean {
  return JSON.stringify(sortedHashGroups(left)) === JSON.stringify(sortedHashGroups(right));
}

function isReplayStep(step: WorldModelStepResult | WorldProgramReplayStep): step is WorldProgramReplayStep {
  return Boolean(
    step
    && typeof step === "object"
    && "schemaVersion" in step
    && (step as { schemaVersion?: unknown }).schemaVersion === WORLD_PROGRAM_REPLAY_STEP_SCHEMA,
  );
}

async function ledgerHeadFromReplaySteps(steps: WorldProgramReplayStep[]): Promise<string> {
  let head = GENESIS_HEAD;
  for (const step of steps) {
    if (step.receipt.parentHead !== head) {
      return "";
    }
    head = await chainHash(head, step.receipt.receiptHash);
  }
  return head;
}
