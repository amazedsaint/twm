from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


NORMAL_VALENCE = {"C": 4, "N": 3, "O": 2, "F": 1, "Cl": 1}
DEFAULT_ELEMENTS = ("C", "N", "O", "F", "Cl")
DEFAULT_BOND_ORDERS = (1, 2, 3)


@dataclass(frozen=True)
class MoleculeAtom:
    atom_id: str
    element: str


@dataclass(frozen=True)
class MoleculeBond:
    bond_id: str
    atoms: tuple[str, str]
    order: int


@dataclass(frozen=True)
class MoleculeGraph:
    atoms: tuple[MoleculeAtom, ...]
    bonds: tuple[MoleculeBond, ...]


@dataclass(frozen=True)
class MoleculeRepairProblem:
    template_graph: MoleculeGraph
    target_formula: Mapping[str, int]
    mutable_atom_id: str
    mutable_bond_id: str
    allowed_elements: tuple[str, ...] = DEFAULT_ELEMENTS
    allowed_bond_orders: tuple[int, ...] = DEFAULT_BOND_ORDERS


@dataclass(frozen=True)
class MoleculeRepairState:
    problem: MoleculeRepairProblem
    solved: bool = False
    graph: MoleculeGraph | None = None


@dataclass(frozen=True)
class MoleculeEpisodeResult:
    calls: int
    success: bool
    audit_ok: bool
    replay_rollback_ok: bool


@dataclass(frozen=True)
class MoleculeRepairReport:
    episodes: int
    candidate_space_size: int
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    repair_success_rate: float
    ledger_audit_rate: float
    replay_rollback_rate: float
    invalid_commit_count: int
    learned_residual_kinds: Mapping[str, int]


class MoleculeGraphAdapter:
    verifier_id = "organic_subset_valence_formula_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        problem = normalize_problem(payload["problem"])
        graph = normalize_graph(payload["graph"])
        metadata = {
            "cost": payload.get("cost", 1),
            "atom_count": len(graph.atoms),
            "bond_count": len(graph.bonds),
        }
        shape_error = _candidate_shape_error(problem, graph)
        if shape_error:
            return self._reject("schema_error", {"message": shape_error}, metadata)

        violations = valence_violations(graph)
        if violations:
            repair = diagnose_molecule_edit(problem, graph)
            return self._reject("valence_exceeded", {"violations": violations, "repair": repair}, metadata)

        formula = molecular_formula(graph)
        target = normalize_formula(problem.target_formula)
        if formula != target:
            repair = diagnose_molecule_edit(problem, graph)
            return self._reject(
                "formula_mismatch",
                {"expected": target, "actual": formula, "repair": repair},
                metadata,
            )
        return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata={**metadata, "formula": formula})

    def apply_commit(self, state: MoleculeRepairState, candidate: TypedCandidate) -> MoleculeRepairState:
        current = normalize_state(state)
        problem = normalize_problem(candidate.payload["problem"])
        if current.problem != problem:
            raise ValueError("candidate problem does not match current molecule state")
        graph = normalize_graph(candidate.payload["graph"])
        return MoleculeRepairState(problem=problem, solved=True, graph=graph)

    def replay(self, state: MoleculeRepairState, receipt: Receipt) -> MoleculeRepairState:
        current = normalize_state(state)
        payload = receipt.replay_bundle["candidate_payload"]
        problem = normalize_problem(payload["problem"])
        if current.problem != problem:
            raise ValueError("receipt problem does not match replay molecule state")
        graph = normalize_graph(payload["graph"])
        return MoleculeRepairState(problem=problem, solved=True, graph=graph)

    def rollback(self, state: MoleculeRepairState, receipt: Receipt) -> MoleculeRepairState:
        return normalize_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **dict(residual)},
            metadata=metadata,
        )


class MoleculeResidualRepairer:
    def __init__(self) -> None:
        self.rejected_residuals: dict[str, int] = {}
        self.accepted_edits: dict[str, int] = {}

    def update(self, receipt: Receipt) -> None:
        if receipt.hard_result.accepted:
            payload = receipt.replay_bundle.get("candidate_payload", {}) if isinstance(receipt.replay_bundle, Mapping) else {}
            key = "unknown"
            if isinstance(payload, Mapping):
                key = stable_hash({"element": payload.get("element"), "bond_order": payload.get("bond_order")})[:12]
            self.accepted_edits[key] = self.accepted_edits.get(key, 0) + 1
            return
        residual = receipt.hard_result.residual
        if receipt.hard_result.rejected and isinstance(residual, Mapping):
            kind = str(residual.get("kind", "unknown"))
            self.rejected_residuals[kind] = self.rejected_residuals.get(kind, 0) + 1

    def propose(self, candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate | None:
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        element = repair.get("element")
        bond_order = repair.get("bond_order")
        if not isinstance(element, str) or not isinstance(bond_order, int):
            return None
        if element == candidate.payload.get("element") and bond_order == candidate.payload.get("bond_order"):
            return None
        return make_molecule_candidate(
            normalize_problem(candidate.payload["problem"]),
            element,
            bond_order,
            context=str(candidate.payload.get("context", "molecule-repair")),
            cost=int(candidate.payload.get("cost", 1)) + 1,
        )


def normalize_atom(atom: MoleculeAtom | Mapping[str, Any]) -> MoleculeAtom:
    if isinstance(atom, MoleculeAtom):
        atom_id = atom.atom_id
        element = atom.element
    else:
        atom_id = atom.get("atom_id", atom.get("atomId"))
        element = atom["element"]
    atom_id = str(atom_id)
    element = str(element)
    if not atom_id:
        raise ValueError("atom_id must be non-empty")
    if element not in NORMAL_VALENCE:
        raise ValueError(f"unsupported organic-subset element: {element}")
    return MoleculeAtom(atom_id=atom_id, element=element)


def normalize_bond(bond: MoleculeBond | Mapping[str, Any]) -> MoleculeBond:
    if isinstance(bond, MoleculeBond):
        bond_id = bond.bond_id
        atoms = bond.atoms
        order = bond.order
    else:
        bond_id = bond.get("bond_id", bond.get("bondId"))
        atoms = tuple(bond["atoms"])
        order = bond["order"]
    bond_id = str(bond_id)
    atom_pair = tuple(str(atom_id) for atom_id in atoms)
    if not bond_id:
        raise ValueError("bond_id must be non-empty")
    if len(atom_pair) != 2 or atom_pair[0] == atom_pair[1]:
        raise ValueError("bond must connect two distinct atom ids")
    order = int(order)
    if order not in DEFAULT_BOND_ORDERS:
        raise ValueError("bond order must be 1, 2, or 3")
    return MoleculeBond(bond_id=bond_id, atoms=atom_pair, order=order)


def normalize_graph(graph: MoleculeGraph | Mapping[str, Any]) -> MoleculeGraph:
    if isinstance(graph, MoleculeGraph):
        atoms = graph.atoms
        bonds = graph.bonds
    else:
        atoms = tuple(graph["atoms"])
        bonds = tuple(graph["bonds"])
    normalized_atoms = tuple(normalize_atom(atom) for atom in atoms)
    atom_ids = [atom.atom_id for atom in normalized_atoms]
    if len(set(atom_ids)) != len(atom_ids):
        raise ValueError("atom ids must be unique")
    known = set(atom_ids)
    normalized_bonds = tuple(normalize_bond(bond) for bond in bonds)
    bond_ids = [bond.bond_id for bond in normalized_bonds]
    if len(set(bond_ids)) != len(bond_ids):
        raise ValueError("bond ids must be unique")
    pairs: set[tuple[str, str]] = set()
    for bond in normalized_bonds:
        if bond.atoms[0] not in known or bond.atoms[1] not in known:
            raise ValueError("bond references unknown atom")
        pair = tuple(sorted(bond.atoms))
        if pair in pairs:
            raise ValueError("duplicate atom pair bonds are not supported in this G1 canary")
        pairs.add(pair)
    return MoleculeGraph(atoms=normalized_atoms, bonds=normalized_bonds)


def normalize_formula(formula: Mapping[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for element, count in formula.items():
        element = str(element)
        count = int(count)
        if count < 0:
            raise ValueError("formula counts must be non-negative")
        if count:
            out[element] = count
    return dict(sorted(out.items()))


def normalize_problem(problem: MoleculeRepairProblem | Mapping[str, Any]) -> MoleculeRepairProblem:
    if isinstance(problem, MoleculeRepairProblem):
        template = problem.template_graph
        target_formula = problem.target_formula
        mutable_atom_id = problem.mutable_atom_id
        mutable_bond_id = problem.mutable_bond_id
        allowed_elements = problem.allowed_elements
        allowed_bond_orders = problem.allowed_bond_orders
    else:
        template = problem.get("template_graph", problem.get("templateGraph"))
        target_formula = problem.get("target_formula", problem.get("targetFormula"))
        mutable_atom_id = problem.get("mutable_atom_id", problem.get("mutableAtomId"))
        mutable_bond_id = problem.get("mutable_bond_id", problem.get("mutableBondId"))
        allowed_elements = tuple(problem.get("allowed_elements", problem.get("allowedElements", DEFAULT_ELEMENTS)))
        allowed_bond_orders = tuple(problem.get("allowed_bond_orders", problem.get("allowedBondOrders", DEFAULT_BOND_ORDERS)))
    graph = normalize_graph(template)
    atom_id = str(mutable_atom_id)
    bond_id = str(mutable_bond_id)
    if atom_id not in {atom.atom_id for atom in graph.atoms}:
        raise ValueError("mutable_atom_id must identify a template atom")
    if bond_id not in {bond.bond_id for bond in graph.bonds}:
        raise ValueError("mutable_bond_id must identify a template bond")
    elements = tuple(str(element) for element in allowed_elements)
    if not elements or any(element not in NORMAL_VALENCE for element in elements) or len(set(elements)) != len(elements):
        raise ValueError("allowed_elements must be unique supported elements")
    orders = tuple(int(order) for order in allowed_bond_orders)
    if not orders or any(order not in DEFAULT_BOND_ORDERS for order in orders) or len(set(orders)) != len(orders):
        raise ValueError("allowed_bond_orders must be unique values from 1,2,3")
    return MoleculeRepairProblem(
        template_graph=graph,
        target_formula=normalize_formula(target_formula),
        mutable_atom_id=atom_id,
        mutable_bond_id=bond_id,
        allowed_elements=elements,
        allowed_bond_orders=orders,
    )


def normalize_state(state: MoleculeRepairState | Mapping[str, Any]) -> MoleculeRepairState:
    if isinstance(state, MoleculeRepairState):
        return MoleculeRepairState(
            problem=normalize_problem(state.problem),
            solved=bool(state.solved),
            graph=normalize_graph(state.graph) if state.graph is not None else None,
        )
    return MoleculeRepairState(
        problem=normalize_problem(state["problem"]),
        solved=bool(state.get("solved", False)),
        graph=normalize_graph(state["graph"]) if state.get("graph") is not None else None,
    )


def explicit_valences(graph_input: MoleculeGraph) -> dict[str, int]:
    graph = normalize_graph(graph_input)
    valences = {atom.atom_id: 0 for atom in graph.atoms}
    for bond in graph.bonds:
        valences[bond.atoms[0]] += bond.order
        valences[bond.atoms[1]] += bond.order
    return valences


def valence_violations(graph_input: MoleculeGraph) -> tuple[dict[str, Any], ...]:
    graph = normalize_graph(graph_input)
    valences = explicit_valences(graph)
    violations: list[dict[str, Any]] = []
    for atom in graph.atoms:
        max_valence = NORMAL_VALENCE[atom.element]
        explicit = valences[atom.atom_id]
        if explicit > max_valence:
            violations.append({"atom_id": atom.atom_id, "element": atom.element, "explicit": explicit, "max": max_valence})
    return tuple(violations)


def molecular_formula(graph_input: MoleculeGraph) -> dict[str, int]:
    graph = normalize_graph(graph_input)
    violations = valence_violations(graph)
    if violations:
        raise ValueError(f"cannot compute formula for invalid valence graph: {violations}")
    valences = explicit_valences(graph)
    formula: dict[str, int] = {}
    hydrogen_count = 0
    for atom in graph.atoms:
        formula[atom.element] = formula.get(atom.element, 0) + 1
        hydrogen_count += NORMAL_VALENCE[atom.element] - valences[atom.atom_id]
    if hydrogen_count:
        formula["H"] = hydrogen_count
    return normalize_formula(formula)


def replace_molecule_edit(graph_input: MoleculeGraph, atom_id: str, element: str, bond_id: str, bond_order: int) -> MoleculeGraph:
    graph = normalize_graph(graph_input)
    element = str(element)
    if element not in NORMAL_VALENCE:
        raise ValueError(f"unsupported organic-subset element: {element}")
    changed_atom = False
    changed_bond = False
    atoms: list[MoleculeAtom] = []
    for atom in graph.atoms:
        if atom.atom_id == atom_id:
            atoms.append(MoleculeAtom(atom.atom_id, element))
            changed_atom = True
        else:
            atoms.append(atom)
    bonds: list[MoleculeBond] = []
    for bond in graph.bonds:
        if bond.bond_id == bond_id:
            bonds.append(MoleculeBond(bond.bond_id, bond.atoms, int(bond_order)))
            changed_bond = True
        else:
            bonds.append(bond)
    if not changed_atom or not changed_bond:
        raise ValueError("mutable atom or bond not found")
    return normalize_graph(MoleculeGraph(atoms=tuple(atoms), bonds=tuple(bonds)))


def diagnose_molecule_edit(problem_input: MoleculeRepairProblem, graph_input: MoleculeGraph) -> dict[str, Any] | None:
    problem = normalize_problem(problem_input)
    matches: list[tuple[str, int, dict[str, int]]] = []
    for element in problem.allowed_elements:
        for bond_order in problem.allowed_bond_orders:
            graph = replace_molecule_edit(problem.template_graph, problem.mutable_atom_id, element, problem.mutable_bond_id, bond_order)
            if valence_violations(graph):
                continue
            formula = molecular_formula(graph)
            if formula == normalize_formula(problem.target_formula):
                matches.append((element, bond_order, formula))
    if len(matches) != 1:
        return None
    element, bond_order, formula = matches[0]
    return {
        "atom_id": problem.mutable_atom_id,
        "bond_id": problem.mutable_bond_id,
        "element": element,
        "bond_order": bond_order,
        "formula": formula,
    }


def make_molecule_candidate(
    problem: MoleculeRepairProblem,
    element: str,
    bond_order: int,
    context: str = "molecule",
    cost: int = 1,
) -> TypedCandidate:
    problem = normalize_problem(problem)
    graph = replace_molecule_edit(problem.template_graph, problem.mutable_atom_id, element, problem.mutable_bond_id, bond_order)
    return TypedCandidate(
        payload={
            "context": context,
            "problem": problem,
            "graph": graph,
            "mutable_atom_id": problem.mutable_atom_id,
            "mutable_bond_id": problem.mutable_bond_id,
            "element": str(element),
            "bond_order": int(bond_order),
            "cost": cost,
        },
        type_name="molecule.organic_subset_graph",
        schema_version="molecule.organic_subset_graph.v1",
        hashes={
            "problem": stable_hash(problem),
            "graph": stable_hash(graph),
            "edit": stable_hash({"element": str(element), "bond_order": int(bond_order)}),
        },
    )


def make_molecule_repair_problem(target_element: str = "O", target_bond_order: int = 1) -> MoleculeRepairProblem:
    template = MoleculeGraph(
        atoms=(
            MoleculeAtom("a0", "C"),
            MoleculeAtom("a1", "C"),
            MoleculeAtom("a2", "C"),
        ),
        bonds=(
            MoleculeBond("b0", ("a0", "a1"), 1),
            MoleculeBond("b1", ("a1", "a2"), 1),
        ),
    )
    target = replace_molecule_edit(template, "a2", target_element, "b1", target_bond_order)
    return MoleculeRepairProblem(
        template_graph=template,
        target_formula=molecular_formula(target),
        mutable_atom_id="a2",
        mutable_bond_id="b1",
    )


def run_static_molecule_episode(
    problem: MoleculeRepairProblem,
    edit_order: Iterable[tuple[str, int]],
    ledger: Ledger,
    episode: int,
) -> MoleculeEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(MoleculeGraphAdapter(), ledger=ledger)
    state = MoleculeRepairState(problem=problem)
    calls = 0
    for element, bond_order in edit_order:
        calls += 1
        candidate = make_molecule_candidate(problem, element, bond_order, context="molecule-static", cost=calls)
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"molecule-static-{episode}-{calls}",
                actions=({"element": element, "bond_order": bond_order},),
                seeds=(episode, calls),
                model_version="molecule.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return _episode_result(calls, True, engine, state)
    return _episode_result(calls, False, engine, state)


def run_repair_molecule_episode(
    problem: MoleculeRepairProblem,
    ledger: Ledger,
    repairer: MoleculeResidualRepairer,
    episode: int,
    initial_element: str = "C",
    initial_bond_order: int = 3,
) -> MoleculeEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(MoleculeGraphAdapter(), ledger=ledger)
    state = MoleculeRepairState(problem=problem)
    candidate = make_molecule_candidate(problem, initial_element, initial_bond_order, context="molecule-repair", cost=1)
    for attempt in range(3):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"molecule-repair-{episode}-{attempt}",
                actions=({"element": candidate.payload["element"], "bond_order": candidate.payload["bond_order"]},),
                seeds=(episode, attempt),
                model_version="molecule.residual_repair.v1",
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
    return _episode_result(3, False, engine, state)


def run_molecule_repair_benchmark(seed: int = 53, episodes: int = 42) -> MoleculeRepairReport:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    edit_space = tuple((element, order) for element in DEFAULT_ELEMENTS for order in DEFAULT_BOND_ORDERS)
    targets: list[tuple[str, int]] = []
    for edit in edit_space:
        if edit == ("C", 3):
            continue
        try:
            make_molecule_repair_problem(*edit)
        except ValueError:
            continue
        targets.append(edit)
    rng = random.Random(seed)
    rng.shuffle(targets)
    static_order = edit_space
    static_results: list[MoleculeEpisodeResult] = []
    repair_results: list[MoleculeEpisodeResult] = []
    static_ledgers: list[Ledger] = []
    repair_ledgers: list[Ledger] = []
    repairer = MoleculeResidualRepairer()
    for episode in range(episodes):
        element, bond_order = targets[episode % len(targets)]
        problem = make_molecule_repair_problem(element, bond_order)
        static_ledger = Ledger()
        repair_ledger = Ledger()
        static_ledgers.append(static_ledger)
        repair_ledgers.append(repair_ledger)
        static_results.append(run_static_molecule_episode(problem, static_order, static_ledger, episode))
        repair_results.append(run_repair_molecule_episode(problem, repair_ledger, repairer, episode))
    all_results = (*static_results, *repair_results)
    static_cps = _calls_per_success(static_results)
    repair_cps = _calls_per_success(repair_results)
    return MoleculeRepairReport(
        episodes=episodes,
        candidate_space_size=len(edit_space),
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        repair_success_rate=sum(1 for row in repair_results if row.success) / len(repair_results),
        ledger_audit_rate=sum(1 for row in all_results if row.audit_ok) / len(all_results),
        replay_rollback_rate=sum(1 for row in all_results if row.replay_rollback_ok) / len(all_results),
        invalid_commit_count=_invalid_commits((*static_ledgers, *repair_ledgers)),
        learned_residual_kinds=dict(repairer.rejected_residuals),
    )


def _candidate_shape_error(problem: MoleculeRepairProblem, graph: MoleculeGraph) -> str | None:
    template = problem.template_graph
    if tuple(atom.atom_id for atom in graph.atoms) != tuple(atom.atom_id for atom in template.atoms):
        return "candidate atom ids must match template order"
    if tuple((bond.bond_id, bond.atoms) for bond in graph.bonds) != tuple((bond.bond_id, bond.atoms) for bond in template.bonds):
        return "candidate bond ids and endpoints must match template"
    for expected, actual in zip(template.atoms, graph.atoms):
        if expected.atom_id != problem.mutable_atom_id and expected.element != actual.element:
            return "only the mutable atom element may change"
    for expected, actual in zip(template.bonds, graph.bonds):
        if expected.bond_id != problem.mutable_bond_id and expected.order != actual.order:
            return "only the mutable bond order may change"
    mutable_atom = next(atom for atom in graph.atoms if atom.atom_id == problem.mutable_atom_id)
    mutable_bond = next(bond for bond in graph.bonds if bond.bond_id == problem.mutable_bond_id)
    if mutable_atom.element not in problem.allowed_elements:
        return "mutable atom element is not allowed"
    if mutable_bond.order not in problem.allowed_bond_orders:
        return "mutable bond order is not allowed"
    return None


def _episode_result(calls: int, success: bool, engine: TransactionEngine, seed_state: MoleculeRepairState) -> MoleculeEpisodeResult:
    audit_ok = engine.ledger.audit()
    replay_rollback_ok = False
    if audit_ok:
        try:
            engine.replay_audit(seed_state)
            replay_rollback_ok = engine.rollback_audit(seed_state) == seed_state
        except Exception:
            replay_rollback_ok = False
    return MoleculeEpisodeResult(calls=calls, success=success, audit_ok=audit_ok, replay_rollback_ok=replay_rollback_ok)


def _calls_per_success(results: Iterable[MoleculeEpisodeResult]) -> float:
    rows = tuple(results)
    successes = sum(1 for row in rows if row.success)
    calls = sum(row.calls for row in rows)
    return calls / successes if successes else float("inf")


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
