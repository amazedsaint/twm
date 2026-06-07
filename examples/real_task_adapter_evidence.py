from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping

from trwm.claims import CLAIM_STATUSES, ClaimCertificate, validate_claim_certificate
from trwm.core import stable_hash
from trwm.evaluation import (
    LearningEvaluationCertificate,
    learning_evaluation_supports_claim,
    validate_learning_evaluation_certificate,
)


REAL_TASK_ADAPTER_EVIDENCE_CERTIFICATE_SCHEMA = "trwm.real_task_adapter_evidence_certificate.v1"
REAL_TASK_ADAPTER_EVIDENCE_DOMAINS = ("robotics", "hardware", "program", "quantum")


@dataclass(frozen=True)
class RealTaskAdapterEvidenceCertificate:
    schema_version: str
    domain: str
    evidence_grade: str
    experiment_id: str
    report_schema_version: str
    report_hash: str
    backend_id: str
    backend_version: str
    backend_available: bool
    real_backend: bool
    missing_requirements: tuple[str, ...]
    train_task_ids: tuple[str, ...]
    held_out_task_ids: tuple[str, ...]
    learner_snapshot_hash: str
    learning_certificate_hash: str
    learning_certificate_valid: bool
    learning_certificate_supports_claim: bool
    claim_certificate_hash: str
    claim_certificate_valid: bool
    claim_certificate_status: str
    receipt_hashes: tuple[str, ...]
    typed_candidate_hashes: tuple[str, ...]
    hard_result_hashes: tuple[str, ...]
    hard_metadata_hashes: tuple[str, ...]
    training_receipt_hashes: tuple[str, ...]
    baseline_receipt_hashes: tuple[str, ...]
    learned_receipt_hashes: tuple[str, ...]
    receipt_count: int
    training_receipt_count: int
    baseline_receipt_count: int
    learned_receipt_count: int
    committed_count: int
    rejected_count: int
    invalid_commit_count: int
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int
    verifier_call_reduction: int
    hard_commit_only: bool
    train_eval_disjoint: bool
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    ledger_head: str
    source_urls: tuple[str, ...]
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REAL_TASK_ADAPTER_EVIDENCE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid real-task adapter evidence certificate schema: {self.schema_version}")
        object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        object.__setattr__(self, "train_task_ids", tuple(self.train_task_ids))
        object.__setattr__(self, "held_out_task_ids", tuple(self.held_out_task_ids))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(self, "typed_candidate_hashes", tuple(self.typed_candidate_hashes))
        object.__setattr__(self, "hard_result_hashes", tuple(self.hard_result_hashes))
        object.__setattr__(self, "hard_metadata_hashes", tuple(self.hard_metadata_hashes))
        object.__setattr__(self, "training_receipt_hashes", tuple(self.training_receipt_hashes))
        object.__setattr__(self, "baseline_receipt_hashes", tuple(self.baseline_receipt_hashes))
        object.__setattr__(self, "learned_receipt_hashes", tuple(self.learned_receipt_hashes))
        object.__setattr__(self, "source_urls", tuple(self.source_urls))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", real_task_adapter_evidence_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


def build_real_task_adapter_evidence_certificate(
    *,
    domain: str,
    report: Any,
    learning_certificate: LearningEvaluationCertificate | None,
    claim_certificate: ClaimCertificate,
) -> RealTaskAdapterEvidenceCertificate:
    report_data = _report_as_dict(report)
    receipt_hashes = tuple(str(row) for row in report_data["receipt_hashes"])
    training_count = int(report_data["training_receipt_count"])
    baseline_count = int(report_data["baseline_receipt_count"])
    learned_count = int(report_data["learned_receipt_count"])
    training_receipts = receipt_hashes[:training_count]
    baseline_receipts = receipt_hashes[training_count : training_count + baseline_count]
    learned_receipts = receipt_hashes[training_count + baseline_count : training_count + baseline_count + learned_count]
    learning_hash = learning_certificate.certificate_hash if learning_certificate is not None else ""
    learning_valid = (
        validate_learning_evaluation_certificate(learning_certificate)
        if learning_certificate is not None
        else False
    )
    learning_supports = learning_evaluation_supports_claim(learning_certificate) if learning_certificate is not None else False
    claim_valid = validate_claim_certificate(claim_certificate)
    claim_supported = claim_valid and claim_certificate.status == "supported"
    evidence_grade = "G1" if report_data["backend_available"] and report_data["real_backend"] and claim_supported else "G0"
    return RealTaskAdapterEvidenceCertificate(
        schema_version=REAL_TASK_ADAPTER_EVIDENCE_CERTIFICATE_SCHEMA,
        domain=domain,
        evidence_grade=evidence_grade,
        experiment_id=str(report_data["experiment_id"]),
        report_schema_version=str(report_data["schema_version"]),
        report_hash=real_task_adapter_report_hash(report),
        backend_id=str(report_data["backend_id"]),
        backend_version=str(report_data["backend_version"]),
        backend_available=bool(report_data["backend_available"]),
        real_backend=bool(report_data["real_backend"]),
        missing_requirements=tuple(str(row) for row in report_data["missing_requirements"]),
        train_task_ids=tuple(str(row) for row in report_data["train_task_ids"]),
        held_out_task_ids=tuple(str(row) for row in report_data["held_out_task_ids"]),
        learner_snapshot_hash=str(report_data["learner_snapshot_hash"]),
        learning_certificate_hash=learning_hash,
        learning_certificate_valid=learning_valid,
        learning_certificate_supports_claim=learning_supports,
        claim_certificate_hash=str(claim_certificate.certificate_hash),
        claim_certificate_valid=claim_valid,
        claim_certificate_status=str(claim_certificate.status),
        receipt_hashes=receipt_hashes,
        typed_candidate_hashes=tuple(str(row) for row in report_data["typed_candidate_hashes"]),
        hard_result_hashes=tuple(str(row) for row in report_data["hard_result_hashes"]),
        hard_metadata_hashes=tuple(str(row) for row in report_data["hard_metadata_hashes"]),
        training_receipt_hashes=training_receipts,
        baseline_receipt_hashes=baseline_receipts,
        learned_receipt_hashes=learned_receipts,
        receipt_count=int(report_data["receipt_count"]),
        training_receipt_count=training_count,
        baseline_receipt_count=baseline_count,
        learned_receipt_count=learned_count,
        committed_count=int(report_data["committed_count"]),
        rejected_count=int(report_data["rejected_count"]),
        invalid_commit_count=int(report_data["invalid_commit_count"]),
        baseline_verifier_calls=int(report_data["baseline_verifier_calls"]),
        learned_verifier_calls=int(report_data["learned_verifier_calls"]),
        baseline_success_count=int(report_data["baseline_success_count"]),
        learned_success_count=int(report_data["learned_success_count"]),
        verifier_call_reduction=int(report_data["verifier_call_reduction"]),
        hard_commit_only=bool(report_data["hard_commit_only"]),
        train_eval_disjoint=bool(report_data["train_eval_disjoint"]),
        replay_audit_ok=bool(report_data["replay_audit_ok"]),
        rollback_audit_ok=bool(report_data["rollback_audit_ok"]),
        ledger_audit_ok=bool(report_data["ledger_audit_ok"]),
        ledger_head=str(report_data["ledger_head"]),
        source_urls=tuple(str(row) for row in report_data["source_urls"]),
        claim_boundary=str(report_data["claim_boundary"]),
    )


def validate_real_task_adapter_evidence_certificate(
    certificate: RealTaskAdapterEvidenceCertificate,
    *,
    report: Any | None = None,
    learning_certificate: LearningEvaluationCertificate | None = None,
    claim_certificate: ClaimCertificate | None = None,
) -> bool:
    try:
        if certificate.schema_version != REAL_TASK_ADAPTER_EVIDENCE_CERTIFICATE_SCHEMA:
            return False
        if certificate.domain not in REAL_TASK_ADAPTER_EVIDENCE_DOMAINS:
            return False
        if certificate.evidence_grade not in {"G0", "G1"}:
            return False
        for value in (
            certificate.experiment_id,
            certificate.report_schema_version,
            certificate.backend_id,
            certificate.backend_version,
            certificate.claim_boundary,
        ):
            if not _nonempty_string(value):
                return False
        for hash_value in (certificate.report_hash, certificate.claim_certificate_hash, certificate.certificate_hash):
            if not _is_hash(hash_value):
                return False
        if certificate.learning_certificate_hash and not _is_hash(certificate.learning_certificate_hash):
            return False
        if certificate.learner_snapshot_hash and not _is_hash(certificate.learner_snapshot_hash):
            return False
        if certificate.ledger_head and not _is_hash(certificate.ledger_head):
            return False
        if not isinstance(certificate.backend_available, bool) or not isinstance(certificate.real_backend, bool):
            return False
        if not isinstance(certificate.claim_certificate_valid, bool):
            return False
        if certificate.claim_certificate_status not in CLAIM_STATUSES:
            return False
        if not isinstance(certificate.learning_certificate_valid, bool):
            return False
        if not isinstance(certificate.learning_certificate_supports_claim, bool):
            return False
        if certificate.claim_certificate_status == "supported" and not certificate.claim_certificate_valid:
            return False
        if not certificate.source_urls or any(not _nonempty_string(source) for source in certificate.source_urls):
            return False
        if not _counts_and_partitions_are_valid(certificate):
            return False
        if certificate.evidence_grade == "G1" and not _g1_supported(certificate):
            return False
        if certificate.evidence_grade == "G0" and _g1_supported(certificate):
            return False
        if report is not None and not _report_matches(certificate, report):
            return False
        if claim_certificate is not None:
            if validate_claim_certificate(claim_certificate) != certificate.claim_certificate_valid:
                return False
            if claim_certificate.certificate_hash != certificate.claim_certificate_hash:
                return False
            if claim_certificate.status != certificate.claim_certificate_status:
                return False
            if report is not None and not _claim_matches_report(claim_certificate, _report_as_dict(report)):
                return False
        if learning_certificate is not None:
            if not _learning_certificate_matches(certificate, learning_certificate):
                return False
            if report is not None and not _learning_certificate_matches_report(learning_certificate, _report_as_dict(report)):
                return False
        elif certificate.receipt_count > 0:
            return False
        return certificate.certificate_hash == real_task_adapter_evidence_certificate_hash(certificate)
    except Exception:
        return False


def real_task_adapter_report_hash(report: Any) -> str:
    return stable_hash(_report_as_dict(report))


def real_task_adapter_evidence_certificate_hash(certificate: RealTaskAdapterEvidenceCertificate) -> str:
    return stable_hash(certificate.without_hash())


def receipt_execution_provenance_hashes(receipts: Any) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    rows = tuple(receipts)
    return (
        tuple(str(receipt.typed_candidate_hash) for receipt in rows),
        tuple(stable_hash(asdict(receipt.hard_result)) for receipt in rows),
        tuple(stable_hash(receipt.hard_result.metadata) for receipt in rows),
    )


def _report_as_dict(report: Any) -> dict[str, Any]:
    if is_dataclass(report):
        return asdict(report)
    if isinstance(report, Mapping):
        return dict(report)
    raise TypeError("report must be a dataclass or mapping")


def _counts_and_partitions_are_valid(certificate: RealTaskAdapterEvidenceCertificate) -> bool:
    int_fields = (
        certificate.receipt_count,
        certificate.training_receipt_count,
        certificate.baseline_receipt_count,
        certificate.learned_receipt_count,
        certificate.committed_count,
        certificate.rejected_count,
        certificate.invalid_commit_count,
        certificate.baseline_verifier_calls,
        certificate.learned_verifier_calls,
        certificate.baseline_success_count,
        certificate.learned_success_count,
        certificate.verifier_call_reduction,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in int_fields):
        return False
    if certificate.receipt_count != len(certificate.receipt_hashes):
        return False
    if certificate.receipt_count != len(certificate.typed_candidate_hashes):
        return False
    if certificate.receipt_count != len(certificate.hard_result_hashes):
        return False
    if certificate.receipt_count != len(certificate.hard_metadata_hashes):
        return False
    if certificate.training_receipt_count != len(certificate.training_receipt_hashes):
        return False
    if certificate.baseline_receipt_count != len(certificate.baseline_receipt_hashes):
        return False
    if certificate.learned_receipt_count != len(certificate.learned_receipt_hashes):
        return False
    if certificate.receipt_hashes != (
        certificate.training_receipt_hashes + certificate.baseline_receipt_hashes + certificate.learned_receipt_hashes
    ):
        return False
    if certificate.receipt_count != certificate.training_receipt_count + certificate.baseline_receipt_count + certificate.learned_receipt_count:
        return False
    if any(not _is_hash(row) for row in certificate.receipt_hashes):
        return False
    if any(not _is_hash(row) for row in certificate.typed_candidate_hashes):
        return False
    if any(not _is_hash(row) for row in certificate.hard_result_hashes):
        return False
    if any(not _is_hash(row) for row in certificate.hard_metadata_hashes):
        return False
    if len(set(certificate.receipt_hashes)) != len(certificate.receipt_hashes):
        return False
    if certificate.committed_count + certificate.rejected_count > certificate.receipt_count:
        return False
    if certificate.verifier_call_reduction != certificate.baseline_verifier_calls - certificate.learned_verifier_calls:
        return False
    if certificate.baseline_success_count > certificate.baseline_verifier_calls:
        return False
    if certificate.learned_success_count > certificate.learned_verifier_calls:
        return False
    if certificate.receipt_count == 0:
        return (
            certificate.training_receipt_count == 0
            and certificate.baseline_receipt_count == 0
            and certificate.learned_receipt_count == 0
            and certificate.committed_count == 0
            and certificate.rejected_count == 0
            and certificate.invalid_commit_count == 0
            and certificate.baseline_verifier_calls == 0
            and certificate.learned_verifier_calls == 0
            and certificate.learner_snapshot_hash == ""
            and certificate.learning_certificate_hash == ""
            and certificate.ledger_head == ""
            and not certificate.learning_certificate_valid
            and not certificate.learning_certificate_supports_claim
        )
    return bool(certificate.ledger_head and certificate.learner_snapshot_hash and certificate.learning_certificate_hash)


def _g1_supported(certificate: RealTaskAdapterEvidenceCertificate) -> bool:
    return (
        certificate.backend_available
        and certificate.real_backend
        and certificate.claim_certificate_valid
        and certificate.claim_certificate_status == "supported"
        and certificate.learning_certificate_valid
        and certificate.learning_certificate_supports_claim
        and certificate.learned_verifier_calls < certificate.baseline_verifier_calls
        and certificate.learned_success_count == certificate.baseline_success_count
        and certificate.learned_success_count > 0
        and certificate.invalid_commit_count == 0
        and certificate.hard_commit_only
        and certificate.train_eval_disjoint
        and certificate.replay_audit_ok
        and certificate.rollback_audit_ok
        and certificate.ledger_audit_ok
    )


def _report_matches(certificate: RealTaskAdapterEvidenceCertificate, report: Any) -> bool:
    data = _report_as_dict(report)
    exact_fields = (
        "experiment_id",
        "backend_id",
        "backend_version",
        "backend_available",
        "real_backend",
        "missing_requirements",
        "train_task_ids",
        "held_out_task_ids",
        "learner_snapshot_hash",
        "learning_certificate_hash",
        "learning_certificate_valid",
        "learning_certificate_supports_claim",
        "receipt_count",
        "typed_candidate_hashes",
        "hard_result_hashes",
        "hard_metadata_hashes",
        "training_receipt_count",
        "baseline_receipt_count",
        "learned_receipt_count",
        "committed_count",
        "rejected_count",
        "invalid_commit_count",
        "baseline_verifier_calls",
        "learned_verifier_calls",
        "baseline_success_count",
        "learned_success_count",
        "verifier_call_reduction",
        "hard_commit_only",
        "train_eval_disjoint",
        "replay_audit_ok",
        "rollback_audit_ok",
        "ledger_audit_ok",
        "ledger_head",
        "receipt_hashes",
        "source_urls",
        "claim_boundary",
    )
    if certificate.report_schema_version != str(data.get("schema_version")):
        return False
    if certificate.report_hash != real_task_adapter_report_hash(report):
        return False
    for field_name in exact_fields:
        value = data.get(field_name)
        expected = getattr(certificate, field_name)
        if isinstance(expected, tuple):
            value = tuple(value)
        if value != expected:
            return False
    return True


def _claim_matches_report(claim: ClaimCertificate, report_data: Mapping[str, Any]) -> bool:
    expected_metrics = {
        "baseline_verifier_calls": int(report_data["baseline_verifier_calls"]),
        "learned_verifier_calls": int(report_data["learned_verifier_calls"]),
        "verifier_call_reduction": int(report_data["verifier_call_reduction"]),
        "invalid_commit_count": int(report_data["invalid_commit_count"]),
    }
    return (
        claim.metrics == expected_metrics
        and claim.boundary == str(report_data["claim_boundary"])
        and claim.sources == tuple(report_data["source_urls"])
    )


def _learning_certificate_matches(
    certificate: RealTaskAdapterEvidenceCertificate,
    learning_certificate: LearningEvaluationCertificate,
) -> bool:
    return (
        validate_learning_evaluation_certificate(learning_certificate) == certificate.learning_certificate_valid
        and learning_certificate.certificate_hash == certificate.learning_certificate_hash
        and learning_evaluation_supports_claim(learning_certificate) == certificate.learning_certificate_supports_claim
        and learning_certificate.training_receipt_hashes == certificate.training_receipt_hashes
        and learning_certificate.evaluation_receipt_hashes == certificate.learned_receipt_hashes
        and learning_certificate.learner_snapshot_hash == certificate.learner_snapshot_hash
    )


def _learning_certificate_matches_report(
    learning_certificate: LearningEvaluationCertificate,
    report_data: Mapping[str, Any],
) -> bool:
    return (
        learning_certificate.baseline_verifier_calls == int(report_data["baseline_verifier_calls"])
        and learning_certificate.learned_verifier_calls == int(report_data["learned_verifier_calls"])
        and learning_certificate.baseline_success_count == int(report_data["baseline_success_count"])
        and learning_certificate.learned_success_count == int(report_data["learned_success_count"])
        and learning_certificate.verifier_budget == int(report_data["baseline_verifier_calls"])
        and learning_certificate.candidate_count == 2 * len(tuple(report_data["held_out_task_ids"]))
        and learning_certificate.hard_commit_only == bool(report_data["hard_commit_only"])
        and learning_certificate.train_eval_disjoint == bool(report_data["train_eval_disjoint"])
        and learning_certificate.invalid_commit_count == int(report_data["invalid_commit_count"])
        and learning_certificate.ledger_audit == bool(report_data["ledger_audit_ok"])
        and learning_certificate.replay_rollback_rate
        == (1.0 if report_data["replay_audit_ok"] and report_data["rollback_audit_ok"] else 0.0)
        and learning_certificate.metrics
        == {
            "backend_id": str(report_data["backend_id"]),
            "real_backend": bool(report_data["real_backend"]),
            "held_out_task_ids": tuple(report_data["held_out_task_ids"]),
        }
    )


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
