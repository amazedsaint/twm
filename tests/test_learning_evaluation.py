from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.evaluation import (
    LEARNING_EVALUATION_CERTIFICATE_SCHEMA,
    build_learning_evaluation_certificate,
    learning_evaluation_supports_claim,
    validate_learning_evaluation_certificate,
)
from trwm.experiments.learning_evaluation import run_learning_evaluation_benchmark


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


class LearningEvaluationTests(unittest.TestCase):
    def test_certificate_validates_trace_disjoint_same_case_learning_claim(self) -> None:
        no_invalid_commits = 0
        certificate = build_learning_evaluation_certificate(
            claim_id="test",
            learner_id="learner",
            learner_snapshot_hash=HASH_A,
            training_receipt_hashes=(HASH_B,),
            baseline_receipt_hashes=("d" * 64, "e" * 64),
            evaluation_receipt_hashes=(HASH_C,),
            baseline_name="baseline",
            learned_name="learned",
            baseline_verifier_calls=2,
            learned_verifier_calls=1,
            baseline_success_count=0,
            learned_success_count=1,
            verifier_budget=1,
            candidate_count=2,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=no_invalid_commits,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )

        self.assertEqual(certificate.schema_version, LEARNING_EVALUATION_CERTIFICATE_SCHEMA)
        self.assertTrue(certificate.train_eval_disjoint)
        self.assertEqual(certificate.baseline_receipt_hashes, ("d" * 64, "e" * 64))
        self.assertEqual(certificate.verifier_call_gain_numerator, 2)
        self.assertEqual(certificate.verifier_call_gain_denominator, 1)
        self.assertEqual(certificate.verifier_call_gain, 2.0)
        self.assertTrue(validate_learning_evaluation_certificate(certificate))
        self.assertTrue(learning_evaluation_supports_claim(certificate))

    def test_certificate_rejects_overlap_duplicate_and_tamper(self) -> None:
        no_invalid_commits = 0
        overlap = build_learning_evaluation_certificate(
            claim_id="test",
            learner_id="learner",
            learner_snapshot_hash=HASH_A,
            training_receipt_hashes=(HASH_B,),
            evaluation_receipt_hashes=(HASH_B,),
            baseline_name="baseline",
            learned_name="learned",
            baseline_verifier_calls=2,
            learned_verifier_calls=1,
            baseline_success_count=0,
            learned_success_count=1,
            verifier_budget=1,
            candidate_count=2,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=no_invalid_commits,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )
        duplicate = replace(overlap, evaluation_receipt_hashes=(HASH_C, HASH_C), train_eval_disjoint=True, certificate_hash="")
        tampered = replace(duplicate, baseline_verifier_calls=9)
        baseline_overlap = build_learning_evaluation_certificate(
            claim_id="test",
            learner_id="learner",
            learner_snapshot_hash=HASH_A,
            training_receipt_hashes=(HASH_B,),
            baseline_receipt_hashes=(HASH_B,),
            evaluation_receipt_hashes=(HASH_C,),
            baseline_name="baseline",
            learned_name="learned",
            baseline_verifier_calls=1,
            learned_verifier_calls=1,
            baseline_success_count=0,
            learned_success_count=1,
            verifier_budget=1,
            candidate_count=2,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=no_invalid_commits,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )
        baseline_count_mismatch = build_learning_evaluation_certificate(
            claim_id="test",
            learner_id="learner",
            learner_snapshot_hash=HASH_A,
            training_receipt_hashes=(HASH_B,),
            baseline_receipt_hashes=("d" * 64,),
            evaluation_receipt_hashes=(HASH_C,),
            baseline_name="baseline",
            learned_name="learned",
            baseline_verifier_calls=2,
            learned_verifier_calls=1,
            baseline_success_count=0,
            learned_success_count=1,
            verifier_budget=1,
            candidate_count=2,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=no_invalid_commits,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )

        self.assertFalse(validate_learning_evaluation_certificate(overlap))
        self.assertFalse(validate_learning_evaluation_certificate(duplicate))
        self.assertFalse(validate_learning_evaluation_certificate(tampered))
        self.assertFalse(validate_learning_evaluation_certificate(baseline_overlap))
        self.assertFalse(validate_learning_evaluation_certificate(baseline_count_mismatch))

    def test_certificate_supports_call_reduction_when_success_is_preserved(self) -> None:
        certificate = build_learning_evaluation_certificate(
            claim_id="test_call_reduction",
            learner_id="learner",
            learner_snapshot_hash=HASH_A,
            training_receipt_hashes=(HASH_B,),
            evaluation_receipt_hashes=(HASH_C,),
            baseline_name="baseline",
            learned_name="learned",
            baseline_verifier_calls=2,
            learned_verifier_calls=1,
            baseline_success_count=1,
            learned_success_count=1,
            verifier_budget=1,
            candidate_count=2,
            same_case_baseline=True,
            hard_commit_only=True,
            invalid_commit_count=0,
            ledger_audit=True,
            replay_rollback_rate=1.0,
        )

        self.assertTrue(validate_learning_evaluation_certificate(certificate))
        self.assertTrue(learning_evaluation_supports_claim(certificate))

    def test_learning_evaluation_benchmark_certifies_budget_policy_claim_boundary(self) -> None:
        report = run_learning_evaluation_benchmark()

        self.assertEqual(report.schema_version, LEARNING_EVALUATION_CERTIFICATE_SCHEMA)
        self.assertTrue(report.certificate_valid)
        self.assertTrue(report.certificate_supports_claim)
        self.assertEqual(report.claim_id, "budget_policy_trace_disjoint_eval")
        self.assertEqual(report.training_receipt_count, 3)
        self.assertEqual(report.evaluation_receipt_count, 1)
        self.assertTrue(report.train_eval_disjoint)
        self.assertTrue(report.same_case_baseline)
        self.assertEqual(report.baseline_success_count, 0)
        self.assertEqual(report.learned_success_count, 1)
        self.assertEqual(report.baseline_verifier_calls, 2)
        self.assertEqual(report.learned_verifier_calls, 1)
        self.assertEqual(report.verifier_call_gain_numerator, 2)
        self.assertEqual(report.verifier_call_gain_denominator, 1)
        self.assertTrue(report.hard_commit_only)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.overlap_detected)


if __name__ == "__main__":
    unittest.main()
