from __future__ import annotations

from dataclasses import replace
import unittest

from examples.common import validate_example_evidence_certificate
from examples.receipt_trained_reversible_proposer_benchmark import (
    BENCHMARK_SOURCES,
    run_receipt_trained_reversible_proposer_benchmark,
)
from trwm.claims import validate_claim_certificate
from trwm.evaluation import learning_evaluation_supports_claim, validate_learning_evaluation_certificate


class ReceiptTrainedReversibleProposerBenchmarkTests(unittest.TestCase):
    def test_certified_receipt_trained_reversible_proposer_benchmark(self) -> None:
        result = run_receipt_trained_reversible_proposer_benchmark()
        report = result.report

        self.assertEqual(report.domain_count, 4)
        self.assertEqual(report.domains, ("robotics", "hardware", "program", "quantum"))
        self.assertEqual(report.training_receipt_count, 8)
        self.assertEqual(report.baseline_receipt_count, 8)
        self.assertEqual(report.learned_receipt_count, 4)
        self.assertEqual(report.receipt_count, 20)
        self.assertEqual(report.committed_count, 12)
        self.assertEqual(report.rejected_count, 8)
        self.assertEqual(report.baseline_success_count, 4)
        self.assertEqual(report.learned_success_count, 4)
        self.assertEqual(report.baseline_verifier_calls, 8)
        self.assertEqual(report.learned_verifier_calls, 4)
        self.assertEqual(report.verifier_call_reduction, 4)
        self.assertEqual(report.verifier_call_gain, 2.0)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.same_case_baseline)
        self.assertTrue(report.train_eval_disjoint)
        self.assertTrue(report.hard_commit_only)
        self.assertTrue(report.all_reversible_cycles_ok)
        self.assertTrue(report.replay_audit_ok)
        self.assertTrue(report.rollback_audit_ok)
        self.assertTrue(report.ledger_audit_ok)
        self.assertTrue(report.learner_snapshot_valid)
        self.assertTrue(report.learning_certificate_valid)
        self.assertTrue(report.learning_certificate_supports_claim)
        self.assertEqual(report.source_urls, BENCHMARK_SOURCES)

        self.assertTrue(validate_example_evidence_certificate(result.evidence_certificate, report))
        self.assertTrue(validate_learning_evaluation_certificate(result.learning_certificate))
        self.assertTrue(learning_evaluation_supports_claim(result.learning_certificate))
        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        self.assertEqual(result.claim_certificate.status, "supported")
        self.assertEqual(result.evidence_certificate.receipt_hashes, report.receipt_hashes)
        self.assertEqual(result.evidence_certificate.receipt_count, report.receipt_count)
        self.assertEqual(result.evidence_certificate.committed_count, report.committed_count)
        self.assertEqual(result.evidence_certificate.rejected_count, report.rejected_count)
        self.assertEqual(len(result.learning_certificate.training_receipt_hashes), report.training_receipt_count)
        self.assertEqual(len(result.learning_certificate.baseline_receipt_hashes), report.baseline_receipt_count)
        self.assertEqual(len(result.learning_certificate.evaluation_receipt_hashes), report.learned_receipt_count)
        self.assertTrue(set(report.train_task_ids).isdisjoint(report.held_out_task_ids))

        for row in report.rows:
            self.assertEqual(row.baseline_verifier_calls, 2)
            self.assertEqual(row.learned_verifier_calls, 1)
            self.assertEqual(row.baseline_success_count, 1)
            self.assertEqual(row.learned_success_count, 1)
            self.assertEqual(len(row.training_receipt_hashes), 2)
            self.assertEqual(len(row.baseline_receipt_hashes), 2)
            self.assertEqual(len(row.learned_receipt_hashes), 1)
            self.assertTrue(row.reversible_cycle_ok)
            self.assertTrue(row.next_real_benchmark)

    def test_tampered_evidence_and_learning_certificates_fail(self) -> None:
        result = run_receipt_trained_reversible_proposer_benchmark()
        bad_evidence = replace(result.evidence_certificate, report_hash="0" * 64)
        bad_learning = replace(result.learning_certificate, learned_verifier_calls=result.learning_certificate.baseline_verifier_calls)

        self.assertFalse(validate_example_evidence_certificate(bad_evidence, result.report))
        self.assertFalse(validate_learning_evaluation_certificate(bad_learning))
        self.assertFalse(learning_evaluation_supports_claim(bad_learning))


if __name__ == "__main__":
    unittest.main()
