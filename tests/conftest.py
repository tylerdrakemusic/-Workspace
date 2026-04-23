"""Shared pytest fixtures for ⊕Workspace tests."""
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))


# Schema mirrors src/utils/init_db.py (SQLCipher stripped — plain sqlite for tests).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS perf_runs (
    run_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
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
    def _insert(run_id=None, name="test", started_at=None, ended_at=None, status=None, detail=None, last_heartbeat=None):
        rid = run_id or _pid()
        started = started_at if started_at is not None else time.time()
        db_conn.execute(
            "INSERT INTO perf_runs (run_id, name, started_at, ended_at, status, detail, last_heartbeat) VALUES (?,?,?,?,?,?,?)",
            (rid, name, started, ended_at, status, detail, last_heartbeat),
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
