"""Prioritization agent. The numeric score comes from score_cluster, not the model."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent, RunContext, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.config import RuntimeConfig, load_runtime_config, redact_secrets
from src.contracts import (
    Assessment,
    FactorBreakdown,
    FactorNote,
    NormalizedIncidentCluster,
    PriorityResult,
    SectorId,
    TraceEntry,
    VulnerabilityFlag,
)
from src.priority import FORMULA_VERSION, score_cluster

_INSTRUCTIONS = """
Eres el agente de priorizacion y evaluacion de necesidad de AguaJusta Oeste.
Evalua un incidente consolidado de falta de agua en Panama Oeste segun horas sin agua, poblacion afectada y vulnerabilidad.
Llama inspect_cluster_evidence y compute_deterministic_priority antes de responder.
No inventes ni modifiques puntajes numericos: el score final lo calcula el codigo deterministico.
El volumen de quejas (report_count) no otorga prioridad.
No apruebes planes ni despaches cisternas.
""".strip()

_CORE_FACTORS = ("duration", "affected", "vulnerability")
_RECORDED_TOOLS = ("inspect_cluster_evidence", "compute_deterministic_priority")
_MISSING_DURATION = "duracion sin agua no especificada"
_MISSING_AFFECTED = "cantidad de afectados no especificada"
_UNKNOWN_SECTOR = "sector desconocido requiere verificacion manual"
_HEALTH_RISK = "riesgo sanitario critico en instalacion de salud"
_SCHOOL_RISK = "afectacion a comunidad escolar"
_VULNERABLE_RISK = "poblacion vulnerable expuesta a deshidratacion"
_INVALID_NUMBERS = "datos numericos invalidos"
_MODEL_FAILED = "fallo del modelo de evaluacion"
_MODEL_UNCERTAINTY = "model call failed before assessment was accepted"


class LLMAssessmentDraft(BaseModel):
    """Qualitative draft. Numeric scores stay in the deterministic scorer."""

    model_config = ConfigDict(extra="forbid")

    factors: list[FactorNote] = []
    risks: list[str] = []
    uncertainties: list[str] = []


class PrioritizationDeps(BaseModel):
    """Closed dependencies for one consolidated incident."""

    model_config = ConfigDict(extra="forbid")

    cluster: NormalizedIncidentCluster


class PrioritizationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster: NormalizedIncidentCluster
    assessment: Assessment
    priority: PriorityResult
    requires_human_review: bool


class PrioritizationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PrioritizationItem]
    assessments: list[Assessment]
    priorities: list[PriorityResult]
    traces: list[TraceEntry]
    usage_requests: int = 0


def _derived_risks(cluster: NormalizedIncidentCluster) -> list[str]:
    risks: list[str] = []
    if cluster.sector_id == SectorId.UNKNOWN:
        risks.append(_UNKNOWN_SECTOR)
    if cluster.max_duration_hours is None:
        risks.append(_MISSING_DURATION)
    if cluster.estimated_affected_count is None:
        risks.append(_MISSING_AFFECTED)
    flags = set(cluster.vulnerability_flags)
    if VulnerabilityFlag.HOSPITAL_SALUD in flags:
        risks.append(_HEALTH_RISK)
    if VulnerabilityFlag.ESCUELA in flags:
        risks.append(_SCHOOL_RISK)
    if flags & {
        VulnerabilityFlag.ADULTOS_MAYORES,
        VulnerabilityFlag.INFANTES,
        VulnerabilityFlag.ALBERGUE,
    }:
        risks.append(_VULNERABLE_RISK)
    return risks


def _inspect_payload(cluster: NormalizedIncidentCluster) -> dict[str, Any]:
    return {
        "cluster_id": cluster.cluster_id,
        "sector_id": cluster.sector_id.value,
        "max_duration_hours": cluster.max_duration_hours,
        "estimated_affected_count": cluster.estimated_affected_count,
        "vulnerability_flags": [flag.value for flag in cluster.vulnerability_flags],
        "evidence_types": [kind.value for kind in cluster.evidence_types],
        "provenance_tags": [tag.value for tag in cluster.provenance_tags],
        "report_count": cluster.report_count,
        "requires_human_review": cluster.requires_human_review,
        "uncertainties": list(cluster.uncertainties),
        "derived_risks": _derived_risks(cluster),
    }


def _build_agent() -> Agent[PrioritizationDeps, LLMAssessmentDraft]:
    agent: Agent[PrioritizationDeps, LLMAssessmentDraft] = Agent(
        None,
        output_type=LLMAssessmentDraft,
        deps_type=PrioritizationDeps,
        instructions=_INSTRUCTIONS,
        retries=1,
        name="prioritization",
    )

    @agent.tool
    def inspect_cluster_evidence(ctx: RunContext[PrioritizationDeps]) -> dict[str, Any]:
        """Return deterministic evidence for one consolidated incident.

        JSON keys: cluster_id, sector_id, max_duration_hours, estimated_affected_count,
        vulnerability_flags, evidence_types, provenance_tags, report_count,
        requires_human_review, uncertainties, derived_risks.
        Enum fields are closed string values. Hours and affected counts stay null
        when the cluster has no number; this tool never invents them.
        derived_risks are qualitative strings. report_count is audit context and
        is not a priority factor. Does not compute or change the numeric score.
        """
        return _inspect_payload(ctx.deps.cluster)

    @agent.tool
    def compute_deterministic_priority(ctx: RunContext[PrioritizationDeps]) -> dict[str, Any]:
        """Run score_cluster and return its PriorityResult as JSON.

        Formula priority-v1: duration 0-40, affected 0-30, vulnerability 0-30,
        maximum 100. report_count is ignored. Keys are cluster_id, score,
        breakdown, formula_version, and explanation. The model must not change
        score, breakdown, or formula_version; code keeps this result.
        """
        priority = score_cluster(ctx.deps.cluster)
        return priority.model_dump(mode="json")

    return agent


_AGENT = _build_agent()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cluster_summary(cluster: NormalizedIncidentCluster) -> str:
    flags = ",".join(flag.value for flag in cluster.vulnerability_flags)
    uncertainties = "; ".join(cluster.uncertainties)
    return (
        f"cluster_id={cluster.cluster_id} sector={cluster.sector_id.value} "
        f"hours={cluster.max_duration_hours} affected={cluster.estimated_affected_count} "
        f"reports={cluster.report_count} flags={flags} uncertainties={uncertainties}"
    )


def _trace(
    cluster_id: str,
    action: str,
    input_summary: str,
    output_summary: str,
    status: str,
) -> TraceEntry:
    return TraceEntry(
        trace_id=f"{cluster_id}:{action}",
        actor="prioritization",
        action=action,
        input_summary=redact_secrets(input_summary)[:500],
        output_summary=redact_secrets(output_summary)[:500],
        status=status,
        timestamp=_now(),
    )


def _prompt(cluster: NormalizedIncidentCluster) -> str:
    return (
        "Evalua este incidente consolidado de falta de agua. "
        f"cluster_id={cluster.cluster_id}. "
        "Usa solo las herramientas. No inventes puntajes."
    )


def _merge_unique(primary: list[str], extra: list[str]) -> list[str]:
    merged = list(primary)
    seen = set(primary)
    for item in extra:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def _factor_uncertainty(name: str, cluster: NormalizedIncidentCluster) -> str:
    if name == "duration" and cluster.max_duration_hours is None:
        return _MISSING_DURATION
    if name == "affected" and cluster.estimated_affected_count is None:
        return _MISSING_AFFECTED
    return ""


def _core_factors(
    priority: PriorityResult,
    cluster: NormalizedIncidentCluster,
) -> list[FactorNote]:
    by_name = {row.factor: row for row in priority.breakdown}
    notes: list[FactorNote] = []
    for name in _CORE_FACTORS:
        row = by_name.get(name)
        notes.append(
            FactorNote(
                name=name,
                evidence=row.reason if row is not None else "",
                uncertainty=_factor_uncertainty(name, cluster),
            )
        )
    return notes


def _with_core_factors(
    draft_factors: list[FactorNote],
    priority: PriorityResult,
    cluster: NormalizedIncidentCluster,
) -> list[FactorNote]:
    """Keep breakdown evidence for the three core factors, then extra notes."""
    by_name = {factor.name: factor for factor in draft_factors}
    merged: list[FactorNote] = []
    for note in _core_factors(priority, cluster):
        draft = by_name.get(note.name)
        uncertainty = note.uncertainty
        if draft is not None and draft.uncertainty and not note.uncertainty:
            uncertainty = draft.uncertainty
        merged.append(
            FactorNote(name=note.name, evidence=note.evidence, uncertainty=uncertainty)
        )
    core_names = set(_CORE_FACTORS)
    for factor in draft_factors:
        if factor.name not in core_names:
            merged.append(factor)
    return merged


def _needs_review(cluster: NormalizedIncidentCluster) -> bool:
    return (
        cluster.requires_human_review
        or cluster.sector_id is SectorId.UNKNOWN
        or cluster.max_duration_hours is None
        or cluster.estimated_affected_count is None
    )


def _zero_priority(cluster: NormalizedIncidentCluster, exc: ValueError) -> PriorityResult:
    reason = _INVALID_NUMBERS
    return PriorityResult(
        cluster_id=cluster.cluster_id,
        score=0.0,
        breakdown=[
            FactorBreakdown(factor=name, points=0.0, reason=reason) for name in _CORE_FACTORS
        ],
        formula_version=FORMULA_VERSION,
        explanation=f"ERROR: ValueError ({exc})",
    )


def _controlled(
    cluster: NormalizedIncidentCluster,
    priority: PriorityResult,
    *,
    factors: list[FactorNote],
    risks: list[str],
    uncertainties: list[str],
    status: str,
    output_summary: str,
) -> tuple[PrioritizationItem, list[TraceEntry], int]:
    item = PrioritizationItem(
        cluster=cluster,
        assessment=Assessment(
            cluster_id=cluster.cluster_id,
            factors=factors,
            risks=risks,
            uncertainties=uncertainties,
        ),
        priority=priority,
        requires_human_review=True,
    )
    trace = _trace(
        cluster.cluster_id,
        "prioritize_cluster",
        _cluster_summary(cluster),
        output_summary,
        status,
    )
    return item, [trace], 0


def _tool_payloads(messages: list[ModelMessage]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue
        for part in message.parts:
            if not isinstance(part, ToolReturnPart):
                continue
            content = part.content
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    continue
            if isinstance(content, dict):
                found[part.tool_name] = content
    return found


def _draft_args(evidence: dict[str, Any], priority: dict[str, Any]) -> dict[str, Any]:
    by_factor = {
        str(row.get("factor")): row
        for row in (priority.get("breakdown") or [])
        if isinstance(row, dict)
    }
    inspect_bits = {
        "duration": f"max_duration_hours={evidence.get('max_duration_hours')}",
        "affected": f"estimated_affected_count={evidence.get('estimated_affected_count')}",
        "vulnerability": "vulnerability_flags="
        + ",".join(str(flag) for flag in (evidence.get("vulnerability_flags") or [])),
    }
    factors: list[dict[str, str]] = []
    for name in _CORE_FACTORS:
        row = by_factor.get(name, {})
        reason = str(row.get("reason") or "")
        evidence_text = f"{reason}; {inspect_bits[name]}".strip("; ")
        uncertainty = ""
        if name == "duration" and evidence.get("max_duration_hours") is None:
            uncertainty = _MISSING_DURATION
        elif name == "affected" and evidence.get("estimated_affected_count") is None:
            uncertainty = _MISSING_AFFECTED
        factors.append(
            {"name": name, "evidence": evidence_text, "uncertainty": uncertainty}
        )
    return {
        "factors": factors,
        "risks": [str(risk) for risk in (evidence.get("derived_risks") or [])],
        "uncertainties": [str(item) for item in (evidence.get("uncertainties") or [])],
    }


def _deterministic_test_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Call both code tools, then return their qualitative draft."""
    payloads = _tool_payloads(messages)
    pending: list[ToolCallPart] = []
    if "inspect_cluster_evidence" not in payloads:
        pending.append(
            ToolCallPart(
                tool_name="inspect_cluster_evidence",
                args={},
                tool_call_id="inspect-evidence",
            )
        )
    if "compute_deterministic_priority" not in payloads:
        pending.append(
            ToolCallPart(
                tool_name="compute_deterministic_priority",
                args={},
                tool_call_id="score-priority",
            )
        )
    if pending:
        return ModelResponse(parts=pending)

    output_tool = info.output_tools[0].name
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=output_tool,
                args=_draft_args(
                    payloads["inspect_cluster_evidence"],
                    payloads["compute_deterministic_priority"],
                ),
                tool_call_id="draft-assessment",
            )
        ]
    )


def _tool_traces(
    cluster: NormalizedIncidentCluster,
    messages: list[ModelMessage],
) -> list[TraceEntry]:
    payloads = _tool_payloads(messages)
    traces: list[TraceEntry] = []
    seen: set[str] = set()
    summary = _cluster_summary(cluster)
    for message in messages:
        if not isinstance(message, ModelResponse):
            continue
        for part in message.parts:
            if not isinstance(part, ToolCallPart) or part.tool_name not in _RECORDED_TOOLS:
                continue
            if part.tool_name in seen:
                continue
            seen.add(part.tool_name)
            payload = payloads.get(part.tool_name, {})
            if part.tool_name == "compute_deterministic_priority":
                output = (
                    f"score={payload.get('score')} formula={payload.get('formula_version')}"
                )
            else:
                output = (
                    f"sector={payload.get('sector_id')} risks={payload.get('derived_risks')}"
                )
            traces.append(_trace(cluster.cluster_id, part.tool_name, summary, output, "ok"))
    return traces


def prioritize_cluster(
    cluster: NormalizedIncidentCluster,
    *,
    model: Model | None = None,
    config: RuntimeConfig | None = None,
) -> tuple[PrioritizationItem, list[TraceEntry], int]:
    """Assess one cluster. MODO=test uses FunctionModel and does not call a provider.

    The PriorityResult is always score_cluster. The model may only return
    qualitative factors, risks, and uncertainties. UsageLimitExceeded,
    ModelHTTPError, and UnexpectedModelBehavior become ERROR traces with
    requires_human_review. There is no retry loop.
    """
    runtime = config or load_runtime_config()
    try:
        priority = score_cluster(cluster)
    except ValueError as exc:
        zero_priority = _zero_priority(cluster, exc)
        return _controlled(
            cluster,
            zero_priority,
            factors=_core_factors(zero_priority, cluster),
            risks=[_INVALID_NUMBERS],
            uncertainties=_merge_unique(list(cluster.uncertainties), [_INVALID_NUMBERS]),
            status="ERROR: ValueError",
            output_summary=f"ERROR: ValueError ({exc})",
        )

    selected: Model | str
    if model is not None:
        selected = model
    elif runtime.modo == "test":
        selected = FunctionModel(_deterministic_test_model)
    else:
        selected = runtime.model_name

    try:
        result = _AGENT.run_sync(
            _prompt(cluster),
            deps=PrioritizationDeps(cluster=cluster),
            model=selected,
            usage_limits=runtime.usage_limits(),
        )
    except UsageLimitExceeded:
        return _controlled(
            cluster,
            priority,
            factors=_core_factors(priority, cluster),
            risks=[_MODEL_FAILED],
            uncertainties=_merge_unique(list(cluster.uncertainties), [_MODEL_UNCERTAINTY]),
            status="ERROR: UsageLimitExceeded",
            output_summary="model call failed",
        )
    except ModelHTTPError as exc:
        status = "ERROR: 429" if exc.status_code == 429 else "ERROR: ModelHTTPError"
        return _controlled(
            cluster,
            priority,
            factors=_core_factors(priority, cluster),
            risks=[_MODEL_FAILED],
            uncertainties=_merge_unique(list(cluster.uncertainties), [_MODEL_UNCERTAINTY]),
            status=status,
            output_summary="model call failed",
        )
    except UnexpectedModelBehavior:
        return _controlled(
            cluster,
            priority,
            factors=_core_factors(priority, cluster),
            risks=[_MODEL_FAILED],
            uncertainties=_merge_unique(list(cluster.uncertainties), [_MODEL_UNCERTAINTY]),
            status="ERROR: UnexpectedModelBehavior",
            output_summary="model call failed",
        )

    draft = result.output
    assessment = Assessment(
        cluster_id=cluster.cluster_id,
        factors=_with_core_factors(list(draft.factors), priority, cluster),
        risks=_merge_unique(_derived_risks(cluster), list(draft.risks)),
        uncertainties=_merge_unique(list(draft.uncertainties), list(cluster.uncertainties)),
    )
    item = PrioritizationItem(
        cluster=cluster,
        assessment=assessment,
        priority=priority,
        requires_human_review=_needs_review(cluster),
    )
    traces = _tool_traces(cluster, result.all_messages())
    traces.append(
        _trace(
            cluster.cluster_id,
            "prioritize_cluster",
            _cluster_summary(cluster),
            f"sector={cluster.sector_id.value} score={priority.score}",
            "ok",
        )
    )
    return item, traces, result.usage.requests


def prioritize_clusters(
    clusters: Iterable[NormalizedIncidentCluster],
    *,
    model: Model | None = None,
    config: RuntimeConfig | None = None,
) -> PrioritizationResult:
    """Score every cluster and rank by descending score, then cluster_id."""
    cluster_list = list(clusters)
    items: list[PrioritizationItem] = []
    traces: list[TraceEntry] = []
    usage_requests = 0
    for cluster in cluster_list:
        item, item_traces, requests = prioritize_cluster(
            cluster,
            model=model,
            config=config,
        )
        items.append(item)
        traces.extend(item_traces)
        usage_requests += requests
    items.sort(key=lambda item: (-item.priority.score, item.priority.cluster_id))
    if cluster_list:
        ranking = " ".join(
            f"{item.priority.cluster_id}={item.priority.score}" for item in items
        )
        traces.append(
            _trace(
                "batch",
                "rank_clusters",
                f"clusters={len(cluster_list)}",
                ranking,
                "ok",
            )
        )
    return PrioritizationResult(
        items=items,
        assessments=[item.assessment for item in items],
        priorities=[item.priority for item in items],
        traces=traces,
        usage_requests=usage_requests,
    )
