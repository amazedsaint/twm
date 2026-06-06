from __future__ import annotations

from dataclasses import dataclass, replace
import unittest

from examples.common import (
    build_example_evidence_certificate,
    example_report_hash,
    validate_example_evidence_certificate,
)
from trwm.core import GENESIS_HEAD, stable_hash


@dataclass(frozen=True)
class DummyReport:
    schema_version: str = "trwm.example.dummy.v1"
    experiment_id: str = "dummy"
    receipt_count: int = 1


class TestExampleEvidenceCertificate(unittest.TestCase):
    def test_valid_certificate_passes(self) -> None:
        report = DummyReport()
        certificate = build_example_evidence_certificate(
            report,
            domain="dummy",
            verifier_id="dummy_verifier",
            verifier_version="1.0",
            ledger_head=GENESIS_HEAD,
            receipt_hashes=(stable_hash({"receipt": 1}), stable_hash({"receipt": 2})),
            committed_count=1,
            rejected_count=1,
            replay_audit_ok=True,
            rollback_audit_ok=True,
            ledger_audit_ok=True,
            invalid_commit_count=0,
            hard_gate_keys=("gate",),
            residual_kinds=("residual",),
            claim_boundary="G1 dummy boundary",
            sources=("https://example.com/source",),
        )

        self.assertTrue(validate_example_evidence_certificate(certificate, report))
        self.assertEqual(certificate.report_hash, example_report_hash(report))

    def test_tampered_report_hash_fails(self) -> None:
        report = DummyReport()
        certificate = build_example_evidence_certificate(
            report,
            domain="dummy",
            verifier_id="dummy_verifier",
            verifier_version="1.0",
            ledger_head=GENESIS_HEAD,
            receipt_hashes=(stable_hash({"receipt": 1}), stable_hash({"receipt": 2})),
            committed_count=1,
            rejected_count=1,
            replay_audit_ok=True,
            rollback_audit_ok=True,
            ledger_audit_ok=True,
            invalid_commit_count=0,
            hard_gate_keys=("gate",),
            residual_kinds=("residual",),
            claim_boundary="G1 dummy boundary",
            sources=("https://example.com/source",),
        )
        tampered = replace(certificate, report_hash=stable_hash({"tampered": True}))

        self.assertFalse(validate_example_evidence_certificate(tampered, report))

    def test_invalid_commit_count_fails(self) -> None:
        report = DummyReport()
        certificate = build_example_evidence_certificate(
            report,
            domain="dummy",
            verifier_id="dummy_verifier",
            verifier_version="1.0",
            ledger_head=GENESIS_HEAD,
            receipt_hashes=(stable_hash({"receipt": 1}), stable_hash({"receipt": 2})),
            committed_count=1,
            rejected_count=1,
            replay_audit_ok=True,
            rollback_audit_ok=True,
            ledger_audit_ok=True,
            invalid_commit_count=1,
            hard_gate_keys=("gate",),
            residual_kinds=("residual",),
            claim_boundary="G1 dummy boundary",
            sources=("https://example.com/source",),
        )

        self.assertFalse(validate_example_evidence_certificate(certificate, report))

    def test_missing_receipt_hash_fails(self) -> None:
        report = DummyReport()
        certificate = build_example_evidence_certificate(
            report,
            domain="dummy",
            verifier_id="dummy_verifier",
            verifier_version="1.0",
            ledger_head=GENESIS_HEAD,
            receipt_hashes=(),
            committed_count=0,
            rejected_count=0,
            replay_audit_ok=True,
            rollback_audit_ok=True,
            ledger_audit_ok=True,
            invalid_commit_count=0,
            hard_gate_keys=("gate",),
            residual_kinds=("residual",),
            claim_boundary="G1 dummy boundary",
            sources=("https://example.com/source",),
        )

        self.assertFalse(validate_example_evidence_certificate(certificate, report))
