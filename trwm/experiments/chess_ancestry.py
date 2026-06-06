from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Mapping

from ..core import HardVerifierResult, Ledger, ProposalTrace, Receipt, TransactionEngine, TypedCandidate, stable_hash


FILES = "abcdefgh"
RANKS = "12345678"
COLORS = ("white", "black")
ROLES = ("K", "R")


@dataclass(frozen=True)
class ChessPiece:
    piece_id: str
    color: str
    role: str
    square: str


@dataclass(frozen=True)
class ChessBoard:
    pieces: tuple[ChessPiece, ...]
    side_to_move: str


@dataclass(frozen=True)
class ChessMove:
    piece_id: str
    from_square: str
    to_square: str
    captured_piece: ChessPiece | None = None


@dataclass(frozen=True)
class ChessAncestryProblem:
    target_board: ChessBoard
    moved_piece_id: str
    max_depth: int = 1


@dataclass(frozen=True)
class ChessAncestryState:
    problem: ChessAncestryProblem
    histories: tuple[ChessMove, ...] = ()


@dataclass(frozen=True)
class ChessAncestryEpisodeResult:
    calls: int
    success: bool
    audit_ok: bool
    replay_rollback_ok: bool


@dataclass(frozen=True)
class ChessAncestryReport:
    candidate_space_size: int
    history_count: int
    ambiguity_entropy: float
    verifier_calls: int
    forward_replay_success_rate: float
    static_calls_per_success: float
    repair_calls_per_success: float
    repair_gain: float
    ledger_audit: bool
    replay_rollback_rate: float
    invalid_commit_count: int
    learned_residual_kinds: Mapping[str, int]


class ChessAncestryAdapter:
    verifier_id = "bounded_rook_king_last_move_verifier"
    verifier_version = "1.0"

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        payload = candidate.payload
        problem = normalize_problem(payload["problem"])
        predecessor = normalize_board(payload["predecessor"])
        move = normalize_move(payload["move"])
        metadata = {
            "cost": payload.get("cost", 1),
            "candidate_space_size": len(reverse_chess_candidates(problem)),
        }
        error = validate_last_move(problem, predecessor, move)
        if error:
            return self._reject(error["kind"], {**error, "repair": diagnose_chess_ancestry(problem)}, metadata)
        return HardVerifierResult.accept(
            self.verifier_id,
            self.verifier_version,
            metadata={
                **metadata,
                "from_square": move.from_square,
                "to_square": move.to_square,
                "forward_replay_hash": stable_hash(apply_move(predecessor, move)),
            },
        )

    def apply_commit(self, state: ChessAncestryState, candidate: TypedCandidate) -> ChessAncestryState:
        current = normalize_state(state)
        problem = normalize_problem(candidate.payload["problem"])
        if current.problem != problem:
            raise ValueError("candidate problem does not match current chess ancestry state")
        move = normalize_move(candidate.payload["move"])
        histories = current.histories if move in current.histories else (*current.histories, move)
        return ChessAncestryState(problem=problem, histories=histories)

    def replay(self, state: ChessAncestryState, receipt: Receipt) -> ChessAncestryState:
        current = normalize_state(state)
        payload = receipt.replay_bundle["candidate_payload"]
        problem = normalize_problem(payload["problem"])
        if current.problem != problem:
            raise ValueError("receipt problem does not match replay chess ancestry state")
        move = normalize_move(payload["move"])
        histories = current.histories if move in current.histories else (*current.histories, move)
        return ChessAncestryState(problem=problem, histories=histories)

    def rollback(self, state: ChessAncestryState, receipt: Receipt) -> ChessAncestryState:
        return normalize_state(receipt.rollback_bundle["pre_state"])

    def _reject(self, kind: str, residual: Mapping[str, Any], metadata: Mapping[str, Any]) -> HardVerifierResult:
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={"kind": kind, **{k: v for k, v in residual.items() if k != "kind"}},
            metadata=metadata,
        )


class ChessResidualRepairer:
    def __init__(self) -> None:
        self.rejected_residuals: dict[str, int] = {}
        self.accepted_moves: dict[str, int] = {}

    def update(self, receipt: Receipt) -> None:
        if receipt.hard_result.accepted:
            payload = receipt.replay_bundle.get("candidate_payload", {}) if isinstance(receipt.replay_bundle, Mapping) else {}
            move = payload.get("move", {}) if isinstance(payload, Mapping) else {}
            key = "unknown"
            if isinstance(move, Mapping):
                key = f"{move.get('from_square', move.get('fromSquare'))}->{move.get('to_square', move.get('toSquare'))}"
            self.accepted_moves[key] = self.accepted_moves.get(key, 0) + 1
            return
        residual = receipt.hard_result.residual
        if receipt.hard_result.rejected and isinstance(residual, Mapping):
            kind = str(residual.get("kind", "unknown"))
            self.rejected_residuals[kind] = self.rejected_residuals.get(kind, 0) + 1

    def propose(self, candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate | None:
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        predecessor = repair.get("predecessor")
        move = repair.get("move")
        if predecessor is None or move is None:
            return None
        return make_chess_candidate(
            normalize_problem(candidate.payload["problem"]),
            normalize_board(predecessor),
            normalize_move(move),
            context=str(candidate.payload.get("context", "chess-repair")),
            cost=int(candidate.payload.get("cost", 1)) + 1,
        )


def normalize_piece(piece: ChessPiece | Mapping[str, Any]) -> ChessPiece:
    if isinstance(piece, ChessPiece):
        piece_id = piece.piece_id
        color = piece.color
        role = piece.role
        square = piece.square
    else:
        piece_id = piece.get("piece_id", piece.get("pieceId"))
        color = piece["color"]
        role = piece["role"]
        square = piece["square"]
    piece_id = str(piece_id)
    color = str(color)
    role = str(role)
    square = normalize_square(square)
    if not piece_id:
        raise ValueError("piece_id must be non-empty")
    if color not in COLORS:
        raise ValueError("unsupported chess color")
    if role not in ROLES:
        raise ValueError("this G1 canary supports only kings and rooks")
    return ChessPiece(piece_id=piece_id, color=color, role=role, square=square)


def normalize_board(board: ChessBoard | Mapping[str, Any]) -> ChessBoard:
    if isinstance(board, ChessBoard):
        pieces = board.pieces
        side_to_move = board.side_to_move
    else:
        pieces = board["pieces"]
        side_to_move = board.get("side_to_move", board.get("sideToMove"))
    side_to_move = str(side_to_move)
    if side_to_move not in COLORS:
        raise ValueError("side_to_move must be white or black")
    normalized = tuple(sorted((normalize_piece(piece) for piece in pieces), key=lambda piece: piece.piece_id))
    piece_ids = [piece.piece_id for piece in normalized]
    if len(set(piece_ids)) != len(piece_ids):
        raise ValueError("piece ids must be unique")
    squares = [piece.square for piece in normalized]
    if len(set(squares)) != len(squares):
        raise ValueError("piece squares must be unique")
    kings = [piece for piece in normalized if piece.role == "K"]
    if sorted(piece.color for piece in kings) != ["black", "white"]:
        raise ValueError("board must contain exactly one white king and one black king")
    if max(abs(coord(kings[0].square)[0] - coord(kings[1].square)[0]), abs(coord(kings[0].square)[1] - coord(kings[1].square)[1])) <= 1:
        raise ValueError("kings may not be adjacent")
    return ChessBoard(pieces=normalized, side_to_move=side_to_move)


def normalize_move(move: ChessMove | Mapping[str, Any]) -> ChessMove:
    if isinstance(move, ChessMove):
        piece_id = move.piece_id
        from_square = move.from_square
        to_square = move.to_square
        captured_piece = move.captured_piece
    else:
        piece_id = move.get("piece_id", move.get("pieceId"))
        from_square = move.get("from_square", move.get("fromSquare"))
        to_square = move.get("to_square", move.get("toSquare"))
        captured_piece = move.get("captured_piece", move.get("capturedPiece"))
    return ChessMove(
        piece_id=str(piece_id),
        from_square=normalize_square(from_square),
        to_square=normalize_square(to_square),
        captured_piece=normalize_piece(captured_piece) if captured_piece is not None else None,
    )


def normalize_problem(problem: ChessAncestryProblem | Mapping[str, Any]) -> ChessAncestryProblem:
    if isinstance(problem, ChessAncestryProblem):
        target_board = problem.target_board
        moved_piece_id = problem.moved_piece_id
        max_depth = problem.max_depth
    else:
        target_board = problem.get("target_board", problem.get("targetBoard"))
        moved_piece_id = problem.get("moved_piece_id", problem.get("movedPieceId"))
        max_depth = problem.get("max_depth", problem.get("maxDepth", 1))
    max_depth = int(max_depth)
    if max_depth != 1:
        raise ValueError("this G1 canary supports last-move depth 1 only")
    board = normalize_board(target_board)
    moved_piece_id = str(moved_piece_id)
    if moved_piece_id not in {piece.piece_id for piece in board.pieces}:
        raise ValueError("moved_piece_id must identify a target-board piece")
    return ChessAncestryProblem(target_board=board, moved_piece_id=moved_piece_id, max_depth=max_depth)


def normalize_state(state: ChessAncestryState | Mapping[str, Any]) -> ChessAncestryState:
    if isinstance(state, ChessAncestryState):
        return ChessAncestryState(problem=normalize_problem(state.problem), histories=tuple(normalize_move(move) for move in state.histories))
    return ChessAncestryState(
        problem=normalize_problem(state["problem"]),
        histories=tuple(normalize_move(move) for move in state.get("histories", ())),
    )


def normalize_square(value: Any) -> str:
    square = str(value)
    if len(square) != 2 or square[0] not in FILES or square[1] not in RANKS:
        raise ValueError(f"invalid chess square: {square}")
    return square


def coord(square: str) -> tuple[int, int]:
    square = normalize_square(square)
    return FILES.index(square[0]), RANKS.index(square[1])


def square(file_idx: int, rank_idx: int) -> str:
    if not (0 <= file_idx < 8 and 0 <= rank_idx < 8):
        raise ValueError("square coordinate out of bounds")
    return f"{FILES[file_idx]}{RANKS[rank_idx]}"


def opposite(color: str) -> str:
    color = str(color)
    if color == "white":
        return "black"
    if color == "black":
        return "white"
    raise ValueError("unsupported color")


def piece_at(board_input: ChessBoard, target_square: str) -> ChessPiece | None:
    board = normalize_board(board_input)
    target_square = normalize_square(target_square)
    return next((piece for piece in board.pieces if piece.square == target_square), None)


def piece_by_id(board_input: ChessBoard, piece_id: str) -> ChessPiece | None:
    board = normalize_board(board_input)
    return next((piece for piece in board.pieces if piece.piece_id == piece_id), None)


def path_clear(board_input: ChessBoard, from_square: str, to_square: str) -> bool:
    board = normalize_board(board_input)
    fx, fy = coord(from_square)
    tx, ty = coord(to_square)
    dx = 0 if tx == fx else (1 if tx > fx else -1)
    dy = 0 if ty == fy else (1 if ty > fy else -1)
    if dx != 0 and dy != 0:
        return False
    x, y = fx + dx, fy + dy
    occupied = {piece.square for piece in board.pieces}
    while (x, y) != (tx, ty):
        if square(x, y) in occupied:
            return False
        x += dx
        y += dy
    return True


def attacks_square(board_input: ChessBoard, piece: ChessPiece, target_square: str) -> bool:
    board = normalize_board(board_input)
    target_square = normalize_square(target_square)
    px, py = coord(piece.square)
    tx, ty = coord(target_square)
    if piece.role == "K":
        return max(abs(px - tx), abs(py - ty)) == 1
    if piece.role == "R":
        return (px == tx or py == ty) and path_clear(board, piece.square, target_square)
    return False


def king_in_check(board_input: ChessBoard, color: str) -> bool:
    board = normalize_board(board_input)
    king = next(piece for piece in board.pieces if piece.color == color and piece.role == "K")
    return any(piece.color != color and attacks_square(board, piece, king.square) for piece in board.pieces)


def board_legality_error(board_input: ChessBoard) -> str | None:
    board = normalize_board(board_input)
    if king_in_check(board, opposite(board.side_to_move)):
        return "side-not-to-move king may not already be in check"
    return None


def pseudo_legal_move(board_input: ChessBoard, move_input: ChessMove) -> str | None:
    board = normalize_board(board_input)
    move = normalize_move(move_input)
    piece = piece_by_id(board, move.piece_id)
    if piece is None:
        return "moving piece is absent from predecessor"
    if piece.color != board.side_to_move:
        return "moving piece color must match side_to_move"
    if piece.square != move.from_square:
        return "move from_square must match piece square"
    destination = piece_at(board, move.to_square)
    if destination is not None and destination.color == piece.color:
        return "destination occupied by same color"
    if destination is not None and (move.captured_piece is None or normalize_piece(move.captured_piece) != destination):
        return "captured_piece must match destination occupant"
    if destination is None and move.captured_piece is not None:
        return "captured_piece supplied for empty destination"
    fx, fy = coord(move.from_square)
    tx, ty = coord(move.to_square)
    if (fx, fy) == (tx, ty):
        return "move must change square"
    if piece.role == "K":
        if max(abs(fx - tx), abs(fy - ty)) != 1:
            return "king move must be one square"
    elif piece.role == "R":
        if fx != tx and fy != ty:
            return "rook move must be orthogonal"
        if not path_clear(board, move.from_square, move.to_square):
            return "rook path is blocked"
    return None


def apply_move(board_input: ChessBoard, move_input: ChessMove) -> ChessBoard:
    board = normalize_board(board_input)
    move = normalize_move(move_input)
    moving = piece_by_id(board, move.piece_id)
    if moving is None:
        raise ValueError("moving piece is absent")
    pieces: list[ChessPiece] = []
    for piece in board.pieces:
        if piece.piece_id == move.piece_id:
            pieces.append(ChessPiece(piece.piece_id, piece.color, piece.role, move.to_square))
        elif piece.square == move.to_square and piece.color != moving.color:
            continue
        else:
            pieces.append(piece)
    return normalize_board(ChessBoard(pieces=tuple(pieces), side_to_move=opposite(board.side_to_move)))


def validate_last_move(problem_input: ChessAncestryProblem, predecessor_input: ChessBoard, move_input: ChessMove) -> dict[str, Any] | None:
    problem = normalize_problem(problem_input)
    predecessor = normalize_board(predecessor_input)
    move = normalize_move(move_input)
    if predecessor.side_to_move != opposite(problem.target_board.side_to_move):
        return {"kind": "schema_error", "message": "predecessor side_to_move must be the last mover"}
    if move.piece_id != problem.moved_piece_id:
        return {"kind": "schema_error", "message": "candidate move must use moved_piece_id"}
    legality = board_legality_error(predecessor)
    if legality:
        return {"kind": "illegal_predecessor", "message": legality}
    pseudo = pseudo_legal_move(predecessor, move)
    if pseudo:
        return {"kind": "illegal_move", "message": pseudo}
    post = apply_move(predecessor, move)
    mover = predecessor.side_to_move
    if king_in_check(post, mover):
        return {"kind": "king_left_in_check", "message": "move leaves mover king in check"}
    if post != problem.target_board:
        return {"kind": "forward_replay_mismatch", "message": "forward replay does not equal target board"}
    return None


def reverse_chess_candidates(problem_input: ChessAncestryProblem) -> tuple[TypedCandidate, ...]:
    problem = normalize_problem(problem_input)
    target = problem.target_board
    moved = piece_by_id(target, problem.moved_piece_id)
    if moved is None:
        return ()
    occupied = {piece.square for piece in target.pieces}
    candidates: list[TypedCandidate] = []
    for from_square in _reverse_from_squares(moved):
        if from_square == moved.square or from_square in occupied:
            continue
        predecessor_pieces = tuple(
            ChessPiece(piece.piece_id, piece.color, piece.role, from_square) if piece.piece_id == moved.piece_id else piece
            for piece in target.pieces
        )
        predecessor = normalize_board(ChessBoard(predecessor_pieces, side_to_move=moved.color))
        move = ChessMove(moved.piece_id, from_square, moved.square)
        candidates.append(make_chess_candidate(problem, predecessor, move, context="chess-static", cost=len(candidates) + 1))
    return tuple(candidates)


def diagnose_chess_ancestry(problem_input: ChessAncestryProblem) -> dict[str, Any] | None:
    for candidate in reverse_chess_candidates(problem_input):
        problem = normalize_problem(candidate.payload["problem"])
        predecessor = normalize_board(candidate.payload["predecessor"])
        move = normalize_move(candidate.payload["move"])
        if validate_last_move(problem, predecessor, move) is None:
            return {
                "predecessor": predecessor,
                "move": move,
                "target_board": problem.target_board,
            }
    return None


def make_chess_candidate(
    problem: ChessAncestryProblem,
    predecessor: ChessBoard,
    move: ChessMove,
    context: str = "chess-ancestry",
    cost: int = 1,
) -> TypedCandidate:
    problem = normalize_problem(problem)
    predecessor = normalize_board(predecessor)
    move = normalize_move(move)
    return TypedCandidate(
        payload={
            "context": context,
            "problem": problem,
            "predecessor": predecessor,
            "move": move,
            "cost": cost,
        },
        type_name="chess.rook_king_last_move",
        schema_version="chess.rook_king_last_move.v1",
        hashes={
            "problem": stable_hash(problem),
            "predecessor": stable_hash(predecessor),
            "move": stable_hash(move),
        },
    )


def make_default_chess_ancestry_problem() -> ChessAncestryProblem:
    target = ChessBoard(
        side_to_move="black",
        pieces=(
            ChessPiece("WK", "white", "K", "a1"),
            ChessPiece("WR", "white", "R", "e4"),
            ChessPiece("BK", "black", "K", "h8"),
            ChessPiece("BR1", "black", "R", "e2"),
            ChessPiece("BR2", "black", "R", "e3"),
            ChessPiece("BR3", "black", "R", "b4"),
            ChessPiece("BR4", "black", "R", "c4"),
            ChessPiece("BR5", "black", "R", "d4"),
            ChessPiece("BR6", "black", "R", "f4"),
            ChessPiece("BR7", "black", "R", "g4"),
        ),
    )
    return normalize_problem(ChessAncestryProblem(target_board=target, moved_piece_id="WR"))


def enumerate_chess_ancestry(problem: ChessAncestryProblem, ledger: Ledger | None = None) -> tuple[ChessAncestryState, TransactionEngine]:
    problem = normalize_problem(problem)
    engine = TransactionEngine(ChessAncestryAdapter(), ledger=ledger or Ledger())
    state = ChessAncestryState(problem=problem)
    for idx, candidate in enumerate(reverse_chess_candidates(problem), start=1):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"chess-enumerate-{idx}",
                actions=(candidate.payload["move"],),
                seeds=("chess", idx),
                model_version="chess.enumerate.v1",
            ),
            candidate,
        )
        if outcome.committed:
            state = outcome.state
    return state, engine


def run_static_chess_episode(problem: ChessAncestryProblem, ledger: Ledger, episode: int) -> ChessAncestryEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(ChessAncestryAdapter(), ledger=ledger)
    state = ChessAncestryState(problem=problem)
    for idx, candidate in enumerate(reverse_chess_candidates(problem), start=1):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"chess-static-{episode}-{idx}",
                actions=(candidate.payload["move"],),
                seeds=(episode, idx),
                model_version="chess.static.v1",
            ),
            candidate,
        )
        if outcome.committed:
            return _episode_result(idx, True, engine, state)
    return _episode_result(engine.hard_verifier_calls, False, engine, state)


def run_repair_chess_episode(
    problem: ChessAncestryProblem,
    ledger: Ledger,
    repairer: ChessResidualRepairer,
    episode: int,
) -> ChessAncestryEpisodeResult:
    problem = normalize_problem(problem)
    engine = TransactionEngine(ChessAncestryAdapter(), ledger=ledger)
    state = ChessAncestryState(problem=problem)
    target_piece = piece_by_id(problem.target_board, problem.moved_piece_id)
    assert target_piece is not None
    bad_predecessor = normalize_board(
        ChessBoard(
            pieces=tuple(
                ChessPiece(piece.piece_id, piece.color, piece.role, "e1") if piece.piece_id == target_piece.piece_id else piece
                for piece in problem.target_board.pieces
            ),
            side_to_move=target_piece.color,
        )
    )
    candidate = make_chess_candidate(problem, bad_predecessor, ChessMove(target_piece.piece_id, "e1", target_piece.square), context="chess-repair", cost=1)
    for attempt in range(3):
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id=f"chess-repair-{episode}-{attempt}",
                actions=(candidate.payload["move"],),
                seeds=(episode, attempt),
                model_version="chess.residual_repair.v1",
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


def run_chess_ancestry_benchmark() -> ChessAncestryReport:
    problem = make_default_chess_ancestry_problem()
    enumeration_ledger = Ledger()
    enumerated_state, enumeration_engine = enumerate_chess_ancestry(problem, enumeration_ledger)
    history_count = len(enumerated_state.histories)
    candidate_space_size = len(reverse_chess_candidates(problem))
    forward_rate = _forward_replay_success_rate(problem, enumerated_state.histories)
    static_ledger = Ledger()
    repair_ledger = Ledger()
    repairer = ChessResidualRepairer()
    static = run_static_chess_episode(problem, static_ledger, 0)
    repair = run_repair_chess_episode(problem, repair_ledger, repairer, 0)
    static_cps = static.calls if static.success else float("inf")
    repair_cps = repair.calls if repair.success else float("inf")
    return ChessAncestryReport(
        candidate_space_size=candidate_space_size,
        history_count=history_count,
        ambiguity_entropy=math.log2(history_count) if history_count else 0.0,
        verifier_calls=enumeration_engine.hard_verifier_calls,
        forward_replay_success_rate=forward_rate,
        static_calls_per_success=static_cps,
        repair_calls_per_success=repair_cps,
        repair_gain=static_cps / repair_cps,
        ledger_audit=enumeration_engine.ledger.audit() and static_ledger.audit() and repair_ledger.audit(),
        replay_rollback_rate=sum(1 for row in (static, repair) if row.replay_rollback_ok) / 2,
        invalid_commit_count=_invalid_commits((enumeration_ledger, static_ledger, repair_ledger)),
        learned_residual_kinds=dict(repairer.rejected_residuals),
    )


def _reverse_from_squares(piece: ChessPiece) -> tuple[str, ...]:
    px, py = coord(piece.square)
    if piece.role == "K":
        squares = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                x, y = px + dx, py + dy
                if 0 <= x < 8 and 0 <= y < 8:
                    squares.append(square(x, y))
        return tuple(sorted(squares, key=coord))
    if piece.role == "R":
        squares = [square(px, y) for y in range(8) if y != py]
        squares.extend(square(x, py) for x in range(8) if x != px)
        return tuple(sorted(squares, key=coord))
    return ()


def _forward_replay_success_rate(problem: ChessAncestryProblem, histories: Iterable[ChessMove]) -> float:
    rows = tuple(histories)
    if not rows:
        return 0.0
    ok = 0
    legal = {normalize_move(candidate.payload["move"]): normalize_board(candidate.payload["predecessor"]) for candidate in reverse_chess_candidates(problem)}
    for move in rows:
        predecessor = legal.get(move)
        if predecessor is not None and apply_move(predecessor, move) == normalize_problem(problem).target_board:
            ok += 1
    return ok / len(rows)


def _episode_result(calls: int, success: bool, engine: TransactionEngine, seed_state: ChessAncestryState) -> ChessAncestryEpisodeResult:
    audit_ok = engine.ledger.audit()
    replay_rollback_ok = False
    if audit_ok:
        try:
            engine.replay_audit(seed_state)
            replay_rollback_ok = engine.rollback_audit(seed_state) == seed_state
        except Exception:
            replay_rollback_ok = False
    return ChessAncestryEpisodeResult(calls=calls, success=success, audit_ok=audit_ok, replay_rollback_ok=replay_rollback_ok)


def _invalid_commits(ledgers: Iterable[Ledger]) -> int:
    return sum(1 for ledger in ledgers for row in ledger.rows if row.committed and not row.hard_result.accepted)
