"""Deterministic cistern assignment with capacity and shift limits."""

from __future__ import annotations

import unittest

from src.contracts import NormalizedIncidentCluster, PriorityResult, SectorId, VulnerabilityFlag
from src.planner.solver import Truck, solve


def _cluster(
    cluster_id: str,
    sector: SectorId,
    hours: int,
    affected: int,
    latitude: float,
    longitude: float,
) -> NormalizedIncidentCluster:
    return NormalizedIncidentCluster(
        cluster_id=cluster_id,
        sector_id=sector,
        source_report_ids=[cluster_id],
        report_count=1,
        max_duration_hours=hours,
        estimated_affected_count=affected,
        vulnerability_flags=[VulnerabilityFlag.NINGUNA],
        requires_human_review=False,
        latitude=latitude,
        longitude=longitude,
        geo_precision="POINT",
    )


def _score(cluster_id: str, score: float) -> PriorityResult:
    return PriorityResult(
        cluster_id=cluster_id,
        score=score,
        breakdown=[],
        formula_version="priority-v1",
        explanation="test",
    )


class SolverTests(unittest.TestCase):
    def test_higher_score_is_served_before_a_later_stop(self) -> None:
        near = _cluster("near", SectorId.CHORRERA_BARRIO_COLON, 10, 100, 8.881, -79.782)
        far = _cluster("far", SectorId.CHORRERA_EL_COCO, 48, 100, 8.87, -79.85)
        fleet = [Truck("cisterna-1", capacity_liters=5000, shift_minutes=480)]
        result = solve([far, near], [_score("far", 80), _score("near", 10)], fleet=fleet)
        self.assertEqual(result.assignments[0].sector_id, SectorId.CHORRERA_EL_COCO)
        self.assertEqual(result.assignments[0].order, 1)
        self.assertEqual(result.assignments[1].sector_id, SectorId.CHORRERA_BARRIO_COLON)
        self.assertEqual(result.unserved, [])

    def test_demand_above_every_truck_is_unserved(self) -> None:
        huge = _cluster("huge", SectorId.ARRAIJAN_BURUNGA, 80, 10000, 8.97, -79.68)
        fleet = [Truck("cisterna-1", capacity_liters=1000, shift_minutes=480)]
        result = solve([huge], [_score("huge", 90)], fleet=fleet)
        self.assertEqual(result.assignments, [])
        self.assertEqual(result.unserved, [SectorId.ARRAIJAN_BURUNGA.value])

    def test_second_truck_takes_what_the_first_cannot_carry(self) -> None:
        first = _cluster("a", SectorId.ARRAIJAN_VISTA_ALEGRE, 40, 400, 8.95, -79.70)
        second = _cluster("b", SectorId.CHORRERA_GUADALUPE, 20, 400, 8.89, -79.82)
        fleet = [
            Truck("cisterna-2", capacity_liters=7000, shift_minutes=480),
            Truck("cisterna-1", capacity_liters=7000, shift_minutes=480),
        ]
        result = solve(
            [first, second],
            [_score("a", 70), _score("b", 40)],
            fleet=fleet,
        )
        by_sector = {item.sector_id: item.vehicle_id for item in result.assignments}
        self.assertEqual(len(result.assignments), 2)
        self.assertNotEqual(
            by_sector[SectorId.ARRAIJAN_VISTA_ALEGRE],
            by_sector[SectorId.CHORRERA_GUADALUPE],
        )
        self.assertEqual(result.unserved, [])

    def test_tight_shift_leaves_a_far_stop_unserved(self) -> None:
        far = _cluster("far", SectorId.CHORRERA_EL_COCO, 2, 10, 8.87, -79.85)
        fleet = [Truck("cisterna-1", capacity_liters=5000, shift_minutes=30)]
        result = solve([far], [_score("far", 10)], fleet=fleet)
        self.assertEqual(result.assignments, [])
        self.assertEqual(result.unserved, [SectorId.CHORRERA_EL_COCO.value])

    def test_same_input_is_deterministic(self) -> None:
        cluster = _cluster("a", SectorId.ARRAIJAN_CABECERA, 12, 40, 8.938, -79.65)
        fleet = [Truck("cisterna-1", capacity_liters=5000, shift_minutes=480)]
        scores = [_score("a", 20)]
        first = solve([cluster], scores, fleet=fleet)
        second = solve([cluster], scores, fleet=fleet)
        self.assertEqual(first.assignments, second.assignments)
        self.assertEqual(first.route_order, second.route_order)
        self.assertIn("capacity", first.constraints)
        self.assertIn("shift-window", first.constraints)


if __name__ == "__main__":
    unittest.main()
