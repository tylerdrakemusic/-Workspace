"""Shared pytest fixtures for ⊕Workspace tests."""
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

PORTAL_HTML = PROJECT_ROOT / "reports" / "portal.html"


@pytest.fixture(scope="session", autouse=True)
def ensure_portal_html() -> None:
    """Generate reports/portal.html if it doesn't exist (CI has no tracked copy)."""
    if not PORTAL_HTML.is_file():
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "dashboard_portal.py"), "--no-open"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
        )
        if result.returncode != 0 or not PORTAL_HTML.is_file():
            import warnings
            warnings.warn(
                f"portal.html generation failed (exit {result.returncode}); "
                "portal-reading tests will be skipped.\n"
                + result.stderr.decode(errors="replace"),
                stacklevel=2,
            )


@pytest.fixture(autouse=True)
def backup_manifest_key(monkeypatch):
    """Give backup tests an ephemeral signing key without persisting key material."""
    monkeypatch.setenv("WORKSPACE_BACKUP_MANIFEST_KEY", "test-only-ephemeral-key")


def pytest_collection_modifyitems(config, items):
    """Skip playwright-marked tests unless PLAYWRIGHT_ENABLED=1 is set."""
    if os.getenv("PLAYWRIGHT_ENABLED") != "1":
        skip = pytest.mark.skip(reason="Set PLAYWRIGHT_ENABLED=1 to run Playwright tests")
        for item in items:
            if item.get_closest_marker("playwright"):
                item.add_marker(skip)


# Schema mirrors src/utils/init_db.py (SQLCipher stripped — plain sqlite for tests).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS perf_runs (
    run_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    agent           TEXT,
    started_at      REAL NOT NULL,
    ended_at        REAL,
    status          TEXT,
    detail          TEXT,
    last_heartbeat  REAL
);

CREATE TABLE IF NOT EXISTS perf_steps (
    step_id     TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES perf_runs(run_id),
    agent       TEXT NOT NULL,
    description TEXT,
    started_at  REAL NOT NULL,
    ended_at    REAL,
    elapsed_ms  REAL,
    status      TEXT,
    detail      TEXT
);

CREATE TABLE IF NOT EXISTS proof_artifacts (
    proof_id      TEXT PRIMARY KEY,
    run_id        TEXT REFERENCES perf_runs(run_id),
    agent         TEXT NOT NULL,
    proof_type    TEXT NOT NULL,
    description   TEXT NOT NULL,
    artifact_path TEXT,
    artifact_hash TEXT,
    verified      INTEGER NOT NULL DEFAULT 0,
    verified_at   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vulnerabilities (
    vuln_id        TEXT PRIMARY KEY,
    scan_date      TEXT NOT NULL,
    category       TEXT NOT NULL,
    severity       TEXT NOT NULL,
    file_path      TEXT,
    line_number    INTEGER,
    description    TEXT NOT NULL,
    owasp_id       TEXT,
    status         TEXT NOT NULL DEFAULT 'open',
    override_note  TEXT,
    remediated_at  TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scan_run_log (
    run_id           TEXT PRIMARY KEY,
    started_at       TEXT NOT NULL,
    completed_at     TEXT,
    projects_scanned TEXT NOT NULL DEFAULT '[]',
    new_vulns_count  INTEGER NOT NULL DEFAULT 0,
    total_findings   INTEGER NOT NULL DEFAULT 0,
    bandit_exit_code INTEGER,
    safety_exit_code INTEGER,
    status           TEXT NOT NULL DEFAULT 'ok',
    error_detail     TEXT
);

CREATE TABLE IF NOT EXISTS api_health (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint   TEXT    NOT NULL,
    status     TEXT    NOT NULL,
    latency_ms REAL,
    error_msg  TEXT,
    checked_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


@pytest.fixture
def db_conn():
    """Fresh in-memory DB that mirrors the workspace.db schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    yield conn
    conn.close()


def _pid() -> str:
    return uuid.uuid4().hex[:12]


@pytest.fixture
def insert_run(db_conn):
    """Factory to insert a perf_run row."""
    def _insert(run_id=None, name="test", started_at=None, ended_at=None, status=None, detail=None, last_heartbeat=None, agent=None):
        rid = run_id or _pid()
        started = started_at if started_at is not None else time.time()
        db_conn.execute(
            "INSERT INTO perf_runs (run_id, name, agent, started_at, ended_at, status, detail, last_heartbeat) VALUES (?,?,?,?,?,?,?,?)",
            (rid, name, agent, started, ended_at, status, detail, last_heartbeat),
        )
        db_conn.commit()
        return rid
    return _insert


@pytest.fixture
def insert_proof(db_conn):
    """Factory to insert a proof_artifact row."""
    def _insert(run_id=None, agent="⊕workspace-doer", proof_type="file_modified",
                description="desc", artifact_path=None, verified=0, created_at=None):
        pid = _pid()
        db_conn.execute(
            """INSERT INTO proof_artifacts
               (proof_id, run_id, agent, proof_type, description, artifact_path, verified, created_at)
               VALUES (?,?,?,?,?,?,?, COALESCE(?, datetime('now')))""",
            (pid, run_id, agent, proof_type, description, artifact_path, verified, created_at),
        )
        db_conn.commit()
        return pid
    return _insert
