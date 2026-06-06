import {




  makeTrace,
} from "./core.js";
import {                      ResidualTaxonomyMemory } from "./residuals.js";


















export class ResidualTopKSubmitter                          {
  engine                                            ;
  memory                        ;

  constructor(engine                                            , memory = new ResidualTaxonomyMemory()) {
    this.engine = engine;
    this.memory = memory;
  }

  rankOptions(
    options                                               ,
    residualSignal                        = null,
  )                                                {
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
    state       ,
    options                                               ,
    params




     ,
  )                                      {
    if (!Number.isInteger(params.topK) || params.topK < 0) {
      throw new RangeError("topK must be a non-negative integer");
    }
    const ranked = this.rankOptions(options, params.residualSignal ?? null);
    const receipts            = [];
    const submittedLabels           = [];
    let current = state;
    for (let idx = 0; idx < Math.min(params.topK, ranked.length); idx += 1) {
      const option = ranked[idx];
      submittedLabels.push(option.label);
      const trace                = makeTrace({
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

          preferredHints(residualSignal                       )              {
    const preferred = new Set        ();
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

function compareCodePoint(a        , b        )         {
  return a < b ? -1 : a > b ? 1 : 0;
}
