"""Deterministic priority scoring: exact math, caps, ordering, guardrails."""

from __future__ import annotations

import unittest

from src.contracts import NormalizedIncidentCluster, SectorId, VulnerabilityFlag
from src.priority import FORMULA_VERSION, rank_clusters, score_cluster


def _cluster(
    cluster_id: str = "c1",
    sector_id: SectorId = SectorId.ARRAIJAN_VISTA_ALEGRE,
    hours: int | None = 84,
    affected: int | None = 25000,
    flags: list[VulnerabilityFlag] | None = None,
    report_count: int = 1,
) -> NormalizedIncidentCluster:
    if flags is None:
        flags = [VulnerabilityFlag.ESCUELA]
    return NormalizedIncidentCluster(
        cluster_id=cluster_id,
        sector_id=sector_id,
        source_report_ids=[f"r{i}" for i in range(report_count)],
        report_count=report_count,
        max_duration_hours=hours,
        estimated_affected_count=affected,
        vulnerability_flags=flags,
        requires_human_review=False,
    )


class PriorityScoringTests(unittest.TestCase):
    def test_exact_math_mid_case(self) -> None:
        result = score_cluster(_cluster())
        self.assertEqual(result.cluster_id, "c1")
        self.assertEqual(result.formula_version, FORMULA_VERSION)
        self.assertEqual(result.score, 47.0)
        by_factor = {item.factor: item for item in result.breakdown}
        self.assertEqual(by_factor["duration"].points, 20.0)
        self.assertEqual(by_factor["affected"].points, 15.0)
        self.assertEqual(by_factor["vulnerability"].points, 12.0)

    def test_exact_math_maxed_case(self) -> None:
        result = score_cluster(
            _cluster(
                hours=168,
                affected=50000,
                flags=[VulnerabilityFlag.HOSPITAL_SALUD],
            )
        )
        self.assertEqual(result.score, 90.0)

    def test_caps_apply(self) -> None:
        result = score_cluster(
            _cluster(
                hours=300,
                affected=10**9,
                flags=[
                    VulnerabilityFlag.HOSPITAL_SALUD,
                    VulnerabilityFlag.ESCUELA,
                    VulnerabilityFlag.ADULTOS_MAYORES,
                    VulnerabilityFlag.INFANTES,
                    VulnerabilityFlag.ALBERGUE,
                ],
            )
        )
        by_factor = {item.factor: item for item in result.breakdown}
        self.assertEqual(by_factor["duration"].points, 40.0)
        self.assertEqual(by_factor["affected"].points, 30.0)
        self.assertEqual(by_factor["vulnerability"].points, 30.0)
        self.assertEqual(result.score, 100.0)

    def test_rounding_is_stable(self) -> None:
        result = score_cluster(_cluster(hours=10, affected=0, flags=[]))
        by_factor = {item.factor: item for item in result.breakdown}
        self.assertEqual(by_factor["duration"].points, 2.38)

    def test_missing_data_scores_zero_with_reasons(self) -> None:
        result = score_cluster(_cluster(hours=None, affected=None, flags=[]))
        self.assertEqual(result.score, 0.0)
        self.assertEqual(len(result.breakdown), 3)
        for item in result.breakdown:
            self.assertTrue(item.reason)

    def test_negative_hours_raise(self) -> None:
        with self.assertRaises(ValueError):
            score_cluster(_cluster(hours=-1))

    def test_negative_affected_raise(self) -> None:
        with self.assertRaises(ValueError):
            score_cluster(_cluster(affected=-5))

    def test_breakdown_sums_to_score(self) -> None:
        for cluster in (
            _cluster(),
            _cluster(hours=200, affected=99999, flags=[VulnerabilityFlag.INFANTES]),
            _cluster(hours=None, affected=None, flags=[VulnerabilityFlag.NINGUNA]),
        ):
            result = score_cluster(cluster)
            self.assertAlmostEqual(
                sum(item.points for item in result.breakdown), result.score, places=9
            )

    def test_complaint_volume_does_not_change_score(self) -> None:
        single = score_cluster(_cluster(cluster_id="c1", report_count=1))
        flooded = score_cluster(_cluster(cluster_id="c1", report_count=50))
        self.assertEqual(single.score, flooded.score)

    def test_rank_orders_highest_first(self) -> None:
        low = _cluster(cluster_id="c-low", hours=5, affected=100, flags=[])
        high = _cluster(
            cluster_id="c-high",
            hours=168,
            affected=50000,
            flags=[VulnerabilityFlag.HOSPITAL_SALUD],
        )
        ranked = rank_clusters([low, high])
        self.assertEqual([item.cluster_id for item in ranked], ["c-high", "c-low"])

    def test_rank_breaks_ties_by_cluster_id(self) -> None:
        first = _cluster(cluster_id="c-a")
        second = _cluster(cluster_id="c-b")
        ranked = rank_clusters([second, first])
        self.assertEqual([item.cluster_id for item in ranked], ["c-a", "c-b"])

    def test_ninguna_scores_zero_vulnerability(self) -> None:
        result = score_cluster(
            _cluster(hours=0, affected=0, flags=[VulnerabilityFlag.NINGUNA])
        )
        by_factor = {item.factor: item for item in result.breakdown}
        self.assertEqual(by_factor["vulnerability"].points, 0.0)
        self.assertEqual(result.score, 0.0)

    def test_unknown_sector_scores_deterministically(self) -> None:
        first = score_cluster(_cluster(sector_id=SectorId.UNKNOWN))
        second = score_cluster(_cluster(sector_id=SectorId.UNKNOWN))
        self.assertEqual(first.score, second.score)

    def test_explanation_names_formula_and_total(self) -> None:
        result = score_cluster(_cluster())
        self.assertIn(FORMULA_VERSION, result.explanation)
        self.assertIn("47.0", result.explanation)


if __name__ == "__main__":
    unittest.main()
