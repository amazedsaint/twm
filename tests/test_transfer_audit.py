from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.experiments.transfer_audit import run_cross_domain_transfer_audit
from trwm.transfer import (
    TRANSFER_EVALUATION_CERTIFICATE_SCHEMA,
    build_transfer_evaluation_certificate,
    transfer_evaluation_rejects_positive_claim,
    transfer_evaluation_supports_positive_claim,
    validate_transfer_evaluation_certificate,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
NO_INVALID_COMMITS = 0


class TransferAuditTests(unittest.TestCase):
    def test_certificate_rejects_positive_transfer_overclaim(self) -> None:
        certificate = build_transfer_evaluation_certificate(
            claim_id="test-transfer",
            learner_id="source-policy",
            learner_snapshot_hash=HASH_A,
            source_domains=("source",),
            target_domains=("target",),
            source_receipt_hashes=(HASH_B,),
            target_evaluation_receipt_hashes=(HASH_C,),
            baseline_name="target-baseline",
            transfer_name="source-transfer",
            baseline_success_count=1,
            transfer_success_count=0,
            baseline_verifier_calls=1,
            transfer_verifier_calls=1,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=NO_INVALID_COMMITS,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )

        self.assertEqual(certificate.schema_version, TRANSFER_EVALUATION_CERTIFICATE_SCHEMA)
        self.assertEqual(certificate.success_delta, -1)
        self.assertEqual(certificate.verifier_call_delta, 0)
        self.assertEqual(certificate.conclusion, "negative_transfer")
        self.assertTrue(validate_transfer_evaluation_certificate(certificate))
        self.assertTrue(transfer_evaluation_rejects_positive_claim(certificate))
        self.assertFalse(transfer_evaluation_supports_positive_claim(certificate))

    def test_certificate_detects_overlap_domain_and_metric_tamper(self) -> None:
        certificate = build_transfer_evaluation_certificate(
            claim_id="test-transfer",
            learner_id="source-policy",
            learner_snapshot_hash=HASH_A,
            source_domains=("source",),
            target_domains=("target",),
            source_receipt_hashes=(HASH_B,),
            target_evaluation_receipt_hashes=(HASH_C,),
            baseline_name="target-baseline",
            transfer_name="source-transfer",
            baseline_success_count=1,
            transfer_success_count=0,
            baseline_verifier_calls=1,
            transfer_verifier_calls=1,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=NO_INVALID_COMMITS,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )
        receipt_overlap = build_transfer_evaluation_certificate(
            claim_id="test-transfer",
            learner_id="source-policy",
            learner_snapshot_hash=HASH_A,
            source_domains=("source",),
            target_domains=("target",),
            source_receipt_hashes=(HASH_B,),
            target_evaluation_receipt_hashes=(HASH_B,),
            baseline_name="target-baseline",
            transfer_name="source-transfer",
            baseline_success_count=1,
            transfer_success_count=0,
            baseline_verifier_calls=1,
            transfer_verifier_calls=1,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=NO_INVALID_COMMITS,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )
        domain_overlap = build_transfer_evaluation_certificate(
            claim_id="test-transfer",
            learner_id="source-policy",
            learner_snapshot_hash=HASH_A,
            source_domains=("shared",),
            target_domains=("shared",),
            source_receipt_hashes=(HASH_B,),
            target_evaluation_receipt_hashes=(HASH_C,),
            baseline_name="target-baseline",
            transfer_name="source-transfer",
            baseline_success_count=1,
            transfer_success_count=0,
            baseline_verifier_calls=1,
            transfer_verifier_calls=1,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=NO_INVALID_COMMITS,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )
        tampered = replace(certificate, transfer_success_count=1)

        self.assertFalse(validate_transfer_evaluation_certificate(receipt_overlap))
        self.assertFalse(validate_transfer_evaluation_certificate(domain_overlap))
        self.assertFalse(validate_transfer_evaluation_certificate(tampered))

    def test_cross_domain_transfer_audit_reports_negative_transfer(self) -> None:
        report = run_cross_domain_transfer_audit()

        self.assertTrue(report.certificate_valid)
        self.assertFalse(report.positive_transfer_claim_supported)
        self.assertTrue(report.positive_transfer_claim_rejected)
        self.assertEqual(report.source_domain_count, 1)
        self.assertEqual(report.target_domain_count, 1)
        self.assertEqual(report.source_receipt_count, 1)
        self.assertEqual(report.target_evaluation_receipt_count, 2)
        self.assertTrue(report.source_target_domain_disjoint)
        self.assertTrue(report.source_target_receipt_disjoint)
        self.assertTrue(report.same_case_baseline)
        self.assertEqual(report.source_selected, ("quantity-5",))
        self.assertEqual(report.transfer_selected, ("quantity-5",))
        self.assertEqual(report.baseline_selected, ("quantity-2",))
        self.assertEqual(report.transfer_success_count, 0)
        self.assertEqual(report.baseline_success_count, 1)
        self.assertEqual(report.transfer_verifier_calls, 1)
        self.assertEqual(report.baseline_verifier_calls, 1)
        self.assertEqual(report.success_delta, -1)
        self.assertEqual(report.verifier_call_delta, 0)
        self.assertEqual(report.conclusion, "negative_transfer")
        self.assertEqual(report.transfer_residual_kind, "stock_shortage")
        self.assertTrue(report.hard_commit_only)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.overlap_detected)


if __name__ == "__main__":
    unittest.main()
