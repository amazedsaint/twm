import { compareCodePoint, stableHash } from "./canonical.js";
import {                                                            makeTrace } from "./core.js";
import { wilsonLowerBound } from "./reliability.js";

export const BUDGET_POLICY_SNAPSHOT_SCHEMA = "trwm.budget_policy_snapshot.v1";











































export class ReceiptBudgetPolicy {
  z        ;
          rows = new Map                         ();

  constructor(options                 = {}) {
    this.z = options.z ?? 1.96;
    if (this.z <= 0) {
      throw new RangeError("z must be positive");
    }
  }

  update(token        , receipt         )                  {
    const subject = String(token);
    if (!subject) {
      throw new RangeError("token must be non-empty");
    }
    const row = { ...this.score(subject) };
    row.observations += 1;
    if (receipt.committed && receipt.hardResult.result === "accept") {
      row.successes += 1;
    } else if (receipt.hardResult.result === "reject" || receipt.commitDecision !== "commit") {
      row.failures += 1;
    }
    const scored = this.scored(row);
    this.rows.set(subject, scored);
    return scored;
  }

  score(token        )                  {
    const subject = String(token);
    return this.rows.get(subject) ?? this.scored({
      token: subject,
      successes: 0,
      failures: 0,
      observations: 0,
      successLowerBound: 0,
    });
  }

  utility                  (candidate                                   )         {
    return roundFloat(candidate.reward * this.score(candidate.token).successLowerBound);
  }

  plan                  (candidates                                          , budget        )                               {
    if (!Number.isInteger(budget) || budget < 0) {
      throw new RangeError("budget must be a non-negative integer");
    }
    for (const row of candidates) {
      validateBudgetCandidate(row);
    }
    const cells                                                                                      = Array.from(
      { length: budget + 1 },
      () => null,
    );
    cells[0] = { utility: 0, subset: [] };
    for (const row of candidates) {
      const rowUtility = this.utility(row);
      for (let spentBefore = budget - row.verifierCost; spentBefore >= 0; spentBefore -= 1) {
        const current = cells[spentBefore];
        if (!current) {
          continue;
        }
        const nextSpent = spentBefore + row.verifierCost;
        const candidateCell = {
          utility: roundFloat(current.utility + rowUtility),
          subset: [...current.subset, row],
        };
        const existing = cells[nextSpent];
        if (!existing || betterSubset(candidateCell.subset, candidateCell.utility, nextSpent, existing.subset, existing.utility, nextSpent)) {
          cells[nextSpent] = candidateCell;
        }
      }
    }
    let bestSubset                                           = [];
    let bestUtility = 0;
    let bestSpent = 0;
    for (let spent = 0; spent < cells.length; spent += 1) {
      const cell = cells[spent];
      if (cell && betterSubset(cell.subset, cell.utility, spent, bestSubset, bestUtility, bestSpent)) {
        bestSubset = cell.subset;
        bestUtility = cell.utility;
        bestSpent = spent;
      }
    }
    const selected = [...bestSubset].sort((a, b) => a.baseRank - b.baseRank || compareCodePoint(a.label, b.label));
    return { budget, selected, spent: bestSpent, expectedUtility: bestUtility };
  }

  async submit                         (
    engine                                            ,
    state       ,
    candidates                                          ,
    params                                                                ,
  )                                      {
    const plan = this.plan(candidates, params.budget);
    const receipts            = [];
    const submittedLabels           = [];
    let spent = 0;
    let current = state;
    for (let idx = 0; idx < plan.selected.length; idx += 1) {
      const row = plan.selected[idx];
      if (spent + row.verifierCost > params.budget) {
        break;
      }
      const outcome = await engine.transact(
        state,
        makeTrace({
          branchId: `${params.tracePrefix}-${idx}-${row.label}`,
          actions: [{ label: row.label, token: row.token, verifierCost: row.verifierCost }],
          modelVersion: params.modelVersion ?? "budget.policy.v1",
        }),
        row.candidate,
      );
      receipts.push(outcome.receipt);
      submittedLabels.push(row.label);
      spent += row.verifierCost;
      if (outcome.committed) {
        current = outcome.state;
        return {
          state: current,
          committed: true,
          committedLabel: row.label,
          selectedLabels: plan.selected.map((item) => item.label),
          submittedLabels,
          verifierCostSpent: spent,
          receipts,
          reason: "commit",
        };
      }
    }
    return {
      state: current,
      committed: false,
      committedLabel: "",
      selectedLabels: plan.selected.map((item) => item.label),
      submittedLabels,
      verifierCostSpent: spent,
      receipts,
      reason: "budget_exhausted",
    };
  }

  async snapshot()                                {
    const pending                       = {
      schemaVersion: BUDGET_POLICY_SNAPSHOT_SCHEMA,
      rows: Array.from(this.rows.values()).sort((a, b) => compareCodePoint(a.token, b.token)),
      z: this.z,
      snapshotHash: "",
    };
    return { ...pending, snapshotHash: await budgetPolicySnapshotHash(pending) };
  }

          scored(row                 )                  {
    return {
      ...row,
      successLowerBound: roundFloat(wilsonLowerBound(row.successes, row.failures, this.z)),
    };
  }
}

export async function budgetPolicySnapshotHash(snapshot                      )                  {
  const { snapshotHash: _snapshotHash, ...withoutHash } = snapshot;
  return stableHash(withoutHash);
}

export async function validateBudgetPolicySnapshot(snapshot                      )                   {
  if (snapshot.schemaVersion !== BUDGET_POLICY_SNAPSHOT_SCHEMA) {
    return false;
  }
  if (!Number.isFinite(snapshot.z) || snapshot.z <= 0) {
    return false;
  }
  if (new Set(snapshot.rows.map((row) => row.token)).size !== snapshot.rows.length) {
    return false;
  }
  for (const row of snapshot.rows) {
    if (!row.token) {
      return false;
    }
    if (!nonNegativeInteger(row.successes) || !nonNegativeInteger(row.failures) || !nonNegativeInteger(row.observations)) {
      return false;
    }
    if (row.observations < row.successes + row.failures) {
      return false;
    }
    if (row.successLowerBound !== roundFloat(wilsonLowerBound(row.successes, row.failures, snapshot.z))) {
      return false;
    }
  }
  return snapshot.snapshotHash === await budgetPolicySnapshotHash(snapshot);
}

function betterSubset                  (
  subset                                          ,
  utility        ,
  spent        ,
  bestSubset                                          ,
  bestUtility        ,
  bestSpent        ,
)          {
  if (utility !== bestUtility) {
    return utility > bestUtility;
  }
  if (spent !== bestSpent) {
    return spent < bestSpent;
  }
  return labelKey(subset) < labelKey(bestSubset);
}

function roundFloat(value        )         {
  return Math.round(value * 1_000_000_000_000) / 1_000_000_000_000;
}

function labelKey                  (rows                                          )         {
  return rows.map((row) => row.label).sort(compareCodePoint).join("\u0000");
}

function nonNegativeInteger(value        )          {
  return Number.isInteger(value) && value >= 0;
}

function validateBudgetCandidate                  (candidate                                   )       {
  if (!candidate.label) {
    throw new RangeError("label must be non-empty");
  }
  if (!candidate.token) {
    throw new RangeError("token must be non-empty");
  }
  if (!Number.isInteger(candidate.verifierCost) || candidate.verifierCost <= 0) {
    throw new RangeError("verifierCost must be a positive integer");
  }
  if (!Number.isFinite(candidate.reward) || candidate.reward < 0) {
    throw new RangeError("reward must be a non-negative finite number");
  }
  if (!Number.isInteger(candidate.baseRank)) {
    throw new RangeError("baseRank must be an integer");
  }
}
