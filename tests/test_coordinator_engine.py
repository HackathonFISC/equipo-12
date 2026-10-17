"""Deterministic stub plan engine."""

from __future__ import annotations

import random
import typing
import unittest

from pydantic import BaseModel

from src.contracts import (
    Assignment,
    FactorBreakdown,
    NormalizedIncidentCluster,
    PlanDraft,
    PriorityResult,
    ProvenanceTag,
    SectorId,
)
from src.contracts import DecisionAction
from src.coordinator.engine import demo_engine
from src.coordinator.state import TRANSITIONS, PlanState


def _cluster(**overrides: object) -> NormalizedIncidentCluster:
    payload: dict[str, object] = {
        "cluster_id": "c1",
        "sector_id": SectorId.ARRAIJAN_VISTA_ALEGRE,
        "source_report_ids": ["r1"],
        "report_count": 1,
        "requires_human_review": False,
        "provenance_tags": [ProvenanceTag.SYNTHETIC_DEMO],
    }
    payload.update(overrides)
    return NormalizedIncidentCluster(**payload)


def _float_field_names(model_cls: type[BaseModel]) -> set[str]:
    names: set[str] = set()
    for name, field in model_cls.model_fields.items():
        annotation = field.annotation
        if annotation is float:
            names.add(name)
            continue
        origin = typing.get_origin(annotation)
        if origin is typing.Union:
            args = typing.get_args(annotation)
            if float in args:
                names.add(name)
    return names


class DemoEngineTests(unittest.TestCase):
    def test_transition_map_legal_edges(self) -> None:
        human = {
            (PlanState.BORRADOR, None, False): PlanState.PENDIENTE,
            (PlanState.PENDIENTE, DecisionAction.APPROVE, False): PlanState.APROBADO,
            (PlanState.PENDIENTE, DecisionAction.REJECT, False): PlanState.RECHAZADO,
            (PlanState.PENDIENTE, DecisionAction.CORRECT, False): PlanState.BORRADOR,
        }
        failure = {
            (PlanState.BORRADOR, None, True): PlanState.ERROR_PARCIAL,
            (PlanState.PENDIENTE, None, True): PlanState.ERROR_PARCIAL,
        }
        self.assertEqual(human | failure, dict(TRANSITIONS))

    def test_stub_engine_order_scoring_and_assignments(self) -> None:
        clusters = [
            _cluster(
                cluster_id="tie-b",
                max_duration_hours=12,
                estimated_affected_count=5,
                sector_id=SectorId.CHORRERA_BARRIO_BALBOA,
            ),
            _cluster(
                cluster_id="high",
                max_duration_hours=30,
                estimated_affected_count=20,
                sector_id=SectorId.ARRAIJAN_BURUNGA,
            ),
            _cluster(
                cluster_id="tie-a",
                max_duration_hours=12,
                estimated_affected_count=3,
                sector_id=SectorId.ARRAIJAN_CABECERA,
            ),
        ]
        out = demo_engine(clusters)
        by_id = {p.cluster_id: p for p in out.priorities}
        self.assertEqual(by_id["high"].score, 50.0)
        self.assertEqual(by_id["tie-a"].score, 15.0)
        self.assertEqual(by_id["tie-b"].score, 17.0)

        expected_route = [
            SectorId.ARRAIJAN_BURUNGA.value,
            SectorId.ARRAIJAN_CABECERA.value,
            SectorId.CHORRERA_BARRIO_BALBOA.value,
        ]
        self.assertEqual(out.plan.route_order, expected_route)
        self.assertEqual(len(out.plan.assignments), 3)
        for idx, assignment in enumerate(out.plan.assignments, start=1):
            self.assertEqual(assignment.vehicle_id, "cisterna-1")
            self.assertEqual(assignment.order, idx)
        self.assertEqual(out.plan.assignments[0].volume_liters, 20)
        self.assertEqual(out.plan.assignments[1].volume_liters, 3)
        self.assertEqual(out.plan.assignments[2].volume_liters, 5)
        self.assertEqual(
            [a.sector_id.value for a in out.plan.assignments],
            expected_route,
        )

    def test_determinism_same_input(self) -> None:
        clusters = [
            _cluster(cluster_id="a", max_duration_hours=10, sector_id=SectorId.ARRAIJAN_BURUNGA),
            _cluster(
                cluster_id="b",
                max_duration_hours=20,
                sector_id=SectorId.CHORRERA_BARRIO_COLON,
            ),
        ]
        out_a = demo_engine(clusters)
        out_b = demo_engine(clusters)
        self.assertEqual(
            [p.model_dump() for p in out_a.priorities],
            [p.model_dump() for p in out_b.priorities],
        )
        self.assertEqual(out_a.plan.model_dump(), out_b.plan.model_dump())

    def test_shuffle_does_not_change_order_when_durations_differ(self) -> None:
        base = [
            _cluster(
                cluster_id="low",
                max_duration_hours=5,
                sector_id=SectorId.ARRAIJAN_VACAMONTE,
            ),
            _cluster(
                cluster_id="high",
                max_duration_hours=48,
                sector_id=SectorId.ARRAIJAN_BURUNGA,
            ),
            _cluster(
                cluster_id="mid",
                max_duration_hours=24,
                sector_id=SectorId.CHORRERA_EL_COCO,
            ),
        ]
        ordered = demo_engine(base)
        shuffled = list(base)
        random.seed(0)
        random.shuffle(shuffled)
        from_shuffle = demo_engine(shuffled)
        self.assertEqual(
            ordered.plan.route_order,
            from_shuffle.plan.route_order,
        )
        self.assertEqual(
            [a.sector_id for a in ordered.plan.assignments],
            [a.sector_id for a in from_shuffle.plan.assignments],
        )

    def test_unknown_only_in_unserved_demand(self) -> None:
        clusters = [
            _cluster(cluster_id="known", sector_id=SectorId.ARRAIJAN_CABECERA),
            _cluster(cluster_id="unk1", sector_id=SectorId.UNKNOWN),
            _cluster(cluster_id="unk2", sector_id=SectorId.UNKNOWN),
        ]
        out = demo_engine(clusters)
        self.assertEqual(out.plan.unserved_demand, ["UNKNOWN", "UNKNOWN"])
        self.assertEqual(len(out.priorities), 1)
        self.assertEqual(out.priorities[0].cluster_id, "known")
        assigned_sectors = {a.sector_id for a in out.plan.assignments}
        self.assertNotIn(SectorId.UNKNOWN, assigned_sectors)

    def test_empty_input(self) -> None:
        out = demo_engine([])
        self.assertEqual(out.priorities, [])
        self.assertEqual(out.plan.assignments, [])
        self.assertEqual(out.plan.unserved_demand, [])
        self.assertEqual(out.plan.route_order, [])
        PlanDraft.model_validate(out.plan.model_dump())

    def test_stub_metadata_and_formula(self) -> None:
        out = demo_engine([_cluster(max_duration_hours=3, estimated_affected_count=10)])
        self.assertEqual(out.priorities[0].formula_version, "STUB-v0")
        for text in (out.priorities[0].explanation, out.plan.explanation):
            self.assertIn("STUB", text)
            self.assertIn("SYNTHETIC_DEMO", text)
        self.assertIn("prototype", out.priorities[0].explanation.lower())
        self.assertIn("idaan", out.priorities[0].explanation.lower())

    def test_no_floats_on_plan_or_assignment(self) -> None:
        out = demo_engine(
            [
                _cluster(
                    cluster_id="x",
                    max_duration_hours=12,
                    estimated_affected_count=7,
                    sector_id=SectorId.CHORRERA_GUADALUPE,
                )
            ]
        )
        self.assertEqual(_float_field_names(PlanDraft), set())
        self.assertEqual(_float_field_names(Assignment), set())
        self.assertIn("score", _float_field_names(PriorityResult))
        self.assertIn("points", _float_field_names(FactorBreakdown))

    def test_plan_id_stable_for_same_clusters(self) -> None:
        clusters = [
            _cluster(cluster_id="a", sector_id=SectorId.ARRAIJAN_NUEVO_CHORRILLO, max_duration_hours=1),
            _cluster(cluster_id="b", sector_id=SectorId.ARRAIJAN_CERRO_SILVESTRE, max_duration_hours=2),
        ]
        id_a = demo_engine(clusters).plan.plan_id
        id_b = demo_engine(list(reversed(clusters))).plan.plan_id
        self.assertEqual(id_a, id_b)


if __name__ == "__main__":
    unittest.main()
