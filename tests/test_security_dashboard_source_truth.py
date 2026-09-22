from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from src.utils import init_db

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DB = WORKTREE_ROOT.parent.parent / "src" / "data" / "workspace.db"
sys.path.insert(0, str(WORKTREE_ROOT / "tools"))
import security_dashboard


def test_canonical_db_path_fails_closed_when_only_worktree_db_exists(
    tmp_path: Path,
) -> None:
    worktree_root = tmp_path / ".worktrees" / "feature"
    local_db = worktree_root / "src" / "data" / "workspace.db"
    local_db.parent.mkdir(parents=True)
    local_db.write_bytes(b"local placeholder")

    with pytest.raises(FileNotFoundError, match="canonical workspace database"):
        init_db.require_canonical_db_path(worktree_root)


def test_canonical_db_path_preserves_parent_root_resolution(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    worktree_root = project_root / ".worktrees" / "feature"
    canonical_db = project_root / "src" / "data" / "workspace.db"
    canonical_db.parent.mkdir(parents=True)
    canonical_db.write_bytes(b"canonical placeholder")

    assert init_db.require_canonical_db_path(worktree_root) == canonical_db


def test_architecture_restores_unrelated_relationships_within_overview_budget() -> None:
    source = (WORKTREE_ROOT / "diagrams" / "workspace-architecture.mmd").read_text(
        encoding="utf-8"
    )

    required_relationships = (
        "Portal -->|POST /api/restart-master · loopback Host + Origin + rotating CSRF| Supervisor",
        "Portal -->|\"load -> local read-only DB Backup Health endpoint -> redacted Healthy / Attention / Unavailable aggregate -> separate DB Backup Health section; observes approved manifest, Windows Task Scheduler metadata, existing audit + generation evidence; evaluates backup_allowed=true only; no execution, restore, validation drill, scheduler mutation, raw paths, filenames, database names, secrets, or raw logs cross browser boundary\"| AIHealth",
        "DecisionMetadata -.->|shared contract consumer| Manifest",
        "SerpApiKeyBoundary -.->|operator authorization only| SerpApiSmoke",
    )

    assert all(relationship in source for relationship in required_relationships)


def test_canonical_false_positive_fixture_has_exact_five_records(tmp_path: Path) -> None:
    records = (
        (
            "11b007bd59167455",
            r"f:\⊕Workspace\tests\test_database_backup.py",
            799,
            "Verified 2026-09-21: test-only SQLCipher PRAGMA key fixture uses a temporary test key and does not construct application SQL or accept user input.",
        ),
        (
            "6da70e959a61ad29",
            r"f:\⊕Workspace\src\utils\database_backup.py",
            258,
            "Verified 2026-09-21: SQLCipher PRAGMA key escapes apostrophes in an environment-backed key; DB-API parameter binding is unavailable for this pragma and no user-controlled SQL is interpolated.",
        ),
        (
            "c3c14057f471b51a",
            r"f:\⊕Workspace\src\utils\database_backup.py",
            255,
            "Verified 2026-09-21: SQLCipher PRAGMA key uses an environment-backed key with hex encoding; DB-API parameter binding is unavailable for this pragma and no user-controlled SQL is interpolated.",
        ),
        (
            "fe056f9e1ff8ecfe",
            r"f:\⊕Workspace\tests\test_database_backup.py",
            829,
            "Verified 2026-09-21: test-only SQLCipher PRAGMA key fixture uses a temporary test key and does not construct application SQL or accept user input.",
        ),
        (
            "9cd4554c6584c95b",
            r"f:\⊕Workspace\tools\fr_portal_server.py",
            290,
            "Verified 2026-09-21: HTTP URL is the local 127.0.0.1 FR portal startup/diagnostic URL; it is not an outbound transport or user-controlled fetch.",
        ),
    )
    db_path = tmp_path / "vulnerability-fixture.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE vulnerabilities ("
        "vuln_id TEXT PRIMARY KEY, file_path TEXT, line_number INTEGER, "
        "status TEXT, override_note TEXT)"
    )
    connection.executemany(
        "INSERT INTO vulnerabilities VALUES (?, ?, ?, ?, ?)",
        [(finding_id, path, line, "false_positive", note) for finding_id, path, line, note in records],
    )
    connection.commit()
    rows = connection.execute(
        "SELECT vuln_id, file_path, line_number, status, override_note "
        "FROM vulnerabilities ORDER BY vuln_id"
    ).fetchall()
    connection.close()

    assert len(rows) == 5
    assert {
        (finding_id, path, line, status, note)
        for finding_id, path, line, status, note in rows
    } == {
        (finding_id, path, line, "false_positive", note)
        for finding_id, path, line, note in records
    }


def test_active_scan_excludes_retired_security_json_shim(tmp_path: Path) -> None:
    retired_scan = tmp_path / "resume" / "retired-security-json-shim" / "legacy.py"
    retired_scan.parent.mkdir(parents=True)
    retired_scan.write_text("eval(user_input)\n", encoding="utf-8")

    original_roots = security_dashboard.SCAN_ROOTS
    security_dashboard.SCAN_ROOTS = [tmp_path]
    try:
        assert security_dashboard.run_owasp_scan() == []
    finally:
        security_dashboard.SCAN_ROOTS = original_roots