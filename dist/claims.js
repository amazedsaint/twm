import { stableHash } from "./canonical.js";

export const CLAIM_CERTIFICATE_SCHEMA = "trwm.claim_certificate.v1";
export const CLAIM_EVIDENCE_GRADES = ["G0", "G1", "G2", "G3"]         ;
export const CLAIM_STATUSES = ["supported", "rejected"]         ;

                                                                      
                                                        

                                   
              
                  
                                    
                 
 

                                   
                        
                  
                    
                                    
                
                      
                                   
                                   
                   
                    
                          
 

export function requirement(
  key        ,
  passed         ,
  options                                                          = {},
)                   {
  if (!key) {
    throw new RangeError("requirement key must be non-empty");
  }
  return {
    key,
    passed,
    evidence: options.evidence ?? {},
    reason: options.reason ?? "",
  };
}

export async function certifyClaim(params   
                  
                    
                                    
                
                                   
                                    
                    
                     
 )                            {
  if (new Set(params.requirements.map((row) => row.key)).size !== params.requirements.length) {
    throw new Error("claim requirement keys must be unique");
  }
  const pending                   = {
    schemaVersion: CLAIM_CERTIFICATE_SCHEMA,
    claimId: params.claimId,
    claimText: params.claimText,
    evidenceGrade: params.evidenceGrade,
    scope: params.scope,
    status: params.requirements.every((row) => row.passed) ? "supported" : "rejected",
    requirements: params.requirements,
    metrics: params.metrics ?? {},
    boundary: params.boundary ?? "",
    sources: params.sources ?? [],
    certificateHash: "",
  };
  validateClaimShape(pending);
  return { ...pending, certificateHash: await claimCertificateHash(pending) };
}

export async function claimCertificateHash(certificate                  )                  {
  const { certificateHash: _certificateHash, ...withoutHash } = certificate;
  return stableHash(withoutHash);
}

export async function validateClaimCertificate(certificate                  )                   {
  try {
    validateClaimShape(certificate);
  } catch (_error) {
    return false;
  }
  if (certificate.status === "supported" && certificate.requirements.some((row) => !row.passed)) {
    return false;
  }
  if (certificate.status === "rejected" && certificate.requirements.every((row) => row.passed)) {
    return false;
  }
  return certificate.certificateHash === await claimCertificateHash(certificate);
}

export function failedClaimKeys(certificate                  )           {
  return certificate.requirements.filter((row) => !row.passed).map((row) => row.key);
}

function validateClaimShape(certificate                  )       {
  if (certificate.schemaVersion !== CLAIM_CERTIFICATE_SCHEMA) {
    throw new Error(`invalid claim certificate schema: ${certificate.schemaVersion}`);
  }
  if (!certificate.claimId) {
    throw new Error("claimId must be non-empty");
  }
  if (!certificate.claimText) {
    throw new Error("claimText must be non-empty");
  }
  if (!CLAIM_EVIDENCE_GRADES.includes(certificate.evidenceGrade)) {
    throw new Error(`invalid evidence grade: ${certificate.evidenceGrade}`);
  }
  if (!CLAIM_STATUSES.includes(certificate.status)) {
    throw new Error(`invalid claim status: ${certificate.status}`);
  }
  if (new Set(certificate.requirements.map((row) => row.key)).size !== certificate.requirements.length) {
    throw new Error("claim requirement keys must be unique");
  }
  for (const row of certificate.requirements) {
    if (!row.key) {
      throw new Error("requirement key must be non-empty");
    }
  }
}
