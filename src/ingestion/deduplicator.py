"""Group extracted reports by sector without adding up duplicate complaints."""

from __future__ import annotations

from src.contracts import (
    EvidenceType,
    GuardrailStatus,
    NormalizedIncidentCluster,
    ProvenanceTag,
    ReportExtracted,
    SectorId,
    VulnerabilityFlag,
)

_REJECTED = {
    GuardrailStatus.REJECTED_EMPTY,
    GuardrailStatus.REJECTED_MALICIOUS,
    GuardrailStatus.REJECTED_OUT_OF_SCOPE,
    GuardrailStatus.REJECTED_ABSURD,
}


def deduplicate_reports(reports: list[ReportExtracted]) -> list[NormalizedIncidentCluster]:
    """Group non-rejected reports that share a sector.

    Source ids stay in arrival order. Affected people use the maximum, not
    the sum, so repeated complaints about one incident do not inflate demand.
    Rejected reports are left out of every cluster.
    """
    grouped: dict[SectorId, list[ReportExtracted]] = {}
    order: list[SectorId] = []
    for report in reports:
        if report.guardrail_status in _REJECTED:
            continue
        bucket = grouped.get(report.candidate_sector_id)
        if bucket is None:
            bucket = []
            grouped[report.candidate_sector_id] = bucket
            order.append(report.candidate_sector_id)
        bucket.append(report)

    clusters: list[NormalizedIncidentCluster] = []
    for sector_id in order:
        items = grouped[sector_id]
        durations = [
            item.duration_hours for item in items if item.duration_hours is not None
        ]
        affected = [
            item.affected_count for item in items if item.affected_count is not None
        ]
        flags: list[VulnerabilityFlag] = []
        evidence_types: list[EvidenceType] = []
        provenance_tags: list[ProvenanceTag] = []
        uncertainties: list[str] = []
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
        if not flags:
            flags = [VulnerabilityFlag.NINGUNA]
        source_ids = [item.report_id for item in items]
        clusters.append(
            NormalizedIncidentCluster(
                cluster_id=f"cluster:{sector_id.value}",
                sector_id=sector_id,
                source_report_ids=source_ids,
                report_count=len(source_ids),
                max_duration_hours=max(durations) if durations else None,
                estimated_affected_count=max(affected) if affected else None,
                vulnerability_flags=flags,
                evidence_types=evidence_types,
                requires_human_review=(
                    sector_id is SectorId.UNKNOWN
                    or any(item.requiere_revision for item in items)
                ),
                uncertainties=uncertainties,
                provenance_tags=provenance_tags,
            )
        )
    return clusters
