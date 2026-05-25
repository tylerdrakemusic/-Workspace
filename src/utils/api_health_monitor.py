"""API endpoint health monitor for ⊕Workspace.

Pings ElevenLabs, Ollama, and HuggingFace at portal-generation time.
Results are written to the api_health table in workspace.db.

Usage (called from dashboard_portal.py at generation time)::

    from src.utils.api_health_monitor import run_pings, get_latest_per_endpoint

    conn = get_connection()
    rows = run_pings(conn)          # pings all 3, writes to DB, prunes old rows
    rows = get_latest_per_endpoint(conn)  # reads latest row per endpoint from DB
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Endpoint definitions
# ---------------------------------------------------------------------------

_ENDPOINTS: list[dict[str, Any]] = [
    {
        "name": "elevenlabs",
        "label": "ElevenLabs",
        "url": "https://api.elevenlabs.io/v1/user",
        "auth_header": lambda: {"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "")},
        "timeout": 8.0,
    },
    {
        "name": "ollama",
        "label": "Ollama",
        "url": "http://localhost:11434/api/tags",
        "auth_header": lambda: {},
        "timeout": 4.0,
    },
    {
        "name": "huggingface",
        "label": "HuggingFace",
        "url": "https://huggingface.co/api/whoami-v2",
        "auth_header": lambda: {"Authorization": f"Bearer {os.environ.get('HF_TOKEN', '')}"},
        "timeout": 8.0,
    },
]

_RETAIN_ROWS = 30  # max rows per endpoint


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def ensure_table(conn) -> None:
    """Create api_health table and index if they do not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_health (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            endpoint   TEXT    NOT NULL,
            status     TEXT    NOT NULL CHECK(status IN ('up', 'down')),
            latency_ms REAL,
            error_msg  TEXT,
            checked_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_health_ep ON api_health(endpoint, checked_at)"
    )
    conn.commit()


def _prune(conn, endpoint: str) -> None:
    """Delete rows beyond the last _RETAIN_ROWS for this endpoint."""
    conn.execute(
        """
        DELETE FROM api_health
        WHERE endpoint = ?
          AND id NOT IN (
              SELECT id FROM api_health
              WHERE endpoint = ?
              ORDER BY id DESC
              LIMIT ?
          )
        """,
        (endpoint, endpoint, _RETAIN_ROWS),
    )


# ---------------------------------------------------------------------------
# Ping
# ---------------------------------------------------------------------------

def _ping(ep: dict[str, Any]) -> dict[str, Any]:
    """Ping a single endpoint. Never raises — failed pings return status='down'."""
    headers = ep["auth_header"]()
    t0 = time.monotonic()
    try:
        r = httpx.get(ep["url"], headers=headers, timeout=ep["timeout"], follow_redirects=True)
        latency_ms = (time.monotonic() - t0) * 1000
        if r.status_code < 400:
            return {"status": "up", "latency_ms": round(latency_ms, 1), "error_msg": None}
        return {
            "status": "down",
            "latency_ms": round(latency_ms, 1),
            "error_msg": f"HTTP {r.status_code}",
        }
    except Exception as exc:  # noqa: BLE001
        latency_ms = (time.monotonic() - t0) * 1000
        return {
            "status": "down",
            "latency_ms": round(latency_ms, 1),
            "error_msg": str(exc)[:200],
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_pings(conn) -> list[dict[str, Any]]:
    """Ping all endpoints, write rows to DB, prune old rows.

    Returns list of result dicts (one per endpoint, canonical order).
    Never raises.
    """
    ensure_table(conn)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results: list[dict[str, Any]] = []

    for ep in _ENDPOINTS:
        result = _ping(ep)
        conn.execute(
            """
            INSERT INTO api_health (endpoint, status, latency_ms, error_msg, checked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ep["name"], result["status"], result["latency_ms"], result["error_msg"], now),
        )
        _prune(conn, ep["name"])
        conn.commit()
        results.append({"name": ep["name"], "label": ep["label"], **result, "checked_at": now})

    return results


def get_latest_per_endpoint(conn) -> list[dict[str, Any]]:
    """Return the latest DB row per endpoint in canonical order.

    Falls back to ``status='unknown'`` for endpoints with no data yet.
    """
    ensure_table(conn)

    rows_by_name: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        """
        SELECT endpoint, status, latency_ms, error_msg, checked_at
        FROM api_health
        WHERE id IN (
            SELECT MAX(id) FROM api_health GROUP BY endpoint
        )
        """
    ).fetchall():
        rows_by_name[row[0]] = {
            "name": row[0],
            "status": row[1],
            "latency_ms": row[2],
            "error_msg": row[3],
            "checked_at": row[4],
        }

    out: list[dict[str, Any]] = []
    for ep in _ENDPOINTS:
        row = rows_by_name.get(
            ep["name"],
            {
                "name": ep["name"],
                "status": "unknown",
                "latency_ms": None,
                "error_msg": None,
                "checked_at": None,
            },
        )
        out.append({"label": ep["label"], **row})
    return out
