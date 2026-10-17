"""Transactional SQLite store for coordinator approval and dispatch."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from src.config import PROJECT_ROOT, redact_secrets
from src.contracts import DecisionAction, ExecutionResult, HumanDecision
from src.coordinator.state import PlanState, transition

_DEFAULT_DB = PROJECT_ROOT / "data" / "agua_justa.db"
_SUMMARY_MAX = 500
_OUTBOX_CHANNEL = "SIMULATED"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _truncate_summary(text: str) -> str:
    redacted = redact_secrets(text)
    if len(redacted) <= _SUMMARY_MAX:
        return redacted
    return redacted[: _SUMMARY_MAX - 3] + "..."


def _sector_ids_from_payload(plan_payload: str) -> list[str]:
    try:
        data = json.loads(plan_payload)
    except json.JSONDecodeError:
        return ["UNKNOWN"]
    assignments = data.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        return ["UNKNOWN"]
    sectors: list[str] = []
    seen: set[str] = set()
    for item in assignments:
        if not isinstance(item, dict):
            continue
        sector_id = item.get("sector_id")
        if sector_id is None:
            continue
        key = str(sector_id)
        if key not in seen:
            seen.add(key)
            sectors.append(key)
    return sectors if sectors else ["UNKNOWN"]


class ApprovalStore:
    def __init__(
        self,
        db_path: Path | None = None,
        *,
        fail_after: str | None = None,
        fail_recovery: bool = False,
    ) -> None:
        self.db_path = db_path if db_path is not None else _DEFAULT_DB
        self.fail_after = fail_after
        # ponytail: test-only seam to assert recovery failures surface on __notes__
        self.fail_recovery = fail_recovery
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self, *, same_thread: bool = True) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=same_thread)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans(id)
                );
                CREATE TABLE IF NOT EXISTS audit (
                    id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    input_summary TEXT NOT NULL,
                    output_summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    ts TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    sector_id TEXT NOT NULL,
                    channel TEXT NOT NULL DEFAULT 'SIMULATED',
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    FOREIGN KEY (plan_id) REFERENCES plans(id)
                );
                """
            )

    def create_plan(
        self,
        plan_id: str,
        payload_json: str,
        *,
        state: PlanState = PlanState.PENDIENTE,
    ) -> None:
        now = _now_iso()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO plans (id, state, payload_json, revision, created_at, updated_at)
                    VALUES (?, ?, ?, 0, ?, ?)
                    """,
                    (plan_id, state.value, payload_json, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"plan already exists: {plan_id}") from exc

    def _fetch_plan(self, conn: sqlite3.Connection, plan_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT id, state, payload_json, revision FROM plans WHERE id = ?",
            (plan_id,),
        ).fetchone()

    def submit_for_review(self, plan_id: str) -> None:
        conn = self._connect(same_thread=False)
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_plan(conn, plan_id)
            if row is None:
                conn.execute("ROLLBACK")
                raise ValueError(f"unknown plan: {plan_id}")

            current = PlanState(row["state"])
            revision = int(row["revision"])
            if current != PlanState.BORRADOR:
                conn.execute("ROLLBACK")
                raise ValueError(f"plan is not in borrador: {plan_id}")

            try:
                new_state = transition(current, None)
            except ValueError as exc:
                conn.execute("ROLLBACK")
                raise ValueError(str(exc)) from exc

            now = _now_iso()
            updated = conn.execute(
                """
                UPDATE plans
                SET state = ?, updated_at = ?
                WHERE id = ? AND state = ? AND revision = ?
                """,
                (new_state.value, now, plan_id, current.value, revision),
            )
            if updated.rowcount == 0:
                conn.execute("ROLLBACK")
                raise ValueError("plan state changed concurrently or plan missing")
            conn.commit()
        finally:
            conn.close()

    def _insert_decision(
        self,
        conn: sqlite3.Connection,
        decision: HumanDecision,
    ) -> str:
        decision_id = _new_id("dec")
        conn.execute(
            """
            INSERT INTO decisions (id, plan_id, action, actor, comment, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                decision.plan_id,
                decision.action.value,
                decision.actor,
                _truncate_summary(decision.comment),
                decision.timestamp.isoformat(),
            ),
        )
        return decision_id

    def _insert_audit(
        self,
        conn: sqlite3.Connection,
        *,
        actor: str,
        action: str,
        input_summary: str,
        output_summary: str,
        status: str,
    ) -> str:
        audit_id = _new_id("aud")
        conn.execute(
            """
            INSERT INTO audit (id, actor, action, input_summary, output_summary, status, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                actor,
                action,
                _truncate_summary(input_summary),
                _truncate_summary(output_summary),
                status,
                _now_iso(),
            ),
        )
        return audit_id

    def _insert_outbox_rows(
        self,
        conn: sqlite3.Connection,
        plan_id: str,
        plan_payload: str,
    ) -> list[str]:
        now = _now_iso()
        outbox_ids: list[str] = []
        for sector_id in _sector_ids_from_payload(plan_payload):
            outbox_id = _new_id("obx")
            conn.execute(
                """
                INSERT INTO outbox (id, plan_id, sector_id, channel, message, created_at, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    outbox_id,
                    plan_id,
                    sector_id,
                    _OUTBOX_CHANNEL,
                    f"Simulated dispatch notification for sector {sector_id}",
                    now,
                ),
            )
            outbox_ids.append(outbox_id)
        return outbox_ids

    def _best_effort_error_partial(self, plan_id: str, prior_state: PlanState) -> None:
        if self.fail_recovery:
            raise RuntimeError("recovery fault injection")
        try:
            error_state = transition(prior_state, None, failed=True)
        except ValueError:
            return
        with self._connect() as conn:
            now = _now_iso()
            conn.execute(
                "UPDATE plans SET state = ?, updated_at = ? WHERE id = ?",
                (error_state.value, now, plan_id),
            )
            self._insert_audit(
                conn,
                actor="system",
                action="ERROR_PARCIAL",
                input_summary=f"plan_id={plan_id}",
                output_summary=f"state={error_state.value}",
                status="error",
            )

    def apply_decision(
        self,
        plan_id: str,
        decision: HumanDecision,
        plan_payload: str,
    ) -> ExecutionResult:
        if decision.plan_id != plan_id:
            raise ValueError("decision.plan_id must match plan_id")

        conn = self._connect(same_thread=False)
        current: PlanState | None = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = self._fetch_plan(conn, plan_id)
            if row is None:
                conn.execute("ROLLBACK")
                raise ValueError(f"unknown plan: {plan_id}")

            current = PlanState(row["state"])
            revision = int(row["revision"])

            if decision.action == DecisionAction.APPROVE and current == PlanState.APROBADO:
                audit_id = self._insert_audit(
                    conn,
                    actor=decision.actor,
                    action=decision.action.value,
                    input_summary=decision.model_dump_json(),
                    output_summary="plan already approved",
                    status="rejected",
                )
                conn.commit()
                return ExecutionResult(
                    saved=False,
                    plan_id=plan_id,
                    audit_id=audit_id,
                    outbox_id=None,
                    detail="plan is already approved",
                )

            try:
                new_state = transition(current, decision.action)
            except ValueError as exc:
                conn.execute("ROLLBACK")
                raise ValueError(str(exc)) from exc

            now = _now_iso()
            new_revision = revision
            payload_to_store = row["payload_json"]
            saved = False
            detail = ""

            if decision.action == DecisionAction.APPROVE:
                payload_to_store = plan_payload
                saved = True
                detail = "plan approved and dispatch queued"
            elif decision.action == DecisionAction.REJECT:
                detail = "plan rejected"
            elif decision.action == DecisionAction.CORRECT:
                new_revision = revision + 1
                payload_to_store = plan_payload
                detail = "plan returned to borrador"

            updated = conn.execute(
                """
                UPDATE plans
                SET state = ?, payload_json = ?, revision = ?, updated_at = ?
                WHERE id = ? AND state = ? AND revision = ?
                """,
                (
                    new_state.value,
                    payload_to_store,
                    new_revision,
                    now,
                    plan_id,
                    current.value,
                    revision,
                ),
            )
            if updated.rowcount == 0:
                conn.execute("ROLLBACK")
                raise ValueError("plan state changed concurrently or plan missing")

            self._insert_decision(conn, decision)

            if self.fail_after == "decision":
                raise RuntimeError("fault injection after decision insert")

            first_outbox_id: str | None = None
            if decision.action == DecisionAction.APPROVE:
                outbox_ids = self._insert_outbox_rows(conn, plan_id, plan_payload)
                first_outbox_id = outbox_ids[0] if outbox_ids else None

            audit_id = self._insert_audit(
                conn,
                actor=decision.actor,
                action=decision.action.value,
                input_summary=decision.model_dump_json(),
                output_summary=detail,
                status="ok",
            )
            conn.commit()
        except ValueError:
            raise
        except Exception as exc:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            if current is not None:
                try:
                    self._best_effort_error_partial(plan_id, current)
                except Exception as recovery_exc:
                    exc.add_note(f"ERROR_PARCIAL recovery failed: {recovery_exc}")
            raise
        finally:
            conn.close()

        return ExecutionResult(
            saved=saved,
            plan_id=plan_id,
            audit_id=audit_id,
            outbox_id=first_outbox_id,
            detail=detail,
        )
