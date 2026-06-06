from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .core import canonical_json, stable_hash
from .macro import Macro
from .reversible import AdditiveCoupling, TickVector


RRLM_MACRO_SNAPSHOT_SCHEMA = "trwm.rrlm_macro_snapshot.v1"
RRLM_PROPOSAL_CERTIFICATE_SCHEMA = "trwm.rrlm_proposal_certificate.v1"
RRLM_TRANSPORT_CERTIFICATE_SCHEMA = "trwm.rrlm_transport_certificate.v1"
RRLM_TRANSPORT_SPEC = "rrlm_integer_additive_coupling.v1"
I32_MIN = -(2**31)
I32_MAX = 2**31 - 1


@dataclass(frozen=True)
class RrlmMacroMemoryRow:
    context: str
    token: str
    accepted_count: int
    rejected_prefix_count: int


@dataclass(frozen=True)
class RrlmMacroSnapshot:
    schema_version: str
    proposer_id: str
    proposer_version: str
    accepted_gain: int
    reject_penalty: int
    length_penalty: int
    rows: tuple[RrlmMacroMemoryRow, ...]
    source_receipt_hashes: tuple[str, ...]
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != RRLM_MACRO_SNAPSHOT_SCHEMA:
            raise ValueError(f"invalid RRLM snapshot schema: {self.schema_version}")
        object.__setattr__(self, "rows", tuple(sorted(self.rows, key=lambda row: (row.context, row.token))))
        object.__setattr__(self, "source_receipt_hashes", tuple(self.source_receipt_hashes))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", rrlm_macro_snapshot_hash(self))


@dataclass(frozen=True)
class RrlmProposalCertificate:
    schema_version: str
    context: str
    proposer_id: str
    proposer_version: str
    snapshot_hash: str
    accepted_gain: int
    reject_penalty: int
    length_penalty: int
    proposal_count: int
    macro_ids: tuple[str, ...]
    proposal_tokens: tuple[str, ...]
    original_indices: tuple[int, ...]
    macro_lengths: tuple[int, ...]
    accepted_counts: tuple[int, ...]
    rejected_prefix_counts: tuple[int, ...]
    latent_before: tuple[TickVector, ...]
    latent_after: tuple[TickVector, ...]
    scores: tuple[int, ...]
    cycle_failure_count: int
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != RRLM_PROPOSAL_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid RRLM proposal certificate schema: {self.schema_version}")
        for field_name in (
            "macro_ids",
            "proposal_tokens",
            "original_indices",
            "macro_lengths",
            "accepted_counts",
            "rejected_prefix_counts",
            "latent_before",
            "latent_after",
            "scores",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "latent_before", tuple(tuple(row) for row in self.latent_before))
        object.__setattr__(self, "latent_after", tuple(tuple(row) for row in self.latent_after))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", rrlm_proposal_certificate_hash(self))


@dataclass(frozen=True)
class RrlmTransportCertificate:
    schema_version: str
    transport_spec: str
    context: str
    proposer_id: str
    proposer_version: str
    snapshot_hash: str
    proposal_certificate_hash: str
    accepted_gain: int
    reject_penalty: int
    length_penalty: int
    proposal_count: int
    macro_lengths: tuple[int, ...]
    latent_before: tuple[TickVector, ...]
    latent_after: tuple[TickVector, ...]
    latent_roundtrip: tuple[TickVector, ...]
    cycle_failure_count: int
    i32_admissible_count: int
    i32_rejected_count: int
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != RRLM_TRANSPORT_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid RRLM transport certificate schema: {self.schema_version}")
        object.__setattr__(self, "macro_lengths", tuple(self.macro_lengths))
        object.__setattr__(self, "latent_before", tuple(tuple(row) for row in self.latent_before))
        object.__setattr__(self, "latent_after", tuple(tuple(row) for row in self.latent_after))
        object.__setattr__(self, "latent_roundtrip", tuple(tuple(row) for row in self.latent_roundtrip))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", rrlm_transport_certificate_hash(self))


@dataclass(frozen=True)
class RrlmMacroProposal:
    macro: Macro
    original_index: int
    token: str
    latent_before: TickVector
    latent_after: TickVector
    score: int
    accepted_count: int
    rejected_prefix_count: int
    cycle_ok: bool


@dataclass(frozen=True)
class RrlmRanking:
    context: str
    proposals: tuple[RrlmMacroProposal, ...]

    @property
    def ranked_macros(self) -> tuple[Macro, ...]:
        return tuple(proposal.macro for proposal in self.proposals)

    @property
    def cycle_failure_count(self) -> int:
        return sum(1 for proposal in self.proposals if not proposal.cycle_ok)


class RrlmMacroProposer:
    """Reversible receipt-learned macro proposer.

    This is a proposal/ranking layer only. It learns from receipts, transports a
    compact integer latent vector with an exactly invertible additive coupling,
    and leaves all commits to the hard verifier runtime.
    """

    def __init__(self, accepted_gain: int = 64, reject_penalty: int = 32, length_penalty: int = 1):
        self.accepted_gain = accepted_gain
        self.reject_penalty = reject_penalty
        self.length_penalty = length_penalty
        self.proposer_id = "rrlm_macro_proposer"
        self.proposer_version = "1.0"
        self.accepted: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rejected_prefixes: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.source_receipt_hashes: list[str] = []
        self.coupling = AdditiveCoupling(self._f, self._g, split=2)

    def update(self, receipt: Any) -> None:
        payload = _receipt_payload(receipt)
        context = str(payload.get("context", "global"))
        token = _token(payload.get("macro", ()))
        counted = False
        if getattr(receipt, "committed", False) and getattr(receipt.hard_result, "accepted", False):
            self.accepted[context][token] += 1
            counted = True
        elif getattr(receipt, "commit_decision", None) == "prefix_unsafe" or getattr(receipt.hard_result, "rejected", False):
            self.rejected_prefixes[context][token] += 1
            counted = True
        receipt_hash = getattr(receipt, "receipt_hash", "")
        if counted and _is_hash(receipt_hash):
            self.source_receipt_hashes.append(receipt_hash)

    def propose(self, context: str, macros: Iterable[Macro]) -> RrlmRanking:
        proposals = [self._proposal(context, macro, idx) for idx, macro in enumerate(macros)]
        ranked = tuple(
            sorted(
                proposals,
                key=lambda proposal: (
                    -proposal.score,
                    -proposal.latent_after[1],
                    proposal.original_index,
                ),
            )
        )
        return RrlmRanking(context=context, proposals=ranked)

    def rank(self, context: str, macros: Iterable[Macro]) -> list[Macro]:
        return list(self.propose(context, macros).ranked_macros)

    def counts(self, context: str, macro: Macro) -> tuple[int, int]:
        token = _token(macro.steps)
        return self.accepted[context][token], self.rejected_prefixes[context][token]

    def snapshot(self) -> RrlmMacroSnapshot:
        rows: list[RrlmMacroMemoryRow] = []
        contexts = set(self.accepted) | set(self.rejected_prefixes)
        for context in sorted(contexts):
            tokens = set(self.accepted[context]) | set(self.rejected_prefixes[context])
            for token in sorted(tokens):
                rows.append(
                    RrlmMacroMemoryRow(
                        context=context,
                        token=token,
                        accepted_count=self.accepted[context][token],
                        rejected_prefix_count=self.rejected_prefixes[context][token],
                    )
                )
        return RrlmMacroSnapshot(
            schema_version=RRLM_MACRO_SNAPSHOT_SCHEMA,
            proposer_id=self.proposer_id,
            proposer_version=self.proposer_version,
            accepted_gain=self.accepted_gain,
            reject_penalty=self.reject_penalty,
            length_penalty=self.length_penalty,
            rows=tuple(rows),
            source_receipt_hashes=tuple(self.source_receipt_hashes),
        )

    def _proposal(self, context: str, macro: Macro, idx: int) -> RrlmMacroProposal:
        token = _token(macro.steps)
        accepted = self.accepted[context][token]
        rejected = self.rejected_prefixes[context][token]
        z = (0, -idx, accepted, rejected)
        coupling_context = {"length": len(macro.steps)}
        z_next = self.coupling.forward(z, coupling_context)
        cycle_ok = self.coupling.inverse(z_next, coupling_context) == z
        return RrlmMacroProposal(
            macro=macro,
            original_index=idx,
            token=token,
            latent_before=z,
            latent_after=z_next,
            score=z_next[0],
            accepted_count=accepted,
            rejected_prefix_count=rejected,
            cycle_ok=cycle_ok,
        )

    def _f(self, v: TickVector, context: Mapping[str, Any]) -> TickVector:
        accepted, rejected = v
        length = int(context.get("length", 0))
        return (
            self.accepted_gain * accepted - self.reject_penalty * rejected,
            -self.length_penalty * length,
        )

    def _g(self, u_next: TickVector, context: Mapping[str, Any]) -> TickVector:
        return (0, 0)


class NonReversibleMacroRanker:
    """Matched receipt ranker without reversible latent transport."""

    def __init__(self, accepted_gain: int = 64, reject_penalty: int = 32, length_penalty: int = 1):
        self.accepted_gain = accepted_gain
        self.reject_penalty = reject_penalty
        self.length_penalty = length_penalty
        self.accepted: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.rejected_prefixes: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def update(self, receipt: Any) -> None:
        payload = _receipt_payload(receipt)
        context = str(payload.get("context", "global"))
        token = _token(payload.get("macro", ()))
        if getattr(receipt, "committed", False) and getattr(receipt.hard_result, "accepted", False):
            self.accepted[context][token] += 1
        elif getattr(receipt, "commit_decision", None) == "prefix_unsafe":
            self.rejected_prefixes[context][token] += 1

    def rank(self, context: str, macros: Iterable[Macro]) -> list[Macro]:
        indexed = list(enumerate(macros))

        def key(row: tuple[int, Macro]) -> tuple[int, int, int]:
            idx, macro = row
            token = _token(macro.steps)
            score = self.accepted_gain * self.accepted[context][token] - self.reject_penalty * self.rejected_prefixes[context][token]
            tie = -self.length_penalty * len(macro.steps) - idx
            return (-score, -tie, idx)

        return [macro for _, macro in sorted(indexed, key=key)]


def _receipt_payload(receipt: Any) -> Mapping[str, Any]:
    bundle = receipt.replay_bundle if isinstance(getattr(receipt, "replay_bundle", None), Mapping) else {}
    payload = bundle.get("candidate_payload", {})
    return payload if isinstance(payload, Mapping) else {}


def _token(value: Any) -> str:
    if isinstance(value, (Mapping, list, tuple, set, bytes)):
        return canonical_json(value)
    return str(value)


def build_rrlm_proposal_certificate(snapshot: RrlmMacroSnapshot, ranking: RrlmRanking) -> RrlmProposalCertificate:
    return RrlmProposalCertificate(
        schema_version=RRLM_PROPOSAL_CERTIFICATE_SCHEMA,
        context=ranking.context,
        proposer_id=snapshot.proposer_id,
        proposer_version=snapshot.proposer_version,
        snapshot_hash=snapshot.snapshot_hash,
        accepted_gain=snapshot.accepted_gain,
        reject_penalty=snapshot.reject_penalty,
        length_penalty=snapshot.length_penalty,
        proposal_count=len(ranking.proposals),
        macro_ids=tuple(proposal.macro.macro_id for proposal in ranking.proposals),
        proposal_tokens=tuple(proposal.token for proposal in ranking.proposals),
        original_indices=tuple(proposal.original_index for proposal in ranking.proposals),
        macro_lengths=tuple(len(proposal.macro.steps) for proposal in ranking.proposals),
        accepted_counts=tuple(proposal.accepted_count for proposal in ranking.proposals),
        rejected_prefix_counts=tuple(proposal.rejected_prefix_count for proposal in ranking.proposals),
        latent_before=tuple(proposal.latent_before for proposal in ranking.proposals),
        latent_after=tuple(proposal.latent_after for proposal in ranking.proposals),
        scores=tuple(proposal.score for proposal in ranking.proposals),
        cycle_failure_count=ranking.cycle_failure_count,
    )


def build_rrlm_transport_certificate(certificate: RrlmProposalCertificate) -> RrlmTransportCertificate:
    latent_roundtrip = tuple(
        rrlm_transport_cpu(
            certificate.latent_after[idx],
            accepted_gain=certificate.accepted_gain,
            reject_penalty=certificate.reject_penalty,
            length_penalty=certificate.length_penalty,
            length=certificate.macro_lengths[idx],
            direction="inverse",
        )
        for idx in range(certificate.proposal_count)
    )
    i32_flags = tuple(
        rrlm_transport_i32_admissible(
            certificate.latent_before[idx],
            accepted_gain=certificate.accepted_gain,
            reject_penalty=certificate.reject_penalty,
            length_penalty=certificate.length_penalty,
            length=certificate.macro_lengths[idx],
        )
        for idx in range(certificate.proposal_count)
    )
    return RrlmTransportCertificate(
        schema_version=RRLM_TRANSPORT_CERTIFICATE_SCHEMA,
        transport_spec=RRLM_TRANSPORT_SPEC,
        context=certificate.context,
        proposer_id=certificate.proposer_id,
        proposer_version=certificate.proposer_version,
        snapshot_hash=certificate.snapshot_hash,
        proposal_certificate_hash=certificate.certificate_hash,
        accepted_gain=certificate.accepted_gain,
        reject_penalty=certificate.reject_penalty,
        length_penalty=certificate.length_penalty,
        proposal_count=certificate.proposal_count,
        macro_lengths=certificate.macro_lengths,
        latent_before=certificate.latent_before,
        latent_after=certificate.latent_after,
        latent_roundtrip=latent_roundtrip,
        cycle_failure_count=sum(1 for before, roundtrip in zip(certificate.latent_before, latent_roundtrip) if before != roundtrip),
        i32_admissible_count=sum(1 for flag in i32_flags if flag),
        i32_rejected_count=sum(1 for flag in i32_flags if not flag),
    )


def rrlm_transport_cpu(
    z: TickVector,
    *,
    accepted_gain: int,
    reject_penalty: int,
    length_penalty: int,
    length: int,
    direction: str = "forward",
) -> TickVector:
    _assert_rrlm_transport_shape(z)
    if direction not in {"forward", "inverse"}:
        raise ValueError("direction must be forward or inverse")
    for value in (accepted_gain, reject_penalty, length_penalty, length):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("RRLM transport parameters must be integers")
    delta_score = accepted_gain * z[2] - reject_penalty * z[3]
    delta_tie = -length_penalty * length
    if direction == "forward":
        return (z[0] + delta_score, z[1] + delta_tie, z[2], z[3])
    return (z[0] - delta_score, z[1] - delta_tie, z[2], z[3])


def rrlm_transport_i32_admissible(
    z: TickVector,
    *,
    accepted_gain: int,
    reject_penalty: int,
    length_penalty: int,
    length: int,
) -> bool:
    try:
        _assert_rrlm_transport_shape(z)
        values = (*z, accepted_gain, reject_penalty, length_penalty, length)
        if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
            return False
        accepted_term = accepted_gain * z[2]
        rejected_term = reject_penalty * z[3]
        delta_score = accepted_term - rejected_term
        delta_tie = -length_penalty * length
        forward = (z[0] + delta_score, z[1] + delta_tie, z[2], z[3])
        inverse = (forward[0] - delta_score, forward[1] - delta_tie, forward[2], forward[3])
        return all(
            I32_MIN <= value <= I32_MAX
            for value in (
                *values,
                accepted_term,
                rejected_term,
                delta_score,
                delta_tie,
                *forward,
                *inverse,
            )
        )
    except Exception:
        return False


def rrlm_macro_snapshot_hash(snapshot: RrlmMacroSnapshot | Mapping[str, Any]) -> str:
    if isinstance(snapshot, RrlmMacroSnapshot):
        data = asdict(snapshot)
    else:
        data = dict(snapshot)
    data.pop("snapshot_hash", None)
    return stable_hash(data)


def rrlm_proposal_certificate_hash(certificate: RrlmProposalCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, RrlmProposalCertificate):
        data = asdict(certificate)
    else:
        data = dict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def rrlm_transport_certificate_hash(certificate: RrlmTransportCertificate | Mapping[str, Any]) -> str:
    if isinstance(certificate, RrlmTransportCertificate):
        data = asdict(certificate)
    else:
        data = dict(certificate)
    data.pop("certificate_hash", None)
    return stable_hash(data)


def validate_rrlm_macro_snapshot(snapshot: RrlmMacroSnapshot) -> bool:
    try:
        if snapshot.schema_version != RRLM_MACRO_SNAPSHOT_SCHEMA:
            return False
        if not isinstance(snapshot.proposer_id, str) or not snapshot.proposer_id:
            return False
        if not isinstance(snapshot.proposer_version, str) or not snapshot.proposer_version:
            return False
        for value in (snapshot.accepted_gain, snapshot.reject_penalty, snapshot.length_penalty):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False
        if snapshot.rows != tuple(sorted(snapshot.rows, key=lambda row: (row.context, row.token))):
            return False
        keys: set[tuple[str, str]] = set()
        evidence_count = 0
        for row in snapshot.rows:
            if not isinstance(row.context, str) or not row.context:
                return False
            if not isinstance(row.token, str) or not row.token:
                return False
            for value in (row.accepted_count, row.rejected_prefix_count):
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    return False
            key = (row.context, row.token)
            if key in keys:
                return False
            keys.add(key)
            evidence_count += row.accepted_count + row.rejected_prefix_count
        if len(snapshot.source_receipt_hashes) != evidence_count:
            return False
        if len(snapshot.source_receipt_hashes) != len(set(snapshot.source_receipt_hashes)):
            return False
        if any(not _is_hash(receipt_hash) for receipt_hash in snapshot.source_receipt_hashes):
            return False
        return snapshot.snapshot_hash == rrlm_macro_snapshot_hash(snapshot)
    except Exception:
        return False


def validate_rrlm_proposal_certificate(certificate: RrlmProposalCertificate, snapshot: RrlmMacroSnapshot | None = None) -> bool:
    try:
        if certificate.schema_version != RRLM_PROPOSAL_CERTIFICATE_SCHEMA:
            return False
        if not isinstance(certificate.context, str) or not certificate.context:
            return False
        if not isinstance(certificate.proposer_id, str) or not certificate.proposer_id:
            return False
        if not isinstance(certificate.proposer_version, str) or not certificate.proposer_version:
            return False
        if not _is_hash(certificate.snapshot_hash):
            return False
        for value in (certificate.accepted_gain, certificate.reject_penalty, certificate.length_penalty):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False
        if not isinstance(certificate.proposal_count, int) or isinstance(certificate.proposal_count, bool) or certificate.proposal_count <= 0:
            return False
        fields = (
            certificate.macro_ids,
            certificate.proposal_tokens,
            certificate.original_indices,
            certificate.macro_lengths,
            certificate.accepted_counts,
            certificate.rejected_prefix_counts,
            certificate.latent_before,
            certificate.latent_after,
            certificate.scores,
        )
        if any(len(field) != certificate.proposal_count for field in fields):
            return False
        if len(certificate.macro_ids) != len(set(certificate.macro_ids)):
            return False
        if len(certificate.proposal_tokens) != len(set(certificate.proposal_tokens)):
            return False
        if len(certificate.original_indices) != len(set(certificate.original_indices)):
            return False
        snapshot_rows = {}
        if snapshot is not None:
            if not validate_rrlm_macro_snapshot(snapshot):
                return False
            if snapshot.snapshot_hash != certificate.snapshot_hash:
                return False
            if snapshot.proposer_id != certificate.proposer_id or snapshot.proposer_version != certificate.proposer_version:
                return False
            if (
                snapshot.accepted_gain != certificate.accepted_gain
                or snapshot.reject_penalty != certificate.reject_penalty
                or snapshot.length_penalty != certificate.length_penalty
            ):
                return False
            snapshot_rows = {(row.context, row.token): row for row in snapshot.rows}
        cycle_failures = 0
        order_keys: list[tuple[int, int, int]] = []
        for idx in range(certificate.proposal_count):
            if not certificate.macro_ids[idx] or not certificate.proposal_tokens[idx]:
                return False
            for value in (
                certificate.original_indices[idx],
                certificate.macro_lengths[idx],
                certificate.accepted_counts[idx],
                certificate.rejected_prefix_counts[idx],
                certificate.scores[idx],
            ):
                if not isinstance(value, int) or isinstance(value, bool):
                    return False
            if certificate.original_indices[idx] < 0 or certificate.macro_lengths[idx] < 0:
                return False
            if certificate.accepted_counts[idx] < 0 or certificate.rejected_prefix_counts[idx] < 0:
                return False
            before = tuple(certificate.latent_before[idx])
            after = tuple(certificate.latent_after[idx])
            if len(before) != 4 or len(after) != 4:
                return False
            if any(not isinstance(value, int) or isinstance(value, bool) for value in (*before, *after)):
                return False
            expected_before = (
                0,
                -certificate.original_indices[idx],
                certificate.accepted_counts[idx],
                certificate.rejected_prefix_counts[idx],
            )
            expected_after = (
                before[0] + certificate.accepted_gain * before[2] - certificate.reject_penalty * before[3],
                before[1] - certificate.length_penalty * certificate.macro_lengths[idx],
                before[2],
                before[3],
            )
            if before != expected_before or after != expected_after:
                return False
            if certificate.scores[idx] != after[0]:
                return False
            inverse = (
                after[0] - certificate.accepted_gain * after[2] + certificate.reject_penalty * after[3],
                after[1] + certificate.length_penalty * certificate.macro_lengths[idx],
                after[2],
                after[3],
            )
            if inverse != before:
                cycle_failures += 1
            if snapshot is not None:
                row = snapshot_rows.get((certificate.context, certificate.proposal_tokens[idx]))
                accepted = row.accepted_count if row is not None else 0
                rejected = row.rejected_prefix_count if row is not None else 0
                if accepted != certificate.accepted_counts[idx] or rejected != certificate.rejected_prefix_counts[idx]:
                    return False
            order_keys.append((-certificate.scores[idx], -after[1], certificate.original_indices[idx]))
        if cycle_failures != certificate.cycle_failure_count:
            return False
        if order_keys != sorted(order_keys):
            return False
        return certificate.certificate_hash == rrlm_proposal_certificate_hash(certificate)
    except Exception:
        return False


def validate_rrlm_transport_certificate(
    certificate: RrlmTransportCertificate,
    proposal_certificate: RrlmProposalCertificate | None = None,
) -> bool:
    try:
        if certificate.schema_version != RRLM_TRANSPORT_CERTIFICATE_SCHEMA:
            return False
        if certificate.transport_spec != RRLM_TRANSPORT_SPEC:
            return False
        if not isinstance(certificate.context, str) or not certificate.context:
            return False
        if not isinstance(certificate.proposer_id, str) or not certificate.proposer_id:
            return False
        if not isinstance(certificate.proposer_version, str) or not certificate.proposer_version:
            return False
        if not _is_hash(certificate.snapshot_hash) or not _is_hash(certificate.proposal_certificate_hash):
            return False
        for value in (certificate.accepted_gain, certificate.reject_penalty, certificate.length_penalty):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return False
        if not isinstance(certificate.proposal_count, int) or isinstance(certificate.proposal_count, bool) or certificate.proposal_count <= 0:
            return False
        if (
            len(certificate.macro_lengths) != certificate.proposal_count
            or len(certificate.latent_before) != certificate.proposal_count
            or len(certificate.latent_after) != certificate.proposal_count
            or len(certificate.latent_roundtrip) != certificate.proposal_count
        ):
            return False
        if proposal_certificate is not None:
            if not validate_rrlm_proposal_certificate(proposal_certificate):
                return False
            if proposal_certificate.certificate_hash != certificate.proposal_certificate_hash:
                return False
            if proposal_certificate.snapshot_hash != certificate.snapshot_hash:
                return False
            if proposal_certificate.context != certificate.context:
                return False
            if proposal_certificate.proposer_id != certificate.proposer_id or proposal_certificate.proposer_version != certificate.proposer_version:
                return False
            if (
                proposal_certificate.accepted_gain != certificate.accepted_gain
                or proposal_certificate.reject_penalty != certificate.reject_penalty
                or proposal_certificate.length_penalty != certificate.length_penalty
                or proposal_certificate.proposal_count != certificate.proposal_count
                or proposal_certificate.macro_lengths != certificate.macro_lengths
                or proposal_certificate.latent_before != certificate.latent_before
                or proposal_certificate.latent_after != certificate.latent_after
            ):
                return False
        cycle_failures = 0
        i32_admissible_count = 0
        for idx in range(certificate.proposal_count):
            length = certificate.macro_lengths[idx]
            before = tuple(certificate.latent_before[idx])
            after = tuple(certificate.latent_after[idx])
            roundtrip = tuple(certificate.latent_roundtrip[idx])
            if not isinstance(length, int) or isinstance(length, bool) or length < 0:
                return False
            for latent in (before, after, roundtrip):
                if len(latent) != 4:
                    return False
                if any(not isinstance(value, int) or isinstance(value, bool) for value in latent):
                    return False
            expected_after = rrlm_transport_cpu(
                before,
                accepted_gain=certificate.accepted_gain,
                reject_penalty=certificate.reject_penalty,
                length_penalty=certificate.length_penalty,
                length=length,
                direction="forward",
            )
            expected_roundtrip = rrlm_transport_cpu(
                after,
                accepted_gain=certificate.accepted_gain,
                reject_penalty=certificate.reject_penalty,
                length_penalty=certificate.length_penalty,
                length=length,
                direction="inverse",
            )
            if after != expected_after or roundtrip != expected_roundtrip:
                return False
            if roundtrip != before:
                cycle_failures += 1
            if rrlm_transport_i32_admissible(
                before,
                accepted_gain=certificate.accepted_gain,
                reject_penalty=certificate.reject_penalty,
                length_penalty=certificate.length_penalty,
                length=length,
            ):
                i32_admissible_count += 1
        if cycle_failures != certificate.cycle_failure_count:
            return False
        if i32_admissible_count != certificate.i32_admissible_count:
            return False
        if certificate.i32_rejected_count != certificate.proposal_count - i32_admissible_count:
            return False
        return certificate.certificate_hash == rrlm_transport_certificate_hash(certificate)
    except Exception:
        return False


def _assert_rrlm_transport_shape(z: TickVector) -> None:
    if len(z) != 4:
        raise ValueError("RRLM transport requires [score, tie, accepted, rejected]")
    if any(not isinstance(value, int) or isinstance(value, bool) for value in z):
        raise TypeError("RRLM transport ticks must be integers")


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
