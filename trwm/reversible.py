from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping


TickVector = tuple[int, ...]
TickFunction = Callable[[TickVector, Mapping[str, Any]], TickVector]


def _add(a: TickVector, b: TickVector) -> TickVector:
    if len(a) != len(b):
        raise ValueError("tick vector lengths differ")
    return tuple(x + y for x, y in zip(a, b))


def _sub(a: TickVector, b: TickVector) -> TickVector:
    if len(a) != len(b):
        raise ValueError("tick vector lengths differ")
    return tuple(x - y for x, y in zip(a, b))


def quantize_to_ticks(value: float, q: int) -> int:
    scale = 1 << q
    return round(value * scale)


@dataclass(frozen=True)
class AdditiveCoupling:
    """Exact reversible additive coupling over integer dyadic ticks."""

    f: TickFunction
    g: TickFunction
    split: int

    def forward(self, z: TickVector, context: Mapping[str, Any] | None = None) -> TickVector:
        context = context or {}
        u, v = z[: self.split], z[self.split :]
        du = self.f(v, context)
        u_next = _add(u, du)
        dv = self.g(u_next, context)
        v_next = _add(v, dv)
        return u_next + v_next

    def inverse(self, z_next: TickVector, context: Mapping[str, Any] | None = None) -> TickVector:
        context = context or {}
        u_next, v_next = z_next[: self.split], z_next[self.split :]
        dv = self.g(u_next, context)
        v = _sub(v_next, dv)
        du = self.f(v, context)
        u = _sub(u_next, du)
        return u + v

    def cycle_ok(self, z: TickVector, context: Mapping[str, Any] | None = None) -> bool:
        return self.inverse(self.forward(z, context), context) == z


@dataclass(frozen=True)
class DeltaToken:
    key: str
    before: Any
    after: Any

    @property
    def read_set(self) -> frozenset[str]:
        return frozenset({self.key})

    @property
    def write_set(self) -> frozenset[str]:
        return frozenset({self.key})

    def apply(self, state: Mapping[str, Any]) -> dict[str, Any]:
        if self.key not in state or state[self.key] != self.before:
            raise ValueError(f"read mismatch for {self.key}")
        next_state = dict(state)
        next_state[self.key] = self.after
        return next_state

    def inverse(self) -> "DeltaToken":
        return DeltaToken(self.key, self.after, self.before)

    def commutes_with(self, other: "DeltaToken") -> bool:
        touched = self.read_set | self.write_set
        other_touched = other.read_set | other.write_set
        return touched.isdisjoint(other_touched)


@dataclass(frozen=True)
class BlockToken:
    tokens: tuple[DeltaToken, ...]

    @classmethod
    def of(cls, tokens: Iterable[DeltaToken]) -> "BlockToken":
        return cls(tuple(tokens))

    @property
    def read_set(self) -> frozenset[str]:
        out: set[str] = set()
        for token in self.tokens:
            out.update(token.read_set)
        return frozenset(out)

    @property
    def write_set(self) -> frozenset[str]:
        out: set[str] = set()
        for token in self.tokens:
            out.update(token.write_set)
        return frozenset(out)

    def apply(self, state: Mapping[str, Any]) -> dict[str, Any]:
        current = dict(state)
        for token in self.tokens:
            current = token.apply(current)
        return current

    def inverse(self) -> "BlockToken":
        return BlockToken(tuple(token.inverse() for token in reversed(self.tokens)))

    def commutes_with(self, other: "BlockToken") -> bool:
        touched = self.read_set | self.write_set
        other_touched = other.read_set | other.write_set
        return touched.isdisjoint(other_touched)
