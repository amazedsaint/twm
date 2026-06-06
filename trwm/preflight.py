from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Sequence


Matrix = tuple[tuple[float, ...], ...]
Vector = tuple[float, ...]


@dataclass(frozen=True)
class ShapeRankPreflight:
    r90: int
    fits_budget: bool
    energy_at_budget: float
    cumulative_energy: tuple[float, ...]
    component_energy: tuple[float, ...]
    total_energy: float


def shape_rank_preflight(
    target_updates: Iterable[Sequence[float]],
    output_map: Sequence[Sequence[float]] | None = None,
    rank_budget: int = 4,
    threshold: float = 0.90,
) -> ShapeRankPreflight:
    updates = tuple(tuple(float(value) for value in update) for update in target_updates)
    if not updates:
        raise ValueError("target_updates must not be empty")
    width = len(updates[0])
    if width == 0:
        raise ValueError("target update vectors must not be empty")
    if any(len(update) != width for update in updates):
        raise ValueError("all target update vectors must have the same length")
    if any(not isfinite(value) for update in updates for value in update):
        raise ValueError("target update values must be finite")
    if not isinstance(rank_budget, int) or isinstance(rank_budget, bool) or rank_budget < 0:
        raise ValueError("rank_budget must be a non-negative integer")
    if not isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")

    matrix = _normalize_matrix(output_map, width)
    eigenvalues, eigenvectors = _jacobi_eigen_symmetric(_gram(matrix))
    components = sorted(
        (
            max(0.0, eigenvalue)
            * sum(_dot(vector, update) ** 2 for update in updates),
            idx,
        )
        for idx, (eigenvalue, vector) in enumerate(zip(eigenvalues, eigenvectors))
    )
    component_energy = tuple(value for value, _idx in sorted(components, key=lambda row: (-row[0], row[1])))
    total = sum(component_energy)
    if total <= 0:
        cumulative = tuple(0.0 for _ in component_energy)
        r90 = 0
        energy_at_budget = 0.0
    else:
        running = 0.0
        cumulative_values = []
        r90 = len(component_energy)
        for idx, value in enumerate(component_energy, start=1):
            running += value
            ratio = running / total
            cumulative_values.append(ratio)
            if ratio >= threshold and r90 == len(component_energy):
                r90 = idx
        cumulative = tuple(cumulative_values)
        energy_at_budget = cumulative[min(rank_budget, len(cumulative)) - 1] if rank_budget > 0 and cumulative else 0.0
    return ShapeRankPreflight(
        r90=r90,
        fits_budget=r90 <= rank_budget,
        energy_at_budget=energy_at_budget,
        cumulative_energy=cumulative,
        component_energy=component_energy,
        total_energy=total,
    )


def one_hot_updates(labels: Iterable[int], label_count: int) -> tuple[Vector, ...]:
    if label_count <= 0:
        raise ValueError("label_count must be positive")
    updates = []
    for label in labels:
        if not 0 <= label < label_count:
            raise ValueError(f"label outside range: {label}")
        updates.append(tuple(1.0 if idx == label else 0.0 for idx in range(label_count)))
    return tuple(updates)


def identity_output_map(width: int) -> Matrix:
    if width <= 0:
        raise ValueError("width must be positive")
    return tuple(tuple(1.0 if row == col else 0.0 for col in range(width)) for row in range(width))


def _normalize_matrix(output_map: Sequence[Sequence[float]] | None, width: int) -> Matrix:
    if output_map is None:
        return identity_output_map(width)
    matrix = tuple(tuple(float(value) for value in row) for row in output_map)
    if not matrix:
        raise ValueError("output_map must not be empty")
    if any(len(row) != width for row in matrix):
        raise ValueError("output_map column count must match target update width")
    if any(not isfinite(value) for row in matrix for value in row):
        raise ValueError("output_map values must be finite")
    return matrix


def _gram(matrix: Matrix) -> Matrix:
    cols = len(matrix[0])
    return tuple(
        tuple(sum(row[i] * row[j] for row in matrix) for j in range(cols))
        for i in range(cols)
    )


def _jacobi_eigen_symmetric(matrix: Matrix, max_sweeps: int = 80, tolerance: float = 1e-12) -> tuple[Vector, tuple[Vector, ...]]:
    n = len(matrix)
    if n == 0 or any(len(row) != n for row in matrix):
        raise ValueError("matrix must be square")
    a = [list(row) for row in matrix]
    vectors = [[1.0 if row == col else 0.0 for col in range(n)] for row in range(n)]
    for _sweep in range(max_sweeps):
        p, q, max_value = 0, 1 if n > 1 else 0, 0.0
        for i in range(n):
            for j in range(i + 1, n):
                value = abs(a[i][j])
                if value > max_value:
                    p, q, max_value = i, j, value
        if max_value < tolerance:
            break
        if a[p][p] == a[q][q]:
            angle = 0.7853981633974483
        else:
            angle = 0.5 * _atan2(2.0 * a[p][q], a[q][q] - a[p][p])
        c = _cos(angle)
        s = _sin(angle)
        app = c * c * a[p][p] - 2.0 * s * c * a[p][q] + s * s * a[q][q]
        aqq = s * s * a[p][p] + 2.0 * s * c * a[p][q] + c * c * a[q][q]
        a[p][p] = app
        a[q][q] = aqq
        a[p][q] = 0.0
        a[q][p] = 0.0
        for k in range(n):
            if k in {p, q}:
                continue
            akp = c * a[k][p] - s * a[k][q]
            akq = s * a[k][p] + c * a[k][q]
            a[k][p] = a[p][k] = akp
            a[k][q] = a[q][k] = akq
        for k in range(n):
            vkp = c * vectors[k][p] - s * vectors[k][q]
            vkq = s * vectors[k][p] + c * vectors[k][q]
            vectors[k][p] = vkp
            vectors[k][q] = vkq
    values = tuple(a[i][i] for i in range(n))
    columns = tuple(tuple(vectors[row][col] for row in range(n)) for col in range(n))
    return values, columns


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _atan2(y: float, x: float) -> float:
    # Local import keeps the public dependency footprint obvious.
    from math import atan2

    return atan2(y, x)


def _cos(x: float) -> float:
    from math import cos

    return cos(x)


def _sin(x: float) -> float:
    from math import sin

    return sin(x)
