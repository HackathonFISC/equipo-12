"""Photo GPS and voice notes must not invent a citizen report."""

from __future__ import annotations

import unittest

from src.ingestion.media import jpeg_with_gps, read_citizen_media, read_jpeg_gps, CitizenMedia


class MediaReadTests(unittest.TestCase):
    def test_photo_gps_uses_the_nearest_demo_place_and_invents_no_numbers(self) -> None:
        photo = jpeg_with_gps(8.95, -79.7)
        gps = read_jpeg_gps(photo)
        self.assertIsNotNone(gps)
        assert gps is not None
        self.assertAlmostEqual(gps[0], 8.95, places=4)
        self.assertAlmostEqual(gps[1], -79.7, places=4)
        reading = read_citizen_media(CitizenMedia("image", "grifo.jpg", photo))
        self.assertIn("chino de vista alegre", reading.text)
        self.assertIn("falta de agua", reading.text)
        self.assertNotIn("hora", reading.text)
        self.assertNotIn("persona", reading.text)
        self.assertFalse(reading.outside)
        self.assertTrue(any("ancla" in note for note in reading.uncertainties))

    def test_photo_without_gps_does_not_invent_a_place(self) -> None:
        reading = read_citizen_media(CitizenMedia("image", "grifo.jpg", b"\xff\xd8\xff\xd9"))
        self.assertEqual(reading.text, "")
        self.assertFalse(reading.outside)
        self.assertTrue(any("No se inventó el lugar" in note for note in reading.uncertainties))

    def test_camera_photo_uses_the_phone_location_when_the_file_has_no_gps(self) -> None:
        reading = read_citizen_media(
            CitizenMedia("image", "camara.jpg", b"\xff\xd8\xff\xd9", 8.95, -79.7)
        )
        self.assertIn("chino de vista alegre", reading.text)
        self.assertFalse(reading.outside)

    def test_photo_outside_panama_oeste_is_out_of_scope(self) -> None:
        reading = read_citizen_media(CitizenMedia("image", "lejos.jpg", jpeg_with_gps(7.1, -79.5)))
        self.assertTrue(reading.outside)
        self.assertEqual(reading.text, "")

    def test_audio_is_not_invented_when_there_is_no_transcription_engine(self) -> None:
        reading = read_citizen_media(CitizenMedia("audio", "nota.wav", b"RIFFxxxxWAVE"))
        self.assertEqual(reading.text, "")
        self.assertFalse(reading.outside)
        self.assertTrue(any("No se inventó" in note for note in reading.uncertainties))

    def test_photo_is_ingested_as_a_place_without_invented_counts(self) -> None:
        from datetime import UTC, datetime

        from src.contracts import ProvenanceTag, ReportInput, SectorId
        from src.ingestion.agent import ingest_report
        from src.ingestion.media import remember_media

        report = ReportInput(
            report_id="foto-1",
            raw_text="",
            source_channel="panel",
            provenance=ProvenanceTag.SYNTHETIC_DEMO,
            timestamp=datetime(2026, 10, 16, 12, 0, tzinfo=UTC),
        )
        remember_media(report.report_id, CitizenMedia("image", "grifo.jpg", jpeg_with_gps(8.95, -79.7)))
        result = ingest_report(report)
        self.assertEqual(result.extracted.candidate_sector_id, SectorId.ARRAIJAN_VISTA_ALEGRE)
        self.assertIsNone(result.extracted.duration_hours)
        self.assertIsNone(result.extracted.affected_count)
        self.assertTrue(result.extracted.requiere_revision)
        self.assertTrue(any(trace.action == "read_image" for trace in result.traces))


if __name__ == "__main__":
    unittest.main()
