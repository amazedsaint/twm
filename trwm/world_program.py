from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable, Mapping

from .core import GENESIS_HEAD, ProposalTrace, Receipt, TypedCandidate, chain_hash, stable_hash
from .world import (
    WorldLearnerDeltaCertificate,
    WorldLearnerSnapshot,
    WorldLearnerUpdateCertificate,
    WorldModelStepCertificate,
    audit_world_learner_delta,
    audit_world_learner_update,
    audit_world_model_step,
    validate_world_learner_delta_certificate,
    validate_world_learner_snapshot,
    validate_world_learner_update_certificate,
    validate_world_model_step_certificate,
)


WORLD_PROGRAM_MANIFEST_SCHEMA = "trwm.world_program_manifest.v1"
WORLD_PROGRAM_CERTIFICATE_SCHEMA = "trwm.world_program_certificate.v1"
WORLD_PROGRAM_ADMISSION_POLICY_SCHEMA = "trwm.world_program_admission_policy.v1"
WORLD_PROGRAM_ADMISSION_CERTIFICATE_SCHEMA = "trwm.world_program_admission_certificate.v1"
WORLD_PROGRAM_EVIDENCE_BUNDLE_SCHEMA = "trwm.world_program_evidence_bundle.v1"
WORLD_PROGRAM_BUNDLE_VERIFICATION_CERTIFICATE_SCHEMA = "trwm.world_program_bundle_verification_certificate.v1"
WORLD_PROGRAM_REPLAY_STEP_SCHEMA = "trwm.world_program_replay_step.v1"
WORLD_PROGRAM_REPLAY_PACKAGE_SCHEMA = "trwm.world_program_replay_package.v1"
WORLD_PROGRAM_REPLAY_VERIFICATION_CERTIFICATE_SCHEMA = "trwm.world_program_replay_verification_certificate.v1"
WORLD_PROGRAM_BUILD_TYPE = "trwm.world_program_execution.v1"


@dataclass(frozen=True)
class WorldProgramManifest:
    schema_version: str
    program_id: str
    program_version: str
    build_type: str
    proposer_id: str
    proposer_version: str
    projector_id: str
    projector_version: str
    learner_id: str
    learner_version: str
    verifier_id: str
    verifier_version: str
    input_schema: str
    candidate_schema: str
    external_parameters: Mapping[str, Any] = field(default_factory=dict)
    resolved_dependencies: tuple[str, ...] = ()
    manifest_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_MANIFEST_SCHEMA:
            raise ValueError(f"invalid world program manifest schema: {self.schema_version}")
        object.__setattr__(self, "external_parameters", dict(self.external_parameters))
        object.__setattr__(self, "resolved_dependencies", tuple(self.resolved_dependencies))
        if not self.manifest_hash:
            object.__setattr__(self, "manifest_hash", world_program_manifest_hash(self))


@dataclass(frozen=True)
class WorldProgramCertificate:
    schema_version: str
    program_id: str
    program_version: str
    manifest_hash: str
    step_count: int
    committed_count: int
    rejected_count: int
    learner_update_count: int
    step_certificate_hashes: tuple[str, ...]
    receipt_hashes: tuple[str, ...]
    final_learner_snapshot_hash: str
    ledger_head: str
    invalid_commit_count: int
    replay_rollback_rate: float
    artifact_hash_groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world program certificate schema: {self.schema_version}")
        object.__setattr__(self, "step_certificate_hashes", tuple(self.step_certificate_hashes))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(
            self,
            "artifact_hash_groups",
            {str(key): tuple(values) for key, values in sorted(self.artifact_hash_groups.items())},
        )
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_program_certificate_hash(self))


@dataclass(frozen=True)
class WorldProgramAdmissionPolicy:
    schema_version: str
    policy_id: str
    policy_version: str
    allowed_build_types: tuple[str, ...] = (WORLD_PROGRAM_BUILD_TYPE,)
    allowed_program_ids: tuple[str, ...] = ()
    allowed_program_versions: tuple[str, ...] = ()
    allowed_proposer_ids: tuple[str, ...] = ()
    allowed_projector_ids: tuple[str, ...] = ()
    allowed_learner_ids: tuple[str, ...] = ()
    allowed_verifier_ids: tuple[str, ...] = ()
    allowed_input_schemas: tuple[str, ...] = ()
    allowed_candidate_schemas: tuple[str, ...] = ()
    required_dependencies: tuple[str, ...] = ()
    required_artifact_keys: tuple[str, ...] = ()
    min_step_count: int = 1
    min_committed_count: int = 0
    min_rejected_count: int = 0
    max_invalid_commit_count: int = 0
    min_replay_rollback_rate: float = 1.0
    policy_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_ADMISSION_POLICY_SCHEMA:
            raise ValueError(f"invalid world program admission policy schema: {self.schema_version}")
        for field_name in (
            "allowed_build_types",
            "allowed_program_ids",
            "allowed_program_versions",
            "allowed_proposer_ids",
            "allowed_projector_ids",
            "allowed_learner_ids",
            "allowed_verifier_ids",
            "allowed_input_schemas",
            "allowed_candidate_schemas",
            "required_dependencies",
            "required_artifact_keys",
        ):
            object.__setattr__(self, field_name, _dedupe_strings(getattr(self, field_name)))
        if not self.policy_hash:
            object.__setattr__(self, "policy_hash", world_program_admission_policy_hash(self))


@dataclass(frozen=True)
class WorldProgramAdmissionCertificate:
    schema_version: str
    policy_id: str
    policy_version: str
    policy_hash: str
    manifest_hash: str
    execution_certificate_hash: str
    program_id: str
    program_version: str
    external_parameters_hash: str
    resolved_dependency_hash: str
    artifact_hash_groups_hash: str
    requirement_count: int
    passed_requirements: tuple[str, ...]
    failed_requirements: tuple[str, ...]
    admitted: bool
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_ADMISSION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world program admission certificate schema: {self.schema_version}")
        object.__setattr__(self, "passed_requirements", tuple(self.passed_requirements))
        object.__setattr__(self, "failed_requirements", tuple(self.failed_requirements))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_program_admission_certificate_hash(self))


@dataclass(frozen=True)
class WorldProgramEvidenceBundle:
    schema_version: str
    bundle_id: str
    bundle_version: str
    manifest: WorldProgramManifest
    execution_certificate: WorldProgramCertificate
    admission_policy: WorldProgramAdmissionPolicy
    admission_certificate: WorldProgramAdmissionCertificate
    step_certificate_hashes: tuple[str, ...]
    receipt_hashes: tuple[str, ...]
    final_learner_snapshot_hash: str
    artifact_hash_groups: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    source_bundle_hashes: tuple[str, ...] = ()
    bundle_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_EVIDENCE_BUNDLE_SCHEMA:
            raise ValueError(f"invalid world program evidence bundle schema: {self.schema_version}")
        object.__setattr__(self, "step_certificate_hashes", tuple(self.step_certificate_hashes))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(self, "source_bundle_hashes", tuple(self.source_bundle_hashes))
        object.__setattr__(
            self,
            "artifact_hash_groups",
            {str(key): tuple(values) for key, values in sorted(self.artifact_hash_groups.items())},
        )
        if not self.bundle_hash:
            object.__setattr__(self, "bundle_hash", world_program_evidence_bundle_hash(self))


@dataclass(frozen=True)
class WorldProgramBundleVerificationCertificate:
    schema_version: str
    bundle_hash: str
    verifier_id: str
    verifier_version: str
    policy_hash: str
    manifest_hash: str
    execution_certificate_hash: str
    admission_certificate_hash: str
    input_attestation_hashes: tuple[str, ...]
    requirement_count: int
    passed_requirements: tuple[str, ...]
    failed_requirements: tuple[str, ...]
    verified: bool
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_BUNDLE_VERIFICATION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world program bundle verification schema: {self.schema_version}")
        object.__setattr__(self, "input_attestation_hashes", tuple(self.input_attestation_hashes))
        object.__setattr__(self, "passed_requirements", tuple(self.passed_requirements))
        object.__setattr__(self, "failed_requirements", tuple(self.failed_requirements))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_program_bundle_verification_certificate_hash(self))


@dataclass(frozen=True)
class WorldProgramReplayStep:
    schema_version: str
    step_index: int
    trace: ProposalTrace
    candidate: TypedCandidate
    receipt: Receipt
    certificate: WorldModelStepCertificate
    pre_learner_snapshot: WorldLearnerSnapshot
    learner_snapshot: WorldLearnerSnapshot
    learner_update_certificate: WorldLearnerUpdateCertificate
    learner_delta_certificate: WorldLearnerDeltaCertificate
    step_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_REPLAY_STEP_SCHEMA:
            raise ValueError(f"invalid world program replay step schema: {self.schema_version}")
        if not self.step_hash:
            object.__setattr__(self, "step_hash", world_program_replay_step_hash(self))


@dataclass(frozen=True)
class WorldProgramReplayPackage:
    schema_version: str
    package_id: str
    package_version: str
    evidence_bundle: WorldProgramEvidenceBundle
    steps: tuple[WorldProgramReplayStep, ...]
    step_hashes: tuple[str, ...]
    step_certificate_hashes: tuple[str, ...]
    receipt_hashes: tuple[str, ...]
    learner_update_certificate_hashes: tuple[str, ...]
    learner_delta_certificate_hashes: tuple[str, ...]
    final_learner_snapshot_hash: str
    ledger_head: str
    package_body_hash: str = ""
    package_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_REPLAY_PACKAGE_SCHEMA:
            raise ValueError(f"invalid world program replay package schema: {self.schema_version}")
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "step_hashes", tuple(self.step_hashes))
        object.__setattr__(self, "step_certificate_hashes", tuple(self.step_certificate_hashes))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(self, "learner_update_certificate_hashes", tuple(self.learner_update_certificate_hashes))
        object.__setattr__(self, "learner_delta_certificate_hashes", tuple(self.learner_delta_certificate_hashes))
        if not self.package_body_hash:
            object.__setattr__(self, "package_body_hash", world_program_replay_package_body_hash(self))
        if not self.package_hash:
            object.__setattr__(self, "package_hash", world_program_replay_package_hash(self))


@dataclass(frozen=True)
class WorldProgramReplayVerificationCertificate:
    schema_version: str
    package_hash: str
    evidence_bundle_hash: str
    verifier_id: str
    verifier_version: str
    package_body_hash: str
    ledger_head: str
    final_learner_snapshot_hash: str
    step_hashes: tuple[str, ...]
    step_certificate_hashes: tuple[str, ...]
    receipt_hashes: tuple[str, ...]
    learner_update_certificate_hashes: tuple[str, ...]
    learner_delta_certificate_hashes: tuple[str, ...]
    requirement_count: int
    passed_requirements: tuple[str, ...]
    failed_requirements: tuple[str, ...]
    replay_verified: bool
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_PROGRAM_REPLAY_VERIFICATION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world program replay verification schema: {self.schema_version}")
        object.__setattr__(self, "step_hashes", tuple(self.step_hashes))
        object.__setattr__(self, "step_certificate_hashes", tuple(self.step_certificate_hashes))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(self, "learner_update_certificate_hashes", tuple(self.learner_update_certificate_hashes))
        object.__setattr__(self, "learner_delta_certificate_hashes", tuple(self.learner_delta_certificate_hashes))
        object.__setattr__(self, "passed_requirements", tuple(self.passed_requirements))
        object.__setattr__(self, "failed_requirements", tuple(self.failed_requirements))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_program_replay_verification_certificate_hash(self))


def build_world_program_manifest(
    *,
    program_id: str,
    program_version: str,
    proposer: Any,
    projector: Any,
    learner: Any,
    verifier_id: str,
    verifier_version: str,
    input_schema: str,
    candidate_schema: str,
    external_parameters: Mapping[str, Any] | None = None,
    resolved_dependencies: Iterable[str] = (),
) -> WorldProgramManifest:
    return WorldProgramManifest(
        schema_version=WORLD_PROGRAM_MANIFEST_SCHEMA,
        program_id=program_id,
        program_version=program_version,
        build_type=WORLD_PROGRAM_BUILD_TYPE,
        proposer_id=_component_value(proposer, "proposer_id", "proposerId", "proposer"),
        proposer_version=_component_value(proposer, "proposer_version", "proposerVersion", "0"),
        projector_id=_component_value(projector, "projector_id", "projectorId", "projector"),
        projector_version=_component_value(projector, "projector_version", "projectorVersion", "0"),
        learner_id=_component_value(learner, "learner_id", "learnerId", "none"),
        learner_version=_component_value(learner, "learner_version", "learnerVersion", "0"),
        verifier_id=verifier_id,
        verifier_version=verifier_version,
        input_schema=input_schema,
        candidate_schema=candidate_schema,
        external_parameters=external_parameters or {},
        resolved_dependencies=tuple(resolved_dependencies),
    )


def build_world_program_admission_policy(
    *,
    policy_id: str,
    policy_version: str,
    allowed_build_types: Iterable[str] = (WORLD_PROGRAM_BUILD_TYPE,),
    allowed_program_ids: Iterable[str] = (),
    allowed_program_versions: Iterable[str] = (),
    allowed_proposer_ids: Iterable[str] = (),
    allowed_projector_ids: Iterable[str] = (),
    allowed_learner_ids: Iterable[str] = (),
    allowed_verifier_ids: Iterable[str] = (),
    allowed_input_schemas: Iterable[str] = (),
    allowed_candidate_schemas: Iterable[str] = (),
    required_dependencies: Iterable[str] = (),
    required_artifact_keys: Iterable[str] = (),
    min_step_count: int = 1,
    min_committed_count: int = 0,
    min_rejected_count: int = 0,
    max_invalid_commit_count: int = 0,
    min_replay_rollback_rate: float = 1.0,
) -> WorldProgramAdmissionPolicy:
    return WorldProgramAdmissionPolicy(
        schema_version=WORLD_PROGRAM_ADMISSION_POLICY_SCHEMA,
        policy_id=policy_id,
        policy_version=policy_version,
        allowed_build_types=tuple(allowed_build_types),
        allowed_program_ids=tuple(allowed_program_ids),
        allowed_program_versions=tuple(allowed_program_versions),
        allowed_proposer_ids=tuple(allowed_proposer_ids),
        allowed_projector_ids=tuple(allowed_projector_ids),
        allowed_learner_ids=tuple(allowed_learner_ids),
        allowed_verifier_ids=tuple(allowed_verifier_ids),
        allowed_input_schemas=tuple(allowed_input_schemas),
        allowed_candidate_schemas=tuple(allowed_candidate_schemas),
        required_dependencies=tuple(required_dependencies),
        required_artifact_keys=tuple(required_artifact_keys),
        min_step_count=min_step_count,
        min_committed_count=min_committed_count,
        min_rejected_count=min_rejected_count,
        max_invalid_commit_count=max_invalid_commit_count,
        min_replay_rollback_rate=min_replay_rollback_rate,
    )


def build_world_program_certificate(
    manifest: WorldProgramManifest,
    steps: Iterable[Any],
    *,
    ledger_head: str,
    invalid_commit_count: int,
    replay_rollback_rate: float,
) -> WorldProgramCertificate:
    rows = tuple(steps)
    if not rows:
        raise ValueError("world program certificate requires at least one step")
    artifact_hash_groups: defaultdict[str, list[str]] = defaultdict(list)
    for step in rows:
        for key, value in getattr(step.receipt, "artifact_hashes", {}).items():
            if value not in artifact_hash_groups[str(key)]:
                artifact_hash_groups[str(key)].append(value)
    final_snapshot = rows[-1].learner_snapshot
    return WorldProgramCertificate(
        schema_version=WORLD_PROGRAM_CERTIFICATE_SCHEMA,
        program_id=manifest.program_id,
        program_version=manifest.program_version,
        manifest_hash=manifest.manifest_hash,
        step_count=len(rows),
        committed_count=sum(1 for step in rows if step.committed),
        rejected_count=sum(1 for step in rows if step.receipt.hard_result.rejected),
        learner_update_count=final_snapshot.update_count,
        step_certificate_hashes=tuple(step.certificate.certificate_hash for step in rows),
        receipt_hashes=tuple(step.receipt.receipt_hash for step in rows),
        final_learner_snapshot_hash=final_snapshot.snapshot_hash,
        ledger_head=ledger_head,
        invalid_commit_count=invalid_commit_count,
        replay_rollback_rate=replay_rollback_rate,
        artifact_hash_groups={key: tuple(values) for key, values in artifact_hash_groups.items()},
    )


def build_world_program_admission_certificate(
    policy: WorldProgramAdmissionPolicy,
    manifest: WorldProgramManifest,
    execution_certificate: WorldProgramCertificate,
) -> WorldProgramAdmissionCertificate:
    passed_requirements, failed_requirements = _evaluate_world_program_admission(policy, manifest, execution_certificate)
    return WorldProgramAdmissionCertificate(
        schema_version=WORLD_PROGRAM_ADMISSION_CERTIFICATE_SCHEMA,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_hash=policy.policy_hash,
        manifest_hash=manifest.manifest_hash,
        execution_certificate_hash=execution_certificate.certificate_hash,
        program_id=manifest.program_id,
        program_version=manifest.program_version,
        external_parameters_hash=stable_hash(manifest.external_parameters),
        resolved_dependency_hash=stable_hash(tuple(manifest.resolved_dependencies)),
        artifact_hash_groups_hash=stable_hash(execution_certificate.artifact_hash_groups),
        requirement_count=len(passed_requirements) + len(failed_requirements),
        passed_requirements=passed_requirements,
        failed_requirements=failed_requirements,
        admitted=not failed_requirements,
    )


def build_world_program_evidence_bundle(
    manifest: WorldProgramManifest,
    execution_certificate: WorldProgramCertificate,
    admission_policy: WorldProgramAdmissionPolicy,
    admission_certificate: WorldProgramAdmissionCertificate,
    *,
    bundle_id: str | None = None,
    bundle_version: str = "1.0",
    source_bundle_hashes: Iterable[str] = (),
) -> WorldProgramEvidenceBundle:
    return WorldProgramEvidenceBundle(
        schema_version=WORLD_PROGRAM_EVIDENCE_BUNDLE_SCHEMA,
        bundle_id=bundle_id or f"{manifest.program_id}.evidence",
        bundle_version=bundle_version,
        manifest=manifest,
        execution_certificate=execution_certificate,
        admission_policy=admission_policy,
        admission_certificate=admission_certificate,
        step_certificate_hashes=execution_certificate.step_certificate_hashes,
        receipt_hashes=execution_certificate.receipt_hashes,
        final_learner_snapshot_hash=execution_certificate.final_learner_snapshot_hash,
        artifact_hash_groups=execution_certificate.artifact_hash_groups,
        source_bundle_hashes=tuple(source_bundle_hashes),
    )


def build_world_program_bundle_verification_certificate(
    bundle: WorldProgramEvidenceBundle,
    *,
    verifier_id: str = "trwm.world_program_bundle_verifier",
    verifier_version: str = "1.0",
) -> WorldProgramBundleVerificationCertificate:
    passed_requirements, failed_requirements = _evaluate_world_program_bundle_verification(bundle)
    return WorldProgramBundleVerificationCertificate(
        schema_version=WORLD_PROGRAM_BUNDLE_VERIFICATION_CERTIFICATE_SCHEMA,
        bundle_hash=bundle.bundle_hash,
        verifier_id=verifier_id,
        verifier_version=verifier_version,
        policy_hash=bundle.admission_policy.policy_hash,
        manifest_hash=bundle.manifest.manifest_hash,
        execution_certificate_hash=bundle.execution_certificate.certificate_hash,
        admission_certificate_hash=bundle.admission_certificate.certificate_hash,
        input_attestation_hashes=_bundle_input_attestation_hashes(bundle),
        requirement_count=len(passed_requirements) + len(failed_requirements),
        passed_requirements=passed_requirements,
        failed_requirements=failed_requirements,
        verified=not failed_requirements,
    )


def build_world_program_replay_step(step: Any, *, step_index: int) -> WorldProgramReplayStep:
    return WorldProgramReplayStep(
        schema_version=WORLD_PROGRAM_REPLAY_STEP_SCHEMA,
        step_index=step_index,
        trace=step.trace,
        candidate=step.candidate,
        receipt=step.receipt,
        certificate=step.certificate,
        pre_learner_snapshot=step.pre_learner_snapshot,
        learner_snapshot=step.learner_snapshot,
        learner_update_certificate=step.learner_update_certificate,
        learner_delta_certificate=step.learner_delta_certificate,
    )


def build_world_program_replay_package(
    evidence_bundle: WorldProgramEvidenceBundle,
    steps: Iterable[Any],
    *,
    package_id: str | None = None,
    package_version: str = "1.0",
) -> WorldProgramReplayPackage:
    rows = tuple(
        step if isinstance(step, WorldProgramReplayStep) else build_world_program_replay_step(step, step_index=index)
        for index, step in enumerate(steps)
    )
    if not rows:
        raise ValueError("world program replay package requires at least one step")
    return WorldProgramReplayPackage(
        schema_version=WORLD_PROGRAM_REPLAY_PACKAGE_SCHEMA,
        package_id=package_id or f"{evidence_bundle.bundle_id}.replay",
        package_version=package_version,
        evidence_bundle=evidence_bundle,
        steps=rows,
        step_hashes=tuple(step.step_hash for step in rows),
        step_certificate_hashes=tuple(step.certificate.certificate_hash for step in rows),
        receipt_hashes=tuple(step.receipt.receipt_hash for step in rows),
        learner_update_certificate_hashes=tuple(step.learner_update_certificate.certificate_hash for step in rows),
        learner_delta_certificate_hashes=tuple(step.learner_delta_certificate.certificate_hash for step in rows),
        final_learner_snapshot_hash=rows[-1].learner_snapshot.snapshot_hash,
        ledger_head=_ledger_head_from_replay_steps(rows),
    )


def build_world_program_replay_verification_certificate(
    replay_package: WorldProgramReplayPackage,
    *,
    verifier_id: str = "trwm.world_program_replay_verifier",
    verifier_version: str = "1.0",
) -> WorldProgramReplayVerificationCertificate:
    passed_requirements, failed_requirements = _evaluate_world_program_replay_verification(replay_package)
    return WorldProgramReplayVerificationCertificate(
        schema_version=WORLD_PROGRAM_REPLAY_VERIFICATION_CERTIFICATE_SCHEMA,
        package_hash=replay_package.package_hash,
        evidence_bundle_hash=replay_package.evidence_bundle.bundle_hash,
        verifier_id=verifier_id,
        verifier_version=verifier_version,
        package_body_hash=replay_package.package_body_hash,
        ledger_head=replay_package.ledger_head,
        final_learner_snapshot_hash=replay_package.final_learner_snapshot_hash,
        step_hashes=replay_package.step_hashes,
        step_certificate_hashes=replay_package.step_certificate_hashes,
        receipt_hashes=replay_package.receipt_hashes,
        learner_update_certificate_hashes=replay_package.learner_update_certificate_hashes,
        learner_delta_certificate_hashes=replay_package.learner_delta_certificate_hashes,
        requirement_count=len(passed_requirements) + len(failed_requirements),
        passed_requirements=passed_requirements,
        failed_requirements=failed_requirements,
        replay_verified=not failed_requirements,
    )


def audit_world_program_certificate(
    manifest: WorldProgramManifest,
    steps: Iterable[Any],
    certificate: WorldProgramCertificate,
    *,
    ledger_head: str,
    invalid_commit_count: int,
    replay_rollback_rate: float,
) -> bool:
    try:
        expected = build_world_program_certificate(
            manifest,
            steps,
            ledger_head=ledger_head,
            invalid_commit_count=invalid_commit_count,
            replay_rollback_rate=replay_rollback_rate,
        )
        return certificate == expected and validate_world_program_certificate(certificate, manifest)
    except Exception:
        return False


def audit_world_program_admission(
    policy: WorldProgramAdmissionPolicy,
    manifest: WorldProgramManifest,
    execution_certificate: WorldProgramCertificate,
    admission_certificate: WorldProgramAdmissionCertificate,
) -> bool:
    try:
        expected = build_world_program_admission_certificate(policy, manifest, execution_certificate)
        return admission_certificate == expected and validate_world_program_admission_certificate(
            admission_certificate,
            policy,
            manifest,
            execution_certificate,
        )
    except Exception:
        return False


def audit_world_program_evidence_bundle(
    manifest: WorldProgramManifest,
    execution_certificate: WorldProgramCertificate,
    admission_policy: WorldProgramAdmissionPolicy,
    admission_certificate: WorldProgramAdmissionCertificate,
    bundle: WorldProgramEvidenceBundle,
) -> bool:
    try:
        expected = build_world_program_evidence_bundle(
            manifest,
            execution_certificate,
            admission_policy,
            admission_certificate,
            bundle_id=bundle.bundle_id,
            bundle_version=bundle.bundle_version,
            source_bundle_hashes=bundle.source_bundle_hashes,
        )
        return bundle == expected and validate_world_program_evidence_bundle(bundle)
    except Exception:
        return False


def audit_world_program_bundle_verification(
    bundle: WorldProgramEvidenceBundle,
    certificate: WorldProgramBundleVerificationCertificate,
) -> bool:
    try:
        expected = build_world_program_bundle_verification_certificate(
            bundle,
            verifier_id=certificate.verifier_id,
            verifier_version=certificate.verifier_version,
        )
        return certificate == expected and validate_world_program_bundle_verification_certificate(certificate, bundle)
    except Exception:
        return False


def audit_world_program_replay_package(
    evidence_bundle: WorldProgramEvidenceBundle,
    steps: Iterable[Any],
    replay_package: WorldProgramReplayPackage,
) -> bool:
    try:
        expected = build_world_program_replay_package(
            evidence_bundle,
            steps,
            package_id=replay_package.package_id,
            package_version=replay_package.package_version,
        )
        return replay_package == expected and validate_world_program_replay_package(replay_package)
    except Exception:
        return False


def audit_world_program_replay_verification(
    replay_package: WorldProgramReplayPackage,
    certificate: WorldProgramReplayVerificationCertificate,
) -> bool:
    try:
        expected = build_world_program_replay_verification_certificate(
            replay_package,
            verifier_id=certificate.verifier_id,
            verifier_version=certificate.verifier_version,
        )
        return certificate == expected and validate_world_program_replay_verification_certificate(certificate, replay_package)
    except Exception:
        return False


def validate_world_program_manifest(manifest: WorldProgramManifest) -> bool:
    try:
        if manifest.schema_version != WORLD_PROGRAM_MANIFEST_SCHEMA:
            return False
        if manifest.build_type != WORLD_PROGRAM_BUILD_TYPE:
            return False
        required = (
            manifest.program_id,
            manifest.program_version,
            manifest.proposer_id,
            manifest.proposer_version,
            manifest.projector_id,
            manifest.projector_version,
            manifest.learner_id,
            manifest.learner_version,
            manifest.verifier_id,
            manifest.verifier_version,
            manifest.input_schema,
            manifest.candidate_schema,
        )
        if any(not isinstance(value, str) or not value for value in required):
            return False
        if not isinstance(manifest.external_parameters, Mapping):
            return False
        if any(not isinstance(value, str) or not value for value in manifest.resolved_dependencies):
            return False
        return manifest.manifest_hash == world_program_manifest_hash(manifest)
    except Exception:
        return False


def validate_world_program_admission_policy(policy: WorldProgramAdmissionPolicy) -> bool:
    try:
        if policy.schema_version != WORLD_PROGRAM_ADMISSION_POLICY_SCHEMA:
            return False
        if not isinstance(policy.policy_id, str) or not policy.policy_id:
            return False
        if not isinstance(policy.policy_version, str) or not policy.policy_version:
            return False
        for values in (
            policy.allowed_build_types,
            policy.allowed_program_ids,
            policy.allowed_program_versions,
            policy.allowed_proposer_ids,
            policy.allowed_projector_ids,
            policy.allowed_learner_ids,
            policy.allowed_verifier_ids,
            policy.allowed_input_schemas,
            policy.allowed_candidate_schemas,
            policy.required_dependencies,
            policy.required_artifact_keys,
        ):
            if not isinstance(values, tuple):
                return False
            if any(not isinstance(value, str) or not value for value in values):
                return False
            if len(set(values)) != len(values):
                return False
        if not policy.allowed_build_types:
            return False
        for value in (
            policy.min_step_count,
            policy.min_committed_count,
            policy.min_rejected_count,
            policy.max_invalid_commit_count,
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False
        if policy.min_step_count <= 0:
            return False
        if not isinstance(policy.min_replay_rollback_rate, (int, float)) or not (0.0 <= policy.min_replay_rollback_rate <= 1.0):
            return False
        return policy.policy_hash == world_program_admission_policy_hash(policy)
    except Exception:
        return False


def validate_world_program_certificate(
    certificate: WorldProgramCertificate,
    manifest: WorldProgramManifest | None = None,
) -> bool:
    try:
        if certificate.schema_version != WORLD_PROGRAM_CERTIFICATE_SCHEMA:
            return False
        if not isinstance(certificate.program_id, str) or not certificate.program_id:
            return False
        if not isinstance(certificate.program_version, str) or not certificate.program_version:
            return False
        if not _is_hash(certificate.manifest_hash):
            return False
        if not isinstance(certificate.step_count, int) or isinstance(certificate.step_count, bool) or certificate.step_count <= 0:
            return False
        if len(certificate.step_certificate_hashes) != certificate.step_count:
            return False
        if len(certificate.receipt_hashes) != certificate.step_count:
            return False
        for value in (certificate.committed_count, certificate.rejected_count, certificate.learner_update_count, certificate.invalid_commit_count):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False
        if certificate.committed_count + certificate.rejected_count > certificate.step_count:
            return False
        if not (0.0 <= certificate.replay_rollback_rate <= 1.0):
            return False
        if not _is_hash(certificate.final_learner_snapshot_hash) or not _is_hash(certificate.ledger_head):
            return False
        if any(not _is_hash(value) for value in certificate.step_certificate_hashes):
            return False
        if any(not _is_hash(value) for value in certificate.receipt_hashes):
            return False
        if len(set(certificate.receipt_hashes)) != len(certificate.receipt_hashes):
            return False
        for key, values in certificate.artifact_hash_groups.items():
            if not isinstance(key, str) or not key:
                return False
            if not isinstance(values, tuple) or any(not _is_hash(value) for value in values):
                return False
        if manifest is not None:
            if not validate_world_program_manifest(manifest):
                return False
            if certificate.manifest_hash != manifest.manifest_hash:
                return False
            if certificate.program_id != manifest.program_id or certificate.program_version != manifest.program_version:
                return False
        return certificate.certificate_hash == world_program_certificate_hash(certificate)
    except Exception:
        return False


def validate_world_program_admission_certificate(
    admission_certificate: WorldProgramAdmissionCertificate,
    policy: WorldProgramAdmissionPolicy | None = None,
    manifest: WorldProgramManifest | None = None,
    execution_certificate: WorldProgramCertificate | None = None,
) -> bool:
    try:
        if admission_certificate.schema_version != WORLD_PROGRAM_ADMISSION_CERTIFICATE_SCHEMA:
            return False
        for value in (
            admission_certificate.policy_id,
            admission_certificate.policy_version,
            admission_certificate.program_id,
            admission_certificate.program_version,
        ):
            if not isinstance(value, str) or not value:
                return False
        for value in (
            admission_certificate.policy_hash,
            admission_certificate.manifest_hash,
            admission_certificate.execution_certificate_hash,
            admission_certificate.external_parameters_hash,
            admission_certificate.resolved_dependency_hash,
            admission_certificate.artifact_hash_groups_hash,
        ):
            if not _is_hash(value):
                return False
        if not isinstance(admission_certificate.requirement_count, int) or isinstance(admission_certificate.requirement_count, bool) or admission_certificate.requirement_count <= 0:
            return False
        if not isinstance(admission_certificate.admitted, bool):
            return False
        if not isinstance(admission_certificate.passed_requirements, tuple) or not isinstance(admission_certificate.failed_requirements, tuple):
            return False
        all_requirements = admission_certificate.passed_requirements + admission_certificate.failed_requirements
        if len(all_requirements) != admission_certificate.requirement_count:
            return False
        if any(not isinstance(value, str) or not value for value in all_requirements):
            return False
        if len(set(all_requirements)) != len(all_requirements):
            return False
        if admission_certificate.admitted != (not admission_certificate.failed_requirements):
            return False
        if policy is not None:
            if not validate_world_program_admission_policy(policy):
                return False
            if admission_certificate.policy_id != policy.policy_id or admission_certificate.policy_version != policy.policy_version:
                return False
            if admission_certificate.policy_hash != policy.policy_hash:
                return False
        if manifest is not None:
            if not validate_world_program_manifest(manifest):
                return False
            if admission_certificate.manifest_hash != manifest.manifest_hash:
                return False
            if admission_certificate.program_id != manifest.program_id or admission_certificate.program_version != manifest.program_version:
                return False
            if admission_certificate.external_parameters_hash != stable_hash(manifest.external_parameters):
                return False
            if admission_certificate.resolved_dependency_hash != stable_hash(tuple(manifest.resolved_dependencies)):
                return False
        if execution_certificate is not None:
            if not validate_world_program_certificate(execution_certificate, manifest):
                return False
            if admission_certificate.execution_certificate_hash != execution_certificate.certificate_hash:
                return False
            if admission_certificate.artifact_hash_groups_hash != stable_hash(execution_certificate.artifact_hash_groups):
                return False
        if policy is not None and manifest is not None and execution_certificate is not None:
            expected = build_world_program_admission_certificate(policy, manifest, execution_certificate)
            if admission_certificate != expected:
                return False
        return admission_certificate.certificate_hash == world_program_admission_certificate_hash(admission_certificate)
    except Exception:
        return False


def validate_world_program_evidence_bundle(bundle: WorldProgramEvidenceBundle) -> bool:
    try:
        if bundle.schema_version != WORLD_PROGRAM_EVIDENCE_BUNDLE_SCHEMA:
            return False
        if not isinstance(bundle.bundle_id, str) or not bundle.bundle_id:
            return False
        if not isinstance(bundle.bundle_version, str) or not bundle.bundle_version:
            return False
        if not validate_world_program_manifest(bundle.manifest):
            return False
        if not validate_world_program_certificate(bundle.execution_certificate, bundle.manifest):
            return False
        if not validate_world_program_admission_policy(bundle.admission_policy):
            return False
        if not validate_world_program_admission_certificate(
            bundle.admission_certificate,
            bundle.admission_policy,
            bundle.manifest,
            bundle.execution_certificate,
        ):
            return False
        if not isinstance(bundle.step_certificate_hashes, tuple) or not isinstance(bundle.receipt_hashes, tuple):
            return False
        if bundle.step_certificate_hashes != bundle.execution_certificate.step_certificate_hashes:
            return False
        if bundle.receipt_hashes != bundle.execution_certificate.receipt_hashes:
            return False
        if bundle.final_learner_snapshot_hash != bundle.execution_certificate.final_learner_snapshot_hash:
            return False
        if bundle.artifact_hash_groups != bundle.execution_certificate.artifact_hash_groups:
            return False
        if any(not _is_hash(value) for value in bundle.step_certificate_hashes):
            return False
        if any(not _is_hash(value) for value in bundle.receipt_hashes):
            return False
        if len(set(bundle.receipt_hashes)) != len(bundle.receipt_hashes):
            return False
        if not _is_hash(bundle.final_learner_snapshot_hash):
            return False
        for key, values in bundle.artifact_hash_groups.items():
            if not isinstance(key, str) or not key:
                return False
            if not isinstance(values, tuple) or any(not _is_hash(value) for value in values):
                return False
        if not isinstance(bundle.source_bundle_hashes, tuple):
            return False
        if any(not _is_hash(value) for value in bundle.source_bundle_hashes):
            return False
        return bundle.bundle_hash == world_program_evidence_bundle_hash(bundle)
    except Exception:
        return False


def validate_world_program_bundle_verification_certificate(
    certificate: WorldProgramBundleVerificationCertificate,
    bundle: WorldProgramEvidenceBundle | None = None,
) -> bool:
    try:
        if certificate.schema_version != WORLD_PROGRAM_BUNDLE_VERIFICATION_CERTIFICATE_SCHEMA:
            return False
        for value in (
            certificate.bundle_hash,
            certificate.policy_hash,
            certificate.manifest_hash,
            certificate.execution_certificate_hash,
            certificate.admission_certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if not isinstance(certificate.verifier_id, str) or not certificate.verifier_id:
            return False
        if not isinstance(certificate.verifier_version, str) or not certificate.verifier_version:
            return False
        if not isinstance(certificate.input_attestation_hashes, tuple):
            return False
        if any(not _is_hash(value) for value in certificate.input_attestation_hashes):
            return False
        if not isinstance(certificate.requirement_count, int) or isinstance(certificate.requirement_count, bool) or certificate.requirement_count <= 0:
            return False
        if not isinstance(certificate.verified, bool):
            return False
        if not isinstance(certificate.passed_requirements, tuple) or not isinstance(certificate.failed_requirements, tuple):
            return False
        all_requirements = certificate.passed_requirements + certificate.failed_requirements
        if len(all_requirements) != certificate.requirement_count:
            return False
        if any(not isinstance(value, str) or not value for value in all_requirements):
            return False
        if len(set(all_requirements)) != len(all_requirements):
            return False
        if certificate.verified != (not certificate.failed_requirements):
            return False
        if bundle is not None:
            if not validate_world_program_evidence_bundle(bundle):
                return False
            if certificate.bundle_hash != bundle.bundle_hash:
                return False
            if certificate.policy_hash != bundle.admission_policy.policy_hash:
                return False
            if certificate.manifest_hash != bundle.manifest.manifest_hash:
                return False
            if certificate.execution_certificate_hash != bundle.execution_certificate.certificate_hash:
                return False
            if certificate.admission_certificate_hash != bundle.admission_certificate.certificate_hash:
                return False
            if certificate.input_attestation_hashes != _bundle_input_attestation_hashes(bundle):
                return False
            expected = build_world_program_bundle_verification_certificate(
                bundle,
                verifier_id=certificate.verifier_id,
                verifier_version=certificate.verifier_version,
            )
            if certificate != expected:
                return False
        return certificate.certificate_hash == world_program_bundle_verification_certificate_hash(certificate)
    except Exception:
        return False


def validate_world_program_replay_step(
    step: WorldProgramReplayStep,
    *,
    expected_index: int | None = None,
    ledger_head: str | None = None,
    previous_learner_snapshot: WorldLearnerSnapshot | None = None,
) -> bool:
    try:
        if step.schema_version != WORLD_PROGRAM_REPLAY_STEP_SCHEMA:
            return False
        if not isinstance(step.step_index, int) or isinstance(step.step_index, bool) or step.step_index < 0:
            return False
        if expected_index is not None and step.step_index != expected_index:
            return False
        if not _is_hash(step.step_hash) or step.step_hash != world_program_replay_step_hash(step):
            return False
        if stable_hash(step.trace) != step.receipt.proposal_trace_hash:
            return False
        if stable_hash(step.candidate) != step.receipt.typed_candidate_hash:
            return False
        if not step.receipt.static_valid():
            return False
        if not validate_world_model_step_certificate(step.certificate):
            return False
        if not validate_world_learner_snapshot(step.pre_learner_snapshot):
            return False
        if not validate_world_learner_snapshot(step.learner_snapshot):
            return False
        if not validate_world_learner_update_certificate(step.learner_update_certificate):
            return False
        if not validate_world_learner_delta_certificate(step.learner_delta_certificate):
            return False
        if previous_learner_snapshot is not None and step.pre_learner_snapshot.snapshot_hash != previous_learner_snapshot.snapshot_hash:
            return False
        if not audit_world_model_step(
            step.receipt,
            step.certificate,
            ledger_head=ledger_head,
            learner_snapshot=step.learner_snapshot,
            learner_update_certificate=step.learner_update_certificate,
        ):
            return False
        if not audit_world_learner_update(
            step.receipt,
            step.pre_learner_snapshot,
            step.learner_snapshot,
            step.learner_update_certificate,
        ):
            return False
        return audit_world_learner_delta(
            step.pre_learner_snapshot,
            step.learner_snapshot,
            step.learner_update_certificate,
            step.learner_delta_certificate,
        )
    except Exception:
        return False


def validate_world_program_replay_package(replay_package: WorldProgramReplayPackage) -> bool:
    try:
        if replay_package.schema_version != WORLD_PROGRAM_REPLAY_PACKAGE_SCHEMA:
            return False
        if not isinstance(replay_package.package_id, str) or not replay_package.package_id:
            return False
        if not isinstance(replay_package.package_version, str) or not replay_package.package_version:
            return False
        if not validate_world_program_evidence_bundle(replay_package.evidence_bundle):
            return False
        if not isinstance(replay_package.steps, tuple) or not replay_package.steps:
            return False
        execution_certificate = replay_package.evidence_bundle.execution_certificate
        if len(replay_package.steps) != execution_certificate.step_count:
            return False
        if not all(isinstance(values, tuple) for values in (
            replay_package.step_hashes,
            replay_package.step_certificate_hashes,
            replay_package.receipt_hashes,
            replay_package.learner_update_certificate_hashes,
            replay_package.learner_delta_certificate_hashes,
        )):
            return False
        if len(replay_package.step_hashes) != len(replay_package.steps):
            return False
        if len(replay_package.learner_update_certificate_hashes) != len(replay_package.steps):
            return False
        if len(replay_package.learner_delta_certificate_hashes) != len(replay_package.steps):
            return False
        if replay_package.step_certificate_hashes != execution_certificate.step_certificate_hashes:
            return False
        if replay_package.receipt_hashes != execution_certificate.receipt_hashes:
            return False
        if replay_package.final_learner_snapshot_hash != execution_certificate.final_learner_snapshot_hash:
            return False
        if any(not _is_hash(value) for value in replay_package.step_hashes):
            return False
        if any(not _is_hash(value) for value in replay_package.learner_update_certificate_hashes):
            return False
        if any(not _is_hash(value) for value in replay_package.learner_delta_certificate_hashes):
            return False

        head = GENESIS_HEAD
        previous_snapshot: WorldLearnerSnapshot | None = None
        for index, step in enumerate(replay_package.steps):
            if step.receipt.parent_head != head:
                return False
            head = chain_hash(head, step.receipt.receipt_hash)
            if not validate_world_program_replay_step(
                step,
                expected_index=index,
                ledger_head=head,
                previous_learner_snapshot=previous_snapshot,
            ):
                return False
            previous_snapshot = step.learner_snapshot

        if replay_package.ledger_head != head or replay_package.ledger_head != execution_certificate.ledger_head:
            return False
        if replay_package.step_hashes != tuple(step.step_hash for step in replay_package.steps):
            return False
        if replay_package.step_certificate_hashes != tuple(step.certificate.certificate_hash for step in replay_package.steps):
            return False
        if replay_package.receipt_hashes != tuple(step.receipt.receipt_hash for step in replay_package.steps):
            return False
        if replay_package.learner_update_certificate_hashes != tuple(
            step.learner_update_certificate.certificate_hash for step in replay_package.steps
        ):
            return False
        if replay_package.learner_delta_certificate_hashes != tuple(
            step.learner_delta_certificate.certificate_hash for step in replay_package.steps
        ):
            return False
        if replay_package.final_learner_snapshot_hash != replay_package.steps[-1].learner_snapshot.snapshot_hash:
            return False
        if not _is_hash(replay_package.package_body_hash) or replay_package.package_body_hash != world_program_replay_package_body_hash(replay_package):
            return False
        if not _is_hash(replay_package.package_hash):
            return False
        return replay_package.package_hash == world_program_replay_package_hash(replay_package)
    except Exception:
        return False


def validate_world_program_replay_verification_certificate(
    certificate: WorldProgramReplayVerificationCertificate,
    replay_package: WorldProgramReplayPackage | None = None,
) -> bool:
    try:
        if certificate.schema_version != WORLD_PROGRAM_REPLAY_VERIFICATION_CERTIFICATE_SCHEMA:
            return False
        for value in (
            certificate.package_hash,
            certificate.evidence_bundle_hash,
            certificate.package_body_hash,
            certificate.ledger_head,
            certificate.final_learner_snapshot_hash,
            certificate.certificate_hash,
        ):
            if not _is_hash(value):
                return False
        if not isinstance(certificate.verifier_id, str) or not certificate.verifier_id:
            return False
        if not isinstance(certificate.verifier_version, str) or not certificate.verifier_version:
            return False
        for values in (
            certificate.step_hashes,
            certificate.step_certificate_hashes,
            certificate.receipt_hashes,
            certificate.learner_update_certificate_hashes,
            certificate.learner_delta_certificate_hashes,
        ):
            if not isinstance(values, tuple) or any(not _is_hash(value) for value in values):
                return False
        if not isinstance(certificate.requirement_count, int) or isinstance(certificate.requirement_count, bool) or certificate.requirement_count <= 0:
            return False
        if not isinstance(certificate.replay_verified, bool):
            return False
        if not isinstance(certificate.passed_requirements, tuple) or not isinstance(certificate.failed_requirements, tuple):
            return False
        all_requirements = certificate.passed_requirements + certificate.failed_requirements
        if len(all_requirements) != certificate.requirement_count:
            return False
        if any(not isinstance(value, str) or not value for value in all_requirements):
            return False
        if len(set(all_requirements)) != len(all_requirements):
            return False
        if certificate.replay_verified != (not certificate.failed_requirements):
            return False
        if replay_package is not None:
            if not validate_world_program_replay_package(replay_package):
                return False
            if certificate.package_hash != replay_package.package_hash:
                return False
            if certificate.evidence_bundle_hash != replay_package.evidence_bundle.bundle_hash:
                return False
            if certificate.package_body_hash != replay_package.package_body_hash:
                return False
            if certificate.ledger_head != replay_package.ledger_head:
                return False
            if certificate.final_learner_snapshot_hash != replay_package.final_learner_snapshot_hash:
                return False
            if certificate.step_hashes != replay_package.step_hashes:
                return False
            if certificate.step_certificate_hashes != replay_package.step_certificate_hashes:
                return False
            if certificate.receipt_hashes != replay_package.receipt_hashes:
                return False
            if certificate.learner_update_certificate_hashes != replay_package.learner_update_certificate_hashes:
                return False
            if certificate.learner_delta_certificate_hashes != replay_package.learner_delta_certificate_hashes:
                return False
            expected = build_world_program_replay_verification_certificate(
                replay_package,
                verifier_id=certificate.verifier_id,
                verifier_version=certificate.verifier_version,
            )
            if certificate != expected:
                return False
        return certificate.certificate_hash == world_program_replay_verification_certificate_hash(certificate)
    except Exception:
        return False


def world_program_manifest_hash(manifest: WorldProgramManifest | Mapping[str, Any]) -> str:
    if isinstance(manifest, WorldProgramManifest):
        data = asdict(manifest)
    else:
        data = dict(manifest)
    data.pop("manifest_hash", None)
    return stable_hash(data)


def world_program_admission_policy_hash(policy: WorldProgramAdmissionPolicy | Mapping[str, Any]) -> str:
    if isinstance(policy, WorldProgramAdmissionPolicy):
        data = asdict(policy)
    else:
        data = dict(policy)
    data.pop("policy_hash", None)
    return stable_hash(data)


def world_program_certificate_hash(certificate: WorldProgramCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, WorldProgramCertificate):
        data = asdict(certificate)
    else:
        data = dict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def world_program_admission_certificate_hash(certificate: WorldProgramAdmissionCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, WorldProgramAdmissionCertificate):
        data = asdict(certificate)
    else:
        data = dict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def world_program_evidence_bundle_hash(bundle: WorldProgramEvidenceBundle | Mapping[str, Any]) -> str:
    if isinstance(bundle, WorldProgramEvidenceBundle):
        data = asdict(bundle)
    else:
        data = dict(bundle)
    data.pop("bundle_hash", None)
    return stable_hash(data)


def world_program_bundle_verification_certificate_hash(
    certificate: WorldProgramBundleVerificationCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, WorldProgramBundleVerificationCertificate):
        data = asdict(certificate)
    else:
        data = dict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def world_program_replay_step_hash(step: WorldProgramReplayStep | Mapping[str, Any]) -> str:
    if isinstance(step, WorldProgramReplayStep):
        data = asdict(step)
    else:
        data = dict(step)
    data.pop("step_hash", None)
    return stable_hash(data)


def world_program_replay_package_body_hash(package: WorldProgramReplayPackage | Mapping[str, Any]) -> str:
    if isinstance(package, WorldProgramReplayPackage):
        return stable_hash(
            {
                "evidence_bundle_hash": package.evidence_bundle.bundle_hash,
                "steps": package.steps,
            }
        )
    data = dict(package)
    evidence_bundle = data.get("evidence_bundle") or data.get("evidenceBundle")
    if isinstance(evidence_bundle, Mapping):
        evidence_bundle_hash = evidence_bundle.get("bundle_hash") or evidence_bundle.get("bundleHash")
    else:
        evidence_bundle_hash = getattr(evidence_bundle, "bundle_hash", None)
    return stable_hash(
        {
            "evidence_bundle_hash": evidence_bundle_hash,
            "steps": data.get("steps", ()),
        }
    )


def world_program_replay_package_hash(package: WorldProgramReplayPackage | Mapping[str, Any]) -> str:
    if isinstance(package, WorldProgramReplayPackage):
        data = asdict(package)
    else:
        data = dict(package)
    data.pop("package_hash", None)
    return stable_hash(data)


def world_program_replay_verification_certificate_hash(
    certificate: WorldProgramReplayVerificationCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, WorldProgramReplayVerificationCertificate):
        data = asdict(certificate)
    else:
        data = dict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def tamper_world_program_certificate(certificate: WorldProgramCertificate) -> WorldProgramCertificate:
    tampered = replace(certificate, step_count=certificate.step_count + 1, certificate_hash="")
    return replace(tampered, certificate_hash=world_program_certificate_hash(tampered))


def tamper_world_program_admission_certificate(certificate: WorldProgramAdmissionCertificate) -> WorldProgramAdmissionCertificate:
    tampered = replace(certificate, admitted=not certificate.admitted, certificate_hash="")
    return replace(tampered, certificate_hash=world_program_admission_certificate_hash(tampered))


def tamper_world_program_evidence_bundle(bundle: WorldProgramEvidenceBundle) -> WorldProgramEvidenceBundle:
    tampered = replace(bundle, receipt_hashes=tuple(reversed(bundle.receipt_hashes)), bundle_hash="")
    return replace(tampered, bundle_hash=world_program_evidence_bundle_hash(tampered))


def tamper_world_program_bundle_verification_certificate(
    certificate: WorldProgramBundleVerificationCertificate,
) -> WorldProgramBundleVerificationCertificate:
    tampered = replace(certificate, verified=not certificate.verified, certificate_hash="")
    return replace(tampered, certificate_hash=world_program_bundle_verification_certificate_hash(tampered))


def tamper_world_program_replay_package(replay_package: WorldProgramReplayPackage) -> WorldProgramReplayPackage:
    tampered = replace(replay_package, receipt_hashes=tuple(reversed(replay_package.receipt_hashes)), package_hash="")
    tampered = replace(tampered, package_body_hash=world_program_replay_package_body_hash(tampered))
    return replace(tampered, package_hash=world_program_replay_package_hash(tampered))


def tamper_world_program_replay_verification_certificate(
    certificate: WorldProgramReplayVerificationCertificate,
) -> WorldProgramReplayVerificationCertificate:
    tampered = replace(certificate, replay_verified=not certificate.replay_verified, certificate_hash="")
    return replace(tampered, certificate_hash=world_program_replay_verification_certificate_hash(tampered))


def _evaluate_world_program_admission(
    policy: WorldProgramAdmissionPolicy,
    manifest: WorldProgramManifest,
    execution_certificate: WorldProgramCertificate,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    dependency_set = set(manifest.resolved_dependencies)
    artifact_groups = execution_certificate.artifact_hash_groups
    checks = (
        ("policy_valid", validate_world_program_admission_policy(policy)),
        ("manifest_valid", validate_world_program_manifest(manifest)),
        ("execution_certificate_valid", validate_world_program_certificate(execution_certificate, manifest)),
        ("build_type_allowed", _allowed(policy.allowed_build_types, manifest.build_type)),
        ("program_id_allowed", _allowed(policy.allowed_program_ids, manifest.program_id)),
        ("program_version_allowed", _allowed(policy.allowed_program_versions, manifest.program_version)),
        ("proposer_allowed", _allowed(policy.allowed_proposer_ids, manifest.proposer_id)),
        ("projector_allowed", _allowed(policy.allowed_projector_ids, manifest.projector_id)),
        ("learner_allowed", _allowed(policy.allowed_learner_ids, manifest.learner_id)),
        ("verifier_allowed", _allowed(policy.allowed_verifier_ids, manifest.verifier_id)),
        ("input_schema_allowed", _allowed(policy.allowed_input_schemas, manifest.input_schema)),
        ("candidate_schema_allowed", _allowed(policy.allowed_candidate_schemas, manifest.candidate_schema)),
        ("required_dependencies_present", all(dependency in dependency_set for dependency in policy.required_dependencies)),
        (
            "required_artifacts_present",
            all(key in artifact_groups and len(artifact_groups[key]) > 0 for key in policy.required_artifact_keys),
        ),
        ("min_step_count", execution_certificate.step_count >= policy.min_step_count),
        ("min_committed_count", execution_certificate.committed_count >= policy.min_committed_count),
        ("min_rejected_count", execution_certificate.rejected_count >= policy.min_rejected_count),
        ("invalid_commit_bound", execution_certificate.invalid_commit_count <= policy.max_invalid_commit_count),
        ("replay_rollback_rate_bound", execution_certificate.replay_rollback_rate >= policy.min_replay_rollback_rate),
    )
    passed = tuple(key for key, ok in checks if ok)
    failed = tuple(key for key, ok in checks if not ok)
    return passed, failed


def _evaluate_world_program_bundle_verification(
    bundle: WorldProgramEvidenceBundle,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    checks = (
        ("bundle_valid", validate_world_program_evidence_bundle(bundle)),
        ("manifest_valid", validate_world_program_manifest(bundle.manifest)),
        ("execution_certificate_valid", validate_world_program_certificate(bundle.execution_certificate, bundle.manifest)),
        ("admission_policy_valid", validate_world_program_admission_policy(bundle.admission_policy)),
        (
            "admission_certificate_valid",
            validate_world_program_admission_certificate(
                bundle.admission_certificate,
                bundle.admission_policy,
                bundle.manifest,
                bundle.execution_certificate,
            ),
        ),
        ("admission_certificate_admitted", bundle.admission_certificate.admitted),
        ("step_hashes_bound", bundle.step_certificate_hashes == bundle.execution_certificate.step_certificate_hashes),
        ("receipt_hashes_bound", bundle.receipt_hashes == bundle.execution_certificate.receipt_hashes),
        ("learner_snapshot_bound", bundle.final_learner_snapshot_hash == bundle.execution_certificate.final_learner_snapshot_hash),
        ("artifact_groups_bound", bundle.artifact_hash_groups == bundle.execution_certificate.artifact_hash_groups),
        ("input_attestations_bound", all(_is_hash(value) for value in _bundle_input_attestation_hashes(bundle))),
    )
    passed = tuple(key for key, ok in checks if ok)
    failed = tuple(key for key, ok in checks if not ok)
    return passed, failed


def _evaluate_world_program_replay_verification(
    replay_package: WorldProgramReplayPackage,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    execution_certificate = replay_package.evidence_bundle.execution_certificate
    step_count_matches = len(replay_package.steps) == execution_certificate.step_count
    trace_hashes_bound = all(stable_hash(step.trace) == step.receipt.proposal_trace_hash for step in replay_package.steps)
    candidate_hashes_bound = all(stable_hash(step.candidate) == step.receipt.typed_candidate_hash for step in replay_package.steps)
    step_certificates_valid = all(validate_world_model_step_certificate(step.certificate) for step in replay_package.steps)
    receipts_valid = all(step.receipt.static_valid() for step in replay_package.steps)
    learner_updates_valid = all(validate_world_learner_update_certificate(step.learner_update_certificate) for step in replay_package.steps)
    learner_deltas_valid = all(validate_world_learner_delta_certificate(step.learner_delta_certificate) for step in replay_package.steps)
    learner_lineage_bound = bool(replay_package.steps) and (
        replay_package.final_learner_snapshot_hash == replay_package.steps[-1].learner_snapshot.snapshot_hash
    )
    checks = (
        ("replay_package_valid", validate_world_program_replay_package(replay_package)),
        ("evidence_bundle_valid", validate_world_program_evidence_bundle(replay_package.evidence_bundle)),
        ("admission_certificate_admitted", replay_package.evidence_bundle.admission_certificate.admitted),
        ("step_count_matches_execution", step_count_matches),
        ("receipt_hashes_bound", replay_package.receipt_hashes == execution_certificate.receipt_hashes),
        ("step_certificate_hashes_bound", replay_package.step_certificate_hashes == execution_certificate.step_certificate_hashes),
        ("final_learner_snapshot_bound", replay_package.final_learner_snapshot_hash == execution_certificate.final_learner_snapshot_hash),
        ("ledger_head_bound", replay_package.ledger_head == execution_certificate.ledger_head),
        ("trace_hashes_bound", trace_hashes_bound),
        ("candidate_hashes_bound", candidate_hashes_bound),
        ("receipts_valid", receipts_valid),
        ("step_certificates_valid", step_certificates_valid),
        ("learner_updates_valid", learner_updates_valid),
        ("learner_deltas_valid", learner_deltas_valid),
        ("learner_lineage_bound", learner_lineage_bound),
        ("package_body_hash_bound", replay_package.package_body_hash == world_program_replay_package_body_hash(replay_package)),
    )
    passed = tuple(key for key, ok in checks if ok)
    failed = tuple(key for key, ok in checks if not ok)
    return passed, failed


def _bundle_input_attestation_hashes(bundle: WorldProgramEvidenceBundle) -> tuple[str, ...]:
    return (
        bundle.manifest.manifest_hash,
        bundle.execution_certificate.certificate_hash,
        bundle.admission_policy.policy_hash,
        bundle.admission_certificate.certificate_hash,
        stable_hash(bundle.step_certificate_hashes),
        stable_hash(bundle.receipt_hashes),
        bundle.final_learner_snapshot_hash,
        stable_hash(bundle.artifact_hash_groups),
    )


def _ledger_head_from_replay_steps(steps: tuple[WorldProgramReplayStep, ...]) -> str:
    head = GENESIS_HEAD
    for step in steps:
        if step.receipt.parent_head != head:
            return ""
        head = chain_hash(head, step.receipt.receipt_hash)
    return head


def _allowed(allowed_values: tuple[str, ...], value: str) -> bool:
    return not allowed_values or value in allowed_values


def _dedupe_strings(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        text = str(value)
        if text not in result:
            result.append(text)
    return tuple(result)


def _component_value(component: Any, snake_name: str, camel_name: str, fallback: str) -> str:
    if component is None:
        return fallback
    value = getattr(component, snake_name, None)
    if value is None:
        value = getattr(component, camel_name, None)
    if value is None:
        value = fallback
    return str(value)


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)
