"""Add versioned acceptance-criteria storage to the FR ledger."""
from __future__ import annotations

import hashlib
import json
import sqlite3


def criteria_content_hash(criteria: object) -> str:
    """Return a stable SHA-256 hash for JSON-compatible criteria content."""
    canonical = json.dumps(criteria, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def migrate(conn: sqlite3.Connection) -> None:
    """Add current-version fields and an immutable prior-criteria history table."""
    existing_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(feature_requests)")
    }
    if "criteria_version" not in existing_columns:
        conn.execute(
            "ALTER TABLE feature_requests ADD COLUMN criteria_version INTEGER NOT NULL DEFAULT 0"
        )
    if "criteria_hash" not in existing_columns:
        conn.execute("ALTER TABLE feature_requests ADD COLUMN criteria_hash TEXT")

    artifact_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(fr_artifacts)")
    }
    if "criteria_version" not in artifact_columns:
        conn.execute("ALTER TABLE fr_artifacts ADD COLUMN criteria_version INTEGER")
    if "criteria_hash" not in artifact_columns:
        conn.execute("ALTER TABLE fr_artifacts ADD COLUMN criteria_hash TEXT")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS fr_criteria_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fr_id TEXT NOT NULL REFERENCES feature_requests(id),
            version INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            approver TEXT NOT NULL,
            event_id INTEGER NOT NULL REFERENCES fr_events(id),
            rationale TEXT NOT NULL,
            UNIQUE(fr_id, version)
        );

        CREATE INDEX IF NOT EXISTS idx_criteria_history_fr
            ON fr_criteria_history(fr_id, version);

        CREATE TRIGGER IF NOT EXISTS trg_criteria_history_no_update
        BEFORE UPDATE ON fr_criteria_history
        BEGIN
            SELECT RAISE(ABORT, 'criteria history is append-only');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_criteria_history_no_delete
        BEFORE DELETE ON fr_criteria_history
        BEGIN
            SELECT RAISE(ABORT, 'criteria history is append-only');
        END;
        """
    )

    rows = conn.execute(
        "SELECT id, acceptance_criteria, criteria_version, criteria_hash "
        "FROM feature_requests"
    ).fetchall()
    for row in rows:
        content = row[1]
        if content is None:
            if row[2] != 0 or row[3] is not None:
                conn.execute(
                    "UPDATE feature_requests SET criteria_version=0, criteria_hash=NULL WHERE id=?",
                    (row[0],),
                )
            continue
        try:
            parsed_content = json.loads(content)
            content_hash = criteria_content_hash(parsed_content)
        except (TypeError, json.JSONDecodeError):
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        version = row[2] if row[2] and row[2] > 0 else 1
        if row[2] != version or row[3] != content_hash:
            conn.execute(
                "UPDATE feature_requests SET criteria_version=?, criteria_hash=? WHERE id=?",
                (version, content_hash, row[0]),
            )
    conn.commit()