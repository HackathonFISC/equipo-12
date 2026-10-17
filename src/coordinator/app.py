"""HTTP server for the coordinator panel and approval API."""

from __future__ import annotations

import json
import mimetypes
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from pydantic import ValidationError

from src.config import PROJECT_ROOT
from src.contracts import DecisionAction, HumanDecision
from src.coordinator.service import CoordinatorService
from src.coordinator.store import ApprovalStore

_USER_HTML = Path(__file__).resolve().parent / "web" / "usuario.html"
_PANEL_HTML = Path(__file__).resolve().parent / "web" / "panel.html"
_MAX_JSON_BODY = 8 * 1024 * 1024
_PAGES = {
    "/": "index.html",
    "/coordinacion": "coordinacion.html",
    "/admin": "admin.html",
    "/ciudadano": "ciudadano.html",
}
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("font/woff2", ".woff2")


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _safe_file(root: Path, rel: str) -> Path | None:
    rel = unquote(rel).lstrip("/")
    if not rel or rel.startswith(("/", "\\")) or "\\" in rel or ".." in rel.split("/"):
        return None
    root_resolved = root.resolve()
    candidate = (root_resolved / rel).resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


def _bytes_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    mime, _enc = mimetypes.guess_type(path.name)
    if path.suffix == ".html":
        mime = "text/html; charset=utf-8"
    body = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime or "application/octet-stream")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        _json_response(handler, 500, {"error": "panel unavailable"})
        return
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
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
    web_dist: Path | None = None,
) -> ThreadingHTTPServer:
    store = ApprovalStore(db_path)
    service = CoordinatorService(store)
    lock = threading.Lock()

    class CoordinatorHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            path_only = self.path.split("?", 1)[0]
            if web_dist is not None and path_only in _PAGES:
                built = _safe_file(web_dist, _PAGES[path_only])
                if built is not None:
                    _bytes_file(self, built)
                    return

            if path_only == "/":
                _html_file(self, _USER_HTML)
                return

            if path_only in ("/coordinacion", "/admin", "/ciudadano"):
                _html_file(self, _PANEL_HTML)
                return

            if web_dist is not None and path_only.startswith("/_astro/"):
                asset = _safe_file(web_dist, path_only)
                if asset is None:
                    _json_response(self, 404, {"error": "not found"})
                    return
                _bytes_file(self, asset)
                return

            if path_only == "/api/context":
                with lock:
                    payload = service.snapshot()
                _json_response(self, 200, payload)
                return

            if path_only == "/api/health":
                with lock:
                    payload = service.health_check()
                http_status = 200 if payload.get("status") == "ok" else 503
                _json_response(self, http_status, payload)
                return

            _json_response(self, 404, {"error": "not found"})

        def do_POST(self) -> None:
            path_only = self.path.split("?", 1)[0]
            if path_only == "/api/reports":
                body, err_status, err_msg = _read_json_body(self)
                if err_status is not None:
                    _json_response(self, err_status, {"error": err_msg or "bad request"})
                    return
                assert body is not None
                texts = body.get("texts", [])
                media = body.get("media", [])
                if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
                    _json_response(self, 400, {"error": "texts must be a list of strings"})
                    return
                if not isinstance(media, list):
                    _json_response(self, 400, {"error": "media must be a list"})
                    return
                with lock:
                    if service.has_plan:
                        _json_response(
                            self,
                            400,
                            {"error": f"plan already exists: {service.plan_id}"},
                        )
                        return
                    try:
                        service.run_reports(texts, media)
                    except ValueError as exc:
                        _json_response(self, 400, {"error": str(exc)})
                        return
                    payload = service.snapshot()
                _json_response(self, 200, payload)
                return

            if path_only == "/api/review":
                with lock:
                    try:
                        service.submit_for_review()
                    except ValueError as exc:
                        _json_response(self, 400, {"error": str(exc)})
                        return
                    payload = service.snapshot()
                _json_response(self, 200, payload)
                return

            if path_only == "/api/decision":
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
                with lock:
                    try:
                        service.decide(decision)
                    except ValueError as exc:
                        _json_response(self, 400, {"error": str(exc)})
                        return
                    payload = service.snapshot()
                _json_response(self, 200, payload)
                return

            if path_only == "/api/citizen-report":
                body, err_status, err_msg = _read_json_body(self)
                if err_status is not None:
                    _json_response(self, err_status, {"error": err_msg or "bad request"})
                    return
                assert body is not None
                text = body.get("text")
                if not isinstance(text, str) or not text.strip():
                    _json_response(self, 400, {"error": "text must be a non-empty string"})
                    return
                source_channel = body.get("source_channel", "citizen_portal")
                if not isinstance(source_channel, str) or not source_channel.strip():
                    source_channel = "citizen_portal"
                else:
                    source_channel = source_channel.strip()
                with lock:
                    try:
                        payload = service.submit_citizen_report(
                            text,
                            source_channel=source_channel,
                        )
                    except ValueError as exc:
                        _json_response(self, 400, {"error": str(exc)})
                        return
                _json_response(self, 200, payload)
                return

            if path_only == "/api/preload":
                _body, err_status, err_msg = _read_json_body(self)
                if err_status is not None:
                    _json_response(self, err_status, {"error": err_msg or "bad request"})
                    return
                with lock:
                    try:
                        payload = service.preload_fixtures()
                    except ValueError as exc:
                        _json_response(self, 400, {"error": str(exc)})
                        return
                _json_response(self, 200, payload)
                return

            if path_only == "/api/reset":
                _body, err_status, err_msg = _read_json_body(self)
                if err_status is not None:
                    _json_response(self, err_status, {"error": err_msg or "bad request"})
                    return
                with lock:
                    payload = service.reset()
                _json_response(self, 200, payload)
                return

            _json_response(self, 404, {"error": "not found"})

    server = ThreadingHTTPServer((host, port), CoordinatorHandler)
    return server


if __name__ == "__main__":
    import os

    _host = os.environ.get("HOST", "127.0.0.1")
    _port = int(os.environ.get("PORT", "8000"))
    # UI=legacy sirve panel.html y usuario.html. El default es web/dist.
    _dist = None if os.environ.get("UI") == "legacy" else PROJECT_ROOT / "web" / "dist"
    server = serve(PROJECT_ROOT / "data" / "agua_justa.db", host=_host, port=_port, web_dist=_dist)
    print(f"Coordinator panel at http://{_host}:{_port}/")
    server.serve_forever()
