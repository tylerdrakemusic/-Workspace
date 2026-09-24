"""Database loading for roadmap source records."""
from __future__ import annotations

import sqlite3

ACTIVE_FR_STATES = {
    "OPEN", "TRIAGED", "BRANCHED", "IN_PROGRESS", "CHANGES_REQUESTED",
    "FUNCTIONAL_QA", "ARCHITECTURE_REVIEW", "REVIEW_REQUESTED", "AUTO_REVIEWED",
    "TYLER_APPROVED", "BRANCH_CHECKED_OUT",
}


def fetch_active_frs(conn: sqlite3.Connection) -> list[dict[str, object]]:
    placeholders = ",".join("?" * len(ACTIVE_FR_STATES))
    rows = conn.execute(
        f"SELECT * FROM feature_requests WHERE state IN ({placeholders})",  # nosec B608
        list(ACTIVE_FR_STATES),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_open_todos(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = conn.execute("SELECT * FROM todos WHERE done = 0").fetchall()
    return [dict(row) for row in rows]