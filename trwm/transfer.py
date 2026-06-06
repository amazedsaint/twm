from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from .core import stable_hash


TRANSFER_EVALUATION_CERTIFICATE_SCHEMA = "trwm.transfer_evaluation_certificate.v1"
TRANSFER_EVALUATION_CONCLUSIONS = ("positive_transfer", "negative_transfer", "neutral")
TRANSFER_GUARD_SNAPSHOT_SCHEMA = "trwm.transfer_guard_snapshot.v1"


@dataclass(frozen=True)
class TransferEvaluationCertificate:
    schema_version: str
    claim_id: str
    learner_id: str
    learner_snapshot_hash: str
    source_domains: tuple[str, ...]
    target_domains: tuple[str, ...]
    source_receipt_hashes: tuple[str, ...]
    target_evaluation_receipt_hashes: tuple[str, ...]
    baseline_name: str
    transfer_name: str
    baseline_success_count: int
    transfer_success_count: int
    baseline_verifier_calls: int
    transfer_verifier_calls: int
    same_case_baseline: bool
    hard_commit_only: bool
    invalid_commit_count: int
    ledger_audit: bool
    replay_rollback_rate: float
    source_target_domain_disjoint: bool
    source_target_receipt_disjoint: bool
    success_delta: int
    verifier_call_delta: int
    conclusion: str
    metrics: Mapping[str, Any] = field(default_factory=dict)
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != TRANSFER_EVALUATION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid transfer evaluation schema: {self.schema_version}")
        for field_name in (
            "source_domains",
            "target_domains",
            "source_receipt_hashes",
            "target_evaluation_receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "metrics", dict(self.metrics))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", transfer_evaluation_certificate_hash(self))

    @property
    def positive_transfer(self) -> bool:
        return self.conclusion == "positive_transfer"

    @property
    def negative_transfer_detected(self) -> bool:
        return self.conclusion == "negative_transfer"


@dataclass(frozen=True)
class TransferGuardEntry:
    source_domains: tuple[str, ...]
    target_domain: str
    conclusion: str
    certificate_hash: str
    success_delta: int
    verifier_call_delta: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_domains", tuple(self.source_domains))


@dataclass(frozen=True)
class TransferGuardDecision:
    source_domains: tuple[str, ...]
    target_domain: str
    admitted: bool
    reason: str
    conclusion: str = ""
    certificate_hash: str = ""
    decision_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_domains", tuple(self.source_domains))
        if not self.decision_hash:
            object.__setattr__(self, "decision_hash", transfer_guard_decision_hash(self))


@dataclass(frozen=True)
class TransferGuardSnapshot:
    schema_version: str
    entries: tuple[TransferGuardEntry, ...]
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != TRANSFER_GUARD_SNAPSHOT_SCHEMA:
            raise ValueError(f"invalid transfer guard snapshot schema: {self.schema_version}")
        object.__setattr__(self, "entries", tuple(sorted(self.entries, key=_entry_sort_key)))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", transfer_guard_snapshot_hash(self))


class TransferGuardMemory:
    """Admits source-domain evidence only after validated positive transfer evidence."""

    def __init__(self) -> None:
        self._entries: dict[tuple[tuple[str, ...], str], TransferGuardEntry] = {}

    def update(self, certificate: TransferEvaluationCertificate) -> tuple[TransferGuardEntry, ...]:
        if not validate_transfer_evaluation_certificate(certificate):
            raise ValueError("transfer certificate must validate before guard update")
        rows: list[TransferGuardEntry] = []
        for target_domain in certificate.target_domains:
            entry = TransferGuardEntry(
                source_domains=certificate.source_domains,
                target_domain=target_domain,
                conclusion=certificate.conclusion,
                certificate_hash=certificate.certificate_hash,
                success_delta=certificate.success_delta,
                verifier_call_delta=certificate.verifier_call_delta,
            )
            key = (entry.source_domains, entry.target_domain)
            existing = self._entries.get(key)
            if existing is None or _more_conservative(entry, existing):
                self._entries[key] = entry
            rows.append(self._entries[key])
        return tuple(rows)

    def decide(self, source_domains: Iterable[str], target_domain: str) -> TransferGuardDecision:
        source_rows = _unique_sorted(source_domains)
        target = str(target_domain)
        entry = self._entries.get((source_rows, target))
        if entry is None:
            return TransferGuardDecision(
                source_domains=source_rows,
                target_domain=target,
                admitted=False,
                reason="no_valid_transfer_certificate",
            )
        if entry.conclusion == "positive_transfer":
            return TransferGuardDecision(
                source_domains=source_rows,
                target_domain=target,
                admitted=True,
                reason="positive_transfer_certificate",
                conclusion=entry.conclusion,
                certificate_hash=entry.certificate_hash,
            )
        reason = "negative_transfer_certificate" if entry.conclusion == "negative_transfer" else "neutral_transfer_certificate"
        return TransferGuardDecision(
            source_domains=source_rows,
            target_domain=target,
            admitted=False,
            reason=reason,
            conclusion=entry.conclusion,
            certificate_hash=entry.certificate_hash,
        )

    def snapshot(self) -> TransferGuardSnapshot:
        return TransferGuardSnapshot(schema_version=TRANSFER_GUARD_SNAPSHOT_SCHEMA, entries=tuple(self._entries.values()))


def build_transfer_evaluation_certificate(
    *,
    claim_id: str,
    learner_id: str,
    learner_snapshot_hash: str,
    source_domains: Iterable[str],
    target_domains: Iterable[str],
    source_receipt_hashes: Iterable[str],
    target_evaluation_receipt_hashes: Iterable[str],
    baseline_name: str,
    transfer_name: str,
    baseline_success_count: int,
    transfer_success_count: int,
    baseline_verifier_calls: int,
    transfer_verifier_calls: int,
    same_case_baseline: bool,
    hard_commit_only: bool,
    invalid_commit_count: int,
    ledger_audit: bool,
    replay_rollback_rate: float,
    metrics: Mapping[str, Any] | None = None,
) -> TransferEvaluationCertificate:
    source_domain_rows = _unique_sorted(source_domains)
    target_domain_rows = _unique_sorted(target_domains)
    source_hash_rows = tuple(str(value) for value in source_receipt_hashes)
    target_hash_rows = tuple(str(value) for value in target_evaluation_receipt_hashes)
    success_delta = int(transfer_success_count) - int(baseline_success_count)
    verifier_call_delta = int(transfer_verifier_calls) - int(baseline_verifier_calls)
    return TransferEvaluationCertificate(
        schema_version=TRANSFER_EVALUATION_CERTIFICATE_SCHEMA,
        claim_id=claim_id,
        learner_id=learner_id,
        learner_snapshot_hash=learner_snapshot_hash,
        source_domains=source_domain_rows,
        target_domains=target_domain_rows,
        source_receipt_hashes=source_hash_rows,
        target_evaluation_receipt_hashes=target_hash_rows,
        baseline_name=baseline_name,
        transfer_name=transfer_name,
        baseline_success_count=baseline_success_count,
        transfer_success_count=transfer_success_count,
        baseline_verifier_calls=baseline_verifier_calls,
        transfer_verifier_calls=transfer_verifier_calls,
        same_case_baseline=bool(same_case_baseline),
        hard_commit_only=bool(hard_commit_only),
        invalid_commit_count=invalid_commit_count,
        ledger_audit=bool(ledger_audit),
        replay_rollback_rate=float(replay_rollback_rate),
        source_target_domain_disjoint=not set(source_domain_rows).intersection(target_domain_rows),
        source_target_receipt_disjoint=not set(source_hash_rows).intersection(target_hash_rows),
        success_delta=success_delta,
        verifier_call_delta=verifier_call_delta,
        conclusion=_transfer_conclusion(success_delta, verifier_call_delta),
        metrics=metrics or {},
    )


def transfer_evaluation_certificate_hash(certificate: TransferEvaluationCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, TransferEvaluationCertificate):
        data = asdict(certificate)
    else:
        data = dict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def validate_transfer_evaluation_certificate(certificate: TransferEvaluationCertificate) -> bool:
    try:
        if certificate.schema_version != TRANSFER_EVALUATION_CERTIFICATE_SCHEMA:
            return False
        if certificate.conclusion not in TRANSFER_EVALUATION_CONCLUSIONS:
            return False
        if not all(
            isinstance(value, str) and value
            for value in (
                certificate.claim_id,
                certificate.learner_id,
                certificate.baseline_name,
                certificate.transfer_name,
            )
        ):
            return False
        if not _is_hash(certificate.learner_snapshot_hash):
            return False
        if not _sorted_unique_nonempty(certificate.source_domains):
            return False
        if not _sorted_unique_nonempty(certificate.target_domains):
            return False
        if set(certificate.source_domains).intersection(certificate.target_domains):
            return False
        if not certificate.source_target_domain_disjoint:
            return False
        if not _unique_hashes(certificate.source_receipt_hashes):
            return False
        if not _unique_hashes(certificate.target_evaluation_receipt_hashes):
            return False
        if set(certificate.source_receipt_hashes).intersection(certificate.target_evaluation_receipt_hashes):
            return False
        if not certificate.source_target_receipt_disjoint:
            return False
        count_values = (
            certificate.baseline_success_count,
            certificate.transfer_success_count,
            certificate.baseline_verifier_calls,
            certificate.transfer_verifier_calls,
            certificate.invalid_commit_count,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in count_values):
            return False
        if certificate.baseline_verifier_calls <= 0 or certificate.transfer_verifier_calls <= 0:
            return False
        if certificate.baseline_success_count > certificate.baseline_verifier_calls:
            return False
        if certificate.transfer_success_count > certificate.transfer_verifier_calls:
            return False
        if not isinstance(certificate.same_case_baseline, bool):
            return False
        if not isinstance(certificate.hard_commit_only, bool):
            return False
        if not isinstance(certificate.ledger_audit, bool):
            return False
        if isinstance(certificate.replay_rollback_rate, bool):
            return False
        if not isinstance(certificate.replay_rollback_rate, float) and not isinstance(certificate.replay_rollback_rate, int):
            return False
        if certificate.replay_rollback_rate < 0.0 or certificate.replay_rollback_rate > 1.0:
            return False
        success_delta = certificate.transfer_success_count - certificate.baseline_success_count
        verifier_call_delta = certificate.transfer_verifier_calls - certificate.baseline_verifier_calls
        if certificate.success_delta != success_delta:
            return False
        if certificate.verifier_call_delta != verifier_call_delta:
            return False
        if certificate.conclusion != _transfer_conclusion(success_delta, verifier_call_delta):
            return False
        return certificate.certificate_hash == transfer_evaluation_certificate_hash(certificate)
    except Exception:
        return False


def transfer_evaluation_supports_positive_claim(certificate: TransferEvaluationCertificate) -> bool:
    return (
        validate_transfer_evaluation_certificate(certificate)
        and certificate.conclusion == "positive_transfer"
        and certificate.same_case_baseline
        and certificate.hard_commit_only
        and certificate.invalid_commit_count == 0
        and certificate.ledger_audit
        and certificate.replay_rollback_rate == 1.0
    )


def transfer_evaluation_rejects_positive_claim(certificate: TransferEvaluationCertificate) -> bool:
    return (
        validate_transfer_evaluation_certificate(certificate)
        and certificate.conclusion == "negative_transfer"
        and certificate.same_case_baseline
        and certificate.hard_commit_only
        and certificate.invalid_commit_count == 0
        and certificate.ledger_audit
        and certificate.replay_rollback_rate == 1.0
    )


def transfer_guard_snapshot_hash(snapshot: TransferGuardSnapshot | Mapping[str, Any]) -> str:
    if isinstance(snapshot, TransferGuardSnapshot):
        data = asdict(snapshot)
    else:
        data = dict(snapshot)
    data.pop("snapshot_hash", None)
    return stable_hash(data)


def transfer_guard_decision_hash(decision: TransferGuardDecision | Mapping[str, Any]) -> str:
    if isinstance(decision, TransferGuardDecision):
        data = asdict(decision)
    else:
        data = dict(decision)
    data.pop("decision_hash", None)
    return stable_hash(data)


def validate_transfer_guard_snapshot(snapshot: TransferGuardSnapshot) -> bool:
    try:
        if snapshot.schema_version != TRANSFER_GUARD_SNAPSHOT_SCHEMA:
            return False
        if snapshot.entries != tuple(sorted(snapshot.entries, key=_entry_sort_key)):
            return False
        keys: set[tuple[tuple[str, ...], str]] = set()
        for entry in snapshot.entries:
            if not _sorted_unique_nonempty(entry.source_domains):
                return False
            if not isinstance(entry.target_domain, str) or not entry.target_domain:
                return False
            if entry.target_domain in entry.source_domains:
                return False
            if entry.conclusion not in TRANSFER_EVALUATION_CONCLUSIONS:
                return False
            if not _is_hash(entry.certificate_hash):
                return False
            if not isinstance(entry.success_delta, int) or isinstance(entry.success_delta, bool):
                return False
            if not isinstance(entry.verifier_call_delta, int) or isinstance(entry.verifier_call_delta, bool):
                return False
            if entry.conclusion != _transfer_conclusion(entry.success_delta, entry.verifier_call_delta):
                return False
            key = (entry.source_domains, entry.target_domain)
            if key in keys:
                return False
            keys.add(key)
        return snapshot.snapshot_hash == transfer_guard_snapshot_hash(snapshot)
    except Exception:
        return False


def validate_transfer_guard_decision(decision: TransferGuardDecision) -> bool:
    try:
        if not _sorted_unique_nonempty(decision.source_domains):
            return False
        if not isinstance(decision.target_domain, str) or not decision.target_domain:
            return False
        if decision.target_domain in decision.source_domains:
            return False
        if not isinstance(decision.admitted, bool):
            return False
        if not isinstance(decision.reason, str) or not decision.reason:
            return False
        if decision.conclusion and decision.conclusion not in TRANSFER_EVALUATION_CONCLUSIONS:
            return False
        if decision.certificate_hash and not _is_hash(decision.certificate_hash):
            return False
        if decision.reason == "no_valid_transfer_certificate":
            if decision.admitted or decision.conclusion or decision.certificate_hash:
                return False
        elif decision.reason == "positive_transfer_certificate":
            if not decision.admitted or decision.conclusion != "positive_transfer" or not decision.certificate_hash:
                return False
        elif decision.reason == "negative_transfer_certificate":
            if decision.admitted or decision.conclusion != "negative_transfer" or not decision.certificate_hash:
                return False
        elif decision.reason == "neutral_transfer_certificate":
            if decision.admitted or decision.conclusion != "neutral" or not decision.certificate_hash:
                return False
        else:
            return False
        return decision.decision_hash == transfer_guard_decision_hash(decision)
    except Exception:
        return False


def _transfer_conclusion(success_delta: int, verifier_call_delta: int) -> str:
    if success_delta > 0 or (success_delta == 0 and verifier_call_delta < 0):
        return "positive_transfer"
    if success_delta < 0 or (success_delta == 0 and verifier_call_delta > 0):
        return "negative_transfer"
    return "neutral"


def _entry_sort_key(entry: TransferGuardEntry) -> tuple[str, tuple[str, ...], str]:
    return entry.target_domain, entry.source_domains, entry.certificate_hash


def _more_conservative(candidate: TransferGuardEntry, existing: TransferGuardEntry) -> bool:
    candidate_priority = _conclusion_priority(candidate.conclusion)
    existing_priority = _conclusion_priority(existing.conclusion)
    if candidate_priority != existing_priority:
        return candidate_priority > existing_priority
    if abs(candidate.success_delta) != abs(existing.success_delta):
        return abs(candidate.success_delta) > abs(existing.success_delta)
    if abs(candidate.verifier_call_delta) != abs(existing.verifier_call_delta):
        return abs(candidate.verifier_call_delta) > abs(existing.verifier_call_delta)
    return candidate.certificate_hash < existing.certificate_hash


def _conclusion_priority(conclusion: str) -> int:
    if conclusion == "negative_transfer":
        return 3
    if conclusion == "neutral":
        return 2
    if conclusion == "positive_transfer":
        return 1
    return 0


def _unique_sorted(values: Iterable[str]) -> tuple[str, ...]:
    rows = tuple(sorted(str(value) for value in values if str(value)))
    if len(rows) != len(set(rows)):
        raise ValueError("domains must be unique")
    return rows


def _sorted_unique_nonempty(values: tuple[str, ...]) -> bool:
    return bool(values) and values == tuple(sorted(values)) and len(values) == len(set(values)) and all(isinstance(value, str) and value for value in values)


def _unique_hashes(values: tuple[str, ...]) -> bool:
    return bool(values) and len(values) == len(set(values)) and all(_is_hash(value) for value in values)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
