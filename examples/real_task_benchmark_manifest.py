from __future__ import annotations

from dataclasses import asdict, dataclass, field
import importlib.util
import json
import os
import shutil
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
    command_templates: tuple[str, ...]
    source_urls: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_tools", tuple(self.required_tools))
        object.__setattr__(self, "required_python_modules", tuple(self.required_python_modules))
        object.__setattr__(self, "required_env_vars", tuple(self.required_env_vars))
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
                command_templates=(
                    "defects4j checkout -p <project> -v <bug_id>b -w <buggy_workdir>",
                    "defects4j checkout -p <project> -v <bug_id>f -w <fixed_workdir>",
                    "defects4j compile",
                    "defects4j test -r",
                ),
                source_urls=(
                    "https://github.com/rjust/defects4j",
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
                command_templates=(
                    "python -m mqt.bench --benchmark <name> --level alg --output-format qasm3",
                    "python -m mqt.qcec <original.qasm> <candidate.qasm>",
                ),
                source_urls=(
                    "https://github.com/munich-quantum-toolkit/bench",
                    "https://mqt.readthedocs.io/projects/qcec/en/stable/",
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
        probes = tuple(
            probe_fn("tool", tool) for tool in spec.required_tools
        ) + tuple(
            probe_fn("python_module", module) for module in spec.required_python_modules
        ) + tuple(
            probe_fn("env_var", env_var) for env_var in spec.required_env_vars
        )
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
        return manifest.manifest_hash == real_task_manifest_hash(manifest)
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
        return RequirementProbe(
            kind=kind,
            name=name,
            available=available,
            evidence="fake_available" if available else "fake_missing",
        )

    return _probe


def _default_probe(kind: str, name: str) -> RequirementProbe:
    if kind == "tool":
        path = shutil.which(name)
        return RequirementProbe(kind=kind, name=name, available=path is not None, evidence=path or "missing_on_path")
    if kind == "python_module":
        try:
            spec = importlib.util.find_spec(name)
        except ModuleNotFoundError:
            spec = None
        return RequirementProbe(kind=kind, name=name, available=spec is not None, evidence=getattr(spec, "origin", None) or "missing_module")
    if kind == "env_var":
        value = os.environ.get(name, "")
        return RequirementProbe(kind=kind, name=name, available=bool(value), evidence="set" if value else "missing_env_var")
    raise ValueError(f"unknown probe kind: {kind}")


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def result_as_dict(result: RealTaskBenchmarkReadinessResult) -> dict[str, object]:
    return asdict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_real_task_benchmark_readiness()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
