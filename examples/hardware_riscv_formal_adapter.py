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
    real_task_adapter_claim_evidence_grade,
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


HARDWARE_RISCV_FORMAL_ADAPTER_REPORT_SCHEMA = "trwm.example.hardware_riscv_formal_adapter.v1"
HARDWARE_RISCV_FORMAL_VERIFIER_ID = "riscv_formal_symbiyosys_rvfi"
HARDWARE_RISCV_FORMAL_VERIFIER_VERSION = "1.0"
HARDWARE_RISCV_FORMAL_REQUIRED_TOOLS = ("sby", "yosys", "make", "python3")
HARDWARE_RISCV_FORMAL_REQUIRED_ENV_VARS = ("TRWM_RISCV_FORMAL_TASK_ROOT",)
HARDWARE_RISCV_FORMAL_REQUIRED_REQUIREMENTS = (*HARDWARE_RISCV_FORMAL_REQUIRED_TOOLS, *HARDWARE_RISCV_FORMAL_REQUIRED_ENV_VARS)
HARDWARE_RISCV_FORMAL_SOURCES = (
    "https://github.com/YosysHQ/riscv-formal",
    "https://yosyshq.readthedocs.io/projects/riscv-formal/en/latest/procedure.html",
    "https://yosyshq.readthedocs.io/projects/riscv-formal/en/latest/rvfi.html",
)
HARDWARE_RISCV_FORMAL_CLAIM_BOUNDARY = (
    "Single-domain hardware adapter evidence only. A supported claim requires real riscv-formal "
    "task assets under TRWM_RISCV_FORMAL_TASK_ROOT plus SymbiYosys/Yosys execution. Deterministic "
    "test doubles validate transaction mechanics but cannot support RISC-V core correctness, "
    "hardware verification performance, or the full four-domain objective."
)


@dataclass(frozen=True)
class HardwareTaskSpec:
    task_id: str
    split: str
    core_id: str
    check_family: str
    make_target: str = "j1"


@dataclass(frozen=True)
class HardwareCandidateBundle:
    task_id: str
    core_id: str
    check_family: str
    make_target: str
    violating_candidate_dir: str
    compliant_candidate_dir: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class HardwareVerificationResult:
    accepted: bool
    residual_kind: str
    metadata: Mapping[str, Any]


class HardwareFormalBackend(Protocol):
    backend_id: str
    backend_version: str
    real_backend: bool

    def available(self) -> bool:
        ...

    def missing_requirements(self) -> tuple[str, ...]:
        ...

    def generate_task(self, spec: HardwareTaskSpec) -> HardwareCandidateBundle:
        ...

    def verify_candidate(self, payload: Mapping[str, Any]) -> HardwareVerificationResult:
        ...


@dataclass(frozen=True)
class HardwareRiscVFormalTaskRow:
    task_id: str
    split: str
    core_id: str
    check_family: str
    baseline_receipt_hashes: tuple[str, ...]
    learned_receipt_hashes: tuple[str, ...]
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int


@dataclass(frozen=True)
class HardwareRiscVFormalAdapterReport:
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
    rows: tuple[HardwareRiscVFormalTaskRow, ...]
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
class HardwareRiscVFormalAdapterResult:
    report: HardwareRiscVFormalAdapterReport
    learning_certificate: LearningEvaluationCertificate | None
    evidence_certificate: RealTaskAdapterEvidenceCertificate
    claim_certificate: ClaimCertificate


@dataclass(frozen=True)
class _CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout_tail: str
    stderr_tail: str


class RiscVFormalBackend:
    backend_id = "riscv-formal+sby+yosys"
    backend_version = "dynamic"
    real_backend = True

    def __init__(self, *, task_root: str | None = None, timeout_seconds: int = 300):
        self.task_root = task_root or os.environ.get("TRWM_RISCV_FORMAL_TASK_ROOT", "")
        self.timeout_seconds = int(timeout_seconds)

    def available(self) -> bool:
        return not self.missing_requirements()

    def missing_requirements(self) -> tuple[str, ...]:
        missing = [tool for tool in HARDWARE_RISCV_FORMAL_REQUIRED_TOOLS if shutil.which(tool) is None]
        if not self.task_root:
            missing.append("TRWM_RISCV_FORMAL_TASK_ROOT")
        elif not Path(self.task_root).exists():
            missing.append("TRWM_RISCV_FORMAL_TASK_ROOT")
        return tuple(missing)

    def generate_task(self, spec: HardwareTaskSpec) -> HardwareCandidateBundle:
        task_root = Path(self.task_root)
        task_dir = task_root / spec.task_id
        return HardwareCandidateBundle(
            task_id=spec.task_id,
            core_id=spec.core_id,
            check_family=spec.check_family,
            make_target=spec.make_target,
            violating_candidate_dir=str(task_dir / "rvfi_violating_candidate"),
            compliant_candidate_dir=str(task_dir / "rvfi_compliant_candidate"),
            metadata={
                "core_id": spec.core_id,
                "check_family": spec.check_family,
                "task_root": str(task_root),
                "layout": "$TRWM_RISCV_FORMAL_TASK_ROOT/<task>/<candidate>",
            },
        )

    def verify_candidate(self, payload: Mapping[str, Any]) -> HardwareVerificationResult:
        data = _normalize_payload(payload)
        if not self.available():
            return HardwareVerificationResult(
                accepted=False,
                residual_kind="riscv_formal_backend_unavailable",
                metadata={"backend_id": self.backend_id, "missing": self.missing_requirements()},
            )
        candidate_dir = Path(data["candidate_dir"])
        if not candidate_dir.exists():
            return HardwareVerificationResult(
                accepted=False,
                residual_kind="riscv_formal_candidate_missing",
                metadata={"candidate_dir": str(candidate_dir)},
            )
        checks_dir = candidate_dir / "checks"
        commands: list[dict[str, Any]] = []
        if not (checks_dir / "Makefile").exists():
            genchecks = candidate_dir / ".." / ".." / "checks" / "genchecks.py"
            if not genchecks.exists():
                return HardwareVerificationResult(
                    accepted=False,
                    residual_kind="riscv_formal_genchecks_missing",
                    metadata={"candidate_dir": str(candidate_dir), "expected_genchecks": str(genchecks)},
                )
            generated = self._run(("python3", str(genchecks)), cwd=candidate_dir)
            commands.append(asdict(generated))
            if generated.returncode != 0:
                return HardwareVerificationResult(
                    accepted=False,
                    residual_kind="riscv_formal_genchecks_failed",
                    metadata={"commands": tuple(commands)},
                )
        check = self._run(("make", "-C", str(checks_dir), data["make_target"]), cwd=candidate_dir)
        commands.append(asdict(check))
        if check.returncode == 0:
            return HardwareVerificationResult(
                accepted=True,
                residual_kind="",
                metadata={"commands": tuple(commands), "candidate_dir": str(candidate_dir)},
            )
        return HardwareVerificationResult(
            accepted=False,
            residual_kind="riscv_formal_check_failed",
            metadata={"commands": tuple(commands), "candidate_dir": str(candidate_dir)},
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


class DeterministicRiscVFormalBackend:
    """Test double for adapter mechanics. It is not real hardware evidence."""

    backend_id = "deterministic.riscv_formal.testdouble"
    backend_version = "1.0"
    real_backend = False

    def __init__(self, available: bool = True):
        self._available = bool(available)

    def available(self) -> bool:
        return self._available

    def missing_requirements(self) -> tuple[str, ...]:
        return () if self._available else HARDWARE_RISCV_FORMAL_REQUIRED_REQUIREMENTS

    def generate_task(self, spec: HardwareTaskSpec) -> HardwareCandidateBundle:
        return HardwareCandidateBundle(
            task_id=spec.task_id,
            core_id=spec.core_id,
            check_family=spec.check_family,
            make_target=spec.make_target,
            violating_candidate_dir=f"/deterministic/{spec.task_id}/rvfi_violating_candidate",
            compliant_candidate_dir=f"/deterministic/{spec.task_id}/rvfi_compliant_candidate",
            metadata={"deterministic_testdouble": True},
        )

    def verify_candidate(self, payload: Mapping[str, Any]) -> HardwareVerificationResult:
        data = _normalize_payload(payload)
        accepted = data["action"] == "rvfi_compliant_candidate"
        if accepted:
            return HardwareVerificationResult(
                accepted=True,
                residual_kind="",
                metadata={"deterministic_testdouble": True},
            )
        return HardwareVerificationResult(
            accepted=False,
            residual_kind="riscv_formal_assertion_failed",
            metadata={"deterministic_testdouble": True, "check_family": data["check_family"]},
        )


class HardwareRiscVFormalAdapter:
    verifier_id = HARDWARE_RISCV_FORMAL_VERIFIER_ID
    verifier_version = HARDWARE_RISCV_FORMAL_VERIFIER_VERSION

    def __init__(self, backend: HardwareFormalBackend):
        self.backend = backend

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        if not self.backend.available():
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "riscv_formal_backend_unavailable", "missing": self.backend.missing_requirements()},
                metadata={"backend_id": self.backend.backend_id},
            )
        result = self.backend.verify_candidate(payload)
        metadata = {
            "backend_id": self.backend.backend_id,
            "backend_version": self.backend.backend_version,
            "real_backend": self.backend.real_backend,
            "task_id": payload["task_id"],
            "core_id": payload["core_id"],
            "check_family": payload["check_family"],
            "make_target": payload["make_target"],
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
                "kind": result.residual_kind or "riscv_formal_candidate_rejected",
                "repair": "rvfi_compliant_candidate",
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


def run_hardware_riscv_formal_adapter_experiment(
    backend: HardwareFormalBackend | None = None,
) -> HardwareRiscVFormalAdapterResult:
    backend = backend or RiscVFormalBackend()
    if not backend.available():
        report = _empty_report(backend)
        return _result_for_report(report, None)
    try:
        return _run_available_backend(backend)
    except Exception as exc:
        report = _empty_report(backend, backend_error=f"{type(exc).__name__}:{_tail(str(exc), limit=400)}")
        return _result_for_report(report, None)


def _run_available_backend(backend: HardwareFormalBackend) -> HardwareRiscVFormalAdapterResult:
    specs = _task_specs()
    bundles = {spec.task_id: backend.generate_task(spec) for spec in specs}
    train_specs = tuple(spec for spec in specs if spec.split == "train")
    heldout_specs = tuple(spec for spec in specs if spec.split == "heldout")
    training_adapter = HardwareRiscVFormalAdapter(backend)
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
    baseline_engine = TransactionEngine(HardwareRiscVFormalAdapter(backend))
    learned_engine = TransactionEngine(HardwareRiscVFormalAdapter(backend))
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
        learned_candidates = tuple(proposer.rank("hardware_riscv_formal", _ordered_candidates(spec, bundles[spec.task_id])))
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
    backend_execution_evidence_ok, backend_execution_evidence_hashes = receipt_backend_execution_evidence("hardware", all_receipts)
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
        claim_id="hardware_riscv_formal_receipt_trained_reversible_call_reduction",
        learner_id=snapshot.learner_id,
        learner_snapshot_hash=snapshot.snapshot_hash,
        training_receipt_hashes=tuple(receipt.receipt_hash for receipt in training_receipts),
        baseline_receipt_hashes=tuple(receipt.receipt_hash for receipt in baseline_receipts),
        evaluation_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned_receipts),
        baseline_name="static_rvfi_violating_candidate_first",
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
    report = HardwareRiscVFormalAdapterReport(
        schema_version=HARDWARE_RISCV_FORMAL_ADAPTER_REPORT_SCHEMA,
        experiment_id="hardware_riscv_formal_receipt_trained_adapter",
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
        source_urls=HARDWARE_RISCV_FORMAL_SOURCES,
        claim_boundary=HARDWARE_RISCV_FORMAL_CLAIM_BOUNDARY,
    )
    return _result_for_report(report, learning_certificate)


def _result_for_report(
    report: HardwareRiscVFormalAdapterReport,
    learning_certificate: LearningEvaluationCertificate | None,
) -> HardwareRiscVFormalAdapterResult:
    claim = _claim_for_report(report)
    evidence = build_real_task_adapter_evidence_certificate(
        domain="hardware",
        report=report,
        learning_certificate=learning_certificate,
        claim_certificate=claim,
    )
    return HardwareRiscVFormalAdapterResult(
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
    spec: HardwareTaskSpec,
    bundle: HardwareCandidateBundle,
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
                branch_id=f"hardware-riscv-formal-{arm}-{spec.task_id}-{idx}-{action}",
                actions=({"task_id": spec.task_id, "arm": arm, "action": action},),
                model_version="hardware.riscv_formal.receipt_trained_reversible.v1",
            ),
            candidate,
        )
        receipts.append(outcome.receipt)
        current = outcome.state
        if outcome.committed:
            break
    return _SubmitOutcome(state=current, receipts=tuple(receipts))


def _ordered_candidates(spec: HardwareTaskSpec, bundle: HardwareCandidateBundle) -> tuple[TypedCandidate, ...]:
    return (
        _candidate(spec, bundle, action="rvfi_violating_candidate", candidate_dir=bundle.violating_candidate_dir),
        _candidate(spec, bundle, action="rvfi_compliant_candidate", candidate_dir=bundle.compliant_candidate_dir),
    )


def _candidate(spec: HardwareTaskSpec, bundle: HardwareCandidateBundle, *, action: str, candidate_dir: str) -> TypedCandidate:
    payload = {
        "context": "hardware_riscv_formal",
        "task_id": spec.task_id,
        "split": spec.split,
        "core_id": spec.core_id,
        "check_family": spec.check_family,
        "make_target": bundle.make_target,
        "action": action,
        "candidate_dir": candidate_dir,
        "candidate_hash": stable_hash(
            {
                "core_id": spec.core_id,
                "check_family": spec.check_family,
                "make_target": bundle.make_target,
                "action": action,
                "candidate_dir": candidate_dir,
            }
        ),
    }
    return TypedCandidate(
        payload=payload,
        type_name="hardware.riscv_formal.rvfi_candidate",
        schema_version="hardware.riscv_formal.rvfi_candidate.v1",
        hashes=_candidate_artifact_hashes(payload, bundle, candidate_dir),
    )


def _candidate_artifact_hashes(payload: Mapping[str, Any], bundle: HardwareCandidateBundle, candidate_dir: str) -> Mapping[str, str]:
    hashes = {
        "candidate_payload_hash": stable_hash(payload),
        "task_bundle_metadata_hash": stable_hash(bundle.metadata),
    }
    candidate_dir_hash = path_fingerprint_hash(candidate_dir)
    if candidate_dir_hash:
        hashes["candidate_dir_fingerprint_hash"] = candidate_dir_hash
    task_root = str(bundle.metadata.get("task_root", ""))
    if task_root:
        genchecks_hash = path_fingerprint_hash(Path(task_root) / "checks" / "genchecks.py")
        if genchecks_hash:
            hashes["genchecks_hash"] = genchecks_hash
    return hashes


def _runtime_requirement_evidence_hashes(backend: HardwareFormalBackend) -> tuple[str, ...]:
    if not backend.real_backend:
        return ()
    return build_runtime_requirement_evidence_hashes(
        required_tools=HARDWARE_RISCV_FORMAL_REQUIRED_TOOLS,
        required_env_vars=HARDWARE_RISCV_FORMAL_REQUIRED_ENV_VARS,
    )


def _task_specs() -> tuple[HardwareTaskSpec, ...]:
    return (
        HardwareTaskSpec("train-rv32i-add", "train", "picorv32", "rv32i_add", "j1"),
        HardwareTaskSpec("heldout-rv32i-branch", "heldout", "picorv32", "rv32i_branch", "j1"),
        HardwareTaskSpec("heldout-rv32i-load-store", "heldout", "nerv", "rv32i_load_store", "j1"),
    )


def _task_row(spec: HardwareTaskSpec, baseline: tuple[Receipt, ...], learned: tuple[Receipt, ...]) -> HardwareRiscVFormalTaskRow:
    return HardwareRiscVFormalTaskRow(
        task_id=spec.task_id,
        split=spec.split,
        core_id=spec.core_id,
        check_family=spec.check_family,
        baseline_receipt_hashes=tuple(receipt.receipt_hash for receipt in baseline),
        learned_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned),
        baseline_verifier_calls=len(baseline),
        learned_verifier_calls=len(learned),
        baseline_success_count=sum(1 for receipt in baseline if receipt.committed),
        learned_success_count=sum(1 for receipt in learned if receipt.committed),
    )


def _claim_for_report(report: HardwareRiscVFormalAdapterReport) -> ClaimCertificate:
    return certify_claim(
        claim_id="hardware_riscv_formal_receipt_trained_reversible_adapter",
        claim_text=(
            "On held-out riscv-formal RVFI hardware tasks, a receipt-trained reversible proposer "
            "reduces hard-verifier calls while preserving zero invalid commits."
        ),
        evidence_grade=real_task_adapter_claim_evidence_grade(report),
        scope="hardware_riscv_formal_adapter",
        requirements=(
            requirement("backend_available", report.backend_available, missing=report.missing_requirements, error=report.backend_error),
            requirement("real_riscv_formal_backend", report.real_backend),
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
            requirement("hard_commit_only", report.hard_commit_only),
            requirement("train_eval_disjoint", report.train_eval_disjoint),
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


def _empty_report(backend: HardwareFormalBackend, *, backend_error: str = "") -> HardwareRiscVFormalAdapterReport:
    return HardwareRiscVFormalAdapterReport(
        schema_version=HARDWARE_RISCV_FORMAL_ADAPTER_REPORT_SCHEMA,
        experiment_id="hardware_riscv_formal_receipt_trained_adapter",
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
        source_urls=HARDWARE_RISCV_FORMAL_SOURCES,
        claim_boundary=HARDWARE_RISCV_FORMAL_CLAIM_BOUNDARY,
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
        "core_id": str(payload["core_id"]),
        "check_family": str(payload["check_family"]),
        "make_target": str(payload["make_target"]),
        "action": str(payload["action"]),
        "candidate_dir": str(payload["candidate_dir"]),
        "candidate_hash": str(payload["candidate_hash"]),
    }


def _tail(text: str | bytes, *, limit: int = 1000) -> str:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return str(text)[-limit:]


def result_as_dict(result: HardwareRiscVFormalAdapterResult) -> dict[str, Any]:
    return asdict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_hardware_riscv_formal_adapter_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
