"""Playwright tests for the ⊕Workspace portal dashboard.

Requires the portal HTML to exist at reports/portal.html.
Run: C:\\G\\python.exe -m pytest tests/test_portal_playwright.py -v

Set PLAYWRIGHT_ENABLED=1 to enable: $env:PLAYWRIGHT_ENABLED=1
"""

from __future__ import annotations

from pathlib import Path

import pytest

PORTAL_PATH = Path(__file__).resolve().parent.parent / "reports" / "portal.html"
PORTAL_URL = PORTAL_PATH.as_uri() if PORTAL_PATH.exists() else ""

pytestmark = pytest.mark.playwright


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


@pytest.mark.skipif(not PORTAL_PATH.exists(), reason="Portal HTML not generated — run dashboard generator first")
def test_portal_loads(page):
    """Portal loads without JS errors."""
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
