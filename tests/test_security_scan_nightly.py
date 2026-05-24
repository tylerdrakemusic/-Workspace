"""Tests for src/utils/security_scan_nightly.py.

Uses in-memory plain sqlite3 (no SQLCipher) via the db_conn fixture from
conftest.py, passing the connection directly to the functions under test.
Subprocess calls to bandit/safety are mocked to avoid needing the tools
installed in CI.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/utils is importable without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "utils"))
import security_scan_nightly as ssn


# ── Unit: _vuln_id ─────────────────────────────────────────────────────────────

def test_vuln_id_is_stable() -> None:
    vid1 = ssn._vuln_id("⊕Workspace", "src/foo.py", 42, "B101")
    vid2 = ssn._vuln_id("⊕Workspace", "src/foo.py", 42, "B101")
    assert vid1 == vid2


def test_vuln_id_differs_on_line() -> None:
    vid1 = ssn._vuln_id("⊕Workspace", "src/foo.py", 10, "B101")
    vid2 = ssn._vuln_id("⊕Workspace", "src/foo.py", 20, "B101")
    assert vid1 != vid2


def test_vuln_id_length() -> None:
    vid = ssn._vuln_id("proj", "file.py", 1, "B001")
    assert len(vid) == 16


# ── Unit: insert_new_vulns ─────────────────────────────────────────────────────

def _sample_finding(**overrides) -> dict:
    base = {
        "project": "⊕Workspace",
        "file_path": "src/utils/foo.py",
        "line_number": 5,
        "rule_id": "B101",
        "description": "B101: assert used",
        "severity": "low",
        "owasp_id": "A03:2021",
    }
    base.update(overrides)
    return base


def test_insert_new_vuln(db_conn) -> None:
    finding = _sample_finding()
    count = ssn.insert_new_vulns(db_conn, [finding])
    assert count == 1
    rows = db_conn.execute("SELECT * FROM vulnerabilities").fetchall()
    assert len(rows) == 1


def test_insert_dedup(db_conn) -> None:
    """Same finding inserted twice — second call is a no-op."""
    finding = _sample_finding()
    ssn.insert_new_vulns(db_conn, [finding])
    count2 = ssn.insert_new_vulns(db_conn, [finding])
    assert count2 == 0
    rows = db_conn.execute("SELECT * FROM vulnerabilities").fetchall()
    assert len(rows) == 1


def test_insert_multiple_distinct(db_conn) -> None:
    f1 = _sample_finding(line_number=1)
    f2 = _sample_finding(line_number=2)
    count = ssn.insert_new_vulns(db_conn, [f1, f2])
    assert count == 2


def test_insert_severity_stored(db_conn) -> None:
    ssn.insert_new_vulns(db_conn, [_sample_finding(severity="high")])
    row = db_conn.execute("SELECT severity FROM vulnerabilities LIMIT 1").fetchone()
    assert row[0] == "high"


# ── Unit: write_scan_run_log ───────────────────────────────────────────────────

def test_write_scan_run_log(db_conn) -> None:
    run_id = str(uuid.uuid4())
    ssn.write_scan_run_log(
        db_conn, run_id, "2026-05-23T02:30:00Z",
        ["⊕Workspace", "∞Life"],
        new_vulns=3, total_findings=10,
        bandit_rc=1, safety_rc=0,
        status="ok", error_detail=None,
    )
    row = db_conn.execute(
        "SELECT * FROM scan_run_log WHERE run_id=?", (run_id,)
    ).fetchone()
    assert row is not None
    assert row["new_vulns_count"] == 3
    assert row["total_findings"] == 10
    assert row["status"] == "ok"
    assert row["error_detail"] is None
    assert json.loads(row["projects_scanned"]) == ["⊕Workspace", "∞Life"]


def test_write_scan_run_log_error(db_conn) -> None:
    run_id = str(uuid.uuid4())
    ssn.write_scan_run_log(
        db_conn, run_id, "2026-05-23T02:30:00Z",
        [], 0, 0, 1, 1, "error", "bandit/⊕Workspace: timeout",
    )
    row = db_conn.execute(
        "SELECT status, error_detail FROM scan_run_log WHERE run_id=?", (run_id,)
    ).fetchone()
    assert row["status"] == "error"
    assert "timeout" in row["error_detail"]


# ── Unit: run_bandit (mocked subprocess) ──────────────────────────────────────

_BANDIT_SAMPLE = {
    "results": [
        {
            "filename": "src/utils/foo.py",
            "line_number": 10,
            "test_id": "B101",
            "issue_text": "Use of assert detected.",
            "issue_severity": "LOW",
        }
    ]
}


def test_run_bandit_parses_output(tmp_path: Path) -> None:
    fake_src = tmp_path / "src"
    fake_src.mkdir()
    (fake_src / "foo.py").write_text("assert True\n")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(_BANDIT_SAMPLE),
            returncode=1,
        )
        findings, rc = ssn.run_bandit(tmp_path)

    assert rc == 1
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "B101"
    assert findings[0]["severity"] == "low"
    assert findings[0]["owasp_id"] == "A03:2021"


def test_run_bandit_empty_stdout(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        findings, rc = ssn.run_bandit(tmp_path)
    assert findings == []
    assert rc == 0


def test_run_bandit_invalid_json(tmp_path: Path) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="not json {", returncode=1)
        findings, rc = ssn.run_bandit(tmp_path)
    assert findings == []
    assert rc == 1


# ── Unit: run_safety (mocked subprocess) ──────────────────────────────────────

_SAFETY_SAMPLE_V3 = {
    "vulnerabilities": [
        {
            "package_name": "requests",
            "vulnerability_id": "CVE-2023-1234",
            "advisory": "Requests: SSRF in redirect handling",
        }
    ]
}


def test_run_safety_v3_parses_output(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=json.dumps(_SAFETY_SAMPLE_V3),
            returncode=64,
        )
        findings, rc = ssn.run_safety(tmp_path)
    assert len(findings) == 1
    assert "requests" in findings[0]["description"]
    assert findings[0]["owasp_id"] == "A06:2021"
    assert findings[0]["severity"] == "high"


def test_run_safety_no_requirements(tmp_path: Path) -> None:
    findings, rc = ssn.run_safety(tmp_path)
    assert findings == []
    assert rc == 0


def test_run_safety_empty_stdout(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        findings, rc = ssn.run_safety(tmp_path)
    assert findings == []
    assert rc == 0


# ── Integration: main() end-to-end (fully mocked) ────────────────────────────

def test_main_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """main() runs, writes a scan_run_log row, writes new vuln rows, returns 0."""
    import sqlite3 as _sqlite3

    # Stub PROJECT_ROOTS to one real tmp dir.
    fake_project = tmp_path / "FakeProject"
    fake_project.mkdir()
    (fake_project / "requirements.txt").write_text("requests==2.28.0\n")
    monkeypatch.setattr(ssn, "PROJECT_ROOTS", [fake_project])

    # Stub LOG_FILE to a tmp path so we don't write to the real log.
    monkeypatch.setattr(ssn, "LOG_FILE", tmp_path / "security_nightly.log")

    # Provide a plain in-memory DB for _get_db_conn.
    # Use a file-based DB so we can reopen it after main() closes it.
    db_file = tmp_path / "workspace_test.db"
    setup_conn = _sqlite3.connect(str(db_file))
    setup_conn.executescript("""
        CREATE TABLE vulnerabilities (
            vuln_id TEXT PRIMARY KEY, scan_date TEXT NOT NULL,
            category TEXT NOT NULL, severity TEXT NOT NULL,
            file_path TEXT, line_number INTEGER, description TEXT NOT NULL,
            owasp_id TEXT, status TEXT NOT NULL DEFAULT 'open',
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
    setup_conn.close()

    def _open_test_db():
        c = _sqlite3.connect(str(db_file))
        c.row_factory = _sqlite3.Row
        return c

    monkeypatch.setattr(ssn, "_get_db_conn", _open_test_db)

    bandit_out = json.dumps({"results": [
        {"filename": "FakeProject/src/a.py", "line_number": 1,
         "test_id": "B101", "issue_text": "assert", "issue_severity": "LOW"}
    ]})
    safety_out = json.dumps({"vulnerabilities": [
        {"package_name": "requests", "vulnerability_id": "CVE-2023-0001",
         "advisory": "SSRF"}
    ]})

    call_count = {"n": 0}

    def mock_run(cmd, **kwargs):
        m = MagicMock()
        if "bandit" in cmd:
            m.stdout = bandit_out
            m.returncode = 1
        else:
            call_count["n"] += 1
            m.stdout = safety_out if call_count["n"] == 1 else ""
            m.returncode = 64
        return m

    with patch("subprocess.run", side_effect=mock_run):
        rc = ssn.main()

    assert rc == 0

    # Reopen to inspect results written by main().
    verify_conn = _sqlite3.connect(str(db_file))
    verify_conn.row_factory = _sqlite3.Row

    log_rows = verify_conn.execute("SELECT * FROM scan_run_log").fetchall()
    assert len(log_rows) == 1
    assert log_rows[0]["new_vulns_count"] >= 1

    vuln_rows = verify_conn.execute("SELECT * FROM vulnerabilities").fetchall()
    assert len(vuln_rows) >= 1

    verify_conn.close()

    log_text = (tmp_path / "security_nightly.log").read_text(encoding="utf-8")
    assert "Nightly Security Scan START" in log_text
    assert "Nightly Security Scan END" in log_text
