from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from .core import stable_hash


CLAIM_CERTIFICATE_SCHEMA = "trwm.claim_certificate.v1"
CLAIM_EVIDENCE_GRADES = ("G0", "G1", "G2", "G3")
CLAIM_STATUSES = ("supported", "rejected")


@dataclass(frozen=True)
class ClaimRequirement:
    key: str
    passed: bool
    evidence: Mapping[str, Any] = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("requirement key must be non-empty")
        object.__setattr__(self, "evidence", dict(self.evidence))


@dataclass(frozen=True)
class ClaimCertificate:
    schema_version: str
    claim_id: str
    claim_text: str
    evidence_grade: str
    scope: str
    status: str
    requirements: tuple[ClaimRequirement, ...]
    metrics: Mapping[str, Any] = field(default_factory=dict)
    boundary: str = ""
    sources: tuple[str, ...] = ()
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != CLAIM_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid claim certificate schema: {self.schema_version}")
        if not self.claim_id:
            raise ValueError("claim_id must be non-empty")
        if not self.claim_text:
            raise ValueError("claim_text must be non-empty")
        if self.evidence_grade not in CLAIM_EVIDENCE_GRADES:
            raise ValueError(f"invalid evidence grade: {self.evidence_grade}")
        if self.status not in CLAIM_STATUSES:
            raise ValueError(f"invalid claim status: {self.status}")
        object.__setattr__(self, "requirements", tuple(self.requirements))
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "sources", tuple(str(source) for source in self.sources))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", claim_certificate_hash(self))

    @property
    def failed_keys(self) -> tuple[str, ...]:
        return tuple(requirement.key for requirement in self.requirements if not requirement.passed)


def requirement(key: str, passed: bool, *, reason: str = "", **evidence: Any) -> ClaimRequirement:
    return ClaimRequirement(key=key, passed=bool(passed), evidence=evidence, reason=reason)


def certify_claim(
    *,
    claim_id: str,
    claim_text: str,
    evidence_grade: str,
    scope: str,
    requirements: Iterable[ClaimRequirement],
    metrics: Mapping[str, Any] | None = None,
    boundary: str = "",
    sources: Iterable[str] = (),
) -> ClaimCertificate:
    rows = tuple(requirements)
    if len({row.key for row in rows}) != len(rows):
        raise ValueError("claim requirement keys must be unique")
    status = "supported" if all(row.passed for row in rows) else "rejected"
    return ClaimCertificate(
        schema_version=CLAIM_CERTIFICATE_SCHEMA,
        claim_id=claim_id,
        claim_text=claim_text,
        evidence_grade=evidence_grade,
        scope=scope,
        status=status,
        requirements=rows,
        metrics=metrics or {},
        boundary=boundary,
        sources=tuple(sources),
    )


def claim_certificate_hash(certificate: ClaimCertificate) -> str:
    data = asdict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def validate_claim_certificate(certificate: ClaimCertificate) -> bool:
    if certificate.schema_version != CLAIM_CERTIFICATE_SCHEMA:
        return False
    if certificate.evidence_grade not in CLAIM_EVIDENCE_GRADES:
        return False
    if certificate.status not in CLAIM_STATUSES:
        return False
    if not certificate.claim_id or not certificate.claim_text:
        return False
    if len({row.key for row in certificate.requirements}) != len(certificate.requirements):
        return False
    if certificate.status == "supported" and any(not row.passed for row in certificate.requirements):
        return False
    if certificate.status == "rejected" and all(row.passed for row in certificate.requirements):
        return False
    return certificate.certificate_hash == claim_certificate_hash(certificate)
