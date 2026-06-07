from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Protocol

from examples.real_task_adapter_evidence import (
    RealTaskAdapterEvidenceCertificate,
    build_real_task_adapter_evidence_certificate,
    path_fingerprint_hash,
    receipt_backend_execution_evidence,
    receipt_artifact_provenance_hashes,
    receipt_artifact_value_provenance_hashes,
    receipt_artifacts_are_bound,
    receipt_execution_provenance_hashes,
)
from examples.real_task_benchmark_manifest import build_runtime_requirement_evidence_hashes
from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import HardVerifierResult, ProposalTrace, Receipt, StateSnapshot, TransactionEngine, TypedCandidate, stable_hash
from trwm.evaluation import (
    LearningEvaluationCertificate,
    build_learning_evaluation_certificate,
    learning_evaluation_supports_claim,
    validate_learning_evaluation_certificate,
)
from trwm.learning import ReceiptTrainedReversibleProposer


ROBOTICS_MOTION_BENCHMARK_ADAPTER_REPORT_SCHEMA = "trwm.example.robotics_motion_benchmark_adapter.v1"
ROBOTICS_MOTION_BENCHMARK_VERIFIER_ID = "motion_benchmark_moveit_ompl"
ROBOTICS_MOTION_BENCHMARK_VERIFIER_VERSION = "1.0"
ROBOTICS_MOTION_BENCHMARK_REQUIRED_TOOLS = ("roslaunch",)
ROBOTICS_MOTION_BENCHMARK_REQUIRED_ENV_VARS = ("TRWM_MOTION_BENCHMARK_TASK_ROOT",)
ROBOTICS_MOTION_BENCHMARK_REQUIRED_REQUIREMENTS = (
    *ROBOTICS_MOTION_BENCHMARK_REQUIRED_TOOLS,
    *ROBOTICS_MOTION_BENCHMARK_REQUIRED_ENV_VARS,
)
ROBOTICS_MOTION_BENCHMARK_SOURCES = (
    "https://carlosquinterop.github.io/project/motionbenchmaker/",
    "https://github.com/KavrakiLab/motion_bench_maker",
    "https://moveit.picknik.ai/main/doc/concepts/motion_planning.html",
    "https://docs.ros.org/en/indigo/api/moveit_tutorials/html/doc/benchmarking_tutorial.html",
    "https://docs.ros.org/en/rolling/p/ompl/doc/markdown/benchmark.html",
)
ROBOTICS_MOTION_BENCHMARK_CLAIM_BOUNDARY = (
    "Single-domain robotics adapter evidence only. A supported claim requires real MotionBenchMaker/"
    "MoveIt/OMPL task assets under TRWM_MOTION_BENCHMARK_TASK_ROOT plus ROS launch execution. "
    "Deterministic test doubles validate transaction mechanics but cannot support robotics safety, "
    "planner performance, or the full four-domain objective."
)


@dataclass(frozen=True)
class RoboticsTaskSpec:
    task_id: str
    split: str
    robot_id: str
    scene_id: str
    query_id: str


@dataclass(frozen=True)
class RoboticsCandidateBundle:
    task_id: str
    robot_id: str
    scene_id: str
    query_id: str
    unsafe_candidate_dir: str
    safe_candidate_dir: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class RoboticsVerificationResult:
    accepted: bool
    residual_kind: str
    metadata: Mapping[str, Any]


class RoboticsBenchmarkBackend(Protocol):
    backend_id: str
    backend_version: str
    real_backend: bool

    def available(self) -> bool:
        ...

    def missing_requirements(self) -> tuple[str, ...]:
        ...

    def generate_task(self, spec: RoboticsTaskSpec) -> RoboticsCandidateBundle:
        ...

    def verify_candidate(self, payload: Mapping[str, Any]) -> RoboticsVerificationResult:
        ...


@dataclass(frozen=True)
class RoboticsMotionBenchmarkTaskRow:
    task_id: str
    split: str
    robot_id: str
    scene_id: str
    query_id: str
    baseline_receipt_hashes: tuple[str, ...]
    learned_receipt_hashes: tuple[str, ...]
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int


@dataclass(frozen=True)
class RoboticsMotionBenchmarkAdapterReport:
    schema_version: str
    experiment_id: str
    backend_id: str
    backend_version: str
    backend_available: bool
    real_backend: bool
    missing_requirements: tuple[str, ...]
    backend_error: str
    runtime_requirement_evidence_hashes: tuple[str, ...]
    task_count: int
    train_task_ids: tuple[str, ...]
    held_out_task_ids: tuple[str, ...]
    rows: tuple[RoboticsMotionBenchmarkTaskRow, ...]
    learner_snapshot_hash: str
    learning_certificate_hash: str
    learning_certificate_valid: bool
    learning_certificate_supports_claim: bool
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
    verifier_call_gain: float
    hard_commit_only: bool
    train_eval_disjoint: bool
    heldout_arm_isolated: bool
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    ledger_head: str
    receipt_hashes: tuple[str, ...]
    typed_candidate_hashes: tuple[str, ...]
    hard_result_hashes: tuple[str, ...]
    hard_metadata_hashes: tuple[str, ...]
    receipt_artifacts_bound: bool
    receipt_artifact_hashes: tuple[str, ...]
    receipt_artifact_value_hashes: tuple[str, ...]
    backend_execution_evidence_ok: bool
    backend_execution_evidence_hashes: tuple[str, ...]
    source_urls: tuple[str, ...]
    claim_boundary: str


@dataclass(frozen=True)
class RoboticsMotionBenchmarkAdapterResult:
    report: RoboticsMotionBenchmarkAdapterReport
    learning_certificate: LearningEvaluationCertificate | None
    evidence_certificate: RealTaskAdapterEvidenceCertificate
    claim_certificate: ClaimCertificate


@dataclass(frozen=True)
class _CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout_tail: str
    stderr_tail: str


class MotionBenchmarkBackend:
    backend_id = "motionbenchmaker+moveit+ompl"
    backend_version = "dynamic"
    real_backend = True

    def __init__(self, *, task_root: str | None = None, timeout_seconds: int = 300):
        self.task_root = task_root or os.environ.get("TRWM_MOTION_BENCHMARK_TASK_ROOT", "")
        self.timeout_seconds = int(timeout_seconds)

    def available(self) -> bool:
        return not self.missing_requirements()

    def missing_requirements(self) -> tuple[str, ...]:
        missing = [tool for tool in ROBOTICS_MOTION_BENCHMARK_REQUIRED_TOOLS if shutil.which(tool) is None]
        if not self.task_root:
            missing.append("TRWM_MOTION_BENCHMARK_TASK_ROOT")
        elif not Path(self.task_root).exists():
            missing.append("TRWM_MOTION_BENCHMARK_TASK_ROOT")
        return tuple(missing)

    def generate_task(self, spec: RoboticsTaskSpec) -> RoboticsCandidateBundle:
        task_root = Path(self.task_root)
        task_dir = task_root / spec.task_id
        return RoboticsCandidateBundle(
            task_id=spec.task_id,
            robot_id=spec.robot_id,
            scene_id=spec.scene_id,
            query_id=spec.query_id,
            unsafe_candidate_dir=str(task_dir / "unsafe_motion_candidate"),
            safe_candidate_dir=str(task_dir / "safe_motion_candidate"),
            metadata={
                "robot_id": spec.robot_id,
                "scene_id": spec.scene_id,
                "query_id": spec.query_id,
                "task_root": str(task_root),
                "layout": "$TRWM_MOTION_BENCHMARK_TASK_ROOT/<task>/<candidate>",
            },
        )

    def verify_candidate(self, payload: Mapping[str, Any]) -> RoboticsVerificationResult:
        data = _normalize_payload(payload)
        if not self.available():
            return RoboticsVerificationResult(
                accepted=False,
                residual_kind="motion_benchmark_backend_unavailable",
                metadata={"backend_id": self.backend_id, "missing": self.missing_requirements()},
            )
        candidate_dir = Path(data["candidate_dir"])
        if not candidate_dir.exists():
            return RoboticsVerificationResult(
                accepted=False,
                residual_kind="motion_benchmark_candidate_missing",
                metadata={"candidate_dir": str(candidate_dir)},
            )
        command_config = candidate_dir / "command.json"
        if not command_config.exists():
            return RoboticsVerificationResult(
                accepted=False,
                residual_kind="motion_benchmark_command_missing",
                metadata={"candidate_dir": str(candidate_dir), "expected_command": str(command_config)},
            )
        command = _load_command_config(command_config)
        result_file = candidate_dir / str(command.get("result_file", "benchmark_result.json"))
        launch_package = str(command["launch_package"])
        launch_file = str(command["launch_file"])
        launch_args = tuple(str(arg) for arg in command.get("args", ()))
        run = self._run(("roslaunch", launch_package, launch_file, *launch_args), cwd=candidate_dir)
        if run.returncode != 0:
            return RoboticsVerificationResult(
                accepted=False,
                residual_kind="motion_benchmark_launch_failed",
                metadata={"command": asdict(run), "candidate_dir": str(candidate_dir)},
            )
        if not result_file.exists():
            return RoboticsVerificationResult(
                accepted=False,
                residual_kind="motion_benchmark_result_missing",
                metadata={"command": asdict(run), "result_file": str(result_file)},
            )
        result_data = json.loads(result_file.read_text(encoding="utf-8"))
        accepted = _benchmark_result_accepted(result_data)
        metadata = {
            "command": asdict(run),
            "candidate_dir": str(candidate_dir),
            "result_file": str(result_file),
            "benchmark_result": result_data,
        }
        if accepted:
            return RoboticsVerificationResult(accepted=True, residual_kind="", metadata=metadata)
        return RoboticsVerificationResult(
            accepted=False,
            residual_kind=_benchmark_residual_kind(result_data),
            metadata=metadata,
        )

    def _run(self, command: tuple[str, ...], *, cwd: Path) -> _CommandResult:
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return _CommandResult(
                command=command,
                returncode=int(completed.returncode),
                stdout_tail=_tail(completed.stdout),
                stderr_tail=_tail(completed.stderr),
            )
        except FileNotFoundError as exc:
            return _CommandResult(command=command, returncode=127, stdout_tail="", stderr_tail=str(exc))
        except subprocess.TimeoutExpired as exc:
            return _CommandResult(
                command=command,
                returncode=124,
                stdout_tail=_tail(exc.stdout or ""),
                stderr_tail=_tail(exc.stderr or ""),
            )


class DeterministicMotionBenchmarkBackend:
    """Test double for adapter mechanics. It is not real robotics evidence."""

    backend_id = "deterministic.motion_benchmark.testdouble"
    backend_version = "1.0"
    real_backend = False

    def __init__(self, available: bool = True):
        self._available = bool(available)

    def available(self) -> bool:
        return self._available

    def missing_requirements(self) -> tuple[str, ...]:
        return () if self._available else ROBOTICS_MOTION_BENCHMARK_REQUIRED_REQUIREMENTS

    def generate_task(self, spec: RoboticsTaskSpec) -> RoboticsCandidateBundle:
        return RoboticsCandidateBundle(
            task_id=spec.task_id,
            robot_id=spec.robot_id,
            scene_id=spec.scene_id,
            query_id=spec.query_id,
            unsafe_candidate_dir=f"/deterministic/{spec.task_id}/unsafe_motion_candidate",
            safe_candidate_dir=f"/deterministic/{spec.task_id}/safe_motion_candidate",
            metadata={"deterministic_testdouble": True},
        )

    def verify_candidate(self, payload: Mapping[str, Any]) -> RoboticsVerificationResult:
        data = _normalize_payload(payload)
        accepted = data["action"] == "safe_motion_candidate"
        if accepted:
            return RoboticsVerificationResult(
                accepted=True,
                residual_kind="",
                metadata={"deterministic_testdouble": True, "solved": True, "correct_solution": True},
            )
        return RoboticsVerificationResult(
            accepted=False,
            residual_kind="motion_benchmark_collision_or_unsolved",
            metadata={"deterministic_testdouble": True, "solved": False, "correct_solution": False},
        )


class RoboticsMotionBenchmarkAdapter:
    verifier_id = ROBOTICS_MOTION_BENCHMARK_VERIFIER_ID
    verifier_version = ROBOTICS_MOTION_BENCHMARK_VERIFIER_VERSION

    def __init__(self, backend: RoboticsBenchmarkBackend):
        self.backend = backend

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        if not self.backend.available():
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "motion_benchmark_backend_unavailable", "missing": self.backend.missing_requirements()},
                metadata={"backend_id": self.backend.backend_id},
            )
        result = self.backend.verify_candidate(payload)
        metadata = {
            "backend_id": self.backend.backend_id,
            "backend_version": self.backend.backend_version,
            "real_backend": self.backend.real_backend,
            "task_id": payload["task_id"],
            "robot_id": payload["robot_id"],
            "scene_id": payload["scene_id"],
            "query_id": payload["query_id"],
            "candidate_hash": payload["candidate_hash"],
            "action": payload["action"],
            **dict(result.metadata),
        }
        if result.accepted:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={
                "kind": result.residual_kind or "motion_benchmark_candidate_rejected",
                "repair": "safe_motion_candidate",
            },
            metadata=metadata,
        )

    def apply_commit(self, state: Mapping[str, Any], candidate: TypedCandidate) -> dict[str, Any]:
        payload = _normalize_payload(candidate.payload)
        return {
            "committed_tasks": (*tuple(state.get("committed_tasks", ())), payload["task_id"]),
            "last_candidate_hash": payload["candidate_hash"],
        }

    def replay(self, state: Mapping[str, Any], receipt: Receipt) -> dict[str, Any]:
        payload = _normalize_payload(receipt.replay_bundle["candidate_payload"])
        return {
            "committed_tasks": (*tuple(state.get("committed_tasks", ())), payload["task_id"]),
            "last_candidate_hash": payload["candidate_hash"],
        }

    def rollback(self, _state: Mapping[str, Any], receipt: Receipt) -> dict[str, Any]:
        return dict(receipt.rollback_bundle["pre_state"])


def run_robotics_motion_benchmark_adapter_experiment(
    backend: RoboticsBenchmarkBackend | None = None,
) -> RoboticsMotionBenchmarkAdapterResult:
    backend = backend or MotionBenchmarkBackend()
    if not backend.available():
        report = _empty_report(backend)
        return _result_for_report(report, None)
    try:
        return _run_available_backend(backend)
    except Exception as exc:
        report = _empty_report(backend, backend_error=f"{type(exc).__name__}:{_tail(str(exc), limit=400)}")
        return _result_for_report(report, None)


def _run_available_backend(backend: RoboticsBenchmarkBackend) -> RoboticsMotionBenchmarkAdapterResult:
    specs = _task_specs()
    bundles = {spec.task_id: backend.generate_task(spec) for spec in specs}
    train_specs = tuple(spec for spec in specs if spec.split == "train")
    heldout_specs = tuple(spec for spec in specs if spec.split == "heldout")
    training_adapter = RoboticsMotionBenchmarkAdapter(backend)
    training_engine = TransactionEngine(training_adapter)
    proposer = ReceiptTrainedReversibleProposer()
    seed_state = {"committed_tasks": (), "last_candidate_hash": ""}
    training_state: Mapping[str, Any] = seed_state

    training_receipts: list[Receipt] = []
    baseline_by_task: dict[str, tuple[Receipt, ...]] = {}
    learned_by_task: dict[str, tuple[Receipt, ...]] = {}

    for spec in train_specs:
        outcome = _submit_until_commit(
            training_engine,
            training_state,
            spec,
            bundles[spec.task_id],
            arm="train",
            candidates=_ordered_candidates(spec, bundles[spec.task_id]),
        )
        training_state = outcome.state
        training_receipts.extend(outcome.receipts)
        for receipt in outcome.receipts:
            proposer.update(receipt)

    snapshot = proposer.snapshot()
    baseline_engine = TransactionEngine(RoboticsMotionBenchmarkAdapter(backend))
    learned_engine = TransactionEngine(RoboticsMotionBenchmarkAdapter(backend))
    baseline_state: Mapping[str, Any] = training_state
    learned_state: Mapping[str, Any] = training_state
    heldout_arm_start_hashes: list[tuple[str, str]] = []
    for spec in heldout_specs:
        heldout_arm_start_hashes.append((
            StateSnapshot.capture(baseline_state).state_hash,
            StateSnapshot.capture(learned_state).state_hash,
        ))
        baseline = _submit_until_commit(
            baseline_engine,
            baseline_state,
            spec,
            bundles[spec.task_id],
            arm="baseline",
            candidates=_ordered_candidates(spec, bundles[spec.task_id]),
        )
        baseline_state = baseline.state
        baseline_by_task[spec.task_id] = baseline.receipts
        learned_candidates = tuple(proposer.rank("robotics_motion_benchmark", _ordered_candidates(spec, bundles[spec.task_id])))
        learned = _submit_until_commit(learned_engine, learned_state, spec, bundles[spec.task_id], arm="learned", candidates=learned_candidates)
        learned_state = learned.state
        learned_by_task[spec.task_id] = learned.receipts

    baseline_receipts = tuple(receipt for receipts in baseline_by_task.values() for receipt in receipts)
    learned_receipts = tuple(receipt for receipts in learned_by_task.values() for receipt in receipts)
    all_receipts = (*tuple(training_receipts), *baseline_receipts, *learned_receipts)
    typed_candidate_hashes, hard_result_hashes, hard_metadata_hashes = receipt_execution_provenance_hashes(all_receipts)
    receipt_artifact_hashes = receipt_artifact_provenance_hashes(all_receipts)
    receipt_artifact_value_hashes = receipt_artifact_value_provenance_hashes(all_receipts)
    receipt_artifacts_bound = receipt_artifacts_are_bound(all_receipts)
    backend_execution_evidence_ok, backend_execution_evidence_hashes = receipt_backend_execution_evidence("robotics", all_receipts)
    runtime_requirement_evidence_hashes = _runtime_requirement_evidence_hashes(backend)
    replay_ok, rollback_ok = _audit_replay_rollback_many(
        (training_engine, seed_state),
        (baseline_engine, training_state),
        (learned_engine, training_state),
    )
    ledger_audit_ok = training_engine.ledger.audit() and baseline_engine.ledger.audit() and learned_engine.ledger.audit()
    invalid_commit_count = (
        training_engine.invalid_commit_count + baseline_engine.invalid_commit_count + learned_engine.invalid_commit_count
    )
    heldout_arm_isolated = len(heldout_arm_start_hashes) == len(heldout_specs) and all(
        left == right for left, right in heldout_arm_start_hashes
    )
    ledger_head = stable_hash(
        {
            "training": training_engine.ledger.head,
            "baseline": baseline_engine.ledger.head,
            "learned": learned_engine.ledger.head,
        }
    )
    learning_certificate = build_learning_evaluation_certificate(
        claim_id="robotics_motion_benchmark_receipt_trained_reversible_call_reduction",
        learner_id=snapshot.learner_id,
        learner_snapshot_hash=snapshot.snapshot_hash,
        training_receipt_hashes=tuple(receipt.receipt_hash for receipt in training_receipts),
        evaluation_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned_receipts),
        baseline_name="static_unsafe_motion_candidate_first",
        learned_name=snapshot.learner_id,
        baseline_verifier_calls=len(baseline_receipts),
        learned_verifier_calls=len(learned_receipts),
        baseline_success_count=sum(1 for receipt in baseline_receipts if receipt.committed),
        learned_success_count=sum(1 for receipt in learned_receipts if receipt.committed),
        verifier_budget=len(baseline_receipts),
        candidate_count=2 * len(heldout_specs),
        same_case_baseline=True,
        hard_commit_only=all(receipt.committed == receipt.hard_result.accepted for receipt in all_receipts),
        invalid_commit_count=invalid_commit_count,
        ledger_audit=ledger_audit_ok,
        replay_rollback_rate=1.0 if replay_ok and rollback_ok else 0.0,
        metrics={
            "backend_id": backend.backend_id,
            "real_backend": backend.real_backend,
            "held_out_task_ids": tuple(spec.task_id for spec in heldout_specs),
            "heldout_arm_isolated": heldout_arm_isolated,
        },
    )
    report = RoboticsMotionBenchmarkAdapterReport(
        schema_version=ROBOTICS_MOTION_BENCHMARK_ADAPTER_REPORT_SCHEMA,
        experiment_id="robotics_motion_benchmark_receipt_trained_adapter",
        backend_id=backend.backend_id,
        backend_version=backend.backend_version,
        backend_available=True,
        real_backend=backend.real_backend,
        missing_requirements=(),
        backend_error="",
        runtime_requirement_evidence_hashes=runtime_requirement_evidence_hashes,
        task_count=len(specs),
        train_task_ids=tuple(spec.task_id for spec in train_specs),
        held_out_task_ids=tuple(spec.task_id for spec in heldout_specs),
        rows=tuple(_task_row(spec, baseline_by_task[spec.task_id], learned_by_task[spec.task_id]) for spec in heldout_specs),
        learner_snapshot_hash=snapshot.snapshot_hash,
        learning_certificate_hash=learning_certificate.certificate_hash,
        learning_certificate_valid=validate_learning_evaluation_certificate(learning_certificate),
        learning_certificate_supports_claim=learning_evaluation_supports_claim(learning_certificate),
        receipt_count=len(all_receipts),
        training_receipt_count=len(training_receipts),
        baseline_receipt_count=len(baseline_receipts),
        learned_receipt_count=len(learned_receipts),
        committed_count=sum(1 for receipt in all_receipts if receipt.committed),
        rejected_count=sum(1 for receipt in all_receipts if receipt.hard_result.rejected),
        invalid_commit_count=invalid_commit_count,
        baseline_verifier_calls=len(baseline_receipts),
        learned_verifier_calls=len(learned_receipts),
        baseline_success_count=sum(1 for receipt in baseline_receipts if receipt.committed),
        learned_success_count=sum(1 for receipt in learned_receipts if receipt.committed),
        verifier_call_reduction=len(baseline_receipts) - len(learned_receipts),
        verifier_call_gain=round(len(baseline_receipts) / len(learned_receipts), 12),
        hard_commit_only=learning_certificate.hard_commit_only,
        train_eval_disjoint=learning_certificate.train_eval_disjoint,
        heldout_arm_isolated=heldout_arm_isolated,
        replay_audit_ok=replay_ok,
        rollback_audit_ok=rollback_ok,
        ledger_audit_ok=ledger_audit_ok,
        ledger_head=ledger_head,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        typed_candidate_hashes=typed_candidate_hashes,
        hard_result_hashes=hard_result_hashes,
        hard_metadata_hashes=hard_metadata_hashes,
        receipt_artifacts_bound=receipt_artifacts_bound,
        receipt_artifact_hashes=receipt_artifact_hashes,
        receipt_artifact_value_hashes=receipt_artifact_value_hashes,
        backend_execution_evidence_ok=backend_execution_evidence_ok,
        backend_execution_evidence_hashes=backend_execution_evidence_hashes,
        source_urls=ROBOTICS_MOTION_BENCHMARK_SOURCES,
        claim_boundary=ROBOTICS_MOTION_BENCHMARK_CLAIM_BOUNDARY,
    )
    return _result_for_report(report, learning_certificate)


def _result_for_report(
    report: RoboticsMotionBenchmarkAdapterReport,
    learning_certificate: LearningEvaluationCertificate | None,
) -> RoboticsMotionBenchmarkAdapterResult:
    claim = _claim_for_report(report)
    evidence = build_real_task_adapter_evidence_certificate(
        domain="robotics",
        report=report,
        learning_certificate=learning_certificate,
        claim_certificate=claim,
    )
    return RoboticsMotionBenchmarkAdapterResult(
        report=report,
        learning_certificate=learning_certificate,
        evidence_certificate=evidence,
        claim_certificate=claim,
    )


@dataclass(frozen=True)
class _SubmitOutcome:
    state: Mapping[str, Any]
    receipts: tuple[Receipt, ...]


def _submit_until_commit(
    engine: TransactionEngine,
    state: Mapping[str, Any],
    spec: RoboticsTaskSpec,
    bundle: RoboticsCandidateBundle,
    *,
    arm: str,
    candidates: tuple[TypedCandidate, ...],
) -> _SubmitOutcome:
    receipts: list[Receipt] = []
    current = state
    for idx, candidate in enumerate(candidates):
        action = str(candidate.payload["action"])
        outcome = engine.transact(
            current,
            ProposalTrace(
                branch_id=f"robotics-motion-benchmark-{arm}-{spec.task_id}-{idx}-{action}",
                actions=({"task_id": spec.task_id, "arm": arm, "action": action},),
                model_version="robotics.motion_benchmark.receipt_trained_reversible.v1",
            ),
            candidate,
        )
        receipts.append(outcome.receipt)
        current = outcome.state
        if outcome.committed:
            break
    return _SubmitOutcome(state=current, receipts=tuple(receipts))


def _ordered_candidates(spec: RoboticsTaskSpec, bundle: RoboticsCandidateBundle) -> tuple[TypedCandidate, ...]:
    return (
        _candidate(spec, bundle, action="unsafe_motion_candidate", candidate_dir=bundle.unsafe_candidate_dir),
        _candidate(spec, bundle, action="safe_motion_candidate", candidate_dir=bundle.safe_candidate_dir),
    )


def _candidate(spec: RoboticsTaskSpec, bundle: RoboticsCandidateBundle, *, action: str, candidate_dir: str) -> TypedCandidate:
    payload = {
        "context": "robotics_motion_benchmark",
        "task_id": spec.task_id,
        "split": spec.split,
        "robot_id": spec.robot_id,
        "scene_id": spec.scene_id,
        "query_id": spec.query_id,
        "action": action,
        "candidate_dir": candidate_dir,
        "candidate_hash": stable_hash(
            {
                "robot_id": spec.robot_id,
                "scene_id": spec.scene_id,
                "query_id": spec.query_id,
                "action": action,
                "candidate_dir": candidate_dir,
            }
        ),
    }
    return TypedCandidate(
        payload=payload,
        type_name="robotics.motion_benchmark.candidate",
        schema_version="robotics.motion_benchmark.candidate.v1",
        hashes=_candidate_artifact_hashes(payload, bundle, candidate_dir),
    )


def _candidate_artifact_hashes(payload: Mapping[str, Any], bundle: RoboticsCandidateBundle, candidate_dir: str) -> Mapping[str, str]:
    hashes = {
        "candidate_payload_hash": stable_hash(payload),
        "task_bundle_metadata_hash": stable_hash(bundle.metadata),
    }
    candidate_dir_hash = path_fingerprint_hash(candidate_dir)
    if candidate_dir_hash:
        hashes["candidate_dir_fingerprint_hash"] = candidate_dir_hash
    command_hash = path_fingerprint_hash(Path(candidate_dir) / "command.json")
    if command_hash:
        hashes["command_config_hash"] = command_hash
    return hashes


def _runtime_requirement_evidence_hashes(backend: RoboticsBenchmarkBackend) -> tuple[str, ...]:
    if not backend.real_backend:
        return ()
    return build_runtime_requirement_evidence_hashes(
        required_tools=ROBOTICS_MOTION_BENCHMARK_REQUIRED_TOOLS,
        required_env_vars=ROBOTICS_MOTION_BENCHMARK_REQUIRED_ENV_VARS,
    )


def _task_specs() -> tuple[RoboticsTaskSpec, ...]:
    return (
        RoboticsTaskSpec("train-kitchen-pick", "train", "fanuc_m10ia", "kitchen", "pick1"),
        RoboticsTaskSpec("heldout-shelf-place", "heldout", "fetch", "shelf", "place1"),
        RoboticsTaskSpec("heldout-cabinet-reach", "heldout", "panda", "cabinet", "reach1"),
    )


def _task_row(
    spec: RoboticsTaskSpec,
    baseline: tuple[Receipt, ...],
    learned: tuple[Receipt, ...],
) -> RoboticsMotionBenchmarkTaskRow:
    return RoboticsMotionBenchmarkTaskRow(
        task_id=spec.task_id,
        split=spec.split,
        robot_id=spec.robot_id,
        scene_id=spec.scene_id,
        query_id=spec.query_id,
        baseline_receipt_hashes=tuple(receipt.receipt_hash for receipt in baseline),
        learned_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned),
        baseline_verifier_calls=len(baseline),
        learned_verifier_calls=len(learned),
        baseline_success_count=sum(1 for receipt in baseline if receipt.committed),
        learned_success_count=sum(1 for receipt in learned if receipt.committed),
    )


def _claim_for_report(report: RoboticsMotionBenchmarkAdapterReport) -> ClaimCertificate:
    return certify_claim(
        claim_id="robotics_motion_benchmark_receipt_trained_reversible_adapter",
        claim_text=(
            "On held-out MotionBenchMaker/MoveIt/OMPL robotics tasks, a receipt-trained reversible "
            "proposer reduces hard-verifier calls while preserving zero invalid commits."
        ),
        evidence_grade=(
            "G1"
            if (
                report.backend_available
                and report.real_backend
                and bool(report.runtime_requirement_evidence_hashes)
                and report.receipt_artifacts_bound
                and report.backend_execution_evidence_ok
            )
            else "G0"
        ),
        scope="robotics_motion_benchmark_adapter",
        requirements=(
            requirement("backend_available", report.backend_available, missing=report.missing_requirements, error=report.backend_error),
            requirement("real_motion_benchmark_backend", report.real_backend),
            requirement(
                "runtime_requirements_bound",
                (not report.real_backend) or bool(report.runtime_requirement_evidence_hashes),
                evidence_hashes=report.runtime_requirement_evidence_hashes,
            ),
            requirement(
                "receipt_artifacts_bound",
                report.receipt_artifacts_bound,
                artifact_hashes=report.receipt_artifact_hashes,
            ),
            requirement(
                "backend_execution_evidence_bound",
                report.backend_execution_evidence_ok,
                evidence_hashes=report.backend_execution_evidence_hashes,
            ),
            requirement("learning_certificate_valid", report.learning_certificate_valid),
            requirement("learning_certificate_supports_claim", report.learning_certificate_supports_claim),
            requirement("hard_verifier_calls_reduced", report.learned_verifier_calls < report.baseline_verifier_calls),
            requirement("success_preserved", report.learned_success_count == report.baseline_success_count and report.learned_success_count > 0),
            requirement("zero_invalid_commits", report.invalid_commit_count == 0),
            requirement("heldout_arm_isolated", report.heldout_arm_isolated),
            requirement("replay_rollback_ok", report.replay_audit_ok and report.rollback_audit_ok and report.ledger_audit_ok),
        ),
        metrics={
            "baseline_verifier_calls": report.baseline_verifier_calls,
            "learned_verifier_calls": report.learned_verifier_calls,
            "verifier_call_reduction": report.verifier_call_reduction,
            "invalid_commit_count": report.invalid_commit_count,
        },
        boundary=report.claim_boundary,
        sources=report.source_urls,
    )


def _empty_report(backend: RoboticsBenchmarkBackend, *, backend_error: str = "") -> RoboticsMotionBenchmarkAdapterReport:
    return RoboticsMotionBenchmarkAdapterReport(
        schema_version=ROBOTICS_MOTION_BENCHMARK_ADAPTER_REPORT_SCHEMA,
        experiment_id="robotics_motion_benchmark_receipt_trained_adapter",
        backend_id=backend.backend_id,
        backend_version=backend.backend_version,
        backend_available=False,
        real_backend=backend.real_backend,
        missing_requirements=backend.missing_requirements(),
        backend_error=backend_error,
        runtime_requirement_evidence_hashes=(),
        task_count=0,
        train_task_ids=(),
        held_out_task_ids=(),
        rows=(),
        learner_snapshot_hash="",
        learning_certificate_hash="",
        learning_certificate_valid=False,
        learning_certificate_supports_claim=False,
        receipt_count=0,
        training_receipt_count=0,
        baseline_receipt_count=0,
        learned_receipt_count=0,
        committed_count=0,
        rejected_count=0,
        invalid_commit_count=0,
        baseline_verifier_calls=0,
        learned_verifier_calls=0,
        baseline_success_count=0,
        learned_success_count=0,
        verifier_call_reduction=0,
        verifier_call_gain=0.0,
        hard_commit_only=False,
        train_eval_disjoint=False,
        heldout_arm_isolated=False,
        replay_audit_ok=False,
        rollback_audit_ok=False,
        ledger_audit_ok=False,
        ledger_head="",
        receipt_hashes=(),
        typed_candidate_hashes=(),
        hard_result_hashes=(),
        hard_metadata_hashes=(),
        receipt_artifacts_bound=False,
        receipt_artifact_hashes=(),
        receipt_artifact_value_hashes=(),
        backend_execution_evidence_ok=False,
        backend_execution_evidence_hashes=(),
        source_urls=ROBOTICS_MOTION_BENCHMARK_SOURCES,
        claim_boundary=ROBOTICS_MOTION_BENCHMARK_CLAIM_BOUNDARY,
    )


def _audit_replay_rollback(engine: TransactionEngine, seed_state: Mapping[str, Any]) -> tuple[bool, bool]:
    replay_ok = False
    rollback_ok = False
    try:
        engine.replay_audit(seed_state)
        replay_ok = True
    except Exception:
        replay_ok = False
    try:
        rollback_ok = engine.rollback_audit(seed_state) == dict(seed_state)
    except Exception:
        rollback_ok = False
    return replay_ok, rollback_ok


def _audit_replay_rollback_many(*items: tuple[TransactionEngine, Mapping[str, Any]]) -> tuple[bool, bool]:
    replay_ok = True
    rollback_ok = True
    for engine, seed_state in items:
        replay, rollback = _audit_replay_rollback(engine, seed_state)
        replay_ok = replay_ok and replay
        rollback_ok = rollback_ok and rollback
    return replay_ok, rollback_ok


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "context": str(payload["context"]),
        "task_id": str(payload["task_id"]),
        "split": str(payload["split"]),
        "robot_id": str(payload["robot_id"]),
        "scene_id": str(payload["scene_id"]),
        "query_id": str(payload["query_id"]),
        "action": str(payload["action"]),
        "candidate_dir": str(payload["candidate_dir"]),
        "candidate_hash": str(payload["candidate_hash"]),
    }


def _load_command_config(path: Path) -> Mapping[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("motion benchmark command config must be a JSON object")
    if not data.get("launch_package") or not data.get("launch_file"):
        raise ValueError("motion benchmark command config needs launch_package and launch_file")
    args = data.get("args", ())
    if not isinstance(args, (list, tuple)):
        raise ValueError("motion benchmark command args must be a list")
    return data


def _benchmark_result_accepted(result_data: Mapping[str, Any]) -> bool:
    solved = bool(result_data.get("solved", False))
    correct = bool(result_data.get("correct_solution", result_data.get("simplified_correct_solution", False)))
    approximate = bool(result_data.get("approximate_solution", False))
    if "solution_clearance" in result_data:
        clearance = float(result_data["solution_clearance"])
    elif "simplified_solution_clearance" in result_data:
        clearance = float(result_data["simplified_solution_clearance"])
    else:
        return False
    return solved and correct and not approximate and clearance >= 0.0


def _benchmark_residual_kind(result_data: Mapping[str, Any]) -> str:
    if not bool(result_data.get("solved", False)):
        return "motion_benchmark_unsolved"
    if bool(result_data.get("approximate_solution", False)):
        return "motion_benchmark_approximate_solution"
    if not bool(result_data.get("correct_solution", result_data.get("simplified_correct_solution", False))):
        return "motion_benchmark_incorrect_solution"
    if "solution_clearance" in result_data:
        clearance = float(result_data["solution_clearance"])
    elif "simplified_solution_clearance" in result_data:
        clearance = float(result_data["simplified_solution_clearance"])
    else:
        return "motion_benchmark_clearance_missing"
    if clearance < 0.0:
        return "motion_benchmark_negative_clearance"
    return "motion_benchmark_candidate_rejected"


def _tail(text: str | bytes, *, limit: int = 1000) -> str:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return str(text)[-limit:]


def result_as_dict(result: RoboticsMotionBenchmarkAdapterResult) -> dict[str, Any]:
    return asdict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_robotics_motion_benchmark_adapter_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
