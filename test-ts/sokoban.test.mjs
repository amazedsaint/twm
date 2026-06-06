import assert from "node:assert/strict";
import test from "node:test";

import {
  SokobanReverseAdapter,
  makeSokobanCandidate,
  parseSokoban,
  renderSokoban,
  replaySokobanPushes,
  searchSokobanPredecessor,
} from "../dist/index.js";

const solvedLevel = [
  "#######",
  "#  @* #",
  "#     #",
  "#######",
];

test("Sokoban parser renders and forward replay verifies push certificate", async () => {
  const { layout, state: solved } = parseSokoban(solvedLevel);
  const predecessor = { boxes: [[1, 3]], player: [1, 2] };
  const pushes = [{ box: [1, 3], direction: "R" }];

  assert.deepEqual(renderSokoban(layout, solved), solvedLevel);
  assert.deepEqual(replaySokobanPushes(layout, predecessor, pushes), solved);
});

test("Sokoban reverse search commits audited predecessor", async () => {
  const { layout, state: solved } = parseSokoban(solvedLevel);
  const report = await searchSokobanPredecessor(layout, solved, 1, 8);

  assert.equal(report.solved, true);
  assert.deepEqual(report.predecessor, { boxes: [[1, 3]], player: [1, 2] });
  assert.deepEqual(report.pushes, [{ box: [1, 3], direction: "R" }]);
  assert.equal(report.verifierCalls, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.ok(report.verifierCallReduction > 1);
});

test("Sokoban hard verifier rejects bad push certificate", async () => {
  const { layout, state: solved } = parseSokoban(solvedLevel);
  const predecessor = { boxes: [[1, 3]], player: [1, 2] };
  const candidate = await makeSokobanCandidate(layout, solved, predecessor, [{ box: [1, 3], direction: "L" }], 1);

  const result = new SokobanReverseAdapter().verify(candidate);
  assert.equal(result.result, "reject");
});
