"""Regression coverage for portal classification presentation."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from tools import dashboard_portal


def test_portal_hides_dashboard_classification_presentation() -> None:
    manifest = {
        "projects": [{"has_spec": True}],
        "dashboards": [
            {"id": "static", "title": "Static Dashboard", "type": "static_html", "category": "ops"},
            {"id": "living", "title": "Living Dashboard", "type": "living_html", "category": "ops"},
            {"id": "live", "title": "Live Dashboard", "type": "flask_app", "category": "security"},
            {"id": "cli", "title": "CLI Dashboard", "type": "console", "category": "tools"},
            {"id": "inline", "title": "Inline Dashboard", "type": "inline_html", "category": "tools"},
        ],
    }

    nav_html = dashboard_portal._nav_items(manifest)
    stats_html = dashboard_portal._stats_bar(manifest)

    assert "nav-badge" not in nav_html
    assert all(f">{label}</span>" not in nav_html for label in ("Static", "Living", "Live", "CLI", "Inline"))
    assert all(label not in stats_html for label in ("Static", "Live", "Console", "Categories"))
    assert "5" in stats_html
    assert "1" in stats_html


def test_security_dashboard_preserves_open_status_badge(monkeypatch) -> None:
    connection = SimpleNamespace(
        execute=lambda query: SimpleNamespace(fetchone=lambda: (3,)),
        close=lambda: None,
    )
    security_dashboard = SimpleNamespace(get_connection=lambda: connection)
    monkeypatch.setitem(sys.modules, "security_dashboard", security_dashboard)

    html = dashboard_portal._nav_items({
        "projects": [],
        "dashboards": [{
            "id": "security-vulns",
            "title": "Security Vulnerabilities",
            "type": "static_html",
            "category": "security",
        }],
    })

    assert 'class="nav-badge warn">Open 3</span>' in html


def test_security_dashboard_keeps_status_badge_when_lookup_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        dashboard_portal,
        "_security_dashboard",
        SimpleNamespace(get_connection=lambda: (_ for _ in ()).throw(RuntimeError("unavailable"))),
    )
    monkeypatch.setitem(
        sys.modules,
        "security_dashboard",
        SimpleNamespace(get_connection=lambda: (_ for _ in ()).throw(RuntimeError("unavailable"))),
    )

    html = dashboard_portal._nav_items({
        "projects": [],
        "dashboards": [{
            "id": "security-vulns",
            "title": "Security Vulnerabilities",
            "type": "static_html",
            "category": "security",
        }],
    })

    assert 'class="nav-badge static">Clear</span>' in html