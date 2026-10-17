"""Team-number WhatsApp after approval. Resident notices stay simulated."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from src.communication.whatsapp import WhatsAppConfig, dispatch_team_whatsapp
from src.contracts import DecisionAction, HumanDecision, PlanDraft, SectorId
from src.coordinator.state import PlanState
from src.coordinator.store import ApprovalStore


def _plan() -> PlanDraft:
    return PlanDraft(
        plan_id="plan-wa",
        assignments=[],
        route_order=[],
        unserved_demand=[],
        explanation="llamar al 50760001111",
    )


def _decision(action: DecisionAction, comment: str = "usar 50761112222") -> HumanDecision:
    return HumanDecision(
        plan_id="plan-wa",
        action=action,
        actor="coordinator",
        comment=comment,
        timestamp=datetime(2026, 10, 16, 18, 0, tzinfo=UTC),
    )


def _config() -> WhatsAppConfig:
    return WhatsAppConfig(
        token="test-token",
        phone_number_id="123456",
        to="50769990000",
    )


class WhatsAppTests(unittest.TestCase):
    def test_missing_config_does_not_call_the_transport(self) -> None:
        called = False

        def transport(config: WhatsAppConfig, body: str) -> None:
            del config, body
            nonlocal called
            called = True

        result = dispatch_team_whatsapp(
            _plan(),
            _decision(DecisionAction.APPROVE),
            config=None,
            transport=transport,
            load_config=lambda: None,
        )
        self.assertFalse(result.sent)
        self.assertFalse(called)
        self.assertEqual(result.detail, "whatsapp not configured")

    def test_reject_does_not_send(self) -> None:
        called = False

        def transport(config: WhatsAppConfig, body: str) -> None:
            del config, body
            nonlocal called
            called = True

        result = dispatch_team_whatsapp(
            _plan(),
            _decision(DecisionAction.REJECT),
            config=_config(),
            transport=transport,
        )
        self.assertFalse(result.sent)
        self.assertFalse(called)

    def test_approve_sends_only_to_the_configured_team_number(self) -> None:
        sent: list[tuple[str, str]] = []

        def transport(config: WhatsAppConfig, body: str) -> None:
            sent.append((config.to, body))

        result = dispatch_team_whatsapp(
            _plan(),
            _decision(DecisionAction.APPROVE),
            config=_config(),
            transport=transport,
        )
        self.assertTrue(result.sent)
        self.assertEqual(sent[0][0], "50769990000")
        self.assertNotIn("50760001111", sent[0][1])
        self.assertNotIn("50761112222", sent[0][1])
        self.assertIn("no se envio a residentes", sent[0][1])
        self.assertNotIn("test-token", sent[0][1])

    def test_transport_failure_stays_unsent(self) -> None:
        def transport(config: WhatsAppConfig, body: str) -> None:
            del config, body
            raise RuntimeError("Bearer test-token failed")

        result = dispatch_team_whatsapp(
            _plan(),
            _decision(DecisionAction.APPROVE),
            config=_config(),
            transport=transport,
        )
        self.assertFalse(result.sent)
        self.assertEqual(result.detail, "whatsapp send failed")
        self.assertNotIn("test-token", result.detail)

    def test_store_approve_sends_once_and_keeps_resident_rows_simulated(self) -> None:
        sent: list[str] = []

        def transport(config: WhatsAppConfig, body: str) -> None:
            sent.append(config.to)
            self.assertNotIn("50760001111", body)

        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = Path(handle.name)
        try:
            store = ApprovalStore(
                path,
                whatsapp_config=_config(),
                whatsapp_transport=transport,
            )
            payload = json.dumps(
                {
                    "plan": {
                        "plan_id": "plan-wa",
                        "assignments": [
                            {
                                "vehicle_id": "cisterna-1",
                                "sector_id": SectorId.ARRAIJAN_BURUNGA.value,
                                "order": 1,
                                "volume_liters": 100,
                            }
                        ],
                        "route_order": [SectorId.ARRAIJAN_BURUNGA.value],
                        "unserved_demand": [],
                        "explanation": "llamar al 50760001111",
                    }
                }
            )
            store.create_plan("plan-wa", payload, state=PlanState.BORRADOR)
            store.submit_for_review("plan-wa")
            result = store.apply_decision("plan-wa", _decision(DecisionAction.APPROVE), payload)
            self.assertTrue(result.saved)
            self.assertEqual(sent, ["50769990000"])
            self.assertIn("whatsapp sent to team number", result.detail)
            import sqlite3

            conn = sqlite3.connect(path)
            try:
                channels = conn.execute("SELECT channel, message FROM outbox").fetchall()
            finally:
                conn.close()
            self.assertTrue(channels)
            self.assertTrue(all(row[0] == "SIMULATED" for row in channels))
            self.assertTrue(all("no se envio por WhatsApp ni Telegram" in row[1] for row in channels))
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
