from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .core import Receipt, TypedCandidate


ProgramStep = Mapping[str, Any]


def evaluate_program(steps: Iterable[ProgramStep], start: int = 0) -> int:
    value = start
    for step in steps:
        op = step.get("op")
        arg = step.get("value")
        if not isinstance(arg, int):
            raise TypeError("program step value must be an integer")
        if op == "set":
            value = arg
        elif op == "add":
            value += arg
        else:
            raise ValueError(f"unsupported program op: {op!r}")
    return value


def program_cost(steps: Iterable[ProgramStep]) -> int:
    return sum(1 for _ in steps)


@dataclass(frozen=True)
class RepairProposal:
    candidate: TypedCandidate
    action: Mapping[str, Any]


class ResidualProgramRepairer:
    """Learns residual-to-program repair macros from ledger receipts.

    It can propose candidate repairs, but it never supplies commit authority.
    The repaired candidate must still pass the hard verifier and replay gates.
    """

    def __init__(self) -> None:
        self.accepted_programs: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.repair_actions: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rejected_residuals: Counter[str] = Counter()

    def update(self, receipt: Receipt) -> None:
        bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
        payload = bundle.get("candidate_payload", {})
        payload = payload if isinstance(payload, Mapping) else {}
        context = str(payload.get("context", "global"))
        if receipt.hard_result.accepted:
            self.accepted_programs[context][str(tuple(_steps(payload)))] += 1
            return
        if receipt.hard_result.rejected and isinstance(receipt.hard_result.residual, Mapping):
            residual = receipt.hard_result.residual
            self.rejected_residuals[str(residual.get("kind", "unknown"))] += 1
            repair = residual.get("repair")
            if isinstance(repair, Mapping):
                self.repair_actions[context][str(dict(repair))] += 1

    def propose(self, candidate: TypedCandidate) -> RepairProposal | None:
        payload = candidate.payload if isinstance(candidate.payload, Mapping) else {}
        residual = payload.get("residual")
        if not isinstance(residual, Mapping):
            return None
        repair = residual.get("repair")
        if not isinstance(repair, Mapping):
            return None
        op = repair.get("op")
        value = repair.get("value")
        if op not in {"add", "set"} or not isinstance(value, int):
            return None
        repaired_payload = {
            **payload,
            "program": [*_steps(payload), {"op": op, "value": value}],
        }
        repaired_payload.pop("residual", None)
        repaired_payload["output"] = evaluate_program(repaired_payload["program"], int(repaired_payload.get("start", 0)))
        return RepairProposal(
            candidate=TypedCandidate(
                payload=repaired_payload,
                type_name=candidate.type_name,
                schema_version=candidate.schema_version,
                hashes=dict(candidate.hashes),
            ),
            action={"op": op, "value": value},
        )


def attach_residual(candidate: TypedCandidate, residual: Mapping[str, Any]) -> TypedCandidate:
    if not isinstance(candidate.payload, Mapping):
        raise TypeError("repair candidate payload must be a mapping")
    return TypedCandidate(
        payload={**candidate.payload, "residual": dict(residual)},
        type_name=candidate.type_name,
        schema_version=candidate.schema_version,
        hashes=dict(candidate.hashes),
    )


def _steps(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    steps = payload.get("program", ())
    if not isinstance(steps, Iterable) or isinstance(steps, (str, bytes, Mapping)):
        raise TypeError("program must be an iterable of steps")
    out = []
    for step in steps:
        if not isinstance(step, Mapping):
            raise TypeError("program step must be a mapping")
        out.append(dict(step))
    return tuple(out)
