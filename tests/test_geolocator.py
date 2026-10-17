"""Demo place anchors and their handoff into ingestion."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.contracts import GeoPrecision, ProvenanceTag, ReportInput, SectorId
from src.ingestion.agent import ingest_report
from src.ingestion.deduplicator import deduplicate_reports
from src.ingestion.geolocator import SAME_INCIDENT_METERS, geocode_text, haversine_meters


def _input(text: str, report_id: str) -> ReportInput:
    return ReportInput(
        report_id=report_id,
        raw_text=text,
        source_channel="whatsapp",
        provenance=ProvenanceTag.SYNTHETIC_DEMO,
        timestamp=datetime(2026, 10, 16, tzinfo=timezone.utc),
    )


class GeolocatorTests(unittest.TestCase):
    def test_named_landmark_is_a_point_and_bare_sector_is_not(self) -> None:
        point = geocode_text("por el chino de Vista Alegre")
        self.assertEqual(point.geo_precision, GeoPrecision.POINT)
        self.assertEqual(point.place_id, "VISTA_ALEGRE_CHINO")
        self.assertEqual(point.sector_id, SectorId.ARRAIJAN_VISTA_ALEGRE)
        self.assertIsNotNone(point.latitude)
        self.assertIsNotNone(point.longitude)

        sector = geocode_text("sin agua en Vista Alegre")
        self.assertEqual(sector.geo_precision, GeoPrecision.SECTOR)
        self.assertEqual(sector.place_id, "")
        self.assertEqual(sector.sector_id, SectorId.ARRAIJAN_VISTA_ALEGRE)

    def test_vista_alegre_landmarks_are_farther_than_one_incident(self) -> None:
        chino = geocode_text("chino de Vista Alegre")
        xtra = geocode_text("Xtra de Vista Alegre")
        assert chino.latitude is not None and chino.longitude is not None
        assert xtra.latitude is not None and xtra.longitude is not None
        distance = haversine_meters(
            chino.latitude, chino.longitude, xtra.latitude, xtra.longitude
        )
        self.assertGreater(distance, SAME_INCIDENT_METERS)

    def test_loma_cova_is_near_burunga(self) -> None:
        loma = geocode_text("Loma Cova")
        burunga = geocode_text("Burunga")
        assert loma.latitude is not None and loma.longitude is not None
        assert burunga.latitude is not None and burunga.longitude is not None
        distance = haversine_meters(
            loma.latitude, loma.longitude, burunga.latitude, burunga.longitude
        )
        self.assertLessEqual(distance, SAME_INCIDENT_METERS)
        self.assertEqual(loma.sector_id, burunga.sector_id)

    def test_outside_panama_oeste_has_no_coordinate(self) -> None:
        found = geocode_text("sin agua en David, Chiriqui")
        self.assertEqual(found.geo_precision, GeoPrecision.UNKNOWN)
        self.assertIsNone(found.latitude)
        self.assertTrue(found.out_of_scope)

    def test_ingest_splits_two_vista_alegre_landmarks_and_joins_repeats(self) -> None:
        chino = ingest_report(
            _input("48 horas sin agua y 15 personas por el chino de Vista Alegre", "A")
        )
        repeat = ingest_report(
            _input("sin agua por el chino de Vista Alegre desde ayer", "B")
        )
        xtra = ingest_report(
            _input("Xtra de Vista Alegre lleva 10 horas sin agua y hay 4 personas", "C")
        )
        self.assertEqual(chino.extracted.place_id, "VISTA_ALEGRE_CHINO")
        self.assertEqual(chino.extracted.geo_precision, GeoPrecision.POINT)
        clusters = deduplicate_reports(
            [chino.extracted, repeat.extracted, xtra.extracted]
        )
        groups = {frozenset(cluster.source_report_ids) for cluster in clusters}
        self.assertEqual(groups, {frozenset({"A", "B"}), frozenset({"C"})})


if __name__ == "__main__":
    unittest.main()
