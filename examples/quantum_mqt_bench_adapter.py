from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any, Mapping, Protocol

from trwm.claims import ClaimCertificate, certify_claim, requirement
from trwm.core import HardVerifierResult, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash
from trwm.evaluation import (
    LearningEvaluationCertificate,
    build_learning_evaluation_certificate,
    learning_evaluation_supports_claim,
    validate_learning_evaluation_certificate,
)
from trwm.learning import ReceiptTrainedReversibleProposer


QUANTUM_MQT_ADAPTER_REPORT_SCHEMA = "trwm.example.quantum_mqt_bench_adapter.v1"
QUANTUM_MQT_VERIFIER_ID = "mqt_qcec_equivalence_oracle"
QUANTUM_MQT_VERIFIER_VERSION = "1.0"
QUANTUM_MQT_SOURCES = (
    "https://github.com/munich-quantum-toolkit/bench",
    "https://mqt.readthedocs.io/projects/bench/en/latest/usage.html",
    "https://mqt.readthedocs.io/projects/qcec/en/stable/",
    "https://mqt.readthedocs.io/projects/qcec/en/v3.3.0/api/mqt/qcec/verify/index.html",
)
QUANTUM_MQT_CLAIM_BOUNDARY = (
    "Single-domain quantum adapter evidence only. A supported claim requires the real MQT Bench "
    "and MQT QCEC backend. Deterministic test doubles validate adapter mechanics but cannot "
    "support quantum benchmark performance claims or the full four-domain objective."
)


@dataclass(frozen=True)
class QuantumTaskSpec:
    task_id: str
    split: str
    benchmark: str
    circuit_size: int
    bad_benchmark: str


@dataclass(frozen=True)
class QuantumProgramBundle:
    task_id: str
    benchmark: str
    circuit_size: int
    original_program: str
    equivalent_program: str
    non_equivalent_program: str
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class QuantumVerificationResult:
    equivalent: bool
    metadata: Mapping[str, Any]


class QuantumEquivalenceBackend(Protocol):
    backend_id: str
    backend_version: str
    real_backend: bool

    def available(self) -> bool:
        ...

    def missing_requirements(self) -> tuple[str, ...]:
        ...

    def generate_task(self, spec: QuantumTaskSpec) -> QuantumProgramBundle:
        ...

    def verify_equivalent(self, original_program: str, candidate_program: str) -> QuantumVerificationResult:
        ...


@dataclass(frozen=True)
class QuantumMqtTaskRow:
    task_id: str
    split: str
    benchmark: str
    circuit_size: int
    baseline_receipt_hashes: tuple[str, ...]
    learned_receipt_hashes: tuple[str, ...]
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int


@dataclass(frozen=True)
class QuantumMqtBenchAdapterReport:
    schema_version: str
    experiment_id: str
    backend_id: str
    backend_version: str
    backend_available: bool
    real_backend: bool
    missing_requirements: tuple[str, ...]
    task_count: int
    train_task_ids: tuple[str, ...]
    held_out_task_ids: tuple[str, ...]
    rows: tuple[QuantumMqtTaskRow, ...]
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
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    ledger_head: str
    receipt_hashes: tuple[str, ...]
    source_urls: tuple[str, ...]
    claim_boundary: str


@dataclass(frozen=True)
class QuantumMqtBenchAdapterResult:
    report: QuantumMqtBenchAdapterReport
    learning_certificate: LearningEvaluationCertificate | None
    claim_certificate: ClaimCertificate


class MqtQuantumEquivalenceBackend:
    backend_id = "mqt.bench+mqt.qcec"
    backend_version = "dynamic"
    real_backend = True

    def available(self) -> bool:
        return not self.missing_requirements()

    def missing_requirements(self) -> tuple[str, ...]:
        missing = []
        for module in ("mqt.bench", "mqt.qcec"):
            try:
                found = importlib.util.find_spec(module) is not None
            except ModuleNotFoundError:
                found = False
            if not found:
                missing.append(module)
        return tuple(missing)

    def generate_task(self, spec: QuantumTaskSpec) -> QuantumProgramBundle:
        from mqt.bench import BenchmarkLevel, get_benchmark  # type: ignore[import-not-found]

        original = get_benchmark(spec.benchmark, BenchmarkLevel.ALG, spec.circuit_size)
        bad = get_benchmark(spec.bad_benchmark, BenchmarkLevel.ALG, spec.circuit_size)
        original_program = _circuit_to_program(original)
        bad_program = _circuit_to_program(bad)
        return QuantumProgramBundle(
            task_id=spec.task_id,
            benchmark=spec.benchmark,
            circuit_size=spec.circuit_size,
            original_program=original_program,
            equivalent_program=original_program,
            non_equivalent_program=bad_program,
            metadata={
                "benchmark": spec.benchmark,
                "bad_benchmark": spec.bad_benchmark,
                "circuit_size": spec.circuit_size,
            },
        )

    def verify_equivalent(self, original_program: str, candidate_program: str) -> QuantumVerificationResult:
        from mqt import qcec  # type: ignore[import-not-found]

        with tempfile.TemporaryDirectory(prefix="trwm-qcec-") as tmp:
            left = Path(tmp) / "original.qasm"
            right = Path(tmp) / "candidate.qasm"
            left.write_text(original_program, encoding="utf-8")
            right.write_text(candidate_program, encoding="utf-8")
            result = qcec.verify(str(left), str(right))
        raw = str(getattr(result, "equivalence", result))
        return QuantumVerificationResult(
            equivalent=_qcec_equivalent(raw),
            metadata={"qcec_equivalence": raw},
        )


class DeterministicQuantumEquivalenceBackend:
    """Test double for adapter mechanics. It is not real benchmark evidence."""

    backend_id = "deterministic.quantum.testdouble"
    backend_version = "1.0"
    real_backend = False

    def __init__(self, available: bool = True):
        self._available = bool(available)

    def available(self) -> bool:
        return self._available

    def missing_requirements(self) -> tuple[str, ...]:
        return () if self._available else ("mqt.bench", "mqt.qcec")

    def generate_task(self, spec: QuantumTaskSpec) -> QuantumProgramBundle:
        original = f"OPENQASM 3.0; // {spec.benchmark}:{spec.circuit_size}:{spec.task_id}"
        return QuantumProgramBundle(
            task_id=spec.task_id,
            benchmark=spec.benchmark,
            circuit_size=spec.circuit_size,
            original_program=original,
            equivalent_program=original,
            non_equivalent_program=f"OPENQASM 3.0; // {spec.bad_benchmark}:{spec.circuit_size}:non-equivalent",
            metadata={"deterministic_testdouble": True},
        )

    def verify_equivalent(self, original_program: str, candidate_program: str) -> QuantumVerificationResult:
        return QuantumVerificationResult(
            equivalent=original_program == candidate_program,
            metadata={"deterministic_testdouble": True},
        )


class QuantumMqtAdapter:
    verifier_id = QUANTUM_MQT_VERIFIER_ID
    verifier_version = QUANTUM_MQT_VERIFIER_VERSION

    def __init__(self, backend: QuantumEquivalenceBackend):
        self.backend = backend

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        if not self.backend.available():
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "quantum_backend_unavailable", "missing": self.backend.missing_requirements()},
                metadata={"backend_id": self.backend.backend_id},
            )
        result = self.backend.verify_equivalent(payload["original_program"], payload["candidate_program"])
        metadata = {
            "backend_id": self.backend.backend_id,
            "backend_version": self.backend.backend_version,
            "real_backend": self.backend.real_backend,
            "task_id": payload["task_id"],
            "action": payload["action"],
            "original_hash": payload["original_hash"],
            "candidate_hash": payload["candidate_hash"],
            **dict(result.metadata),
        }
        if result.equivalent:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": "qcec_not_equivalent", "repair": "equivalence_preserving_rewrite"},
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


def run_quantum_mqt_bench_adapter_experiment(
    backend: QuantumEquivalenceBackend | None = None,
) -> QuantumMqtBenchAdapterResult:
    backend = backend or MqtQuantumEquivalenceBackend()
    if not backend.available():
        report = _empty_report(backend)
        claim = _claim_for_report(report)
        return QuantumMqtBenchAdapterResult(report=report, learning_certificate=None, claim_certificate=claim)

    specs = _task_specs()
    bundles = {spec.task_id: backend.generate_task(spec) for spec in specs}
    train_specs = tuple(spec for spec in specs if spec.split == "train")
    heldout_specs = tuple(spec for spec in specs if spec.split == "heldout")
    adapter = QuantumMqtAdapter(backend)
    engine = TransactionEngine(adapter)
    proposer = ReceiptTrainedReversibleProposer()
    seed_state = {"committed_tasks": (), "last_candidate_hash": ""}
    state: Mapping[str, Any] = seed_state

    training_receipts: list[Receipt] = []
    baseline_by_task: dict[str, tuple[Receipt, ...]] = {}
    learned_by_task: dict[str, tuple[Receipt, ...]] = {}

    for spec in train_specs:
        outcome = _submit_until_commit(engine, state, spec, bundles[spec.task_id], arm="train", candidates=_ordered_candidates(spec, bundles[spec.task_id]))
        state = outcome.state
        training_receipts.extend(outcome.receipts)
        for receipt in outcome.receipts:
            proposer.update(receipt)

    snapshot = proposer.snapshot()
    for spec in heldout_specs:
        baseline = _submit_until_commit(engine, state, spec, bundles[spec.task_id], arm="baseline", candidates=_ordered_candidates(spec, bundles[spec.task_id]))
        state = baseline.state
        baseline_by_task[spec.task_id] = baseline.receipts
        learned_candidates = tuple(proposer.rank("quantum_mqt_equivalence", _ordered_candidates(spec, bundles[spec.task_id])))
        learned = _submit_until_commit(engine, state, spec, bundles[spec.task_id], arm="learned", candidates=learned_candidates)
        state = learned.state
        learned_by_task[spec.task_id] = learned.receipts

    baseline_receipts = tuple(receipt for receipts in baseline_by_task.values() for receipt in receipts)
    learned_receipts = tuple(receipt for receipts in learned_by_task.values() for receipt in receipts)
    all_receipts = (*tuple(training_receipts), *baseline_receipts, *learned_receipts)
    replay_ok, rollback_ok = _audit_replay_rollback(engine, seed_state)
    learning_certificate = build_learning_evaluation_certificate(
        claim_id="quantum_mqt_receipt_trained_reversible_call_reduction",
        learner_id=snapshot.learner_id,
        learner_snapshot_hash=snapshot.snapshot_hash,
        training_receipt_hashes=tuple(receipt.receipt_hash for receipt in training_receipts),
        evaluation_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned_receipts),
        baseline_name="static_non_equivalent_first",
        learned_name=snapshot.learner_id,
        baseline_verifier_calls=len(baseline_receipts),
        learned_verifier_calls=len(learned_receipts),
        baseline_success_count=sum(1 for receipt in baseline_receipts if receipt.committed),
        learned_success_count=sum(1 for receipt in learned_receipts if receipt.committed),
        verifier_budget=len(baseline_receipts),
        candidate_count=2 * len(heldout_specs),
        same_case_baseline=True,
        hard_commit_only=all(receipt.committed == receipt.hard_result.accepted for receipt in all_receipts),
        invalid_commit_count=engine.invalid_commit_count,
        ledger_audit=engine.ledger.audit(),
        replay_rollback_rate=1.0 if replay_ok and rollback_ok else 0.0,
        metrics={
            "backend_id": backend.backend_id,
            "real_backend": backend.real_backend,
            "held_out_task_ids": tuple(spec.task_id for spec in heldout_specs),
        },
    )
    report = QuantumMqtBenchAdapterReport(
        schema_version=QUANTUM_MQT_ADAPTER_REPORT_SCHEMA,
        experiment_id="quantum_mqt_bench_receipt_trained_adapter",
        backend_id=backend.backend_id,
        backend_version=backend.backend_version,
        backend_available=True,
        real_backend=backend.real_backend,
        missing_requirements=(),
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
        invalid_commit_count=engine.invalid_commit_count,
        baseline_verifier_calls=len(baseline_receipts),
        learned_verifier_calls=len(learned_receipts),
        baseline_success_count=sum(1 for receipt in baseline_receipts if receipt.committed),
        learned_success_count=sum(1 for receipt in learned_receipts if receipt.committed),
        verifier_call_reduction=len(baseline_receipts) - len(learned_receipts),
        verifier_call_gain=round(len(baseline_receipts) / len(learned_receipts), 12),
        hard_commit_only=learning_certificate.hard_commit_only,
        train_eval_disjoint=learning_certificate.train_eval_disjoint,
        replay_audit_ok=replay_ok,
        rollback_audit_ok=rollback_ok,
        ledger_audit_ok=engine.ledger.audit(),
        ledger_head=engine.ledger.head,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        source_urls=QUANTUM_MQT_SOURCES,
        claim_boundary=QUANTUM_MQT_CLAIM_BOUNDARY,
    )
    return QuantumMqtBenchAdapterResult(
        report=report,
        learning_certificate=learning_certificate,
        claim_certificate=_claim_for_report(report),
    )


@dataclass(frozen=True)
class _SubmitOutcome:
    state: Mapping[str, Any]
    receipts: tuple[Receipt, ...]


def _submit_until_commit(
    engine: TransactionEngine,
    state: Mapping[str, Any],
    spec: QuantumTaskSpec,
    bundle: QuantumProgramBundle,
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
                branch_id=f"quantum-mqt-{arm}-{spec.task_id}-{idx}-{action}",
                actions=({"task_id": spec.task_id, "arm": arm, "action": action},),
                model_version="quantum.mqt.receipt_trained_reversible.v1",
            ),
            candidate,
        )
        receipts.append(outcome.receipt)
        current = outcome.state
        if outcome.committed:
            break
    return _SubmitOutcome(state=current, receipts=tuple(receipts))


def _ordered_candidates(spec: QuantumTaskSpec, bundle: QuantumProgramBundle) -> tuple[TypedCandidate, ...]:
    return (
        _candidate(spec, bundle, action="non_equivalent_rewrite", candidate_program=bundle.non_equivalent_program),
        _candidate(spec, bundle, action="equivalence_preserving_rewrite", candidate_program=bundle.equivalent_program),
    )


def _candidate(
    spec: QuantumTaskSpec,
    bundle: QuantumProgramBundle,
    *,
    action: str,
    candidate_program: str,
) -> TypedCandidate:
    return TypedCandidate(
        payload={
            "context": "quantum_mqt_equivalence",
            "task_id": spec.task_id,
            "split": spec.split,
            "benchmark": spec.benchmark,
            "circuit_size": spec.circuit_size,
            "action": action,
            "original_program": bundle.original_program,
            "candidate_program": candidate_program,
            "original_hash": stable_hash(bundle.original_program),
            "candidate_hash": stable_hash(candidate_program),
        },
        type_name="quantum.mqt.equivalence_candidate",
        schema_version="quantum.mqt.equivalence_candidate.v1",
    )


def _task_specs() -> tuple[QuantumTaskSpec, ...]:
    return (
        QuantumTaskSpec("train-ghz-3", "train", "ghz", 3, "dj"),
        QuantumTaskSpec("heldout-qft-3", "heldout", "qft", 3, "ghz"),
        QuantumTaskSpec("heldout-ghz-4", "heldout", "ghz", 4, "dj"),
    )


def _task_row(spec: QuantumTaskSpec, baseline: tuple[Receipt, ...], learned: tuple[Receipt, ...]) -> QuantumMqtTaskRow:
    return QuantumMqtTaskRow(
        task_id=spec.task_id,
        split=spec.split,
        benchmark=spec.benchmark,
        circuit_size=spec.circuit_size,
        baseline_receipt_hashes=tuple(receipt.receipt_hash for receipt in baseline),
        learned_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned),
        baseline_verifier_calls=len(baseline),
        learned_verifier_calls=len(learned),
        baseline_success_count=sum(1 for receipt in baseline if receipt.committed),
        learned_success_count=sum(1 for receipt in learned if receipt.committed),
    )


def _claim_for_report(report: QuantumMqtBenchAdapterReport) -> ClaimCertificate:
    return certify_claim(
        claim_id="quantum_mqt_receipt_trained_reversible_adapter",
        claim_text=(
            "On held-out MQT Bench/QCEC quantum tasks, a receipt-trained reversible proposer "
            "reduces hard-verifier calls while preserving zero invalid commits."
        ),
        evidence_grade="G1" if report.backend_available and report.real_backend else "G0",
        scope="quantum_mqt_bench_adapter",
        requirements=(
            requirement("backend_available", report.backend_available, missing=report.missing_requirements),
            requirement("real_mqt_backend", report.real_backend),
            requirement("learning_certificate_valid", report.learning_certificate_valid),
            requirement("learning_certificate_supports_claim", report.learning_certificate_supports_claim),
            requirement("hard_verifier_calls_reduced", report.learned_verifier_calls < report.baseline_verifier_calls),
            requirement("success_preserved", report.learned_success_count == report.baseline_success_count and report.learned_success_count > 0),
            requirement("zero_invalid_commits", report.invalid_commit_count == 0),
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


def _empty_report(backend: QuantumEquivalenceBackend) -> QuantumMqtBenchAdapterReport:
    missing = backend.missing_requirements()
    return QuantumMqtBenchAdapterReport(
        schema_version=QUANTUM_MQT_ADAPTER_REPORT_SCHEMA,
        experiment_id="quantum_mqt_bench_receipt_trained_adapter",
        backend_id=backend.backend_id,
        backend_version=backend.backend_version,
        backend_available=False,
        real_backend=backend.real_backend,
        missing_requirements=missing,
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
        replay_audit_ok=False,
        rollback_audit_ok=False,
        ledger_audit_ok=False,
        ledger_head="",
        receipt_hashes=(),
        source_urls=QUANTUM_MQT_SOURCES,
        claim_boundary=QUANTUM_MQT_CLAIM_BOUNDARY,
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


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "context": str(payload["context"]),
        "task_id": str(payload["task_id"]),
        "split": str(payload["split"]),
        "benchmark": str(payload["benchmark"]),
        "circuit_size": int(payload["circuit_size"]),
        "action": str(payload["action"]),
        "original_program": str(payload["original_program"]),
        "candidate_program": str(payload["candidate_program"]),
        "original_hash": str(payload["original_hash"]),
        "candidate_hash": str(payload["candidate_hash"]),
    }


def _circuit_to_program(circuit: Any) -> str:
    try:
        from qiskit import qasm3  # type: ignore[import-not-found]

        return str(qasm3.dumps(circuit))
    except Exception:
        if hasattr(circuit, "qasm"):
            return str(circuit.qasm())
        return str(circuit)


def _qcec_equivalent(raw: str) -> bool:
    token = raw.strip().lower().split(".")[-1]
    return token in {"equivalent", "true", "1", "yes"}


def result_as_dict(result: QuantumMqtBenchAdapterResult) -> dict[str, Any]:
    return asdict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_quantum_mqt_bench_adapter_experiment()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
