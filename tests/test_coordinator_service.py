"""CoordinatorService end-to-end flow with temp SQLite store."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from src.contracts import DecisionAction, HumanDecision, SectorId
from src.coordinator.service import CoordinatorService
from src.coordinator.state import PlanState
from src.coordinator.store import ApprovalStore

_SAMPLE_TEXTS = [
    "48 horas sin agua y 15 personas por el chino de Vista Alegre",
    "Xtra de Vista Alegre: tres dias sin agua y 20 familias",
    "36 horas sin agua en Burunga Loma Cova, 8 personas",
    "72 horas sin agua en Ciudad Imaginaria XYZ",
    "",
]


def _decision(
    plan_id: str,
    action: DecisionAction,
    *,
    comment: str = "",
) -> HumanDecision:
    return HumanDecision(
        plan_id=plan_id,
        action=action,
        actor="coordinator",
        comment=comment,
        timestamp=datetime(2026, 10, 16, 14, 0, tzinfo=UTC),
    )


def _temp_store() -> tuple[ApprovalStore, Path]:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = Path(tmp.name)
    return ApprovalStore(path), path


class CoordinatorServiceTests(unittest.TestCase):
    def _outbox_count(self, db_path: Path) -> int:
        with sqlite3.connect(db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    def _plan_row(self, db_path: Path, plan_id: str) -> tuple[str, int]:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT state, revision FROM plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
            assert row is not None
            return str(row[0]), int(row[1])

    def test_fixture_flow_dedup_unknown_and_no_outbox_until_approve(self) -> None:
        store, db_path = _temp_store()
        try:
            svc = CoordinatorService(store)
            ingested = svc.ingest_texts(_SAMPLE_TEXTS)
            self.assertGreater(len(svc.traces), 0)
            unknown_report = ingested[3].extracted
            self.assertEqual(unknown_report.candidate_sector_id, SectorId.UNKNOWN)
            self.assertTrue(unknown_report.requiere_revision)
            self.assertEqual(self._outbox_count(db_path), 0)

            clusters = svc.consolidate()
            vista = next(
                c for c in clusters if c.sector_id == SectorId.ARRAIJAN_VISTA_ALEGRE
            )
            self.assertEqual(vista.report_count, 2)
            self.assertEqual(vista.estimated_affected_count, 80)
            unknown = next(c for c in clusters if c.sector_id == SectorId.UNKNOWN)
            self.assertTrue(unknown.requires_human_review)

            output = svc.prepare_draft()
            plan_id = output.plan.plan_id
            self.assertEqual(len(output.plan.assignments), 2)
            self.assertIn("UNKNOWN", output.plan.unserved_demand)
            self.assertEqual(self._outbox_count(db_path), 0)

            svc.submit_for_review()
            state, revision = self._plan_row(db_path, plan_id)
            self.assertEqual(state, PlanState.PENDIENTE.value)
            self.assertEqual(revision, 0)
            self.assertEqual(self._outbox_count(db_path), 0)

            svc.decide(_decision(plan_id, DecisionAction.REJECT, comment="not today"))
            self.assertEqual(self._outbox_count(db_path), 0)
        finally:
            db_path.unlink(missing_ok=True)

    def test_approve_enqueues_simulated_outbox(self) -> None:
        store, db_path = _temp_store()
        try:
            svc = CoordinatorService(store)
            svc.ingest_texts(_SAMPLE_TEXTS)
            output = svc.prepare_draft()
            plan_id = output.plan.plan_id
            svc.submit_for_review()
            result = svc.decide(_decision(plan_id, DecisionAction.APPROVE))
            self.assertTrue(result.saved)
            self.assertIsNotNone(result.outbox_id)
            self.assertGreaterEqual(self._outbox_count(db_path), 1)
            with sqlite3.connect(db_path) as conn:
                channels = conn.execute(
                    "SELECT channel FROM outbox WHERE plan_id = ?",
                    (plan_id,),
                ).fetchall()
            self.assertTrue(all(row[0] == "SIMULATED" for row in channels))
        finally:
            db_path.unlink(missing_ok=True)

    def test_correct_empty_comment_raises_without_outbox(self) -> None:
        store, db_path = _temp_store()
        try:
            svc = CoordinatorService(store)
            svc.ingest_texts(_SAMPLE_TEXTS[:3])
            output = svc.prepare_draft()
            plan_id = output.plan.plan_id
            svc.submit_for_review()
            with self.assertRaises(ValueError):
                svc.decide(_decision(plan_id, DecisionAction.CORRECT, comment="   "))
            self.assertEqual(self._outbox_count(db_path), 0)
            with sqlite3.connect(db_path) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0],
                    0,
                )
        finally:
            db_path.unlink(missing_ok=True)

    def test_correct_with_comment_returns_to_borrador(self) -> None:
        store, db_path = _temp_store()
        try:
            svc = CoordinatorService(store)
            svc.ingest_texts(_SAMPLE_TEXTS[:3])
            output = svc.prepare_draft()
            plan_id = output.plan.plan_id
            svc.submit_for_review()
            svc.decide(
                _decision(plan_id, DecisionAction.CORRECT, comment="adjust Burunga volume")
            )
            state, revision = self._plan_row(db_path, plan_id)
            self.assertEqual(state, PlanState.BORRADOR.value)
            self.assertEqual(revision, 1)
            self.assertEqual(self._outbox_count(db_path), 0)
        finally:
            db_path.unlink(missing_ok=True)

    def test_decide_unknown_plan_id_raises(self) -> None:
        store, db_path = _temp_store()
        try:
            svc = CoordinatorService(store)
            svc.ingest_texts(_SAMPLE_TEXTS[:2])
            svc.prepare_draft()
            svc.submit_for_review()
            with self.assertRaises(ValueError):
                svc.decide(_decision("never-prepared", DecisionAction.APPROVE))
            self.assertEqual(self._outbox_count(db_path), 0)
        finally:
            db_path.unlink(missing_ok=True)

    def test_prepare_draft_twice_raises(self) -> None:
        store, db_path = _temp_store()
        try:
            svc = CoordinatorService(store)
            svc.ingest_texts(_SAMPLE_TEXTS[:2])
            svc.prepare_draft()
            with self.assertRaises(ValueError):
                svc.prepare_draft()
        finally:
            db_path.unlink(missing_ok=True)

    def test_submit_for_review_store_transitions_borrador(self) -> None:
        store, db_path = _temp_store()
        try:
            svc = CoordinatorService(store)
            svc.ingest_texts(_SAMPLE_TEXTS[:2])
            output = svc.prepare_draft()
            plan_id = output.plan.plan_id
            store.submit_for_review(plan_id)
            state, _ = self._plan_row(db_path, plan_id)
            self.assertEqual(state, PlanState.PENDIENTE.value)
            with self.assertRaises(ValueError):
                store.submit_for_review(plan_id)
        finally:
            db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
