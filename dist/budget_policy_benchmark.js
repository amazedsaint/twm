import { ReceiptBudgetPolicy,                       validateBudgetPolicySnapshot } from "./budget_policy.js";
import { TransactionEngine, makeTrace } from "./core.js";
import {


  InventoryReservationAdapter,
  makeReservationCandidate,
  normalizeInventoryState,
} from "./operations.js";

export const BUDGET_POLICY_LIMIT = 3;
export const BUDGET_POLICY_ORDER = [8, 7, 5, 4]         ;




























export async function runBudgetPolicyBenchmark()                              {
  const seedState                 = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const policy = new ReceiptBudgetPolicy();
  const trainingEngine = new TransactionEngine(new InventoryReservationAdapter());
  const trainingSpecs                          = [["quantity-5", 5], ["quantity-8", 8], ["quantity-7", 7]];
  const trainingBranchIds           = [];
  for (const [label, quantity] of trainingSpecs) {
    const branchId = `budget-policy-train-${label}`;
    trainingBranchIds.push(branchId);
    const receipt = (await trainingEngine.transact(
      seedState,
      makeTrace({ branchId, actions: [{ label }] }),
      await makeReservationCandidate(seedState, `train-${label}`, "widget", 8, quantity, "budget-policy-train"),
    )).receipt;
    policy.update(label, receipt);
  }

  const candidates = await budgetCandidates(seedState);
  const cheapEngine = new TransactionEngine(new InventoryReservationAdapter());
  const cheap = await cheapFirstSubmit(cheapEngine, seedState, candidates, BUDGET_POLICY_LIMIT);
  const learnedEngine = new TransactionEngine(new InventoryReservationAdapter());
  const learned = await policy.submit(
    learnedEngine,
    seedState,
    candidates,
    { budget: BUDGET_POLICY_LIMIT, tracePrefix: "budget-policy-learned" },
  );
  const snapshot = await policy.snapshot();
  const tampered = { ...snapshot, rows: snapshot.rows.map((row) => ({ ...row, successes: 0 })) };
  const committedState = normalizeInventoryState(learned.state);
  let replayRollbackRate = 0;
  if (await learnedEngine.ledger.audit()) {
    try {
      await learnedEngine.replayAudit(seedState);
      replayRollbackRate = JSON.stringify(await learnedEngine.rollbackAudit(seedState)) === JSON.stringify(seedState) ? 1 : 0;
    } catch (_error) {
      replayRollbackRate = 0;
    }
  }

  return {
    trainingReceiptCount: trainingSpecs.length,
    budget: BUDGET_POLICY_LIMIT,
    candidateCount: candidates.length,
    learnedSuccessToken: "quantity-5",
    learnedSuccessLowerBound: policy.score("quantity-5").successLowerBound,
    cheapFirstSelected: cheap.submittedLabels,
    cheapFirstCommitted: cheap.committed,
    cheapFirstVerifierCalls: cheap.submittedLabels.length,
    cheapFirstCostSpent: cheap.verifierCostSpent,
    learnedSelected: learned.selectedLabels,
    learnedCommitted: learned.committed,
    learnedCommittedLabel: learned.committedLabel,
    learnedVerifierCalls: learned.receipts.length,
    learnedCostSpent: learned.verifierCostSpent,
    learnedExpectedUtility: policy.plan(candidates, BUDGET_POLICY_LIMIT).expectedUtility,
    verifierCallGain: cheap.submittedLabels.length / learned.receipts.length,
    verifierCostRatio: cheap.verifierCostSpent / learned.verifierCostSpent,
    evaluationReceiptCount: learned.receipts.length,
    heldoutTraceDisjoint: learned.receipts.every((receipt) => !trainingBranchIds.includes(receipt.branchId)),
    snapshotValid: await validateBudgetPolicySnapshot(snapshot),
    tamperDetected: !await validateBudgetPolicySnapshot(tampered),
    ledgerAudit: await learnedEngine.ledger.audit() && committedState.stock.widget === 0,
    replayRollbackRate,
    invalidCommitCount: trainingEngine.invalidCommitCount + cheapEngine.invalidCommitCount + learnedEngine.invalidCommitCount,
  };
}

async function budgetCandidates(state                )                                                               {
  const costs = new Map                ([[8, 1], [7, 1], [5, 3], [4, 2]]);
  const rows                                                      = [];
  for (let idx = 0; idx < BUDGET_POLICY_ORDER.length; idx += 1) {
    const quantity = BUDGET_POLICY_ORDER[idx];
    const cost = costs.get(quantity) ?? 1;
    rows.push({
      label: `quantity-${quantity}`,
      token: `quantity-${quantity}`,
      candidate: await makeReservationCandidate(state, `budget-q${quantity}`, "widget", 8, quantity, "budget-policy", cost),
      verifierCost: cost,
      reward: quantity,
      baseRank: idx,
    });
  }
  return rows;
}

async function cheapFirstSubmit(
  engine                                                                ,
  state                ,
  candidates                                                     ,
  budget        ,
)                                                                                        {
  let spent = 0;
  const submittedLabels           = [];
  for (const [idx, row] of [...candidates].sort((a, b) => a.verifierCost - b.verifierCost || a.baseRank - b.baseRank || compareCodePoint(a.label, b.label)).entries()) {
    if (spent + row.verifierCost > budget) {
      continue;
    }
    const outcome = await engine.transact(
      state,
      makeTrace({ branchId: `budget-policy-cheap-${idx}-${row.label}`, actions: [{ label: row.label }] }),
      row.candidate,
    );
    submittedLabels.push(row.label);
    spent += row.verifierCost;
    if (outcome.committed) {
      return { committed: true, submittedLabels, verifierCostSpent: spent };
    }
  }
  return { committed: false, submittedLabels, verifierCostSpent: spent };
}

function compareCodePoint(a        , b        )         {
  return a < b ? -1 : a > b ? 1 : 0;
}
