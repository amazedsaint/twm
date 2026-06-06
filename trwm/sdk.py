from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from typing import Any, Iterable, Mapping

from .core import Ledger, ProposalTrace, Receipt, ReplayRollbackAdapter, TransactionEngine, TransactionOutcome, TypedCandidate, stable_hash
from .transfer import (
    TransferEvaluationCertificate,
    TransferGuardDecision,
    TransferGuardMemory,
    TransferGuardSnapshot,
    validate_transfer_guard_decision,
)


SDK_DOMAIN_MANIFEST_SCHEMA = "trwm.sdk_domain_manifest.v1"
TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA = "trwm.transfer_guarded_domain_route.v1"


@dataclass
class DomainRuntime:
    domain_id: str
    adapter: ReplayRollbackAdapter
    ledger: Ledger = field(default_factory=Ledger)
    hard_verifier_calls: int = 0


@dataclass(frozen=True)
class SdkTransactionResult:
    domain_id: str
    outcome: TransactionOutcome
    hard_verifier_calls: int

    @property
    def committed(self) -> bool:
        return self.outcome.committed

    @property
    def receipt(self) -> Receipt:
        return self.outcome.receipt


@dataclass(frozen=True)
class DomainAudit:
    domain_id: str
    ledger_audit: bool
    replay_matches_receipts: bool
    rollback_matches_seed: bool
    invalid_commit_count: int

    @property
    def ok(self) -> bool:
        return self.ledger_audit and self.replay_matches_receipts and self.rollback_matches_seed and self.invalid_commit_count == 0


@dataclass(frozen=True)
class DomainManifestCertificate:
    schema_version: str
    domain_id: str
    adapter_type: str
    verifier_id: str
    verifier_version: str
    candidate_type_names: tuple[str, ...]
    projection_schema_versions: tuple[str, ...]
    model_versions: tuple[str, ...]
    receipt_schema_versions: tuple[str, ...]
    receipt_count: int
    accepted_count: int
    rejected_count: int
    abstained_count: int
    committed_count: int
    hard_verifier_calls: int
    verifier_cost: int
    invalid_commit_count: int
    ledger_head: str
    ledger_audit: bool
    receipt_hashes: tuple[str, ...]
    manifest_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != SDK_DOMAIN_MANIFEST_SCHEMA:
            raise ValueError(f"invalid SDK domain manifest schema: {self.schema_version}")
        for field_name in (
            "candidate_type_names",
            "projection_schema_versions",
            "model_versions",
            "receipt_schema_versions",
            "receipt_hashes",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.manifest_hash:
            object.__setattr__(self, "manifest_hash", domain_manifest_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("manifest_hash", None)
        return data


@dataclass(frozen=True)
class TransferGuardedDomainRoute:
    schema_version: str
    context: str
    source_domains: tuple[str, ...]
    target_domain: str
    input_domain_ids: tuple[str, ...]
    base_ranked_domain_ids: tuple[str, ...]
    ranked_domain_ids: tuple[str, ...]
    blocked_domain_ids: tuple[str, ...]
    decision_reason: str
    decision_admitted: bool
    decision_hash: str
    top_domain_id: str = ""
    source_blocked: bool = False
    route_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA:
            raise ValueError(f"invalid transfer guarded route schema: {self.schema_version}")
        for field_name in (
            "source_domains",
            "input_domain_ids",
            "base_ranked_domain_ids",
            "ranked_domain_ids",
            "blocked_domain_ids",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.top_domain_id:
            object.__setattr__(self, "top_domain_id", self.ranked_domain_ids[0] if self.ranked_domain_ids else "")
        if self.source_blocked != bool(self.blocked_domain_ids):
            object.__setattr__(self, "source_blocked", bool(self.blocked_domain_ids))
        if not self.route_hash:
            object.__setattr__(self, "route_hash", transfer_guarded_domain_route_hash(self))


@dataclass
class VerifierCostStats:
    accepted: int = 0
    rejected: int = 0
    abstained: int = 0
    verifier_cost: int = 0
    calls: int = 0

    @property
    def success_per_cost(self) -> Fraction:
        if self.verifier_cost <= 0:
            return Fraction(0, 1)
        return Fraction(self.accepted, self.verifier_cost)


class ReceiptDomainRouter:
    """Learns domain ordering from receipts, but never supplies commit authority."""

    def __init__(self) -> None:
        self.accepted: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rejected: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def update(self, domain_id: str, context: str, receipt: Receipt) -> None:
        if receipt.committed and receipt.hard_result.accepted:
            self.accepted[context][domain_id] += 1
        elif receipt.hard_result.rejected or receipt.commit_decision != "commit":
            self.rejected[context][domain_id] += 1

    def rank(self, context: str, domain_ids: Iterable[str]) -> list[str]:
        indexed = list(enumerate(domain_ids))

        def key(row: tuple[int, str]) -> tuple[int, int, int]:
            idx, domain_id = row
            return (-self.accepted[context][domain_id], self.rejected[context][domain_id], idx)

        return [domain_id for _, domain_id in sorted(indexed, key=key)]

    def counts(self, context: str, domain_id: str) -> tuple[int, int]:
        return self.accepted[context][domain_id], self.rejected[context][domain_id]


class CostAwareReceiptDomainRouter:
    """Ranks domains by committed successes per verifier-cost unit."""

    def __init__(self, default_verifier_cost: int = 1) -> None:
        if not isinstance(default_verifier_cost, int) or isinstance(default_verifier_cost, bool) or default_verifier_cost <= 0:
            raise ValueError("default_verifier_cost must be a positive integer")
        self.default_verifier_cost = default_verifier_cost
        self.rows: defaultdict[str, defaultdict[str, VerifierCostStats]] = defaultdict(lambda: defaultdict(VerifierCostStats))
        self.invalid_cost_metadata: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def update(self, domain_id: str, context: str, receipt: Receipt) -> None:
        row = self.rows[context][domain_id]
        cost, metadata_ok = verifier_cost_units(receipt, default=self.default_verifier_cost)
        row.calls += 1
        row.verifier_cost += cost
        if not metadata_ok:
            self.invalid_cost_metadata[context][domain_id] += 1
        if receipt.committed and receipt.hard_result.accepted:
            row.accepted += 1
        elif receipt.hard_result.abstained:
            row.abstained += 1
        elif receipt.hard_result.rejected or receipt.commit_decision != "commit":
            row.rejected += 1

    def rank(self, context: str, domain_ids: Iterable[str]) -> list[str]:
        indexed = list(enumerate(domain_ids))

        def key(row: tuple[int, str]) -> tuple[Fraction, int, int, int, int]:
            idx, domain_id = row
            stats = self.stats(context, domain_id)
            return (
                -stats.success_per_cost,
                stats.rejected,
                stats.abstained,
                stats.verifier_cost,
                idx,
            )

        return [domain_id for _, domain_id in sorted(indexed, key=key)]

    def counts(self, context: str, domain_id: str) -> tuple[int, int]:
        row = self.stats(context, domain_id)
        return row.accepted, row.rejected

    def stats(self, context: str, domain_id: str) -> VerifierCostStats:
        return self.rows[context][domain_id]


class TransferGuardedDomainRouter:
    """Routes proposal sources through validated transfer-admission memory."""

    def __init__(
        self,
        base_router: ReceiptDomainRouter | CostAwareReceiptDomainRouter | None = None,
        transfer_guard: TransferGuardMemory | None = None,
    ) -> None:
        self.base_router = base_router or ReceiptDomainRouter()
        self.transfer_guard = transfer_guard or TransferGuardMemory()

    def update(self, domain_id: str, context: str, receipt: Receipt) -> None:
        self.base_router.update(domain_id, context, receipt)

    def rank(self, context: str, domain_ids: Iterable[str]) -> list[str]:
        return self.base_router.rank(context, domain_ids)

    def counts(self, context: str, domain_id: str) -> tuple[int, int]:
        return self.base_router.counts(context, domain_id)

    def update_transfer_certificate(self, certificate: TransferEvaluationCertificate) -> tuple[Any, ...]:
        return self.transfer_guard.update(certificate)

    def guard_snapshot(self) -> TransferGuardSnapshot:
        return self.transfer_guard.snapshot()

    def decide_transfer(self, source_domains: Iterable[str], target_domain: str) -> TransferGuardDecision:
        return self.transfer_guard.decide(source_domains, target_domain)

    def rank_with_transfer_guard(
        self,
        context: str,
        domain_ids: Iterable[str],
        source_domains: Iterable[str],
        target_domain: str,
    ) -> TransferGuardedDomainRoute:
        input_ids = _unique_ordered(domain_ids)
        source_rows = _unique_sorted(source_domains)
        base_ranked = tuple(self.base_router.rank(context, input_ids))
        decision = self.transfer_guard.decide(source_rows, target_domain)
        blocked = () if decision.admitted else tuple(domain_id for domain_id in base_ranked if domain_id in source_rows)
        blocked_set = set(blocked)
        ranked = tuple(domain_id for domain_id in base_ranked if domain_id not in blocked_set) + blocked
        return TransferGuardedDomainRoute(
            schema_version=TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA,
            context=str(context),
            source_domains=source_rows,
            target_domain=str(target_domain),
            input_domain_ids=input_ids,
            base_ranked_domain_ids=base_ranked,
            ranked_domain_ids=ranked,
            blocked_domain_ids=blocked,
            decision_reason=decision.reason,
            decision_admitted=decision.admitted,
            decision_hash=decision.decision_hash,
        )


def verifier_cost_units(receipt: Receipt, *, default: int = 1) -> tuple[int, bool]:
    if not isinstance(default, int) or isinstance(default, bool) or default <= 0:
        raise ValueError("default must be a positive integer")
    metadata = receipt.hard_result.metadata
    if "verifier_cost_spent" in metadata:
        spent = _int_metadata(metadata["verifier_cost_spent"])
        if spent is None:
            return default, False
        if spent == 0 and receipt.hard_result.abstained:
            return 0, True
        if spent > 0:
            return spent, True
        return default, False

    value = metadata.get("verifier_cost", default)
    cost = _int_metadata(value)
    if cost is None or cost <= 0:
        return default, False
    return cost, True


def _int_metadata(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


def build_domain_manifest(runtime: DomainRuntime) -> DomainManifestCertificate:
    rows = tuple(runtime.ledger.rows)
    accepted_count = sum(1 for receipt in rows if receipt.hard_result.accepted)
    rejected_count = sum(1 for receipt in rows if receipt.hard_result.rejected)
    abstained_count = sum(1 for receipt in rows if receipt.hard_result.abstained)
    committed_count = sum(1 for receipt in rows if receipt.committed)
    verifier_cost = sum(verifier_cost_units(receipt)[0] for receipt in rows)
    return DomainManifestCertificate(
        schema_version=SDK_DOMAIN_MANIFEST_SCHEMA,
        domain_id=runtime.domain_id,
        adapter_type=type(runtime.adapter).__name__,
        verifier_id=runtime.adapter.verifier_id,
        verifier_version=runtime.adapter.verifier_version,
        candidate_type_names=_unique_sorted(_receipt_candidate_type(receipt) for receipt in rows),
        projection_schema_versions=_unique_sorted(receipt.projection_schema_version for receipt in rows),
        model_versions=_unique_sorted(receipt.model_version for receipt in rows),
        receipt_schema_versions=_unique_sorted(receipt.receipt_schema for receipt in rows),
        receipt_count=len(rows),
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        abstained_count=abstained_count,
        committed_count=committed_count,
        hard_verifier_calls=runtime.hard_verifier_calls,
        verifier_cost=verifier_cost,
        invalid_commit_count=sum(1 for receipt in rows if receipt.committed and not receipt.hard_result.accepted),
        ledger_head=runtime.ledger.head,
        ledger_audit=runtime.ledger.audit(),
        receipt_hashes=tuple(receipt.receipt_hash for receipt in rows),
    )


def audit_domain_manifest(runtime: DomainRuntime, certificate: DomainManifestCertificate) -> bool:
    try:
        if not validate_domain_manifest(certificate):
            return False
        if not runtime.ledger.audit():
            return False
        rebuilt = build_domain_manifest(runtime)
        return rebuilt.manifest_hash == certificate.manifest_hash
    except Exception:
        return False


def validate_domain_manifest(certificate: DomainManifestCertificate) -> bool:
    try:
        if certificate.schema_version != SDK_DOMAIN_MANIFEST_SCHEMA:
            return False
        if not all(
            isinstance(value, str) and value
            for value in (
                certificate.domain_id,
                certificate.adapter_type,
                certificate.verifier_id,
                certificate.verifier_version,
            )
        ):
            return False
        count_values = (
            certificate.receipt_count,
            certificate.accepted_count,
            certificate.rejected_count,
            certificate.abstained_count,
            certificate.committed_count,
            certificate.hard_verifier_calls,
            certificate.verifier_cost,
            certificate.invalid_commit_count,
        )
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in count_values):
            return False
        if certificate.receipt_count != certificate.accepted_count + certificate.rejected_count + certificate.abstained_count:
            return False
        if certificate.committed_count > certificate.accepted_count:
            return False
        if certificate.hard_verifier_calls < certificate.receipt_count:
            return False
        if certificate.invalid_commit_count != 0:
            return False
        if not certificate.ledger_audit:
            return False
        if not _is_hash(certificate.ledger_head):
            return False
        if len(certificate.receipt_hashes) != certificate.receipt_count:
            return False
        if any(not _is_hash(value) for value in certificate.receipt_hashes):
            return False
        if not _sorted_unique_nonempty_when_receipts(certificate.candidate_type_names, certificate.receipt_count):
            return False
        if not _sorted_unique_nonempty_when_receipts(certificate.projection_schema_versions, certificate.receipt_count):
            return False
        if not _sorted_unique_nonempty_when_receipts(certificate.model_versions, certificate.receipt_count):
            return False
        if not _sorted_unique_nonempty_when_receipts(certificate.receipt_schema_versions, certificate.receipt_count):
            return False
        return certificate.manifest_hash == domain_manifest_hash(certificate)
    except Exception:
        return False


def domain_manifest_hash(certificate: DomainManifestCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, DomainManifestCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("manifest_hash", None)
    return stable_hash(data)


def transfer_guarded_domain_route_hash(route: TransferGuardedDomainRoute | Mapping[str, Any]) -> str:
    if isinstance(route, TransferGuardedDomainRoute):
        data = asdict(route)
    else:
        data = dict(route)
    data.pop("route_hash", None)
    return stable_hash(data)


def validate_transfer_guarded_domain_route(route: TransferGuardedDomainRoute) -> bool:
    try:
        if route.schema_version != TRANSFER_GUARDED_DOMAIN_ROUTE_SCHEMA:
            return False
        if not isinstance(route.context, str) or not route.context:
            return False
        if not _sorted_unique_nonempty(route.source_domains):
            return False
        if not isinstance(route.target_domain, str) or not route.target_domain:
            return False
        if route.target_domain in route.source_domains:
            return False
        if not _unique_nonempty(route.input_domain_ids):
            return False
        if set(route.base_ranked_domain_ids) != set(route.input_domain_ids):
            return False
        if set(route.ranked_domain_ids) != set(route.input_domain_ids):
            return False
        if len(route.base_ranked_domain_ids) != len(route.input_domain_ids):
            return False
        if len(route.ranked_domain_ids) != len(route.input_domain_ids):
            return False
        if not set(route.blocked_domain_ids).issubset(route.input_domain_ids):
            return False
        if not set(route.blocked_domain_ids).issubset(route.source_domains):
            return False
        if len(route.blocked_domain_ids) != len(set(route.blocked_domain_ids)):
            return False
        if not isinstance(route.decision_admitted, bool):
            return False
        if not isinstance(route.decision_reason, str) or not route.decision_reason:
            return False
        if not _is_hash(route.decision_hash):
            return False
        if route.decision_admitted and (route.decision_reason != "positive_transfer_certificate" or route.blocked_domain_ids):
            return False
        if not route.decision_admitted and route.decision_reason not in {
            "no_valid_transfer_certificate",
            "negative_transfer_certificate",
            "neutral_transfer_certificate",
        }:
            return False
        blocked = set(route.blocked_domain_ids)
        expected_ranked = tuple(domain_id for domain_id in route.base_ranked_domain_ids if domain_id not in blocked) + tuple(
            domain_id for domain_id in route.base_ranked_domain_ids if domain_id in blocked
        )
        if route.ranked_domain_ids != expected_ranked:
            return False
        if route.top_domain_id != (route.ranked_domain_ids[0] if route.ranked_domain_ids else ""):
            return False
        if route.source_blocked != bool(route.blocked_domain_ids):
            return False
        return route.route_hash == transfer_guarded_domain_route_hash(route)
    except Exception:
        return False


class ProgrammableSubstrate:
    """Domain-agnostic transaction SDK built on the existing hard-authority engine."""

    def __init__(self, router: ReceiptDomainRouter | None = None):
        self.router = router or ReceiptDomainRouter()
        self.domains: dict[str, DomainRuntime] = {}

    def register(self, domain_id: str, adapter: ReplayRollbackAdapter) -> DomainRuntime:
        if domain_id in self.domains:
            raise ValueError(f"domain already registered: {domain_id}")
        runtime = DomainRuntime(domain_id=domain_id, adapter=adapter)
        self.domains[domain_id] = runtime
        return runtime

    def submit(
        self,
        domain_id: str,
        state: Any,
        trace: ProposalTrace,
        candidate: TypedCandidate,
        *,
        context: str = "global",
        soft_scores: Mapping[str, float] | None = None,
    ) -> SdkTransactionResult:
        domain = self._domain(domain_id)
        engine = TransactionEngine(domain.adapter, ledger=domain.ledger)
        outcome = engine.transact(state, trace, candidate, soft_scores=soft_scores)
        domain.hard_verifier_calls += engine.hard_verifier_calls
        self.router.update(domain_id, context, outcome.receipt)
        return SdkTransactionResult(domain_id=domain_id, outcome=outcome, hard_verifier_calls=engine.hard_verifier_calls)

    def rank_domains(self, context: str, domain_ids: Iterable[str] | None = None) -> list[str]:
        ids = list(domain_ids) if domain_ids is not None else list(self.domains)
        return self.router.rank(context, ids)

    def audit_domain(self, domain_id: str, seed_state: Any) -> DomainAudit:
        domain = self._domain(domain_id)
        engine = TransactionEngine(domain.adapter, ledger=domain.ledger)
        ledger_ok = domain.ledger.audit()
        replay_ok = False
        rollback_ok = False
        if ledger_ok:
            try:
                engine.replay_audit(seed_state)
                replay_ok = True
                rollback_ok = engine.rollback_audit(seed_state) == seed_state
            except Exception:
                replay_ok = False
                rollback_ok = False
        return DomainAudit(
            domain_id=domain_id,
            ledger_audit=ledger_ok,
            replay_matches_receipts=replay_ok,
            rollback_matches_seed=rollback_ok,
            invalid_commit_count=self.invalid_commit_count((domain_id,)),
        )

    def domain_manifest(self, domain_id: str) -> DomainManifestCertificate:
        return build_domain_manifest(self._domain(domain_id))

    def audit_domain_manifest(self, domain_id: str, certificate: DomainManifestCertificate) -> bool:
        return audit_domain_manifest(self._domain(domain_id), certificate)

    def invalid_commit_count(self, domain_ids: Iterable[str] | None = None) -> int:
        ids = list(domain_ids) if domain_ids is not None else list(self.domains)
        return sum(
            1
            for domain_id in ids
            for receipt in self._domain(domain_id).ledger.rows
            if receipt.committed and not receipt.hard_result.accepted
        )

    def _domain(self, domain_id: str) -> DomainRuntime:
        try:
            return self.domains[domain_id]
        except KeyError as exc:
            raise KeyError(f"unknown domain: {domain_id}") from exc


def _receipt_candidate_type(receipt: Receipt) -> str:
    bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
    value = bundle.get("candidate_type", bundle.get("candidateType", "unknown"))
    return str(value)


def _unique_sorted(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _unique_ordered(values: Iterable[Any]) -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        row = str(value)
        if not row:
            continue
        if row in seen:
            raise ValueError("domain ids must be unique")
        rows.append(row)
        seen.add(row)
    return tuple(rows)


def _unique_nonempty(values: tuple[str, ...]) -> bool:
    return bool(values) and len(values) == len(set(values)) and all(isinstance(value, str) and value for value in values)


def _sorted_unique_nonempty(values: tuple[str, ...]) -> bool:
    return _unique_nonempty(values) and values == tuple(sorted(values))


def _sorted_unique_nonempty_when_receipts(values: tuple[str, ...], receipt_count: int) -> bool:
    if values != tuple(sorted(values)):
        return False
    if len(values) != len(set(values)):
        return False
    if any(not isinstance(value, str) or not value for value in values):
        return False
    return receipt_count == 0 or bool(values)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
