from __future__ import annotations

from dataclasses import replace
import unittest

from examples.real_task_benchmark_manifest import (
    REAL_TASK_MANIFEST_CERTIFICATE_SCHEMA,
    build_real_task_benchmark_manifest,
    build_real_task_manifest_certificate,
    build_real_task_preflight_report,
    fake_probe,
    run_real_task_benchmark_readiness,
    validate_real_task_manifest,
    validate_real_task_manifest_certificate,
)
from trwm.claims import validate_claim_certificate


class RealTaskBenchmarkManifestTests(unittest.TestCase):
    def test_real_task_manifest_binds_four_external_benchmark_domains(self) -> None:
        manifest = build_real_task_benchmark_manifest()

        self.assertTrue(validate_real_task_manifest(manifest))
        self.assertEqual(manifest.domains, ("robotics", "hardware", "program", "quantum"))
        self.assertEqual(len(manifest.specs), 4)
        self.assertTrue(all(spec.source_urls for spec in manifest.specs))
        self.assertTrue(all(spec.command_templates for spec in manifest.specs))
        self.assertIn("TRWM_MOTION_BENCHMARK_TASK_ROOT", manifest.specs[0].required_env_vars)
        self.assertIn("TRWM_RISCV_FORMAL_TASK_ROOT", manifest.specs[1].required_env_vars)
        self.assertTrue(set(spec.train_split_id for spec in manifest.specs).isdisjoint(spec.held_out_split_id for spec in manifest.specs))

    def test_readiness_fails_closed_when_external_requirements_are_missing(self) -> None:
        result = run_real_task_benchmark_readiness(probe=fake_probe({}))

        self.assertEqual(result.manifest_certificate.schema_version, REAL_TASK_MANIFEST_CERTIFICATE_SCHEMA)
        self.assertTrue(validate_real_task_manifest(result.manifest))
        self.assertTrue(validate_real_task_manifest_certificate(result.manifest_certificate, result.manifest, result.preflight_report))
        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        self.assertEqual(result.claim_certificate.status, "rejected")
        self.assertEqual(result.preflight_report.domain_count, 4)
        self.assertEqual(result.preflight_report.ready_domain_count, 0)
        self.assertFalse(result.preflight_report.ready_to_run_all)
        self.assertTrue(result.preflight_report.missing_requirements)

    def test_readiness_can_support_only_adapter_readiness_when_all_requirements_probe_available(self) -> None:
        manifest = build_real_task_benchmark_manifest()
        availability = {
            ("tool", tool): True
            for spec in manifest.specs
            for tool in spec.required_tools
        }
        availability.update(
            {
                ("python_module", module): True
                for spec in manifest.specs
                for module in spec.required_python_modules
            }
        )
        availability.update(
            {
                ("env_var", env_var): True
                for spec in manifest.specs
                for env_var in spec.required_env_vars
            }
        )
        result = run_real_task_benchmark_readiness(probe=fake_probe(availability))

        self.assertTrue(validate_real_task_manifest_certificate(result.manifest_certificate, result.manifest, result.preflight_report))
        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        self.assertEqual(result.claim_certificate.status, "supported")
        self.assertTrue(result.preflight_report.ready_to_run_all)
        self.assertEqual(result.preflight_report.ready_domain_count, 4)
        self.assertEqual(result.preflight_report.missing_requirements, ())
        self.assertIn("Readiness gate only", result.claim_certificate.boundary)

    def test_manifest_certificate_detects_tampering(self) -> None:
        manifest = build_real_task_benchmark_manifest()
        report = build_real_task_preflight_report(manifest, probe=fake_probe({}))
        certificate = build_real_task_manifest_certificate(manifest, report)

        bad_hash = replace(certificate, manifest_hash="0" * 64, certificate_hash="")
        bad_missing = replace(certificate, ready_to_run_all=True, certificate_hash="")

        self.assertTrue(validate_real_task_manifest_certificate(certificate, manifest, report))
        self.assertFalse(validate_real_task_manifest_certificate(bad_hash, manifest, report))
        self.assertFalse(validate_real_task_manifest_certificate(bad_missing, manifest, report))


if __name__ == "__main__":
    unittest.main()
