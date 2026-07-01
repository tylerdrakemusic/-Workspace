"""
migrate_fr_target_quarter.py — Additive schema migration for fr_ledgers.db

Adds a nullable `target_quarter` TEXT column (e.g. "2026-Q3") to the
`feature_requests` table. Manual override value used by roadmap_generator.py
when set; otherwise the generator computes a heuristic quarter.

Additive-only, backward compatible, and idempotent (safe to re-run against a
DB that already has the column).

Usage:
    C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\migrate_fr_target_quarter.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

COLUMN_NAME = "target_quarter"


def has_target_quarter_column(conn: sqlite3.Connection) -> bool:
    """Return True if feature_requests.target_quarter already exists."""
    rows = conn.execute("PRAGMA table_info(feature_requests)").fetchall()
    return any(row[1] == COLUMN_NAME for row in rows)


def migrate(conn: sqlite3.Connection) -> bool:
    """Add the nullable target_quarter column if it does not already exist.

    Returns True if the column was added, False if it already existed
    (no-op). Safe to call repeatedly.
    """
    if has_target_quarter_column(conn):
        return False
    conn.execute(f"ALTER TABLE feature_requests ADD COLUMN {COLUMN_NAME} TEXT")
    conn.commit()
    return True


def main() -> None:
    from init_fr_db import get_connection, init_db  # noqa: E402

    init_db()
    conn = get_connection()
    try:
        added = migrate(conn)
        if added:
            print(f"[migrate_fr_target_quarter] Added column: {COLUMN_NAME}")
        else:
            print(f"[migrate_fr_target_quarter] Column already present: {COLUMN_NAME} (no-op)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
