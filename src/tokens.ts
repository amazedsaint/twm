export interface DeltaToken<T = unknown> {
  key: string;
  before: T;
  after: T;
}

export interface BlockToken<T = unknown> {
  tokens: DeltaToken<T>[];
}

export function applyDelta<TState extends Record<string, unknown>>(state: TState, token: DeltaToken): TState {
  if (!Object.is(state[token.key], token.before)) {
    throw new Error(`read mismatch for ${token.key}`);
  }
  return { ...state, [token.key]: token.after };
}

export function inverseDelta<T>(token: DeltaToken<T>): DeltaToken<T> {
  return { key: token.key, before: token.after, after: token.before };
}

export function deltaCommutes(a: DeltaToken, b: DeltaToken): boolean {
  return a.key !== b.key;
}

export function applyBlock<TState extends Record<string, unknown>>(state: TState, block: BlockToken): TState {
  return block.tokens.reduce((current, token) => applyDelta(current, token), state);
}

export function inverseBlock<T>(block: BlockToken<T>): BlockToken<T> {
  return { tokens: [...block.tokens].reverse().map((token) => inverseDelta(token)) };
}

export function blockCommutes(a: BlockToken, b: BlockToken): boolean {
  const keys = new Set(a.tokens.map((token) => token.key));
  return b.tokens.every((token) => !keys.has(token.key));
}

