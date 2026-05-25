"""Tests for perf_regression_alerter.py

FR: FR-20260525-perf-regression-alerter
"""
from __future__ import annotations

import sqlite3
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

import perf_regression_alerter as pra  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_conn() -> sqlite3.Connection:
    """Fresh in-memory DB with the perf_runs + proof_artifacts schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE perf_runs (
            run_id         TEXT PRIMARY KEY,
            name           TEXT NOT NULL,
            agent          TEXT,
            started_at     REAL NOT NULL,
            ended_at       REAL,
            status         TEXT,
            detail         TEXT,
            last_heartbeat REAL
        );
        CREATE TABLE proof_artifacts (
            proof_id      TEXT PRIMARY KEY,
            run_id        TEXT,
            agent         TEXT NOT NULL,
            proof_type    TEXT NOT NULL,
            description   TEXT NOT NULL,
            artifact_path TEXT,
            artifact_hash TEXT,
            verified      INTEGER NOT NULL DEFAULT 0,
            verified_at   TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    return conn


def _insert_run(
    conn: sqlite3.Connection,
    agent: str,
    elapsed_s: float,
    status: str = "ok",
    days_ago: float = 1.0,
) -> None:
    """Insert a completed perf_run WINDOW_DAYS - days_ago seconds ago."""
    started = time.time() - days_ago * 86400
    ended = started + elapsed_s
    conn.execute(
        "INSERT INTO perf_runs (run_id, name, agent, started_at, ended_at, status) VALUES (?,?,?,?,?,?)",
        (uuid.uuid4().hex[:12], f"{agent}: task", agent, started, ended, status),
    )
    conn.commit()


def _alerter_with_conn(conn: sqlite3.Connection, dry_run: bool = False) -> int:
    """Run the alerter against a provided connection (bypasses init_db).

    Note: run_alerter closes the connection when done. Do not use `conn`
    after this call returns — open a new connection to inspect results.
    """
    with patch("perf_regression_alerter._conn", return_value=conn):
        return pra.run_alerter(dry_run=dry_run)


def _make_file_conn(path: Path) -> sqlite3.Connection:
    """Open (or create) a file-backed test DB with the required schema."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS perf_runs (
            run_id         TEXT PRIMARY KEY,
            name           TEXT NOT NULL,
            agent          TEXT,
            started_at     REAL NOT NULL,
            ended_at       REAL,
            status         TEXT,
            detail         TEXT,
            last_heartbeat REAL
        );
        CREATE TABLE IF NOT EXISTS proof_artifacts (
            proof_id      TEXT PRIMARY KEY,
            run_id        TEXT,
            agent         TEXT NOT NULL,
            proof_type    TEXT NOT NULL,
            description   TEXT NOT NULL,
            artifact_path TEXT,
            artifact_hash TEXT,
            verified      INTEGER NOT NULL DEFAULT 0,
            verified_at   TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    return conn


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestNoData:
    def test_empty_db_returns_zero(self):
        conn = _make_conn()
        assert _alerter_with_conn(conn, dry_run=True) == 0

    def test_below_floor_no_alert(self):
        conn = _make_conn()
        for i in range(pra.MIN_BASELINE_RUNS - 1):
            _insert_run(conn, "⊕workspace-qa", elapsed_s=100.0, days_ago=i + 1)
        assert _alerter_with_conn(conn, dry_run=True) == 0


class TestRegressionDetection:
    def test_regression_above_threshold_flagged(self):
        conn = _make_conn()
        agent = "⊕workspace-qa"
        # 10 baseline runs at ~100s
        for i in range(10):
            _insert_run(conn, agent, elapsed_s=100.0, days_ago=i + 5)
        # 3 most-recent runs at 250s = 2.5x median → regression
        for i in range(3):
            _insert_run(conn, agent, elapsed_s=250.0, days_ago=i + 1)
        assert _alerter_with_conn(conn, dry_run=True) == 1

    def test_exactly_at_threshold_flagged(self):
        conn = _make_conn()
        agent = "⊕workspace-intake"
        for i in range(10):
            _insert_run(conn, agent, elapsed_s=100.0, days_ago=i + 5)
        for i in range(3):
            _insert_run(conn, agent, elapsed_s=200.0, days_ago=i + 1)  # exactly 2.0x
        assert _alerter_with_conn(conn, dry_run=True) == 1

    def test_below_threshold_no_alert(self):
        conn = _make_conn()
        agent = "⊕workspace-qa"
        for i in range(10):
            _insert_run(conn, agent, elapsed_s=100.0, days_ago=i + 5)
        for i in range(3):
            _insert_run(conn, agent, elapsed_s=190.0, days_ago=i + 1)  # 1.9x < 2.0
        assert _alerter_with_conn(conn, dry_run=True) == 0

    def test_multiple_agents_one_regressing(self):
        conn = _make_conn()
        # healthy agent
        for i in range(10):
            _insert_run(conn, "⊕workspace-qa", elapsed_s=100.0, days_ago=i + 2)
        for i in range(3):
            _insert_run(conn, "⊕workspace-qa", elapsed_s=110.0, days_ago=i + 1)
        # regressing agent
        for i in range(10):
            _insert_run(conn, "⊕workspace-intake", elapsed_s=200.0, days_ago=i + 5)
        for i in range(3):
            _insert_run(conn, "⊕workspace-intake", elapsed_s=600.0, days_ago=i + 1)
        assert _alerter_with_conn(conn, dry_run=True) == 1


class TestDryRun:
    def test_dry_run_writes_no_rows(self, tmp_path):
        db = tmp_path / "test.db"
        conn = _make_file_conn(db)
        agent = "⊕workspace-qa"
        for i in range(10):
            _insert_run(conn, agent, elapsed_s=100.0, days_ago=i + 5)
        for i in range(3):
            _insert_run(conn, agent, elapsed_s=300.0, days_ago=i + 1)
        _alerter_with_conn(conn, dry_run=True)  # conn is closed after this
        conn2 = sqlite3.connect(str(db))
        rows = conn2.execute("SELECT COUNT(*) FROM proof_artifacts").fetchone()[0]
        conn2.close()
        assert rows == 0

    def test_live_run_writes_alert_row(self, tmp_path):
        db = tmp_path / "test.db"
        conn = _make_file_conn(db)
        agent = "⊕workspace-qa"
        for i in range(10):
            _insert_run(conn, agent, elapsed_s=100.0, days_ago=i + 5)
        for i in range(3):
            _insert_run(conn, agent, elapsed_s=300.0, days_ago=i + 1)
        _alerter_with_conn(conn, dry_run=False)
        conn2 = sqlite3.connect(str(db))
        conn2.row_factory = sqlite3.Row
        row = conn2.execute(
            "SELECT * FROM proof_artifacts WHERE proof_type='perf_regression_alert'"
        ).fetchone()
        conn2.close()
        assert row is not None
        assert row["agent"] == agent
        assert "regression" in row["description"]

    def test_live_run_writes_low_data_row(self, tmp_path):
        db = tmp_path / "test.db"
        conn = _make_file_conn(db)
        agent = "⊕workspace-discovery"
        for i in range(2):
            _insert_run(conn, agent, elapsed_s=100.0, days_ago=i + 1)
        _alerter_with_conn(conn, dry_run=False)
        conn2 = sqlite3.connect(str(db))
        conn2.row_factory = sqlite3.Row
        row = conn2.execute(
            "SELECT * FROM proof_artifacts WHERE proof_type='perf_low_data' AND agent=?",
            (agent,),
        ).fetchone()
        conn2.close()
        assert row is not None
        assert "min" in row["description"]

    def test_live_run_writes_own_perf_run(self, tmp_path):
        db = tmp_path / "test.db"
        conn = _make_file_conn(db)
        _alerter_with_conn(conn, dry_run=False)
        conn2 = sqlite3.connect(str(db))
        conn2.row_factory = sqlite3.Row
        row = conn2.execute(
            "SELECT * FROM perf_runs WHERE agent=?", (pra.ALERTER_AGENT,)
        ).fetchone()
        conn2.close()
        assert row is not None
        assert row["status"] == "ok"
        assert row["ended_at"] is not None


class TestNonOkRunsExcluded:
    def test_error_runs_not_counted_in_baseline(self):
        conn = _make_conn()
        agent = "⊕workspace-qa"
        # 4 ok runs + 10 error runs — should not qualify (< MIN_BASELINE_RUNS ok)
        for i in range(4):
            _insert_run(conn, agent, elapsed_s=100.0, status="ok", days_ago=i + 1)
        for i in range(10):
            _insert_run(conn, agent, elapsed_s=500.0, status="error", days_ago=i + 1)
        assert _alerter_with_conn(conn, dry_run=True) == 0
