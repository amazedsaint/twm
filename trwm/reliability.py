from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from math import sqrt
from typing import Any, Iterable, Mapping

from .core import Receipt, stable_hash


RELIABILITY_SNAPSHOT_SCHEMA = "trwm.reliability_snapshot.v1"


@dataclass(frozen=True)
class VerifierReliabilityRow:
    subject_id: str
    audited_successes: int = 0
    audited_failures: int = 0
    blocked_unknown: int = 0
    observations: int = 0
    posterior_mean: float = 0.5
    wilson_lower_bound: float = 0.0
    risk_score: float = 1.0


@dataclass(frozen=True)
class VerifierReliabilitySnapshot:
    schema_version: str
    rows: tuple[VerifierReliabilityRow, ...]
    prior_success: float = 1.0
    prior_failure: float = 1.0
    z: float = 1.96
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != RELIABILITY_SNAPSHOT_SCHEMA:
            raise ValueError(f"invalid reliability snapshot schema: {self.schema_version}")
        object.__setattr__(self, "rows", tuple(sorted(self.rows, key=lambda row: row.subject_id)))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", verifier_reliability_snapshot_hash(self))


class VerifierReliabilityMemory:
    def __init__(self, *, prior_success: float = 1.0, prior_failure: float = 1.0, z: float = 1.96) -> None:
        if prior_success <= 0 or prior_failure <= 0:
            raise ValueError("priors must be positive")
        if z <= 0:
            raise ValueError("z must be positive")
        self.prior_success = float(prior_success)
        self.prior_failure = float(prior_failure)
        self.z = float(z)
        self._rows: dict[str, VerifierReliabilityRow] = {}

    def update(self, subject_id: str, *, audited_success: bool | None) -> VerifierReliabilityRow:
        subject = str(subject_id)
        if not subject:
            raise ValueError("subject_id must be non-empty")
        row = self._rows.get(subject, VerifierReliabilityRow(subject_id=subject))
        if audited_success is True:
            row = replace(row, audited_successes=row.audited_successes + 1, observations=row.observations + 1)
        elif audited_success is False:
            row = replace(row, audited_failures=row.audited_failures + 1, observations=row.observations + 1)
        else:
            row = replace(row, blocked_unknown=row.blocked_unknown + 1, observations=row.observations + 1)
        row = self._scored(row)
        self._rows[subject] = row
        return row

    def update_from_receipt(self, receipt: Receipt) -> VerifierReliabilityRow | None:
        residual = receipt.hard_result.residual
        metadata = receipt.hard_result.metadata
        if isinstance(residual, Mapping) and _get(residual, "kind") == "verifier_false_positive":
            subject = _get(residual, "primary_verifier_id", "primaryVerifierId")
            audit_result = str(_get(residual, "audit_result", "auditResult") or "")
            if subject:
                return self.update(str(subject), audited_success=False if audit_result == "reject" else None)
        primary_result = str(_get(metadata, "primary_result", "primaryResult") or "")
        audit_result = str(_get(metadata, "audit_result", "auditResult") or "")
        subject = _get(metadata, "primary_verifier_id", "primaryVerifierId")
        if receipt.hard_result.accepted and primary_result == "accept" and audit_result == "accept" and subject:
            return self.update(str(subject), audited_success=True)
        return None

    def score(self, subject_id: str) -> VerifierReliabilityRow:
        subject = str(subject_id)
        return self._rows.get(subject, self._scored(VerifierReliabilityRow(subject_id=subject)))

    def rank_for_audit(self, subject_ids: Iterable[str]) -> tuple[str, ...]:
        unique_subjects = tuple(dict.fromkeys(str(subject) for subject in subject_ids if str(subject)))
        return tuple(
            row.subject_id
            for row in sorted(
                (self.score(subject) for subject in unique_subjects),
                key=lambda row: (-row.risk_score, -row.audited_failures, row.subject_id),
            )
        )

    def select_for_audit(self, subject_ids: Iterable[str], max_audits: int) -> tuple[str, ...]:
        if not isinstance(max_audits, int) or isinstance(max_audits, bool) or max_audits < 0:
            raise ValueError("max_audits must be a non-negative integer")
        return self.rank_for_audit(subject_ids)[:max_audits]

    def snapshot(self) -> VerifierReliabilitySnapshot:
        return VerifierReliabilitySnapshot(
            schema_version=RELIABILITY_SNAPSHOT_SCHEMA,
            rows=tuple(self._rows.values()),
            prior_success=self.prior_success,
            prior_failure=self.prior_failure,
            z=self.z,
        )

    def _scored(self, row: VerifierReliabilityRow) -> VerifierReliabilityRow:
        successes = row.audited_successes
        failures = row.audited_failures
        n = successes + failures
        posterior_mean = (self.prior_success + successes) / (self.prior_success + self.prior_failure + n)
        lower = wilson_lower_bound(successes, failures, z=self.z)
        risk = 1.0 - lower
        return replace(
            row,
            posterior_mean=_round_float(posterior_mean),
            wilson_lower_bound=_round_float(lower),
            risk_score=_round_float(risk),
        )


def wilson_lower_bound(successes: int, failures: int, *, z: float = 1.96) -> float:
    if successes < 0 or failures < 0:
        raise ValueError("successes and failures must be non-negative")
    n = successes + failures
    if n == 0:
        return 0.0
    phat = successes / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    center = phat + z2 / (2.0 * n)
    margin = z * sqrt((phat * (1.0 - phat) / n) + (z2 / (4.0 * n * n)))
    return max(0.0, (center - margin) / denominator)


def verifier_reliability_snapshot_hash(snapshot: VerifierReliabilitySnapshot) -> str:
    data = asdict(snapshot)
    data.pop("snapshot_hash", None)
    return stable_hash(data)


def validate_verifier_reliability_snapshot(snapshot: VerifierReliabilitySnapshot) -> bool:
    if snapshot.schema_version != RELIABILITY_SNAPSHOT_SCHEMA:
        return False
    if any(row.subject_id == "" for row in snapshot.rows):
        return False
    if len({row.subject_id for row in snapshot.rows}) != len(snapshot.rows):
        return False
    return snapshot.snapshot_hash == verifier_reliability_snapshot_hash(snapshot)


def _get(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _round_float(value: float) -> float:
    return round(float(value), 12)
