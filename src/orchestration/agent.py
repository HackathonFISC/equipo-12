"""Orchestrator. It calls the three role agents and never approves the plan."""

from __future__ import annotations

import asyncio
import contextvars
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, RunContext, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.config import RuntimeConfig, load_runtime_config, redact_secrets
from src.contracts import (
    NormalizedIncidentCluster,
    PlanDraft,
    PriorityResult,
    ReportExtracted,
    ReportInput,
    SectorId,
    TraceEntry,
)
from src.ingestion.agent import ingest_report
from src.ingestion.deduplicator import deduplicate_reports
from src.planner.agent import plan_assignment
from src.prioritization.agent import prioritize_clusters

_INSTRUCTIONS = """
Eres el orquestador de AguaJusta Oeste. Llama run_ingestion, luego
run_assessment y luego run_planning. No calcules prioridad, litros ni rutas.
No apruebes el plan: un humano debe revisarlo.
Si una herramienta responde ERROR, no reintentes y no inventes el resultado.
""".strip()

_STEPS = ("run_ingestion", "run_assessment", "run_planning")


class OrchestratorNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = ""


class OrchestrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extracted: list[ReportExtracted] = []
    clusters: list[NormalizedIncidentCluster] = []
    priorities: list[PriorityResult] = []
    plan: PlanDraft
    traces: list[TraceEntry] = []
    requires_human_approval: bool = True
    status: str
    usage_requests: int = 0


@dataclass
class OrchestratorDeps:
    reports: list[ReportInput]
    config: RuntimeConfig
    extracted: list[ReportExtracted] = field(default_factory=list)
    clusters: list[NormalizedIncidentCluster] | None = None
    priorities: list[PriorityResult] | None = None
    plan: PlanDraft | None = None
    traces: list[TraceEntry] = field(default_factory=list)
    error: str | None = None
    nested_requests: int = 0


def _build_agent() -> Agent[OrchestratorDeps, OrchestratorNote]:
    agent: Agent[OrchestratorDeps, OrchestratorNote] = Agent(
        None,
        output_type=OrchestratorNote,
        deps_type=OrchestratorDeps,
        instructions=_INSTRUCTIONS,
        retries=1,
        name="orchestrator",
    )

    @agent.tool
    def run_ingestion(ctx: RunContext[OrchestratorDeps]) -> dict[str, object]:
        """Ingest every report already stored for this run.

        Returns how many reports were read. Does not accept new report text,
        a sector, or an approval.
        """
        if ctx.deps.error:
            return {"status": ctx.deps.error}
        extracted: list[ReportExtracted] = []
        for report in ctx.deps.reports:
            result = _call_outside_run(ingest_report, report, config=ctx.deps.config)
            extracted.append(result.extracted)
            ctx.deps.traces.extend(result.traces)
            ctx.deps.nested_requests += result.usage_requests
        ctx.deps.extracted = extracted
        summary = f"reports={len(extracted)}"
        ctx.deps.traces.append(_trace("run_ingestion", summary, summary, "ok"))
        return {"status": "ok", "reports": len(extracted)}

    @agent.tool
    def run_assessment(ctx: RunContext[OrchestratorDeps]) -> dict[str, object]:
        """Deduplicate ingested reports and score them with the priority agent.

        Returns the cluster count. Does not accept a score or an approval.
        Refuses to run before ingestion.
        """
        if ctx.deps.error:
            return {"status": ctx.deps.error}
        if not ctx.deps.extracted and ctx.deps.reports:
            ctx.deps.error = "ERROR: assessment before ingestion"
            ctx.deps.traces.append(_trace("run_assessment", "no extraction", ctx.deps.error, ctx.deps.error))
            return {"status": ctx.deps.error}
        clusters = deduplicate_reports(ctx.deps.extracted)
        known = [cluster for cluster in clusters if cluster.sector_id != SectorId.UNKNOWN]
        assessed = _call_outside_run(prioritize_clusters, known, config=ctx.deps.config)
        ctx.deps.clusters = clusters
        ctx.deps.priorities = list(assessed.priorities)
        ctx.deps.traces.extend(assessed.traces)
        ctx.deps.nested_requests += assessed.usage_requests
        summary = f"clusters={len(clusters)} scored={len(assessed.priorities)}"
        ctx.deps.traces.append(_trace("run_assessment", summary, summary, "ok"))
        return {"status": "ok", "clusters": len(clusters)}

    @agent.tool
    def run_planning(ctx: RunContext[OrchestratorDeps]) -> dict[str, object]:
        """Call the planning agent, which must call the deterministic solver.

        Returns assignment and unserved counts. Does not accept a route,
        a liter amount, or an approval. Refuses to run before assessment.
        """
        if ctx.deps.error:
            return {"status": ctx.deps.error}
        if ctx.deps.clusters is None or ctx.deps.priorities is None:
            ctx.deps.error = "ERROR: planning before assessment"
            ctx.deps.traces.append(_trace("run_planning", "no assessment", ctx.deps.error, ctx.deps.error))
            return {"status": ctx.deps.error}
        plan, traces, requests = _call_outside_run(
            plan_assignment,
            ctx.deps.clusters,
            ctx.deps.priorities,
            config=ctx.deps.config,
        )
        ctx.deps.plan = plan
        ctx.deps.traces.extend(traces)
        ctx.deps.nested_requests += requests
        summary = f"assignments={len(plan.assignments)} unserved={len(plan.unserved_demand)}"
        ctx.deps.traces.append(_trace("run_planning", summary, summary, "ok"))
        return {"status": "ok", "assignments": len(plan.assignments)}

    return agent


_AGENT = _build_agent()


def _call_outside_run(function: Any, /, *args: Any, **kwargs: Any) -> Any:
    """Run a sync agent entry point outside this tool's callback context.

    pydantic-ai rejects Agent.run_sync inside a synchronous tool. The worker
    switches to a blank context so each role agent keeps its own event loop.
    """
    outcome: dict[str, Any] = {}

    def invoke() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            outcome["value"] = function(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — re-raised on the caller thread
            outcome["error"] = exc
        finally:
            if not loop.is_closed():
                loop.close()
            asyncio.set_event_loop(None)

    def target() -> None:
        contextvars.Context().run(invoke)

    worker = threading.Thread(target=target)
    worker.start()
    worker.join()
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trace(action: str, input_summary: str, output_summary: str, status: str) -> TraceEntry:
    return TraceEntry(
        trace_id=f"orchestrator:{action}",
        actor="orchestrator",
        action=action,
        input_summary=redact_secrets(input_summary)[:500],
        output_summary=redact_secrets(output_summary)[:500],
        status=status,
        timestamp=_now(),
    )


def _empty_plan(status: str) -> PlanDraft:
    return PlanDraft(
        plan_id="orchestrator-stopped",
        explanation=status,
    )


def _tool_payloads(messages: list[ModelMessage]) -> dict[str, dict[str, object]]:
    found: dict[str, dict[str, object]] = {}
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if isinstance(part, ToolReturnPart) and isinstance(part.content, dict):
                found[part.tool_name] = part.content
    return found


def _test_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    payloads = _tool_payloads(messages)
    for name in _STEPS:
        if name not in payloads:
            return ModelResponse(
                parts=[ToolCallPart(tool_name=name, args={}, tool_call_id=f"call-{name}")]
            )
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=info.output_tools[0].name,
                args={"summary": "draft ready for a human"},
                tool_call_id="orchestrator-output",
            )
        ]
    )


def _result(deps: OrchestratorDeps, status: str, usage_requests: int) -> OrchestrationResult:
    plan = deps.plan if deps.plan is not None else _empty_plan(status)
    return OrchestrationResult(
        extracted=list(deps.extracted),
        clusters=list(deps.clusters or []),
        priorities=list(deps.priorities or []),
        plan=plan,
        traces=list(deps.traces),
        requires_human_approval=True,
        status=deps.error or status,
        usage_requests=usage_requests + deps.nested_requests,
    )


def orchestrate(
    reports: list[ReportInput],
    *,
    model: Model | None = None,
    config: RuntimeConfig | None = None,
) -> OrchestrationResult:
    """Run ingestion, assessment, and planning. The returned plan is not approved."""
    runtime = config or load_runtime_config()
    deps = OrchestratorDeps(reports=list(reports), config=runtime)
    selected: Model | str
    if model is not None:
        selected = model
    elif runtime.modo == "test":
        selected = FunctionModel(_test_model)
    else:
        selected = runtime.model_name
    try:
        result = _call_outside_run(
            _AGENT.run_sync,
            f"reports={len(reports)}",
            deps=deps,
            model=selected,
            usage_limits=runtime.usage_limits(),
        )
    except UsageLimitExceeded:
        return _result(deps, "ERROR: UsageLimitExceeded", 0)
    except ModelHTTPError as exc:
        status = "ERROR: 429" if exc.status_code == 429 else "ERROR: ModelHTTPError"
        return _result(deps, status, 0)
    except UnexpectedModelBehavior:
        return _result(deps, "ERROR: UnexpectedModelBehavior", 0)
    return _result(deps, "ok", result.usage.requests)
