from __future__ import annotations

from dataclasses import replace
import unittest

from examples.real_task_adapter_evidence import (
    real_task_adapter_claim_evidence_grade,
    validate_real_task_adapter_evidence_certificate,
)
from examples.robotics_motion_benchmark_adapter import (
    DeterministicMotionBenchmarkBackend,
    _claim_for_report as robotics_claim_for_report,
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
        self.assertEqual(certificate.runtime_requirement_evidence_hashes, result.report.runtime_requirement_evidence_hashes)
        self.assertEqual(certificate.runtime_requirement_evidence_hashes, ())
        self.assertTrue(certificate.learner_snapshot_valid)
        self.assertEqual(certificate.learner_snapshot_valid, result.report.learner_snapshot_valid)
        self.assertEqual(certificate.learner_snapshot_receipt_hashes, certificate.training_receipt_hashes)
        self.assertEqual(certificate.learner_snapshot_receipt_hashes, result.report.learner_snapshot_receipt_hashes)
        self.assertEqual(certificate.learner_snapshot_row_hashes, result.report.learner_snapshot_row_hashes)
        self.assertTrue(certificate.learner_snapshot_row_hashes)
        self.assertEqual(certificate.receipt_count, result.report.receipt_count)
        self.assertEqual(certificate.training_receipt_count, result.report.training_receipt_count)
        self.assertEqual(certificate.baseline_receipt_count, result.report.baseline_receipt_count)
        self.assertEqual(certificate.learned_receipt_count, result.report.learned_receipt_count)
        self.assertTrue(certificate.heldout_arm_isolated)
        self.assertEqual(certificate.heldout_arm_isolated, result.report.heldout_arm_isolated)
        self.assertTrue(certificate.proposer_rank_audit_ok)
        self.assertEqual(certificate.proposer_rank_audit_ok, result.report.proposer_rank_audit_ok)
        self.assertEqual(certificate.proposer_rank_audit_hashes, result.report.proposer_rank_audit_hashes)
        self.assertEqual(len(certificate.proposer_rank_audit_hashes), len(certificate.held_out_task_ids))
        self.assertEqual(certificate.typed_candidate_hashes, result.report.typed_candidate_hashes)
        self.assertEqual(certificate.hard_result_hashes, result.report.hard_result_hashes)
        self.assertEqual(certificate.hard_metadata_hashes, result.report.hard_metadata_hashes)
        self.assertEqual(certificate.receipt_artifacts_bound, result.report.receipt_artifacts_bound)
        self.assertEqual(certificate.receipt_artifact_hashes, result.report.receipt_artifact_hashes)
        self.assertEqual(certificate.receipt_artifact_value_hashes, result.report.receipt_artifact_value_hashes)
        self.assertTrue(certificate.receipt_artifact_value_hashes)
        self.assertEqual(certificate.backend_execution_evidence_ok, result.report.backend_execution_evidence_ok)
        self.assertEqual(certificate.backend_execution_evidence_hashes, result.report.backend_execution_evidence_hashes)
        self.assertEqual(len(certificate.typed_candidate_hashes), result.report.receipt_count)
        self.assertEqual(len(certificate.hard_result_hashes), result.report.receipt_count)
        self.assertEqual(len(certificate.hard_metadata_hashes), result.report.receipt_count)
        self.assertEqual(len(certificate.receipt_artifact_hashes), result.report.receipt_count)
        self.assertEqual(len(certificate.backend_execution_evidence_hashes), result.report.receipt_count)
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
        self.assertEqual(certificate.runtime_requirement_evidence_hashes, ())
        self.assertFalse(certificate.learner_snapshot_valid)
        self.assertEqual(certificate.learner_snapshot_receipt_hashes, ())
        self.assertEqual(certificate.learner_snapshot_row_hashes, ())
        self.assertFalse(certificate.receipt_artifacts_bound)
        self.assertEqual(certificate.receipt_artifact_hashes, ())
        self.assertEqual(certificate.receipt_artifact_value_hashes, ())
        self.assertFalse(certificate.backend_execution_evidence_ok)
        self.assertEqual(certificate.backend_execution_evidence_hashes, ())
        self.assertEqual(certificate.learning_certificate_hash, "")
        self.assertFalse(certificate.heldout_arm_isolated)
        self.assertFalse(certificate.proposer_rank_audit_ok)
        self.assertEqual(certificate.proposer_rank_audit_hashes, ())
        self.assertEqual(certificate.heldout_arm_isolated, result.report.heldout_arm_isolated)
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

    def test_tampered_report_backend_execution_evidence_hash_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(
            result.report,
            backend_execution_evidence_hashes=("0" * 64, *result.report.backend_execution_evidence_hashes[1:]),
        )

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=bad_report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_tampered_report_runtime_requirement_evidence_hash_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(result.report, runtime_requirement_evidence_hashes=("f" * 64,))

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=bad_report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_tampered_report_learner_snapshot_hashes_fail(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(result.report, learner_snapshot_receipt_hashes=("0" * 64, *result.report.learner_snapshot_receipt_hashes[1:]))

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=bad_report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_tampered_report_proposer_rank_audit_hash_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(result.report, proposer_rank_audit_hashes=("0" * 64, *result.report.proposer_rank_audit_hashes[1:]))

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=bad_report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_tampered_report_receipt_artifact_hash_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(
            result.report,
            receipt_artifact_hashes=("0" * 64, *result.report.receipt_artifact_hashes[1:]),
        )

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=bad_report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_tampered_report_receipt_artifact_value_hash_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(
            result.report,
            receipt_artifact_value_hashes=("0" * 64, *result.report.receipt_artifact_value_hashes[1:]),
        )

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                result.evidence_certificate,
                report=bad_report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_zero_receipt_backend_execution_evidence_ok_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend(available=False))
        certificate = replace(result.evidence_certificate, backend_execution_evidence_ok=True, certificate_hash="")

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                certificate,
                report=result.report,
                learning_certificate=result.learning_certificate,
                claim_certificate=result.claim_certificate,
            )
        )

    def test_zero_receipt_artifacts_bound_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend(available=False))
        certificate = replace(result.evidence_certificate, receipt_artifacts_bound=True, certificate_hash="")

        self.assertFalse(
            validate_real_task_adapter_evidence_certificate(
                certificate,
                report=result.report,
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

    def test_tampered_report_heldout_arm_isolation_fails(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        bad_report = replace(result.report, heldout_arm_isolated=False)

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
        self.assertEqual(result.learning_certificate.baseline_receipt_hashes, result.evidence_certificate.baseline_receipt_hashes)
        bad_learning = replace(
            result.learning_certificate,
            baseline_receipt_hashes=tuple(f"{index}" * 64 for index in ("1", "2", "3", "4")),
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

    def test_adapter_claim_grade_requires_all_objective_gates(self) -> None:
        result = run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend())
        report = replace(
            result.report,
            backend_available=True,
            real_backend=True,
            runtime_requirement_evidence_hashes=("f" * 64,),
        )

        self.assertEqual(real_task_adapter_claim_evidence_grade(report), "G1")
        claim = robotics_claim_for_report(report)
        self.assertEqual(claim.status, "supported")
        self.assertEqual(claim.evidence_grade, "G1")

        cases = (
            ("learning_certificate_valid", replace(report, learning_certificate_valid=False), "learning_certificate_valid"),
            (
                "learning_certificate_supports_claim",
                replace(report, learning_certificate_supports_claim=False),
                "learning_certificate_supports_claim",
            ),
            (
                "hard_verifier_calls_reduced",
                replace(report, learned_verifier_calls=report.baseline_verifier_calls, verifier_call_reduction=0),
                "hard_verifier_calls_reduced",
            ),
            ("success_preserved", replace(report, learned_success_count=0), "success_preserved"),
            ("zero_invalid_commits", replace(report, invalid_commit_count=1), "zero_invalid_commits"),
            ("hard_commit_only", replace(report, hard_commit_only=False), "hard_commit_only"),
            ("train_eval_disjoint", replace(report, train_eval_disjoint=False), "train_eval_disjoint"),
            ("heldout_arm_isolated", replace(report, heldout_arm_isolated=False), "heldout_arm_isolated"),
            ("replay_rollback_ok", replace(report, replay_audit_ok=False), "replay_rollback_ok"),
            ("backend_execution_evidence_bound", replace(report, backend_execution_evidence_ok=False), "backend_execution_evidence_bound"),
        )
        for case_name, bad_report, failed_key in cases:
            with self.subTest(case=case_name):
                self.assertEqual(real_task_adapter_claim_evidence_grade(bad_report), "G0")
                bad_claim = robotics_claim_for_report(bad_report)
                self.assertEqual(bad_claim.status, "rejected")
                self.assertEqual(bad_claim.evidence_grade, "G0")
                self.assertIn(failed_key, bad_claim.failed_keys)


if __name__ == "__main__":
    unittest.main()
