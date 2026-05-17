"""
Tests for fr_server.py — FR Ledger Panel Server
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any
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

    def test_merged_state_not_active(self) -> None:
        fr = _make_fr("FR-002", "MERGED")
        assert fr["is_active"] is False

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
) -> threading.Thread:
    import http.server as hs

    watcher = _MockWatcher(frs, stale)
    handler = fr_server._make_handler(watcher)  # type: ignore[attr-defined]
    server = hs.ThreadingHTTPServer(("127.0.0.1", port), handler)

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    # Give the server a moment to bind
    time.sleep(0.15)
    return t


class TestApiEndpoints:
    @pytest.fixture(autouse=True)
    def _server(self, tmp_path: Path) -> None:
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
        _start_test_server(self._port, [sample_fr])

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
