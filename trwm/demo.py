from __future__ import annotations

from dataclasses import asdict
import json

from .experiments.game_of_life import life_step, search_predecessor
from .experiments.chess_ancestry import run_chess_ancestry_benchmark
from .experiments.budget_policy import run_budget_policy_benchmark
from .experiments.branch_selection import run_branch_selection_benchmark
from .experiments.claim_audit import run_claim_audit_benchmark
from .experiments.checkpoint_compaction import run_checkpoint_compaction_benchmark
from .experiments.circular_token_log import run_circular_token_log_benchmark
from .experiments.circuit_repair import run_circuit_repair_benchmark
from .experiments.code_repair import run_code_repair_benchmark
from .experiments.counterfactual_learning import run_counterfactual_rollback_benchmark
from .experiments.distributed_counter import run_distributed_counter_benchmark
from .experiments.hdc_memory import run_hdc_memory_benchmark
from .experiments.learning_evaluation import run_learning_evaluation_benchmark
from .experiments.macro_grid import run_macro_grid_benchmark
from .experiments.memory_consolidation import run_memory_consolidation_benchmark
from .experiments.molecule_repair import run_molecule_repair_benchmark
from .experiments.operations import run_operations_benchmark
from .experiments.parallel_replay import run_parallel_replay_benchmark
from .experiments.proof_kernel import run_proof_kernel_benchmark
from .experiments.projection_contract import run_projection_contract_benchmark
from .experiments.repair_simulator import run_residual_repair_benchmark
from .experiments.redacted_receipt import run_redacted_receipt_benchmark
from .experiments.reliability_audit import run_reliability_audit_benchmark
from .experiments.residual_taxonomy import run_residual_taxonomy_benchmark
from .experiments.residual_topk import run_residual_topk_benchmark
from .experiments.robotics import run_robot_trajectory_benchmark
from .experiments.rrlm_macro import run_rrlm_macro_benchmark
from .experiments.sat_csp import run_sat_csp_benchmark
from .experiments.sdk_multi_domain import run_multi_domain_sdk_benchmark
from .experiments.sdk_manifest import run_sdk_manifest_benchmark
from .experiments.sdk_transfer_guard import run_sdk_transfer_guard_benchmark
from .experiments.shape_simulator import run_shape_conditionality
from .experiments.sokoban import parse_sokoban, search_sokoban_predecessor
from .experiments.transfer_audit import run_cross_domain_transfer_audit
from .experiments.transfer_guard import run_transfer_guard_benchmark
from .experiments.verifier_cost import run_verifier_cost_benchmark
from .experiments.verifier_budget import run_verifier_budget_benchmark
from .experiments.verifier_guard import run_verifier_guard_benchmark
from .experiments.world_loop import run_world_loop_benchmark


def main() -> None:
    seed_predecessor = (
        (0, 0, 0),
        (1, 1, 1),
        (0, 0, 0),
    )
    target = life_step(seed_predecessor)
    budget_policy = run_budget_policy_benchmark()
    branch_selection = run_branch_selection_benchmark()
    claim_audit = run_claim_audit_benchmark()
    chess = run_chess_ancestry_benchmark()
    checkpoint_compaction = run_checkpoint_compaction_benchmark()
    circular_token_log = run_circular_token_log_benchmark()
    circuit = run_circuit_repair_benchmark()
    code = run_code_repair_benchmark()
    counterfactual = run_counterfactual_rollback_benchmark()
    distributed = run_distributed_counter_benchmark()
    life = search_predecessor(target)
    hdc = run_hdc_memory_benchmark()
    learning_evaluation = run_learning_evaluation_benchmark()
    macro = run_macro_grid_benchmark()
    memory_consolidation = run_memory_consolidation_benchmark()
    molecule = run_molecule_repair_benchmark()
    operations = run_operations_benchmark()
    parallel_replay = run_parallel_replay_benchmark()
    proof = run_proof_kernel_benchmark()
    projection_contract = run_projection_contract_benchmark()
    rrlm = run_rrlm_macro_benchmark()
    sat = run_sat_csp_benchmark()
    sdk = run_multi_domain_sdk_benchmark()
    sdk_manifest = run_sdk_manifest_benchmark()
    sdk_transfer_guard = run_sdk_transfer_guard_benchmark()
    sokoban_layout, sokoban_solved = parse_sokoban((
        "#######",
        "#  @* #",
        "#     #",
        "#######",
    ))
    run_sokoban = search_sokoban_predecessor(sokoban_layout, sokoban_solved, max_depth=1)
    shape = run_shape_conditionality()
    repair = run_residual_repair_benchmark()
    redacted_receipt = run_redacted_receipt_benchmark()
    reliability_audit = run_reliability_audit_benchmark()
    residual_taxonomy = run_residual_taxonomy_benchmark()
    residual_topk = run_residual_topk_benchmark()
    robot = run_robot_trajectory_benchmark()
    transfer_audit = run_cross_domain_transfer_audit()
    transfer_guard = run_transfer_guard_benchmark()
    verifier_cost = run_verifier_cost_benchmark()
    verifier_budget = run_verifier_budget_benchmark()
    verifier_guard = run_verifier_guard_benchmark()
    world_loop = run_world_loop_benchmark()
    print(
        json.dumps(
            {
                "chess_ancestry": chess.__dict__,
                "budget_policy": budget_policy.__dict__,
                "branch_selection": branch_selection.__dict__,
                "claim_audit": claim_audit.__dict__,
                "checkpoint_compaction": checkpoint_compaction.__dict__,
                "circular_token_log": circular_token_log.__dict__,
                "circuit_repair": circuit.__dict__,
                "code_repair": code.__dict__,
                "counterfactual_rollback_learning": counterfactual.__dict__,
                "distributed_counter": distributed.__dict__,
                "game_of_life": {
                    "committed": life.committed,
                    "verifier_calls": life.verifier_calls,
                    "predecessor": life.predecessor,
                    "ledger_audit": life.ledger.audit(),
                },
                "hdc_memory": hdc.__dict__,
                "learning_evaluation": learning_evaluation.__dict__,
                "macro_grid": macro.__dict__,
                "memory_consolidation": memory_consolidation.__dict__,
                "molecule_repair": molecule.__dict__,
                "operations": operations.__dict__,
                "parallel_replay": parallel_replay.__dict__,
                "proof_kernel": proof.__dict__,
                "projection_contract": projection_contract.__dict__,
                "rrlm_macro": rrlm.__dict__,
                "sat_csp": sat.__dict__,
                "multi_domain_sdk": sdk.__dict__,
                "sdk_manifest": sdk_manifest.__dict__,
                "sdk_transfer_guard": sdk_transfer_guard.__dict__,
                "sokoban_reverse": asdict(run_sokoban),
                "shape_conditionality": shape.__dict__,
                "residual_repair": repair.__dict__,
                "redacted_receipt": redacted_receipt.__dict__,
                "reliability_audit": reliability_audit.__dict__,
                "residual_taxonomy": residual_taxonomy.__dict__,
                "residual_topk": residual_topk.__dict__,
                "robot_trajectory": robot.__dict__,
                "transfer_audit": transfer_audit.__dict__,
                "transfer_guard": transfer_guard.__dict__,
                "verifier_cost": verifier_cost.__dict__,
                "verifier_budget": verifier_budget.__dict__,
                "verifier_guard": verifier_guard.__dict__,
                "world_loop": world_loop.__dict__,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
