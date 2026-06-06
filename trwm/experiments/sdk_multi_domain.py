from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..core import ProposalTrace
from ..macro import Macro
from ..sdk import ProgrammableSubstrate
from .circuit_repair import BooleanCircuitAdapter, CircuitRepairState, make_circuit_candidate, make_circuit_repair_problem
from .chess_ancestry import (
    ChessAncestryAdapter,
    ChessAncestryState,
    diagnose_chess_ancestry,
    make_chess_candidate,
    make_default_chess_ancestry_problem,
)
from .code_repair import CodePatchAdapter, CodeRepairState, make_code_patch_candidate, make_code_repair_problem
from .game_of_life import LifePredecessorAdapter, LifeProjector, LifeState, life_step
from .macro_grid import GridMacroAdapter, default_grid_state, default_macros
from .molecule_repair import MoleculeGraphAdapter, MoleculeRepairState, make_molecule_candidate, make_molecule_repair_problem
from .operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate
from .proof_kernel import HornProofAdapter, ProofState, chain_proof_problem, make_proof_candidate
from .repair_simulator import ScalarProgramAdapter, make_scalar_candidate
from .robotics import RobotTrajectoryAdapter, RobotTrajectoryState, make_robot_trajectory_candidate, make_robot_trajectory_problem
from .sokoban import SokobanReverseAdapter, SokobanState, make_sokoban_candidate, parse_sokoban


@dataclass(frozen=True)
class MultiDomainSdkReport:
    domains_supported: int
    committed_domains: int
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int
    scalar_hard_calls: int
    life_hard_calls: int
    grid_hard_calls: int
    sokoban_hard_calls: int
    operations_hard_calls: int
    proof_hard_calls: int
    circuit_hard_calls: int
    molecule_hard_calls: int
    code_hard_calls: int
    robot_hard_calls: int
    chess_hard_calls: int
    router_top_domain: str
    router_scalar_counts: tuple[int, int]
    router_life_counts: tuple[int, int]
    router_sokoban_counts: tuple[int, int]
    router_operations_counts: tuple[int, int]
    router_proof_counts: tuple[int, int]
    router_circuit_counts: tuple[int, int]
    router_molecule_counts: tuple[int, int]
    router_code_counts: tuple[int, int]
    router_robot_counts: tuple[int, int]
    router_chess_counts: tuple[int, int]


def run_multi_domain_sdk_benchmark() -> MultiDomainSdkReport:
    substrate = ProgrammableSubstrate()
    substrate.register("scalar", ScalarProgramAdapter())
    substrate.register("life", LifePredecessorAdapter())
    substrate.register("grid", GridMacroAdapter())
    substrate.register("sokoban", SokobanReverseAdapter())
    substrate.register("operations", InventoryReservationAdapter())
    substrate.register("proof", HornProofAdapter())
    substrate.register("circuit", BooleanCircuitAdapter())
    substrate.register("molecule", MoleculeGraphAdapter())
    substrate.register("code", CodePatchAdapter())
    substrate.register("robot", RobotTrajectoryAdapter())
    substrate.register("chess", ChessAncestryAdapter())

    scalar_state = {"episode": 0, "target": 5, "solved": False}
    scalar_candidate = make_scalar_candidate("sdk-routing", 5, ({"op": "set", "value": 5},))
    scalar = substrate.submit(
        "scalar",
        scalar_state,
        ProposalTrace(
            branch_id="sdk-scalar",
            actions=({"op": "set", "value": 5},),
            seeds=("sdk", "scalar"),
            model_version="sdk.scalar.v1",
        ),
        scalar_candidate,
        context="sdk-routing",
    )
    substrate.submit(
        "scalar",
        scalar.outcome.state,
        ProposalTrace(
            branch_id="sdk-scalar-repeat",
            actions=({"op": "set", "value": 5},),
            seeds=("sdk", "scalar-repeat"),
            model_version="sdk.scalar.v1",
        ),
        scalar_candidate,
        context="sdk-routing",
    )

    seed_predecessor = (
        (0, 0, 0),
        (1, 1, 1),
        (0, 0, 0),
    )
    target = life_step(seed_predecessor)
    life_state = LifeState(target=target)
    life_trace = ProposalTrace(
        branch_id="sdk-life",
        actions=({"predecessor": seed_predecessor, "cost": 1},),
        seeds=("sdk", "life"),
        model_version="sdk.life.v1",
    )
    life = substrate.submit(
        "life",
        life_state,
        life_trace,
        LifeProjector().project(life_state, life_trace),
        context="sdk-routing",
    )

    grid_adapter = GridMacroAdapter()
    grid_seed = default_grid_state()
    grid_macro = default_macros()[1]
    grid_final = _apply_macro(grid_adapter, grid_seed, grid_macro)
    grid = substrate.submit(
        "grid",
        grid_seed,
        ProposalTrace(
            branch_id="sdk-grid",
            actions=grid_macro.steps,
            seeds=("sdk", "grid"),
            model_version="sdk.grid.v1",
        ),
        grid_adapter.project_macro(grid_seed, grid_macro, grid_final),
        context="sdk-routing",
    )

    sokoban_layout, sokoban_solved = parse_sokoban((
        "#######",
        "#  @* #",
        "#     #",
        "#######",
    ))
    sokoban_predecessor = SokobanState(boxes=((1, 3),), player=(1, 2))
    sokoban_pushes = ({"box": (1, 3), "direction": "R"},)
    sokoban = substrate.submit(
        "sokoban",
        sokoban_solved,
        ProposalTrace(
            branch_id="sdk-sokoban",
            actions=sokoban_pushes,
            seeds=("sdk", "sokoban"),
            model_version="sdk.sokoban.v1",
        ),
        make_sokoban_candidate(sokoban_layout, sokoban_solved, sokoban_predecessor, sokoban_pushes, cost=1),
        context="sdk-routing",
    )

    operations_seed = InventoryState(stock={"A": 5}, reserved={"A": 0})
    operations = substrate.submit(
        "operations",
        operations_seed,
        ProposalTrace(
            branch_id="sdk-operations",
            actions=({"order_id": "sdk-order", "sku": "A", "quantity": 5},),
            seeds=("sdk", "operations"),
            model_version="sdk.operations.v1",
        ),
        make_reservation_candidate(operations_seed, "sdk-order", "A", requested=7, quantity=5),
        context="sdk-routing",
    )

    proof_problem, proof_script = chain_proof_problem(rule_count=2, prefix="sdk_p")
    proof_state = ProofState(problem=proof_problem)
    proof = substrate.submit(
        "proof",
        proof_state,
        ProposalTrace(
            branch_id="sdk-proof",
            actions=({"script": proof_script},),
            seeds=("sdk", "proof"),
            model_version="sdk.proof.v1",
        ),
        make_proof_candidate(proof_problem, proof_script, context="sdk-routing", cost=1),
        context="sdk-routing",
    )

    circuit_problem = make_circuit_repair_problem(target_op_mask=6)
    circuit_state = CircuitRepairState(problem=circuit_problem)
    circuit = substrate.submit(
        "circuit",
        circuit_state,
        ProposalTrace(
            branch_id="sdk-circuit",
            actions=({"gate_id": "g1", "op_mask": 6},),
            seeds=("sdk", "circuit"),
            model_version="sdk.circuit.v1",
        ),
        make_circuit_candidate(circuit_problem, op_mask=6, context="sdk-routing", cost=1),
        context="sdk-routing",
    )

    molecule_problem = make_molecule_repair_problem(target_element="O", target_bond_order=1)
    molecule_state = MoleculeRepairState(problem=molecule_problem)
    molecule = substrate.submit(
        "molecule",
        molecule_state,
        ProposalTrace(
            branch_id="sdk-molecule",
            actions=({"element": "O", "bond_order": 1},),
            seeds=("sdk", "molecule"),
            model_version="sdk.molecule.v1",
        ),
        make_molecule_candidate(molecule_problem, "O", 1, context="sdk-routing", cost=1),
        context="sdk-routing",
    )

    code_problem = make_code_repair_problem("+")
    code_state = CodeRepairState(problem=code_problem)
    code = substrate.submit(
        "code",
        code_state,
        ProposalTrace(
            branch_id="sdk-code",
            actions=({"node_id": "op0", "operator": "+"},),
            seeds=("sdk", "code"),
            model_version="sdk.code.v1",
        ),
        make_code_patch_candidate(code_problem, "+", context="sdk-routing", cost=1),
        context="sdk-routing",
    )

    robot_problem = make_robot_trajectory_problem(0.24)
    robot_state = RobotTrajectoryState(problem=robot_problem)
    robot = substrate.submit(
        "robot",
        robot_state,
        ProposalTrace(
            branch_id="sdk-robot",
            actions=({"detour_y": 0.22},),
            seeds=("sdk", "robot"),
            model_version="sdk.robot.v1",
        ),
        make_robot_trajectory_candidate(robot_problem, 0.22, context="sdk-routing", cost=1),
        context="sdk-routing",
    )

    chess_problem = make_default_chess_ancestry_problem()
    chess_state = ChessAncestryState(problem=chess_problem)
    chess_repair = diagnose_chess_ancestry(chess_problem)
    assert chess_repair is not None
    chess = substrate.submit(
        "chess",
        chess_state,
        ProposalTrace(
            branch_id="sdk-chess",
            actions=(chess_repair["move"],),
            seeds=("sdk", "chess"),
            model_version="sdk.chess.v1",
        ),
        make_chess_candidate(
            chess_problem,
            chess_repair["predecessor"],
            chess_repair["move"],
            context="sdk-routing",
            cost=1,
        ),
        context="sdk-routing",
    )

    life_reject_trace = ProposalTrace(
        branch_id="sdk-life-reject",
        actions=({"predecessor": ((0, 0, 0), (0, 0, 0), (0, 0, 0)), "cost": 2},),
        seeds=("sdk", "life-reject"),
        model_version="sdk.life.v1",
    )
    substrate.submit(
        "life",
        life_state,
        life_reject_trace,
        LifeProjector().project(life_state, life_reject_trace),
        context="sdk-routing",
    )

    audits = (
        substrate.audit_domain("scalar", scalar_state),
        substrate.audit_domain("life", life_state),
        substrate.audit_domain("grid", grid_seed),
        substrate.audit_domain("sokoban", sokoban_solved),
        substrate.audit_domain("operations", operations_seed),
        substrate.audit_domain("proof", proof_state),
        substrate.audit_domain("circuit", circuit_state),
        substrate.audit_domain("molecule", molecule_state),
        substrate.audit_domain("code", code_state),
        substrate.audit_domain("robot", robot_state),
        substrate.audit_domain("chess", chess_state),
    )
    replay_rollback_rate = sum(1 for audit in audits if audit.ok) / len(audits)
    router_order = substrate.rank_domains(
        "sdk-routing",
        ("life", "grid", "sokoban", "operations", "proof", "circuit", "molecule", "code", "robot", "chess", "scalar"),
    )
    committed_domains = sum(1 for result in (scalar, life, grid, sokoban, operations, proof, circuit, molecule, code, robot, chess) if result.committed)
    return MultiDomainSdkReport(
        domains_supported=len(substrate.domains),
        committed_domains=committed_domains,
        ledger_audit=all(audit.ledger_audit for audit in audits),
        replay_rollback_rate=replay_rollback_rate,
        invalid_commit_count=substrate.invalid_commit_count(),
        scalar_hard_calls=substrate.domains["scalar"].hard_verifier_calls,
        life_hard_calls=substrate.domains["life"].hard_verifier_calls,
        grid_hard_calls=substrate.domains["grid"].hard_verifier_calls,
        sokoban_hard_calls=substrate.domains["sokoban"].hard_verifier_calls,
        operations_hard_calls=substrate.domains["operations"].hard_verifier_calls,
        proof_hard_calls=substrate.domains["proof"].hard_verifier_calls,
        circuit_hard_calls=substrate.domains["circuit"].hard_verifier_calls,
        molecule_hard_calls=substrate.domains["molecule"].hard_verifier_calls,
        code_hard_calls=substrate.domains["code"].hard_verifier_calls,
        robot_hard_calls=substrate.domains["robot"].hard_verifier_calls,
        chess_hard_calls=substrate.domains["chess"].hard_verifier_calls,
        router_top_domain=router_order[0],
        router_scalar_counts=substrate.router.counts("sdk-routing", "scalar"),
        router_life_counts=substrate.router.counts("sdk-routing", "life"),
        router_sokoban_counts=substrate.router.counts("sdk-routing", "sokoban"),
        router_operations_counts=substrate.router.counts("sdk-routing", "operations"),
        router_proof_counts=substrate.router.counts("sdk-routing", "proof"),
        router_circuit_counts=substrate.router.counts("sdk-routing", "circuit"),
        router_molecule_counts=substrate.router.counts("sdk-routing", "molecule"),
        router_code_counts=substrate.router.counts("sdk-routing", "code"),
        router_robot_counts=substrate.router.counts("sdk-routing", "robot"),
        router_chess_counts=substrate.router.counts("sdk-routing", "chess"),
    )


def _apply_macro(adapter: GridMacroAdapter, state: dict[str, Any], macro: Macro) -> dict[str, Any]:
    current = state
    for step in macro.steps:
        current = adapter.apply_step(current, step)
    return dict(current)
