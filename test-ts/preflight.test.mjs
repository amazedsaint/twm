import assert from "node:assert/strict";
import test from "node:test";

import { oneHotUpdates, shapeRankPreflight } from "../dist/index.js";

test("shape-rank preflight accepts low-rank updates within budget", () => {
  const updates = oneHotUpdates(Array.from({ length: 8 }).flatMap(() => [1, 1, 1, 3, 3, 7]), 24);
  const report = shapeRankPreflight(updates, undefined, 4);

  assert.ok(report.r90 <= 3);
  assert.equal(report.fitsBudget, true);
  assert.equal(report.energyAtBudget, 1);
});

test("shape-rank preflight refuses high-rank updates for compact budget", () => {
  const updates = oneHotUpdates(Array.from({ length: 4 }).flatMap(() => Array.from({ length: 24 }, (_unused, idx) => idx)), 24);
  const report = shapeRankPreflight(updates, undefined, 4);

  assert.ok(report.r90 > 4);
  assert.equal(report.fitsBudget, false);
  assert.ok(report.energyAtBudget < 0.5);
});

test("shape-rank preflight respects output-map energy weights", () => {
  const report = shapeRankPreflight([[1, 0], [0, 1]], [[2, 0], [0, 1]], 1);

  assert.equal(report.r90, 2);
  assert.equal(Math.round(report.energyAtBudget * 100) / 100, 0.8);
});

test("shape-rank preflight rejects non-finite values", () => {
  assert.throws(() => shapeRankPreflight([[1, Number.NaN]], undefined, 1), /finite/);
  assert.throws(() => shapeRankPreflight([[1, 0]], [[1, Number.POSITIVE_INFINITY]], 1), /finite/);
  assert.throws(() => shapeRankPreflight([[1, 0]], undefined, 1.5), /non-negative integer/);
});
