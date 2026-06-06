import { makeTrace } from "./core.js";
import {
                
                 
  GridMacroAdapter,
  defaultGridMacros,
  defaultGridState,
} from "./macro.js";
import {
  LifePredecessorAdapter,
  lifeStep,
  makeLifeCandidate,
} from "./life.js";
import {
  ScalarProgramAdapter,
  makeScalarCandidate,
} from "./repair.js";
import { ProgrammableSubstrate } from "./sdk.js";
import {
  SokobanReverseAdapter,
  makeSokobanCandidate,
  parseSokoban,
} from "./sokoban.js";
import {
  InventoryReservationAdapter,
  makeReservationCandidate,
} from "./operations.js";
import {
  HornProofAdapter,
  chainProofProblem,
  makeProofCandidate,
} from "./proof_kernel.js";
import {
  BooleanCircuitAdapter,
  makeCircuitCandidate,
  makeCircuitRepairProblem,
} from "./circuit_repair.js";
import {
  ChessAncestryAdapter,
  diagnoseChessAncestry,
  makeChessCandidate,
  makeDefaultChessAncestryProblem,
} from "./chess_ancestry.js";
import {
  MoleculeGraphAdapter,
  makeMoleculeCandidate,
  makeMoleculeRepairProblem,
} from "./molecule_repair.js";
import {
  CodePatchAdapter,
  makeCodePatchCandidate,
  makeCodeRepairProblem,
} from "./code_repair.js";
import {
  RobotTrajectoryAdapter,
  makeRobotTrajectoryCandidate,
  makeRobotTrajectoryProblem,
} from "./robotics.js";

                                       
                           
                           
                       
                             
                             
                          
                        
                        
                           
                              
                         
                           
                            
                        
                         
                         
                          
                                                             
                                                           
                                                              
                                                                 
                                                            
                                                              
                                                               
                                                           
                                                            
                                                            
 

export async function runMultiDomainSdkBenchmark()                                {
  const substrate = new ProgrammableSubstrate();
  substrate.register("scalar", new ScalarProgramAdapter());
  substrate.register("life", new LifePredecessorAdapter());
  substrate.register("grid", new GridMacroAdapter());
  substrate.register("sokoban", new SokobanReverseAdapter());
  substrate.register("operations", new InventoryReservationAdapter());
  substrate.register("proof", new HornProofAdapter());
  substrate.register("circuit", new BooleanCircuitAdapter());
  substrate.register("molecule", new MoleculeGraphAdapter());
  substrate.register("code", new CodePatchAdapter());
  substrate.register("robot", new RobotTrajectoryAdapter());
  substrate.register("chess", new ChessAncestryAdapter());

  const scalarState = { episode: 0, target: 5, solved: false };
  const scalar = await substrate.submit(
    "scalar",
    scalarState,
    makeTrace({
      branchId: "sdk-scalar",
      actions: [{ op: "set", value: 5 }],
      seeds: ["sdk", "scalar"],
      modelVersion: "sdk.scalar.v1",
    }),
    makeScalarCandidate("sdk-routing", 5, [{ op: "set", value: 5 }]),
    { context: "sdk-routing" },
  );
  await substrate.submit(
    "scalar",
    scalar.outcome.state,
    makeTrace({
      branchId: "sdk-scalar-repeat",
      actions: [{ op: "set", value: 5 }],
      seeds: ["sdk", "scalar-repeat"],
      modelVersion: "sdk.scalar.v1",
    }),
    makeScalarCandidate("sdk-routing", 5, [{ op: "set", value: 5 }]),
    { context: "sdk-routing" },
  );

  const seedPredecessor = [
    [0, 0, 0],
    [1, 1, 1],
    [0, 0, 0],
  ];
  const target = lifeStep(seedPredecessor);
  const lifeState = { target };
  const life = await substrate.submit(
    "life",
    lifeState,
    makeTrace({
      branchId: "sdk-life",
      actions: [{ predecessor: seedPredecessor, cost: 1 }],
      seeds: ["sdk", "life"],
      modelVersion: "sdk.life.v1",
    }),
    await makeLifeCandidate(target, seedPredecessor, 1),
    { context: "sdk-routing" },
  );

  const gridAdapter = new GridMacroAdapter();
  const gridSeed = defaultGridState();
  const gridMacro = defaultGridMacros()[1];
  const gridFinal = applyGridMacro(gridAdapter, gridSeed, gridMacro.steps);
  const grid = await substrate.submit(
    "grid",
    gridSeed,
    makeTrace({
      branchId: "sdk-grid",
      actions: gridMacro.steps,
      seeds: ["sdk", "grid"],
      modelVersion: "sdk.grid.v1",
    }),
    gridAdapter.projectMacro(gridSeed, gridMacro, gridFinal),
    { context: "sdk-routing" },
  );

  const { layout: sokobanLayout, state: sokobanSolved } = parseSokoban([
    "#######",
    "#  @* #",
    "#     #",
    "#######",
  ]);
  const sokobanPredecessor = { boxes: [[1, 3]], player: [1, 2] };
  const sokobanPushes = [{ box: [1, 3], direction: "R" }];
  const sokoban = await substrate.submit(
    "sokoban",
    sokobanSolved,
    makeTrace({
      branchId: "sdk-sokoban",
      actions: sokobanPushes,
      seeds: ["sdk", "sokoban"],
      modelVersion: "sdk.sokoban.v1",
    }),
    await makeSokobanCandidate(sokobanLayout, sokobanSolved, sokobanPredecessor, sokobanPushes, 1),
    { context: "sdk-routing" },
  );

  const operationsSeed = { stock: { A: 5 }, reserved: { A: 0 }, committedOrders: [] };
  const operations = await substrate.submit(
    "operations",
    operationsSeed,
    makeTrace({
      branchId: "sdk-operations",
      actions: [{ orderId: "sdk-order", sku: "A", quantity: 5 }],
      seeds: ["sdk", "operations"],
      modelVersion: "sdk.operations.v1",
    }),
    await makeReservationCandidate(operationsSeed, "sdk-order", "A", 7, 5),
    { context: "sdk-routing" },
  );

  const { problem: proofProblem, correctScript: proofScript } = chainProofProblem(2, "sdk_p");
  const proofState = { problem: proofProblem, proven: false, derived: [], proof: [] };
  const proof = await substrate.submit(
    "proof",
    proofState,
    makeTrace({
      branchId: "sdk-proof",
      actions: [{ script: proofScript }],
      seeds: ["sdk", "proof"],
      modelVersion: "sdk.proof.v1",
    }),
    await makeProofCandidate(proofProblem, proofScript, "sdk-routing", 1),
    { context: "sdk-routing" },
  );

  const circuitProblem = makeCircuitRepairProblem(6);
  const circuitState = { problem: circuitProblem, solved: false, netlist: null };
  const circuit = await substrate.submit(
    "circuit",
    circuitState,
    makeTrace({
      branchId: "sdk-circuit",
      actions: [{ gateId: "g1", opMask: 6 }],
      seeds: ["sdk", "circuit"],
      modelVersion: "sdk.circuit.v1",
    }),
    await makeCircuitCandidate(circuitProblem, 6, "sdk-routing", 1),
    { context: "sdk-routing" },
  );

  const moleculeProblem = makeMoleculeRepairProblem("O", 1);
  const moleculeState = { problem: moleculeProblem, solved: false, graph: null };
  const molecule = await substrate.submit(
    "molecule",
    moleculeState,
    makeTrace({
      branchId: "sdk-molecule",
      actions: [{ element: "O", bondOrder: 1 }],
      seeds: ["sdk", "molecule"],
      modelVersion: "sdk.molecule.v1",
    }),
    await makeMoleculeCandidate(moleculeProblem, "O", 1, "sdk-routing", 1),
    { context: "sdk-routing" },
  );

  const codeProblem = await makeCodeRepairProblem("+");
  const codeState = { problem: codeProblem, solved: false, operator: null, sourceAfter: null };
  const code = await substrate.submit(
    "code",
    codeState,
    makeTrace({
      branchId: "sdk-code",
      actions: [{ nodeId: "op0", operator: "+" }],
      seeds: ["sdk", "code"],
      modelVersion: "sdk.code.v1",
    }),
    await makeCodePatchCandidate(codeProblem, "+", "sdk-routing", 1),
    { context: "sdk-routing" },
  );

  const robotProblem = makeRobotTrajectoryProblem(0.24);
  const robotState = { problem: robotProblem, solved: false, trajectory: null };
  const robot = await substrate.submit(
    "robot",
    robotState,
    makeTrace({
      branchId: "sdk-robot",
      actions: [{ detourY: 0.22 }],
      seeds: ["sdk", "robot"],
      modelVersion: "sdk.robot.v1",
    }),
    await makeRobotTrajectoryCandidate(robotProblem, 0.22, "sdk-routing", 1),
    { context: "sdk-routing" },
  );

  const chessProblem = makeDefaultChessAncestryProblem();
  const chessState = { problem: chessProblem, histories: [] };
  const chessRepair = diagnoseChessAncestry(chessProblem);
  if (!chessRepair) {
    throw new Error("default chess ancestry problem has no legal predecessor");
  }
  const chess = await substrate.submit(
    "chess",
    chessState,
    makeTrace({
      branchId: "sdk-chess",
      actions: [chessRepair.move],
      seeds: ["sdk", "chess"],
      modelVersion: "sdk.chess.v1",
    }),
    await makeChessCandidate(chessProblem, chessRepair.predecessor, chessRepair.move, "sdk-routing", 1),
    { context: "sdk-routing" },
  );

  await substrate.submit(
    "life",
    lifeState,
    makeTrace({
      branchId: "sdk-life-reject",
      actions: [{ predecessor: [[0, 0, 0], [0, 0, 0], [0, 0, 0]], cost: 2 }],
      seeds: ["sdk", "life-reject"],
      modelVersion: "sdk.life.v1",
    }),
    await makeLifeCandidate(target, [[0, 0, 0], [0, 0, 0], [0, 0, 0]], 2),
    { context: "sdk-routing" },
  );

  const audits = [
    await substrate.auditDomain("scalar", scalarState),
    await substrate.auditDomain("life", lifeState),
    await substrate.auditDomain("grid", gridSeed),
    await substrate.auditDomain("sokoban", sokobanSolved),
    await substrate.auditDomain("operations", operationsSeed),
    await substrate.auditDomain("proof", proofState),
    await substrate.auditDomain("circuit", circuitState),
    await substrate.auditDomain("molecule", moleculeState),
    await substrate.auditDomain("code", codeState),
    await substrate.auditDomain("robot", robotState),
    await substrate.auditDomain("chess", chessState),
  ];
  const routerOrder = substrate.rankDomains("sdk-routing", ["life", "grid", "sokoban", "operations", "proof", "circuit", "molecule", "code", "robot", "chess", "scalar"]);
  return {
    domainsSupported: substrate.domains.size,
    committedDomains: [scalar, life, grid, sokoban, operations, proof, circuit, molecule, code, robot, chess].filter((result) => result.committed).length,
    ledgerAudit: audits.every((audit) => audit.ledgerAudit),
    replayRollbackRate: audits.filter((audit) => audit.ok).length / audits.length,
    invalidCommitCount: substrate.invalidCommitCount(),
    scalarHardCalls: substrate.domain("scalar").hardVerifierCalls,
    lifeHardCalls: substrate.domain("life").hardVerifierCalls,
    gridHardCalls: substrate.domain("grid").hardVerifierCalls,
    sokobanHardCalls: substrate.domain("sokoban").hardVerifierCalls,
    operationsHardCalls: substrate.domain("operations").hardVerifierCalls,
    proofHardCalls: substrate.domain("proof").hardVerifierCalls,
    circuitHardCalls: substrate.domain("circuit").hardVerifierCalls,
    moleculeHardCalls: substrate.domain("molecule").hardVerifierCalls,
    codeHardCalls: substrate.domain("code").hardVerifierCalls,
    robotHardCalls: substrate.domain("robot").hardVerifierCalls,
    chessHardCalls: substrate.domain("chess").hardVerifierCalls,
    routerTopDomain: routerOrder[0],
    routerScalarCounts: substrate.router.counts("sdk-routing", "scalar"),
    routerLifeCounts: substrate.router.counts("sdk-routing", "life"),
    routerSokobanCounts: substrate.router.counts("sdk-routing", "sokoban"),
    routerOperationsCounts: substrate.router.counts("sdk-routing", "operations"),
    routerProofCounts: substrate.router.counts("sdk-routing", "proof"),
    routerCircuitCounts: substrate.router.counts("sdk-routing", "circuit"),
    routerMoleculeCounts: substrate.router.counts("sdk-routing", "molecule"),
    routerCodeCounts: substrate.router.counts("sdk-routing", "code"),
    routerRobotCounts: substrate.router.counts("sdk-routing", "robot"),
    routerChessCounts: substrate.router.counts("sdk-routing", "chess"),
  };
}

function applyGridMacro(adapter                  , state           , steps            )            {
  return steps.reduce((current, step) => adapter.applyStep(current, step), state);
}
