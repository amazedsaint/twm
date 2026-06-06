from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Mapping

from trwm.claims import ClaimCertificate
from trwm.core import stable_hash


EXAMPLE_EVIDENCE_CERTIFICATE_SCHEMA = "trwm.example_evidence_certificate.v1"


@dataclass(frozen=True)
class ExampleEvidenceCertificate:
    schema_version: str
    experiment_id: str
    domain: str
    evidence_grade: str
    report_schema_version: str
    report_hash: str
    verifier_id: str
    verifier_version: str
    ledger_head: str
    receipt_hashes: tuple[str, ...]
    receipt_count: int
    committed_count: int
    rejected_count: int
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    invalid_commit_count: int
    hard_gate_keys: tuple[str, ...]
    residual_kinds: tuple[str, ...]
    claim_boundary: str
    sources: tuple[str, ...]
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != EXAMPLE_EVIDENCE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid example evidence certificate schema: {self.schema_version}")
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(self, "hard_gate_keys", _unique_sorted_nonempty_strings(self.hard_gate_keys))
        object.__setattr__(self, "residual_kinds", _unique_sorted_nonempty_strings(self.residual_kinds))
        object.__setattr__(self, "sources", tuple(str(source) for source in self.sources))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", example_evidence_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class CertifiedExampleResult:
    report: Any
    evidence_certificate: ExampleEvidenceCertificate
    claim_certificate: ClaimCertificate


def report_as_dict(report: Any) -> dict[str, Any]:
    if is_dataclass(report):
        return asdict(report)
    if isinstance(report, Mapping):
        return dict(report)
    raise TypeError("report must be a dataclass or mapping")


def example_report_hash(report: Any) -> str:
    return stable_hash(report_as_dict(report))


def build_example_evidence_certificate(
    report: Any,
    *,
    domain: str,
    verifier_id: str,
    verifier_version: str,
    ledger_head: str,
    receipt_hashes: tuple[str, ...],
    committed_count: int,
    rejected_count: int,
    replay_audit_ok: bool,
    rollback_audit_ok: bool,
    ledger_audit_ok: bool,
    invalid_commit_count: int,
    hard_gate_keys: tuple[str, ...],
    residual_kinds: tuple[str, ...],
    claim_boundary: str,
    sources: tuple[str, ...],
    evidence_grade: str = "G1",
) -> ExampleEvidenceCertificate:
    report_data = report_as_dict(report)
    return ExampleEvidenceCertificate(
        schema_version=EXAMPLE_EVIDENCE_CERTIFICATE_SCHEMA,
        experiment_id=str(report_data["experiment_id"]),
        domain=domain,
        evidence_grade=evidence_grade,
        report_schema_version=str(report_data["schema_version"]),
        report_hash=example_report_hash(report),
        verifier_id=verifier_id,
        verifier_version=verifier_version,
        ledger_head=ledger_head,
        receipt_hashes=receipt_hashes,
        receipt_count=len(receipt_hashes),
        committed_count=committed_count,
        rejected_count=rejected_count,
        replay_audit_ok=replay_audit_ok,
        rollback_audit_ok=rollback_audit_ok,
        ledger_audit_ok=ledger_audit_ok,
        invalid_commit_count=invalid_commit_count,
        hard_gate_keys=hard_gate_keys,
        residual_kinds=residual_kinds,
        claim_boundary=claim_boundary,
        sources=sources,
    )


def validate_example_evidence_certificate(certificate: ExampleEvidenceCertificate, report: Any | None = None) -> bool:
    try:
        if certificate.schema_version != EXAMPLE_EVIDENCE_CERTIFICATE_SCHEMA:
            return False
        if certificate.evidence_grade != "G1":
            return False
        if not _nonempty_string(certificate.experiment_id):
            return False
        if not _nonempty_string(certificate.domain):
            return False
        if not _nonempty_string(certificate.report_schema_version):
            return False
        if not _is_hash(certificate.report_hash):
            return False
        if report is not None:
            report_data = report_as_dict(report)
            if str(report_data.get("experiment_id")) != certificate.experiment_id:
                return False
            if str(report_data.get("schema_version")) != certificate.report_schema_version:
                return False
            if example_report_hash(report) != certificate.report_hash:
                return False
        if not _nonempty_string(certificate.verifier_id) or not _nonempty_string(certificate.verifier_version):
            return False
        if not _is_hash(certificate.ledger_head):
            return False
        if certificate.receipt_count != len(certificate.receipt_hashes):
            return False
        if certificate.receipt_count <= 0:
            return False
        if any(not _is_hash(receipt_hash) for receipt_hash in certificate.receipt_hashes):
            return False
        count_values = (
            certificate.receipt_count,
            certificate.committed_count,
            certificate.rejected_count,
            certificate.invalid_commit_count,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in count_values):
            return False
        if certificate.committed_count + certificate.rejected_count > certificate.receipt_count:
            return False
        if certificate.committed_count <= 0 or certificate.rejected_count <= 0:
            return False
        if certificate.invalid_commit_count != 0:
            return False
        if not (certificate.replay_audit_ok and certificate.rollback_audit_ok and certificate.ledger_audit_ok):
            return False
        if not certificate.hard_gate_keys or any(not _nonempty_string(key) for key in certificate.hard_gate_keys):
            return False
        if not certificate.residual_kinds or any(not _nonempty_string(kind) for kind in certificate.residual_kinds):
            return False
        if not _nonempty_string(certificate.claim_boundary):
            return False
        if not certificate.sources or any(not _nonempty_string(source) for source in certificate.sources):
            return False
        return certificate.certificate_hash == example_evidence_certificate_hash(certificate)
    except Exception:
        return False


def example_evidence_certificate_hash(certificate: ExampleEvidenceCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, ExampleEvidenceCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _unique_sorted_nonempty_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if any(not value for value in rows):
        raise ValueError("certificate string sets must not contain empty values")
    return tuple(sorted(set(rows)))
