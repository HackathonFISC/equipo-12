"""Group extracted reports into incidents using place anchors.

Reports that only share a sector stay apart when their landmarks are farther
apart than SAME_INCIDENT_METERS. Repeated complaints of one place still count
once: affected people use the maximum, not the sum.
"""

from __future__ import annotations

from src.contracts import (
    EvidenceType,
    GeoPrecision,
    GuardrailStatus,
    NormalizedIncidentCluster,
    ProvenanceTag,
    ReportExtracted,
    SectorId,
    VulnerabilityFlag,
)
from src.ingestion.geolocator import SAME_INCIDENT_METERS, geolocate_report, haversine_meters

_REJECTED = {
    GuardrailStatus.REJECTED_EMPTY,
    GuardrailStatus.REJECTED_MALICIOUS,
    GuardrailStatus.REJECTED_OUT_OF_SCOPE,
    GuardrailStatus.REJECTED_ABSURD,
}


def _ensure_geo(report: ReportExtracted) -> ReportExtracted:
    if report.geo_precision is GeoPrecision.UNKNOWN and report.raw_location_mention.strip():
        return geolocate_report(report, report.raw_location_mention)
    return report


def _same_incident(left: ReportExtracted, right: ReportExtracted) -> bool:
    if left.candidate_sector_id != right.candidate_sector_id:
        return False
    if left.place_id and left.place_id == right.place_id:
        return True
    if (
        left.latitude is None
        or left.longitude is None
        or right.latitude is None
        or right.longitude is None
    ):
        return False
    return (
        haversine_meters(left.latitude, left.longitude, right.latitude, right.longitude)
        <= SAME_INCIDENT_METERS
    )


def _point_components(points: list[ReportExtracted]) -> list[list[ReportExtracted]]:
    parent = list(range(len(points)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left_index, left in enumerate(points):
        for right_index in range(left_index + 1, len(points)):
            if _same_incident(left, points[right_index]):
                parent[find(right_index)] = find(left_index)
    grouped: dict[int, list[ReportExtracted]] = {}
    for index, report in enumerate(points):
        grouped.setdefault(find(index), []).append(report)
    return list(grouped.values())


def _build_cluster(items: list[ReportExtracted]) -> NormalizedIncidentCluster:
    sector_id = items[0].candidate_sector_id
    durations = [item.duration_hours for item in items if item.duration_hours is not None]
    affected = [item.affected_count for item in items if item.affected_count is not None]
    flags: list[VulnerabilityFlag] = []
    evidence_types: list[EvidenceType] = []
    provenance_tags: list[ProvenanceTag] = []
    uncertainties: list[str] = []
    place_ids: list[str] = []
    latitudes: list[float] = []
    longitudes: list[float] = []
    for item in items:
        for flag in item.vulnerability_flags:
            if flag is VulnerabilityFlag.NINGUNA or flag in flags:
                continue
            flags.append(flag)
        if item.evidence_type not in evidence_types:
            evidence_types.append(item.evidence_type)
        if item.provenance not in provenance_tags:
            provenance_tags.append(item.provenance)
        for note in item.uncertainties:
            if note not in uncertainties:
                uncertainties.append(note)
        if item.place_id and item.place_id not in place_ids:
            place_ids.append(item.place_id)
        if item.latitude is not None and item.longitude is not None:
            latitudes.append(item.latitude)
            longitudes.append(item.longitude)
    if not flags:
        flags = [VulnerabilityFlag.NINGUNA]
    place_ids.sort()
    if any(item.geo_precision is GeoPrecision.POINT for item in items):
        precision = GeoPrecision.POINT
        place_key = "+".join(place_ids) or "POINT"
    elif any(item.geo_precision is GeoPrecision.SECTOR for item in items):
        precision = GeoPrecision.SECTOR
        place_key = "SECTOR"
    else:
        precision = GeoPrecision.UNKNOWN
        place_key = "UNPLACED"
    source_ids = [item.report_id for item in items]
    return NormalizedIncidentCluster(
        cluster_id=f"cluster:{sector_id.value}:{place_key}",
        sector_id=sector_id,
        source_report_ids=source_ids,
        report_count=len(source_ids),
        max_duration_hours=max(durations) if durations else None,
        estimated_affected_count=max(affected) if affected else None,
        vulnerability_flags=flags,
        evidence_types=evidence_types,
        requires_human_review=(
            sector_id is SectorId.UNKNOWN
            or precision is GeoPrecision.SECTOR
            or len(place_ids) > 1
            or any(item.requiere_revision for item in items)
        ),
        uncertainties=uncertainties,
        provenance_tags=provenance_tags,
        place_id="+".join(place_ids),
        latitude=(sum(latitudes) / len(latitudes)) if latitudes else None,
        longitude=(sum(longitudes) / len(longitudes)) if longitudes else None,
        geo_precision=precision,
    )


def deduplicate_reports(reports: list[ReportExtracted]) -> list[NormalizedIncidentCluster]:
    """Group non-rejected reports that describe the same incident.

    A named place is geocoded from raw_location_mention when the report has
    no fix yet. Landmarks in the same sector merge only when they are the
    same place or within SAME_INCIDENT_METERS. Sector-wide mentions stay in
    their own cluster. Rejected reports are left out.
    """
    prepared: list[ReportExtracted] = []
    for report in reports:
        if report.guardrail_status in _REJECTED:
            continue
        prepared.append(_ensure_geo(report))

    points = [
        report
        for report in prepared
        if report.geo_precision is GeoPrecision.POINT and report.latitude is not None
    ]
    point_ids = {id(report) for report in points}
    rest: dict[SectorId, list[ReportExtracted]] = {}
    for report in prepared:
        if id(report) in point_ids:
            continue
        rest.setdefault(report.candidate_sector_id, []).append(report)

    grouped: list[tuple[int, list[ReportExtracted]]] = []
    for component in _point_components(points):
        first_index = min(prepared.index(item) for item in component)
        grouped.append((first_index, component))
    for items in rest.values():
        first_index = min(prepared.index(item) for item in items)
        grouped.append((first_index, items))
    grouped.sort(key=lambda item: item[0])
    return [_build_cluster(items) for _, items in grouped]
