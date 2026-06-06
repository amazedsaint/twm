from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from .branch import BranchSelectionCertificate, audit_branch_selection, validate_branch_selection_certificate
from .core import Receipt, canonical_json, stable_hash


ANCESTRAL_BRANCH_MEMORY_SNAPSHOT_SCHEMA = "trwm.ancestral_branch_memory_snapshot.v1"
ANCESTRAL_CONTEXT_DESCRIPTOR_SCHEMA = "trwm.ancestral_context_descriptor.v1"
ANCESTRAL_CONTEXT_SELECTION_CERTIFICATE_SCHEMA = "trwm.ancestral_context_selection_certificate.v1"
ANCESTRAL_CONTEXT_REFINEMENT_CERTIFICATE_SCHEMA = "trwm.ancestral_context_refinement_certificate.v1"


@dataclass(frozen=True)
class AncestralContextDescriptor:
    context_id: str
    domain: str
    family: str
    hard_gate_keys: tuple[str, ...]
    residual_kinds: tuple[str, ...]
    tags: Mapping[str, str]
    schema_version: str = ANCESTRAL_CONTEXT_DESCRIPTOR_SCHEMA
    descriptor_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != ANCESTRAL_CONTEXT_DESCRIPTOR_SCHEMA:
            raise ValueError(f"invalid ancestral context descriptor schema: {self.schema_version}")
        if not self.context_id or not self.domain or not self.family:
            raise ValueError("context_id, domain, and family must be non-empty")
        object.__setattr__(self, "hard_gate_keys", _sorted_nonempty_strings(self.hard_gate_keys))
        object.__setattr__(self, "residual_kinds", _sorted_nonempty_strings(self.residual_kinds))
        object.__setattr__(self, "tags", {str(key): str(value) for key, value in self.tags.items()})
        if any(not key or not value for key, value in self.tags.items()):
            raise ValueError("context descriptor tags must be non-empty strings")
        if not self.descriptor_hash:
            object.__setattr__(self, "descriptor_hash", ancestral_context_descriptor_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("descriptor_hash", None)
        return data


@dataclass(frozen=True)
class AncestralContextSelectionCertificate:
    schema_version: str
    selection_rule_id: str
    selection_rule_version: str
    target_context_id: str
    target_context_hash: str
    candidate_count: int
    candidate_context_ids: tuple[str, ...]
    candidate_context_hashes: tuple[str, ...]
    selected_context_ids: tuple[str, ...]
    selected_context_hashes: tuple[str, ...]
    rejected_context_ids: tuple[str, ...]
    rejected_context_hashes: tuple[str, ...]
    required_tag_keys: tuple[str, ...]
    rejected_reasons: Mapping[str, str]
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != ANCESTRAL_CONTEXT_SELECTION_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid ancestral context selection certificate schema: {self.schema_version}")
        for field_name in (
            "candidate_context_ids",
            "candidate_context_hashes",
            "selected_context_ids",
            "selected_context_hashes",
            "rejected_context_ids",
            "rejected_context_hashes",
            "required_tag_keys",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "required_tag_keys", _unique_nonempty_strings(self.required_tag_keys))
        object.__setattr__(self, "rejected_reasons", {str(key): str(value) for key, value in self.rejected_reasons.items()})
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", ancestral_context_selection_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class AncestralContextRefinementCertificate:
    schema_version: str
    refinement_rule_id: str
    refinement_rule_version: str
    target_context_id: str
    target_context_hash: str
    candidate_context_ids: tuple[str, ...]
    candidate_context_hashes: tuple[str, ...]
    base_selection_certificate_hash: str
    refined_selection_certificate_hash: str
    counterexample_receipt_hash: str
    counterexample_result: str
    counterexample_residual_kind: str
    previous_required_tag_keys: tuple[str, ...]
    added_required_tag_keys: tuple[str, ...]
    refined_required_tag_keys: tuple[str, ...]
    selected_before_ids: tuple[str, ...]
    selected_after_ids: tuple[str, ...]
    newly_rejected_context_ids: tuple[str, ...]
    refinement_reason: str
    certificate_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != ANCESTRAL_CONTEXT_REFINEMENT_CERTIFICATE_SCHEMA:
            raise ValueError(f"invalid ancestral context refinement certificate schema: {self.schema_version}")
        for field_name in (
            "candidate_context_ids",
            "candidate_context_hashes",
            "previous_required_tag_keys",
            "added_required_tag_keys",
            "refined_required_tag_keys",
            "selected_before_ids",
            "selected_after_ids",
            "newly_rejected_context_ids",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "previous_required_tag_keys", _unique_nonempty_strings(self.previous_required_tag_keys))
        object.__setattr__(self, "added_required_tag_keys", _unique_nonempty_strings(self.added_required_tag_keys))
        object.__setattr__(self, "refined_required_tag_keys", _unique_nonempty_strings(self.refined_required_tag_keys))
        if not self.certificate_hash:
            object.__setattr__(self, "certificate_hash", ancestral_context_refinement_certificate_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("certificate_hash", None)
        return data


@dataclass(frozen=True)
class AncestralBranchActionStats:
    context: str
    action: str
    committed: int
    rolled_back: int
    rejected: int
    abstained: int
    receipt_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.context or not self.action:
            raise ValueError("context and action must be non-empty")
        for field_name in ("committed", "rolled_back", "rejected", "abstained"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))


@dataclass(frozen=True)
class AncestralBranchMemorySnapshot:
    schema_version: str
    learning_policy: Mapping[str, float]
    receipt_hashes: tuple[str, ...]
    branch_selection_certificate_hashes: tuple[str, ...]
    rows: tuple[AncestralBranchActionStats, ...]
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != ANCESTRAL_BRANCH_MEMORY_SNAPSHOT_SCHEMA:
            raise ValueError(f"invalid ancestral memory snapshot schema: {self.schema_version}")
        object.__setattr__(self, "learning_policy", dict(self.learning_policy))
        object.__setattr__(self, "receipt_hashes", tuple(self.receipt_hashes))
        object.__setattr__(
            self,
            "branch_selection_certificate_hashes",
            tuple(self.branch_selection_certificate_hashes),
        )
        object.__setattr__(self, "rows", tuple(self.rows))
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", ancestral_branch_memory_snapshot_hash(self))

    def without_hash(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("snapshot_hash", None)
        return data


class AncestralBranchMemory:
    """Receipt-bound proposal-ordering memory for past branch outcomes.

    The memory can rank candidates, but it never supplies commit authority.
    Receipts should come from audited branch selections; every ranked candidate
    still needs to pass the hard verifier and transaction replay/rollback gates.
    """

    def __init__(
        self,
        *,
        commit_weight: float = 1.0,
        rollback_weight: float = 1.0,
        reject_weight: float = 2.0,
        abstain_weight: float = 1.5,
    ) -> None:
        self.commit_weight = float(commit_weight)
        self.rollback_weight = float(rollback_weight)
        self.reject_weight = float(reject_weight)
        self.abstain_weight = float(abstain_weight)
        self._rows: defaultdict[tuple[str, str], _MutableActionStats] = defaultdict(_MutableActionStats)
        self._seen_receipt_hashes: set[str] = set()
        self._receipt_hashes: list[str] = []
        self._branch_selection_certificate_hashes: list[str] = []

    def update_branch(
        self,
        receipts: Iterable[Receipt],
        certificate: BranchSelectionCertificate,
    ) -> None:
        rows = tuple(receipts)
        if not validate_branch_selection_certificate(certificate):
            raise ValueError("branch selection certificate must validate before memory update")
        if not audit_branch_selection(rows, certificate):
            raise ValueError("branch selection certificate must audit against receipts before memory update")
        if certificate.certificate_hash not in self._branch_selection_certificate_hashes:
            self._branch_selection_certificate_hashes.append(certificate.certificate_hash)
        for receipt in rows:
            self.update_receipt(receipt)

    def update_receipt(self, receipt: Receipt) -> None:
        if not receipt.static_valid():
            raise ValueError("receipt must be statically valid before memory update")
        if receipt.receipt_hash in self._seen_receipt_hashes:
            return
        context, action = _receipt_context_action(receipt)
        row = self._rows[(context, action)]
        if receipt.committed and receipt.hard_result.accepted:
            row.committed += 1
        elif receipt.hard_result.accepted and receipt.commit_decision == "rolled_back_loser":
            row.rolled_back += 1
        elif receipt.hard_result.rejected:
            row.rejected += 1
        elif receipt.hard_result.abstained:
            row.abstained += 1
        row.receipt_hashes.append(receipt.receipt_hash)
        self._seen_receipt_hashes.add(receipt.receipt_hash)
        self._receipt_hashes.append(receipt.receipt_hash)

    def stats(self, context: str, candidate: Any) -> AncestralBranchActionStats:
        context_token = str(context)
        action_token = _token(candidate)
        row = self._rows.get((context_token, action_token), _MutableActionStats())
        return row.to_frozen(context_token, action_token)

    def score(self, context: str, candidate: Any) -> float:
        row = self.stats(context, candidate)
        return (
            self.commit_weight * row.committed
            - self.rollback_weight * row.rolled_back
            - self.reject_weight * row.rejected
            - self.abstain_weight * row.abstained
        )

    def rank(self, context: str, candidates: Iterable[Any]) -> list[Any]:
        indexed = tuple(enumerate(candidates))

        def key(row_candidate: tuple[int, Any]) -> tuple[float, int, int, int, int, int]:
            idx, candidate = row_candidate
            row = self.stats(context, candidate)
            return (
                -self.score(context, candidate),
                -row.committed,
                row.rolled_back,
                row.rejected,
                row.abstained,
                idx,
            )

        return [candidate for _, candidate in sorted(indexed, key=key)]

    def stats_from_contexts(self, contexts: Iterable[str], candidate: Any) -> AncestralBranchActionStats:
        context_tokens = _unique_contexts(contexts)
        action_token = _token(candidate)
        committed = 0
        rolled_back = 0
        rejected = 0
        abstained = 0
        receipt_hashes: list[str] = []
        for context in context_tokens:
            row = self._rows.get((context, action_token), _MutableActionStats())
            committed += row.committed
            rolled_back += row.rolled_back
            rejected += row.rejected
            abstained += row.abstained
            receipt_hashes.extend(row.receipt_hashes or ())
        return AncestralBranchActionStats(
            context="+".join(context_tokens) if context_tokens else "none",
            action=action_token,
            committed=committed,
            rolled_back=rolled_back,
            rejected=rejected,
            abstained=abstained,
            receipt_hashes=tuple(receipt_hashes),
        )

    def score_from_contexts(self, contexts: Iterable[str], candidate: Any) -> float:
        row = self.stats_from_contexts(contexts, candidate)
        return (
            self.commit_weight * row.committed
            - self.rollback_weight * row.rolled_back
            - self.reject_weight * row.rejected
            - self.abstain_weight * row.abstained
        )

    def rank_from_contexts(self, contexts: Iterable[str], candidates: Iterable[Any]) -> list[Any]:
        context_tokens = _unique_contexts(contexts)
        indexed = tuple(enumerate(candidates))

        def key(row_candidate: tuple[int, Any]) -> tuple[float, int, int, int, int, int]:
            idx, candidate = row_candidate
            row = self.stats_from_contexts(context_tokens, candidate)
            return (
                -self.score_from_contexts(context_tokens, candidate),
                -row.committed,
                row.rolled_back,
                row.rejected,
                row.abstained,
                idx,
            )

        return [candidate for _, candidate in sorted(indexed, key=key)]

    def snapshot(self) -> AncestralBranchMemorySnapshot:
        rows = tuple(
            self._rows[key].to_frozen(*key)
            for key in sorted(self._rows.keys())
        )
        return AncestralBranchMemorySnapshot(
            schema_version=ANCESTRAL_BRANCH_MEMORY_SNAPSHOT_SCHEMA,
            learning_policy={
                "commit_weight": self.commit_weight,
                "rollback_weight": self.rollback_weight,
                "reject_weight": self.reject_weight,
                "abstain_weight": self.abstain_weight,
            },
            receipt_hashes=tuple(self._receipt_hashes),
            branch_selection_certificate_hashes=tuple(self._branch_selection_certificate_hashes),
            rows=rows,
        )


def validate_ancestral_branch_memory_snapshot(snapshot: AncestralBranchMemorySnapshot) -> bool:
    try:
        if snapshot.schema_version != ANCESTRAL_BRANCH_MEMORY_SNAPSHOT_SCHEMA:
            return False
        for key in ("commit_weight", "rollback_weight", "reject_weight", "abstain_weight"):
            value = snapshot.learning_policy.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                return False
        if any(not _is_hash(value) for value in snapshot.receipt_hashes):
            return False
        if len(snapshot.receipt_hashes) != len(set(snapshot.receipt_hashes)):
            return False
        if any(not _is_hash(value) for value in snapshot.branch_selection_certificate_hashes):
            return False
        if len(snapshot.branch_selection_certificate_hashes) != len(set(snapshot.branch_selection_certificate_hashes)):
            return False
        row_keys = tuple((row.context, row.action) for row in snapshot.rows)
        if row_keys != tuple(sorted(row_keys)):
            return False
        if len(row_keys) != len(set(row_keys)):
            return False
        bound_receipts: list[str] = []
        for row in snapshot.rows:
            if not isinstance(row, AncestralBranchActionStats):
                return False
            if not row.context or not row.action:
                return False
            counts = (row.committed, row.rolled_back, row.rejected, row.abstained)
            if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts):
                return False
            if sum(counts) != len(row.receipt_hashes):
                return False
            if any(not _is_hash(value) for value in row.receipt_hashes):
                return False
            if len(row.receipt_hashes) != len(set(row.receipt_hashes)):
                return False
            bound_receipts.extend(row.receipt_hashes)
        if tuple(sorted(bound_receipts)) != tuple(sorted(snapshot.receipt_hashes)):
            return False
        return snapshot.snapshot_hash == ancestral_branch_memory_snapshot_hash(snapshot)
    except Exception:
        return False


def build_ancestral_context_selection_certificate(
    target: AncestralContextDescriptor,
    candidates: Iterable[AncestralContextDescriptor],
    *,
    required_tag_keys: Iterable[str],
    selection_rule_id: str = "tagged_context_overlap",
    selection_rule_version: str = "1.0",
) -> AncestralContextSelectionCertificate:
    candidate_rows = tuple(candidates)
    required_tags = _unique_nonempty_strings(required_tag_keys)
    selected: list[AncestralContextDescriptor] = []
    rejected: list[AncestralContextDescriptor] = []
    rejected_reasons: dict[str, str] = {}
    for candidate in candidate_rows:
        compatible, reason = _context_compatible(target, candidate, required_tags)
        if compatible:
            selected.append(candidate)
        else:
            rejected.append(candidate)
            rejected_reasons[candidate.context_id] = reason
    return AncestralContextSelectionCertificate(
        schema_version=ANCESTRAL_CONTEXT_SELECTION_CERTIFICATE_SCHEMA,
        selection_rule_id=selection_rule_id,
        selection_rule_version=selection_rule_version,
        target_context_id=target.context_id,
        target_context_hash=target.descriptor_hash,
        candidate_count=len(candidate_rows),
        candidate_context_ids=tuple(candidate.context_id for candidate in candidate_rows),
        candidate_context_hashes=tuple(candidate.descriptor_hash for candidate in candidate_rows),
        selected_context_ids=tuple(candidate.context_id for candidate in selected),
        selected_context_hashes=tuple(candidate.descriptor_hash for candidate in selected),
        rejected_context_ids=tuple(candidate.context_id for candidate in rejected),
        rejected_context_hashes=tuple(candidate.descriptor_hash for candidate in rejected),
        required_tag_keys=required_tags,
        rejected_reasons=rejected_reasons,
    )


def validate_ancestral_context_selection_certificate(
    certificate: AncestralContextSelectionCertificate,
    *,
    target: AncestralContextDescriptor | None = None,
    candidates: Iterable[AncestralContextDescriptor] | None = None,
) -> bool:
    try:
        if certificate.schema_version != ANCESTRAL_CONTEXT_SELECTION_CERTIFICATE_SCHEMA:
            return False
        if not certificate.selection_rule_id or not certificate.selection_rule_version:
            return False
        if not certificate.target_context_id or not _is_hash(certificate.target_context_hash):
            return False
        if not isinstance(certificate.candidate_count, int) or isinstance(certificate.candidate_count, bool) or certificate.candidate_count < 0:
            return False
        length_fields = (
            certificate.candidate_context_ids,
            certificate.candidate_context_hashes,
        )
        if any(len(field) != certificate.candidate_count for field in length_fields):
            return False
        if len(certificate.candidate_context_ids) != len(set(certificate.candidate_context_ids)):
            return False
        if any(not context_id for context_id in certificate.candidate_context_ids):
            return False
        if any(not _is_hash(value) for value in certificate.candidate_context_hashes):
            return False
        if any(not _is_hash(value) for value in certificate.selected_context_hashes):
            return False
        if any(not _is_hash(value) for value in certificate.rejected_context_hashes):
            return False
        if len(certificate.selected_context_ids) != len(certificate.selected_context_hashes):
            return False
        if len(certificate.rejected_context_ids) != len(certificate.rejected_context_hashes):
            return False
        selected_ids = set(certificate.selected_context_ids)
        rejected_ids = set(certificate.rejected_context_ids)
        candidate_ids = set(certificate.candidate_context_ids)
        if selected_ids.intersection(rejected_ids):
            return False
        if selected_ids.union(rejected_ids) != candidate_ids:
            return False
        if len(certificate.selected_context_ids) != len(selected_ids):
            return False
        if len(certificate.rejected_context_ids) != len(rejected_ids):
            return False
        if certificate.required_tag_keys != _unique_nonempty_strings(certificate.required_tag_keys):
            return False
        if set(certificate.rejected_reasons.keys()) != rejected_ids:
            return False
        if any(not reason for reason in certificate.rejected_reasons.values()):
            return False
        if target is not None:
            if certificate.target_context_id != target.context_id or certificate.target_context_hash != target.descriptor_hash:
                return False
        if candidates is not None:
            rows = tuple(candidates)
            if certificate.candidate_context_ids != tuple(candidate.context_id for candidate in rows):
                return False
            if certificate.candidate_context_hashes != tuple(candidate.descriptor_hash for candidate in rows):
                return False
            if target is None:
                return False
            rebuilt = build_ancestral_context_selection_certificate(
                target,
                rows,
                required_tag_keys=certificate.required_tag_keys,
                selection_rule_id=certificate.selection_rule_id,
                selection_rule_version=certificate.selection_rule_version,
            )
            if rebuilt.certificate_hash != certificate.certificate_hash:
                return False
        return certificate.certificate_hash == ancestral_context_selection_certificate_hash(certificate)
    except Exception:
        return False


def build_ancestral_context_refinement_certificate(
    *,
    target: AncestralContextDescriptor,
    candidates: Iterable[AncestralContextDescriptor],
    base_selection: AncestralContextSelectionCertificate,
    refined_selection: AncestralContextSelectionCertificate,
    counterexample_receipt: Receipt,
    added_required_tag_keys: Iterable[str],
    refinement_reason: str,
    refinement_rule_id: str = "counterexample_tag_refinement",
    refinement_rule_version: str = "1.0",
) -> AncestralContextRefinementCertificate:
    candidate_rows = tuple(candidates)
    added_keys = _unique_nonempty_strings(added_required_tag_keys)
    previous_keys = _unique_nonempty_strings(base_selection.required_tag_keys)
    refined_keys = _unique_nonempty_strings((*previous_keys, *added_keys))
    newly_rejected = tuple(
        context_id
        for context_id in base_selection.selected_context_ids
        if context_id not in set(refined_selection.selected_context_ids)
    )
    residual = counterexample_receipt.hard_result.residual
    residual_kind = ""
    if isinstance(residual, Mapping):
        residual_kind = str(residual.get("kind", ""))
    return AncestralContextRefinementCertificate(
        schema_version=ANCESTRAL_CONTEXT_REFINEMENT_CERTIFICATE_SCHEMA,
        refinement_rule_id=refinement_rule_id,
        refinement_rule_version=refinement_rule_version,
        target_context_id=target.context_id,
        target_context_hash=target.descriptor_hash,
        candidate_context_ids=tuple(candidate.context_id for candidate in candidate_rows),
        candidate_context_hashes=tuple(candidate.descriptor_hash for candidate in candidate_rows),
        base_selection_certificate_hash=base_selection.certificate_hash,
        refined_selection_certificate_hash=refined_selection.certificate_hash,
        counterexample_receipt_hash=counterexample_receipt.receipt_hash,
        counterexample_result=counterexample_receipt.hard_result.result,
        counterexample_residual_kind=residual_kind,
        previous_required_tag_keys=previous_keys,
        added_required_tag_keys=added_keys,
        refined_required_tag_keys=refined_keys,
        selected_before_ids=base_selection.selected_context_ids,
        selected_after_ids=refined_selection.selected_context_ids,
        newly_rejected_context_ids=newly_rejected,
        refinement_reason=refinement_reason,
    )


def validate_ancestral_context_refinement_certificate(
    certificate: AncestralContextRefinementCertificate,
    *,
    target: AncestralContextDescriptor | None = None,
    candidates: Iterable[AncestralContextDescriptor] | None = None,
    base_selection: AncestralContextSelectionCertificate | None = None,
    refined_selection: AncestralContextSelectionCertificate | None = None,
    counterexample_receipt: Receipt | None = None,
) -> bool:
    try:
        if certificate.schema_version != ANCESTRAL_CONTEXT_REFINEMENT_CERTIFICATE_SCHEMA:
            return False
        if not certificate.refinement_rule_id or not certificate.refinement_rule_version:
            return False
        if not certificate.target_context_id or not _is_hash(certificate.target_context_hash):
            return False
        if len(certificate.candidate_context_ids) != len(certificate.candidate_context_hashes):
            return False
        if not certificate.candidate_context_ids or len(certificate.candidate_context_ids) != len(set(certificate.candidate_context_ids)):
            return False
        if any(not context_id for context_id in certificate.candidate_context_ids):
            return False
        if any(not _is_hash(value) for value in certificate.candidate_context_hashes):
            return False
        for value in (
            certificate.base_selection_certificate_hash,
            certificate.refined_selection_certificate_hash,
            certificate.counterexample_receipt_hash,
        ):
            if not _is_hash(value):
                return False
        if certificate.counterexample_result != "reject":
            return False
        if not certificate.counterexample_residual_kind:
            return False
        previous_keys = _unique_nonempty_strings(certificate.previous_required_tag_keys)
        added_keys = _unique_nonempty_strings(certificate.added_required_tag_keys)
        refined_keys = _unique_nonempty_strings(certificate.refined_required_tag_keys)
        if previous_keys != certificate.previous_required_tag_keys:
            return False
        if added_keys != certificate.added_required_tag_keys:
            return False
        if refined_keys != certificate.refined_required_tag_keys:
            return False
        if refined_keys != _unique_nonempty_strings((*previous_keys, *added_keys)):
            return False
        before = set(certificate.selected_before_ids)
        after = set(certificate.selected_after_ids)
        newly_rejected = set(certificate.newly_rejected_context_ids)
        if not before or not after:
            return False
        if not after.issubset(before):
            return False
        if newly_rejected != before.difference(after):
            return False
        if not newly_rejected:
            return False
        if any(not context_id for context_id in (*certificate.selected_before_ids, *certificate.selected_after_ids, *certificate.newly_rejected_context_ids)):
            return False
        if not certificate.refinement_reason:
            return False
        if target is not None:
            if certificate.target_context_id != target.context_id or certificate.target_context_hash != target.descriptor_hash:
                return False
        if candidates is not None:
            rows = tuple(candidates)
            if certificate.candidate_context_ids != tuple(candidate.context_id for candidate in rows):
                return False
            if certificate.candidate_context_hashes != tuple(candidate.descriptor_hash for candidate in rows):
                return False
        if base_selection is not None:
            if target is None or candidates is None:
                return False
            if not validate_ancestral_context_selection_certificate(base_selection, target=target, candidates=candidates):
                return False
            if base_selection.certificate_hash != certificate.base_selection_certificate_hash:
                return False
            if base_selection.required_tag_keys != certificate.previous_required_tag_keys:
                return False
            if base_selection.selected_context_ids != certificate.selected_before_ids:
                return False
        if refined_selection is not None:
            if target is None or candidates is None:
                return False
            if not validate_ancestral_context_selection_certificate(refined_selection, target=target, candidates=candidates):
                return False
            if refined_selection.certificate_hash != certificate.refined_selection_certificate_hash:
                return False
            if refined_selection.required_tag_keys != certificate.refined_required_tag_keys:
                return False
            if refined_selection.selected_context_ids != certificate.selected_after_ids:
                return False
        if counterexample_receipt is not None:
            if not counterexample_receipt.static_valid():
                return False
            if counterexample_receipt.receipt_hash != certificate.counterexample_receipt_hash:
                return False
            if counterexample_receipt.hard_result.result != certificate.counterexample_result:
                return False
            residual = counterexample_receipt.hard_result.residual
            if not isinstance(residual, Mapping) or str(residual.get("kind", "")) != certificate.counterexample_residual_kind:
                return False
        return certificate.certificate_hash == ancestral_context_refinement_certificate_hash(certificate)
    except Exception:
        return False


def ancestral_branch_memory_snapshot_hash(snapshot: AncestralBranchMemorySnapshot | Mapping[str, Any]) -> str:
    if isinstance(snapshot, AncestralBranchMemorySnapshot):
        data = snapshot.without_hash()
    else:
        data = dict(snapshot)
        data.pop("snapshot_hash", None)
    return stable_hash(data)


def ancestral_context_descriptor_hash(descriptor: AncestralContextDescriptor | Mapping[str, Any]) -> str:
    if isinstance(descriptor, AncestralContextDescriptor):
        data = descriptor.without_hash()
    else:
        data = dict(descriptor)
        data.pop("descriptor_hash", None)
    return stable_hash(data)


def ancestral_context_selection_certificate_hash(
    certificate: AncestralContextSelectionCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, AncestralContextSelectionCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


def ancestral_context_refinement_certificate_hash(
    certificate: AncestralContextRefinementCertificate | Mapping[str, Any],
) -> str:
    if isinstance(certificate, AncestralContextRefinementCertificate):
        data = certificate.without_hash()
    else:
        data = dict(certificate)
        data.pop("certificate_hash", None)
    return stable_hash(data)


@dataclass
class _MutableActionStats:
    committed: int = 0
    rolled_back: int = 0
    rejected: int = 0
    abstained: int = 0
    receipt_hashes: list[str] | None = None

    def __post_init__(self) -> None:
        if self.receipt_hashes is None:
            self.receipt_hashes = []

    def to_frozen(self, context: str, action: str) -> AncestralBranchActionStats:
        return AncestralBranchActionStats(
            context=context,
            action=action,
            committed=self.committed,
            rolled_back=self.rolled_back,
            rejected=self.rejected,
            abstained=self.abstained,
            receipt_hashes=tuple(self.receipt_hashes or ()),
        )


def _receipt_context_action(receipt: Receipt) -> tuple[str, str]:
    bundle = receipt.replay_bundle if isinstance(receipt.replay_bundle, Mapping) else {}
    payload = bundle.get("candidate_payload", {})
    payload = payload if isinstance(payload, Mapping) else {}
    context = str(bundle.get("context", payload.get("context", "global")))
    action = _token(bundle.get("action", payload.get("action", payload.get("guess", payload))))
    return context, action


def _token(value: Any) -> str:
    if isinstance(value, (Mapping, list, tuple, set, bytes)):
        return canonical_json(value)
    return str(value)


def _unique_contexts(contexts: Iterable[str]) -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for context in contexts:
        token = str(context)
        if not token:
            raise ValueError("ancestor context must be non-empty")
        if token not in seen:
            rows.append(token)
            seen.add(token)
    return tuple(rows)


def _context_compatible(
    target: AncestralContextDescriptor,
    candidate: AncestralContextDescriptor,
    required_tag_keys: tuple[str, ...],
) -> tuple[bool, str]:
    if target.context_id == candidate.context_id:
        return False, "same_context"
    if target.domain != candidate.domain:
        return False, "domain_mismatch"
    if target.family != candidate.family:
        return False, "family_mismatch"
    if target.hard_gate_keys != candidate.hard_gate_keys:
        return False, "hard_gate_mismatch"
    if not set(target.residual_kinds).intersection(candidate.residual_kinds):
        return False, "residual_mismatch"
    for key in required_tag_keys:
        if key not in target.tags or key not in candidate.tags:
            return False, f"missing_tag:{key}"
        if target.tags[key] != candidate.tags[key]:
            return False, f"tag_mismatch:{key}"
    return True, ""


def _sorted_nonempty_strings(values: Iterable[str]) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if not rows or any(not value for value in rows):
        raise ValueError("string set must contain non-empty strings")
    return tuple(sorted(set(rows)))


def _unique_nonempty_strings(values: Iterable[str]) -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value)
        if not token:
            raise ValueError("string set must contain non-empty strings")
        if token not in seen:
            rows.append(token)
            seen.add(token)
    return tuple(rows)


def _is_hash(value: str) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)
