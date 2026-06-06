import {
  type HardVerifierResult,
  type Receipt,
  type ReplayRollbackAdapter,
  type ProposalTrace,
  type TypedCandidate,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { stableHash } from "./canonical.js";
import { AdditiveCoupling } from "./reversible.js";

export type Board = number[][];

export interface LifeState {
  target: Board;
}

export interface LifeCandidatePayload {
  target: Board;
  predecessor: Board;
  cost: number;
}

export function normalizeBoard(board: Board): Board {
  if (board.length === 0) {
    return [];
  }
  const width = board[0].length;
  return board.map((row) => {
    if (row.length !== width) {
      throw new RangeError("board rows must have equal width");
    }
    return row.map((cell) => cell ? 1 : 0);
  });
}

export function lifeStep(boardInput: Board): Board {
  const board = normalizeBoard(boardInput);
  const height = board.length;
  const width = height === 0 ? 0 : board[0].length;
  const next: Board = [];
  for (let row = 0; row < height; row += 1) {
    const out: number[] = [];
    for (let col = 0; col < width; col += 1) {
      let neighbors = 0;
      for (let dr = -1; dr <= 1; dr += 1) {
        for (let dc = -1; dc <= 1; dc += 1) {
          if (dr === 0 && dc === 0) {
            continue;
          }
          const rr = row + dr;
          const cc = col + dc;
          if (rr >= 0 && rr < height && cc >= 0 && cc < width) {
            neighbors += board[rr][cc];
          }
        }
      }
      const live = board[row][col] === 1;
      out.push(neighbors === 3 || (live && neighbors === 2) ? 1 : 0);
    }
    next.push(out);
  }
  return next;
}

export function* enumerateBoards(height: number, width: number): Generator<Board> {
  const cells = height * width;
  const total = 2 ** cells;
  for (let mask = 0; mask < total; mask += 1) {
    const board: Board = [];
    for (let row = 0; row < height; row += 1) {
      const out: number[] = [];
      for (let col = 0; col < width; col += 1) {
        const bit = row * width + col;
        out.push((mask >> bit) & 1);
      }
      board.push(out);
    }
    yield board;
  }
}

export async function makeLifeCandidate(target: Board, predecessor: Board, cost: number): Promise<TypedCandidate<LifeCandidatePayload>> {
  return makeCandidate(
    { target: normalizeBoard(target), predecessor: normalizeBoard(predecessor), cost },
    "game_of_life.predecessor",
    "game_of_life.predecessor.v1",
    {
      target: await stableHash(normalizeBoard(target)),
      predecessor: await stableHash(normalizeBoard(predecessor)),
    },
  );
}

export async function guidedLifeTraces(targetInput: Board, maxCandidates?: number): Promise<ProposalTrace[]> {
  const target = normalizeBoard(targetInput);
  const traces: ProposalTrace[] = [];
  const seen = new Set<string>();
  const macros = blinkerMacroPredecessors(target);
  for (let idx = 0; idx < macros.length; idx += 1) {
    const predecessor = macros[idx];
    seen.add(JSON.stringify(predecessor));
    traces.push(await reversibleBlinkerTrace(target, predecessor, `life-reversible-${idx}`, idx + 1));
  }
  const height = target.length;
  const width = height === 0 ? 0 : target[0].length;
  let idx = 0;
  for (const predecessor of enumerateBoards(height, width)) {
    if (maxCandidates !== undefined && traces.length >= maxCandidates) {
      break;
    }
    const key = JSON.stringify(predecessor);
    if (seen.has(key)) {
      idx += 1;
      continue;
    }
    traces.push(makeTrace({
      branchId: `life-exhaustive-${idx}`,
      actions: [{ predecessor, cost: traces.length + 1 }],
      seeds: [idx],
      modelVersion: "exhaustive.life.v1",
    }));
    idx += 1;
  }
  return traces;
}

export function lifeBaselineVerifierCalls(target: Board): number {
  const board = normalizeBoard(target);
  const height = board.length;
  const width = height === 0 ? 0 : board[0].length;
  return 2 ** (height * width);
}

export class LifePredecessorAdapter implements ReplayRollbackAdapter<LifeState, LifeCandidatePayload> {
  verifierId = "life_forward_verifier";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<LifeCandidatePayload>): HardVerifierResult {
    const predicted = lifeStep(candidate.payload.predecessor);
    const target = normalizeBoard(candidate.payload.target);
    if (boardsEqual(predicted, target)) {
      return hardAccept(this.verifierId, this.verifierVersion, { cost: candidate.payload.cost });
    }
    return hardReject(this.verifierId, this.verifierVersion, { predicted, target }, { cost: candidate.payload.cost });
  }

  applyCommit(_state: LifeState, candidate: TypedCandidate<LifeCandidatePayload>): LifeState {
    return { target: normalizeBoard(candidate.payload.predecessor) };
  }

  replay(_state: LifeState, receipt: Receipt): LifeState {
    const payload = (receipt.replayBundle as { candidatePayload: LifeCandidatePayload }).candidatePayload;
    return { target: normalizeBoard(payload.predecessor) };
  }

  rollback(_state: LifeState, receipt: Receipt): LifeState {
    return (receipt.rollbackBundle as { preState: LifeState }).preState;
  }
}

export function boardsEqual(a: Board, b: Board): boolean {
  return a.length === b.length && a.every((row, rowIdx) =>
    row.length === b[rowIdx].length && row.every((cell, colIdx) => cell === b[rowIdx][colIdx]),
  );
}

function blinkerMacroPredecessors(target: Board): Board[] {
  const board = normalizeBoard(target);
  const height = board.length;
  const width = height === 0 ? 0 : board[0].length;
  const live: Array<[number, number]> = [];
  for (let row = 0; row < height; row += 1) {
    for (let col = 0; col < width; col += 1) {
      if (board[row][col] === 1) {
        live.push([row, col]);
      }
    }
  }
  if (live.length !== 3) {
    return [];
  }
  const rows = new Set(live.map(([row]) => row));
  const cols = new Set(live.map(([, col]) => col));
  const proposals: Board[] = [];
  if (cols.size === 1 && rows.size === 3) {
    const centerRow = Math.floor(Array.from(rows).reduce((a, b) => a + b, 0) / 3);
    const centerCol = Array.from(cols)[0];
    if (centerCol > 0 && centerCol < width - 1) {
      proposals.push(Array.from({ length: height }, (_unused, row) =>
        Array.from({ length: width }, (_unusedCol, col) => row === centerRow && Math.abs(col - centerCol) <= 1 ? 1 : 0),
      ));
    }
  }
  if (rows.size === 1 && cols.size === 3) {
    const centerRow = Array.from(rows)[0];
    const centerCol = Math.floor(Array.from(cols).reduce((a, b) => a + b, 0) / 3);
    if (centerRow > 0 && centerRow < height - 1) {
      proposals.push(Array.from({ length: height }, (_unused, row) =>
        Array.from({ length: width }, (_unusedCol, col) => col === centerCol && Math.abs(row - centerRow) <= 1 ? 1 : 0),
      ));
    }
  }
  return proposals;
}

async function reversibleBlinkerTrace(target: Board, predecessor: Board, branchId: string, cost: number): Promise<ProposalTrace> {
  const liveCount = target.flat().reduce((sum, cell) => sum + cell, 0);
  const firstLive = target.flatMap((row, rowIdx) => row.map((cell, colIdx) => ({ cell, rowIdx, colIdx }))).find((item) => item.cell === 1);
  const z = [BigInt(liveCount), BigInt(firstLive?.rowIdx ?? 0), BigInt(firstLive?.colIdx ?? 0), BigInt(cost)];
  const coupling = new AdditiveCoupling(
    (v, context) => [v[0] + BigInt(context.bias), v[1]],
    (uNext, context) => [uNext[0] - BigInt(context.bias), -uNext[1]],
    2,
  );
  const zNext = coupling.forward(z, { bias: 1 });
  if (!coupling.cycleOk(z, { bias: 1 })) {
    throw new Error("reversible macro proposal failed exact cycle check");
  }
  return makeTrace({
    branchId,
    actions: [{ predecessor, cost, proposal: "reversible_blinker_macro" }],
    latentStates: [z.map(String), zNext.map(String)],
    seeds: [await stableHash(target), cost],
    modelVersion: "reversible.blinker_macro.v1",
  });
}
