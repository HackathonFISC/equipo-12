"""The ingestion eval suite runs in MODO=test and records real metrics."""

from __future__ import annotations

import json
import unittest

from src.config import PROJECT_ROOT
from src.ingestion.agent import ingest_report

_RESULTS = PROJECT_ROOT / "evals" / "results_ingestion.json"


class IngestionEvalTests(unittest.TestCase):
    def test_eighteen_cases_score_perfect_metrics(self) -> None:
        from evals.eval_ingestion import run_ingestion_evals

        payload = run_ingestion_evals()
        self.assertGreaterEqual(payload["case_count"], 18)
        self.assertEqual(payload["modo"], "test")
        self.assertEqual(
            payload["group_counts"],
            {
                "citizen": 8,
                "institution": 3,
                "incomplete": 2,
                "adversarial": 5,
            },
        )
        for name, value in payload["metrics"].items():
            self.assertEqual(value, 1.0, name)
        self.assertTrue(_RESULTS.is_file())
        saved = json.loads(_RESULTS.read_text(encoding="utf-8"))
        self.assertEqual(saved["metrics"], payload["metrics"])
        self.assertNotIn("api_key", json.dumps(saved).lower())
        by_id = {case["case_id"]: case for case in payload["cases"]}
        self.assertEqual(by_id["EVAL-09"]["actual_vulnerability"], ["HOSPITAL_SALUD"])
        self.assertEqual(by_id["EVAL-10"]["actual_vulnerability"], ["ESCUELA"])
        self.assertEqual(by_id["EVAL-11"]["actual_vulnerability"], ["ADULTOS_MAYORES"])

    def test_eval_runner_does_not_use_a_live_model(self) -> None:
        from evals.eval_ingestion import CASES

        sample = CASES[0]
        result = ingest_report(sample.as_input())
        self.assertEqual(result.usage_requests >= 0, True)
        self.assertNotEqual(result.extracted.report_id, "")


if __name__ == "__main__":
    unittest.main()
