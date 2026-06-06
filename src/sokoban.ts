import {
  type HardVerifierResult,
  type ProposalTrace,
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

export type SokobanPosition = [number, number];
export type SokobanDirection = "U" | "D" | "L" | "R";

export interface SokobanLayout {
  height: number;
  width: number;
  walls: SokobanPosition[];
  goals: SokobanPosition[];
}

export interface SokobanState {
  boxes: SokobanPosition[];
  player: SokobanPosition;
}

export interface SokobanPush {
  box: SokobanPosition;
  direction: SokobanDirection;
}

export interface SokobanCandidatePayload {
  layout: SokobanLayout;
  solvedState: SokobanState;
  predecessor: SokobanState;
  pushes: SokobanPush[];
  cost: number;
}

export interface SokobanReverseReport {
  solved: boolean;
  predecessor: SokobanState | null;
  solvedState: SokobanState;
  pushes: SokobanPush[];
  verifierCalls: number;
  reverseExpansions: number;
  maxDepth: number;
  baselineStateCount: number;
  verifierCallReduction: number;
  invalidCommitCount: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
}

const DIRECTIONS: Array<[SokobanDirection, SokobanPosition]> = [
  ["U", [-1, 0]],
  ["D", [1, 0]],
  ["L", [0, -1]],
  ["R", [0, 1]],
];

interface SearchNode {
  state: SokobanState;
  pushes: SokobanPush[];
  depth: number;
}

export function parseSokoban(rows: string[]): { layout: SokobanLayout; state: SokobanState } {
  if (rows.length === 0) {
    throw new RangeError("sokoban level must not be empty");
  }
  const width = rows[0].length;
  if (width === 0 || rows.some((row) => row.length !== width)) {
    throw new RangeError("sokoban rows must be non-empty and equal width");
  }
  const walls: SokobanPosition[] = [];
  const goals: SokobanPosition[] = [];
  const boxes: SokobanPosition[] = [];
  const players: SokobanPosition[] = [];
  const valid = new Set(["#", " ", ".", "$", "*", "@", "+"]);
  for (let row = 0; row < rows.length; row += 1) {
    for (let col = 0; col < width; col += 1) {
      const cell = rows[row][col];
      if (!valid.has(cell)) {
        throw new RangeError(`unsupported sokoban tile: ${cell}`);
      }
      const pos: SokobanPosition = [row, col];
      if (cell === "#") walls.push(pos);
      if (cell === "." || cell === "*" || cell === "+") goals.push(pos);
      if (cell === "$" || cell === "*") boxes.push(pos);
      if (cell === "@" || cell === "+") players.push(pos);
    }
  }
  if (players.length !== 1) {
    throw new RangeError("sokoban level must contain exactly one player");
  }
  if (goals.length === 0) {
    throw new RangeError("sokoban level must contain at least one goal");
  }
  if (boxes.length !== goals.length) {
    throw new RangeError("sokoban level must contain the same number of boxes and goals");
  }
  return {
    layout: normalizeLayout({ height: rows.length, width, walls, goals }),
    state: normalizeState({ boxes, player: players[0] }),
  };
}

export function renderSokoban(layoutInput: SokobanLayout, stateInput: SokobanState): string[] {
  const layout = normalizeLayout(layoutInput);
  const state = normalizeState(stateInput);
  const walls = positionSet(layout.walls);
  const goals = positionSet(layout.goals);
  const boxes = positionSet(state.boxes);
  const rows: string[] = [];
  for (let row = 0; row < layout.height; row += 1) {
    let out = "";
    for (let col = 0; col < layout.width; col += 1) {
      const key = positionKey([row, col]);
      if (walls.has(key)) out += "#";
      else if (samePosition(state.player, [row, col]) && goals.has(key)) out += "+";
      else if (samePosition(state.player, [row, col])) out += "@";
      else if (boxes.has(key) && goals.has(key)) out += "*";
      else if (boxes.has(key)) out += "$";
      else if (goals.has(key)) out += ".";
      else out += " ";
    }
    rows.push(out);
  }
  return rows;
}

export function sokobanSolved(layout: SokobanLayout, state: SokobanState): boolean {
  const goals = positionSet(normalizeLayout(layout).goals);
  const boxes = positionSet(normalizeState(state).boxes);
  return boxes.size === goals.size && Array.from(boxes).every((box) => goals.has(box));
}

export async function makeSokobanCandidate(
  layoutInput: SokobanLayout,
  solvedStateInput: SokobanState,
  predecessorInput: SokobanState,
  pushesInput: SokobanPush[],
  cost: number,
): Promise<TypedCandidate<SokobanCandidatePayload>> {
  const layout = normalizeLayout(layoutInput);
  const solvedState = normalizeState(solvedStateInput);
  const predecessor = normalizeState(predecessorInput);
  const pushes = pushesInput.map(normalizePush);
  return makeCandidate(
    { layout, solvedState, predecessor, pushes, cost },
    "sokoban.reverse_certificate",
    "sokoban.reverse_certificate.v1",
    {
      layout: await stableHash(layout),
      solvedState: await stableHash(solvedState),
      predecessor: await stableHash(predecessor),
      pushes: await stableHash(pushes),
    },
  );
}

export class SokobanReverseAdapter implements ReplayRollbackAdapter<SokobanState, SokobanCandidatePayload> {
  verifierId = "sokoban_forward_replay_verifier";
  verifierVersion = "1.0";

  verify(candidate: TypedCandidate<SokobanCandidatePayload>): HardVerifierResult {
    const payload = candidate.payload;
    const layout = normalizeLayout(payload.layout);
    const solvedState = normalizeState(payload.solvedState);
    const predecessor = normalizeState(payload.predecessor);
    const pushes = payload.pushes.map(normalizePush);
    const metadata = { cost: payload.cost, pushCount: pushes.length };
    try {
      const replayed = replaySokobanPushes(layout, predecessor, pushes);
      if (statesEqual(replayed, solvedState) && sokobanSolved(layout, replayed)) {
        return hardAccept(this.verifierId, this.verifierVersion, metadata);
      }
      return hardReject(
        this.verifierId,
        this.verifierVersion,
        { replayed, solvedState, replayedSolved: sokobanSolved(layout, replayed) },
        metadata,
      );
    } catch (error) {
      return hardReject(
        this.verifierId,
        this.verifierVersion,
        { reason: error instanceof Error ? error.message : "unknown", predecessor },
        metadata,
      );
    }
  }

  applyCommit(_state: SokobanState, candidate: TypedCandidate<SokobanCandidatePayload>): SokobanState {
    return normalizeState(candidate.payload.predecessor);
  }

  replay(_state: SokobanState, receipt: Receipt): SokobanState {
    const payload = (receipt.replayBundle as { candidatePayload: SokobanCandidatePayload }).candidatePayload;
    return normalizeState(payload.predecessor);
  }

  rollback(_state: SokobanState, receipt: Receipt): SokobanState {
    return normalizeState((receipt.rollbackBundle as { preState: SokobanState }).preState);
  }
}

export function replaySokobanPushes(layout: SokobanLayout, state: SokobanState, pushes: SokobanPush[]): SokobanState {
  return pushes.reduce((current, push) => applySokobanPush(layout, current, push), normalizeState(state));
}

export function applySokobanPush(layoutInput: SokobanLayout, stateInput: SokobanState, pushInput: SokobanPush): SokobanState {
  const layout = normalizeLayout(layoutInput);
  const state = normalizeState(stateInput);
  const push = normalizePush(pushInput);
  const boxes = new Map(state.boxes.map((box) => [positionKey(box), box]));
  const boxKey = positionKey(push.box);
  if (!boxes.has(boxKey)) {
    throw new Error(`no box at push origin: ${boxKey}`);
  }
  const delta = directionDelta(push.direction);
  const stand = subPosition(push.box, delta);
  const destination = addPosition(push.box, delta);
  if (!isOpen(layout, state.boxes, stand)) {
    throw new Error(`push stand cell is blocked: ${positionKey(stand)}`);
  }
  if (!reachable(layout, state.boxes, state.player, stand)) {
    throw new Error(`player cannot reach push stand cell: ${positionKey(stand)}`);
  }
  boxes.delete(boxKey);
  const remaining = Array.from(boxes.values());
  if (!isOpen(layout, remaining, destination)) {
    throw new Error(`push destination is blocked: ${positionKey(destination)}`);
  }
  remaining.push(destination);
  return normalizeState({ boxes: remaining, player: push.box });
}

export function reachable(layoutInput: SokobanLayout, boxesInput: SokobanPosition[], start: SokobanPosition, target: SokobanPosition): boolean {
  const layout = normalizeLayout(layoutInput);
  const boxes = positionSet(boxesInput);
  const startKey = positionKey(start);
  const targetKey = positionKey(target);
  if (boxes.has(startKey) || boxes.has(targetKey) || !inBounds(layout, start) || !inBounds(layout, target)) {
    return false;
  }
  const walls = positionSet(layout.walls);
  if (walls.has(startKey) || walls.has(targetKey)) {
    return false;
  }
  const queue: SokobanPosition[] = [start];
  const seen = new Set([startKey]);
  for (let idx = 0; idx < queue.length; idx += 1) {
    const current = queue[idx];
    if (samePosition(current, target)) {
      return true;
    }
    for (const [, delta] of DIRECTIONS) {
      const next = addPosition(current, delta);
      const key = positionKey(next);
      if (seen.has(key) || boxes.has(key) || walls.has(key) || !inBounds(layout, next)) {
        continue;
      }
      seen.add(key);
      queue.push(next);
    }
  }
  return false;
}

export async function reversePullTraces(
  layoutInput: SokobanLayout,
  solvedStateInput: SokobanState,
  maxDepth = 3,
  maxCandidates = 64,
): Promise<Array<{ trace: ProposalTrace; candidate: TypedCandidate<SokobanCandidatePayload> }>> {
  return (await collectReversePullTraces(layoutInput, solvedStateInput, maxDepth, maxCandidates)).items;
}

async function collectReversePullTraces(
  layoutInput: SokobanLayout,
  solvedStateInput: SokobanState,
  maxDepth = 3,
  maxCandidates = 64,
): Promise<{ items: Array<{ trace: ProposalTrace; candidate: TypedCandidate<SokobanCandidatePayload> }>; expansions: number }> {
  if (!Number.isInteger(maxDepth) || maxDepth <= 0) {
    throw new RangeError("maxDepth must be positive");
  }
  if (!Number.isInteger(maxCandidates) || maxCandidates <= 0) {
    throw new RangeError("maxCandidates must be positive");
  }
  const layout = normalizeLayout(layoutInput);
  const solvedState = normalizeState(solvedStateInput);
  const queue: SearchNode[] = [{ state: solvedState, pushes: [], depth: 0 }];
  const seen = new Set([stateKey(solvedState)]);
  const candidates: Array<{ trace: ProposalTrace; candidate: TypedCandidate<SokobanCandidatePayload> }> = [];
  let expansions = 0;
  for (let queueIdx = 0; queueIdx < queue.length && candidates.length < maxCandidates; queueIdx += 1) {
    const node = queue[queueIdx];
    if (node.depth >= maxDepth) {
      continue;
    }
    expansions += 1;
    for (const box of node.state.boxes) {
      for (const [direction, delta] of DIRECTIONS) {
        const previousBox = subPosition(box, delta);
        const previousPlayer = subPosition(previousBox, delta);
        if (!reachable(layout, node.state.boxes, node.state.player, previousBox)) {
          continue;
        }
        const boxes = node.state.boxes.filter((candidateBox) => !samePosition(candidateBox, box));
        if (!isOpen(layout, boxes, previousBox)) {
          continue;
        }
        boxes.push(previousBox);
        const predecessor = normalizeState({ boxes, player: previousPlayer });
        if (!isOpen(layout, predecessor.boxes, previousPlayer)) {
          continue;
        }
        const key = stateKey(predecessor);
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);
        const push: SokobanPush = { box: previousBox, direction };
        const pushes = [push, ...node.pushes];
        const depth = node.depth + 1;
        const trace = makeTrace({
          branchId: `sokoban-reverse-${candidates.length}`,
          actions: pushes,
          seeds: [await stableHash(solvedState), depth, candidates.length],
          modelVersion: "reverse_pull.sokoban.v1",
        });
        const candidate = await makeSokobanCandidate(layout, solvedState, predecessor, pushes, depth);
        candidates.push({ trace, candidate });
        queue.push({ state: predecessor, pushes, depth });
        if (candidates.length >= maxCandidates) {
          break;
        }
      }
      if (candidates.length >= maxCandidates) {
        break;
      }
    }
  }
  return { items: candidates, expansions };
}

export async function searchSokobanPredecessor(
  layoutInput: SokobanLayout,
  solvedStateInput: SokobanState,
  maxDepth = 3,
  maxCandidates = 64,
): Promise<SokobanReverseReport> {
  const layout = normalizeLayout(layoutInput);
  const solvedState = normalizeState(solvedStateInput);
  if (!sokobanSolved(layout, solvedState)) {
    throw new RangeError("solvedState must have every box on a goal");
  }
  const { items: traces, expansions } = await collectReversePullTraces(layout, solvedState, maxDepth, maxCandidates);
  const adapter = new SokobanReverseAdapter();
  const ledger = new Ledger();
  const engine = new TransactionEngine(adapter, ledger);
  let predecessor: SokobanState | null = null;
  let pushes: SokobanPush[] = [];
  for (const { trace, candidate } of traces) {
    const outcome = await engine.transact(solvedState, trace, candidate);
    if (outcome.committed) {
      predecessor = outcome.state;
      pushes = candidate.payload.pushes;
      break;
    }
  }
  const ledgerAudit = await ledger.audit();
  let replayRollbackRate = 0;
  if (ledgerAudit) {
    try {
      await engine.replayAudit(solvedState);
      const rollback = await engine.rollbackAudit(solvedState);
      replayRollbackRate = statesEqual(rollback, solvedState) ? 1 : 0;
    } catch (_error) {
      replayRollbackRate = 0;
    }
  }
  const baselineStateCount = baselineStateCountFor(layout);
  return {
    solved: predecessor !== null,
    predecessor,
    solvedState,
    pushes,
    verifierCalls: engine.hardVerifierCalls,
    reverseExpansions: expansions,
    maxDepth,
    baselineStateCount,
    verifierCallReduction: engine.hardVerifierCalls > 0 ? baselineStateCount / engine.hardVerifierCalls : 0,
    invalidCommitCount: engine.invalidCommitCount,
    ledgerAudit,
    replayRollbackRate,
  };
}

export function normalizeLayout(layout: SokobanLayout): SokobanLayout {
  if (!Number.isInteger(layout.height) || !Number.isInteger(layout.width) || layout.height <= 0 || layout.width <= 0) {
    throw new RangeError("sokoban layout dimensions must be positive integers");
  }
  return {
    height: layout.height,
    width: layout.width,
    walls: normalizePositions(layout.walls),
    goals: normalizePositions(layout.goals),
  };
}

export function normalizeState(state: SokobanState): SokobanState {
  return {
    boxes: normalizePositions(state.boxes),
    player: normalizePosition(state.player),
  };
}

function normalizePush(push: SokobanPush): SokobanPush {
  return {
    box: normalizePosition(push.box),
    direction: normalizeDirection(push.direction),
  };
}

function normalizePositions(positions: SokobanPosition[]): SokobanPosition[] {
  const normalized = positions.map(normalizePosition).sort(comparePositions);
  const unique = new Set(normalized.map(positionKey));
  if (unique.size !== normalized.length) {
    throw new RangeError("duplicate sokoban positions are not allowed");
  }
  return normalized;
}

function normalizePosition(position: SokobanPosition): SokobanPosition {
  if (!Array.isArray(position) || position.length !== 2 || !Number.isInteger(position[0]) || !Number.isInteger(position[1])) {
    throw new RangeError("sokoban positions must be integer pairs");
  }
  return [position[0], position[1]];
}

function normalizeDirection(direction: string): SokobanDirection {
  if (direction === "U" || direction === "D" || direction === "L" || direction === "R") {
    return direction;
  }
  throw new RangeError(`unknown sokoban direction: ${direction}`);
}

function directionDelta(direction: SokobanDirection): SokobanPosition {
  const found = DIRECTIONS.find(([name]) => name === direction);
  if (!found) {
    throw new RangeError(`unknown sokoban direction: ${direction}`);
  }
  return found[1];
}

function baselineStateCountFor(layout: SokobanLayout): number {
  const floor = layout.height * layout.width - layout.walls.length;
  return Math.max(0, floor * Math.max(0, floor - 1));
}

function isOpen(layout: SokobanLayout, boxes: SokobanPosition[], pos: SokobanPosition): boolean {
  return inBounds(layout, pos) && !positionSet(layout.walls).has(positionKey(pos)) && !positionSet(boxes).has(positionKey(pos));
}

function inBounds(layout: SokobanLayout, pos: SokobanPosition): boolean {
  return pos[0] >= 0 && pos[0] < layout.height && pos[1] >= 0 && pos[1] < layout.width;
}

function positionSet(positions: SokobanPosition[]): Set<string> {
  return new Set(positions.map(positionKey));
}

function positionKey(pos: SokobanPosition): string {
  return `${pos[0]},${pos[1]}`;
}

function stateKey(state: SokobanState): string {
  const normalized = normalizeState(state);
  return `${normalized.boxes.map(positionKey).join(";")}|${positionKey(normalized.player)}`;
}

function samePosition(a: SokobanPosition, b: SokobanPosition): boolean {
  return a[0] === b[0] && a[1] === b[1];
}

function statesEqual(a: SokobanState, b: SokobanState): boolean {
  return stateKey(a) === stateKey(b);
}

function addPosition(a: SokobanPosition, b: SokobanPosition): SokobanPosition {
  return [a[0] + b[0], a[1] + b[1]];
}

function subPosition(a: SokobanPosition, b: SokobanPosition): SokobanPosition {
  return [a[0] - b[0], a[1] - b[1]];
}

function comparePositions(a: SokobanPosition, b: SokobanPosition): number {
  if (a[0] !== b[0]) return a[0] - b[0];
  return a[1] - b[1];
}
