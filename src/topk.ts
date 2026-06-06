import {
  type ProposalTrace,
  type Receipt,
  type TransactionEngine,
  type TypedCandidate,
  makeTrace,
} from "./core.js";
import { type ResidualSignal, ResidualTaxonomyMemory } from "./residuals.js";

export interface ResidualRepairOption<CandidatePayload> {
  label: string;
  candidate: TypedCandidate<CandidatePayload>;
  repairHint: string;
  baseRank: number;
}

export interface ResidualTopKOutcome<State> {
  state: State;
  committed: boolean;
  committedLabel: string;
  submittedLabels: string[];
  receipts: Receipt[];
  verifierCalls: number;
  reason: "commit" | "top_k_exhausted";
}

export class ResidualTopKSubmitter<State, CandidatePayload> {
  engine: TransactionEngine<State, CandidatePayload>;
  memory: ResidualTaxonomyMemory;

  constructor(engine: TransactionEngine<State, CandidatePayload>, memory = new ResidualTaxonomyMemory()) {
    this.engine = engine;
    this.memory = memory;
  }

  rankOptions(
    options: Array<ResidualRepairOption<CandidatePayload>>,
    residualSignal: ResidualSignal | null = null,
  ): Array<ResidualRepairOption<CandidatePayload>> {
    const preferred = this.preferredHints(residualSignal);
    return [...options].sort((a, b) => {
      const aPreferred = a.repairHint && preferred.has(a.repairHint) ? 0 : 1;
      const bPreferred = b.repairHint && preferred.has(b.repairHint) ? 0 : 1;
      return aPreferred - bPreferred
        || a.baseRank - b.baseRank
        || compareCodePoint(a.label, b.label);
    });
  }

  async submit(
    state: State,
    options: Array<ResidualRepairOption<CandidatePayload>>,
    params: {
      topK: number;
      tracePrefix: string;
      residualSignal?: ResidualSignal | null;
      modelVersion?: string;
    },
  ): Promise<ResidualTopKOutcome<State>> {
    if (!Number.isInteger(params.topK) || params.topK < 0) {
      throw new RangeError("topK must be a non-negative integer");
    }
    const ranked = this.rankOptions(options, params.residualSignal ?? null);
    const receipts: Receipt[] = [];
    const submittedLabels: string[] = [];
    let current = state;
    for (let idx = 0; idx < Math.min(params.topK, ranked.length); idx += 1) {
      const option = ranked[idx];
      submittedLabels.push(option.label);
      const trace: ProposalTrace = makeTrace({
        branchId: `${params.tracePrefix}-${idx}-${option.label}`,
        actions: [{ label: option.label, repairHint: option.repairHint }],
        modelVersion: params.modelVersion ?? "residual.topk.v1",
      });
      const outcome = await this.engine.transact(state, trace, option.candidate);
      receipts.push(outcome.receipt);
      if (outcome.committed) {
        current = outcome.state;
        return {
          state: current,
          committed: true,
          committedLabel: option.label,
          submittedLabels,
          receipts,
          verifierCalls: receipts.length,
          reason: "commit",
        };
      }
    }
    return {
      state: current,
      committed: false,
      committedLabel: "",
      submittedLabels,
      receipts,
      verifierCalls: receipts.length,
      reason: "top_k_exhausted",
    };
  }

  private preferredHints(residualSignal: ResidualSignal | null): Set<string> {
    const preferred = new Set<string>();
    if (!residualSignal) {
      return preferred;
    }
    for (const hint of residualSignal.repairHints) {
      preferred.add(hint);
    }
    const topHint = this.memory.topRepairHint(residualSignal.kind);
    if (topHint) {
      preferred.add(topHint);
    }
    return preferred;
  }
}

function compareCodePoint(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}
