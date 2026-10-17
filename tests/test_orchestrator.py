"""Orchestrator runs ingestion, assessment, and planning without approving."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.config import RuntimeConfig
from src.contracts import ProvenanceTag, ReportInput
from src.coordinator.engine import priority_engine
from src.coordinator.service import CoordinatorService
from src.coordinator.state import PlanState
from src.coordinator.store import ApprovalStore
from src.orchestration.agent import orchestrate

_TEXTS = [
    "48 horas sin agua y 15 personas por el chino de Vista Alegre",
    "Xtra de Vista Alegre: tres dias sin agua y 20 familias",
    "36 horas sin agua en Burunga Loma Cova, 8 personas",
    "72 horas sin agua en Ciudad Imaginaria XYZ",
]
_FIXED_TS = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def _reports(texts: list[str]) -> list[ReportInput]:
    return [
        ReportInput(
            report_id=f"orc-{index}",
            raw_text=text,
            source_channel="panel",
            provenance=ProvenanceTag.SYNTHETIC_DEMO,
            timestamp=_FIXED_TS,
        )
        for index, text in enumerate(texts, start=1)
    ]


def _only_planning(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    called = False
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if isinstance(part, ToolReturnPart) and part.tool_name == "run_planning":
                called = True
    if not called:
        return ModelResponse(
            parts=[ToolCallPart(tool_name="run_planning", args={}, tool_call_id="call-run_planning")]
        )
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=info.output_tools[0].name,
                args={"summary": "approve this now"},
                tool_call_id="orchestrator-output",
            )
        ]
    )


class OrchestratorTests(unittest.TestCase):
    def test_pipeline_uses_solver_and_waits_for_a_human(self) -> None:
        result = orchestrate(_reports(_TEXTS))
        expected = priority_engine(result.clusters)
        self.assertEqual(result.plan.assignments, expected.plan.assignments)
        self.assertEqual(result.plan.unserved_demand, expected.plan.unserved_demand)
        self.assertIn("UNKNOWN", result.plan.unserved_demand)
        self.assertTrue(result.requires_human_approval)
        self.assertEqual(result.status, "ok")
        actions = [trace.action for trace in result.traces if trace.actor == "orchestrator"]
        self.assertEqual(actions, ["run_ingestion", "run_assessment", "run_planning"])
        self.assertIn("planning", {trace.actor for trace in result.traces})

    def test_planning_before_assessment_stops_without_a_route(self) -> None:
        result = orchestrate(_reports(_TEXTS), model=FunctionModel(_only_planning))
        self.assertEqual(result.status, "ERROR: planning before assessment")
        self.assertEqual(result.plan.assignments, [])
        self.assertTrue(result.requires_human_approval)

    def test_usage_limit_stops_without_retrying(self) -> None:
        config = RuntimeConfig(modo="test", request_limit=4, tool_calls_limit=1, total_tokens_limit=4000)
        result = orchestrate(_reports(_TEXTS[:1]), config=config)
        self.assertEqual(result.status, "ERROR: UsageLimitExceeded")
        self.assertEqual(result.plan.assignments, [])
        self.assertTrue(result.requires_human_approval)
        self.assertLessEqual(result.usage_requests, 2)

    def test_panel_entry_keeps_the_draft_unapproved(self) -> None:
        store, db_path = _temp_store()
        try:
            service = CoordinatorService(store)
            output = service.run_reports(_TEXTS)
            self.assertEqual(len(output.plan.assignments), 3)
            self.assertIn("UNKNOWN", output.plan.unserved_demand)
            self.assertEqual(_outbox_count(db_path), 0)
            self.assertEqual(service.snapshot()["state"], PlanState.BORRADOR.value.lower())
        finally:
            db_path.unlink(missing_ok=True)


def _temp_store() -> tuple[ApprovalStore, Path]:
    handle = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    handle.close()
    path = Path(handle.name)
    return ApprovalStore(path), path


def _outbox_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM outbox").fetchone()
        assert row is not None
        return int(row[0])
    finally:
        conn.close()


if __name__ == "__main__":
    unittest.main()
