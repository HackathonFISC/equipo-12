"""HTTP coordinator panel and approval API."""

from __future__ import annotations

import http.client
import json
import re
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from src.coordinator.app import serve

_PANEL_PATH = Path(__file__).resolve().parents[1] / "src" / "coordinator" / "web" / "panel.html"
_USER_PATH = Path(__file__).resolve().parents[1] / "src" / "coordinator" / "web" / "usuario.html"

_VISTA_LINES = [
    "48 horas sin agua y 15 personas por el chino de Vista Alegre",
    "Xtra de Vista Alegre: tres dias sin agua y 20 familias",
]
_UNKNOWN_LINE = "72 horas sin agua en Ciudad Imaginaria XYZ"


def _temp_db() -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return Path(tmp.name)


def _url(base: str, path: str) -> str:
    return base.rstrip("/") + path


def _get_json(base: str, path: str) -> tuple[int, dict]:
    req = urllib.request.Request(_url(base, path), method="GET")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _post_json(base: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        _url(base, path),
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw)


def _cluster_report_counts(clusters: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cluster in clusters:
        sector = str(cluster.get("sector_id", ""))
        counts[sector] = int(cluster.get("report_count", 0))
    return counts


def _outbox_count(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
    finally:
        conn.close()


class CoordinatorAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = _temp_db()
        self.server = serve(self.db_path, port=0)
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.db_path.unlink(missing_ok=True)

    def test_panel_html_ids_match_get_element_by_id(self) -> None:
        html = _PANEL_PATH.read_text(encoding="utf-8")
        self.assertIn("btn-aprobar", html)
        self.assertNotIn('id="btn-camara"', html)
        self.assertNotIn('id="btn-microfono"', html)
        ids_in_js = set(re.findall(r'getElementById\("([^"]+)"\)', html))
        for element_id in ids_in_js:
            self.assertIn(f'id="{element_id}"', html, msg=f"missing id={element_id}")

    def test_user_html_ids_match_get_element_by_id(self) -> None:
        html = _USER_PATH.read_text(encoding="utf-8")
        for forbidden in ("btn-aprobar", "btn-rechazar", "btn-corregir", "btn-revisar", "SIMULATED"):
            self.assertNotIn(forbidden, html)
        for required in ("btn-camara", "btn-microfono", "btn-camara-frontal", "btn-camara-trasera"):
            self.assertIn(required, html)
        ids_in_js = set(re.findall(r'getElementById\("([^"]+)"\)', html))
        for element_id in ids_in_js:
            self.assertIn(f'id="{element_id}"', html, msg=f"missing id={element_id}")

    def test_get_root_returns_the_public_page(self) -> None:
        req = urllib.request.Request(_url(self.base, "/"), method="GET")
        with urllib.request.urlopen(req) as resp:
            html = resp.read().decode("utf-8")
        self.assertIn("btn-camara-frontal", html)
        self.assertIn("btn-microfono", html)
        self.assertNotIn("btn-aprobar", html)

    def test_coordinator_page_keeps_the_decision(self) -> None:
        req = urllib.request.Request(_url(self.base, "/coordinacion"), method="GET")
        with urllib.request.urlopen(req) as resp:
            html = resp.read().decode("utf-8")
        self.assertIn("btn-aprobar", html)
        self.assertIn("SIMULATED", html)
        self.assertNotIn('id="btn-camara"', html)

    def test_context_before_reports(self) -> None:
        status, ctx = _get_json(self.base, "/api/context")
        self.assertEqual(status, 200)
        self.assertIsNone(ctx["state"])
        self.assertEqual(ctx["clusters"], [])
        self.assertIsNone(ctx["execution"])

    def test_reports_review_approve_flow(self) -> None:
        status, ctx = _post_json(
            self.base,
            "/api/reports",
            {"texts": _VISTA_LINES + [_UNKNOWN_LINE]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(ctx["state"], "borrador")
        self.assertEqual(_outbox_count(self.db_path), 0)

        vista = [
            c
            for c in ctx["clusters"]
            if c.get("sector_id") == "ARRAIJAN_VISTA_ALEGRE"
        ]
        self.assertEqual(len(vista), 2)
        self.assertEqual(sorted(c["report_count"] for c in vista), [1, 1])
        unknown = [c for c in ctx["clusters"] if c.get("sector_id") == "UNKNOWN"]
        self.assertEqual(len(unknown), 1)

        status, ctx = _post_json(self.base, "/api/review", {})
        self.assertEqual(status, 200)
        self.assertEqual(ctx["state"], "pendiente")
        self.assertEqual(_outbox_count(self.db_path), 0)

        plan_id = ctx["plan"]["plan_id"]
        status, ctx = _post_json(
            self.base,
            "/api/decision",
            {
                "plan_id": plan_id,
                "action": "APPROVE",
                "actor": "coordinador",
                "comment": "",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(ctx["state"], "aprobado")
        self.assertTrue(ctx["execution"]["saved"])
        self.assertGreaterEqual(_outbox_count(self.db_path), 1)
        conn = sqlite3.connect(self.db_path)
        try:
            channels = conn.execute("SELECT channel FROM outbox").fetchall()
        finally:
            conn.close()
        self.assertTrue(all(row[0] == "SIMULATED" for row in channels))

    def test_invalid_action_lowercase_returns_400(self) -> None:
        db_path = _temp_db()
        server = serve(db_path, port=0)
        host, port = server.server_address
        base = f"http://{host}:{port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            _post_json(base, "/api/reports", {"texts": _VISTA_LINES})
            _post_json(base, "/api/review", {})
            _, ctx = _get_json(base, "/api/context")
            plan_id = ctx["plan"]["plan_id"]
            status, body = _post_json(
                base,
                "/api/decision",
                {
                    "plan_id": plan_id,
                    "action": "approve",
                    "actor": "coordinador",
                    "comment": "",
                },
            )
            self.assertEqual(status, 400)
            self.assertIn("error", body)
            self.assertEqual(_outbox_count(db_path), 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            db_path.unlink(missing_ok=True)

    def test_second_reports_post_rejected_without_mutating_queue(self) -> None:
        status, first_ctx = _post_json(
            self.base,
            "/api/reports",
            {"texts": _VISTA_LINES + [_UNKNOWN_LINE]},
        )
        self.assertEqual(status, 200)
        expected_counts = _cluster_report_counts(first_ctx["clusters"])

        status, body = _post_json(
            self.base,
            "/api/reports",
            {"texts": ["reporte nuevo en otro sector totalmente distinto"]},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", body)

        _, ctx = _get_json(self.base, "/api/context")
        self.assertEqual(_cluster_report_counts(ctx["clusters"]), expected_counts)

    def test_oversized_content_length_returns_413(self) -> None:
        host, port = self.server.server_address
        conn = http.client.HTTPConnection(host, port, timeout=5)
        try:
            conn.putrequest("POST", "/api/reports")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(8 * 1024 * 1024 + 1))
            conn.endheaders()
            resp = conn.getresponse()
            self.assertEqual(resp.status, 413)
            payload = json.loads(resp.read().decode("utf-8"))
            self.assertIn("error", payload)
        finally:
            conn.close()

    def test_correct_empty_comment_returns_400(self) -> None:
        _post_json(self.base, "/api/reports", {"texts": _VISTA_LINES})
        _post_json(self.base, "/api/review", {})
        _, ctx = _get_json(self.base, "/api/context")
        plan_id = ctx["plan"]["plan_id"]
        status, body = _post_json(
            self.base,
            "/api/decision",
            {
                "plan_id": plan_id,
                "action": "CORRECT",
                "actor": "coordinador",
                "comment": "   ",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        self.assertEqual(_outbox_count(self.db_path), 0)


if __name__ == "__main__":
    unittest.main()
