import {
                          
               
                             
                      
  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { stableHash } from "./canonical.js";

                                                                                          

export const DEFAULT_CODE_OPERATORS                 = ["left", "+", "-", "*", "max", "min", "right", "absdiff"];
export const INITIAL_CODE_OPERATOR               = "left";
export const BASE_SOURCE = "def combine(x, y):\n    return __op0__(x, y)\n";
export const DEFAULT_TEST_INPUTS                                = [
  { x: 0, y: 0 },
  { x: 1, y: 2 },
  { x: 3, y: 1 },
  { x: -2, y: 5 },
  { x: 4, y: -3 },
  { x: -4, y: -2 },
];

                               
                                 
                   
 

                                   
                   
                       
                     
                     
                        
                        
                  
                   
                                   
 

                            
                 
                         
                   
 

                                  
                            
                  
                                 
                              
 

                                   
                  
                            
                   
                      
               
 

                               
                                        
                   
                     
                                  
                    
                  
            
                   
                           
                     
                        
                         
           
 

                                          
                
                   
                   
                            
 

                                   
                   
                             
                                
                                
                     
                            
                          
                             
                             
                                               
 

export class CodePatchAdapter                                                                     {
  verifierId = "bounded_unit_test_expression_verifier";
  verifierVersion = "1.0";

  async verify(candidate                                  )                              {
    const problem = normalizeCodeProblem(candidate.payload.problem);
    const patch = normalizeCodePatch(candidate.payload.patch);
    const sourceAfter = String(candidate.payload.sourceAfter ?? (candidate.payload                                      ).source_after ?? "");
    const metadata = {
      cost: candidate.payload.cost,
      testCount: problem.tests.length,
      operator: patch.operator,
      sourceHash: problem.sourceHash,
    };
    const shapeError = await candidateShapeError(problem, patch, sourceAfter);
    if (shapeError) {
      return this.reject("schema_error", { message: shapeError }, metadata);
    }
    for (let idx = 0; idx < problem.tests.length; idx += 1) {
      const testCase = problem.tests[idx];
      const actual = evaluatePatch(problem, patch.operator, testCase);
      if (actual !== testCase.expected) {
        return this.reject(
          "test_failure",
          {
            testIndex: idx,
            inputs: testCase.inputs,
            expected: testCase.expected,
            actual,
            repair: diagnoseOperatorRepair(problem),
          },
          metadata,
        );
      }
    }
    return hardAccept(this.verifierId, this.verifierVersion, {
      ...metadata,
      testsPassed: problem.tests.length,
      patchHash: await stableHash({ nodeId: patch.nodeId, operator: patch.operator, baseHash: patch.baseHash }),
    });
  }

  applyCommit(state                 , candidate                                  )                  {
    const current = normalizeCodeState(state);
    const problem = normalizeCodeProblem(candidate.payload.problem);
    if (!codeProblemsEqual(current.problem, problem)) {
      throw new Error("candidate problem does not match current code repair state");
    }
    const patch = normalizeCodePatch(candidate.payload.patch);
    return { problem, solved: true, operator: patch.operator, sourceAfter: renderSource(problem, patch.operator) };
  }

  replay(state                 , receipt         )                  {
    const current = normalizeCodeState(state);
    const payload = (receipt.replayBundle                                          ).candidatePayload;
    const problem = normalizeCodeProblem(payload.problem);
    if (!codeProblemsEqual(current.problem, problem)) {
      throw new Error("receipt problem does not match replay code repair state");
    }
    const patch = normalizeCodePatch(payload.patch);
    return { problem, solved: true, operator: patch.operator, sourceAfter: renderSource(problem, patch.operator) };
  }

  rollback(_state                 , receipt         )                  {
    return normalizeCodeState((receipt.rollbackBundle                                 ).preState);
  }

          reject(kind                      , residual                            , metadata                         )                     {
    return hardReject(this.verifierId, this.verifierVersion, { kind, ...residual }, metadata);
  }
}

export class CodeResidualRepairer {
  rejectedResiduals = new Map                ();
  acceptedOperators = new Map                ();

  update(receipt         )       {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle                           
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload                             
      : {};
    if (receipt.hardResult.result === "accept") {
      const operator = payload.patch?.operator ?? "unknown";
      this.acceptedOperators.set(operator, (this.acceptedOperators.get(operator) ?? 0) + 1);
      return;
    }
    if (receipt.hardResult.result === "reject" && isCodeResidual(receipt.hardResult.residual)) {
      const kind = receipt.hardResult.residual.kind;
      this.rejectedResiduals.set(kind, (this.rejectedResiduals.get(kind) ?? 0) + 1);
    }
  }

  async propose(candidate                                  , residual         )                                                   {
    if (!isCodeResidual(residual) || !residual.repair) {
      return null;
    }
    const patch = normalizeCodePatch(candidate.payload.patch);
    if (residual.repair.operator === patch.operator) {
      return null;
    }
    return makeCodePatchCandidate(
      normalizeCodeProblem(candidate.payload.problem),
      residual.repair.operator,
      candidate.payload.context || "code-repair",
      candidate.payload.cost + 1,
    );
  }
}

export function normalizeCodeTestCase(testInput                                        )               {
  const raw = testInput                           ;
  const expected = intValue(raw.expected, "expected test output");
  const inputs = normalizeInputs(raw.inputs);
  return { inputs, expected };
}

export function normalizeCodeProblem(problemInput                                            )                   {
  const raw = problemInput                           ;
  const filePath = raw.filePath ?? raw.file_path;
  const functionName = raw.functionName ?? raw.function_name;
  const baseSource = raw.baseSource ?? raw.base_source;
  const sourceHash = raw.sourceHash ?? raw.source_hash;
  const testsInput = raw.tests;
  const mutableNodeId = raw.mutableNodeId ?? raw.mutable_node_id ?? "op0";
  const leftVar = raw.leftVar ?? raw.left_var ?? "x";
  const rightVar = raw.rightVar ?? raw.right_var ?? "y";
  const allowedInput = raw.allowedOperators ?? raw.allowed_operators ?? DEFAULT_CODE_OPERATORS;
  if (typeof filePath !== "string" || filePath.length === 0 || filePath.includes("\n")) {
    throw new RangeError("filePath must be a non-empty single-line path");
  }
  if (typeof functionName !== "string" || !isIdentifier(functionName)) {
    throw new RangeError("functionName must be an identifier");
  }
  if (typeof baseSource !== "string" || baseSource.length === 0) {
    throw new RangeError("baseSource must be non-empty");
  }
  if (typeof sourceHash !== "string" || sourceHash.length === 0) {
    throw new RangeError("sourceHash must be non-empty");
  }
  if (typeof mutableNodeId !== "string" || mutableNodeId.length === 0) {
    throw new RangeError("mutableNodeId must be non-empty");
  }
  if (typeof leftVar !== "string" || typeof rightVar !== "string" || leftVar === rightVar || !isIdentifier(leftVar) || !isIdentifier(rightVar)) {
    throw new RangeError("leftVar and rightVar must be distinct identifiers");
  }
  if (!Array.isArray(testsInput) || testsInput.length === 0) {
    throw new RangeError("tests must be a non-empty array");
  }
  const tests = testsInput.map((testCase) => normalizeCodeTestCase(testCase                                          ));
  if (!Array.isArray(allowedInput) || allowedInput.length === 0) {
    throw new RangeError("allowedOperators must be a non-empty array");
  }
  const allowedOperators = allowedInput.map((operator) => normalizeCodeOperator(operator));
  if (new Set(allowedOperators).size !== allowedOperators.length) {
    throw new RangeError("allowedOperators must be unique");
  }
  for (const testCase of tests) {
    if (!(leftVar in testCase.inputs) || !(rightVar in testCase.inputs)) {
      throw new RangeError("each test must provide both expression variables");
    }
  }
  return {
    filePath,
    functionName,
    baseSource,
    sourceHash,
    tests,
    mutableNodeId,
    leftVar,
    rightVar,
    allowedOperators,
  };
}

export function normalizeCodePatch(patchInput                                     )            {
  const raw = patchInput                           ;
  const nodeId = raw.nodeId ?? raw.node_id;
  const baseHash = raw.baseHash ?? raw.base_hash;
  if (typeof nodeId !== "string" || nodeId.length === 0) {
    throw new RangeError("nodeId must be non-empty");
  }
  if (typeof baseHash !== "string" || baseHash.length === 0) {
    throw new RangeError("baseHash must be non-empty");
  }
  return { nodeId, operator: normalizeCodeOperator(raw.operator), baseHash };
}

export function normalizeCodeState(stateInput                                           )                  {
  const raw = stateInput                           ;
  const operator = raw.operator == null ? null : normalizeCodeOperator(raw.operator);
  return {
    problem: normalizeCodeProblem(raw.problem                                              ),
    solved: Boolean(raw.solved),
    operator,
    sourceAfter: raw.sourceAfter == null && raw.source_after == null ? null : String(raw.sourceAfter ?? raw.source_after),
  };
}

export function evaluateOperator(operator                       , left        , right        )         {
  const op = normalizeCodeOperator(operator);
  if (op === "left") return left;
  if (op === "right") return right;
  if (op === "+") return left + right;
  if (op === "-") return left - right;
  if (op === "*") return left * right;
  if (op === "max") return Math.max(left, right);
  if (op === "min") return Math.min(left, right);
  if (op === "absdiff") return Math.abs(left - right);
  throw new RangeError(`unsupported operator: ${String(operator)}`);
}

export function evaluatePatch(problemInput                  , operator                       , testInput                                        )         {
  const problem = normalizeCodeProblem(problemInput);
  const testCase = normalizeCodeTestCase(testInput);
  return evaluateOperator(operator, testCase.inputs[problem.leftVar], testCase.inputs[problem.rightVar]);
}

export function renderSource(problemInput                  , operatorInput                       )         {
  const problem = normalizeCodeProblem(problemInput);
  const operator = normalizeCodeOperator(operatorInput);
  const left = problem.leftVar;
  const right = problem.rightVar;
  const expressions                               = {
    left,
    right,
    "+": `${left} + ${right}`,
    "-": `${left} - ${right}`,
    "*": `${left} * ${right}`,
    max: `max(${left}, ${right})`,
    min: `min(${left}, ${right})`,
    absdiff: `abs(${left} - ${right})`,
  };
  return `def ${problem.functionName}(${left}, ${right}):\n    return ${expressions[operator]}\n`;
}

export function diagnoseOperatorRepair(problemInput                  )                         {
  const problem = normalizeCodeProblem(problemInput);
  const matches                 = [];
  for (const operator of problem.allowedOperators) {
    if (problem.tests.every((testCase) => evaluatePatch(problem, operator, testCase) === testCase.expected)) {
      matches.push(operator);
    }
  }
  if (matches.length !== 1) {
    return null;
  }
  const operator = matches[0];
  return {
    nodeId: problem.mutableNodeId,
    operator,
    baseHash: problem.sourceHash,
    sourceAfter: renderSource(problem, operator),
    passingTests: problem.tests.length,
  };
}

export async function makeCodePatchCandidate(
  problemInput                  ,
  operatorInput                       ,
  context = "code-repair",
  cost = 1,
)                                            {
  const problem = normalizeCodeProblem(problemInput);
  const operator = normalizeCodeOperator(operatorInput);
  const patch            = { nodeId: problem.mutableNodeId, operator, baseHash: problem.sourceHash };
  const sourceAfter = renderSource(problem, operator);
  return makeCandidate(
    {
      context,
      problem,
      patch,
      sourceAfter,
      cost,
    },
    "code.bounded_expression_patch",
    "code.bounded_expression_patch.v1",
    {
      problem: await stableHash(problem),
      patch: await stableHash(patch),
      sourceAfter: await stableHash(sourceAfter),
    },
  );
}

export async function makeCodeRepairProblem(targetOperatorInput                        = "+")                            {
  const targetOperator = normalizeCodeOperator(targetOperatorInput);
  const sourceHash = await stableHash(BASE_SOURCE);
  const tests = DEFAULT_TEST_INPUTS.map((inputs) => ({
    inputs: normalizeInputs(inputs),
    expected: evaluateOperator(targetOperator, inputs.x, inputs.y),
  }));
  const problem                   = {
    filePath: "math_ops.py",
    functionName: "combine",
    baseSource: BASE_SOURCE,
    sourceHash,
    tests,
    mutableNodeId: "op0",
    leftVar: "x",
    rightVar: "y",
    allowedOperators: [...DEFAULT_CODE_OPERATORS],
  };
  const repair = diagnoseOperatorRepair(problem);
  if (!repair || repair.operator !== targetOperator) {
    throw new Error("test suite does not uniquely identify target operator");
  }
  return problem;
}

export async function runStaticCodeRepairEpisode(
  problemInput                  ,
  operatorOrder                              ,
  ledger        ,
  episode        ,
)                                   {
  const problem = normalizeCodeProblem(problemInput);
  const engine = new TransactionEngine(new CodePatchAdapter(), ledger);
  const state                  = { problem, solved: false, operator: null, sourceAfter: null };
  for (let idx = 0; idx < operatorOrder.length; idx += 1) {
    const operator = normalizeCodeOperator(operatorOrder[idx]);
    const candidate = await makeCodePatchCandidate(problem, operator, "code-static", idx + 1);
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `code-static-${episode}-${idx + 1}`,
        actions: [{ nodeId: problem.mutableNodeId, operator }],
        seeds: [episode, idx + 1],
        modelVersion: "code.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return episodeResult(idx + 1, true, engine, state);
    }
  }
  return episodeResult(operatorOrder.length, false, engine, state);
}

export async function runRepairCodeEpisode(
  problemInput                  ,
  ledger        ,
  repairer                      ,
  episode        ,
  initialOperator                        = INITIAL_CODE_OPERATOR,
)                                   {
  const problem = normalizeCodeProblem(problemInput);
  const engine = new TransactionEngine(new CodePatchAdapter(), ledger);
  const state                  = { problem, solved: false, operator: null, sourceAfter: null };
  let candidate = await makeCodePatchCandidate(problem, initialOperator, "code-repair", 1);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `code-repair-${episode}-${attempt}`,
        actions: [{ nodeId: problem.mutableNodeId, operator: candidate.payload.patch.operator }],
        seeds: [episode, attempt],
        modelVersion: "code.residual_repair.v1",
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

export async function runCodeRepairBenchmark(seed = 59, episodes = 42)                            {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  const targets = shuffle(DEFAULT_CODE_OPERATORS.filter((operator) => operator !== INITIAL_CODE_OPERATOR), seed);
  const staticResults                            = [];
  const repairResults                            = [];
  const staticLedgers           = [];
  const repairLedgers           = [];
  const repairer = new CodeResidualRepairer();
  for (let episode = 0; episode < episodes; episode += 1) {
    const target = targets[episode % targets.length];
    const problem = await makeCodeRepairProblem(target);
    const staticLedger = new Ledger();
    const repairLedger = new Ledger();
    staticLedgers.push(staticLedger);
    repairLedgers.push(repairLedger);
    staticResults.push(await runStaticCodeRepairEpisode(problem, DEFAULT_CODE_OPERATORS, staticLedger, episode));
    repairResults.push(await runRepairCodeEpisode(problem, repairLedger, repairer, episode));
  }
  const allResults = [...staticResults, ...repairResults];
  const staticCps = callsPerSuccess(staticResults);
  const repairCps = callsPerSuccess(repairResults);
  return {
    episodes,
    candidateSpaceSize: DEFAULT_CODE_OPERATORS.length,
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

async function candidateShapeError(problem                  , patch           , sourceAfter        )                         {
  if (problem.sourceHash !== await stableHash(problem.baseSource)) {
    return "problem sourceHash does not match baseSource";
  }
  if (patch.nodeId !== problem.mutableNodeId) {
    return "patch nodeId does not match mutable node";
  }
  if (patch.baseHash !== problem.sourceHash) {
    return "patch baseHash does not match problem sourceHash";
  }
  if (!problem.allowedOperators.includes(patch.operator)) {
    return "patch operator is not allowed by the problem grammar";
  }
  if (sourceAfter !== renderSource(problem, patch.operator)) {
    return "sourceAfter must be the canonical rendered patch";
  }
  return null;
}

async function episodeResult(
  calls        ,
  success         ,
  engine                                                      ,
  seedState                 ,
)                                   {
  const auditOk = await engine.ledger.audit();
  let replayRollbackOk = false;
  if (auditOk) {
    try {
      await engine.replayAudit(seedState);
      replayRollbackOk = codeStatesEqual(await engine.rollbackAudit(seedState), seedState);
    } catch (_error) {
      replayRollbackOk = false;
    }
  }
  return { calls, success, auditOk, replayRollbackOk };
}

function normalizeCodeOperator(value         )               {
  if (typeof value !== "string" || !DEFAULT_CODE_OPERATORS.includes(value                )) {
    throw new RangeError(`unsupported operator: ${String(value)}`);
  }
  return value                ;
}

function normalizeInputs(inputsInput         )                         {
  if (!inputsInput || typeof inputsInput !== "object") {
    throw new RangeError("test inputs must be an object or entries array");
  }
  let entries                          ;
  if (Array.isArray(inputsInput)) {
    entries = inputsInput.map((entry) => {
      if (!Array.isArray(entry) || entry.length !== 2) {
        throw new RangeError("test input entries must be [name, value] pairs");
      }
      return [String(entry[0]), entry[1]];
    });
  } else {
    entries = Object.entries(inputsInput                           );
  }
  const out                         = {};
  for (const [name, value] of entries.sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) {
    if (Object.prototype.hasOwnProperty.call(out, name)) {
      throw new RangeError("test input names must be unique");
    }
    out[name] = intValue(value, "test input");
  }
  return out;
}

function intValue(value         , label        )         {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    throw new RangeError(`${label} must be an integer`);
  }
  return value;
}

function isIdentifier(value        )          {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(value);
}

function isCodeResidual(value         )                        {
  if (!value || typeof value !== "object") {
    return false;
  }
  const residual = value                         ;
  return residual.kind === "schema_error" || residual.kind === "test_failure";
}

function codeProblemsEqual(a                  , b                  )          {
  return JSON.stringify(normalizeCodeProblem(a)) === JSON.stringify(normalizeCodeProblem(b));
}

function codeStatesEqual(a                 , b                 )          {
  return JSON.stringify(normalizeCodeState(a)) === JSON.stringify(normalizeCodeState(b));
}

function callsPerSuccess(results                           )         {
  const successes = results.filter((row) => row.success).length;
  const calls = results.reduce((sum, row) => sum + row.calls, 0);
  return successes === 0 ? Number.POSITIVE_INFINITY : calls / successes;
}

function invalidCommits(ledgers          )         {
  return ledgers.reduce((sum, ledger) =>
    sum + ledger.rows.filter((row) => row.committed && row.hardResult.result !== "accept").length,
  0);
}

function shuffle   (values     , seed        )      {
  const rng = mulberry32(seed);
  const out = [...values];
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
