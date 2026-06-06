import { ReceiptBudgetPolicy, type BudgetCandidate } from "./budget_policy.js";
import { type Receipt, TransactionEngine, makeTrace } from "./core.js";
import {
  type InventoryReservationPayload,
  type InventoryState,
  InventoryReservationAdapter,
  makeReservationCandidate,
} from "./operations.js";
import {
  LEARNING_EVALUATION_CERTIFICATE_SCHEMA,
  buildLearningEvaluationCertificate,
  learningEvaluationSupportsClaim,
  validateLearningEvaluationCertificate,
} from "./evaluation.js";
import { BUDGET_POLICY_LIMIT, BUDGET_POLICY_ORDER } from "./budget_policy_benchmark.js";

export interface LearningEvaluationReport {
  schemaVersion: string;
  certificateValid: boolean;
  certificateSupportsClaim: boolean;
  claimId: string;
  trainingReceiptCount: number;
  evaluationReceiptCount: number;
  trainEvalDisjoint: boolean;
  sameCaseBaseline: boolean;
  baselineName: string;
  learnedName: string;
  baselineSuccessCount: number;
  learnedSuccessCount: number;
  baselineVerifierCalls: number;
  learnedVerifierCalls: number;
  verifierBudget: number;
  candidateCount: number;
  verifierCallGainNumerator: number;
  verifierCallGainDenominator: number;
  hardCommitOnly: boolean;
  invalidCommitCount: number;
  ledgerAudit: boolean;
  replayRollbackRate: number;
  learnerSnapshotHash: string;
  certificateHash: string;
  tamperDetected: boolean;
  overlapDetected: boolean;
}

export async function runLearningEvaluationBenchmark(): Promise<LearningEvaluationReport> {
  const state: InventoryState = { stock: { widget: 5 }, reserved: { widget: 0 }, committedOrders: [] };
  const policy = new ReceiptBudgetPolicy();
  const trainingEngine = new TransactionEngine(new InventoryReservationAdapter());
  const trainingReceipts: Receipt[] = [];
  for (const [label, quantity] of [["quantity-5", 5], ["quantity-8", 8], ["quantity-7", 7]] as Array<[string, number]>) {
    const receipt = (await trainingEngine.transact(
      state,
      makeTrace({ branchId: `learning-eval-train-${label}`, actions: [{ label }] }),
      await makeReservationCandidate(state, `learning-train-${label}`, "widget", 8, quantity, "learning-eval-train"),
    )).receipt;
    policy.update(label, receipt);
    trainingReceipts.push(receipt);
  }

  const candidates = await learningEvalCandidates(state);
  const baselineEngine = new TransactionEngine(new InventoryReservationAdapter());
  const baseline = await cheapFirstSubmit(baselineEngine, state, candidates, BUDGET_POLICY_LIMIT);
  const learnedEngine = new TransactionEngine(new InventoryReservationAdapter());
  const learned = await policy.submit(learnedEngine, state, candidates, {
    budget: BUDGET_POLICY_LIMIT,
    tracePrefix: "learning-eval-learned",
  });
  const snapshot = await policy.snapshot();
  const ledgerAudit = await trainingEngine.ledger.audit()
    && await baselineEngine.ledger.audit()
    && await learnedEngine.ledger.audit();
  const replayRollbackRate = await replayRollbackRateFor([
    [trainingEngine, state],
    [baselineEngine, state],
    [learnedEngine, state],
  ]);
  const certificate = await buildLearningEvaluationCertificate({
    claimId: "budget_policy_trace_disjoint_eval",
    learnerId: "receipt_budget_policy",
    learnerSnapshotHash: snapshot.snapshotHash,
    trainingReceiptHashes: trainingReceipts.map((receipt) => receipt.receiptHash),
    evaluationReceiptHashes: learned.receipts.map((receipt) => receipt.receiptHash),
    baselineName: "cheap_first_same_budget",
    learnedName: "receipt_budget_policy",
    baselineVerifierCalls: baseline.receipts.length,
    learnedVerifierCalls: learned.receipts.length,
    baselineSuccessCount: baseline.committed ? 1 : 0,
    learnedSuccessCount: learned.committed ? 1 : 0,
    verifierBudget: BUDGET_POLICY_LIMIT,
    candidateCount: candidates.length,
    sameCaseBaseline: true,
    hardCommitOnly: learned.receipts.every((receipt) => receipt.committed === (receipt.hardResult.result === "accept")),
    invalidCommitCount: trainingEngine.invalidCommitCount + baselineEngine.invalidCommitCount + learnedEngine.invalidCommitCount,
    ledgerAudit,
    replayRollbackRate,
    metrics: {
      baselineSelected: baseline.submittedLabels,
      learnedSelected: learned.selectedLabels,
      baselineCostSpent: baseline.verifierCostSpent,
      learnedCostSpent: learned.verifierCostSpent,
    },
  });
  const tampered = { ...certificate, metrics: { ...certificate.metrics, learnedVerifierCalls: 99 } };
  const overlapping = await buildLearningEvaluationCertificate({
    claimId: certificate.claimId,
    learnerId: certificate.learnerId,
    learnerSnapshotHash: certificate.learnerSnapshotHash,
    trainingReceiptHashes: certificate.trainingReceiptHashes,
    evaluationReceiptHashes: [certificate.trainingReceiptHashes[0]],
    baselineName: certificate.baselineName,
    learnedName: certificate.learnedName,
    baselineVerifierCalls: certificate.baselineVerifierCalls,
    learnedVerifierCalls: 1,
    baselineSuccessCount: certificate.baselineSuccessCount,
    learnedSuccessCount: certificate.learnedSuccessCount,
    verifierBudget: certificate.verifierBudget,
    candidateCount: certificate.candidateCount,
    sameCaseBaseline: certificate.sameCaseBaseline,
    hardCommitOnly: certificate.hardCommitOnly,
    invalidCommitCount: certificate.invalidCommitCount,
    ledgerAudit: certificate.ledgerAudit,
    replayRollbackRate: certificate.replayRollbackRate,
    metrics: certificate.metrics,
  });

  return {
    schemaVersion: LEARNING_EVALUATION_CERTIFICATE_SCHEMA,
    certificateValid: await validateLearningEvaluationCertificate(certificate),
    certificateSupportsClaim: await learningEvaluationSupportsClaim(certificate),
    claimId: certificate.claimId,
    trainingReceiptCount: certificate.trainingReceiptHashes.length,
    evaluationReceiptCount: certificate.evaluationReceiptHashes.length,
    trainEvalDisjoint: certificate.trainEvalDisjoint,
    sameCaseBaseline: certificate.sameCaseBaseline,
    baselineName: certificate.baselineName,
    learnedName: certificate.learnedName,
    baselineSuccessCount: certificate.baselineSuccessCount,
    learnedSuccessCount: certificate.learnedSuccessCount,
    baselineVerifierCalls: certificate.baselineVerifierCalls,
    learnedVerifierCalls: certificate.learnedVerifierCalls,
    verifierBudget: certificate.verifierBudget,
    candidateCount: certificate.candidateCount,
    verifierCallGainNumerator: certificate.verifierCallGainNumerator,
    verifierCallGainDenominator: certificate.verifierCallGainDenominator,
    hardCommitOnly: certificate.hardCommitOnly,
    invalidCommitCount: certificate.invalidCommitCount,
    ledgerAudit: certificate.ledgerAudit,
    replayRollbackRate: certificate.replayRollbackRate,
    learnerSnapshotHash: certificate.learnerSnapshotHash,
    certificateHash: certificate.certificateHash,
    tamperDetected: !await validateLearningEvaluationCertificate(tampered),
    overlapDetected: !await validateLearningEvaluationCertificate(overlapping),
  };
}

async function learningEvalCandidates(state: InventoryState): Promise<Array<BudgetCandidate<InventoryReservationPayload>>> {
  const costs = new Map<number, number>([[8, 1], [7, 1], [5, 3], [4, 2]]);
  const rows: Array<BudgetCandidate<InventoryReservationPayload>> = [];
  for (let idx = 0; idx < BUDGET_POLICY_ORDER.length; idx += 1) {
    const quantity = BUDGET_POLICY_ORDER[idx];
    const cost = costs.get(quantity) ?? 1;
    rows.push({
      label: `quantity-${quantity}`,
      token: `quantity-${quantity}`,
      candidate: await makeReservationCandidate(state, `learning-eval-q${quantity}`, "widget", 8, quantity, "learning-eval", cost),
      verifierCost: cost,
      reward: quantity,
      baseRank: idx,
    });
  }
  return rows;
}

async function cheapFirstSubmit(
  engine: TransactionEngine<InventoryState, InventoryReservationPayload>,
  state: InventoryState,
  candidates: Array<BudgetCandidate<InventoryReservationPayload>>,
  budget: number,
): Promise<{ committed: boolean; submittedLabels: string[]; verifierCostSpent: number; receipts: Receipt[] }> {
  let spent = 0;
  const submittedLabels: string[] = [];
  const receipts: Receipt[] = [];
  for (const [idx, row] of [...candidates].sort((a, b) => a.verifierCost - b.verifierCost || a.baseRank - b.baseRank || compareCodePoint(a.label, b.label)).entries()) {
    if (spent + row.verifierCost > budget) {
      continue;
    }
    const outcome = await engine.transact(
      state,
      makeTrace({ branchId: `learning-eval-baseline-${idx}-${row.label}`, actions: [{ label: row.label }] }),
      row.candidate,
    );
    receipts.push(outcome.receipt);
    submittedLabels.push(row.label);
    spent += row.verifierCost;
    if (outcome.committed) {
      return { committed: true, submittedLabels, verifierCostSpent: spent, receipts };
    }
  }
  return { committed: false, submittedLabels, verifierCostSpent: spent, receipts };
}

async function replayRollbackRateFor(rows: Array<[TransactionEngine<InventoryState, InventoryReservationPayload>, InventoryState]>): Promise<number> {
  let ok = 0;
  for (const [engine, state] of rows) {
    try {
      if (await engine.ledger.audit()) {
        await engine.replayAudit(state);
        if (JSON.stringify(await engine.rollbackAudit(state)) === JSON.stringify(state)) {
          ok += 1;
        }
      }
    } catch (_error) {
      // Leave this row failed.
    }
  }
  return ok / rows.length;
}

function compareCodePoint(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}
