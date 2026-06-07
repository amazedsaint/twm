from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.real_task_benchmark_manifest import (
    REAL_TASK_MANIFEST_CERTIFICATE_SCHEMA,
    RequirementProbe,
    _default_probe,
    build_real_task_benchmark_manifest,
    build_real_task_manifest_certificate,
    build_real_task_preflight_report,
    fake_probe,
    preflight_runtime_requirement_evidence_hashes,
    preflight_task_asset_content_hashes,
    real_task_preflight_report_hash,
    run_real_task_benchmark_readiness,
    runtime_requirement_count,
    validate_real_task_manifest,
    validate_real_task_manifest_certificate,
    validate_real_task_preflight_report,
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
        self.assertTrue(manifest.specs[0].required_task_assets)
        self.assertTrue(manifest.specs[1].required_task_assets)
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
        self.assertTrue(validate_real_task_preflight_report(result.preflight_report, result.manifest))
        for row in result.preflight_report.rows:
            for probe in row.probes:
                self.assertEqual(len(probe.evidence_hash), 64)

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
        availability.update(
            {
                ("task_asset", asset): True
                for spec in manifest.specs
                for asset in spec.required_task_assets
            }
        )
        result = run_real_task_benchmark_readiness(probe=fake_probe(availability))

        self.assertTrue(validate_real_task_manifest_certificate(result.manifest_certificate, result.manifest, result.preflight_report))
        self.assertTrue(validate_claim_certificate(result.claim_certificate))
        self.assertEqual(result.claim_certificate.status, "supported")
        self.assertTrue(result.preflight_report.ready_to_run_all)
        self.assertEqual(result.preflight_report.ready_domain_count, 4)
        self.assertEqual(result.preflight_report.missing_requirements, ())
        self.assertTrue(validate_real_task_preflight_report(result.preflight_report, result.manifest))
        self.assertEqual(result.manifest_certificate.preflight_report_hash, real_task_preflight_report_hash(result.preflight_report))
        self.assertIn("Readiness gate only", result.claim_certificate.boundary)
        expected_runtime_counts = {
            spec.domain: runtime_requirement_count(spec)
            for spec in manifest.specs
        }
        for row in result.preflight_report.rows:
            runtime_hashes = preflight_runtime_requirement_evidence_hashes(row)
            self.assertEqual(len(runtime_hashes), expected_runtime_counts[row.domain])
            self.assertTrue(all(len(runtime_hash) == 64 for runtime_hash in runtime_hashes))

    def test_manifest_certificate_detects_tampering(self) -> None:
        manifest = build_real_task_benchmark_manifest()
        report = build_real_task_preflight_report(manifest, probe=fake_probe({}))
        certificate = build_real_task_manifest_certificate(manifest, report)

        bad_hash = replace(certificate, manifest_hash="0" * 64, certificate_hash="")
        bad_missing = replace(certificate, ready_to_run_all=True, certificate_hash="")

        self.assertTrue(validate_real_task_manifest_certificate(certificate, manifest, report))
        self.assertFalse(validate_real_task_manifest_certificate(bad_hash, manifest, report))
        self.assertFalse(validate_real_task_manifest_certificate(bad_missing, manifest, report))

    def test_preflight_report_validation_rejects_tampered_probe_evidence_hash(self) -> None:
        manifest = build_real_task_benchmark_manifest()
        report = build_real_task_preflight_report(manifest, probe=fake_probe({}))
        first_row = report.rows[0]
        first_probe = first_row.probes[0]
        bad_probe = replace(first_probe, evidence_hash="0" * 64)
        bad_row = replace(first_row, probes=(bad_probe, *first_row.probes[1:]))
        bad_report = replace(report, rows=(bad_row, *report.rows[1:]))

        self.assertTrue(validate_real_task_preflight_report(report, manifest))
        self.assertFalse(validate_real_task_preflight_report(bad_report, manifest))
        self.assertFalse(validate_real_task_manifest_certificate(build_real_task_manifest_certificate(manifest, bad_report), manifest, bad_report))

    def test_default_env_probe_requires_existing_task_root_directory(self) -> None:
        key = "TRWM_MOTION_BENCHMARK_TASK_ROOT"
        with patch.dict(os.environ, {}, clear=True):
            missing = _default_probe("env_var", key)
        self.assertFalse(missing.available)
        self.assertEqual(missing.evidence, "missing_env_var")

        with tempfile.TemporaryDirectory() as tmp:
            absent_path = str(Path(tmp) / "absent")
            with patch.dict(os.environ, {key: absent_path}, clear=True):
                absent = _default_probe("env_var", key)
            self.assertFalse(absent.available)
            self.assertEqual(absent.evidence, f"missing_path:{absent_path}")

            file_path = Path(tmp) / "not-a-directory"
            file_path.write_text("not a task root", encoding="utf-8")
            with patch.dict(os.environ, {key: str(file_path)}, clear=True):
                file_probe = _default_probe("env_var", key)
            self.assertFalse(file_probe.available)
            self.assertEqual(file_probe.evidence, f"not_directory:{file_path}")

            task_root = Path(tmp) / "tasks"
            task_root.mkdir()
            with patch.dict(os.environ, {key: str(task_root)}, clear=True):
                directory_probe = _default_probe("env_var", key)
            self.assertTrue(directory_probe.available)
            self.assertEqual(directory_probe.evidence, str(task_root))

    def test_task_asset_probes_reject_empty_task_roots_and_accept_shaped_assets(self) -> None:
        manifest = build_real_task_benchmark_manifest()
        with tempfile.TemporaryDirectory() as robotics_tmp, tempfile.TemporaryDirectory() as hardware_tmp:
            env = {
                "TRWM_MOTION_BENCHMARK_TASK_ROOT": robotics_tmp,
                "TRWM_RISCV_FORMAL_TASK_ROOT": hardware_tmp,
            }

            def probe(kind: str, name: str):
                if kind in {"tool", "python_module"}:
                    return RequirementProbe(kind=kind, name=name, available=True, evidence="fake_available")
                return _default_probe(kind, name)

            with patch.dict(os.environ, env, clear=True):
                empty_report = build_real_task_preflight_report(manifest, probe=probe)
            self.assertFalse(empty_report.ready_to_run_all)
            self.assertTrue(any(":task_asset:" in missing for missing in empty_report.missing_requirements))

            with patch.dict(os.environ, env, clear=True):
                for spec in manifest.specs:
                    for asset in spec.required_task_assets:
                        asset_kind, _, template = asset.partition(":")
                        path = Path(os.path.expandvars(template))
                        path.parent.mkdir(parents=True, exist_ok=True)
                        if asset_kind == "dir":
                            path.mkdir(parents=True, exist_ok=True)
                        else:
                            path.write_text("{}", encoding="utf-8")

            with patch.dict(os.environ, env, clear=True):
                shaped_report = build_real_task_preflight_report(manifest, probe=probe)
            self.assertTrue(shaped_report.ready_to_run_all)
            self.assertEqual(shaped_report.missing_requirements, ())
            expected_counts = {
                spec.domain: len(spec.required_task_assets)
                for spec in manifest.specs
            }
            for row in shaped_report.rows:
                content_hashes = preflight_task_asset_content_hashes(row)
                self.assertEqual(len(content_hashes), expected_counts[row.domain])
                self.assertTrue(all(len(content_hash) == 64 for content_hash in content_hashes))

            robotics_row = shaped_report.rows[0]
            robotics_asset_index = next(
                index for index, probe_row in enumerate(robotics_row.probes) if probe_row.kind == "task_asset"
            )
            bad_probe = replace(robotics_row.probes[robotics_asset_index], content_hash="not-a-hash")
            bad_probes = tuple(
                bad_probe if index == robotics_asset_index else probe_row
                for index, probe_row in enumerate(robotics_row.probes)
            )
            bad_row = replace(robotics_row, probes=bad_probes)
            bad_report = replace(shaped_report, rows=(bad_row, *shaped_report.rows[1:]))
            self.assertFalse(validate_real_task_preflight_report(bad_report, manifest))


if __name__ == "__main__":
    unittest.main()
