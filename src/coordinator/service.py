"""Coordinator glue: ingest, consolidate, draft, review, and human decision.

Each ``CoordinatorService`` instance owns at most one plan; start a new instance
for a new batch of reports.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from src.contracts import (
    DecisionAction,
    ExecutionResult,
    HumanDecision,
    NormalizedIncidentCluster,
    ProvenanceTag,
    ReportExtracted,
    ReportInput,
    TraceEntry,
)
from src.coordinator.engine import EngineOutput, PlanEngine, demo_engine
from src.coordinator.state import PlanState, transition
from src.coordinator.store import ApprovalStore
from src.ingestion.agent import IngestionResult, ingest_report
from src.ingestion.deduplicator import deduplicate_reports

_FIXED_REPORT_TS = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
_SOURCE_CHANNEL = "panel"
_PROVENANCE = ProvenanceTag.SYNTHETIC_DEMO


class CoordinatorService:
    def __init__(
        self,
        store: ApprovalStore,
        engine: PlanEngine = demo_engine,
    ) -> None:
        self._store = store
        self._engine = engine
        self._next_report_num = 1
        self._extracted: list[ReportExtracted] = []
        self._traces: list[TraceEntry] = []
        self._plan_id: str | None = None
        self._payload_json: str | None = None
        self._submitted = False
        self._state: PlanState | None = None
        self._execution: ExecutionResult | None = None
        self._draft: EngineOutput | None = None

    @property
    def traces(self) -> list[TraceEntry]:
        return list(self._traces)

    def ingest_texts(self, texts: list[str]) -> list[IngestionResult]:
        results: list[IngestionResult] = []
        for text in texts:
            report_id = f"svc-{self._next_report_num}"
            self._next_report_num += 1
            report = ReportInput(
                report_id=report_id,
                raw_text=text,
                source_channel=_SOURCE_CHANNEL,
                provenance=_PROVENANCE,
                timestamp=_FIXED_REPORT_TS,
            )
            result = ingest_report(report)
            self._extracted.append(result.extracted)
            self._traces.extend(result.traces)
            results.append(result)
        return results

    def consolidate(self) -> list[NormalizedIncidentCluster]:
        return deduplicate_reports(self._extracted)

    def prepare_draft(self) -> EngineOutput:
        if self._plan_id is not None:
            raise ValueError(f"plan already exists: {self._plan_id}")

        clusters = self.consolidate()
        output = self._engine(clusters)
        plan_id = output.plan.plan_id
        payload = {
            "clusters": [c.model_dump(mode="json") for c in clusters],
            "priorities": [p.model_dump(mode="json") for p in output.priorities],
            "plan": output.plan.model_dump(mode="json"),
            "assignments": [a.model_dump(mode="json") for a in output.plan.assignments],
            "label": _PROVENANCE.value,
        }
        payload_json = json.dumps(payload, ensure_ascii=False)
        self._store.create_plan(plan_id, payload_json, state=PlanState.BORRADOR)
        self._plan_id = plan_id
        self._payload_json = payload_json
        self._submitted = False
        self._state = PlanState.BORRADOR
        self._draft = output
        self._execution = None
        return output

    def submit_for_review(self) -> None:
        if self._plan_id is None:
            raise ValueError("no draft prepared")
        self._store.submit_for_review(self._plan_id)
        self._submitted = True
        self._state = PlanState.PENDIENTE

    def snapshot(self) -> dict[str, object]:
        clusters = self.consolidate()
        cluster_payload = [c.model_dump(mode="json") for c in clusters]
        tag_set: set[str] = set()
        for cluster in clusters:
            for tag in cluster.provenance_tags:
                tag_set.add(tag.value if isinstance(tag, ProvenanceTag) else str(tag))

        priorities: list[dict[str, object]] = []
        plan: dict[str, object] | None = None
        if self._draft is not None:
            priorities = [p.model_dump(mode="json") for p in self._draft.priorities]
            plan = self._draft.plan.model_dump(mode="json")

        state_value: str | None
        if self._state is None:
            state_value = None
        else:
            state_value = self._state.value.lower()

        execution_payload: dict[str, object] | None = None
        if self._execution is not None:
            execution_payload = self._execution.model_dump(mode="json")

        return {
            "clusters": cluster_payload,
            "priorities": priorities,
            "plan": plan,
            "state": state_value,
            "traces": [t.model_dump(mode="json") for t in self._traces],
            "execution": execution_payload,
            "provenance_tags": sorted(tag_set),
        }

    def decide(self, decision: HumanDecision) -> ExecutionResult:
        if decision.action == DecisionAction.CORRECT and not decision.comment.strip():
            raise ValueError("CORRECT requires a non-empty comment")

        if self._plan_id is None or self._payload_json is None:
            raise ValueError("no draft prepared")

        if decision.plan_id != self._plan_id:
            raise ValueError("decision.plan_id must match prepared plan")

        if not self._submitted:
            raise ValueError("plan must be submitted for review before decide")

        assert self._payload_json is not None
        result = self._store.apply_decision(
            self._plan_id,
            decision,
            self._payload_json,
        )
        self._execution = result
        if decision.action == DecisionAction.CORRECT:
            self._submitted = False
            self._state = PlanState.BORRADOR
        else:
            self._state = transition(PlanState.PENDIENTE, decision.action)
        return result


__all__ = ["CoordinatorService"]
