from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Iterable

from ..branch import BranchRuntime
from ..core import HardVerifierResult, Ledger, ProposalTrace, TransactionEngine, TypedCandidate, stable_hash
from ..reversible import AdditiveCoupling


Board = tuple[tuple[int, ...], ...]


def normalize_board(board: Iterable[Iterable[int]]) -> Board:
    return tuple(tuple(1 if cell else 0 for cell in row) for row in board)


def board_shape(board: Board) -> tuple[int, int]:
    if not board:
        return (0, 0)
    return (len(board), len(board[0]))


def life_step(board: Board) -> Board:
    height, width = board_shape(board)

    def neighbors(row: int, col: int) -> int:
        total = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = row + dr, col + dc
                if 0 <= rr < height and 0 <= cc < width:
                    total += board[rr][cc]
        return total

    rows = []
    for row in range(height):
        out = []
        for col in range(width):
            live = board[row][col] == 1
            count = neighbors(row, col)
            out.append(1 if count == 3 or (live and count == 2) else 0)
        rows.append(tuple(out))
    return tuple(rows)


def enumerate_boards(height: int, width: int) -> Iterable[Board]:
    for bits in product((0, 1), repeat=height * width):
        yield tuple(tuple(bits[row * width + col] for col in range(width)) for row in range(height))


@dataclass(frozen=True)
class LifeState:
    target: Board


class LifePredecessorAdapter:
    verifier_id = "life_forward_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        predecessor = normalize_board(payload["predecessor"])
        target = normalize_board(payload["target"])
        predicted = life_step(predecessor)
        metadata = {"cost": payload.get("cost", 1)}
        if predicted == target:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, residual=None, metadata=metadata)
        residual = {"predicted_hash": stable_hash(predicted), "target_hash": stable_hash(target)}
        return HardVerifierResult.reject(self.verifier_id, self.verifier_version, residual=residual, metadata=metadata)

    def apply_commit(self, state: LifeState, candidate: TypedCandidate) -> LifeState:
        return LifeState(target=normalize_board(candidate.payload["predecessor"]))

    def replay(self, state: LifeState, receipt: Any) -> LifeState:
        payload = receipt.replay_bundle["candidate_payload"]
        return LifeState(target=normalize_board(payload["predecessor"]))

    def rollback(self, state: LifeState, receipt: Any) -> LifeState:
        pre_state = receipt.rollback_bundle["pre_state"]
        if isinstance(pre_state, LifeState):
            return pre_state
        return LifeState(target=normalize_board(pre_state["target"]))


class LifeProjector:
    def project(self, state: LifeState, trace: ProposalTrace) -> TypedCandidate:
        action = trace.actions[-1]
        predecessor = normalize_board(action["predecessor"])
        target = normalize_board(state.target)
        return TypedCandidate(
            payload={
                "target": target,
                "predecessor": predecessor,
                "cost": action.get("cost", 1),
            },
            type_name="game_of_life.predecessor",
            schema_version="game_of_life.predecessor.v1",
            hashes={"target": stable_hash(target), "predecessor": stable_hash(predecessor)},
        )


@dataclass(frozen=True)
class LifeSearchResult:
    predecessor: Board | None
    ledger: Ledger
    verifier_calls: int
    committed: bool
    baseline_verifier_calls: int
    verifier_call_reduction: float
    reversible_trace_count: int


def _blinker_macro_predecessors(target: Board) -> list[Board]:
    height, width = board_shape(target)
    live = [(row, col) for row in range(height) for col in range(width) if target[row][col] == 1]
    if len(live) != 3:
        return []
    rows = {row for row, _ in live}
    cols = {col for _, col in live}
    proposals: list[Board] = []
    if len(cols) == 1 and len(rows) == 3:
        center_row = sum(rows) // 3
        center_col = next(iter(cols))
        if 0 <= center_row < height and 0 < center_col < width - 1:
            proposals.append(
                tuple(
                    tuple(1 if row == center_row and col in {center_col - 1, center_col, center_col + 1} else 0 for col in range(width))
                    for row in range(height)
                )
            )
    if len(rows) == 1 and len(cols) == 3:
        center_row = next(iter(rows))
        center_col = sum(cols) // 3
        if 0 < center_row < height - 1 and 0 <= center_col < width:
            proposals.append(
                tuple(
                    tuple(1 if col == center_col and row in {center_row - 1, center_row, center_row + 1} else 0 for col in range(width))
                    for row in range(height)
                )
            )
    return proposals


def _reversible_macro_trace(target: Board, predecessor: Board, branch_id: str, cost: int) -> ProposalTrace:
    live_count = sum(sum(row) for row in target)
    first_live = next(((row, col) for row, line in enumerate(target) for col, cell in enumerate(line) if cell), (0, 0))
    z = (live_count, first_live[0], first_live[1], cost)
    coupling = AdditiveCoupling(
        f=lambda v, context: (v[0] + context["bias"], v[1]),
        g=lambda u_next, context: (u_next[0] - context["bias"], -u_next[1]),
        split=2,
    )
    context = {"bias": 1}
    z_next = coupling.forward(z, context)
    if coupling.inverse(z_next, context) != z:
        raise AssertionError("reversible macro proposal failed exact cycle check")
    return ProposalTrace(
        branch_id=branch_id,
        actions=({"predecessor": predecessor, "cost": cost, "proposal": "reversible_blinker_macro"},),
        latent_states=(z, z_next),
        seeds=(stable_hash(target), cost),
        model_version="reversible.blinker_macro.v1",
    )


def _guided_traces(target: Board, max_candidates: int | None) -> list[ProposalTrace]:
    traces: list[ProposalTrace] = []
    seen: set[Board] = set()
    for idx, predecessor in enumerate(_blinker_macro_predecessors(target)):
        seen.add(predecessor)
        traces.append(_reversible_macro_trace(target, predecessor, f"life-reversible-{idx}", idx + 1))

    height, width = board_shape(target)
    for idx, predecessor in enumerate(enumerate_boards(height, width)):
        if predecessor in seen:
            continue
        if max_candidates is not None and len(traces) >= max_candidates:
            break
        traces.append(
            ProposalTrace(
                branch_id=f"life-exhaustive-{idx}",
                actions=({"predecessor": predecessor, "cost": len(traces) + 1},),
                seeds=(idx,),
                model_version="exhaustive.life.v1",
            )
        )
    return traces


def search_predecessor(target: Board, max_candidates: int | None = None) -> LifeSearchResult:
    target = normalize_board(target)
    height, width = board_shape(target)
    baseline_verifier_calls = 2 ** (height * width)
    traces = _guided_traces(target, max_candidates)

    adapter = LifePredecessorAdapter()
    engine = TransactionEngine(adapter=adapter)
    state = LifeState(target=target)
    predecessor = None
    committed = False
    for trace in traces:
        candidate = LifeProjector().project(state, trace)
        outcome = engine.transact(state, trace, candidate)
        if outcome.committed:
            predecessor = outcome.state.target
            committed = True
            break
    reduction = baseline_verifier_calls / engine.hard_verifier_calls if engine.hard_verifier_calls else 0.0
    return LifeSearchResult(
        predecessor,
        engine.ledger,
        engine.hard_verifier_calls,
        committed,
        baseline_verifier_calls,
        reduction,
        sum(1 for trace in traces if trace.model_version.startswith("reversible.")),
    )


def search_predecessor_branch_exhaustive(target: Board, max_candidates: int | None = None) -> LifeSearchResult:
    target = normalize_board(target)
    height, width = board_shape(target)
    traces = []
    for idx, predecessor in enumerate(enumerate_boards(height, width)):
        if max_candidates is not None and idx >= max_candidates:
            break
        traces.append(
            ProposalTrace(
                branch_id=f"life-{idx}",
                actions=({"predecessor": predecessor, "cost": idx + 1},),
                seeds=(idx,),
                model_version="exhaustive.life.v1",
            )
        )

    adapter = LifePredecessorAdapter()
    engine = TransactionEngine(adapter=adapter)
    runtime = BranchRuntime(engine=engine, projector=LifeProjector())
    state = LifeState(target=target)
    outcome = runtime.step(state, traces)
    predecessor = outcome.state.target if outcome.committed else None
    baseline = 2 ** (height * width)
    reduction = baseline / engine.hard_verifier_calls if engine.hard_verifier_calls else 0.0
    return LifeSearchResult(predecessor, engine.ledger, engine.hard_verifier_calls, outcome.committed, baseline, reduction, 0)
