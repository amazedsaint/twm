import assert from "node:assert/strict";
import test from "node:test";

import {
  LifePredecessorAdapter,
  TransactionEngine,
  boardsEqual,
  enumerateBoards,
  guidedLifeTraces,
  lifeBaselineVerifierCalls,
  lifeStep,
  makeLifeCandidate,
  makeTrace,
} from "../dist/index.js";

test("Game of Life predecessor is a typed hard-checker transaction", async () => {
  const predecessor = [
    [0, 0, 0],
    [1, 1, 1],
    [0, 0, 0],
  ];
  const target = lifeStep(predecessor);
  const adapter = new LifePredecessorAdapter();
  const engine = new TransactionEngine(adapter);
  let committed = false;
  let state = { target };
  let calls = 0;
  for (const board of enumerateBoards(3, 3)) {
    calls += 1;
    const candidate = await makeLifeCandidate(target, board, calls);
    const outcome = await engine.transact(state, makeTrace({ branchId: `life-${calls}`, actions: [board] }), candidate);
    if (outcome.committed) {
      committed = true;
      state = outcome.state;
      break;
    }
  }

  assert.equal(committed, true);
  assert.equal(boardsEqual(lifeStep(state.target), target), true);
  assert.equal(await engine.ledger.audit(), true);
  assert.deepEqual(await engine.rollbackAudit({ target }), { target });
});

test("guided Life traces use reversible macro proposal before exhaustive fallback", async () => {
  const predecessor = [
    [0, 0, 0],
    [1, 1, 1],
    [0, 0, 0],
  ];
  const target = lifeStep(predecessor);
  const traces = await guidedLifeTraces(target);

  assert.equal(traces[0].modelVersion, "reversible.blinker_macro.v1");
  assert.equal(traces[0].latentStates.length, 2);
  assert.equal(lifeBaselineVerifierCalls(target), 512);
});
