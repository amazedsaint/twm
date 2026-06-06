import { canonicalJson } from "./canonical.js";

export type Tick = bigint;
export type TickVector = Tick[];
export type TickFunction = (input: TickVector, context: Record<string, unknown>) => TickVector;

export interface AffineCouplingParams {
  split: number;
  gainF: bigint;
  biasF: bigint;
  gainG: bigint;
  biasG: bigint;
}

const I32_MIN = BigInt(-(2 ** 31));
const I32_MAX = BigInt(2 ** 31 - 1);

export function toTicks(value: number, q: number): bigint {
  if (!Number.isFinite(value)) {
    throw new TypeError("cannot quantize NaN or Infinity");
  }
  if (!Number.isInteger(q) || q < 0 || q > 40) {
    throw new RangeError("q must be an integer in [0, 40]");
  }
  return BigInt(Math.round(value * 2 ** q));
}

export function fromTicks(ticks: bigint, q: number): number {
  return Number(ticks) / 2 ** q;
}

export class AdditiveCoupling {
  f: TickFunction;
  g: TickFunction;
  split: number;

  constructor(f: TickFunction, g: TickFunction, split: number) {
    if (!Number.isInteger(split) || split <= 0) {
      throw new RangeError("split must be a positive integer");
    }
    this.f = f;
    this.g = g;
    this.split = split;
  }

  forward(z: TickVector, context: Record<string, unknown> = {}): TickVector {
    this.assertShape(z);
    const u = z.slice(0, this.split);
    const v = z.slice(this.split);
    const du = this.f(v, context);
    const uNext = addTicks(u, du);
    const dv = this.g(uNext, context);
    const vNext = addTicks(v, dv);
    return [...uNext, ...vNext];
  }

  inverse(zNext: TickVector, context: Record<string, unknown> = {}): TickVector {
    this.assertShape(zNext);
    const uNext = zNext.slice(0, this.split);
    const vNext = zNext.slice(this.split);
    const dv = this.g(uNext, context);
    const v = subTicks(vNext, dv);
    const du = this.f(v, context);
    const u = subTicks(uNext, du);
    return [...u, ...v];
  }

  cycleOk(z: TickVector, context: Record<string, unknown> = {}): boolean {
    return equalTicks(this.inverse(this.forward(z, context), context), z);
  }

  private assertShape(z: TickVector): void {
    if (z.length <= this.split) {
      throw new RangeError("tick vector must contain both coupling halves");
    }
  }
}

export function affineForward(z: TickVector, params: AffineCouplingParams): TickVector {
  const coupling = makeAffineCoupling(params);
  return coupling.forward(z);
}

export function affineInverse(zNext: TickVector, params: AffineCouplingParams): TickVector {
  const coupling = makeAffineCoupling(params);
  return coupling.inverse(zNext);
}

export function makeAffineCoupling(params: AffineCouplingParams): AdditiveCoupling {
  return new AdditiveCoupling(
    (v) => v.map((tick) => params.gainF * tick + params.biasF),
    (uNext) => uNext.map((tick) => params.gainG * tick + params.biasG),
    params.split,
  );
}

export function assertI32Ticks(z: TickVector): Int32Array {
  const out = new Int32Array(z.length);
  for (let idx = 0; idx < z.length; idx += 1) {
    assertI32(z[idx], `tick ${idx}`);
    out[idx] = Number(z[idx]);
  }
  return out;
}

export function assertAffineI32Safe(
  z: TickVector,
  params: AffineCouplingParams,
  direction: "forward" | "inverse" = "forward",
): Int32Array {
  assertI32(params.gainF, "gainF");
  assertI32(params.biasF, "biasF");
  assertI32(params.gainG, "gainG");
  assertI32(params.biasG, "biasG");
  const data = assertI32Ticks(z);
  if (z.length !== params.split * 2) {
    throw new RangeError("affine i32 admission requires equal coupling halves");
  }
  const u = z.slice(0, params.split);
  const v = z.slice(params.split);
  if (direction === "forward") {
    for (let idx = 0; idx < params.split; idx += 1) {
      const du = params.gainF * v[idx] + params.biasF;
      assertI32(du, `du ${idx}`);
      const uNext = u[idx] + du;
      assertI32(uNext, `u_next ${idx}`);
      const dv = params.gainG * uNext + params.biasG;
      assertI32(dv, `dv ${idx}`);
      assertI32(v[idx] + dv, `v_next ${idx}`);
    }
  } else {
    for (let idx = 0; idx < params.split; idx += 1) {
      const dv = params.gainG * u[idx] + params.biasG;
      assertI32(dv, `dv ${idx}`);
      const vPrev = v[idx] - dv;
      assertI32(vPrev, `v_prev ${idx}`);
      const du = params.gainF * vPrev + params.biasF;
      assertI32(du, `du ${idx}`);
      assertI32(u[idx] - du, `u_prev ${idx}`);
    }
  }
  return data;
}

export function i32ArrayToTicks(values: Int32Array): TickVector {
  return Array.from(values, (value) => BigInt(value));
}

export class DeltaToken {
  key: string;
  before: unknown;
  after: unknown;

  constructor(key: string, before: unknown, after: unknown) {
    if (!key) {
      throw new RangeError("key must be non-empty");
    }
    this.key = key;
    this.before = before;
    this.after = after;
  }

  get readSet(): Set<string> {
    return new Set([this.key]);
  }

  get writeSet(): Set<string> {
    return new Set([this.key]);
  }

  apply(state: Record<string, unknown>): Record<string, unknown> {
    if (!Object.prototype.hasOwnProperty.call(state, this.key) || canonicalJson(state[this.key]) !== canonicalJson(this.before)) {
      throw new Error(`read mismatch for ${this.key}`);
    }
    return { ...state, [this.key]: this.after };
  }

  inverse(): DeltaToken {
    return new DeltaToken(this.key, this.after, this.before);
  }

  commutesWith(other: DeltaToken): boolean {
    return disjoint(union(this.readSet, this.writeSet), union(other.readSet, other.writeSet));
  }
}

export class BlockToken {
  tokens: DeltaToken[];

  constructor(tokens: DeltaToken[]) {
    this.tokens = [...tokens];
  }

  static of(tokens: DeltaToken[]): BlockToken {
    return new BlockToken(tokens);
  }

  get readSet(): Set<string> {
    const out = new Set<string>();
    for (const token of this.tokens) {
      for (const key of token.readSet) out.add(key);
    }
    return out;
  }

  get writeSet(): Set<string> {
    const out = new Set<string>();
    for (const token of this.tokens) {
      for (const key of token.writeSet) out.add(key);
    }
    return out;
  }

  apply(state: Record<string, unknown>): Record<string, unknown> {
    let current = { ...state };
    for (const token of this.tokens) {
      current = token.apply(current);
    }
    return current;
  }

  inverse(): BlockToken {
    return new BlockToken([...this.tokens].reverse().map((token) => token.inverse()));
  }

  commutesWith(other: BlockToken): boolean {
    return disjoint(union(this.readSet, this.writeSet), union(other.readSet, other.writeSet));
  }
}

export function addTicks(a: TickVector, b: TickVector): TickVector {
  assertSameLength(a, b);
  return a.map((value, idx) => value + b[idx]);
}

export function subTicks(a: TickVector, b: TickVector): TickVector {
  assertSameLength(a, b);
  return a.map((value, idx) => value - b[idx]);
}

export function equalTicks(a: TickVector, b: TickVector): boolean {
  return a.length === b.length && a.every((value, idx) => value === b[idx]);
}

function assertSameLength(a: TickVector, b: TickVector): void {
  if (a.length !== b.length) {
    throw new RangeError("tick vector lengths differ");
  }
}

function assertI32(value: bigint, label: string): void {
  if (value < I32_MIN || value > I32_MAX) {
    throw new RangeError(`${label} is outside signed i32 WebGPU bounds`);
  }
}

function union(left: Set<string>, right: Set<string>): Set<string> {
  return new Set([...left, ...right]);
}

function disjoint(left: Set<string>, right: Set<string>): boolean {
  for (const key of left) {
    if (right.has(key)) {
      return false;
    }
  }
  return true;
}
