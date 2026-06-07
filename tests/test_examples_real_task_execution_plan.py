from __future__ import annotations

from dataclasses import replace
import json
import unittest

from examples.real_task_benchmark_manifest import build_real_task_benchmark_manifest, fake_probe
from examples.real_task_execution_plan import (
    ADAPTER_MODULE_BY_DOMAIN,
    REAL_TASK_BUNDLE_COMMAND,
    REAL_TASK_EXECUTION_PLAN_CERTIFICATE_SCHEMA,
    REAL_TASK_EXECUTION_PLAN_REPORT_SCHEMA,
    REAL_TASK_PREFLIGHT_COMMAND,
    REAL_TASK_SUITE_COMMAND,
    RealTaskExecutionPlanResult,
    result_as_dict,
    run_real_task_execution_plan,
    validate_real_task_execution_plan,
    validate_real_task_execution_plan_certificate,
    validate_real_task_execution_plan_report,
)


class RealTaskExecutionPlanTests(unittest.TestCase):
    def test_default_execution_plan_binds_current_preflight_failures(self) -> None:
        result = run_real_task_execution_plan()
        report = result.plan_report
        certificate = result.plan_certificate

        self.assertEqual(report.schema_version, REAL_TASK_EXECUTION_PLAN_REPORT_SCHEMA)
        self.assertEqual(certificate.schema_version, REAL_TASK_EXECUTION_PLAN_CERTIFICATE_SCHEMA)
        self.assertEqual(report.preflight_command, REAL_TASK_PREFLIGHT_COMMAND)
        self.assertEqual(report.suite_command, REAL_TASK_SUITE_COMMAND)
        self.assertEqual(report.bundle_command, REAL_TASK_BUNDLE_COMMAND)
        self.assertEqual(report.command_sequence, (report.preflight_command, *report.adapter_commands, report.suite_command, report.bundle_command))
        self.assertEqual(len(certificate.command_sequence_hash), 64)
        self.assertEqual(report.domain_count, 4)
        self.assertEqual(certificate.domains, ("robotics", "hardware", "program", "quantum"))
        self.assertFalse(report.ready_to_run_all)
        self.assertFalse(certificate.ready_to_run_all)
        self.assertEqual(report.missing_requirements, result.preflight_report.missing_requirements)
        self.assertEqual(certificate.missing_requirements, report.missing_requirements)
        self.assertTrue(certificate.all_rows_match_manifest)
        self.assertTrue(certificate.all_rows_match_preflight)
        self.assertTrue(certificate.all_adapter_commands_bound)
        self.assertTrue(certificate.all_sources_bound)
        for row in report.rows:
            self.assertEqual(row.adapter_module, ADAPTER_MODULE_BY_DOMAIN[row.domain])
            self.assertEqual(row.adapter_command, f"python3 -m {row.adapter_module}")
            self.assertEqual(len(row.row_hash), 64)
        self.assertTrue(validate_real_task_execution_plan_report(report, result.manifest, result.preflight_report, result.manifest_certificate))
        self.assertTrue(validate_real_task_execution_plan_certificate(certificate, report, result.manifest, result.preflight_report, result.manifest_certificate))
        self.assertTrue(validate_real_task_execution_plan(result))
        json.dumps(result_as_dict(result), sort_keys=True)

    def test_execution_plan_can_be_ready_under_available_fake_preflight(self) -> None:
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

        result = run_real_task_execution_plan(probe=fake_probe(availability))

        self.assertTrue(result.plan_report.ready_to_run_all)
        self.assertTrue(result.plan_certificate.ready_to_run_all)
        self.assertEqual(result.plan_report.ready_domain_count, 4)
        self.assertEqual(result.plan_report.missing_requirements, ())
        self.assertTrue(all(row.ready for row in result.plan_report.rows))
        self.assertTrue(validate_real_task_execution_plan(result))

    def test_tampered_plan_row_fails_validation(self) -> None:
        result = run_real_task_execution_plan()
        first_row = result.plan_report.rows[0]
        bad_row = replace(first_row, adapter_command="python3 -m examples.wrong_adapter", row_hash="")
        bad_report = replace(result.plan_report, rows=(bad_row, *result.plan_report.rows[1:]))
        bad_result = RealTaskExecutionPlanResult(
            manifest=result.manifest,
            preflight_report=result.preflight_report,
            manifest_certificate=result.manifest_certificate,
            plan_report=bad_report,
            plan_certificate=result.plan_certificate,
        )

        self.assertFalse(validate_real_task_execution_plan_report(bad_report, result.manifest, result.preflight_report, result.manifest_certificate))
        self.assertFalse(validate_real_task_execution_plan(bad_result))

    def test_tampered_plan_certificate_fails_validation(self) -> None:
        result = run_real_task_execution_plan()
        bad_certificate = replace(result.plan_certificate, bundle_command="python3 -m examples.real_task_benchmark_suite", certificate_hash="")
        bad_result = RealTaskExecutionPlanResult(
            manifest=result.manifest,
            preflight_report=result.preflight_report,
            manifest_certificate=result.manifest_certificate,
            plan_report=result.plan_report,
            plan_certificate=bad_certificate,
        )

        self.assertFalse(
            validate_real_task_execution_plan_certificate(
                bad_certificate,
                result.plan_report,
                result.manifest,
                result.preflight_report,
                result.manifest_certificate,
            )
        )
        self.assertFalse(validate_real_task_execution_plan(bad_result))


if __name__ == "__main__":
    unittest.main()
