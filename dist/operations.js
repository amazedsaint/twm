import {




  Ledger,
  TransactionEngine,
  hardAccept,
  hardReject,
  makeCandidate,
  makeTrace,
} from "./core.js";
import { stableHash } from "./canonical.js";





































export class InventoryReservationAdapter                                                                               {
  verifierId = "inventory_reservation_verifier";
  verifierVersion = "1.0";

  verify(candidate                                             )                     {
    const payload = candidate.payload;
    const state = normalizeInventoryState(payload.preState);
    const metadata = { cost: payload.cost, requested: payload.requested, quantity: payload.quantity };
    if (!payload.orderId) {
      return this.reject("schema_error", { message: "orderId must be non-empty" }, metadata);
    }
    if (state.committedOrders.includes(payload.orderId)) {
      return this.reject("duplicate_order", { orderId: payload.orderId }, metadata);
    }
    if (!positiveInt(payload.requested) || !positiveInt(payload.quantity)) {
      return this.reject("schema_error", { message: "requested and quantity must be positive" }, metadata);
    }
    const available = state.stock[payload.sku] ?? 0;
    if (payload.quantity > payload.requested) {
      return this.reject(
        "over_reservation",
        { requested: payload.requested, quantity: payload.quantity, repair: { quantity: payload.requested } },
        metadata,
      );
    }
    if (payload.quantity > available) {
      return this.reject(
        "stock_shortage",
        {
          sku: payload.sku,
          requested: payload.requested,
          available,
          quantity: payload.quantity,
          repair: available > 0 ? { quantity: available } : null,
        },
        metadata,
      );
    }
    const expected = { stockDelta: -payload.quantity, reservedDelta: payload.quantity };
    if (payload.diff.stockDelta !== expected.stockDelta || payload.diff.reservedDelta !== expected.reservedDelta) {
      return this.reject("diff_mismatch", { expected, actual: payload.diff }, metadata);
    }
    const next = applyInventoryReservation(state, payload.orderId, payload.sku, payload.quantity);
    if (totalUnits(state, payload.sku) !== totalUnits(next, payload.sku)) {
      return this.reject("accounting_mismatch", { sku: payload.sku }, metadata);
    }
    return hardAccept(this.verifierId, this.verifierVersion, {
      ...metadata,
      availableBefore: available,
      availableAfter: next.stock[payload.sku] ?? 0,
    });
  }

  applyCommit(state                , candidate                                             )                 {
    const current = normalizeInventoryState(state);
    const preState = normalizeInventoryState(candidate.payload.preState);
    if (!statesEqual(current, preState)) {
      throw new Error("candidate preState does not match current inventory state");
    }
    return applyInventoryReservation(current, candidate.payload.orderId, candidate.payload.sku, candidate.payload.quantity);
  }

  replay(state                , receipt         )                 {
    const payload = (receipt.replayBundle                                                     ).candidatePayload;
    return applyInventoryReservation(normalizeInventoryState(state), payload.orderId, payload.sku, payload.quantity);
  }

  rollback(_state                , receipt         )                 {
    return normalizeInventoryState((receipt.rollbackBundle                                ).preState);
  }

          reject(kind        , residual                         , metadata                         )                     {
    return hardReject(this.verifierId, this.verifierVersion, { kind, ...residual }, metadata);
  }
}

export class InventoryResidualRepairer {
  rejectedResiduals = new Map                ();
  acceptedOrders = new Map                ();

  update(receipt         )       {
    const bundle = receipt.replayBundle && typeof receipt.replayBundle === "object"
      ? receipt.replayBundle
      : {};
    const payload = bundle.candidatePayload && typeof bundle.candidatePayload === "object"
      ? bundle.candidatePayload
      : {};
    if (receipt.hardResult.result === "accept") {
      incrementMap(this.acceptedOrders, String(payload.sku ?? "unknown"));
      return;
    }
    const residual = receipt.hardResult.residual;
    if (receipt.hardResult.result === "reject" && residual && typeof residual === "object") {
      incrementMap(this.rejectedResiduals, String((residual                      ).kind ?? "unknown"));
    }
  }

  async propose(candidate                                             , residual         )                                                              {
    if (!residual || typeof residual !== "object") {
      return null;
    }
    const repair = (residual                                       ).repair;
    const quantity = repair?.quantity;
    if (!Number.isInteger(quantity) || Number(quantity) <= 0) {
      return null;
    }
    return makeReservationCandidate(
      candidate.payload.preState,
      candidate.payload.orderId,
      candidate.payload.sku,
      candidate.payload.requested,
      Number(quantity),
      candidate.payload.context,
      candidate.payload.cost + 1,
    );
  }
}

export function normalizeInventoryState(state                         )                 {
  const stock = normalizeQuantities(state.stock ?? {});
  const reserved = normalizeQuantities(state.reserved ?? {});
  const committedOrders = (state.committedOrders ?? []).map(String);
  if (new Set(committedOrders).size !== committedOrders.length) {
    throw new RangeError("committedOrders must be unique");
  }
  return { stock, reserved, committedOrders };
}

export function applyInventoryReservation(stateInput                , orderId        , sku        , quantity        )                 {
  const state = normalizeInventoryState(stateInput);
  if (!positiveInt(quantity)) {
    throw new RangeError("quantity must be positive");
  }
  const available = state.stock[sku] ?? 0;
  if (quantity > available) {
    throw new RangeError("reservation exceeds available stock");
  }
  return {
    stock: { ...state.stock, [sku]: available - quantity },
    reserved: { ...state.reserved, [sku]: (state.reserved[sku] ?? 0) + quantity },
    committedOrders: [...state.committedOrders, orderId],
  };
}

export async function makeReservationCandidate(
  stateInput                ,
  orderId        ,
  sku        ,
  requested        ,
  quantity        ,
  context = "inventory",
  cost = 1,
)                                                       {
  const state = normalizeInventoryState(stateInput);
  const diff = { stockDelta: -quantity, reservedDelta: quantity };
  return makeCandidate(
    {
      context,
      preState: state,
      orderId,
      sku,
      requested,
      quantity,
      diff,
      cost,
    },
    "ops.inventory_reservation",
    "ops.inventory_reservation.v1",
    {
      preState: await stableHash(state),
      order: await stableHash({ orderId, sku, requested, quantity }),
      diff: await stableHash(diff),
    },
  );
}

export async function runStaticOperationsEpisode(
  stateInput                ,
  orderId        ,
  sku        ,
  requested        ,
  ledger        ,
  episode        ,
)                                   {
  const state = normalizeInventoryState(stateInput);
  const engine = new TransactionEngine(new InventoryReservationAdapter(), ledger);
  for (let quantity = requested, calls = 1; quantity > 0; quantity -= 1, calls += 1) {
    const candidate = await makeReservationCandidate(state, orderId, sku, requested, quantity, "ops-static", calls);
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `ops-static-${episode}-${quantity}`,
        actions: [{ orderId, sku, quantity }],
        seeds: [episode, quantity],
        modelVersion: "ops.static.v1",
      }),
      candidate,
    );
    if (outcome.committed) {
      return episodeResult(calls, true, engine, state);
    }
  }
  return episodeResult(requested, false, engine, state);
}

export async function runRepairOperationsEpisode(
  stateInput                ,
  orderId        ,
  sku        ,
  requested        ,
  ledger        ,
  repairer                           ,
  episode        ,
)                                   {
  const state = normalizeInventoryState(stateInput);
  const engine = new TransactionEngine(new InventoryReservationAdapter(), ledger);
  let candidate = await makeReservationCandidate(state, orderId, sku, requested, requested, "ops-repair", 1);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const outcome = await engine.transact(
      state,
      makeTrace({
        branchId: `ops-repair-${episode}-${attempt}`,
        actions: [{ orderId, sku, quantity: candidate.payload.quantity }],
        seeds: [episode, attempt],
        modelVersion: "ops.residual_repair.v1",
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

export async function runOperationsBenchmark(seed = 31, episodes = 48)                            {
  if (!Number.isInteger(episodes) || episodes <= 0) {
    throw new RangeError("episodes must be positive");
  }
  const rng = mulberry32(seed);
  const staticResults                            = [];
  const repairResults                            = [];
  const staticLedgers           = [];
  const repairLedgers           = [];
  const repairer = new InventoryResidualRepairer();
  for (let idx = 0; idx < episodes; idx += 1) {
    const sku = idx % 2 === 0 ? "A" : "B";
    const available = 4 + Math.floor(rng() * 9);
    const requested = available + Math.floor(rng() * 9);
    const state = { stock: { [sku]: available }, reserved: { [sku]: 0 }, committedOrders: [] };
    const staticLedger = new Ledger();
    const repairLedger = new Ledger();
    staticLedgers.push(staticLedger);
    repairLedgers.push(repairLedger);
    const orderId = `order-${idx}`;
    staticResults.push(await runStaticOperationsEpisode(state, orderId, sku, requested, staticLedger, idx));
    repairResults.push(await runRepairOperationsEpisode(state, orderId, sku, requested, repairLedger, repairer, idx));
  }
  const allResults = [...staticResults, ...repairResults];
  const staticCps = callsPerSuccess(staticResults);
  const repairCps = callsPerSuccess(repairResults);
  return {
    episodes,
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

async function episodeResult(calls        , success         , engine                                                                , seedState                )                                   {
  const auditOk = await engine.ledger.audit();
  let replayRollbackOk = false;
  if (auditOk) {
    try {
      await engine.replayAudit(seedState);
      replayRollbackOk = statesEqual(await engine.rollbackAudit(seedState), seedState);
    } catch (_error) {
      replayRollbackOk = false;
    }
  }
  return { calls, success, auditOk, replayRollbackOk };
}

function normalizeQuantities(values                        )                         {
  const out                         = {};
  for (const [key, value] of Object.entries(values)) {
    if (!Number.isInteger(value) || value < 0) {
      throw new RangeError("inventory quantities must be non-negative integers");
    }
    out[String(key)] = value;
  }
  return out;
}

function positiveInt(value        )          {
  return Number.isInteger(value) && value > 0;
}

function totalUnits(state                , sku        )         {
  return (state.stock[sku] ?? 0) + (state.reserved[sku] ?? 0);
}

function statesEqual(a                , b                )          {
  return JSON.stringify(normalizeInventoryState(a)) === JSON.stringify(normalizeInventoryState(b));
}

function incrementMap     (map                  , key     )       {
  map.set(key, (map.get(key) ?? 0) + 1);
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

function mulberry32(seed        )               {
  let t = seed >>> 0;
  return () => {
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}
