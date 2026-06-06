import {




  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { stableHash } from "./canonical.js";

export const NORMAL_VALENCE                         = { C: 4, N: 3, O: 2, F: 1, Cl: 1 };
export const DEFAULT_ELEMENTS = ["C", "N", "O", "F", "Cl"]         ;
export const DEFAULT_BOND_ORDERS = [1, 2, 3]         ;








































































export class MoleculeGraphAdapter                                                                                 {
  verifierId = "organic_subset_valence_formula_verifier";
  verifierVersion = "1.0";

  verify(candidate                                          )                     {
    const problem = normalizeMoleculeProblem(candidate.payload.problem);
    const graph = normalizeMoleculeGraph(candidate.payload.graph);
    const metadata = { cost: candidate.payload.cost, atomCount: graph.atoms.length, bondCount: graph.bonds.length };
    const shapeError = candidateShapeError(problem, graph);
    if (shapeError) {
      return this.reject("schema_error", { message: shapeError }, metadata);
    }
    const violations = valenceViolations(graph);
    if (violations.length > 0) {
      return this.reject("valence_exceeded", { violations, repair: diagnoseMoleculeEdit(problem, graph) }, metadata);
    }
    const formula = molecularFormula(graph);
    const target = normalizeFormula(problem.targetFormula);
    if (!formulasEqual(formula, target)) {
      return this.reject(
        "formula_mismatch",
        { expected: target, actual: formula, repair: diagnoseMoleculeEdit(problem, graph) },
        metadata,
      );
    }
    return hardAccept(this.verifierId, this.verifierVersion, { ...metadata, formula });
  }

  applyCommit(state                     , candidate                                          )                      {
    const current = normalizeMoleculeState(state);
    const problem = normalizeMoleculeProblem(candidate.payload.problem);
    if (!moleculeProblemsEqual(current.problem, problem)) {
      throw new Error("candidate problem does not match current molecule state");
    }
    return { problem, solved: true, graph: normalizeMoleculeGraph(candidate.payload.graph) };
  }

  replay(state                     , receipt         )                      {
    const current = normalizeMoleculeState(state);
    const payload = (receipt.replayBundle                                                  ).candidatePayload;
    const problem = normalizeMoleculeProblem(payload.problem);
    if (!moleculeProblemsEqual(current.problem, problem)) {
      throw new Error("receipt problem does not match replay molecule state");
    }
    return { problem, solved: true, graph: normalizeMoleculeGraph(payload.graph) };
  }

  rollback(_state                     , receipt         )                      {
    return normalizeMoleculeState((receipt.rollbackBundle                                     ).preState);
  }

          reject(kind                          , residual                                , metadata                         )                     {
    return hardReject(this.verifierId, this.verifierVersion, { kind, ...residual }, metadata);
  }
}

export class MoleculeResidualRepairer {
  rejectedResiduals = new Map                ();
  acceptedEdits = new Map                ();

  update(receipt         )       {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload
      : {};
    if (receipt.hardResult.result === "accept") {
      const key = JSON.stringify({ element: payload.element, bondOrder: payload.bondOrder });
      this.acceptedEdits.set(key, (this.acceptedEdits.get(key) ?? 0) + 1);
      return;
    }
    if (receipt.hardResult.result === "reject" && isMoleculeResidual(receipt.hardResult.residual)) {
      const kind = receipt.hardResult.residual.kind;
      this.rejectedResiduals.set(kind, (this.rejectedResiduals.get(kind) ?? 0) + 1);
    }
  }

  async propose(candidate                                          , residual         )                                                           {
    if (!isMoleculeResidual(residual) || !residual.repair) {
      return null;
    }
    const { element, bondOrder } = residual.repair;
    if (element === candidate.payload.element && bondOrder === candidate.payload.bondOrder) {
      return null;
    }
    return makeMoleculeCandidate(
      normalizeMoleculeProblem(candidate.payload.problem),
      element,
      bondOrder,
      candidate.payload.context || "molecule-repair",
      candidate.payload.cost + 1,
    );
  }
}

export function normalizeMoleculeAtom(atomInput                                        )               {
  const raw = atomInput                           ;
  const atomId = raw.atomId ?? raw.atom_id;
  const element = raw.element;
  if (typeof atomId !== "string" || atomId.length === 0) {
    throw new RangeError("atomId must be non-empty");
  }
  if (typeof element !== "string" || !(element in NORMAL_VALENCE)) {
    throw new RangeError(`unsupported organic-subset element: ${String(element)}`);
  }
  return { atomId, element };
}

export function normalizeMoleculeBond(bondInput                                        )               {
  const raw = bondInput                           ;
  const bondId = raw.bondId ?? raw.bond_id;
  if (typeof bondId !== "string" || bondId.length === 0) {
    throw new RangeError("bondId must be non-empty");
  }
  if (!Array.isArray(raw.atoms) || raw.atoms.length !== 2 || String(raw.atoms[0]) === String(raw.atoms[1])) {
    throw new RangeError("bond must connect two distinct atom ids");
  }
  const order = normalizeBondOrder(Number(raw.order));
  return { bondId, atoms: [String(raw.atoms[0]), String(raw.atoms[1])], order };
}

export function normalizeMoleculeGraph(graphInput                                         )                {
  const raw = graphInput                           ;
  if (!Array.isArray(raw.atoms) || !Array.isArray(raw.bonds)) {
    throw new RangeError("molecule graph requires atoms and bonds arrays");
  }
  const atoms = raw.atoms.map((atom) => normalizeMoleculeAtom(atom                                          ));
  const atomIds = atoms.map((atom) => atom.atomId);
  if (new Set(atomIds).size !== atomIds.length) {
    throw new RangeError("atom ids must be unique");
  }
  const known = new Set(atomIds);
  const bonds = raw.bonds.map((bond) => normalizeMoleculeBond(bond                                          ));
  const bondIds = bonds.map((bond) => bond.bondId);
  if (new Set(bondIds).size !== bondIds.length) {
    throw new RangeError("bond ids must be unique");
  }
  const pairs = new Set        ();
  for (const bond of bonds) {
    if (!known.has(bond.atoms[0]) || !known.has(bond.atoms[1])) {
      throw new RangeError("bond references unknown atom");
    }
    const key = [...bond.atoms].sort().join(":");
    if (pairs.has(key)) {
      throw new RangeError("duplicate atom pair bonds are not supported in this G1 canary");
    }
    pairs.add(key);
  }
  return { atoms, bonds };
}

export function normalizeFormula(formulaInput                         )                         {
  const out                         = {};
  for (const [element, rawCount] of Object.entries(formulaInput)) {
    const count = Number(rawCount);
    if (!Number.isInteger(count) || count < 0) {
      throw new RangeError("formula counts must be non-negative integers");
    }
    if (count > 0) {
      out[element] = count;
    }
  }
  return Object.fromEntries(Object.entries(out).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0));
}

export function normalizeMoleculeProblem(problemInput                                                 )                        {
  const raw = problemInput                           ;
  const template = normalizeMoleculeGraph((raw.templateGraph ?? raw.template_graph)                                           );
  const targetFormula = normalizeFormula((raw.targetFormula ?? raw.target_formula)                           );
  const mutableAtomId = raw.mutableAtomId ?? raw.mutable_atom_id;
  const mutableBondId = raw.mutableBondId ?? raw.mutable_bond_id;
  if (typeof mutableAtomId !== "string" || !template.atoms.some((atom) => atom.atomId === mutableAtomId)) {
    throw new RangeError("mutableAtomId must identify a template atom");
  }
  if (typeof mutableBondId !== "string" || !template.bonds.some((bond) => bond.bondId === mutableBondId)) {
    throw new RangeError("mutableBondId must identify a template bond");
  }
  const allowedElementsInput = raw.allowedElements ?? raw.allowed_elements ?? [...DEFAULT_ELEMENTS];
  const allowedBondOrdersInput = raw.allowedBondOrders ?? raw.allowed_bond_orders ?? [...DEFAULT_BOND_ORDERS];
  if (!Array.isArray(allowedElementsInput) || !Array.isArray(allowedBondOrdersInput)) {
    throw new RangeError("allowed elements and bond orders must be arrays");
  }
  const allowedElements = allowedElementsInput.map(String);
  if (allowedElements.length === 0 || new Set(allowedElements).size !== allowedElements.length || allowedElements.some((element) => !(element in NORMAL_VALENCE))) {
    throw new RangeError("allowedElements must be unique supported elements");
  }
  const allowedBondOrders = allowedBondOrdersInput.map((order) => normalizeBondOrder(Number(order)));
  if (allowedBondOrders.length === 0 || new Set(allowedBondOrders).size !== allowedBondOrders.length) {
    throw new RangeError("allowedBondOrders must be unique");
  }
  return { templateGraph: template, targetFormula, mutableAtomId, mutableBondId, allowedElements, allowedBondOrders };
}

export function normalizeMoleculeState(stateInput                     )                      {
  return {
    problem: normalizeMoleculeProblem(stateInput.problem),
    solved: Boolean(stateInput.solved),
    graph: stateInput.graph ? normalizeMoleculeGraph(stateInput.graph) : null,
  };
}

export function explicitValences(graphInput               )                         {
  const graph = normalizeMoleculeGraph(graphInput);
  const valences                         = Object.fromEntries(graph.atoms.map((atom) => [atom.atomId, 0]));
  for (const bond of graph.bonds) {
    valences[bond.atoms[0]] += bond.order;
    valences[bond.atoms[1]] += bond.order;
  }
  return valences;
}

export function valenceViolations(graphInput               )                                                                            {
  const graph = normalizeMoleculeGraph(graphInput);
  const valences = explicitValences(graph);
  const violations                                                                            = [];
  for (const atom of graph.atoms) {
    const explicit = valences[atom.atomId];
    const max = NORMAL_VALENCE[atom.element];
    if (explicit > max) {
      violations.push({ atomId: atom.atomId, element: atom.element, explicit, max });
    }
  }
  return violations;
}

export function molecularFormula(graphInput               )                         {
  const graph = normalizeMoleculeGraph(graphInput);
  const violations = valenceViolations(graph);
  if (violations.length > 0) {
    throw new RangeError(`cannot compute formula for invalid valence graph: ${JSON.stringify(violations)}`);
  }
  const valences = explicitValences(graph);
  const formula                         = {};
  let hydrogens = 0;
  for (const atom of graph.atoms) {
    formula[atom.element] = (formula[atom.element] ?? 0) + 1;
    hydrogens += NORMAL_VALENCE[atom.element] - valences[atom.atomId];
  }
  if (hydrogens > 0) {
    formula.H = hydrogens;
  }
  return normalizeFormula(formula);
}

export function replaceMoleculeEdit(
  graphInput               ,
  atomId        ,
  element        ,
  bondId        ,
  bondOrderInput        ,
)                {
  const graph = normalizeMoleculeGraph(graphInput);
  if (!(element in NORMAL_VALENCE)) {
    throw new RangeError(`unsupported organic-subset element: ${element}`);
  }
  const bondOrder = normalizeBondOrder(bondOrderInput);
  let atomChanged = false;
  let bondChanged = false;
  const atoms = graph.atoms.map((atom) => {
    if (atom.atomId !== atomId) return atom;
    atomChanged = true;
    return { atomId: atom.atomId, element };
  });
  const bonds = graph.bonds.map((bond) => {
    if (bond.bondId !== bondId) return bond;
    bondChanged = true;
    return { ...bond, order: bondOrder };
  });
  if (!atomChanged || !bondChanged) {
    throw new RangeError("mutable atom or bond not found");
  }
  return normalizeMoleculeGraph({ atoms, bonds });
}

export function diagnoseMoleculeEdit(problemInput                       , graphInput               )                             {
  const problem = normalizeMoleculeProblem(problemInput);
  normalizeMoleculeGraph(graphInput);
  const matches                                                                                 = [];
  for (const element of problem.allowedElements) {
    for (const bondOrder of problem.allowedBondOrders) {
      const graph = replaceMoleculeEdit(problem.templateGraph, problem.mutableAtomId, element, problem.mutableBondId, bondOrder);
      if (valenceViolations(graph).length > 0) {
        continue;
      }
      const formula = molecularFormula(graph);
      if (formulasEqual(formula, problem.targetFormula)) {
        matches.push({ element, bondOrder, formula });
      }
    }
  }
  if (matches.length !== 1) {
    return null;
  }
  const match = matches[0];
  return {
    atomId: problem.mutableAtomId,
    bondId: problem.mutableBondId,
    element: match.element,
    bondOrder: match.bondOrder,
    formula: match.formula,
  };
}

export async function makeMoleculeCandidate(
  problemInput                       ,
  element        ,
  bondOrderInput        ,
  context = "molecule",
  cost = 1,
)                                                    {
  const problem = normalizeMoleculeProblem(problemInput);
  const bondOrder = normalizeBondOrder(bondOrderInput);
  const graph = replaceMoleculeEdit(problem.templateGraph, problem.mutableAtomId, element, problem.mutableBondId, bondOrder);
  return makeCandidate(
    {
      context,
      problem,
      graph,
      mutableAtomId: problem.mutableAtomId,
      mutableBondId: problem.mutableBondId,
      element,
      bondOrder,
      cost,
    },
    "molecule.organic_subset_graph",
    "molecule.organic_subset_graph.v1",
    {
      problem: await stableHash(problem),
      graph: await stableHash(graph),
      edit: await stableHash({ element, bondOrder }),
    },
  );
}

export function makeMoleculeRepairProblem(targetElement = "O", targetBondOrderInput = 1)                        {
  const targetBondOrder = normalizeBondOrder(targetBondOrderInput);
  const template                = {
    atoms: [
      { atomId: "a0", element: "C" },
      { atomId: "a1", element: "C" },
      { atomId: "a2", element: "C" },
    ],
    bonds: [
      { bondId: "b0", atoms: ["a0", "a1"], order: 1 },
      { bondId: "b1", atoms: ["a1", "a2"], order: 1 },
    ],
  };
  const target = replaceMoleculeEdit(template, "a2", targetElement, "b1", targetBondOrder);
  return {
    templateGraph: template,
    targetFormula: molecularFormula(target),
    mutableAtomId: "a2",
    mutableBondId: "b1",
    allowedElements: [...DEFAULT_ELEMENTS],
    allowedBondOrders: [...DEFAULT_BOND_ORDERS],
  };
}

export async function runStaticMoleculeEpisode(
  problemInput                       ,
  editOrder                         ,
  ledger        ,
  episode        ,
)                                 {
  const problem = normalizeMoleculeProblem(problemInput);
  const engine = new TransactionEngine(new MoleculeGraphAdapter(), ledger);
  const state                      = { problem, solved: false, graph: null };
  for (let idx = 0; idx < editOrder.length; idx += 1) {
    const [element, bondOrder] = editOrder[idx];
    const candidate = await makeMoleculeCandidate(problem, element, bondOrder, "molecule-static", idx + 1);
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `molecule-static-${episode}-${idx + 1}`,
        actions: [{ element, bondOrder }],
        seeds: [episode, idx + 1],
        modelVersion: "molecule.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return episodeResult(idx + 1, true, engine, state);
    }
  }
  return episodeResult(editOrder.length, false, engine, state);
}

export async function runRepairMoleculeEpisode(
  problemInput                       ,
  ledger        ,
  repairer                          ,
  episode        ,
  initialElement = "C",
  initialBondOrder = 3,
)                                 {
  const problem = normalizeMoleculeProblem(problemInput);
  const engine = new TransactionEngine(new MoleculeGraphAdapter(), ledger);
  const state                      = { problem, solved: false, graph: null };
  let candidate = await makeMoleculeCandidate(problem, initialElement, initialBondOrder, "molecule-repair", 1);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `molecule-repair-${episode}-${attempt}`,
        actions: [{ element: candidate.payload.element, bondOrder: candidate.payload.bondOrder }],
        seeds: [episode, attempt],
        modelVersion: "molecule.residual_repair.v1",
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

export async function runMoleculeRepairBenchmark(seed = 53, episodes = 42)                                {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  const editSpace                          = [];
  for (const element of DEFAULT_ELEMENTS) {
    for (const order of DEFAULT_BOND_ORDERS) {
      editSpace.push([element, order]);
    }
  }
  const targets = shuffle(editSpace.filter(([element, order]) => {
    if (element === "C" && order === 3) {
      return false;
    }
    try {
      makeMoleculeRepairProblem(element, order);
      return true;
    } catch (_error) {
      return false;
    }
  }), seed);
  const staticResults                          = [];
  const repairResults                          = [];
  const staticLedgers           = [];
  const repairLedgers           = [];
  const repairer = new MoleculeResidualRepairer();
  for (let episode = 0; episode < episodes; episode += 1) {
    const [element, bondOrder] = targets[episode % targets.length];
    const problem = makeMoleculeRepairProblem(element, bondOrder);
    const staticLedger = new Ledger();
    const repairLedger = new Ledger();
    staticLedgers.push(staticLedger);
    repairLedgers.push(repairLedger);
    staticResults.push(await runStaticMoleculeEpisode(problem, editSpace, staticLedger, episode));
    repairResults.push(await runRepairMoleculeEpisode(problem, repairLedger, repairer, episode));
  }
  const allResults = [...staticResults, ...repairResults];
  const staticCps = callsPerSuccess(staticResults);
  const repairCps = callsPerSuccess(repairResults);
  return {
    episodes,
    candidateSpaceSize: editSpace.length,
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

function candidateShapeError(problem                       , graph               )                {
  const template = problem.templateGraph;
  if (!arrayEqual(graph.atoms.map((atom) => atom.atomId), template.atoms.map((atom) => atom.atomId))) {
    return "candidate atom ids must match template order";
  }
  if (!arrayEqual(graph.bonds.map((bond) => `${bond.bondId}:${bond.atoms.join("-")}`), template.bonds.map((bond) => `${bond.bondId}:${bond.atoms.join("-")}`))) {
    return "candidate bond ids and endpoints must match template";
  }
  for (let idx = 0; idx < template.atoms.length; idx += 1) {
    const expected = template.atoms[idx];
    const actual = graph.atoms[idx];
    if (expected.atomId !== problem.mutableAtomId && expected.element !== actual.element) {
      return "only the mutable atom element may change";
    }
  }
  for (let idx = 0; idx < template.bonds.length; idx += 1) {
    const expected = template.bonds[idx];
    const actual = graph.bonds[idx];
    if (expected.bondId !== problem.mutableBondId && expected.order !== actual.order) {
      return "only the mutable bond order may change";
    }
  }
  const mutableAtom = graph.atoms.find((atom) => atom.atomId === problem.mutableAtomId);
  const mutableBond = graph.bonds.find((bond) => bond.bondId === problem.mutableBondId);
  if (!mutableAtom || !problem.allowedElements.includes(mutableAtom.element)) {
    return "mutable atom element is not allowed";
  }
  if (!mutableBond || !problem.allowedBondOrders.includes(mutableBond.order)) {
    return "mutable bond order is not allowed";
  }
  return null;
}

async function episodeResult(
  calls        ,
  success         ,
  engine                                                                  ,
  seedState                     ,
)                                 {
  const auditOk = await engine.ledger.audit();
  let replayRollbackOk = false;
  if (auditOk) {
    try {
      await engine.replayAudit(seedState);
      replayRollbackOk = moleculeStatesEqual(await engine.rollbackAudit(seedState), seedState);
    } catch (_error) {
      replayRollbackOk = false;
    }
  }
  return { calls, success, auditOk, replayRollbackOk };
}

function normalizeBondOrder(value        )         {
  if (!Number.isInteger(value) || !DEFAULT_BOND_ORDERS.includes(value             )) {
    throw new RangeError("bond order must be 1, 2, or 3");
  }
  return value;
}

function formulasEqual(a                        , b                        )          {
  return JSON.stringify(normalizeFormula(a)) === JSON.stringify(normalizeFormula(b));
}

function moleculeProblemsEqual(a                       , b                       )          {
  return JSON.stringify(normalizeMoleculeProblem(a)) === JSON.stringify(normalizeMoleculeProblem(b));
}

function moleculeStatesEqual(a                     , b                     )          {
  return JSON.stringify(normalizeMoleculeState(a)) === JSON.stringify(normalizeMoleculeState(b));
}

function arrayEqual   (a              , b              )          {
  return a.length === b.length && a.every((value, idx) => value === b[idx]);
}

function isMoleculeResidual(value         )                            {
  if (!value || typeof value !== "object") {
    return false;
  }
  const residual = value                             ;
  return residual.kind === "schema_error" || residual.kind === "valence_exceeded" || residual.kind === "formula_mismatch";
}

function callsPerSuccess(results                         )         {
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
