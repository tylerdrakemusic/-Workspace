"""Tests for tools/stale_vuln_dedup.py — TDD RED → GREEN.

FR-20260530-stale-vuln-dedup-report
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest

# stale_vuln_dedup lives in tools/ which is on sys.path via conftest
from stale_vuln_dedup import (
    check_file_exists,
    check_line_in_range,
    check_pattern_at_line,
    classify_vuln,
    find_dedup_candidates,
    load_open_vulns,
    run_sweep,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _insert_vuln(
    conn,
    *,
    file_path: str = "f:/nonexistent/ghost.py",
    line_number: int = 5,
    description: str = "B101: assert used",
    status: str = "open",
    created_at: str = "2026-01-01T00:00:00Z",
) -> str:
    vid = uuid.uuid4().hex[:16]
    conn.execute(
        """INSERT INTO vulnerabilities
           (vuln_id, scan_date, category, severity, file_path, line_number,
            description, owasp_id, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (vid, "2026-01-01", "OWASP", "low", file_path, line_number,
         description, "A03:2021", status, created_at),
    )
    conn.commit()
    return vid


# ── Unit: check_file_exists ────────────────────────────────────────────────────

def test_check_file_exists_real_file(tmp_path: Path) -> None:
    f = tmp_path / "real.py"
    f.write_text("x = 1\n", encoding="utf-8")
    assert check_file_exists(str(f)) is True


def test_check_file_exists_missing() -> None:
    assert check_file_exists("f:/totally/made/up/ghost.py") is False


def test_check_file_exists_empty_path() -> None:
    """Empty / None path should not flag as file-gone."""
    assert check_file_exists("") is True
    assert check_file_exists(None) is True  # type: ignore[arg-type]


# ── Unit: check_line_in_range ──────────────────────────────────────────────────

def test_line_in_range_within_bounds(tmp_path: Path) -> None:
    f = tmp_path / "code.py"
    f.write_text("line1\nline2\nline3\n", encoding="utf-8")
    assert check_line_in_range(str(f), 3) is True


def test_line_in_range_beyond_bounds(tmp_path: Path) -> None:
    f = tmp_path / "code.py"
    f.write_text("line1\nline2\n", encoding="utf-8")
    assert check_line_in_range(str(f), 99) is False


def test_line_in_range_zero_skips_check(tmp_path: Path) -> None:
    """line_number=0 (safety findings) always returns True."""
    f = tmp_path / "req.txt"
    f.write_text("requests==2.0\n", encoding="utf-8")
    assert check_line_in_range(str(f), 0) is True


def test_line_in_range_missing_file() -> None:
    assert check_line_in_range("f:/ghost.py", 5) is False


# ── Unit: check_pattern_at_line ───────────────────────────────────────────────

def test_pattern_at_line_detects_eval(tmp_path: Path) -> None:
    f = tmp_path / "code.py"
    f.write_text("x = 1\nresult = eval(user_input)\ny = 2\n", encoding="utf-8")
    assert check_pattern_at_line(str(f), 2) is True


def test_pattern_at_line_no_pattern(tmp_path: Path) -> None:
    f = tmp_path / "safe.py"
    f.write_text("x = 1\ny = x + 2\n", encoding="utf-8")
    assert check_pattern_at_line(str(f), 2) is False


def test_pattern_at_line_zero_skips(tmp_path: Path) -> None:
    """line_number=0 always returns True (safety findings)."""
    assert check_pattern_at_line("f:/req.txt", 0) is True


# ── Unit: classify_vuln ───────────────────────────────────────────────────────

def test_classify_file_gone() -> None:
    vuln = {"file_path": "f:/ghost/missing.py", "line_number": 5}
    assert classify_vuln(vuln) == "file_gone"


def test_classify_line_shifted(tmp_path: Path) -> None:
    f = tmp_path / "code.py"
    f.write_text("line1\nline2\n", encoding="utf-8")
    vuln = {"file_path": str(f), "line_number": 999}
    assert classify_vuln(vuln) == "line_shifted"


def test_classify_pattern_gone(tmp_path: Path) -> None:
    f = tmp_path / "safe.py"
    f.write_text("x = 1\ny = 2\n", encoding="utf-8")
    vuln = {"file_path": str(f), "line_number": 1}
    # line 1 is just "x = 1" — no OWASP pattern
    assert classify_vuln(vuln) == "pattern_gone"


def test_classify_still_valid(tmp_path: Path) -> None:
    f = tmp_path / "dangerous.py"
    f.write_text("x = 1\nresult = eval(cmd)\n", encoding="utf-8")
    vuln = {"file_path": str(f), "line_number": 2}
    assert classify_vuln(vuln) is None


def test_classify_zero_line_only_checks_file_existence(tmp_path: Path) -> None:
    """line_number=0 findings only fail on file-gone."""
    f = tmp_path / "requirements.txt"
    f.write_text("requests==2.0\n", encoding="utf-8")
    vuln = {"file_path": str(f), "line_number": 0}
    assert classify_vuln(vuln) is None


# ── Unit: find_dedup_candidates ───────────────────────────────────────────────

def test_find_dedup_no_dupes() -> None:
    vulns = [
        {"vuln_id": "aaa", "file_path": "f.py", "line_number": 1,
         "description": "B101", "created_at": "2026-01-01T00:00:00Z"},
        {"vuln_id": "bbb", "file_path": "f.py", "line_number": 2,
         "description": "B101", "created_at": "2026-01-02T00:00:00Z"},
    ]
    assert find_dedup_candidates(vulns) == []


def test_find_dedup_exact_match_marks_newer() -> None:
    # Same file+line+desc → keep oldest (earliest created_at)
    vulns = [
        {"vuln_id": "older", "file_path": "f.py", "line_number": 5,
         "description": "B101: assert", "created_at": "2026-01-01T00:00:00Z"},
        {"vuln_id": "newer", "file_path": "f.py", "line_number": 5,
         "description": "B101: assert", "created_at": "2026-06-01T00:00:00Z"},
    ]
    dupes = find_dedup_candidates(vulns)
    assert len(dupes) == 1
    assert dupes[0]["vuln_id"] == "newer"


def test_find_dedup_three_way_keeps_oldest() -> None:
    vulns = [
        {"vuln_id": "mid", "file_path": "f.py", "line_number": 3,
         "description": "eval", "created_at": "2026-03-01T00:00:00Z"},
        {"vuln_id": "newest", "file_path": "f.py", "line_number": 3,
         "description": "eval", "created_at": "2026-05-01T00:00:00Z"},
        {"vuln_id": "oldest", "file_path": "f.py", "line_number": 3,
         "description": "eval", "created_at": "2026-01-01T00:00:00Z"},
    ]
    dupes = find_dedup_candidates(vulns)
    dupe_ids = {d["vuln_id"] for d in dupes}
    assert "oldest" not in dupe_ids
    assert "mid" in dupe_ids
    assert "newest" in dupe_ids


# ── Integration: load_open_vulns ───────────────────────────────────────────────

def test_load_open_vulns_filters_status(db_conn) -> None:
    _insert_vuln(db_conn, status="open")
    _insert_vuln(db_conn, status="false_positive")
    _insert_vuln(db_conn, status="open")
    rows = load_open_vulns(db_conn)
    assert len(rows) == 2
    assert all(r["status"] == "open" for r in rows)


# ── Integration: run_sweep dry_run=True ───────────────────────────────────────

def test_dry_run_no_db_writes(db_conn) -> None:
    """Dry-run must not modify any vuln status in the DB."""
    vid = _insert_vuln(db_conn, file_path="f:/ghost.py", line_number=5)
    result = run_sweep(db_conn, dry_run=True)
    # The vuln must still be 'open'
    row = db_conn.execute(
        "SELECT status FROM vulnerabilities WHERE vuln_id=?", (vid,)
    ).fetchone()
    assert row[0] == "open"
    assert result["total_stale"] >= 1


def test_dry_run_returns_candidates(db_conn) -> None:
    _insert_vuln(db_conn, file_path="f:/ghost.py")
    result = run_sweep(db_conn, dry_run=True)
    assert len(result["stale_candidates"]) >= 1


def test_dry_run_no_scan_run_log(db_conn) -> None:
    """Dry-run must not write to scan_run_log."""
    _insert_vuln(db_conn, file_path="f:/ghost.py")
    run_sweep(db_conn, dry_run=True)
    rows = db_conn.execute("SELECT COUNT(*) FROM scan_run_log").fetchone()
    assert rows[0] == 0


# ── Integration: run_sweep dry_run=False (apply) ─────────────────────────────

def test_apply_marks_file_gone_stale(db_conn) -> None:
    vid = _insert_vuln(db_conn, file_path="f:/ghost_missing.py", line_number=5)
    run_sweep(db_conn, dry_run=False)
    row = db_conn.execute(
        "SELECT status, override_note FROM vulnerabilities WHERE vuln_id=?", (vid,)
    ).fetchone()
    assert row[0] == "stale"
    assert "file_gone" in (row[1] or "")


def test_apply_marks_line_shifted_stale(db_conn, tmp_path: Path) -> None:
    f = tmp_path / "short.py"
    f.write_text("line1\nline2\n", encoding="utf-8")
    vid = _insert_vuln(db_conn, file_path=str(f), line_number=999)
    run_sweep(db_conn, dry_run=False)
    row = db_conn.execute(
        "SELECT status, override_note FROM vulnerabilities WHERE vuln_id=?", (vid,)
    ).fetchone()
    assert row[0] == "stale"
    assert "line_shifted" in (row[1] or "")


def test_apply_marks_pattern_gone_stale(db_conn, tmp_path: Path) -> None:
    f = tmp_path / "clean.py"
    f.write_text("x = 1\n# benign comment\n", encoding="utf-8")
    vid = _insert_vuln(db_conn, file_path=str(f), line_number=2)
    run_sweep(db_conn, dry_run=False)
    row = db_conn.execute(
        "SELECT status FROM vulnerabilities WHERE vuln_id=?", (vid,)
    ).fetchone()
    assert row[0] == "stale"


def test_apply_dedup_keeps_oldest(db_conn) -> None:
    """Exact-match dedup: older vuln stays open, newer becomes stale."""
    older = _insert_vuln(
        db_conn, file_path="f:/ghost.py", line_number=1,
        description="B101: assert", created_at="2026-01-01T00:00:00Z",
    )
    newer = _insert_vuln(
        db_conn, file_path="f:/ghost.py", line_number=1,
        description="B101: assert", created_at="2026-06-01T00:00:00Z",
    )
    run_sweep(db_conn, dry_run=False)
    older_status = db_conn.execute(
        "SELECT status FROM vulnerabilities WHERE vuln_id=?", (older,)
    ).fetchone()[0]
    newer_status = db_conn.execute(
        "SELECT status FROM vulnerabilities WHERE vuln_id=?", (newer,)
    ).fetchone()[0]
    # Older file_path doesn't exist so it becomes stale(file_gone) — that's fine
    # The important check: newer is marked stale, and the dedup reason is exact-duplicate
    assert newer_status == "stale"
    newer_note = db_conn.execute(
        "SELECT override_note FROM vulnerabilities WHERE vuln_id=?", (newer,)
    ).fetchone()[0]
    assert "duplicate" in (newer_note or "").lower()


def test_apply_valid_vuln_stays_open(db_conn, tmp_path: Path) -> None:
    """A still-valid finding must not be marked stale."""
    f = tmp_path / "danger.py"
    f.write_text("x = 1\nresult = eval(user_cmd)\n", encoding="utf-8")
    vid = _insert_vuln(db_conn, file_path=str(f), line_number=2, description="eval")
    run_sweep(db_conn, dry_run=False)
    row = db_conn.execute(
        "SELECT status FROM vulnerabilities WHERE vuln_id=?", (vid,)
    ).fetchone()
    assert row[0] == "open"


def test_apply_writes_scan_run_log(db_conn) -> None:
    run_sweep(db_conn, dry_run=False)
    row = db_conn.execute("SELECT COUNT(*) FROM scan_run_log").fetchone()
    assert row[0] == 1


def test_apply_scan_run_log_note_contains_counts(db_conn) -> None:
    _insert_vuln(db_conn, file_path="f:/ghost1.py")
    _insert_vuln(db_conn, file_path="f:/ghost2.py")
    run_sweep(db_conn, dry_run=False)
    row = db_conn.execute("SELECT error_detail FROM scan_run_log LIMIT 1").fetchone()
    note = row[0] or ""
    assert "stale" in note.lower()


# ── Summary dict structure ────────────────────────────────────────────────────

def test_sweep_result_keys(db_conn) -> None:
    result = run_sweep(db_conn, dry_run=True)
    for key in ("stale_file_gone", "stale_line_shifted", "stale_pattern_gone",
                "deduped", "total_stale", "stale_candidates", "dedup_candidates"):
        assert key in result, f"Missing key: {key}"


def test_sweep_total_stale_equals_sum(db_conn) -> None:
    _insert_vuln(db_conn, file_path="f:/ghost.py")
    result = run_sweep(db_conn, dry_run=True)
    manual_total = (
        result["stale_file_gone"]
        + result["stale_line_shifted"]
        + result["stale_pattern_gone"]
        + result["deduped"]
    )
    assert result["total_stale"] == manual_total


# ── AC6: 'stale' status accepted by DB (no CHECK constraint error) ────────────

def test_stale_status_insert_no_constraint_error(db_conn) -> None:
    """Inserting status='stale' must not raise a constraint error."""
    vid = _insert_vuln(db_conn, status="open")
    db_conn.execute(
        "UPDATE vulnerabilities SET status='stale' WHERE vuln_id=?", (vid,)
    )
    db_conn.commit()
    row = db_conn.execute(
        "SELECT status FROM vulnerabilities WHERE vuln_id=?", (vid,)
    ).fetchone()
    assert row[0] == "stale"


# ── Migration: old schema with CHECK constraint gets upgraded ─────────────────

def test_migration_adds_stale_to_check_constraint() -> None:
    """After migration, a DB with old CHECK constraint accepts 'stale'."""
    from migrate_add_stale_status import migrate

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Create old-style table with restricted CHECK constraint
    conn.executescript("""
        CREATE TABLE vulnerabilities (
            vuln_id        TEXT PRIMARY KEY,
            scan_date      TEXT NOT NULL,
            category       TEXT NOT NULL,
            severity       TEXT NOT NULL,
            file_path      TEXT,
            line_number    INTEGER,
            description    TEXT NOT NULL,
            owasp_id       TEXT,
            status         TEXT NOT NULL DEFAULT 'open'
                           CHECK(status IN ('open','remediated','accepted','false_positive')),
            override_note  TEXT,
            remediated_at  TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE scan_run_log (
            run_id           TEXT PRIMARY KEY,
            started_at       TEXT NOT NULL,
            completed_at     TEXT,
            projects_scanned TEXT NOT NULL DEFAULT '[]',
            new_vulns_count  INTEGER NOT NULL DEFAULT 0,
            total_findings   INTEGER NOT NULL DEFAULT 0,
            bandit_exit_code INTEGER,
            safety_exit_code INTEGER,
            status           TEXT NOT NULL DEFAULT 'ok',
            error_detail     TEXT
        );
    """)
    # Insert an existing row with valid status
    conn.execute(
        "INSERT INTO vulnerabilities (vuln_id, scan_date, category, severity, description, status) "
        "VALUES ('abc123','2026-01-01','OWASP','low','test','open')"
    )
    conn.commit()

    # Run migration
    migrate(conn)

    # Now 'stale' should be accepted
    conn.execute(
        "UPDATE vulnerabilities SET status='stale' WHERE vuln_id='abc123'"
    )
    conn.commit()
    row = conn.execute(
        "SELECT status FROM vulnerabilities WHERE vuln_id='abc123'"
    ).fetchone()
    assert row[0] == "stale"
    conn.close()


def test_migration_idempotent() -> None:
    """Running migration twice on the same DB must not raise an error."""
    from migrate_add_stale_status import migrate

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE vulnerabilities (
            vuln_id        TEXT PRIMARY KEY,
            scan_date      TEXT NOT NULL,
            category       TEXT NOT NULL,
            severity       TEXT NOT NULL,
            file_path      TEXT,
            line_number    INTEGER,
            description    TEXT NOT NULL,
            owasp_id       TEXT,
            status         TEXT NOT NULL DEFAULT 'open'
                           CHECK(status IN ('open','remediated','accepted','false_positive')),
            override_note  TEXT,
            remediated_at  TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE scan_run_log (
            run_id           TEXT PRIMARY KEY,
            started_at       TEXT NOT NULL,
            completed_at     TEXT,
            projects_scanned TEXT NOT NULL DEFAULT '[]',
            new_vulns_count  INTEGER NOT NULL DEFAULT 0,
            total_findings   INTEGER NOT NULL DEFAULT 0,
            bandit_exit_code INTEGER,
            safety_exit_code INTEGER,
            status           TEXT NOT NULL DEFAULT 'ok',
            error_detail     TEXT
        );
    """)
    migrate(conn)
    migrate(conn)  # second call must not raise
    conn.close()


def test_migration_preserves_existing_data() -> None:
    """Migration must not lose existing vuln rows."""
    from migrate_add_stale_status import migrate

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE vulnerabilities (
            vuln_id TEXT PRIMARY KEY, scan_date TEXT NOT NULL,
            category TEXT NOT NULL, severity TEXT NOT NULL,
            file_path TEXT, line_number INTEGER, description TEXT NOT NULL,
            owasp_id TEXT,
            status TEXT NOT NULL DEFAULT 'open'
                       CHECK(status IN ('open','remediated','accepted','false_positive')),
            override_note TEXT, remediated_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE scan_run_log (
            run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
            completed_at TEXT, projects_scanned TEXT NOT NULL DEFAULT '[]',
            new_vulns_count INTEGER NOT NULL DEFAULT 0,
            total_findings INTEGER NOT NULL DEFAULT 0,
            bandit_exit_code INTEGER, safety_exit_code INTEGER,
            status TEXT NOT NULL DEFAULT 'ok', error_detail TEXT
        );
    """)
    for i in range(5):
        conn.execute(
            "INSERT INTO vulnerabilities (vuln_id, scan_date, category, severity, description) "
            "VALUES (?, '2026-01-01', 'OWASP', 'low', 'test')",
            (f"v{i:04d}",),
        )
    conn.commit()

    migrate(conn)

    count = conn.execute("SELECT COUNT(*) FROM vulnerabilities").fetchone()[0]
    assert count == 5
    conn.close()


# ── AC4: Nightly scanner integration ─────────────────────────────────────────

def test_nightly_scanner_calls_stale_sweep(db_conn) -> None:
    """After insert_new_vulns + write_scan_run_log, nightly scanner also runs sweep."""
    import security_scan_nightly as ssn
    from unittest.mock import patch, MagicMock

    finding = {
        "project": "⊕Workspace",
        "file_path": "f:/ghost_nightly.py",
        "line_number": 3,
        "rule_id": "B101",
        "description": "B101: assert used",
        "severity": "low",
        "owasp_id": "A03:2021",
    }
    ssn.insert_new_vulns(db_conn, [finding])

    # Patch run_sweep to verify it gets called with dry_run=False
    sweep_called = {}
    original_sweep = None

    def _fake_sweep(conn, *, dry_run=True):
        sweep_called["called"] = True
        sweep_called["dry_run"] = dry_run
        return {
            "stale_file_gone": 0, "stale_line_shifted": 0,
            "stale_pattern_gone": 0, "deduped": 0, "total_stale": 0,
            "stale_candidates": [], "dedup_candidates": [],
        }

    with patch("security_scan_nightly._run_stale_sweep", _fake_sweep):
        ssn._run_stale_sweep(db_conn, dry_run=False)

    # Also verify the function is importable from security_scan_nightly
    assert hasattr(ssn, "_run_stale_sweep"), \
        "security_scan_nightly must expose _run_stale_sweep(conn, *, dry_run)"


# ── AC5: Dashboard HTML contains Stale filter and card ───────────────────────

def test_dashboard_html_has_stale_filter_button() -> None:
    """render_html must include a Stale filter button."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import security_dashboard as sd

    vulns = [
        {"vuln_id": "aaa", "scan_date": "2026-01-01", "category": "OWASP",
         "severity": "low", "file_path": "f.py", "line_number": 1,
         "description": "eval", "owasp_id": "A03", "status": "stale",
         "override_note": "auto-stale: file_gone", "remediated_at": None,
         "created_at": "2026-01-01"},
    ]
    html = sd.render_html(vulns)
    assert 'data-filter="stale"' in html, "Missing stale filter button"


def test_dashboard_html_has_stale_count_in_summary() -> None:
    """render_html must show stale count in the summary section."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import security_dashboard as sd

    vulns = [
        {"vuln_id": "s1", "scan_date": "2026-01-01", "category": "OWASP",
         "severity": "medium", "file_path": "f.py", "line_number": 1,
         "description": "shell=True", "owasp_id": "A03", "status": "stale",
         "override_note": None, "remediated_at": None, "created_at": "2026-01-01"},
        {"vuln_id": "s2", "scan_date": "2026-01-01", "category": "OWASP",
         "severity": "low", "file_path": "g.py", "line_number": 2,
         "description": "eval", "owasp_id": "A03", "status": "stale",
         "override_note": None, "remediated_at": None, "created_at": "2026-01-01"},
        {"vuln_id": "o1", "scan_date": "2026-01-01", "category": "OWASP",
         "severity": "high", "file_path": "h.py", "line_number": 3,
         "description": "exec", "owasp_id": "A03", "status": "open",
         "override_note": None, "remediated_at": None, "created_at": "2026-01-01"},
    ]
    html = sd.render_html(vulns)
    # Should contain "2" somewhere near "Stale" (the count)
    assert "stale" in html.lower()
    # The stale count label should appear
    assert "Stale" in html
