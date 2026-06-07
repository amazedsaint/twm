from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping

from examples.hardware_riscv_formal_adapter import run_hardware_riscv_formal_adapter_experiment
from examples.program_defects4j_adapter import run_program_defects4j_adapter_experiment
from examples.quantum_mqt_bench_adapter import run_quantum_mqt_bench_adapter_experiment
from examples.real_task_adapter_evidence import (
    real_task_adapter_report_hash,
    validate_real_task_adapter_evidence_certificate,
)
from examples.real_task_benchmark_suite import (
    REAL_TASK_BENCHMARK_SUITE_DOMAINS,
    RealTaskBenchmarkSuiteResult,
    build_real_task_benchmark_suite_result,
    real_task_benchmark_suite_report_hash,
    result_as_dict as suite_result_as_dict,
    validate_real_task_benchmark_suite_certificate,
    validate_real_task_benchmark_suite_report,
)
from examples.robotics_motion_benchmark_adapter import run_robotics_motion_benchmark_adapter_experiment
from trwm.claims import validate_claim_certificate
from trwm.core import stable_hash


REAL_TASK_EVIDENCE_BUNDLE_CERTIFICATE_SCHEMA = "trwm.real_task_evidence_bundle_certificate.v1"


@dataclass(frozen=True)
class RealTaskEvidenceBundleCertificate:
    schema_version: str
    experiment_id: str
    manifest_hash: str
    manifest_certificate_hash: str
    preflight_report_hash: str
    suite_report_hash: str
    suite_certificate_hash: str
    aggregate_claim_hash: str
    aggregate_claim_status: str
    aggregate_evidence_grade: str
    domains: tuple[str, ...]
    child_report_hashes: tuple[str, ...]
    child_evidence_certificate_hashes: tuple[str, ...]
    child_claim_hashes: tuple[str, ...]
    child_learning_certificate_hashes: tuple[str, ...]
    child_receipt_counts: tuple[int, ...]
    child_training_receipt_counts: tuple[int, ...]
    child_baseline_receipt_counts: tuple[int, ...]
    child_learned_receipt_counts: tuple[int, ...]
    total_receipt_count: int
    total_invalid_commit_count: int
    all_child_reports_bound_to_suite: bool
    all_child_evidence_certificates_valid: bool
    all_child_evidence_certificates_match_reports: bool
    all_child_claims_valid: bool
    all_child_claims_match_reports: bool
    all_learning_certificates_valid: bool
    all_learning_certificates_match_reports: bool
    suite_report_valid: bool
    suite_certificate_valid: bool
    aggregate_claim_valid: bool
    ready_to_run_all: bool
    all_backends_available: bool
    all_real_backends: bool
    all_runtime_requirements_match_preflight: bool
    all_receipt_artifacts_cover_manifest_assets: bool
    all_backend_execution_evidence_bound: bool
    all_learning_certificates_support_claim: bool
    hard_verifier_calls_reduced: bool
    success_preserved: bool
    replay_rollback_ledger_ok: bool
    no_invalid_commits: bool
    failed_aggregate_requirements: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    source_urls: tuple[str, ...]
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REAL_TASK_EVIDENCE_BUNDLE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid real-task evidence bundle schema: {self.schema_version}")
        object.__setattr__(self, "domains", tuple(self.domains))
        object.__setattr__(self, "child_report_hashes", tuple(self.child_report_hashes))
        object.__setattr__(self, "child_evidence_certificate_hashes", tuple(self.child_evidence_certificate_hashes))
        object.__setattr__(self, "child_claim_hashes", tuple(self.child_claim_hashes))
        object.__setattr__(self, "child_learning_certificate_hashes", tuple(self.child_learning_certificate_hashes))
        object.__setattr__(self, "child_receipt_counts", tuple(int(row) for row in self.child_receipt_counts))
        object.__setattr__(self, "child_training_receipt_counts", tuple(int(row) for row in self.child_training_receipt_counts))
        object.__setattr__(self, "child_baseline_receipt_counts", tuple(int(row) for row in self.child_baseline_receipt_counts))
        object.__setattr__(self, "child_learned_receipt_counts", tuple(int(row) for row in self.child_learned_receipt_counts))
        object.__setattr__(self, "failed_aggregate_requirements", tuple(self.failed_aggregate_requirements))
        object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        object.__setattr__(self, "source_urls", tuple(self.source_urls))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", real_task_evidence_bundle_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class RealTaskEvidenceBundleResult:
    bundle_certificate: RealTaskEvidenceBundleCertificate
    suite_result: RealTaskBenchmarkSuiteResult
    child_results: Mapping[str, Any]


def run_real_task_evidence_bundle(
    adapter_results: Mapping[str, Any] | None = None,
) -> RealTaskEvidenceBundleResult:
    child_results = dict(adapter_results) if adapter_results is not None else _run_default_adapter_results()
    suite_result = build_real_task_benchmark_suite_result(child_results)
    certificate = build_real_task_evidence_bundle_certificate(suite_result, child_results)
    return RealTaskEvidenceBundleResult(
        bundle_certificate=certificate,
        suite_result=suite_result,
        child_results=child_results,
    )


def build_real_task_evidence_bundle_certificate(
    suite_result: RealTaskBenchmarkSuiteResult,
    child_results: Mapping[str, Any],
) -> RealTaskEvidenceBundleCertificate:
    child_reports = tuple(child_results[domain].report for domain in REAL_TASK_BENCHMARK_SUITE_DOMAINS)
    child_learning_certificates = tuple(child_results[domain].learning_certificate for domain in REAL_TASK_BENCHMARK_SUITE_DOMAINS)
    child_claims = tuple(child_results[domain].claim_certificate for domain in REAL_TASK_BENCHMARK_SUITE_DOMAINS)
    child_evidence_certificates = tuple(child_results[domain].evidence_certificate for domain in REAL_TASK_BENCHMARK_SUITE_DOMAINS)
    child_report_hashes = tuple(real_task_adapter_report_hash(report) for report in child_reports)
    child_evidence_valid = tuple(
        validate_real_task_adapter_evidence_certificate(
            evidence,
            report=report,
            learning_certificate=learning,
            claim_certificate=claim,
        )
        for evidence, report, learning, claim in zip(
            child_evidence_certificates,
            child_reports,
            child_learning_certificates,
            child_claims,
        )
    )
    suite_row_report_hashes = tuple(row.child_report_hash for row in suite_result.report.rows)
    failed_requirements = tuple(row.key for row in suite_result.claim_certificate.requirements if not row.passed)
    return RealTaskEvidenceBundleCertificate(
        schema_version=REAL_TASK_EVIDENCE_BUNDLE_CERTIFICATE_SCHEMA,
        experiment_id="receipt_trained_reversible_real_task_evidence_bundle",
        manifest_hash=suite_result.manifest.manifest_hash,
        manifest_certificate_hash=suite_result.manifest_certificate.certificate_hash,
        preflight_report_hash=suite_result.manifest_certificate.preflight_report_hash,
        suite_report_hash=real_task_benchmark_suite_report_hash(suite_result.report),
        suite_certificate_hash=suite_result.suite_certificate.certificate_hash,
        aggregate_claim_hash=suite_result.claim_certificate.certificate_hash,
        aggregate_claim_status=suite_result.claim_certificate.status,
        aggregate_evidence_grade=suite_result.claim_certificate.evidence_grade,
        domains=REAL_TASK_BENCHMARK_SUITE_DOMAINS,
        child_report_hashes=child_report_hashes,
        child_evidence_certificate_hashes=tuple(evidence.certificate_hash for evidence in child_evidence_certificates),
        child_claim_hashes=tuple(claim.certificate_hash for claim in child_claims),
        child_learning_certificate_hashes=tuple(_learning_hash(learning) for learning in child_learning_certificates),
        child_receipt_counts=tuple(int(report.receipt_count) for report in child_reports),
        child_training_receipt_counts=tuple(int(report.training_receipt_count) for report in child_reports),
        child_baseline_receipt_counts=tuple(int(report.baseline_receipt_count) for report in child_reports),
        child_learned_receipt_counts=tuple(int(report.learned_receipt_count) for report in child_reports),
        total_receipt_count=int(suite_result.report.total_receipt_count),
        total_invalid_commit_count=int(suite_result.report.total_invalid_commit_count),
        all_child_reports_bound_to_suite=child_report_hashes == suite_row_report_hashes,
        all_child_evidence_certificates_valid=all(child_evidence_valid) and suite_result.report.all_adapter_evidence_certificates_valid,
        all_child_evidence_certificates_match_reports=suite_result.report.all_adapter_evidence_certificates_match_reports,
        all_child_claims_valid=all(validate_claim_certificate(claim) for claim in child_claims) and suite_result.report.all_child_claims_valid,
        all_child_claims_match_reports=suite_result.report.all_child_claims_match_reports,
        all_learning_certificates_valid=suite_result.report.all_learning_certificates_valid,
        all_learning_certificates_match_reports=suite_result.report.all_learning_certificates_match_reports,
        suite_report_valid=validate_real_task_benchmark_suite_report(suite_result.report),
        suite_certificate_valid=validate_real_task_benchmark_suite_certificate(suite_result.suite_certificate, suite_result.report),
        aggregate_claim_valid=validate_claim_certificate(suite_result.claim_certificate),
        ready_to_run_all=suite_result.preflight_report.ready_to_run_all,
        all_backends_available=suite_result.report.all_backends_available,
        all_real_backends=suite_result.report.all_real_backends,
        all_runtime_requirements_match_preflight=suite_result.report.all_runtime_requirements_match_preflight,
        all_receipt_artifacts_cover_manifest_assets=suite_result.report.all_receipt_artifacts_cover_manifest_assets,
        all_backend_execution_evidence_bound=suite_result.report.all_backend_execution_evidence_bound,
        all_learning_certificates_support_claim=suite_result.report.all_learning_certificates_support_claim,
        hard_verifier_calls_reduced=suite_result.report.hard_verifier_calls_reduced,
        success_preserved=suite_result.report.success_preserved,
        replay_rollback_ledger_ok=suite_result.report.replay_rollback_ledger_ok,
        no_invalid_commits=suite_result.report.no_invalid_commits,
        failed_aggregate_requirements=failed_requirements,
        missing_requirements=suite_result.preflight_report.missing_requirements,
        source_urls=suite_result.manifest.source_urls,
    )


def validate_real_task_evidence_bundle(
    result: RealTaskEvidenceBundleResult,
) -> bool:
    try:
        certificate = result.bundle_certificate
        suite_result = result.suite_result
        child_results = result.child_results
        if certificate.schema_version != REAL_TASK_EVIDENCE_BUNDLE_CERTIFICATE_SCHEMA:
            return False
        if certificate.experiment_id != "receipt_trained_reversible_real_task_evidence_bundle":
            return False
        if certificate.domains != REAL_TASK_BENCHMARK_SUITE_DOMAINS:
            return False
        if set(child_results) != set(REAL_TASK_BENCHMARK_SUITE_DOMAINS):
            return False
        if not _hash_tuple(certificate.child_report_hashes, size=4):
            return False
        if not _hash_tuple(certificate.child_evidence_certificate_hashes, size=4):
            return False
        if not _hash_tuple(certificate.child_claim_hashes, size=4):
            return False
        if len(certificate.child_learning_certificate_hashes) != 4:
            return False
        if any(value and not _is_hash(value) for value in certificate.child_learning_certificate_hashes):
            return False
        count_fields = (
            certificate.child_receipt_counts,
            certificate.child_training_receipt_counts,
            certificate.child_baseline_receipt_counts,
            certificate.child_learned_receipt_counts,
        )
        if any(len(field) != 4 or any(value < 0 for value in field) for field in count_fields):
            return False
        if certificate.total_receipt_count != sum(certificate.child_receipt_counts):
            return False
        if certificate.total_invalid_commit_count < 0:
            return False
        if not _hash_tuple(
            (
                certificate.manifest_hash,
                certificate.manifest_certificate_hash,
                certificate.preflight_report_hash,
                certificate.suite_report_hash,
                certificate.suite_certificate_hash,
                certificate.aggregate_claim_hash,
                certificate.certificate_hash,
            )
        ):
            return False
        if certificate.aggregate_claim_status not in {"supported", "rejected"}:
            return False
        if certificate.aggregate_evidence_grade not in {"G0", "G1", "G2", "G3"}:
            return False
        if not certificate.source_urls or any(not isinstance(source, str) or not source for source in certificate.source_urls):
            return False
        expected_suite_result = build_real_task_benchmark_suite_result(child_results)
        if real_task_benchmark_suite_report_hash(expected_suite_result.report) != certificate.suite_report_hash:
            return False
        if expected_suite_result.suite_certificate.certificate_hash != certificate.suite_certificate_hash:
            return False
        if expected_suite_result.claim_certificate.certificate_hash != certificate.aggregate_claim_hash:
            return False
        if real_task_benchmark_suite_report_hash(suite_result.report) != certificate.suite_report_hash:
            return False
        if suite_result.suite_certificate.certificate_hash != certificate.suite_certificate_hash:
            return False
        if suite_result.claim_certificate.certificate_hash != certificate.aggregate_claim_hash:
            return False
        expected_certificate = build_real_task_evidence_bundle_certificate(suite_result, child_results)
        if certificate.without_hash() != expected_certificate.without_hash():
            return False
        if certificate.aggregate_claim_status == "supported" and not _supported_bundle(certificate):
            return False
        return certificate.certificate_hash == real_task_evidence_bundle_certificate_hash(certificate)
    except Exception:
        return False


def real_task_evidence_bundle_certificate_hash(certificate: RealTaskEvidenceBundleCertificate) -> str:
    return stable_hash(certificate.without_hash())


def result_as_dict(result: RealTaskEvidenceBundleResult) -> dict[str, Any]:
    return {
        "bundle_certificate": asdict(result.bundle_certificate),
        "suite_result": suite_result_as_dict(result.suite_result),
        "child_results": {
            domain: asdict(result.child_results[domain])
            for domain in REAL_TASK_BENCHMARK_SUITE_DOMAINS
        },
    }


def _run_default_adapter_results() -> dict[str, Any]:
    return {
        "robotics": run_robotics_motion_benchmark_adapter_experiment(),
        "hardware": run_hardware_riscv_formal_adapter_experiment(),
        "program": run_program_defects4j_adapter_experiment(),
        "quantum": run_quantum_mqt_bench_adapter_experiment(),
    }


def _learning_hash(learning_certificate: Any | None) -> str:
    return str(learning_certificate.certificate_hash) if learning_certificate is not None else ""


def _supported_bundle(certificate: RealTaskEvidenceBundleCertificate) -> bool:
    return (
        certificate.aggregate_evidence_grade == "G1"
        and certificate.ready_to_run_all
        and certificate.all_child_reports_bound_to_suite
        and certificate.all_child_evidence_certificates_valid
        and certificate.all_child_evidence_certificates_match_reports
        and certificate.all_child_claims_valid
        and certificate.all_child_claims_match_reports
        and certificate.all_learning_certificates_valid
        and certificate.all_learning_certificates_match_reports
        and certificate.suite_report_valid
        and certificate.suite_certificate_valid
        and certificate.aggregate_claim_valid
        and certificate.all_backends_available
        and certificate.all_real_backends
        and certificate.all_runtime_requirements_match_preflight
        and certificate.all_receipt_artifacts_cover_manifest_assets
        and certificate.all_backend_execution_evidence_bound
        and certificate.all_learning_certificates_support_claim
        and certificate.hard_verifier_calls_reduced
        and certificate.success_preserved
        and certificate.replay_rollback_ledger_ok
        and certificate.no_invalid_commits
        and certificate.total_receipt_count > 0
        and certificate.total_invalid_commit_count == 0
        and not certificate.failed_aggregate_requirements
        and not certificate.missing_requirements
    )


def _hash_tuple(values: tuple[str, ...], *, size: int | None = None) -> bool:
    if size is not None and len(values) != size:
        return False
    return all(_is_hash(value) for value in values)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def main() -> None:
    print(json.dumps(result_as_dict(run_real_task_evidence_bundle()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
