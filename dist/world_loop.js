import {
                     
               
                      
  Ledger,
  TransactionEngine,
  makeTrace,
} from "./core.js";
import { stableHash } from "./canonical.js";
import {
             
} from "./macro.js";
import {
                         
                               
                                
  RrlmMacroProposer,
  buildRrlmProposalCertificate,
  buildRrlmTransportCertificate,
  rrlmProposalCertificateHash,
  validateRrlmMacroSnapshot,
  validateRrlmProposalCertificate,
  validateRrlmTransportCertificate,
} from "./rrlm.js";
import {
                   
                            
                          
  ScalarProgramAdapter,
  makeScalarCandidate,
} from "./repair.js";
import {
                            
                            
  TransactionalWorldModelRuntime,
  auditWorldLearnerDelta,
  auditWorldLearnerLineage,
  auditWorldLearnerMerge,
  auditWorldLearnerUpdate,
  auditWorldModelStep,
  buildWorldLearnerLineageCertificate,
  mergeWorldLearnerSnapshots,
  validateWorldLearnerDeltaCertificate,
  validateWorldLearnerLineageCertificate,
  validateWorldLearnerMergeCertificate,
  validateWorldLearnerSnapshot,
  validateWorldLearnerUpdateCertificate,
  validateWorldModelStepCertificate,
  worldLearnerDeltaCertificateHash,
  worldLearnerLineageCertificateHash,
  worldLearnerMergeCertificateHash,
  worldLearnerSnapshotHash,
  worldLearnerStateHash,
  worldLearnerUpdateCertificateHash,
  worldModelStepCertificateHash,
} from "./world.js";
import {
                                        
                                   
                                                 
                               
                                  
                            
                                 
                                                 
  auditWorldProgramAdmission,
  auditWorldProgramBundleVerification,
  auditWorldProgramCertificate,
  auditWorldProgramEvidenceBundle,
  auditWorldProgramReplayPackage,
  auditWorldProgramReplayVerification,
  buildWorldProgramAdmissionCertificate,
  buildWorldProgramAdmissionPolicy,
  buildWorldProgramBundleVerificationCertificate,
  buildWorldProgramCertificate,
  buildWorldProgramEvidenceBundle,
  buildWorldProgramManifest,
  buildWorldProgramReplayPackage,
  buildWorldProgramReplayVerificationCertificate,
  tamperWorldProgramAdmissionCertificate,
  tamperWorldProgramBundleVerificationCertificate,
  tamperWorldProgramCertificate,
  tamperWorldProgramEvidenceBundle,
  tamperWorldProgramReplayPackage,
  tamperWorldProgramReplayVerificationCertificate,
  validateWorldProgramAdmissionCertificate,
  validateWorldProgramAdmissionPolicy,
  validateWorldProgramBundleVerificationCertificate,
  validateWorldProgramCertificate,
  validateWorldProgramEvidenceBundle,
  validateWorldProgramManifest,
  validateWorldProgramReplayPackage,
  validateWorldProgramReplayVerificationCertificate,
} from "./world_program.js";

                                  
                        
                    
                          
                           
                        
                         
                             
                        
                        
                                
                          
                                        
                                   
                                    
                                            
                                             
                                       
                                             
                                       
                                            
                                      
                                    
                                      
                                          
                                    
                                      
                                        
                                        
                                  
                                        
                                           
                                                
                                                      
                                                    
                                      
                                        
                                   
                                    
                                        
                                             
                                              
                                             
                                           
                                   
                                     
                                        
                                  
                                          
                                      
                                            
                                                 
                                           
                                
                                                         
                                               
                                           
                                                
                                                          
                                      
                                            
                                          
                                               
                                                          
                                      
                                            
                          
                                         
                             
                       
                             
 

class ResidualRepairProposer {
  proposerId = "scalar_residual_repair_proposer";
  proposerVersion = "1.0";
  target        ;
  initialGuess        ;
  learnedRepair                                      = null;

  constructor(target        , initialGuess        ) {
    this.target = target;
    this.initialGuess = initialGuess;
  }

  propose(_state                    , _budget                         )                {
    const program = [{ op: "set"         , value: this.initialGuess }];
    if (this.learnedRepair) {
      program.push(this.learnedRepair);
    }
    return makeTrace({
      branchId: `world-loop-${program.length}`,
      actions: program,
      seeds: ["world-loop", program.length],
      modelVersion: this.proposerVersion,
    });
  }
}

class ScalarProgramProjector {
  projectorId = "scalar_program_projector";
  projectorVersion = "1.0";
  target        ;

  constructor(target        ) {
    this.target = target;
  }

  project(_state                    , trace               )                                       {
    return makeScalarCandidate("world-loop", this.target, trace.actions                                               );
  }
}

class ResidualRepairLearner {
  learnerId = "scalar_residual_repair_learner";
  learnerVersion = "1.0";
  proposer                        ;
  updateCount = 0;
  rejectedCount = 0;
  acceptedCount = 0;

  constructor(proposer                        ) {
    this.proposer = proposer;
  }

  update(receipt         )       {
    this.updateCount += 1;
    if (receipt.hardResult.result === "accept" && receipt.committed) {
      this.acceptedCount += 1;
      return;
    }
    if (receipt.hardResult.result === "reject") {
      this.rejectedCount += 1;
      const residual = receipt.hardResult.residual;
      if (residual && typeof residual === "object" && "repair" in residual) {
        const repair = (residual                        ).repair;
        if (repair && typeof repair === "object") {
          this.proposer.learnedRepair = repair                                ;
        }
      }
    }
  }

  snapshotState()                          {
    return {
      acceptedCount: this.acceptedCount,
      rejectedCount: this.rejectedCount,
      learnedRepair: this.proposer.learnedRepair ? { ...this.proposer.learnedRepair } : null,
      proposerId: this.proposer.proposerId,
      updateCount: this.updateCount,
    };
  }
}

                                                        
                  
                       
  

class RrlmScalarTraceProposer {
  proposerId = "rrlm_macro_proposer";
  proposerVersion = "1.0";
  target        ;
  initialGuess        ;
  rrlm = new RrlmMacroProposer             ();
  macros                           ;
  lastSnapshot                           = null;
  lastProposalCertificate                                 = null;
  lastTransportCertificate                                  = null;
  lastSelectedMacro                            = null;

  constructor(target        , initialGuess = 0) {
    this.target = target;
    this.initialGuess = initialGuess;
    this.macros = [
      {
        macroId: "set0",
        steps: [{ op: "set", value: initialGuess }],
        context: "scalar-world",
        modelVersion: "rrlm.scalar.world.v1",
      },
      {
        macroId: "set0-add-target",
        steps: [
          { op: "set", value: initialGuess },
          { op: "add", value: target - initialGuess },
        ],
        context: "scalar-world",
        modelVersion: "rrlm.scalar.world.v1",
      },
    ];
  }

  async propose(_state                    , _budget                         )                         {
    const snapshot = await this.rrlm.snapshot();
    const ranking = this.rrlm.propose("scalar-world", this.macros);
    const proposalCertificate = await buildRrlmProposalCertificate(snapshot, ranking);
    const transportCertificate = await buildRrlmTransportCertificate(proposalCertificate);
    const selected = ranking.rankedMacros[0];
    this.lastSnapshot = snapshot;
    this.lastProposalCertificate = proposalCertificate;
    this.lastTransportCertificate = transportCertificate;
    this.lastSelectedMacro = selected;
    return makeTrace({
      branchId: `rrlm-world-${selected.macroId}`,
      actions: selected.steps,
      seeds: ["rrlm-world", selected.macroId, proposalCertificate.certificateHash],
      modelVersion: this.proposerVersion,
    });
  }
}

class RrlmScalarProgramProjector {
  projectorId = "rrlm_scalar_program_projector";
  projectorVersion = "1.0";
  target        ;
  proposer                         ;

  constructor(target        , proposer                         ) {
    this.target = target;
    this.proposer = proposer;
  }

  project(_state                    , trace               )                                           {
    const selected = this.proposer.lastSelectedMacro;
    const snapshot = this.proposer.lastSnapshot;
    const proposalCertificate = this.proposer.lastProposalCertificate;
    const transportCertificate = this.proposer.lastTransportCertificate;
    if (!selected || !snapshot || !proposalCertificate || !transportCertificate) {
      throw new Error("RRLM scalar projector requires a preceding RRLM proposal");
    }
    const candidate = makeScalarCandidate("scalar-world", this.target, trace.actions                 );
    return {
      payload: {
        ...candidate.payload,
        macroId: selected.macroId,
        macro: selected.steps.map((step) => ({ ...step })),
      },
      typeName: candidate.typeName,
      schemaVersion: candidate.schemaVersion,
      hashes: {
        rrlmSnapshotHash: snapshot.snapshotHash,
        rrlmProposalCertificateHash: proposalCertificate.certificateHash,
        rrlmTransportCertificateHash: transportCertificate.certificateHash,
      },
    };
  }
}

class RrlmWorldReceiptLearner {
  learnerId = "rrlm_world_receipt_learner";
  learnerVersion = "1.0";
  proposer                         ;
  updateCount = 0;

  constructor(proposer                         ) {
    this.proposer = proposer;
  }

  update(receipt         )       {
    this.proposer.rrlm.update(receipt);
    this.updateCount += 1;
  }

  async snapshotState()                                   {
    const snapshot = await this.proposer.rrlm.snapshot();
    return {
      rrlmSnapshotHash: snapshot.snapshotHash,
      rows: snapshot.rows.map((row) => ({ ...row })),
      sourceReceiptHashes: [...snapshot.sourceReceiptHashes],
      updateCount: this.updateCount,
    };
  }
}

export async function runWorldLoopBenchmark()                           {
  const target = 5;
  const { seedState, engine, runtime, learner } = buildWorldLoopRuntime(target, 0);

  const first = await runtime.step(seedState);
  const second = await runtime.step(first.state);
  const other = buildWorldLoopRuntime(target, 1);
  await other.runtime.step(other.seedState);
  const otherSecond = await other.runtime.step(other.seedState);
  const partialRight = await forkWorldLoopFromSnapshot(first, target, 2);
  const certificates = [first.certificate, second.certificate];
  const receipts = [first.receipt, second.receipt];
  const learnerSnapshots = [first.learnerSnapshot, second.learnerSnapshot];
  const preLearnerSnapshots = [first.preLearnerSnapshot, second.preLearnerSnapshot];
  const learnerUpdateCertificates = [first.learnerUpdateCertificate, second.learnerUpdateCertificate];
  const learnerDeltaCertificates = [first.learnerDeltaCertificate, second.learnerDeltaCertificate];
  const learnerLineage = await buildWorldLearnerLineageCertificate(
    first.preLearnerSnapshot,
    second.learnerSnapshot,
    learnerUpdateCertificates,
  );
  const learnerMerge = await mergeWorldLearnerSnapshots(second.learnerSnapshot, otherSecond.learnerSnapshot);
  const learnerPartialMerge = await mergeWorldLearnerSnapshots(
    second.learnerSnapshot,
    partialRight.learnerSnapshot,
    {
      baseSnapshot: first.learnerSnapshot,
      leftDeltaCertificates: [second.learnerDeltaCertificate],
      rightDeltaCertificates: [partialRight.learnerDeltaCertificate],
    },
  );
  const tamperedMergeCertificate = { ...learnerMerge.certificate, mergedUpdateCount: 3, certificateHash: "" };
  tamperedMergeCertificate.certificateHash = await worldLearnerMergeCertificateHash(tamperedMergeCertificate);
  const conflictingSnapshot = {
    ...otherSecond.learnerSnapshot,
    learnerState: {
      ...(otherSecond.learnerSnapshot.learnerState                           ),
      learnedRepair: { op: "add", value: target + 1 },
    },
    learnerStateHash: "",
    snapshotHash: "",
  };
  conflictingSnapshot.learnerStateHash = await worldLearnerStateHash(conflictingSnapshot.learnerState);
  conflictingSnapshot.snapshotHash = await worldLearnerSnapshotHash(conflictingSnapshot);
  const tampered = { ...second.certificate, committed: false, certificateHash: "" };
  tampered.certificateHash = await worldModelStepCertificateHash(tampered);
  const tamperedSnapshot = { ...second.learnerSnapshot, updateCount: 99, snapshotHash: "" };
  const tamperedUpdateCertificate = { ...second.learnerUpdateCertificate, postUpdateCount: 4, certificateHash: "" };
  tamperedUpdateCertificate.certificateHash = await worldLearnerUpdateCertificateHash(tamperedUpdateCertificate);
  const tamperedDeltaCertificate = { ...second.learnerDeltaCertificate, deltaOpCount: 9, certificateHash: "" };
  tamperedDeltaCertificate.certificateHash = await worldLearnerDeltaCertificateHash(tamperedDeltaCertificate);
  const tamperedLineageCertificate = { ...learnerLineage, appliedUpdateCount: 3, certificateHash: "" };
  tamperedLineageCertificate.certificateHash = await worldLearnerLineageCertificateHash(tamperedLineageCertificate);
  const rrlmWorld = await runRrlmWorldLoop(target);
  const tamperedRrlmWorldProposal = {
    ...rrlmWorld.secondProposalCertificate,
    scores: [
      rrlmWorld.secondProposalCertificate.scores[0] + 1,
      ...rrlmWorld.secondProposalCertificate.scores.slice(1),
    ],
    certificateHash: "",
  };
  tamperedRrlmWorldProposal.certificateHash = await rrlmProposalCertificateHash(tamperedRrlmWorldProposal);
  const replayed = await engine.replayAudit(seedState);
  const rolledBack = await engine.rollbackAudit(seedState);

  return {
    schemaVersion: first.certificate.schemaVersion,
    stepCount: 2,
    firstCommitted: first.committed,
    secondCommitted: second.committed,
    firstDecision: first.reason,
    secondDecision: second.reason,
    learnerUpdateCount: learner.updateCount,
    acceptedCount: learner.acceptedCount,
    rejectedCount: learner.rejectedCount,
    certificateValidCount: (await Promise.all(certificates.map((certificate) => validateWorldModelStepCertificate(certificate)))).filter(Boolean).length,
    auditValidCount: (await Promise.all(receipts.map((receipt, idx) => auditWorldModelStep(receipt, certificates[idx], {
      learnerSnapshot: learnerSnapshots[idx],
      learnerUpdateCertificate: learnerUpdateCertificates[idx],
    })))).filter(Boolean).length,
    proposerImprovedFromResidual: (second.candidate.payload.program.at(-1)?.op === "add"
      && second.candidate.payload.program.at(-1)?.value === target),
    hardVerifierOwnedCommit: second.receipt.hardResult.result === "accept"
      && second.receipt.committed
      && second.receipt.commitDecision === "commit",
    learnerSnapshotValidCount: (await Promise.all(learnerSnapshots.map((snapshot) => validateWorldLearnerSnapshot(snapshot)))).filter(Boolean).length,
    stepCertificateBindsLearnerState: certificates.every((certificate, idx) => (
      certificate.learnerStateHash === learnerSnapshots[idx].learnerStateHash
      && certificate.learnerSnapshotHash === learnerSnapshots[idx].snapshotHash
      && certificate.learnerUpdateCount === learnerSnapshots[idx].updateCount
    )),
    learnerUpdateCertificateValidCount: (await Promise.all(learnerUpdateCertificates.map((certificate) => validateWorldLearnerUpdateCertificate(certificate)))).filter(Boolean).length,
    learnerUpdateAuditValidCount: (await Promise.all(receipts.map((receipt, idx) => auditWorldLearnerUpdate(
      receipt,
      preLearnerSnapshots[idx],
      learnerSnapshots[idx],
      learnerUpdateCertificates[idx],
    )))).filter(Boolean).length,
    stepCertificateBindsLearnerUpdate: certificates.every((certificate, idx) => (
      certificate.learnerUpdateCertificateHash === learnerUpdateCertificates[idx].certificateHash
    )),
    learnerUpdateTamperDetected: !await validateWorldLearnerUpdateCertificate(tamperedUpdateCertificate),
    learnerDeltaCertificateValidCount: (await Promise.all(learnerDeltaCertificates.map((certificate) => validateWorldLearnerDeltaCertificate(certificate)))).filter(Boolean).length,
    learnerDeltaAuditValidCount: (await Promise.all(learnerDeltaCertificates.map((deltaCertificate, idx) => auditWorldLearnerDelta(
      preLearnerSnapshots[idx],
      learnerSnapshots[idx],
      learnerUpdateCertificates[idx],
      deltaCertificate,
    )))).filter(Boolean).length,
    learnerDeltaBindsUpdates: learnerDeltaCertificates.every((deltaCertificate, idx) => (
      deltaCertificate.updateCertificateHash === learnerUpdateCertificates[idx].certificateHash
    )),
    learnerDeltaTamperDetected: !await validateWorldLearnerDeltaCertificate(tamperedDeltaCertificate),
    learnerLineageCertificateValid: await validateWorldLearnerLineageCertificate(learnerLineage),
    learnerLineageAuditValid: await auditWorldLearnerLineage(
      first.preLearnerSnapshot,
      second.learnerSnapshot,
      learnerUpdateCertificates,
      learnerLineage,
    ),
    learnerLineageBindsUpdates: sameStringArray(
      learnerLineage.updateCertificateHashes,
      learnerUpdateCertificates.map((certificate) => certificate.certificateHash),
    ),
    learnerLineageTamperDetected: !await validateWorldLearnerLineageCertificate(tamperedLineageCertificate),
    learnerMergeCertificateValid: await validateWorldLearnerMergeCertificate(learnerMerge.certificate),
    learnerMergeAuditValid: await auditWorldLearnerMerge(
      second.learnerSnapshot,
      otherSecond.learnerSnapshot,
      learnerMerge.mergedSnapshot,
      learnerMerge.certificate,
    ),
    learnerMergeDisjointReceipts: !hasOverlap(second.learnerSnapshot.sourceReceiptHashes, otherSecond.learnerSnapshot.sourceReceiptHashes)
      && learnerMerge.mergedSnapshot.updateCount === 4,
    learnerMergePartialOverlapValid: await validateWorldLearnerMergeCertificate(learnerPartialMerge.certificate),
    learnerMergePartialOverlapAuditValid: await auditWorldLearnerMerge(
      second.learnerSnapshot,
      partialRight.learnerSnapshot,
      learnerPartialMerge.mergedSnapshot,
      learnerPartialMerge.certificate,
      {
        baseSnapshot: first.learnerSnapshot,
        leftDeltaCertificates: [second.learnerDeltaCertificate],
        rightDeltaCertificates: [partialRight.learnerDeltaCertificate],
      },
    ),
    learnerMergePartialOverlapCountsSharedOnce: learnerPartialMerge.certificate.mergeBasis === "delta_common_prefix"
      && learnerPartialMerge.certificate.sharedReceiptCount === 1
      && learnerPartialMerge.certificate.commonPrefixReceiptCount === 1
      && learnerPartialMerge.mergedSnapshot.updateCount === 3
      && (learnerPartialMerge.mergedSnapshot.learnerState                           ).acceptedCount === 2
      && (learnerPartialMerge.mergedSnapshot.learnerState                           ).rejectedCount === 1
      && (learnerPartialMerge.mergedSnapshot.learnerState                           ).updateCount === 3,
    learnerMergePartialOverlapRequiresDeltas: await learnerMergeConflictDetected(second.learnerSnapshot, partialRight.learnerSnapshot),
    learnerMergeTamperDetected: !await validateWorldLearnerMergeCertificate(tamperedMergeCertificate),
    learnerMergeConflictDetected: await learnerMergeConflictDetected(second.learnerSnapshot, conflictingSnapshot),
    rrlmWorldFirstCommitted: rrlmWorld.first.committed,
    rrlmWorldSecondCommitted: rrlmWorld.second.committed,
    rrlmWorldSelectedRepairMacro: rrlmWorld.secondSelectedMacroId === "set0-add-target",
    rrlmWorldProposalCertificateValid: await validateRrlmMacroSnapshot(rrlmWorld.secondSnapshot)
      && await validateRrlmProposalCertificate(rrlmWorld.secondProposalCertificate, rrlmWorld.secondSnapshot),
    rrlmWorldTransportCertificateValid: await validateRrlmTransportCertificate(
      rrlmWorld.secondTransportCertificate,
      rrlmWorld.secondProposalCertificate,
    ),
    rrlmWorldArtifactsBoundToReceipts: rrlmWorld.first.candidate.hashes.rrlmSnapshotHash === rrlmWorld.firstSnapshot.snapshotHash
      && rrlmWorld.first.candidate.hashes.rrlmProposalCertificateHash === rrlmWorld.firstProposalCertificate.certificateHash
      && rrlmWorld.first.candidate.hashes.rrlmTransportCertificateHash === rrlmWorld.firstTransportCertificate.certificateHash
      && rrlmWorld.first.receipt.artifactHashes.rrlmProposalCertificateHash === rrlmWorld.firstProposalCertificate.certificateHash
      && rrlmWorld.second.candidate.hashes.rrlmSnapshotHash === rrlmWorld.secondSnapshot.snapshotHash
      && rrlmWorld.second.candidate.hashes.rrlmProposalCertificateHash === rrlmWorld.secondProposalCertificate.certificateHash
      && rrlmWorld.second.candidate.hashes.rrlmTransportCertificateHash === rrlmWorld.secondTransportCertificate.certificateHash
      && rrlmWorld.second.receipt.artifactHashes.rrlmTransportCertificateHash === rrlmWorld.secondTransportCertificate.certificateHash
      && rrlmWorld.second.certificate.typedCandidateHash === rrlmWorld.second.receipt.typedCandidateHash,
    rrlmWorldRejectedMacroPenalized: rrlmWorld.firstSelectedMacroId === "set0"
      && rrlmWorld.first.receipt.hardResult.result === "reject"
      && rrlmWorld.secondProposalCertificate.rejectedPrefixCounts[1] === 1,
    rrlmWorldTamperDetected: !await validateRrlmProposalCertificate(
      tamperedRrlmWorldProposal,
      rrlmWorld.secondSnapshot,
    ),
    worldProgramManifestValid: await validateWorldProgramManifest(rrlmWorld.programManifest),
    worldProgramCertificateValid: await validateWorldProgramCertificate(
      rrlmWorld.programCertificate,
      rrlmWorld.programManifest,
    ),
    worldProgramAuditValid: await auditWorldProgramCertificate(
      rrlmWorld.programManifest,
      [rrlmWorld.first, rrlmWorld.second],
      rrlmWorld.programCertificate,
      {
        ledgerHead: rrlmWorld.ledgerHead,
        invalidCommitCount: rrlmWorld.invalidCommitCount,
        replayRollbackRate: rrlmWorld.replayRollbackRate,
      },
    ),
    worldProgramBindsRrlmArtifacts: rrlmWorld.programCertificate.artifactHashGroups.rrlmSnapshotHash?.[0] === rrlmWorld.firstSnapshot.snapshotHash
      && rrlmWorld.programCertificate.artifactHashGroups.rrlmSnapshotHash?.[1] === rrlmWorld.secondSnapshot.snapshotHash
      && rrlmWorld.programCertificate.artifactHashGroups.rrlmProposalCertificateHash?.[0] === rrlmWorld.firstProposalCertificate.certificateHash
      && rrlmWorld.programCertificate.artifactHashGroups.rrlmProposalCertificateHash?.[1] === rrlmWorld.secondProposalCertificate.certificateHash
      && rrlmWorld.programCertificate.artifactHashGroups.rrlmTransportCertificateHash?.[0] === rrlmWorld.firstTransportCertificate.certificateHash
      && rrlmWorld.programCertificate.artifactHashGroups.rrlmTransportCertificateHash?.[1] === rrlmWorld.secondTransportCertificate.certificateHash,
    worldProgramTamperDetected: !await validateWorldProgramCertificate(
      await tamperWorldProgramCertificate(rrlmWorld.programCertificate),
      rrlmWorld.programManifest,
    ),
    worldProgramAdmissionPolicyValid: await validateWorldProgramAdmissionPolicy(rrlmWorld.admissionPolicy),
    worldProgramAdmissionCertificateValid: await validateWorldProgramAdmissionCertificate(
      rrlmWorld.admissionCertificate,
      rrlmWorld.admissionPolicy,
      rrlmWorld.programManifest,
      rrlmWorld.programCertificate,
    ),
    worldProgramAdmissionAuditValid: await auditWorldProgramAdmission(
      rrlmWorld.admissionPolicy,
      rrlmWorld.programManifest,
      rrlmWorld.programCertificate,
      rrlmWorld.admissionCertificate,
    ),
    worldProgramAdmitted: rrlmWorld.admissionCertificate.admitted,
    worldProgramAdmissionRejectsUnmetRequirements: await validateWorldProgramAdmissionCertificate(
      rrlmWorld.rejectedAdmissionCertificate,
      rrlmWorld.rejectedAdmissionPolicy,
      rrlmWorld.programManifest,
      rrlmWorld.programCertificate,
    )
      && !rrlmWorld.rejectedAdmissionCertificate.admitted
      && JSON.stringify(rrlmWorld.rejectedAdmissionCertificate.failedRequirements) === JSON.stringify(["required_artifacts_present"]),
    worldProgramAdmissionTamperDetected: !await validateWorldProgramAdmissionCertificate(
      await tamperWorldProgramAdmissionCertificate(rrlmWorld.admissionCertificate),
      rrlmWorld.admissionPolicy,
      rrlmWorld.programManifest,
      rrlmWorld.programCertificate,
    ),
    worldProgramEvidenceBundleValid: await validateWorldProgramEvidenceBundle(rrlmWorld.evidenceBundle),
    worldProgramEvidenceBundleAuditValid: await auditWorldProgramEvidenceBundle(
      rrlmWorld.programManifest,
      rrlmWorld.programCertificate,
      rrlmWorld.admissionPolicy,
      rrlmWorld.admissionCertificate,
      rrlmWorld.evidenceBundle,
    ),
    worldProgramBundleVerificationCertificateValid: await validateWorldProgramBundleVerificationCertificate(
      rrlmWorld.bundleVerificationCertificate,
      rrlmWorld.evidenceBundle,
    ),
    worldProgramBundleVerified: rrlmWorld.bundleVerificationCertificate.verified,
    worldProgramBundleTamperDetected: !await validateWorldProgramEvidenceBundle(
      await tamperWorldProgramEvidenceBundle(rrlmWorld.evidenceBundle),
    )
      && !await validateWorldProgramBundleVerificationCertificate(
        await tamperWorldProgramBundleVerificationCertificate(rrlmWorld.bundleVerificationCertificate),
        rrlmWorld.evidenceBundle,
      )
      && !await auditWorldProgramBundleVerification(
        await tamperWorldProgramEvidenceBundle(rrlmWorld.evidenceBundle),
        rrlmWorld.bundleVerificationCertificate,
      ),
    worldProgramReplayPackageValid: await validateWorldProgramReplayPackage(rrlmWorld.replayPackage),
    worldProgramReplayPackageAuditValid: await auditWorldProgramReplayPackage(
      rrlmWorld.evidenceBundle,
      [rrlmWorld.first, rrlmWorld.second],
      rrlmWorld.replayPackage,
    ),
    worldProgramReplayVerificationCertificateValid: await validateWorldProgramReplayVerificationCertificate(
      rrlmWorld.replayVerificationCertificate,
      rrlmWorld.replayPackage,
    ),
    worldProgramReplayVerified: rrlmWorld.replayVerificationCertificate.replayVerified,
    worldProgramReplayTamperDetected: !await validateWorldProgramReplayPackage(
      await tamperWorldProgramReplayPackage(rrlmWorld.replayPackage),
    )
      && !await validateWorldProgramReplayVerificationCertificate(
        await tamperWorldProgramReplayVerificationCertificate(rrlmWorld.replayVerificationCertificate),
        rrlmWorld.replayPackage,
      )
      && !await auditWorldProgramReplayVerification(
        await tamperWorldProgramReplayPackage(rrlmWorld.replayPackage),
        rrlmWorld.replayVerificationCertificate,
      ),
    tamperDetected: !await validateWorldModelStepCertificate(tampered),
    learnerSnapshotTamperDetected: !await validateWorldLearnerSnapshot(tamperedSnapshot),
    invalidCommitCount: engine.invalidCommitCount + rrlmWorld.invalidCommitCount,
    ledgerAudit: await engine.ledger.audit() && rrlmWorld.ledgerAudit,
    replayRollbackRate: await stableHash(replayed) === await stableHash(second.state)
      && await stableHash(rolledBack) === await stableHash(seedState)
      && rrlmWorld.replayRollbackRate === 1
      ? 1
      : 0,
  };
}

async function runRrlmWorldLoop(target        )           
                                                                            
                                                                             
                                   
                                    
                                                    
                                                     
                                                      
                                                       
                               
                                
                                        
                                              
                                               
                                                         
                                             
                                                                           
                                           
                                                                           
                                                       
                                                                 
                     
                             
                       
                             
   {
  const proposer = new RrlmScalarTraceProposer(target, 0);
  const projector = new RrlmScalarProgramProjector(target, proposer);
  const learner = new RrlmWorldReceiptLearner(proposer);
  const seedState                     = { episode: 100, target, solved: false };
  const engine = new TransactionEngine                                              (
    new ScalarProgramAdapter(),
    new Ledger(),
  );
  const runtime = new TransactionalWorldModelRuntime(
    engine,
    proposer,
    projector,
    learner,
  );
  const first = await runtime.step(seedState);
  const firstSnapshot = proposer.lastSnapshot;
  const firstProposalCertificate = proposer.lastProposalCertificate;
  const firstTransportCertificate = proposer.lastTransportCertificate;
  const firstSelectedMacro = proposer.lastSelectedMacro;
  const second = await runtime.step(first.state);
  const secondSnapshot = proposer.lastSnapshot;
  const secondProposalCertificate = proposer.lastProposalCertificate;
  const secondTransportCertificate = proposer.lastTransportCertificate;
  const secondSelectedMacro = proposer.lastSelectedMacro;
  if (
    !firstSnapshot
    || !firstProposalCertificate
    || !firstTransportCertificate
    || !firstSelectedMacro
    || !secondSnapshot
    || !secondProposalCertificate
    || !secondTransportCertificate
    || !secondSelectedMacro
  ) {
    throw new Error("RRLM world loop did not emit proposal certificates");
  }
  const replayRollbackRate = await stableHash(await engine.replayAudit(seedState)) === await stableHash(second.state)
    && await stableHash(await engine.rollbackAudit(seedState)) === await stableHash(seedState)
    ? 1
    : 0;
  const programManifest = await buildWorldProgramManifest({
    programId: "rrlm_scalar_world_program",
    programVersion: "1.0",
    proposer,
    projector,
    learner,
    verifierId: engine.adapter.verifierId,
    verifierVersion: engine.adapter.verifierVersion,
    inputSchema: "scalar.program.state.v1",
    candidateSchema: "scalar.program.v1",
    externalParameters: { target, initialGuess: proposer.initialGuess },
    resolvedDependencies: [
      "trwm.rrlm_macro_snapshot.v1",
      "trwm.rrlm_proposal_certificate.v1",
      "trwm.rrlm_transport_certificate.v1",
    ],
  });
  const programCertificate = await buildWorldProgramCertificate(
    programManifest,
    [first, second],
    {
      ledgerHead: engine.ledger.head,
      invalidCommitCount: engine.invalidCommitCount,
      replayRollbackRate,
    },
  );
  const admissionPolicy = await buildWorldProgramAdmissionPolicy({
    policyId: "rrlm_scalar_world_program_policy",
    policyVersion: "1.0",
    allowedProgramIds: ["rrlm_scalar_world_program"],
    allowedProgramVersions: ["1.0"],
    allowedProposerIds: [proposer.proposerId],
    allowedProjectorIds: [projector.projectorId],
    allowedLearnerIds: [learner.learnerId],
    allowedVerifierIds: [engine.adapter.verifierId],
    allowedInputSchemas: ["scalar.program.state.v1"],
    allowedCandidateSchemas: ["scalar.program.v1"],
    requiredDependencies: [
      "trwm.rrlm_macro_snapshot.v1",
      "trwm.rrlm_proposal_certificate.v1",
      "trwm.rrlm_transport_certificate.v1",
    ],
    requiredArtifactKeys: [
      "rrlmSnapshotHash",
      "rrlmProposalCertificateHash",
      "rrlmTransportCertificateHash",
    ],
    minStepCount: 2,
    minCommittedCount: 1,
    minRejectedCount: 1,
    maxInvalidCommitCount: 0,
    minReplayRollbackRate: 1,
  });
  const admissionCertificate = await buildWorldProgramAdmissionCertificate(admissionPolicy, programManifest, programCertificate);
  const evidenceBundle = await buildWorldProgramEvidenceBundle(
    programManifest,
    programCertificate,
    admissionPolicy,
    admissionCertificate,
    { bundleId: "rrlm_scalar_world_program_evidence_bundle" },
  );
  const bundleVerificationCertificate = await buildWorldProgramBundleVerificationCertificate(evidenceBundle);
  const replayPackage = await buildWorldProgramReplayPackage(
    evidenceBundle,
    [first, second],
    { packageId: "rrlm_scalar_world_program_replay_package" },
  );
  const replayVerificationCertificate = await buildWorldProgramReplayVerificationCertificate(replayPackage);
  const rejectedAdmissionPolicy = await buildWorldProgramAdmissionPolicy({
    policyId: "rrlm_scalar_world_program_missing_artifact_probe",
    policyVersion: "1.0",
    allowedProgramIds: ["rrlm_scalar_world_program"],
    requiredArtifactKeys: ["missingRrlmArtifactHash"],
  });
  const rejectedAdmissionCertificate = await buildWorldProgramAdmissionCertificate(
    rejectedAdmissionPolicy,
    programManifest,
    programCertificate,
  );
  return {
    first,
    second,
    firstSnapshot,
    secondSnapshot,
    firstProposalCertificate,
    secondProposalCertificate,
    firstTransportCertificate,
    secondTransportCertificate,
    firstSelectedMacroId: firstSelectedMacro.macroId,
    secondSelectedMacroId: secondSelectedMacro.macroId,
    programManifest,
    programCertificate,
    admissionPolicy,
    admissionCertificate,
    evidenceBundle,
    bundleVerificationCertificate,
    replayPackage,
    replayVerificationCertificate,
    rejectedAdmissionPolicy,
    rejectedAdmissionCertificate,
    ledgerHead: engine.ledger.head,
    invalidCommitCount: engine.invalidCommitCount,
    ledgerAudit: await engine.ledger.audit(),
    replayRollbackRate,
  };
}

function buildWorldLoopRuntime(target        , episode        )   
                                
                                                                      
                                                                                    
                                 
  {
  const seedState                     = { episode, target, solved: false };
  const proposer = new ResidualRepairProposer(target, 0);
  const projector = new ScalarProgramProjector(target);
  const learner = new ResidualRepairLearner(proposer);
  const engine = new TransactionEngine(new ScalarProgramAdapter(), new Ledger());
  const runtime = new TransactionalWorldModelRuntime(engine, proposer, projector, learner);
  return { seedState, engine, runtime, learner };
}

async function forkWorldLoopFromSnapshot(
  baseStep                                                                                                       ,
  target        ,
  episode        ,
)                                                                                                                 {
  const proposer = new ResidualRepairProposer(target, 0);
  const baseState = baseStep.learnerSnapshot.learnerState                           ;
  proposer.learnedRepair = baseState.learnedRepair
    ? { ...(baseState.learnedRepair                                ) }
    : null;
  const learner = new ResidualRepairLearner(proposer);
  learner.acceptedCount = baseState.acceptedCount          ;
  learner.rejectedCount = baseState.rejectedCount          ;
  learner.updateCount = baseState.updateCount          ;
  const runtime = new TransactionalWorldModelRuntime(
    new TransactionEngine(new ScalarProgramAdapter(), new Ledger()),
    proposer,
    new ScalarProgramProjector(target),
    learner,
  );
  runtime.learnerUpdateCount = baseStep.learnerSnapshot.updateCount;
  runtime.learnerReceiptHashes = [...baseStep.learnerSnapshot.sourceReceiptHashes];
  return runtime.step({ episode, target, solved: false });
}

function hasOverlap(left          , right          )          {
  const rightSet = new Set(right);
  return left.some((value) => rightSet.has(value));
}

function sameStringArray(left          , right          )          {
  return left.length === right.length && left.every((value, idx) => value === right[idx]);
}

async function learnerMergeConflictDetected(
  left                      ,
  right                      ,
)                   {
  try {
    await mergeWorldLearnerSnapshots(left, right);
  } catch (_error) {
    return true;
  }
  return false;
}
