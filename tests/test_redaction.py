from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.experiments.redacted_receipt import REDACTION_DEMO_PATHS, REDACTION_DEMO_SALT, run_redacted_receipt_benchmark
from trwm.experiments.operations import InventoryReservationAdapter, InventoryState, make_reservation_candidate
from trwm.core import ProposalTrace, TransactionEngine
from trwm.redaction import (
    REDACTION_SCHEMA,
    RedactionPolicy,
    redact_receipt,
    redacted_receipt_cannot_replay,
    validate_redacted_receipt,
    verify_redacted_path,
)


class RedactionTests(unittest.TestCase):
    def test_policy_rejects_duplicate_missing_and_audit_paths(self) -> None:
        with self.assertRaises(ValueError):
            RedactionPolicy(("replay_bundle.candidate_payload.order_id", "replay_bundle.candidate_payload.order_id"))
        with self.assertRaises(ValueError):
            RedactionPolicy(("",))
        with self.assertRaises(ValueError):
            RedactionPolicy(("receipt_hash",))

    def test_redacted_receipt_validation_and_disclosure(self) -> None:
        receipt, engine = self._committed_receipt()
        view = redact_receipt(receipt, RedactionPolicy(REDACTION_DEMO_PATHS), REDACTION_DEMO_SALT)
        tampered = replace(view, redacted_payload={**dict(view.redacted_payload), "commit_decision": "hard_reject"})

        self.assertEqual(view.schema_version, REDACTION_SCHEMA)
        self.assertEqual(view.original_receipt_hash, receipt.receipt_hash)
        self.assertTrue(validate_redacted_receipt(view))
        self.assertFalse(validate_redacted_receipt(tampered))
        self.assertTrue(verify_redacted_path(view, REDACTION_DEMO_PATHS[0], "order-private-1", REDACTION_DEMO_SALT))
        self.assertFalse(verify_redacted_path(view, REDACTION_DEMO_PATHS[0], "order-private-2", REDACTION_DEMO_SALT))
        self.assertTrue(redacted_receipt_cannot_replay(view))
        self.assertTrue(engine.ledger.audit())

    def test_missing_redaction_path_fails_closed(self) -> None:
        receipt, _engine = self._committed_receipt()

        with self.assertRaises(KeyError):
            redact_receipt(receipt, RedactionPolicy(("replay_bundle.candidate_payload.not_here",)), REDACTION_DEMO_SALT)

    def test_redacted_receipt_benchmark(self) -> None:
        report = run_redacted_receipt_benchmark()

        self.assertEqual(report.schema_version, REDACTION_SCHEMA)
        self.assertEqual(report.redacted_path_count, 3)
        self.assertEqual(report.visible_commit_decision, "commit")
        self.assertEqual(report.visible_verifier_result, "accept")
        self.assertTrue(report.order_id_redacted)
        self.assertTrue(report.pre_state_redacted)
        self.assertTrue(report.selective_disclosure_ok)
        self.assertTrue(report.wrong_disclosure_rejected)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.redacted_hash_stable)
        self.assertTrue(report.original_receipt_still_audits)
        self.assertTrue(report.redacted_view_is_not_replayable)
        self.assertEqual(report.invalid_commit_count, 0)

    def _committed_receipt(self):
        state = InventoryState(stock={"widget": 5}, reserved={})
        candidate = make_reservation_candidate(state, "order-private-1", "widget", 3, 3, context="redaction-demo")
        engine = TransactionEngine(InventoryReservationAdapter())
        outcome = engine.transact(
            state,
            ProposalTrace(
                branch_id="redaction-test",
                actions=({"sku": "widget", "quantity": 3},),
                seeds=("redaction", "test"),
                model_version="redaction.test.v1",
            ),
            candidate,
        )
        self.assertTrue(outcome.committed)
        return outcome.receipt, engine


if __name__ == "__main__":
    unittest.main()
