from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from examples.common import (
    ExampleEvidenceCertificate,
    build_example_evidence_certificate,
    report_as_dict,
    validate_example_evidence_certificate,
)
from trwm.claims import ClaimCertificate, certify_claim, requirement, validate_claim_certificate
from trwm.core import HardVerifierResult, ProposalTrace, Receipt, TransactionEngine, TypedCandidate
from trwm.evaluation import (
    LearningEvaluationCertificate,
    build_learning_evaluation_certificate,
    learning_evaluation_supports_claim,
    validate_learning_evaluation_certificate,
)
from trwm.learning import ReceiptTrainedReversibleProposer, validate_receipt_trained_reversible_proposer_snapshot
from trwm.reversible import BlockToken, DeltaToken


BENCHMARK_SCHEMA = "trwm.example.receipt_trained_reversible_proposer_benchmark.v1"
BENCHMARK_VERIFIER_ID = "receipt_trained_reversible_benchmark_oracle"
BENCHMARK_VERIFIER_VERSION = "1.0"
BENCHMARK_SOURCES = (
    "https://ompl.kavrakilab.org/",
    "https://github.com/YosysHQ/riscv-formal",
    "https://github.com/rjust/defects4j",
    "https://github.com/munich-quantum-toolkit/bench",
    "https://mqt.readthedocs.io/projects/qcec/en/v3.4.0/index.html",
    "https://www.revlib.org/",
)
BENCHMARK_CLAIM_BOUNDARY = (
    "G1 local deterministic canary over robotics, hardware, program, and quantum task families. "
    "It proves the certificate shape and metric gate for receipt-trained reversible proposal "
    "ordering, not real robot safety, RISC-V core correctness, Defects4J repair, or quantum "
    "compiler equivalence on external benchmark artifacts."
)


@dataclass(frozen=True)
class BenchmarkTask:
    domain: str
    context: str
    train_task_id: str
    held_out_task_id: str
    hard_gate_key: str
    residual_kind: str
    rejected_action: str
    repair_action: str
    rejected_proposal_type: str
    committed_repair: str
    rejected_state: str
    repaired_state: str
    next_real_benchmark: str


@dataclass(frozen=True)
class BenchmarkDomainRow:
    domain: str
    context: str
    train_task_id: str
    held_out_task_id: str
    hard_gate_key: str
    residual_kind: str
    rejected_proposal_type: str
    committed_repair: str
    baseline_verifier_calls: int
    learned_verifier_calls: int
    baseline_success_count: int
    learned_success_count: int
    training_receipt_hashes: tuple[str, ...]
    baseline_receipt_hashes: tuple[str, ...]
    learned_receipt_hashes: tuple[str, ...]
    reversible_cycle_ok: bool
    next_real_benchmark: str


@dataclass(frozen=True)
class ReceiptTrainedReversibleBenchmarkReport:
    schema_version: str
    experiment_id: str
    evidence_grade: str
    domain_count: int
    domains: tuple[str, ...]
    train_task_ids: tuple[str, ...]
    held_out_task_ids: tuple[str, ...]
    rows: tuple[BenchmarkDomainRow, ...]
    verifier_id: str
    verifier_version: str
    learner_id: str
    learner_version: str
    learner_snapshot_hash: str
    learner_snapshot_valid: bool
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
    same_case_baseline: bool
    train_eval_disjoint: bool
    hard_commit_only: bool
    all_reversible_cycles_ok: bool
    replay_audit_ok: bool
    rollback_audit_ok: bool
    ledger_audit_ok: bool
    ledger_head: str
    receipt_hashes: tuple[str, ...]
    source_urls: tuple[str, ...]
    claim_boundary: str


@dataclass(frozen=True)
class ReceiptTrainedReversibleBenchmarkResult:
    report: ReceiptTrainedReversibleBenchmarkReport
    evidence_certificate: ExampleEvidenceCertificate
    learning_certificate: LearningEvaluationCertificate
    claim_certificate: ClaimCertificate


class ReversibleBenchmarkAdapter:
    verifier_id = BENCHMARK_VERIFIER_ID
    verifier_version = BENCHMARK_VERIFIER_VERSION

    def __init__(self, tasks: tuple[BenchmarkTask, ...]):
        self._tasks = {task.train_task_id: task for task in tasks}
        self._tasks.update({task.held_out_task_id: task for task in tasks})

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = _normalize_payload(candidate.payload)
        task = self._tasks[payload["task_id"]]
        block = _block_from_payload(payload)
        cycle_ok = _cycle_ok(payload["pre_state"], block)
        metadata = {
            "domain": task.domain,
            "context": task.context,
            "task_id": payload["task_id"],
            "hard_gate_key": task.hard_gate_key,
            "reversible_cycle_ok": cycle_ok,
        }
        if not cycle_ok:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "reversible_cycle_failure", "repair": task.repair_action},
                metadata=metadata,
            )
        if payload["action"] != task.repair_action:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": task.residual_kind, "repair": task.repair_action},
                metadata=metadata,
            )
        expected = _expected_post_state(payload["pre_state"], payload["state_key"], task.repaired_state)
        actual = block.apply(payload["pre_state"])
        if actual != expected:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"kind": "reversible_state_mismatch", "repair": task.repair_action},
                metadata=metadata,
            )
        return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)

    def apply_commit(self, state: Mapping[str, Any], candidate: TypedCandidate) -> dict[str, Any]:
        return _block_from_payload(_normalize_payload(candidate.payload)).apply(state)

    def replay(self, state: Mapping[str, Any], receipt: Receipt) -> dict[str, Any]:
        return _block_from_payload(_normalize_payload(receipt.replay_bundle["candidate_payload"])).apply(state)

    def rollback(self, _state: Mapping[str, Any], receipt: Receipt) -> dict[str, Any]:
        return dict(receipt.rollback_bundle["pre_state"])


def run_receipt_trained_reversible_proposer_benchmark() -> ReceiptTrainedReversibleBenchmarkResult:
    tasks = _benchmark_tasks()
    seed_state = _seed_state(tasks)
    adapter = ReversibleBenchmarkAdapter(tasks)
    engine = TransactionEngine(adapter)
    proposer = ReceiptTrainedReversibleProposer()
    state: Mapping[str, Any] = seed_state

    training_by_domain: dict[str, tuple[Receipt, ...]] = {}
    baseline_by_domain: dict[str, tuple[Receipt, ...]] = {}
    learned_by_domain: dict[str, tuple[Receipt, ...]] = {}
    cycle_flags: list[bool] = []

    for task in tasks:
        train_candidates = _candidates_for(task, arm="train")
        training_outcome = _submit_until_commit(engine, state, task, train_candidates, "train")
        state = training_outcome.state
        for receipt in training_outcome.receipts:
            proposer.update(receipt)
        training_by_domain[task.domain] = training_outcome.receipts
        cycle_flags.extend(_candidate_cycle_flags(seed_state, train_candidates))

    snapshot = proposer.snapshot()
    for task in tasks:
        baseline_candidates = _candidates_for(task, arm="baseline")
        baseline_outcome = _submit_until_commit(engine, state, task, baseline_candidates, "baseline")
        state = baseline_outcome.state
        baseline_by_domain[task.domain] = baseline_outcome.receipts
        cycle_flags.extend(_candidate_cycle_flags(seed_state, baseline_candidates))

        learned_candidates = tuple(proposer.rank(task.context, _candidates_for(task, arm="learned")))
        learned_outcome = _submit_until_commit(engine, state, task, learned_candidates, "learned")
        state = learned_outcome.state
        learned_by_domain[task.domain] = learned_outcome.receipts
        cycle_flags.extend(_candidate_cycle_flags(seed_state, learned_candidates))

    training_receipts = tuple(receipt for receipts in training_by_domain.values() for receipt in receipts)
    baseline_receipts = tuple(receipt for receipts in baseline_by_domain.values() for receipt in receipts)
    learned_receipts = tuple(receipt for receipts in learned_by_domain.values() for receipt in receipts)
    all_receipts = (*training_receipts, *baseline_receipts, *learned_receipts)
    baseline_success = sum(1 for receipt in baseline_receipts if receipt.committed)
    learned_success = sum(1 for receipt in learned_receipts if receipt.committed)
    replay_ok, rollback_ok = _audit_replay_rollback(engine, seed_state)
    learning_certificate = build_learning_evaluation_certificate(
        claim_id="receipt_trained_reversible_proposer_heldout_call_reduction",
        learner_id=snapshot.learner_id,
        learner_snapshot_hash=snapshot.snapshot_hash,
        training_receipt_hashes=tuple(receipt.receipt_hash for receipt in training_receipts),
        baseline_receipt_hashes=tuple(receipt.receipt_hash for receipt in baseline_receipts),
        evaluation_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned_receipts),
        baseline_name="static_rejected_first_same_heldout_tasks",
        learned_name=snapshot.learner_id,
        baseline_verifier_calls=len(baseline_receipts),
        learned_verifier_calls=len(learned_receipts),
        baseline_success_count=baseline_success,
        learned_success_count=learned_success,
        verifier_budget=len(baseline_receipts),
        candidate_count=sum(len(_candidates_for(task, arm="baseline")) for task in tasks),
        same_case_baseline=True,
        hard_commit_only=all(receipt.committed == receipt.hard_result.accepted for receipt in all_receipts),
        invalid_commit_count=engine.invalid_commit_count,
        ledger_audit=engine.ledger.audit(),
        replay_rollback_rate=1.0 if replay_ok and rollback_ok else 0.0,
        metrics={
            "baseline_submitted_actions": tuple(_receipt_action(receipt) for receipt in baseline_receipts),
            "learned_submitted_actions": tuple(_receipt_action(receipt) for receipt in learned_receipts),
            "domains": tuple(task.domain for task in tasks),
        },
    )
    rows = tuple(
        BenchmarkDomainRow(
            domain=task.domain,
            context=task.context,
            train_task_id=task.train_task_id,
            held_out_task_id=task.held_out_task_id,
            hard_gate_key=task.hard_gate_key,
            residual_kind=task.residual_kind,
            rejected_proposal_type=task.rejected_proposal_type,
            committed_repair=task.committed_repair,
            baseline_verifier_calls=len(baseline_by_domain[task.domain]),
            learned_verifier_calls=len(learned_by_domain[task.domain]),
            baseline_success_count=sum(1 for receipt in baseline_by_domain[task.domain] if receipt.committed),
            learned_success_count=sum(1 for receipt in learned_by_domain[task.domain] if receipt.committed),
            training_receipt_hashes=tuple(receipt.receipt_hash for receipt in training_by_domain[task.domain]),
            baseline_receipt_hashes=tuple(receipt.receipt_hash for receipt in baseline_by_domain[task.domain]),
            learned_receipt_hashes=tuple(receipt.receipt_hash for receipt in learned_by_domain[task.domain]),
            reversible_cycle_ok=all(_candidate_cycle_flags(seed_state, (*_candidates_for(task, "train"), *_candidates_for(task, "baseline"), *_candidates_for(task, "learned")))),
            next_real_benchmark=task.next_real_benchmark,
        )
        for task in tasks
    )
    report = ReceiptTrainedReversibleBenchmarkReport(
        schema_version=BENCHMARK_SCHEMA,
        experiment_id="receipt_trained_reversible_proposer_benchmark",
        evidence_grade="G1",
        domain_count=len(tasks),
        domains=tuple(task.domain for task in tasks),
        train_task_ids=tuple(task.train_task_id for task in tasks),
        held_out_task_ids=tuple(task.held_out_task_id for task in tasks),
        rows=rows,
        verifier_id=adapter.verifier_id,
        verifier_version=adapter.verifier_version,
        learner_id=snapshot.learner_id,
        learner_version=snapshot.learner_version,
        learner_snapshot_hash=snapshot.snapshot_hash,
        learner_snapshot_valid=validate_receipt_trained_reversible_proposer_snapshot(snapshot),
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
        baseline_success_count=baseline_success,
        learned_success_count=learned_success,
        verifier_call_reduction=len(baseline_receipts) - len(learned_receipts),
        verifier_call_gain=round(len(baseline_receipts) / len(learned_receipts), 12),
        same_case_baseline=True,
        train_eval_disjoint=learning_certificate.train_eval_disjoint,
        hard_commit_only=learning_certificate.hard_commit_only,
        all_reversible_cycles_ok=all(cycle_flags),
        replay_audit_ok=replay_ok,
        rollback_audit_ok=rollback_ok,
        ledger_audit_ok=engine.ledger.audit(),
        ledger_head=engine.ledger.head,
        receipt_hashes=tuple(receipt.receipt_hash for receipt in all_receipts),
        source_urls=BENCHMARK_SOURCES,
        claim_boundary=BENCHMARK_CLAIM_BOUNDARY,
    )
    evidence = build_example_evidence_certificate(
        report,
        domain="cross_domain_receipt_trained_reversible_proposer",
        verifier_id=report.verifier_id,
        verifier_version=report.verifier_version,
        ledger_head=report.ledger_head,
        receipt_hashes=report.receipt_hashes,
        committed_count=report.committed_count,
        rejected_count=report.rejected_count,
        replay_audit_ok=report.replay_audit_ok,
        rollback_audit_ok=report.rollback_audit_ok,
        ledger_audit_ok=report.ledger_audit_ok,
        invalid_commit_count=report.invalid_commit_count,
        hard_gate_keys=tuple(row.hard_gate_key for row in report.rows),
        residual_kinds=tuple(row.residual_kind for row in report.rows),
        claim_boundary=report.claim_boundary,
        sources=report.source_urls,
    )
    claim = certify_claim(
        claim_id="receipt_trained_reversible_proposer_heldout_g1",
        claim_text=(
            "A receipt-trained reversible proposer reduces hard-verifier calls while preserving "
            "zero invalid commits on held-out local robotics, hardware, program, and quantum canaries."
        ),
        evidence_grade="G1",
        scope="local_cross_domain_canary",
        requirements=(
            requirement("four_domains", report.domain_count == 4),
            requirement("evidence_certificate_valid", validate_example_evidence_certificate(evidence, report)),
            requirement("learning_certificate_valid", report.learning_certificate_valid),
            requirement("learning_certificate_supports_claim", report.learning_certificate_supports_claim),
            requirement("success_preserved", report.learned_success_count == report.baseline_success_count == report.domain_count),
            requirement("hard_verifier_calls_reduced", report.learned_verifier_calls < report.baseline_verifier_calls),
            requirement("zero_invalid_commits", report.invalid_commit_count == 0),
            requirement("hard_commit_only", report.hard_commit_only),
            requirement("replay_rollback_ok", report.replay_audit_ok and report.rollback_audit_ok),
            requirement("all_reversible_cycles_ok", report.all_reversible_cycles_ok),
            requirement("heldout_disjoint_from_training", report.train_eval_disjoint and set(report.train_task_ids).isdisjoint(report.held_out_task_ids)),
        ),
        metrics={
            "baseline_verifier_calls": report.baseline_verifier_calls,
            "learned_verifier_calls": report.learned_verifier_calls,
            "verifier_call_reduction": report.verifier_call_reduction,
            "verifier_call_gain": report.verifier_call_gain,
            "invalid_commit_count": report.invalid_commit_count,
        },
        boundary=report.claim_boundary,
        sources=report.source_urls,
    )
    return ReceiptTrainedReversibleBenchmarkResult(
        report=report,
        evidence_certificate=evidence,
        learning_certificate=learning_certificate,
        claim_certificate=claim,
    )


@dataclass(frozen=True)
class _SubmitOutcome:
    state: Mapping[str, Any]
    receipts: tuple[Receipt, ...]


def _submit_until_commit(
    engine: TransactionEngine,
    state: Mapping[str, Any],
    task: BenchmarkTask,
    candidates: tuple[TypedCandidate, ...],
    arm: str,
) -> _SubmitOutcome:
    current = state
    receipts: list[Receipt] = []
    for idx, candidate in enumerate(candidates):
        action = str(candidate.payload["action"])
        outcome = engine.transact(
            current,
            ProposalTrace(
                branch_id=f"{task.domain}-{arm}-{idx}-{action}",
                actions=({"domain": task.domain, "arm": arm, "action": action},),
                model_version="receipt.trained.reversible.proposer.v1",
            ),
            candidate,
        )
        receipts.append(outcome.receipt)
        current = outcome.state
        if outcome.committed:
            break
    return _SubmitOutcome(state=current, receipts=tuple(receipts))


def _benchmark_tasks() -> tuple[BenchmarkTask, ...]:
    return (
        BenchmarkTask(
            domain="robotics",
            context="robotics_motion_planning",
            train_task_id="robotics_corridor_train",
            held_out_task_id="robotics_fixture_shelf_heldout",
            hard_gate_key="collision_free_path_and_step_bound",
            residual_kind="collision_clearance_violation",
            rejected_action="straight_line_collision",
            repair_action="signed_distance_detour",
            rejected_proposal_type="short path through occupied swept volume",
            committed_repair="signed-distance detour trajectory",
            rejected_state="collision_path",
            repaired_state="detour_path",
            next_real_benchmark="OMPL MotionBenchMaker or Planner Arena motion-planning tasks",
        ),
        BenchmarkTask(
            domain="hardware",
            context="hardware_formal",
            train_task_id="hardware_rvfi_add_train",
            held_out_task_id="hardware_rvfi_branch_heldout",
            hard_gate_key="rvfi_instruction_assertions",
            residual_kind="isa_equivalence_violation",
            rejected_action="rvfi_without_carry_fix",
            repair_action="rvfi_carry_corrected",
            rejected_proposal_type="RTL patch that violates instruction-level formal assertion",
            committed_repair="RVFI-consistent carry/control repair",
            rejected_state="assertion_failed",
            repaired_state="assertion_holds",
            next_real_benchmark="riscv-formal RVFI instruction checks on open RISC-V cores",
        ),
        BenchmarkTask(
            domain="program",
            context="program_repair",
            train_task_id="program_operator_train",
            held_out_task_id="program_trigger_test_heldout",
            hard_gate_key="triggering_and_relevant_tests",
            residual_kind="test_failure",
            rejected_action="single_operator_patch",
            repair_action="triggering_test_patch",
            rejected_proposal_type="source patch that still fails the triggering test",
            committed_repair="test-suite preserving source repair",
            rejected_state="tests_fail",
            repaired_state="tests_pass",
            next_real_benchmark="Defects4J active bug ids with triggering and relevant tests",
        ),
        BenchmarkTask(
            domain="quantum",
            context="quantum_circuit_equivalence",
            train_task_id="quantum_rewrite_train",
            held_out_task_id="quantum_transpile_heldout",
            hard_gate_key="unitary_equivalence_and_target_basis",
            residual_kind="circuit_equivalence_failure",
            rejected_action="depth_rewrite_non_equivalent",
            repair_action="equivalence_preserving_rewrite",
            rejected_proposal_type="quantum rewrite that changes the represented operation",
            committed_repair="basis-compatible equivalent rewrite",
            rejected_state="not_equivalent",
            repaired_state="equivalent",
            next_real_benchmark="MQT Bench circuits verified with MQT QCEC and RevLib reversible circuits",
        ),
    )


def _seed_state(tasks: tuple[BenchmarkTask, ...]) -> dict[str, str]:
    state: dict[str, str] = {}
    for task in tasks:
        for arm in ("train", "baseline", "learned"):
            state[_state_key(task, arm)] = "initial"
    return state


def _candidates_for(task: BenchmarkTask, arm: str) -> tuple[TypedCandidate, ...]:
    if arm == "train":
        task_id = task.train_task_id
    else:
        task_id = task.held_out_task_id
    return (
        _make_candidate(task, arm, task_id, task.rejected_action, task.rejected_state),
        _make_candidate(task, arm, task_id, task.repair_action, task.repaired_state),
    )


def _make_candidate(task: BenchmarkTask, arm: str, task_id: str, action: str, after: str) -> TypedCandidate:
    state_key = _state_key(task, arm)
    return TypedCandidate(
        payload={
            "domain": task.domain,
            "context": task.context,
            "task_id": task_id,
            "arm": arm,
            "state_key": state_key,
            "action": action,
            "pre_state": {state_key: "initial"},
            "reversible_tokens": ({"key": state_key, "before": "initial", "after": after},),
        },
        type_name="receipt_trained_reversible.benchmark_candidate",
        schema_version="receipt_trained_reversible.benchmark_candidate.v1",
    )


def _state_key(task: BenchmarkTask, arm: str) -> str:
    return f"{task.domain}:{arm}"


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    state_key = str(payload["state_key"])
    action = str(payload["action"])
    task_id = str(payload["task_id"])
    pre_state = {str(key): str(value) for key, value in dict(payload["pre_state"]).items()}
    tokens = tuple(dict(token) for token in payload["reversible_tokens"])
    return {
        "domain": str(payload["domain"]),
        "context": str(payload["context"]),
        "task_id": task_id,
        "state_key": state_key,
        "action": action,
        "pre_state": pre_state,
        "reversible_tokens": tokens,
    }


def _block_from_payload(payload: Mapping[str, Any]) -> BlockToken:
    return BlockToken.of(
        DeltaToken(str(token["key"]), str(token["before"]), str(token["after"]))
        for token in payload["reversible_tokens"]
    )


def _cycle_ok(pre_state: Mapping[str, Any], block: BlockToken) -> bool:
    try:
        return block.inverse().apply(block.apply(pre_state)) == dict(pre_state)
    except Exception:
        return False


def _candidate_cycle_flags(seed_state: Mapping[str, Any], candidates: tuple[TypedCandidate, ...]) -> tuple[bool, ...]:
    flags = []
    for candidate in candidates:
        payload = _normalize_payload(candidate.payload)
        block = _block_from_payload(payload)
        flags.append(_cycle_ok({payload["state_key"]: seed_state[payload["state_key"]]}, block))
    return tuple(flags)


def _expected_post_state(pre_state: Mapping[str, Any], state_key: str, repaired_state: str) -> dict[str, Any]:
    out = dict(pre_state)
    out[state_key] = repaired_state
    return out


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


def _receipt_action(receipt: Receipt) -> str:
    payload = receipt.replay_bundle["candidate_payload"]
    return str(payload["action"])


def result_as_dict(result: ReceiptTrainedReversibleBenchmarkResult) -> dict[str, Any]:
    return report_as_dict(result)


def main() -> None:
    print(json.dumps(result_as_dict(run_receipt_trained_reversible_proposer_benchmark()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
