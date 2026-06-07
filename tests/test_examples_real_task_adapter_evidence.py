from __future__ import annotations

from dataclasses import replace
import unittest

from examples.real_task_adapter_evidence import validate_real_task_adapter_evidence_certificate
from examples.robotics_motion_benchmark_adapter import (
    DeterministicMotionBenchmarkBackend,
    run_robotics_motion_benchmark_adapter_experiment,
)


class RealTaskAdapterEvidenceCertificateTests(unittest.TestCase):
    def test_valid_deterministic_adapter_evidence_passes_as_g0(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        certificate = result.evidence_certificate

        self.assertEqual(certificate.schema_version, "trwm.real_task_adapter_evidence_certificate.v1")
        self.assertEqual(certificate.domain, "robotics")
        self.assertEqual(certificate.evidence_grade, "G0")
        self.assertEqual(certificate.backend_error, result.report.backend_error)
        self.assertEqual(certificate.receipt_count, result.report.receipt_count)
        self.assertEqual(certificate.training_receipt_count, result.report.training_receipt_count)
        self.assertEqual(certificate.baseline_receipt_count, result.report.baseline_receipt_count)
        self.assertEqual(certificate.learned_receipt_count, result.report.learned_receipt_count)
        self.assertEqual(certificate.typed_candidate_hashes, result.report.typed_candidate_hashes)
        self.assertEqual(certificate.hard_result_hashes, result.report.hard_result_hashes)
        self.assertEqual(certificate.hard_metadata_hashes, result.report.hard_metadata_hashes)
        self.assertEqual(len(certificate.typed_candidate_hashes), result.report.receipt_count)
        self.assertEqual(len(certificate.hard_result_hashes), result.report.receipt_count)
        self.assertEqual(len(certificate.hard_metadata_hashes), result.report.receipt_count)
        self.assertEqual(
            certificate.receipt_hashes,
            certificate.training_receipt_hashes + certificate.baseline_receipt_hashes + certificate.learned_receipt_hashes,
        )
        self.assertTrue(
            validate_real_task_adapter_evidence_certificate(
                certificate,
                report=result.report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_unavailable_adapter_evidence_passes_with_zero_receipts(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend(available=False))
        certificate = result.evidence_certificate

        self.assertEqual(certificate.evidence_grade, "G0")
        self.assertEqual(certificate.backend_error, result.report.backend_error)
        self.assertEqual(certificate.receipt_count, 0)
        self.assertEqual(certificate.receipt_hashes, ())
        self.assertEqual(certificate.typed_candidate_hashes, ())
        self.assertEqual(certificate.hard_result_hashes, ())
        self.assertEqual(certificate.hard_metadata_hashes, ())
        self.assertEqual(certificate.learning_certificate_hash, "")
        self.assertTrue(
            validate_real_task_adapter_evidence_certificate(
                certificate,
                report=result.report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_tampered_report_hash_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        certificate = replace(result.evidence_certificate, report_hash="0" * 64, certificate_hash="")

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                certificate,
                report=result.report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_tampered_report_provenance_hash_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(result.report, hard_metadata_hashes=("0" * 64, *result.report.hard_metadata_hashes[1:]))

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=bad_report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_tampered_report_backend_error_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(result.report, backend_error="hidden backend failure")

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=bad_report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_mismatched_learning_certificate_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        assert result.learning_certificate is not None
        bad_learning = replace(
            result.learning_certificate,
            baseline_verifier_calls=result.learning_certificate.baseline_verifier_calls + 1,
            verifier_call_gain_numerator=result.learning_certificate.verifier_call_gain_numerator + 1,
            certificate_hash="",
        )

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=result.report,
                learning_certificate=bad_learning,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_mismatched_claim_certificate_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_metrics = dict(result.claim_certificate.metrics)
        bad_metrics["learned_verifier_calls"] = bad_metrics["learned_verifier_calls"] + 1
        bad_claim = replace(result.claim_certificate, metrics=bad_metrics, certificate_hash="")

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=result.report,
                learning_certificate=result.learning_certificate,
                claim_certificate=bad_claim,
            )
        )


if __name__ == "__main__":
    unittest.main()
