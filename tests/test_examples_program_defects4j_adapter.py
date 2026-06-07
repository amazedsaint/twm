from __future__ import annotations

import unittest

from examples.program_defects4j_adapter import (
    Defects4JProgramBackend,
    DeterministicDefects4JBackend,
    PROGRAM_DEFECTS4J_REQUIRED_TOOLS,
    run_program_defects4j_adapter_experiment,
)
from examples.real_task_adapter_evidence import validate_real_task_adapter_evidence_certificate
from trwm.claims import validate_claim_certificate
from trwm.evaluation import learning_evaluation_supports_claim, validate_learning_evaluation_certificate


class ProgramDefects4JAdapterTests(unittest.TestCase):
    def test_unavailable_backend_fails_closed_without_receipts(self) -> None:
        result = run_program_defects4j_adapter_experiment(DeterministicDefects4JBackend(available=False))
        report = result.report

        self.assertFalse(report.backend_available)
        self.assertEqual(report.missing_requirements, PROGRAM_DEFECTS4J_REQUIRED_TOOLS)
        self.assertEqual(report.receipt_count, 0)
        self.assertEqual(report.typed_candidate_hashes, ())
        self.assertEqual(report.hard_result_hashes, ())
        self.assertEqual(report.hard_metadata_hashes, ())
        self.assertFalse(report.receipt_artifacts_bound)
        self.assertEqual(report.receipt_artifact_hashes, ())
        self.assertFalse(report.backend_execution_evidence_ok)
        self.assertEqual(report.backend_execution_evidence_hashes, ())
        self.assertFalse(report.heldout_arm_isolated)
        self.assertIsNone(result.learning_certificate)
        self.assertTrue(validate_real_task_adapter_evidence_certificate(
            result.evidence_certificate,
            report=report,
            learning_certificate=result.learning_certificate,
            claim_certificate=result.claim_certificate,
        ))
        self.assertEqual(result.evidence_certificate.evidence_grade, "G0")
        self.assertFalse(result.evidence_certificate.heldout_arm_isolated)
        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertEqual(result.claim_certificate.evidence_grade, "G0")
        self.assertIn("backend_available", result.claim_certificate.failed_keys)

    def test_deterministic_backend_exercises_receipt_trained_program_adapter_mechanics(self) -> None:
        result = run_program_defects4j_adapter_experiment(DeterministicDefects4JBackend())
        report = result.report

        self.assertTrue(report.backend_available)
        self.assertFalse(report.real_backend)
        self.assertEqual(report.task_count, 3)
        self.assertEqual(report.train_task_ids, ("train-lang-1",))
        self.assertEqual(report.held_out_task_ids, ("heldout-math-5", "heldout-chart-1"))
        self.assertEqual(report.training_receipt_count, 2)
        self.assertEqual(report.baseline_receipt_count, 4)
        self.assertEqual(report.learned_receipt_count, 2)
        self.assertEqual(report.receipt_count, 8)
        self.assertEqual(report.committed_count, 5)
        self.assertEqual(report.rejected_count, 3)
        self.assertEqual(report.baseline_verifier_calls, 4)
        self.assertEqual(report.learned_verifier_calls, 2)
        self.assertEqual(report.verifier_call_reduction, 2)
        self.assertEqual(report.verifier_call_gain, 2.0)
        self.assertEqual(report.baseline_success_count, 2)
        self.assertEqual(report.learned_success_count, 2)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.hard_commit_only)
        self.assertTrue(report.train_eval_disjoint)
        self.assertTrue(report.heldout_arm_isolated)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertTrue(report.receipt_artifacts_bound)
        self.assertTrue(report.backend_execution_evidence_ok)
        self.assertTrue(report.learning_certificate_valid)
        self.assertTrue(report.learning_certificate_supports_claim)
        self.assertTrue(report.source_urls)
        self.assertIsNotNone(result.learning_certificate)
        assert result.learning_certificate is not None
        self.assertTrue(validate_real_task_adapter_evidence_certificate(
            result.evidence_certificate,
            report=report,
            learning_certificate=result.learning_certificate,
            claim_certificate=result.claim_certificate,
        ))
        self.assertEqual(result.evidence_certificate.evidence_grade, "G0")
        self.assertTrue(result.evidence_certificate.heldout_arm_isolated)
        self.assertEqual(result.evidence_certificate.receipt_count, report.receipt_count)
        self.assertEqual(result.evidence_certificate.learned_receipt_hashes, result.learning_certificate.evaluation_receipt_hashes)
        self.assertEqual(result.evidence_certificate.typed_candidate_hashes, report.typed_candidate_hashes)
        self.assertEqual(result.evidence_certificate.hard_result_hashes, report.hard_result_hashes)
        self.assertEqual(result.evidence_certificate.hard_metadata_hashes, report.hard_metadata_hashes)
        self.assertEqual(result.evidence_certificate.receipt_artifact_hashes, report.receipt_artifact_hashes)
        self.assertEqual(result.evidence_certificate.backend_execution_evidence_hashes, report.backend_execution_evidence_hashes)
        self.assertTrue(validate_learning_evaluation_certificate(result.learning_certificate))
        self.assertTrue(learning_evaluation_supports_claim(result.learning_certificate))
        self.assertEqual(result.learning_certificate.metrics["heldout_arm_isolated"], True)

        self.assertEqual(len(report.receipt_hashes), report.receipt_count)
        self.assertEqual(len(report.typed_candidate_hashes), report.receipt_count)
        self.assertEqual(len(report.hard_result_hashes), report.receipt_count)
        self.assertEqual(len(report.hard_metadata_hashes), report.receipt_count)
        self.assertEqual(len(report.receipt_artifact_hashes), report.receipt_count)
        self.assertEqual(len(report.backend_execution_evidence_hashes), report.receipt_count)
        for row in report.rows:
            self.assertEqual(row.baseline_verifier_calls, 2)
            self.assertEqual(row.learned_verifier_calls, 1)
            self.assertEqual(row.baseline_success_count, 1)
            self.assertEqual(row.learned_success_count, 1)
            self.assertEqual(len(row.baseline_receipt_hashes), 2)
            self.assertEqual(len(row.learned_receipt_hashes), 1)

    def test_deterministic_backend_cannot_support_real_program_claim(self) -> None:
        result = run_program_defects4j_adapter_experiment(DeterministicDefects4JBackend())

        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertEqual(result.claim_certificate.evidence_grade, "G0")
        self.assertIn("real_defects4j_backend", result.claim_certificate.failed_keys)
        self.assertNotIn("receipt_artifacts_bound", result.claim_certificate.failed_keys)
        self.assertNotIn("backend_execution_evidence_bound", result.claim_certificate.failed_keys)
        self.assertNotIn("learning_certificate_supports_claim", result.claim_certificate.failed_keys)
        self.assertNotIn("heldout_arm_isolated", result.claim_certificate.failed_keys)
        self.assertIn("Single-domain program adapter evidence only", result.claim_certificate.boundary)

    def test_default_backend_reports_missing_tools_or_real_backend(self) -> None:
        backend = Defects4JProgramBackend(timeout_seconds=1)
        result = run_program_defects4j_adapter_experiment(backend)

        self.assertEqual(result.report.backend_id, "defects4j.cli")
        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        if result.report.backend_available:
            self.assertTrue(result.report.real_backend)
            self.assertEqual(
                result.claim_certificate.evidence_grade,
                "G1" if result.report.receipt_artifacts_bound and result.report.backend_execution_evidence_ok else "G0",
            )
        else:
            self.assertEqual(result.claim_certificate.status, "rejected")
            self.assertEqual(result.claim_certificate.evidence_grade, "G0")
            self.assertTrue(result.report.missing_requirements or result.report.backend_error)


if __name__ == "__main__":
    unittest.main()
