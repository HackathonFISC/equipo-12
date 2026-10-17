"""Deterministic priority scoring for water dispatch planning.

Prototype policy for the hackathon demo. These weights are NOT official
IDAAN policy. The LLM never decides numbers: this module applies the
formula and always returns an auditable breakdown.

score = duration_pts (0-40) + affected_pts (0-30) + vulnerability_pts (0-30)
Max score is 100. Complaint volume (report_count) is deliberately NOT a
factor: a duplicated incident does not buy priority.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.contracts import (
    FactorBreakdown,
    NormalizedIncidentCluster,
    PriorityResult,
    VulnerabilityFlag,
)

FORMULA_VERSION = "priority-v1"

MAX_HOURS = 168.0
WEIGHT_HOURS = 40.0
MAX_AFFECTED = 50000
WEIGHT_AFFECTED = 30.0
MAX_VULNERABILITY = 30.0

_VULNERABILITY_POINTS = {
    VulnerabilityFlag.HOSPITAL_SALUD: 20.0,
    VulnerabilityFlag.ESCUELA: 12.0,
    VulnerabilityFlag.ADULTOS_MAYORES: 10.0,
    VulnerabilityFlag.INFANTES: 10.0,
    VulnerabilityFlag.ALBERGUE: 8.0,
    VulnerabilityFlag.NINGUNA: 0.0,
}
_VULNERABILITY_LABEL = {
    VulnerabilityFlag.HOSPITAL_SALUD: "hospital o centro de salud",
    VulnerabilityFlag.ESCUELA: "escuela",
    VulnerabilityFlag.ADULTOS_MAYORES: "adultos mayores",
    VulnerabilityFlag.INFANTES: "infantes",
    VulnerabilityFlag.ALBERGUE: "albergue",
    VulnerabilityFlag.NINGUNA: "ninguna",
}


def _duration_points(hours: int | None) -> tuple[float, str]:
    if hours is None:
        return 0.0, "sin dato de duración"
    if hours < 0:
        raise ValueError("max_duration_hours must be >= 0")
    capped = min(float(hours), MAX_HOURS)
    points = round(capped / MAX_HOURS * WEIGHT_HOURS, 2)
    return points, f"{hours}h sin agua (tope {int(MAX_HOURS)}h)"


def _affected_points(count: int | None) -> tuple[float, str]:
    if count is None:
        return 0.0, "sin dato de afectados"
    if count < 0:
        raise ValueError("estimated_affected_count must be >= 0")
    capped = min(count, MAX_AFFECTED)
    points = round(capped / MAX_AFFECTED * WEIGHT_AFFECTED, 2)
    return points, f"{count} personas afectadas (tope {MAX_AFFECTED})"


def _vulnerability_points(
    flags: list[VulnerabilityFlag],
) -> tuple[float, str]:
    total = round(min(sum(_VULNERABILITY_POINTS[f] for f in flags), MAX_VULNERABILITY), 2)
    if not flags or flags == [VulnerabilityFlag.NINGUNA]:
        return total, "sin vulnerabilidad marcada"
    names = ", ".join(_VULNERABILITY_LABEL[flag] for flag in flags)
    return total, f"vulnerabilidad: {names} (tope {int(MAX_VULNERABILITY)})"


def score_cluster(cluster: NormalizedIncidentCluster) -> PriorityResult:
    """Score one incident cluster. Pure and deterministic."""
    duration_pts, duration_reason = _duration_points(cluster.max_duration_hours)
    affected_pts, affected_reason = _affected_points(cluster.estimated_affected_count)
    vulnerability_pts, vulnerability_reason = _vulnerability_points(
        cluster.vulnerability_flags
    )
    score = round(duration_pts + affected_pts + vulnerability_pts, 2)
    return PriorityResult(
        cluster_id=cluster.cluster_id,
        score=score,
        breakdown=[
            FactorBreakdown(factor="duration", points=duration_pts, reason=duration_reason),
            FactorBreakdown(factor="affected", points=affected_pts, reason=affected_reason),
            FactorBreakdown(
                factor="vulnerability",
                points=vulnerability_pts,
                reason=vulnerability_reason,
            ),
        ],
        formula_version=FORMULA_VERSION,
        explanation=(
            f"{FORMULA_VERSION}: horas {duration_pts} + afectados {affected_pts} "
            f"+ vulnerabilidad {vulnerability_pts} = {score}. "
            "Pesos de prototipo, no política del IDAAN."
        ),
    )


def rank_clusters(clusters: Iterable[NormalizedIncidentCluster]) -> list[PriorityResult]:
    """Score every cluster, highest first. Ties break by cluster_id (stable)."""
    scored = [score_cluster(cluster) for cluster in clusters]
    scored.sort(key=lambda result: (-result.score, result.cluster_id))
    return scored
