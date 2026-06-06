from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.branch import (
    BranchRuntime,
    audit_branch_selection,
    build_branch_selection_certificate,
    validate_branch_selection_certificate,
)
from trwm.core import ProposalTrace, TransactionEngine
from trwm.experiments.branch_selection import (
    BadRanker,
    CounterAdapter,
    CounterProjector,
    run_branch_selection_benchmark,
)


class BranchSelectionCertificateTests(unittest.TestCase):
    def test_certificate_records_selected_branch_after_hard_filter(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        outcome = BranchRuntime(engine, CounterProjector()).step(
            0,
            (
                ProposalTrace("reject", actions=({"delta": 9, "cost": 1, "soft_rank": 999},)),
                ProposalTrace("loser", actions=({"delta": 1, "cost": 4},)),
                ProposalTrace("winner", actions=({"delta": 2, "cost": 2},)),
            ),
        )

        certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)

        self.assertEqual(certificate.accepted_indices, (1, 2))
        self.assertEqual(certificate.rejected_indices, (0,))
        self.assertEqual(certificate.abstained_indices, ())
        self.assertEqual(certificate.loser_indices, (1,))
        self.assertEqual(certificate.selected_index, 2)
        self.assertEqual(certificate.committed_index, 2)
        self.assertTrue(validate_branch_selection_certificate(certificate))
        self.assertTrue(audit_branch_selection(outcome.receipts, certificate))

    def test_rejected_branch_cannot_be_marked_committed(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        outcome = BranchRuntime(engine, CounterProjector()).step(
            0,
            (
                ProposalTrace("reject", actions=({"delta": 9, "cost": 1},)),
                ProposalTrace("winner", actions=({"delta": 2, "cost": 2},)),
            ),
        )
        certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)
        tampered = replace(certificate, committed_index=0, certificate_hash="")

        self.assertFalse(validate_branch_selection_certificate(tampered))

    def test_invalid_ranker_receipts_still_have_a_valid_fail_closed_certificate(self) -> None:
        engine = TransactionEngine(CounterAdapter())
        outcome = BranchRuntime(engine, CounterProjector(), BadRanker()).step(
            0,
            (
                ProposalTrace("a", actions=({"delta": 1, "cost": 1},)),
                ProposalTrace("b", actions=({"delta": 2, "cost": 2},)),
            ),
        )

        certificate = build_branch_selection_certificate(outcome.receipts, verifier_call_count=outcome.verifier_calls)

        self.assertFalse(outcome.committed)
        self.assertIsNone(certificate.selected_index)
        self.assertIsNone(certificate.committed_index)
        self.assertEqual(certificate.loser_indices, ())
        self.assertTrue(validate_branch_selection_certificate(certificate))
        self.assertTrue(audit_branch_selection(outcome.receipts, certificate))

    def test_branch_selection_benchmark_metrics(self) -> None:
        report = run_branch_selection_benchmark()

        self.assertEqual(report.branch_count, 3)
        self.assertEqual(report.accepted_count, 2)
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(report.selected_index, 2)
        self.assertEqual(report.committed_index, 2)
        self.assertEqual(report.loser_count, 1)
        self.assertTrue(report.hard_reject_soft_rank_blocked)
        self.assertTrue(report.rank_after_hard_filter)
        self.assertTrue(report.certificate_valid)
        self.assertTrue(report.audit_valid)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.invalid_ranker_certificate_valid)
        self.assertFalse(report.invalid_ranker_committed)
        self.assertEqual(report.verifier_calls, 3)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.replay_rollback_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
