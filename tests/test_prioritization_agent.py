"""Prioritization agent in MODO=test, with no live provider."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone

os.environ["MODO"] = "test"

from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from src.config import RuntimeConfig
from src.contracts import (
    NormalizedIncidentCluster,
    ProvenanceTag,
    ReportInput,
    SectorId,
    VulnerabilityFlag,
)
from src.ingestion.agent import ingest_report
from src.ingestion.deduplicator import deduplicate_reports
from src.priority import rank_clusters, score_cluster
from src.prioritization.agent import _derived_risks, prioritize_cluster, prioritize_clusters

_SECRET = "sk-secretkey1234567890"
_HALLUCINATED_EVIDENCE = {
    "duration": "HALLUCINATED duration of 9999 hours",
    "affected": "HALLUCINATED affected count of 0",
    "vulnerability": "HALLUCINATED no vulnerability",
}


def _cluster(
    cluster_id: str = "c1",
    sector_id: SectorId = SectorId.ARRAIJAN_VISTA_ALEGRE,
    hours: int | None = 84,
    affected: int | None = 25000,
    flags: list[VulnerabilityFlag] | None = None,
    report_count: int = 1,
    uncertainties: list[str] | None = None,
    requires_human_review: bool = False,
) -> NormalizedIncidentCluster:
    if flags is None:
        flags = [VulnerabilityFlag.ESCUELA]
    return NormalizedIncidentCluster(
        cluster_id=cluster_id,
        sector_id=sector_id,
        source_report_ids=[f"{cluster_id}-r{index}" for index in range(report_count)],
        report_count=report_count,
        max_duration_hours=hours,
        estimated_affected_count=affected,
        vulnerability_flags=flags,
        requires_human_review=requires_human_review,
        uncertainties=list(uncertainties or []),
    )


def _citizen(report_id: str, text: str) -> ReportInput:
    return ReportInput(
        report_id=report_id,
        raw_text=text,
        source_channel="whatsapp",
        provenance=ProvenanceTag.SYNTHETIC_DEMO,
        timestamp=datetime(2026, 10, 16, tzinfo=timezone.utc),
    )


def _raise_status(status_code: int):
    def _function(messages, info) -> ModelResponse:
        raise ModelHTTPError(status_code=status_code, model_name="test")

    return _function


def _raise_unexpected(messages, info) -> ModelResponse:
    raise UnexpectedModelBehavior("simulated failure")


def _wrong_draft(info) -> ModelResponse:
    output_tool = info.output_tools[0].name
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=output_tool,
                args={
                    "factors": [
                        {
                            "name": name,
                            "evidence": _HALLUCINATED_EVIDENCE[name],
                            "uncertainty": "",
                        }
                        for name in ("duration", "affected", "vulnerability")
                    ],
                    "risks": [],
                    "uncertainties": [],
                },
                tool_call_id="hallucinated-draft",
            )
        ]
    )


def _skip_tools(messages, info) -> ModelResponse:
    """Return a qualitative draft without calling either code tool."""
    return _wrong_draft(info)


def _lie_after_tools(messages, info) -> ModelResponse:
    """Call both tools, then ignore their evidence in the draft."""
    seen: set[str] = set()
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if isinstance(part, ToolReturnPart):
                seen.add(part.tool_name)
    if "inspect_cluster_evidence" not in seen or "compute_deterministic_priority" not in seen:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="inspect_cluster_evidence",
                    args={},
                    tool_call_id="inspect-evidence",
                ),
                ToolCallPart(
                    tool_name="compute_deterministic_priority",
                    args={},
                    tool_call_id="score-priority",
                ),
            ]
        )
    return _wrong_draft(info)


def _empty_draft(messages, info) -> ModelResponse:
    """Return an empty qualitative draft and skip both code tools."""
    output_tool = info.output_tools[0].name
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=output_tool,
                args={"factors": [], "risks": [], "uncertainties": []},
                tool_call_id="empty-draft",
            )
        ]
    )


class PrioritizationAgentTests(unittest.TestCase):
    def test_prioritize_cluster_calls_tools_and_records_traces(self) -> None:
        cluster = _cluster()
        item, traces, usage_requests = prioritize_cluster(cluster)

        actions = [trace.action for trace in traces]
        self.assertIn("inspect_cluster_evidence", actions)
        self.assertIn("compute_deterministic_priority", actions)
        self.assertTrue(all(trace.actor == "prioritization" for trace in traces))
        self.assertGreaterEqual(usage_requests, 2)
        cluster_traces = [trace for trace in traces if trace.action == "prioritize_cluster"]
        self.assertEqual(len(cluster_traces), 1)
        self.assertEqual(cluster_traces[0].status, "ok")
        self.assertTrue(
            all(trace.status == "ok" for trace in traces if trace.action in {
                "inspect_cluster_evidence",
                "compute_deterministic_priority",
                "prioritize_cluster",
            })
        )
        self.assertEqual(item.priority, score_cluster(cluster))
        self.assertFalse(item.requires_human_review)

    def test_prioritize_clusters_ranks_like_deterministic_scorer(self) -> None:
        clusters = [
            _cluster(cluster_id="c-mid-b", hours=48, affected=1000, flags=[VulnerabilityFlag.ESCUELA]),
            _cluster(cluster_id="c-low", hours=2, affected=10, flags=[VulnerabilityFlag.NINGUNA]),
            _cluster(cluster_id="c-mid-a", hours=48, affected=1000, flags=[VulnerabilityFlag.ESCUELA]),
            _cluster(
                cluster_id="c-high",
                hours=168,
                affected=40000,
                flags=[VulnerabilityFlag.HOSPITAL_SALUD],
            ),
            _cluster(
                cluster_id="c-elderly",
                hours=36,
                affected=200,
                flags=[VulnerabilityFlag.ADULTOS_MAYORES],
            ),
        ]
        result = prioritize_clusters(clusters)

        self.assertEqual(result.priorities, rank_clusters(clusters))
        self.assertEqual(result.assessments, [item.assessment for item in result.items])
        self.assertEqual(result.priorities, [item.priority for item in result.items])
        self.assertEqual(
            [item.cluster_id for item in result.priorities],
            ["c-high", "c-mid-a", "c-mid-b", "c-elderly", "c-low"],
        )
        flags_by_id = {
            item.cluster.cluster_id: item.cluster.vulnerability_flags for item in result.items
        }
        self.assertIn(VulnerabilityFlag.HOSPITAL_SALUD, flags_by_id["c-high"])
        self.assertIn(VulnerabilityFlag.ESCUELA, flags_by_id["c-mid-a"])
        self.assertEqual(flags_by_id["c-elderly"], [VulnerabilityFlag.ADULTOS_MAYORES])
        for left, right in zip(result.priorities, result.priorities[1:]):
            if left.score == right.score:
                self.assertLess(left.cluster_id, right.cluster_id)
            else:
                self.assertGreater(left.score, right.score)

    def test_complaint_volume_does_not_change_score_or_breakdown(self) -> None:
        single = _cluster(cluster_id="volume", report_count=1, hours=36, affected=800)
        flooded = _cluster(cluster_id="volume", report_count=50, hours=36, affected=800)
        single_item, _, _ = prioritize_cluster(single)
        flooded_item, _, _ = prioritize_cluster(flooded)

        self.assertEqual(single_item.priority.score, flooded_item.priority.score)
        self.assertEqual(single_item.priority.breakdown, flooded_item.priority.breakdown)
        self.assertEqual(single_item.priority.score, score_cluster(single).score)

    def test_hallucinated_draft_keeps_deterministic_score_and_evidence(self) -> None:
        cluster = _cluster(
            cluster_id="hallucinated",
            sector_id=SectorId.CHORRERA_BARRIO_COLON,
            hours=48,
            affected=1200,
            flags=[VulnerabilityFlag.HOSPITAL_SALUD, VulnerabilityFlag.ESCUELA],
            uncertainties=["alias de sector sin confirmar"],
        )
        expected = score_cluster(cluster)
        reasons = {row.factor: row.reason for row in expected.breakdown}

        drafts = (
            ("skip-tools", FunctionModel(_skip_tools)),
            ("lie-after-tools", FunctionModel(_lie_after_tools)),
            ("empty-draft", FunctionModel(_empty_draft)),
        )
        for label, model in drafts:
            with self.subTest(model=label):
                item, _, _ = prioritize_cluster(cluster, model=model)
                self.assertEqual(item.priority, expected)
                self.assertEqual(item.priority.score, expected.score)
                self.assertEqual(
                    [factor.name for factor in item.assessment.factors[:3]],
                    ["duration", "affected", "vulnerability"],
                )
                by_name = {factor.name: factor for factor in item.assessment.factors}
                for name, reason in reasons.items():
                    self.assertEqual(by_name[name].evidence, reason)
                    self.assertNotIn("HALLUCINATED", by_name[name].evidence)
                self.assertEqual(item.assessment.risks, _derived_risks(cluster))
                self.assertEqual(item.assessment.uncertainties, cluster.uncertainties)
                if label == "empty-draft":
                    self.assertEqual(
                        [factor.name for factor in item.assessment.factors],
                        ["duration", "affected", "vulnerability"],
                    )

    def test_missing_sector_duration_or_affected_requires_human_review(self) -> None:
        cases = (
            _cluster(cluster_id="unknown-sector", sector_id=SectorId.UNKNOWN),
            _cluster(cluster_id="missing-hours", hours=None),
            _cluster(cluster_id="missing-affected", affected=None),
        )
        for cluster in cases:
            with self.subTest(cluster_id=cluster.cluster_id):
                item, _, _ = prioritize_cluster(cluster)
                self.assertTrue(item.requires_human_review)
                self.assertEqual(item.priority, score_cluster(cluster))

    def test_invalid_numbers_skip_the_model(self) -> None:
        cases = (
            _cluster(cluster_id="negative-hours", hours=-3, affected=10),
            _cluster(cluster_id="negative-affected", hours=4, affected=-8),
        )
        for cluster in cases:
            with self.subTest(cluster_id=cluster.cluster_id):
                item, traces, usage_requests = prioritize_cluster(cluster)
                self.assertEqual(usage_requests, 0)
                self.assertEqual(item.priority.score, 0.0)
                self.assertEqual(
                    [factor.name for factor in item.assessment.factors],
                    ["duration", "affected", "vulnerability"],
                )
                self.assertTrue(item.requires_human_review)
                self.assertEqual(traces[-1].action, "prioritize_cluster")
                self.assertEqual(traces[-1].status, "ERROR: ValueError")
                self.assertEqual(traces[-1].actor, "prioritization")

    def test_model_failures_keep_deterministic_score(self) -> None:
        cluster = _cluster(cluster_id="model-error", hours=30, affected=400)
        expected = score_cluster(cluster)
        cases = (
            (
                "usage-limit",
                {},
                {"config": RuntimeConfig(request_limit=1)},
                "ERROR: UsageLimitExceeded",
            ),
            (
                "http-429",
                {"model": FunctionModel(_raise_status(429))},
                {},
                "ERROR: 429",
            ),
            (
                "http-500",
                {"model": FunctionModel(_raise_status(500))},
                {},
                "ERROR: ModelHTTPError",
            ),
            (
                "unexpected",
                {"model": FunctionModel(_raise_unexpected)},
                {},
                "ERROR: UnexpectedModelBehavior",
            ),
        )
        for name, model_kwargs, config_kwargs, status in cases:
            with self.subTest(name=name):
                item, traces, _ = prioritize_cluster(cluster, **model_kwargs, **config_kwargs)
                self.assertEqual(item.priority, expected)
                self.assertTrue(item.requires_human_review)
                self.assertEqual(traces[-1].status, status)
                self.assertTrue(traces[-1].status.startswith("ERROR:"))
                self.assertEqual(traces[-1].actor, "prioritization")

    def test_secrets_in_cluster_uncertainty_are_redacted(self) -> None:
        cluster = _cluster(
            cluster_id="secret-cluster",
            uncertainties=[f"reporte cita {_SECRET} en el texto"],
        )
        _, traces, _ = prioritize_cluster(cluster)
        inputs = "\n".join(trace.input_summary for trace in traces)
        outputs = "\n".join(trace.output_summary for trace in traces)
        self.assertNotIn(_SECRET, inputs)
        self.assertNotIn(_SECRET, outputs)
        self.assertIn("[REDACTED]", inputs)
        self.assertTrue(all(trace.actor == "prioritization" for trace in traces))

    def test_pipeline_ranks_critical_outage_above_repeated_minor_complaints(self) -> None:
        hospital_text = (
            "El Hospital Nicolas Solano lleva 24 horas sin agua y atiende 200 personas"
        )
        minor_text = "2 horas sin agua y 3 personas por el chino de Vista Alegre"
        reports = [_citizen("SYN-HOSPITAL", hospital_text)]
        reports.extend(
            _citizen(f"SYN-MINOR-{index}", minor_text) for index in range(1, 7)
        )

        extracted = [ingest_report(report).extracted for report in reports]
        clusters = deduplicate_reports(extracted)
        ranked = prioritize_clusters(clusters)

        self.assertEqual(ranked.priorities, rank_clusters(clusters))
        hospitals = [
            item
            for item in ranked.items
            if VulnerabilityFlag.HOSPITAL_SALUD in item.cluster.vulnerability_flags
        ]
        minors = [
            item
            for item in ranked.items
            if item.cluster.sector_id is SectorId.ARRAIJAN_VISTA_ALEGRE
        ]
        self.assertEqual(len(hospitals), 1)
        self.assertEqual(hospitals[0].cluster.sector_id, SectorId.CHORRERA_BARRIO_COLON)
        self.assertEqual(len(minors), 1)
        self.assertEqual(minors[0].cluster.report_count, 6)
        self.assertGreater(hospitals[0].priority.score, minors[0].priority.score)
        self.assertLess(
            ranked.priorities.index(hospitals[0].priority),
            ranked.priorities.index(minors[0].priority),
        )


if __name__ == "__main__":
    unittest.main()
