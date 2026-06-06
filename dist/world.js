import { stableHash } from "./canonical.js";
import {
                     
               
                         
                      
  receiptStaticValid,
} from "./core.js";

export const WORLD_MODEL_STEP_CERTIFICATE_SCHEMA = "trwm.world_model_step_certificate.v1";
export const WORLD_LEARNER_SNAPSHOT_SCHEMA = "trwm.world_learner_snapshot.v1";
export const WORLD_LEARNER_UPDATE_CERTIFICATE_SCHEMA = "trwm.world_learner_update_certificate.v1";
export const WORLD_LEARNER_DELTA_CERTIFICATE_SCHEMA = "trwm.world_learner_delta_certificate.v1";
export const WORLD_LEARNER_LINEAGE_CERTIFICATE_SCHEMA = "trwm.world_learner_lineage_certificate.v1";
export const WORLD_LEARNER_MERGE_CERTIFICATE_SCHEMA = "trwm.world_learner_merge_certificate.v1";
export const WORLD_LEARNER_MERGE_STRATEGY = "trace_delta_counter_join.v2";
const WORLD_LEARNER_MERGE_BASIS = new Set([
  "duplicate",
  "left_superset",
  "right_superset",
  "disjoint",
  "delta_common_prefix",
]);

                                                 
                      
                           
                                                                                                 
 

                                                                     
                       
                            
                                                                                                          
 

                                 
                     
                          
                                                 
                            
                       
 

                                       
                                                      
                    
                         
                      
                                
                        
                           
                       
 

                                               
                                                               
                    
                         
                                                     
                     
                           
                            
                             
                                  
                          
                           
                            
                             
                                   
                        
                         
                                
                                       
                                        
                          
                          
 

                                          
                                       
                                            
 

                                        
                       
                 
                  
 

                                               
                                                               
                    
                         
                                
                            
                          
                           
                              
                               
                       
                                        
                           
                          
 

                                                 
                                                                 
                    
                         
                              
                            
                             
                           
                                 
                             
                                
                                    
                      
                          
 

                                                
                                                                
                    
                         
                            
                        
                     
                         
                     
                         
                         
                          
                                 
                              
                               
                              
                          
 

                                            
                                                            
                     
                          
                      
                           
                    
                         
                     
                          
                            
                             
                      
                        
                       
                               
                                   
                     
                         
                     
                             
                           
                              
                                       
                     
                          
 

                                                                           
               
                     
                   
                                         
                       
                                     
                                           
                                        
                                                          
                                                        
                             
                 
 

export class TransactionalWorldModelRuntime                 {
  engine                                   ;
  proposer                      ;
  projector                                ;
  learner                 ;
  learnerUpdateCount = 0;
  learnerReceiptHashes           = [];

  constructor(
    engine                                   ,
    proposer                      ,
    projector                                ,
    learner                 ,
  ) {
    this.engine = engine;
    this.proposer = proposer;
    this.projector = projector;
    this.learner = learner;
  }

  async step(
    state       ,
    options                                                                            = {},
  )                                                {
    const trace = await this.proposer.propose(state, options.budget ?? {});
    const candidate = await this.projector.project(state, trace);
    const outcome = await this.engine.transact(state, trace, candidate, { softScores: options.softScores });
    const preLearnerSnapshot = await buildWorldLearnerSnapshot(this.learner, {
      updateCount: this.learnerUpdateCount,
      sourceReceiptHashes: this.learnerReceiptHashes,
    });
    const updateApplied = Boolean(this.learner);
    if (this.learner) {
      await this.learner.update(outcome.receipt);
      this.learnerUpdateCount += 1;
      this.learnerReceiptHashes.push(outcome.receipt.receiptHash);
    }
    const learnerSnapshot = await buildWorldLearnerSnapshot(this.learner, {
      updateCount: this.learnerUpdateCount,
      sourceReceiptHashes: this.learnerReceiptHashes,
    });
    const learnerUpdateCertificate = await buildWorldLearnerUpdateCertificate(outcome.receipt, {
      preSnapshot: preLearnerSnapshot,
      postSnapshot: learnerSnapshot,
      updateApplied,
    });
    const learnerDeltaCertificate = await buildWorldLearnerDeltaCertificate(
      preLearnerSnapshot,
      learnerSnapshot,
      learnerUpdateCertificate,
    );
    const certificate = await buildWorldModelStepCertificate(outcome.receipt, {
      proposerId: componentId(this.proposer, "proposer"),
      proposerVersion: componentVersion(this.proposer),
      projectorId: componentId(this.projector, "projector"),
      projectorVersion: componentVersion(this.projector),
      learnerId: learnerSnapshot.learnerId,
      learnerVersion: learnerSnapshot.learnerVersion,
      learnerUpdateCount: this.learnerUpdateCount,
      learnerStateHash: learnerSnapshot.learnerStateHash,
      learnerSnapshotHash: learnerSnapshot.snapshotHash,
      learnerUpdateCertificateHash: learnerUpdateCertificate.certificateHash,
      ledgerHead: this.engine.ledger.head,
    });
    return {
      state: outcome.state,
      committed: outcome.committed,
      receipt: outcome.receipt,
      certificate,
      trace,
      candidate,
      preLearnerSnapshot,
      learnerSnapshot,
      learnerUpdateCertificate,
      learnerDeltaCertificate,
      learnerUpdateCount: this.learnerUpdateCount,
      reason: outcome.reason,
    };
  }
}

export async function buildWorldLearnerSnapshot(
  learner                            ,
  params   
                        
                                   
   ,
)                                {
  const learnerState = await learnerStateSnapshot(learner);
  const snapshot                       = {
    schemaVersion: WORLD_LEARNER_SNAPSHOT_SCHEMA,
    learnerId: learner ? componentId(learner, "learner") : "none",
    learnerVersion: learner ? componentVersion(learner) : "0",
    updateCount: params.updateCount,
    sourceReceiptHashes: [...(params.sourceReceiptHashes ?? [])],
    learnerState,
    learnerStateHash: await worldLearnerStateHash(learnerState),
    snapshotHash: "",
  };
  snapshot.snapshotHash = await worldLearnerSnapshotHash(snapshot);
  return snapshot;
}

export async function buildWorldModelStepCertificate(
  receipt         ,
  params   
                       
                            
                        
                             
                      
                           
                               
                             
                                
                                         
                       
   ,
)                                     {
  const certificate                            = {
    schemaVersion: WORLD_MODEL_STEP_CERTIFICATE_SCHEMA,
    proposerId: params.proposerId,
    proposerVersion: params.proposerVersion,
    projectorId: params.projectorId,
    projectorVersion: params.projectorVersion,
    learnerId: params.learnerId,
    learnerVersion: params.learnerVersion,
    verifierId: receipt.hardResult.verifierId,
    verifierVersion: receipt.hardResult.verifierVersion,
    proposalTraceHash: receipt.proposalTraceHash,
    typedCandidateHash: receipt.typedCandidateHash,
    receiptHash: receipt.receiptHash,
    receiptSchema: receipt.receiptSchema,
    preStateHash: receipt.preStateHash,
    postStateHash: receipt.postStateHash,
    rollbackStateHash: receipt.rollbackStateHash,
    hardResult: receipt.hardResult.result,
    commitDecision: receipt.commitDecision,
    committed: receipt.committed,
    learnerUpdateCount: params.learnerUpdateCount,
    learnerStateHash: params.learnerStateHash,
    learnerSnapshotHash: params.learnerSnapshotHash,
    learnerUpdateCertificateHash: params.learnerUpdateCertificateHash,
    ledgerHead: params.ledgerHead,
    certificateHash: "",
  };
  certificate.certificateHash = await worldModelStepCertificateHash(certificate);
  return certificate;
}

export async function buildWorldLearnerUpdateCertificate(
  receipt         ,
  params   
                                      
                                       
                           
   ,
)                                         {
  const certificate                                = {
    schemaVersion: WORLD_LEARNER_UPDATE_CERTIFICATE_SCHEMA,
    learnerId: params.postSnapshot.learnerId,
    learnerVersion: params.postSnapshot.learnerVersion,
    sourceReceiptHash: receipt.receiptHash,
    receiptSchema: receipt.receiptSchema,
    hardResult: receipt.hardResult.result,
    commitDecision: receipt.commitDecision,
    committed: receipt.committed,
    updateApplied: params.updateApplied,
    preUpdateCount: params.preSnapshot.updateCount,
    postUpdateCount: params.postSnapshot.updateCount,
    preLearnerSnapshotHash: params.preSnapshot.snapshotHash,
    preLearnerStateHash: params.preSnapshot.learnerStateHash,
    postLearnerStateHash: params.postSnapshot.learnerStateHash,
    learnerSnapshotHash: params.postSnapshot.snapshotHash,
    certificateHash: "",
  };
  certificate.certificateHash = await worldLearnerUpdateCertificateHash(certificate);
  return certificate;
}

export async function buildWorldLearnerDeltaCertificate(
  preSnapshot                      ,
  postSnapshot                      ,
  updateCertificate                               ,
)                                        {
  const learnerDelta = learnerStateDelta(preSnapshot.learnerState, postSnapshot.learnerState);
  const certificate                               = {
    schemaVersion: WORLD_LEARNER_DELTA_CERTIFICATE_SCHEMA,
    learnerId: postSnapshot.learnerId,
    learnerVersion: postSnapshot.learnerVersion,
    updateCertificateHash: updateCertificate.certificateHash,
    sourceReceiptHash: updateCertificate.sourceReceiptHash,
    preSnapshotHash: preSnapshot.snapshotHash,
    postSnapshotHash: postSnapshot.snapshotHash,
    preLearnerStateHash: preSnapshot.learnerStateHash,
    postLearnerStateHash: postSnapshot.learnerStateHash,
    deltaOpCount: learnerDelta.length,
    learnerDelta,
    learnerDeltaHash: await worldLearnerDeltaHash(learnerDelta),
    certificateHash: "",
  };
  certificate.certificateHash = await worldLearnerDeltaCertificateHash(certificate);
  return certificate;
}

export async function buildWorldLearnerLineageCertificate(
  initialSnapshot                      ,
  finalSnapshot                      ,
  updateCertificates                                 ,
)                                          {
  const certificate                                 = {
    schemaVersion: WORLD_LEARNER_LINEAGE_CERTIFICATE_SCHEMA,
    learnerId: finalSnapshot.learnerId,
    learnerVersion: finalSnapshot.learnerVersion,
    initialSnapshotHash: initialSnapshot.snapshotHash,
    finalSnapshotHash: finalSnapshot.snapshotHash,
    initialUpdateCount: initialSnapshot.updateCount,
    finalUpdateCount: finalSnapshot.updateCount,
    updateCertificateCount: updateCertificates.length,
    appliedUpdateCount: updateCertificates.filter((certificate) => certificate.updateApplied).length,
    sourceReceiptHashes: updateCertificates.filter((certificate) => certificate.updateApplied).map((certificate) => certificate.sourceReceiptHash),
    updateCertificateHashes: updateCertificates.map((certificate) => certificate.certificateHash),
    lineageHash: "",
    certificateHash: "",
  };
  certificate.lineageHash = await worldLearnerLineageHash(certificate);
  certificate.certificateHash = await worldLearnerLineageCertificateHash(certificate);
  return certificate;
}

export async function auditWorldModelStep(
  receipt         ,
  certificate                           ,
  options                                                                                                                            = {},
)                   {
  try {
    if (!await validateWorldModelStepCertificate(certificate)) {
      return false;
    }
    if (!await receiptStaticValid(receipt)) {
      return false;
    }
    if (options.ledgerHead && certificate.ledgerHead !== options.ledgerHead) {
      return false;
    }
    if (options.learnerSnapshot) {
      if (!await validateWorldLearnerSnapshot(options.learnerSnapshot)) {
        return false;
      }
      if (
        certificate.learnerId !== options.learnerSnapshot.learnerId
        || certificate.learnerVersion !== options.learnerSnapshot.learnerVersion
        || certificate.learnerUpdateCount !== options.learnerSnapshot.updateCount
        || certificate.learnerStateHash !== options.learnerSnapshot.learnerStateHash
        || certificate.learnerSnapshotHash !== options.learnerSnapshot.snapshotHash
      ) {
        return false;
      }
    }
    if (options.learnerUpdateCertificate) {
      if (!await validateWorldLearnerUpdateCertificate(options.learnerUpdateCertificate)) {
        return false;
      }
      if (certificate.learnerUpdateCertificateHash !== options.learnerUpdateCertificate.certificateHash) {
        return false;
      }
    }
    return certificate.verifierId === receipt.hardResult.verifierId
      && certificate.verifierVersion === receipt.hardResult.verifierVersion
      && certificate.proposalTraceHash === receipt.proposalTraceHash
      && certificate.typedCandidateHash === receipt.typedCandidateHash
      && certificate.receiptHash === receipt.receiptHash
      && certificate.receiptSchema === receipt.receiptSchema
      && certificate.preStateHash === receipt.preStateHash
      && certificate.postStateHash === receipt.postStateHash
      && certificate.rollbackStateHash === receipt.rollbackStateHash
      && certificate.hardResult === receipt.hardResult.result
      && certificate.commitDecision === receipt.commitDecision
      && certificate.committed === receipt.committed;
  } catch {
    return false;
  }
}

export async function validateWorldLearnerSnapshot(snapshot                      )                   {
  try {
    if (snapshot.schemaVersion !== WORLD_LEARNER_SNAPSHOT_SCHEMA) {
      return false;
    }
    if (![snapshot.learnerId, snapshot.learnerVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!Number.isInteger(snapshot.updateCount) || snapshot.updateCount < 0) {
      return false;
    }
    if (snapshot.sourceReceiptHashes.length !== snapshot.updateCount) {
      return false;
    }
    if (snapshot.sourceReceiptHashes.length !== new Set(snapshot.sourceReceiptHashes).size) {
      return false;
    }
    if (!snapshot.sourceReceiptHashes.every(isHash)) {
      return false;
    }
    if (!isHash(snapshot.learnerStateHash) || !isHash(snapshot.snapshotHash)) {
      return false;
    }
    if (snapshot.learnerStateHash !== await worldLearnerStateHash(snapshot.learnerState)) {
      return false;
    }
    return snapshot.snapshotHash === await worldLearnerSnapshotHash(snapshot);
  } catch {
    return false;
  }
}

export async function auditWorldLearnerUpdate(
  receipt         ,
  preSnapshot                      ,
  postSnapshot                      ,
  certificate                               ,
)                   {
  try {
    if (!await validateWorldLearnerUpdateCertificate(certificate)) {
      return false;
    }
    if (!await receiptStaticValid(receipt)) {
      return false;
    }
    if (!await validateWorldLearnerSnapshot(preSnapshot) || !await validateWorldLearnerSnapshot(postSnapshot)) {
      return false;
    }
    if (preSnapshot.learnerId !== postSnapshot.learnerId || preSnapshot.learnerVersion !== postSnapshot.learnerVersion) {
      return false;
    }
    if (certificate.learnerId !== postSnapshot.learnerId || certificate.learnerVersion !== postSnapshot.learnerVersion) {
      return false;
    }
    if (certificate.sourceReceiptHash !== receipt.receiptHash || certificate.receiptSchema !== receipt.receiptSchema) {
      return false;
    }
    if (
      certificate.hardResult !== receipt.hardResult.result
      || certificate.commitDecision !== receipt.commitDecision
      || certificate.committed !== receipt.committed
    ) {
      return false;
    }
    if (
      certificate.preUpdateCount !== preSnapshot.updateCount
      || certificate.postUpdateCount !== postSnapshot.updateCount
      || certificate.preLearnerSnapshotHash !== preSnapshot.snapshotHash
      || certificate.preLearnerStateHash !== preSnapshot.learnerStateHash
      || certificate.postLearnerStateHash !== postSnapshot.learnerStateHash
      || certificate.learnerSnapshotHash !== postSnapshot.snapshotHash
    ) {
      return false;
    }
    if (certificate.updateApplied) {
      const expectedReceipts = [...preSnapshot.sourceReceiptHashes, receipt.receiptHash];
      if (!sameStringArray(postSnapshot.sourceReceiptHashes, expectedReceipts)) {
        return false;
      }
      if (postSnapshot.updateCount !== preSnapshot.updateCount + 1) {
        return false;
      }
    } else {
      if (!sameStringArray(postSnapshot.sourceReceiptHashes, preSnapshot.sourceReceiptHashes)) {
        return false;
      }
      if (postSnapshot.updateCount !== preSnapshot.updateCount) {
        return false;
      }
    }
    return true;
  } catch {
    return false;
  }
}

export async function validateWorldLearnerUpdateCertificate(certificate                               )                   {
  try {
    if (certificate.schemaVersion !== WORLD_LEARNER_UPDATE_CERTIFICATE_SCHEMA) {
      return false;
    }
    const requiredStrings = [
      certificate.learnerId,
      certificate.learnerVersion,
      certificate.receiptSchema,
      certificate.commitDecision,
    ];
    if (!requiredStrings.every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!["accept", "reject", "abstain"].includes(certificate.hardResult)) {
      return false;
    }
    if (typeof certificate.committed !== "boolean" || typeof certificate.updateApplied !== "boolean") {
      return false;
    }
    if (certificate.committed && (certificate.hardResult !== "accept" || certificate.commitDecision !== "commit")) {
      return false;
    }
    if (![certificate.preUpdateCount, certificate.postUpdateCount].every((value) => Number.isSafeInteger(value) && value >= 0)) {
      return false;
    }
    if (certificate.updateApplied) {
      if (certificate.postUpdateCount !== certificate.preUpdateCount + 1) {
        return false;
      }
    } else if (certificate.postUpdateCount !== certificate.preUpdateCount) {
      return false;
    }
    const hashes = [
      certificate.sourceReceiptHash,
      certificate.preLearnerSnapshotHash,
      certificate.preLearnerStateHash,
      certificate.postLearnerStateHash,
      certificate.learnerSnapshotHash,
    ];
    if (!hashes.every(isHash)) {
      return false;
    }
    return certificate.certificateHash === await worldLearnerUpdateCertificateHash(certificate);
  } catch {
    return false;
  }
}

export async function auditWorldLearnerDelta(
  preSnapshot                      ,
  postSnapshot                      ,
  updateCertificate                               ,
  deltaCertificate                              ,
)                   {
  try {
    if (!await validateWorldLearnerDeltaCertificate(deltaCertificate)) {
      return false;
    }
    if (!await validateWorldLearnerSnapshot(preSnapshot) || !await validateWorldLearnerSnapshot(postSnapshot)) {
      return false;
    }
    if (!await validateWorldLearnerUpdateCertificate(updateCertificate)) {
      return false;
    }
    if (updateCertificate.preLearnerSnapshotHash !== preSnapshot.snapshotHash) {
      return false;
    }
    if (updateCertificate.learnerSnapshotHash !== postSnapshot.snapshotHash) {
      return false;
    }
    if (deltaCertificate.learnerId !== postSnapshot.learnerId || deltaCertificate.learnerVersion !== postSnapshot.learnerVersion) {
      return false;
    }
    if (deltaCertificate.updateCertificateHash !== updateCertificate.certificateHash) {
      return false;
    }
    if (deltaCertificate.sourceReceiptHash !== updateCertificate.sourceReceiptHash) {
      return false;
    }
    if (
      deltaCertificate.preSnapshotHash !== preSnapshot.snapshotHash
      || deltaCertificate.postSnapshotHash !== postSnapshot.snapshotHash
      || deltaCertificate.preLearnerStateHash !== preSnapshot.learnerStateHash
      || deltaCertificate.postLearnerStateHash !== postSnapshot.learnerStateHash
    ) {
      return false;
    }
    const replayedState = applyWorldLearnerDelta(preSnapshot.learnerState, deltaCertificate.learnerDelta);
    return await worldLearnerStateHash(replayedState) === postSnapshot.learnerStateHash;
  } catch {
    return false;
  }
}

export async function validateWorldLearnerDeltaCertificate(certificate                              )                   {
  try {
    if (certificate.schemaVersion !== WORLD_LEARNER_DELTA_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (![certificate.learnerId, certificate.learnerVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!Number.isSafeInteger(certificate.deltaOpCount) || certificate.deltaOpCount < 0) {
      return false;
    }
    if (certificate.learnerDelta.length !== certificate.deltaOpCount) {
      return false;
    }
    const hashes = [
      certificate.updateCertificateHash,
      certificate.sourceReceiptHash,
      certificate.preSnapshotHash,
      certificate.postSnapshotHash,
      certificate.preLearnerStateHash,
      certificate.postLearnerStateHash,
      certificate.learnerDeltaHash,
    ];
    if (!hashes.every(isHash)) {
      return false;
    }
    if (!validateLearnerDelta(certificate.learnerDelta)) {
      return false;
    }
    if (certificate.learnerDeltaHash !== await worldLearnerDeltaHash(certificate.learnerDelta)) {
      return false;
    }
    return certificate.certificateHash === await worldLearnerDeltaCertificateHash(certificate);
  } catch {
    return false;
  }
}

export function applyWorldLearnerDelta(learnerState         , learnerDelta                         )          {
  let state = structuredCloneJson(learnerState);
  for (const operation of learnerDelta) {
    if (operation.op === "set") {
      state = setPath(state, operation.path, structuredCloneJson(operation.value));
    } else if (operation.op === "remove") {
      state = removePath(state, operation.path);
    } else {
      throw new Error(`unsupported learner delta op: ${(operation                    ).op}`);
    }
  }
  return state;
}

export async function auditWorldLearnerLineage(
  initialSnapshot                      ,
  finalSnapshot                      ,
  updateCertificates                                 ,
  certificate                                ,
)                   {
  try {
    if (!await validateWorldLearnerLineageCertificate(certificate)) {
      return false;
    }
    if (!await validateWorldLearnerSnapshot(initialSnapshot) || !await validateWorldLearnerSnapshot(finalSnapshot)) {
      return false;
    }
    if (initialSnapshot.learnerId !== finalSnapshot.learnerId || initialSnapshot.learnerVersion !== finalSnapshot.learnerVersion) {
      return false;
    }
    if (certificate.learnerId !== finalSnapshot.learnerId || certificate.learnerVersion !== finalSnapshot.learnerVersion) {
      return false;
    }
    if (certificate.initialSnapshotHash !== initialSnapshot.snapshotHash || certificate.finalSnapshotHash !== finalSnapshot.snapshotHash) {
      return false;
    }
    if (certificate.initialUpdateCount !== initialSnapshot.updateCount || certificate.finalUpdateCount !== finalSnapshot.updateCount) {
      return false;
    }
    if (certificate.updateCertificateCount !== updateCertificates.length) {
      return false;
    }
    if (!(await Promise.all(updateCertificates.map((updateCertificate) => validateWorldLearnerUpdateCertificate(updateCertificate)))).every(Boolean)) {
      return false;
    }
    if (!sameStringArray(certificate.updateCertificateHashes, updateCertificates.map((updateCertificate) => updateCertificate.certificateHash))) {
      return false;
    }

    const appliedReceipts = updateCertificates.filter((updateCertificate) => updateCertificate.updateApplied).map((updateCertificate) => updateCertificate.sourceReceiptHash);
    if (certificate.appliedUpdateCount !== appliedReceipts.length || !sameStringArray(certificate.sourceReceiptHashes, appliedReceipts)) {
      return false;
    }
    const expectedReceipts = [...initialSnapshot.sourceReceiptHashes, ...appliedReceipts];
    if (!sameStringArray(finalSnapshot.sourceReceiptHashes, expectedReceipts)) {
      return false;
    }
    if (finalSnapshot.updateCount !== initialSnapshot.updateCount + appliedReceipts.length) {
      return false;
    }

    let previousHash = initialSnapshot.snapshotHash;
    let previousCount = initialSnapshot.updateCount;
    for (const updateCertificate of updateCertificates) {
      if (updateCertificate.learnerId !== certificate.learnerId || updateCertificate.learnerVersion !== certificate.learnerVersion) {
        return false;
      }
      if (updateCertificate.preLearnerSnapshotHash !== previousHash) {
        return false;
      }
      if (updateCertificate.preUpdateCount !== previousCount) {
        return false;
      }
      previousHash = updateCertificate.learnerSnapshotHash;
      previousCount = updateCertificate.postUpdateCount;
    }
    return previousHash === finalSnapshot.snapshotHash && previousCount === finalSnapshot.updateCount;
  } catch {
    return false;
  }
}

export async function validateWorldLearnerLineageCertificate(certificate                                )                   {
  try {
    if (certificate.schemaVersion !== WORLD_LEARNER_LINEAGE_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (![certificate.learnerId, certificate.learnerVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    const counts = [
      certificate.initialUpdateCount,
      certificate.finalUpdateCount,
      certificate.updateCertificateCount,
      certificate.appliedUpdateCount,
    ];
    if (!counts.every((value) => Number.isSafeInteger(value) && value >= 0)) {
      return false;
    }
    if (certificate.finalUpdateCount < certificate.initialUpdateCount) {
      return false;
    }
    if (certificate.appliedUpdateCount !== certificate.finalUpdateCount - certificate.initialUpdateCount) {
      return false;
    }
    if (certificate.appliedUpdateCount > certificate.updateCertificateCount) {
      return false;
    }
    if (certificate.sourceReceiptHashes.length !== certificate.appliedUpdateCount) {
      return false;
    }
    if (certificate.updateCertificateHashes.length !== certificate.updateCertificateCount) {
      return false;
    }
    if (certificate.sourceReceiptHashes.length !== new Set(certificate.sourceReceiptHashes).size) {
      return false;
    }
    if (![certificate.initialSnapshotHash, certificate.finalSnapshotHash, certificate.lineageHash].every(isHash)) {
      return false;
    }
    if (!certificate.sourceReceiptHashes.every(isHash) || !certificate.updateCertificateHashes.every(isHash)) {
      return false;
    }
    if (certificate.lineageHash !== await worldLearnerLineageHash(certificate)) {
      return false;
    }
    return certificate.certificateHash === await worldLearnerLineageCertificateHash(certificate);
  } catch {
    return false;
  }
}

export async function mergeWorldLearnerSnapshots(
  left                      ,
  right                      ,
  options   
                                        
                                                           
                                                            
    = {},
)                                   {
  if (!await validateWorldLearnerSnapshot(left) || !await validateWorldLearnerSnapshot(right)) {
    throw new Error("world learner snapshots must validate before merge");
  }
  if (left.learnerId !== right.learnerId || left.learnerVersion !== right.learnerVersion) {
    throw new Error("world learner snapshots must use the same learner identity");
  }

  const leftReceipts = new Set(left.sourceReceiptHashes);
  const rightReceipts = new Set(right.sourceReceiptHashes);
  const sharedReceipts = intersection(leftReceipts, rightReceipts);
  let mergedState         ;
  let mergedReceipts          ;
  let mergeBasis = "disjoint";
  let commonPrefixReceiptCount = 0;
  let baseSnapshotHash                = null;
  const leftDeltaCertificates = options.leftDeltaCertificates ?? [];
  const rightDeltaCertificates = options.rightDeltaCertificates ?? [];

  if (left.snapshotHash === right.snapshotHash) {
    mergeBasis = "duplicate";
    mergedState = left.learnerState;
    mergedReceipts = [...left.sourceReceiptHashes];
    commonPrefixReceiptCount = left.updateCount;
  } else if (setSubset(leftReceipts, rightReceipts)) {
    mergeBasis = "left_superset";
    mergedState = right.learnerState;
    mergedReceipts = [...right.sourceReceiptHashes];
    commonPrefixReceiptCount = left.updateCount;
  } else if (setSubset(rightReceipts, leftReceipts)) {
    mergeBasis = "right_superset";
    mergedState = left.learnerState;
    mergedReceipts = [...left.sourceReceiptHashes];
    commonPrefixReceiptCount = right.updateCount;
  } else if (sharedReceipts.size > 0) {
    if (!options.baseSnapshot || leftDeltaCertificates.length === 0 || rightDeltaCertificates.length === 0) {
      throw new Error("partially overlapping learner snapshots require base snapshot and per-receipt deltas");
    }
    const partial = await mergePartialOverlapWithDeltas(
      options.baseSnapshot,
      left,
      right,
      leftDeltaCertificates,
      rightDeltaCertificates,
    );
    mergeBasis = "delta_common_prefix";
    mergedState = partial.mergedState;
    mergedReceipts = partial.mergedReceipts;
    commonPrefixReceiptCount = partial.commonPrefixReceiptCount;
    baseSnapshotHash = options.baseSnapshot.snapshotHash;
  } else {
    const merged = mergeDisjointLearnerState(left.learnerState, right.learnerState);
    if (merged.conflictKeys.length > 0) {
      throw new Error(`conflicting learner state keys: ${merged.conflictKeys.join(", ")}`);
    }
    mergedState = merged.value;
    mergedReceipts = Array.from(new Set([...leftReceipts, ...rightReceipts])).sort(compareString);
  }

  const mergedSnapshot = await buildMergedWorldLearnerSnapshot(left, mergedReceipts, mergedState);
  const certificate                               = {
    schemaVersion: WORLD_LEARNER_MERGE_CERTIFICATE_SCHEMA,
    learnerId: left.learnerId,
    learnerVersion: left.learnerVersion,
    mergeStrategy: WORLD_LEARNER_MERGE_STRATEGY,
    mergeBasis,
    leftSnapshotHash: left.snapshotHash,
    rightSnapshotHash: right.snapshotHash,
    mergedSnapshotHash: mergedSnapshot.snapshotHash,
    baseSnapshotHash,
    leftUpdateCount: left.updateCount,
    rightUpdateCount: right.updateCount,
    mergedUpdateCount: mergedSnapshot.updateCount,
    sharedReceiptCount: sharedReceipts.size,
    commonPrefixReceiptCount,
    conflictCount: 0,
    conflictKeys: [],
    sourceReceiptHashes: [...mergedSnapshot.sourceReceiptHashes],
    leftDeltaCertificateHashes: leftDeltaCertificates.map((certificate) => certificate.certificateHash),
    rightDeltaCertificateHashes: rightDeltaCertificates.map((certificate) => certificate.certificateHash),
    mergedStateHash: mergedSnapshot.learnerStateHash,
    certificateHash: "",
  };
  certificate.certificateHash = await worldLearnerMergeCertificateHash(certificate);
  return { mergedSnapshot, certificate };
}

export async function auditWorldLearnerMerge(
  left                      ,
  right                      ,
  merged                      ,
  certificate                              ,
  options   
                                        
                                                           
                                                            
    = {},
)                   {
  try {
    if (!await validateWorldLearnerMergeCertificate(certificate)) {
      return false;
    }
    const recomputed = await mergeWorldLearnerSnapshots(left, right, options);
    return await validateWorldLearnerSnapshot(merged)
      && merged.snapshotHash === recomputed.mergedSnapshot.snapshotHash
      && certificate.certificateHash === recomputed.certificate.certificateHash
      && certificate.mergedSnapshotHash === merged.snapshotHash
      && certificate.mergedStateHash === merged.learnerStateHash;
  } catch {
    return false;
  }
}

export async function validateWorldLearnerMergeCertificate(certificate                              )                   {
  try {
    if (certificate.schemaVersion !== WORLD_LEARNER_MERGE_CERTIFICATE_SCHEMA) {
      return false;
    }
    if (certificate.mergeStrategy !== WORLD_LEARNER_MERGE_STRATEGY) {
      return false;
    }
    if (!WORLD_LEARNER_MERGE_BASIS.has(certificate.mergeBasis)) {
      return false;
    }
    if (![certificate.learnerId, certificate.learnerVersion].every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (![certificate.leftSnapshotHash, certificate.rightSnapshotHash, certificate.mergedSnapshotHash, certificate.mergedStateHash].every(isHash)) {
      return false;
    }
    const counts = [
      certificate.leftUpdateCount,
      certificate.rightUpdateCount,
      certificate.mergedUpdateCount,
      certificate.sharedReceiptCount,
      certificate.commonPrefixReceiptCount,
      certificate.conflictCount,
    ];
    if (!counts.every((value) => Number.isSafeInteger(value) && value >= 0)) {
      return false;
    }
    if (certificate.baseSnapshotHash !== null && !isHash(certificate.baseSnapshotHash)) {
      return false;
    }
    if (certificate.conflictCount !== 0 || certificate.conflictKeys.length > 0) {
      return false;
    }
    if (certificate.sourceReceiptHashes.length !== certificate.mergedUpdateCount) {
      return false;
    }
    if (certificate.sourceReceiptHashes.length !== new Set(certificate.sourceReceiptHashes).size) {
      return false;
    }
    if (!certificate.sourceReceiptHashes.every(isHash)) {
      return false;
    }
    if (!certificate.leftDeltaCertificateHashes.every(isHash) || !certificate.rightDeltaCertificateHashes.every(isHash)) {
      return false;
    }
    if (certificate.sharedReceiptCount > Math.min(certificate.leftUpdateCount, certificate.rightUpdateCount)) {
      return false;
    }
    if (certificate.commonPrefixReceiptCount < certificate.sharedReceiptCount) {
      return false;
    }
    if (certificate.commonPrefixReceiptCount > Math.min(certificate.leftUpdateCount, certificate.rightUpdateCount)) {
      return false;
    }
    if (certificate.mergedUpdateCount !== certificate.leftUpdateCount + certificate.rightUpdateCount - certificate.sharedReceiptCount) {
      return false;
    }
    if (certificate.mergeBasis === "delta_common_prefix") {
      if (certificate.baseSnapshotHash === null) {
        return false;
      }
      if (certificate.leftDeltaCertificateHashes.length === 0 || certificate.rightDeltaCertificateHashes.length === 0) {
        return false;
      }
      if (certificate.commonPrefixReceiptCount !== certificate.sharedReceiptCount) {
        return false;
      }
    } else if (certificate.baseSnapshotHash !== null) {
      return false;
    }
    return certificate.certificateHash === await worldLearnerMergeCertificateHash(certificate);
  } catch {
    return false;
  }
}

export async function validateWorldModelStepCertificate(certificate                           )                   {
  try {
    if (certificate.schemaVersion !== WORLD_MODEL_STEP_CERTIFICATE_SCHEMA) {
      return false;
    }
    const requiredStrings = [
      certificate.proposerId,
      certificate.proposerVersion,
      certificate.projectorId,
      certificate.projectorVersion,
      certificate.learnerId,
      certificate.learnerVersion,
      certificate.verifierId,
      certificate.verifierVersion,
      certificate.receiptSchema,
      certificate.commitDecision,
    ];
    if (!requiredStrings.every((value) => typeof value === "string" && value.length > 0)) {
      return false;
    }
    if (!["accept", "reject", "abstain"].includes(certificate.hardResult)) {
      return false;
    }
    if (typeof certificate.committed !== "boolean") {
      return false;
    }
    if (!Number.isInteger(certificate.learnerUpdateCount) || certificate.learnerUpdateCount < 0) {
      return false;
    }
    const requiredHashes = [
      certificate.proposalTraceHash,
      certificate.typedCandidateHash,
      certificate.receiptHash,
      certificate.preStateHash,
      certificate.learnerStateHash,
      certificate.learnerSnapshotHash,
      certificate.learnerUpdateCertificateHash,
      certificate.ledgerHead,
    ];
    if (!requiredHashes.every(isHash)) {
      return false;
    }
    for (const value of [certificate.postStateHash, certificate.rollbackStateHash]) {
      if (value !== null && !isHash(value)) {
        return false;
      }
    }
    if (certificate.committed) {
      if (certificate.hardResult !== "accept" || certificate.commitDecision !== "commit") {
        return false;
      }
      if (!certificate.postStateHash || !certificate.rollbackStateHash) {
        return false;
      }
    } else if (certificate.commitDecision === "commit") {
      return false;
    }
    return certificate.certificateHash === await worldModelStepCertificateHash(certificate);
  } catch {
    return false;
  }
}

export async function worldModelStepCertificateHash(certificate                           )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function worldLearnerStateHash(learnerState         )                  {
  return stableHash(learnerState);
}

export async function worldLearnerSnapshotHash(snapshot                      )                  {
  const { snapshotHash: _snapshotHash, ...withoutHash } = snapshot;
  return stableHash(withoutHash);
}

export async function worldLearnerUpdateCertificateHash(certificate                               )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function worldLearnerDeltaHash(learnerDelta                         )                  {
  return stableHash(learnerDelta.map((operation) => ({ ...operation, path: [...operation.path] })));
}

export async function worldLearnerDeltaCertificateHash(certificate                              )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function worldLearnerLineageHash(certificate                                )                  {
  return stableHash({
    schemaVersion: certificate.schemaVersion,
    learnerId: certificate.learnerId,
    learnerVersion: certificate.learnerVersion,
    initialSnapshotHash: certificate.initialSnapshotHash,
    finalSnapshotHash: certificate.finalSnapshotHash,
    sourceReceiptHashes: [...certificate.sourceReceiptHashes],
    updateCertificateHashes: [...certificate.updateCertificateHashes],
  });
}

export async function worldLearnerLineageCertificateHash(certificate                                )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function worldLearnerMergeCertificateHash(certificate                              )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

async function buildMergedWorldLearnerSnapshot(
  base                      ,
  sourceReceiptHashes          ,
  learnerState         ,
)                                {
  const snapshot                       = {
    schemaVersion: WORLD_LEARNER_SNAPSHOT_SCHEMA,
    learnerId: base.learnerId,
    learnerVersion: base.learnerVersion,
    updateCount: sourceReceiptHashes.length,
    sourceReceiptHashes: [...sourceReceiptHashes],
    learnerState,
    learnerStateHash: await worldLearnerStateHash(learnerState),
    snapshotHash: "",
  };
  snapshot.snapshotHash = await worldLearnerSnapshotHash(snapshot);
  return snapshot;
}

function mergeDisjointLearnerState(left         , right         , path = "$")                                             {
  if (isRecord(left) && isRecord(right)) {
    const value                          = {};
    const conflictKeys           = [];
    const keys = Array.from(new Set([...Object.keys(left), ...Object.keys(right)])).sort(compareString);
    for (const key of keys) {
      const childPath = `${path}.${key}`;
      if (!(key in left)) {
        value[key] = right[key];
        continue;
      }
      if (!(key in right)) {
        value[key] = left[key];
        continue;
      }
      const merged = mergeDisjointLearnerState(left[key], right[key], childPath);
      value[key] = merged.value;
      conflictKeys.push(...merged.conflictKeys);
    }
    return { value, conflictKeys };
  }
  const key = path.split(".").at(-1) ?? "";
  if (key.toLowerCase().endsWith("count") && nonnegativeSafeInteger(left) && nonnegativeSafeInteger(right)) {
    return { value: left + right, conflictKeys: [] };
  }
  if (stableEqual(left, right)) {
    return { value: left, conflictKeys: [] };
  }
  if (left === null || left === undefined) {
    return { value: right, conflictKeys: [] };
  }
  if (right === null || right === undefined) {
    return { value: left, conflictKeys: [] };
  }
  return { value: null, conflictKeys: [path] };
}

async function mergePartialOverlapWithDeltas(
  baseSnapshot                      ,
  left                      ,
  right                      ,
  leftDeltaCertificates                                ,
  rightDeltaCertificates                                ,
)                                                                                                {
  if (!await validateWorldLearnerSnapshot(baseSnapshot)) {
    throw new Error("base learner snapshot must validate before partial-overlap merge");
  }
  if (
    baseSnapshot.learnerId !== left.learnerId
    || baseSnapshot.learnerId !== right.learnerId
    || baseSnapshot.learnerVersion !== left.learnerVersion
    || baseSnapshot.learnerVersion !== right.learnerVersion
  ) {
    throw new Error("partial-overlap merge requires one learner identity");
  }
  const baseReceipts = [...baseSnapshot.sourceReceiptHashes];
  if (!arrayPrefix(baseReceipts, left.sourceReceiptHashes) || !arrayPrefix(baseReceipts, right.sourceReceiptHashes)) {
    throw new Error("base learner snapshot must be a receipt prefix of both partial-overlap snapshots");
  }

  const leftReplay = await replayWorldLearnerDeltaChain(baseSnapshot, left, leftDeltaCertificates);
  const rightReplay = await replayWorldLearnerDeltaChain(baseSnapshot, right, rightDeltaCertificates);
  const sharedReceipts = intersection(new Set(left.sourceReceiptHashes), new Set(right.sourceReceiptHashes));
  const commonPrefixReceiptCount = commonPrefixCount(left.sourceReceiptHashes, right.sourceReceiptHashes);
  const commonPrefixReceipts = left.sourceReceiptHashes.slice(0, commonPrefixReceiptCount);
  if (!sameStringSet(new Set(commonPrefixReceipts), sharedReceipts)) {
    throw new Error("partial-overlap learner snapshots must overlap only on a common receipt prefix");
  }
  if (commonPrefixReceiptCount < baseSnapshot.updateCount) {
    throw new Error("base learner snapshot extends past the common receipt prefix");
  }

  const commonOffset = commonPrefixReceiptCount - baseSnapshot.updateCount;
  const leftCommon = leftReplay.snapshots[commonOffset];
  const rightCommon = rightReplay.snapshots[commonOffset];
  if (leftCommon.snapshotHash !== rightCommon.snapshotHash) {
    throw new Error("partial-overlap learner delta chains disagree on common prefix state");
  }

  const merged = mergeCommonAncestorLearnerState(leftCommon.learnerState, left.learnerState, right.learnerState);
  if (merged.conflictKeys.length > 0) {
    throw new Error(`conflicting partial-overlap learner state keys: ${merged.conflictKeys.join(", ")}`);
  }
  const uniqueReceipts = Array.from(new Set([...left.sourceReceiptHashes, ...right.sourceReceiptHashes]))
    .filter((receiptHash) => !sharedReceipts.has(receiptHash))
    .sort(compareString);
  return {
    mergedState: merged.value,
    mergedReceipts: [...commonPrefixReceipts, ...uniqueReceipts],
    commonPrefixReceiptCount,
  };
}

async function replayWorldLearnerDeltaChain(
  baseSnapshot                      ,
  finalSnapshot                      ,
  deltaCertificates                                ,
)                                                                 {
  const suffixReceipts = finalSnapshot.sourceReceiptHashes.slice(baseSnapshot.updateCount);
  if (deltaCertificates.length !== suffixReceipts.length) {
    throw new Error("learner delta certificate count must match receipt suffix");
  }
  let currentState = structuredCloneJson(baseSnapshot.learnerState);
  let currentSnapshot = baseSnapshot;
  const snapshots = [baseSnapshot];
  for (let idx = 0; idx < suffixReceipts.length; idx += 1) {
    const receiptHash = suffixReceipts[idx];
    const deltaCertificate = deltaCertificates[idx];
    if (!await validateWorldLearnerDeltaCertificate(deltaCertificate)) {
      throw new Error("learner delta certificate must validate before replay");
    }
    if (deltaCertificate.learnerId !== finalSnapshot.learnerId || deltaCertificate.learnerVersion !== finalSnapshot.learnerVersion) {
      throw new Error("learner delta certificate identity mismatch");
    }
    if (deltaCertificate.sourceReceiptHash !== receiptHash) {
      throw new Error("learner delta certificate receipt order mismatch");
    }
    if (deltaCertificate.preSnapshotHash !== currentSnapshot.snapshotHash) {
      throw new Error("learner delta certificate pre-snapshot hash mismatch");
    }
    if (deltaCertificate.preLearnerStateHash !== await worldLearnerStateHash(currentState)) {
      throw new Error("learner delta certificate pre-state hash mismatch");
    }
    currentState = applyWorldLearnerDelta(currentState, deltaCertificate.learnerDelta);
    if (deltaCertificate.postLearnerStateHash !== await worldLearnerStateHash(currentState)) {
      throw new Error("learner delta certificate post-state hash mismatch");
    }
    currentSnapshot = await buildMergedWorldLearnerSnapshot(
      finalSnapshot,
      [...currentSnapshot.sourceReceiptHashes, receiptHash],
      currentState,
    );
    if (deltaCertificate.postSnapshotHash !== currentSnapshot.snapshotHash) {
      throw new Error("learner delta certificate post-snapshot hash mismatch");
    }
    snapshots.push(currentSnapshot);
  }
  if (currentSnapshot.snapshotHash !== finalSnapshot.snapshotHash || !stableEqual(currentState, finalSnapshot.learnerState)) {
    throw new Error("learner delta chain does not replay to final snapshot");
  }
  return { state: currentState, snapshots };
}

const MISSING = Symbol("missing");

function mergeCommonAncestorLearnerState(
  base         ,
  left         ,
  right         ,
  path = "$",
)                                                              {
  if (isRecord(base) || isRecord(left) || isRecord(right)) {
    if (![base, left, right].every((value) => value === MISSING || isRecord(value))) {
      return { value: null, conflictKeys: [path] };
    }
    const value                          = {};
    const conflictKeys           = [];
    const keys = new Set        ();
    for (const record of [base, left, right]) {
      if (isRecord(record)) {
        for (const key of Object.keys(record)) keys.add(key);
      }
    }
    for (const key of Array.from(keys).sort(compareString)) {
      const childBase = isRecord(base) && Object.prototype.hasOwnProperty.call(base, key) ? base[key] : MISSING;
      const childLeft = isRecord(left) && Object.prototype.hasOwnProperty.call(left, key) ? left[key] : MISSING;
      const childRight = isRecord(right) && Object.prototype.hasOwnProperty.call(right, key) ? right[key] : MISSING;
      const merged = mergeCommonAncestorLearnerState(childBase, childLeft, childRight, `${path}.${key}`);
      if (merged.conflictKeys.length > 0) {
        conflictKeys.push(...merged.conflictKeys);
      } else if (merged.value !== MISSING) {
        value[key] = merged.value;
      }
    }
    return { value, conflictKeys };
  }

  if (left === MISSING && right === MISSING) {
    return { value: MISSING, conflictKeys: [] };
  }
  if (base === MISSING) {
    return mergeDisjointLearnerState(left, right, path);
  }
  if (left === MISSING) {
    return stableEqual(right, base) ? { value: MISSING, conflictKeys: [] } : { value: null, conflictKeys: [path] };
  }
  if (right === MISSING) {
    return stableEqual(left, base) ? { value: MISSING, conflictKeys: [] } : { value: null, conflictKeys: [path] };
  }

  const key = path.split(".").at(-1) ?? "";
  if (
    key.toLowerCase().endsWith("count")
    && nonnegativeSafeInteger(base)
    && nonnegativeSafeInteger(left)
    && nonnegativeSafeInteger(right)
  ) {
    if (left < base || right < base) {
      return { value: null, conflictKeys: [path] };
    }
    return { value: base + (left - base) + (right - base), conflictKeys: [] };
  }
  if (stableEqual(left, right)) {
    return { value: left, conflictKeys: [] };
  }
  if (stableEqual(left, base)) {
    return { value: right, conflictKeys: [] };
  }
  if (stableEqual(right, base)) {
    return { value: left, conflictKeys: [] };
  }
  return { value: null, conflictKeys: [path] };
}

function learnerStateDelta(pre         , post         , path           = [])                          {
  if (stableEqual(pre, post)) {
    return [];
  }
  if (isRecord(pre) && isRecord(post)) {
    const operations                          = [];
    const keys = Array.from(new Set([...Object.keys(pre), ...Object.keys(post)])).sort(compareString);
    for (const key of keys) {
      const keyPath = [...path, key];
      if (!(key in post)) {
        operations.push({ op: "remove", path: keyPath });
      } else if (!(key in pre)) {
        operations.push({ op: "set", path: keyPath, value: post[key] });
      } else {
        operations.push(...learnerStateDelta(pre[key], post[key], keyPath));
      }
    }
    return operations;
  }
  return [{ op: "set", path, value: post }];
}

function validateLearnerDelta(learnerDelta                         )          {
  return learnerDelta.every((operation) => {
    if (!operation || typeof operation !== "object") {
      return false;
    }
    if (operation.op !== "set" && operation.op !== "remove") {
      return false;
    }
    if (!Array.isArray(operation.path) || !operation.path.every((part) => typeof part === "string" && part.length > 0)) {
      return false;
    }
    if (operation.op === "set" && !Object.prototype.hasOwnProperty.call(operation, "value")) {
      return false;
    }
    if (operation.op === "remove" && Object.prototype.hasOwnProperty.call(operation, "value")) {
      return false;
    }
    return true;
  });
}

function setPath(state         , path          , value         )          {
  if (path.length === 0) {
    return value;
  }
  if (!isRecord(state)) {
    throw new Error("cannot set nested learner delta path on non-record state");
  }
  let cursor                          = state;
  for (const key of path.slice(0, -1)) {
    if (!isRecord(cursor[key])) {
      throw new Error("cannot set missing nested learner delta path");
    }
    cursor = cursor[key]                           ;
  }
  cursor[path[path.length - 1]] = value;
  return state;
}

function removePath(state         , path          )          {
  if (path.length === 0) {
    throw new Error("cannot remove learner root state");
  }
  if (!isRecord(state)) {
    throw new Error("cannot remove nested learner delta path on non-record state");
  }
  let cursor                          = state;
  for (const key of path.slice(0, -1)) {
    if (!isRecord(cursor[key])) {
      throw new Error("cannot remove missing nested learner delta path");
    }
    cursor = cursor[key]                           ;
  }
  const leaf = path[path.length - 1];
  if (!Object.prototype.hasOwnProperty.call(cursor, leaf)) {
    throw new Error("cannot remove missing learner delta path");
  }
  delete cursor[leaf];
  return state;
}

function isRecord(value         )                                   {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function intersection   (left        , right        )         {
  return new Set(Array.from(left).filter((value) => right.has(value)));
}

function setSubset   (left        , right        )          {
  return Array.from(left).every((value) => right.has(value));
}

function compareString(left        , right        )         {
  if (left < right) return -1;
  if (left > right) return 1;
  return 0;
}

function stableEqual(left         , right         )          {
  return JSON.stringify(left) === JSON.stringify(right);
}

function structuredCloneJson(value         )          {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function sameStringArray(left          , right          )          {
  return left.length === right.length && left.every((value, idx) => value === right[idx]);
}

function sameStringSet(left             , right             )          {
  return left.size === right.size && Array.from(left).every((value) => right.has(value));
}

function arrayPrefix(prefix          , value          )          {
  return prefix.every((part, index) => value[index] === part);
}

function commonPrefixCount(left          , right          )         {
  let count = 0;
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    if (left[index] !== right[index]) break;
    count += 1;
  }
  return count;
}

function nonnegativeSafeInteger(value         )                  {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function componentId(component         , role                                      )         {
  const object = component                           ;
  const key = role === "proposer" ? "proposerId" : role === "projector" ? "projectorId" : "learnerId";
  return String(object[key] ?? component?.constructor?.name ?? role);
}

function componentVersion(component         )         {
  const object = component                           ;
  return String(object.proposerVersion ?? object.projectorVersion ?? object.learnerVersion ?? object.version ?? object.modelVersion ?? "1.0");
}

async function learnerStateSnapshot(learner                            )                   {
  if (!learner) {
    return {};
  }
  if (typeof learner.snapshotState === "function") {
    return learner.snapshotState();
  }
  if (typeof learner.snapshot === "function") {
    return learner.snapshot();
  }
  return {
    class: learner.constructor?.name ?? "ReceiptLearner",
    snapshot: "opaque",
  };
}

function isHash(value        )          {
  return /^[0-9a-f]{64}$/.test(value);
}
