"""Coordinator glue: ingest, consolidate, draft, review, and human decision.

Each ``CoordinatorService`` instance owns at most one plan; start a new instance
for a new batch of reports.
"""

from __future__ import annotations

import base64
import json
import sqlite3
from datetime import UTC, datetime

from src.communication.outbox import notices_for_panel
from src.config import PROJECT_ROOT, load_runtime_config
from src.contracts import (
    DecisionAction,
    ExecutionResult,
    HumanDecision,
    NormalizedIncidentCluster,
    PlanDraft,
    ProvenanceTag,
    ReportExtracted,
    ReportInput,
    TraceEntry,
)
from src.coordinator.engine import EngineOutput, PlanEngine, priority_engine
from src.coordinator.state import PlanState, transition
from src.coordinator.store import ApprovalStore
from src.ingestion.agent import IngestionResult, ingest_report
from src.ingestion.catalog import sector_map
from src.ingestion.deduplicator import deduplicate_reports
from src.ingestion.media import CitizenMedia, remember_media
from src.orchestration.agent import orchestrate

_FIXED_REPORT_TS = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
_SOURCE_CHANNEL = "panel"
_PROVENANCE = ProvenanceTag.SYNTHETIC_DEMO
_FIXTURES_DIR = PROJECT_ROOT / "data" / "fixtures"


def _load_named_fixture_list(filename: str, key: str) -> list[dict[str, object]]:
    path = _FIXTURES_DIR / filename
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        raise ValueError(f"{filename} must be a JSON object")
    items = payload.get(key)
    if not isinstance(items, list):
        raise ValueError(f"{filename} missing list '{key}'")
    loaded: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{filename} '{key}' entries must be objects")
        loaded.append(item)
    return loaded


def _load_places_fixture() -> list[dict[str, object]]:
    return _load_named_fixture_list("places_panama_oeste.json", "places")


_OPERATIONAL_PRELOAD_REPORTS: tuple[dict[str, str], ...] = (
    {
        "report_id": "OP-101",
        "raw_text": (
            "Urgente sin agua en el Hospital Nicolas Solano en Barrio Colon "
            "desde hace 72 horas, 500 personas y pacientes afectados."
        ),
        "source_channel": "phone",
        "provenance": "SYNTHETIC_DEMO",
    },
    {
        "report_id": "OP-102",
        "raw_text": (
            "En Burunga llevamos 48 horas sin agua, somos 60 familias "
            "con ninos y adultos mayores sin suministro."
        ),
        "source_channel": "whatsapp",
        "provenance": "SYNTHETIC_DEMO",
    },
    {
        "report_id": "OP-103",
        "raw_text": (
            "Sin agua por el chino de Vista Alegre desde hace 48 horas, "
            "60 familias y una escuela afectadas."
        ),
        "source_channel": "citizen_portal",
        "provenance": "SYNTHETIC_DEMO",
    },
    {
        "report_id": "OP-104",
        "raw_text": (
            "Por el Xtra de Vista Alegre llevamos 30 horas sin agua "
            "en 50 familias."
        ),
        "source_channel": "whatsapp",
        "provenance": "SYNTHETIC_DEMO",
    },
    {
        "report_id": "OP-105",
        "raw_text": (
            "En Guadalupe llevamos 60 horas sin agua, 80 familias "
            "y un centro de salud afectados."
        ),
        "source_channel": "phone",
        "provenance": "SYNTHETIC_DEMO",
    },
    {
        "report_id": "OP-106",
        "raw_text": (
            "Cerca del Parque Feuillet llevamos 24 horas sin agua, "
            "45 familias afectadas."
        ),
        "source_channel": "citizen_portal",
        "provenance": "SYNTHETIC_DEMO",
    },
    {
        "report_id": "OP-107",
        "raw_text": (
            "Puerto Caimito sigue sin agua desde hace 36 horas, "
            "70 familias afectadas."
        ),
        "source_channel": "phone",
        "provenance": "SYNTHETIC_DEMO",
    },
    {
        "report_id": "OP-108",
        "raw_text": (
            "En El Coco las familias llevan 18 horas sin agua, "
            "35 familias afectadas."
        ),
        "source_channel": "whatsapp",
        "provenance": "SYNTHETIC_DEMO",
    },
)


def _load_sample_reports_fixture() -> list[dict[str, object]]:
    return _load_named_fixture_list("sample_citizen_reports.json", "reports")


class CoordinatorService:
    def __init__(
        self,
        store: ApprovalStore,
        engine: PlanEngine = priority_engine,
    ) -> None:
        self._store = store
        self._engine = engine
        self._next_report_num = 1
        self._report_inputs: dict[str, ReportInput] = {}
        self._reports: list[ReportInput] = []
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

    @property
    def has_plan(self) -> bool:
        return self._plan_id is not None

    @property
    def plan_id(self) -> str | None:
        return self._plan_id

    def _make_report(
        self,
        text: str,
        *,
        report_id: str | None = None,
        source_channel: str = _SOURCE_CHANNEL,
        provenance: ProvenanceTag = _PROVENANCE,
    ) -> ReportInput:
        if report_id is None:
            report_id = f"svc-{self._next_report_num}"
            self._next_report_num += 1
        report = ReportInput(
            report_id=report_id,
            raw_text=text,
            source_channel=source_channel,
            provenance=provenance,
            timestamp=_FIXED_REPORT_TS,
        )
        self._reports.append(report)
        self._report_inputs[report.report_id] = report
        return report

    def ingest_texts(self, texts: list[str]) -> list[IngestionResult]:
        results: list[IngestionResult] = []
        for text in texts:
            report = self._make_report(text)
            result = ingest_report(report)
            self._extracted.append(result.extracted)
            self._traces.extend(result.traces)
            results.append(result)
        return results

    def run_reports(
        self,
        texts: list[str],
        media: list[dict[str, object]] | None = None,
    ) -> EngineOutput:
        """Run the orchestrator for one batch and store the draft. Does not approve it."""
        if self._plan_id is not None:
            raise ValueError(f"plan already exists: {self._plan_id}")
        reports: list[ReportInput] = []
        for text in texts:
            reports.append(self._make_report(text))
        for item in media or []:
            reports.append(self._report_from_media(item))
        result = orchestrate(reports)
        self._extracted = list(result.extracted)
        self._traces.extend(result.traces)
        output = EngineOutput(
            priorities=list(result.priorities),
            plan=result.plan,
            traces=tuple(result.traces),
        )
        self._persist(output, list(result.clusters))
        return output

    def _report_from_media(self, item: dict[str, object]) -> ReportInput:
        kind = item.get("kind")
        encoded = item.get("content_base64")
        filename = item.get("filename")
        if kind not in ("audio", "image") or not isinstance(encoded, str) or not encoded.strip():
            raise ValueError("media item is incomplete")
        safe_name = str(filename or "adjunto").replace("\\", "/").split("/")[-1][:80]
        try:
            data = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("media item is not valid base64") from exc
        report = self._make_report("")
        remember_media(
            report.report_id,
            CitizenMedia(str(kind), safe_name, data, _optional_coord(item.get("latitude")), _optional_coord(item.get("longitude"))),
        )
        return report

    def consolidate(self) -> list[NormalizedIncidentCluster]:
        return deduplicate_reports(self._extracted)

    def prepare_draft(self) -> EngineOutput:
        if self._plan_id is not None:
            raise ValueError(f"plan already exists: {self._plan_id}")

        clusters = self.consolidate()
        output = self._engine(clusters)
        self._traces.extend(output.traces)
        self._persist(output, clusters)
        return output

    def _payload_json_for(
        self,
        output: EngineOutput,
        clusters: list[NormalizedIncidentCluster],
    ) -> tuple[str, str]:
        plan_id = output.plan.plan_id
        payload = {
            "clusters": [c.model_dump(mode="json") for c in clusters],
            "priorities": [p.model_dump(mode="json") for p in output.priorities],
            "plan": output.plan.model_dump(mode="json"),
            "assignments": [a.model_dump(mode="json") for a in output.plan.assignments],
            "label": _PROVENANCE.value,
        }
        return plan_id, json.dumps(payload, ensure_ascii=False)

    def _remember_draft(self, plan_id: str, payload_json: str, output: EngineOutput) -> None:
        self._plan_id = plan_id
        self._payload_json = payload_json
        self._submitted = False
        self._state = PlanState.BORRADOR
        self._draft = output
        self._execution = None

    def _persist(self, output: EngineOutput, clusters: list[NormalizedIncidentCluster]) -> None:
        self._persist_or_update(output, clusters)

    def _persist_or_update(
        self,
        output: EngineOutput,
        clusters: list[NormalizedIncidentCluster],
    ) -> None:
        if not _reviewable_plan(output.plan):
            raise ValueError("draft is not reviewable")
        plan_id, payload_json = self._payload_json_for(output, clusters)
        try:
            self._store.create_plan(plan_id, payload_json, state=PlanState.BORRADOR)
        except ValueError:
            conn = self._store._connect(same_thread=False)
            try:
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    UPDATE plans
                    SET state = ?, payload_json = ?, updated_at = ?, revision = revision + 1
                    WHERE id = ?
                    """,
                    (PlanState.BORRADOR.value, payload_json, now, plan_id),
                )
                conn.execute("DELETE FROM outbox WHERE plan_id = ?", (plan_id,))
                conn.commit()
            finally:
                conn.close()
        self._remember_draft(plan_id, payload_json, output)

    def _report_from_sample(self, record: dict[str, object]) -> ReportInput:
        raw = record.get("raw_text", "")
        raw_text = raw if isinstance(raw, str) else str(raw)
        fixture_id = record.get("report_id")
        report_id = fixture_id.strip() if isinstance(fixture_id, str) and fixture_id.strip() else None
        channel = record.get("source_channel", _SOURCE_CHANNEL)
        if isinstance(channel, str) and channel.strip():
            source_channel = channel.strip()
        else:
            source_channel = _SOURCE_CHANNEL
        provenance_raw = record.get("provenance", _PROVENANCE.value)
        try:
            provenance = ProvenanceTag(str(provenance_raw))
        except ValueError:
            provenance = _PROVENANCE
        return self._make_report(
            raw_text,
            report_id=report_id,
            source_channel=source_channel,
            provenance=provenance,
        )

    def submit_citizen_report(
        self,
        text: str,
        *,
        source_channel: str = "citizen_portal",
    ) -> dict[str, object]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("report text cannot be empty")
        if self._state == PlanState.APROBADO:
            raise ValueError("plan already approved")
        if self._state == PlanState.PENDIENTE:
            raise ValueError("plan is pending human review; return to borrador via CORRECT first")
        report = self._make_report(text.strip(), source_channel=source_channel)
        result = orchestrate(self._reports)
        self._extracted = list(result.extracted)
        self._traces.extend(result.traces)
        output = EngineOutput(
            priorities=list(result.priorities),
            plan=result.plan,
            traces=tuple(result.traces),
        )
        self._persist_or_update(output, list(result.clusters))
        snap = self.snapshot()
        latest_dict: dict[str, object] | None = None
        extracted_reports = snap["extracted_reports"]
        if isinstance(extracted_reports, list) and extracted_reports:
            for item in extracted_reports:
                if isinstance(item, dict) and item.get("report_id") == report.report_id:
                    latest_dict = item
                    break
            if latest_dict is None:
                last = extracted_reports[-1]
                if isinstance(last, dict):
                    latest_dict = last
        snap["latest_report"] = latest_dict if latest_dict is not None else {}
        return snap

    def preload_fixtures(self) -> dict[str, object]:
        if self._state == PlanState.APROBADO:
            raise ValueError("plan already approved")
        if self._state == PlanState.PENDIENTE:
            raise ValueError("plan is pending human review; return to borrador via CORRECT first")
        records = _load_sample_reports_fixture() + [
            dict(item) for item in _OPERATIONAL_PRELOAD_REPORTS
        ]
        self._reports = []
        self._report_inputs = {}
        for record in records:
            self._report_from_sample(record)
        result = orchestrate(self._reports)
        self._extracted = list(result.extracted)
        self._traces = []
        self._traces.extend(result.traces)
        output = EngineOutput(
            priorities=list(result.priorities),
            plan=result.plan,
            traces=tuple(result.traces),
        )
        self._persist_or_update(output, list(result.clusters))
        return self.snapshot()

    def reset(self) -> dict[str, object]:
        """Clear in-memory session state for a new coordinator cycle (SQLite history kept)."""
        if self._plan_id is not None:
            conn = self._store._connect(same_thread=False)
            try:
                conn.execute("DELETE FROM outbox WHERE plan_id = ?", (self._plan_id,))
                conn.commit()
            finally:
                conn.close()
        self._reports = []
        self._report_inputs = {}
        self._extracted = []
        self._traces = []
        self._plan_id = None
        self._payload_json = None
        self._submitted = False
        self._state = None
        self._execution = None
        self._draft = None
        return self.snapshot()

    def health_check(self) -> dict[str, object]:
        status = "ok"
        sectors: list[dict[str, object]] = []
        places: list[dict[str, object]] = []
        samples: list[dict[str, object]] = []
        db_ok = False

        for filename, key, bucket in (
            ("sectors_panama_oeste.json", "sectors", "sectors"),
            ("places_panama_oeste.json", "places", "places"),
            ("sample_citizen_reports.json", "reports", "samples"),
        ):
            path = _FIXTURES_DIR / filename
            try:
                if not path.is_file():
                    raise ValueError(f"missing {filename}")
                raw = path.read_bytes()
                if not raw.strip():
                    raise ValueError(f"empty {filename}")
                raw.decode("utf-8")
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError(f"invalid {filename}")
                items = payload.get(key)
                if not isinstance(items, list):
                    raise ValueError(f"invalid {filename}")
                if bucket == "sectors":
                    sectors = [i for i in items if isinstance(i, dict)]
                elif bucket == "places":
                    places = [i for i in items if isinstance(i, dict)]
                else:
                    samples = [i for i in items if isinstance(i, dict)]
            except (OSError, ValueError, json.JSONDecodeError):
                status = "degraded"

        if len(sectors) != 11 or len(places) < 15 or len(samples) < 7:
            status = "degraded"

        try:
            conn = self._store._connect()
            try:
                conn.execute("SELECT 1").fetchone()
                db_ok = True
            finally:
                conn.close()
        except sqlite3.Error:
            status = "degraded"

        return {
            "status": status,
            "modo": load_runtime_config().modo,
            "formula_version": "priority-v1",
            "solver": "ortools",
            "fixtures": {
                "sectors": len(sectors),
                "places": len(places),
                "sample_reports": len(samples),
            },
            "db_ok": db_ok,
            "state": self._state.value.lower() if self._state else None,
        }

    def submit_for_review(self) -> None:
        if self._plan_id is None:
            raise ValueError("no draft prepared")
        if self._draft is None or not _reviewable_plan(self._draft.plan):
            raise ValueError("draft is not reviewable")
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

        extracted_reports: list[dict[str, object]] = []
        for ext in self._extracted:
            item = ext.model_dump(mode="json")
            if ext.report_id in self._report_inputs:
                stored = self._report_inputs[ext.report_id]
                item["raw_text"] = stored.raw_text
                item["source_channel"] = stored.source_channel
            else:
                item["raw_text"] = ""
                item["source_channel"] = "panel"
            extracted_reports.append(item)

        outbox_notices: list[dict[str, str]] = []
        if self._draft is not None:
            notice_status = "QUEUED" if self._state == PlanState.APROBADO else "PREVIEW"
            outbox_notices = [
                {
                    "sector_id": sec,
                    "message": msg,
                    "channel": "SIMULATED",
                    "status": notice_status,
                }
                for sec, msg in notices_for_panel(self._draft.plan)
            ]

        return {
            "clusters": cluster_payload,
            "priorities": priorities,
            "plan": plan,
            "state": state_value,
            "traces": [t.model_dump(mode="json") for t in self._traces],
            "execution": execution_payload,
            "provenance_tags": sorted(tag_set),
            "sectors": sector_map(),
            "extracted_reports": extracted_reports,
            "places": _load_places_fixture(),
            "sample_reports": _load_sample_reports_fixture(),
            "outbox_notices": outbox_notices,
        }

    def decide(self, decision: HumanDecision) -> ExecutionResult:
        if decision.action == DecisionAction.CORRECT and not decision.comment.strip():
            raise ValueError("CORRECT requires a non-empty comment")

        if self._plan_id is None or self._payload_json is None:
            raise ValueError("no draft prepared")
        if self._draft is None or not _reviewable_plan(self._draft.plan):
            raise ValueError("draft is not reviewable")

        if decision.plan_id != self._plan_id:
            raise ValueError("decision.plan_id must match prepared plan")

        if not self._submitted:
            raise ValueError("plan must be submitted for review before decide")

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


def _reviewable_plan(plan: PlanDraft) -> bool:
    if plan.plan_id == "orchestrator-stopped" or plan.explanation.startswith("ERROR:"):
        return False
    return bool(plan.assignments or plan.unserved_demand)


def _optional_coord(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


__all__ = ["CoordinatorService"]
