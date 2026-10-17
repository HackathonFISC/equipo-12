"""HTTP server for the coordinator panel and approval API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.config import PROJECT_ROOT
from src.contracts import DecisionAction, HumanDecision
from src.coordinator.service import CoordinatorService
from src.coordinator.store import ApprovalStore

_PANEL_HTML = Path(__file__).resolve().parent / "web" / "panel.html"
_MAX_JSON_BODY = 256 * 1024


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(
    handler: BaseHTTPRequestHandler,
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    """Return (data, error_status, error_message). error_status set => reject with JSON error."""
    header = handler.headers.get("Content-Length")
    if header is None or not str(header).strip():
        return None, 400, "missing or invalid Content-Length"
    try:
        length = int(header)
    except ValueError:
        return None, 400, "missing or invalid Content-Length"
    if length < 0:
        return None, 400, "missing or invalid Content-Length"
    if length > _MAX_JSON_BODY:
        return None, 413, "request body too large"
    if length == 0:
        return {}, None, None
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None, 400, "invalid JSON body"
    if not isinstance(data, dict):
        return None, 400, "invalid JSON body"
    return data, None, None


def serve(
    db_path: Path,
    host: str = "127.0.0.1",
    port: int = 0,
) -> ThreadingHTTPServer:
    store = ApprovalStore(db_path)
    service = CoordinatorService(store)

    class CoordinatorHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/" or self.path.startswith("/?"):
                try:
                    html = _PANEL_HTML.read_text(encoding="utf-8")
                except OSError:
                    _json_response(self, 500, {"error": "panel unavailable"})
                    return
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == "/api/context":
                _json_response(self, 200, service.snapshot())
                return

            _json_response(self, 404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path == "/api/reports":
                body, err_status, err_msg = _read_json_body(self)
                if err_status is not None:
                    _json_response(self, err_status, {"error": err_msg or "bad request"})
                    return
                assert body is not None
                if service.has_plan:
                    _json_response(
                        self,
                        400,
                        {"error": f"plan already exists: {service.plan_id}"},
                    )
                    return
                texts = body.get("texts")
                if texts is None or not isinstance(texts, list) or not all(
                    isinstance(t, str) for t in texts
                ):
                    _json_response(self, 400, {"error": "texts must be a list of strings"})
                    return
                try:
                    service.ingest_texts(texts)
                    service.prepare_draft()
                except ValueError as exc:
                    _json_response(self, 400, {"error": str(exc)})
                    return
                _json_response(self, 200, service.snapshot())
                return

            if self.path == "/api/review":
                try:
                    service.submit_for_review()
                except ValueError as exc:
                    _json_response(self, 400, {"error": str(exc)})
                    return
                _json_response(self, 200, service.snapshot())
                return

            if self.path == "/api/decision":
                body, err_status, err_msg = _read_json_body(self)
                if err_status is not None:
                    _json_response(self, err_status, {"error": err_msg or "bad request"})
                    return
                assert body is not None
                try:
                    action_raw = body.get("action")
                    if not isinstance(action_raw, str):
                        raise ValueError("action must be a string")
                    action = DecisionAction(action_raw)
                    decision = HumanDecision(
                        plan_id=body["plan_id"],
                        action=action,
                        actor=body["actor"],
                        comment=body.get("comment", "") or "",
                        timestamp=datetime.now(UTC),
                    )
                except (KeyError, TypeError, ValueError, ValidationError) as exc:
                    message = str(exc)
                    if isinstance(exc, ValidationError):
                        message = exc.errors()[0]["msg"]
                    _json_response(self, 400, {"error": message})
                    return
                try:
                    service.decide(decision)
                except ValueError as exc:
                    _json_response(self, 400, {"error": str(exc)})
                    return
                _json_response(self, 200, service.snapshot())
                return

            _json_response(self, 404, {"error": "not found"})

    server = ThreadingHTTPServer((host, port), CoordinatorHandler)
    return server


if __name__ == "__main__":
    server = serve(PROJECT_ROOT / "data" / "agua_justa.db", port=8000)
    print("Coordinator panel at http://127.0.0.1:8000/")
    server.serve_forever()
