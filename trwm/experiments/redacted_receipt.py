from __future__ import annotations

from dataclasses import dataclass, replace

from ..core import ProposalTrace, TransactionEngine
from ..experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate
from ..redaction import (
    REDACTION_SCHEMA,
    RedactionPolicy,
    redact_receipt,
    redacted_receipt_cannot_replay,
    validate_redacted_receipt,
    verify_redacted_path,
)


REDACTION_DEMO_SALT = "redaction-demo-salt"
REDACTION_DEMO_PATHS = (
    "replay_bundle.candidate_payload.order_id",
    "replay_bundle.candidate_payload.pre_state",
    "rollback_bundle.pre_state",
)


@dataclass(frozen=True)
class RedactedReceiptReport:
    schema_version: str
    original_receipt_hash: str
    redacted_hash: str
    policy_hash: str
    redacted_path_count: int
    visible_commit_decision: str
    visible_verifier_result: str
    order_id_redacted: bool
    pre_state_redacted: bool
    selective_disclosure_ok: bool
    wrong_disclosure_rejected: bool
    tamper_detected: bool
    redacted_hash_stable: bool
    original_receipt_still_audits: bool
    redacted_view_is_not_replayable: bool
    invalid_commit_count: int


def run_redacted_receipt_benchmark() -> RedactedReceiptReport:
    state = InventoryState(stock={"widget": 5}, reserved={})
    candidate = make_reservation_candidate(
        state,
        "order-private-1",
        "widget",
        requested=3,
        quantity=3,
        context="redaction-demo",
    )
    engine = TransactionEngine(InventoryReservationAdapter())
    outcome = engine.transact(
        state,
        ProposalTrace(
            branch_id="redacted-receipt-demo",
            actions=({"sku": "widget", "quantity": 3},),
            seeds=("redaction", "inventory"),
            model_version="redaction.demo.v1",
        ),
        candidate,
    )
    if not outcome.committed:
        raise AssertionError("redaction demo requires a committed receipt")

    policy = RedactionPolicy(REDACTION_DEMO_PATHS)
    view = redact_receipt(outcome.receipt, policy, REDACTION_DEMO_SALT)
    repeat_view = redact_receipt(outcome.receipt, policy, REDACTION_DEMO_SALT)
    tampered = replace(view, redacted_payload={**dict(view.redacted_payload), "commit_decision": "hard_reject"})

    return RedactedReceiptReport(
        schema_version=REDACTION_SCHEMA,
        original_receipt_hash=view.original_receipt_hash,
        redacted_hash=view.redacted_hash,
        policy_hash=view.policy_hash,
        redacted_path_count=len(view.commitments),
        visible_commit_decision=str(view.redacted_payload["commit_decision"]),
        visible_verifier_result=str(view.redacted_payload["hard_result"]["result"]),
        order_id_redacted=_redaction_marker_present(view.redacted_payload, REDACTION_DEMO_PATHS[0]),
        pre_state_redacted=_redaction_marker_present(view.redacted_payload, REDACTION_DEMO_PATHS[1])
        and _redaction_marker_present(view.redacted_payload, REDACTION_DEMO_PATHS[2]),
        selective_disclosure_ok=verify_redacted_path(
            view,
            REDACTION_DEMO_PATHS[0],
            "order-private-1",
            REDACTION_DEMO_SALT,
        ),
        wrong_disclosure_rejected=not verify_redacted_path(
            view,
            REDACTION_DEMO_PATHS[0],
            "order-private-2",
            REDACTION_DEMO_SALT,
        ),
        tamper_detected=not validate_redacted_receipt(tampered),
        redacted_hash_stable=view.redacted_hash == repeat_view.redacted_hash,
        original_receipt_still_audits=engine.ledger.audit(),
        redacted_view_is_not_replayable=redacted_receipt_cannot_replay(view),
        invalid_commit_count=engine.invalid_commit_count,
    )


def _redaction_marker_present(payload: object, path: str) -> bool:
    current = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return isinstance(current, dict) and current.get("redacted") is True
