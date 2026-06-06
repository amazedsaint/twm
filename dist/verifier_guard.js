import {
                          
               
                             
                      
  hardAccept,
  hardAbstain,
  hardReject,
} from "./core.js";

                                                        
                     
                          
                                                                                                        
 

export class VerifierAgreementAdapter                         
                                                          {
  verifierId        ;
  verifierVersion        ;
  primary                                                ;
  audit                                       ;
  primaryCalls = 0;
  auditCalls = 0;
  falsePositiveCount = 0;
  primaryAcceptBlockCount = 0;

  constructor(
    primary                                                ,
    audit                                       ,
    options                                                    = {},
  ) {
    this.primary = primary;
    this.audit = audit;
    this.verifierId = options.verifierId ?? "verifier_agreement_guard";
    this.verifierVersion = options.verifierVersion ?? "1.0";
  }

  async verify(candidate                                  )                              {
    this.primaryCalls += 1;
    const primaryResult = await this.primary.verify(candidate);
    if (!this.resultMatches(primaryResult, this.primary)) {
      if (primaryResult.result === "accept") {
        this.primaryAcceptBlockCount += 1;
      }
      return hardReject(
        this.verifierId,
        this.verifierVersion,
        {
          kind: "primary_verifier_mismatch",
          primaryResult: primaryResult.result,
          primary_result: primaryResult.result,
          primaryVerifierId: primaryResult.verifierId,
          primary_verifier_id: primaryResult.verifierId,
          expectedPrimaryVerifierId: this.primary.verifierId,
          expected_primary_verifier_id: this.primary.verifierId,
        },
        this.metadata(primaryResult, undefined, false),
      );
    }

    if (primaryResult.result !== "accept") {
      const metadata = this.metadata(primaryResult, undefined, false);
      if (primaryResult.result === "abstain") {
        return hardAbstain(this.verifierId, this.verifierVersion, primaryResult.residual, metadata);
      }
      return hardReject(this.verifierId, this.verifierVersion, primaryResult.residual, metadata);
    }

    this.auditCalls += 1;
    const auditResult = await this.audit.verify(candidate);
    const metadata = this.metadata(primaryResult, auditResult, true);
    if (!this.resultMatches(auditResult, this.audit)) {
      this.primaryAcceptBlockCount += 1;
      return hardReject(
        this.verifierId,
        this.verifierVersion,
        {
          kind: "audit_verifier_mismatch",
          primaryResult: primaryResult.result,
          primary_result: primaryResult.result,
          auditResult: auditResult.result,
          audit_result: auditResult.result,
          auditVerifierId: auditResult.verifierId,
          audit_verifier_id: auditResult.verifierId,
          expectedAuditVerifierId: this.audit.verifierId,
          expected_audit_verifier_id: this.audit.verifierId,
        },
        metadata,
      );
    }

    if (auditResult.result === "accept") {
      return hardAccept(this.verifierId, this.verifierVersion, metadata);
    }

    this.falsePositiveCount += 1;
    this.primaryAcceptBlockCount += 1;
    return hardReject(
      this.verifierId,
      this.verifierVersion,
      {
        kind: "verifier_false_positive",
        primaryResult: primaryResult.result,
        primary_result: primaryResult.result,
        auditResult: auditResult.result,
        audit_result: auditResult.result,
        auditResidual: auditResult.residual,
        audit_residual: auditResult.residual,
        primaryVerifierId: this.primary.verifierId,
        primary_verifier_id: this.primary.verifierId,
        auditVerifierId: this.audit.verifierId,
        audit_verifier_id: this.audit.verifierId,
      },
      metadata,
    );
  }

  async applyCommit(state       , candidate                                  )                 {
    return this.primary.applyCommit(state, candidate);
  }

  async replay(state       , receipt         )                 {
    return this.primary.replay(state, receipt);
  }

  async rollback(state       , receipt         )                 {
    return this.primary.rollback(state, receipt);
  }

          resultMatches(result                    , adapter                                       )          {
    return result.verifierId === adapter.verifierId && result.verifierVersion === adapter.verifierVersion;
  }

          metadata(
    primaryResult                    ,
    auditResult                                ,
    auditCalled         ,
  )                          {
    const metadata                          = {
      ...primaryResult.metadata,
      primaryResult: primaryResult.result,
      primary_result: primaryResult.result,
      auditResult: auditResult?.result ?? null,
      audit_result: auditResult?.result ?? null,
      auditCalled,
      audit_called: auditCalled,
      primaryVerifierId: this.primary.verifierId,
      primary_verifier_id: this.primary.verifierId,
      primaryVerifierVersion: this.primary.verifierVersion,
      primary_verifier_version: this.primary.verifierVersion,
      auditVerifierId: this.audit.verifierId,
      audit_verifier_id: this.audit.verifierId,
      auditVerifierVersion: this.audit.verifierVersion,
      audit_verifier_version: this.audit.verifierVersion,
      primaryMetadata: primaryResult.metadata,
      primary_metadata: primaryResult.metadata,
      auditMetadata: auditResult?.metadata ?? {},
      audit_metadata: auditResult?.metadata ?? {},
    };
    if (!("cost" in metadata) && auditResult && "cost" in auditResult.metadata) {
      metadata.cost = auditResult.metadata.cost;
    }
    return metadata;
  }
}
