from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol

from .core import ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


WORLD_MODEL_STEP_CERTIFICATE_SCHEMA = "trwm.world_model_step_certificate.v1"
WORLD_LEARNER_SNAPSHOT_SCHEMA = "trwm.world_learner_snapshot.v1"
WORLD_LEARNER_UPDATE_CERTIFICATE_SCHEMA = "trwm.world_learner_update_certificate.v1"
WORLD_LEARNER_DELTA_CERTIFICATE_SCHEMA = "trwm.world_learner_delta_certificate.v1"
WORLD_LEARNER_LINEAGE_CERTIFICATE_SCHEMA = "trwm.world_learner_lineage_certificate.v1"
WORLD_LEARNER_MERGE_CERTIFICATE_SCHEMA = "trwm.world_learner_merge_certificate.v1"
WORLD_LEARNER_MERGE_STRATEGY = "trace_delta_counter_join.v2"
WORLD_LEARNER_MERGE_BASIS = {
    "duplicate",
    "left_superset",
    "right_superset",
    "disjoint",
    "delta_common_prefix",
}


class TraceProposer(Protocol):
    proposer_id: str
    proposer_version: str

    def propose(self, state: Any, budget: Mapping[str, Any]) -> ProposalTrace:
        ...


class TraceProjector(Protocol):
    projector_id: str
    projector_version: str

    def project(self, state: Any, trace: ProposalTrace) -> TypedCandidate:
        ...


class ReceiptLearner(Protocol):
    def update(self, receipt: Receipt) -> None:
        ...


@dataclass(frozen=True)
class WorldLearnerSnapshot:
    schema_version: str
    learner_id: str
    learner_version: str
    update_count: int
    source_receipt_hashes: tuple[str, ...]
    learner_state: Any
    learner_state_hash: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_LEARNER_SNAPSHOT_SCHEMA:
            raise ValueError(f"invalid world learner snapshot schema: {self.schema_version}")
        object.__setattr__(self, "source_receipt_hashes", tuple(self.source_receipt_hashes))
        if not self.learner_state_hash:
            object.__setattr__(self, "learner_state_hash", world_learner_state_hash(self.learner_state))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", world_learner_snapshot_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("snapshot_hash", None)
        return data


@dataclass(frozen=True)
class WorldLearnerMergeCertificate:
    schema_version: str
    learner_id: str
    learner_version: str
    merge_strategy: str
    merge_basis: str
    left_snapshot_hash: str
    right_snapshot_hash: str
    merged_snapshot_hash: str
    base_snapshot_hash: str | None
    left_update_count: int
    right_update_count: int
    merged_update_count: int
    shared_receipt_count: int
    common_prefix_receipt_count: int
    conflict_count: int
    conflict_keys: tuple[str, ...]
    source_receipt_hashes: tuple[str, ...]
    left_delta_certificate_hashes: tuple[str, ...]
    right_delta_certificate_hashes: tuple[str, ...]
    merged_state_hash: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_LEARNER_MERGE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world learner merge certificate schema: {self.schema_version}")
        object.__setattr__(self, "conflict_keys", tuple(self.conflict_keys))
        object.__setattr__(self, "source_receipt_hashes", tuple(self.source_receipt_hashes))
        object.__setattr__(self, "left_delta_certificate_hashes", tuple(self.left_delta_certificate_hashes))
        object.__setattr__(self, "right_delta_certificate_hashes", tuple(self.right_delta_certificate_hashes))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_learner_merge_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class WorldLearnerMergeResult:
    merged_snapshot: WorldLearnerSnapshot
    certificate: WorldLearnerMergeCertificate


@dataclass(frozen=True)
class WorldLearnerDeltaCertificate:
    schema_version: str
    learner_id: str
    learner_version: str
    update_certificate_hash: str
    source_receipt_hash: str
    pre_snapshot_hash: str
    post_snapshot_hash: str
    pre_learner_state_hash: str
    post_learner_state_hash: str
    delta_op_count: int
    learner_delta: tuple[Mapping[str, Any], ...]
    learner_delta_hash: str = ""
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_LEARNER_DELTA_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world learner delta certificate schema: {self.schema_version}")
        object.__setattr__(self, "learner_delta", tuple(dict(operation) for operation in self.learner_delta))
        if not self.learner_delta_hash:
            object.__setattr__(self, "learner_delta_hash", world_learner_delta_hash(self.learner_delta))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_learner_delta_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class WorldLearnerLineageCertificate:
    schema_version: str
    learner_id: str
    learner_version: str
    initial_snapshot_hash: str
    final_snapshot_hash: str
    initial_update_count: int
    final_update_count: int
    update_certificate_count: int
    applied_update_count: int
    source_receipt_hashes: tuple[str, ...]
    update_certificate_hashes: tuple[str, ...]
    lineage_hash: str = ""
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_LEARNER_LINEAGE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world learner lineage certificate schema: {self.schema_version}")
        object.__setattr__(self, "source_receipt_hashes", tuple(self.source_receipt_hashes))
        object.__setattr__(self, "update_certificate_hashes", tuple(self.update_certificate_hashes))
        if not self.lineage_hash:
            object.__setattr__(self, "lineage_hash", world_learner_lineage_hash(self))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_learner_lineage_certificate_hash(self))

    def without_certificate_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data

    def lineage_data(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "learner_id": self.learner_id,
            "learner_version": self.learner_version,
            "initial_snapshot_hash": self.initial_snapshot_hash,
            "final_snapshot_hash": self.final_snapshot_hash,
            "source_receipt_hashes": self.source_receipt_hashes,
            "update_certificate_hashes": self.update_certificate_hashes,
        }


@dataclass(frozen=True)
class WorldLearnerUpdateCertificate:
    schema_version: str
    learner_id: str
    learner_version: str
    source_receipt_hash: str
    receipt_schema: str
    hard_result: str
    commit_decision: str
    committed: bool
    update_applied: bool
    pre_update_count: int
    post_update_count: int
    pre_learner_snapshot_hash: str
    pre_learner_state_hash: str
    post_learner_state_hash: str
    learner_snapshot_hash: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_LEARNER_UPDATE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world learner update certificate schema: {self.schema_version}")
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_learner_update_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class WorldModelStepCertificate:
    schema_version: str
    proposer_id: str
    proposer_version: str
    projector_id: str
    projector_version: str
    learner_id: str
    learner_version: str
    verifier_id: str
    verifier_version: str
    proposal_trace_hash: str
    typed_candidate_hash: str
    receipt_hash: str
    receipt_schema: str
    pre_state_hash: str
    post_state_hash: str | None
    rollback_state_hash: str | None
    hard_result: str
    commit_decision: str
    committed: bool
    learner_update_count: int
    learner_state_hash: str
    learner_snapshot_hash: str
    learner_update_certificate_hash: str
    ledger_head: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != WORLD_MODEL_STEP_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid world model step certificate schema: {self.schema_version}")
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", world_model_step_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class WorldModelStepResult:
    state: Any
    committed: bool
    receipt: Receipt
    certificate: WorldModelStepCertificate
    trace: ProposalTrace
    candidate: TypedCandidate
    pre_learner_snapshot: WorldLearnerSnapshot
    learner_snapshot: WorldLearnerSnapshot
    learner_update_certificate: WorldLearnerUpdateCertificate
    learner_delta_certificate: WorldLearnerDeltaCertificate
    learner_update_count: int

    @property
    def reason(self) -> str:
        return self.receipt.commit_decision


class TransactionalWorldModelRuntime:
    """One verified proposal step with optional receipt learner update."""

    def __init__(
        self,
        engine: TransactionEngine,
        proposer: TraceProposer,
        projector: TraceProjector,
        learner: ReceiptLearner | None = None,
    ):
        self.engine = engine
        self.proposer = proposer
        self.projector = projector
        self.learner = learner
        self.learner_update_count = 0
        self.learner_receipt_hashes: list[str] = []

    def step(
        self,
        state: Any,
        *,
        budget: Mapping[str, Any] | None = None,
        soft_scores: Mapping[str, float] | None = None,
    ) -> WorldModelStepResult:
        trace = self.proposer.propose(state, budget or {})
        candidate = self.projector.project(state, trace)
        outcome = self.engine.transact(state, trace, candidate, soft_scores=soft_scores)
        pre_learner_snapshot = build_world_learner_snapshot(
            self.learner,
            update_count=self.learner_update_count,
            source_receipt_hashes=tuple(self.learner_receipt_hashes),
        )
        update_applied = self.learner is not None
        if self.learner is not None:
            self.learner.update(outcome.receipt)
            self.learner_update_count += 1
            self.learner_receipt_hashes.append(outcome.receipt.receipt_hash)
        learner_snapshot = build_world_learner_snapshot(
            self.learner,
            update_count=self.learner_update_count,
            source_receipt_hashes=tuple(self.learner_receipt_hashes),
        )
        learner_update_certificate = build_world_learner_update_certificate(
            outcome.receipt,
            pre_snapshot=pre_learner_snapshot,
            post_snapshot=learner_snapshot,
            update_applied=update_applied,
        )
        learner_delta_certificate = build_world_learner_delta_certificate(
            pre_learner_snapshot,
            learner_snapshot,
            learner_update_certificate,
        )
        certificate = build_world_model_step_certificate(
            outcome.receipt,
            proposer_id=_component_id(self.proposer, "proposer"),
            proposer_version=_component_version(self.proposer),
            projector_id=_component_id(self.projector, "projector"),
            projector_version=_component_version(self.projector),
            learner_id=learner_snapshot.learner_id,
            learner_version=learner_snapshot.learner_version,
            learner_update_count=self.learner_update_count,
            learner_state_hash=learner_snapshot.learner_state_hash,
            learner_snapshot_hash=learner_snapshot.snapshot_hash,
            learner_update_certificate_hash=learner_update_certificate.certificate_hash,
            ledger_head=self.engine.ledger.head,
        )
        return WorldModelStepResult(
            state=outcome.state,
            committed=outcome.committed,
            receipt=outcome.receipt,
            certificate=certificate,
            trace=trace,
            candidate=candidate,
            pre_learner_snapshot=pre_learner_snapshot,
            learner_snapshot=learner_snapshot,
            learner_update_certificate=learner_update_certificate,
            learner_delta_certificate=learner_delta_certificate,
            learner_update_count=self.learner_update_count,
        )


def build_world_learner_snapshot(
    learner: ReceiptLearner | None,
    *,
    update_count: int,
    source_receipt_hashes: tuple[str, ...] = (),
) -> WorldLearnerSnapshot:
    return WorldLearnerSnapshot(
        schema_version=WORLD_LEARNER_SNAPSHOT_SCHEMA,
        learner_id=_component_id(learner, "learner") if learner is not None else "none",
        learner_version=_component_version(learner) if learner is not None else "0",
        update_count=update_count,
        source_receipt_hashes=source_receipt_hashes,
        learner_state=_learner_state(learner),
    )


def build_world_model_step_certificate(
    receipt: Receipt,
    *,
    proposer_id: str,
    proposer_version: str,
    projector_id: str,
    projector_version: str,
    learner_id: str,
    learner_version: str,
    learner_update_count: int,
    learner_state_hash: str,
    learner_snapshot_hash: str,
    learner_update_certificate_hash: str,
    ledger_head: str,
) -> WorldModelStepCertificate:
    return WorldModelStepCertificate(
        schema_version=WORLD_MODEL_STEP_CERTIFICATE_SCHEMA,
        proposer_id=proposer_id,
        proposer_version=proposer_version,
        projector_id=projector_id,
        projector_version=projector_version,
        learner_id=learner_id,
        learner_version=learner_version,
        verifier_id=receipt.hard_result.verifier_id,
        verifier_version=receipt.hard_result.verifier_version,
        proposal_trace_hash=receipt.proposal_trace_hash,
        typed_candidate_hash=receipt.typed_candidate_hash,
        receipt_hash=receipt.receipt_hash,
        receipt_schema=receipt.receipt_schema,
        pre_state_hash=receipt.pre_state_hash,
        post_state_hash=receipt.post_state_hash,
        rollback_state_hash=receipt.rollback_state_hash,
        hard_result=receipt.hard_result.result,
        commit_decision=receipt.commit_decision,
        committed=receipt.committed,
        learner_update_count=learner_update_count,
        learner_state_hash=learner_state_hash,
        learner_snapshot_hash=learner_snapshot_hash,
        learner_update_certificate_hash=learner_update_certificate_hash,
        ledger_head=ledger_head,
    )


def build_world_learner_update_certificate(
    receipt: Receipt,
    *,
    pre_snapshot: WorldLearnerSnapshot,
    post_snapshot: WorldLearnerSnapshot,
    update_applied: bool,
) -> WorldLearnerUpdateCertificate:
    return WorldLearnerUpdateCertificate(
        schema_version=WORLD_LEARNER_UPDATE_CERTIFICATE_SCHEMA,
        learner_id=post_snapshot.learner_id,
        learner_version=post_snapshot.learner_version,
        source_receipt_hash=receipt.receipt_hash,
        receipt_schema=receipt.receipt_schema,
        hard_result=receipt.hard_result.result,
        commit_decision=receipt.commit_decision,
        committed=receipt.committed,
        update_applied=update_applied,
        pre_update_count=pre_snapshot.update_count,
        post_update_count=post_snapshot.update_count,
        pre_learner_snapshot_hash=pre_snapshot.snapshot_hash,
        pre_learner_state_hash=pre_snapshot.learner_state_hash,
        post_learner_state_hash=post_snapshot.learner_state_hash,
        learner_snapshot_hash=post_snapshot.snapshot_hash,
    )


def build_world_learner_delta_certificate(
    pre_snapshot: WorldLearnerSnapshot,
    post_snapshot: WorldLearnerSnapshot,
    update_certificate: WorldLearnerUpdateCertificate,
) -> WorldLearnerDeltaCertificate:
    learner_delta = _learner_state_delta(pre_snapshot.learner_state, post_snapshot.learner_state)
    return WorldLearnerDeltaCertificate(
        schema_version=WORLD_LEARNER_DELTA_CERTIFICATE_SCHEMA,
        learner_id=post_snapshot.learner_id,
        learner_version=post_snapshot.learner_version,
        update_certificate_hash=update_certificate.certificate_hash,
        source_receipt_hash=update_certificate.source_receipt_hash,
        pre_snapshot_hash=pre_snapshot.snapshot_hash,
        post_snapshot_hash=post_snapshot.snapshot_hash,
        pre_learner_state_hash=pre_snapshot.learner_state_hash,
        post_learner_state_hash=post_snapshot.learner_state_hash,
        delta_op_count=len(learner_delta),
        learner_delta=learner_delta,
    )


def build_world_learner_lineage_certificate(
    initial_snapshot: WorldLearnerSnapshot,
    final_snapshot: WorldLearnerSnapshot,
    update_certificates: tuple[WorldLearnerUpdateCertificate, ...],
) -> WorldLearnerLineageCertificate:
    return WorldLearnerLineageCertificate(
        schema_version=WORLD_LEARNER_LINEAGE_CERTIFICATE_SCHEMA,
        learner_id=final_snapshot.learner_id,
        learner_version=final_snapshot.learner_version,
        initial_snapshot_hash=initial_snapshot.snapshot_hash,
        final_snapshot_hash=final_snapshot.snapshot_hash,
        initial_update_count=initial_snapshot.update_count,
        final_update_count=final_snapshot.update_count,
        update_certificate_count=len(update_certificates),
        applied_update_count=sum(1 for certificate in update_certificates if certificate.update_applied),
        source_receipt_hashes=tuple(certificate.source_receipt_hash for certificate in update_certificates if certificate.update_applied),
        update_certificate_hashes=tuple(certificate.certificate_hash for certificate in update_certificates),
    )


def audit_world_model_step(
    receipt: Receipt,
    certificate: WorldModelStepCertificate,
    *,
    ledger_head: str | None = None,
    learner_snapshot: WorldLearnerSnapshot | None = None,
    learner_update_certificate: WorldLearnerUpdateCertificate | None = None,
) -> bool:
    try:
        if not validate_world_model_step_certificate(certificate):
            return False
        if not receipt.static_valid():
            return False
        if ledger_head is not None and certificate.ledger_head != ledger_head:
            return False
        if learner_snapshot is not None:
            if not validate_world_learner_snapshot(learner_snapshot):
                return False
            if (
                certificate.learner_id != learner_snapshot.learner_id
                or certificate.learner_version != learner_snapshot.learner_version
                or certificate.learner_update_count != learner_snapshot.update_count
                or certificate.learner_state_hash != learner_snapshot.learner_state_hash
                or certificate.learner_snapshot_hash != learner_snapshot.snapshot_hash
            ):
                return False
        if learner_update_certificate is not None:
            if not validate_world_learner_update_certificate(learner_update_certificate):
                return False
            if certificate.learner_update_certificate_hash != learner_update_certificate.certificate_hash:
                return False
        return (
            certificate.verifier_id == receipt.hard_result.verifier_id
            and certificate.verifier_version == receipt.hard_result.verifier_version
            and certificate.proposal_trace_hash == receipt.proposal_trace_hash
            and certificate.typed_candidate_hash == receipt.typed_candidate_hash
            and certificate.receipt_hash == receipt.receipt_hash
            and certificate.receipt_schema == receipt.receipt_schema
            and certificate.pre_state_hash == receipt.pre_state_hash
            and certificate.post_state_hash == receipt.post_state_hash
            and certificate.rollback_state_hash == receipt.rollback_state_hash
            and certificate.hard_result == receipt.hard_result.result
            and certificate.commit_decision == receipt.commit_decision
            and certificate.committed == receipt.committed
        )
    except Exception:
        return False


def validate_world_learner_snapshot(snapshot: WorldLearnerSnapshot) -> bool:
    try:
        if snapshot.schema_version != WORLD_LEARNER_SNAPSHOT_SCHEMA:
            return False
        if not isinstance(snapshot.learner_id, str) or not snapshot.learner_id:
            return False
        if not isinstance(snapshot.learner_version, str) or not snapshot.learner_version:
            return False
        if not isinstance(snapshot.update_count, int) or isinstance(snapshot.update_count, bool) or snapshot.update_count < 0:
            return False
        if len(snapshot.source_receipt_hashes) != snapshot.update_count:
            return False
        if len(snapshot.source_receipt_hashes) != len(set(snapshot.source_receipt_hashes)):
            return False
        if any(not _is_hash(receipt_hash) for receipt_hash in snapshot.source_receipt_hashes):
            return False
        if not _is_hash(snapshot.learner_state_hash) or not _is_hash(snapshot.snapshot_hash):
            return False
        if snapshot.learner_state_hash != world_learner_state_hash(snapshot.learner_state):
            return False
        return snapshot.snapshot_hash == world_learner_snapshot_hash(snapshot)
    except Exception:
        return False


def audit_world_learner_update(
    receipt: Receipt,
    pre_snapshot: WorldLearnerSnapshot,
    post_snapshot: WorldLearnerSnapshot,
    certificate: WorldLearnerUpdateCertificate,
) -> bool:
    try:
        if not validate_world_learner_update_certificate(certificate):
            return False
        if not receipt.static_valid():
            return False
        if not validate_world_learner_snapshot(pre_snapshot) or not validate_world_learner_snapshot(post_snapshot):
            return False
        if pre_snapshot.learner_id != post_snapshot.learner_id or pre_snapshot.learner_version != post_snapshot.learner_version:
            return False
        if certificate.learner_id != post_snapshot.learner_id or certificate.learner_version != post_snapshot.learner_version:
            return False
        if certificate.source_receipt_hash != receipt.receipt_hash or certificate.receipt_schema != receipt.receipt_schema:
            return False
        if (
            certificate.hard_result != receipt.hard_result.result
            or certificate.commit_decision != receipt.commit_decision
            or certificate.committed != receipt.committed
        ):
            return False
        if (
            certificate.pre_update_count != pre_snapshot.update_count
            or certificate.post_update_count != post_snapshot.update_count
            or certificate.pre_learner_snapshot_hash != pre_snapshot.snapshot_hash
            or certificate.pre_learner_state_hash != pre_snapshot.learner_state_hash
            or certificate.post_learner_state_hash != post_snapshot.learner_state_hash
            or certificate.learner_snapshot_hash != post_snapshot.snapshot_hash
        ):
            return False
        if certificate.update_applied:
            expected_receipts = (*pre_snapshot.source_receipt_hashes, receipt.receipt_hash)
            if post_snapshot.source_receipt_hashes != expected_receipts:
                return False
            if post_snapshot.update_count != pre_snapshot.update_count + 1:
                return False
        else:
            if post_snapshot.source_receipt_hashes != pre_snapshot.source_receipt_hashes:
                return False
            if post_snapshot.update_count != pre_snapshot.update_count:
                return False
        return True
    except Exception:
        return False


def validate_world_learner_update_certificate(certificate: WorldLearnerUpdateCertificate) -> bool:
    try:
        if certificate.schema_version != WORLD_LEARNER_UPDATE_CERTIFICATE_SCHEMA:
            return False
        for value in (
            certificate.learner_id,
            certificate.learner_version,
            certificate.receipt_schema,
            certificate.commit_decision,
        ):
            if not isinstance(value, str) or not value:
                return False
        if certificate.hard_result not in {"accept", "reject", "abstain"}:
            return False
        if not isinstance(certificate.committed, bool) or not isinstance(certificate.update_applied, bool):
            return False
        if certificate.committed and (certificate.hard_result != "accept" or certificate.commit_decision != "commit"):
            return False
        for value in (certificate.pre_update_count, certificate.post_update_count):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False
        if certificate.update_applied:
            if certificate.post_update_count != certificate.pre_update_count + 1:
                return False
        elif certificate.post_update_count != certificate.pre_update_count:
            return False
        for value in (
            certificate.source_receipt_hash,
            certificate.pre_learner_snapshot_hash,
            certificate.pre_learner_state_hash,
            certificate.post_learner_state_hash,
            certificate.learner_snapshot_hash,
        ):
            if not _is_hash(value):
                return False
        return certificate.certificate_hash == world_learner_update_certificate_hash(certificate)
    except Exception:
        return False


def audit_world_learner_delta(
    pre_snapshot: WorldLearnerSnapshot,
    post_snapshot: WorldLearnerSnapshot,
    update_certificate: WorldLearnerUpdateCertificate,
    delta_certificate: WorldLearnerDeltaCertificate,
) -> bool:
    try:
        if not validate_world_learner_delta_certificate(delta_certificate):
            return False
        if not validate_world_learner_snapshot(pre_snapshot) or not validate_world_learner_snapshot(post_snapshot):
            return False
        if not validate_world_learner_update_certificate(update_certificate):
            return False
        if update_certificate.pre_learner_snapshot_hash != pre_snapshot.snapshot_hash:
            return False
        if update_certificate.learner_snapshot_hash != post_snapshot.snapshot_hash:
            return False
        if delta_certificate.learner_id != post_snapshot.learner_id or delta_certificate.learner_version != post_snapshot.learner_version:
            return False
        if delta_certificate.update_certificate_hash != update_certificate.certificate_hash:
            return False
        if delta_certificate.source_receipt_hash != update_certificate.source_receipt_hash:
            return False
        if (
            delta_certificate.pre_snapshot_hash != pre_snapshot.snapshot_hash
            or delta_certificate.post_snapshot_hash != post_snapshot.snapshot_hash
            or delta_certificate.pre_learner_state_hash != pre_snapshot.learner_state_hash
            or delta_certificate.post_learner_state_hash != post_snapshot.learner_state_hash
        ):
            return False
        replayed_state = apply_world_learner_delta(pre_snapshot.learner_state, delta_certificate.learner_delta)
        return world_learner_state_hash(replayed_state) == post_snapshot.learner_state_hash and replayed_state == post_snapshot.learner_state
    except Exception:
        return False


def validate_world_learner_delta_certificate(certificate: WorldLearnerDeltaCertificate) -> bool:
    try:
        if certificate.schema_version != WORLD_LEARNER_DELTA_CERTIFICATE_SCHEMA:
            return False
        if not isinstance(certificate.learner_id, str) or not certificate.learner_id:
            return False
        if not isinstance(certificate.learner_version, str) or not certificate.learner_version:
            return False
        if not isinstance(certificate.delta_op_count, int) or isinstance(certificate.delta_op_count, bool) or certificate.delta_op_count < 0:
            return False
        if len(certificate.learner_delta) != certificate.delta_op_count:
            return False
        for value in (
            certificate.update_certificate_hash,
            certificate.source_receipt_hash,
            certificate.pre_snapshot_hash,
            certificate.post_snapshot_hash,
            certificate.pre_learner_state_hash,
            certificate.post_learner_state_hash,
            certificate.learner_delta_hash,
        ):
            if not _is_hash(value):
                return False
        if not _validate_learner_delta(certificate.learner_delta):
            return False
        if certificate.learner_delta_hash != world_learner_delta_hash(certificate.learner_delta):
            return False
        return certificate.certificate_hash == world_learner_delta_certificate_hash(certificate)
    except Exception:
        return False


def apply_world_learner_delta(learner_state: Any, learner_delta: tuple[Mapping[str, Any], ...]) -> Any:
    state = deepcopy(learner_state)
    for operation in learner_delta:
        op = operation["op"]
        path = tuple(operation["path"])
        if op == "set":
            state = _set_path(state, path, deepcopy(operation.get("value")))
        elif op == "remove":
            state = _remove_path(state, path)
        else:
            raise ValueError(f"unsupported learner delta op: {op}")
    return state


def audit_world_learner_lineage(
    initial_snapshot: WorldLearnerSnapshot,
    final_snapshot: WorldLearnerSnapshot,
    update_certificates: tuple[WorldLearnerUpdateCertificate, ...],
    certificate: WorldLearnerLineageCertificate,
) -> bool:
    try:
        if not validate_world_learner_lineage_certificate(certificate):
            return False
        if not validate_world_learner_snapshot(initial_snapshot) or not validate_world_learner_snapshot(final_snapshot):
            return False
        if initial_snapshot.learner_id != final_snapshot.learner_id or initial_snapshot.learner_version != final_snapshot.learner_version:
            return False
        if certificate.learner_id != final_snapshot.learner_id or certificate.learner_version != final_snapshot.learner_version:
            return False
        if certificate.initial_snapshot_hash != initial_snapshot.snapshot_hash or certificate.final_snapshot_hash != final_snapshot.snapshot_hash:
            return False
        if certificate.initial_update_count != initial_snapshot.update_count or certificate.final_update_count != final_snapshot.update_count:
            return False
        if certificate.update_certificate_count != len(update_certificates):
            return False
        if any(not validate_world_learner_update_certificate(update_certificate) for update_certificate in update_certificates):
            return False
        if certificate.update_certificate_hashes != tuple(update_certificate.certificate_hash for update_certificate in update_certificates):
            return False

        applied_receipts = tuple(update_certificate.source_receipt_hash for update_certificate in update_certificates if update_certificate.update_applied)
        if certificate.applied_update_count != len(applied_receipts) or certificate.source_receipt_hashes != applied_receipts:
            return False
        expected_receipts = (*initial_snapshot.source_receipt_hashes, *applied_receipts)
        if final_snapshot.source_receipt_hashes != expected_receipts:
            return False
        if final_snapshot.update_count != initial_snapshot.update_count + len(applied_receipts):
            return False

        previous_hash = initial_snapshot.snapshot_hash
        previous_count = initial_snapshot.update_count
        for update_certificate in update_certificates:
            if update_certificate.learner_id != certificate.learner_id or update_certificate.learner_version != certificate.learner_version:
                return False
            if update_certificate.pre_learner_snapshot_hash != previous_hash:
                return False
            if update_certificate.pre_update_count != previous_count:
                return False
            previous_hash = update_certificate.learner_snapshot_hash
            previous_count = update_certificate.post_update_count
        return previous_hash == final_snapshot.snapshot_hash and previous_count == final_snapshot.update_count
    except Exception:
        return False


def validate_world_learner_lineage_certificate(certificate: WorldLearnerLineageCertificate) -> bool:
    try:
        if certificate.schema_version != WORLD_LEARNER_LINEAGE_CERTIFICATE_SCHEMA:
            return False
        if not isinstance(certificate.learner_id, str) or not certificate.learner_id:
            return False
        if not isinstance(certificate.learner_version, str) or not certificate.learner_version:
            return False
        for value in (
            certificate.initial_update_count,
            certificate.final_update_count,
            certificate.update_certificate_count,
            certificate.applied_update_count,
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False
        if certificate.final_update_count < certificate.initial_update_count:
            return False
        if certificate.applied_update_count != certificate.final_update_count - certificate.initial_update_count:
            return False
        if certificate.applied_update_count > certificate.update_certificate_count:
            return False
        if len(certificate.source_receipt_hashes) != certificate.applied_update_count:
            return False
        if len(certificate.update_certificate_hashes) != certificate.update_certificate_count:
            return False
        if len(certificate.source_receipt_hashes) != len(set(certificate.source_receipt_hashes)):
            return False
        for value in (
            certificate.initial_snapshot_hash,
            certificate.final_snapshot_hash,
            certificate.lineage_hash,
        ):
            if not _is_hash(value):
                return False
        if any(not _is_hash(receipt_hash) for receipt_hash in certificate.source_receipt_hashes):
            return False
        if any(not _is_hash(update_hash) for update_hash in certificate.update_certificate_hashes):
            return False
        if certificate.lineage_hash != world_learner_lineage_hash(certificate):
            return False
        return certificate.certificate_hash == world_learner_lineage_certificate_hash(certificate)
    except Exception:
        return False


def merge_world_learner_snapshots(
    left: WorldLearnerSnapshot,
    right: WorldLearnerSnapshot,
    *,
    base_snapshot: WorldLearnerSnapshot | None = None,
    left_delta_certificates: tuple[WorldLearnerDeltaCertificate, ...] = (),
    right_delta_certificates: tuple[WorldLearnerDeltaCertificate, ...] = (),
) -> WorldLearnerMergeResult:
    if not validate_world_learner_snapshot(left) or not validate_world_learner_snapshot(right):
        raise ValueError("world learner snapshots must validate before merge")
    if left.learner_id != right.learner_id or left.learner_version != right.learner_version:
        raise ValueError("world learner snapshots must use the same learner identity")

    left_receipts = set(left.source_receipt_hashes)
    right_receipts = set(right.source_receipt_hashes)
    shared_receipts = left_receipts & right_receipts
    conflict_keys: tuple[str, ...] = ()
    merge_basis = "disjoint"
    common_prefix_receipt_count = 0
    base_snapshot_hash: str | None = None

    if left.snapshot_hash == right.snapshot_hash:
        merge_basis = "duplicate"
        merged_state = left.learner_state
        merged_receipts = left.source_receipt_hashes
        common_prefix_receipt_count = left.update_count
    elif left_receipts <= right_receipts:
        merge_basis = "left_superset"
        merged_state = right.learner_state
        merged_receipts = right.source_receipt_hashes
        common_prefix_receipt_count = left.update_count
    elif right_receipts <= left_receipts:
        merge_basis = "right_superset"
        merged_state = left.learner_state
        merged_receipts = left.source_receipt_hashes
        common_prefix_receipt_count = right.update_count
    elif shared_receipts:
        if base_snapshot is None or not left_delta_certificates or not right_delta_certificates:
            raise ValueError("partially overlapping learner snapshots require base snapshot and per-receipt deltas")
        partial = _merge_partial_overlap_with_deltas(
            base_snapshot,
            left,
            right,
            left_delta_certificates,
            right_delta_certificates,
        )
        merge_basis = "delta_common_prefix"
        merged_state = partial["merged_state"]
        merged_receipts = partial["merged_receipts"]
        common_prefix_receipt_count = partial["common_prefix_receipt_count"]
        base_snapshot_hash = base_snapshot.snapshot_hash
    else:
        merged_state, conflicts = _merge_disjoint_learner_state(left.learner_state, right.learner_state)
        if conflicts:
            conflict_keys = tuple(conflicts)
            raise ValueError(f"conflicting learner state keys: {', '.join(conflict_keys)}")
        merged_receipts = tuple(sorted(left_receipts | right_receipts))

    merged_snapshot = WorldLearnerSnapshot(
        schema_version=WORLD_LEARNER_SNAPSHOT_SCHEMA,
        learner_id=left.learner_id,
        learner_version=left.learner_version,
        update_count=len(merged_receipts),
        source_receipt_hashes=tuple(merged_receipts),
        learner_state=merged_state,
    )
    certificate = WorldLearnerMergeCertificate(
        schema_version=WORLD_LEARNER_MERGE_CERTIFICATE_SCHEMA,
        learner_id=left.learner_id,
        learner_version=left.learner_version,
        merge_strategy=WORLD_LEARNER_MERGE_STRATEGY,
        merge_basis=merge_basis,
        left_snapshot_hash=left.snapshot_hash,
        right_snapshot_hash=right.snapshot_hash,
        merged_snapshot_hash=merged_snapshot.snapshot_hash,
        base_snapshot_hash=base_snapshot_hash,
        left_update_count=left.update_count,
        right_update_count=right.update_count,
        merged_update_count=merged_snapshot.update_count,
        shared_receipt_count=len(shared_receipts),
        common_prefix_receipt_count=common_prefix_receipt_count,
        conflict_count=len(conflict_keys),
        conflict_keys=conflict_keys,
        source_receipt_hashes=merged_snapshot.source_receipt_hashes,
        left_delta_certificate_hashes=tuple(certificate.certificate_hash for certificate in left_delta_certificates),
        right_delta_certificate_hashes=tuple(certificate.certificate_hash for certificate in right_delta_certificates),
        merged_state_hash=merged_snapshot.learner_state_hash,
    )
    return WorldLearnerMergeResult(merged_snapshot=merged_snapshot, certificate=certificate)


def audit_world_learner_merge(
    left: WorldLearnerSnapshot,
    right: WorldLearnerSnapshot,
    merged: WorldLearnerSnapshot,
    certificate: WorldLearnerMergeCertificate,
    *,
    base_snapshot: WorldLearnerSnapshot | None = None,
    left_delta_certificates: tuple[WorldLearnerDeltaCertificate, ...] = (),
    right_delta_certificates: tuple[WorldLearnerDeltaCertificate, ...] = (),
) -> bool:
    try:
        if not validate_world_learner_merge_certificate(certificate):
            return False
        recomputed = merge_world_learner_snapshots(
            left,
            right,
            base_snapshot=base_snapshot,
            left_delta_certificates=left_delta_certificates,
            right_delta_certificates=right_delta_certificates,
        )
        return (
            validate_world_learner_snapshot(merged)
            and merged.snapshot_hash == recomputed.merged_snapshot.snapshot_hash
            and certificate.certificate_hash == recomputed.certificate.certificate_hash
            and certificate.merged_snapshot_hash == merged.snapshot_hash
            and certificate.merged_state_hash == merged.learner_state_hash
        )
    except Exception:
        return False


def validate_world_learner_merge_certificate(certificate: WorldLearnerMergeCertificate) -> bool:
    try:
        if certificate.schema_version != WORLD_LEARNER_MERGE_CERTIFICATE_SCHEMA:
            return False
        if certificate.merge_strategy != WORLD_LEARNER_MERGE_STRATEGY:
            return False
        if certificate.merge_basis not in WORLD_LEARNER_MERGE_BASIS:
            return False
        if not isinstance(certificate.learner_id, str) or not certificate.learner_id:
            return False
        if not isinstance(certificate.learner_version, str) or not certificate.learner_version:
            return False
        for value in (
            certificate.left_snapshot_hash,
            certificate.right_snapshot_hash,
            certificate.merged_snapshot_hash,
            certificate.merged_state_hash,
        ):
            if not _is_hash(value):
                return False
        for value in (
            certificate.left_update_count,
            certificate.right_update_count,
            certificate.merged_update_count,
            certificate.shared_receipt_count,
            certificate.common_prefix_receipt_count,
            certificate.conflict_count,
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False
        if certificate.base_snapshot_hash is not None and not _is_hash(certificate.base_snapshot_hash):
            return False
        if certificate.conflict_count != 0 or certificate.conflict_keys:
            return False
        if len(certificate.source_receipt_hashes) != certificate.merged_update_count:
            return False
        if len(certificate.source_receipt_hashes) != len(set(certificate.source_receipt_hashes)):
            return False
        if any(not _is_hash(receipt_hash) for receipt_hash in certificate.source_receipt_hashes):
            return False
        if any(not _is_hash(delta_hash) for delta_hash in certificate.left_delta_certificate_hashes):
            return False
        if any(not _is_hash(delta_hash) for delta_hash in certificate.right_delta_certificate_hashes):
            return False
        if certificate.shared_receipt_count > min(certificate.left_update_count, certificate.right_update_count):
            return False
        if certificate.common_prefix_receipt_count < certificate.shared_receipt_count:
            return False
        if certificate.common_prefix_receipt_count > min(certificate.left_update_count, certificate.right_update_count):
            return False
        if certificate.merged_update_count != certificate.left_update_count + certificate.right_update_count - certificate.shared_receipt_count:
            return False
        if certificate.merge_basis == "delta_common_prefix":
            if certificate.base_snapshot_hash is None:
                return False
            if not certificate.left_delta_certificate_hashes or not certificate.right_delta_certificate_hashes:
                return False
            if certificate.common_prefix_receipt_count != certificate.shared_receipt_count:
                return False
        elif certificate.base_snapshot_hash is not None:
            return False
        return certificate.certificate_hash == world_learner_merge_certificate_hash(certificate)
    except Exception:
        return False


def validate_world_model_step_certificate(certificate: WorldModelStepCertificate) -> bool:
    try:
        if certificate.schema_version != WORLD_MODEL_STEP_CERTIFICATE_SCHEMA:
            return False
        for value in (
            certificate.proposer_id,
            certificate.proposer_version,
            certificate.projector_id,
            certificate.projector_version,
            certificate.learner_id,
            certificate.learner_version,
            certificate.verifier_id,
            certificate.verifier_version,
            certificate.receipt_schema,
            certificate.commit_decision,
        ):
            if not isinstance(value, str) or not value:
                return False
        if certificate.hard_result not in {"accept", "reject", "abstain"}:
            return False
        if not isinstance(certificate.committed, bool):
            return False
        if (
            not isinstance(certificate.learner_update_count, int)
            or isinstance(certificate.learner_update_count, bool)
            or certificate.learner_update_count < 0
        ):
            return False
        for value in (
            certificate.proposal_trace_hash,
            certificate.typed_candidate_hash,
            certificate.receipt_hash,
            certificate.pre_state_hash,
            certificate.learner_state_hash,
            certificate.learner_snapshot_hash,
            certificate.learner_update_certificate_hash,
            certificate.ledger_head,
        ):
            if not _is_hash(value):
                return False
        for value in (certificate.post_state_hash, certificate.rollback_state_hash):
            if value is not None and not _is_hash(value):
                return False
        if certificate.committed:
            if certificate.hard_result != "accept" or certificate.commit_decision != "commit":
                return False
            if certificate.post_state_hash is None or certificate.rollback_state_hash is None:
                return False
        elif certificate.commit_decision == "commit":
            return False
        return certificate.certificate_hash == world_model_step_certificate_hash(certificate)
    except Exception:
        return False


def world_model_step_certificate_hash(certificate: WorldModelStepCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, WorldModelStepCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def world_learner_state_hash(learner_state: Any) -> str:
    return stable_hash(learner_state)


def world_learner_snapshot_hash(snapshot: WorldLearnerSnapshot | Mapping[str, Any]) -> str:
    if isinstance(snapshot, WorldLearnerSnapshot):
        data = snapshot.without_hash()
    else:
        data = dict(snapshot)
        data.pop("snapshot_hash", None)
    return stable_hash(data)


def world_learner_update_certificate_hash(certificate: WorldLearnerUpdateCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, WorldLearnerUpdateCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def world_learner_delta_hash(learner_delta: tuple[Mapping[str, Any], ...]) -> str:
    return stable_hash(tuple(dict(operation) for operation in learner_delta))


def world_learner_delta_certificate_hash(certificate: WorldLearnerDeltaCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, WorldLearnerDeltaCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def world_learner_lineage_hash(certificate: WorldLearnerLineageCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, WorldLearnerLineageCertificate):
        data = certificate.lineage_data()
    else:
        data = {
            "schema_version": certificate["schema_version"],
            "learner_id": certificate["learner_id"],
            "learner_version": certificate["learner_version"],
            "initial_snapshot_hash": certificate["initial_snapshot_hash"],
            "final_snapshot_hash": certificate["final_snapshot_hash"],
            "source_receipt_hashes": tuple(certificate["source_receipt_hashes"]),
            "update_certificate_hashes": tuple(certificate["update_certificate_hashes"]),
        }
    return stable_hash(data)


def world_learner_lineage_certificate_hash(certificate: WorldLearnerLineageCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, WorldLearnerLineageCertificate):
        data = certificate.without_certificate_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def world_learner_merge_certificate_hash(certificate: WorldLearnerMergeCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, WorldLearnerMergeCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def _merge_disjoint_learner_state(left: Any, right: Any, path: str = "$") -> tuple[Any, tuple[str, ...]]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        merged: dict[str, Any] = {}
        conflicts: list[str] = []
        for key in sorted(set(left) | set(right), key=str):
            child_path = f"{path}.{key}"
            if key not in left:
                merged[str(key)] = right[key]
                continue
            if key not in right:
                merged[str(key)] = left[key]
                continue
            value, child_conflicts = _merge_disjoint_learner_state(left[key], right[key], child_path)
            merged[str(key)] = value
            conflicts.extend(child_conflicts)
        return merged, tuple(conflicts)
    key = path.rsplit(".", 1)[-1]
    if key.endswith("count") and _is_nonnegative_int(left) and _is_nonnegative_int(right):
        return left + right, ()
    if left == right:
        return left, ()
    if left is None:
        return right, ()
    if right is None:
        return left, ()
    return None, (path,)


_MISSING = object()


def _merge_partial_overlap_with_deltas(
    base_snapshot: WorldLearnerSnapshot,
    left: WorldLearnerSnapshot,
    right: WorldLearnerSnapshot,
    left_delta_certificates: tuple[WorldLearnerDeltaCertificate, ...],
    right_delta_certificates: tuple[WorldLearnerDeltaCertificate, ...],
) -> dict[str, Any]:
    if not validate_world_learner_snapshot(base_snapshot):
        raise ValueError("base learner snapshot must validate before partial-overlap merge")
    if (
        base_snapshot.learner_id != left.learner_id
        or base_snapshot.learner_id != right.learner_id
        or base_snapshot.learner_version != left.learner_version
        or base_snapshot.learner_version != right.learner_version
    ):
        raise ValueError("partial-overlap merge requires one learner identity")
    base_receipts = tuple(base_snapshot.source_receipt_hashes)
    if not _tuple_prefix(base_receipts, left.source_receipt_hashes) or not _tuple_prefix(base_receipts, right.source_receipt_hashes):
        raise ValueError("base learner snapshot must be a receipt prefix of both partial-overlap snapshots")

    left_replay = _replay_world_learner_delta_chain(base_snapshot, left, left_delta_certificates)
    right_replay = _replay_world_learner_delta_chain(base_snapshot, right, right_delta_certificates)

    shared_receipts = set(left.source_receipt_hashes) & set(right.source_receipt_hashes)
    common_prefix_count = _common_prefix_count(left.source_receipt_hashes, right.source_receipt_hashes)
    common_prefix_receipts = tuple(left.source_receipt_hashes[:common_prefix_count])
    if set(common_prefix_receipts) != shared_receipts:
        raise ValueError("partial-overlap learner snapshots must overlap only on a common receipt prefix")
    if common_prefix_count < base_snapshot.update_count:
        raise ValueError("base learner snapshot extends past the common receipt prefix")

    common_offset = common_prefix_count - base_snapshot.update_count
    left_common = left_replay["snapshots"][common_offset]
    right_common = right_replay["snapshots"][common_offset]
    if left_common.snapshot_hash != right_common.snapshot_hash:
        raise ValueError("partial-overlap learner delta chains disagree on common prefix state")

    merged_state, conflicts = _merge_common_ancestor_learner_state(
        left_common.learner_state,
        left.learner_state,
        right.learner_state,
    )
    if conflicts:
        raise ValueError(f"conflicting partial-overlap learner state keys: {', '.join(conflicts)}")
    unique_receipts = sorted((set(left.source_receipt_hashes) | set(right.source_receipt_hashes)) - shared_receipts)
    return {
        "merged_state": merged_state,
        "merged_receipts": (*common_prefix_receipts, *unique_receipts),
        "common_prefix_receipt_count": common_prefix_count,
    }


def _replay_world_learner_delta_chain(
    base_snapshot: WorldLearnerSnapshot,
    final_snapshot: WorldLearnerSnapshot,
    delta_certificates: tuple[WorldLearnerDeltaCertificate, ...],
) -> dict[str, Any]:
    suffix_receipts = tuple(final_snapshot.source_receipt_hashes[base_snapshot.update_count :])
    if len(delta_certificates) != len(suffix_receipts):
        raise ValueError("learner delta certificate count must match receipt suffix")
    current_state = deepcopy(base_snapshot.learner_state)
    current_snapshot = base_snapshot
    snapshots = [base_snapshot]
    for receipt_hash, delta_certificate in zip(suffix_receipts, delta_certificates):
        if not validate_world_learner_delta_certificate(delta_certificate):
            raise ValueError("learner delta certificate must validate before replay")
        if delta_certificate.learner_id != final_snapshot.learner_id or delta_certificate.learner_version != final_snapshot.learner_version:
            raise ValueError("learner delta certificate identity mismatch")
        if delta_certificate.source_receipt_hash != receipt_hash:
            raise ValueError("learner delta certificate receipt order mismatch")
        if delta_certificate.pre_snapshot_hash != current_snapshot.snapshot_hash:
            raise ValueError("learner delta certificate pre-snapshot hash mismatch")
        if delta_certificate.pre_learner_state_hash != world_learner_state_hash(current_state):
            raise ValueError("learner delta certificate pre-state hash mismatch")
        current_state = apply_world_learner_delta(current_state, delta_certificate.learner_delta)
        if delta_certificate.post_learner_state_hash != world_learner_state_hash(current_state):
            raise ValueError("learner delta certificate post-state hash mismatch")
        current_snapshot = WorldLearnerSnapshot(
            schema_version=WORLD_LEARNER_SNAPSHOT_SCHEMA,
            learner_id=final_snapshot.learner_id,
            learner_version=final_snapshot.learner_version,
            update_count=current_snapshot.update_count + 1,
            source_receipt_hashes=(*current_snapshot.source_receipt_hashes, receipt_hash),
            learner_state=current_state,
        )
        if delta_certificate.post_snapshot_hash != current_snapshot.snapshot_hash:
            raise ValueError("learner delta certificate post-snapshot hash mismatch")
        snapshots.append(current_snapshot)
    if current_snapshot.snapshot_hash != final_snapshot.snapshot_hash or current_state != final_snapshot.learner_state:
        raise ValueError("learner delta chain does not replay to final snapshot")
    return {"state": current_state, "snapshots": tuple(snapshots)}


def _merge_common_ancestor_learner_state(base: Any, left: Any, right: Any, path: str = "$") -> tuple[Any, tuple[str, ...]]:
    if isinstance(base, Mapping) or isinstance(left, Mapping) or isinstance(right, Mapping):
        if not all(value is _MISSING or isinstance(value, Mapping) for value in (base, left, right)):
            return None, (path,)
        merged: dict[str, Any] = {}
        conflicts: list[str] = []
        keys = set()
        for value in (base, left, right):
            if isinstance(value, Mapping):
                keys.update(value.keys())
        for key in sorted(keys, key=str):
            child_base = base.get(key, _MISSING) if isinstance(base, Mapping) else _MISSING
            child_left = left.get(key, _MISSING) if isinstance(left, Mapping) else _MISSING
            child_right = right.get(key, _MISSING) if isinstance(right, Mapping) else _MISSING
            child_value, child_conflicts = _merge_common_ancestor_learner_state(child_base, child_left, child_right, f"{path}.{key}")
            if child_conflicts:
                conflicts.extend(child_conflicts)
            elif child_value is not _MISSING:
                merged[str(key)] = child_value
        return merged, tuple(conflicts)

    if left is _MISSING and right is _MISSING:
        return _MISSING, ()
    if base is _MISSING:
        return _merge_disjoint_learner_state(left, right, path)
    if left is _MISSING:
        return (_MISSING, ()) if right == base else (None, (path,))
    if right is _MISSING:
        return (_MISSING, ()) if left == base else (None, (path,))

    key = path.rsplit(".", 1)[-1]
    if key.endswith("count") and all(_is_nonnegative_int(value) for value in (base, left, right)):
        if left < base or right < base:
            return None, (path,)
        return base + (left - base) + (right - base), ()
    if left == right:
        return left, ()
    if left == base:
        return right, ()
    if right == base:
        return left, ()
    return None, (path,)


def _tuple_prefix(prefix: tuple[str, ...], value: tuple[str, ...]) -> bool:
    return value[: len(prefix)] == prefix


def _common_prefix_count(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    count = 0
    for left_value, right_value in zip(left, right):
        if left_value != right_value:
            break
        count += 1
    return count


def _learner_state_delta(pre: Any, post: Any, path: tuple[str, ...] = ()) -> tuple[Mapping[str, Any], ...]:
    if pre == post:
        return ()
    if isinstance(pre, Mapping) and isinstance(post, Mapping):
        operations: list[Mapping[str, Any]] = []
        keys = sorted(set(pre) | set(post), key=str)
        for key in keys:
            key_path = (*path, str(key))
            if key not in post:
                operations.append({"op": "remove", "path": key_path})
            elif key not in pre:
                operations.append({"op": "set", "path": key_path, "value": post[key]})
            else:
                operations.extend(_learner_state_delta(pre[key], post[key], key_path))
        return tuple(operations)
    return ({"op": "set", "path": path, "value": post},)


def _validate_learner_delta(learner_delta: tuple[Mapping[str, Any], ...]) -> bool:
    for operation in learner_delta:
        if not isinstance(operation, Mapping):
            return False
        op = operation.get("op")
        if op not in {"set", "remove"}:
            return False
        path = operation.get("path")
        if not isinstance(path, (tuple, list)) or any(not isinstance(part, str) or not part for part in path):
            return False
        if op == "set" and "value" not in operation:
            return False
        if op == "remove" and "value" in operation:
            return False
    return True


def _set_path(state: Any, path: tuple[str, ...], value: Any) -> Any:
    if not path:
        return value
    if not isinstance(state, Mapping):
        raise ValueError("cannot set nested learner delta path on non-mapping state")
    cursor = state
    for key in path[:-1]:
        if not isinstance(cursor, dict) or key not in cursor or not isinstance(cursor[key], Mapping):
            raise ValueError("cannot set missing nested learner delta path")
        cursor = cursor[key]
    if not isinstance(cursor, dict):
        raise ValueError("cannot set learner delta path on non-dict cursor")
    cursor[path[-1]] = value
    return state


def _remove_path(state: Any, path: tuple[str, ...]) -> Any:
    if not path:
        raise ValueError("cannot remove learner root state")
    if not isinstance(state, Mapping):
        raise ValueError("cannot remove nested learner delta path on non-mapping state")
    cursor = state
    for key in path[:-1]:
        if not isinstance(cursor, dict) or key not in cursor or not isinstance(cursor[key], Mapping):
            raise ValueError("cannot remove missing nested learner delta path")
        cursor = cursor[key]
    if not isinstance(cursor, dict) or path[-1] not in cursor:
        raise ValueError("cannot remove missing learner delta path")
    del cursor[path[-1]]
    return state


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _component_id(component: Any, attr: str) -> str:
    return str(getattr(component, f"{attr}_id", type(component).__name__))


def _component_version(component: Any) -> str:
    return str(
        getattr(
            component,
            "proposer_version",
            getattr(
                component,
                "projector_version",
                getattr(component, "learner_version", getattr(component, "version", getattr(component, "model_version", "1.0"))),
            ),
        )
    )


def _learner_state(learner: ReceiptLearner | None) -> Any:
    if learner is None:
        return {}
    for attr in ("snapshot_state", "snapshot"):
        method = getattr(learner, attr, None)
        if callable(method):
            return method()
    return {
        "class": type(learner).__name__,
        "snapshot": "opaque",
    }


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
