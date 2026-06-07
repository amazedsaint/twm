from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping

from examples.hardware_riscv_formal_adapter import run_hardware_riscv_formal_adapter_experiment
from examples.program_defects4j_adapter import run_program_defects4j_adapter_experiment
from examples.quantum_mqt_bench_adapter import run_quantum_mqt_bench_adapter_experiment
from examples.real_task_benchmark_manifest import (
    RealTaskBenchmarkManifest,
    RealTaskBenchmarkManifestCertificate,
    RealTaskBenchmarkPreflightReport,
    RealTaskPreflightRow,
    RealTaskBenchmarkSpec,
    build_real_task_benchmark_manifest,
    build_real_task_manifest_certificate,
    build_real_task_preflight_report,
    manifest_split_task_hash,
    preflight_runtime_requirement_evidence_hashes,
    preflight_task_asset_content_hashes,
    real_task_preflight_report_hash,
    runtime_requirement_count,
    validate_real_task_manifest,
    validate_real_task_manifest_certificate,
    validate_real_task_preflight_report,
)
from examples.real_task_adapter_evidence import validate_real_task_adapter_evidence_certificate
from examples.robotics_motion_benchmark_adapter import run_robotics_motion_benchmark_adapter_experiment
from trwm.claims import ClaimCertificate, certify_claim, requirement, validate_claim_certificate
from trwm.core import stable_hash
from trwm.evaluation import validate_learning_evaluation_certificate, learning_evaluation_supports_claim


REAL_TASK_BENCHMARK_SUITE_REPORT_SCHEMA = "trwm.real_task_benchmark_suite_report.v1"
REAL_TASK_BENCHMARK_SUITE_CERTIFICATE_SCHEMA = "trwm.real_task_benchmark_suite_certificate.v1"
REAL_TASK_BENCHMARK_SUITE_DOMAINS = ("robotics", "hardware", "program", "quantum")
REAL_TASK_BENCHMARK_SUITE_CLAIM_BOUNDARY = (
    "Four-domain real-task objective gate. A supported claim requires real robotics, hardware, "
    "program, and quantum benchmark backends, held-out success preservation, reduced "
    "hard-verifier calls, supported child claims, valid learning certificates, replay/rollback "
    "and ledger audits, and zero invalid commits. Deterministic test doubles and missing "
    "external toolchains must reject."
)
_REAL_BACKEND_REQUIREMENT_BY_DOMAIN = {
    "robotics": "real_motion_benchmark_backend",
    "hardware": "real_riscv_formal_backend",
    "program": "real_defects4j_backend",
    "quantum": "real_mqt_backend",
}
_CHILD_CLAIM_ID_BY_DOMAIN = {
    "robotics": "robotics_motion_benchmark_receipt_trained_reversible_adapter",
    "hardware": "hardware_riscv_formal_receipt_trained_reversible_adapter",
    "program": "program_defects4j_receipt_trained_reversible_adapter",
    "quantum": "quantum_mqt_receipt_trained_reversible_adapter",
}
_CHILD_CLAIM_SCOPE_BY_DOMAIN = {
    "robotics": "robotics_motion_benchmark_adapter",
    "hardware": "hardware_riscv_formal_adapter",
    "program": "program_defects4j_adapter",
    "quantum": "quantum_mqt_bench_adapter",
}


@dataclass(frozen=True)
class RealTaskBenchmarkSuiteRow:
    domain: str
    report_schema_version: str
    experiment_id: str
    backend_id: str
    backend_version: str
    backend_available: bool
    real_backend: bool
    missing_requirements: tuple[str, ...]
    backend_error: str
    adapter_runtime_requirement_evidence_hashes: tuple[str, ...]
    adapter_runtime_requirements_match_preflight: bool
    manifest_spec_hash: str
    manifest_benchmark_id: str
    manifest_train_split_id: str
    manifest_held_out_split_id: str
    manifest_train_task_ids: tuple[str, ...]
    manifest_held_out_task_ids: tuple[str, ...]
    manifest_split_task_hash: str
    adapter_task_splits_match_manifest: bool
    manifest_runtime_requirement_count: int
    manifest_runtime_requirement_evidence_hashes: tuple[str, ...]
    manifest_required_task_asset_count: int
    manifest_task_asset_content_hashes: tuple[str, ...]
    child_report_hash: str
    adapter_evidence_certificate_hash: str
    adapter_evidence_certificate_valid: bool
    adapter_evidence_certificate_matches_report: bool
    adapter_evidence_matches_manifest: bool
    child_claim_valid: bool
    child_claim_status: str
    child_claim_hash: str
    child_claim_matches_report: bool
    learning_certificate_hash: str
    learning_certificate_valid: bool
    learning_certificate_supports_claim: bool
    learning_certificate_matches_report: bool
    train_task_ids: tuple[str, ...]
    held_out_task_ids: tuple[str, ...]
    receipt_count: int
    training_receipt_count: int
    baseline_receipt_count: int
    learned_receipt_count: int
    committed_count: int
    rejected_count: int
    invalid_commit_count: int
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int
    verifier_call_reduction: int
    hard_commit_only: bool
    heldout_arm_isolated: bool
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    training_receipt_hashes: tuple[str, ...]
    baseline_receipt_hashes: tuple[str, ...]
    learned_receipt_hashes: tuple[str, ...]
    receipt_hashes: tuple[str, ...]
    typed_candidate_hashes: tuple[str, ...]
    hard_result_hashes: tuple[str, ...]
    hard_metadata_hashes: tuple[str, ...]
    receipt_artifacts_bound: bool
    receipt_artifact_hashes: tuple[str, ...]
    receipt_artifact_value_hashes: tuple[str, ...]
    receipt_artifacts_cover_manifest_assets: bool
    backend_execution_evidence_ok: bool
    backend_execution_evidence_hashes: tuple[str, ...]
    source_urls: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        object.__setattr__(self, "backend_error", str(self.backend_error))
        object.__setattr__(self, "adapter_runtime_requirement_evidence_hashes", tuple(self.adapter_runtime_requirement_evidence_hashes))
        object.__setattr__(self, "manifest_runtime_requirement_evidence_hashes", tuple(self.manifest_runtime_requirement_evidence_hashes))
        object.__setattr__(self, "manifest_train_task_ids", tuple(self.manifest_train_task_ids))
        object.__setattr__(self, "manifest_held_out_task_ids", tuple(self.manifest_held_out_task_ids))
        object.__setattr__(self, "manifest_task_asset_content_hashes", tuple(self.manifest_task_asset_content_hashes))
        object.__setattr__(self, "train_task_ids", tuple(self.train_task_ids))
        object.__setattr__(self, "held_out_task_ids", tuple(self.held_out_task_ids))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(self, "typed_candidate_hashes", tuple(self.typed_candidate_hashes))
        object.__setattr__(self, "hard_result_hashes", tuple(self.hard_result_hashes))
        object.__setattr__(self, "hard_metadata_hashes", tuple(self.hard_metadata_hashes))
        object.__setattr__(self, "receipt_artifact_hashes", tuple(self.receipt_artifact_hashes))
        object.__setattr__(self, "receipt_artifact_value_hashes", tuple(self.receipt_artifact_value_hashes))
        object.__setattr__(self, "backend_execution_evidence_hashes", tuple(self.backend_execution_evidence_hashes))
        object.__setattr__(self, "source_urls", tuple(self.source_urls))
        object.__setattr__(self, "training_receipt_hashes", tuple(self.training_receipt_hashes))
        object.__setattr__(self, "baseline_receipt_hashes", tuple(self.baseline_receipt_hashes))
        object.__setattr__(self, "learned_receipt_hashes", tuple(self.learned_receipt_hashes))


@dataclass(frozen=True)
class RealTaskBenchmarkSuiteReport:
    schema_version: str
    experiment_id: str
    manifest_hash: str
    manifest_preflight_report_hash: str
    manifest_certificate_hash: str
    domain_count: int
    domains: tuple[str, ...]
    rows: tuple[RealTaskBenchmarkSuiteRow, ...]
    all_child_claims_valid: bool
    all_child_claims_supported: bool
    all_child_claims_match_reports: bool
    all_adapter_evidence_certificates_valid: bool
    all_adapter_evidence_certificates_match_reports: bool
    all_adapter_evidence_matches_manifest: bool
    all_adapter_task_splits_match_manifest: bool
    all_learning_certificates_valid: bool
    all_learning_certificates_support_claim: bool
    all_learning_certificates_match_reports: bool
    all_backends_available: bool
    all_real_backends: bool
    all_runtime_requirements_match_preflight: bool
    all_receipt_counts_bound: bool
    all_receipt_artifacts_bound: bool
    all_receipt_artifacts_cover_manifest_assets: bool
    all_backend_execution_evidence_bound: bool
    heldout_arms_isolated: bool
    hard_verifier_calls_reduced: bool
    success_preserved: bool
    replay_rollback_ledger_ok: bool
    no_invalid_commits: bool
    total_receipt_count: int
    total_training_receipt_count: int
    total_baseline_receipt_count: int
    total_learned_receipt_count: int
    total_committed_count: int
    total_rejected_count: int
    total_invalid_commit_count: int
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int
    verifier_call_reduction: int
    missing_requirements: tuple[str, ...]
    aggregate_sources: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        if self.schema_version != REAL_TASK_BENCHMARK_SUITE_REPORT_SCHEMA:
            raise ValueError(f"invalid real-task suite report schema: {self.schema_version}")
        object.__setattr__(self, "domains", tuple(self.domains))
        object.__setattr__(self, "rows", tuple(self.rows))
        object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        object.__setattr__(self, "aggregate_sources", tuple(self.aggregate_sources))


@dataclass(frozen=True)
class RealTaskBenchmarkSuiteCertificate:
    schema_version: str
    experiment_id: str
    report_hash: str
    manifest_hash: str
    manifest_preflight_report_hash: str
    manifest_certificate_hash: str
    domain_count: int
    domains: tuple[str, ...]
    manifest_spec_hashes: tuple[str, ...]
    manifest_split_task_hashes: tuple[str, ...]
    manifest_train_task_ids: tuple[str, ...]
    manifest_held_out_task_ids: tuple[str, ...]
    manifest_runtime_requirement_evidence_hashes: tuple[str, ...]
    manifest_task_asset_content_hashes: tuple[str, ...]
    adapter_train_task_ids: tuple[str, ...]
    adapter_held_out_task_ids: tuple[str, ...]
    adapter_runtime_requirement_evidence_hashes: tuple[str, ...]
    child_report_hashes: tuple[str, ...]
    adapter_evidence_certificate_hashes: tuple[str, ...]
    child_claim_hashes: tuple[str, ...]
    learning_certificate_hashes: tuple[str, ...]
    training_receipt_hashes: tuple[str, ...]
    baseline_receipt_hashes: tuple[str, ...]
    learned_receipt_hashes: tuple[str, ...]
    receipt_hashes: tuple[str, ...]
    typed_candidate_hashes: tuple[str, ...]
    hard_result_hashes: tuple[str, ...]
    hard_metadata_hashes: tuple[str, ...]
    receipt_artifact_hashes: tuple[str, ...]
    receipt_artifact_value_hashes: tuple[str, ...]
    backend_execution_evidence_hashes: tuple[str, ...]
    all_child_claims_valid: bool
    all_child_claims_supported: bool
    all_child_claims_match_reports: bool
    all_adapter_evidence_certificates_valid: bool
    all_adapter_evidence_certificates_match_reports: bool
    all_adapter_evidence_matches_manifest: bool
    all_adapter_task_splits_match_manifest: bool
    all_learning_certificates_valid: bool
    all_learning_certificates_match_reports: bool
    all_real_backends: bool
    all_runtime_requirements_match_preflight: bool
    all_receipt_counts_bound: bool
    all_receipt_artifacts_bound: bool
    all_receipt_artifacts_cover_manifest_assets: bool
    all_backend_execution_evidence_bound: bool
    heldout_arms_isolated: bool
    hard_verifier_calls_reduced: bool
    success_preserved: bool
    replay_rollback_ledger_ok: bool
    no_invalid_commits: bool
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REAL_TASK_BENCHMARK_SUITE_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid real-task suite certificate schema: {self.schema_version}")
        object.__setattr__(self, "domains", tuple(self.domains))
        object.__setattr__(self, "manifest_spec_hashes", tuple(self.manifest_spec_hashes))
        object.__setattr__(self, "manifest_split_task_hashes", tuple(self.manifest_split_task_hashes))
        object.__setattr__(self, "manifest_train_task_ids", tuple(self.manifest_train_task_ids))
        object.__setattr__(self, "manifest_held_out_task_ids", tuple(self.manifest_held_out_task_ids))
        object.__setattr__(self, "manifest_runtime_requirement_evidence_hashes", tuple(self.manifest_runtime_requirement_evidence_hashes))
        object.__setattr__(self, "manifest_task_asset_content_hashes", tuple(self.manifest_task_asset_content_hashes))
        object.__setattr__(self, "adapter_train_task_ids", tuple(self.adapter_train_task_ids))
        object.__setattr__(self, "adapter_held_out_task_ids", tuple(self.adapter_held_out_task_ids))
        object.__setattr__(self, "adapter_runtime_requirement_evidence_hashes", tuple(self.adapter_runtime_requirement_evidence_hashes))
        object.__setattr__(self, "child_report_hashes", tuple(self.child_report_hashes))
        object.__setattr__(self, "adapter_evidence_certificate_hashes", tuple(self.adapter_evidence_certificate_hashes))
        object.__setattr__(self, "child_claim_hashes", tuple(self.child_claim_hashes))
        object.__setattr__(self, "learning_certificate_hashes", tuple(self.learning_certificate_hashes))
        object.__setattr__(self, "training_receipt_hashes", tuple(self.training_receipt_hashes))
        object.__setattr__(self, "baseline_receipt_hashes", tuple(self.baseline_receipt_hashes))
        object.__setattr__(self, "learned_receipt_hashes", tuple(self.learned_receipt_hashes))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(self, "typed_candidate_hashes", tuple(self.typed_candidate_hashes))
        object.__setattr__(self, "hard_result_hashes", tuple(self.hard_result_hashes))
        object.__setattr__(self, "hard_metadata_hashes", tuple(self.hard_metadata_hashes))
        object.__setattr__(self, "receipt_artifact_hashes", tuple(self.receipt_artifact_hashes))
        object.__setattr__(self, "receipt_artifact_value_hashes", tuple(self.receipt_artifact_value_hashes))
        object.__setattr__(self, "backend_execution_evidence_hashes", tuple(self.backend_execution_evidence_hashes))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", real_task_benchmark_suite_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class RealTaskBenchmarkSuiteResult:
    manifest: RealTaskBenchmarkManifest
    preflight_report: RealTaskBenchmarkPreflightReport
    manifest_certificate: RealTaskBenchmarkManifestCertificate
    report: RealTaskBenchmarkSuiteReport
    suite_certificate: RealTaskBenchmarkSuiteCertificate
    claim_certificate: ClaimCertificate


def run_real_task_benchmark_suite(
    adapter_results: Mapping[str, Any] | None = None,
) -> RealTaskBenchmarkSuiteResult:
    results = adapter_results or {
        "robotics": run_robotics_motion_benchmark_adapter_experiment(),
        "hardware": run_hardware_riscv_formal_adapter_experiment(),
        "program": run_program_defects4j_adapter_experiment(),
        "quantum": run_quantum_mqt_bench_adapter_experiment(),
    }
    return build_real_task_benchmark_suite_result(results)


def build_real_task_benchmark_suite_result(
    adapter_results: Mapping[str, Any],
) -> RealTaskBenchmarkSuiteResult:
    manifest = build_real_task_benchmark_manifest()
    preflight_report = build_real_task_preflight_report(manifest)
    manifest_certificate = build_real_task_manifest_certificate(manifest, preflight_report)
    specs_by_domain = {spec.domain: spec for spec in manifest.specs}
    preflight_rows_by_domain = {row.domain: row for row in preflight_report.rows}
    rows = tuple(
        _suite_row(domain, adapter_results[domain], specs_by_domain[domain], preflight_rows_by_domain[domain])
        for domain in REAL_TASK_BENCHMARK_SUITE_DOMAINS
    )
    child_claims_valid = tuple(row.child_claim_valid for row in rows)
    child_claims_supported = tuple(row.child_claim_valid and row.child_claim_status == "supported" for row in rows)
    report = _build_report(manifest, preflight_report, manifest_certificate, rows, child_claims_valid, child_claims_supported)
    suite_certificate = build_real_task_benchmark_suite_certificate(report, manifest, manifest_certificate)
    claim = certify_claim(
        claim_id="receipt_trained_reversible_real_task_four_domain_call_reduction",
        claim_text=(
            "A receipt-trained reversible proposer reduces hard-verifier calls while preserving "
            "zero invalid commits on held-out robotics, hardware, program, and quantum real-task "
            "benchmarks."
        ),
        evidence_grade=(
            "G1"
            if (
                report.all_real_backends
                and report.all_child_claims_supported
                and report.all_child_claims_match_reports
                and report.all_adapter_evidence_certificates_valid
                and report.all_adapter_evidence_certificates_match_reports
                and report.all_adapter_evidence_matches_manifest
                and report.all_adapter_task_splits_match_manifest
                and report.all_learning_certificates_match_reports
                and report.all_runtime_requirements_match_preflight
                and report.all_receipt_artifacts_bound
                and report.all_receipt_artifacts_cover_manifest_assets
                and report.all_backend_execution_evidence_bound
                and report.heldout_arms_isolated
                and validate_real_task_preflight_report(preflight_report, manifest)
            )
            else "G0"
        ),
        scope="real_task_benchmark_suite",
        requirements=(
            requirement("manifest_valid", validate_real_task_manifest(manifest)),
            requirement("preflight_report_valid", validate_real_task_preflight_report(preflight_report, manifest)),
            requirement("manifest_certificate_valid", validate_real_task_manifest_certificate(manifest_certificate, manifest, preflight_report)),
            requirement("manifest_preflight_report_bound", report.manifest_preflight_report_hash == real_task_preflight_report_hash(preflight_report)),
            requirement("suite_report_valid", validate_real_task_benchmark_suite_report(report)),
            requirement("suite_certificate_valid", validate_real_task_benchmark_suite_certificate(suite_certificate, report)),
            requirement("exactly_four_domains", report.domain_count == 4 and report.domains == REAL_TASK_BENCHMARK_SUITE_DOMAINS),
            requirement("all_child_claims_valid", report.all_child_claims_valid),
            requirement("all_child_claims_supported", report.all_child_claims_supported),
            requirement("all_child_claims_match_reports", report.all_child_claims_match_reports),
            requirement("all_adapter_evidence_certificates_valid", report.all_adapter_evidence_certificates_valid),
            requirement("all_adapter_evidence_certificates_match_reports", report.all_adapter_evidence_certificates_match_reports),
            requirement("all_adapter_evidence_matches_manifest", report.all_adapter_evidence_matches_manifest),
            requirement("all_adapter_task_splits_match_manifest", report.all_adapter_task_splits_match_manifest),
            requirement("all_learning_certificates_valid", report.all_learning_certificates_valid),
            requirement("all_learning_certificates_support_claim", report.all_learning_certificates_support_claim),
            requirement("all_learning_certificates_match_reports", report.all_learning_certificates_match_reports),
            requirement("all_backends_available", report.all_backends_available, missing=report.missing_requirements),
            requirement("all_real_backends", report.all_real_backends),
            requirement("all_runtime_requirements_match_preflight", report.all_runtime_requirements_match_preflight),
            requirement("all_receipt_counts_bound", report.all_receipt_counts_bound),
            requirement("all_receipt_artifacts_bound", report.all_receipt_artifacts_bound),
            requirement("all_receipt_artifacts_cover_manifest_assets", report.all_receipt_artifacts_cover_manifest_assets),
            requirement("all_backend_execution_evidence_bound", report.all_backend_execution_evidence_bound),
            requirement("heldout_arms_isolated", report.heldout_arms_isolated),
            requirement("hard_verifier_calls_reduced", report.hard_verifier_calls_reduced),
            requirement("success_preserved", report.success_preserved),
            requirement("replay_rollback_ledger_ok", report.replay_rollback_ledger_ok),
            requirement("zero_invalid_commits", report.no_invalid_commits),
        ),
        metrics={
            "domain_count": report.domain_count,
            "baseline_verifier_calls": report.baseline_verifier_calls,
            "learned_verifier_calls": report.learned_verifier_calls,
            "verifier_call_reduction": report.verifier_call_reduction,
            "baseline_success_count": report.baseline_success_count,
            "learned_success_count": report.learned_success_count,
            "total_invalid_commit_count": report.total_invalid_commit_count,
            "total_receipt_count": report.total_receipt_count,
            "heldout_arms_isolated": report.heldout_arms_isolated,
            "task_splits_match_manifest": report.all_adapter_task_splits_match_manifest,
            "runtime_requirements_match_preflight": report.all_runtime_requirements_match_preflight,
            "receipt_artifacts_cover_manifest_assets": report.all_receipt_artifacts_cover_manifest_assets,
        },
        boundary=REAL_TASK_BENCHMARK_SUITE_CLAIM_BOUNDARY,
        sources=report.aggregate_sources,
    )
    return RealTaskBenchmarkSuiteResult(
        manifest=manifest,
        preflight_report=preflight_report,
        manifest_certificate=manifest_certificate,
        report=report,
        suite_certificate=suite_certificate,
        claim_certificate=claim,
    )


def build_real_task_benchmark_suite_certificate(
    report: RealTaskBenchmarkSuiteReport,
    manifest: RealTaskBenchmarkManifest,
    manifest_certificate: RealTaskBenchmarkManifestCertificate,
) -> RealTaskBenchmarkSuiteCertificate:
    return RealTaskBenchmarkSuiteCertificate(
        schema_version=REAL_TASK_BENCHMARK_SUITE_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        report_hash=real_task_benchmark_suite_report_hash(report),
        manifest_hash=manifest.manifest_hash,
        manifest_preflight_report_hash=report.manifest_preflight_report_hash,
        manifest_certificate_hash=manifest_certificate.certificate_hash,
        domain_count=report.domain_count,
        domains=report.domains,
        manifest_spec_hashes=tuple(row.manifest_spec_hash for row in report.rows),
        manifest_split_task_hashes=tuple(row.manifest_split_task_hash for row in report.rows),
        manifest_train_task_ids=tuple(task_id for row in report.rows for task_id in row.manifest_train_task_ids),
        manifest_held_out_task_ids=tuple(task_id for row in report.rows for task_id in row.manifest_held_out_task_ids),
        manifest_runtime_requirement_evidence_hashes=tuple(
            evidence_hash for row in report.rows for evidence_hash in row.manifest_runtime_requirement_evidence_hashes
        ),
        manifest_task_asset_content_hashes=tuple(
            content_hash for row in report.rows for content_hash in row.manifest_task_asset_content_hashes
        ),
        adapter_train_task_ids=tuple(task_id for row in report.rows for task_id in row.train_task_ids),
        adapter_held_out_task_ids=tuple(task_id for row in report.rows for task_id in row.held_out_task_ids),
        adapter_runtime_requirement_evidence_hashes=tuple(
            evidence_hash for row in report.rows for evidence_hash in row.adapter_runtime_requirement_evidence_hashes
        ),
        child_report_hashes=tuple(row.child_report_hash for row in report.rows),
        adapter_evidence_certificate_hashes=tuple(row.adapter_evidence_certificate_hash for row in report.rows),
        child_claim_hashes=tuple(row.child_claim_hash for row in report.rows),
        learning_certificate_hashes=tuple(row.learning_certificate_hash for row in report.rows if row.learning_certificate_hash),
        training_receipt_hashes=tuple(receipt_hash for row in report.rows for receipt_hash in row.training_receipt_hashes),
        baseline_receipt_hashes=tuple(receipt_hash for row in report.rows for receipt_hash in row.baseline_receipt_hashes),
        learned_receipt_hashes=tuple(receipt_hash for row in report.rows for receipt_hash in row.learned_receipt_hashes),
        receipt_hashes=tuple(receipt_hash for row in report.rows for receipt_hash in row.receipt_hashes),
        typed_candidate_hashes=tuple(candidate_hash for row in report.rows for candidate_hash in row.typed_candidate_hashes),
        hard_result_hashes=tuple(result_hash for row in report.rows for result_hash in row.hard_result_hashes),
        hard_metadata_hashes=tuple(metadata_hash for row in report.rows for metadata_hash in row.hard_metadata_hashes),
        receipt_artifact_hashes=tuple(artifact_hash for row in report.rows for artifact_hash in row.receipt_artifact_hashes),
        receipt_artifact_value_hashes=tuple(
            artifact_hash for row in report.rows for artifact_hash in row.receipt_artifact_value_hashes
        ),
        backend_execution_evidence_hashes=tuple(evidence_hash for row in report.rows for evidence_hash in row.backend_execution_evidence_hashes),
        all_child_claims_valid=report.all_child_claims_valid,
        all_child_claims_supported=report.all_child_claims_supported,
        all_child_claims_match_reports=report.all_child_claims_match_reports,
        all_adapter_evidence_certificates_valid=report.all_adapter_evidence_certificates_valid,
        all_adapter_evidence_certificates_match_reports=report.all_adapter_evidence_certificates_match_reports,
        all_adapter_evidence_matches_manifest=report.all_adapter_evidence_matches_manifest,
        all_adapter_task_splits_match_manifest=report.all_adapter_task_splits_match_manifest,
        all_learning_certificates_valid=report.all_learning_certificates_valid,
        all_learning_certificates_match_reports=report.all_learning_certificates_match_reports,
        all_real_backends=report.all_real_backends,
        all_runtime_requirements_match_preflight=report.all_runtime_requirements_match_preflight,
        all_receipt_counts_bound=report.all_receipt_counts_bound,
        all_receipt_artifacts_bound=report.all_receipt_artifacts_bound,
        all_receipt_artifacts_cover_manifest_assets=report.all_receipt_artifacts_cover_manifest_assets,
        all_backend_execution_evidence_bound=report.all_backend_execution_evidence_bound,
        heldout_arms_isolated=report.heldout_arms_isolated,
        hard_verifier_calls_reduced=report.hard_verifier_calls_reduced,
        success_preserved=report.success_preserved,
        replay_rollback_ledger_ok=report.replay_rollback_ledger_ok,
        no_invalid_commits=report.no_invalid_commits,
    )


def validate_real_task_benchmark_suite_report(report: RealTaskBenchmarkSuiteReport) -> bool:
    try:
        if report.schema_version != REAL_TASK_BENCHMARK_SUITE_REPORT_SCHEMA:
            return False
        if report.domain_count != 4 or report.domains != REAL_TASK_BENCHMARK_SUITE_DOMAINS:
            return False
        if len(report.rows) != 4 or tuple(row.domain for row in report.rows) != REAL_TASK_BENCHMARK_SUITE_DOMAINS:
            return False
        if not _is_hash(report.manifest_hash) or not _is_hash(report.manifest_preflight_report_hash) or not _is_hash(report.manifest_certificate_hash):
            return False
        if report.manifest_preflight_report_hash == "0" * 64:
            return False
        if not report.claim_boundary or not report.aggregate_sources:
            return False
        if any(not row.source_urls for row in report.rows):
            return False
        if any(not _is_hash(row.manifest_spec_hash) for row in report.rows):
            return False
        if any(not _is_hash(row.manifest_split_task_hash) for row in report.rows):
            return False
        if any(not row.manifest_benchmark_id or not row.manifest_train_split_id or not row.manifest_held_out_split_id for row in report.rows):
            return False
        if any(not row.manifest_train_task_ids or not row.manifest_held_out_task_ids for row in report.rows):
            return False
        if any(set(row.manifest_train_task_ids).intersection(row.manifest_held_out_task_ids) for row in report.rows):
            return False
        if any(not row.train_task_ids or not row.held_out_task_ids for row in report.rows if row.receipt_count > 0):
            return False
        if any(set(row.train_task_ids).intersection(row.held_out_task_ids) for row in report.rows):
            return False
        if any(not isinstance(row.adapter_task_splits_match_manifest, bool) for row in report.rows):
            return False
        if any(isinstance(row.manifest_runtime_requirement_count, bool) or row.manifest_runtime_requirement_count < 0 for row in report.rows):
            return False
        if any(isinstance(row.manifest_required_task_asset_count, bool) or row.manifest_required_task_asset_count < 0 for row in report.rows):
            return False
        if any(not _is_hash(evidence_hash) for row in report.rows for evidence_hash in row.manifest_runtime_requirement_evidence_hashes):
            return False
        if any(not _is_hash(evidence_hash) for row in report.rows for evidence_hash in row.adapter_runtime_requirement_evidence_hashes):
            return False
        if any(not _is_hash(content_hash) for row in report.rows for content_hash in row.manifest_task_asset_content_hashes):
            return False
        if any(not isinstance(row.backend_error, str) for row in report.rows):
            return False
        if any(not _is_hash(row.child_report_hash) for row in report.rows):
            return False
        if any(not _is_hash(row.adapter_evidence_certificate_hash) for row in report.rows):
            return False
        if any(not _is_hash(row.child_claim_hash) for row in report.rows):
            return False
        if any(row.child_claim_status not in {"supported", "rejected"} for row in report.rows):
            return False
        if any(not isinstance(row.child_claim_matches_report, bool) for row in report.rows):
            return False
        if any(not isinstance(row.adapter_evidence_certificate_valid, bool) for row in report.rows):
            return False
        if any(not isinstance(row.adapter_evidence_certificate_matches_report, bool) for row in report.rows):
            return False
        if any(not isinstance(row.adapter_evidence_matches_manifest, bool) for row in report.rows):
            return False
        if not isinstance(report.all_adapter_task_splits_match_manifest, bool):
            return False
        if any(not isinstance(row.adapter_runtime_requirements_match_preflight, bool) for row in report.rows):
            return False
        if any(not isinstance(row.learning_certificate_matches_report, bool) for row in report.rows):
            return False
        if any(not isinstance(row.heldout_arm_isolated, bool) for row in report.rows):
            return False
        if any(not isinstance(row.receipt_artifacts_bound, bool) for row in report.rows):
            return False
        if any(not isinstance(row.receipt_artifacts_cover_manifest_assets, bool) for row in report.rows):
            return False
        if any(not isinstance(row.backend_execution_evidence_ok, bool) for row in report.rows):
            return False
        if not isinstance(report.heldout_arms_isolated, bool):
            return False
        if not isinstance(report.all_receipt_artifacts_bound, bool):
            return False
        if not isinstance(report.all_runtime_requirements_match_preflight, bool):
            return False
        if not isinstance(report.all_receipt_artifacts_cover_manifest_assets, bool):
            return False
        if not isinstance(report.all_backend_execution_evidence_bound, bool):
            return False
        if report.all_child_claims_valid != all(row.child_claim_valid for row in report.rows):
            return False
        if report.all_child_claims_match_reports != all(row.child_claim_matches_report for row in report.rows):
            return False
        if report.all_adapter_evidence_certificates_valid != all(row.adapter_evidence_certificate_valid for row in report.rows):
            return False
        if report.all_adapter_evidence_certificates_match_reports != all(row.adapter_evidence_certificate_matches_report for row in report.rows):
            return False
        if report.all_adapter_evidence_matches_manifest != all(row.adapter_evidence_matches_manifest for row in report.rows):
            return False
        if report.all_adapter_task_splits_match_manifest != all(row.adapter_task_splits_match_manifest for row in report.rows):
            return False
        if report.all_learning_certificates_match_reports != all(row.learning_certificate_matches_report for row in report.rows):
            return False
        if report.all_runtime_requirements_match_preflight != all(row.adapter_runtime_requirements_match_preflight for row in report.rows):
            return False
        if any(row.adapter_evidence_matches_manifest and not row.adapter_evidence_certificate_matches_report for row in report.rows):
            return False
        if any(row.child_claim_matches_report and not row.child_claim_valid for row in report.rows):
            return False
        for row in report.rows:
            if row.receipt_count != len(row.receipt_hashes):
                return False
            if row.receipt_count != len(row.typed_candidate_hashes):
                return False
            if row.receipt_count != len(row.hard_result_hashes):
                return False
            if row.receipt_count != len(row.hard_metadata_hashes):
                return False
            if row.receipt_count != len(row.receipt_artifact_hashes):
                return False
            if row.receipt_count != len(row.backend_execution_evidence_hashes):
                return False
            if row.receipt_count != row.training_receipt_count + row.baseline_receipt_count + row.learned_receipt_count:
                return False
            if row.training_receipt_count != len(row.training_receipt_hashes):
                return False
            if row.baseline_receipt_count != len(row.baseline_receipt_hashes):
                return False
            if row.learned_receipt_count != len(row.learned_receipt_hashes):
                return False
            if row.receipt_hashes != row.training_receipt_hashes + row.baseline_receipt_hashes + row.learned_receipt_hashes:
                return False
            if any(not _is_hash(receipt_hash) for receipt_hash in row.receipt_hashes):
                return False
            if any(not _is_hash(receipt_hash) for receipt_hash in row.training_receipt_hashes):
                return False
            if any(not _is_hash(receipt_hash) for receipt_hash in row.baseline_receipt_hashes):
                return False
            if any(not _is_hash(receipt_hash) for receipt_hash in row.learned_receipt_hashes):
                return False
            if any(not _is_hash(candidate_hash) for candidate_hash in row.typed_candidate_hashes):
                return False
            if any(not _is_hash(result_hash) for result_hash in row.hard_result_hashes):
                return False
            if any(not _is_hash(metadata_hash) for metadata_hash in row.hard_metadata_hashes):
                return False
            if any(not _is_hash(artifact_hash) for artifact_hash in row.receipt_artifact_hashes):
                return False
            if any(not _is_hash(artifact_hash) for artifact_hash in row.receipt_artifact_value_hashes):
                return False
            if any(not _is_hash(evidence_hash) for evidence_hash in row.backend_execution_evidence_hashes):
                return False
            if row.receipt_artifacts_bound and row.receipt_count == 0:
                return False
            if row.receipt_artifacts_bound and not row.receipt_artifact_value_hashes:
                return False
            if not _row_runtime_requirement_coverage_bound(row):
                return False
            if not _row_manifest_asset_coverage_bound(row):
                return False
            if row.backend_execution_evidence_ok and row.receipt_count == 0:
                return False
            if row.receipt_count > 0 and not _is_hash(row.learning_certificate_hash):
                return False
            if row.receipt_count == 0 and row.learning_certificate_hash:
                return False
            int_fields = (
                row.receipt_count,
                row.training_receipt_count,
                row.baseline_receipt_count,
                row.learned_receipt_count,
                row.committed_count,
                row.rejected_count,
                row.invalid_commit_count,
                row.baseline_verifier_calls,
                row.learned_verifier_calls,
                row.baseline_success_count,
                row.learned_success_count,
                row.verifier_call_reduction,
            )
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in int_fields):
                return False
            if row.verifier_call_reduction != row.baseline_verifier_calls - row.learned_verifier_calls:
                return False
            if not _row_task_split_coverage_bound(row):
                return False
        if report.total_receipt_count != sum(row.receipt_count for row in report.rows):
            return False
        if report.total_training_receipt_count != sum(row.training_receipt_count for row in report.rows):
            return False
        if report.total_baseline_receipt_count != sum(row.baseline_receipt_count for row in report.rows):
            return False
        if report.total_learned_receipt_count != sum(row.learned_receipt_count for row in report.rows):
            return False
        if report.total_committed_count != sum(row.committed_count for row in report.rows):
            return False
        if report.total_rejected_count != sum(row.rejected_count for row in report.rows):
            return False
        if report.total_invalid_commit_count != sum(row.invalid_commit_count for row in report.rows):
            return False
        if report.baseline_verifier_calls != sum(row.baseline_verifier_calls for row in report.rows):
            return False
        if report.learned_verifier_calls != sum(row.learned_verifier_calls for row in report.rows):
            return False
        if report.baseline_success_count != sum(row.baseline_success_count for row in report.rows):
            return False
        if report.learned_success_count != sum(row.learned_success_count for row in report.rows):
            return False
        if report.verifier_call_reduction != report.baseline_verifier_calls - report.learned_verifier_calls:
            return False
        if report.all_backends_available != all(row.backend_available for row in report.rows):
            return False
        if report.all_real_backends != all(row.real_backend for row in report.rows):
            return False
        if report.all_child_claims_supported != all(row.child_claim_valid and row.child_claim_status == "supported" for row in report.rows):
            return False
        if report.all_learning_certificates_valid != all(row.learning_certificate_valid for row in report.rows):
            return False
        if report.all_learning_certificates_support_claim != all(row.learning_certificate_supports_claim for row in report.rows):
            return False
        if report.all_receipt_counts_bound != all(_row_receipt_counts_bound(row) for row in report.rows):
            return False
        if report.all_receipt_artifacts_bound != all(row.receipt_artifacts_bound for row in report.rows):
            return False
        if report.all_receipt_artifacts_cover_manifest_assets != all(row.receipt_artifacts_cover_manifest_assets for row in report.rows):
            return False
        if report.all_backend_execution_evidence_bound != all(row.backend_execution_evidence_ok for row in report.rows):
            return False
        if report.heldout_arms_isolated != all(row.heldout_arm_isolated for row in report.rows):
            return False
        if report.hard_verifier_calls_reduced != all(row.learned_verifier_calls < row.baseline_verifier_calls for row in report.rows):
            return False
        if report.success_preserved != all(row.learned_success_count == row.baseline_success_count and row.learned_success_count > 0 for row in report.rows):
            return False
        if report.replay_rollback_ledger_ok != all(row.replay_audit_ok and row.rollback_audit_ok and row.ledger_audit_ok for row in report.rows):
            return False
        if report.no_invalid_commits != (report.total_invalid_commit_count == 0):
            return False
        expected_missing = tuple(
            f"{row.domain}:{missing}" for row in report.rows for missing in row.missing_requirements
        )
        if report.missing_requirements != expected_missing:
            return False
        return True
    except Exception:
        return False


def validate_real_task_benchmark_suite_certificate(
    certificate: RealTaskBenchmarkSuiteCertificate,
    report: RealTaskBenchmarkSuiteReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != REAL_TASK_BENCHMARK_SUITE_CERTIFICATE_SCHEMA:
            return False
        if certificate.domain_count != 4 or certificate.domains != REAL_TASK_BENCHMARK_SUITE_DOMAINS:
            return False
        for hash_value in (
            certificate.report_hash,
            certificate.manifest_hash,
            certificate.manifest_preflight_report_hash,
            certificate.manifest_certificate_hash,
            certificate.certificate_hash,
        ):
            if not _is_hash(hash_value):
                return False
        if certificate.manifest_preflight_report_hash == "0" * 64:
            return False
        if len(certificate.manifest_spec_hashes) != 4 or any(not _is_hash(row) for row in certificate.manifest_spec_hashes):
            return False
        if len(certificate.manifest_split_task_hashes) != 4 or any(not _is_hash(row) for row in certificate.manifest_split_task_hashes):
            return False
        if not certificate.manifest_train_task_ids or not certificate.manifest_held_out_task_ids:
            return False
        if any(not value for value in (*certificate.manifest_train_task_ids, *certificate.manifest_held_out_task_ids)):
            return False
        if any(not value for value in (*certificate.adapter_train_task_ids, *certificate.adapter_held_out_task_ids)):
            return False
        if any(not _is_hash(row) for row in certificate.manifest_runtime_requirement_evidence_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.adapter_runtime_requirement_evidence_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.manifest_task_asset_content_hashes):
            return False
        if len(certificate.child_report_hashes) != 4 or any(not _is_hash(row) for row in certificate.child_report_hashes):
            return False
        if len(certificate.adapter_evidence_certificate_hashes) != 4 or any(
            not _is_hash(row) for row in certificate.adapter_evidence_certificate_hashes
        ):
            return False
        if len(certificate.child_claim_hashes) != 4 or any(not _is_hash(row) for row in certificate.child_claim_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.learning_certificate_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.training_receipt_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.baseline_receipt_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.learned_receipt_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.receipt_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.typed_candidate_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.hard_result_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.hard_metadata_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.receipt_artifact_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.receipt_artifact_value_hashes):
            return False
        if any(not _is_hash(row) for row in certificate.backend_execution_evidence_hashes):
            return False
        if not (
            len(certificate.receipt_hashes)
            == len(certificate.typed_candidate_hashes)
            == len(certificate.hard_result_hashes)
            == len(certificate.hard_metadata_hashes)
            == len(certificate.receipt_artifact_hashes)
            == len(certificate.backend_execution_evidence_hashes)
        ):
            return False
        receipt_partition_hashes = certificate.training_receipt_hashes + certificate.baseline_receipt_hashes + certificate.learned_receipt_hashes
        if len(receipt_partition_hashes) != len(certificate.receipt_hashes):
            return False
        if set(receipt_partition_hashes) != set(certificate.receipt_hashes):
            return False
        if len(set(receipt_partition_hashes)) != len(receipt_partition_hashes):
            return False
        if not certificate.all_receipt_counts_bound and certificate.all_child_claims_supported:
            return False
        if certificate.all_child_claims_supported and not certificate.all_child_claims_valid:
            return False
        if not isinstance(certificate.heldout_arms_isolated, bool):
            return False
        if not isinstance(certificate.all_backend_execution_evidence_bound, bool):
            return False
        if not isinstance(certificate.all_runtime_requirements_match_preflight, bool):
            return False
        if not isinstance(certificate.all_receipt_artifacts_bound, bool):
            return False
        if certificate.all_receipt_artifacts_bound and not certificate.receipt_artifact_value_hashes:
            return False
        if not isinstance(certificate.all_receipt_artifacts_cover_manifest_assets, bool):
            return False
        if not isinstance(certificate.all_adapter_task_splits_match_manifest, bool):
            return False
        if certificate.all_child_claims_supported and not certificate.all_adapter_task_splits_match_manifest:
            return False
        if certificate.all_child_claims_supported and not certificate.all_receipt_artifacts_bound:
            return False
        if certificate.all_child_claims_supported and not certificate.all_runtime_requirements_match_preflight:
            return False
        if certificate.all_child_claims_supported and not certificate.all_receipt_artifacts_cover_manifest_assets:
            return False
        if certificate.all_child_claims_supported and not certificate.all_backend_execution_evidence_bound:
            return False
        if certificate.all_child_claims_supported and not certificate.heldout_arms_isolated:
            return False
        if report is not None:
            if not validate_real_task_benchmark_suite_report(report):
                return False
            if certificate.report_hash != real_task_benchmark_suite_report_hash(report):
                return False
            if certificate.manifest_hash != report.manifest_hash:
                return False
            if certificate.manifest_preflight_report_hash != report.manifest_preflight_report_hash:
                return False
            if certificate.manifest_certificate_hash != report.manifest_certificate_hash:
                return False
            if certificate.domains != report.domains:
                return False
            if certificate.manifest_spec_hashes != tuple(row.manifest_spec_hash for row in report.rows):
                return False
            if certificate.manifest_split_task_hashes != tuple(row.manifest_split_task_hash for row in report.rows):
                return False
            if certificate.manifest_train_task_ids != tuple(task_id for row in report.rows for task_id in row.manifest_train_task_ids):
                return False
            if certificate.manifest_held_out_task_ids != tuple(task_id for row in report.rows for task_id in row.manifest_held_out_task_ids):
                return False
            if certificate.manifest_runtime_requirement_evidence_hashes != tuple(
                evidence_hash for row in report.rows for evidence_hash in row.manifest_runtime_requirement_evidence_hashes
            ):
                return False
            if certificate.manifest_task_asset_content_hashes != tuple(
                content_hash for row in report.rows for content_hash in row.manifest_task_asset_content_hashes
            ):
                return False
            if certificate.adapter_train_task_ids != tuple(task_id for row in report.rows for task_id in row.train_task_ids):
                return False
            if certificate.adapter_held_out_task_ids != tuple(task_id for row in report.rows for task_id in row.held_out_task_ids):
                return False
            if certificate.adapter_runtime_requirement_evidence_hashes != tuple(
                evidence_hash for row in report.rows for evidence_hash in row.adapter_runtime_requirement_evidence_hashes
            ):
                return False
            if certificate.child_report_hashes != tuple(row.child_report_hash for row in report.rows):
                return False
            if certificate.adapter_evidence_certificate_hashes != tuple(row.adapter_evidence_certificate_hash for row in report.rows):
                return False
            if certificate.child_claim_hashes != tuple(row.child_claim_hash for row in report.rows):
                return False
            if certificate.learning_certificate_hashes != tuple(row.learning_certificate_hash for row in report.rows if row.learning_certificate_hash):
                return False
            if certificate.training_receipt_hashes != tuple(receipt_hash for row in report.rows for receipt_hash in row.training_receipt_hashes):
                return False
            if certificate.baseline_receipt_hashes != tuple(receipt_hash for row in report.rows for receipt_hash in row.baseline_receipt_hashes):
                return False
            if certificate.learned_receipt_hashes != tuple(receipt_hash for row in report.rows for receipt_hash in row.learned_receipt_hashes):
                return False
            if certificate.receipt_hashes != tuple(receipt_hash for row in report.rows for receipt_hash in row.receipt_hashes):
                return False
            if certificate.typed_candidate_hashes != tuple(candidate_hash for row in report.rows for candidate_hash in row.typed_candidate_hashes):
                return False
            if certificate.hard_result_hashes != tuple(result_hash for row in report.rows for result_hash in row.hard_result_hashes):
                return False
            if certificate.hard_metadata_hashes != tuple(metadata_hash for row in report.rows for metadata_hash in row.hard_metadata_hashes):
                return False
            if certificate.receipt_artifact_hashes != tuple(artifact_hash for row in report.rows for artifact_hash in row.receipt_artifact_hashes):
                return False
            if certificate.receipt_artifact_value_hashes != tuple(
                artifact_hash for row in report.rows for artifact_hash in row.receipt_artifact_value_hashes
            ):
                return False
            if certificate.backend_execution_evidence_hashes != tuple(evidence_hash for row in report.rows for evidence_hash in row.backend_execution_evidence_hashes):
                return False
            for field in (
                "all_child_claims_valid",
                "all_child_claims_supported",
                "all_child_claims_match_reports",
                "all_adapter_evidence_certificates_valid",
                "all_adapter_evidence_certificates_match_reports",
                "all_adapter_evidence_matches_manifest",
                "all_adapter_task_splits_match_manifest",
                "all_learning_certificates_valid",
                "all_learning_certificates_match_reports",
                "all_real_backends",
                "all_runtime_requirements_match_preflight",
                "all_receipt_counts_bound",
                "all_receipt_artifacts_bound",
                "all_receipt_artifacts_cover_manifest_assets",
                "all_backend_execution_evidence_bound",
                "heldout_arms_isolated",
                "hard_verifier_calls_reduced",
                "success_preserved",
                "replay_rollback_ledger_ok",
                "no_invalid_commits",
            ):
                if getattr(certificate, field) != getattr(report, field):
                    return False
        return certificate.certificate_hash == real_task_benchmark_suite_certificate_hash(certificate)
    except Exception:
        return False


def _build_report(
    manifest: RealTaskBenchmarkManifest,
    preflight_report: RealTaskBenchmarkPreflightReport,
    manifest_certificate: RealTaskBenchmarkManifestCertificate,
    rows: tuple[RealTaskBenchmarkSuiteRow, ...],
    child_claims_valid: tuple[bool, ...],
    child_claims_supported: tuple[bool, ...],
) -> RealTaskBenchmarkSuiteReport:
    return RealTaskBenchmarkSuiteReport(
        schema_version=REAL_TASK_BENCHMARK_SUITE_REPORT_SCHEMA,
        experiment_id="receipt_trained_reversible_real_task_suite",
        manifest_hash=manifest.manifest_hash,
        manifest_preflight_report_hash=real_task_preflight_report_hash(preflight_report),
        manifest_certificate_hash=manifest_certificate.certificate_hash,
        domain_count=len(rows),
        domains=tuple(row.domain for row in rows),
        rows=rows,
        all_child_claims_valid=all(child_claims_valid),
        all_child_claims_supported=all(child_claims_supported),
        all_child_claims_match_reports=all(row.child_claim_matches_report for row in rows),
        all_adapter_evidence_certificates_valid=all(row.adapter_evidence_certificate_valid for row in rows),
        all_adapter_evidence_certificates_match_reports=all(row.adapter_evidence_certificate_matches_report for row in rows),
        all_adapter_evidence_matches_manifest=all(row.adapter_evidence_matches_manifest for row in rows),
        all_adapter_task_splits_match_manifest=all(row.adapter_task_splits_match_manifest for row in rows),
        all_learning_certificates_valid=all(row.learning_certificate_valid for row in rows),
        all_learning_certificates_support_claim=all(row.learning_certificate_supports_claim for row in rows),
        all_learning_certificates_match_reports=all(row.learning_certificate_matches_report for row in rows),
        all_backends_available=all(row.backend_available for row in rows),
        all_real_backends=all(row.real_backend for row in rows),
        all_runtime_requirements_match_preflight=all(row.adapter_runtime_requirements_match_preflight for row in rows),
        all_receipt_counts_bound=all(_row_receipt_counts_bound(row) for row in rows),
        all_receipt_artifacts_bound=all(row.receipt_artifacts_bound for row in rows),
        all_receipt_artifacts_cover_manifest_assets=all(row.receipt_artifacts_cover_manifest_assets for row in rows),
        all_backend_execution_evidence_bound=all(row.backend_execution_evidence_ok for row in rows),
        heldout_arms_isolated=all(row.heldout_arm_isolated for row in rows),
        hard_verifier_calls_reduced=all(row.learned_verifier_calls < row.baseline_verifier_calls for row in rows),
        success_preserved=all(row.learned_success_count == row.baseline_success_count and row.learned_success_count > 0 for row in rows),
        replay_rollback_ledger_ok=all(row.replay_audit_ok and row.rollback_audit_ok and row.ledger_audit_ok for row in rows),
        no_invalid_commits=sum(row.invalid_commit_count for row in rows) == 0,
        total_receipt_count=sum(row.receipt_count for row in rows),
        total_training_receipt_count=sum(row.training_receipt_count for row in rows),
        total_baseline_receipt_count=sum(row.baseline_receipt_count for row in rows),
        total_learned_receipt_count=sum(row.learned_receipt_count for row in rows),
        total_committed_count=sum(row.committed_count for row in rows),
        total_rejected_count=sum(row.rejected_count for row in rows),
        total_invalid_commit_count=sum(row.invalid_commit_count for row in rows),
        baseline_verifier_calls=sum(row.baseline_verifier_calls for row in rows),
        learned_verifier_calls=sum(row.learned_verifier_calls for row in rows),
        baseline_success_count=sum(row.baseline_success_count for row in rows),
        learned_success_count=sum(row.learned_success_count for row in rows),
        verifier_call_reduction=sum(row.verifier_call_reduction for row in rows),
        missing_requirements=tuple(f"{row.domain}:{missing}" for row in rows for missing in row.missing_requirements),
        aggregate_sources=tuple(sorted({source for row in rows for source in row.source_urls})),
        claim_boundary=REAL_TASK_BENCHMARK_SUITE_CLAIM_BOUNDARY,
    )


def _suite_row(
    domain: str,
    result: Any,
    manifest_spec: RealTaskBenchmarkSpec,
    preflight_row: RealTaskPreflightRow,
) -> RealTaskBenchmarkSuiteRow:
    report = result.report
    learning_certificate = result.learning_certificate
    learning_valid = False
    learning_supports = False
    learning_hash = ""
    if learning_certificate is not None:
        learning_valid = validate_learning_evaluation_certificate(learning_certificate)
        learning_supports = learning_evaluation_supports_claim(learning_certificate)
        learning_hash = learning_certificate.certificate_hash
    child_claim = result.claim_certificate
    child_claim_valid = validate_claim_certificate(child_claim)
    adapter_evidence_certificate = result.evidence_certificate
    adapter_evidence_valid = validate_real_task_adapter_evidence_certificate(
        adapter_evidence_certificate,
        report=report,
        learning_certificate=learning_certificate,
        claim_certificate=child_claim,
    )
    manifest_runtime_requirement_count = runtime_requirement_count(manifest_spec)
    manifest_runtime_requirement_evidence_hashes = preflight_runtime_requirement_evidence_hashes(preflight_row)
    adapter_runtime_requirement_evidence_hashes = tuple(str(row) for row in report.runtime_requirement_evidence_hashes)
    train_task_ids = tuple(str(row) for row in report.train_task_ids)
    held_out_task_ids = tuple(str(row) for row in report.held_out_task_ids)
    adapter_task_splits_match_manifest = _adapter_task_splits_match_manifest(
        manifest_train_task_ids=manifest_spec.train_task_ids,
        manifest_held_out_task_ids=manifest_spec.held_out_task_ids,
        adapter_train_task_ids=train_task_ids,
        adapter_held_out_task_ids=held_out_task_ids,
    )
    adapter_runtime_requirements_match_preflight = _adapter_runtime_requirements_match_preflight(
        backend_available=bool(report.backend_available),
        real_backend=bool(report.real_backend),
        manifest_runtime_requirement_count=manifest_runtime_requirement_count,
        manifest_runtime_requirement_evidence_hashes=manifest_runtime_requirement_evidence_hashes,
        adapter_runtime_requirement_evidence_hashes=adapter_runtime_requirement_evidence_hashes,
    )
    manifest_task_asset_content_hashes = preflight_task_asset_content_hashes(preflight_row)
    receipt_artifact_value_hashes = tuple(str(row) for row in report.receipt_artifact_value_hashes)
    receipt_artifacts_cover_manifest_assets = _receipt_artifacts_cover_manifest_assets(
        manifest_required_task_asset_count=len(manifest_spec.required_task_assets),
        manifest_task_asset_content_hashes=manifest_task_asset_content_hashes,
        receipt_artifact_value_hashes=receipt_artifact_value_hashes,
    )
    receipt_hashes = tuple(str(row) for row in report.receipt_hashes)
    training_receipt_hashes, baseline_receipt_hashes, learned_receipt_hashes = _receipt_partitions(
        receipt_hashes=receipt_hashes,
        training_receipt_count=int(report.training_receipt_count),
        baseline_receipt_count=int(report.baseline_receipt_count),
        learned_receipt_count=int(report.learned_receipt_count),
    )
    return RealTaskBenchmarkSuiteRow(
        domain=domain,
        report_schema_version=str(report.schema_version),
        experiment_id=str(report.experiment_id),
        backend_id=str(report.backend_id),
        backend_version=str(report.backend_version),
        backend_available=bool(report.backend_available),
        real_backend=bool(report.real_backend),
        missing_requirements=tuple(str(row) for row in report.missing_requirements),
        backend_error=str(getattr(report, "backend_error", "")),
        adapter_runtime_requirement_evidence_hashes=adapter_runtime_requirement_evidence_hashes,
        adapter_runtime_requirements_match_preflight=adapter_runtime_requirements_match_preflight,
        manifest_spec_hash=manifest_spec.spec_hash,
        manifest_benchmark_id=manifest_spec.benchmark_id,
        manifest_train_split_id=manifest_spec.train_split_id,
        manifest_held_out_split_id=manifest_spec.held_out_split_id,
        manifest_train_task_ids=manifest_spec.train_task_ids,
        manifest_held_out_task_ids=manifest_spec.held_out_task_ids,
        manifest_split_task_hash=manifest_split_task_hash(manifest_spec),
        adapter_task_splits_match_manifest=adapter_task_splits_match_manifest,
        manifest_runtime_requirement_count=manifest_runtime_requirement_count,
        manifest_runtime_requirement_evidence_hashes=manifest_runtime_requirement_evidence_hashes,
        manifest_required_task_asset_count=len(manifest_spec.required_task_assets),
        manifest_task_asset_content_hashes=manifest_task_asset_content_hashes,
        child_report_hash=stable_hash(asdict(report)),
        adapter_evidence_certificate_hash=str(adapter_evidence_certificate.certificate_hash),
        adapter_evidence_certificate_valid=adapter_evidence_valid,
        adapter_evidence_certificate_matches_report=(
            adapter_evidence_valid
            and adapter_evidence_certificate.report_hash == stable_hash(asdict(report))
            and adapter_evidence_certificate.domain == domain
        ),
        adapter_evidence_matches_manifest=_adapter_evidence_matches_manifest(
            domain,
            manifest_spec,
            report,
            adapter_evidence_certificate,
            adapter_evidence_valid,
        ),
        child_claim_valid=child_claim_valid,
        child_claim_status=str(child_claim.status),
        child_claim_hash=str(child_claim.certificate_hash),
        child_claim_matches_report=_child_claim_matches_report(domain, report, child_claim),
        learning_certificate_hash=learning_hash,
        learning_certificate_valid=learning_valid,
        learning_certificate_supports_claim=learning_supports,
        learning_certificate_matches_report=_learning_certificate_matches_report(report, learning_certificate),
        train_task_ids=train_task_ids,
        held_out_task_ids=held_out_task_ids,
        receipt_count=int(report.receipt_count),
        training_receipt_count=int(report.training_receipt_count),
        baseline_receipt_count=int(report.baseline_receipt_count),
        learned_receipt_count=int(report.learned_receipt_count),
        committed_count=int(report.committed_count),
        rejected_count=int(report.rejected_count),
        invalid_commit_count=int(report.invalid_commit_count),
        baseline_verifier_calls=int(report.baseline_verifier_calls),
        learned_verifier_calls=int(report.learned_verifier_calls),
        baseline_success_count=int(report.baseline_success_count),
        learned_success_count=int(report.learned_success_count),
        verifier_call_reduction=int(report.verifier_call_reduction),
        hard_commit_only=bool(report.hard_commit_only),
        heldout_arm_isolated=bool(report.heldout_arm_isolated),
        replay_audit_ok=bool(report.replay_audit_ok),
        rollback_audit_ok=bool(report.rollback_audit_ok),
        ledger_audit_ok=bool(report.ledger_audit_ok),
        training_receipt_hashes=training_receipt_hashes,
        baseline_receipt_hashes=baseline_receipt_hashes,
        learned_receipt_hashes=learned_receipt_hashes,
        receipt_hashes=receipt_hashes,
        typed_candidate_hashes=tuple(str(row) for row in report.typed_candidate_hashes),
        hard_result_hashes=tuple(str(row) for row in report.hard_result_hashes),
        hard_metadata_hashes=tuple(str(row) for row in report.hard_metadata_hashes),
        receipt_artifacts_bound=bool(report.receipt_artifacts_bound),
        receipt_artifact_hashes=tuple(str(row) for row in report.receipt_artifact_hashes),
        receipt_artifact_value_hashes=receipt_artifact_value_hashes,
        receipt_artifacts_cover_manifest_assets=receipt_artifacts_cover_manifest_assets,
        backend_execution_evidence_ok=bool(report.backend_execution_evidence_ok),
        backend_execution_evidence_hashes=tuple(str(row) for row in report.backend_execution_evidence_hashes),
        source_urls=tuple(str(row) for row in report.source_urls),
        claim_boundary=str(report.claim_boundary),
    )


def _adapter_evidence_matches_manifest(
    domain: str,
    manifest_spec: RealTaskBenchmarkSpec,
    report: Any,
    adapter_evidence_certificate: Any,
    adapter_evidence_valid: bool,
) -> bool:
    if manifest_spec.domain != domain or not adapter_evidence_valid:
        return False
    manifest_sources = set(manifest_spec.source_urls)
    report_sources = set(report.source_urls)
    evidence_sources = set(adapter_evidence_certificate.source_urls)
    if not report_sources or not report_sources.issubset(manifest_sources):
        return False
    if not evidence_sources or not evidence_sources.issubset(manifest_sources):
        return False
    if adapter_evidence_certificate.domain != domain:
        return False
    if adapter_evidence_certificate.backend_id != report.backend_id:
        return False
    if adapter_evidence_certificate.train_task_ids != tuple(report.train_task_ids):
        return False
    if adapter_evidence_certificate.held_out_task_ids != tuple(report.held_out_task_ids):
        return False
    if report.receipt_count > 0 and (not report.train_task_ids or not report.held_out_task_ids):
        return False
    if set(report.train_task_ids).intersection(report.held_out_task_ids):
        return False
    return True


def _child_claim_matches_report(domain: str, report: Any, claim: ClaimCertificate) -> bool:
    if not validate_claim_certificate(claim):
        return False
    real_backend_requirement = _REAL_BACKEND_REQUIREMENT_BY_DOMAIN.get(domain)
    if real_backend_requirement is None:
        return False
    expected_requirement_keys = (
        "backend_available",
        real_backend_requirement,
        "runtime_requirements_bound",
        "receipt_artifacts_bound",
        "backend_execution_evidence_bound",
        "learning_certificate_valid",
        "learning_certificate_supports_claim",
        "hard_verifier_calls_reduced",
        "success_preserved",
        "zero_invalid_commits",
        "heldout_arm_isolated",
        "replay_rollback_ok",
    )
    if tuple(row.key for row in claim.requirements) != expected_requirement_keys:
        return False
    requirements = {row.key: row for row in claim.requirements}
    backend_requirement = requirements["backend_available"]
    if tuple(backend_requirement.evidence.get("missing", ())) != tuple(report.missing_requirements):
        return False
    if str(backend_requirement.evidence.get("error", "")) != str(getattr(report, "backend_error", "")):
        return False
    runtime_requirement = requirements["runtime_requirements_bound"]
    if tuple(runtime_requirement.evidence.get("evidence_hashes", ())) != tuple(report.runtime_requirement_evidence_hashes):
        return False
    execution_requirement = requirements["backend_execution_evidence_bound"]
    if tuple(execution_requirement.evidence.get("evidence_hashes", ())) != tuple(report.backend_execution_evidence_hashes):
        return False
    artifact_requirement = requirements["receipt_artifacts_bound"]
    if tuple(artifact_requirement.evidence.get("artifact_hashes", ())) != tuple(report.receipt_artifact_hashes):
        return False
    expected_passes = {
        "backend_available": bool(report.backend_available),
        real_backend_requirement: bool(report.real_backend),
        "runtime_requirements_bound": (not bool(report.real_backend)) or bool(report.runtime_requirement_evidence_hashes),
        "receipt_artifacts_bound": bool(report.receipt_artifacts_bound),
        "backend_execution_evidence_bound": bool(report.backend_execution_evidence_ok),
        "learning_certificate_valid": bool(report.learning_certificate_valid),
        "learning_certificate_supports_claim": bool(report.learning_certificate_supports_claim),
        "hard_verifier_calls_reduced": report.learned_verifier_calls < report.baseline_verifier_calls,
        "success_preserved": report.learned_success_count == report.baseline_success_count and report.learned_success_count > 0,
        "zero_invalid_commits": report.invalid_commit_count == 0,
        "heldout_arm_isolated": bool(report.heldout_arm_isolated),
        "replay_rollback_ok": bool(report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
    }
    if any(requirements[key].passed != expected_passes[key] for key in expected_requirement_keys):
        return False
    expected_metrics = {
        "baseline_verifier_calls": int(report.baseline_verifier_calls),
        "learned_verifier_calls": int(report.learned_verifier_calls),
        "verifier_call_reduction": int(report.verifier_call_reduction),
        "invalid_commit_count": int(report.invalid_commit_count),
    }
    if claim.metrics != expected_metrics:
        return False
    return (
        claim.claim_id == _CHILD_CLAIM_ID_BY_DOMAIN[domain]
        and claim.scope == _CHILD_CLAIM_SCOPE_BY_DOMAIN[domain]
        and claim.evidence_grade
        == (
            "G1"
            if (
                report.backend_available
                and report.real_backend
                and bool(report.runtime_requirement_evidence_hashes)
                and report.receipt_artifacts_bound
                and report.backend_execution_evidence_ok
            )
            else "G0"
        )
        and claim.status == ("supported" if all(expected_passes.values()) else "rejected")
        and claim.boundary == report.claim_boundary
        and claim.sources == tuple(report.source_urls)
    )


def _learning_certificate_matches_report(report: Any, learning_certificate: Any | None) -> bool:
    if learning_certificate is None:
        return (
            report.receipt_count == 0
            and report.training_receipt_count == 0
            and report.baseline_receipt_count == 0
            and report.learned_receipt_count == 0
            and report.learner_snapshot_hash == ""
            and report.learning_certificate_hash == ""
            and not report.learning_certificate_valid
            and not report.learning_certificate_supports_claim
        )
    if not validate_learning_evaluation_certificate(learning_certificate):
        return False
    receipt_hashes = tuple(report.receipt_hashes)
    training_end = int(report.training_receipt_count)
    learned_start = int(report.training_receipt_count) + int(report.baseline_receipt_count)
    training_hashes = receipt_hashes[:training_end]
    baseline_hashes = receipt_hashes[training_end:learned_start]
    learned_hashes = receipt_hashes[learned_start:]
    expected_metrics = {
        "backend_id": str(report.backend_id),
        "real_backend": bool(report.real_backend),
        "held_out_task_ids": tuple(report.held_out_task_ids),
        "heldout_arm_isolated": bool(report.heldout_arm_isolated),
    }
    return (
        learning_certificate.certificate_hash == report.learning_certificate_hash
        and learning_certificate.learner_snapshot_hash == report.learner_snapshot_hash
        and learning_certificate.training_receipt_hashes == training_hashes
        and learning_certificate.baseline_receipt_hashes == baseline_hashes
        and learning_certificate.evaluation_receipt_hashes == learned_hashes
        and len(learning_certificate.training_receipt_hashes) == report.training_receipt_count
        and len(learning_certificate.baseline_receipt_hashes) == report.baseline_receipt_count
        and len(learning_certificate.evaluation_receipt_hashes) == report.learned_receipt_count
        and learning_certificate.baseline_verifier_calls == report.baseline_verifier_calls
        and learning_certificate.learned_verifier_calls == report.learned_verifier_calls
        and learning_certificate.baseline_success_count == report.baseline_success_count
        and learning_certificate.learned_success_count == report.learned_success_count
        and learning_certificate.verifier_budget == report.baseline_verifier_calls
        and learning_certificate.candidate_count == 2 * len(report.held_out_task_ids)
        and learning_certificate.same_case_baseline
        and learning_certificate.train_eval_disjoint == report.train_eval_disjoint
        and learning_certificate.hard_commit_only == report.hard_commit_only
        and learning_certificate.invalid_commit_count == report.invalid_commit_count
        and learning_certificate.ledger_audit == report.ledger_audit_ok
        and learning_certificate.replay_rollback_rate == (1.0 if report.replay_audit_ok and report.rollback_audit_ok else 0.0)
        and learning_certificate.metrics == expected_metrics
        and report.learning_certificate_valid == validate_learning_evaluation_certificate(learning_certificate)
        and report.learning_certificate_supports_claim == learning_evaluation_supports_claim(learning_certificate)
    )


def real_task_benchmark_suite_report_hash(report: RealTaskBenchmarkSuiteReport) -> str:
    return stable_hash(asdict(report))


def real_task_benchmark_suite_certificate_hash(certificate: RealTaskBenchmarkSuiteCertificate) -> str:
    return stable_hash(certificate.without_hash())


def _row_receipt_counts_bound(row: RealTaskBenchmarkSuiteRow) -> bool:
    return (
        row.receipt_count
        == len(row.receipt_hashes)
        == len(row.typed_candidate_hashes)
        == len(row.hard_result_hashes)
        == len(row.hard_metadata_hashes)
        == len(row.receipt_artifact_hashes)
        == len(row.backend_execution_evidence_hashes)
        and row.training_receipt_count == len(row.training_receipt_hashes)
        and row.baseline_receipt_count == len(row.baseline_receipt_hashes)
        and row.learned_receipt_count == len(row.learned_receipt_hashes)
        and row.receipt_hashes == row.training_receipt_hashes + row.baseline_receipt_hashes + row.learned_receipt_hashes
    )


def _receipt_partitions(
    *,
    receipt_hashes: tuple[str, ...],
    training_receipt_count: int,
    baseline_receipt_count: int,
    learned_receipt_count: int,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    training_end = training_receipt_count
    baseline_end = training_receipt_count + baseline_receipt_count
    learned_end = baseline_end + learned_receipt_count
    return (
        receipt_hashes[:training_end],
        receipt_hashes[training_end:baseline_end],
        receipt_hashes[baseline_end:learned_end],
    )


def _adapter_task_splits_match_manifest(
    *,
    manifest_train_task_ids: tuple[str, ...],
    manifest_held_out_task_ids: tuple[str, ...],
    adapter_train_task_ids: tuple[str, ...],
    adapter_held_out_task_ids: tuple[str, ...],
) -> bool:
    if not manifest_train_task_ids or not manifest_held_out_task_ids:
        return False
    if not adapter_train_task_ids or not adapter_held_out_task_ids:
        return False
    if set(manifest_train_task_ids).intersection(manifest_held_out_task_ids):
        return False
    if set(adapter_train_task_ids).intersection(adapter_held_out_task_ids):
        return False
    return adapter_train_task_ids == manifest_train_task_ids and adapter_held_out_task_ids == manifest_held_out_task_ids


def _row_task_split_coverage_bound(row: RealTaskBenchmarkSuiteRow) -> bool:
    expected = _adapter_task_splits_match_manifest(
        manifest_train_task_ids=row.manifest_train_task_ids,
        manifest_held_out_task_ids=row.manifest_held_out_task_ids,
        adapter_train_task_ids=row.train_task_ids,
        adapter_held_out_task_ids=row.held_out_task_ids,
    )
    if row.adapter_task_splits_match_manifest != expected:
        return False
    if row.manifest_split_task_hash != stable_hash(
        {
            "domain": row.domain,
            "benchmark_id": row.manifest_benchmark_id,
            "train_split_id": row.manifest_train_split_id,
            "held_out_split_id": row.manifest_held_out_split_id,
            "train_task_ids": row.manifest_train_task_ids,
            "held_out_task_ids": row.manifest_held_out_task_ids,
        }
    ):
        return False
    return True


def _receipt_artifacts_cover_manifest_assets(
    *,
    manifest_required_task_asset_count: int,
    manifest_task_asset_content_hashes: tuple[str, ...],
    receipt_artifact_value_hashes: tuple[str, ...],
) -> bool:
    if manifest_required_task_asset_count == 0:
        return not manifest_task_asset_content_hashes
    if len(manifest_task_asset_content_hashes) != manifest_required_task_asset_count:
        return False
    return set(manifest_task_asset_content_hashes).issubset(set(receipt_artifact_value_hashes))


def _adapter_runtime_requirements_match_preflight(
    *,
    backend_available: bool,
    real_backend: bool,
    manifest_runtime_requirement_count: int,
    manifest_runtime_requirement_evidence_hashes: tuple[str, ...],
    adapter_runtime_requirement_evidence_hashes: tuple[str, ...],
) -> bool:
    if not backend_available or not real_backend:
        return False
    if len(manifest_runtime_requirement_evidence_hashes) != manifest_runtime_requirement_count:
        return False
    return adapter_runtime_requirement_evidence_hashes == manifest_runtime_requirement_evidence_hashes


def _row_runtime_requirement_coverage_bound(row: RealTaskBenchmarkSuiteRow) -> bool:
    expected = _adapter_runtime_requirements_match_preflight(
        backend_available=row.backend_available,
        real_backend=row.real_backend,
        manifest_runtime_requirement_count=row.manifest_runtime_requirement_count,
        manifest_runtime_requirement_evidence_hashes=row.manifest_runtime_requirement_evidence_hashes,
        adapter_runtime_requirement_evidence_hashes=row.adapter_runtime_requirement_evidence_hashes,
    )
    return row.adapter_runtime_requirements_match_preflight == expected


def _row_manifest_asset_coverage_bound(row: RealTaskBenchmarkSuiteRow) -> bool:
    expected = _receipt_artifacts_cover_manifest_assets(
        manifest_required_task_asset_count=row.manifest_required_task_asset_count,
        manifest_task_asset_content_hashes=row.manifest_task_asset_content_hashes,
        receipt_artifact_value_hashes=row.receipt_artifact_value_hashes,
    )
    if row.receipt_artifacts_cover_manifest_assets != expected:
        return False
    if row.manifest_required_task_asset_count > 0 and row.receipt_artifacts_cover_manifest_assets and not row.receipt_artifacts_bound:
        return False
    return True


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def result_as_dict(result: RealTaskBenchmarkSuiteResult) -> dict[str, Any]:
    return asdict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_real_task_benchmark_suite()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
