"""Playwright tests for the ⊕Workspace portal dashboard.

Canonical launch path (mirrors what Tyler uses from the desktop shortcut):
    C:\\Windows\\System32\\wscript.exe
        "C:\\Users\\tyler\\AppData\\Local\\WorkspacePortal\\open_portal.vbs"
    → open_portal.ps1 → launch_portal.ps1
    → opens file:///f:/⊕Workspace/reports/portal.html in Brave

The portal is a static file:// page that embeds live localhost iframes.
Tests here validate both the static shell AND the live service behaviour.

Run: C:\\G\\python.exe -m pytest tests/test_portal_playwright.py -v
Set PLAYWRIGHT_ENABLED=1 to enable: $env:PLAYWRIGHT_ENABLED=1
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

PORTAL_PATH = Path(__file__).resolve().parent.parent / "reports" / "portal.html"
PORTAL_URL = PORTAL_PATH.as_uri() if PORTAL_PATH.exists() else ""
FR_BOARD_URL = "http://localhost:7474"

pytestmark = pytest.mark.playwright


def _port_open(port: int) -> bool:
    """Return True if something is listening on localhost:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="module")
def browser():
    """Launch a Chromium browser for the test module."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture(scope="module")
def page(browser):
    """Open the portal in a new browser page."""
    p = browser.new_page()
    yield p
    p.close()


# ---------------------------------------------------------------------------
# Static shell tests (file:// — mirrors VBS launcher entry point)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not PORTAL_PATH.exists(), reason="Portal HTML not generated — run dashboard generator first")
def test_portal_loads(page):
    """Portal loads without JS errors (file:// — same origin as VBS launcher)."""
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(PORTAL_URL)
    assert page.title() != "", "Page title should not be empty"
    assert errors == [], f"JS errors on page load: {errors}"


@pytest.mark.skipif(not PORTAL_PATH.exists(), reason="Portal HTML not generated — run dashboard generator first")
def test_portal_has_content(page):
    """Portal renders at least one meaningful content section."""
    page.goto(PORTAL_URL)
    body_text = page.inner_text("body")
    assert len(body_text.strip()) > 50, "Portal body appears empty"


@pytest.mark.skipif(not PORTAL_PATH.exists(), reason="Portal HTML not generated — run dashboard generator first")
def test_fr_pane_uses_live_iframe(page):
    """Feature Requests pane must embed the live server, not a static file.

    When opened via the VBS launcher the portal is file://-served.  The FR
    pane must point to http://localhost:7474 so that signoff POSTs and
    auto-refresh work — a static fr_dashboard.html embed silently breaks both.
    """
    page.goto(PORTAL_URL)
    # Find pane-9 (Feature Requests) and check its iframe src
    iframe_src = page.get_attribute("#pane-9 iframe", "src")
    assert iframe_src is not None, "No iframe found in #pane-9 (Feature Requests pane)"
    assert iframe_src.startswith("http://localhost:7474"), (
        f"FR pane iframe must be http://localhost:7474, got: {iframe_src!r}\n"
        "Regenerate portal: C:\\G\\python.exe tools/dashboard_portal.py --regen --no-open"
    )


@pytest.mark.skipif(not PORTAL_PATH.exists(), reason="Portal HTML not generated — run dashboard generator first")
def test_fr_nav_badge_is_live(page):
    """Feature Requests nav item must show 'Live' badge, not 'Static'."""
    page.goto(PORTAL_URL)
    # nav-item with data-idx=9 holds the Feature Requests entry
    badge_text = page.inner_text("[data-idx='9'] .nav-badge")
    assert badge_text.strip().lower() == "live", (
        f"FR nav badge should be 'Live', got: {badge_text!r}"
    )


# ---------------------------------------------------------------------------
# Live server tests (http://localhost:7474 — only run when server is up)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _port_open(7474), reason="FR server not running on :7474 — start with start_fr_board.ps1")
def test_fr_board_live_loads():
    """FR board at http://localhost:7474 loads the DB-backed live panel."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(FR_BOARD_URL)
        page.wait_for_selector("h1", timeout=5000)
        title = page.inner_text("h1")
        assert "Feature Request" in title, f"Unexpected page title: {title!r}"
        assert errors == [], f"JS errors on FR board: {errors}"
        browser.close()


@pytest.mark.skipif(not _port_open(7474), reason="FR server not running on :7474 — start with start_fr_board.ps1")
def test_fr_board_uses_db_registry():
    """FR board footer must reference fr_ledgers.db, not deprecated markdown paths."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FR_BOARD_URL)
        page.wait_for_selector("body", timeout=5000)
        body = page.inner_text("body")
        assert "fr_ledgers.db" in body, (
            "FR board footer should reference fr_ledgers.db — old static generator may be running"
        )
        assert "FEATURE_REQUESTS.md" not in body, (
            "FR board references deprecated FEATURE_REQUESTS.md — wrong server binary is running on :7474"
        )
        browser.close()
