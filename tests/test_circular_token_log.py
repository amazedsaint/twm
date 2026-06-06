from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.core import stable_hash
from trwm.experiments.circular_token_log import demo_state, demo_tokens, run_circular_token_log_benchmark
from trwm.reversible import BlockToken, DeltaToken
from trwm.token_log import (
    CircularTokenLog,
    audit_circular_token_log,
    build_circular_token_log_certificate,
    compact_token_prefix,
    randomized_circular_token_log_trials,
    replay_circular_token_log,
    validate_circular_token_log_certificate,
)


class CircularTokenLogTests(unittest.TestCase):
    def test_compact_token_prefix_collapses_overwritten_keys(self) -> None:
        compacted = compact_token_prefix(demo_state(), demo_tokens()[:5])

        self.assertEqual(tuple(token.key for token in compacted), ("b", "c"))
        self.assertEqual(tuple((token.before, token.after) for token in compacted), ((0, 2), (0, 4)))

    def test_circular_log_keeps_bounded_suffix(self) -> None:
        log = CircularTokenLog.from_tokens(demo_state(), demo_tokens(), capacity=3)

        self.assertEqual(log.total_token_count, 8)
        self.assertEqual(log.compacted_prefix_count, 5)
        self.assertEqual(len(log.suffix_tokens), 3)
        self.assertEqual(tuple(token.key for token in log.compacted_tokens), ("b", "c"))
        self.assertEqual(log.replay(), {"a": 7, "b": 5, "c": 4, "d": 6})

    def test_circular_log_certificate_audits_and_detects_tampering(self) -> None:
        state = demo_state()
        tokens = demo_tokens()
        certificate = build_circular_token_log_certificate(state, tokens, capacity=3)
        tampered = replace(certificate, final_state_hash=stable_hash({"tampered": True}), certificate_hash="")
        wrong_original = tokens[:-1] + (DeltaToken("a", 0, 8),)

        self.assertTrue(validate_circular_token_log_certificate(certificate))
        self.assertTrue(audit_circular_token_log(state, certificate, tokens))
        self.assertTrue(validate_circular_token_log_certificate(tampered))
        self.assertFalse(audit_circular_token_log(state, tampered, tokens))
        self.assertFalse(audit_circular_token_log(state, certificate, wrong_original))

    def test_circular_log_replay_matches_full_replay_and_inverse(self) -> None:
        state = demo_state()
        tokens = demo_tokens()
        certificate = build_circular_token_log_certificate(state, tokens, capacity=3)
        compacted = replay_circular_token_log(state, certificate.compacted_tokens, certificate.suffix_tokens)
        full = BlockToken.of(tokens).apply(state)
        restored = BlockToken.of(certificate.suffix_tokens).inverse().apply(compacted)
        restored = BlockToken.of(certificate.compacted_tokens).inverse().apply(restored)

        self.assertEqual(compacted, full)
        self.assertEqual(restored, state)

    def test_randomized_circular_log_trials_have_no_mismatches(self) -> None:
        trials, mismatches = randomized_circular_token_log_trials(seed=5, trials=48, key_count=4, token_count=12, capacity=3)

        self.assertEqual(trials, 48)
        self.assertEqual(mismatches, 0)

    def test_circular_token_log_benchmark_reports_exact_gate_metrics(self) -> None:
        report = run_circular_token_log_benchmark()

        self.assertEqual(report.schema_version, "trwm.circular_token_log_certificate.v1")
        self.assertEqual(report.capacity, 3)
        self.assertEqual(report.total_token_count, 8)
        self.assertEqual(report.compacted_prefix_count, 5)
        self.assertEqual(report.suffix_count, 3)
        self.assertEqual(report.compacted_delta_count, 2)
        self.assertEqual(report.retained_replay_token_count, 5)
        self.assertEqual(report.replay_tokens_saved, 3)
        self.assertEqual(report.compacted_token_summary, ("b:0->2", "c:0->4"))
        self.assertEqual(report.suffix_token_summary, ("b:2->5", "d:0->6", "a:0->7"))
        self.assertEqual(report.full_state, {"a": 7, "b": 5, "c": 4, "d": 6})
        self.assertEqual(report.compacted_state, report.full_state)
        self.assertTrue(report.full_equals_compacted)
        self.assertTrue(report.inverse_roundtrip)
        self.assertTrue(report.certificate_valid)
        self.assertTrue(report.audit_valid)
        self.assertTrue(report.tamper_detected)
        self.assertEqual(report.randomized_trial_count, 64)
        self.assertEqual(report.randomized_mismatch_count, 0)
        self.assertEqual(report.invalid_commit_count, 0)


if __name__ == "__main__":
    unittest.main()
