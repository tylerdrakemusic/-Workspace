from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = WORKTREE_ROOT / "open_security_dashboard.ps1"
MANIFEST = WORKTREE_ROOT / "dashboard.json"
GENERATOR_PATH = WORKTREE_ROOT / "tools" / "security_dashboard.py"


def _load_dashboard_module():
    spec = importlib.util.spec_from_file_location("security_dashboard", GENERATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_routes_to_db_dashboard_generator_without_mutation_flags() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "tools\\security_dashboard.py" in launcher
    assert "reports\\security_dashboard.html" in launcher
    assert "$PSScriptRoot" in launcher
    assert "f:\\⊕Workspace" not in launcher
    assert "security_scan.py" not in launcher
    assert "--scan" not in launcher
    assert "--seed" not in launcher
    assert "--set-status" not in launcher


def test_default_generation_is_read_only_and_skips_override_import(monkeypatch, tmp_path) -> None:
    dashboard = _load_dashboard_module()
    database_path = tmp_path / "vulnerabilities.db"
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE vulnerabilities (
            vuln_id TEXT PRIMARY KEY, scan_date TEXT NOT NULL,
            category TEXT NOT NULL, severity TEXT NOT NULL,
            file_path TEXT, line_number INTEGER, description TEXT NOT NULL,
            owasp_id TEXT, status TEXT NOT NULL,
            override_note TEXT, remediated_at TEXT, created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO vulnerabilities
        VALUES ('open-1', '2026-09-21', 'OWASP', 'high', NULL, NULL,
                'Read-only regression', 'A01', 'open', NULL, NULL, '2026-09-21')
        """
    )
    connection.commit()
    sidecar = tmp_path / "reports" / "vuln_overrides.json"
    sidecar.parent.mkdir()
    sidecar.write_text('{"open-1": {"status": "remediated"}}', encoding="utf-8")

    connection.close()

    def open_connection():
        fresh_connection = sqlite3.connect(database_path)
        fresh_connection.row_factory = sqlite3.Row
        return fresh_connection

    monkeypatch.setattr(dashboard, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(dashboard, "OUT_PATH", tmp_path / "reports" / "security_dashboard.html")
    monkeypatch.setattr(dashboard, "get_connection", open_connection)
    monkeypatch.setattr(
        dashboard,
        "import_overrides",
        lambda: (_ for _ in ()).throw(AssertionError("default generation imported overrides")),
    )
    monkeypatch.setattr(sys, "argv", ["security_dashboard.py", "--no-open"])

    dashboard.main()

    connection = open_connection()
    row = connection.execute(
        "SELECT status, override_note FROM vulnerabilities WHERE vuln_id = 'open-1'"
    ).fetchone()
    connection.close()
    assert tuple(row) == ("open", None)
    assert sidecar.exists()
    assert sidecar.read_text(encoding="utf-8") == '{"open-1": {"status": "remediated"}}'


def test_json_security_ledger_and_generator_are_not_active_inventory_sources() -> None:
    json_ledger = WORKTREE_ROOT / "src" / "data" / "security_findings.json"
    legacy_generator = WORKTREE_ROOT / "src" / "utils" / "security_scan.py"

    assert not json_ledger.exists(), "The retired JSON vulnerability ledger must be removed"
    assert not legacy_generator.exists(), "The retired JSON dashboard generator must be removed"


def test_checked_in_portal_artifact_does_not_advertise_stale_open_count() -> None:
    portal = (WORKTREE_ROOT / "reports" / "portal.html").read_text(encoding="utf-8")

    assert "Open 12" not in portal


def test_security_dashboard_manifest_generation_does_not_scan_or_mutate_inventory() -> None:
    manifest = MANIFEST.read_text(encoding="utf-8")

    assert '"generator": "tools/security_dashboard.py"' in manifest
    assert '"cli": "C:\\\\G\\\\python.exe tools/security_dashboard.py --no-open"' in manifest
    assert "security_dashboard.py --scan" not in manifest


def test_dashboard_generator_resolves_canonical_workspace_db_from_worktree() -> None:
    _load_dashboard_module()
    from utils import init_db

    canonical_db = WORKTREE_ROOT.parent.parent / "src" / "data" / "workspace.db"

    assert init_db.DB_PATH == canonical_db


def test_generated_summary_matches_controlled_database_aggregates(monkeypatch) -> None:
    """Verify dashboard shows ONLY open vulnerabilities in summary and severity breakdown.

    Read-only dashboard must NOT expose reconciled status counts (Remediated, Accepted/FP, Stale).
    """
    dashboard = _load_dashboard_module()
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE vulnerabilities (
            vuln_id TEXT PRIMARY KEY, scan_date TEXT NOT NULL,
            category TEXT NOT NULL, severity TEXT NOT NULL,
            file_path TEXT, line_number INTEGER, description TEXT NOT NULL,
            owasp_id TEXT, status TEXT NOT NULL,
            override_note TEXT, remediated_at TEXT, created_at TEXT NOT NULL
        )
        """
    )
    rows = [
        ("critical-open", "2026-09-03", "OWASP", "critical", "open"),
        ("high-open", "2026-09-03", "OWASP", "high", "open"),
        ("medium-remediated", "2026-09-03", "OWASP", "medium", "remediated"),
        ("low-accepted", "2026-09-03", "OWASP", "low", "accepted"),
    ]
    connection.executemany(
        "INSERT INTO vulnerabilities VALUES (?, ?, ?, ?, NULL, NULL, ?, NULL, ?, NULL, NULL, ?)",
        [(vuln_id, scan_date, category, severity, vuln_id, status, scan_date) for vuln_id, scan_date, category, severity, status in rows],
    )
    connection.commit()
    monkeypatch.setattr(dashboard, "get_connection", lambda: connection)

    vulns = dashboard.load_all_vulns()
    rendered = dashboard.render_html(vulns)

    # ASSERT: Only open count should be shown; no reconciled status labels
    assert '<div class="stat open-stat">2</div><div class="label">Open</div>' in rendered, \
        "Dashboard must show open count"
    assert "Total Findings" not in rendered, \
        "Total Findings count must NOT appear in read-only dashboard"
    assert "Remediated" not in rendered, \
        "Remediated status label must NOT appear in read-only dashboard"
    assert "Accepted / FP" not in rendered, \
        "Accepted/FP status label must NOT appear in read-only dashboard"

    # ASSERT: Severity breakdown shows only open counts (critical=1, high=1, medium=0, low=0)
    assert rendered.count('<span class="sev-count">1</span>') == 2, \
        "Severity breakdown should show 1 for critical and 1 for high"
    assert rendered.count('<span class="sev-count">0</span>') == 2, \
        "Severity breakdown should show 0 for medium and low"