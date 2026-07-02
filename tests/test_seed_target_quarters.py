"""Tests for seed_target_quarters.py — one-time bulk seed of target_quarter
for currently-open/active FRs (AC3 of BFX-20260701-roadmap-tab-follow-up)."""
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "utils"))

from seed_target_quarters import seed_target_quarters  # noqa: E402


_SCHEMA = """
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
    concurrency_notes   TEXT,
    target_quarter      TEXT
);
"""


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    c.executemany(
        "INSERT INTO feature_requests "
        "(id, title, type, risk, projects, state, opened_at, updated_at, target_quarter) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("FR-20260101-old-active", "Old active low-risk", "feature", "low", "workspace",
             "FUNCTIONAL_QA", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", None),
            ("FR-20260625-new-active", "New active high-risk", "feature", "high", "workspace",
             "OPEN", "2026-06-25T00:00:00Z", "2026-06-25T00:00:00Z", None),
            ("FR-20260101-already-seeded", "Already has a quarter", "feature", "low", "music",
             "OPEN", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "2026-Q4"),
            ("FR-20260101-done", "Finished work, not active", "feature", "low", "quantum",
             "DONE", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", None),
        ],
    )
    c.commit()
    yield c
    c.close()


def test_seed_assigns_quarters_to_active_frs_with_null_target_quarter(conn):
    today = date(2026, 6, 30)
    updated = seed_target_quarters(conn, today=today)
    updated_ids = {row["id"] for row in updated}
    assert updated_ids == {"FR-20260101-old-active", "FR-20260625-new-active"}
    for row in updated:
        assert row["target_quarter"]


def test_seed_writes_quarters_back_to_db(conn):
    seed_target_quarters(conn, today=date(2026, 6, 30))
    row = conn.execute(
        "SELECT target_quarter FROM feature_requests WHERE id='FR-20260101-old-active'"
    ).fetchone()
    assert row["target_quarter"] is not None


def test_seed_does_not_touch_already_seeded_rows(conn):
    seed_target_quarters(conn, today=date(2026, 6, 30))
    row = conn.execute(
        "SELECT target_quarter FROM feature_requests WHERE id='FR-20260101-already-seeded'"
    ).fetchone()
    assert row["target_quarter"] == "2026-Q4"


def test_seed_ignores_non_active_states(conn):
    seed_target_quarters(conn, today=date(2026, 6, 30))
    row = conn.execute(
        "SELECT target_quarter FROM feature_requests WHERE id='FR-20260101-done'"
    ).fetchone()
    assert row["target_quarter"] is None


def test_seed_is_idempotent_on_rerun(conn):
    first_pass = seed_target_quarters(conn, today=date(2026, 6, 30))
    assert len(first_pass) == 2
    second_pass = seed_target_quarters(conn, today=date(2026, 6, 30))
    assert second_pass == []


def test_seed_leaves_column_overridable_afterward(conn):
    seed_target_quarters(conn, today=date(2026, 6, 30))
    conn.execute(
        "UPDATE feature_requests SET target_quarter='2027-Q1' WHERE id='FR-20260101-old-active'"
    )
    conn.commit()
    row = conn.execute(
        "SELECT target_quarter FROM feature_requests WHERE id='FR-20260101-old-active'"
    ).fetchone()
    assert row["target_quarter"] == "2027-Q1"


def test_seed_heuristic_matches_assign_quarter_logic(conn):
    """Seed uses the same assign_quarter() heuristic as roadmap_generator, so
    low-risk/advanced-state/old FRs land earlier than high-risk/new ones."""
    updated = seed_target_quarters(conn, today=date(2026, 6, 30))
    by_id = {row["id"]: row["target_quarter"] for row in updated}

    def _q_index(q):
        year, qn = q.split("-Q")
        return int(year) * 4 + int(qn)

    assert _q_index(by_id["FR-20260101-old-active"]) <= _q_index(by_id["FR-20260625-new-active"])
