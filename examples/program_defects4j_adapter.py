from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, Protocol

from examples.real_task_adapter_evidence import (
    RealTaskAdapterEvidenceCertificate,
    build_real_task_adapter_evidence_certificate,
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


PROGRAM_DEFECTS4J_ADAPTER_REPORT_SCHEMA = "trwm.example.program_defects4j_adapter.v1"
PROGRAM_DEFECTS4J_VERIFIER_ID = "defects4j_compile_relevant_tests"
PROGRAM_DEFECTS4J_VERIFIER_VERSION = "1.0"
PROGRAM_DEFECTS4J_REQUIRED_TOOLS = ("defects4j", "java", "git", "svn", "perl")
PROGRAM_DEFECTS4J_SOURCES = (
    "https://defects4j.org/",
    "https://defects4j.org/html_doc/defects4j.html",
    "https://defects4j.org/html_doc/d4j/d4j-checkout.html",
    "https://defects4j.org/html_doc/d4j/d4j-test.html",
)
PROGRAM_DEFECTS4J_CLAIM_BOUNDARY = (
    "Single-domain program adapter evidence only. A supported claim requires the real Defects4J "
    "CLI backend. This adapter compares buggy-version and fixed-version candidates through "
    "Defects4J compile plus relevant-test execution; deterministic test doubles validate mechanics "
    "but cannot support program-repair performance claims or the full four-domain objective."
)


@dataclass(frozen=True)
class ProgramTaskSpec:
    task_id: str
    split: str
    project_id: str
    bug_id: int


@dataclass(frozen=True)
class ProgramVersionBundle:
    task_id: str
    project_id: str
    bug_id: int
    buggy_version_id: str
    fixed_version_id: str
    verifier_scope: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class ProgramVerificationResult:
    accepted: bool
    residual_kind: str
    failing_tests: tuple[str, ...]
    metadata: Mapping[str, Any]


class ProgramRepairBackend(Protocol):
    backend_id: str
    backend_version: str
    real_backend: bool

    def available(self) -> bool:
        ...

    def missing_requirements(self) -> tuple[str, ...]:
        ...

    def generate_task(self, spec: ProgramTaskSpec) -> ProgramVersionBundle:
        ...

    def verify_candidate(self, payload: Mapping[str, Any]) -> ProgramVerificationResult:
        ...


@dataclass(frozen=True)
class ProgramDefects4JTaskRow:
    task_id: str
    split: str
    project_id: str
    bug_id: int
    baseline_receipt_hashes: tuple[str, ...]
    learned_receipt_hashes: tuple[str, ...]
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int


@dataclass(frozen=True)
class ProgramDefects4JAdapterReport:
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
    rows: tuple[ProgramDefects4JTaskRow, ...]
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
class ProgramDefects4JAdapterResult:
    report: ProgramDefects4JAdapterReport
    learning_certificate: LearningEvaluationCertificate | None
    evidence_certificate: RealTaskAdapterEvidenceCertificate
    claim_certificate: ClaimCertificate


@dataclass(frozen=True)
class _CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout_tail: str
    stderr_tail: str


class Defects4JProgramBackend:
    backend_id = "defects4j.cli"
    backend_version = "dynamic"
    real_backend = True

    def __init__(self, *, timeout_seconds: int = 300):
        self.timeout_seconds = int(timeout_seconds)

    def available(self) -> bool:
        return not self.missing_requirements()

    def missing_requirements(self) -> tuple[str, ...]:
        return tuple(tool for tool in PROGRAM_DEFECTS4J_REQUIRED_TOOLS if shutil.which(tool) is None)

    def generate_task(self, spec: ProgramTaskSpec) -> ProgramVersionBundle:
        bug = int(spec.bug_id)
        return ProgramVersionBundle(
            task_id=spec.task_id,
            project_id=spec.project_id,
            bug_id=bug,
            buggy_version_id=f"{bug}b",
            fixed_version_id=f"{bug}f",
            verifier_scope="defects4j compile + defects4j test -r",
            metadata={
                "project_id": spec.project_id,
                "bug_id": bug,
                "source": "Defects4J version candidates",
            },
        )

    def verify_candidate(self, payload: Mapping[str, Any]) -> ProgramVerificationResult:
        data = _normalize_payload(payload)
        if not self.available():
            return ProgramVerificationResult(
                accepted=False,
                residual_kind="defects4j_backend_unavailable",
                failing_tests=(),
                metadata={"backend_id": self.backend_id, "missing": self.missing_requirements()},
            )

        with tempfile.TemporaryDirectory(prefix="trwm-defects4j-") as tmp:
            work_dir = Path(tmp) / "checkout"
            checkout = self._run(
                (
                    "defects4j",
                    "checkout",
                    "-p",
                    data["project_id"],
                    "-v",
                    data["version_id"],
                    "-w",
                    str(work_dir),
                ),
                cwd=None,
            )
            if checkout.returncode != 0:
                return _program_reject("defects4j_checkout_failed", (), {"checkout": asdict(checkout)})

            compile_result = self._run(("defects4j", "compile"), cwd=work_dir)
            if compile_result.returncode != 0:
                return _program_reject(
                    "defects4j_compile_failed",
                    (),
                    {"checkout": asdict(checkout), "compile": asdict(compile_result)},
                )

            test_result = self._run(("defects4j", "test", "-r"), cwd=work_dir)
            failing_tests = _read_failing_tests(work_dir)
            accepted = test_result.returncode == 0 and not failing_tests and not _stdout_reports_failures(test_result.stdout_tail)
            metadata = {
                "checkout": asdict(checkout),
                "compile": asdict(compile_result),
                "test": asdict(test_result),
                "workdir_deleted": True,
                "version_id": data["version_id"],
            }
            if accepted:
                return ProgramVerificationResult(
                    accepted=True,
                    residual_kind="",
                    failing_tests=(),
                    metadata=metadata,
                )
            return ProgramVerificationResult(
                accepted=False,
                residual_kind="defects4j_relevant_tests_failed",
                failing_tests=failing_tests,
                metadata=metadata,
            )

    def _run(self, command: tuple[str, ...], *, cwd: Path | None) -> _CommandResult:
        env = dict(os.environ)
        env.setdefault("TZ", "America/Los_Angeles")
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd) if cwd is not None else None,
                env=env,
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


class DeterministicDefects4JBackend:
    """Test double for adapter mechanics. It is not real Defects4J evidence."""

    backend_id = "deterministic.defects4j.testdouble"
    backend_version = "1.0"
    real_backend = False

    def __init__(self, available: bool = True):
        self._available = bool(available)

    def available(self) -> bool:
        return self._available

    def missing_requirements(self) -> tuple[str, ...]:
        return () if self._available else PROGRAM_DEFECTS4J_REQUIRED_TOOLS

    def generate_task(self, spec: ProgramTaskSpec) -> ProgramVersionBundle:
        bug = int(spec.bug_id)
        return ProgramVersionBundle(
            task_id=spec.task_id,
            project_id=spec.project_id,
            bug_id=bug,
            buggy_version_id=f"{bug}b",
            fixed_version_id=f"{bug}f",
            verifier_scope="deterministic fixed-version test double",
            metadata={"deterministic_testdouble": True},
        )

    def verify_candidate(self, payload: Mapping[str, Any]) -> ProgramVerificationResult:
        data = _normalize_payload(payload)
        accepted = data["version_id"].endswith("f")
        if accepted:
            return ProgramVerificationResult(
                accepted=True,
                residual_kind="",
                failing_tests=(),
                metadata={"deterministic_testdouble": True},
            )
        return ProgramVerificationResult(
            accepted=False,
            residual_kind="defects4j_relevant_tests_failed",
            failing_tests=(f"{data['project_id']}Bug{data['bug_id']}::trigger",),
            metadata={"deterministic_testdouble": True},
        )


class ProgramDefects4JAdapter:
    verifier_id = PROGRAM_DEFECTS4J_VERIFIER_ID
    verifier_version = PROGRAM_DEFECTS4J_VERIFIER_VERSION

    def __init__(self, backend: ProgramRepairBackend):
        self.backend = backend

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        if not self.backend.available():
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "defects4j_backend_unavailable", "missing": self.backend.missing_requirements()},
                metadata={"backend_id": self.backend.backend_id},
            )
        result = self.backend.verify_candidate(payload)
        metadata = {
            "backend_id": self.backend.backend_id,
            "backend_version": self.backend.backend_version,
            "real_backend": self.backend.real_backend,
            "task_id": payload["task_id"],
            "project_id": payload["project_id"],
            "bug_id": payload["bug_id"],
            "version_id": payload["version_id"],
            "action": payload["action"],
            "candidate_hash": payload["candidate_hash"],
            **dict(result.metadata),
        }
        if result.accepted:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={
                "kind": result.residual_kind or "defects4j_candidate_rejected",
                "failing_tests": result.failing_tests,
                "repair": "fixed_version_candidate",
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


def run_program_defects4j_adapter_experiment(
    backend: ProgramRepairBackend | None = None,
) -> ProgramDefects4JAdapterResult:
    backend = backend or Defects4JProgramBackend()
    if not backend.available():
        report = _empty_report(backend)
        return _result_for_report(report, None)

    try:
        return _run_available_backend(backend)
    except Exception as exc:
        report = _empty_report(backend, backend_error=f"{type(exc).__name__}:{_tail(str(exc), limit=400)}")
        return _result_for_report(report, None)


def _run_available_backend(backend: ProgramRepairBackend) -> ProgramDefects4JAdapterResult:
    specs = _task_specs()
    bundles = {spec.task_id: backend.generate_task(spec) for spec in specs}
    train_specs = tuple(spec for spec in specs if spec.split == "train")
    heldout_specs = tuple(spec for spec in specs if spec.split == "heldout")
    training_adapter = ProgramDefects4JAdapter(backend)
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
    baseline_engine = TransactionEngine(ProgramDefects4JAdapter(backend))
    learned_engine = TransactionEngine(ProgramDefects4JAdapter(backend))
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
        learned_candidates = tuple(proposer.rank("program_defects4j_repair", _ordered_candidates(spec, bundles[spec.task_id])))
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
    backend_execution_evidence_ok, backend_execution_evidence_hashes = receipt_backend_execution_evidence("program", all_receipts)
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
        claim_id="program_defects4j_receipt_trained_reversible_call_reduction",
        learner_id=snapshot.learner_id,
        learner_snapshot_hash=snapshot.snapshot_hash,
        training_receipt_hashes=tuple(receipt.receipt_hash for receipt in training_receipts),
        baseline_receipt_hashes=tuple(receipt.receipt_hash for receipt in baseline_receipts),
        evaluation_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned_receipts),
        baseline_name="static_buggy_version_first",
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
    report = ProgramDefects4JAdapterReport(
        schema_version=PROGRAM_DEFECTS4J_ADAPTER_REPORT_SCHEMA,
        experiment_id="program_defects4j_receipt_trained_adapter",
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
        source_urls=PROGRAM_DEFECTS4J_SOURCES,
        claim_boundary=PROGRAM_DEFECTS4J_CLAIM_BOUNDARY,
    )
    return _result_for_report(report, learning_certificate)


def _result_for_report(
    report: ProgramDefects4JAdapterReport,
    learning_certificate: LearningEvaluationCertificate | None,
) -> ProgramDefects4JAdapterResult:
    claim = _claim_for_report(report)
    evidence = build_real_task_adapter_evidence_certificate(
        domain="program",
        report=report,
        learning_certificate=learning_certificate,
        claim_certificate=claim,
    )
    return ProgramDefects4JAdapterResult(
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
    spec: ProgramTaskSpec,
    bundle: ProgramVersionBundle,
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
                branch_id=f"program-defects4j-{arm}-{spec.task_id}-{idx}-{action}",
                actions=({"task_id": spec.task_id, "arm": arm, "action": action},),
                model_version="program.defects4j.receipt_trained_reversible.v1",
            ),
            candidate,
        )
        receipts.append(outcome.receipt)
        current = outcome.state
        if outcome.committed:
            break
    return _SubmitOutcome(state=current, receipts=tuple(receipts))


def _ordered_candidates(spec: ProgramTaskSpec, bundle: ProgramVersionBundle) -> tuple[TypedCandidate, ...]:
    return (
        _candidate(spec, bundle, action="buggy_version_candidate", version_id=bundle.buggy_version_id),
        _candidate(spec, bundle, action="fixed_version_candidate", version_id=bundle.fixed_version_id),
    )


def _candidate(spec: ProgramTaskSpec, bundle: ProgramVersionBundle, *, action: str, version_id: str) -> TypedCandidate:
    payload = {
        "context": "program_defects4j_repair",
        "task_id": spec.task_id,
        "split": spec.split,
        "project_id": spec.project_id,
        "bug_id": int(spec.bug_id),
        "version_id": version_id,
        "action": action,
        "verifier_scope": bundle.verifier_scope,
        "candidate_hash": stable_hash(
            {
                "project_id": spec.project_id,
                "bug_id": int(spec.bug_id),
                "version_id": version_id,
                "action": action,
            }
        ),
    }
    return TypedCandidate(
        payload=payload,
        type_name="program.defects4j.version_candidate",
        schema_version="program.defects4j.version_candidate.v1",
        hashes=_candidate_artifact_hashes(payload, bundle),
    )


def _candidate_artifact_hashes(payload: Mapping[str, Any], bundle: ProgramVersionBundle) -> Mapping[str, str]:
    return {
        "candidate_payload_hash": stable_hash(payload),
        "task_bundle_metadata_hash": stable_hash(bundle.metadata),
        "defects4j_version_hash": stable_hash(
            {
                "project_id": bundle.project_id,
                "bug_id": int(bundle.bug_id),
                "version_id": payload["version_id"],
            }
        ),
        "verifier_scope_hash": stable_hash(bundle.verifier_scope),
    }


def _runtime_requirement_evidence_hashes(backend: ProgramRepairBackend) -> tuple[str, ...]:
    if not backend.real_backend:
        return ()
    return build_runtime_requirement_evidence_hashes(required_tools=PROGRAM_DEFECTS4J_REQUIRED_TOOLS)


def _task_specs() -> tuple[ProgramTaskSpec, ...]:
    return (
        ProgramTaskSpec("train-lang-1", "train", "Lang", 1),
        ProgramTaskSpec("heldout-math-5", "heldout", "Math", 5),
        ProgramTaskSpec("heldout-chart-1", "heldout", "Chart", 1),
    )


def _task_row(spec: ProgramTaskSpec, baseline: tuple[Receipt, ...], learned: tuple[Receipt, ...]) -> ProgramDefects4JTaskRow:
    return ProgramDefects4JTaskRow(
        task_id=spec.task_id,
        split=spec.split,
        project_id=spec.project_id,
        bug_id=int(spec.bug_id),
        baseline_receipt_hashes=tuple(receipt.receipt_hash for receipt in baseline),
        learned_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned),
        baseline_verifier_calls=len(baseline),
        learned_verifier_calls=len(learned),
        baseline_success_count=sum(1 for receipt in baseline if receipt.committed),
        learned_success_count=sum(1 for receipt in learned if receipt.committed),
    )


def _claim_for_report(report: ProgramDefects4JAdapterReport) -> ClaimCertificate:
    return certify_claim(
        claim_id="program_defects4j_receipt_trained_reversible_adapter",
        claim_text=(
            "On held-out Defects4J program tasks, a receipt-trained reversible proposer reduces "
            "hard-verifier calls while preserving zero invalid commits."
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
        scope="program_defects4j_adapter",
        requirements=(
            requirement("backend_available", report.backend_available, missing=report.missing_requirements, error=report.backend_error),
            requirement("real_defects4j_backend", report.real_backend),
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


def _empty_report(backend: ProgramRepairBackend, *, backend_error: str = "") -> ProgramDefects4JAdapterReport:
    return ProgramDefects4JAdapterReport(
        schema_version=PROGRAM_DEFECTS4J_ADAPTER_REPORT_SCHEMA,
        experiment_id="program_defects4j_receipt_trained_adapter",
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
        source_urls=PROGRAM_DEFECTS4J_SOURCES,
        claim_boundary=PROGRAM_DEFECTS4J_CLAIM_BOUNDARY,
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
        "project_id": str(payload["project_id"]),
        "bug_id": int(payload["bug_id"]),
        "version_id": str(payload["version_id"]),
        "action": str(payload["action"]),
        "verifier_scope": str(payload["verifier_scope"]),
        "candidate_hash": str(payload["candidate_hash"]),
    }


def _program_reject(kind: str, failing_tests: tuple[str, ...], metadata: Mapping[str, Any]) -> ProgramVerificationResult:
    return ProgramVerificationResult(accepted=False, residual_kind=kind, failing_tests=failing_tests, metadata=metadata)


def _read_failing_tests(work_dir: Path) -> tuple[str, ...]:
    failing = work_dir / "failing_tests"
    if not failing.exists():
        return ()
    lines = tuple(line.strip() for line in failing.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    return lines


def _stdout_reports_failures(stdout_tail: str) -> bool:
    for line in stdout_tail.splitlines():
        if "Failing tests:" not in line:
            continue
        suffix = line.split("Failing tests:", 1)[1].strip()
        try:
            return int(suffix) > 0
        except ValueError:
            return bool(suffix)
    return False


def _tail(text: str | bytes, *, limit: int = 1000) -> str:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return str(text)[-limit:]


def result_as_dict(result: ProgramDefects4JAdapterResult) -> dict[str, Any]:
    return asdict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_program_defects4j_adapter_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
