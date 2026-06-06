import {




  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { canonicalJson } from "./canonical.js";
























export class PrefixSafeMacroRuntime                                {
  engine                                            ;
  adapter                                                   ;
  prefixChecks = 0;
  prefixRejectCount = 0;
  terminalVerifierCalls = 0;

  constructor(engine                                            , adapter                                                   ) {
    this.engine = engine;
    this.adapter = adapter;
  }

  async run(state       , macro             )                               {
    let current = state;
    const visited          = [state];
    let prefixChecks = 0;
    for (let idx = 0; idx < macro.steps.length; idx += 1) {
      const step = macro.steps[idx];
      const nextState = this.adapter.applyStep(current, step);
      prefixChecks += 1;
      this.prefixChecks += 1;
      const result = this.adapter.prefixSafe(nextState, step, idx);
      visited.push(nextState);
      if (result.result !== "accept") {
        this.prefixRejectCount += 1;
        const candidate = makeCandidate(
          {
            context: macro.context,
            macroId: macro.macroId,
            macro: macro.steps,
            unsafePrefix: macro.steps.slice(0, idx + 1),
            stepIndex: idx,
            state: nextState,
          }                    ,
          "macro.prefix",
          "macro.prefix.v1",
        );
        const outcome = await this.engine.recordEvaluatedCandidate(
          state,
          makeTrace({
            branchId: `${macro.macroId}:prefix:${idx}`,
            actions: macro.steps.slice(0, idx + 1),
            latentStates: visited,
            modelVersion: macro.modelVersion,
          }),
          candidate,
          result,
          {},
          "prefix_unsafe",
        );
        return { state, committed: false, receipt: outcome.receipt, reason: outcome.reason, prefixChecks, terminalVerifierCalls: 0 };
      }
      current = nextState;
    }
    const candidate = this.adapter.projectMacro(state, macro, current);
    const outcome = await this.engine.transact(
      state,
      makeTrace({
        branchId: macro.macroId,
        actions: macro.steps,
        latentStates: visited,
        modelVersion: macro.modelVersion,
      }),
      candidate,
    );
    this.terminalVerifierCalls += 1;
    return {
      state: outcome.state,
      committed: outcome.committed,
      receipt: outcome.receipt,
      reason: outcome.reason,
      prefixChecks,
      terminalVerifierCalls: 1,
    };
  }
}

export class MacroMemory                 {
  accepted = new Map                             ();
  rejectedPrefixes = new Map                             ();

  update(receipt         )       {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload
      : {};
    const context = String(payload.context ?? "global");
    const token = tokenFromUnknown(payload.macro ?? []);
    if (receipt.hardResult.result === "accept" && receipt.committed) {
      increment(this.accepted, context, token);
    } else if (receipt.commitDecision === "prefix_unsafe") {
      increment(this.rejectedPrefixes, context, token);
    }
  }

  rank(context        , macros                    )                     {
    return macros
      .map((macro, idx) => ({ macro, idx, token: tokenFromUnknown(macro.steps) }))
      .sort((a, b) => {
        const acceptedDiff = getCount(this.accepted, context, b.token) - getCount(this.accepted, context, a.token);
        if (acceptedDiff !== 0) {
          return acceptedDiff;
        }
        const rejectDiff = getCount(this.rejectedPrefixes, context, a.token) - getCount(this.rejectedPrefixes, context, b.token);
        if (rejectDiff !== 0) {
          return rejectDiff;
        }
        return a.idx - b.idx;
      })
      .map((row) => row.macro);
  }
}





































export class GridMacroAdapter                                                                      {
  verifierId = "grid_macro_oracle";
  verifierVersion = "1.0";

  applyStep(state           , step          )            {
    const [x0, y0] = state.position;
    let x = x0;
    let y = y0;
    if (step === "E") x += 1;
    else if (step === "W") x -= 1;
    else if (step === "N") y -= 1;
    else if (step === "S") y += 1;
    else throw new Error(`unsupported grid step: ${step}`);
    return { ...state, position: [x, y] };
  }

  prefixSafe(state           , step          , stepIndex        )                     {
    const [x, y] = state.position;
    const [width, height] = state.bounds;
    if (x < 0 || x >= width || y < 0 || y >= height) {
      return hardReject(this.verifierId, this.verifierVersion, {
        kind: "out_of_bounds",
        position: state.position,
        step,
        stepIndex,
      });
    }
    if (state.walls.some(([wx, wy]) => wx === x && wy === y)) {
      return hardReject(this.verifierId, this.verifierVersion, {
        kind: "wall",
        position: state.position,
        step,
        stepIndex,
      });
    }
    return hardAccept(this.verifierId, this.verifierVersion);
  }

  projectMacro(preState           , macro                 , finalState           )                                   {
    return makeCandidate(
      {
        context: macro.context,
        macroId: macro.macroId,
        macro: macro.steps,
        start: preState.position,
        goal: preState.goal,
        final: finalState.position,
        bounds: preState.bounds,
        walls: [...preState.walls].sort(([ax, ay], [bx, by]) => ax - bx || ay - by),
        cost: macro.steps.length,
      },
      "grid.macro",
      "grid.macro.v1",
    );
  }

  verify(candidate                                  )                     {
    const final = candidate.payload.final;
    const goal = candidate.payload.goal;
    if (final[0] === goal[0] && final[1] === goal[1]) {
      return hardAccept(this.verifierId, this.verifierVersion, { cost: candidate.payload.cost });
    }
    return hardReject(this.verifierId, this.verifierVersion, { kind: "missed_goal", final, goal }, { cost: candidate.payload.cost });
  }

  applyCommit(state           , candidate                                  )            {
    return { ...state, position: candidate.payload.final, solved: true, macroId: candidate.payload.macroId };
  }

  replay(state           , receipt         )            {
    const payload = (receipt.replayBundle                                          ).candidatePayload;
    return { ...state, position: payload.final, solved: true, macroId: payload.macroId };
  }

  rollback(_state           , receipt         )            {
    return (receipt.rollbackBundle                           ).preState;
  }
}

export function defaultGridState()            {
  return {
    position: [0, 0],
    goal: [2, 2],
    bounds: [3, 3],
    walls: [[1, 1]],
    solved: false,
  };
}

export function defaultGridMacros()                         {
  return [
    { macroId: "unsafe-through-wall", steps: ["E", "S", "E", "S"], context: "grid-3x3", modelVersion: "macro.grid.v1" },
    { macroId: "safe-around-wall", steps: ["E", "E", "S", "S"], context: "grid-3x3", modelVersion: "macro.grid.v1" },
  ];
}

export async function runPrefixSafeGridSequence(
  macros                        ,
  ledger        ,
  memory                        ,
)                                                                                                {
  const adapter = new GridMacroAdapter();
  const engine = new TransactionEngine(adapter, ledger);
  const runtime = new PrefixSafeMacroRuntime(engine, adapter);
  const state = defaultGridState();
  let attempts = 0;
  let terminalCalls = 0;
  for (const macro of macros) {
    attempts += 1;
    const outcome = await runtime.run(state, macro);
    terminalCalls += outcome.terminalVerifierCalls;
    memory?.update(outcome.receipt);
    if (outcome.committed) {
      return { attempts, terminalCalls, prefixRejects: runtime.prefixRejectCount, success: true };
    }
  }
  return { attempts, terminalCalls, prefixRejects: runtime.prefixRejectCount, success: false };
}

export async function runMacroGridBenchmark(episodes = 32)                           {
  const macros = defaultGridMacros();
  const prefixLedger = new Ledger();
  const learnedLedger = new Ledger();
  let staticAttempts = 0;
  let staticTerminalCalls = 0;
  let staticSuccesses = 0;
  let staticPrefixRejects = 0;
  for (let idx = 0; idx < episodes; idx += 1) {
    const result = await runPrefixSafeGridSequence(macros, prefixLedger);
    staticAttempts += result.attempts;
    staticTerminalCalls += result.terminalCalls;
    staticPrefixRejects += result.prefixRejects;
    staticSuccesses += result.success ? 1 : 0;
  }

  const memory = new MacroMemory          ();
  let learnedAttempts = 0;
  let learnedTerminalCalls = 0;
  let learnedSuccesses = 0;
  let learnedPrefixRejects = 0;
  for (let idx = 0; idx < episodes; idx += 1) {
    const result = await runPrefixSafeGridSequence(memory.rank("grid-3x3", macros), learnedLedger, memory);
    learnedAttempts += result.attempts;
    learnedTerminalCalls += result.terminalCalls;
    learnedPrefixRejects += result.prefixRejects;
    learnedSuccesses += result.success ? 1 : 0;
  }

  const staticAttemptsPerSuccess = staticAttempts / staticSuccesses;
  const learnedAttemptsPerSuccess = learnedAttempts / learnedSuccesses;
  return {
    terminalOnlyCallsPerSuccess: macros.length,
    prefixSafeCallsPerSuccess: staticTerminalCalls / staticSuccesses,
    staticMacroAttemptsPerSuccess: staticAttemptsPerSuccess,
    learnedMacroAttemptsPerSuccess: learnedAttemptsPerSuccess,
    prefixRejectCount: staticPrefixRejects,
    learnedPrefixRejectCount: learnedPrefixRejects,
    macroReuseGain: staticAttemptsPerSuccess / learnedAttemptsPerSuccess,
    ledgerAudit: await prefixLedger.audit() && await learnedLedger.audit(),
    invalidCommitCount: invalidCommits([prefixLedger, learnedLedger]),
  };
}

function tokenFromUnknown(value         )         {
  if (value && typeof value === "object") {
    return canonicalJson(value);
  }
  return String(value);
}

function increment(table                                  , context        , token        )       {
  let row = table.get(context);
  if (!row) {
    row = new Map();
    table.set(context, row);
  }
  row.set(token, (row.get(token) ?? 0) + 1);
}

function getCount(table                                  , context        , token        )         {
  return table.get(context)?.get(token) ?? 0;
}

function invalidCommits(ledgers          )         {
  return ledgers.reduce(
    (total, ledger) => total + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
    0,
  );
}
