import { compareCodePoint, stableHash } from "./canonical.js";

export const PROJECTION_CONTRACT_SCHEMA = "trwm.projection_contract.v1";
export const PROJECTION_MANIFEST_SCHEMA = "trwm.projection_manifest.v1";

export interface ProjectionContract {
  requiredFields: string[];
  contractId: string;
  schemaVersion: typeof PROJECTION_CONTRACT_SCHEMA;
}

export interface ProjectionManifest {
  projectorId: string;
  projectorVersion: string;
  sourceHash: string;
  coveredFields: string[];
  fieldHashes: Record<string, string>;
  projectionHash: string;
  schemaVersion: typeof PROJECTION_MANIFEST_SCHEMA;
}

export interface ProjectionAudit {
  accepted: boolean;
  missingFields: string[];
  staleFields: string[];
  absentSourceFields: string[];
  hashMismatch: boolean;
  sourceHashMismatch: boolean;
  residual: {
    kind: "projection_contract_violation";
    missingFields: string[];
    staleFields: string[];
    absentSourceFields: string[];
    hashMismatch: boolean;
    sourceHashMismatch: boolean;
  };
}

export function makeProjectionContract(
  requiredFields: string[],
  options: { contractId?: string } = {},
): ProjectionContract {
  const fields = normalizeFieldNames(requiredFields);
  if (fields.length === 0) {
    throw new RangeError("requiredFields must not be empty");
  }
  const contractId = options.contractId ?? "projection.contract";
  if (!contractId) {
    throw new RangeError("contractId must be non-empty");
  }
  return {
    requiredFields: fields,
    contractId,
    schemaVersion: PROJECTION_CONTRACT_SCHEMA,
  };
}

export async function buildProjectionManifest(
  source: Record<string, unknown>,
  coveredFields: string[],
  options: { projectorId: string; projectorVersion: string },
): Promise<ProjectionManifest> {
  const fields = normalizeFieldNames(coveredFields);
  const missing = fields.filter((field) => !(field in source));
  if (missing.length > 0) {
    throw new RangeError(`covered fields not present in source: ${missing.join(",")}`);
  }
  const fieldHashes: Record<string, string> = {};
  for (const field of fields) {
    fieldHashes[field] = await fieldValueHash(field, source[field]);
  }
  const sourceHash = await sourceProjectionHash(source);
  const projectionHash = await projectionManifestHash({
    schemaVersion: PROJECTION_MANIFEST_SCHEMA,
    projectorId: options.projectorId,
    projectorVersion: options.projectorVersion,
    sourceHash,
    coveredFields: fields,
    fieldHashes,
  });
  return {
    projectorId: options.projectorId,
    projectorVersion: options.projectorVersion,
    sourceHash,
    coveredFields: fields,
    fieldHashes,
    projectionHash,
    schemaVersion: PROJECTION_MANIFEST_SCHEMA,
  };
}

export async function validateProjectionContract(
  contract: ProjectionContract,
  manifest: ProjectionManifest | Record<string, unknown>,
  source?: Record<string, unknown>,
): Promise<ProjectionAudit> {
  const normalized = normalizeProjectionManifest(manifest);
  const covered = new Set(normalized.coveredFields);
  const missingFields = contract.requiredFields.filter((field) => !covered.has(field));
  const expectedHash = await projectionManifestHash(normalized);
  const hashMismatch = Boolean(normalized.projectionHash && normalized.projectionHash !== expectedHash);
  let sourceHashMismatch = false;
  let absentSourceFields: string[] = [];
  const staleFields: string[] = [];
  if (source) {
    sourceHashMismatch = normalized.sourceHash !== await sourceProjectionHash(source);
    absentSourceFields = contract.requiredFields.filter((field) => !(field in source));
    for (const field of contract.requiredFields) {
      if (field in source && field in normalized.fieldHashes) {
        const expectedFieldHash = await fieldValueHash(field, source[field]);
        if (normalized.fieldHashes[field] !== expectedFieldHash) {
          staleFields.push(field);
        }
      }
    }
  }
  const accepted = missingFields.length === 0
    && staleFields.length === 0
    && absentSourceFields.length === 0
    && !hashMismatch
    && !sourceHashMismatch;
  const residual = {
    kind: "projection_contract_violation" as const,
    missingFields,
    staleFields,
    absentSourceFields,
    hashMismatch,
    sourceHashMismatch,
  };
  return {
    accepted,
    missingFields,
    staleFields,
    absentSourceFields,
    hashMismatch,
    sourceHashMismatch,
    residual,
  };
}

export function normalizeProjectionManifest(manifest: ProjectionManifest | Record<string, unknown>): ProjectionManifest {
  const raw = manifest as Record<string, unknown>;
  const schemaVersion = String(raw.schemaVersion ?? raw.schema_version ?? PROJECTION_MANIFEST_SCHEMA);
  if (schemaVersion !== PROJECTION_MANIFEST_SCHEMA) {
    throw new RangeError(`unsupported projection manifest schema: ${schemaVersion}`);
  }
  const projectorId = String(raw.projectorId ?? raw.projector_id ?? "");
  const projectorVersion = String(raw.projectorVersion ?? raw.projector_version ?? "");
  if (!projectorId || !projectorVersion) {
    throw new RangeError("projector id and version must be non-empty");
  }
  const coveredRaw = raw.coveredFields ?? raw.covered_fields;
  if (!Array.isArray(coveredRaw)) {
    throw new RangeError("coveredFields must be an array");
  }
  const fieldHashesRaw = raw.fieldHashes ?? raw.field_hashes;
  if (!fieldHashesRaw || typeof fieldHashesRaw !== "object" || Array.isArray(fieldHashesRaw)) {
    throw new RangeError("fieldHashes must be an object");
  }
  const coveredFields = normalizeFieldNames(coveredRaw.map((field) => String(field)));
  const fieldHashes = Object.fromEntries(
    Object.entries(fieldHashesRaw as Record<string, unknown>)
      .map(([key, value]) => [String(key), String(value)])
      .sort((a, b) => compareCodePoint(a[0], b[0])),
  );
  if (coveredFields.length !== Object.keys(fieldHashes).length || coveredFields.some((field) => !(field in fieldHashes))) {
    throw new RangeError("fieldHashes must match coveredFields");
  }
  return {
    projectorId,
    projectorVersion,
    sourceHash: String(raw.sourceHash ?? raw.source_hash ?? ""),
    coveredFields,
    fieldHashes,
    projectionHash: String(raw.projectionHash ?? raw.projection_hash ?? ""),
    schemaVersion: PROJECTION_MANIFEST_SCHEMA,
  };
}

export async function sourceProjectionHash(source: Record<string, unknown>): Promise<string> {
  return stableHash({ schemaVersion: PROJECTION_MANIFEST_SCHEMA, source });
}

export async function fieldValueHash(field: string, value: unknown): Promise<string> {
  return stableHash({ field: String(field), value });
}

async function projectionManifestHash(manifest: {
  schemaVersion: string;
  projectorId: string;
  projectorVersion: string;
  sourceHash: string;
  coveredFields: string[];
  fieldHashes: Record<string, string>;
}): Promise<string> {
  return stableHash({
    schemaVersion: manifest.schemaVersion,
    projectorId: manifest.projectorId,
    projectorVersion: manifest.projectorVersion,
    sourceHash: manifest.sourceHash,
    coveredFields: manifest.coveredFields,
    fieldHashes: manifest.fieldHashes,
  });
}

function normalizeFieldNames(fields: string[]): string[] {
  const normalized = fields.map((field) => String(field));
  if (normalized.some((field) => !field)) {
    throw new RangeError("field names must be non-empty");
  }
  const deduped = Array.from(new Set(normalized)).sort(compareCodePoint);
  if (deduped.length !== normalized.length) {
    throw new RangeError("field names must be unique");
  }
  return deduped;
}
