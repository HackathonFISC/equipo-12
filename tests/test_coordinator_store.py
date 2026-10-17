"""Transactional approval store (SQLite)."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import UTC, datetime
from pathlib import Path

from src.contracts import DecisionAction, HumanDecision
from src.coordinator.state import PlanState
from src.coordinator.store import ApprovalStore


def _sample_payload(
    plan_id: str = "plan-1",
    sectors: list[str] | None = None,
    *,
    assignments: list[dict[str, object]] | None = None,
) -> str:
    if assignments is None:
        sectors = sectors or ["ARRAIJAN_VISTA_ALEGRE"]
        assignments = [
            {
                "vehicle_id": "cisterna-1",
                "sector_id": s,
                "order": i + 1,
                "volume_liters": 1000,
            }
            for i, s in enumerate(sectors)
        ]
        route_order = sectors
    else:
        route_order = [
            str(a["sector_id"]) for a in assignments if "sector_id" in a
        ]
    return json.dumps(
        {
            "plan_id": plan_id,
            "assignments": assignments,
            "route_order": route_order,
            "constraints_satisfied": [],
            "unserved_demand": [],
            "explanation": "test",
        }
    )


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
        timestamp=datetime(2026, 10, 16, 12, 0, tzinfo=UTC),
    )


class ApprovalStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db_path = Path(self._tmp.name)
        self.store = ApprovalStore(self.db_path)

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def test_approve_persists_dispatch_and_audit(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        result = self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.APPROVE),
            payload,
        )
        self.assertTrue(result.saved)
        self.assertIsNotNone(result.outbox_id)
        self.assertTrue(result.audit_id)

        with self._conn() as conn:
            state = conn.execute("SELECT state FROM plans WHERE id = ?", ("plan-1",)).fetchone()[0]
            self.assertEqual(state, PlanState.APROBADO.value)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM decisions WHERE plan_id = ?", ("plan-1",)).fetchone()[
                    0
                ],
                1,
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 1)
            rows = conn.execute(
                "SELECT channel, sent_at FROM outbox WHERE plan_id = ?",
                ("plan-1",),
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "SIMULATED")
            self.assertIsNone(rows[0][1])

    def test_reject_after_approve_cancels_simulated_notices(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.APPROVE),
            payload,
        )
        result = self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.REJECT),
            payload,
        )
        self.assertFalse(result.saved)
        self.assertIn("cancelados", result.detail)
        with self._conn() as conn:
            state = conn.execute("SELECT state FROM plans WHERE id = 'plan-1'").fetchone()
            statuses = conn.execute(
                "SELECT status FROM outbox WHERE plan_id = 'plan-1'"
            ).fetchall()
        assert state is not None
        self.assertEqual(state[0], PlanState.RECHAZADO.value)
        self.assertTrue(statuses)
        self.assertTrue(all(row[0] == "CANCELLED" for row in statuses))

    def test_reject_no_outbox(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        result = self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.REJECT),
            payload,
        )
        self.assertFalse(result.saved)
        self.assertIsNone(result.outbox_id)
        self.assertTrue(result.audit_id)

        with self._conn() as conn:
            self.assertEqual(
                conn.execute("SELECT state FROM plans WHERE id = ?", ("plan-1",)).fetchone()[0],
                PlanState.RECHAZADO.value,
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 1)

    def test_correct_increments_revision(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        updated = _sample_payload(sectors=["CHORRERA_EL_COCO"])
        result = self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.CORRECT),
            updated,
        )
        self.assertFalse(result.saved)
        self.assertIsNone(result.outbox_id)

        with self._conn() as conn:
            row = conn.execute(
                "SELECT state, revision, payload_json FROM plans WHERE id = ?",
                ("plan-1",),
            ).fetchone()
            self.assertEqual(row[0], PlanState.BORRADOR.value)
            self.assertEqual(row[1], 1)
            self.assertIn("CHORRERA_EL_COCO", row[2])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 0)

    def test_double_approve_does_not_duplicate_outbox(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        first = self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.APPROVE),
            payload,
        )
        self.assertTrue(first.saved)
        second = self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.APPROVE),
            payload,
        )
        self.assertFalse(second.saved)
        self.assertIsNone(second.outbox_id)
        self.assertIn("approved", second.detail.lower())

        with self._conn() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM decisions WHERE plan_id = ?", ("plan-1",)).fetchone()[
                    0
                ],
                1,
            )
            rejected = conn.execute(
                "SELECT status FROM audit WHERE id = ?",
                (second.audit_id,),
            ).fetchone()[0]
            self.assertEqual(rejected, "rejected")

    def test_decision_plan_id_mismatch_writes_nothing(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        with self.assertRaises(ValueError):
            self.store.apply_decision(
                "plan-1",
                _decision("other-plan", DecisionAction.APPROVE),
                payload,
            )
        with self._conn() as conn:
            self.assertEqual(
                conn.execute("SELECT state FROM plans WHERE id = ?", ("plan-1",)).fetchone()[0],
                PlanState.PENDIENTE.value,
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 0)

    def test_create_plan_does_not_enqueue_outbox(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        with self._conn() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 0)

    def test_approve_outbox_rows_follow_unique_sectors(self) -> None:
        two_sectors = _sample_payload(
            assignments=[
                {
                    "vehicle_id": "cisterna-1",
                    "sector_id": "ARRAIJAN_VISTA_ALEGRE",
                    "order": 1,
                    "volume_liters": 1000,
                },
                {
                    "vehicle_id": "cisterna-1",
                    "sector_id": "CHORRERA_EL_COCO",
                    "order": 2,
                    "volume_liters": 1000,
                },
            ]
        )
        self.store.create_plan("plan-1", two_sectors)
        self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.APPROVE),
            two_sectors,
        )
        duplicate_sector = _sample_payload(
            assignments=[
                {
                    "vehicle_id": "cisterna-1",
                    "sector_id": "ARRAIJAN_BURUNGA",
                    "order": 1,
                    "volume_liters": 1000,
                },
                {
                    "vehicle_id": "cisterna-2",
                    "sector_id": "ARRAIJAN_BURUNGA",
                    "order": 2,
                    "volume_liters": 500,
                },
            ]
        )
        self.store.create_plan("plan-2", duplicate_sector)
        self.store.apply_decision(
            "plan-2",
            _decision("plan-2", DecisionAction.APPROVE),
            duplicate_sector,
        )
        with self._conn() as conn:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM outbox WHERE plan_id = ?", ("plan-1",)).fetchone()[
                    0
                ],
                2,
            )
            channels = conn.execute(
                "SELECT channel FROM outbox WHERE plan_id = ?",
                ("plan-1",),
            ).fetchall()
            self.assertTrue(all(row[0] == "SIMULATED" for row in channels))
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM outbox WHERE plan_id = ?", ("plan-2",)).fetchone()[
                    0
                ],
                1,
            )

    def test_approve_empty_assignments_uses_unknown_sector(self) -> None:
        payload = _sample_payload(assignments=[])
        self.store.create_plan("plan-1", payload)
        self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.APPROVE),
            payload,
        )
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT sector_id, channel FROM outbox WHERE plan_id = ?",
                ("plan-1",),
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "UNKNOWN")
            self.assertEqual(rows[0][1], "SIMULATED")

    def test_audit_summary_truncated_to_five_hundred_chars(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        long_comment = "x" * 600
        self.store.apply_decision(
            "plan-1",
            _decision("plan-1", DecisionAction.REJECT, comment=long_comment),
            payload,
        )
        with self._conn() as conn:
            summary = conn.execute("SELECT input_summary FROM audit LIMIT 1").fetchone()[0]
            self.assertLessEqual(len(summary), 500)

    def test_missing_plan_raises_without_side_effects(self) -> None:
        payload = _sample_payload()
        with self.assertRaises(ValueError):
            self.store.apply_decision(
                "missing",
                _decision("missing", DecisionAction.APPROVE),
                payload,
            )
        with self._conn() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 0)

    def test_concurrent_approve_and_reject_single_winner(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        barrier = threading.Barrier(2)
        errors: list[BaseException] = []
        results: list[object] = []

        def worker(action: DecisionAction) -> None:
            store = ApprovalStore(self.db_path)
            try:
                barrier.wait(timeout=5)
                results.append(
                    store.apply_decision(
                        "plan-1",
                        _decision("plan-1", action),
                        payload,
                    )
                )
            except BaseException as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(DecisionAction.APPROVE,)),
            threading.Thread(target=worker, args=(DecisionAction.REJECT,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        with self._conn() as conn:
            outbox_count = conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
            state = conn.execute("SELECT state FROM plans WHERE id = ?", ("plan-1",)).fetchone()[0]

        self.assertIn(outbox_count, (0, 1))
        self.assertIn(state, (PlanState.APROBADO.value, PlanState.RECHAZADO.value))
        self.assertNotEqual(state, PlanState.PENDIENTE.value)
        self.assertEqual(len(results) + len(errors), 2)

    def test_recovery_failure_surfaces_on_original_exception(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        faulty = ApprovalStore(
            self.db_path,
            fail_after="decision",
            fail_recovery=True,
        )
        caught: RuntimeError | None = None
        try:
            faulty.apply_decision(
                "plan-1",
                _decision("plan-1", DecisionAction.APPROVE),
                payload,
            )
        except RuntimeError as exc:
            caught = exc

        self.assertIsNotNone(caught)
        assert caught is not None
        self.assertIn("fault injection", str(caught))
        notes = getattr(caught, "__notes__", [])
        self.assertTrue(
            any("ERROR_PARCIAL recovery failed" in note for note in notes),
            msg=f"notes={notes!r}",
        )
        with self._conn() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 0)

    def test_fault_injection_rolls_back_outbox(self) -> None:
        payload = _sample_payload()
        self.store.create_plan("plan-1", payload)
        faulty = ApprovalStore(self.db_path, fail_after="decision")
        with self.assertRaises(RuntimeError):
            faulty.apply_decision(
                "plan-1",
                _decision("plan-1", DecisionAction.APPROVE),
                payload,
            )
        with self._conn() as conn:
            self.assertEqual(
                conn.execute("SELECT state FROM plans WHERE id = ?", ("plan-1",)).fetchone()[0],
                PlanState.ERROR_PARCIAL.value,
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 0)
            error_audits = conn.execute(
                "SELECT COUNT(*) FROM audit WHERE status = ?",
                ("error",),
            ).fetchone()[0]
            self.assertGreaterEqual(error_audits, 1)

    def test_secrets_redacted_in_stored_comment(self) -> None:
        secret = "super-secret-token-value-xyz"
        prev = os.environ.get("API_TOKEN")
        os.environ["API_TOKEN"] = secret
        try:
            payload = _sample_payload()
            self.store.create_plan("plan-1", payload)
            comment = f"please approve {secret}"
            self.store.apply_decision(
                "plan-1",
                _decision("plan-1", DecisionAction.REJECT, comment=comment),
                payload,
            )
            with self._conn() as conn:
                stored_comment = conn.execute(
                    "SELECT comment FROM decisions WHERE plan_id = ?",
                    ("plan-1",),
                ).fetchone()[0]
                self.assertNotIn(secret, stored_comment)
                self.assertIn("[REDACTED]", stored_comment)
                audit_row = conn.execute(
                    "SELECT input_summary FROM audit LIMIT 1",
                ).fetchone()[0]
                self.assertNotIn(secret, audit_row)
                self.assertIn("[REDACTED]", audit_row)
        finally:
            if prev is None:
                os.environ.pop("API_TOKEN", None)
            else:
                os.environ["API_TOKEN"] = prev


if __name__ == "__main__":
    unittest.main()
