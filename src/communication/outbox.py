"""Simulated outbox for resident notices.

An approved plan queues one notice per assigned sector and one per unserved
sector. The notice stays QUEUED on SIMULATED_OUTBOX. This module does not
call WhatsApp or Telegram.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.config import PROJECT_ROOT
from src.contracts import DecisionAction, ExecutionResult, HumanDecision, PlanDraft

_CHANNEL = "SIMULATED_OUTBOX"
_STATUS = "QUEUED"
_NOT_SENT = "Este mensaje quedo en la bandeja simulada y no se envio por WhatsApp ni Telegram."


def _database(path: Path | None) -> Path:
    if path is not None:
        return path
    return PROJECT_ROOT / "data" / "outbox.sqlite3"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS outbox (
            outbox_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL UNIQUE,
            audit_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notices (
            notice_id TEXT PRIMARY KEY,
            outbox_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            audit_id TEXT NOT NULL,
            sector_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            kind TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL
        );
        """
    )
    return connection


def _assigned_body(plan: PlanDraft, vehicle_id: str, sector_id: str, volume_liters: int, order: int) -> str:
    return (
        f"Aviso de demostracion para {sector_id}. "
        f"La cisterna {vehicle_id} llevaria {volume_liters} litros "
        f"en el turno {order} del plan {plan.plan_id}. {_NOT_SENT}"
    )


def _unserved_body(plan_id: str, sector_id: str) -> str:
    return (
        f"Aviso de demostracion para {sector_id}. "
        f"El plan {plan_id} no asigno cisterna. {_NOT_SENT}"
    )


def notices_for_panel(plan: PlanDraft) -> list[tuple[str, str]]:
    """One simulated notice per sector for the coordinator panel.

    The first assignment for a sector supplies the liters and the turn.
    A later truck for that same sector does not add a second row.
    Unserved sectors that are not already assigned are included.
    """
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for assignment in plan.assignments:
        sector_id = assignment.sector_id.value
        if sector_id in seen:
            continue
        seen.add(sector_id)
        rows.append(
            (
                sector_id,
                _assigned_body(
                    plan,
                    assignment.vehicle_id,
                    sector_id,
                    assignment.volume_liters,
                    assignment.order,
                ),
            )
        )
    for sector_id in plan.unserved_demand:
        if sector_id in seen:
            continue
        seen.add(sector_id)
        rows.append((sector_id, _unserved_body(plan.plan_id, sector_id)))
    return rows


def communicate(
    plan: PlanDraft,
    decision: HumanDecision,
    database: Path | None = None,
) -> ExecutionResult:
    """Queue simulated notices only when the human decision approves this plan.

    REJECT and CORRECT leave the outbox empty. A second approval of the same
    plan returns the existing outbox instead of writing the notices again.
    The plan explanation and the human comment are not copied into the message.
    """
    path = _database(database)
    if decision.plan_id != plan.plan_id:
        return ExecutionResult(
            saved=False,
            plan_id=plan.plan_id,
            audit_id=f"audit-mismatch-{plan.plan_id}",
            detail="plan_id does not match the approved plan",
        )
    if decision.action is not DecisionAction.APPROVE:
        return ExecutionResult(
            saved=False,
            plan_id=plan.plan_id,
            audit_id=f"audit-{plan.plan_id}-{decision.action.value}",
            detail="human decision did not approve the plan",
        )

    outbox_id = f"outbox-{plan.plan_id}"
    audit_id = f"audit-{plan.plan_id}"
    connection = _connect(path)
    try:
        existing = connection.execute(
            "SELECT outbox_id, audit_id FROM outbox WHERE plan_id = ?",
            (plan.plan_id,),
        ).fetchone()
        if existing is not None:
            return ExecutionResult(
                saved=True,
                plan_id=plan.plan_id,
                audit_id=str(existing["audit_id"]),
                outbox_id=str(existing["outbox_id"]),
                detail="outbox already queued",
            )
        connection.execute("BEGIN")
        connection.execute(
            """
            INSERT INTO outbox (outbox_id, plan_id, audit_id, actor, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                outbox_id,
                plan.plan_id,
                audit_id,
                decision.actor,
                decision.timestamp.isoformat(),
            ),
        )
        for assignment in plan.assignments:
            sector_id = assignment.sector_id.value
            connection.execute(
                """
                INSERT INTO notices (
                    notice_id, outbox_id, plan_id, audit_id, sector_id,
                    channel, kind, body, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"notice-{plan.plan_id}-{sector_id}-{assignment.vehicle_id}-{assignment.order}-ASSIGNED",
                    outbox_id,
                    plan.plan_id,
                    audit_id,
                    sector_id,
                    _CHANNEL,
                    "ASSIGNED",
                    _assigned_body(
                        plan,
                        assignment.vehicle_id,
                        sector_id,
                        assignment.volume_liters,
                        assignment.order,
                    ),
                    _STATUS,
                ),
            )
        seen_unserved: set[str] = set()
        for sector_id in plan.unserved_demand:
            if sector_id in seen_unserved:
                continue
            seen_unserved.add(sector_id)
            connection.execute(
                """
                INSERT INTO notices (
                    notice_id, outbox_id, plan_id, audit_id, sector_id,
                    channel, kind, body, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"notice-{plan.plan_id}-{sector_id}-UNSERVED",
                    outbox_id,
                    plan.plan_id,
                    audit_id,
                    sector_id,
                    _CHANNEL,
                    "UNSERVED",
                    _unserved_body(plan.plan_id, sector_id),
                    _STATUS,
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return ExecutionResult(
        saved=True,
        plan_id=plan.plan_id,
        audit_id=audit_id,
        outbox_id=outbox_id,
        detail="simulated notices queued",
    )


def list_notices(plan_id: str, database: Path | None = None) -> list[dict[str, str]]:
    """Return queued notices for a plan. Missing databases yield an empty list."""
    path = _database(database)
    if not path.is_file():
        return []
    connection = _connect(path)
    try:
        rows = connection.execute(
            """
            SELECT sector_id, channel, kind, body, status
            FROM notices
            WHERE plan_id = ?
            ORDER BY notice_id
            """,
            (plan_id,),
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "sector_id": str(row["sector_id"]),
            "channel": str(row["channel"]),
            "kind": str(row["kind"]),
            "body": str(row["body"]),
            "status": str(row["status"]),
        }
        for row in rows
    ]
