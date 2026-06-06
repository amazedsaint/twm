from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .core import stable_hash


LEARNING_EVALUATION_CERTIFICATE_SCHEMA = "trwm.learning_evaluation_certificate.v1"


@dataclass(frozen=True)
class LearningEvaluationCertificate:
    schema_version: str
    claim_id: str
    learner_id: str
    learner_snapshot_hash: str
    training_receipt_hashes: tuple[str, ...]
    evaluation_receipt_hashes: tuple[str, ...]
    baseline_name: str
    learned_name: str
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int
    verifier_budget: int
    candidate_count: int
    same_case_baseline: bool
    train_eval_disjoint: bool
    hard_commit_only: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float
    verifier_call_gain_numerator: int
    verifier_call_gain_denominator: int
    metrics: Mapping[str, Any]
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != LEARNING_EVALUATION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid learning evaluation certificate schema: {self.schema_version}")
        object.__setattr__(self, "training_receipt_hashes", tuple(self.training_receipt_hashes))
        object.__setattr__(self, "evaluation_receipt_hashes", tuple(self.evaluation_receipt_hashes))
        object.__setattr__(self, "metrics", dict(self.metrics))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", learning_evaluation_certificate_hash(self))

    @property
    def verifier_call_gain(self) -> float:
        if self.verifier_call_gain_denominator <= 0:
            return float("inf")
        return self.verifier_call_gain_numerator / self.verifier_call_gain_denominator

    @property
    def supports_learning_claim(self) -> bool:
        return learning_evaluation_supports_claim(self)

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


def build_learning_evaluation_certificate(
    *,
    claim_id: str,
    learner_id: str,
    learner_snapshot_hash: str,
    training_receipt_hashes: tuple[str, ...],
    evaluation_receipt_hashes: tuple[str, ...],
    baseline_name: str,
    learned_name: str,
    baseline_verifier_calls: int,
    learned_verifier_calls: int,
    baseline_success_count: int,
    learned_success_count: int,
    verifier_budget: int,
    candidate_count: int,
    same_case_baseline: bool,
    hard_commit_only: bool,
    invalid_commit_count: int,
    ledger_audit: bool,
    replay_rollback_rate: float,
    metrics: Mapping[str, Any] | None = None,
) -> LearningEvaluationCertificate:
    train = tuple(training_receipt_hashes)
    eval_rows = tuple(evaluation_receipt_hashes)
    return LearningEvaluationCertificate(
        schema_version=LEARNING_EVALUATION_CERTIFICATE_SCHEMA,
        claim_id=claim_id,
        learner_id=learner_id,
        learner_snapshot_hash=learner_snapshot_hash,
        training_receipt_hashes=train,
        evaluation_receipt_hashes=eval_rows,
        baseline_name=baseline_name,
        learned_name=learned_name,
        baseline_verifier_calls=baseline_verifier_calls,
        learned_verifier_calls=learned_verifier_calls,
        baseline_success_count=baseline_success_count,
        learned_success_count=learned_success_count,
        verifier_budget=verifier_budget,
        candidate_count=candidate_count,
        same_case_baseline=bool(same_case_baseline),
        train_eval_disjoint=not set(train).intersection(eval_rows),
        hard_commit_only=bool(hard_commit_only),
        invalid_commit_count=invalid_commit_count,
        ledger_audit=bool(ledger_audit),
        replay_rollback_rate=float(replay_rollback_rate),
        verifier_call_gain_numerator=baseline_verifier_calls,
        verifier_call_gain_denominator=learned_verifier_calls,
        metrics=metrics or {},
    )


def learning_evaluation_certificate_hash(certificate: LearningEvaluationCertificate) -> str:
    return stable_hash(certificate.without_hash())


def validate_learning_evaluation_certificate(certificate: LearningEvaluationCertificate) -> bool:
    try:
        if certificate.schema_version != LEARNING_EVALUATION_CERTIFICATE_SCHEMA:
            return False
        for value in (
            certificate.claim_id,
            certificate.learner_id,
            certificate.baseline_name,
            certificate.learned_name,
        ):
            if not isinstance(value, str) or not value:
                return False
        if not _is_hash(certificate.learner_snapshot_hash):
            return False
        if not certificate.training_receipt_hashes or not certificate.evaluation_receipt_hashes:
            return False
        if any(not _is_hash(row) for row in certificate.training_receipt_hashes + certificate.evaluation_receipt_hashes):
            return False
        if len(set(certificate.training_receipt_hashes)) != len(certificate.training_receipt_hashes):
            return False
        if len(set(certificate.evaluation_receipt_hashes)) != len(certificate.evaluation_receipt_hashes):
            return False
        disjoint = not set(certificate.training_receipt_hashes).intersection(certificate.evaluation_receipt_hashes)
        if certificate.train_eval_disjoint != disjoint or not disjoint:
            return False
        int_fields = (
            certificate.baseline_verifier_calls,
            certificate.learned_verifier_calls,
            certificate.baseline_success_count,
            certificate.learned_success_count,
            certificate.verifier_budget,
            certificate.candidate_count,
            certificate.invalid_commit_count,
            certificate.verifier_call_gain_numerator,
            certificate.verifier_call_gain_denominator,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in int_fields):
            return False
        if certificate.learned_verifier_calls == 0 or certificate.verifier_call_gain_denominator == 0:
            return False
        if certificate.verifier_call_gain_numerator != certificate.baseline_verifier_calls:
            return False
        if certificate.verifier_call_gain_denominator != certificate.learned_verifier_calls:
            return False
        if certificate.learned_verifier_calls > certificate.verifier_budget:
            return False
        if certificate.baseline_success_count > certificate.baseline_verifier_calls:
            return False
        if certificate.learned_success_count > certificate.learned_verifier_calls:
            return False
        if not isinstance(certificate.same_case_baseline, bool):
            return False
        if not isinstance(certificate.hard_commit_only, bool):
            return False
        if not isinstance(certificate.ledger_audit, bool):
            return False
        if not 0.0 <= certificate.replay_rollback_rate <= 1.0:
            return False
        if not _is_hash(certificate.certificate_hash):
            return False
        return certificate.certificate_hash == learning_evaluation_certificate_hash(certificate)
    except Exception:
        return False


def learning_evaluation_supports_claim(certificate: LearningEvaluationCertificate) -> bool:
    return (
        validate_learning_evaluation_certificate(certificate)
        and certificate.same_case_baseline
        and certificate.train_eval_disjoint
        and certificate.hard_commit_only
        and certificate.invalid_commit_count == 0
        and certificate.ledger_audit
        and certificate.replay_rollback_rate == 1.0
        and certificate.learned_success_count > certificate.baseline_success_count
    )


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
