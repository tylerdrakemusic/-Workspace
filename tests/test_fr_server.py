"""
Tests for fr_server.py — FR Ledger Panel Server
"""
from __future__ import annotations

import json
import sys
import textwrap
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
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_REGISTRY = textwrap.dedent("""\
    # Feature Request Registry

    ## Active FRs

    | FR ID | Title | Type | Projects | State | Branch | PRs | Owner | Opened | Updated |
    |-------|-------|------|----------|-------|--------|-----|-------|--------|---------|
    | FR-20260425-live-fr-ledger-panel | Live FR Ledger Panel | feature | ⊕Workspace | BRANCHED | feature/workspace/live-fr-ledger-panel | [#23](https://github.com/tylerdrakemusic/-Workspace/pull/23) | ⊕workspace-ci | 2026-04-25 | 2026-04-25 |
    | FR-20260423-audio-brief-fix | Fix Audio Brief | fix | 👁AI-Manifest | REVIEW_REQUESTED | fix/ai-manifest/audio-brief | [#9](https://github.com/tylerdrakemusic/-Workspace/pull/9) | ⊕workspace-ci | 2026-04-23 | 2026-04-24 |
    | FR-20260422-old-feature | Old Feature | feature | ⊕Workspace | MERGED | main | — | ⊕workspace-overseer | 2026-04-22 | 2026-04-22 |
""")


@pytest.fixture()
def registry_file(tmp_path: Path) -> Path:
    f = tmp_path / "FEATURE_REQUESTS.md"
    f.write_text(SAMPLE_REGISTRY, encoding="utf-8")
    return f


# ─────────────────────────────────────────────────────────────────────────────
# parse_feature_requests
# ─────────────────────────────────────────────────────────────────────────────

class TestParseFRs:
    def test_returns_correct_count(self, registry_file: Path) -> None:
        frs = fr_server.parse_feature_requests(registry_file)
        assert len(frs) == 3

    def test_first_fr_fields(self, registry_file: Path) -> None:
        frs = fr_server.parse_feature_requests(registry_file)
        first = frs[0]
        assert first["id"] == "FR-20260425-live-fr-ledger-panel"
        assert first["state"] == "BRANCHED"
        assert first["is_active"] is True
        assert first["signoff_eligible"] is False  # BRANCHED not in signoff-eligible states

    def test_review_requested_fr_is_signoff_eligible(self, registry_file: Path) -> None:
        frs = fr_server.parse_feature_requests(registry_file)
        review_fr = next(f for f in frs if f["id"] == "FR-20260423-audio-brief-fix")
        assert review_fr["signoff_eligible"] is True
        assert review_fr["pr_number"] == 9

    def test_merged_fr_is_not_active(self, registry_file: Path) -> None:
        frs = fr_server.parse_feature_requests(registry_file)
        merged = next(f for f in frs if f["id"] == "FR-20260422-old-feature")
        assert merged["is_active"] is False

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        missing = tmp_path / "MISSING.md"
        frs = fr_server.parse_feature_requests(missing)
        assert frs == []

    def test_pr_number_extraction(self, registry_file: Path) -> None:
        frs = fr_server.parse_feature_requests(registry_file)
        first = frs[0]
        assert first["pr_number"] == 23

    def test_state_class_assigned(self, registry_file: Path) -> None:
        frs = fr_server.parse_feature_requests(registry_file)
        review_fr = next(f for f in frs if f["state"] == "REVIEW_REQUESTED")
        assert review_fr["state_class"] == "state-info"


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
            "signoff_eligible": True,
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

    def test_signoff_missing_pr_number_returns_400(self) -> None:
        status, body = self._post("/signoff", {"fr_id": "FR-20260425-test"})
        assert status == 400
        assert body["ok"] is False
        assert "pr_number" in body["error"]

    def test_signoff_missing_fr_id_returns_400(self) -> None:
        status, body = self._post("/signoff", {"pr_number": 42})
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

    def test_signoff_calls_approve_pr_when_valid(self) -> None:
        with patch.object(fr_server, "approve_pr", return_value={"ok": True}) as mock_approve:
            status, body = self._post("/signoff", {"fr_id": "FR-20260425-test", "pr_number": 42})
        assert status == 200
        assert body["ok"] is True
        mock_approve.assert_called_once_with(42, "FR-20260425-test")
