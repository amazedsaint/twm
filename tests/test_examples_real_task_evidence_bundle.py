from __future__ import annotations

from dataclasses import replace
import json
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
from examples.real_task_adapter_evidence import real_task_adapter_report_hash
from examples.real_task_benchmark_suite import REAL_TASK_BENCHMARK_SUITE_DOMAINS
from examples.real_task_evidence_bundle import (
    REAL_TASK_EVIDENCE_BUNDLE_CERTIFICATE_SCHEMA,
    RealTaskEvidenceBundleResult,
    result_as_dict,
    run_real_task_evidence_bundle,
    validate_real_task_evidence_bundle,
)
from examples.robotics_motion_benchmark_adapter import (
    DeterministicMotionBenchmarkBackend,
    run_robotics_motion_benchmark_adapter_experiment,
)


def _deterministic_adapter_results() -> dict[str, object]:
    return {
        "robotics": run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend()),
        "hardware": run_hardware_riscv_formal_adapter_experiment(DeterministicRiscVFormalBackend()),
        "program": run_program_defects4j_adapter_experiment(DeterministicDefects4JBackend()),
        "quantum": run_quantum_mqt_bench_adapter_experiment(DeterministicQuantumEquivalenceBackend()),
    }


def _unavailable_adapter_results() -> dict[str, object]:
    return {
        "robotics": run_robotics_motion_benchmark_adapter_experiment(DeterministicMotionBenchmarkBackend(available=False)),
        "hardware": run_hardware_riscv_formal_adapter_experiment(DeterministicRiscVFormalBackend(available=False)),
        "program": run_program_defects4j_adapter_experiment(DeterministicDefects4JBackend(available=False)),
        "quantum": run_quantum_mqt_bench_adapter_experiment(DeterministicQuantumEquivalenceBackend(available=False)),
    }


class RealTaskEvidenceBundleTests(unittest.TestCase):
    def test_deterministic_bundle_binds_child_and_suite_evidence(self) -> None:
        child_results = _deterministic_adapter_results()
        result = run_real_task_evidence_bundle(child_results)
        certificate = result.bundle_certificate

        self.assertEqual(certificate.schema_version, REAL_TASK_EVIDENCE_BUNDLE_CERTIFICATE_SCHEMA)
        self.assertEqual(certificate.domains, REAL_TASK_BENCHMARK_SUITE_DOMAINS)
        self.assertEqual(certificate.aggregate_claim_status, "rejected")
        self.assertEqual(certificate.aggregate_evidence_grade, "G0")
        self.assertEqual(certificate.total_receipt_count, 32)
        self.assertEqual(certificate.total_invalid_commit_count, 0)
        self.assertEqual(certificate.child_receipt_counts, (8, 8, 8, 8))
        self.assertEqual(certificate.child_training_receipt_counts, (2, 2, 2, 2))
        self.assertEqual(certificate.child_baseline_receipt_counts, (4, 4, 4, 4))
        self.assertEqual(certificate.child_learned_receipt_counts, (2, 2, 2, 2))
        self.assertEqual(
            certificate.child_report_hashes,
            tuple(real_task_adapter_report_hash(child_results[domain].report) for domain in REAL_TASK_BENCHMARK_SUITE_DOMAINS),
        )
        self.assertEqual(certificate.child_report_hashes, tuple(row.child_report_hash for row in result.suite_result.report.rows))
        self.assertTrue(certificate.all_child_reports_bound_to_suite)
        self.assertTrue(certificate.all_child_evidence_certificates_valid)
        self.assertTrue(certificate.all_child_evidence_certificates_match_reports)
        self.assertTrue(certificate.all_child_claims_valid)
        self.assertTrue(certificate.all_child_claims_match_reports)
        self.assertTrue(certificate.all_learning_certificates_valid)
        self.assertTrue(certificate.all_learning_certificates_match_reports)
        self.assertTrue(certificate.all_learning_certificates_support_claim)
        self.assertTrue(certificate.hard_verifier_calls_reduced)
        self.assertTrue(certificate.success_preserved)
        self.assertTrue(certificate.replay_rollback_ledger_ok)
        self.assertTrue(certificate.no_invalid_commits)
        self.assertTrue(certificate.all_backends_available)
        self.assertFalse(certificate.all_real_backends)
        self.assertIn("all_real_backends", certificate.failed_aggregate_requirements)
        self.assertEqual(certificate.missing_requirements, result.suite_result.preflight_report.missing_requirements)
        self.assertTrue(validate_real_task_evidence_bundle(result))
        json.dumps(result_as_dict(result), sort_keys=True)

    def test_unavailable_bundle_fails_closed_with_zero_receipts(self) -> None:
        result = run_real_task_evidence_bundle(_unavailable_adapter_results())
        certificate = result.bundle_certificate

        self.assertEqual(certificate.aggregate_claim_status, "rejected")
        self.assertEqual(certificate.aggregate_evidence_grade, "G0")
        self.assertEqual(certificate.total_receipt_count, 0)
        self.assertEqual(certificate.child_receipt_counts, (0, 0, 0, 0))
        self.assertEqual(certificate.child_learning_certificate_hashes, ("", "", "", ""))
        self.assertFalse(certificate.all_backends_available)
        self.assertFalse(certificate.all_learning_certificates_valid)
        self.assertFalse(certificate.all_learning_certificates_support_claim)
        self.assertFalse(certificate.hard_verifier_calls_reduced)
        self.assertFalse(certificate.success_preserved)
        self.assertTrue(certificate.no_invalid_commits)
        self.assertTrue(validate_real_task_evidence_bundle(result))

    def test_tampered_bundle_certificate_fails(self) -> None:
        result = run_real_task_evidence_bundle(_deterministic_adapter_results())
        bad_certificate = replace(
            result.bundle_certificate,
            child_report_hashes=("0" * 64, *result.bundle_certificate.child_report_hashes[1:]),
            certificate_hash="",
        )
        bad_result = RealTaskEvidenceBundleResult(
            bundle_certificate=bad_certificate,
            suite_result=result.suite_result,
            child_results=result.child_results,
        )

        self.assertFalse(validate_real_task_evidence_bundle(bad_result))

    def test_bundle_rejects_mismatched_child_result(self) -> None:
        result = run_real_task_evidence_bundle(_deterministic_adapter_results())
        child_results = dict(result.child_results)
        robotics = child_results["robotics"]
        child_results["robotics"] = replace(
            robotics,
            report=replace(robotics.report, receipt_count=robotics.report.receipt_count + 1),
        )
        bad_result = RealTaskEvidenceBundleResult(
            bundle_certificate=result.bundle_certificate,
            suite_result=result.suite_result,
            child_results=child_results,
        )

        self.assertFalse(validate_real_task_evidence_bundle(bad_result))


if __name__ == "__main__":
    unittest.main()
