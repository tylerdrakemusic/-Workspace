"""seed_target_quarters.py — one-time bulk seed of `target_quarter` for
currently open/active FRs (AC3 of BFX-20260701-roadmap-tab-follow-up).

Unlike roadmap_generator.assign_quarter(), which computes a target quarter
at read-time for display, this script WRITES the computed value back into
`feature_requests.target_quarter` for rows where it is currently NULL. This
lets Tyler (or future automation) manually override individual FRs afterward
without this script clobbering them on re-run.

Usage:
    C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\seed_target_quarters.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from roadmap_generator import ACTIVE_FR_STATES, assign_quarter  # noqa: E402


def seed_target_quarters(
    conn: sqlite3.Connection, today: date | None = None
) -> list[dict[str, Any]]:
    """Assign and persist `target_quarter` for active FRs where it is NULL.

    Only rows whose `state` is in ACTIVE_FR_STATES and whose `target_quarter`
    IS NULL are touched — idempotent by construction (a re-run finds no
    matching rows and updates nothing). Returns the list of rows that were
    updated, each as a dict with at least `id` and `target_quarter`.
    """
    placeholders = ",".join("?" * len(ACTIVE_FR_STATES))
    rows = conn.execute(
        f"SELECT * FROM feature_requests WHERE state IN ({placeholders}) "  # nosec B608
        "AND target_quarter IS NULL",
        list(ACTIVE_FR_STATES),
    ).fetchall()

    updated: list[dict[str, Any]] = []
    for row in rows:
        fr = dict(row)
        quarter = assign_quarter(fr, today=today)
        conn.execute(
            "UPDATE feature_requests SET target_quarter = ? WHERE id = ?",
            (quarter, fr["id"]),
        )
        fr["target_quarter"] = quarter
        updated.append(fr)

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk-seed target_quarter for active FRs with no value set"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Compute assignments without writing to the database",
    )
    args = parser.parse_args()

    from init_fr_db import get_connection, init_db  # noqa: E402

    init_db()
    conn = get_connection()
    try:
        updated = seed_target_quarters(conn)
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()
    finally:
        conn.close()

    print(f"[seed_target_quarters] {'Would assign' if args.dry_run else 'Assigned'} "
          f"target_quarter to {len(updated)} FR(s).")
    for fr in updated:
        print(f"  {fr['id']}: {fr['target_quarter']}")


if __name__ == "__main__":
    main()
