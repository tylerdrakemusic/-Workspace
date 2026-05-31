#!/usr/bin/env python3
"""
⊕ Migration: Add 'stale' to vulnerabilities.status CHECK constraint.

The original schema constrains status to:
  ('open', 'remediated', 'accepted', 'false_positive')

This migration rebuilds the table to extend that list to include 'stale'.
The migration is idempotent — safe to run multiple times.

Usage:
  C:\\G\\python.exe tools/migrate_add_stale_status.py

FR-20260530-stale-vuln-dedup-report
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))


def migrate(conn) -> None:
    """Add 'stale' to the status CHECK constraint on the vulnerabilities table.

    Idempotent: if 'stale' is already in the constraint (or if the table uses
    no CHECK constraint), this function is a no-op.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='vulnerabilities'"
    ).fetchone()
    if not row:
        # Table doesn't exist yet; init_db will create it with the correct schema.
        return

    schema_sql: str = row[0] or ""

    # Already migrated — 'stale' is in the constraint.
    if "'stale'" in schema_sql:
        return

    # Rebuild the table with the extended CHECK constraint.
    conn.execute("SAVEPOINT add_stale_status")
    try:
        conn.execute("ALTER TABLE vulnerabilities RENAME TO _vulnerabilities_pre_stale")
        conn.execute("""
            CREATE TABLE vulnerabilities (
                vuln_id        TEXT PRIMARY KEY,
                scan_date      TEXT NOT NULL,
                category       TEXT NOT NULL,
                severity       TEXT NOT NULL CHECK(severity IN ('critical','high','medium','low','info')),
                file_path      TEXT,
                line_number    INTEGER,
                description    TEXT NOT NULL,
                owasp_id       TEXT,
                status         TEXT NOT NULL DEFAULT 'open'
                               CHECK(status IN ('open','remediated','accepted','false_positive','stale')),
                override_note  TEXT,
                remediated_at  TEXT,
                created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            INSERT INTO vulnerabilities
            SELECT vuln_id, scan_date, category, severity, file_path, line_number,
                   description, owasp_id, status, override_note, remediated_at, created_at
            FROM _vulnerabilities_pre_stale
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vuln_status ON vulnerabilities(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vuln_severity ON vulnerabilities(severity)")
        conn.execute("DROP TABLE _vulnerabilities_pre_stale")
        conn.execute("RELEASE SAVEPOINT add_stale_status")
        conn.commit()
        print("  Migration complete: 'stale' added to vulnerabilities.status CHECK constraint.")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT add_stale_status")
        raise


def main() -> int:
    from init_db import get_connection, init_db  # noqa: PLC0415
    init_db()
    conn = get_connection()
    try:
        migrate(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
