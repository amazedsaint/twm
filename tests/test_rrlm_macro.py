from __future__ import annotations

import unittest
from dataclasses import replace

from trwm.core import Ledger, TransactionEngine
from trwm.experiments.macro_grid import GridMacroAdapter, default_grid_state, default_macros
from trwm.experiments.rrlm_macro import run_rrlm_macro_benchmark
from trwm.macro import PrefixSafeMacroRuntime
from trwm.rrlm import (
    RrlmMacroProposer,
    build_rrlm_proposal_certificate,
    build_rrlm_transport_certificate,
    rrlm_macro_snapshot_hash,
    rrlm_proposal_certificate_hash,
    rrlm_transport_certificate_hash,
    rrlm_transport_cpu,
    rrlm_transport_i32_admissible,
    validate_rrlm_macro_snapshot,
    validate_rrlm_proposal_certificate,
    validate_rrlm_transport_certificate,
)


class RrlmMacroTests(unittest.TestCase):
    def test_rrlm_transport_helper_cycles_and_rejects_i32_overflow_risk(self) -> None:
        z = (0, -1, 2, 1)

        forward = rrlm_transport_cpu(z, accepted_gain=64, reject_penalty=32, length_penalty=1, length=4)

        self.assertEqual(forward, (96, -5, 2, 1))
        self.assertEqual(
            rrlm_transport_cpu(forward, accepted_gain=64, reject_penalty=32, length_penalty=1, length=4, direction="inverse"),
            z,
        )
        self.assertTrue(rrlm_transport_i32_admissible(z, accepted_gain=64, reject_penalty=32, length_penalty=1, length=4))
        self.assertFalse(
            rrlm_transport_i32_admissible(
                (0, 0, 2**30, 0),
                accepted_gain=4,
                reject_penalty=0,
                length_penalty=1,
                length=1,
            )
        )

    def test_reversible_latent_proposals_cycle_exactly(self) -> None:
        proposer = RrlmMacroProposer()
        ranking = proposer.propose("grid-3x3", default_macros())

        self.assertEqual(ranking.cycle_failure_count, 0)
        self.assertEqual(ranking.ranked_macros[0].macro_id, "unsafe-through-wall")
        for proposal in ranking.proposals:
            self.assertEqual(proposer.coupling.inverse(proposal.latent_after, {"length": len(proposal.macro.steps)}), proposal.latent_before)

    def test_rrlm_learns_from_receipts_without_commit_authority(self) -> None:
        proposer = RrlmMacroProposer()
        adapter = GridMacroAdapter()
        engine = TransactionEngine(adapter, ledger=Ledger())
        runtime = PrefixSafeMacroRuntime(engine, adapter)

        for macro in default_macros():
            outcome = runtime.run(default_grid_state(), macro)
            proposer.update(outcome.receipt)
            if outcome.committed:
                break

        ranking = proposer.propose("grid-3x3", default_macros())

        self.assertEqual(ranking.cycle_failure_count, 0)
        self.assertEqual(ranking.ranked_macros[0].macro_id, "safe-around-wall")
        self.assertTrue(engine.ledger.audit())
        self.assertEqual(engine.invalid_commit_count, 0)
        self.assertEqual(engine.hard_verifier_calls, 1)

    def test_rrlm_snapshot_and_proposal_certificate_validate_exact_transport(self) -> None:
        proposer = RrlmMacroProposer()
        adapter = GridMacroAdapter()
        engine = TransactionEngine(adapter, ledger=Ledger())
        runtime = PrefixSafeMacroRuntime(engine, adapter)
        for macro in default_macros():
            outcome = runtime.run(default_grid_state(), macro)
            proposer.update(outcome.receipt)
            if outcome.committed:
                break

        snapshot = proposer.snapshot()
        ranking = proposer.propose("grid-3x3", default_macros())
        certificate = build_rrlm_proposal_certificate(snapshot, ranking)
        transport_certificate = build_rrlm_transport_certificate(certificate)
        tampered_snapshot = replace(
            snapshot,
            rows=(replace(snapshot.rows[0], accepted_count=snapshot.rows[0].accepted_count + 1), *snapshot.rows[1:]),
            snapshot_hash="",
        )
        tampered_snapshot = replace(tampered_snapshot, snapshot_hash=rrlm_macro_snapshot_hash(tampered_snapshot))
        tampered_certificate = replace(
            certificate,
            scores=(certificate.scores[0] + 1, *certificate.scores[1:]),
            certificate_hash="",
        )
        tampered_certificate = replace(tampered_certificate, certificate_hash=rrlm_proposal_certificate_hash(tampered_certificate))
        duplicate_macro_certificate = replace(
            certificate,
            macro_ids=(certificate.macro_ids[1], *certificate.macro_ids[1:]),
            certificate_hash="",
        )
        duplicate_macro_certificate = replace(
            duplicate_macro_certificate,
            certificate_hash=rrlm_proposal_certificate_hash(duplicate_macro_certificate),
        )
        duplicate_token_certificate = replace(
            certificate,
            proposal_tokens=(certificate.proposal_tokens[1], *certificate.proposal_tokens[1:]),
            certificate_hash="",
        )
        duplicate_token_certificate = replace(
            duplicate_token_certificate,
            certificate_hash=rrlm_proposal_certificate_hash(duplicate_token_certificate),
        )
        tampered_transport = replace(
            transport_certificate,
            latent_roundtrip=((transport_certificate.latent_roundtrip[0][0] + 1, *transport_certificate.latent_roundtrip[0][1:]), *transport_certificate.latent_roundtrip[1:]),
            certificate_hash="",
        )
        tampered_transport = replace(tampered_transport, certificate_hash=rrlm_transport_certificate_hash(tampered_transport))

        self.assertTrue(validate_rrlm_macro_snapshot(snapshot))
        self.assertTrue(validate_rrlm_proposal_certificate(certificate, snapshot))
        self.assertTrue(validate_rrlm_transport_certificate(transport_certificate, certificate))
        self.assertEqual(certificate.snapshot_hash, snapshot.snapshot_hash)
        self.assertEqual(certificate.cycle_failure_count, 0)
        self.assertEqual(transport_certificate.proposal_certificate_hash, certificate.certificate_hash)
        self.assertEqual(transport_certificate.cycle_failure_count, 0)
        self.assertEqual(transport_certificate.i32_admissible_count, transport_certificate.proposal_count)
        self.assertEqual(transport_certificate.i32_rejected_count, 0)
        self.assertEqual(certificate.macro_ids[0], "safe-around-wall")
        self.assertFalse(validate_rrlm_macro_snapshot(tampered_snapshot))
        self.assertFalse(validate_rrlm_proposal_certificate(tampered_certificate, snapshot))
        self.assertFalse(validate_rrlm_transport_certificate(tampered_transport, certificate))
        self.assertFalse(validate_rrlm_proposal_certificate(duplicate_macro_certificate, snapshot))
        self.assertFalse(validate_rrlm_proposal_certificate(duplicate_token_certificate, snapshot))

    def test_rrlm_benchmark_matches_non_reversible_baseline_honestly(self) -> None:
        report = run_rrlm_macro_benchmark(episodes=16)

        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)
        self.assertEqual(report.rrlm_cycle_failure_count, 0)
        self.assertTrue(report.snapshot_valid)
        self.assertTrue(report.proposal_certificate_valid)
        self.assertTrue(report.transport_certificate_valid)
        self.assertGreater(report.transport_certificate_i32_admissible_count, 0)
        self.assertEqual(report.transport_certificate_i32_rejected_count, 0)
        self.assertTrue(report.snapshot_tamper_detected)
        self.assertTrue(report.proposal_tamper_detected)
        self.assertTrue(report.transport_tamper_detected)
        self.assertEqual(len(report.snapshot_hash), 64)
        self.assertEqual(len(report.proposal_certificate_hash), 64)
        self.assertEqual(len(report.transport_certificate_hash), 64)
        self.assertLess(report.rrlm_attempts_per_success, report.reversible_only_attempts_per_success)
        self.assertAlmostEqual(report.rrlm_vs_non_reversible_gain, 1.0)
        self.assertGreater(report.rrlm_reuse_gain, 1.5)
        self.assertEqual(report.reversible_only_prefix_reject_count, 16)
        self.assertEqual(report.rrlm_prefix_reject_count, 1)


if __name__ == "__main__":
    unittest.main()
