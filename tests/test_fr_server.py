"""
Tests for fr_server.py — FR Ledger Panel Server
"""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/utils is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

import fr_server


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — build FR dicts matching the shape query_feature_requests_from_db returns
# ─────────────────────────────────────────────────────────────────────────────

def _make_fr(
    fr_id: str,
    state: str,
    prs: str = "—",
    pr_number: int | None = None,
) -> dict[str, Any]:
    is_active = state.upper() in fr_server.ACTIVE_STATES
    return {
        "id": fr_id,
        "title": "Test FR",
        "type": "feature",
        "projects": "⊕Workspace",
        "state": state,
        "branch": f"feature/workspace/{fr_id}",
        "prs": prs,
        "pr_number": pr_number,
        "owner": "⊕workspace-ci",
        "opened": "2026-04-25",
        "updated": "2026-04-25",
        "is_active": is_active,
        "state_class": fr_server._state_class(state),
    }


# ─────────────────────────────────────────────────────────────────────────────
# query_feature_requests_from_db (unit — DB mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryFRsFromDb:
    def test_db_unavailable_returns_empty(self) -> None:
        with patch.object(fr_server, "_DB_AVAILABLE", False):
            result = fr_server.query_feature_requests_from_db()
        assert result == []

    def test_db_error_returns_empty(self) -> None:
        with patch.object(fr_server, "_DB_AVAILABLE", True), \
             patch.object(fr_server, "_init_fr_db", side_effect=RuntimeError("fail")):
            result = fr_server.query_feature_requests_from_db()
        assert result == []

    def test_active_state_flag(self) -> None:
        fr = _make_fr("FR-001", "BRANCHED")
        assert fr["is_active"] is True

    def test_branch_checked_out_and_merged_states_are_active(self) -> None:
        assert _make_fr("FR-002A", "BRANCH_CHECKED_OUT")["is_active"] is True
        assert _make_fr("FR-002B", "MERGED")["is_active"] is True

    def test_merged_state_is_active(self) -> None:
        fr = _make_fr("FR-002", "MERGED")
        assert fr["is_active"] is True

    def test_review_requested_is_active(self) -> None:
        fr = _make_fr("FR-003", "REVIEW_REQUESTED", prs="[#9](...)", pr_number=9)
        assert fr["is_active"] is True
        assert fr["pr_number"] == 9

    def test_branched_is_active(self) -> None:
        fr = _make_fr("FR-004", "BRANCHED", prs="[#23](...)", pr_number=23)
        assert fr["is_active"] is True

    def test_state_class_review_requested(self) -> None:
        fr = _make_fr("FR-005", "REVIEW_REQUESTED")
        assert fr["state_class"] == "state-info"

    def test_state_class_merged(self) -> None:
        fr = _make_fr("FR-006", "MERGED")
        assert fr["state_class"] == "state-done"

    @pytest.mark.parametrize("state", ["SIGNED_OFF", "ARCHIVED", "CLOSED", "DONE"])
    def test_archived_states_render_in_archived_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
    ) -> None:
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        monkeypatch.setattr(fr_server, "DASHBOARD_HTML", reports_dir / "fr_dashboard.html")

        fr_server.regenerate_dashboard([_make_fr("FR-ARCHIVED", state)])

        html = (reports_dir / "fr_dashboard.html").read_text(encoding="utf-8")
        assert 'id="archived-grid"' in html
        assert "FR-ARCHIVED" in html
        assert 'id="active-grid">\n    <div class="empty">No active FRs.</div>' in html


def _make_signoff_db(db_path: Path, state: str = "SOAKING") -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE feature_requests (
            id TEXT PRIMARY KEY, state TEXT, updated_at TEXT, signed_off_at TEXT
        );
        CREATE TABLE fr_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, fr_id TEXT, ts TEXT,
            agent TEXT, event_type TEXT, summary TEXT, details TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO feature_requests (id, state, updated_at, signed_off_at) VALUES (?, ?, ?, ?)",
        ("FR-SIGNOFF", state, "old-updated", None),
    )
    conn.commit()
    return conn


def test_signoff_persists_signed_off_timestamps_and_audit_event(tmp_path: Path) -> None:
    db_path = tmp_path / "fr.db"
    conn = _make_signoff_db(db_path)

    with patch.object(fr_server, "_DB_AVAILABLE", True), patch.object(
        fr_server, "_get_fr_conn", return_value=conn
    ), patch.object(fr_server, "datetime") as clock:
        clock.now.return_value = type(
            "Timestamp", (), {"isoformat": lambda self: "2026-09-15T12:34:56+00:00"}
        )()
        result = fr_server.signoff_fr("FR-SIGNOFF")

    assert result == {"ok": True}
    check_conn = sqlite3.connect(str(db_path))
    check_conn.row_factory = sqlite3.Row
    row = check_conn.execute(
        "SELECT state, updated_at, signed_off_at FROM feature_requests WHERE id=?",
        ("FR-SIGNOFF",),
    ).fetchone()
    event = check_conn.execute(
        "SELECT agent, event_type, summary, details FROM fr_events WHERE fr_id=?",
        ("FR-SIGNOFF",),
    ).fetchone()
    check_conn.close()

    assert tuple(row) == (
        "SIGNED_OFF",
        "2026-09-15T12:34:56+00:00",
        "2026-09-15T12:34:56+00:00",
    )
    assert event["agent"] == "⊕workspace-overseer"
    assert event["event_type"] == "signoff"
    assert "previous state SOAKING" in event["summary"]
    assert "Tyler-authorized production-observation signoff" in event["details"]


def test_signoff_does_not_mutate_historical_done_row(tmp_path: Path) -> None:
    db_path = tmp_path / "fr.db"
    conn = _make_signoff_db(db_path, state="DONE")

    with patch.object(fr_server, "_DB_AVAILABLE", True), patch.object(
        fr_server, "_get_fr_conn", return_value=conn
    ), patch.object(fr_server, "datetime") as clock:
        clock.now.return_value = type(
            "Timestamp", (), {"isoformat": lambda self: "2026-09-15T12:34:56+00:00"}
        )()
        result = fr_server.signoff_fr("FR-SIGNOFF")

    assert result == {"ok": True}
    check_conn = sqlite3.connect(str(db_path))
    row = check_conn.execute(
        "SELECT state, updated_at, signed_off_at FROM feature_requests WHERE id=?",
        ("FR-SIGNOFF",),
    ).fetchone()
    event_count = check_conn.execute("SELECT COUNT(*) FROM fr_events").fetchone()[0]
    check_conn.close()
    assert tuple(row) == ("DONE", "old-updated", None)
    assert event_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# query_ledger_events (unit — DB mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryLedgerEvents:
    def test_db_unavailable_returns_empty(self) -> None:
        with patch.object(fr_server, "_DB_AVAILABLE", False):
            result = fr_server.query_ledger_events("FR-001")
        assert result == []

    def test_db_error_returns_empty(self) -> None:
        with patch.object(fr_server, "_DB_AVAILABLE", True), \
             patch.object(fr_server, "_get_fr_conn", side_effect=RuntimeError("fail")):
            result = fr_server.query_ledger_events("FR-001")
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# Live server — /api/frs and /signoff
# ─────────────────────────────────────────────────────────────────────────────

def _find_free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _MockWatcher:
    """Stand-in for _WatcherThread in handler tests."""

    def __init__(self, frs: list[dict[str, Any]], stale: bool = False) -> None:
        self._frs = frs
        self._stale = stale

    @property
    def frs(self) -> list[dict[str, Any]]:
        return self._frs

    @property
    def stale(self) -> bool:
        return self._stale

    def _reload(self) -> None:  # called by signoff handler after successful write
        pass


def _start_test_server(
    port: int, frs: list[dict[str, Any]], stale: bool = False
) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
    import http.server as hs

    watcher = _MockWatcher(frs, stale)
    handler = fr_server._make_handler(watcher)  # type: ignore[attr-defined]
    server = hs.ThreadingHTTPServer(("127.0.0.1", port), handler)

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    # Give the server a moment to bind
    time.sleep(0.15)
    return server, t


class TestApiEndpoints:
    @pytest.fixture(autouse=True)
    def _server(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
        """Spin up a test server on a free port before each test method."""
        self._port = _find_free_port()
        sample_fr: dict[str, Any] = {
            "id": "FR-20260425-test",
            "title": "Test FR",
            "type": "feature",
            "projects": "⊕Workspace",
            "state": "REVIEW_REQUESTED",
            "branch": "feature/workspace/test",
            "prs": "[#42](https://github.com/...)",
            "pr_number": 42,
            "owner": "⊕workspace-ci",
            "opened": "2026-04-25",
            "updated": "2026-04-25",
            "is_active": True,
            "state_class": "state-info",
        }
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        monkeypatch.setattr(fr_server, "WORKSPACE_ROOT", tmp_path)
        monkeypatch.setattr(fr_server, "DASHBOARD_HTML", reports_dir / "fr_dashboard.html")
        fr_server.regenerate_dashboard([sample_fr])
        server, thread = _start_test_server(self._port, [sample_fr])
        try:
            yield
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def _get(self, path: str) -> Any:
        url = f"http://127.0.0.1:{self._port}{path}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path: str, data: Any) -> tuple[int, Any]:
        url = f"http://127.0.0.1:{self._port}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_api_frs_returns_json_list(self) -> None:
        data = self._get("/api/frs")
        assert "frs" in data
        assert isinstance(data["frs"], list)

    def test_api_frs_contains_test_fr(self) -> None:
        data = self._get("/api/frs")
        ids = [f["id"] for f in data["frs"]]
        assert "FR-20260425-test" in ids

    def test_api_frs_stale_field_present(self) -> None:
        data = self._get("/api/frs")
        assert "stale" in data

    def test_cache_busted_root_serves_feature_request_board(self) -> None:
        url = f"http://127.0.0.1:{self._port}/?generation=probe"
        with urllib.request.urlopen(url, timeout=5) as response:
            html = response.read().decode("utf-8")

        assert "<title>⊕ Feature Request Board</title>" in html
        assert 'class="fr-card"' in html
        assert "Directory listing for" not in html

    def test_signoff_missing_fr_id_returns_400(self) -> None:
        status, body = self._post("/signoff", {})
        assert status == 400
        assert body["ok"] is False
        assert "fr_id" in body["error"]

    def test_signoff_invalid_json_returns_400(self) -> None:
        url = f"http://127.0.0.1:{self._port}/signoff"
        req = urllib.request.Request(
            url, data=b"not json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            data = json.loads(exc.read().decode("utf-8"))
            assert data["ok"] is False

    def test_signoff_calls_signoff_fr_when_valid(self) -> None:
        with patch.object(fr_server, "signoff_fr", return_value={"ok": True}) as mock_signoff:
            status, body = self._post("/signoff", {"fr_id": "FR-20260425-test"})
        assert status == 200
        assert body["ok"] is True
        mock_signoff.assert_called_once_with("FR-20260425-test")
