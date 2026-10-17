"""Shared plan draft from priority scores and the route solver."""

from __future__ import annotations

import hashlib

from src.contracts import NormalizedIncidentCluster, PlanDraft, PriorityResult, SectorId
from src.planner.solver import solve

_EXPLANATION = (
    "Plan priority-v1 (SYNTHETIC_DEMO): OR-Tools asigna las cisternas "
    "con capacidad y ventana de turno. Los litros por persona, la velocidad "
    "y el depósito son ASSUMPTION de la demostración, no un despacho oficial del IDAAN."
)


def build_plan(
    clusters: list[NormalizedIncidentCluster],
    priorities: list[PriorityResult],
) -> PlanDraft:
    """Route known clusters. UNKNOWN sectors stay unserved. The model does not choose the route."""
    unserved = [cluster.sector_id.value for cluster in clusters if cluster.sector_id == SectorId.UNKNOWN]
    known = {cluster.cluster_id: cluster for cluster in clusters if cluster.sector_id != SectorId.UNKNOWN}
    ordered = [known[item.cluster_id] for item in priorities if item.cluster_id in known]
    scores = [item for item in priorities if item.cluster_id in known]
    routed = solve(ordered, scores)
    unserved.extend(routed.unserved)
    return PlanDraft(
        plan_id=_plan_id(routed.route_order),
        assignments=routed.assignments,
        route_order=routed.route_order,
        constraints_satisfied=["priority-v1", *routed.constraints],
        unserved_demand=unserved,
        explanation=_EXPLANATION,
    )


def _plan_id(sector_ids: list[str]) -> str:
    if not sector_ids:
        return "stub-plan-empty"
    digest = hashlib.sha256(",".join(sector_ids).encode()).hexdigest()[:12]
    return f"stub-plan-{digest}"
