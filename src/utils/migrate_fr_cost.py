"""Additive migration for FR AI-credit and USD cost lifecycle fields."""
from __future__ import annotations

import sqlite3


COST_COLUMNS: dict[str, str] = {
    "ai_credits_estimated": "REAL",
    "usd_cost_estimated": "REAL",
    "cost_status": "TEXT",
    "cost_source": "TEXT",
    "cost_baseline_json": "TEXT",
    "cost_finalized_at": "TEXT",
    "cost_reconciliation_status": "TEXT",
    "cost_reconciled_at": "TEXT",
    "cost_pricing_source_url": "TEXT",
    "cost_pricing_version": "TEXT",
    "cost_pricing_effective_date": "TEXT",
    "cost_rate_snapshot_json": "TEXT",
}


def migrate(conn: sqlite3.Connection) -> None:
    """Add missing cost columns without changing existing FR rows."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(feature_requests)")}
    for name, column_type in COST_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE feature_requests ADD COLUMN {name} {column_type}")  # nosec B608
    conn.commit()