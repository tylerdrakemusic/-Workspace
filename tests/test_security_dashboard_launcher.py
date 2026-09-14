from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = WORKTREE_ROOT / "open_security_dashboard.ps1"
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
    assert "security_scan.py" not in launcher
    assert "--scan" not in launcher
    assert "--seed" not in launcher
    assert "--set-status" not in launcher


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