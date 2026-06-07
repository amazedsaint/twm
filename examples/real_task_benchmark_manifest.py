from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Mapping

from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import stable_hash


REAL_TASK_MANIFEST_SCHEMA = "trwm.real_task_benchmark_manifest.v1"
REAL_TASK_PREFLIGHT_REPORT_SCHEMA = "trwm.real_task_benchmark_preflight_report.v1"
REAL_TASK_MANIFEST_CERTIFICATE_SCHEMA = "trwm.real_task_benchmark_manifest_certificate.v1"


@dataclass(frozen=True)
class RealTaskBenchmarkSpec:
    domain: str
    benchmark_id: str
    task_selector: str
    train_split_id: str
    held_out_split_id: str
    hard_verifier: str
    required_tools: tuple[str, ...]
    required_python_modules: tuple[str, ...]
    required_env_vars: tuple[str, ...]
    required_task_assets: tuple[str, ...]
    command_templates: tuple[str, ...]
    source_urls: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_tools", tuple(self.required_tools))
        object.__setattr__(self, "required_python_modules", tuple(self.required_python_modules))
        object.__setattr__(self, "required_env_vars", tuple(self.required_env_vars))
        object.__setattr__(self, "required_task_assets", tuple(self.required_task_assets))
        object.__setattr__(self, "command_templates", tuple(self.command_templates))
        object.__setattr__(self, "source_urls", tuple(self.source_urls))

    @property
    def spec_hash(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class RealTaskBenchmarkManifest:
    schema_version: str
    experiment_id: str
    objective: str
    specs: tuple[RealTaskBenchmarkSpec, ...]
    manifest_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REAL_TASK_MANIFEST_SCHEMA:
            raise ValueError(f"invalid real-task manifest schema: {self.schema_version}")
        object.__setattr__(self, "specs", tuple(self.specs))
        if not self.manifest_hash:
            object.__setattr__(self, "manifest_hash", real_task_manifest_hash(self))

    @property
    def domains(self) -> tuple[str, ...]:
        return tuple(spec.domain for spec in self.specs)

    @property
    def source_urls(self) -> tuple[str, ...]:
        return tuple(sorted({source for spec in self.specs for source in spec.source_urls}))

    def without_hash(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("manifest_hash", None)
        return data


@dataclass(frozen=True)
class RequirementProbe:
    kind: str
    name: str
    available: bool
    evidence: str
    evidence_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", str(self.kind))
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "available", bool(self.available))
        object.__setattr__(self, "evidence", str(self.evidence))
        if not self.evidence_hash:
            object.__setattr__(self, "evidence_hash", _probe_evidence_hash(self.kind, self.name, self.available, self.evidence))


@dataclass(frozen=True)
class RealTaskPreflightRow:
    domain: str
    benchmark_id: str
    task_selector: str
    train_split_id: str
    held_out_split_id: str
    hard_verifier: str
    probes: tuple[RequirementProbe, ...]
    ready: bool
    missing_requirements: tuple[str, ...]
    source_urls: tuple[str, ...]


@dataclass(frozen=True)
class RealTaskBenchmarkPreflightReport:
    schema_version: str
    experiment_id: str
    manifest_hash: str
    domain_count: int
    ready_domain_count: int
    ready_to_run_all: bool
    rows: tuple[RealTaskPreflightRow, ...]
    missing_requirements: tuple[str, ...]


@dataclass(frozen=True)
class RealTaskBenchmarkManifestCertificate:
    schema_version: str
    experiment_id: str
    manifest_hash: str
    preflight_report_hash: str
    domain_count: int
    domains: tuple[str, ...]
    spec_hashes: tuple[str, ...]
    all_sources_present: bool
    ready_to_run_all: bool
    missing_requirements: tuple[str, ...]
    claim_boundary: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REAL_TASK_MANIFEST_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid real-task manifest certificate schema: {self.schema_version}")
        object.__setattr__(self, "domains", tuple(self.domains))
        object.__setattr__(self, "spec_hashes", tuple(self.spec_hashes))
        object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", real_task_manifest_certificate_hash(self))

    def without_hash(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class RealTaskBenchmarkReadinessResult:
    manifest: RealTaskBenchmarkManifest
    preflight_report: RealTaskBenchmarkPreflightReport
    manifest_certificate: RealTaskBenchmarkManifestCertificate
    claim_certificate: ClaimCertificate


ProbeFn = Callable[[str, str], RequirementProbe]


def build_real_task_benchmark_manifest() -> RealTaskBenchmarkManifest:
    return RealTaskBenchmarkManifest(
        schema_version=REAL_TASK_MANIFEST_SCHEMA,
        experiment_id="receipt_trained_reversible_real_task_manifest",
        objective=(
            "Run receipt-trained reversible proposer evaluations on held-out robotics, hardware, "
            "program, and quantum benchmarks with hard-verifier calls and zero-invalid-commit checks."
        ),
        specs=(
            RealTaskBenchmarkSpec(
                domain="robotics",
                benchmark_id="motion_bench_maker_ompl",
                task_selector="prefabricated manipulation datasets; train on generated source scenes, hold out distinct problem sets",
                train_split_id="motion-benchmark.train.motionbenchmaker-scenes",
                held_out_split_id="motion-benchmark.heldout.motionbenchmaker-scenes",
                hard_verifier="MoveIt/OMPL benchmark solved/correct-solution/clearance result",
                required_tools=("roslaunch",),
                required_python_modules=(),
                required_env_vars=("TRWM_MOTION_BENCHMARK_TASK_ROOT",),
                required_task_assets=(
                    "file:$TRWM_MOTION_BENCHMARK_TASK_ROOT/train-kitchen-pick/unsafe_motion_candidate/command.json",
                    "file:$TRWM_MOTION_BENCHMARK_TASK_ROOT/train-kitchen-pick/safe_motion_candidate/command.json",
                    "file:$TRWM_MOTION_BENCHMARK_TASK_ROOT/heldout-shelf-place/unsafe_motion_candidate/command.json",
                    "file:$TRWM_MOTION_BENCHMARK_TASK_ROOT/heldout-shelf-place/safe_motion_candidate/command.json",
                    "file:$TRWM_MOTION_BENCHMARK_TASK_ROOT/heldout-cabinet-reach/unsafe_motion_candidate/command.json",
                    "file:$TRWM_MOTION_BENCHMARK_TASK_ROOT/heldout-cabinet-reach/safe_motion_candidate/command.json",
                ),
                command_templates=(
                    "cd $TRWM_MOTION_BENCHMARK_TASK_ROOT/<task>/<candidate>",
                    "roslaunch <launch_package> <launch_file> <candidate_args>",
                    "read benchmark_result.json and require solved=true, correct_solution=true, approximate_solution=false, solution_clearance>=0",
                ),
                source_urls=(
                    "https://carlosquinterop.github.io/project/motionbenchmaker/",
                    "https://github.com/KavrakiLab/motion_bench_maker",
                    "https://moveit.picknik.ai/main/doc/concepts/motion_planning.html",
                    "https://docs.ros.org/en/indigo/api/moveit_tutorials/html/doc/benchmarking_tutorial.html",
                    "https://docs.ros.org/en/rolling/p/ompl/doc/markdown/benchmark.html",
                ),
                claim_boundary=(
                    "Readiness only; not robotics safety evidence until task-root-backed "
                    "MotionBenchMaker/MoveIt/OMPL receipts are produced."
                ),
            ),
            RealTaskBenchmarkSpec(
                domain="hardware",
                benchmark_id="riscv_formal_rvfi",
                task_selector="RVFI instruction checks for open RISC-V cores; train and hold out by instruction/check family",
                train_split_id="riscv-formal.train.rv32i.instruction-checks",
                held_out_split_id="riscv-formal.heldout.rv32i.branch-load-store-checks",
                hard_verifier="riscv-formal generated checks executed through SymbiYosys/Yosys",
                required_tools=("sby", "yosys", "make", "python3"),
                required_python_modules=(),
                required_env_vars=("TRWM_RISCV_FORMAL_TASK_ROOT",),
                required_task_assets=(
                    "file:$TRWM_RISCV_FORMAL_TASK_ROOT/checks/genchecks.py",
                    "dir:$TRWM_RISCV_FORMAL_TASK_ROOT/train-rv32i-add/rvfi_violating_candidate",
                    "dir:$TRWM_RISCV_FORMAL_TASK_ROOT/train-rv32i-add/rvfi_compliant_candidate",
                    "dir:$TRWM_RISCV_FORMAL_TASK_ROOT/heldout-rv32i-branch/rvfi_violating_candidate",
                    "dir:$TRWM_RISCV_FORMAL_TASK_ROOT/heldout-rv32i-branch/rvfi_compliant_candidate",
                    "dir:$TRWM_RISCV_FORMAL_TASK_ROOT/heldout-rv32i-load-store/rvfi_violating_candidate",
                    "dir:$TRWM_RISCV_FORMAL_TASK_ROOT/heldout-rv32i-load-store/rvfi_compliant_candidate",
                ),
                command_templates=(
                    "cd $TRWM_RISCV_FORMAL_TASK_ROOT/<task>/<candidate>",
                    "python3 ../../checks/genchecks.py",
                    "make -C checks j1",
                ),
                source_urls=(
                    "https://github.com/YosysHQ/riscv-formal",
                    "https://yosyshq.readthedocs.io/projects/riscv-formal/en/latest/procedure.html",
                    "https://yosyshq.readthedocs.io/projects/riscv-formal/en/latest/rvfi.html",
                ),
                claim_boundary=(
                    "Readiness only; not RISC-V core correctness evidence until task-root-backed "
                    "formal-check receipts are produced."
                ),
            ),
            RealTaskBenchmarkSpec(
                domain="program",
                benchmark_id="defects4j_repair",
                task_selector="Defects4J active bugs; train and hold out by project/bug id with triggering and relevant tests",
                train_split_id="defects4j.train.active-bug-ids",
                held_out_split_id="defects4j.heldout.active-bug-ids",
                hard_verifier="defects4j compile plus triggering/relevant test execution",
                required_tools=("defects4j", "java", "git", "svn", "perl"),
                required_python_modules=(),
                required_env_vars=(),
                required_task_assets=(),
                command_templates=(
                    "defects4j checkout -p <project> -v <bug_id>b -w <buggy_workdir>",
                    "defects4j checkout -p <project> -v <bug_id>f -w <fixed_workdir>",
                    "defects4j compile",
                    "defects4j test -r",
                ),
                source_urls=(
                    "https://github.com/rjust/defects4j",
                    "https://defects4j.org/",
                    "https://defects4j.org/html_doc/defects4j.html",
                    "https://defects4j.org/html_doc/d4j/d4j-checkout.html",
                    "https://defects4j.org/html_doc/d4j/d4j-test.html",
                ),
                claim_boundary=(
                    "Readiness only; fixed-version candidate receipts are not program-repair effectiveness "
                    "evidence until patch-generation and patch-minimization receipts are produced."
                ),
            ),
            RealTaskBenchmarkSpec(
                domain="quantum",
                benchmark_id="mqt_bench_qcec_revlib",
                task_selector="MQT Bench generated circuits and RevLib reversible circuits; hold out by algorithm/circuit family",
                train_split_id="mqt-bench.train.algorithms-and-revlib-families",
                held_out_split_id="mqt-bench.heldout.qft-ghz-revlib-families",
                hard_verifier="MQT QCEC equivalence checking against original/generated circuit",
                required_tools=(),
                required_python_modules=("mqt.bench", "mqt.qcec"),
                required_env_vars=(),
                required_task_assets=(),
                command_templates=(
                    "python -m mqt.bench --benchmark <name> --level alg --output-format qasm3",
                    "python -m mqt.qcec <original.qasm> <candidate.qasm>",
                ),
                source_urls=(
                    "https://github.com/munich-quantum-toolkit/bench",
                    "https://mqt.readthedocs.io/projects/bench/en/latest/usage.html",
                    "https://mqt.readthedocs.io/projects/qcec/en/stable/",
                    "https://mqt.readthedocs.io/projects/qcec/en/v3.3.0/api/mqt/qcec/verify/index.html",
                    "https://www.revlib.org/",
                ),
                claim_boundary="Readiness only; not quantum compiler/equivalence evidence until QCEC receipts are produced.",
            ),
        ),
    )


def run_real_task_benchmark_readiness(probe: ProbeFn | None = None) -> RealTaskBenchmarkReadinessResult:
    manifest = build_real_task_benchmark_manifest()
    report = build_real_task_preflight_report(manifest, probe=probe)
    certificate = build_real_task_manifest_certificate(manifest, report)
    claim = certify_claim(
        claim_id="receipt_trained_reversible_real_task_readiness",
        claim_text=(
            "The real robotics, hardware, program, and quantum benchmark adapters are ready "
            "to run held-out receipt-trained reversible proposer evaluations."
        ),
        evidence_grade="G0",
        scope="real_task_benchmark_readiness",
        requirements=(
            requirement("manifest_valid", validate_real_task_manifest(manifest)),
            requirement("preflight_report_valid", validate_real_task_preflight_report(report, manifest)),
            requirement("certificate_valid", validate_real_task_manifest_certificate(certificate, manifest, report)),
            requirement("exactly_four_domains", report.domain_count == 4 and set(manifest.domains) == {"robotics", "hardware", "program", "quantum"}),
            requirement("sources_present", certificate.all_sources_present),
            requirement("all_external_requirements_available", report.ready_to_run_all, missing=report.missing_requirements),
        ),
        metrics={
            "domain_count": report.domain_count,
            "ready_domain_count": report.ready_domain_count,
            "missing_requirement_count": len(report.missing_requirements),
        },
        boundary=(
            "Readiness gate only. A supported readiness claim is not a performance claim; the final "
            "objective still requires real benchmark receipts, held-out call-reduction metrics, and "
            "zero invalid commits."
        ),
        sources=manifest.source_urls,
    )
    return RealTaskBenchmarkReadinessResult(
        manifest=manifest,
        preflight_report=report,
        manifest_certificate=certificate,
        claim_certificate=claim,
    )


def build_real_task_preflight_report(
    manifest: RealTaskBenchmarkManifest,
    *,
    probe: ProbeFn | None = None,
) -> RealTaskBenchmarkPreflightReport:
    probe_fn = probe or _default_probe
    rows: list[RealTaskPreflightRow] = []
    missing: list[str] = []
    for spec in manifest.specs:
        tool_probes = tuple(probe_fn("tool", tool) for tool in spec.required_tools)
        module_probes = tuple(probe_fn("python_module", module) for module in spec.required_python_modules)
        env_probes = tuple(probe_fn("env_var", env_var) for env_var in spec.required_env_vars)
        asset_probes = (
            tuple(probe_fn("task_asset", asset) for asset in spec.required_task_assets)
            if all(probe.available for probe in env_probes)
            else ()
        )
        probes = tool_probes + module_probes + env_probes + asset_probes
        row_missing = tuple(f"{spec.domain}:{probe.kind}:{probe.name}" for probe in probes if not probe.available)
        missing.extend(row_missing)
        rows.append(
            RealTaskPreflightRow(
                domain=spec.domain,
                benchmark_id=spec.benchmark_id,
                task_selector=spec.task_selector,
                train_split_id=spec.train_split_id,
                held_out_split_id=spec.held_out_split_id,
                hard_verifier=spec.hard_verifier,
                probes=probes,
                ready=not row_missing,
                missing_requirements=row_missing,
                source_urls=spec.source_urls,
            )
        )
    ready_count = sum(1 for row in rows if row.ready)
    return RealTaskBenchmarkPreflightReport(
        schema_version=REAL_TASK_PREFLIGHT_REPORT_SCHEMA,
        experiment_id=manifest.experiment_id,
        manifest_hash=manifest.manifest_hash,
        domain_count=len(rows),
        ready_domain_count=ready_count,
        ready_to_run_all=ready_count == len(rows),
        rows=tuple(rows),
        missing_requirements=tuple(missing),
    )


def build_real_task_manifest_certificate(
    manifest: RealTaskBenchmarkManifest,
    report: RealTaskBenchmarkPreflightReport,
) -> RealTaskBenchmarkManifestCertificate:
    return RealTaskBenchmarkManifestCertificate(
        schema_version=REAL_TASK_MANIFEST_CERTIFICATE_SCHEMA,
        experiment_id=manifest.experiment_id,
        manifest_hash=manifest.manifest_hash,
        preflight_report_hash=real_task_preflight_report_hash(report),
        domain_count=len(manifest.specs),
        domains=manifest.domains,
        spec_hashes=tuple(spec.spec_hash for spec in manifest.specs),
        all_sources_present=all(spec.source_urls for spec in manifest.specs),
        ready_to_run_all=report.ready_to_run_all,
        missing_requirements=report.missing_requirements,
        claim_boundary=(
            "This certificate binds external benchmark adapter readiness only. It cannot support the "
            "receipt-trained proposer performance claim without real benchmark execution receipts."
        ),
    )


def validate_real_task_manifest(manifest: RealTaskBenchmarkManifest) -> bool:
    try:
        if manifest.schema_version != REAL_TASK_MANIFEST_SCHEMA:
            return False
        if not manifest.experiment_id or not manifest.objective:
            return False
        if len(manifest.specs) != 4 or len(set(manifest.domains)) != len(manifest.specs):
            return False
        if set(manifest.domains) != {"robotics", "hardware", "program", "quantum"}:
            return False
        for spec in manifest.specs:
            required_strings = (
                spec.domain,
                spec.benchmark_id,
                spec.task_selector,
                spec.train_split_id,
                spec.held_out_split_id,
                spec.hard_verifier,
                spec.claim_boundary,
            )
            if any(not value for value in required_strings):
                return False
            if spec.train_split_id == spec.held_out_split_id:
                return False
            if not spec.command_templates or not spec.source_urls:
                return False
            if spec.required_env_vars and not spec.required_task_assets:
                return False
            if any(
                not asset.startswith(("file:", "dir:", "exists:"))
                for asset in spec.required_task_assets
            ):
                return False
        return manifest.manifest_hash == real_task_manifest_hash(manifest)
    except Exception:
        return False


def validate_real_task_preflight_report(
    report: RealTaskBenchmarkPreflightReport,
    manifest: RealTaskBenchmarkManifest | None = None,
) -> bool:
    try:
        if report.schema_version != REAL_TASK_PREFLIGHT_REPORT_SCHEMA:
            return False
        if not report.experiment_id or not _is_hash(report.manifest_hash):
            return False
        if report.domain_count != len(report.rows):
            return False
        if report.ready_domain_count != sum(1 for row in report.rows if row.ready):
            return False
        if report.ready_to_run_all != (report.ready_domain_count == report.domain_count):
            return False
        expected_missing: list[str] = []
        for row in report.rows:
            if not row.domain or not row.benchmark_id or not row.task_selector:
                return False
            if not row.train_split_id or not row.held_out_split_id or row.train_split_id == row.held_out_split_id:
                return False
            if not row.hard_verifier or not row.source_urls:
                return False
            row_missing = tuple(f"{row.domain}:{probe.kind}:{probe.name}" for probe in row.probes if not probe.available)
            expected_missing.extend(row_missing)
            if row.ready != (not row_missing):
                return False
            if row.missing_requirements != row_missing:
                return False
            for probe in row.probes:
                if probe.kind not in {"tool", "python_module", "env_var", "task_asset"}:
                    return False
                if not probe.name or not probe.evidence:
                    return False
                if not isinstance(probe.available, bool):
                    return False
                if not _is_hash(probe.evidence_hash) or probe.evidence_hash == "0" * 64:
                    return False
        if report.missing_requirements != tuple(expected_missing):
            return False
        if manifest is not None:
            if not validate_real_task_manifest(manifest):
                return False
            if report.manifest_hash != manifest.manifest_hash:
                return False
            if report.experiment_id != manifest.experiment_id:
                return False
            if report.domain_count != len(manifest.specs):
                return False
            if tuple(row.domain for row in report.rows) != manifest.domains:
                return False
            for row, spec in zip(report.rows, manifest.specs):
                if row.benchmark_id != spec.benchmark_id:
                    return False
                if row.task_selector != spec.task_selector:
                    return False
                if row.train_split_id != spec.train_split_id:
                    return False
                if row.held_out_split_id != spec.held_out_split_id:
                    return False
                if row.hard_verifier != spec.hard_verifier:
                    return False
                if row.source_urls != spec.source_urls:
                    return False
                expected_probe_keys = (
                    *((("tool", value) for value in spec.required_tools)),
                    *((("python_module", value) for value in spec.required_python_modules)),
                    *((("env_var", value) for value in spec.required_env_vars)),
                )
                probe_keys = tuple((probe.kind, probe.name) for probe in row.probes)
                if probe_keys[: len(expected_probe_keys)] != expected_probe_keys:
                    return False
                env_count = len(spec.required_env_vars)
                env_start = len(spec.required_tools) + len(spec.required_python_modules)
                env_probes = row.probes[env_start : env_start + env_count]
                expected_asset_keys = tuple(("task_asset", value) for value in spec.required_task_assets)
                if all(probe.available for probe in env_probes):
                    if probe_keys[len(expected_probe_keys) :] != expected_asset_keys:
                        return False
                elif any(kind == "task_asset" for kind, _ in probe_keys[len(expected_probe_keys) :]):
                    return False
        return True
    except Exception:
        return False


def validate_real_task_manifest_certificate(
    certificate: RealTaskBenchmarkManifestCertificate,
    manifest: RealTaskBenchmarkManifest | None = None,
    report: RealTaskBenchmarkPreflightReport | None = None,
) -> bool:
    try:
        if certificate.schema_version != REAL_TASK_MANIFEST_CERTIFICATE_SCHEMA:
            return False
        if not _is_hash(certificate.manifest_hash) or not _is_hash(certificate.preflight_report_hash):
            return False
        if certificate.domain_count != len(certificate.domains) or certificate.domain_count != len(certificate.spec_hashes):
            return False
        if certificate.domain_count != 4 or set(certificate.domains) != {"robotics", "hardware", "program", "quantum"}:
            return False
        if any(not _is_hash(spec_hash) for spec_hash in certificate.spec_hashes):
            return False
        if not isinstance(certificate.all_sources_present, bool) or not isinstance(certificate.ready_to_run_all, bool):
            return False
        if certificate.ready_to_run_all and certificate.missing_requirements:
            return False
        if not certificate.ready_to_run_all and not certificate.missing_requirements:
            return False
        if not certificate.claim_boundary:
            return False
        if manifest is not None:
            if not validate_real_task_manifest(manifest):
                return False
            if certificate.manifest_hash != manifest.manifest_hash:
                return False
            if certificate.domains != manifest.domains:
                return False
            if certificate.spec_hashes != tuple(spec.spec_hash for spec in manifest.specs):
                return False
        if report is not None:
            if not validate_real_task_preflight_report(report, manifest):
                return False
            if certificate.preflight_report_hash != real_task_preflight_report_hash(report):
                return False
            if certificate.ready_to_run_all != report.ready_to_run_all:
                return False
            if certificate.missing_requirements != report.missing_requirements:
                return False
        return certificate.certificate_hash == real_task_manifest_certificate_hash(certificate)
    except Exception:
        return False


def real_task_manifest_hash(manifest: RealTaskBenchmarkManifest) -> str:
    return stable_hash(manifest.without_hash())


def real_task_preflight_report_hash(report: RealTaskBenchmarkPreflightReport) -> str:
    return stable_hash(asdict(report))


def real_task_manifest_certificate_hash(certificate: RealTaskBenchmarkManifestCertificate) -> str:
    return stable_hash(certificate.without_hash())


def fake_probe(availability: Mapping[tuple[str, str], bool]) -> ProbeFn:
    def _probe(kind: str, name: str) -> RequirementProbe:
        available = bool(availability.get((kind, name), False))
        evidence = "fake_available" if available else "fake_missing"
        return RequirementProbe(
            kind=kind,
            name=name,
            available=available,
            evidence=evidence,
            evidence_hash=_probe_evidence_hash(kind, name, available, evidence),
        )

    return _probe


def _default_probe(kind: str, name: str) -> RequirementProbe:
    if kind == "tool":
        path = shutil.which(name)
        if path is None:
            return _make_probe(kind=kind, name=name, available=False, evidence="missing_on_path")
        version = _tool_version(path)
        return _make_probe(kind=kind, name=name, available=True, evidence=path, extra={"version": version})
    if kind == "python_module":
        try:
            spec = importlib.util.find_spec(name)
        except ModuleNotFoundError:
            spec = None
        origin = getattr(spec, "origin", None) if spec is not None else None
        extra = {"origin": origin or "", "package": name}
        return _make_probe(kind=kind, name=name, available=spec is not None, evidence=origin or "missing_module", extra=extra)
    if kind == "env_var":
        value = os.environ.get(name, "")
        if not value:
            return _make_probe(kind=kind, name=name, available=False, evidence="missing_env_var")
        if name.endswith("TASK_ROOT"):
            path = Path(value)
            if not path.exists():
                return _make_probe(kind=kind, name=name, available=False, evidence=f"missing_path:{value}")
            if not path.is_dir():
                return _make_probe(kind=kind, name=name, available=False, evidence=f"not_directory:{value}")
            return _make_probe(kind=kind, name=name, available=True, evidence=str(path), extra={"realpath": str(path.resolve())})
        return _make_probe(kind=kind, name=name, available=True, evidence="set")
    if kind == "task_asset":
        return _probe_task_asset(name)
    raise ValueError(f"unknown probe kind: {kind}")


def _probe_task_asset(name: str) -> RequirementProbe:
    asset_kind, separator, template = name.partition(":")
    if not separator:
        asset_kind = "exists"
        template = name
    if asset_kind not in {"file", "dir", "exists"}:
        return RequirementProbe(
            kind="task_asset",
            name=name,
            available=False,
            evidence=f"unknown_asset_kind:{asset_kind}",
        )
    expanded = os.path.expandvars(template)
    if "$" in expanded:
        return _make_probe(kind="task_asset", name=name, available=False, evidence=f"unresolved_env:{template}")
    path = Path(expanded)
    if asset_kind == "file":
        if not path.exists():
            return _make_probe(kind="task_asset", name=name, available=False, evidence=f"missing_path:{expanded}")
        return _make_probe(
            kind="task_asset",
            name=name,
            available=path.is_file(),
            evidence=str(path) if path.is_file() else f"not_file:{expanded}",
            extra=_path_fingerprint(path) if path.is_file() else None,
        )
    if asset_kind == "dir":
        if not path.exists():
            return _make_probe(kind="task_asset", name=name, available=False, evidence=f"missing_path:{expanded}")
        return _make_probe(
            kind="task_asset",
            name=name,
            available=path.is_dir(),
            evidence=str(path) if path.is_dir() else f"not_directory:{expanded}",
            extra=_path_fingerprint(path) if path.is_dir() else None,
        )
    return _make_probe(
        kind="task_asset",
        name=name,
        available=path.exists(),
        evidence=str(path) if path.exists() else f"missing_path:{expanded}",
        extra=_path_fingerprint(path) if path.exists() else None,
    )


def _make_probe(
    *,
    kind: str,
    name: str,
    available: bool,
    evidence: str,
    extra: Mapping[str, object] | None = None,
) -> RequirementProbe:
    return RequirementProbe(
        kind=kind,
        name=name,
        available=available,
        evidence=evidence,
        evidence_hash=_probe_evidence_hash(kind, name, available, evidence, extra=extra),
    )


def _probe_evidence_hash(
    kind: str,
    name: str,
    available: bool,
    evidence: str,
    *,
    extra: Mapping[str, object] | None = None,
) -> str:
    return stable_hash(
        {
            "schema_version": "trwm.real_task_requirement_probe_evidence.v1",
            "kind": kind,
            "name": name,
            "available": bool(available),
            "evidence": evidence,
            "extra": dict(extra or {}),
        }
    )


def _tool_version(path: str) -> str:
    for flag in ("--version", "-V", "-version"):
        try:
            completed = subprocess.run(
                (path, flag),
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception:
            continue
        output = f"{completed.stdout}\n{completed.stderr}".strip()
        if output:
            return output[-500:]
    return "version_unavailable"


def _path_fingerprint(path: Path) -> Mapping[str, object]:
    if path.is_file():
        return {
            "kind": "file",
            "path": str(path),
            "size": path.stat().st_size,
            "sha256": _file_sha256(path),
        }
    if path.is_dir():
        entries: list[Mapping[str, object]] = []
        for idx, child in enumerate(sorted(path.rglob("*"), key=lambda item: str(item.relative_to(path)))):
            if idx >= 200:
                entries.append({"truncated_after": 200})
                break
            relative = str(child.relative_to(path))
            if child.is_file():
                entries.append({"path": relative, "kind": "file", "size": child.stat().st_size, "sha256": _file_sha256(child)})
            elif child.is_dir():
                entries.append({"path": relative, "kind": "dir"})
            elif child.is_symlink():
                entries.append({"path": relative, "kind": "symlink", "target": os.readlink(child)})
            else:
                entries.append({"path": relative, "kind": "other"})
        return {"kind": "dir", "path": str(path), "entries": tuple(entries)}
    return {"kind": "missing", "path": str(path)}


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def result_as_dict(result: RealTaskBenchmarkReadinessResult) -> dict[str, object]:
    return asdict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_real_task_benchmark_readiness()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
