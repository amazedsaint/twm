from __future__ import annotations

from dataclasses import replace
import unittest

from examples.hardware_riscv_formal_adapter import (
    DeterministicRiscVFormalBackend,
    run_hardware_riscv_formal_adapter_experiment,
)
from examples.program_defects4j_adapter import (
    DeterministicDefects4JBackend,
    run_program_defects4j_adapter_experiment,
)
from examples.quantum_mqt_bench_adapter import (
    DeterministicQuantumEquivalenceBackend,
    run_quantum_mqt_bench_adapter_experiment,
)
from examples.real_task_benchmark_suite import (
    REAL_TASK_BENCHMARK_SUITE_DOMAINS,
    build_real_task_benchmark_suite_result,
    run_real_task_benchmark_suite,
    validate_real_task_benchmark_suite_certificate,
    validate_real_task_benchmark_suite_report,
)
from examples.real_task_adapter_evidence import build_real_task_adapter_evidence_certificate
from examples.robotics_motion_benchmark_adapter import (
    DeterministicMotionBenchmarkBackend,
    _claim_for_report as _robotics_claim_for_report,
    run_robotics_motion_benchmark_adapter_experiment,
)
from trwm.claims import validate_claim_certificate


def _deterministic_adapter_results() -> dict[str, object]:
    return {
        "robotics": run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend()),
        "hardware": run_hardware_riscv_formal_adapter_experiment(DeterministicRiscVFormalBackend()),
        "program": run_program_defects4j_adapter_experiment(DeterministicDefects4JBackend()),
        "quantum": run_quantum_mqt_bench_adapter_experiment(DeterministicQuantumEquivalenceBackend()),
    }


class RealTaskBenchmarkSuiteTests(unittest.TestCase):
    def test_suite_aggregates_four_domain_adapter_metrics_but_rejects_test_doubles(self) -> None:
        result = run_real_task_benchmark_suite(_deterministic_adapter_results())
        report = result.report
        claim = result.claim_certificate

        self.assertEqual(report.schema_version, "trwm.real_task_benchmark_suite_report.v1")
        self.assertEqual(report.domains, REAL_TASK_BENCHMARK_SUITE_DOMAINS)
        self.assertEqual(report.domain_count, 4)
        self.assertEqual(len(report.rows), 4)
        self.assertTrue(report.all_child_claims_valid)
        self.assertFalse(report.all_child_claims_supported)
        self.assertTrue(report.all_child_claims_match_reports)
        self.assertTrue(report.all_adapter_evidence_certificates_valid)
        self.assertTrue(report.all_adapter_evidence_certificates_match_reports)
        self.assertTrue(report.all_adapter_evidence_matches_manifest)
        self.assertTrue(all(row.child_claim_valid for row in report.rows))
        self.assertTrue(all(row.child_claim_matches_report for row in report.rows))
        self.assertTrue(all(row.adapter_evidence_certificate_valid for row in report.rows))
        self.assertTrue(all(row.adapter_evidence_certificate_matches_report for row in report.rows))
        self.assertTrue(all(row.adapter_evidence_matches_manifest for row in report.rows))
        self.assertTrue(all(len(row.manifest_spec_hash) == 64 for row in report.rows))
        self.assertTrue(report.all_learning_certificates_valid)
        self.assertTrue(report.all_learning_certificates_support_claim)
        self.assertTrue(report.all_learning_certificates_match_reports)
        self.assertTrue(all(row.learning_certificate_matches_report for row in report.rows))
        self.assertTrue(report.all_backends_available)
        self.assertFalse(report.all_real_backends)
        self.assertTrue(report.all_receipt_counts_bound)
        self.assertTrue(report.hard_verifier_calls_reduced)
        self.assertTrue(report.success_preserved)
        self.assertTrue(report.replay_rollback_ledger_ok)
        self.assertTrue(report.no_invalid_commits)
        self.assertEqual(report.total_receipt_count, 32)
        self.assertEqual(report.total_training_receipt_count, 8)
        self.assertEqual(report.total_baseline_receipt_count, 16)
        self.assertEqual(report.total_learned_receipt_count, 8)
        self.assertEqual(report.total_committed_count, 20)
        self.assertEqual(report.total_rejected_count, 12)
        self.assertEqual(report.total_invalid_commit_count, 0)
        self.assertEqual(report.baseline_verifier_calls, 16)
        self.assertEqual(report.learned_verifier_calls, 8)
        self.assertEqual(report.verifier_call_reduction, 8)
        self.assertEqual(report.baseline_success_count, 8)
        self.assertEqual(report.learned_success_count, 8)
        for row in report.rows:
            self.assertEqual(len(row.receipt_hashes), row.receipt_count)
            self.assertEqual(len(row.typed_candidate_hashes), row.receipt_count)
            self.assertEqual(len(row.hard_result_hashes), row.receipt_count)
            self.assertEqual(len(row.hard_metadata_hashes), row.receipt_count)

        self.assertTrue(validate_real_task_benchmark_suite_report(report))
        self.assertEqual(
            result.suite_certificate.child_report_hashes,
            tuple(row.child_report_hash for row in report.rows),
        )
        self.assertEqual(
            result.suite_certificate.adapter_evidence_certificate_hashes,
            tuple(row.adapter_evidence_certificate_hash for row in report.rows),
        )
        self.assertEqual(
            result.suite_certificate.manifest_spec_hashes,
            tuple(row.manifest_spec_hash for row in report.rows),
        )
        self.assertEqual(
            result.suite_certificate.receipt_hashes,
            tuple(receipt_hash for row in report.rows for receipt_hash in row.receipt_hashes),
        )
        self.assertEqual(
            result.suite_certificate.typed_candidate_hashes,
            tuple(candidate_hash for row in report.rows for candidate_hash in row.typed_candidate_hashes),
        )
        self.assertEqual(
            result.suite_certificate.hard_result_hashes,
            tuple(result_hash for row in report.rows for result_hash in row.hard_result_hashes),
        )
        self.assertEqual(
            result.suite_certificate.hard_metadata_hashes,
            tuple(metadata_hash for row in report.rows for metadata_hash in row.hard_metadata_hashes),
        )
        self.assertTrue(result.suite_certificate.all_child_claims_match_reports)
        self.assertTrue(result.suite_certificate.all_adapter_evidence_certificates_valid)
        self.assertTrue(result.suite_certificate.all_adapter_evidence_certificates_match_reports)
        self.assertTrue(result.suite_certificate.all_adapter_evidence_matches_manifest)
        self.assertTrue(result.suite_certificate.all_learning_certificates_match_reports)
        self.assertTrue(validate_real_task_benchmark_suite_certificate(result.suite_certificate, report))
        self.assertTrue(validate_claim_certificate(claim))
        self.assertEqual(claim.status, "rejected")
        self.assertEqual(claim.evidence_grade, "G0")
        self.assertIn("all_child_claims_supported", claim.failed_keys)
        self.assertIn("all_real_backends", claim.failed_keys)

    def test_suite_rejects_unavailable_adapters_with_zero_receipts(self) -> None:
        results = {
            "robotics": run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend(available=False)),
            "hardware": run_hardware_riscv_formal_adapter_experiment(DeterministicRiscVFormalBackend(available=False)),
            "program": run_program_defects4j_adapter_experiment(DeterministicDefects4JBackend(available=False)),
            "quantum": run_quantum_mqt_bench_adapter_experiment(DeterministicQuantumEquivalenceBackend(available=False)),
        }
        result = build_real_task_benchmark_suite_result(results)

        self.assertEqual(result.report.total_receipt_count, 0)
        self.assertEqual(result.suite_certificate.receipt_hashes, ())
        self.assertEqual(result.suite_certificate.typed_candidate_hashes, ())
        self.assertEqual(result.suite_certificate.hard_result_hashes, ())
        self.assertEqual(result.suite_certificate.hard_metadata_hashes, ())
        self.assertFalse(result.report.all_backends_available)
        self.assertTrue(result.report.all_child_claims_match_reports)
        self.assertTrue(result.report.all_adapter_evidence_certificates_valid)
        self.assertTrue(result.report.all_adapter_evidence_certificates_match_reports)
        self.assertTrue(result.report.all_learning_certificates_match_reports)
        self.assertFalse(result.report.hard_verifier_calls_reduced)
        self.assertFalse(result.report.success_preserved)
        self.assertTrue(result.report.missing_requirements)
        self.assertTrue(validate_real_task_benchmark_suite_certificate(result.suite_certificate, result.report))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertIn("all_backends_available", result.claim_certificate.failed_keys)
        self.assertIn("hard_verifier_calls_reduced", result.claim_certificate.failed_keys)

    def test_suite_rejects_tampered_child_claim_certificate(self) -> None:
        results = _deterministic_adapter_results()
        robotics = results["robotics"]
        results["robotics"] = replace(
            robotics,
            claim_certificate=replace(robotics.claim_certificate, certificate_hash="0" * 64),
        )
        result = build_real_task_benchmark_suite_result(results)

        self.assertFalse(result.report.all_child_claims_valid)
        self.assertFalse(result.report.all_child_claims_match_reports)
        self.assertFalse(result.report.all_adapter_evidence_certificates_valid)
        self.assertFalse(result.report.all_adapter_evidence_certificates_match_reports)
        self.assertFalse(result.report.all_adapter_evidence_matches_manifest)
        self.assertTrue(validate_real_task_benchmark_suite_report(result.report))
        self.assertTrue(validate_real_task_benchmark_suite_certificate(result.suite_certificate, result.report))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertIn("all_child_claims_valid", result.claim_certificate.failed_keys)
        self.assertIn("all_child_claims_match_reports", result.claim_certificate.failed_keys)
        self.assertIn("all_adapter_evidence_certificates_valid", result.claim_certificate.failed_keys)
        self.assertIn("all_adapter_evidence_certificates_match_reports", result.claim_certificate.failed_keys)
        self.assertIn("all_adapter_evidence_matches_manifest", result.claim_certificate.failed_keys)

    def test_suite_rejects_valid_child_claim_that_does_not_match_report(self) -> None:
        results = _deterministic_adapter_results()
        robotics = results["robotics"]
        bad_metrics = dict(robotics.claim_certificate.metrics)
        bad_metrics["baseline_verifier_calls"] = bad_metrics["baseline_verifier_calls"] + 1
        results["robotics"] = replace(
            robotics,
            claim_certificate=replace(robotics.claim_certificate, metrics=bad_metrics, certificate_hash=""),
        )
        result = build_real_task_benchmark_suite_result(results)

        self.assertTrue(result.report.all_child_claims_valid)
        self.assertFalse(result.report.all_child_claims_match_reports)
        self.assertFalse(result.report.all_adapter_evidence_certificates_valid)
        self.assertFalse(result.report.all_adapter_evidence_certificates_match_reports)
        self.assertFalse(result.report.all_adapter_evidence_matches_manifest)
        self.assertTrue(validate_real_task_benchmark_suite_report(result.report))
        self.assertTrue(validate_real_task_benchmark_suite_certificate(result.suite_certificate, result.report))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertIn("all_child_claims_match_reports", result.claim_certificate.failed_keys)
        self.assertIn("all_adapter_evidence_certificates_valid", result.claim_certificate.failed_keys)

    def test_suite_rejects_valid_adapter_evidence_outside_manifest_sources(self) -> None:
        results = _deterministic_adapter_results()
        robotics = results["robotics"]
        bad_report = replace(
            robotics.report,
            source_urls=(*robotics.report.source_urls, "https://example.invalid/not-in-real-task-manifest"),
        )
        bad_claim = _robotics_claim_for_report(bad_report)
        bad_evidence = build_real_task_adapter_evidence_certificate(
            domain="robotics",
            report=bad_report,
            learning_certificate=robotics.learning_certificate,
            claim_certificate=bad_claim,
        )
        results["robotics"] = replace(
            robotics,
            report=bad_report,
            evidence_certificate=bad_evidence,
            claim_certificate=bad_claim,
        )
        result = build_real_task_benchmark_suite_result(results)

        self.assertTrue(result.report.all_child_claims_valid)
        self.assertTrue(result.report.all_child_claims_match_reports)
        self.assertTrue(result.report.all_adapter_evidence_certificates_valid)
        self.assertTrue(result.report.all_adapter_evidence_certificates_match_reports)
        self.assertFalse(result.report.all_adapter_evidence_matches_manifest)
        self.assertTrue(validate_real_task_benchmark_suite_report(result.report))
        self.assertTrue(validate_real_task_benchmark_suite_certificate(result.suite_certificate, result.report))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertIn("all_adapter_evidence_matches_manifest", result.claim_certificate.failed_keys)

    def test_suite_rejects_tampered_adapter_evidence_certificate(self) -> None:
        results = _deterministic_adapter_results()
        robotics = results["robotics"]
        results["robotics"] = replace(
            robotics,
            evidence_certificate=replace(robotics.evidence_certificate, certificate_hash="0" * 64),
        )
        result = build_real_task_benchmark_suite_result(results)

        self.assertTrue(result.report.all_child_claims_valid)
        self.assertTrue(result.report.all_child_claims_match_reports)
        self.assertFalse(result.report.all_adapter_evidence_certificates_valid)
        self.assertFalse(result.report.all_adapter_evidence_certificates_match_reports)
        self.assertFalse(result.report.all_adapter_evidence_matches_manifest)
        self.assertTrue(validate_real_task_benchmark_suite_report(result.report))
        self.assertTrue(validate_real_task_benchmark_suite_certificate(result.suite_certificate, result.report))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertIn("all_adapter_evidence_certificates_valid", result.claim_certificate.failed_keys)
        self.assertIn("all_adapter_evidence_certificates_match_reports", result.claim_certificate.failed_keys)

    def test_suite_rejects_valid_learning_certificate_that_does_not_match_report(self) -> None:
        results = _deterministic_adapter_results()
        robotics = results["robotics"]
        learning_certificate = robotics.learning_certificate
        self.assertIsNotNone(learning_certificate)
        bad_baseline_calls = learning_certificate.baseline_verifier_calls + 1
        results["robotics"] = replace(
            robotics,
            learning_certificate=replace(
                learning_certificate,
                baseline_verifier_calls=bad_baseline_calls,
                verifier_call_gain_numerator=bad_baseline_calls,
                certificate_hash="",
            ),
        )
        result = build_real_task_benchmark_suite_result(results)

        self.assertTrue(result.report.all_learning_certificates_valid)
        self.assertTrue(result.report.all_learning_certificates_support_claim)
        self.assertFalse(result.report.all_adapter_evidence_certificates_valid)
        self.assertFalse(result.report.all_adapter_evidence_certificates_match_reports)
        self.assertFalse(result.report.all_learning_certificates_match_reports)
        self.assertTrue(validate_real_task_benchmark_suite_report(result.report))
        self.assertTrue(validate_real_task_benchmark_suite_certificate(result.suite_certificate, result.report))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertIn("all_adapter_evidence_certificates_valid", result.claim_certificate.failed_keys)
        self.assertIn("all_learning_certificates_match_reports", result.claim_certificate.failed_keys)

    def test_suite_certificate_binds_child_report_hashes(self) -> None:
        result = run_real_task_benchmark_suite(_deterministic_adapter_results())
        first = result.report.rows[0]
        bad_first = replace(first, child_report_hash="0" * 64)
        bad_report = replace(result.report, rows=(bad_first, *result.report.rows[1:]))

        self.assertTrue(validate_real_task_benchmark_suite_report(bad_report))
        self.assertFalse(validate_real_task_benchmark_suite_certificate(result.suite_certificate, bad_report))

    def test_suite_report_validation_rejects_missing_receipt_hash(self) -> None:
        result = run_real_task_benchmark_suite(_deterministic_adapter_results())
        first = result.report.rows[0]
        bad_first = replace(first, receipt_hashes=first.receipt_hashes[:-1])
        bad_report = replace(result.report, rows=(bad_first, *result.report.rows[1:]))

        self.assertFalse(validate_real_task_benchmark_suite_report(bad_report))
        self.assertFalse(validate_real_task_benchmark_suite_certificate(result.suite_certificate, bad_report))

    def test_suite_report_validation_rejects_missing_execution_provenance_hash(self) -> None:
        result = run_real_task_benchmark_suite(_deterministic_adapter_results())
        first = result.report.rows[0]
        bad_first = replace(first, hard_metadata_hashes=first.hard_metadata_hashes[:-1])
        bad_report = replace(result.report, rows=(bad_first, *result.report.rows[1:]))

        self.assertFalse(validate_real_task_benchmark_suite_report(bad_report))
        self.assertFalse(validate_real_task_benchmark_suite_certificate(result.suite_certificate, bad_report))

    def test_suite_certificate_binds_execution_provenance_hashes(self) -> None:
        result = run_real_task_benchmark_suite(_deterministic_adapter_results())
        bad_certificate = replace(result.suite_certificate, hard_result_hashes=result.suite_certificate.hard_result_hashes[:-1], certificate_hash="")

        self.assertFalse(validate_real_task_benchmark_suite_certificate(bad_certificate, result.report))


if __name__ == "__main__":
    unittest.main()
