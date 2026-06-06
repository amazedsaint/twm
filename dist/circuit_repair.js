import {




  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { stableHash } from "./canonical.js";




export const OP_NAMES                         = {
  0: "FALSE",
  1: "NOR",
  2: "A_LT_B",
  3: "NOT_A",
  4: "A_GT_B",
  5: "NOT_B",
  6: "XOR",
  7: "NAND",
  8: "AND",
  9: "XNOR",
  10: "B",
  11: "A_IMPLIES_B",
  12: "A",
  13: "B_IMPLIES_A",
  14: "OR",
  15: "TRUE",
};







































































export class BooleanCircuitAdapter                                                                               {
  verifierId = "boolean_circuit_truth_table_verifier";
  verifierVersion = "1.0";

  verify(candidate                                         )                     {
    const problem = normalizeCircuitProblem(candidate.payload.problem);
    const netlist = normalizeNetlist(candidate.payload.netlist);
    const metadata = {
      cost: candidate.payload.cost,
      gateCount: netlist.gates.length,
      truthRows: problem.targetTable.length,
    };
    const shapeError = candidateShapeError(problem, netlist);
    if (shapeError) {
      return this.reject("schema_error", { message: shapeError }, metadata);
    }
    for (let index = 0; index < problem.targetTable.length; index += 1) {
      const row = problem.targetTable[index];
      const actual = evaluateNetlist(netlist, row.assignment);
      if (!bitsEqual(actual, row.outputs)) {
        return this.reject(
          "truth_table_mismatch",
          {
            row: index,
            assignment: row.assignment,
            expected: row.outputs,
            actual,
            repair: diagnoseMutableGate(problem, netlist),
          },
          metadata,
        );
      }
    }
    return hardAccept(this.verifierId, this.verifierVersion, metadata);
  }

  applyCommit(state                    , candidate                                         )                     {
    const current = normalizeCircuitState(state);
    const problem = normalizeCircuitProblem(candidate.payload.problem);
    if (!circuitProblemsEqual(current.problem, problem)) {
      throw new Error("candidate problem does not match current circuit state");
    }
    return { problem, solved: true, netlist: normalizeNetlist(candidate.payload.netlist) };
  }

  replay(state                    , receipt         )                     {
    const current = normalizeCircuitState(state);
    const payload = (receipt.replayBundle                                                 ).candidatePayload;
    const problem = normalizeCircuitProblem(payload.problem);
    if (!circuitProblemsEqual(current.problem, problem)) {
      throw new Error("receipt problem does not match replay circuit state");
    }
    return { problem, solved: true, netlist: normalizeNetlist(payload.netlist) };
  }

  rollback(_state                    , receipt         )                     {
    return normalizeCircuitState((receipt.rollbackBundle                                    ).preState);
  }

          reject(kind                         , residual                               , metadata                         )                     {
    return hardReject(this.verifierId, this.verifierVersion, { kind, ...residual }, metadata);
  }
}

export class CircuitResidualRepairer {
  rejectedResiduals = new Map                ();
  acceptedOps = new Map                ();

  update(receipt         )       {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload
      : {};
    if (receipt.hardResult.result === "accept") {
      const key = String(payload.opMask ?? "unknown");
      this.acceptedOps.set(key, (this.acceptedOps.get(key) ?? 0) + 1);
      return;
    }
    if (receipt.hardResult.result === "reject" && isCircuitResidual(receipt.hardResult.residual)) {
      const kind = receipt.hardResult.residual.kind;
      this.rejectedResiduals.set(kind, (this.rejectedResiduals.get(kind) ?? 0) + 1);
    }
  }

  async propose(candidate                                         , residual         )                                                          {
    if (!isCircuitResidual(residual) || !residual.repair || typeof residual.repair.opMask !== "number") {
      return null;
    }
    if (residual.repair.opMask === candidate.payload.opMask) {
      return null;
    }
    return makeCircuitCandidate(
      normalizeCircuitProblem(candidate.payload.problem),
      residual.repair.opMask,
      candidate.payload.context || "circuit-repair",
      candidate.payload.cost + 1,
    );
  }
}

export function evalOpMask(opMaskInput        , leftInput        , rightInput        )         {
  const opMask = normalizeOpMask(opMaskInput);
  const left = bit(leftInput);
  const right = bit(rightInput);
  const index = (left << 1) | right;
  return (opMask >> index) & 1;
}

export function normalizeGate(gateInput                                       )              {
  const raw = gateInput                           ;
  const gateId = raw.gateId ?? raw.gate_id;
  const opMask = raw.opMask ?? raw.op_mask;
  if (typeof gateId !== "string" || gateId.length === 0) {
    throw new RangeError("gateId must be a non-empty string");
  }
  if (!Array.isArray(raw.inputs) || raw.inputs.length !== 2) {
    throw new RangeError("this G1 canary supports binary gates only");
  }
  return {
    gateId,
    opMask: normalizeOpMask(Number(opMask)),
    inputs: [String(raw.inputs[0]), String(raw.inputs[1])],
  };
}

export function normalizeNetlist(netlistInput                                          )                 {
  const raw = netlistInput                           ;
  if (!Array.isArray(raw.inputs) || raw.inputs.length === 0) {
    throw new RangeError("netlist inputs must be non-empty");
  }
  if (!Array.isArray(raw.gates)) {
    throw new RangeError("netlist gates must be an array");
  }
  if (!Array.isArray(raw.outputs) || raw.outputs.length === 0) {
    throw new RangeError("netlist must expose at least one output");
  }
  const inputs = raw.inputs.map(String);
  if (new Set(inputs).size !== inputs.length) {
    throw new RangeError("netlist inputs must be unique");
  }
  const gates = raw.gates.map((gate) => normalizeGate(gate                                         ));
  if (new Set(gates.map((gate) => gate.gateId)).size !== gates.length) {
    throw new RangeError("gate ids must be unique");
  }
  const known = new Set(inputs);
  for (const gate of gates) {
    for (const wire of gate.inputs) {
      if (!known.has(wire)) {
        throw new RangeError(`unknown gate input wire: ${wire}`);
      }
    }
    known.add(gate.gateId);
  }
  const outputs = raw.outputs.map(String);
  for (const output of outputs) {
    if (!known.has(output)) {
      throw new RangeError(`unknown output wire: ${output}`);
    }
  }
  return { inputs, gates, outputs };
}

export function normalizeTruthRow(rowInput                                    )           {
  const raw = rowInput                           ;
  if (!Array.isArray(raw.assignment) || !Array.isArray(raw.outputs)) {
    throw new RangeError("truth rows need assignment and outputs arrays");
  }
  return {
    assignment: raw.assignment.map(bit),
    outputs: raw.outputs.map(bit),
  };
}

export function normalizeCircuitProblem(problemInput                                                )                       {
  const raw = problemInput                           ;
  const template = normalizeNetlist((raw.templateNetlist ?? raw.template_netlist)                                            );
  const targetTableInput = raw.targetTable ?? raw.target_table;
  const mutableGateId = raw.mutableGateId ?? raw.mutable_gate_id;
  if (!Array.isArray(targetTableInput)) {
    throw new RangeError("targetTable must be an array");
  }
  if (typeof mutableGateId !== "string" || !template.gates.some((gate) => gate.gateId === mutableGateId)) {
    throw new RangeError("mutableGateId must identify a template gate");
  }
  const targetTable = targetTableInput.map((row) => normalizeTruthRow(row                                      ));
  const expectedAssignments = assignments(template.inputs.length);
  if (targetTable.length !== expectedAssignments.length || !targetTable.every((row, idx) => bitsEqual(row.assignment, expectedAssignments[idx]))) {
    throw new RangeError("targetTable must contain complete assignments in canonical order");
  }
  if (!targetTable.every((row) => row.outputs.length === template.outputs.length)) {
    throw new RangeError("target row output arity must match netlist outputs");
  }
  const allowedOpsInput = raw.allowedOps ?? raw.allowed_ops ?? Array.from({ length: 16 }, (_unused, idx) => idx);
  if (!Array.isArray(allowedOpsInput)) {
    throw new RangeError("allowedOps must be an array");
  }
  const allowedOps = allowedOpsInput.map((op) => normalizeOpMask(Number(op)));
  if (new Set(allowedOps).size !== allowedOps.length || allowedOps.length === 0) {
    throw new RangeError("allowedOps must contain unique op masks");
  }
  return { templateNetlist: template, targetTable, mutableGateId, allowedOps };
}

export function normalizeCircuitState(stateInput                    )                     {
  return {
    problem: normalizeCircuitProblem(stateInput.problem),
    solved: Boolean(stateInput.solved),
    netlist: stateInput.netlist ? normalizeNetlist(stateInput.netlist) : null,
  };
}

export function evaluateNetlist(netlistInput                , assignmentInput                 )              {
  const netlist = normalizeNetlist(netlistInput);
  const values = assignmentInput.map(bit);
  if (values.length !== netlist.inputs.length) {
    throw new RangeError("assignment length must match netlist input count");
  }
  const wires = new Map                ();
  netlist.inputs.forEach((name, idx) => wires.set(name, values[idx]));
  for (const gate of netlist.gates) {
    const left = wires.get(gate.inputs[0]);
    const right = wires.get(gate.inputs[1]);
    if (typeof left !== "number" || typeof right !== "number") {
      throw new RangeError(`missing wire while evaluating gate: ${gate.gateId}`);
    }
    wires.set(gate.gateId, evalOpMask(gate.opMask, left, right));
  }
  return netlist.outputs.map((output) => {
    const value = wires.get(output);
    if (typeof value !== "number") {
      throw new RangeError(`missing output wire: ${output}`);
    }
    return value;
  });
}

export function truthTable(netlistInput                )             {
  const netlist = normalizeNetlist(netlistInput);
  return assignments(netlist.inputs.length).map((assignment) => ({ assignment, outputs: evaluateNetlist(netlist, assignment) }));
}

export function replaceGateOp(netlistInput                , gateId        , opMaskInput        )                 {
  const netlist = normalizeNetlist(netlistInput);
  const opMask = normalizeOpMask(opMaskInput);
  let changed = false;
  const gates = netlist.gates.map((gate) => {
    if (gate.gateId !== gateId) {
      return gate;
    }
    changed = true;
    return { ...gate, opMask };
  });
  if (!changed) {
    throw new RangeError(`unknown gate: ${gateId}`);
  }
  return { ...netlist, gates };
}

export function diagnoseMutableGate(problemInput                      , netlistInput                )                                                            {
  const problem = normalizeCircuitProblem(problemInput);
  const matches           = [];
  for (const opMask of problem.allowedOps) {
    const repaired = replaceGateOp(netlistInput, problem.mutableGateId, opMask);
    if (problem.targetTable.every((row) => bitsEqual(evaluateNetlist(repaired, row.assignment), row.outputs))) {
      matches.push(opMask);
    }
  }
  if (matches.length !== 1) {
    return null;
  }
  const opMask = matches[0];
  return { gateId: problem.mutableGateId, opMask, opName: OP_NAMES[opMask] };
}

export async function makeCircuitCandidate(
  problemInput                      ,
  opMaskInput        ,
  context = "circuit",
  cost = 1,
)                                                   {
  const problem = normalizeCircuitProblem(problemInput);
  const opMask = normalizeOpMask(opMaskInput);
  const netlist = replaceGateOp(problem.templateNetlist, problem.mutableGateId, opMask);
  return makeCandidate(
    {
      context,
      problem,
      netlist,
      mutableGateId: problem.mutableGateId,
      opMask,
      opName: OP_NAMES[opMask],
      cost,
    },
    "circuit.boolean_netlist",
    "circuit.boolean_netlist.v1",
    {
      problem: await stableHash(problem),
      netlist: await stableHash(netlist),
      op: await stableHash({ gateId: problem.mutableGateId, opMask }),
    },
  );
}

export function makeCircuitRepairProblem(targetOpMaskInput = 6)                       {
  const targetOpMask = normalizeOpMask(targetOpMaskInput);
  const template                 = {
    inputs: ["x0", "x1", "x2"],
    gates: [
      { gateId: "g0", opMask: 6, inputs: ["x0", "x1"] },
      { gateId: "g1", opMask: 0, inputs: ["g0", "x2"] },
    ],
    outputs: ["g1"],
  };
  const target = replaceGateOp(template, "g1", targetOpMask);
  return {
    templateNetlist: template,
    targetTable: truthTable(target),
    mutableGateId: "g1",
    allowedOps: Array.from({ length: 16 }, (_unused, idx) => idx),
  };
}

export async function runStaticCircuitEpisode(
  problemInput                      ,
  opOrder          ,
  ledger        ,
  episode        ,
)                                {
  const problem = normalizeCircuitProblem(problemInput);
  const engine = new TransactionEngine(new BooleanCircuitAdapter(), ledger);
  const state                     = { problem, solved: false, netlist: null };
  for (let idx = 0; idx < opOrder.length; idx += 1) {
    const opMask = normalizeOpMask(opOrder[idx]);
    const candidate = await makeCircuitCandidate(problem, opMask, "circuit-static", idx + 1);
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `circuit-static-${episode}-${idx + 1}`,
        actions: [{ gateId: problem.mutableGateId, opMask }],
        seeds: [episode, idx + 1],
        modelVersion: "circuit.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return episodeResult(idx + 1, true, engine, state);
    }
  }
  return episodeResult(opOrder.length, false, engine, state);
}

export async function runRepairCircuitEpisode(
  problemInput                      ,
  ledger        ,
  repairer                         ,
  episode        ,
  initialOpMask = 0,
)                                {
  const problem = normalizeCircuitProblem(problemInput);
  const engine = new TransactionEngine(new BooleanCircuitAdapter(), ledger);
  const state                     = { problem, solved: false, netlist: null };
  let candidate = await makeCircuitCandidate(problem, initialOpMask, "circuit-repair", 1);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `circuit-repair-${episode}-${attempt}`,
        actions: [{ gateId: problem.mutableGateId, opMask: candidate.payload.opMask }],
        seeds: [episode, attempt],
        modelVersion: "circuit.residual_repair.v1",
      }),
      candidate,
    );
    repairer.update(outcome.receipt);
    if (outcome.committed) {
      return episodeResult(attempt + 1, true, engine, state);
    }
    const repaired = await repairer.propose(candidate, outcome.receipt.hardResult.residual);
    if (!repaired) {
      return episodeResult(attempt + 1, false, engine, state);
    }
    candidate = repaired;
  }
  return episodeResult(3, false, engine, state);
}

export async function runCircuitRepairBenchmark(seed = 47, episodes = 45)                               {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  const opMasks = shuffledOps(seed);
  const staticResults                         = [];
  const repairResults                         = [];
  const staticLedgers           = [];
  const repairLedgers           = [];
  const repairer = new CircuitResidualRepairer();
  const staticOrder = Array.from({ length: 16 }, (_unused, idx) => idx);
  for (let episode = 0; episode < episodes; episode += 1) {
    const problem = makeCircuitRepairProblem(opMasks[episode % opMasks.length]);
    const staticLedger = new Ledger();
    const repairLedger = new Ledger();
    staticLedgers.push(staticLedger);
    repairLedgers.push(repairLedger);
    staticResults.push(await runStaticCircuitEpisode(problem, staticOrder, staticLedger, episode));
    repairResults.push(await runRepairCircuitEpisode(problem, repairLedger, repairer, episode));
  }
  const allResults = [...staticResults, ...repairResults];
  const staticCps = callsPerSuccess(staticResults);
  const repairCps = callsPerSuccess(repairResults);
  return {
    episodes,
    opCount: 16,
    staticCallsPerSuccess: staticCps,
    repairCallsPerSuccess: repairCps,
    repairGain: staticCps / repairCps,
    repairSuccessRate: repairResults.filter((row) => row.success).length / repairResults.length,
    ledgerAuditRate: allResults.filter((row) => row.auditOk).length / allResults.length,
    replayRollbackRate: allResults.filter((row) => row.replayRollbackOk).length / allResults.length,
    invalidCommitCount: invalidCommits([...staticLedgers, ...repairLedgers]),
    learnedResidualKinds: Object.fromEntries(repairer.rejectedResiduals),
  };
}

function candidateShapeError(problem                      , netlist                )                {
  const template = problem.templateNetlist;
  if (!bitsEqualStrings(netlist.inputs, template.inputs) || !bitsEqualStrings(netlist.outputs, template.outputs) || netlist.gates.length !== template.gates.length) {
    return "candidate netlist shape must match template";
  }
  for (let idx = 0; idx < template.gates.length; idx += 1) {
    const left = template.gates[idx];
    const right = netlist.gates[idx];
    if (left.gateId !== right.gateId || !bitsEqualStrings(left.inputs, right.inputs)) {
      return "candidate gate ids and inputs must match template";
    }
    if (left.gateId !== problem.mutableGateId && left.opMask !== right.opMask) {
      return "only the mutable gate op may change";
    }
  }
  return null;
}

async function episodeResult(
  calls        ,
  success         ,
  engine                                                                ,
  seedState                    ,
)                                {
  const auditOk = await engine.ledger.audit();
  let replayRollbackOk = false;
  if (auditOk) {
    try {
      await engine.replayAudit(seedState);
      replayRollbackOk = circuitStatesEqual(await engine.rollbackAudit(seedState), seedState);
    } catch (_error) {
      replayRollbackOk = false;
    }
  }
  return { calls, success, auditOk, replayRollbackOk };
}

function normalizeOpMask(value        )         {
  if (!Number.isInteger(value) || value < 0 || value > 15) {
    throw new RangeError("opMask must be in [0, 15]");
  }
  return value;
}

function assignments(width        )                    {
  return Array.from({ length: 2 ** width }, (_unused, mask) =>
    Array.from({ length: width }, (_bitUnused, bitIdx) => (mask >> bitIdx) & 1)
  );
}

function bit(value         )         {
  if (value === 0 || value === false) return 0;
  if (value === 1 || value === true) return 1;
  throw new RangeError(`Boolean value must be 0/1: ${String(value)}`);
}

function bitsEqual(a          , b          )          {
  return a.length === b.length && a.every((value, idx) => value === b[idx]);
}

function bitsEqualStrings(a                   , b                   )          {
  return a.length === b.length && a.every((value, idx) => value === b[idx]);
}

function circuitProblemsEqual(a                      , b                      )          {
  return JSON.stringify(normalizeCircuitProblem(a)) === JSON.stringify(normalizeCircuitProblem(b));
}

function circuitStatesEqual(a                    , b                    )          {
  return JSON.stringify(normalizeCircuitState(a)) === JSON.stringify(normalizeCircuitState(b));
}

function isCircuitResidual(value         )                           {
  if (!value || typeof value !== "object") {
    return false;
  }
  const residual = value                            ;
  return residual.kind === "schema_error" || residual.kind === "truth_table_mismatch";
}

function callsPerSuccess(results                        )         {
  const successes = results.filter((row) => row.success).length;
  const calls = results.reduce((sum, row) => sum + row.calls, 0);
  return successes === 0 ? Number.POSITIVE_INFINITY : calls / successes;
}

function invalidCommits(ledgers          )         {
  return ledgers.reduce((sum, ledger) =>
    sum + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  0);
}

function shuffledOps(seed        )           {
  const rng = mulberry32(seed);
  const out = Array.from({ length: 15 }, (_unused, idx) => idx + 1);
  for (let idx = out.length - 1; idx > 0; idx -= 1) {
    const swap = Math.floor(rng() * (idx + 1));
    [out[idx], out[swap]] = [out[swap], out[idx]];
  }
  return out;
}

function mulberry32(seed        )               {
  let t = seed >>> 0;
  return () => {
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}
