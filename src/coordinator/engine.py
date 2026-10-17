# ponytail: demo_engine stays STUB-v0 for its tests; priority_engine calls the OR-Tools solver.

"""Deterministic stub engine seam for coordinator planning."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from src.contracts import (
    Assignment,
    FactorBreakdown,
    NormalizedIncidentCluster,
    PlanDraft,
    PriorityResult,
    SectorId,
    TraceEntry,
)
from src.planner.solver import solve
from src.prioritization.agent import prioritize_clusters

_STUB_VEHICLE = "cisterna-1"
_FORMULA_VERSION = "STUB-v0"
_PRIORITY_EXPLANATION = (
    "STUB priority (SYNTHETIC_DEMO): prototype weights from hours without water and "
    "affected count; not official IDAAN policy."
)
_PLAN_EXPLANATION = (
    "STUB plan (SYNTHETIC_DEMO): single-vehicle route by sorted priority; "
    "not official IDAAN dispatch."
)


@dataclass(frozen=True)
class EngineOutput:
    priorities: list[PriorityResult]
    plan: PlanDraft
    traces: tuple[TraceEntry, ...] = ()


PlanEngine = Callable[[list[NormalizedIncidentCluster]], EngineOutput]


def _sort_key(cluster: NormalizedIncidentCluster) -> tuple[int, str]:
    hours = cluster.max_duration_hours if cluster.max_duration_hours is not None else 0
    return (-hours, cluster.sector_id.value)


def _stable_plan_id(sector_ids: list[str]) -> str:
    if not sector_ids:
        return "stub-plan-empty"
    digest = hashlib.sha256(",".join(sector_ids).encode()).hexdigest()[:12]
    return f"stub-plan-{digest}"


def _priority_for(cluster: NormalizedIncidentCluster) -> PriorityResult:
    hours = float(cluster.max_duration_hours if cluster.max_duration_hours is not None else 0)
    affected = float(
        cluster.estimated_affected_count if cluster.estimated_affected_count is not None else 0
    )
    score = hours + affected
    breakdown: list[FactorBreakdown] = []
    if hours:
        breakdown.append(
            FactorBreakdown(
                factor="hours_without_water",
                points=hours,
                reason=f"max_duration_hours={int(hours)}",
            )
        )
    if affected:
        breakdown.append(
            FactorBreakdown(
                factor="estimated_affected",
                points=affected,
                reason=f"estimated_affected_count={int(affected)}",
            )
        )
    if not breakdown:
        breakdown.append(
            FactorBreakdown(
                factor="baseline",
                points=0.0,
                reason="no duration or affected count",
            )
        )
    return PriorityResult(
        cluster_id=cluster.cluster_id,
        score=score,
        breakdown=breakdown,
        formula_version=_FORMULA_VERSION,
        explanation=_PRIORITY_EXPLANATION,
    )


def demo_engine(clusters: list[NormalizedIncidentCluster]) -> EngineOutput:
    unserved = [c.sector_id.value for c in clusters if c.sector_id == SectorId.UNKNOWN]
    known = [c for c in clusters if c.sector_id != SectorId.UNKNOWN]
    ordered = sorted(known, key=_sort_key)

    priorities = [_priority_for(c) for c in ordered]
    assignments: list[Assignment] = []
    route_order: list[str] = []
    for idx, cluster in enumerate(ordered, start=1):
        volume = (
            cluster.estimated_affected_count
            if cluster.estimated_affected_count is not None
            else 0
        )
        assignments.append(
            Assignment(
                vehicle_id=_STUB_VEHICLE,
                sector_id=cluster.sector_id,
                order=idx,
                volume_liters=volume,
            )
        )
        route_order.append(cluster.sector_id.value)

    plan = PlanDraft(
        plan_id=_stable_plan_id(route_order),
        assignments=assignments,
        route_order=route_order,
        constraints_satisfied=["stub-single-vehicle"],
        unserved_demand=unserved,
        explanation=_PLAN_EXPLANATION,
    )
    return EngineOutput(priorities=priorities, plan=plan)


def priority_engine(clusters: list[NormalizedIncidentCluster]) -> EngineOutput:
    """Route known sectors with OR-Tools using Edward's priority-v1 score.

    The numeric score comes from score_cluster. The prioritization agent may
    only add qualitative factors. UNKNOWN sectors stay unserved. Liters, speed
    and the depot are ASSUMPTION demo values, not IDAAN policy.
    """
    unserved = [c.sector_id.value for c in clusters if c.sector_id == SectorId.UNKNOWN]
    known = [c for c in clusters if c.sector_id != SectorId.UNKNOWN]
    assessed = prioritize_clusters(known)
    by_id = {cluster.cluster_id: cluster for cluster in known}
    ordered = [by_id[item.cluster_id] for item in assessed.priorities]
    routed = solve(ordered, assessed.priorities)
    unserved.extend(routed.unserved)
    plan = PlanDraft(
        plan_id=_stable_plan_id(routed.route_order),
        assignments=routed.assignments,
        route_order=routed.route_order,
        constraints_satisfied=["priority-v1", *routed.constraints],
        unserved_demand=unserved,
        explanation=(
            "priority-v1 plan (SYNTHETIC_DEMO): OR-Tools assigns cisterns with "
            "capacity and shift windows. Liters per person, speed and the depot "
            "are ASSUMPTION demo values, not official IDAAN dispatch."
        ),
    )
    return EngineOutput(priorities=assessed.priorities, plan=plan, traces=tuple(assessed.traces))


__all__ = ["EngineOutput", "PlanEngine", "demo_engine", "priority_engine"]
