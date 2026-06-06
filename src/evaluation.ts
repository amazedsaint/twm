import { stableHash } from "./canonical.js";

export const LEARNING_EVALUATION_CERTIFICATE_SCHEMA = "trwm.learning_evaluation_certificate.v1";

export interface LearningEvaluationCertificate {
  schemaVersion: typeof LEARNING_EVALUATION_CERTIFICATE_SCHEMA;
  claimId: string;
  learnerId: string;
  learnerSnapshotHash: string;
  trainingReceiptHashes: string[];
  evaluationReceiptHashes: string[];
  baselineName: string;
  learnedName: string;
  baselineVerifierCalls: number;
  learnedVerifierCalls: number;
  baselineSuccessCount: number;
  learnedSuccessCount: number;
  verifierBudget: number;
  candidateCount: number;
  sameCaseBaseline: boolean;
  trainEvalDisjoint: boolean;
  hardCommitOnly: boolean;
  invalidCommitCount: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
  verifierCallGainNumerator: number;
  verifierCallGainDenominator: number;
  metrics: Record<string, unknown>;
  certificateHash: string;
}

export async function buildLearningEvaluationCertificate(params: {
  claimId: string;
  learnerId: string;
  learnerSnapshotHash: string;
  trainingReceiptHashes: string[];
  evaluationReceiptHashes: string[];
  baselineName: string;
  learnedName: string;
  baselineVerifierCalls: number;
  learnedVerifierCalls: number;
  baselineSuccessCount: number;
  learnedSuccessCount: number;
  verifierBudget: number;
  candidateCount: number;
  sameCaseBaseline: boolean;
  hardCommitOnly: boolean;
  invalidCommitCount: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
  metrics?: Record<string, unknown>;
}): Promise<LearningEvaluationCertificate> {
  const certificate: LearningEvaluationCertificate = {
    schemaVersion: LEARNING_EVALUATION_CERTIFICATE_SCHEMA,
    claimId: params.claimId,
    learnerId: params.learnerId,
    learnerSnapshotHash: params.learnerSnapshotHash,
    trainingReceiptHashes: [...params.trainingReceiptHashes],
    evaluationReceiptHashes: [...params.evaluationReceiptHashes],
    baselineName: params.baselineName,
    learnedName: params.learnedName,
    baselineVerifierCalls: params.baselineVerifierCalls,
    learnedVerifierCalls: params.learnedVerifierCalls,
    baselineSuccessCount: params.baselineSuccessCount,
    learnedSuccessCount: params.learnedSuccessCount,
    verifierBudget: params.verifierBudget,
    candidateCount: params.candidateCount,
    sameCaseBaseline: params.sameCaseBaseline,
    trainEvalDisjoint: disjoint(params.trainingReceiptHashes, params.evaluationReceiptHashes),
    hardCommitOnly: params.hardCommitOnly,
    invalidCommitCount: params.invalidCommitCount,
    ledgerAudit: params.ledgerAudit,
    replayRollbackRate: params.replayRollbackRate,
    verifierCallGainNumerator: params.baselineVerifierCalls,
    verifierCallGainDenominator: params.learnedVerifierCalls,
    metrics: params.metrics ?? {},
    certificateHash: "",
  };
  certificate.certificateHash = await learningEvaluationCertificateHash(certificate);
  return certificate;
}

export async function learningEvaluationCertificateHash(certificate: LearningEvaluationCertificate): Promise<string> {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function validateLearningEvaluationCertificate(certificate: LearningEvaluationCertificate): Promise<boolean> {
  try {
    if (certificate.schemaVersion !== LEARNING_EVALUATION_CERTIFICATE_SCHEMA) {
      return false;
    }
    const requiredStrings = [
      certificate.claimId,
      certificate.learnerId,
      certificate.baselineName,
      certificate.learnedName,
    ];
    if (!requiredStrings.every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!isHash(certificate.learnerSnapshotHash)) {
      return false;
    }
    if (certificate.trainingReceiptHashes.length === 0 || certificate.evaluationReceiptHashes.length === 0) {
      return false;
    }
    if (![...certificate.trainingReceiptHashes, ...certificate.evaluationReceiptHashes].every(isHash)) {
      return false;
    }
    if (new Set(certificate.trainingReceiptHashes).size !== certificate.trainingReceiptHashes.length) {
      return false;
    }
    if (new Set(certificate.evaluationReceiptHashes).size !== certificate.evaluationReceiptHashes.length) {
      return false;
    }
    const actualDisjoint = disjoint(certificate.trainingReceiptHashes, certificate.evaluationReceiptHashes);
    if (certificate.trainEvalDisjoint !== actualDisjoint || !actualDisjoint) {
      return false;
    }
    const ints = [
      certificate.baselineVerifierCalls,
      certificate.learnedVerifierCalls,
      certificate.baselineSuccessCount,
      certificate.learnedSuccessCount,
      certificate.verifierBudget,
      certificate.candidateCount,
      certificate.invalidCommitCount,
      certificate.verifierCallGainNumerator,
      certificate.verifierCallGainDenominator,
    ];
    if (ints.some((value) => !Number.isInteger(value) || value < 0)) {
      return false;
    }
    if (certificate.learnedVerifierCalls === 0 || certificate.verifierCallGainDenominator === 0) {
      return false;
    }
    if (certificate.verifierCallGainNumerator !== certificate.baselineVerifierCalls) {
      return false;
    }
    if (certificate.verifierCallGainDenominator !== certificate.learnedVerifierCalls) {
      return false;
    }
    if (certificate.learnedVerifierCalls > certificate.verifierBudget) {
      return false;
    }
    if (certificate.baselineSuccessCount > certificate.baselineVerifierCalls) {
      return false;
    }
    if (certificate.learnedSuccessCount > certificate.learnedVerifierCalls) {
      return false;
    }
    if (typeof certificate.sameCaseBaseline !== "boolean" || typeof certificate.hardCommitOnly !== "boolean") {
      return false;
    }
    if (typeof certificate.ledgerAudit !== "boolean") {
      return false;
    }
    if (certificate.replayRollbackRate < 0 || certificate.replayRollbackRate > 1) {
      return false;
    }
    if (!isHash(certificate.certificateHash)) {
      return false;
    }
    return certificate.certificateHash === await learningEvaluationCertificateHash(certificate);
  } catch {
    return false;
  }
}

export async function learningEvaluationSupportsClaim(certificate: LearningEvaluationCertificate): Promise<boolean> {
  return await validateLearningEvaluationCertificate(certificate)
    && certificate.sameCaseBaseline
    && certificate.trainEvalDisjoint
    && certificate.hardCommitOnly
    && certificate.invalidCommitCount === 0
    && certificate.ledgerAudit
    && certificate.replayRollbackRate === 1
    && certificate.learnedSuccessCount > certificate.baselineSuccessCount;
}

function disjoint(left: string[], right: string[]): boolean {
  const seen = new Set(left);
  return right.every((value) => !seen.has(value));
}

function isHash(value: string): boolean {
  return /^[0-9a-f]{64}$/.test(value);
}
