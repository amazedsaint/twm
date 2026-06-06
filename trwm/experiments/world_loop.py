from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping

from ..core import Ledger, ProposalTrace, TransactionEngine, TypedCandidate
from ..macro import Macro
from ..rrlm import (
    RrlmMacroProposer,
    RrlmMacroSnapshot,
    RrlmProposalCertificate,
    RrlmTransportCertificate,
    build_rrlm_proposal_certificate,
    build_rrlm_transport_certificate,
    rrlm_proposal_certificate_hash,
    validate_rrlm_macro_snapshot,
    validate_rrlm_proposal_certificate,
    validate_rrlm_transport_certificate,
)
from ..world import (
    TransactionalWorldModelRuntime,
    audit_world_learner_delta,
    audit_world_learner_lineage,
    audit_world_learner_merge,
    audit_world_learner_update,
    audit_world_model_step,
    build_world_learner_lineage_certificate,
    merge_world_learner_snapshots,
    validate_world_learner_delta_certificate,
    validate_world_learner_lineage_certificate,
    validate_world_learner_merge_certificate,
    validate_world_learner_snapshot,
    validate_world_learner_update_certificate,
    validate_world_model_step_certificate,
    world_learner_delta_certificate_hash,
    world_learner_lineage_certificate_hash,
    world_learner_update_certificate_hash,
)
from ..world_program import (
    audit_world_program_admission,
    audit_world_program_bundle_verification,
    audit_world_program_certificate,
    audit_world_program_evidence_bundle,
    audit_world_program_replay_package,
    audit_world_program_replay_verification,
    build_world_program_admission_certificate,
    build_world_program_admission_policy,
    build_world_program_bundle_verification_certificate,
    build_world_program_certificate,
    build_world_program_evidence_bundle,
    build_world_program_manifest,
    build_world_program_replay_package,
    build_world_program_replay_verification_certificate,
    tamper_world_program_admission_certificate,
    tamper_world_program_bundle_verification_certificate,
    tamper_world_program_certificate,
    tamper_world_program_evidence_bundle,
    tamper_world_program_replay_package,
    tamper_world_program_replay_verification_certificate,
    validate_world_program_admission_certificate,
    validate_world_program_admission_policy,
    validate_world_program_bundle_verification_certificate,
    validate_world_program_certificate,
    validate_world_program_evidence_bundle,
    validate_world_program_manifest,
    validate_world_program_replay_package,
    validate_world_program_replay_verification_certificate,
)
from .repair_simulator import ScalarProgramAdapter, make_scalar_candidate


@dataclass(frozen=True)
class WorldLoopReport:
    schema_version: str
    step_count: int
    first_committed: bool
    second_committed: bool
    first_decision: str
    second_decision: str
    learner_update_count: int
    accepted_count: int
    rejected_count: int
    certificate_valid_count: int
    audit_valid_count: int
    proposer_improved_from_residual: bool
    hard_verifier_owned_commit: bool
    learner_snapshot_valid_count: int
    step_certificate_binds_learner_state: bool
    learner_update_certificate_valid_count: int
    learner_update_audit_valid_count: int
    step_certificate_binds_learner_update: bool
    learner_update_tamper_detected: bool
    learner_delta_certificate_valid_count: int
    learner_delta_audit_valid_count: int
    learner_delta_binds_updates: bool
    learner_delta_tamper_detected: bool
    learner_lineage_certificate_valid: bool
    learner_lineage_audit_valid: bool
    learner_lineage_binds_updates: bool
    learner_lineage_tamper_detected: bool
    learner_merge_certificate_valid: bool
    learner_merge_audit_valid: bool
    learner_merge_disjoint_receipts: bool
    learner_merge_partial_overlap_valid: bool
    learner_merge_partial_overlap_audit_valid: bool
    learner_merge_partial_overlap_counts_shared_once: bool
    learner_merge_partial_overlap_requires_deltas: bool
    learner_merge_tamper_detected: bool
    learner_merge_conflict_detected: bool
    rrlm_world_first_committed: bool
    rrlm_world_second_committed: bool
    rrlm_world_selected_repair_macro: bool
    rrlm_world_proposal_certificate_valid: bool
    rrlm_world_transport_certificate_valid: bool
    rrlm_world_artifacts_bound_to_receipts: bool
    rrlm_world_rejected_macro_penalized: bool
    rrlm_world_tamper_detected: bool
    world_program_manifest_valid: bool
    world_program_certificate_valid: bool
    world_program_audit_valid: bool
    world_program_binds_rrlm_artifacts: bool
    world_program_tamper_detected: bool
    world_program_admission_policy_valid: bool
    world_program_admission_certificate_valid: bool
    world_program_admission_audit_valid: bool
    world_program_admitted: bool
    world_program_admission_rejects_unmet_requirements: bool
    world_program_admission_tamper_detected: bool
    world_program_evidence_bundle_valid: bool
    world_program_evidence_bundle_audit_valid: bool
    world_program_bundle_verification_certificate_valid: bool
    world_program_bundle_verified: bool
    world_program_bundle_tamper_detected: bool
    world_program_replay_package_valid: bool
    world_program_replay_package_audit_valid: bool
    world_program_replay_verification_certificate_valid: bool
    world_program_replay_verified: bool
    world_program_replay_tamper_detected: bool
    tamper_detected: bool
    learner_snapshot_tamper_detected: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float


class ResidualRepairProposer:
    proposer_id = "scalar_residual_repair_proposer"
    proposer_version = "1.0"

    def __init__(self, target: int, initial_guess: int):
        self.target = target
        self.initial_guess = initial_guess
        self.learned_repair: Mapping[str, Any] | None = None

    def propose(self, _state: Mapping[str, Any], _budget: Mapping[str, Any]) -> ProposalTrace:
        program = [{"op": "set", "value": self.initial_guess}]
        if self.learned_repair is not None:
            program.append(dict(self.learned_repair))
        return ProposalTrace(
            branch_id=f"world-loop-{len(program)}",
            actions=tuple(program),
            seeds=("world-loop", len(program)),
            model_version=self.proposer_version,
        )


class ScalarProgramProjector:
    projector_id = "scalar_program_projector"
    projector_version = "1.0"

    def __init__(self, target: int):
        self.target = target

    def project(self, _state: Mapping[str, Any], trace: ProposalTrace) -> TypedCandidate:
        return make_scalar_candidate("world-loop", self.target, trace.actions)


class ResidualRepairLearner:
    learner_id = "scalar_residual_repair_learner"
    learner_version = "1.0"

    def __init__(self, proposer: ResidualRepairProposer):
        self.proposer = proposer
        self.update_count = 0
        self.rejected_count = 0
        self.accepted_count = 0

    def update(self, receipt) -> None:
        self.update_count += 1
        if receipt.hard_result.accepted and receipt.committed:
            self.accepted_count += 1
            return
        if receipt.hard_result.rejected:
            self.rejected_count += 1
            residual = receipt.hard_result.residual
            if isinstance(residual, Mapping) and isinstance(residual.get("repair"), Mapping):
                self.proposer.learned_repair = dict(residual["repair"])

    def snapshot_state(self) -> Mapping[str, Any]:
        return {
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "learned_repair": dict(self.proposer.learned_repair) if self.proposer.learned_repair is not None else None,
            "proposer_id": self.proposer.proposer_id,
            "update_count": self.update_count,
        }


class RrlmScalarTraceProposer:
    proposer_id = "rrlm_macro_proposer"
    proposer_version = "1.0"

    def __init__(self, target: int, initial_guess: int = 0):
        self.target = target
        self.initial_guess = initial_guess
        self.rrlm = RrlmMacroProposer()
        self.macros = (
            Macro(
                "set0",
                ({"op": "set", "value": initial_guess},),
                context="scalar-world",
                model_version="rrlm.scalar.world.v1",
            ),
            Macro(
                "set0-add-target",
                (
                    {"op": "set", "value": initial_guess},
                    {"op": "add", "value": target - initial_guess},
                ),
                context="scalar-world",
                model_version="rrlm.scalar.world.v1",
            ),
        )
        self.last_snapshot: RrlmMacroSnapshot | None = None
        self.last_proposal_certificate: RrlmProposalCertificate | None = None
        self.last_transport_certificate: RrlmTransportCertificate | None = None
        self.last_selected_macro: Macro | None = None

    def propose(self, _state: Mapping[str, Any], _budget: Mapping[str, Any]) -> ProposalTrace:
        snapshot = self.rrlm.snapshot()
        ranking = self.rrlm.propose("scalar-world", self.macros)
        proposal_certificate = build_rrlm_proposal_certificate(snapshot, ranking)
        transport_certificate = build_rrlm_transport_certificate(proposal_certificate)
        selected = ranking.ranked_macros[0]
        self.last_snapshot = snapshot
        self.last_proposal_certificate = proposal_certificate
        self.last_transport_certificate = transport_certificate
        self.last_selected_macro = selected
        return ProposalTrace(
            branch_id=f"rrlm-world-{selected.macro_id}",
            actions=selected.steps,
            seeds=("rrlm-world", selected.macro_id, proposal_certificate.certificate_hash),
            model_version=self.proposer_version,
        )


class RrlmScalarProgramProjector:
    projector_id = "rrlm_scalar_program_projector"
    projector_version = "1.0"

    def __init__(self, target: int, proposer: RrlmScalarTraceProposer):
        self.target = target
        self.proposer = proposer

    def project(self, _state: Mapping[str, Any], trace: ProposalTrace) -> TypedCandidate:
        selected = self.proposer.last_selected_macro
        snapshot = self.proposer.last_snapshot
        proposal_certificate = self.proposer.last_proposal_certificate
        transport_certificate = self.proposer.last_transport_certificate
        if selected is None or snapshot is None or proposal_certificate is None or transport_certificate is None:
            raise ValueError("RRLM scalar projector requires a preceding RRLM proposal")
        candidate = make_scalar_candidate("scalar-world", self.target, trace.actions)
        return TypedCandidate(
            payload={
                **candidate.payload,
                "macro_id": selected.macro_id,
                "macro": tuple(dict(step) for step in selected.steps),
            },
            type_name=candidate.type_name,
            schema_version=candidate.schema_version,
            hashes={
                "rrlm_snapshot_hash": snapshot.snapshot_hash,
                "rrlm_proposal_certificate_hash": proposal_certificate.certificate_hash,
                "rrlm_transport_certificate_hash": transport_certificate.certificate_hash,
            },
        )


class RrlmWorldReceiptLearner:
    learner_id = "rrlm_world_receipt_learner"
    learner_version = "1.0"

    def __init__(self, proposer: RrlmScalarTraceProposer):
        self.proposer = proposer
        self.update_count = 0

    def update(self, receipt) -> None:
        self.proposer.rrlm.update(receipt)
        self.update_count += 1

    def snapshot_state(self) -> Mapping[str, Any]:
        snapshot = self.proposer.rrlm.snapshot()
        return {
            "rrlm_snapshot_hash": snapshot.snapshot_hash,
            "rows": tuple(asdict(row) for row in snapshot.rows),
            "source_receipt_hashes": snapshot.source_receipt_hashes,
            "update_count": self.update_count,
        }


def run_world_loop_benchmark() -> WorldLoopReport:
    target = 5
    seed_state, engine, runtime, learner = _build_world_loop_runtime(target, episode=0)

    first = runtime.step(seed_state)
    second = runtime.step(first.state)
    other_seed_state, _other_engine, other_runtime, _other_learner = _build_world_loop_runtime(target, episode=1)
    other_runtime.step(other_seed_state)
    other_second = other_runtime.step(other_seed_state)
    partial_right = _fork_world_loop_from_snapshot(first, target=target, episode=2)
    certificates = (first.certificate, second.certificate)
    receipts = (first.receipt, second.receipt)
    learner_snapshots = (first.learner_snapshot, second.learner_snapshot)
    pre_learner_snapshots = (first.pre_learner_snapshot, second.pre_learner_snapshot)
    learner_update_certificates = (first.learner_update_certificate, second.learner_update_certificate)
    learner_delta_certificates = (first.learner_delta_certificate, second.learner_delta_certificate)
    learner_lineage = build_world_learner_lineage_certificate(
        first.pre_learner_snapshot,
        second.learner_snapshot,
        learner_update_certificates,
    )
    learner_merge = merge_world_learner_snapshots(second.learner_snapshot, other_second.learner_snapshot)
    learner_partial_merge = merge_world_learner_snapshots(
        second.learner_snapshot,
        partial_right.learner_snapshot,
        base_snapshot=first.learner_snapshot,
        left_delta_certificates=(second.learner_delta_certificate,),
        right_delta_certificates=(partial_right.learner_delta_certificate,),
    )
    tampered_merge_certificate = replace(learner_merge.certificate, merged_update_count=3, certificate_hash="")
    conflicting_snapshot = replace(
        other_second.learner_snapshot,
        learner_state={**other_second.learner_snapshot.learner_state, "learned_repair": {"op": "add", "value": target + 1}},
        learner_state_hash="",
        snapshot_hash="",
    )
    tampered = replace(second.certificate, committed=False, certificate_hash="")
    tampered_snapshot = replace(second.learner_snapshot, update_count=99, snapshot_hash="")
    tampered_update_certificate = replace(second.learner_update_certificate, post_update_count=4, certificate_hash="")
    tampered_update_certificate = replace(
        tampered_update_certificate,
        certificate_hash=world_learner_update_certificate_hash(tampered_update_certificate),
    )
    tampered_delta_certificate = replace(second.learner_delta_certificate, delta_op_count=9, certificate_hash="")
    tampered_delta_certificate = replace(
        tampered_delta_certificate,
        certificate_hash=world_learner_delta_certificate_hash(tampered_delta_certificate),
    )
    tampered_lineage_certificate = replace(learner_lineage, applied_update_count=3, certificate_hash="")
    tampered_lineage_certificate = replace(
        tampered_lineage_certificate,
        certificate_hash=world_learner_lineage_certificate_hash(tampered_lineage_certificate),
    )
    rrlm_world = _run_rrlm_world_loop(target)
    tampered_rrlm_world_proposal = replace(
        rrlm_world["second_proposal_certificate"],
        scores=(rrlm_world["second_proposal_certificate"].scores[0] + 1,)
        + rrlm_world["second_proposal_certificate"].scores[1:],
        certificate_hash="",
    )
    tampered_rrlm_world_proposal = replace(
        tampered_rrlm_world_proposal,
        certificate_hash=rrlm_proposal_certificate_hash(tampered_rrlm_world_proposal),
    )

    return WorldLoopReport(
        schema_version=first.certificate.schema_version,
        step_count=2,
        first_committed=first.committed,
        second_committed=second.committed,
        first_decision=first.reason,
        second_decision=second.reason,
        learner_update_count=learner.update_count,
        accepted_count=learner.accepted_count,
        rejected_count=learner.rejected_count,
        certificate_valid_count=sum(1 for certificate in certificates if validate_world_model_step_certificate(certificate)),
        audit_valid_count=sum(
            1
            for receipt, certificate, snapshot, update_certificate in zip(
                receipts,
                certificates,
                learner_snapshots,
                learner_update_certificates,
            )
            if audit_world_model_step(
                receipt,
                certificate,
                learner_snapshot=snapshot,
                learner_update_certificate=update_certificate,
            )
        ),
        proposer_improved_from_residual=second.candidate.payload["program"][-1] == {"op": "add", "value": target},
        hard_verifier_owned_commit=second.receipt.hard_result.accepted and second.receipt.committed and second.receipt.commit_decision == "commit",
        learner_snapshot_valid_count=sum(1 for snapshot in learner_snapshots if validate_world_learner_snapshot(snapshot)),
        step_certificate_binds_learner_state=all(
            certificate.learner_state_hash == snapshot.learner_state_hash
            and certificate.learner_snapshot_hash == snapshot.snapshot_hash
            and certificate.learner_update_count == snapshot.update_count
            for certificate, snapshot in zip(certificates, learner_snapshots)
        ),
        learner_update_certificate_valid_count=sum(
            1 for certificate in learner_update_certificates if validate_world_learner_update_certificate(certificate)
        ),
        learner_update_audit_valid_count=sum(
            1
            for receipt, pre_snapshot, post_snapshot, certificate in zip(
                receipts,
                pre_learner_snapshots,
                learner_snapshots,
                learner_update_certificates,
            )
            if audit_world_learner_update(receipt, pre_snapshot, post_snapshot, certificate)
        ),
        step_certificate_binds_learner_update=all(
            certificate.learner_update_certificate_hash == update_certificate.certificate_hash
            for certificate, update_certificate in zip(certificates, learner_update_certificates)
        ),
        learner_update_tamper_detected=not validate_world_learner_update_certificate(tampered_update_certificate),
        learner_delta_certificate_valid_count=sum(
            1 for certificate in learner_delta_certificates if validate_world_learner_delta_certificate(certificate)
        ),
        learner_delta_audit_valid_count=sum(
            1
            for pre_snapshot, post_snapshot, update_certificate, delta_certificate in zip(
                pre_learner_snapshots,
                learner_snapshots,
                learner_update_certificates,
                learner_delta_certificates,
            )
            if audit_world_learner_delta(pre_snapshot, post_snapshot, update_certificate, delta_certificate)
        ),
        learner_delta_binds_updates=all(
            delta_certificate.update_certificate_hash == update_certificate.certificate_hash
            for delta_certificate, update_certificate in zip(learner_delta_certificates, learner_update_certificates)
        ),
        learner_delta_tamper_detected=not validate_world_learner_delta_certificate(tampered_delta_certificate),
        learner_lineage_certificate_valid=validate_world_learner_lineage_certificate(learner_lineage),
        learner_lineage_audit_valid=audit_world_learner_lineage(
            first.pre_learner_snapshot,
            second.learner_snapshot,
            learner_update_certificates,
            learner_lineage,
        ),
        learner_lineage_binds_updates=learner_lineage.update_certificate_hashes == tuple(
            certificate.certificate_hash for certificate in learner_update_certificates
        ),
        learner_lineage_tamper_detected=not validate_world_learner_lineage_certificate(tampered_lineage_certificate),
        learner_merge_certificate_valid=validate_world_learner_merge_certificate(learner_merge.certificate),
        learner_merge_audit_valid=audit_world_learner_merge(
            second.learner_snapshot,
            other_second.learner_snapshot,
            learner_merge.merged_snapshot,
            learner_merge.certificate,
        ),
        learner_merge_disjoint_receipts=not (
            set(second.learner_snapshot.source_receipt_hashes) & set(other_second.learner_snapshot.source_receipt_hashes)
        ) and learner_merge.merged_snapshot.update_count == 4,
        learner_merge_partial_overlap_valid=validate_world_learner_merge_certificate(learner_partial_merge.certificate),
        learner_merge_partial_overlap_audit_valid=audit_world_learner_merge(
            second.learner_snapshot,
            partial_right.learner_snapshot,
            learner_partial_merge.merged_snapshot,
            learner_partial_merge.certificate,
            base_snapshot=first.learner_snapshot,
            left_delta_certificates=(second.learner_delta_certificate,),
            right_delta_certificates=(partial_right.learner_delta_certificate,),
        ),
        learner_merge_partial_overlap_counts_shared_once=(
            learner_partial_merge.certificate.merge_basis == "delta_common_prefix"
            and learner_partial_merge.certificate.shared_receipt_count == 1
            and learner_partial_merge.certificate.common_prefix_receipt_count == 1
            and learner_partial_merge.merged_snapshot.update_count == 3
            and learner_partial_merge.merged_snapshot.learner_state["accepted_count"] == 2
            and learner_partial_merge.merged_snapshot.learner_state["rejected_count"] == 1
            and learner_partial_merge.merged_snapshot.learner_state["update_count"] == 3
        ),
        learner_merge_partial_overlap_requires_deltas=_merge_conflict_detected(second.learner_snapshot, partial_right.learner_snapshot),
        learner_merge_tamper_detected=not validate_world_learner_merge_certificate(tampered_merge_certificate),
        learner_merge_conflict_detected=_merge_conflict_detected(second.learner_snapshot, conflicting_snapshot),
        rrlm_world_first_committed=rrlm_world["first"].committed,
        rrlm_world_second_committed=rrlm_world["second"].committed,
        rrlm_world_selected_repair_macro=rrlm_world["second_selected_macro_id"] == "set0-add-target",
        rrlm_world_proposal_certificate_valid=(
            validate_rrlm_macro_snapshot(rrlm_world["second_snapshot"])
            and validate_rrlm_proposal_certificate(rrlm_world["second_proposal_certificate"], rrlm_world["second_snapshot"])
        ),
        rrlm_world_transport_certificate_valid=validate_rrlm_transport_certificate(
            rrlm_world["second_transport_certificate"],
            rrlm_world["second_proposal_certificate"],
        ),
        rrlm_world_artifacts_bound_to_receipts=(
            rrlm_world["first"].candidate.hashes["rrlm_snapshot_hash"] == rrlm_world["first_snapshot"].snapshot_hash
            and rrlm_world["first"].candidate.hashes["rrlm_proposal_certificate_hash"]
            == rrlm_world["first_proposal_certificate"].certificate_hash
            and rrlm_world["first"].candidate.hashes["rrlm_transport_certificate_hash"]
            == rrlm_world["first_transport_certificate"].certificate_hash
            and rrlm_world["first"].receipt.artifact_hashes["rrlm_proposal_certificate_hash"]
            == rrlm_world["first_proposal_certificate"].certificate_hash
            and rrlm_world["second"].candidate.hashes["rrlm_snapshot_hash"] == rrlm_world["second_snapshot"].snapshot_hash
            and rrlm_world["second"].candidate.hashes["rrlm_proposal_certificate_hash"]
            == rrlm_world["second_proposal_certificate"].certificate_hash
            and rrlm_world["second"].candidate.hashes["rrlm_transport_certificate_hash"]
            == rrlm_world["second_transport_certificate"].certificate_hash
            and rrlm_world["second"].receipt.artifact_hashes["rrlm_transport_certificate_hash"]
            == rrlm_world["second_transport_certificate"].certificate_hash
            and rrlm_world["second"].certificate.typed_candidate_hash == rrlm_world["second"].receipt.typed_candidate_hash
        ),
        rrlm_world_rejected_macro_penalized=(
            rrlm_world["first_selected_macro_id"] == "set0"
            and rrlm_world["first"].receipt.hard_result.rejected
            and rrlm_world["second_proposal_certificate"].rejected_prefix_counts[1] == 1
        ),
        rrlm_world_tamper_detected=not validate_rrlm_proposal_certificate(
            tampered_rrlm_world_proposal,
            rrlm_world["second_snapshot"],
        ),
        world_program_manifest_valid=validate_world_program_manifest(rrlm_world["program_manifest"]),
        world_program_certificate_valid=validate_world_program_certificate(
            rrlm_world["program_certificate"],
            rrlm_world["program_manifest"],
        ),
        world_program_audit_valid=audit_world_program_certificate(
            rrlm_world["program_manifest"],
            (rrlm_world["first"], rrlm_world["second"]),
            rrlm_world["program_certificate"],
            ledger_head=rrlm_world["ledger_head"],
            invalid_commit_count=rrlm_world["invalid_commit_count"],
            replay_rollback_rate=rrlm_world["replay_rollback_rate"],
        ),
        world_program_binds_rrlm_artifacts=(
            rrlm_world["program_certificate"].artifact_hash_groups["rrlm_snapshot_hash"][0]
            == rrlm_world["first_snapshot"].snapshot_hash
            and rrlm_world["program_certificate"].artifact_hash_groups["rrlm_snapshot_hash"][1]
            == rrlm_world["second_snapshot"].snapshot_hash
            and rrlm_world["program_certificate"].artifact_hash_groups["rrlm_proposal_certificate_hash"][0]
            == rrlm_world["first_proposal_certificate"].certificate_hash
            and rrlm_world["program_certificate"].artifact_hash_groups["rrlm_proposal_certificate_hash"][1]
            == rrlm_world["second_proposal_certificate"].certificate_hash
            and rrlm_world["program_certificate"].artifact_hash_groups["rrlm_transport_certificate_hash"][0]
            == rrlm_world["first_transport_certificate"].certificate_hash
            and rrlm_world["program_certificate"].artifact_hash_groups["rrlm_transport_certificate_hash"][1]
            == rrlm_world["second_transport_certificate"].certificate_hash
        ),
        world_program_tamper_detected=not validate_world_program_certificate(
            tamper_world_program_certificate(rrlm_world["program_certificate"]),
            rrlm_world["program_manifest"],
        ),
        world_program_admission_policy_valid=validate_world_program_admission_policy(rrlm_world["admission_policy"]),
        world_program_admission_certificate_valid=validate_world_program_admission_certificate(
            rrlm_world["admission_certificate"],
            rrlm_world["admission_policy"],
            rrlm_world["program_manifest"],
            rrlm_world["program_certificate"],
        ),
        world_program_admission_audit_valid=audit_world_program_admission(
            rrlm_world["admission_policy"],
            rrlm_world["program_manifest"],
            rrlm_world["program_certificate"],
            rrlm_world["admission_certificate"],
        ),
        world_program_admitted=rrlm_world["admission_certificate"].admitted,
        world_program_admission_rejects_unmet_requirements=(
            validate_world_program_admission_certificate(
                rrlm_world["rejected_admission_certificate"],
                rrlm_world["rejected_admission_policy"],
                rrlm_world["program_manifest"],
                rrlm_world["program_certificate"],
            )
            and not rrlm_world["rejected_admission_certificate"].admitted
            and rrlm_world["rejected_admission_certificate"].failed_requirements == ("required_artifacts_present",)
        ),
        world_program_admission_tamper_detected=not validate_world_program_admission_certificate(
            tamper_world_program_admission_certificate(rrlm_world["admission_certificate"]),
            rrlm_world["admission_policy"],
            rrlm_world["program_manifest"],
            rrlm_world["program_certificate"],
        ),
        world_program_evidence_bundle_valid=validate_world_program_evidence_bundle(rrlm_world["evidence_bundle"]),
        world_program_evidence_bundle_audit_valid=audit_world_program_evidence_bundle(
            rrlm_world["program_manifest"],
            rrlm_world["program_certificate"],
            rrlm_world["admission_policy"],
            rrlm_world["admission_certificate"],
            rrlm_world["evidence_bundle"],
        ),
        world_program_bundle_verification_certificate_valid=validate_world_program_bundle_verification_certificate(
            rrlm_world["bundle_verification_certificate"],
            rrlm_world["evidence_bundle"],
        ),
        world_program_bundle_verified=rrlm_world["bundle_verification_certificate"].verified,
        world_program_bundle_tamper_detected=(
            not validate_world_program_evidence_bundle(tamper_world_program_evidence_bundle(rrlm_world["evidence_bundle"]))
            and not validate_world_program_bundle_verification_certificate(
                tamper_world_program_bundle_verification_certificate(rrlm_world["bundle_verification_certificate"]),
                rrlm_world["evidence_bundle"],
            )
            and not audit_world_program_bundle_verification(
                tamper_world_program_evidence_bundle(rrlm_world["evidence_bundle"]),
                rrlm_world["bundle_verification_certificate"],
            )
        ),
        world_program_replay_package_valid=validate_world_program_replay_package(rrlm_world["replay_package"]),
        world_program_replay_package_audit_valid=audit_world_program_replay_package(
            rrlm_world["evidence_bundle"],
            (rrlm_world["first"], rrlm_world["second"]),
            rrlm_world["replay_package"],
        ),
        world_program_replay_verification_certificate_valid=validate_world_program_replay_verification_certificate(
            rrlm_world["replay_verification_certificate"],
            rrlm_world["replay_package"],
        ),
        world_program_replay_verified=rrlm_world["replay_verification_certificate"].replay_verified,
        world_program_replay_tamper_detected=(
            not validate_world_program_replay_package(tamper_world_program_replay_package(rrlm_world["replay_package"]))
            and not validate_world_program_replay_verification_certificate(
                tamper_world_program_replay_verification_certificate(rrlm_world["replay_verification_certificate"]),
                rrlm_world["replay_package"],
            )
            and not audit_world_program_replay_verification(
                tamper_world_program_replay_package(rrlm_world["replay_package"]),
                rrlm_world["replay_verification_certificate"],
            )
        ),
        tamper_detected=not validate_world_model_step_certificate(tampered),
        learner_snapshot_tamper_detected=not validate_world_learner_snapshot(tampered_snapshot),
        invalid_commit_count=engine.invalid_commit_count + rrlm_world["invalid_commit_count"],
        ledger_audit=engine.ledger.audit() and rrlm_world["ledger_audit"],
        replay_rollback_rate=min(
            1.0 if engine.replay_audit(seed_state) == second.state and engine.rollback_audit(seed_state) == seed_state else 0.0,
            rrlm_world["replay_rollback_rate"],
        ),
    )


def _run_rrlm_world_loop(target: int) -> Mapping[str, Any]:
    proposer = RrlmScalarTraceProposer(target=target, initial_guess=0)
    projector = RrlmScalarProgramProjector(target=target, proposer=proposer)
    learner = RrlmWorldReceiptLearner(proposer)
    seed_state = {"episode": 100, "target": target, "solved": False}
    engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
    runtime = TransactionalWorldModelRuntime(
        engine,
        proposer,
        projector,
        learner,
    )
    first = runtime.step(seed_state)
    first_snapshot = proposer.last_snapshot
    first_proposal_certificate = proposer.last_proposal_certificate
    first_transport_certificate = proposer.last_transport_certificate
    first_selected_macro = proposer.last_selected_macro
    second = runtime.step(first.state)
    second_snapshot = proposer.last_snapshot
    second_proposal_certificate = proposer.last_proposal_certificate
    second_transport_certificate = proposer.last_transport_certificate
    second_selected_macro = proposer.last_selected_macro
    if (
        first_snapshot is None
        or first_proposal_certificate is None
        or first_transport_certificate is None
        or first_selected_macro is None
        or second_snapshot is None
        or second_proposal_certificate is None
        or second_transport_certificate is None
        or second_selected_macro is None
    ):
        raise AssertionError("RRLM world loop did not emit proposal certificates")
    replay_rollback_rate = 1.0 if engine.replay_audit(seed_state) == second.state and engine.rollback_audit(seed_state) == seed_state else 0.0
    manifest = build_world_program_manifest(
        program_id="rrlm_scalar_world_program",
        program_version="1.0",
        proposer=proposer,
        projector=projector,
        learner=learner,
        verifier_id=engine.adapter.verifier_id,
        verifier_version=engine.adapter.verifier_version,
        input_schema="scalar.program.state.v1",
        candidate_schema="scalar.program.v1",
        external_parameters={"target": target, "initial_guess": proposer.initial_guess},
        resolved_dependencies=(
            "trwm.rrlm_macro_snapshot.v1",
            "trwm.rrlm_proposal_certificate.v1",
            "trwm.rrlm_transport_certificate.v1",
        ),
    )
    program_certificate = build_world_program_certificate(
        manifest,
        (first, second),
        ledger_head=engine.ledger.head,
        invalid_commit_count=engine.invalid_commit_count,
        replay_rollback_rate=replay_rollback_rate,
    )
    admission_policy = build_world_program_admission_policy(
        policy_id="rrlm_scalar_world_program_policy",
        policy_version="1.0",
        allowed_program_ids=("rrlm_scalar_world_program",),
        allowed_program_versions=("1.0",),
        allowed_proposer_ids=(proposer.proposer_id,),
        allowed_projector_ids=(projector.projector_id,),
        allowed_learner_ids=(learner.learner_id,),
        allowed_verifier_ids=(engine.adapter.verifier_id,),
        allowed_input_schemas=("scalar.program.state.v1",),
        allowed_candidate_schemas=("scalar.program.v1",),
        required_dependencies=(
            "trwm.rrlm_macro_snapshot.v1",
            "trwm.rrlm_proposal_certificate.v1",
            "trwm.rrlm_transport_certificate.v1",
        ),
        required_artifact_keys=(
            "rrlm_snapshot_hash",
            "rrlm_proposal_certificate_hash",
            "rrlm_transport_certificate_hash",
        ),
        min_step_count=2,
        min_committed_count=1,
        min_rejected_count=1,
        max_invalid_commit_count=0,
        min_replay_rollback_rate=1.0,
    )
    admission_certificate = build_world_program_admission_certificate(admission_policy, manifest, program_certificate)
    evidence_bundle = build_world_program_evidence_bundle(
        manifest,
        program_certificate,
        admission_policy,
        admission_certificate,
        bundle_id="rrlm_scalar_world_program_evidence_bundle",
    )
    bundle_verification_certificate = build_world_program_bundle_verification_certificate(evidence_bundle)
    replay_package = build_world_program_replay_package(
        evidence_bundle,
        (first, second),
        package_id="rrlm_scalar_world_program_replay_package",
    )
    replay_verification_certificate = build_world_program_replay_verification_certificate(replay_package)
    rejected_admission_policy = build_world_program_admission_policy(
        policy_id="rrlm_scalar_world_program_missing_artifact_probe",
        policy_version="1.0",
        allowed_program_ids=("rrlm_scalar_world_program",),
        required_artifact_keys=("missing_rrlm_artifact_hash",),
    )
    rejected_admission_certificate = build_world_program_admission_certificate(
        rejected_admission_policy,
        manifest,
        program_certificate,
    )
    return {
        "first": first,
        "second": second,
        "first_snapshot": first_snapshot,
        "second_snapshot": second_snapshot,
        "first_proposal_certificate": first_proposal_certificate,
        "second_proposal_certificate": second_proposal_certificate,
        "first_transport_certificate": first_transport_certificate,
        "second_transport_certificate": second_transport_certificate,
        "first_selected_macro_id": first_selected_macro.macro_id,
        "second_selected_macro_id": second_selected_macro.macro_id,
        "program_manifest": manifest,
        "program_certificate": program_certificate,
        "admission_policy": admission_policy,
        "admission_certificate": admission_certificate,
        "evidence_bundle": evidence_bundle,
        "bundle_verification_certificate": bundle_verification_certificate,
        "replay_package": replay_package,
        "replay_verification_certificate": replay_verification_certificate,
        "rejected_admission_policy": rejected_admission_policy,
        "rejected_admission_certificate": rejected_admission_certificate,
        "ledger_head": engine.ledger.head,
        "invalid_commit_count": engine.invalid_commit_count,
        "ledger_audit": engine.ledger.audit(),
        "replay_rollback_rate": replay_rollback_rate,
    }


def _build_world_loop_runtime(target: int, episode: int) -> tuple[Mapping[str, Any], TransactionEngine, TransactionalWorldModelRuntime, ResidualRepairLearner]:
    seed_state = {"episode": episode, "target": target, "solved": False}
    proposer = ResidualRepairProposer(target=target, initial_guess=0)
    projector = ScalarProgramProjector(target=target)
    learner = ResidualRepairLearner(proposer)
    engine = TransactionEngine(ScalarProgramAdapter(), ledger=Ledger())
    runtime = TransactionalWorldModelRuntime(engine, proposer, projector, learner)
    return seed_state, engine, runtime, learner


def _fork_world_loop_from_snapshot(base_step, *, target: int, episode: int):
    proposer = ResidualRepairProposer(target=target, initial_guess=0)
    learned_repair = base_step.learner_snapshot.learner_state["learned_repair"]
    proposer.learned_repair = dict(learned_repair) if learned_repair is not None else None
    learner = ResidualRepairLearner(proposer)
    learner.accepted_count = base_step.learner_snapshot.learner_state["accepted_count"]
    learner.rejected_count = base_step.learner_snapshot.learner_state["rejected_count"]
    learner.update_count = base_step.learner_snapshot.learner_state["update_count"]
    runtime = TransactionalWorldModelRuntime(
        TransactionEngine(ScalarProgramAdapter(), ledger=Ledger()),
        proposer,
        ScalarProgramProjector(target=target),
        learner,
    )
    runtime.learner_update_count = base_step.learner_snapshot.update_count
    runtime.learner_receipt_hashes = list(base_step.learner_snapshot.source_receipt_hashes)
    return runtime.step({"episode": episode, "target": target, "solved": False})


def _merge_conflict_detected(left, right) -> bool:
    try:
        merge_world_learner_snapshots(left, right)
    except ValueError:
        return True
    return False
