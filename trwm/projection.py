from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .core import stable_hash


PROJECTION_CONTRACT_SCHEMA = "trwm.projection_contract.v1"
PROJECTION_MANIFEST_SCHEMA = "trwm.projection_manifest.v1"


@dataclass(frozen=True)
class ProjectionContract:
    required_fields: tuple[str, ...]
    contract_id: str = "projection.contract"
    schema_version: str = PROJECTION_CONTRACT_SCHEMA

    def __post_init__(self) -> None:
        fields = _normalize_field_names(self.required_fields)
        if not fields:
            raise ValueError("required_fields must not be empty")
        object.__setattr__(self, "required_fields", fields)
        if not self.contract_id:
            raise ValueError("contract_id must be non-empty")
        if self.schema_version != PROJECTION_CONTRACT_SCHEMA:
            raise ValueError(f"unsupported projection contract schema: {self.schema_version}")


@dataclass(frozen=True)
class ProjectionManifest:
    projector_id: str
    projector_version: str
    source_hash: str
    covered_fields: tuple[str, ...]
    field_hashes: Mapping[str, str]
    projection_hash: str = ""
    schema_version: str = PROJECTION_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        covered = _normalize_field_names(self.covered_fields)
        hashes = {str(key): str(value) for key, value in self.field_hashes.items()}
        object.__setattr__(self, "covered_fields", covered)
        object.__setattr__(self, "field_hashes", hashes)
        if not self.projector_id:
            raise ValueError("projector_id must be non-empty")
        if not self.projector_version:
            raise ValueError("projector_version must be non-empty")
        if self.schema_version != PROJECTION_MANIFEST_SCHEMA:
            raise ValueError(f"unsupported projection manifest schema: {self.schema_version}")
        if set(covered) != set(hashes):
            raise ValueError("field_hashes must match covered_fields")
        expected = _projection_manifest_hash(
            self.schema_version,
            self.projector_id,
            self.projector_version,
            self.source_hash,
            covered,
            hashes,
        )
        if not self.projection_hash:
            object.__setattr__(self, "projection_hash", expected)


@dataclass(frozen=True)
class ProjectionAudit:
    accepted: bool
    missing_fields: tuple[str, ...] = ()
    stale_fields: tuple[str, ...] = ()
    absent_source_fields: tuple[str, ...] = ()
    hash_mismatch: bool = False
    source_hash_mismatch: bool = False

    @property
    def residual(self) -> dict[str, Any]:
        return {
            "kind": "projection_contract_violation",
            "missing_fields": self.missing_fields,
            "stale_fields": self.stale_fields,
            "absent_source_fields": self.absent_source_fields,
            "hash_mismatch": self.hash_mismatch,
            "source_hash_mismatch": self.source_hash_mismatch,
        }


def build_projection_manifest(
    source: Mapping[str, Any],
    covered_fields: Iterable[str],
    *,
    projector_id: str,
    projector_version: str,
) -> ProjectionManifest:
    fields = _normalize_field_names(tuple(covered_fields))
    missing = tuple(field for field in fields if field not in source)
    if missing:
        raise ValueError(f"covered fields not present in source: {missing}")
    field_hashes = {field: field_value_hash(field, source[field]) for field in fields}
    return ProjectionManifest(
        projector_id=projector_id,
        projector_version=projector_version,
        source_hash=source_projection_hash(source),
        covered_fields=fields,
        field_hashes=field_hashes,
    )


def validate_projection_contract(
    contract: ProjectionContract,
    manifest: ProjectionManifest | Mapping[str, Any],
    source: Mapping[str, Any] | None = None,
) -> ProjectionAudit:
    normalized = manifest if isinstance(manifest, ProjectionManifest) else projection_manifest_from_mapping(manifest)
    covered = set(normalized.covered_fields)
    missing = tuple(field for field in contract.required_fields if field not in covered)
    expected_hash = _projection_manifest_hash(
        normalized.schema_version,
        normalized.projector_id,
        normalized.projector_version,
        normalized.source_hash,
        normalized.covered_fields,
        normalized.field_hashes,
    )
    hash_mismatch = bool(normalized.projection_hash and normalized.projection_hash != expected_hash)
    source_hash_mismatch = False
    absent_source_fields: tuple[str, ...] = ()
    stale_fields: tuple[str, ...] = ()
    if source is not None:
        source_hash_mismatch = normalized.source_hash != source_projection_hash(source)
        absent_source_fields = tuple(field for field in contract.required_fields if field not in source)
        stale_fields = tuple(
            field
            for field in contract.required_fields
            if field in source
            and field in normalized.field_hashes
            and normalized.field_hashes[field] != field_value_hash(field, source[field])
        )
    accepted = not missing and not stale_fields and not absent_source_fields and not hash_mismatch and not source_hash_mismatch
    return ProjectionAudit(
        accepted=accepted,
        missing_fields=missing,
        stale_fields=stale_fields,
        absent_source_fields=absent_source_fields,
        hash_mismatch=hash_mismatch,
        source_hash_mismatch=source_hash_mismatch,
    )


def projection_manifest_from_mapping(data: Mapping[str, Any]) -> ProjectionManifest:
    return ProjectionManifest(
        projector_id=str(data["projector_id"]),
        projector_version=str(data["projector_version"]),
        source_hash=str(data["source_hash"]),
        covered_fields=tuple(str(field) for field in data["covered_fields"]),
        field_hashes={str(key): str(value) for key, value in data["field_hashes"].items()},
        projection_hash=str(data.get("projection_hash", "")),
        schema_version=str(data.get("schema_version", PROJECTION_MANIFEST_SCHEMA)),
    )


def source_projection_hash(source: Mapping[str, Any]) -> str:
    return stable_hash({"schema_version": PROJECTION_MANIFEST_SCHEMA, "source": dict(source)})


def field_value_hash(field: str, value: Any) -> str:
    return stable_hash({"field": str(field), "value": value})


def _normalize_field_names(fields: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(str(field) for field in fields)
    if any(not field for field in normalized):
        raise ValueError("field names must be non-empty")
    deduped = tuple(sorted(set(normalized)))
    if len(deduped) != len(normalized):
        raise ValueError("field names must be unique")
    return deduped


def _projection_manifest_hash(
    schema_version: str,
    projector_id: str,
    projector_version: str,
    source_hash: str,
    covered_fields: tuple[str, ...],
    field_hashes: Mapping[str, str],
) -> str:
    return stable_hash(
        {
            "schema_version": schema_version,
            "projector_id": projector_id,
            "projector_version": projector_version,
            "source_hash": source_hash,
            "covered_fields": covered_fields,
            "field_hashes": dict(field_hashes),
        }
    )
