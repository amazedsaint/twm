import assert from "node:assert/strict";
import test from "node:test";

import {
  ChessAncestryAdapter,
  ChessResidualRepairer,
  Ledger,
  TransactionEngine,
  coord,
  enumerateChessAncestry,
  makeDefaultChessAncestryProblem,
  makeTrace,
  pathClear,
  reverseChessCandidates,
  runChessAncestryBenchmark,
  runRepairChessEpisode,
} from "../dist/index.js";

test("chess rook path clear uses rule geometry", () => {
  const problem = makeDefaultChessAncestryProblem();
  const candidate = reverseChessCandidates(problem).find((row) => row.payload.move.fromSquare === "e5");

  assert.deepEqual(coord("e4"), [4, 3]);
  assert.equal(pathClear(problem.targetBoard, "a4", "e4"), false);
  assert.equal(pathClear(candidate.payload.predecessor, "e5", "e4"), true);
});

test("chess verifier rejects blocked rook with repair", () => {
  const problem = makeDefaultChessAncestryProblem();
  const candidate = reverseChessCandidates(problem)[0];
  const result = new ChessAncestryAdapter().verify(candidate);

  assert.equal(result.result, "reject");
  assert.equal(result.residual.kind, "illegal_move");
  assert.equal(result.residual.message, "rook path is blocked");
  assert.equal(result.residual.repair.move.fromSquare, "e5");
  assert.equal(result.residual.repair.move.toSquare, "e4");
});

test("chess enumeration finds all legal histories", async () => {
  const problem = makeDefaultChessAncestryProblem();
  const { state, engine } = await enumerateChessAncestry(problem);

  assert.equal(engine.hardVerifierCalls, 7);
  assert.equal(await engine.ledger.audit(), true);
  assert.deepEqual(state.histories.map((move) => [move.fromSquare, move.toSquare]), [
    ["e5", "e4"],
    ["e6", "e4"],
    ["e7", "e4"],
  ]);
});

test("chess residual repair commits after illegal move feedback", async () => {
  const problem = makeDefaultChessAncestryProblem();
  const ledger = new Ledger();
  const result = await runRepairChessEpisode(problem, ledger, new ChessResidualRepairer(), 1);

  assert.equal(result.calls, 2);
  assert.equal(result.success, true);
  assert.equal(result.auditOk, true);
  assert.equal(result.replayRollbackOk, true);
  assert.equal(ledger.committedRows().length, 1);
  assert.equal(ledger.committedRows()[0].replayBundle.candidatePayload.move.fromSquare, "e5");
});

test("chess ancestry benchmark metrics", async () => {
  const report = await runChessAncestryBenchmark();

  assert.equal(report.candidateSpaceSize, 7);
  assert.equal(report.historyCount, 3);
  assert.equal(report.ambiguityEntropy, Math.log2(3));
  assert.equal(report.verifierCalls, 7);
  assert.equal(report.forwardReplaySuccessRate, 1);
  assert.equal(report.staticCallsPerSuccess, 3);
  assert.equal(report.repairCallsPerSuccess, 2);
  assert.equal(report.repairGain, 1.5);
  assert.equal(report.ledgerAudit, true);
  assert.equal(report.replayRollbackRate, 1);
  assert.equal(report.invalidCommitCount, 0);
  assert.equal(report.learnedResidualKinds.illegal_move, 1);
});

test("valid chess history for wrong problem fails closed", async () => {
  const problemA = makeDefaultChessAncestryProblem();
  const problemB = { targetBoard: problemA.targetBoard, movedPieceId: "WK", maxDepth: 1 };
  const candidate = reverseChessCandidates(problemA).find((row) => row.payload.move.fromSquare === "e5");
  const engine = new TransactionEngine(new ChessAncestryAdapter(), new Ledger());
  const outcome = await engine.transact(
    { problem: problemB, histories: [] },
    makeTrace({
      branchId: "wrong-chess-problem",
      actions: [candidate.payload.move],
      seeds: ["chess", "wrong-problem"],
      modelVersion: "chess.test.v1",
    }),
    candidate,
  );

  assert.equal(outcome.committed, false);
  assert.equal(outcome.reason.startsWith("replay_or_rollback_error:"), true);
  assert.equal(engine.invalidCommitCount, 0);
});
