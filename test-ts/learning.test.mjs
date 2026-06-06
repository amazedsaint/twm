import assert from "node:assert/strict";
import test from "node:test";

import {
  HyperdimensionalMemory,
  CounterfactualRollbackRanker,
  ReceiptRanker,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "../dist/index.js";

class GuessAdapter {
  verifierId = "guess_oracle";
  verifierVersion = "1.0";

  verify(candidate) {
    return candidate.payload.guess === candidate.payload.defect
      ? hardAccept(this.verifierId, this.verifierVersion)
      : hardReject(this.verifierId, this.verifierVersion, { miss: true });
  }

  applyCommit(state, candidate) {
    return { ...state, solved: true, guess: candidate.payload.guess };
  }

  replay(state, receipt) {
    return { ...state, solved: true, guess: receipt.replayBundle.candidatePayload.guess };
  }

  rollback(_state, receipt) {
    return receipt.rollbackBundle.preState;
  }
}

test("receipt ranker learns from hard verifier outcomes", async () => {
  const engine = new TransactionEngine(new GuessAdapter());
  const ranker = new ReceiptRanker();
  const state = { context: "low", solved: false };
  for (const guess of [2, 2, 1, 1, 3]) {
    const outcome = await engine.transact(
      state,
      makeTrace({ branchId: `g-${guess}`, actions: [guess] }),
      makeCandidate({ context: "low", action: guess, guess, defect: 1 }, "guess", "guess.v1"),
    );
    ranker.update(outcome.receipt);
  }

  assert.deepEqual(ranker.rank("low", [3, 2, 1]), [1, 3, 2]);
  assert.equal(await engine.ledger.audit(), true);
});

test("receipt ranker uses canonical tokens for structured actions", async () => {
  const engine = new TransactionEngine(new GuessAdapter());
  const ranker = new ReceiptRanker();
  const action = { b: 2, a: 1 };
  const outcome = await engine.transact(
    { context: "objects", solved: false },
    makeTrace({ branchId: "object-action", actions: [action] }),
    makeCandidate({ context: "objects", action, guess: 1, defect: 1 }, "guess", "guess.v1"),
  );
  ranker.update(outcome.receipt);

  const ranked = ranker.rank("objects", [{ a: 0 }, { a: 1, b: 2 }]);

  assert.deepEqual(ranked[0], { a: 1, b: 2 });
});

test("hyperdimensional memory retrieves similar receipt context", async () => {
  const engine = new TransactionEngine(new GuessAdapter());
  const memory = new HyperdimensionalMemory(128);
  const state = { context: "low", solved: false };
  const accepted = await engine.transact(
    state,
    makeTrace({ branchId: "accepted", actions: [1] }),
    makeCandidate({ context: "low", action: 1, guess: 1, defect: 1 }, "guess", "guess.v1"),
  );
  const rejected = await engine.transact(
    state,
    makeTrace({ branchId: "rejected", actions: [5] }),
    makeCandidate({ context: "high", action: 5, guess: 5, defect: 1 }, "guess", "guess.v1"),
  );
  await memory.add(rejected.receipt);
  await memory.add(accepted.receipt);

  const nearest = await memory.nearest({ context: "low", action: 1 }, 1);
  assert.equal(nearest[0].branchId, "accepted");
});

test("counterfactual ranker penalizes rolled-back accepted losers", async () => {
  const engine = new TransactionEngine(new GuessAdapter());
  const ranker = new CounterfactualRollbackRanker();
  const state = { context: "low", solved: false };
  const committed = await engine.transact(
    state,
    makeTrace({ branchId: "committed", actions: ["b_fast"] }),
    makeCandidate({ context: "low", action: "b_fast", guess: 1, defect: 1 }, "guess", "guess.v1"),
  );
  const loser = await engine.recordEvaluatedCandidate(
    state,
    makeTrace({ branchId: "loser", actions: ["a_slow"] }),
    makeCandidate({ context: "low", action: "a_slow", guess: 1, defect: 1 }, "guess", "guess.v1"),
    hardAccept("guess_oracle", "1.0"),
    {},
    "rolled_back_loser",
  );
  const rejected = await engine.transact(
    state,
    makeTrace({ branchId: "rejected", actions: ["c_unsafe"] }),
    makeCandidate({ context: "low", action: "c_unsafe", guess: 3, defect: 1 }, "guess", "guess.v1"),
  );
  for (const receipt of [committed.receipt, loser.receipt, rejected.receipt]) {
    ranker.update(receipt);
  }

  assert.equal(ranker.rank("low", ["a_slow", "b_fast", "c_unsafe"])[0], "b_fast");
  assert.equal(ranker.stats("low", "b_fast").committed, 1);
  assert.equal(ranker.stats("low", "a_slow").rolledBack, 1);
  assert.equal(ranker.stats("low", "c_unsafe").rejected, 1);
  assert.ok(ranker.score("low", "b_fast") > ranker.score("low", "a_slow"));
});
