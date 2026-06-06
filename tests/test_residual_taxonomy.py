from __future__ import annotations

from dataclasses import replace
import unittest

from trwm.experiments.residual_taxonomy import run_residual_taxonomy_benchmark
from trwm.residuals import (
    RESIDUAL_SCHEMA,
    ResidualTaxonomyMemory,
    normalize_residual,
    residual_learning_hash,
    validate_residual_signal,
)


class ResidualTaxonomyTests(unittest.TestCase):
    def test_snake_and_camel_residuals_share_learning_hash(self) -> None:
        snake = normalize_residual(
            {"kind": "stock_shortage", "sku": "widget", "repair": {"quantity": 2}},
            status="reject",
            verifier_id="inventory_reservation_verifier",
            verifier_version="1.0",
        )
        camel = normalize_residual(
            {"kind": "stockShortage", "sku": "widget", "repair": {"quantity": 2}},
            status="reject",
            verifier_id="inventory_reservation_verifier",
            verifier_version="1.0",
        )

        self.assertEqual(snake.kind, "stock_shortage")
        self.assertEqual(camel.kind, "stock_shortage")
        self.assertEqual(residual_learning_hash(snake), residual_learning_hash(camel))
        self.assertNotEqual(snake.residual_hash, camel.residual_hash)

    def test_duplicate_aliases_are_allowed_only_when_equal(self) -> None:
        signal = normalize_residual(
            {"kind": "verifier_budget_exhausted", "required_verifier_cost": 7, "requiredVerifierCost": 7},
            status="abstain",
            verifier_id="v",
            verifier_version="1",
        )

        self.assertIn("7", signal.fields)
        with self.assertRaises(ValueError):
            normalize_residual(
                {"kind": "verifier_budget_exhausted", "required_verifier_cost": 7, "requiredVerifierCost": 9},
                status="abstain",
                verifier_id="v",
                verifier_version="1",
            )

    def test_signal_hash_detects_tampering(self) -> None:
        signal = normalize_residual(
            {"kind": "projection_contract_violation", "missing_fields": ("safety_clearance",)},
            status="reject",
            verifier_id="projection_contract_guard",
            verifier_version="1.0",
        )
        tampered = replace(signal, category="unknown")

        self.assertTrue(validate_residual_signal(signal))
        self.assertFalse(validate_residual_signal(tampered))

    def test_residual_taxonomy_memory_and_report(self) -> None:
        report = run_residual_taxonomy_benchmark()

        self.assertEqual(report.signal_count, 3)
        self.assertEqual(report.schema_version, RESIDUAL_SCHEMA)
        self.assertEqual(report.categories, {"resource": 1, "coverage": 1, "budget": 1})
        self.assertEqual(report.resource_kind, "stock_shortage")
        self.assertEqual(report.coverage_kind, "projection_contract_violation")
        self.assertEqual(report.budget_kind, "verifier_budget_exhausted")
        self.assertEqual(report.resource_category, "resource")
        self.assertEqual(report.coverage_category, "coverage")
        self.assertEqual(report.budget_category, "budget")
        self.assertEqual(report.stock_shortage_fields, ("widget",))
        self.assertEqual(report.projection_missing_fields, ("safety_clearance",))
        self.assertEqual(report.budget_fields, ("7", "4"))
        self.assertEqual(report.top_stock_shortage_repair_hint, "quantity=2")
        self.assertTrue(report.snake_camel_learning_hash_equal)
        self.assertTrue(report.raw_residual_hash_distinct)
        self.assertTrue(report.tamper_detected)
        self.assertTrue(report.ledger_audit)
        self.assertEqual(report.invalid_commit_count, 0)

        memory = ResidualTaxonomyMemory()
        memory.update(
            normalize_residual(
                {"kind": "stock_shortage", "sku": "widget", "repair": {"quantity": 2}},
                status="reject",
                verifier_id="v",
                verifier_version="1",
            )
        )
        self.assertEqual(memory.top_repair_hint("stockShortage"), "quantity=2")


if __name__ == "__main__":
    unittest.main()
