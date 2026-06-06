import {

  certifyClaim,
  failedClaimKeys,
  requirement,
  validateClaimCertificate,
} from "./claims.js";
import { runBudgetPolicyBenchmark } from "./budget_policy_benchmark.js";
import { runLearningEvaluationBenchmark } from "./learning_evaluation.js";
import { runResidualTopKBenchmark } from "./residual_topk.js";
import { runRrlmMacroBenchmark,                      } from "./rrlm.js";
import { runShapeConditionality } from "./shape.js";
import { runCrossDomainTransferAudit } from "./transfer_audit.js";
import { runTransferGuardBenchmark } from "./transfer_guard.js";
import { runWorldLoopBenchmark } from "./world_loop.js";

export const PROV_SOURCE = "https://www.w3.org/TR/prov-overview/";
export const ASSURANCE_SOURCE = "https://standards.iteh.ai/catalog/standards/iso/4734d411-2bff-428f-8f4a-164859f171b8/iso-iec-ieee-15026-2-2022";











































export async function runClaimAuditBenchmark()                            {
  const budget = await runBudgetPolicyBenchmark();
  const learningEval = await runLearningEvaluationBenchmark();
  const topk = await runResidualTopKBenchmark();
  const rrlm = await runRrlmMacroBenchmark();
  const shape = await runShapeConditionality();
  const transfer = await runCrossDomainTransferAudit();
  const transferGuard = await runTransferGuardBenchmark();
  const worldLoop = await runWorldLoopBenchmark();

  const invalidCommitCount = budget.invalidCommitCount
    + learningEval.invalidCommitCount
    + topk.invalidCommitCount
    + rrlm.invalidCommitCount
    + shape.invalidCommitCount
    + transfer.invalidCommitCount
    + transferGuard.invalidCommitCount
    + worldLoop.invalidCommitCount;
  const ledgerAudit = budget.ledgerAudit && learningEval.ledgerAudit && topk.ledgerAudit && rrlm.ledgerAudit && shape.ledgerAudit && transfer.ledgerAudit && transferGuard.ledgerAudit && worldLoop.ledgerAudit;
  const replayRollbackRate = Math.min(
    budget.replayRollbackRate,
    learningEval.replayRollbackRate,
    topk.replayRollbackRate,
    transfer.replayRollbackRate,
    transferGuard.replayRollbackRate,
    worldLoop.replayRollbackRate,
  );
  const heldoutTraceEvaluation = budget.heldoutTraceDisjoint
    && budget.evaluationReceiptCount > 0
    && learningEval.trainEvalDisjoint
    && learningEval.evaluationReceiptCount > 0
    && transfer.sourceTargetReceiptDisjoint
    && transfer.targetEvaluationReceiptCount > 0;
  const sameCaseEqualBudget = budget.budget === 3
    && budget.candidateCount === 4
    && learningEval.sameCaseBaseline
    && learningEval.verifierBudget === 3
    && learningEval.candidateCount === 4
    && topk.topK === 2
    && topk.candidateCount === 4
    && transfer.sameCaseBaseline
    && transfer.transferVerifierCalls === transfer.baselineVerifierCalls;
  const verifierCallAccounting = near(budget.verifierCallGain, budget.cheapFirstVerifierCalls / budget.learnedVerifierCalls)
    && learningEval.verifierCallGainDenominator > 0
    && learningEval.verifierCallGainNumerator === learningEval.baselineVerifierCalls
    && learningEval.verifierCallGainDenominator === learningEval.learnedVerifierCalls
    && near(topk.callsToCommitGain, topk.unrankedVerifierCalls / topk.residualRankedVerifierCalls)
    && transfer.successDelta === transfer.transferSuccessCount - transfer.baselineSuccessCount
    && transfer.verifierCallDelta === transfer.transferVerifierCalls - transfer.baselineVerifierCalls;
  const learningEvaluationCertificateValid = learningEval.certificateValid;
  const learningEvaluationSupportsClaim = learningEval.certificateSupportsClaim;
  const transferEvaluationCertificateValid = transfer.certificateValid;
  const transferPositiveOverclaimRejected = transfer.positiveTransferClaimRejected && !transfer.positiveTransferClaimSupported;
  const transferGuardSnapshotValid = transferGuard.snapshotValid && transferGuard.decisionValid;
  const transferGuardBlocksNegativeTransfer = transferGuard.guardBlocksSourcePolicy
    && transferGuard.avoidedNegativeTransfer
    && !transferGuard.guardDecisionAdmitted
    && transferGuard.certificateConclusion === "negative_transfer";
  const rrlmProposalCertificateValid = rrlm.snapshotValid && rrlm.proposalCertificateValid;
  const rrlmTransportCertificateValid = rrlm.transportCertificateValid
    && rrlm.transportCertificateI32AdmissibleCount > 0
    && rrlm.transportCertificateI32RejectedCount === 0
    && rrlm.transportTamperDetected;
  const worldLearnerUpdateCertificateValid = worldLoop.learnerUpdateCertificateValidCount === worldLoop.stepCount
    && worldLoop.learnerUpdateAuditValidCount === worldLoop.stepCount
    && worldLoop.stepCertificateBindsLearnerUpdate
    && worldLoop.learnerUpdateTamperDetected;
  const worldLearnerDeltaCertificateValid = worldLoop.learnerDeltaCertificateValidCount === worldLoop.stepCount
    && worldLoop.learnerDeltaAuditValidCount === worldLoop.stepCount
    && worldLoop.learnerDeltaBindsUpdates
    && worldLoop.learnerDeltaTamperDetected;
  const worldLearnerLineageCertificateValid = worldLoop.learnerLineageCertificateValid
    && worldLoop.learnerLineageAuditValid
    && worldLoop.learnerLineageBindsUpdates
    && worldLoop.learnerLineageTamperDetected;
  const worldLearnerMergeCertificateValid = worldLoop.learnerMergeCertificateValid
    && worldLoop.learnerMergeAuditValid
    && worldLoop.learnerMergeDisjointReceipts
    && worldLoop.learnerMergeTamperDetected
    && worldLoop.learnerMergeConflictDetected;
  const worldLearnerPartialOverlapMergeValid = worldLoop.learnerMergePartialOverlapValid
    && worldLoop.learnerMergePartialOverlapAuditValid
    && worldLoop.learnerMergePartialOverlapCountsSharedOnce
    && worldLoop.learnerMergePartialOverlapRequiresDeltas;
  const worldRrlmProposalCertificateValid = !worldLoop.rrlmWorldFirstCommitted
    && worldLoop.rrlmWorldSecondCommitted
    && worldLoop.rrlmWorldSelectedRepairMacro
    && worldLoop.rrlmWorldProposalCertificateValid
    && worldLoop.rrlmWorldTransportCertificateValid
    && worldLoop.rrlmWorldArtifactsBoundToReceipts
    && worldLoop.rrlmWorldRejectedMacroPenalized
    && worldLoop.rrlmWorldTamperDetected;
  const worldProgramCertificateValid = worldLoop.worldProgramManifestValid
    && worldLoop.worldProgramCertificateValid
    && worldLoop.worldProgramAuditValid
    && worldLoop.worldProgramBindsRrlmArtifacts
    && worldLoop.worldProgramTamperDetected;
  const worldProgramAdmissionCertificateValid = worldProgramCertificateValid
    && worldLoop.worldProgramAdmissionPolicyValid
    && worldLoop.worldProgramAdmissionCertificateValid
    && worldLoop.worldProgramAdmissionAuditValid
    && worldLoop.worldProgramAdmitted
    && worldLoop.worldProgramAdmissionRejectsUnmetRequirements
    && worldLoop.worldProgramAdmissionTamperDetected;
  const worldProgramBundleVerificationCertificateValid = worldProgramAdmissionCertificateValid
    && worldLoop.worldProgramEvidenceBundleValid
    && worldLoop.worldProgramEvidenceBundleAuditValid
    && worldLoop.worldProgramBundleVerificationCertificateValid
    && worldLoop.worldProgramBundleVerified
    && worldLoop.worldProgramBundleTamperDetected;
  const worldProgramReplayVerificationCertificateValid = worldProgramBundleVerificationCertificateValid
    && worldLoop.worldProgramReplayPackageValid
    && worldLoop.worldProgramReplayPackageAuditValid
    && worldLoop.worldProgramReplayVerificationCertificateValid
    && worldLoop.worldProgramReplayVerified
    && worldLoop.worldProgramReplayTamperDetected;
  const mechanismAblationRecorded = rrlm.reversibleOnlyAttemptsPerSuccess > 0
    && rrlm.matchedNonReversibleAttemptsPerSuccess > 0
    && rrlm.rrlmAttemptsPerSuccess > 0
    && rrlm.rrlmCycleFailureCount === 0;
  const highRankGain = Math.min(shape.highReceiptGain, shape.highHdcGain);
  const nullResultRecorded = near(rrlm.rrlmVsNonReversibleGain, 1) && !shape.highPreflightFitsBudget;

  const supported = await supportedCertificate({
    invalidCommitCount,
    ledgerAudit,
    replayRollbackRate,
    heldoutTraceEvaluation,
    sameCaseEqualBudget,
    verifierCallAccounting,
    learningEvaluationCertificateValid,
    learningEvaluationSupportsClaim,
    transferEvaluationCertificateValid,
    transferPositiveOverclaimRejected,
    transferGuardSnapshotValid,
    transferGuardBlocksNegativeTransfer,
    rrlmProposalCertificateValid,
    rrlmTransportCertificateValid,
    worldLearnerUpdateCertificateValid,
    worldLearnerDeltaCertificateValid,
    worldLearnerLineageCertificateValid,
    worldLearnerMergeCertificateValid,
    worldLearnerPartialOverlapMergeValid,
    worldRrlmProposalCertificateValid,
    worldProgramCertificateValid,
    worldProgramAdmissionCertificateValid,
    worldProgramBundleVerificationCertificateValid,
    worldProgramReplayVerificationCertificateValid,
    mechanismAblationRecorded,
    nullResultRecorded,
    budgetCallGain: budget.verifierCallGain,
    topkCallGain: topk.callsToCommitGain,
    learningEvalCertificateHash: learningEval.certificateHash,
    transferCertificateHash: transfer.certificateHash,
    transferGuardSnapshotHash: transferGuard.snapshotHash,
    transferGuardDecisionHash: transferGuard.guardDecisionHash,
    rrlmProposalCertificateHash: rrlm.proposalCertificateHash,
    rrlmTransportCertificateHash: rrlm.transportCertificateHash,
    transferSuccessDelta: transfer.successDelta,
    rrlmVsNonReversibleGain: rrlm.rrlmVsNonReversibleGain,
    highRankGain,
  });
  const rejected = await overclaimCertificate(rrlm);
  const tampered = { ...supported, metrics: { ...supported.metrics, invalidCommitCount: 1 } };

  return {
    supportedClaimId: supported.claimId,
    supportedStatus: supported.status,
    supportedRequirementCount: supported.requirements.length,
    supportedFailedKeys: failedClaimKeys(supported),
    rejectedClaimId: rejected.claimId,
    rejectedStatus: rejected.status,
    rejectedFailedKeys: failedClaimKeys(rejected),
    overclaimDetected: rejected.status === "rejected" && failedClaimKeys(rejected).includes("matched_non_reversible_lift"),
    nullResultRecorded,
    mechanismAblationRecorded,
    heldoutTraceEvaluation,
    sameCaseEqualBudget,
    verifierCallAccounting,
    learningEvaluationCertificateValid,
    learningEvaluationSupportsClaim,
    transferEvaluationCertificateValid,
    transferPositiveOverclaimRejected,
    transferGuardSnapshotValid,
    transferGuardBlocksNegativeTransfer,
    rrlmProposalCertificateValid,
    rrlmTransportCertificateValid,
    worldLearnerUpdateCertificateValid,
    worldLearnerDeltaCertificateValid,
    worldLearnerLineageCertificateValid,
    worldLearnerMergeCertificateValid,
    worldLearnerPartialOverlapMergeValid,
    worldRrlmProposalCertificateValid,
    worldProgramCertificateValid,
    worldProgramAdmissionCertificateValid,
    worldProgramBundleVerificationCertificateValid,
    worldProgramReplayVerificationCertificateValid,
    supportedCertificateValid: await validateClaimCertificate(supported),
    rejectedCertificateValid: await validateClaimCertificate(rejected),
    tamperDetected: !await validateClaimCertificate(tampered),
    invalidCommitCount,
    ledgerAudit,
    replayRollbackRate,
    supportedCertificateHash: supported.certificateHash,
    rejectedCertificateHash: rejected.certificateHash,
  };
}

async function supportedCertificate(params





































 )                            {
  return certifyClaim({
    claimId: "g1_learning_claim_boundary",
    claimText: "Selected G1 learning canaries preserve transaction safety and record baselines, ablations, nulls, and trace-disjoint evaluation.",
    evidenceGrade: "G1",
    scope: "budget-policy, residual-topk, RRLM macro, and shape-conditionality canaries",
    boundary: "This certificate supports only local deterministic G1 evidence. It is not public benchmark lift, learned-model lift, or real-world safety evidence.",
    sources: [PROV_SOURCE, ASSURANCE_SOURCE],
    metrics: {
      budgetCallGain: params.budgetCallGain,
      topkCallGain: params.topkCallGain,
      learningEvalCertificateHash: params.learningEvalCertificateHash,
      transferCertificateHash: params.transferCertificateHash,
      transferGuardSnapshotHash: params.transferGuardSnapshotHash,
      transferGuardDecisionHash: params.transferGuardDecisionHash,
      rrlmProposalCertificateHash: params.rrlmProposalCertificateHash,
      rrlmTransportCertificateHash: params.rrlmTransportCertificateHash,
      transferSuccessDelta: params.transferSuccessDelta,
      rrlmVsNonReversibleGain: params.rrlmVsNonReversibleGain,
      highRankGain: params.highRankGain,
      invalidCommitCount: params.invalidCommitCount,
      replayRollbackRate: params.replayRollbackRate,
    },
    requirements: [
      requirement("claim_boundary_g1", true, { evidence: { evidenceGrade: "G1" } }),
      requirement("invalid_commits_zero", params.invalidCommitCount === 0, { evidence: { invalidCommitCount: params.invalidCommitCount } }),
      requirement("ledger_audit", params.ledgerAudit),
      requirement("replay_rollback_rate_one", near(params.replayRollbackRate, 1), { evidence: { replayRollbackRate: params.replayRollbackRate } }),
      requirement("trace_disjoint_evaluation", params.heldoutTraceEvaluation),
      requirement("same_case_equal_budget", params.sameCaseEqualBudget),
      requirement("verifier_call_accounting", params.verifierCallAccounting),
      requirement("learning_evaluation_certificate_valid", params.learningEvaluationCertificateValid),
      requirement("learning_evaluation_supports_claim", params.learningEvaluationSupportsClaim),
      requirement("transfer_evaluation_certificate_valid", params.transferEvaluationCertificateValid),
      requirement("transfer_positive_overclaim_rejected", params.transferPositiveOverclaimRejected),
      requirement("transfer_guard_snapshot_valid", params.transferGuardSnapshotValid),
      requirement("transfer_guard_blocks_negative_transfer", params.transferGuardBlocksNegativeTransfer),
      requirement("rrlm_proposal_certificate_valid", params.rrlmProposalCertificateValid),
      requirement("rrlm_transport_certificate_valid", params.rrlmTransportCertificateValid),
      requirement("world_learner_update_certificate_valid", params.worldLearnerUpdateCertificateValid),
      requirement("world_learner_delta_certificate_valid", params.worldLearnerDeltaCertificateValid),
      requirement("world_learner_lineage_certificate_valid", params.worldLearnerLineageCertificateValid),
      requirement("world_learner_merge_certificate_valid", params.worldLearnerMergeCertificateValid),
      requirement("world_learner_partial_overlap_merge_valid", params.worldLearnerPartialOverlapMergeValid),
      requirement("world_rrlm_proposal_certificate_valid", params.worldRrlmProposalCertificateValid),
      requirement("world_program_certificate_valid", params.worldProgramCertificateValid),
      requirement("world_program_admission_certificate_valid", params.worldProgramAdmissionCertificateValid),
      requirement("world_program_bundle_verification_certificate_valid", params.worldProgramBundleVerificationCertificateValid),
      requirement("world_program_replay_verification_certificate_valid", params.worldProgramReplayVerificationCertificateValid),
      requirement("mechanism_ablation_recorded", params.mechanismAblationRecorded),
      requirement("null_result_recorded", params.nullResultRecorded),
      requirement("soft_scores_no_commit_authority", true, { reason: "all listed learners rank or schedule only; commit evidence is hard-verifier ledger evidence" }),
    ],
  });
}

async function overclaimCertificate(rrlm                 )                            {
  return certifyClaim({
    claimId: "rrlm_reversibility_alone_lift_overclaim",
    claimText: "RRLM reversibility alone improves over the matched non-reversible receipt ranker.",
    evidenceGrade: "G1",
    scope: "RRLM macro-grid canary",
    boundary: "The current result ties the matched non-reversible ranker, so mechanism lift is rejected.",
    sources: [PROV_SOURCE, ASSURANCE_SOURCE],
    metrics: {
      rrlmVsNonReversibleGain: rrlm.rrlmVsNonReversibleGain,
      cycleFailureCount: rrlm.rrlmCycleFailureCount,
      invalidCommitCount: rrlm.invalidCommitCount,
    },
    requirements: [
      requirement("cycle_exactness", rrlm.rrlmCycleFailureCount === 0, { evidence: { cycleFailures: rrlm.rrlmCycleFailureCount } }),
      requirement("mechanism_ablation_present", rrlm.matchedNonReversibleAttemptsPerSuccess > 0),
      requirement("matched_non_reversible_lift", rrlm.rrlmVsNonReversibleGain > 1, { evidence: { gain: rrlm.rrlmVsNonReversibleGain } }),
      requirement("invalid_commits_zero", rrlm.invalidCommitCount === 0, { evidence: { invalidCommitCount: rrlm.invalidCommitCount } }),
    ],
  });
}

function near(left        , right        , eps = 1e-12)          {
  return Math.abs(left - right) <= eps;
}
