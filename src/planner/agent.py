"""Planning agent. The route comes from the solver tool, not from the model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, RunContext, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.config import RuntimeConfig, load_runtime_config, redact_secrets
from src.contracts import NormalizedIncidentCluster, PlanDraft, PriorityResult, TraceEntry
from src.planner.draft import build_plan

_INSTRUCTIONS = """
Eres el agente de planificacion de AguaJusta Oeste. Llama solve_assignment
y no inventes litros, camiones ni el orden de la ruta: eso lo fija el solver.
No apruebes el plan ni despaches cisternas.
""".strip()


class PlanningNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = ""


@dataclass
class PlanningDeps:
    clusters: list[NormalizedIncidentCluster]
    priorities: list[PriorityResult]
    plan: PlanDraft | None = None


def _build_agent() -> Agent[PlanningDeps, PlanningNote]:
    agent: Agent[PlanningDeps, PlanningNote] = Agent(
        None,
        output_type=PlanningNote,
        deps_type=PlanningDeps,
        instructions=_INSTRUCTIONS,
        retries=1,
        name="planning",
    )

    @agent.tool
    def solve_assignment(ctx: RunContext[PlanningDeps]) -> dict[str, object]:
        """Run the deterministic cistern solver for the clusters already scored.

        Returns how many assignments and which sectors stay unserved.
        Does not accept a vehicle, a liter amount, or an approval.
        """
        ctx.deps.plan = build_plan(ctx.deps.clusters, ctx.deps.priorities)
        plan = ctx.deps.plan
        return {
            "assignments": len(plan.assignments),
            "unserved": list(plan.unserved_demand),
            "constraints": list(plan.constraints_satisfied),
        }

    return agent


_AGENT = _build_agent()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trace(action: str, input_summary: str, output_summary: str, status: str) -> TraceEntry:
    return TraceEntry(
        trace_id=f"planning:{action}",
        actor="planning",
        action=action,
        input_summary=redact_secrets(input_summary)[:500],
        output_summary=redact_secrets(output_summary)[:500],
        status=status,
        timestamp=_now(),
    )


def _test_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    called = False
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if isinstance(part, ToolReturnPart) and part.tool_name == "solve_assignment":
                called = True
    if not called:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="solve_assignment",
                    args={},
                    tool_call_id="solve-assignment",
                )
            ]
        )
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=info.output_tools[0].name,
                args={"summary": "solver draft ready for a human"},
                tool_call_id="planning-output",
            )
        ]
    )


def plan_assignment(
    clusters: list[NormalizedIncidentCluster],
    priorities: list[PriorityResult],
    *,
    model: Model | None = None,
    config: RuntimeConfig | None = None,
) -> tuple[PlanDraft, list[TraceEntry], int]:
    """Ask the planning agent to call the solver. Code keeps the solver plan if the model fails."""
    runtime = config or load_runtime_config()
    deps = PlanningDeps(clusters=list(clusters), priorities=list(priorities))
    selected: Model | str
    if model is not None:
        selected = model
    elif runtime.modo == "test":
        selected = FunctionModel(_test_model)
    else:
        selected = runtime.model_name
    usage = 0
    status = "ok"
    try:
        result = _AGENT.run_sync(
            f"clusters={len(clusters)}",
            deps=deps,
            model=selected,
            usage_limits=runtime.usage_limits(),
        )
        usage = result.usage.requests
        del result
    except UsageLimitExceeded:
        status = "ERROR: UsageLimitExceeded"
    except ModelHTTPError as exc:
        status = "ERROR: 429" if exc.status_code == 429 else "ERROR: ModelHTTPError"
    except UnexpectedModelBehavior:
        status = "ERROR: UnexpectedModelBehavior"
    plan = deps.plan if deps.plan is not None else build_plan(clusters, priorities)
    trace = _trace(
        "solve_assignment",
        f"clusters={len(clusters)}",
        f"assignments={len(plan.assignments)} unserved={len(plan.unserved_demand)}",
        status,
    )
    return plan, [trace], usage
