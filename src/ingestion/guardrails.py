"""Deterministic guardrails for citizen water reports.

Prompt text is not a security boundary. These checks decide rejection,
review, and which numbers are allowed to survive a model draft.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from src.contracts import GuardrailStatus, ReportExtracted, SectorId, VulnerabilityFlag
from src.ingestion.catalog import normalize_text, resolve_sector_candidate

# Prototype assumption, not an official IDAAN factor.
PEOPLE_PER_FAMILY = 4
MAX_DURATION_HOURS = 2160
MAX_AFFECTED_COUNT = 100_000

_NUMBER_WORDS = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "quince": 15,
    "veinte": 20,
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
}
_NUMBER = (
    r"\d+|cincuenta|cuarenta|treinta|quince|veinte|doce|once|diez|"
    r"nueve|ocho|siete|seis|cinco|cuatro|tres|dos|una|uno|un"
)
_DURATION_RE = re.compile(
    rf"(?<![a-z0-9])({_NUMBER}) (hora|horas|dia|dias|semana|semanas)(?![a-z0-9])"
)
_PEOPLE_RE = re.compile(
    rf"(?<![a-z0-9])({_NUMBER}) (persona|personas|habitante|habitantes)(?![a-z0-9])"
)
_FAMILY_RE = re.compile(rf"(?<![a-z0-9])({_NUMBER}) (familia|familias)(?![a-z0-9])")
_HOUSE_RE = re.compile(
    rf"(?<![a-z0-9])({_NUMBER}) (casa|casas|vivienda|viviendas)(?![a-z0-9])"
)
_MALICIOUS_NEEDLES = (
    "ignore previous instructions",
    "ignora las instrucciones",
    "system prompt",
    "aprueba el plan",
    "despacha las cisternas",
    "despacha cisternas",
    "drop table",
)
_WATER_TERMS = (
    "agua",
    "cisterna",
    "tuberia",
    "potabilizadora",
    "grifo",
    "idaan",
    "tanque",
)
_VULNERABILITY_TERMS: tuple[tuple[VulnerabilityFlag, tuple[str, ...]], ...] = (
    (
        VulnerabilityFlag.HOSPITAL_SALUD,
        ("hospital", "clinica", "centro de salud", "puesto de salud"),
    ),
    (VulnerabilityFlag.ESCUELA, ("escuela", "colegio")),
    (
        VulnerabilityFlag.ADULTOS_MAYORES,
        ("adultos mayores", "adulto mayor", "asilo", "ancianos", "anciano"),
    ),
    (
        VulnerabilityFlag.INFANTES,
        ("infantes", "infante", "ninos", "nino", "bebes", "bebe"),
    ),
    (VulnerabilityFlag.ALBERGUE, ("albergues", "albergue")),
)


class InputInspection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: GuardrailStatus
    reason: str = ""


class TextSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_hours: int | None = None
    affected_count: int | None = None
    affected_is_assumption: bool = False
    vulnerability_flags: list[VulnerabilityFlag] = [VulnerabilityFlag.NINGUNA]
    has_temporal_evidence: bool = False
    has_quantity_evidence: bool = False
    uncertainties: list[str] = []


def _phrase_in(text: str, phrase: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _parse_number(token: str) -> int:
    if token.isdigit():
        return int(token)
    return _NUMBER_WORDS[token]


def _to_hours(amount: int, unit: str) -> int:
    if unit.startswith("semana"):
        return amount * 24 * 7
    if unit.startswith("dia"):
        return amount * 24
    return amount


def _is_absurd_duration(value: int | None) -> bool:
    return value is not None and (value <= 0 or value > MAX_DURATION_HOURS)


def _is_absurd_affected(value: int | None) -> bool:
    return value is not None and (value <= 0 or value > MAX_AFFECTED_COUNT)


def inspect_input_guardrails(raw_text: str) -> InputInspection:
    """Reject empty, malicious, or out-of-scope text before any model call.

    Empty wins over other classes. Malicious wins over an outside location.
    A water report whose place is unknown stays valid so a later step can
    mark it for review instead of dropping it.
    """
    normalized = normalize_text(raw_text)
    if not normalized:
        return InputInspection(
            status=GuardrailStatus.REJECTED_EMPTY,
            reason="report text is empty",
        )
    lowered = raw_text.lower()
    if "<script" in lowered or any(
        needle in lowered or needle in normalized for needle in _MALICIOUS_NEEDLES
    ):
        return InputInspection(
            status=GuardrailStatus.REJECTED_MALICIOUS,
            reason="report text matches a malicious pattern",
        )
    resolution = resolve_sector_candidate(raw_text)
    about_water = any(_phrase_in(normalized, term) for term in _WATER_TERMS)
    if resolution.out_of_scope:
        return InputInspection(
            status=GuardrailStatus.REJECTED_OUT_OF_SCOPE,
            reason=resolution.scope_reason or "location is outside Panama Oeste",
        )
    if not about_water:
        return InputInspection(
            status=GuardrailStatus.REJECTED_OUT_OF_SCOPE,
            reason="report is not about water supply",
        )
    return InputInspection(status=GuardrailStatus.VALID)


def extract_text_signals(report_text: str) -> TextSignals:
    """Read duration, affected people, and vulnerability only from the text.

    Family counts become people with PEOPLE_PER_FAMILY and an explicit
    assumption note. 'desde ayer' counts as 24 hours and is marked uncertain.
    """
    normalized = normalize_text(report_text)
    uncertainties: list[str] = []
    durations = [
        _to_hours(_parse_number(amount), unit)
        for amount, unit in _DURATION_RE.findall(normalized)
    ]
    has_temporal = bool(durations)
    duration_hours = max(durations) if durations else None
    if duration_hours is None and _phrase_in(normalized, "desde ayer"):
        duration_hours = 24
        has_temporal = True
        uncertainties.append("desde ayer counted as 24 hours")

    people = [_parse_number(amount) for amount, _unit in _PEOPLE_RE.findall(normalized)]
    families = [_parse_number(amount) for amount, _unit in _FAMILY_RE.findall(normalized)]
    houses = [_parse_number(amount) for amount, _unit in _HOUSE_RE.findall(normalized)]
    affected_is_assumption = False
    affected_count: int | None = None
    if people:
        affected_count = max(people)
    elif families:
        affected_count = max(families) * PEOPLE_PER_FAMILY
        affected_is_assumption = True
        uncertainties.append(
            "affected_count uses 4 people per family (ASSUMPTION, not an official factor)"
        )
    elif houses:
        affected_count = max(houses)
        affected_is_assumption = True
        uncertainties.append("house count is not a person count")

    flags = [
        flag
        for flag, phrases in _VULNERABILITY_TERMS
        if any(_phrase_in(normalized, phrase) for phrase in phrases)
    ]
    if not flags:
        flags = [VulnerabilityFlag.NINGUNA]

    return TextSignals(
        duration_hours=duration_hours,
        affected_count=affected_count,
        affected_is_assumption=affected_is_assumption,
        vulnerability_flags=flags,
        has_temporal_evidence=has_temporal,
        has_quantity_evidence=affected_count is not None,
        uncertainties=uncertainties,
    )


def enforce_post_extraction_guardrails(
    extracted: ReportExtracted,
    raw_text: str,
) -> ReportExtracted:
    """Drop invented numbers, keep code-backed ones, and flag absurd ranges.

    A model duration or affected count with no evidence in the text becomes
    None. When the text does contain evidence, the code value replaces the
    model value. Absurd incoming or remaining values set REJECTED_ABSURD.
    Unknown sector, missing duration, or confidence below 0.70 force review.
    """
    signals = extract_text_signals(raw_text)
    uncertainties = list(extracted.uncertainties)
    duration = extracted.duration_hours
    affected = extracted.affected_count
    incoming_absurd = _is_absurd_duration(duration) or _is_absurd_affected(affected)

    if duration is not None and not signals.has_temporal_evidence:
        duration = None
        uncertainties.append("duration_hours removed: no temporal evidence in the text")
    elif signals.has_temporal_evidence:
        duration = signals.duration_hours

    if affected is not None and not signals.has_quantity_evidence:
        affected = None
        uncertainties.append("affected_count removed: no quantity evidence in the text")
    elif signals.has_quantity_evidence:
        affected = signals.affected_count

    for note in signals.uncertainties:
        if note not in uncertainties:
            uncertainties.append(note)

    status = extracted.guardrail_status
    reason = extracted.guardrail_reason
    revision = extracted.requiere_revision
    remaining_absurd = _is_absurd_duration(duration) or _is_absurd_affected(affected)
    if incoming_absurd or remaining_absurd:
        status = GuardrailStatus.REJECTED_ABSURD
        reason = "duration or affected count is outside the physical range"
        revision = True

    needs_review = (
        extracted.candidate_sector_id is SectorId.UNKNOWN
        or duration is None
        or extracted.confidence < 0.70
    )
    if needs_review:
        revision = True
        if status is GuardrailStatus.VALID:
            status = GuardrailStatus.NEEDS_REVIEW
            reason = reason or "sector, duration, or confidence needs human review"

    return extracted.model_copy(
        update={
            "duration_hours": duration,
            "affected_count": affected,
            "vulnerability_flags": signals.vulnerability_flags,
            "uncertainties": uncertainties,
            "requiere_revision": revision,
            "guardrail_status": status,
            "guardrail_reason": reason,
        }
    )
