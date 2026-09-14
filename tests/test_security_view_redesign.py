"""
TDD tests for FR-20260913: Security View Redesign

Requirements:
- Render ONLY vulnerabilities with status exactly "open"
- Hide remediated/accepted/false_positive/stale rows
- Remove remediation/status controls and instructions
- Show severity, category/OWASP, file/line, description, scan date
- Sort critical-to-low then newest within severity
- Show "All Clear" at zero
- Portal nav badge shows Open count + warning accent, or Clear badge at zero
"""

from __future__ import annotations

import importlib.util
import sqlite3
from datetime import datetime
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_PATH = WORKTREE_ROOT / "tools" / "security_dashboard.py"
PORTAL_PATH = WORKTREE_ROOT / "tools" / "dashboard_portal.py"


def _load_dashboard_module():
    """Dynamically load security_dashboard.py module."""
    spec = importlib.util.spec_from_file_location("security_dashboard", DASHBOARD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_portal_module():
    """Dynamically load dashboard_portal.py module."""
    spec = importlib.util.spec_from_file_location("dashboard_portal", PORTAL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_html_filters_to_open_vulnerabilities_only(monkeypatch) -> None:
    """RED: Verify HTML rendering shows ONLY open vulnerabilities."""
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

    # Create test data: 1 open, and 1 each of other statuses (should not appear in rendered HTML)
    rows = [
        ("open-1", "2026-09-10", "OWASP", "critical", r"f:\test.py", 10, "Test open issue", "A01", "open", None, None, "2026-09-10"),
        ("remediated-1", "2026-09-05", "OWASP", "high", r"f:\fixed.py", 20, "Fixed issue", "A02", "remediated", "Fixed in v2", "2026-09-08", "2026-09-05"),
        ("accepted-1", "2026-09-03", "OWASP", "medium", r"f:\accepted.py", 30, "Accepted issue", "A03", "accepted", "Risk accepted", "2026-09-06", "2026-09-03"),
        ("fp-1", "2026-09-01", "OWASP", "low", r"f:\fp.py", 40, "False positive", "A04", "false_positive", "Not real", "2026-09-02", "2026-09-01"),
        ("stale-1", "2026-08-20", "OWASP", "low", r"f:\old.py", 50, "Stale finding", "A05", "stale", None, None, "2026-08-20"),
    ]
    connection.executemany(
        "INSERT INTO vulnerabilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    monkeypatch.setattr(dashboard, "get_connection", lambda: connection)

    vulns = dashboard.load_all_vulns()
    rendered = dashboard.render_html(vulns)

    # ASSERT: Only "open" vulnerability should appear in rendered HTML
    assert "Test open issue" in rendered, "Open vulnerability should be in HTML"
    assert "Fixed issue" not in rendered, "Remediated vulnerability should NOT be in HTML"
    assert "Accepted issue" not in rendered, "Accepted vulnerability should NOT be in HTML"
    assert "False positive" not in rendered, "False positive vulnerability should NOT be in HTML"
    assert "Stale finding" not in rendered, "Stale vulnerability should NOT be in HTML"


def test_render_html_does_not_show_status_controls(monkeypatch) -> None:
    """RED: Verify HTML does not contain status select/dropdown or action controls."""
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
    connection.execute(
        "INSERT INTO vulnerabilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("open-1", "2026-09-10", "OWASP", "critical", r"f:\test.py", 10, "Test issue", "A01", "open", None, None, "2026-09-10"),
    )
    connection.commit()
    monkeypatch.setattr(dashboard, "get_connection", lambda: connection)

    vulns = dashboard.load_all_vulns()
    rendered = dashboard.render_html(vulns)

    # ASSERT: No status select dropdowns, action buttons, or remediation instructions
    assert '<select class="status-select"' not in rendered, "Status select dropdown should not be in HTML"
    assert 'class="save-btn"' not in rendered, "Save button should not be in HTML"
    assert 'class="note-input"' not in rendered, "Note input field should not be in HTML"
    assert "Override a finding" not in rendered, "Remediation instructions should not be in footer"
    assert "--set-status" not in rendered, "--set-status command should not be in HTML"


def test_render_html_shows_all_clear_at_zero(monkeypatch) -> None:
    """RED: Verify 'All Clear' message displays when zero open vulnerabilities."""
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
    connection.commit()
    monkeypatch.setattr(dashboard, "get_connection", lambda: connection)

    vulns = dashboard.load_all_vulns()
    rendered = dashboard.render_html(vulns)

    # ASSERT: All Clear message should appear
    assert "All Clear" in rendered, "'All Clear' message should be displayed at zero"


def test_render_html_includes_required_fields(monkeypatch) -> None:
    """RED: Verify rendered HTML contains all required fields."""
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
    connection.execute(
        "INSERT INTO vulnerabilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("id-1", "2026-09-10T14:30:00", "OWASP", "high", r"f:\src\app.py", 42, "SQL injection risk", "A03", "open", None, None, "2026-09-10"),
    )
    connection.commit()
    monkeypatch.setattr(dashboard, "get_connection", lambda: connection)

    vulns = dashboard.load_all_vulns()
    rendered = dashboard.render_html(vulns)

    # ASSERT: All required fields must be present in table
    assert "high" in rendered.lower(), "Severity field required"
    assert "OWASP" in rendered or "A03" in rendered, "Category/OWASP field required"
    assert r"f:\src\app.py" in rendered or "src/app.py" in rendered, "File path field required"
    assert "42" in rendered, "Line number field required"
    assert "SQL injection risk" in rendered, "Description field required"
    assert "2026-09-10" in rendered, "Scan date field required"


def test_render_html_sorts_by_severity_then_date(monkeypatch) -> None:
    """RED: Verify vulnerabilities are sorted critical->low then newest within severity."""
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

    # Insert with mixed severities and dates (not in sorted order)
    rows = [
        ("id-low-old", "2026-09-01", "OWASP", "low", r"f:\a.py", 1, "Low old", "A01", "open", None, None, "2026-09-01"),
        ("id-crit-new", "2026-09-10", "OWASP", "critical", r"f:\b.py", 2, "Critical new", "A02", "open", None, None, "2026-09-10"),
        ("id-high-new", "2026-09-11", "OWASP", "high", r"f:\c.py", 3, "High new", "A03", "open", None, None, "2026-09-11"),
        ("id-crit-old", "2026-09-09", "OWASP", "critical", r"f:\d.py", 4, "Critical old", "A04", "open", None, None, "2026-09-09"),
        ("id-high-old", "2026-09-05", "OWASP", "high", r"f:\e.py", 5, "High old", "A05", "open", None, None, "2026-09-05"),
        ("id-low-new", "2026-09-12", "OWASP", "low", r"f:\f.py", 6, "Low new", "A01", "open", None, None, "2026-09-12"),
    ]
    connection.executemany(
        "INSERT INTO vulnerabilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    monkeypatch.setattr(dashboard, "get_connection", lambda: connection)

    vulns = dashboard.load_all_vulns()
    rendered = dashboard.render_html(vulns)

    # Find positions of descriptions in rendered HTML
    pos_crit_new = rendered.find("Critical new")
    pos_crit_old = rendered.find("Critical old")
    pos_high_new = rendered.find("High new")
    pos_high_old = rendered.find("High old")
    pos_low_new = rendered.find("Low new")
    pos_low_old = rendered.find("Low old")

    # ASSERT: Proper ordering
    # Critical should come before High, High before Low
    assert pos_crit_new > 0, "Critical new should be in rendered HTML"
    assert pos_crit_old > 0, "Critical old should be in rendered HTML"
    assert pos_high_new > 0, "High new should be in rendered HTML"
    assert pos_low_new > 0, "Low new should be in rendered HTML"

    # Within critical: newer should come before older
    assert pos_crit_new < pos_crit_old, "Critical new should come before critical old"
    # Within high: newer should come before older
    assert pos_high_new < pos_high_old, "High new should come before high old"
    # Within low: newer should come before older
    assert pos_low_new < pos_low_old, "Low new should come before low old"

    # Critical should come before high
    assert pos_crit_new < pos_high_new, "Critical severity should come before high"
    # High should come before low
    assert pos_high_new < pos_low_new, "High severity should come before low"


def test_portal_nav_shows_security_badge_with_open_count(monkeypatch) -> None:
    """RED: Verify portal nav badge shows numeric Open count for security dashboard."""
    import sys
    portal = _load_portal_module()
    dashboard = _load_dashboard_module()
    sys.modules["security_dashboard"] = dashboard  # Register for portal._nav_items to find

    # Mock the manifest with security dashboard
    manifest = {
        "dashboards": [
            {
                "id": "security-vulns",
                "title": "Security Vulnerabilities",
                "type": "static_html",
                "icon": "🛡️",
                "project": "⊕Workspace",
                "sigil": "⊕",
            }
        ]
    }

    # Create mock connection with 3 open vulnerabilities
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
        ("id-1", "2026-09-10", "OWASP", "critical", r"f:\a.py", 1, "Issue 1", "A01", "open", None, None, "2026-09-10"),
        ("id-2", "2026-09-10", "OWASP", "high", r"f:\b.py", 2, "Issue 2", "A02", "open", None, None, "2026-09-10"),
        ("id-3", "2026-09-10", "OWASP", "medium", r"f:\c.py", 3, "Issue 3", "A03", "open", None, None, "2026-09-10"),
        ("id-4", "2026-09-10", "OWASP", "low", r"f:\d.py", 4, "Remediated", "A04", "remediated", None, None, "2026-09-10"),
    ]
    connection.executemany(
        "INSERT INTO vulnerabilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    monkeypatch.setattr(dashboard, "get_connection", lambda: connection)

    nav_html = portal._nav_items(manifest)

    # ASSERT: Badge should show "Open 3" or similar, with warning accent class
    assert "3" in nav_html, "Badge should show count of 3 open vulnerabilities"
    assert "Open" in nav_html or "open" in nav_html, "Badge should indicate 'Open' status"


def test_portal_nav_shows_clear_badge_at_zero(monkeypatch) -> None:
    """RED: Verify portal nav badge shows Clear status at zero open vulnerabilities."""
    import sys
    portal = _load_portal_module()
    dashboard = _load_dashboard_module()
    sys.modules["security_dashboard"] = dashboard  # Register for portal._nav_items to find

    # Mock the manifest with security dashboard
    manifest = {
        "dashboards": [
            {
                "id": "security-vulns",
                "title": "Security Vulnerabilities",
                "type": "static_html",
                "icon": "🛡️",
                "project": "⊕Workspace",
                "sigil": "⊕",
            }
        ]
    }

    # Create mock connection with 0 open vulnerabilities
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
    # Only remediated/accepted/etc - no open
    rows = [
        ("id-1", "2026-09-10", "OWASP", "critical", r"f:\a.py", 1, "Fixed", "A01", "remediated", None, None, "2026-09-10"),
    ]
    connection.executemany(
        "INSERT INTO vulnerabilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    monkeypatch.setattr(dashboard, "get_connection", lambda: connection)

    nav_html = portal._nav_items(manifest)

    # ASSERT: Badge should show "Clear" with neutral styling
    assert "Clear" in nav_html or "0" in nav_html, "Badge should indicate Clear status or show 0"
