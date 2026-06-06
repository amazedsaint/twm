from __future__ import annotations

from typing import Any, Protocol

from .core import HardVerifierResult, Receipt, TypedCandidate


class VerifierOnlyAdapter(Protocol):
    verifier_id: str
    verifier_version: str

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        ...


class VerifierAgreementAdapter:
    """Require an independent audit verifier to agree before primary accepts can commit."""

    verifier_id = "verifier_agreement_guard"
    verifier_version = "1.0"

    def __init__(
        self,
        primary: Any,
        audit: VerifierOnlyAdapter,
        *,
        verifier_id: str | None = None,
        verifier_version: str | None = None,
    ) -> None:
        self.primary = primary
        self.audit = audit
        if verifier_id is not None:
            self.verifier_id = verifier_id
        if verifier_version is not None:
            self.verifier_version = verifier_version
        self.primary_calls = 0
        self.audit_calls = 0
        self.false_positive_count = 0
        self.primary_accept_block_count = 0

    def verify(self, candidate: TypedCandidate) -> HardVerifierResult:
        self.primary_calls += 1
        primary_result = self.primary.verify(candidate)
        if not self._result_matches(primary_result, self.primary):
            self.primary_accept_block_count += int(primary_result.accepted)
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={
                    "kind": "primary_verifier_mismatch",
                    "primary_result": primary_result.result,
                    "primary_verifier_id": primary_result.verifier_id,
                    "expected_primary_verifier_id": self.primary.verifier_id,
                },
                metadata=self._metadata(primary_result, audit_called=False),
            )

        if not primary_result.accepted:
            if primary_result.abstained:
                return HardVerifierResult.abstain(
                    self.verifier_id,
                    self.verifier_version,
                    residual=primary_result.residual,
                    metadata=self._metadata(primary_result, audit_called=False),
                )
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual=primary_result.residual,
                metadata=self._metadata(primary_result, audit_called=False),
            )

        self.audit_calls += 1
        audit_result = self.audit.verify(candidate)
        if not self._result_matches(audit_result, self.audit):
            self.primary_accept_block_count += 1
            return HardVerifierResult.reject(
                self.verifier_id,
                self.verifier_version,
                residual={
                    "kind": "audit_verifier_mismatch",
                    "primary_result": primary_result.result,
                    "audit_result": audit_result.result,
                    "audit_verifier_id": audit_result.verifier_id,
                    "expected_audit_verifier_id": self.audit.verifier_id,
                },
                metadata=self._metadata(primary_result, audit_result, audit_called=True),
            )

        metadata = self._metadata(primary_result, audit_result, audit_called=True)
        if audit_result.accepted:
            return HardVerifierResult.accept(self.verifier_id, self.verifier_version, metadata=metadata)

        self.false_positive_count += 1
        self.primary_accept_block_count += 1
        return HardVerifierResult.reject(
            self.verifier_id,
            self.verifier_version,
            residual={
                "kind": "verifier_false_positive",
                "primary_result": primary_result.result,
                "audit_result": audit_result.result,
                "audit_residual": audit_result.residual,
                "primary_verifier_id": self.primary.verifier_id,
                "audit_verifier_id": self.audit.verifier_id,
            },
            metadata=metadata,
        )

    def apply_commit(self, state: Any, candidate: TypedCandidate) -> Any:
        return self.primary.apply_commit(state, candidate)

    def replay(self, state: Any, receipt: Receipt) -> Any:
        return self.primary.replay(state, receipt)

    def rollback(self, state: Any, receipt: Receipt) -> Any:
        return self.primary.rollback(state, receipt)

    def _result_matches(self, result: HardVerifierResult, adapter: VerifierOnlyAdapter) -> bool:
        return result.verifier_id == adapter.verifier_id and result.verifier_version == adapter.verifier_version

    def _metadata(
        self,
        primary_result: HardVerifierResult,
        audit_result: HardVerifierResult | None = None,
        *,
        audit_called: bool,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = dict(primary_result.metadata)
        metadata.update(
            {
                "primary_result": primary_result.result,
                "audit_result": audit_result.result if audit_result is not None else None,
                "audit_called": audit_called,
                "primary_verifier_id": self.primary.verifier_id,
                "primary_verifier_version": self.primary.verifier_version,
                "audit_verifier_id": self.audit.verifier_id,
                "audit_verifier_version": self.audit.verifier_version,
                "primary_metadata": dict(primary_result.metadata),
                "audit_metadata": dict(audit_result.metadata) if audit_result is not None else {},
            }
        )
        if "cost" not in metadata and audit_result is not None and "cost" in audit_result.metadata:
            metadata["cost"] = audit_result.metadata["cost"]
        return metadata
