"""One WhatsApp message to the team test number after a human approves a plan.

Resident notices stay in the simulated outbox. This module never reads a
phone number from a report, a plan explanation, or a human comment.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from src.contracts import DecisionAction, HumanDecision, PlanDraft

_PHONE_ID = re.compile(r"[0-9]{5,20}")
_TEAM_NUMBER = re.compile(r"[0-9]{8,15}")
_GRAPH_VERSION = "v21.0"


@dataclass(frozen=True)
class WhatsAppConfig:
    token: str
    phone_number_id: str
    to: str


@dataclass(frozen=True)
class WhatsAppDispatch:
    sent: bool
    detail: str


Transport = Callable[[WhatsAppConfig, str], None]


def load_whatsapp_config() -> WhatsAppConfig | None:
    """Read the team number and Cloud API settings. Missing or invalid values send nothing."""
    token = os.environ.get("WHATSAPP_TOKEN", "").strip()
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    team_number = os.environ.get("WHATSAPP_TO", "").strip().lstrip("+")
    if not token or _PHONE_ID.fullmatch(phone_number_id) is None:
        return None
    if _TEAM_NUMBER.fullmatch(team_number) is None:
        return None
    return WhatsAppConfig(token=token, phone_number_id=phone_number_id, to=team_number)


def team_message(plan: PlanDraft) -> str:
    """Fixed demo text. It does not copy the plan explanation or the human comment."""
    sectors = len({item.sector_id.value for item in plan.assignments})
    return (
        f"AguaJusta Oeste: el plan {plan.plan_id} fue aprobado. "
        f"Sectores con cisterna: {sectors}. "
        "Este aviso es de prueba para el equipo y no se envio a residentes."
    )


def post_cloud_api(config: WhatsAppConfig, body: str) -> None:
    """POST one text message to the configured team number. Raises on HTTP failure."""
    url = (
        f"https://graph.facebook.com/{_GRAPH_VERSION}/"
        f"{config.phone_number_id}/messages"
    )
    payload = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": config.to,
            "type": "text",
            "text": {"preview_url": False, "body": body},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 300:
                raise RuntimeError("whatsapp send failed")
    except urllib.error.HTTPError as exc:
        raise RuntimeError("whatsapp send failed") from exc


def dispatch_team_whatsapp(
    plan: PlanDraft,
    decision: HumanDecision,
    *,
    config: WhatsAppConfig | None = None,
    transport: Transport | None = None,
    load_config: Callable[[], WhatsAppConfig | None] | None = None,
) -> WhatsAppDispatch:
    """Send only after APPROVE, and only to the configured team number."""
    if decision.action is not DecisionAction.APPROVE or decision.plan_id != plan.plan_id:
        return WhatsAppDispatch(sent=False, detail="not approved")
    selected = config if config is not None else (load_config or load_whatsapp_config)()
    if selected is None:
        return WhatsAppDispatch(sent=False, detail="whatsapp not configured")
    sender = transport or post_cloud_api
    try:
        sender(selected, team_message(plan))
    except Exception:
        return WhatsAppDispatch(sent=False, detail="whatsapp send failed")
    return WhatsAppDispatch(sent=True, detail="whatsapp sent to team number")
