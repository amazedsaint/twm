export type NumericVector = number[];
export type NumericMatrix = number[][];

export interface ShapeRankPreflight {
  r90: number;
  fitsBudget: boolean;
  energyAtBudget: number;
  cumulativeEnergy: number[];
  componentEnergy: number[];
  totalEnergy: number;
}

export function shapeRankPreflight(
  targetUpdates: NumericVector[],
  outputMap?: NumericMatrix,
  rankBudget = 4,
  threshold = 0.9,
): ShapeRankPreflight {
  if (targetUpdates.length === 0) {
    throw new RangeError("targetUpdates must not be empty");
  }
  const width = targetUpdates[0].length;
  if (width === 0) {
    throw new RangeError("target update vectors must not be empty");
  }
  if (targetUpdates.some((update) => update.length !== width)) {
    throw new RangeError("all target update vectors must have the same length");
  }
  if (targetUpdates.some((update) => update.some((value) => !Number.isFinite(value)))) {
    throw new TypeError("target update values must be finite");
  }
  if (!Number.isInteger(rankBudget) || rankBudget < 0) {
    throw new RangeError("rankBudget must be a non-negative integer");
  }
  if (!Number.isFinite(threshold) || threshold <= 0 || threshold > 1) {
    throw new RangeError("threshold must be in (0, 1]");
  }
  const matrix = normalizeMatrix(outputMap, width);
  const { values, vectors } = jacobiEigenSymmetric(gram(matrix));
  const componentEnergy = values
    .map((value, idx) => Math.max(0, value) * targetUpdates.reduce((sum, update) => {
      const coeff = dot(vectors[idx], update);
      return sum + coeff * coeff;
    }, 0))
    .sort((a, b) => b - a);
  const totalEnergy = componentEnergy.reduce((sum, value) => sum + value, 0);
  let r90 = 0;
  let energyAtBudget = 0;
  const cumulativeEnergy: number[] = [];
  if (totalEnergy > 0) {
    let running = 0;
    r90 = componentEnergy.length;
    for (let idx = 0; idx < componentEnergy.length; idx += 1) {
      running += componentEnergy[idx];
      const ratio = running / totalEnergy;
      cumulativeEnergy.push(ratio);
      if (ratio >= threshold && r90 === componentEnergy.length) {
        r90 = idx + 1;
      }
    }
    energyAtBudget = rankBudget > 0 && cumulativeEnergy.length > 0
      ? cumulativeEnergy[Math.min(rankBudget, cumulativeEnergy.length) - 1]
      : 0;
  }
  return {
    r90,
    fitsBudget: r90 <= rankBudget,
    energyAtBudget,
    cumulativeEnergy,
    componentEnergy,
    totalEnergy,
  };
}

export function oneHotUpdates(labels: number[], labelCount: number): NumericVector[] {
  if (!Number.isInteger(labelCount) || labelCount <= 0) {
    throw new RangeError("labelCount must be a positive integer");
  }
  return labels.map((label) => {
    if (!Number.isInteger(label) || label < 0 || label >= labelCount) {
      throw new RangeError(`label outside range: ${label}`);
    }
    return Array.from({ length: labelCount }, (_unused, idx) => idx === label ? 1 : 0);
  });
}

export function identityOutputMap(width: number): NumericMatrix {
  if (!Number.isInteger(width) || width <= 0) {
    throw new RangeError("width must be a positive integer");
  }
  return Array.from({ length: width }, (_unused, row) =>
    Array.from({ length: width }, (_unusedCol, col) => row === col ? 1 : 0),
  );
}

function normalizeMatrix(outputMap: NumericMatrix | undefined, width: number): NumericMatrix {
  if (!outputMap) {
    return identityOutputMap(width);
  }
  if (outputMap.length === 0 || outputMap.some((row) => row.length !== width)) {
    throw new RangeError("outputMap column count must match target update width");
  }
  return outputMap.map((row) => row.map((value) => {
    if (!Number.isFinite(value)) {
      throw new TypeError("outputMap values must be finite");
    }
    return value;
  }));
}

function gram(matrix: NumericMatrix): NumericMatrix {
  const cols = matrix[0].length;
  return Array.from({ length: cols }, (_unused, i) =>
    Array.from({ length: cols }, (_unusedCol, j) =>
      matrix.reduce((sum, row) => sum + row[i] * row[j], 0),
    ),
  );
}

function jacobiEigenSymmetric(matrix: NumericMatrix, maxSweeps = 80, tolerance = 1e-12): { values: number[]; vectors: NumericVector[] } {
  const n = matrix.length;
  if (n === 0 || matrix.some((row) => row.length !== n)) {
    throw new RangeError("matrix must be square");
  }
  const a = matrix.map((row) => [...row]);
  const basis = Array.from({ length: n }, (_unused, row) =>
    Array.from({ length: n }, (_unusedCol, col) => row === col ? 1 : 0),
  );
  for (let sweep = 0; sweep < maxSweeps; sweep += 1) {
    let p = 0;
    let q = n > 1 ? 1 : 0;
    let maxValue = 0;
    for (let i = 0; i < n; i += 1) {
      for (let j = i + 1; j < n; j += 1) {
        const value = Math.abs(a[i][j]);
        if (value > maxValue) {
          p = i;
          q = j;
          maxValue = value;
        }
      }
    }
    if (maxValue < tolerance) break;
    const angle = a[p][p] === a[q][q]
      ? Math.PI / 4
      : 0.5 * Math.atan2(2 * a[p][q], a[q][q] - a[p][p]);
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    const app = c * c * a[p][p] - 2 * s * c * a[p][q] + s * s * a[q][q];
    const aqq = s * s * a[p][p] + 2 * s * c * a[p][q] + c * c * a[q][q];
    a[p][p] = app;
    a[q][q] = aqq;
    a[p][q] = 0;
    a[q][p] = 0;
    for (let k = 0; k < n; k += 1) {
      if (k === p || k === q) continue;
      const akp = c * a[k][p] - s * a[k][q];
      const akq = s * a[k][p] + c * a[k][q];
      a[k][p] = akp;
      a[p][k] = akp;
      a[k][q] = akq;
      a[q][k] = akq;
    }
    for (let k = 0; k < n; k += 1) {
      const vkp = c * basis[k][p] - s * basis[k][q];
      const vkq = s * basis[k][p] + c * basis[k][q];
      basis[k][p] = vkp;
      basis[k][q] = vkq;
    }
  }
  return {
    values: Array.from({ length: n }, (_unused, idx) => a[idx][idx]),
    vectors: Array.from({ length: n }, (_unused, col) =>
      Array.from({ length: n }, (_unusedRow, row) => basis[row][col]),
    ),
  };
}

function dot(a: NumericVector, b: NumericVector): number {
  return a.reduce((sum, value, idx) => sum + value * b[idx], 0);
}
