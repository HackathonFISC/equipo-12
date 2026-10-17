"""The allocation eval suite runs in MODO=test and records real metrics."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.config import PROJECT_ROOT

_RESULTS = PROJECT_ROOT / "evals" / "results_allocation.json"


class AllocationEvalTests(unittest.TestCase):
    def test_sixteen_cases_score_perfect_metrics(self) -> None:
        from evals.eval_allocation import run_allocation_evals

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "results_allocation.json"
            payload = run_allocation_evals(out)
            self.assertGreaterEqual(payload["case_count"], 16)
            self.assertEqual(payload["modo"], "test")
            self.assertEqual(
                payload["group_counts"],
                {
                    "priority_order": 4,
                    "volume_invariance": 4,
                    "constraint_compliance": 4,
                    "demand_coverage": 4,
                },
            )
            metrics = payload["metrics"]
            for name in (
                "case_accuracy",
                "priority_order_accuracy",
                "volume_invariance_rate",
                "constraint_compliance_rate",
                "demand_coverage_accuracy",
            ):
                self.assertEqual(metrics[name], 1.0, name)
            self.assertTrue(out.is_file())
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(saved["metrics"], payload["metrics"])
            self.assertNotIn("api_key", json.dumps(saved).lower())

        self.assertTrue(_RESULTS.is_file())
        tracked = json.loads(_RESULTS.read_text(encoding="utf-8"))
        for name, value in tracked["metrics"].items():
            self.assertEqual(value, 1.0, f"tracked {name}")

    def test_eval_runner_refuses_prod_mode(self) -> None:
        from evals.eval_allocation import run_allocation_evals

        with mock.patch.dict(os.environ, {"MODO": "live"}, clear=False):
            with self.assertRaises(RuntimeError) as ctx:
                run_allocation_evals()
        self.assertIn("MODO=test", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
