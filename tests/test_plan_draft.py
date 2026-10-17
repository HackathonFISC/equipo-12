"""Planner must not add a sector-wide mention on top of a specific place."""

from __future__ import annotations

import unittest

from src.contracts import GeoPrecision, NormalizedIncidentCluster, PriorityResult, SectorId, VulnerabilityFlag
from src.planner.draft import build_plan


def _cluster(cluster_id: str, affected: int, precision: GeoPrecision) -> NormalizedIncidentCluster:
    return NormalizedIncidentCluster(
        cluster_id=cluster_id,
        sector_id=SectorId.ARRAIJAN_BURUNGA,
        source_report_ids=[cluster_id],
        report_count=1,
        max_duration_hours=12,
        estimated_affected_count=affected,
        vulnerability_flags=[VulnerabilityFlag.NINGUNA],
        requires_human_review=precision is GeoPrecision.SECTOR,
        latitude=8.97,
        longitude=-79.68,
        geo_precision=precision,
    )


def _score(cluster_id: str, score: float) -> PriorityResult:
    return PriorityResult(
        cluster_id=cluster_id,
        score=score,
        breakdown=[],
        formula_version="priority-v1",
        explanation="test",
    )


class PlanDraftTests(unittest.TestCase):
    def test_sector_mention_is_not_added_when_a_place_exists(self) -> None:
        point = _cluster("place", 100, GeoPrecision.POINT)
        broad = _cluster("sector", 500, GeoPrecision.SECTOR)
        plan = build_plan(
            [point, broad],
            [_score("place", 40), _score("sector", 80)],
        )
        self.assertEqual(len(plan.assignments), 1)
        self.assertEqual(plan.assignments[0].volume_liters, 1500)
        self.assertNotIn(SectorId.ARRAIJAN_BURUNGA.value, plan.unserved_demand)
        self.assertIn("Burunga", plan.explanation)
        self.assertIn("no se sumó", plan.explanation)

    def test_sector_mention_is_routed_when_it_is_the_only_report(self) -> None:
        broad = _cluster("sector", 40, GeoPrecision.SECTOR)
        plan = build_plan([broad], [_score("sector", 20)])
        self.assertEqual(len(plan.assignments), 1)
        self.assertEqual(plan.assignments[0].volume_liters, 600)


if __name__ == "__main__":
    unittest.main()
