"""Shared pydantic contracts and closed enumerations."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


class ProvenanceTag(StrEnum):
    OFFICIAL_SOURCE = "OFFICIAL_SOURCE"
    SYNTHETIC_DEMO = "SYNTHETIC_DEMO"
    ASSUMPTION = "ASSUMPTION"


class SectorId(StrEnum):
    ARRAIJAN_VISTA_ALEGRE = "ARRAIJAN_VISTA_ALEGRE"
    ARRAIJAN_BURUNGA = "ARRAIJAN_BURUNGA"
    ARRAIJAN_NUEVO_CHORRILLO = "ARRAIJAN_NUEVO_CHORRILLO"
    ARRAIJAN_VACAMONTE = "ARRAIJAN_VACAMONTE"
    ARRAIJAN_CERRO_SILVESTRE = "ARRAIJAN_CERRO_SILVESTRE"
    ARRAIJAN_CABECERA = "ARRAIJAN_CABECERA"
    CHORRERA_BARRIO_COLON = "CHORRERA_BARRIO_COLON"
    CHORRERA_BARRIO_BALBOA = "CHORRERA_BARRIO_BALBOA"
    CHORRERA_GUADALUPE = "CHORRERA_GUADALUPE"
    CHORRERA_EL_COCO = "CHORRERA_EL_COCO"
    CHORRERA_PUERTO_CAIMITO = "CHORRERA_PUERTO_CAIMITO"
    UNKNOWN = "UNKNOWN"


class EvidenceType(StrEnum):
    TEXT_REPORT = "TEXT_REPORT"
    INSTITUTIONAL_REPORT = "INSTITUTIONAL_REPORT"
    MULTIPLE_NEIGHBORS = "MULTIPLE_NEIGHBORS"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"


class VulnerabilityFlag(StrEnum):
    HOSPITAL_SALUD = "HOSPITAL_SALUD"
    ESCUELA = "ESCUELA"
    ADULTOS_MAYORES = "ADULTOS_MAYORES"
    INFANTES = "INFANTES"
    ALBERGUE = "ALBERGUE"
    NINGUNA = "NINGUNA"


class GuardrailStatus(StrEnum):
    VALID = "VALID"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED_EMPTY = "REJECTED_EMPTY"
    REJECTED_MALICIOUS = "REJECTED_MALICIOUS"
    REJECTED_OUT_OF_SCOPE = "REJECTED_OUT_OF_SCOPE"
    REJECTED_ABSURD = "REJECTED_ABSURD"


class GeoPrecision(StrEnum):
    POINT = "POINT"
    SECTOR = "SECTOR"
    UNKNOWN = "UNKNOWN"


class DecisionAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CORRECT = "CORRECT"


def _ninguna_is_exclusive(flags: list[VulnerabilityFlag]) -> list[VulnerabilityFlag]:
    if VulnerabilityFlag.NINGUNA in flags and len(flags) != 1:
        raise ValueError("NINGUNA must be the only vulnerability flag")
    return flags


_VulnerabilityFlags = Annotated[
    list[VulnerabilityFlag],
    AfterValidator(_ninguna_is_exclusive),
]


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReportInput(_ClosedModel):
    report_id: str = Field(min_length=1)
    raw_text: str
    source_channel: str = Field(min_length=1)
    provenance: ProvenanceTag
    timestamp: datetime


class ReportExtracted(_ClosedModel):
    report_id: str = Field(min_length=1)
    candidate_sector_id: SectorId
    raw_location_mention: str = ""
    duration_hours: int | None = None
    affected_count: int | None = None
    vulnerability_flags: _VulnerabilityFlags = []
    evidence_type: EvidenceType
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainties: list[str] = []
    requiere_revision: bool
    guardrail_status: GuardrailStatus
    guardrail_reason: str = ""
    provenance: ProvenanceTag
    place_id: str = ""
    latitude: float | None = None
    longitude: float | None = None
    geo_precision: GeoPrecision = GeoPrecision.UNKNOWN


ReporteExtraido = ReportExtracted


class NormalizedIncidentCluster(_ClosedModel):
    cluster_id: str = Field(min_length=1)
    sector_id: SectorId
    source_report_ids: list[str]
    report_count: int
    max_duration_hours: int | None = None
    estimated_affected_count: int | None = None
    vulnerability_flags: _VulnerabilityFlags = []
    evidence_types: list[EvidenceType] = []
    requires_human_review: bool
    uncertainties: list[str] = []
    provenance_tags: list[ProvenanceTag] = []
    place_id: str = ""
    latitude: float | None = None
    longitude: float | None = None
    geo_precision: GeoPrecision = GeoPrecision.UNKNOWN

    @model_validator(mode="after")
    def _report_count_matches_sources(self) -> Self:
        if self.report_count != len(self.source_report_ids):
            raise ValueError("report_count must equal len(source_report_ids)")
        return self


class TraceEntry(_ClosedModel):
    trace_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    action: str = Field(min_length=1)
    input_summary: str
    output_summary: str
    status: str = Field(min_length=1)
    timestamp: datetime


class FactorNote(_ClosedModel):
    name: str = Field(min_length=1)
    evidence: str
    uncertainty: str = ""


class Assessment(_ClosedModel):
    cluster_id: str = Field(min_length=1)
    factors: list[FactorNote]
    risks: list[str] = []
    uncertainties: list[str] = []


class FactorBreakdown(_ClosedModel):
    factor: str = Field(min_length=1)
    points: float
    reason: str


class PriorityResult(_ClosedModel):
    cluster_id: str = Field(min_length=1)
    score: float
    breakdown: list[FactorBreakdown]
    formula_version: str = Field(min_length=1)
    explanation: str


class Assignment(_ClosedModel):
    vehicle_id: str = Field(min_length=1)
    sector_id: SectorId
    order: int = Field(ge=1)
    volume_liters: int = Field(ge=0)


class PlanDraft(_ClosedModel):
    plan_id: str = Field(min_length=1)
    assignments: list[Assignment] = []
    route_order: list[str] = []
    constraints_satisfied: list[str] = []
    unserved_demand: list[str] = []
    explanation: str = ""


class HumanDecision(_ClosedModel):
    plan_id: str = Field(min_length=1)
    action: DecisionAction
    actor: str = Field(min_length=1)
    comment: str = ""
    timestamp: datetime


class ExecutionResult(_ClosedModel):
    saved: bool
    plan_id: str = Field(min_length=1)
    audit_id: str = Field(min_length=1)
    outbox_id: str | None = None
    detail: str = ""


__all__ = [
    "Assessment",
    "Assignment",
    "DecisionAction",
    "EvidenceType",
    "ExecutionResult",
    "FactorBreakdown",
    "FactorNote",
    "GeoPrecision",
    "GuardrailStatus",
    "HumanDecision",
    "NormalizedIncidentCluster",
    "PlanDraft",
    "PriorityResult",
    "ProvenanceTag",
    "ReportExtracted",
    "ReportInput",
    "ReporteExtraido",
    "SectorId",
    "TraceEntry",
    "VulnerabilityFlag",
]
