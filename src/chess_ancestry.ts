import {
  type HardVerifierResult,
  type Receipt,
  type ReplayRollbackAdapter,
  type TypedCandidate,
  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { stableHash } from "./canonical.js";

export type ChessColor = "white" | "black";
export type ChessRole = "K" | "R";

export const CHESS_FILES = "abcdefgh";
export const CHESS_RANKS = "12345678";

export interface ChessPiece {
  pieceId: string;
  color: ChessColor;
  role: ChessRole;
  square: string;
}

export interface ChessBoard {
  pieces: ChessPiece[];
  sideToMove: ChessColor;
}

export interface ChessMove {
  pieceId: string;
  fromSquare: string;
  toSquare: string;
  capturedPiece?: ChessPiece | null;
}

export interface ChessAncestryProblem {
  targetBoard: ChessBoard;
  movedPieceId: string;
  maxDepth: number;
}

export interface ChessAncestryState {
  problem: ChessAncestryProblem;
  histories: ChessMove[];
}

export interface ChessCandidatePayload {
  context: string;
  problem: ChessAncestryProblem;
  predecessor: ChessBoard;
  move: ChessMove;
  cost: number;
}

export interface ChessResidual {
  kind: "schema_error" | "illegal_predecessor" | "illegal_move" | "king_left_in_check" | "forward_replay_mismatch";
  message?: string;
  repair?: {
    predecessor: ChessBoard;
    move: ChessMove;
    targetBoard: ChessBoard;
  } | null;
}

export interface ChessAncestryEpisodeResult {
  calls: number;
  success: boolean;
  auditOk: boolean;
  replayRollbackOk: boolean;
}

export interface ChessAncestryReport {
  candidateSpaceSize: number;
  historyCount: number;
  ambiguityEntropy: number;
  verifierCalls: number;
  forwardReplaySuccessRate: number;
  staticCallsPerSuccess: number;
  repairCallsPerSuccess: number;
  repairGain: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
  invalidCommitCount: number;
  learnedResidualKinds: Record<string, number>;
}

export class ChessAncestryAdapter implements ReplayRollbackAdapter<ChessAncestryState, ChessCandidatePayload> {
  verifierId = "bounded_rook_king_last_move_verifier";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<ChessCandidatePayload>): HardVerifierResult {
    const problem = normalizeChessProblem(candidate.payload.problem);
    const predecessor = normalizeBoard(candidate.payload.predecessor);
    const move = normalizeMove(candidate.payload.move);
    const metadata = {
      cost: candidate.payload.cost,
      candidateSpaceSize: reverseChessCandidates(problem).length,
    };
    const error = validateLastMove(problem, predecessor, move);
    if (error) {
      return this.reject(error.kind, { ...error, repair: diagnoseChessAncestry(problem) }, metadata);
    }
    return hardAccept(this.verifierId, this.verifierVersion, {
      ...metadata,
      fromSquare: move.fromSquare,
      toSquare: move.toSquare,
    });
  }

  applyCommit(state: ChessAncestryState, candidate: TypedCandidate<ChessCandidatePayload>): ChessAncestryState {
    const current = normalizeChessState(state);
    const problem = normalizeChessProblem(candidate.payload.problem);
    if (!chessProblemsEqual(current.problem, problem)) {
      throw new Error("candidate problem does not match current chess ancestry state");
    }
    const move = normalizeMove(candidate.payload.move);
    return { problem, histories: appendHistory(current.histories, move) };
  }

  replay(state: ChessAncestryState, receipt: Receipt): ChessAncestryState {
    const current = normalizeChessState(state);
    const payload = (receipt.replayBundle as { candidatePayload: ChessCandidatePayload }).candidatePayload;
    const problem = normalizeChessProblem(payload.problem);
    if (!chessProblemsEqual(current.problem, problem)) {
      throw new Error("receipt problem does not match replay chess ancestry state");
    }
    const move = normalizeMove(payload.move);
    return { problem, histories: appendHistory(current.histories, move) };
  }

  rollback(_state: ChessAncestryState, receipt: Receipt): ChessAncestryState {
    return normalizeChessState((receipt.rollbackBundle as { preState: ChessAncestryState }).preState);
  }

  private reject(kind: ChessResidual["kind"], residual: Omit<ChessResidual, "kind">, metadata: Record<string, unknown>): HardVerifierResult {
    return hardReject(this.verifierId, this.verifierVersion, { kind, ...residual }, metadata);
  }
}

export class ChessResidualRepairer {
  rejectedResiduals = new Map<string, number>();
  acceptedMoves = new Map<string, number>();

  update(receipt: Receipt): void {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle as Record<string, unknown>
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload as Partial<ChessCandidatePayload>
      : {};
    if (receipt.hardResult.result === "accept") {
      const move = payload.move;
      const key = move ? `${move.fromSquare}->${move.toSquare}` : "unknown";
      this.acceptedMoves.set(key, (this.acceptedMoves.get(key) ?? 0) + 1);
      return;
    }
    if (receipt.hardResult.result === "reject" && isChessResidual(receipt.hardResult.residual)) {
      const kind = receipt.hardResult.residual.kind;
      this.rejectedResiduals.set(kind, (this.rejectedResiduals.get(kind) ?? 0) + 1);
    }
  }

  async propose(candidate: TypedCandidate<ChessCandidatePayload>, residual: unknown): Promise<TypedCandidate<ChessCandidatePayload> | null> {
    if (!isChessResidual(residual) || !residual.repair) {
      return null;
    }
    return makeChessCandidate(
      normalizeChessProblem(candidate.payload.problem),
      normalizeBoard(residual.repair.predecessor),
      normalizeMove(residual.repair.move),
      candidate.payload.context || "chess-repair",
      candidate.payload.cost + 1,
    );
  }
}

export function normalizePiece(pieceInput: ChessPiece | Record<string, unknown>): ChessPiece {
  const raw = pieceInput as Record<string, unknown>;
  const pieceId = raw.pieceId ?? raw.piece_id;
  if (typeof pieceId !== "string" || pieceId.length === 0) {
    throw new RangeError("pieceId must be non-empty");
  }
  return {
    pieceId,
    color: normalizeColor(raw.color),
    role: normalizeRole(raw.role),
    square: normalizeSquare(raw.square),
  };
}

export function normalizeBoard(boardInput: ChessBoard | Record<string, unknown>): ChessBoard {
  const raw = boardInput as Record<string, unknown>;
  const piecesInput = raw.pieces;
  if (!Array.isArray(piecesInput)) {
    throw new RangeError("board pieces must be an array");
  }
  const pieces = piecesInput.map((piece) => normalizePiece(piece as ChessPiece | Record<string, unknown>))
    .sort((a, b) => a.pieceId < b.pieceId ? -1 : a.pieceId > b.pieceId ? 1 : 0);
  if (new Set(pieces.map((piece) => piece.pieceId)).size !== pieces.length) {
    throw new RangeError("piece ids must be unique");
  }
  if (new Set(pieces.map((piece) => piece.square)).size !== pieces.length) {
    throw new RangeError("piece squares must be unique");
  }
  const kings = pieces.filter((piece) => piece.role === "K");
  if (kings.length !== 2 || !kings.some((piece) => piece.color === "white") || !kings.some((piece) => piece.color === "black")) {
    throw new RangeError("board must contain exactly one white king and one black king");
  }
  const [kx0, ky0] = coord(kings[0].square);
  const [kx1, ky1] = coord(kings[1].square);
  if (Math.max(Math.abs(kx0 - kx1), Math.abs(ky0 - ky1)) <= 1) {
    throw new RangeError("kings may not be adjacent");
  }
  return { pieces, sideToMove: normalizeColor(raw.sideToMove ?? raw.side_to_move) };
}

export function normalizeMove(moveInput: ChessMove | Record<string, unknown>): ChessMove {
  const raw = moveInput as Record<string, unknown>;
  const pieceId = raw.pieceId ?? raw.piece_id;
  if (typeof pieceId !== "string" || pieceId.length === 0) {
    throw new RangeError("move pieceId must be non-empty");
  }
  const captured = raw.capturedPiece ?? raw.captured_piece;
  return {
    pieceId,
    fromSquare: normalizeSquare(raw.fromSquare ?? raw.from_square),
    toSquare: normalizeSquare(raw.toSquare ?? raw.to_square),
    capturedPiece: captured == null ? null : normalizePiece(captured as ChessPiece | Record<string, unknown>),
  };
}

export function normalizeChessProblem(problemInput: ChessAncestryProblem | Record<string, unknown>): ChessAncestryProblem {
  const raw = problemInput as Record<string, unknown>;
  const targetBoard = normalizeBoard((raw.targetBoard ?? raw.target_board) as ChessBoard | Record<string, unknown>);
  const movedPieceId = raw.movedPieceId ?? raw.moved_piece_id;
  const maxDepth = Number(raw.maxDepth ?? raw.max_depth ?? 1);
  if (!Number.isInteger(maxDepth) || maxDepth !== 1) {
    throw new RangeError("this G1 canary supports last-move depth 1 only");
  }
  if (typeof movedPieceId !== "string" || !targetBoard.pieces.some((piece) => piece.pieceId === movedPieceId)) {
    throw new RangeError("movedPieceId must identify a target-board piece");
  }
  return { targetBoard, movedPieceId, maxDepth };
}

export function normalizeChessState(stateInput: ChessAncestryState | Record<string, unknown>): ChessAncestryState {
  const raw = stateInput as Record<string, unknown>;
  const historiesInput = raw.histories ?? [];
  if (!Array.isArray(historiesInput)) {
    throw new RangeError("histories must be an array");
  }
  return {
    problem: normalizeChessProblem(raw.problem as ChessAncestryProblem | Record<string, unknown>),
    histories: historiesInput.map((move) => normalizeMove(move as ChessMove | Record<string, unknown>)),
  };
}

export function normalizeSquare(value: unknown): string {
  const square = String(value);
  if (square.length !== 2 || !CHESS_FILES.includes(square[0]) || !CHESS_RANKS.includes(square[1])) {
    throw new RangeError(`invalid chess square: ${square}`);
  }
  return square;
}

export function coord(squareInput: string): [number, number] {
  const sq = normalizeSquare(squareInput);
  return [CHESS_FILES.indexOf(sq[0]), CHESS_RANKS.indexOf(sq[1])];
}

export function square(fileIdx: number, rankIdx: number): string {
  if (!Number.isInteger(fileIdx) || !Number.isInteger(rankIdx) || fileIdx < 0 || fileIdx >= 8 || rankIdx < 0 || rankIdx >= 8) {
    throw new RangeError("square coordinate out of bounds");
  }
  return `${CHESS_FILES[fileIdx]}${CHESS_RANKS[rankIdx]}`;
}

export function opposite(colorInput: ChessColor | string): ChessColor {
  const color = normalizeColor(colorInput);
  return color === "white" ? "black" : "white";
}

export function pieceAt(boardInput: ChessBoard, targetSquareInput: string): ChessPiece | null {
  const board = normalizeBoard(boardInput);
  const targetSquare = normalizeSquare(targetSquareInput);
  return board.pieces.find((piece) => piece.square === targetSquare) ?? null;
}

export function pieceById(boardInput: ChessBoard, pieceId: string): ChessPiece | null {
  const board = normalizeBoard(boardInput);
  return board.pieces.find((piece) => piece.pieceId === pieceId) ?? null;
}

export function pathClear(boardInput: ChessBoard, fromSquareInput: string, toSquareInput: string): boolean {
  const board = normalizeBoard(boardInput);
  const [fx, fy] = coord(fromSquareInput);
  const [tx, ty] = coord(toSquareInput);
  const dx = tx === fx ? 0 : tx > fx ? 1 : -1;
  const dy = ty === fy ? 0 : ty > fy ? 1 : -1;
  if (dx !== 0 && dy !== 0) {
    return false;
  }
  const occupied = new Set(board.pieces.map((piece) => piece.square));
  let x = fx + dx;
  let y = fy + dy;
  while (x !== tx || y !== ty) {
    if (occupied.has(square(x, y))) {
      return false;
    }
    x += dx;
    y += dy;
  }
  return true;
}

export function attacksSquare(boardInput: ChessBoard, pieceInput: ChessPiece, targetSquareInput: string): boolean {
  const board = normalizeBoard(boardInput);
  const piece = normalizePiece(pieceInput);
  const [px, py] = coord(piece.square);
  const [tx, ty] = coord(targetSquareInput);
  if (piece.role === "K") {
    return Math.max(Math.abs(px - tx), Math.abs(py - ty)) === 1;
  }
  if (piece.role === "R") {
    return (px === tx || py === ty) && pathClear(board, piece.square, targetSquareInput);
  }
  return false;
}

export function kingInCheck(boardInput: ChessBoard, colorInput: ChessColor | string): boolean {
  const board = normalizeBoard(boardInput);
  const color = normalizeColor(colorInput);
  const king = board.pieces.find((piece) => piece.color === color && piece.role === "K");
  if (!king) {
    throw new RangeError("king missing");
  }
  return board.pieces.some((piece) => piece.color !== color && attacksSquare(board, piece, king.square));
}

export function boardLegalityError(boardInput: ChessBoard): string | null {
  const board = normalizeBoard(boardInput);
  return kingInCheck(board, opposite(board.sideToMove)) ? "side-not-to-move king may not already be in check" : null;
}

export function pseudoLegalMove(boardInput: ChessBoard, moveInput: ChessMove): string | null {
  const board = normalizeBoard(boardInput);
  const move = normalizeMove(moveInput);
  const piece = pieceById(board, move.pieceId);
  if (!piece) return "moving piece is absent from predecessor";
  if (piece.color !== board.sideToMove) return "moving piece color must match sideToMove";
  if (piece.square !== move.fromSquare) return "move fromSquare must match piece square";
  const destination = pieceAt(board, move.toSquare);
  if (destination && destination.color === piece.color) return "destination occupied by same color";
  if (destination && (!move.capturedPiece || JSON.stringify(normalizePiece(move.capturedPiece)) !== JSON.stringify(destination))) {
    return "capturedPiece must match destination occupant";
  }
  if (!destination && move.capturedPiece) return "capturedPiece supplied for empty destination";
  const [fx, fy] = coord(move.fromSquare);
  const [tx, ty] = coord(move.toSquare);
  if (fx === tx && fy === ty) return "move must change square";
  if (piece.role === "K") {
    return Math.max(Math.abs(fx - tx), Math.abs(fy - ty)) === 1 ? null : "king move must be one square";
  }
  if (piece.role === "R") {
    if (fx !== tx && fy !== ty) return "rook move must be orthogonal";
    return pathClear(board, move.fromSquare, move.toSquare) ? null : "rook path is blocked";
  }
  return "unsupported piece role";
}

export function applyChessMove(boardInput: ChessBoard, moveInput: ChessMove): ChessBoard {
  const board = normalizeBoard(boardInput);
  const move = normalizeMove(moveInput);
  const moving = pieceById(board, move.pieceId);
  if (!moving) {
    throw new RangeError("moving piece is absent");
  }
  const pieces = board.pieces.flatMap((piece) => {
    if (piece.pieceId === move.pieceId) {
      return [{ ...piece, square: move.toSquare }];
    }
    if (piece.square === move.toSquare && piece.color !== moving.color) {
      return [];
    }
    return [piece];
  });
  return normalizeBoard({ pieces, sideToMove: opposite(board.sideToMove) });
}

export function validateLastMove(problemInput: ChessAncestryProblem, predecessorInput: ChessBoard, moveInput: ChessMove): ChessResidual | null {
  const problem = normalizeChessProblem(problemInput);
  const predecessor = normalizeBoard(predecessorInput);
  const move = normalizeMove(moveInput);
  if (predecessor.sideToMove !== opposite(problem.targetBoard.sideToMove)) {
    return { kind: "schema_error", message: "predecessor sideToMove must be the last mover" };
  }
  if (move.pieceId !== problem.movedPieceId) {
    return { kind: "schema_error", message: "candidate move must use movedPieceId" };
  }
  const boardError = boardLegalityError(predecessor);
  if (boardError) {
    return { kind: "illegal_predecessor", message: boardError };
  }
  const pseudo = pseudoLegalMove(predecessor, move);
  if (pseudo) {
    return { kind: "illegal_move", message: pseudo };
  }
  const post = applyChessMove(predecessor, move);
  if (kingInCheck(post, predecessor.sideToMove)) {
    return { kind: "king_left_in_check", message: "move leaves mover king in check" };
  }
  if (!boardsEqual(post, problem.targetBoard)) {
    return { kind: "forward_replay_mismatch", message: "forward replay does not equal target board" };
  }
  return null;
}

export function reverseChessCandidates(problemInput: ChessAncestryProblem): Array<TypedCandidate<ChessCandidatePayload>> {
  const problem = normalizeChessProblem(problemInput);
  const target = problem.targetBoard;
  const moved = pieceById(target, problem.movedPieceId);
  if (!moved) return [];
  const occupied = new Set(target.pieces.map((piece) => piece.square));
  const candidates: Array<TypedCandidate<ChessCandidatePayload>> = [];
  for (const fromSquare of reverseFromSquares(moved)) {
    if (fromSquare === moved.square || occupied.has(fromSquare)) {
      continue;
    }
    const predecessor = normalizeBoard({
      pieces: target.pieces.map((piece) => piece.pieceId === moved.pieceId ? { ...piece, square: fromSquare } : piece),
      sideToMove: moved.color,
    });
    const move = { pieceId: moved.pieceId, fromSquare, toSquare: moved.square, capturedPiece: null };
    candidates.push(makeChessCandidateSync(problem, predecessor, move, "chess-static", candidates.length + 1));
  }
  return candidates;
}

export function diagnoseChessAncestry(problemInput: ChessAncestryProblem): ChessResidual["repair"] {
  const problem = normalizeChessProblem(problemInput);
  for (const candidate of reverseChessCandidates(problem)) {
    const predecessor = normalizeBoard(candidate.payload.predecessor);
    const move = normalizeMove(candidate.payload.move);
    if (validateLastMove(problem, predecessor, move) === null) {
      return { predecessor, move, targetBoard: problem.targetBoard };
    }
  }
  return null;
}

export async function makeChessCandidate(
  problemInput: ChessAncestryProblem,
  predecessorInput: ChessBoard,
  moveInput: ChessMove,
  context = "chess-ancestry",
  cost = 1,
): Promise<TypedCandidate<ChessCandidatePayload>> {
  const candidate = makeChessCandidateSync(problemInput, predecessorInput, moveInput, context, cost);
  return makeCandidate(candidate.payload, candidate.typeName, candidate.schemaVersion, {
    problem: await stableHash(candidate.payload.problem),
    predecessor: await stableHash(candidate.payload.predecessor),
    move: await stableHash(candidate.payload.move),
  });
}

export function makeDefaultChessAncestryProblem(): ChessAncestryProblem {
  return normalizeChessProblem({
    movedPieceId: "WR",
    maxDepth: 1,
    targetBoard: {
      sideToMove: "black",
      pieces: [
        { pieceId: "WK", color: "white", role: "K", square: "a1" },
        { pieceId: "WR", color: "white", role: "R", square: "e4" },
        { pieceId: "BK", color: "black", role: "K", square: "h8" },
        { pieceId: "BR1", color: "black", role: "R", square: "e2" },
        { pieceId: "BR2", color: "black", role: "R", square: "e3" },
        { pieceId: "BR3", color: "black", role: "R", square: "b4" },
        { pieceId: "BR4", color: "black", role: "R", square: "c4" },
        { pieceId: "BR5", color: "black", role: "R", square: "d4" },
        { pieceId: "BR6", color: "black", role: "R", square: "f4" },
        { pieceId: "BR7", color: "black", role: "R", square: "g4" },
      ],
    },
  });
}

export async function enumerateChessAncestry(problemInput: ChessAncestryProblem, ledger = new Ledger()): Promise<{ state: ChessAncestryState; engine: TransactionEngine<ChessAncestryState, ChessCandidatePayload> }> {
  const problem = normalizeChessProblem(problemInput);
  const engine = new TransactionEngine(new ChessAncestryAdapter(), ledger);
  let state: ChessAncestryState = { problem, histories: [] };
  const candidates = reverseChessCandidates(problem);
  for (let idx = 0; idx < candidates.length; idx += 1) {
    const candidate = candidates[idx];
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `chess-enumerate-${idx + 1}`,
        actions: [candidate.payload.move],
        seeds: ["chess", idx + 1],
        modelVersion: "chess.enumerate.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      state = outcome.state;
    }
  }
  return { state, engine };
}

export async function runStaticChessEpisode(problemInput: ChessAncestryProblem, ledger: Ledger, episode: number): Promise<ChessAncestryEpisodeResult> {
  const problem = normalizeChessProblem(problemInput);
  const engine = new TransactionEngine(new ChessAncestryAdapter(), ledger);
  const state: ChessAncestryState = { problem, histories: [] };
  const candidates = reverseChessCandidates(problem);
  for (let idx = 0; idx < candidates.length; idx += 1) {
    const candidate = candidates[idx];
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `chess-static-${episode}-${idx + 1}`,
        actions: [candidate.payload.move],
        seeds: [episode, idx + 1],
        modelVersion: "chess.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return episodeResult(idx + 1, true, engine, state);
    }
  }
  return episodeResult(engine.hardVerifierCalls, false, engine, state);
}

export async function runRepairChessEpisode(problemInput: ChessAncestryProblem, ledger: Ledger, repairer: ChessResidualRepairer, episode: number): Promise<ChessAncestryEpisodeResult> {
  const problem = normalizeChessProblem(problemInput);
  const engine = new TransactionEngine(new ChessAncestryAdapter(), ledger);
  const state: ChessAncestryState = { problem, histories: [] };
  const targetPiece = pieceById(problem.targetBoard, problem.movedPieceId);
  if (!targetPiece) {
    throw new Error("moved piece missing");
  }
  const badPredecessor = normalizeBoard({
    pieces: problem.targetBoard.pieces.map((piece) => piece.pieceId === targetPiece.pieceId ? { ...piece, square: "e1" } : piece),
    sideToMove: targetPiece.color,
  });
  let candidate = await makeChessCandidate(problem, badPredecessor, { pieceId: targetPiece.pieceId, fromSquare: "e1", toSquare: targetPiece.square }, "chess-repair", 1);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `chess-repair-${episode}-${attempt}`,
        actions: [candidate.payload.move],
        seeds: [episode, attempt],
        modelVersion: "chess.residual_repair.v1",
      }),
      candidate,
    );
    repairer.update(outcome.receipt);
    if (outcome.committed) {
      return episodeResult(attempt + 1, true, engine, state);
    }
    const repaired = await repairer.propose(candidate, outcome.receipt.hardResult.residual);
    if (!repaired) {
      return episodeResult(attempt + 1, false, engine, state);
    }
    candidate = repaired;
  }
  return episodeResult(3, false, engine, state);
}

export async function runChessAncestryBenchmark(): Promise<ChessAncestryReport> {
  const problem = makeDefaultChessAncestryProblem();
  const enumerationLedger = new Ledger();
  const { state: enumeratedState, engine: enumerationEngine } = await enumerateChessAncestry(problem, enumerationLedger);
  const historyCount = enumeratedState.histories.length;
  const candidateSpaceSize = reverseChessCandidates(problem).length;
  const staticLedger = new Ledger();
  const repairLedger = new Ledger();
  const repairer = new ChessResidualRepairer();
  const staticResult = await runStaticChessEpisode(problem, staticLedger, 0);
  const repairResult = await runRepairChessEpisode(problem, repairLedger, repairer, 0);
  return {
    candidateSpaceSize,
    historyCount,
    ambiguityEntropy: historyCount === 0 ? 0 : Math.log2(historyCount),
    verifierCalls: enumerationEngine.hardVerifierCalls,
    forwardReplaySuccessRate: forwardReplaySuccessRate(problem, enumeratedState.histories),
    staticCallsPerSuccess: staticResult.success ? staticResult.calls : Number.POSITIVE_INFINITY,
    repairCallsPerSuccess: repairResult.success ? repairResult.calls : Number.POSITIVE_INFINITY,
    repairGain: staticResult.calls / repairResult.calls,
    ledgerAudit: await enumerationEngine.ledger.audit() && await staticLedger.audit() && await repairLedger.audit(),
    replayRollbackRate: [staticResult, repairResult].filter((row) => row.replayRollbackOk).length / 2,
    invalidCommitCount: invalidCommits([enumerationLedger, staticLedger, repairLedger]),
    learnedResidualKinds: Object.fromEntries(repairer.rejectedResiduals),
  };
}

function makeChessCandidateSync(
  problemInput: ChessAncestryProblem,
  predecessorInput: ChessBoard,
  moveInput: ChessMove,
  context: string,
  cost: number,
): TypedCandidate<ChessCandidatePayload> {
  const problem = normalizeChessProblem(problemInput);
  const predecessor = normalizeBoard(predecessorInput);
  const move = normalizeMove(moveInput);
  return makeCandidate(
    { context, problem, predecessor, move, cost },
    "chess.rook_king_last_move",
    "chess.rook_king_last_move.v1",
    {},
  );
}

function reverseFromSquares(piece: ChessPiece): string[] {
  const [px, py] = coord(piece.square);
  if (piece.role === "K") {
    const out: string[] = [];
    for (const dx of [-1, 0, 1]) {
      for (const dy of [-1, 0, 1]) {
        if (dx === 0 && dy === 0) continue;
        const x = px + dx;
        const y = py + dy;
        if (x >= 0 && x < 8 && y >= 0 && y < 8) out.push(square(x, y));
      }
    }
    return out.sort(compareSquares);
  }
  if (piece.role === "R") {
    const out: string[] = [];
    for (let y = 0; y < 8; y += 1) {
      if (y !== py) out.push(square(px, y));
    }
    for (let x = 0; x < 8; x += 1) {
      if (x !== px) out.push(square(x, py));
    }
    return out.sort(compareSquares);
  }
  return [];
}

async function episodeResult(
  calls: number,
  success: boolean,
  engine: TransactionEngine<ChessAncestryState, ChessCandidatePayload>,
  seedState: ChessAncestryState,
): Promise<ChessAncestryEpisodeResult> {
  const auditOk = await engine.ledger.audit();
  let replayRollbackOk = false;
  if (auditOk) {
    try {
      await engine.replayAudit(seedState);
      replayRollbackOk = chessStatesEqual(await engine.rollbackAudit(seedState), seedState);
    } catch (_error) {
      replayRollbackOk = false;
    }
  }
  return { calls, success, auditOk, replayRollbackOk };
}

function forwardReplaySuccessRate(problemInput: ChessAncestryProblem, histories: ChessMove[]): number {
  const problem = normalizeChessProblem(problemInput);
  if (histories.length === 0) return 0;
  const legal = new Map(reverseChessCandidates(problem).map((candidate) => [moveKey(candidate.payload.move), candidate.payload.predecessor]));
  let ok = 0;
  for (const move of histories) {
    const predecessor = legal.get(moveKey(move));
    if (predecessor && boardsEqual(applyChessMove(predecessor, move), problem.targetBoard)) ok += 1;
  }
  return ok / histories.length;
}

function appendHistory(histories: ChessMove[], move: ChessMove): ChessMove[] {
  return histories.some((row) => moveKey(row) === moveKey(move)) ? histories : [...histories, move];
}

function normalizeColor(value: unknown): ChessColor {
  if (value !== "white" && value !== "black") {
    throw new RangeError("unsupported chess color");
  }
  return value;
}

function normalizeRole(value: unknown): ChessRole {
  if (value !== "K" && value !== "R") {
    throw new RangeError("this G1 canary supports only kings and rooks");
  }
  return value;
}

function compareSquares(a: string, b: string): number {
  const [ax, ay] = coord(a);
  const [bx, by] = coord(b);
  return ax - bx || ay - by;
}

function moveKey(moveInput: ChessMove): string {
  const move = normalizeMove(moveInput);
  return `${move.pieceId}:${move.fromSquare}:${move.toSquare}`;
}

function boardsEqual(a: ChessBoard, b: ChessBoard): boolean {
  return JSON.stringify(normalizeBoard(a)) === JSON.stringify(normalizeBoard(b));
}

function chessProblemsEqual(a: ChessAncestryProblem, b: ChessAncestryProblem): boolean {
  return JSON.stringify(normalizeChessProblem(a)) === JSON.stringify(normalizeChessProblem(b));
}

function chessStatesEqual(a: ChessAncestryState, b: ChessAncestryState): boolean {
  return JSON.stringify(normalizeChessState(a)) === JSON.stringify(normalizeChessState(b));
}

function isChessResidual(value: unknown): value is ChessResidual {
  if (!value || typeof value !== "object") return false;
  const residual = value as Partial<ChessResidual>;
  return residual.kind === "schema_error"
    || residual.kind === "illegal_predecessor"
    || residual.kind === "illegal_move"
    || residual.kind === "king_left_in_check"
    || residual.kind === "forward_replay_mismatch";
}

function invalidCommits(ledgers: Ledger[]): number {
  return ledgers.reduce((sum, ledger) =>
    sum + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  0);
}
