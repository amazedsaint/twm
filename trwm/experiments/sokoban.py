from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, TransactionEngine, TypedCandidate, stable_hash


Position = tuple[int, int]
PushAction = Mapping[str, Any]
DIRECTIONS: tuple[tuple[str, Position], ...] = (
    ("U", (-1, 0)),
    ("D", (1, 0)),
    ("L", (0, -1)),
    ("R", (0, 1)),
)


@dataclass(frozen=True)
class SokobanLayout:
    height: int
    width: int
    walls: tuple[Position, ...]
    goals: tuple[Position, ...]

    @property
    def wall_set(self) -> frozenset[Position]:
        return frozenset(self.walls)

    @property
    def goal_set(self) -> frozenset[Position]:
        return frozenset(self.goals)


@dataclass(frozen=True)
class SokobanState:
    boxes: tuple[Position, ...]
    player: Position


@dataclass(frozen=True)
class SokobanSearchNode:
    state: SokobanState
    pushes: tuple[PushAction, ...]
    depth: int


@dataclass(frozen=True)
class SokobanReverseReport:
    solved: bool
    predecessor: SokobanState | None
    solved_state: SokobanState
    pushes: tuple[PushAction, ...]
    verifier_calls: int
    reverse_expansions: int
    max_depth: int
    baseline_state_count: int
    verifier_call_reduction: float
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float


def parse_sokoban(rows: Iterable[str]) -> tuple[SokobanLayout, SokobanState]:
    lines = tuple(str(row).rstrip("\n") for row in rows)
    if not lines:
        raise ValueError("sokoban level must not be empty")
    width = len(lines[0])
    if width == 0:
        raise ValueError("sokoban rows must not be empty")
    if any(len(line) != width for line in lines):
        raise ValueError("sokoban rows must have equal width")

    walls: list[Position] = []
    goals: list[Position] = []
    boxes: list[Position] = []
    players: list[Position] = []
    valid = {"#", " ", ".", "$", "*", "@", "+"}
    for row, line in enumerate(lines):
        for col, cell in enumerate(line):
            if cell not in valid:
                raise ValueError(f"unsupported sokoban tile: {cell!r}")
            pos = (row, col)
            if cell == "#":
                walls.append(pos)
            if cell in {".", "*", "+"}:
                goals.append(pos)
            if cell in {"$", "*"}:
                boxes.append(pos)
            if cell in {"@", "+"}:
                players.append(pos)
    if len(players) != 1:
        raise ValueError("sokoban level must contain exactly one player")
    if not goals:
        raise ValueError("sokoban level must contain at least one goal")
    if len(boxes) != len(goals):
        raise ValueError("sokoban level must contain the same number of boxes and goals")
    layout = SokobanLayout(
        height=len(lines),
        width=width,
        walls=tuple(sorted(walls)),
        goals=tuple(sorted(goals)),
    )
    return layout, SokobanState(boxes=_normalize_boxes(boxes), player=players[0])


def render_sokoban(layout: SokobanLayout, state: SokobanState) -> tuple[str, ...]:
    walls = layout.wall_set
    goals = layout.goal_set
    boxes = frozenset(state.boxes)
    rows: list[str] = []
    for row in range(layout.height):
        out = []
        for col in range(layout.width):
            pos = (row, col)
            if pos in walls:
                out.append("#")
            elif pos == state.player and pos in goals:
                out.append("+")
            elif pos == state.player:
                out.append("@")
            elif pos in boxes and pos in goals:
                out.append("*")
            elif pos in boxes:
                out.append("$")
            elif pos in goals:
                out.append(".")
            else:
                out.append(" ")
        rows.append("".join(out))
    return tuple(rows)


def is_solved(layout: SokobanLayout, state: SokobanState) -> bool:
    return frozenset(state.boxes) == layout.goal_set


def make_sokoban_candidate(
    layout: SokobanLayout,
    solved_state: SokobanState,
    predecessor: SokobanState,
    pushes: Iterable[PushAction],
    cost: int,
) -> TypedCandidate:
    pushes_tuple = tuple(_normalize_push(push) for push in pushes)
    return TypedCandidate(
        payload={
            "layout": layout,
            "solved_state": _normalize_state(solved_state),
            "predecessor": _normalize_state(predecessor),
            "pushes": pushes_tuple,
            "cost": int(cost),
        },
        type_name="sokoban.reverse_certificate",
        schema_version="sokoban.reverse_certificate.v1",
        hashes={
            "layout": stable_hash(layout),
            "solved_state": stable_hash(_normalize_state(solved_state)),
            "predecessor": stable_hash(_normalize_state(predecessor)),
            "pushes": stable_hash(pushes_tuple),
        },
    )


class SokobanReverseAdapter:
    verifier_id = "sokoban_forward_replay_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        layout = _coerce_layout(payload["layout"])
        solved_state = _coerce_state(payload["solved_state"])
        predecessor = _coerce_state(payload["predecessor"])
        pushes = tuple(_normalize_push(push) for push in payload["pushes"])
        metadata = {"cost": payload.get("cost", len(pushes)), "push_count": len(pushes)}
        try:
            replayed = replay_pushes(layout, predecessor, pushes)
        except ValueError as exc:
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={"reason": str(exc), "predecessor_hash": stable_hash(predecessor)},
                metadata=metadata,
            )
        if replayed == solved_state and is_solved(layout, replayed):
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={
                "replayed_hash": stable_hash(replayed),
                "solved_hash": stable_hash(solved_state),
                "replayed_solved": is_solved(layout, replayed),
            },
            metadata=metadata,
        )

    def apply_commit(self, state: SokobanState, candidate: TypedCandidate) -> SokobanState:
        return _coerce_state(candidate.payload["predecessor"])

    def replay(self, state: SokobanState, receipt: Any) -> SokobanState:
        return _coerce_state(receipt.replay_bundle["candidate_payload"]["predecessor"])

    def rollback(self, state: SokobanState, receipt: Any) -> SokobanState:
        pre_state = receipt.rollback_bundle["pre_state"]
        return _coerce_state(pre_state)


def replay_pushes(layout: SokobanLayout, state: SokobanState, pushes: Iterable[PushAction]) -> SokobanState:
    current = _normalize_state(state)
    for push in pushes:
        current = apply_push(layout, current, push)
    return current


def apply_push(layout: SokobanLayout, state: SokobanState, push: PushAction) -> SokobanState:
    action = _normalize_push(push)
    box = action["box"]
    delta = _direction_delta(action["direction"])
    boxes = set(state.boxes)
    if box not in boxes:
        raise ValueError(f"no box at push origin: {box}")
    stand = _sub(box, delta)
    dest = _add(box, delta)
    if not _is_open(layout, state.boxes, stand):
        raise ValueError(f"push stand cell is blocked: {stand}")
    if not reachable(layout, state.boxes, state.player, stand):
        raise ValueError(f"player cannot reach push stand cell: {stand}")
    boxes.remove(box)
    if not _is_open(layout, tuple(sorted(boxes)), dest):
        raise ValueError(f"push destination is blocked: {dest}")
    boxes.add(dest)
    return SokobanState(boxes=_normalize_boxes(boxes), player=box)


def reachable(layout: SokobanLayout, boxes: Iterable[Position], start: Position, target: Position) -> bool:
    box_set = frozenset(boxes)
    if start in box_set or target in box_set:
        return False
    if not _in_bounds(layout, start) or not _in_bounds(layout, target):
        return False
    if start in layout.wall_set or target in layout.wall_set:
        return False
    queue: deque[Position] = deque([start])
    seen = {start}
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        for _, delta in DIRECTIONS:
            nxt = _add(current, delta)
            if nxt in seen or nxt in box_set or nxt in layout.wall_set or not _in_bounds(layout, nxt):
                continue
            seen.add(nxt)
            queue.append(nxt)
    return False


def reverse_pull_traces(
    layout: SokobanLayout,
    solved_state: SokobanState,
    max_depth: int = 3,
    max_candidates: int = 64,
) -> tuple[tuple[ProposalTrace, TypedCandidate], int]:
    if max_depth <= 0:
        raise ValueError("max_depth must be positive")
    if max_candidates <= 0:
        raise ValueError("max_candidates must be positive")
    solved_state = _normalize_state(solved_state)
    queue: deque[SokobanSearchNode] = deque([SokobanSearchNode(solved_state, (), 0)])
    seen = {_state_key(solved_state)}
    candidates: list[tuple[ProposalTrace, TypedCandidate]] = []
    expansions = 0

    while queue and len(candidates) < max_candidates:
        node = queue.popleft()
        if node.depth >= max_depth:
            continue
        expansions += 1
        for box in node.state.boxes:
            for direction, delta in DIRECTIONS:
                previous_box = _sub(box, delta)
                previous_player = _sub(previous_box, delta)
                if not reachable(layout, node.state.boxes, node.state.player, previous_box):
                    continue
                boxes = set(node.state.boxes)
                boxes.remove(box)
                if not _is_open(layout, tuple(sorted(boxes)), previous_box):
                    continue
                boxes.add(previous_box)
                predecessor = SokobanState(boxes=_normalize_boxes(boxes), player=previous_player)
                if not _is_open(layout, predecessor.boxes, previous_player):
                    continue
                key = _state_key(predecessor)
                if key in seen:
                    continue
                seen.add(key)
                push = {"box": previous_box, "direction": direction}
                pushes = (push,) + node.pushes
                depth = node.depth + 1
                trace = ProposalTrace(
                    branch_id=f"sokoban-reverse-{len(candidates)}",
                    actions=pushes,
                    seeds=(stable_hash(solved_state), depth, len(candidates)),
                    model_version="reverse_pull.sokoban.v1",
                )
                candidate = make_sokoban_candidate(layout, solved_state, predecessor, pushes, cost=depth)
                candidates.append((trace, candidate))
                queue.append(SokobanSearchNode(predecessor, pushes, depth))
                if len(candidates) >= max_candidates:
                    break
            if len(candidates) >= max_candidates:
                break
    return tuple(candidates), expansions


def search_sokoban_predecessor(
    layout: SokobanLayout,
    solved_state: SokobanState,
    max_depth: int = 3,
    max_candidates: int = 64,
) -> SokobanReverseReport:
    if not is_solved(layout, solved_state):
        raise ValueError("solved_state must have every box on a goal")
    traces, expansions = reverse_pull_traces(layout, solved_state, max_depth=max_depth, max_candidates=max_candidates)
    adapter = SokobanReverseAdapter()
    engine = TransactionEngine(adapter=adapter)
    predecessor = None
    pushes: tuple[PushAction, ...] = ()
    committed = False
    for trace, candidate in traces:
        outcome = engine.transact(solved_state, trace, candidate)
        if outcome.committed:
            predecessor = outcome.state
            pushes = tuple(_normalize_push(push) for push in candidate.payload["pushes"])
            committed = True
            break
    replay_rate = 0.0
    if engine.ledger.audit():
        try:
            replay_rate = 1.0 if engine.rollback_audit(solved_state) == solved_state else 0.0
            engine.replay_audit(solved_state)
        except Exception:
            replay_rate = 0.0
    baseline = _baseline_state_count(layout)
    return SokobanReverseReport(
        solved=committed,
        predecessor=predecessor,
        solved_state=solved_state,
        pushes=pushes,
        verifier_calls=engine.hard_verifier_calls,
        reverse_expansions=expansions,
        max_depth=max_depth,
        baseline_state_count=baseline,
        verifier_call_reduction=baseline / engine.hard_verifier_calls if engine.hard_verifier_calls else 0.0,
        invalid_commit_count=engine.invalid_commit_count,
        ledger_audit=engine.ledger.audit(),
        replay_rollback_rate=replay_rate,
    )


def _baseline_state_count(layout: SokobanLayout) -> int:
    floor = layout.height * layout.width - len(layout.walls)
    return max(0, floor * max(0, floor - 1))


def _normalize_state(state: SokobanState) -> SokobanState:
    return SokobanState(boxes=_normalize_boxes(state.boxes), player=tuple(state.player))  # type: ignore[arg-type]


def _normalize_boxes(boxes: Iterable[Position]) -> tuple[Position, ...]:
    normalized = tuple(sorted((int(row), int(col)) for row, col in boxes))
    if len(set(normalized)) != len(normalized):
        raise ValueError("duplicate sokoban boxes are not allowed")
    return normalized


def _normalize_push(push: PushAction) -> dict[str, Any]:
    direction = str(push["direction"])
    _direction_delta(direction)
    row, col = push["box"]
    return {"box": (int(row), int(col)), "direction": direction}


def _coerce_layout(value: Any) -> SokobanLayout:
    if isinstance(value, SokobanLayout):
        return value
    return SokobanLayout(
        height=int(value["height"]),
        width=int(value["width"]),
        walls=_normalize_boxes(value["walls"]),
        goals=_normalize_boxes(value["goals"]),
    )


def _coerce_state(value: Any) -> SokobanState:
    if isinstance(value, SokobanState):
        return _normalize_state(value)
    return SokobanState(boxes=_normalize_boxes(value["boxes"]), player=tuple(value["player"]))  # type: ignore[arg-type]


def _direction_delta(direction: str) -> Position:
    for name, delta in DIRECTIONS:
        if direction == name:
            return delta
    raise ValueError(f"unknown sokoban direction: {direction!r}")


def _state_key(state: SokobanState) -> tuple[tuple[Position, ...], Position]:
    normalized = _normalize_state(state)
    return normalized.boxes, normalized.player


def _is_open(layout: SokobanLayout, boxes: Iterable[Position], pos: Position) -> bool:
    return _in_bounds(layout, pos) and pos not in layout.wall_set and pos not in frozenset(boxes)


def _in_bounds(layout: SokobanLayout, pos: Position) -> bool:
    row, col = pos
    return 0 <= row < layout.height and 0 <= col < layout.width


def _add(pos: Position, delta: Position) -> Position:
    return pos[0] + delta[0], pos[1] + delta[1]


def _sub(pos: Position, delta: Position) -> Position:
    return pos[0] - delta[0], pos[1] - delta[1]
