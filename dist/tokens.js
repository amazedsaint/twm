









export function applyDelta                                        (state        , token            )         {
  if (!Object.is(state[token.key], token.before)) {
    throw new Error(`read mismatch for ${token.key}`);
  }
  return { ...state, [token.key]: token.after };
}

export function inverseDelta   (token               )                {
  return { key: token.key, before: token.after, after: token.before };
}

export function deltaCommutes(a            , b            )          {
  return a.key !== b.key;
}

export function applyBlock                                        (state        , block            )         {
  return block.tokens.reduce((current, token) => applyDelta(current, token), state);
}

export function inverseBlock   (block               )                {
  return { tokens: [...block.tokens].reverse().map((token) => inverseDelta(token)) };
}

export function blockCommutes(a            , b            )          {
  const keys = new Set(a.tokens.map((token) => token.key));
  return b.tokens.every((token) => !keys.has(token.key));
}

