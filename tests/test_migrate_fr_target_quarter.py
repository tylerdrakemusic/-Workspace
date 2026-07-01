"""Tests for migrate_fr_target_quarter.py — additive, idempotent schema migration."""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "utils"))

from migrate_fr_target_quarter import has_target_quarter_column, migrate  # noqa: E402

_BASE_SCHEMA = """
CREATE TABLE feature_requests (
    id                  TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    type                TEXT NOT NULL,
    risk                TEXT,
    projects            TEXT,
    state               TEXT NOT NULL DEFAULT 'OPEN',
    opened_at           TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    acceptance_criteria TEXT,
    concurrency_notes   TEXT
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_BASE_SCHEMA)
    c.execute(
        "INSERT INTO feature_requests (id, title, type, risk, projects, state, opened_at, updated_at) "
        "VALUES ('FR-20260101-existing', 'Existing FR', 'feature', 'low', 'workspace', 'OPEN', "
        "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    c.commit()
    yield c
    c.close()


def test_column_absent_before_migration(conn):
    assert has_target_quarter_column(conn) is False


def test_migrate_adds_column(conn):
    added = migrate(conn)
    assert added is True
    assert has_target_quarter_column(conn) is True


def test_migrate_is_idempotent(conn):
    first = migrate(conn)
    second = migrate(conn)
    assert first is True
    assert second is False  # no-op on re-run
    assert has_target_quarter_column(conn) is True


def test_existing_rows_unaffected_and_column_defaults_null(conn):
    migrate(conn)
    row = conn.execute(
        "SELECT id, title, risk, target_quarter FROM feature_requests WHERE id='FR-20260101-existing'"
    ).fetchone()
    assert row["id"] == "FR-20260101-existing"
    assert row["title"] == "Existing FR"
    assert row["risk"] == "low"
    assert row["target_quarter"] is None


def test_migrate_preserves_row_count(conn):
    before = conn.execute("SELECT COUNT(*) FROM feature_requests").fetchone()[0]
    migrate(conn)
    after = conn.execute("SELECT COUNT(*) FROM feature_requests").fetchone()[0]
    assert before == after == 1


def test_can_set_target_quarter_manually_after_migration(conn):
    migrate(conn)
    conn.execute(
        "UPDATE feature_requests SET target_quarter='2026-Q4' WHERE id='FR-20260101-existing'"
    )
    conn.commit()
    row = conn.execute(
        "SELECT target_quarter FROM feature_requests WHERE id='FR-20260101-existing'"
    ).fetchone()
    assert row["target_quarter"] == "2026-Q4"
