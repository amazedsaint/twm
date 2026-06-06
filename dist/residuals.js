import { canonicalJson, stableHash } from "./canonical.js";


export const RESIDUAL_SCHEMA = "trwm.residual.v1";






























const residualCategories = new Set                  ([
  "none",
  "constraint",
  "coverage",
  "resource",
  "safety",
  "budget",
  "test",
  "equivalence",
  "schema",
  "unknown",
]);

const kindCategory                                   = {
  none: "none",
  schema_error: "schema",
  duplicate_order: "constraint",
  over_reservation: "resource",
  stock_shortage: "resource",
  diff_mismatch: "constraint",
  accounting_mismatch: "constraint",
  unsatisfied_clause: "constraint",
  goal_not_derived: "constraint",
  missing_premise: "constraint",
  formula_mismatch: "constraint",
  valence_exceeded: "constraint",
  truth_table_mismatch: "equivalence",
  test_failure: "test",
  operator_mismatch: "test",
  collision: "safety",
  speed_limit_exceeded: "safety",
  stopping_distance_violation: "safety",
  illegal_move: "constraint",
  projection_contract_violation: "coverage",
  projection_contract_missing_fields: "coverage",
  field_hash_mismatch: "coverage",
  missing_fields: "coverage",
  verifier_budget_exhausted: "budget",
  verifier_false_positive: "safety",
  primary_verifier_mismatch: "coverage",
  audit_verifier_mismatch: "coverage",
  candidate_rejected: "constraint",
  wrong_domain: "schema",
};

const fieldKeys = [
  "field",
  "fields",
  "missing_field",
  "missing_fields",
  "required_field",
  "required_fields",
  "sku",
  "variable",
  "variables",
  "clause",
  "gate",
  "gate_id",
  "operator",
  "action",
  "test",
  "obstacle_id",
  "required_verifier_cost",
  "remaining_budget",
  "budget",
];

const repairKeys = [
  "repair",
  "repair_hint",
  "repair_hints",
  "suggested_repair",
  "suggested_action",
  "hint",
  "replacement",
  "expected",
];

export class ResidualTaxonomyMemory {
  categoryCounts = new Map                ();
  kindCounts = new Map                ();
  hintCounts = new Map                             ();

  async update(signal                )                {
    if (!await validateResidualSignal(signal)) {
      throw new Error("invalid residual signal");
    }
    increment(this.categoryCounts, signal.category);
    increment(this.kindCounts, signal.kind);
    for (const hint of signal.repairHints) {
      let row = this.hintCounts.get(signal.kind);
      if (!row) {
        row = new Map();
        this.hintCounts.set(signal.kind, row);
      }
      increment(row, hint);
    }
  }

  rankCategories()           {
    return sortCounts(this.categoryCounts);
  }

  rankKinds()           {
    return sortCounts(this.kindCounts);
  }

  topRepairHint(kind        )                {
    const row = this.hintCounts.get(snakeCase(kind));
    if (!row || row.size === 0) {
      return null;
    }
    return sortCounts(row)[0];
  }
}

export async function residualSignalFromReceipt(receipt         , options                            = {})                          {
  return normalizeResidual(receipt.hardResult.residual, {
    status: receipt.hardResult.result,
    verifierId: receipt.hardResult.verifierId,
    verifierVersion: receipt.hardResult.verifierVersion,
    receiptHash: receipt.receiptHash,
    candidateHash: receipt.typedCandidateHash,
    sourceDomain: options.sourceDomain ?? "",
  });
}

export async function normalizeResidual(
  residual         ,
  options






   ,
)                          {
  let normalized                         ;
  let kind        ;
  if (typeof residual === "undefined" || residual === null) {
    normalized = {};
    kind = "none";
  } else if (isRecord(residual)) {
    normalized = normalizeMapping(residual);
    kind = snakeCase(String(normalized.kind ?? "unknown"));
  } else {
    normalized = { message: String(residual) };
    kind = "unknown";
  }
  const category = kindCategory[kind] ?? "unknown";
  const attributes = { ...normalized };
  delete attributes.kind;
  const pending                 = {
    schemaVersion: RESIDUAL_SCHEMA,
    status: options.status,
    kind,
    category,
    verifierId: String(options.verifierId),
    verifierVersion: String(options.verifierVersion),
    residualHash: await stableHash(residual),
    sourceDomain: String(options.sourceDomain ?? ""),
    fields: unique(extractFields(normalized)),
    repairHints: unique(extractRepairHints(normalized)),
    attributes,
    receiptHash: String(options.receiptHash ?? ""),
    candidateHash: String(options.candidateHash ?? ""),
    signalHash: "",
  };
  return { ...pending, signalHash: await residualSignalHash(pending) };
}

export async function residualSignalHash(signal                )                  {
  const { signalHash: _signalHash, ...withoutHash } = signal;
  return stableHash(withoutHash);
}

export async function residualLearningHash(signal                )                  {
  return stableHash({
    schemaVersion: signal.schemaVersion,
    status: signal.status,
    kind: signal.kind,
    category: signal.category,
    fields: signal.fields,
    repairHints: signal.repairHints,
    attributes: signal.attributes,
  });
}

export async function validateResidualSignal(signal                )                   {
  if (signal.schemaVersion !== RESIDUAL_SCHEMA) {
    return false;
  }
  if (signal.status !== "accept" && signal.status !== "reject" && signal.status !== "abstain") {
    return false;
  }
  if (!residualCategories.has(signal.category)) {
    return false;
  }
  if (!/^[0-9a-f]{64}$/.test(signal.residualHash)) {
    return false;
  }
  return signal.signalHash === await residualSignalHash(signal);
}

function normalizeMapping(mapping                         )                          {
  const out                          = {};
  for (const [key, value] of Object.entries(mapping)) {
    const normalizedKey = snakeCase(key);
    const normalizedValue = normalizeValue(value);
    if (Object.prototype.hasOwnProperty.call(out, normalizedKey)) {
      if (canonicalJson(out[normalizedKey]) !== canonicalJson(normalizedValue)) {
        throw new Error(`residual key collision after normalization: ${normalizedKey}`);
      }
      continue;
    }
    out[normalizedKey] = normalizedValue;
  }
  return out;
}

function normalizeValue(value         )          {
  if (isRecord(value)) {
    return normalizeMapping(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => normalizeValue(item));
  }
  return value;
}

function extractFields(residual                         )           {
  const fields           = [];
  for (const key of fieldKeys) {
    if (Object.prototype.hasOwnProperty.call(residual, key)) {
      fields.push(...flattenStrings(residual[key]));
    }
  }
  return fields;
}

function extractRepairHints(residual                         )           {
  const hints           = [];
  for (const key of repairKeys) {
    if (Object.prototype.hasOwnProperty.call(residual, key)) {
      hints.push(...flattenRepairHint(key, residual[key]));
    }
  }
  return hints;
}

function flattenRepairHint(key        , value         )           {
  if (isRecord(value)) {
    const normalized = normalizeMapping(value);
    const hints           = [];
    for (const [nestedKey, nestedValue] of Object.entries(normalized)) {
      hints.push(`${nestedKey}=${String(nestedValue)}`);
    }
    return hints;
  }
  const values = flattenStrings(value);
  if (key === "hint" || key === "repair_hint" || key === "suggested_action") {
    return values;
  }
  return values.map((item) => `${key}=${item}`);
}

function flattenStrings(value         )           {
  if (typeof value === "undefined" || value === null) {
    return [];
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return [String(value)];
  }
  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }
  if (isRecord(value)) {
    const out           = [];
    for (const [key, nested] of Object.entries(value)) {
      for (const item of flattenStrings(nested)) {
        out.push(`${snakeCase(key)}=${item}`);
      }
    }
    return out;
  }
  return [String(value)];
}

function unique(values          )           {
  const seen = new Set        ();
  const out           = [];
  for (const value of values) {
    if (!seen.has(value)) {
      seen.add(value);
      out.push(value);
    }
  }
  return out;
}

function snakeCase(value        )         {
  return value
    .replace(/[-. ]/g, "_")
    .replace(/(.)([A-Z][a-z]+)/g, "$1_$2")
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/__+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase() || "unknown";
}

function isRecord(value         )                                   {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function increment(map                     , key        )       {
  map.set(key, (map.get(key) ?? 0) + 1);
}

function sortCounts(map                     )           {
  return Array.from(map.entries())
    .sort((a, b) => {
      const countDiff = b[1] - a[1];
      if (countDiff !== 0) return countDiff;
      if (a[0] < b[0]) return -1;
      if (a[0] > b[0]) return 1;
      return 0;
    })
    .map((row) => row[0]);
}
