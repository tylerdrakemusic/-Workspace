from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "utils"))

from migrate_fr_criteria_versions import migrate  # noqa: E402


@pytest.fixture
def legacy_ledger() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE feature_requests (
            id TEXT PRIMARY KEY,
            acceptance_criteria TEXT
        );
        CREATE TABLE fr_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fr_id TEXT NOT NULL
        );
        CREATE TABLE fr_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fr_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL
        );
        """
    )
    criteria = {
        "acceptance_criteria": [
            {"given": "a context", "when": "an action occurs", "then": "a result is visible"}
        ]
    }
    connection.execute(
        "INSERT INTO feature_requests (id, acceptance_criteria) VALUES (?, ?)",
        ("FR-LEGACY", json.dumps(criteria, ensure_ascii=False)),
    )
    connection.execute(
        "INSERT INTO feature_requests (id, acceptance_criteria) VALUES (?, NULL)",
        ("FR-EMPTY",),
    )
    connection.commit()
    yield connection
    connection.close()


def test_migration_backfills_legacy_criteria_identity_and_empty_rows(
    legacy_ledger: sqlite3.Connection,
) -> None:
    migrate(legacy_ledger)

    rows = {
        row["id"]: row
        for row in legacy_ledger.execute(
            "SELECT id, acceptance_criteria, criteria_version, criteria_hash "
            "FROM feature_requests"
        )
    }
    criteria = json.loads(rows["FR-LEGACY"]["acceptance_criteria"])
    canonical = json.dumps(criteria, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    assert rows["FR-LEGACY"]["criteria_version"] == 1
    assert rows["FR-LEGACY"]["criteria_hash"] == expected_hash
    assert rows["FR-EMPTY"]["criteria_version"] == 0
    assert rows["FR-EMPTY"]["criteria_hash"] is None
    artifact_columns = {
        row[1] for row in legacy_ledger.execute("PRAGMA table_info(fr_artifacts)")
    }
    assert {"criteria_version", "criteria_hash"}.issubset(artifact_columns)


def test_migration_is_idempotent_and_preserves_criteria_identity(
    legacy_ledger: sqlite3.Connection,
) -> None:
    migrate(legacy_ledger)
    before = tuple(
        legacy_ledger.execute(
            "SELECT criteria_version, criteria_hash FROM feature_requests "
            "WHERE id='FR-LEGACY'"
        ).fetchone()
    )

    migrate(legacy_ledger)

    after = tuple(
        legacy_ledger.execute(
            "SELECT criteria_version, criteria_hash FROM feature_requests "
            "WHERE id='FR-LEGACY'"
        ).fetchone()
    )
    assert after == before
    assert legacy_ledger.execute(
        "SELECT COUNT(*) FROM fr_criteria_history"
    ).fetchone()[0] == 0


def test_criteria_history_rejects_update_and_delete(
    legacy_ledger: sqlite3.Connection,
) -> None:
    migrate(legacy_ledger)
    legacy_ledger.execute(
        "INSERT INTO fr_criteria_history "
        "(fr_id, version, content, content_hash, created_at, approver, event_id, rationale) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "FR-LEGACY",
            1,
            "{}",
            "0" * 64,
            "2026-10-22T00:00:00Z",
            "Tyler",
            1,
            "approved rationale",
        ),
    )
    legacy_ledger.commit()

    with pytest.raises(sqlite3.IntegrityError, match="criteria history is append-only"):
        legacy_ledger.execute(
            "UPDATE fr_criteria_history SET rationale='changed' WHERE fr_id='FR-LEGACY'"
        )
    legacy_ledger.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="criteria history is append-only"):
        legacy_ledger.execute(
            "DELETE FROM fr_criteria_history WHERE fr_id='FR-LEGACY'"
        )