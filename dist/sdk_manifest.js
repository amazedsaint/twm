import { makeTrace } from "./core.js";
import {
  LifePredecessorAdapter,
  lifeStep,
  makeLifeCandidate,
} from "./life.js";
import {
  ScalarProgramAdapter,
  makeScalarCandidate,
} from "./repair.js";
import {
  ProgrammableSubstrate,
  domainManifestHash,
  validateDomainManifest,
} from "./sdk.js";

                                    
                        
                      
                             
                             
                                 
                                  
                           
                         
                             
                           
                            
                        
                        
                            
                            
                                
                          
                             
                       
                             
 

export async function runSdkManifestBenchmark()                             {
  const substrate = new ProgrammableSubstrate();
  substrate.register("scalar", new ScalarProgramAdapter());
  substrate.register("life", new LifePredecessorAdapter());

  const scalarState = { episode: 0, target: 5, solved: false };
  await substrate.submit(
    "scalar",
    scalarState,
    makeTrace({
      branchId: "manifest-scalar",
      actions: [{ op: "set", value: 5 }],
      seeds: ["manifest", "scalar"],
      modelVersion: "manifest.scalar.v1",
    }),
    makeScalarCandidate("manifest", 5, [{ op: "set", value: 5 }]),
    { context: "manifest" },
  );

  const predecessor = [
    [0, 0, 0],
    [1, 1, 1],
    [0, 0, 0],
  ];
  const target = lifeStep(predecessor);
  const lifeState = { target };
  const badPredecessor = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
  ];
  await substrate.submit(
    "life",
    lifeState,
    makeTrace({
      branchId: "manifest-life-reject",
      actions: [{ predecessor: badPredecessor, cost: 2 }],
      seeds: ["manifest", "life-reject"],
      modelVersion: "manifest.life.v1",
    }),
    await makeLifeCandidate(target, badPredecessor, 2),
    { context: "manifest" },
  );
  await substrate.submit(
    "life",
    lifeState,
    makeTrace({
      branchId: "manifest-life-accept",
      actions: [{ predecessor, cost: 1 }],
      seeds: ["manifest", "life-accept"],
      modelVersion: "manifest.life.v1",
    }),
    await makeLifeCandidate(target, predecessor, 1),
    { context: "manifest" },
  );

  const scalarManifest = await substrate.domainManifest("scalar");
  const lifeManifest = await substrate.domainManifest("life");
  const manifests = [scalarManifest, lifeManifest];
  const audits = [
    await substrate.auditDomain("scalar", scalarState),
    await substrate.auditDomain("life", lifeState),
  ];
  const tampered = { ...scalarManifest, verifierId: "tampered_verifier", manifestHash: "" };
  tampered.manifestHash = await domainManifestHash(tampered);

  return {
    schemaVersion: scalarManifest.schemaVersion,
    domainCount: substrate.domains.size,
    manifestValidCount: (await Promise.all(manifests.map((manifest) => validateDomainManifest(manifest)))).filter(Boolean).length,
    manifestAuditCount: (await Promise.all([
      substrate.auditDomainManifest("scalar", scalarManifest),
      substrate.auditDomainManifest("life", lifeManifest),
    ])).filter(Boolean).length,
    scalarCandidateTypes: scalarManifest.candidateTypeNames,
    lifeProjectionSchemas: lifeManifest.projectionSchemaVersions,
    scalarVerifierId: scalarManifest.verifierId,
    lifeVerifierId: lifeManifest.verifierId,
    scalarReceiptCount: scalarManifest.receiptCount,
    lifeReceiptCount: lifeManifest.receiptCount,
    totalReceiptCount: manifests.reduce((total, manifest) => total + manifest.receiptCount, 0),
    acceptedCount: manifests.reduce((total, manifest) => total + manifest.acceptedCount, 0),
    rejectedCount: manifests.reduce((total, manifest) => total + manifest.rejectedCount, 0),
    hardVerifierCalls: manifests.reduce((total, manifest) => total + manifest.hardVerifierCalls, 0),
    totalVerifierCost: manifests.reduce((total, manifest) => total + manifest.verifierCost, 0),
    manifestHashesStable: (await Promise.all(manifests.map(async (manifest) => await domainManifestHash(manifest) === manifest.manifestHash))).every(Boolean),
    tamperDetected: !await substrate.auditDomainManifest("scalar", tampered),
    invalidCommitCount: substrate.invalidCommitCount(),
    ledgerAudit: audits.every((audit) => audit.ledgerAudit),
    replayRollbackRate: audits.filter((audit) => audit.ok).length / audits.length,
  };
}
