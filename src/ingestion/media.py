"""Read a citizen photo or voice note without inventing the report.

A JPEG location comes from the GPS tag in the file. It is matched to the
nearest demonstration anchor. A voice note is not transcribed on this machine:
the text is left empty instead of being guessed.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from src.ingestion.geolocator import locate_coordinates

_NO_TRANSCRIPT = (
    "No hay un motor de transcripción en este equipo. No se inventó lo que dice la nota de voz."
)
_NO_GPS = "La foto no trae coordenadas. No se inventó el lugar."
_CHANNEL_NOTE = (
    "La foto no trae un texto. Se tomó como reporte de falta de agua porque entró por este canal "
    "y queda para revisión."
)


@dataclass(frozen=True)
class CitizenMedia:
    kind: str
    filename: str
    data: bytes
    latitude: float | None = None
    longitude: float | None = None


_PENDING_MEDIA: dict[str, CitizenMedia] = {}


def remember_media(report_id: str, media: CitizenMedia) -> None:
    """Keep an attachment until ingest_report reads it. The bytes are not traced."""
    _PENDING_MEDIA[report_id] = media


def take_media(report_id: str) -> CitizenMedia | None:
    return _PENDING_MEDIA.pop(report_id, None)


@dataclass(frozen=True)
class MediaReading:
    text: str
    uncertainties: tuple[str, ...]
    outside: bool
    action: str


def read_citizen_media(media: CitizenMedia) -> MediaReading:
    """Turn an attachment into text the rest of ingestion can check."""
    if media.kind == "image":
        return _read_image(media)
    if media.kind == "audio":
        return _read_audio()
    return MediaReading("", ("El archivo adjunto no es una foto ni una nota de voz.",), False, "read_media")


def _read_audio() -> MediaReading:
    return MediaReading("", (_NO_TRANSCRIPT,), False, "read_audio")


def _read_image(media: CitizenMedia) -> MediaReading:
    gps = read_jpeg_gps(media.data)
    if gps is None and media.latitude is not None and media.longitude is not None:
        gps = (media.latitude, media.longitude)
    if gps is None:
        return MediaReading("", (_NO_GPS,), False, "read_image")
    fix = locate_coordinates(gps[0], gps[1])
    if fix.out_of_scope:
        return MediaReading("", (fix.scope_reason,), True, "read_image")
    if not fix.matched_alias:
        return MediaReading("", (fix.scope_reason or _NO_GPS,), False, "read_image")
    return MediaReading(
        f"falta de agua {fix.matched_alias}",
        (
            "Las coordenadas salen de la foto. El lugar es el ancla de demostración más cercana, no un levantamiento.",
            _CHANNEL_NOTE,
        ),
        False,
        "read_image",
    )


def read_jpeg_gps(data: bytes) -> tuple[float, float] | None:
    """Return latitude and longitude from a JPEG GPS tag, if the file has one."""
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            return None
        marker = data[offset + 1]
        if marker == 0xDA:
            return None
        size = int.from_bytes(data[offset + 2 : offset + 4], "big")
        if size < 2 or offset + 2 + size > len(data):
            return None
        if marker == 0xE1:
            payload = data[offset + 4 : offset + 2 + size]
            if payload.startswith(b"Exif\x00\x00"):
                gps = _gps_from_tiff(payload[6:])
                if gps is not None:
                    return gps
        offset += 2 + size
    return None


def jpeg_with_gps(latitude: float, longitude: float) -> bytes:
    """Build a tiny JPEG whose only useful content is a GPS tag. Used by tests."""
    tiff = _tiff_with_gps(latitude, longitude)
    payload = b"Exif\x00\x00" + tiff
    segment = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    return b"\xff\xd8" + segment + b"\xff\xd9"


def _dms(value: float) -> list[tuple[int, int]]:
    absolute = abs(value)
    degrees = int(absolute)
    minutes_float = (absolute - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    return [(degrees, 1), (minutes, 1), (int(round(seconds * 1000)), 1000)]


def _tiff_with_gps(latitude: float, longitude: float) -> bytes:
    lat_ref = struct.unpack("<I", (b"N\x00" if latitude >= 0 else b"S\x00") + b"\x00\x00")[0]
    lon_ref = struct.unpack("<I", (b"E\x00" if longitude >= 0 else b"W\x00") + b"\x00\x00")[0]
    gps_offset = 26
    lat_offset = 80
    lon_offset = 104
    header = b"II" + struct.pack("<HI", 42, 8)
    ifd0 = struct.pack("<H", 1) + struct.pack("<HHII", 0x8825, 4, 1, gps_offset) + struct.pack("<I", 0)
    gps = struct.pack("<H", 4)
    gps += struct.pack("<HHII", 1, 2, 2, lat_ref)
    gps += struct.pack("<HHII", 2, 5, 3, lat_offset)
    gps += struct.pack("<HHII", 3, 2, 2, lon_ref)
    gps += struct.pack("<HHII", 4, 5, 3, lon_offset)
    gps += struct.pack("<I", 0)
    values = b"".join(struct.pack("<II", num, den) for num, den in _dms(latitude) + _dms(longitude))
    return header + ifd0 + gps + values


def _gps_from_tiff(tiff: bytes) -> tuple[float, float] | None:
    if len(tiff) < 8 or tiff[:2] not in (b"II", b"MM"):
        return None
    order = "<" if tiff[:2] == b"II" else ">"
    if struct.unpack_from(order + "H", tiff, 2)[0] != 42:
        return None
    ifd = struct.unpack_from(order + "I", tiff, 4)[0]
    gps_at = _ifd_value(tiff, ifd, order, 0x8825)
    if gps_at is None:
        return None
    return _read_gps_ifd(tiff, gps_at, order)


def _ifd_value(tiff: bytes, ifd: int, order: str, wanted: int) -> int | None:
    if ifd < 0 or ifd + 2 > len(tiff):
        return None
    count = struct.unpack_from(order + "H", tiff, ifd)[0]
    for index in range(count):
        start = ifd + 2 + index * 12
        if start + 12 > len(tiff):
            return None
        tag, kind, number, value = struct.unpack_from(order + "HHII", tiff, start)
        if tag == wanted and kind == 4 and number == 1:
            return value
    return None


def _read_gps_ifd(tiff: bytes, ifd: int, order: str) -> tuple[float, float] | None:
    if ifd + 2 > len(tiff):
        return None
    count = struct.unpack_from(order + "H", tiff, ifd)[0]
    fields: dict[int, tuple[int, int, int]] = {}
    for index in range(count):
        start = ifd + 2 + index * 12
        if start + 12 > len(tiff):
            return None
        tag, kind, number, value = struct.unpack_from(order + "HHII", tiff, start)
        fields[tag] = (kind, number, value)
    lat = _coordinate(tiff, order, fields.get(1), fields.get(2))
    lon = _coordinate(tiff, order, fields.get(3), fields.get(4))
    if lat is None or lon is None:
        return None
    return lat, lon


def _coordinate(
    tiff: bytes,
    order: str,
    ref_field: tuple[int, int, int] | None,
    value_field: tuple[int, int, int] | None,
) -> float | None:
    if ref_field is None or value_field is None:
        return None
    ref_kind, ref_count, ref_value = ref_field
    if ref_kind != 2 or ref_count < 1:
        return None
    ref = struct.pack(order + "I", ref_value)[:1].decode("ascii", errors="ignore")
    kind, number, offset = value_field
    if kind != 5 or number < 1:
        return None
    if offset + number * 8 > len(tiff):
        return None
    parts: list[float] = []
    for index in range(number):
        num, den = struct.unpack_from(order + "II", tiff, offset + index * 8)
        parts.append(0 if den == 0 else num / den)
    while len(parts) < 3:
        parts.append(0)
    decimal = parts[0] + parts[1] / 60 + parts[2] / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal
