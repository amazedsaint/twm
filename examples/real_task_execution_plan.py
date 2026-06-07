from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any

from examples.real_task_benchmark_manifest import (
    ProbeFn,
    RealTaskBenchmarkManifest,
    RealTaskBenchmarkManifestCertificate,
    RealTaskBenchmarkPreflightReport,
    RealTaskBenchmarkSpec,
    RealTaskPreflightRow,
    build_real_task_benchmark_manifest,
    build_real_task_manifest_certificate,
    build_real_task_preflight_report,
    preflight_runtime_requirement_evidence_hashes,
    preflight_task_asset_content_hashes,
    real_task_preflight_report_hash,
    runtime_requirement_count,
    validate_real_task_manifest,
    validate_real_task_manifest_certificate,
    validate_real_task_preflight_report,
)
from trwm.core import stable_hash


REAL_TASK_EXECUTION_PLAN_REPORT_SCHEMA = "trwm.real_task_execution_plan_report.v1"
REAL_TASK_EXECUTION_PLAN_CERTIFICATE_SCHEMA = "trwm.real_task_execution_plan_certificate.v1"
REAL_TASK_PREFLIGHT_COMMAND = "python3 -m examples.real_task_benchmark_manifest"
REAL_TASK_SUITE_COMMAND = "python3 -m examples.real_task_benchmark_suite"
REAL_TASK_BUNDLE_COMMAND = "python3 -m examples.real_task_evidence_bundle"
ADAPTER_MODULE_BY_DOMAIN = {
    "robotics": "examples.robotics_motion_benchmark_adapter",
    "hardware": "examples.hardware_riscv_formal_adapter",
    "program": "examples.program_defects4j_adapter",
    "quantum": "examples.quantum_mqt_bench_adapter",
}


@dataclass(frozen=True)
class RealTaskExecutionPlanRow:
    domain: str
    benchmark_id: str
    adapter_module: str
    adapter_command: str
    hard_verifier: str
    train_task_ids: tuple[str, ...]
    held_out_task_ids: tuple[str, ...]
    required_tools: tuple[str, ...]
    required_python_modules: tuple[str, ...]
    required_env_vars: tuple[str, ...]
    required_task_assets: tuple[str, ...]
    command_templates: tuple[str, ...]
    preflight_probe_hashes: tuple[str, ...]
    runtime_requirement_evidence_hashes: tuple[str, ...]
    task_asset_content_hashes: tuple[str, ...]
    runtime_requirement_count: int
    task_asset_count: int
    ready: bool
    missing_requirements: tuple[str, ...]
    source_urls: tuple[str, ...]
    row_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "train_task_ids", tuple(self.train_task_ids))
        object.__setattr__(self, "held_out_task_ids", tuple(self.held_out_task_ids))
        object.__setattr__(self, "required_tools", tuple(self.required_tools))
        object.__setattr__(self, "required_python_modules", tuple(self.required_python_modules))
        object.__setattr__(self, "required_env_vars", tuple(self.required_env_vars))
        object.__setattr__(self, "required_task_assets", tuple(self.required_task_assets))
        object.__setattr__(self, "command_templates", tuple(self.command_templates))
        object.__setattr__(self, "preflight_probe_hashes", tuple(self.preflight_probe_hashes))
        object.__setattr__(self, "runtime_requirement_evidence_hashes", tuple(self.runtime_requirement_evidence_hashes))
        object.__setattr__(self, "task_asset_content_hashes", tuple(self.task_asset_content_hashes))
        object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        object.__setattr__(self, "source_urls", tuple(self.source_urls))
        if not self.row_hash:
            object.__setattr__(self, "row_hash", real_task_execution_plan_row_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("row_hash", None)
        return data


@dataclass(frozen=True)
class RealTaskExecutionPlanReport:
    schema_version: str
    experiment_id: str
    manifest_hash: str
    preflight_report_hash: str
    manifest_certificate_hash: str
    domain_count: int
    ready_domain_count: int
    ready_to_run_all: bool
    rows: tuple[RealTaskExecutionPlanRow, ...]
    preflight_command: str
    adapter_commands: tuple[str, ...]
    suite_command: str
    bundle_command: str
    command_sequence: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    source_urls: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != REAL_TASK_EXECUTION_PLAN_REPORT_SCHEMA:
            raise ValueError(f"invalid real-task execution plan report schema: {self.schema_version}")
        object.__setattr__(self, "rows", tuple(self.rows))
        object.__setattr__(self, "adapter_commands", tuple(self.adapter_commands))
        object.__setattr__(self, "command_sequence", tuple(self.command_sequence))
        object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        object.__setattr__(self, "source_urls", tuple(self.source_urls))


@dataclass(frozen=True)
class RealTaskExecutionPlanCertificate:
    schema_version: str
    experiment_id: str
    manifest_hash: str
    preflight_report_hash: str
    manifest_certificate_hash: str
    plan_report_hash: str
    domain_count: int
    domains: tuple[str, ...]
    row_hashes: tuple[str, ...]
    adapter_modules: tuple[str, ...]
    adapter_commands: tuple[str, ...]
    preflight_command: str
    suite_command: str
    bundle_command: str
    command_sequence_hash: str
    all_rows_match_manifest: bool
    all_rows_match_preflight: bool
    all_adapter_commands_bound: bool
    all_sources_bound: bool
    ready_to_run_all: bool
    missing_requirements: tuple[str, ...]
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REAL_TASK_EXECUTION_PLAN_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid real-task execution plan certificate schema: {self.schema_version}")
        object.__setattr__(self, "domains", tuple(self.domains))
        object.__setattr__(self, "row_hashes", tuple(self.row_hashes))
        object.__setattr__(self, "adapter_modules", tuple(self.adapter_modules))
        object.__setattr__(self, "adapter_commands", tuple(self.adapter_commands))
        object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", real_task_execution_plan_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class RealTaskExecutionPlanResult:
    manifest: RealTaskBenchmarkManifest
    preflight_report: RealTaskBenchmarkPreflightReport
    manifest_certificate: RealTaskBenchmarkManifestCertificate
    plan_report: RealTaskExecutionPlanReport
    plan_certificate: RealTaskExecutionPlanCertificate


def run_real_task_execution_plan(probe: ProbeFn | None = None) -> RealTaskExecutionPlanResult:
    manifest = build_real_task_benchmark_manifest()
    preflight_report = build_real_task_preflight_report(manifest, probe=probe)
    manifest_certificate = build_real_task_manifest_certificate(manifest, preflight_report)
    plan_report = build_real_task_execution_plan_report(manifest, preflight_report, manifest_certificate)
    plan_certificate = build_real_task_execution_plan_certificate(plan_report, manifest, preflight_report, manifest_certificate)
    return RealTaskExecutionPlanResult(
        manifest=manifest,
        preflight_report=preflight_report,
        manifest_certificate=manifest_certificate,
        plan_report=plan_report,
        plan_certificate=plan_certificate,
    )


def build_real_task_execution_plan_report(
    manifest: RealTaskBenchmarkManifest,
    preflight_report: RealTaskBenchmarkPreflightReport,
    manifest_certificate: RealTaskBenchmarkManifestCertificate,
) -> RealTaskExecutionPlanReport:
    rows = tuple(
        _plan_row(spec, preflight_row)
        for spec, preflight_row in zip(manifest.specs, preflight_report.rows)
    )
    adapter_commands = tuple(row.adapter_command for row in rows)
    command_sequence = (REAL_TASK_PREFLIGHT_COMMAND, *adapter_commands, REAL_TASK_SUITE_COMMAND, REAL_TASK_BUNDLE_COMMAND)
    return RealTaskExecutionPlanReport(
        schema_version=REAL_TASK_EXECUTION_PLAN_REPORT_SCHEMA,
        experiment_id="receipt_trained_reversible_real_task_execution_plan",
        manifest_hash=manifest.manifest_hash,
        preflight_report_hash=real_task_preflight_report_hash(preflight_report),
        manifest_certificate_hash=manifest_certificate.certificate_hash,
        domain_count=len(rows),
        ready_domain_count=sum(1 for row in rows if row.ready),
        ready_to_run_all=preflight_report.ready_to_run_all,
        rows=rows,
        preflight_command=REAL_TASK_PREFLIGHT_COMMAND,
        adapter_commands=adapter_commands,
        suite_command=REAL_TASK_SUITE_COMMAND,
        bundle_command=REAL_TASK_BUNDLE_COMMAND,
        command_sequence=command_sequence,
        missing_requirements=preflight_report.missing_requirements,
        source_urls=manifest.source_urls,
    )


def build_real_task_execution_plan_certificate(
    report: RealTaskExecutionPlanReport,
    manifest: RealTaskBenchmarkManifest,
    preflight_report: RealTaskBenchmarkPreflightReport,
    manifest_certificate: RealTaskBenchmarkManifestCertificate,
) -> RealTaskExecutionPlanCertificate:
    return RealTaskExecutionPlanCertificate(
        schema_version=REAL_TASK_EXECUTION_PLAN_CERTIFICATE_SCHEMA,
        experiment_id=report.experiment_id,
        manifest_hash=manifest.manifest_hash,
        preflight_report_hash=real_task_preflight_report_hash(preflight_report),
        manifest_certificate_hash=manifest_certificate.certificate_hash,
        plan_report_hash=real_task_execution_plan_report_hash(report),
        domain_count=report.domain_count,
        domains=tuple(row.domain for row in report.rows),
        row_hashes=tuple(row.row_hash for row in report.rows),
        adapter_modules=tuple(row.adapter_module for row in report.rows),
        adapter_commands=report.adapter_commands,
        preflight_command=report.preflight_command,
        suite_command=report.suite_command,
        bundle_command=report.bundle_command,
        command_sequence_hash=stable_hash(report.command_sequence),
        all_rows_match_manifest=all(_row_matches_manifest(row, spec) for row, spec in zip(report.rows, manifest.specs)),
        all_rows_match_preflight=all(_row_matches_preflight(row, preflight_row) for row, preflight_row in zip(report.rows, preflight_report.rows)),
        all_adapter_commands_bound=all(
            row.adapter_command == f"python3 -m {row.adapter_module}"
            and row.adapter_module == ADAPTER_MODULE_BY_DOMAIN.get(row.domain, "")
            for row in report.rows
        ),
        all_sources_bound=all(set(row.source_urls).issubset(set(manifest.source_urls)) and row.source_urls for row in report.rows),
        ready_to_run_all=report.ready_to_run_all,
        missing_requirements=report.missing_requirements,
        claim_boundary=(
            "Execution plan only. A valid plan binds commands, requirements, task assets, and "
            "preflight evidence for collecting real receipts, but it cannot support the final "
            "performance claim without a supported real-task evidence bundle."
        ),
    )


def validate_real_task_execution_plan(
    result: RealTaskExecutionPlanResult,
) -> bool:
    try:
        manifest = result.manifest
        preflight_report = result.preflight_report
        manifest_certificate = result.manifest_certificate
        report = result.plan_report
        certificate = result.plan_certificate
        if not validate_real_task_manifest(manifest):
            return False
        if not validate_real_task_preflight_report(preflight_report, manifest):
            return False
        if not validate_real_task_manifest_certificate(manifest_certificate, manifest, preflight_report):
            return False
        if not validate_real_task_execution_plan_report(report, manifest, preflight_report, manifest_certificate):
            return False
        if not validate_real_task_execution_plan_certificate(certificate, report, manifest, preflight_report, manifest_certificate):
            return False
        expected_report = build_real_task_execution_plan_report(manifest, preflight_report, manifest_certificate)
        expected_certificate = build_real_task_execution_plan_certificate(expected_report, manifest, preflight_report, manifest_certificate)
        return (
            real_task_execution_plan_report_hash(report) == real_task_execution_plan_report_hash(expected_report)
            and certificate.without_hash() == expected_certificate.without_hash()
            and certificate.certificate_hash == expected_certificate.certificate_hash
        )
    except Exception:
        return False


def validate_real_task_execution_plan_report(
    report: RealTaskExecutionPlanReport,
    manifest: RealTaskBenchmarkManifest | None = None,
    preflight_report: RealTaskBenchmarkPreflightReport | None = None,
    manifest_certificate: RealTaskBenchmarkManifestCertificate | None = None,
) -> bool:
    try:
        if report.schema_version != REAL_TASK_EXECUTION_PLAN_REPORT_SCHEMA:
            return False
        if report.experiment_id != "receipt_trained_reversible_real_task_execution_plan":
            return False
        if report.domain_count != len(report.rows) or report.domain_count != 4:
            return False
        if report.ready_domain_count != sum(1 for row in report.rows if row.ready):
            return False
        if report.ready_to_run_all != (report.ready_domain_count == report.domain_count):
            return False
        if tuple(row.adapter_command for row in report.rows) != report.adapter_commands:
            return False
        if report.preflight_command != REAL_TASK_PREFLIGHT_COMMAND:
            return False
        if report.suite_command != REAL_TASK_SUITE_COMMAND:
            return False
        if report.bundle_command != REAL_TASK_BUNDLE_COMMAND:
            return False
        if report.command_sequence != (report.preflight_command, *report.adapter_commands, report.suite_command, report.bundle_command):
            return False
        if report.missing_requirements != tuple(missing for row in report.rows for missing in row.missing_requirements):
            return False
        if not report.source_urls:
            return False
        for row in report.rows:
            if not _validate_row_shape(row):
                return False
        if manifest is not None:
            if report.manifest_hash != manifest.manifest_hash:
                return False
            if tuple(row.domain for row in report.rows) != manifest.domains:
                return False
            if report.source_urls != manifest.source_urls:
                return False
            for row, spec in zip(report.rows, manifest.specs):
                if not _row_matches_manifest(row, spec):
                    return False
        if preflight_report is not None:
            if report.preflight_report_hash != real_task_preflight_report_hash(preflight_report):
                return False
            if report.ready_to_run_all != preflight_report.ready_to_run_all:
                return False
            if report.missing_requirements != preflight_report.missing_requirements:
                return False
            for row, preflight_row in zip(report.rows, preflight_report.rows):
                if not _row_matches_preflight(row, preflight_row):
                    return False
        if manifest_certificate is not None and report.manifest_certificate_hash != manifest_certificate.certificate_hash:
            return False
        return True
    except Exception:
        return False


def validate_real_task_execution_plan_certificate(
    certificate: RealTaskExecutionPlanCertificate,
    report: RealTaskExecutionPlanReport,
    manifest: RealTaskBenchmarkManifest,
    preflight_report: RealTaskBenchmarkPreflightReport,
    manifest_certificate: RealTaskBenchmarkManifestCertificate,
) -> bool:
    try:
        if certificate.schema_version != REAL_TASK_EXECUTION_PLAN_CERTIFICATE_SCHEMA:
            return False
        if certificate.experiment_id != report.experiment_id:
            return False
        if certificate.manifest_hash != manifest.manifest_hash:
            return False
        if certificate.preflight_report_hash != real_task_preflight_report_hash(preflight_report):
            return False
        if certificate.manifest_certificate_hash != manifest_certificate.certificate_hash:
            return False
        if certificate.plan_report_hash != real_task_execution_plan_report_hash(report):
            return False
        if certificate.domain_count != 4 or certificate.domain_count != report.domain_count:
            return False
        if certificate.domains != tuple(row.domain for row in report.rows):
            return False
        if certificate.row_hashes != tuple(row.row_hash for row in report.rows):
            return False
        if certificate.adapter_modules != tuple(row.adapter_module for row in report.rows):
            return False
        if certificate.adapter_commands != report.adapter_commands:
            return False
        if certificate.preflight_command != report.preflight_command:
            return False
        if certificate.suite_command != report.suite_command:
            return False
        if certificate.bundle_command != report.bundle_command:
            return False
        if certificate.command_sequence_hash != stable_hash(report.command_sequence):
            return False
        if certificate.ready_to_run_all != report.ready_to_run_all:
            return False
        if certificate.missing_requirements != report.missing_requirements:
            return False
        if not certificate.claim_boundary:
            return False
        expected_flags = {
            "all_rows_match_manifest": all(_row_matches_manifest(row, spec) for row, spec in zip(report.rows, manifest.specs)),
            "all_rows_match_preflight": all(_row_matches_preflight(row, preflight_row) for row, preflight_row in zip(report.rows, preflight_report.rows)),
            "all_adapter_commands_bound": all(
                row.adapter_command == f"python3 -m {row.adapter_module}"
                and row.adapter_module == ADAPTER_MODULE_BY_DOMAIN.get(row.domain, "")
                for row in report.rows
            ),
            "all_sources_bound": all(set(row.source_urls).issubset(set(manifest.source_urls)) and row.source_urls for row in report.rows),
        }
        for key, expected in expected_flags.items():
            value = getattr(certificate, key)
            if not isinstance(value, bool) or value != expected:
                return False
        if certificate.ready_to_run_all and certificate.missing_requirements:
            return False
        return certificate.certificate_hash == real_task_execution_plan_certificate_hash(certificate)
    except Exception:
        return False


def real_task_execution_plan_row_hash(row: RealTaskExecutionPlanRow) -> str:
    return stable_hash(row.without_hash())


def real_task_execution_plan_report_hash(report: RealTaskExecutionPlanReport) -> str:
    return stable_hash(asdict(report))


def real_task_execution_plan_certificate_hash(certificate: RealTaskExecutionPlanCertificate) -> str:
    return stable_hash(certificate.without_hash())


def result_as_dict(result: RealTaskExecutionPlanResult) -> dict[str, Any]:
    return asdict(result)


def _plan_row(spec: RealTaskBenchmarkSpec, preflight_row: RealTaskPreflightRow) -> RealTaskExecutionPlanRow:
    adapter_module = ADAPTER_MODULE_BY_DOMAIN[spec.domain]
    return RealTaskExecutionPlanRow(
        domain=spec.domain,
        benchmark_id=spec.benchmark_id,
        adapter_module=adapter_module,
        adapter_command=f"python3 -m {adapter_module}",
        hard_verifier=spec.hard_verifier,
        train_task_ids=spec.train_task_ids,
        held_out_task_ids=spec.held_out_task_ids,
        required_tools=spec.required_tools,
        required_python_modules=spec.required_python_modules,
        required_env_vars=spec.required_env_vars,
        required_task_assets=spec.required_task_assets,
        command_templates=spec.command_templates,
        preflight_probe_hashes=tuple(probe.evidence_hash for probe in preflight_row.probes),
        runtime_requirement_evidence_hashes=preflight_runtime_requirement_evidence_hashes(preflight_row),
        task_asset_content_hashes=preflight_task_asset_content_hashes(preflight_row),
        runtime_requirement_count=runtime_requirement_count(spec),
        task_asset_count=len(spec.required_task_assets),
        ready=preflight_row.ready,
        missing_requirements=preflight_row.missing_requirements,
        source_urls=spec.source_urls,
    )


def _row_matches_manifest(row: RealTaskExecutionPlanRow, spec: RealTaskBenchmarkSpec) -> bool:
    return (
        row.domain == spec.domain
        and row.benchmark_id == spec.benchmark_id
        and row.adapter_module == ADAPTER_MODULE_BY_DOMAIN.get(spec.domain, "")
        and row.adapter_command == f"python3 -m {row.adapter_module}"
        and row.hard_verifier == spec.hard_verifier
        and row.train_task_ids == spec.train_task_ids
        and row.held_out_task_ids == spec.held_out_task_ids
        and row.required_tools == spec.required_tools
        and row.required_python_modules == spec.required_python_modules
        and row.required_env_vars == spec.required_env_vars
        and row.required_task_assets == spec.required_task_assets
        and row.command_templates == spec.command_templates
        and row.runtime_requirement_count == runtime_requirement_count(spec)
        and row.task_asset_count == len(spec.required_task_assets)
        and row.source_urls == spec.source_urls
    )


def _row_matches_preflight(row: RealTaskExecutionPlanRow, preflight_row: RealTaskPreflightRow) -> bool:
    return (
        row.domain == preflight_row.domain
        and row.benchmark_id == preflight_row.benchmark_id
        and row.hard_verifier == preflight_row.hard_verifier
        and row.train_task_ids == preflight_row.train_task_ids
        and row.held_out_task_ids == preflight_row.held_out_task_ids
        and row.preflight_probe_hashes == tuple(probe.evidence_hash for probe in preflight_row.probes)
        and row.runtime_requirement_evidence_hashes == preflight_runtime_requirement_evidence_hashes(preflight_row)
        and row.task_asset_content_hashes == preflight_task_asset_content_hashes(preflight_row)
        and row.ready == preflight_row.ready
        and row.missing_requirements == preflight_row.missing_requirements
        and row.source_urls == preflight_row.source_urls
    )


def _validate_row_shape(row: RealTaskExecutionPlanRow) -> bool:
    if row.domain not in ADAPTER_MODULE_BY_DOMAIN:
        return False
    if not row.benchmark_id or not row.adapter_module or not row.adapter_command:
        return False
    if row.adapter_command != f"python3 -m {row.adapter_module}":
        return False
    if not row.hard_verifier:
        return False
    if not row.train_task_ids or not row.held_out_task_ids:
        return False
    if set(row.train_task_ids).intersection(row.held_out_task_ids):
        return False
    if row.runtime_requirement_count != len(row.required_tools) + len(row.required_python_modules) + len(row.required_env_vars):
        return False
    if row.task_asset_count != len(row.required_task_assets):
        return False
    if len(row.runtime_requirement_evidence_hashes) > row.runtime_requirement_count:
        return False
    if len(row.task_asset_content_hashes) > row.task_asset_count:
        return False
    hash_groups = (
        row.preflight_probe_hashes,
        row.runtime_requirement_evidence_hashes,
        row.task_asset_content_hashes,
        (row.row_hash,),
    )
    if any(not _hash_tuple(group) for group in hash_groups):
        return False
    if not isinstance(row.ready, bool):
        return False
    if row.ready and row.missing_requirements:
        return False
    if not row.command_templates or not row.source_urls:
        return False
    return row.row_hash == real_task_execution_plan_row_hash(row)


def _hash_tuple(values: tuple[str, ...]) -> bool:
    return all(_is_hash(value) for value in values)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def main() -> None:
    print(json.dumps(result_as_dict(run_real_task_execution_plan()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
