"""Deterministic place anchors for Panama Oeste.

Coordinates are demo assumptions used to separate incidents inside one sector.
They are not a survey and they are not the IDAAN pipe layer.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.config import PROJECT_ROOT
from src.contracts import GeoPrecision, ProvenanceTag, ReportExtracted, SectorId
from src.ingestion.catalog import normalize_text, resolve_sector_candidate

PLACES_FILENAME = "places_panama_oeste.json"
SAME_INCIDENT_METERS = 800
_LATITUDE_RANGE = (8.70, 9.15)
_LONGITUDE_RANGE = (-80.05, -79.45)
_PLACE_ID_RE = re.compile(r"^[A-Z0-9_]+$")
_COORDINATE_NOTE = "coordinates are ASSUMPTION demo anchors, not a surveyed location"
_SECTOR_NOTE = "location is only as precise as the sector"


class PlaceFix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sector_id: SectorId
    place_id: str = ""
    latitude: float | None = None
    longitude: float | None = None
    geo_precision: GeoPrecision = GeoPrecision.UNKNOWN
    matched_alias: str = ""
    out_of_scope: bool = False
    scope_reason: str = ""


def _fixtures_dir(fixtures_dir: Path | None) -> Path:
    if fixtures_dir is None:
        return PROJECT_ROOT / "data" / "fixtures"
    return fixtures_dir


def _phrase_in(text: str, phrase: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def haversine_meters(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """Great-circle distance in meters."""
    radius = 6_371_000.0
    phi_a = math.radians(latitude_a)
    phi_b = math.radians(latitude_b)
    delta_phi = math.radians(latitude_b - latitude_a)
    delta_lambda = math.radians(longitude_b - longitude_a)
    chord = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(chord))


def _read_places(fixtures_dir: Path | None) -> dict[str, object]:
    path = _fixtures_dir(fixtures_dir) / PLACES_FILENAME
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
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"fixture file is not json: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"fixture file must be an object: {path.name}")
    return payload


def validate_places(fixtures_dir: Path | None = None) -> list[str]:
    """Check demo place anchors. Returns sorted place ids."""
    payload = _read_places(fixtures_dir)
    records = payload.get("places")
    if not isinstance(records, list) or not records:
        raise ValueError(f"fixture file has no places: {PLACES_FILENAME}")
    found: list[str] = []
    aliases_seen: set[str] = set()
    sectors_seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"place record is not an object: {PLACES_FILENAME}")
        place_id = record.get("place_id")
        if not isinstance(place_id, str) or not _PLACE_ID_RE.fullmatch(place_id):
            raise ValueError(f"bad place id in {PLACES_FILENAME}: {place_id}")
        if place_id in found:
            raise ValueError(f"duplicate place id: {place_id}")
        found.append(place_id)
        try:
            sector_id = SectorId(record.get("sector_id"))
        except ValueError as exc:
            raise ValueError(
                f"unknown sector id in {PLACES_FILENAME}: {record.get('sector_id')}"
            ) from exc
        if sector_id is SectorId.UNKNOWN:
            raise ValueError(f"UNKNOWN is not a place sector: {place_id}")
        sectors_seen.add(sector_id.value)
        try:
            provenance = ProvenanceTag(record.get("provenance"))
        except ValueError as exc:
            raise ValueError(
                f"bad provenance in {PLACES_FILENAME}: {record.get('provenance')}"
            ) from exc
        if provenance is not ProvenanceTag.ASSUMPTION:
            raise ValueError(f"place coordinates must be tagged ASSUMPTION: {place_id}")
        latitude = record.get("latitude")
        longitude = record.get("longitude")
        if not isinstance(latitude, (int, float)) or isinstance(latitude, bool):
            raise ValueError(f"place latitude is missing: {place_id}")
        if not isinstance(longitude, (int, float)) or isinstance(longitude, bool):
            raise ValueError(f"place longitude is missing: {place_id}")
        if not _LATITUDE_RANGE[0] <= float(latitude) <= _LATITUDE_RANGE[1]:
            raise ValueError(f"place latitude is outside Panama Oeste: {place_id}")
        if not _LONGITUDE_RANGE[0] <= float(longitude) <= _LONGITUDE_RANGE[1]:
            raise ValueError(f"place longitude is outside Panama Oeste: {place_id}")
        aliases = record.get("aliases")
        if (
            not isinstance(aliases, list)
            or not aliases
            or not all(isinstance(alias, str) and alias.strip() for alias in aliases)
        ):
            raise ValueError(f"place aliases are empty: {place_id}")
        for alias in aliases:
            key = normalize_text(alias)
            if key in aliases_seen:
                raise ValueError(f"duplicate place alias: {alias}")
            aliases_seen.add(key)
    expected = {member.value for member in SectorId if member is not SectorId.UNKNOWN}
    missing = expected.difference(sectors_seen)
    if missing:
        raise ValueError(
            f"missing place sectors in {PLACES_FILENAME}: {', '.join(sorted(missing))}"
        )
    return sorted(found)


def _load_places(fixtures_dir: Path | None) -> list[tuple[str, str, SectorId, float, float]]:
    validate_places(fixtures_dir)
    payload = _read_places(fixtures_dir)
    records = payload["places"]
    ranked: list[tuple[str, str, SectorId, float, float]] = []
    if not isinstance(records, list):
        return ranked
    for record in records:
        if not isinstance(record, dict):
            continue
        place_id = str(record["place_id"])
        sector_id = SectorId(str(record["sector_id"]))
        latitude = float(record["latitude"])
        longitude = float(record["longitude"])
        aliases = record.get("aliases")
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if isinstance(alias, str) and alias.strip():
                ranked.append(
                    (normalize_text(alias), place_id, sector_id, latitude, longitude)
                )
    ranked.sort(key=lambda item: len(item[0]), reverse=True)
    return ranked


def _centroids(fixtures_dir: Path | None) -> dict[SectorId, tuple[float, float]]:
    payload = _read_places(fixtures_dir)
    totals: dict[SectorId, list[tuple[float, float]]] = {}
    records = payload.get("places")
    if not isinstance(records, list):
        return {}
    for record in records:
        if not isinstance(record, dict):
            continue
        sector_id = SectorId(str(record["sector_id"]))
        totals.setdefault(sector_id, []).append(
            (float(record["latitude"]), float(record["longitude"]))
        )
    return {
        sector_id: (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
        for sector_id, points in totals.items()
    }


def geocode_text(text: str, fixtures_dir: Path | None = None) -> PlaceFix:
    """Resolve text to a demo place, a sector centroid, or unknown.

    A named landmark wins over the bare sector. Coordinates are the fixture
    anchors. The model is not asked for a latitude.
    """
    normalized = normalize_text(text)
    if not normalized:
        return PlaceFix(sector_id=SectorId.UNKNOWN, geo_precision=GeoPrecision.UNKNOWN)
    for alias, place_id, sector_id, latitude, longitude in _load_places(fixtures_dir):
        if _phrase_in(normalized, alias):
            return PlaceFix(
                sector_id=sector_id,
                place_id=place_id,
                latitude=latitude,
                longitude=longitude,
                geo_precision=GeoPrecision.POINT,
                matched_alias=alias,
            )
    resolution = resolve_sector_candidate(text, fixtures_dir)
    if resolution.out_of_scope or resolution.sector_id is SectorId.UNKNOWN:
        return PlaceFix(
            sector_id=SectorId.UNKNOWN,
            geo_precision=GeoPrecision.UNKNOWN,
            out_of_scope=resolution.out_of_scope,
            scope_reason=resolution.scope_reason,
        )
    centroid = _centroids(fixtures_dir).get(resolution.sector_id)
    if centroid is None:
        return PlaceFix(sector_id=resolution.sector_id, geo_precision=GeoPrecision.SECTOR)
    return PlaceFix(
        sector_id=resolution.sector_id,
        latitude=centroid[0],
        longitude=centroid[1],
        geo_precision=GeoPrecision.SECTOR,
        matched_alias=resolution.matched_alias,
    )


def geolocate_report(report: ReportExtracted, text: str, fixtures_dir: Path | None = None) -> ReportExtracted:
    """Stamp a report with the catalog place. Does not invent a coordinate."""
    fix = geocode_text(text, fixtures_dir)
    uncertainties = list(report.uncertainties)
    if fix.geo_precision is GeoPrecision.POINT and _COORDINATE_NOTE not in uncertainties:
        uncertainties.append(_COORDINATE_NOTE)
    if fix.geo_precision is GeoPrecision.SECTOR and _SECTOR_NOTE not in uncertainties:
        uncertainties.append(_SECTOR_NOTE)
    update: dict[str, object] = {
        "place_id": fix.place_id,
        "latitude": fix.latitude,
        "longitude": fix.longitude,
        "geo_precision": fix.geo_precision,
        "uncertainties": uncertainties,
    }
    if fix.geo_precision is not GeoPrecision.UNKNOWN:
        update["candidate_sector_id"] = fix.sector_id
    if fix.matched_alias and not report.raw_location_mention:
        update["raw_location_mention"] = fix.matched_alias
    if fix.geo_precision is GeoPrecision.SECTOR:
        update["requiere_revision"] = True
    return report.model_copy(update=update)
