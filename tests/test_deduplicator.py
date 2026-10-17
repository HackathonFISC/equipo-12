"""Deterministic grouping of extracted reports."""

from __future__ import annotations

import unittest

from src.contracts import (
    EvidenceType,
    GeoPrecision,
    GuardrailStatus,
    ProvenanceTag,
    ReportExtracted,
    SectorId,
    VulnerabilityFlag,
)
from src.ingestion.deduplicator import deduplicate_reports


def _report(report_id: str, **overrides: object) -> ReportExtracted:
    payload: dict[str, object] = {
        "report_id": report_id,
        "candidate_sector_id": SectorId.ARRAIJAN_VISTA_ALEGRE,
        "evidence_type": EvidenceType.TEXT_REPORT,
        "confidence": 0.9,
        "requiere_revision": False,
        "guardrail_status": GuardrailStatus.VALID,
        "provenance": ProvenanceTag.SYNTHETIC_DEMO,
        "duration_hours": 24,
        "affected_count": 10,
        "vulnerability_flags": [VulnerabilityFlag.NINGUNA],
    }
    payload.update(overrides)
    return ReportExtracted(**payload)


class DeduplicatorTests(unittest.TestCase):
    def test_same_sector_becomes_one_cluster_and_keeps_source_ids(self) -> None:
        clusters = deduplicate_reports(
            [
                _report("SYN-002", duration_hours=48, affected_count=30),
                _report(
                    "SYN-001",
                    duration_hours=24,
                    affected_count=10,
                    provenance=ProvenanceTag.ASSUMPTION,
                    evidence_type=EvidenceType.MULTIPLE_NEIGHBORS,
                    vulnerability_flags=[VulnerabilityFlag.ESCUELA],
                    requiere_revision=True,
                    uncertainties=["desde ayer counted as 24 hours"],
                ),
            ]
        )
        self.assertEqual(len(clusters), 1)
        cluster = clusters[0]
        self.assertEqual(cluster.sector_id, SectorId.ARRAIJAN_VISTA_ALEGRE)
        self.assertEqual(cluster.source_report_ids, ["SYN-002", "SYN-001"])
        self.assertEqual(cluster.report_count, 2)
        self.assertEqual(cluster.max_duration_hours, 48)
        self.assertEqual(cluster.estimated_affected_count, 30)
        self.assertEqual(cluster.vulnerability_flags, [VulnerabilityFlag.ESCUELA])
        self.assertEqual(
            cluster.evidence_types,
            [EvidenceType.TEXT_REPORT, EvidenceType.MULTIPLE_NEIGHBORS],
        )
        self.assertEqual(
            cluster.provenance_tags,
            [ProvenanceTag.SYNTHETIC_DEMO, ProvenanceTag.ASSUMPTION],
        )
        self.assertTrue(cluster.requires_human_review)
        self.assertIn("desde ayer counted as 24 hours", cluster.uncertainties)

    def test_different_sectors_stay_separate_and_rejections_are_excluded(self) -> None:
        clusters = deduplicate_reports(
            [
                _report("A", candidate_sector_id=SectorId.ARRAIJAN_BURUNGA),
                _report("B", candidate_sector_id=SectorId.CHORRERA_EL_COCO),
                _report(
                    "BAD",
                    guardrail_status=GuardrailStatus.REJECTED_MALICIOUS,
                    requiere_revision=True,
                ),
            ]
        )
        self.assertEqual(
            [cluster.sector_id for cluster in clusters],
            [SectorId.ARRAIJAN_BURUNGA, SectorId.CHORRERA_EL_COCO],
        )
        self.assertEqual(clusters[0].source_report_ids, ["A"])
        self.assertFalse(any("BAD" in cluster.source_report_ids for cluster in clusters))

    def test_far_landmarks_in_one_sector_stay_apart(self) -> None:
        clusters = deduplicate_reports(
            [
                _report(
                    "CHINO",
                    raw_location_mention="por el chino de Vista Alegre",
                ),
                _report(
                    "XTRA",
                    raw_location_mention="Xtra de Vista Alegre",
                ),
            ]
        )
        groups = {frozenset(cluster.source_report_ids) for cluster in clusters}
        self.assertEqual(groups, {frozenset({"CHINO"}), frozenset({"XTRA"})})
        self.assertTrue(all(cluster.geo_precision is GeoPrecision.POINT for cluster in clusters))

    def test_nearby_landmarks_in_one_sector_merge(self) -> None:
        clusters = deduplicate_reports(
            [
                _report("LOMA", raw_location_mention="Loma Cova"),
                _report("BURUNGA", raw_location_mention="Burunga"),
            ]
        )
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].source_report_ids, ["LOMA", "BURUNGA"])
        self.assertEqual(clusters[0].sector_id, SectorId.ARRAIJAN_BURUNGA)
        self.assertIn("LOMA_COVA", clusters[0].place_id)
        self.assertIn("BURUNGA_CENTRO", clusters[0].place_id)
        self.assertTrue(clusters[0].requires_human_review)


if __name__ == "__main__":
    unittest.main()
