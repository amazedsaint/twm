from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from .core import Receipt, stable_hash


REDACTION_SCHEMA = "trwm.redacted_receipt.v1"
REDACTION_POLICY_SCHEMA = "trwm.redaction_policy.v1"
REDACTION_COMMITMENT_SCHEMA = "trwm.redaction_commitment.v1"
REDACTION_MARKER_SCHEMA = "trwm.redaction_marker.v1"

DISALLOWED_REDACTION_PATHS = frozenset(
    {
        "receipt_hash",
        "receiptHash",
        "parent_head",
        "parentHead",
        "commit_decision",
        "commitDecision",
        "committed",
        "hard_result.result",
        "hardResult.result",
        "hard_result.verifier_id",
        "hardResult.verifierId",
        "hard_result.verifier_version",
        "hardResult.verifierVersion",
        "receipt_schema",
        "receiptSchema",
    }
)


@dataclass(frozen=True)
class RedactionPolicy:
    paths: tuple[str, ...]
    policy_id: str = "receipt.redaction"
    schema_version: str = REDACTION_POLICY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != REDACTION_POLICY_SCHEMA:
            raise ValueError(f"invalid redaction policy schema: {self.schema_version}")
        paths = tuple(str(path) for path in self.paths)
        if not paths:
            raise ValueError("redaction policy requires at least one path")
        if len(set(paths)) != len(paths):
            raise ValueError("redaction policy paths must be unique")
        for path in paths:
            _validate_redaction_path(path)
        object.__setattr__(self, "paths", paths)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "paths": self.paths,
        }

    @property
    def policy_hash(self) -> str:
        return redaction_policy_hash(self)


@dataclass(frozen=True)
class RedactionCommitment:
    path: str
    commitment_hash: str
    marker_hash: str
    schema_version: str = REDACTION_COMMITMENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != REDACTION_COMMITMENT_SCHEMA:
            raise ValueError(f"invalid redaction commitment schema: {self.schema_version}")


@dataclass(frozen=True)
class RedactedReceiptView:
    original_receipt_hash: str
    redaction_policy: Mapping[str, Any]
    policy_hash: str
    redacted_payload: Mapping[str, Any]
    commitments: tuple[RedactionCommitment, ...]
    schema_version: str = REDACTION_SCHEMA
    redacted_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != REDACTION_SCHEMA:
            raise ValueError(f"invalid redacted receipt schema: {self.schema_version}")
        if not self.redacted_hash:
            object.__setattr__(self, "redacted_hash", redacted_receipt_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("redacted_hash", None)
        return data


def redaction_policy_hash(policy: RedactionPolicy | Mapping[str, Any]) -> str:
    normalized = _coerce_policy(policy)
    return stable_hash(normalized.to_public_dict())


def redaction_commitment_hash(path: str, value: Any, salt: str) -> str:
    _validate_redaction_path(path)
    return stable_hash(
        {
            "schema_version": REDACTION_COMMITMENT_SCHEMA,
            "path": path,
            "salt": str(salt),
            "value": value,
        }
    )


def redact_receipt(receipt: Receipt | Mapping[str, Any], policy: RedactionPolicy | Mapping[str, Any], salt: str) -> RedactedReceiptView:
    normalized_policy = _coerce_policy(policy)
    payload = _receipt_payload(receipt)
    original_hash = _original_receipt_hash(payload)
    commitments: list[RedactionCommitment] = []
    for path in normalized_policy.paths:
        exists, value = _get_path(payload, path)
        if not exists:
            raise KeyError(f"redaction path not found: {path}")
        commitment_hash = redaction_commitment_hash(path, value, salt)
        marker = _redaction_marker(path, commitment_hash)
        _set_path(payload, path, marker)
        commitments.append(
            RedactionCommitment(
                path=path,
                commitment_hash=commitment_hash,
                marker_hash=stable_hash(marker),
            )
        )
    return RedactedReceiptView(
        original_receipt_hash=original_hash,
        redaction_policy=normalized_policy.to_public_dict(),
        policy_hash=normalized_policy.policy_hash,
        redacted_payload=payload,
        commitments=tuple(commitments),
    )


def redacted_receipt_hash(view: RedactedReceiptView | Mapping[str, Any]) -> str:
    data = _view_without_hash(view)
    return stable_hash(data)


def validate_redacted_receipt(view: RedactedReceiptView | Mapping[str, Any]) -> bool:
    try:
        data = _view_mapping(view)
        if data.get("schema_version") != REDACTION_SCHEMA:
            return False
        if not _is_hex_hash(str(data.get("original_receipt_hash", ""))):
            return False
        policy = _coerce_policy(data.get("redaction_policy", {}))
        if data.get("policy_hash") != policy.policy_hash:
            return False
        commitments = tuple(_coerce_commitment(item) for item in data.get("commitments", ()))
        if tuple(commitment.path for commitment in commitments) != policy.paths:
            return False
        if data.get("redacted_hash") != redacted_receipt_hash(data):
            return False
        payload = data.get("redacted_payload")
        if not isinstance(payload, Mapping):
            return False
        for commitment in commitments:
            exists, marker = _get_path(payload, commitment.path)
            if not exists or not isinstance(marker, Mapping):
                return False
            if marker != _redaction_marker(commitment.path, commitment.commitment_hash):
                return False
            if stable_hash(marker) != commitment.marker_hash:
                return False
        return True
    except Exception:
        return False


def verify_redacted_path(view: RedactedReceiptView | Mapping[str, Any], path: str, value: Any, salt: str) -> bool:
    if not validate_redacted_receipt(view):
        return False
    data = _view_mapping(view)
    for commitment in (_coerce_commitment(item) for item in data.get("commitments", ())):
        if commitment.path == path:
            return commitment.commitment_hash == redaction_commitment_hash(path, value, salt)
    return False


def redacted_receipt_cannot_replay(view: RedactedReceiptView | Mapping[str, Any]) -> bool:
    data = _view_mapping(view)
    payload = data.get("redacted_payload", {})
    if not isinstance(payload, Mapping):
        return True
    for key in ("replay_bundle", "replayBundle", "rollback_bundle", "rollbackBundle"):
        if key in payload and _contains_redaction_marker(payload[key]):
            return True
    return False


def _coerce_policy(policy: RedactionPolicy | Mapping[str, Any]) -> RedactionPolicy:
    if isinstance(policy, RedactionPolicy):
        return policy
    if not isinstance(policy, Mapping):
        raise TypeError("redaction policy must be a RedactionPolicy or mapping")
    return RedactionPolicy(
        paths=tuple(str(path) for path in policy.get("paths", ())),
        policy_id=str(policy.get("policy_id", "receipt.redaction")),
        schema_version=str(policy.get("schema_version", REDACTION_POLICY_SCHEMA)),
    )


def _coerce_commitment(value: RedactionCommitment | Mapping[str, Any]) -> RedactionCommitment:
    if isinstance(value, RedactionCommitment):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("redaction commitment must be a RedactionCommitment or mapping")
    return RedactionCommitment(
        path=str(value.get("path", "")),
        commitment_hash=str(value.get("commitment_hash", "")),
        marker_hash=str(value.get("marker_hash", "")),
        schema_version=str(value.get("schema_version", REDACTION_COMMITMENT_SCHEMA)),
    )


def _receipt_payload(receipt: Receipt | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(receipt, Receipt):
        payload = receipt.without_hash()
        payload["receipt_hash"] = receipt.receipt_hash
    elif isinstance(receipt, Mapping):
        payload = dict(receipt)
    else:
        raise TypeError("receipt must be a Receipt or mapping")
    return deepcopy(payload)


def _original_receipt_hash(payload: Mapping[str, Any]) -> str:
    value = str(payload.get("receipt_hash") or payload.get("receiptHash") or "")
    if not _is_hex_hash(value):
        raise ValueError("redacted receipt view requires a finalized original receipt hash")
    return value


def _validate_redaction_path(path: str) -> None:
    if not path or path.strip() != path:
        raise ValueError("redaction paths must be non-empty and trimmed")
    if ".." in path or any(not part for part in path.split(".")):
        raise ValueError(f"invalid redaction path: {path}")
    if path in DISALLOWED_REDACTION_PATHS:
        raise ValueError(f"redaction path must stay visible for auditability: {path}")


def _redaction_marker(path: str, commitment_hash: str) -> dict[str, Any]:
    return {
        "schema_version": REDACTION_MARKER_SCHEMA,
        "redacted": True,
        "path": path,
        "commitment_hash": commitment_hash,
    }


def _get_path(root: Any, path: str) -> tuple[bool, Any]:
    current = root
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return False, None
            current = current[part]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            if not part.isdigit():
                return False, None
            idx = int(part)
            if idx < 0 or idx >= len(current):
                return False, None
            current = current[idx]
        else:
            return False, None
    return True, current


def _set_path(root: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    current = root
    for part in parts[:-1]:
        if isinstance(current, Mapping):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(f"redaction path not settable: {path}")
    leaf = parts[-1]
    if isinstance(current, dict):
        current[leaf] = value
    elif isinstance(current, list):
        current[int(leaf)] = value
    else:
        raise KeyError(f"redaction path not settable: {path}")


def _contains_redaction_marker(value: Any) -> bool:
    if isinstance(value, Mapping):
        if value.get("schema_version") == REDACTION_MARKER_SCHEMA and value.get("redacted") is True:
            return True
        return any(_contains_redaction_marker(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_redaction_marker(item) for item in value)
    return False


def _view_mapping(view: RedactedReceiptView | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(view, RedactedReceiptView):
        return asdict(view)
    if isinstance(view, Mapping):
        return view
    raise TypeError("redacted receipt view must be a RedactedReceiptView or mapping")


def _view_without_hash(view: RedactedReceiptView | Mapping[str, Any]) -> dict[str, Any]:
    data = dict(_view_mapping(view))
    data.pop("redacted_hash", None)
    return data


def _is_hex_hash(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)
