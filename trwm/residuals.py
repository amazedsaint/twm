from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Iterable, Mapping

from .core import Receipt, canonical_json, stable_hash


RESIDUAL_SCHEMA = "trwm.residual.v1"
RESIDUAL_CATEGORIES = (
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
)

KIND_CATEGORY: Mapping[str, str] = {
    "none": "none",
    "schema_error": "schema",
    "duplicate_order": "constraint",
    "over_reservation": "resource",
    "stock_shortage": "resource",
    "diff_mismatch": "constraint",
    "accounting_mismatch": "constraint",
    "unsatisfied_clause": "constraint",
    "goal_not_derived": "constraint",
    "missing_premise": "constraint",
    "formula_mismatch": "constraint",
    "valence_exceeded": "constraint",
    "truth_table_mismatch": "equivalence",
    "test_failure": "test",
    "operator_mismatch": "test",
    "collision": "safety",
    "speed_limit_exceeded": "safety",
    "stopping_distance_violation": "safety",
    "illegal_move": "constraint",
    "projection_contract_violation": "coverage",
    "projection_contract_missing_fields": "coverage",
    "field_hash_mismatch": "coverage",
    "missing_fields": "coverage",
    "verifier_budget_exhausted": "budget",
    "verifier_false_positive": "safety",
    "primary_verifier_mismatch": "coverage",
    "audit_verifier_mismatch": "coverage",
    "candidate_rejected": "constraint",
    "wrong_domain": "schema",
}

FIELD_KEYS = (
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
)

REPAIR_KEYS = (
    "repair",
    "repair_hint",
    "repair_hints",
    "suggested_repair",
    "suggested_action",
    "hint",
    "replacement",
    "expected",
)


@dataclass(frozen=True)
class ResidualSignal:
    schema_version: str
    status: str
    kind: str
    category: str
    verifier_id: str
    verifier_version: str
    residual_hash: str
    source_domain: str = ""
    fields: tuple[str, ...] = ()
    repair_hints: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)
    receipt_hash: str = ""
    candidate_hash: str = ""
    signal_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != RESIDUAL_SCHEMA:
            raise ValueError(f"invalid residual schema: {self.schema_version}")
        if self.status not in {"accept", "reject", "abstain"}:
            raise ValueError(f"invalid residual status: {self.status}")
        if self.category not in RESIDUAL_CATEGORIES:
            raise ValueError(f"invalid residual category: {self.category}")
        object.__setattr__(self, "kind", _snake_case(self.kind or "unknown"))
        object.__setattr__(self, "fields", tuple(_unique(str(field) for field in self.fields if str(field))))
        object.__setattr__(self, "repair_hints", tuple(_unique(str(hint) for hint in self.repair_hints if str(hint))))
        object.__setattr__(self, "attributes", _normalize_mapping(self.attributes))
        if not self.signal_hash:
            object.__setattr__(self, "signal_hash", residual_signal_hash(self))


class ResidualTaxonomyMemory:
    def __init__(self) -> None:
        self.category_counts: dict[str, int] = {}
        self.kind_counts: dict[str, int] = {}
        self.hint_counts: dict[str, dict[str, int]] = {}

    def update(self, signal: ResidualSignal) -> None:
        if not validate_residual_signal(signal):
            raise ValueError("invalid residual signal")
        self.category_counts[signal.category] = self.category_counts.get(signal.category, 0) + 1
        self.kind_counts[signal.kind] = self.kind_counts.get(signal.kind, 0) + 1
        for hint in signal.repair_hints:
            row = self.hint_counts.setdefault(signal.kind, {})
            row[hint] = row.get(hint, 0) + 1

    def rank_categories(self) -> tuple[str, ...]:
        return tuple(key for key, _ in sorted(self.category_counts.items(), key=lambda row: (-row[1], row[0])))

    def rank_kinds(self) -> tuple[str, ...]:
        return tuple(key for key, _ in sorted(self.kind_counts.items(), key=lambda row: (-row[1], row[0])))

    def top_repair_hint(self, kind: str) -> str | None:
        row = self.hint_counts.get(_snake_case(kind), {})
        if not row:
            return None
        return sorted(row.items(), key=lambda item: (-item[1], item[0]))[0][0]


def residual_signal_from_receipt(receipt: Receipt, *, source_domain: str = "") -> ResidualSignal:
    return normalize_residual(
        receipt.hard_result.residual,
        status=receipt.hard_result.result,
        verifier_id=receipt.hard_result.verifier_id,
        verifier_version=receipt.hard_result.verifier_version,
        receipt_hash=receipt.receipt_hash,
        candidate_hash=receipt.typed_candidate_hash,
        source_domain=source_domain,
    )


def normalize_residual(
    residual: Any,
    *,
    status: str,
    verifier_id: str,
    verifier_version: str,
    receipt_hash: str = "",
    candidate_hash: str = "",
    source_domain: str = "",
) -> ResidualSignal:
    if residual is None:
        normalized: Mapping[str, Any] = {}
        kind = "none"
    elif isinstance(residual, Mapping):
        normalized = _normalize_mapping(residual)
        kind = _snake_case(str(normalized.get("kind", "unknown")))
    else:
        normalized = {"message": str(residual)}
        kind = "unknown"
    category = KIND_CATEGORY.get(kind, "unknown")
    return ResidualSignal(
        schema_version=RESIDUAL_SCHEMA,
        status=status,
        kind=kind,
        category=category,
        verifier_id=str(verifier_id),
        verifier_version=str(verifier_version),
        source_domain=str(source_domain),
        fields=_extract_fields(normalized),
        repair_hints=_extract_repair_hints(normalized),
        attributes={key: value for key, value in normalized.items() if key != "kind"},
        residual_hash=stable_hash(residual),
        receipt_hash=str(receipt_hash),
        candidate_hash=str(candidate_hash),
    )


def residual_signal_hash(signal: ResidualSignal) -> str:
    data = asdict(signal)
    data.pop("signal_hash", None)
    return stable_hash(data)


def residual_learning_hash(signal: ResidualSignal) -> str:
    return stable_hash(
        {
            "schema_version": signal.schema_version,
            "status": signal.status,
            "kind": signal.kind,
            "category": signal.category,
            "fields": signal.fields,
            "repair_hints": signal.repair_hints,
            "attributes": signal.attributes,
        }
    )


def validate_residual_signal(signal: ResidualSignal) -> bool:
    if signal.schema_version != RESIDUAL_SCHEMA:
        return False
    if signal.status not in {"accept", "reject", "abstain"}:
        return False
    if signal.category not in RESIDUAL_CATEGORIES:
        return False
    if len(signal.residual_hash) != 64:
        return False
    return signal.signal_hash == residual_signal_hash(signal)


def _normalize_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        normalized_key = _snake_case(str(key))
        if normalized_key in out:
            normalized_value = _normalize_value(value)
            if canonical_json(out[normalized_key]) != canonical_json(normalized_value):
                raise ValueError(f"residual key collision after normalization: {normalized_key}")
            continue
        out[normalized_key] = _normalize_value(value)
    return out


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _normalize_mapping(value)
    if isinstance(value, tuple):
        return tuple(_normalize_value(item) for item in value)
    if isinstance(value, list):
        return tuple(_normalize_value(item) for item in value)
    return value


def _extract_fields(residual: Mapping[str, Any]) -> tuple[str, ...]:
    fields: list[str] = []
    for key in FIELD_KEYS:
        if key in residual:
            fields.extend(_flatten_strings(residual[key]))
    return tuple(_unique(fields))


def _extract_repair_hints(residual: Mapping[str, Any]) -> tuple[str, ...]:
    hints: list[str] = []
    for key in REPAIR_KEYS:
        if key in residual:
            hints.extend(_flatten_repair_hint(key, residual[key]))
    return tuple(_unique(hints))


def _flatten_repair_hint(key: str, value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for nested_key, nested_value in _normalize_mapping(value).items():
            yield f"{nested_key}={nested_value}"
        return
    for item in _flatten_strings(value):
        yield f"{key}={item}" if key not in {"hint", "repair_hint", "suggested_action"} else item


def _flatten_strings(value: Any) -> Iterable[str]:
    if value is None:
        return ()
    if isinstance(value, (str, int, float, bool)):
        return (str(value),)
    if isinstance(value, Mapping):
        return tuple(f"{_snake_case(str(key))}={item}" for key, val in value.items() for item in _flatten_strings(val))
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value)
    return (str(value),)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return tuple(out)


def _snake_case(value: str) -> str:
    value = value.replace("-", "_").replace(".", "_").replace(" ", "_")
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"__+", "_", value)
    return value.strip("_").lower() or "unknown"
