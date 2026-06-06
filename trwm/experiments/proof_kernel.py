from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
import random
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


@dataclass(frozen=True)
class ProofRule:
    rule_id: str
    premises: tuple[str, ...]
    conclusion: str


@dataclass(frozen=True)
class ProofProblem:
    hypotheses: tuple[str, ...]
    rules: tuple[ProofRule, ...]
    goal: str


@dataclass(frozen=True)
class ProofState:
    problem: ProofProblem
    proven: bool = False
    derived: tuple[str, ...] = ()
    proof: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProofEpisodeResult:
    calls: int
    success: bool
    audit_ok: bool
    replay_rollback_ok: bool


@dataclass(frozen=True)
class ProofKernelReport:
    episodes: int
    rule_count: int
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    repair_success_rate: float
    ledger_audit_rate: float
    replay_rollback_rate: float
    invalid_commit_count: int
    learned_residual_kinds: Mapping[str, int]


class HornProofAdapter:
    verifier_id = "horn_proof_kernel"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        problem = normalize_problem(payload["problem"])
        script = tuple(str(rule_id) for rule_id in payload["script"])
        metadata = {"cost": payload.get("cost", len(script)), "script_length": len(script)}
        rules = {rule.rule_id: rule for rule in problem.rules}
        facts = set(problem.hypotheses)
        used: set[str] = set()
        for index, rule_id in enumerate(script):
            rule = rules.get(rule_id)
            if rule is None:
                return self._reject("unknown_rule", {"rule_id": rule_id, "step": index}, metadata)
            if rule_id in used:
                repair = _next_applicable_rule(problem, facts, used)
                return self._reject("duplicate_rule", {"rule_id": rule_id, "step": index, "repair": repair}, metadata)
            missing = tuple(premise for premise in rule.premises if premise not in facts)
            if missing:
                repair = _next_applicable_rule(problem, facts, used)
                return self._reject(
                    "missing_premise",
                    {"rule_id": rule_id, "step": index, "missing": missing, "repair": repair},
                    metadata,
                )
            facts.add(rule.conclusion)
            used.add(rule_id)
        if problem.goal in facts:
            return HardVerifierResult.accept(
                self.verifier_id,
                self.verifier_version,
                metadata={**metadata, "derived_count": len(facts)},
            )
        repair = _next_applicable_rule(problem, facts, used)
        return self._reject(
            "goal_not_derived",
            {"goal": problem.goal, "derived": tuple(sorted(facts)), "repair": repair},
            metadata,
        )

    def apply_commit(self, state: ProofState, candidate: TypedCandidate) -> ProofState:
        current = normalize_state(state)
        problem = normalize_problem(candidate.payload["problem"])
        if current.problem != problem:
            raise ValueError("candidate problem does not match current proof state")
        script = tuple(str(rule_id) for rule_id in candidate.payload["script"])
        derived = derive_facts(problem, script)
        return ProofState(problem=problem, proven=True, derived=tuple(sorted(derived)), proof=script)

    def replay(self, state: ProofState, receipt: Receipt) -> ProofState:
        current = normalize_state(state)
        payload = receipt.replay_bundle["candidate_payload"]
        problem = normalize_problem(payload["problem"])
        if current.problem != problem:
            raise ValueError("receipt problem does not match replay proof state")
        script = tuple(str(rule_id) for rule_id in payload["script"])
        derived = derive_facts(problem, script)
        return ProofState(problem=problem, proven=True, derived=tuple(sorted(derived)), proof=script)

    def rollback(self, state: ProofState, receipt: Receipt) -> ProofState:
        return normalize_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


class ProofResidualRepairer:
    def __init__(self) -> None:
        self.rejected_residuals: dict[str, int] = {}
        self.accepted_scripts: dict[str, int] = {}

    def update(self, receipt: Receipt) -> None:
        if receipt.hard_result.accepted:
            payload = receipt.replay_bundle.get("candidate_payload", {}) if isinstance(receipt.replay_bundle, Mapping) else {}
            script = payload.get("script", ()) if isinstance(payload, Mapping) else ()
            key = stable_hash(tuple(script))[:12]
            self.accepted_scripts[key] = self.accepted_scripts.get(key, 0) + 1
            return
        residual = receipt.hard_result.residual
        if receipt.hard_result.rejected and isinstance(residual, Mapping):
            kind = str(residual.get("kind", "unknown"))
            self.rejected_residuals[kind] = self.rejected_residuals.get(kind, 0) + 1

    def propose(self, candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate | None:
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        rule_id = repair.get("rule_id")
        if not isinstance(rule_id, str):
            return None
        script = tuple(str(value) for value in candidate.payload["script"])
        if rule_id in script:
            return None
        return make_proof_candidate(
            normalize_problem(candidate.payload["problem"]),
            (*script, rule_id),
            context=str(candidate.payload.get("context", "proof-repair")),
            cost=int(candidate.payload.get("cost", len(script))) + 1,
        )


def normalize_rule(rule: ProofRule | Mapping[str, Any]) -> ProofRule:
    if isinstance(rule, ProofRule):
        return ProofRule(rule_id=str(rule.rule_id), premises=tuple(str(p) for p in rule.premises), conclusion=str(rule.conclusion))
    return ProofRule(
        rule_id=str(rule["rule_id"]),
        premises=tuple(str(premise) for premise in rule.get("premises", ())),
        conclusion=str(rule["conclusion"]),
    )


def normalize_problem(problem: ProofProblem | Mapping[str, Any]) -> ProofProblem:
    if isinstance(problem, ProofProblem):
        hypotheses = problem.hypotheses
        rules = problem.rules
        goal = problem.goal
    else:
        hypotheses = tuple(problem["hypotheses"])
        rules = tuple(problem["rules"])
        goal = problem["goal"]
    normalized_rules = tuple(normalize_rule(rule) for rule in rules)
    ids = [rule.rule_id for rule in normalized_rules]
    if len(set(ids)) != len(ids):
        raise ValueError("proof rule ids must be unique")
    if not normalized_rules:
        raise ValueError("proof problem must contain at least one rule")
    return ProofProblem(
        hypotheses=tuple(str(hypothesis) for hypothesis in hypotheses),
        rules=normalized_rules,
        goal=str(goal),
    )


def normalize_state(state: ProofState | Mapping[str, Any]) -> ProofState:
    if isinstance(state, ProofState):
        return ProofState(
            problem=normalize_problem(state.problem),
            proven=bool(state.proven),
            derived=tuple(str(fact) for fact in state.derived),
            proof=tuple(str(rule_id) for rule_id in state.proof),
        )
    return ProofState(
        problem=normalize_problem(state["problem"]),
        proven=bool(state.get("proven", False)),
        derived=tuple(str(fact) for fact in state.get("derived", ())),
        proof=tuple(str(rule_id) for rule_id in state.get("proof", ())),
    )


def derive_facts(problem: ProofProblem, script: Iterable[str]) -> set[str]:
    problem = normalize_problem(problem)
    rules = {rule.rule_id: rule for rule in problem.rules}
    facts = set(problem.hypotheses)
    used: set[str] = set()
    for rule_id in script:
        rule = rules[str(rule_id)]
        if rule.rule_id in used or any(premise not in facts for premise in rule.premises):
            raise ValueError(f"invalid proof script step: {rule_id}")
        facts.add(rule.conclusion)
        used.add(rule.rule_id)
    return facts


def make_proof_candidate(problem: ProofProblem, script: Iterable[str], context: str = "proof", cost: int | None = None) -> TypedCandidate:
    problem = normalize_problem(problem)
    script_tuple = tuple(str(rule_id) for rule_id in script)
    return TypedCandidate(
        payload={
            "context": context,
            "problem": problem,
            "script": script_tuple,
            "cost": len(script_tuple) if cost is None else int(cost),
        },
        type_name="proof.horn_script",
        schema_version="proof.horn_script.v1",
        hashes={"problem": stable_hash(problem), "script": stable_hash(script_tuple)},
    )


def chain_proof_problem(rule_count: int = 6, prefix: str = "p") -> tuple[ProofProblem, tuple[str, ...]]:
    if rule_count <= 0:
        raise ValueError("rule_count must be positive")
    rules = []
    for idx in range(rule_count):
        premise = f"{prefix}{idx}"
        conclusion = f"{prefix}{idx + 1}"
        rules.append(ProofRule(rule_id=f"r{idx + 1}", premises=(premise,), conclusion=conclusion))
    return ProofProblem(hypotheses=(f"{prefix}0",), rules=tuple(rules), goal=f"{prefix}{rule_count}"), tuple(rule.rule_id for rule in rules)


def run_static_proof_episode(problem: ProofProblem, scripts: Iterable[tuple[str, ...]], ledger: Ledger, episode: int) -> ProofEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(HornProofAdapter(), ledger=ledger)
    state = ProofState(problem=problem)
    calls = 0
    for script in scripts:
        calls += 1
        candidate = make_proof_candidate(problem, script, context="proof-static", cost=calls)
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"proof-static-{episode}-{calls}",
                actions=({"script": script},),
                seeds=(episode, calls),
                model_version="proof.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return _episode_result(calls, True, engine, state)
    return _episode_result(calls, False, engine, state)


def run_repair_proof_episode(problem: ProofProblem, ledger: Ledger, repairer: ProofResidualRepairer, episode: int) -> ProofEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(HornProofAdapter(), ledger=ledger)
    state = ProofState(problem=problem)
    candidate = make_proof_candidate(problem, (), context="proof-repair", cost=1)
    for attempt in range(len(problem.rules) + 2):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"proof-repair-{episode}-{attempt}",
                actions=({"script": candidate.payload["script"]},),
                seeds=(episode, attempt),
                model_version="proof.residual_repair.v1",
            ),
            candidate,
        )
        repairer.update(outcome.receipt)
        if outcome.committed:
            return _episode_result(attempt + 1, True, engine, state)
        residual = outcome.receipt.hard_result.residual
        if not isinstance(residual, Mapping):
            return _episode_result(attempt + 1, False, engine, state)
        repaired = repairer.propose(candidate, residual)
        if repaired is None:
            return _episode_result(attempt + 1, False, engine, state)
        candidate = repaired
    return _episode_result(len(problem.rules) + 2, False, engine, state)


def run_proof_kernel_benchmark(seed: int = 41, episodes: int = 24, rule_count: int = 6) -> ProofKernelReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    problem, correct_script = chain_proof_problem(rule_count=rule_count)
    scripts = list(permutations(correct_script))
    rng = random.Random(seed)
    rng.shuffle(scripts)
    if correct_script not in scripts:
        raise AssertionError("permutation generator lost correct proof script")
    static_ledgers: list[Ledger] = []
    repair_ledgers: list[Ledger] = []
    repairer = ProofResidualRepairer()
    static_results: list[ProofEpisodeResult] = []
    repair_results: list[ProofEpisodeResult] = []
    for episode in range(episodes):
        static_ledger = Ledger()
        repair_ledger = Ledger()
        static_ledgers.append(static_ledger)
        repair_ledgers.append(repair_ledger)
        static_results.append(run_static_proof_episode(problem, scripts, static_ledger, episode))
        repair_results.append(run_repair_proof_episode(problem, repair_ledger, repairer, episode))
    static_cps = _calls_per_success(static_results)
    repair_cps = _calls_per_success(repair_results)
    all_results = (*static_results, *repair_results)
    return ProofKernelReport(
        episodes=episodes,
        rule_count=rule_count,
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        repair_success_rate=sum(1 for row in repair_results if row.success) / len(repair_results),
        ledger_audit_rate=sum(1 for row in all_results if row.audit_ok) / len(all_results),
        replay_rollback_rate=sum(1 for row in all_results if row.replay_rollback_ok) / len(all_results),
        invalid_commit_count=_invalid_commits((*static_ledgers, *repair_ledgers)),
        learned_residual_kinds=dict(repairer.rejected_residuals),
    )


def _next_applicable_rule(problem: ProofProblem, facts: set[str], used: set[str]) -> dict[str, Any] | None:
    for rule in problem.rules:
        if rule.rule_id in used:
            continue
        if all(premise in facts for premise in rule.premises):
            return {"rule_id": rule.rule_id, "conclusion": rule.conclusion}
    return None


def _episode_result(calls: int, success: bool, engine: TransactionEngine, seed_state: ProofState) -> ProofEpisodeResult:
    audit_ok = engine.ledger.audit()
    replay_rollback_ok = False
    if audit_ok:
        try:
            engine.replay_audit(seed_state)
            replay_rollback_ok = engine.rollback_audit(seed_state) == seed_state
        except Exception:
            replay_rollback_ok = False
    return ProofEpisodeResult(calls=calls, success=success, audit_ok=audit_ok, replay_rollback_ok=replay_rollback_ok)


def _calls_per_success(results: Iterable[ProofEpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
