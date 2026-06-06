from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.core import stable_hash
from trwm.experiments.parallel_replay import demo_state, demo_tokens, run_parallel_replay_benchmark
from trwm.parallel import (
    ParallelReplayCertificate,
    audit_parallel_replay,
    build_parallel_replay_certificate,
    parallel_batches,
    parallel_replay,
    randomized_parallel_replay_trials,
    token_conflicts,
    validate_parallel_replay_certificate,
)
from trwm.reversible import DeltaToken


class ParallelReplayTests(unittest.TestCase):
    def test_token_conflicts_uses_bernstein_read_write_conditions(self) -> None:
        x0 = DeltaToken("x", 0, 1)
        y0 = DeltaToken("y", 0, 1)
        x1 = DeltaToken("x", 1, 2)

        self.assertFalse(token_conflicts(x0, y0))
        self.assertTrue(token_conflicts(x0, x1))

    def test_parallel_batches_preserve_conflict_order(self) -> None:
        self.assertEqual(parallel_batches(demo_tokens()), ((0, 1, 3, 5), (2, 4)))

    def test_parallel_replay_certificate_audits_and_detects_tampering(self) -> None:
        state = demo_state()
        tokens = demo_tokens()
        certificate = build_parallel_replay_certificate(state, tokens)
        tampered = replace(certificate, parallel_state_hash=stable_hash({"tampered": True}))

        self.assertTrue(validate_parallel_replay_certificate(certificate))
        self.assertTrue(audit_parallel_replay(state, tokens, certificate))
        self.assertFalse(validate_parallel_replay_certificate(tampered))
        self.assertFalse(audit_parallel_replay(state, tokens, tampered))

        wrong_conflict_count = replace(certificate, conflict_count=certificate.conflict_count + 1, certificate_hash="")
        self.assertTrue(validate_parallel_replay_certificate(wrong_conflict_count))
        self.assertFalse(audit_parallel_replay(state, tokens, wrong_conflict_count))

    def test_parallel_replay_rejects_conflicting_batch(self) -> None:
        state = demo_state()
        tokens = demo_tokens()

        with self.assertRaisesRegex(ValueError, "conflicting tokens"):
            parallel_replay(state, tokens, ((0, 2),))

    def test_parallel_certificate_rejects_non_integer_batch_indices(self) -> None:
        certificate = build_parallel_replay_certificate(demo_state(), demo_tokens())

        with self.assertRaisesRegex(ValueError, "indices must be integers"):
            ParallelReplayCertificate(
                schema_version=certificate.schema_version,
                token_count=certificate.token_count,
                batch_count=certificate.batch_count,
                conflict_count=certificate.conflict_count,
                max_batch_width=certificate.max_batch_width,
                batches=((0, 1.5),),
                sequential_state_hash=certificate.sequential_state_hash,
                parallel_state_hash=certificate.parallel_state_hash,
            )

    def test_randomized_parallel_replay_trials_have_no_mismatches(self) -> None:
        trials, mismatches = randomized_parallel_replay_trials(seed=7, trials=48, key_count=4, token_count=10)

        self.assertEqual(trials, 48)
        self.assertEqual(mismatches, 0)

    def test_parallel_replay_benchmark_reports_exact_gate_metrics(self) -> None:
        report = run_parallel_replay_benchmark()

        self.assertEqual(report.schema_version, "trwm.parallel_replay_certificate.v1")
        self.assertEqual(report.token_count, 6)
        self.assertEqual(report.batch_count, 2)
        self.assertEqual(report.max_batch_width, 4)
        self.assertEqual(report.conflict_count, 2)
        self.assertEqual(report.batches, ((0, 1, 3, 5), (2, 4)))
        self.assertEqual(report.sequential_state, {"a": 3, "b": 5, "c": 4, "d": 6})
        self.assertEqual(report.parallel_state, report.sequential_state)
        self.assertTrue(report.parallel_equals_sequential)
        self.assertTrue(report.inverse_roundtrip)
        self.assertTrue(report.certificate_valid)
        self.assertTrue(report.audit_valid)
        self.assertTrue(report.tamper_detected)
        self.assertEqual(report.randomized_trial_count, 64)
        self.assertEqual(report.randomized_mismatch_count, 0)
        self.assertEqual(report.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
