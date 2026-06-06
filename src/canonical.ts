export type CanonicalValue =
  | null
  | boolean
  | number
  | string
  | bigint
  | CanonicalValue[]
  | { [key: string]: CanonicalValue };

export function normalizeCanonical(value: unknown): unknown {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new TypeError("canonical values cannot contain NaN or Infinity");
    }
    return value;
  }
  if (typeof value === "bigint") {
    return { __bigint__: value.toString(10) };
  }
  if (value instanceof Uint8Array) {
    return { __bytes__: bytesToHex(value) };
  }
  if (Array.isArray(value)) {
    return value.map((item) => normalizeCanonical(item));
  }
  if (value instanceof Set) {
    return Array.from(value, (item) => normalizeCanonical(item)).sort((a, b) =>
      compareCodePoint(canonicalJson(a), canonicalJson(b)),
    );
  }
  if (value instanceof Map) {
    const output: Record<string, unknown> = {};
    const entries = Array.from(value.entries()).sort((a, b) => compareCodePoint(String(a[0]), String(b[0])));
    for (const [key, item] of entries) {
      const normalizedKey = String(key);
      if (Object.prototype.hasOwnProperty.call(output, normalizedKey)) {
        throw new TypeError(`mapping key collision after canonicalization: ${normalizedKey}`);
      }
      output[normalizedKey] = normalizeCanonical(item);
    }
    return output;
  }
  if (value && typeof value === "object") {
    const input = value as Record<PropertyKey, unknown>;
    const output: Record<string, unknown> = {};
    const keys = Reflect.ownKeys(input).sort((a, b) => compareCodePoint(String(a), String(b)));
    for (const key of keys) {
      if (typeof key === "symbol") {
        throw new TypeError("canonical values cannot contain symbol keys");
      }
      const normalizedKey = String(key);
      if (Object.prototype.hasOwnProperty.call(output, normalizedKey)) {
        throw new TypeError(`mapping key collision after canonicalization: ${normalizedKey}`);
      }
      output[normalizedKey] = normalizeCanonical(input[key]);
    }
    return output;
  }
  if (typeof value === "undefined") {
    throw new TypeError("canonical values cannot contain undefined");
  }
  if (typeof value === "function") {
    throw new TypeError("canonical values cannot contain functions");
  }
  if (typeof value === "symbol") {
    throw new TypeError("canonical values cannot contain symbols");
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(normalizeCanonical(value));
}

export async function stableHash(value: unknown): Promise<string> {
  return sha256Hex(canonicalJson(value));
}

export async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  if (!globalThis.crypto?.subtle) {
    throw new Error("Web Crypto subtle digest is required for stable hashes");
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return bytesToHex(new Uint8Array(digest));
}

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function chainHash(parentHead: string, receiptHash: string): Promise<string> {
  assertHexHash(parentHead, "parentHead");
  assertHexHash(receiptHash, "receiptHash");
  return sha256Hex(parentHead + receiptHash);
}

export function assertHexHash(value: string, label: string): void {
  if (!/^[0-9a-f]{64}$/.test(value)) {
    throw new TypeError(`${label} must be a lowercase SHA-256 hex digest`);
  }
}

export function compareCodePoint(a: string, b: string): number {
  if (a < b) {
    return -1;
  }
  if (a > b) {
    return 1;
  }
  return 0;
}
