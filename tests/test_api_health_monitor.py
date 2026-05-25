"""Tests for src/utils/api_health_monitor.py — AC1–AC5."""
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "utils"))
import api_health_monitor as ahm


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mem_db() -> sqlite3.Connection:
    """In-memory DB with api_health table pre-created."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ahm.ensure_table(conn)
    return conn


def _mock_response(status_code: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    return r


# ── AC1: api_health table exists ──────────────────────────────────────────────

def test_ensure_table_creates_table():
    conn = sqlite3.connect(":memory:")
    ahm.ensure_table(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "api_health" in tables


def test_ensure_table_idempotent():
    conn = sqlite3.connect(":memory:")
    ahm.ensure_table(conn)
    ahm.ensure_table(conn)  # second call must not raise


def test_api_health_columns():
    conn = sqlite3.connect(":memory:")
    ahm.ensure_table(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(api_health)").fetchall()}
    assert {"id", "endpoint", "status", "latency_ms", "error_msg", "checked_at"} <= cols


# ── AC2: Lightweight ping per endpoint ───────────────────────────────────────

def test_ping_returns_up_on_200():
    ep = {
        "name": "elevenlabs",
        "label": "ElevenLabs",
        "url": "https://api.elevenlabs.io/v1/user",
        "auth_header": lambda: {"xi-api-key": "test"},
        "timeout": 8.0,
    }
    with patch.object(ahm.httpx, "get", return_value=_mock_response(200)):
        result = ahm._ping(ep)
    assert result["status"] == "up"
    assert result["latency_ms"] >= 0
    assert result["error_msg"] is None


def test_ping_returns_down_on_4xx():
    ep = {
        "name": "huggingface",
        "label": "HuggingFace",
        "url": "https://huggingface.co/api/whoami-v2",
        "auth_header": lambda: {"Authorization": "Bearer bad-token"},
        "timeout": 8.0,
    }
    with patch.object(ahm.httpx, "get", return_value=_mock_response(401)):
        result = ahm._ping(ep)
    assert result["status"] == "down"
    assert "401" in result["error_msg"]


# ── AC4: Failed pings write status=down + error_msg; never raise ─────────────

def test_ping_never_raises_on_exception():
    ep = {
        "name": "ollama",
        "label": "Ollama",
        "url": "http://localhost:11434/api/tags",
        "auth_header": lambda: {},
        "timeout": 4.0,
    }
    with patch.object(ahm.httpx, "get", side_effect=ConnectionRefusedError("refused")):
        result = ahm._ping(ep)  # must not raise
    assert result["status"] == "down"
    assert result["error_msg"] is not None


def test_run_pings_never_raises_even_on_exception(monkeypatch):
    monkeypatch.setattr(ahm.httpx, "get", MagicMock(side_effect=RuntimeError("boom")))
    conn = _mem_db()
    results = ahm.run_pings(conn)  # must not raise
    assert isinstance(results, list)
    assert all(r["status"] == "down" for r in results)


# ── AC2+AC3: run_pings writes rows and prunes to 30 ──────────────────────────

def test_run_pings_writes_three_rows():
    conn = _mem_db()
    with patch.object(ahm.httpx, "get", return_value=_mock_response(200)):
        results = ahm.run_pings(conn)
    assert len(results) == 3
    db_rows = conn.execute("SELECT COUNT(*) FROM api_health").fetchone()[0]
    assert db_rows == 3


def test_run_pings_endpoint_names():
    conn = _mem_db()
    with patch.object(ahm.httpx, "get", return_value=_mock_response(200)):
        results = ahm.run_pings(conn)
    names = [r["name"] for r in results]
    assert names == ["elevenlabs", "ollama", "huggingface"]


def test_run_pings_prunes_to_30_rows():
    conn = _mem_db()
    # Pre-insert 35 rows for 'elevenlabs'
    for _ in range(35):
        conn.execute(
            "INSERT INTO api_health (endpoint, status, latency_ms, checked_at) VALUES (?,?,?,datetime('now'))",
            ("elevenlabs", "up", 10.0),
        )
    conn.commit()
    # One more ping should leave exactly 30
    with patch.object(ahm.httpx, "get", return_value=_mock_response(200)):
        ahm.run_pings(conn)
    count = conn.execute(
        "SELECT COUNT(*) FROM api_health WHERE endpoint='elevenlabs'"
    ).fetchone()[0]
    assert count == 30


# ── AC5: get_latest_per_endpoint returns canonical order + unknown fallback ───

def test_get_latest_per_endpoint_canonical_order():
    conn = _mem_db()
    with patch.object(ahm.httpx, "get", return_value=_mock_response(200)):
        ahm.run_pings(conn)
    rows = ahm.get_latest_per_endpoint(conn)
    assert [r["name"] for r in rows] == ["elevenlabs", "ollama", "huggingface"]


def test_get_latest_per_endpoint_unknown_when_empty():
    conn = _mem_db()
    rows = ahm.get_latest_per_endpoint(conn)
    assert len(rows) == 3
    assert all(r["status"] == "unknown" for r in rows)


def test_get_latest_per_endpoint_returns_most_recent():
    conn = _mem_db()
    # Insert two rows for elevenlabs — second should win
    conn.execute(
        "INSERT INTO api_health (endpoint, status, latency_ms, error_msg, checked_at) VALUES (?,?,?,?,?)",
        ("elevenlabs", "down", 99.0, "HTTP 503", "2026-01-01T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO api_health (endpoint, status, latency_ms, error_msg, checked_at) VALUES (?,?,?,?,?)",
        ("elevenlabs", "up", 55.0, None, "2026-01-02T00:00:00Z"),
    )
    conn.commit()
    rows = ahm.get_latest_per_endpoint(conn)
    el = next(r for r in rows if r["name"] == "elevenlabs")
    assert el["status"] == "up"
    assert el["latency_ms"] == 55.0
