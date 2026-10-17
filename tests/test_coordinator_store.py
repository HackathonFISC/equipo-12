"""Transactional approval store (SQLite)."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from src.contracts import DecisionAction, HumanDecision
from src.coordinator.state import PlanState
from src.coordinator.store import ApprovalStore


def _sample_payload(
    plan_id: str = "plan-1",
    sectors: list[str] | None = None,
) -> str:
    sectors = sectors or ["ARRAIJAN_VISTA_ALEGRE"]
    assignments = [
        {"vehicle_id": "cisterna-1", "sector_id": s, "order": i + 1, "volume_liters": 1000}
        for i, s in enumerate(sectors)
    ]
    return json.dumps(
        {
            "plan_id": plan_id,
            "assignments": assignments,
            "route_order": sectors,
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

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

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
            rejected = conn.execute(
                "SELECT status FROM audit WHERE id = ?",
                (second.audit_id,),
            ).fetchone()[0]
            self.assertEqual(rejected, "rejected")

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
