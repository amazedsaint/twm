from __future__ import annotations

from dataclasses import dataclass, replace

from ..core import ProposalTrace
from ..sdk import domain_manifest_hash, validate_domain_manifest, ProgrammableSubstrate
from .game_of_life import LifePredecessorAdapter, LifeProjector, LifeState, life_step
from .repair_simulator import ScalarProgramAdapter, make_scalar_candidate


@dataclass(frozen=True)
class SdkManifestReport:
    schema_version: str
    domain_count: int
    manifest_valid_count: int
    manifest_audit_count: int
    scalar_candidate_types: tuple[str, ...]
    life_projection_schemas: tuple[str, ...]
    scalar_verifier_id: str
    life_verifier_id: str
    scalar_receipt_count: int
    life_receipt_count: int
    total_receipt_count: int
    accepted_count: int
    rejected_count: int
    hard_verifier_calls: int
    total_verifier_cost: int
    manifest_hashes_stable: bool
    tamper_detected: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float


def run_sdk_manifest_benchmark() -> SdkManifestReport:
    substrate = ProgrammableSubstrate()
    substrate.register("scalar", ScalarProgramAdapter())
    substrate.register("life", LifePredecessorAdapter())

    scalar_state = {"episode": 0, "target": 5, "solved": False}
    substrate.submit(
        "scalar",
        scalar_state,
        ProposalTrace(
            branch_id="manifest-scalar",
            actions=({"op": "set", "value": 5},),
            seeds=("manifest", "scalar"),
            model_version="manifest.scalar.v1",
        ),
        make_scalar_candidate("manifest", 5, ({"op": "set", "value": 5},)),
        context="manifest",
    )

    predecessor = (
        (0, 0, 0),
        (1, 1, 1),
        (0, 0, 0),
    )
    target = life_step(predecessor)
    life_state = LifeState(target=target)
    bad_trace = ProposalTrace(
        branch_id="manifest-life-reject",
        actions=({"predecessor": ((0, 0, 0), (0, 0, 0), (0, 0, 0)), "cost": 2},),
        seeds=("manifest", "life-reject"),
        model_version="manifest.life.v1",
    )
    good_trace = ProposalTrace(
        branch_id="manifest-life-accept",
        actions=({"predecessor": predecessor, "cost": 1},),
        seeds=("manifest", "life-accept"),
        model_version="manifest.life.v1",
    )
    projector = LifeProjector()
    substrate.submit("life", life_state, bad_trace, projector.project(life_state, bad_trace), context="manifest")
    substrate.submit("life", life_state, good_trace, projector.project(life_state, good_trace), context="manifest")

    scalar_manifest = substrate.domain_manifest("scalar")
    life_manifest = substrate.domain_manifest("life")
    manifests = (scalar_manifest, life_manifest)
    audits = (substrate.audit_domain("scalar", scalar_state), substrate.audit_domain("life", life_state))
    tampered = replace(scalar_manifest, verifier_id="tampered_verifier", manifest_hash="")
    return SdkManifestReport(
        schema_version=scalar_manifest.schema_version,
        domain_count=len(substrate.domains),
        manifest_valid_count=sum(1 for manifest in manifests if validate_domain_manifest(manifest)),
        manifest_audit_count=sum(
            1 for domain_id, manifest in (("scalar", scalar_manifest), ("life", life_manifest))
            if substrate.audit_domain_manifest(domain_id, manifest)
        ),
        scalar_candidate_types=scalar_manifest.candidate_type_names,
        life_projection_schemas=life_manifest.projection_schema_versions,
        scalar_verifier_id=scalar_manifest.verifier_id,
        life_verifier_id=life_manifest.verifier_id,
        scalar_receipt_count=scalar_manifest.receipt_count,
        life_receipt_count=life_manifest.receipt_count,
        total_receipt_count=sum(manifest.receipt_count for manifest in manifests),
        accepted_count=sum(manifest.accepted_count for manifest in manifests),
        rejected_count=sum(manifest.rejected_count for manifest in manifests),
        hard_verifier_calls=sum(manifest.hard_verifier_calls for manifest in manifests),
        total_verifier_cost=sum(manifest.verifier_cost for manifest in manifests),
        manifest_hashes_stable=all(domain_manifest_hash(manifest) == manifest.manifest_hash for manifest in manifests),
        tamper_detected=not substrate.audit_domain_manifest("scalar", tampered),
        invalid_commit_count=substrate.invalid_commit_count(),
        ledger_audit=all(audit.ledger_audit for audit in audits),
        replay_rollback_rate=sum(1 for audit in audits if audit.ok) / len(audits),
    )
