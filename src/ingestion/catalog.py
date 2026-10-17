"""Closed sector catalog and deterministic alias resolution."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.config import PROJECT_ROOT
from src.contracts import ProvenanceTag, SectorId

SECTORS_FILENAME = "sectors_panama_oeste.json"
REPORTS_FILENAME = "sample_citizen_reports.json"

_OUT_OF_SCOPE_PHRASES = (
    "ciudad de panama",
    "san miguelito",
    "chiriqui",
    "tocumen",
    "darien",
    "david",
)


class SectorResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sector_id: SectorId
    matched_alias: str = ""
    out_of_scope: bool = False
    scope_reason: str = ""


def _fixtures_dir(fixtures_dir: Path | None) -> Path:
    if fixtures_dir is None:
        return PROJECT_ROOT / "data" / "fixtures"
    return fixtures_dir


def normalize_text(text: str) -> str:
    """Lowercase, strip accents, and collapse punctuation to single spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    lowered = without_marks.lower()
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", spaced).strip()


def _phrase_in(text: str, phrase: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise ValueError(f"missing fixture file: {path.name}")
    raw = path.read_bytes()
    if not raw.strip():
        raise ValueError(f"empty fixture file: {path.name}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"fixture file is not utf-8: {path.name}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"fixture file is not json: {path.name}") from exc


def _require_object(payload: object, filename: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError(f"fixture file must be an object: {filename}")
    return payload


def _require_records(payload: dict[str, object], key: str, filename: str) -> list[object]:
    records = payload.get(key)
    if not isinstance(records, list) or not records:
        raise ValueError(f"fixture file has no {key}: {filename}")
    return records


def _provenance(value: object, filename: str) -> ProvenanceTag:
    try:
        return ProvenanceTag(value)
    except ValueError as exc:
        raise ValueError(f"bad provenance in {filename}: {value}") from exc


def _sector_id(value: object, filename: str) -> SectorId:
    try:
        return SectorId(value)
    except ValueError as exc:
        raise ValueError(f"unknown sector id in {filename}: {value}") from exc


def _validate_sectors(payload: dict[str, object]) -> list[str]:
    records = _require_records(payload, "sectors", SECTORS_FILENAME)
    found: list[str] = []
    expected = {
        member.value for member in SectorId if member is not SectorId.UNKNOWN
    }
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"sector record is not an object: {SECTORS_FILENAME}")
        sector_id = _sector_id(record.get("sector_id"), SECTORS_FILENAME)
        if sector_id is SectorId.UNKNOWN:
            raise ValueError(f"UNKNOWN is not a fixture sector: {SECTORS_FILENAME}")
        _provenance(record.get("provenance"), SECTORS_FILENAME)
        aliases = record.get("aliases")
        if (
            not isinstance(aliases, list)
            or not aliases
            or not all(isinstance(alias, str) and alias.strip() for alias in aliases)
        ):
            raise ValueError(f"sector aliases are empty: {sector_id.value}")
        found.append(sector_id.value)
    if len(found) != len(set(found)):
        raise ValueError(f"duplicate sector id in {SECTORS_FILENAME}")
    missing = expected.difference(found)
    if missing:
        raise ValueError(
            f"missing sector ids in {SECTORS_FILENAME}: {', '.join(sorted(missing))}"
        )
    extra = set(found).difference(expected)
    if extra:
        raise ValueError(f"unknown sector id in {SECTORS_FILENAME}: {sorted(extra)}")
    return sorted(found)


def _validate_reports(payload: dict[str, object]) -> None:
    records = _require_records(payload, "reports", REPORTS_FILENAME)
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"report record is not an object: {REPORTS_FILENAME}")
        report_id = record.get("report_id")
        raw_text = record.get("raw_text")
        source_channel = record.get("source_channel")
        if not isinstance(report_id, str) or not report_id.strip():
            raise ValueError(f"report id is empty: {REPORTS_FILENAME}")
        if report_id in seen:
            raise ValueError(f"duplicate report id: {report_id}")
        seen.add(report_id)
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError(f"report text is empty: {report_id}")
        if not isinstance(source_channel, str) or not source_channel.strip():
            raise ValueError(f"report channel is empty: {report_id}")
        _provenance(record.get("provenance"), REPORTS_FILENAME)
        _sector_id(record.get("expected_sector_id"), REPORTS_FILENAME)


def validate_fixtures(fixtures_dir: Path | None = None) -> list[str]:
    """Check the sector catalog and sample reports before any agent runs.

    Returns the sorted non-UNKNOWN sector ids. Raises ValueError when a file
    is missing, empty, not UTF-8, or does not match SectorId and ProvenanceTag.
    """
    root = _fixtures_dir(fixtures_dir)
    sectors = _require_object(_read_json(root / SECTORS_FILENAME), SECTORS_FILENAME)
    reports = _require_object(_read_json(root / REPORTS_FILENAME), REPORTS_FILENAME)
    sector_ids = _validate_sectors(sectors)
    _validate_reports(reports)
    from src.ingestion.geolocator import validate_places

    validate_places(root)
    return sector_ids


def _load_aliases(fixtures_dir: Path | None) -> list[tuple[str, str, SectorId]]:
    root = _fixtures_dir(fixtures_dir)
    payload = _require_object(_read_json(root / SECTORS_FILENAME), SECTORS_FILENAME)
    _validate_sectors(payload)
    ranked: list[tuple[str, str, SectorId]] = []
    records = payload["sectors"]
    if not isinstance(records, list):
        return ranked
    for record in records:
        if not isinstance(record, dict):
            continue
        sector_id = SectorId(str(record["sector_id"]))
        aliases = record.get("aliases")
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            normalized = normalize_text(alias)
            if normalized:
                ranked.append((normalized, alias, sector_id))
    ranked.sort(key=lambda item: len(item[0]), reverse=True)
    return ranked


def _out_of_scope_reason(normalized: str) -> str:
    phrases = sorted(_OUT_OF_SCOPE_PHRASES, key=len, reverse=True)
    for phrase in phrases:
        if _phrase_in(normalized, phrase):
            return phrase
    for match in re.finditer(r"(?<![a-z0-9])colon(?![a-z0-9])", normalized):
        prefix = normalized[max(0, match.start() - 7) : match.start()]
        if prefix != "barrio ":
            return "colon"
    return ""


def resolve_sector_candidate(
    text: str,
    fixtures_dir: Path | None = None,
) -> SectorResolution:
    """Map colloquial text to a closed SectorId using the longest alias."""
    normalized = normalize_text(text)
    for alias_normalized, alias_original, sector_id in _load_aliases(fixtures_dir):
        if _phrase_in(normalized, alias_normalized):
            return SectorResolution(
                sector_id=sector_id,
                matched_alias=alias_original,
                out_of_scope=False,
            )
    reason = _out_of_scope_reason(normalized)
    if reason:
        return SectorResolution(
            sector_id=SectorId.UNKNOWN,
            out_of_scope=True,
            scope_reason=reason,
        )
    return SectorResolution(sector_id=SectorId.UNKNOWN)
