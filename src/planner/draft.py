"""Shared plan draft from priority scores and the route solver."""

from __future__ import annotations

import hashlib

from src.contracts import GeoPrecision, NormalizedIncidentCluster, PlanDraft, PriorityResult, SectorId
from src.ingestion.catalog import sector_map
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
    """Route known clusters. UNKNOWN sectors stay unserved. The model does not choose the route.

    A sector-wide mention is not added when that sector already has a specific place.
    """
    unserved = [cluster.sector_id.value for cluster in clusters if cluster.sector_id == SectorId.UNKNOWN]
    known = {cluster.cluster_id: cluster for cluster in clusters if cluster.sector_id != SectorId.UNKNOWN}
    point_sectors = {
        cluster.sector_id
        for cluster in known.values()
        if cluster.geo_precision is GeoPrecision.POINT
    }
    ordered: list[NormalizedIncidentCluster] = []
    withheld: list[str] = []
    for item in priorities:
        cluster = known.get(item.cluster_id)
        if cluster is None:
            continue
        if cluster.geo_precision is GeoPrecision.SECTOR and cluster.sector_id in point_sectors:
            withheld.append(cluster.sector_id.value)
            continue
        ordered.append(cluster)
    scores = [item for item in priorities if any(cluster.cluster_id == item.cluster_id for cluster in ordered)]
    routed = solve(ordered, scores)
    unserved.extend(routed.unserved)
    explanation = _EXPLANATION
    if withheld:
        names = _sector_names(withheld)
        explanation += (
            " La mención general de "
            + names
            + " no se sumó porque ese sector ya tiene un lugar concreto."
        )
    return PlanDraft(
        plan_id=_plan_id(routed.route_order),
        assignments=routed.assignments,
        route_order=routed.route_order,
        constraints_satisfied=["priority-v1", *routed.constraints],
        unserved_demand=unserved,
        explanation=explanation,
    )


def _sector_names(sector_ids: list[str]) -> str:
    catalog = {str(item["sector_id"]): str(item["name"]) for item in sector_map()}
    labels = []
    for sector_id in sector_ids:
        label = catalog.get(sector_id, sector_id)
        if label not in labels:
            labels.append(label)
    return ", ".join(labels)


def _plan_id(sector_ids: list[str]) -> str:
    if not sector_ids:
        return "stub-plan-empty"
    digest = hashlib.sha256(",".join(sector_ids).encode()).hexdigest()[:12]
    return f"stub-plan-{digest}"
