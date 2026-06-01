"""Tests for BFX-20260530-nova-serve-url and BFX-20260530-remove-live-dash-chrome.

Verifies:
- ∞Life/dashboard.json biomarker entry has a serve_url pointing to localhost:8300
- _content_frames in dashboard_portal renders living_html with serve_url as iframe src
- flask_app panes render as bare iframes with no live-dash chrome
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
LIFE_ROOT = WORKSPACE_ROOT.parent / "\u221eLife"
sys.path.insert(0, str(WORKSPACE_ROOT / "tools"))

import dashboard_portal as dp  # noqa: E402


# ---------------------------------------------------------------------------
# dashboard.json assertions
# ---------------------------------------------------------------------------

def test_biomarker_entry_has_serve_url() -> None:
    """∞Life/dashboard.json biomarker-html entry must declare serve_url."""
    spec = LIFE_ROOT / "dashboard.json"
    if not spec.exists():
        pytest.skip(f"∞Life/dashboard.json not present — requires private repo checkout: {spec}")
    data = json.loads(spec.read_text(encoding="utf-8"))
    entries = {d["id"]: d for d in data["dashboards"]}
    assert "biomarker-html" in entries, "biomarker-html entry missing from dashboard.json"
    entry = entries["biomarker-html"]
    assert "serve_url" in entry, "biomarker-html entry missing serve_url field"
    assert entry["serve_url"] == "http://localhost:8300/", (
        f"serve_url should be 'http://localhost:8300/', got {entry['serve_url']!r}"
    )


# ---------------------------------------------------------------------------
# _content_frames renders serve_url for living_html
# ---------------------------------------------------------------------------

def _make_manifest(serve_url: str | None = "http://localhost:8300/") -> dict:
    dash: dict = {
        "id": "biomarker-html",
        "title": "Biomarker Dashboard",
        "type": "living_html",
        "output": "tmp/biomarker_dashboard.html",
        "output_abs": "",
        "cli": "C:\\G\\python.exe src/...",
        "category": "health",
        "icon": "\U0001f9ec",
        "priority": 10,
    }
    if serve_url is not None:
        dash["serve_url"] = serve_url
    return {
        "dashboards": [dash],
        "projects": [],
    }


def test_content_frames_uses_serve_url_for_living_html() -> None:
    """When living_html has serve_url, iframe src must use that URL."""
    manifest = _make_manifest(serve_url="http://localhost:8300/")
    html = dp._content_frames(manifest)
    assert "http://localhost:8300/" in html, (
        "Expected serve_url in iframe src for living_html dash"
    )
    assert "tmp/biomarker_dashboard.html" not in html, (
        "Static file path must NOT appear when serve_url is set"
    )


def test_content_frames_falls_back_to_static_when_no_serve_url(tmp_path: Path) -> None:
    """When living_html has no serve_url, iframe src uses the static file (existing behaviour)."""
    static = tmp_path / "biomarker_dashboard.html"
    static.write_text("<html></html>", encoding="utf-8")

    manifest = _make_manifest(serve_url=None)
    manifest["dashboards"][0]["output_abs"] = str(static)

    # Patch PORTAL_OUT so the mirror logic resolves correctly
    with patch.object(dp, "PORTAL_OUT", tmp_path / "reports" / "portal.html"):
        html = dp._content_frames(manifest)

    assert "biomarker_dashboard" in html, (
        "Static file path must appear when no serve_url is set"
    )


# ---------------------------------------------------------------------------
# BFX-20260530-remove-live-dash-chrome
# flask_app panes must render as bare iframes — no live-dash chrome
# ---------------------------------------------------------------------------

def _make_flask_manifest(dash_id: str = "fr-board", url: str = "http://localhost:7474") -> dict:
    return {
        "dashboards": [
            {
                "id": dash_id,
                "title": "Feature Requests",
                "type": "flask_app",
                "url": url,
                "cli": "C:\\G\\python.exe src/utils/fr_server.py --port 7474",
                "category": "workflow",
                "icon": "\U0001f4cb",
                "priority": 50,
            }
        ],
        "projects": [],
    }


def test_flask_app_pane_has_no_live_header() -> None:
    """BFX-20260530-remove-live-dash-chrome: flask_app panes must not emit live-header chrome."""
    html = dp._content_frames(_make_flask_manifest("fr-board"))
    assert "live-header" not in html, "flask_app pane still emits live-header chrome"
    assert "open-btn" not in html, "flask_app pane still emits open-btn"
    assert "Live Dashboard" not in html, "flask_app pane still emits 'Live Dashboard' text"


def test_flask_app_pane_renders_iframe_with_correct_url() -> None:
    """BFX-20260530-remove-live-dash-chrome: flask_app pane must contain bare iframe pointing to url."""
    url = "http://localhost:7474"
    html = dp._content_frames(_make_flask_manifest("fr-board", url))
    assert f'src="{url}"' in html, f"Expected bare iframe src={url!r} in flask_app pane"


def test_guitar_trainer_flask_app_also_has_no_live_header() -> None:
    """BFX-20260530-remove-live-dash-chrome: guitar-trainer pane (also flask_app) must remain chrome-free."""
    html = dp._content_frames(_make_flask_manifest("guitar-trainer", "http://localhost:5055"))
    assert "live-header" not in html, "guitar-trainer pane should never emit live-header"
    assert "open-btn" not in html, "guitar-trainer pane should never emit open-btn"


def test_living_html_serve_url_has_no_live_header() -> None:
    """BFX-20260530-remove-live-dash-chrome: living_html with serve_url must not emit live-header chrome."""
    manifest = _make_manifest(serve_url="http://localhost:8300/")
    html = dp._content_frames(manifest)
    assert "live-header" not in html, "living_html pane still emits live-header chrome"
    assert "open-btn" not in html, "living_html pane still emits open-btn"
    assert "live-dash" not in html, "living_html pane still emits live-dash wrapper"
    assert 'src="http://localhost:8300/"' in html, "serve_url must still be used as iframe src"


# ---------------------------------------------------------------------------
# BFX-20260531-dashboard-portal-shell-test
# regenerate_dashboards must call subprocess.run with shell=False
# ---------------------------------------------------------------------------

def _make_regen_manifest() -> dict:
    return {
        "dashboards": [
            {
                "id": "test-dash",
                "title": "Test Dashboard",
                "type": "static_html",
                "cli": "C:\\\\G\\\\python.exe tools/gen_test.py",
                "project": "workspace",
                "project_root": str(WORKSPACE_ROOT),
                "output": "reports/test.html",
                "output_abs": str(WORKSPACE_ROOT / "reports" / "test.html"),
                "category": "test",
                "icon": "\U0001f9ea",
                "priority": 99,
            }
        ],
        "projects": [],
    }


def test_regenerate_dashboards_uses_shell_false() -> None:
    """BFX-20260531-dashboard-portal-shell-test: subprocess.run must be called with shell=False."""
    manifest = _make_regen_manifest()
    mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        dp.regenerate_dashboards(manifest)
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("shell") is False, (
            "regenerate_dashboards must pass shell=False to subprocess.run — "
            "regression guard for BFX-20260531-dashboard-portal-shell-test"
        )


def test_regenerate_dashboards_passes_list_not_string_to_subprocess() -> None:
    """BFX-20260531-dashboard-portal-shell-test: cli string must be split into a list (shlex) before subprocess."""
    manifest = _make_regen_manifest()
    mock_result = MagicMock(returncode=0, stdout="ok", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        dp.regenerate_dashboards(manifest)
        args, _ = mock_run.call_args
        cmd = args[0]
        assert isinstance(cmd, list), (
            f"subprocess.run must receive a list, not {type(cmd).__name__!r} — "
            "shell=True bypass guard"
        )
