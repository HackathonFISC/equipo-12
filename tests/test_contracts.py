"""Shared pydantic contracts and closed enumerations."""

from __future__ import annotations

import typing
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from src.contracts import (
    Assessment,
    Assignment,
    DecisionAction,
    EvidenceType,
    ExecutionResult,
    FactorBreakdown,
    FactorNote,
    GeoPrecision,
    GuardrailStatus,
    HumanDecision,
    NormalizedIncidentCluster,
    PlanDraft,
    PriorityResult,
    ProvenanceTag,
    ReportExtracted,
    ReportInput,
    ReporteExtraido,
    SectorId,
    TraceEntry,
    VulnerabilityFlag,
)

_ENUMS = (
    ProvenanceTag,
    SectorId,
    EvidenceType,
    VulnerabilityFlag,
    GuardrailStatus,
    DecisionAction,
    GeoPrecision,
)

_EXPECTED_MEMBERS = {
    ProvenanceTag: {"OFFICIAL_SOURCE", "SYNTHETIC_DEMO", "ASSUMPTION"},
    SectorId: {
        "ARRAIJAN_VISTA_ALEGRE",
        "ARRAIJAN_BURUNGA",
        "ARRAIJAN_NUEVO_CHORRILLO",
        "ARRAIJAN_VACAMONTE",
        "ARRAIJAN_CERRO_SILVESTRE",
        "ARRAIJAN_CABECERA",
        "CHORRERA_BARRIO_COLON",
        "CHORRERA_BARRIO_BALBOA",
        "CHORRERA_GUADALUPE",
        "CHORRERA_EL_COCO",
        "CHORRERA_PUERTO_CAIMITO",
        "UNKNOWN",
    },
    EvidenceType: {
        "TEXT_REPORT",
        "INSTITUTIONAL_REPORT",
        "MULTIPLE_NEIGHBORS",
        "UNVERIFIED_CLAIM",
    },
    VulnerabilityFlag: {
        "HOSPITAL_SALUD",
        "ESCUELA",
        "ADULTOS_MAYORES",
        "INFANTES",
        "ALBERGUE",
        "NINGUNA",
    },
    GuardrailStatus: {
        "VALID",
        "NEEDS_REVIEW",
        "REJECTED_EMPTY",
        "REJECTED_MALICIOUS",
        "REJECTED_OUT_OF_SCOPE",
        "REJECTED_ABSURD",
    },
    DecisionAction: {"APPROVE", "REJECT", "CORRECT"},
    GeoPrecision: {"POINT", "SECTOR", "UNKNOWN"},
}

_MODELS = (
    ReportInput,
    ReportExtracted,
    NormalizedIncidentCluster,
    TraceEntry,
    FactorNote,
    Assessment,
    FactorBreakdown,
    PriorityResult,
    Assignment,
    PlanDraft,
    HumanDecision,
    ExecutionResult,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _annotation_includes_float(annotation: object) -> bool:
    if annotation is float:
        return True
    origin = typing.get_origin(annotation)
    if origin is None:
        return False
    return any(_annotation_includes_float(arg) for arg in typing.get_args(annotation))


def _extracted(**overrides: object) -> ReportExtracted:
    payload: dict[str, object] = {
        "report_id": "r1",
        "candidate_sector_id": SectorId.ARRAIJAN_VISTA_ALEGRE,
        "evidence_type": EvidenceType.TEXT_REPORT,
        "confidence": 0.5,
        "requiere_revision": False,
        "guardrail_status": GuardrailStatus.VALID,
        "provenance": ProvenanceTag.OFFICIAL_SOURCE,
    }
    payload.update(overrides)
    return ReportExtracted(**payload)


def _cluster(**overrides: object) -> NormalizedIncidentCluster:
    payload: dict[str, object] = {
        "cluster_id": "c1",
        "sector_id": SectorId.UNKNOWN,
        "source_report_ids": ["r1"],
        "report_count": 1,
        "requires_human_review": False,
    }
    payload.update(overrides)
    return NormalizedIncidentCluster(**payload)


class ContractTests(unittest.TestCase):
    def test_enum_member_values_equal_names_and_descriptions_fail(self) -> None:
        for enum_cls in _ENUMS:
            self.assertEqual(
                {member.name for member in enum_cls},
                _EXPECTED_MEMBERS[enum_cls],
            )
            for member in enum_cls:
                self.assertEqual(member.value, member.name)

        now = _now()
        with self.assertRaises(ValidationError):
            _extracted(candidate_sector_id="Vista Alegre")
        accepted_sector = _extracted(candidate_sector_id="ARRAIJAN_VISTA_ALEGRE")
        self.assertEqual(
            accepted_sector.candidate_sector_id,
            SectorId.ARRAIJAN_VISTA_ALEGRE,
        )

        with self.assertRaises(ValidationError):
            HumanDecision(
                plan_id="p1",
                action="approve",
                actor="operator",
                timestamp=now,
            )
        with self.assertRaises(ValidationError):
            _extracted(vulnerability_flags=["hospital"])
        with self.assertRaises(ValidationError):
            ReportInput(
                report_id="r1",
                raw_text="agua",
                source_channel="sms",
                provenance="official source",
                timestamp=now,
            )
        with self.assertRaises(ValidationError):
            _extracted(evidence_type="text report")
        with self.assertRaises(ValidationError):
            _extracted(guardrail_status="valid")

    def test_report_input_rejects_empty_report_id_and_accepts_empty_raw_text(self) -> None:
        now = _now()
        with self.assertRaises(ValidationError):
            ReportInput(
                report_id="",
                raw_text="sin agua",
                source_channel="sms",
                provenance=ProvenanceTag.SYNTHETIC_DEMO,
                timestamp=now,
            )
        accepted = ReportInput(
            report_id="r1",
            raw_text="",
            source_channel="whatsapp",
            provenance=ProvenanceTag.ASSUMPTION,
            timestamp=now,
        )
        self.assertEqual(accepted.raw_text, "")
        self.assertEqual(accepted.report_id, "r1")

    def test_report_extracted_allows_unbounded_counts(self) -> None:
        extracted = _extracted(duration_hours=-5, affected_count=10**9)
        self.assertEqual(extracted.duration_hours, -5)
        self.assertEqual(extracted.affected_count, 10**9)

    def test_confidence_is_closed_unit_interval(self) -> None:
        for illegal in (-0.01, 1.01):
            with self.assertRaises(ValidationError):
                _extracted(confidence=illegal)
        for legal in (0.0, 1.0):
            extracted = _extracted(confidence=legal)
            self.assertEqual(extracted.confidence, legal)

    def test_ninguna_must_be_the_only_vulnerability_flag(self) -> None:
        with self.assertRaises(ValidationError):
            _extracted(
                vulnerability_flags=[
                    VulnerabilityFlag.NINGUNA,
                    VulnerabilityFlag.ESCUELA,
                ]
            )
        with self.assertRaises(ValidationError):
            _cluster(
                vulnerability_flags=[
                    VulnerabilityFlag.NINGUNA,
                    VulnerabilityFlag.ESCUELA,
                ]
            )

        only_ninguna = _extracted(vulnerability_flags=[VulnerabilityFlag.NINGUNA])
        self.assertEqual(only_ninguna.vulnerability_flags, [VulnerabilityFlag.NINGUNA])

        mixed = _extracted(
            vulnerability_flags=[
                VulnerabilityFlag.ESCUELA,
                VulnerabilityFlag.HOSPITAL_SALUD,
            ]
        )
        self.assertEqual(
            mixed.vulnerability_flags,
            [VulnerabilityFlag.ESCUELA, VulnerabilityFlag.HOSPITAL_SALUD],
        )

        cluster_ninguna = _cluster(vulnerability_flags=[VulnerabilityFlag.NINGUNA])
        self.assertEqual(
            cluster_ninguna.vulnerability_flags,
            [VulnerabilityFlag.NINGUNA],
        )
        cluster_mixed = _cluster(
            vulnerability_flags=[
                VulnerabilityFlag.ESCUELA,
                VulnerabilityFlag.HOSPITAL_SALUD,
            ]
        )
        self.assertEqual(len(cluster_mixed.vulnerability_flags), 2)

    def test_reporte_extraido_is_report_extracted(self) -> None:
        self.assertIs(ReporteExtraido, ReportExtracted)

    def test_cluster_report_count_must_match_source_ids(self) -> None:
        with self.assertRaises(ValidationError):
            _cluster(source_report_ids=["r1", "r2"], report_count=1)
        matched = _cluster(source_report_ids=["r1", "r2"], report_count=2)
        self.assertEqual(matched.report_count, 2)
        self.assertEqual(matched.source_report_ids, ["r1", "r2"])

    def test_assessment_has_no_numeric_score_field(self) -> None:
        self.assertEqual(
            set(Assessment.model_fields),
            {"cluster_id", "factors", "risks", "uncertainties"},
        )
        self.assertNotIn("score", Assessment.model_fields)
        self.assertNotIn("points", Assessment.model_fields)
        for field in Assessment.model_fields.values():
            self.assertFalse(_annotation_includes_float(field.annotation))

        self.assertEqual(set(FactorNote.model_fields), {"name", "evidence", "uncertainty"})
        self.assertNotIn("score", FactorNote.model_fields)
        self.assertNotIn("points", FactorNote.model_fields)
        for field in FactorNote.model_fields.values():
            self.assertFalse(_annotation_includes_float(field.annotation))

        with self.assertRaises(ValidationError):
            Assessment(cluster_id="c1", factors=[], score=0.8)

    def test_priority_result_round_trips_formula_and_points(self) -> None:
        original = PriorityResult(
            cluster_id="c1",
            score=12.5,
            breakdown=[
                FactorBreakdown(factor="duration", points=4.5, reason="long outage"),
                FactorBreakdown(factor="population", points=8.0, reason="many affected"),
            ],
            formula_version="priority-v1",
            explanation="weighted sum",
        )
        restored = PriorityResult.model_validate(original.model_dump())
        self.assertEqual(restored.formula_version, "priority-v1")
        self.assertEqual(restored.breakdown[0].points, 4.5)
        self.assertEqual(restored.breakdown[1].points, 8.0)
        self.assertEqual(restored.score, 12.5)

    def test_human_decision_accepts_only_closed_actions(self) -> None:
        now = _now()
        with self.assertRaises(ValidationError):
            HumanDecision(
                plan_id="p1",
                action="APPROVE_NOW",
                actor="operator",
                timestamp=now,
            )
        for action in ("APPROVE", "REJECT", "CORRECT"):
            decision = HumanDecision(
                plan_id="p1",
                action=action,
                actor="operator",
                timestamp=now,
            )
            self.assertEqual(decision.action, DecisionAction(action))

    def test_extra_fields_are_forbidden(self) -> None:
        now = _now()
        for model in _MODELS:
            self.assertEqual(model.model_config.get("extra"), "forbid")

        with self.assertRaises(ValidationError):
            ReportInput(
                report_id="r1",
                raw_text="agua",
                source_channel="sms",
                provenance=ProvenanceTag.OFFICIAL_SOURCE,
                timestamp=now,
                unexpected="nope",
            )
        with self.assertRaises(ValidationError):
            TraceEntry(
                trace_id="t1",
                actor="extractor",
                action="parse",
                input_summary="raw report",
                output_summary="sector guess",
                status="ok",
                timestamp=now,
                secret="do-not-store",
            )

    def test_plan_draft_and_execution_result_construct(self) -> None:
        draft = PlanDraft(
            plan_id="p1",
            assignments=[
                Assignment(
                    vehicle_id="v1",
                    sector_id=SectorId.CHORRERA_BARRIO_COLON,
                    order=1,
                    volume_liters=500,
                )
            ],
            route_order=["v1"],
            constraints_satisfied=["capacity"],
            unserved_demand=["sector-b"],
            explanation="one truck",
        )
        self.assertEqual(draft.plan_id, "p1")
        self.assertEqual(draft.assignments[0].order, 1)
        self.assertEqual(draft.assignments[0].volume_liters, 500)
        self.assertEqual(draft.route_order, ["v1"])

        empty_draft = PlanDraft(plan_id="p2")
        self.assertEqual(empty_draft.assignments, [])
        self.assertEqual(empty_draft.route_order, [])
        self.assertEqual(empty_draft.constraints_satisfied, [])
        self.assertEqual(empty_draft.unserved_demand, [])
        self.assertEqual(empty_draft.explanation, "")

        result = ExecutionResult(
            saved=True,
            plan_id="p1",
            audit_id="a1",
            outbox_id="o1",
            detail="stored",
        )
        self.assertTrue(result.saved)
        self.assertEqual(result.plan_id, "p1")
        self.assertEqual(result.audit_id, "a1")
        self.assertEqual(result.outbox_id, "o1")
        self.assertEqual(result.detail, "stored")

        pending = ExecutionResult(saved=False, plan_id="p2", audit_id="a2")
        self.assertIsNone(pending.outbox_id)
        self.assertEqual(pending.detail, "")

        with self.assertRaises(ValidationError):
            Assignment(
                vehicle_id="v1",
                sector_id=SectorId.UNKNOWN,
                order=0,
                volume_liters=0,
            )
        with self.assertRaises(ValidationError):
            Assignment(
                vehicle_id="v1",
                sector_id=SectorId.UNKNOWN,
                order=1,
                volume_liters=-1,
            )


if __name__ == "__main__":
    unittest.main()
