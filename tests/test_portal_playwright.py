"""Playwright tests for the staged ⊕Workspace portal dashboard.

The desktop launcher starts the resident supervisor, which serves the portal at
http://127.0.0.1:8790/portal.html. Tests use the production HTTP handlers with
deterministic in-process state so they exercise that contract without launching
the full workspace service fleet.

Run: C:\\G\\python.exe -m pytest tests/test_portal_playwright.py -v
Set PLAYWRIGHT_ENABLED=1 to enable: $env:PLAYWRIGHT_ENABLED=1
"""

from __future__ import annotations

import http.server
import threading
import time
from pathlib import Path
from typing import Iterator
from urllib.request import urlopen

import pytest

import fr_server
from portal_supervisor import create_http_server

PORTAL_PATH = Path(__file__).resolve().parent.parent / "reports" / "portal.html"
PORTAL_URL = "http://127.0.0.1:8790/portal.html"
FR_BOARD_URL = "http://localhost:7474"

pytestmark = pytest.mark.playwright


class _SupervisorState:
    current_generation = "playwright-test"
    state: dict[str, dict[str, object]] = {}
    csrf_token = "playwright-test-csrf"

    def snapshot(self, *, include_token: bool = False) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "generation": self.current_generation,
            "services": {
                name: dict(service_state)
                for name, service_state in self.state.items()
            },
        }
        if include_token:
            snapshot["csrf_token"] = self.csrf_token
        return snapshot


class _FrWatcherState:
    frs: list[dict[str, object]] = []
    stale = False


def _serve_in_thread(server: http.server.ThreadingHTTPServer) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def _wait_until_healthy(url: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            continue
    raise RuntimeError(f"Test server did not become healthy: {url}")


@pytest.fixture(scope="module")
def fr_board_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Serve the real FR board handler with deterministic generated content."""
    reports_dir = tmp_path_factory.mktemp("fr-board") / "reports"
    reports_dir.mkdir()
    original_root = fr_server.WORKSPACE_ROOT
    original_dashboard = fr_server.DASHBOARD_HTML
    fr_server.WORKSPACE_ROOT = reports_dir.parent
    fr_server.DASHBOARD_HTML = reports_dir / "fr_dashboard.html"
    fr_server.regenerate_dashboard([])
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 7474), fr_server._make_handler(_FrWatcherState())
    )
    thread = _serve_in_thread(server)
    try:
        _wait_until_healthy(f"{FR_BOARD_URL}/health")
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        fr_server.WORKSPACE_ROOT = original_root
        fr_server.DASHBOARD_HTML = original_dashboard


@pytest.fixture(scope="module")
def supervisor_server(fr_board_server: None) -> Iterator[None]:
    """Serve the portal through the production supervisor HTTP handler."""
    supervisor = _SupervisorState()
    server = create_http_server(
        ("127.0.0.1", 8790), supervisor, PORTAL_PATH, lambda _url: None
    )
    thread = _serve_in_thread(server)
    try:
        _wait_until_healthy("http://127.0.0.1:8790/api/state")
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser(supervisor_server: None) -> Iterator[object]:
    """Launch a Chromium browser for the test module."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture(scope="module")
def page(browser: object) -> Iterator[object]:
    """Open the portal in a new browser page."""
    p = browser.new_page()
    yield p
    p.close()


# ---------------------------------------------------------------------------
# Supervisor-served portal shell tests
# ---------------------------------------------------------------------------

def test_portal_loads(page):
    """Portal loads from the supervisor without JavaScript errors."""
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(PORTAL_URL, wait_until="domcontentloaded")
    assert page.title() != "", "Page title should not be empty"
    assert errors == [], f"JS errors on page load: {errors}"


def test_portal_has_content(page):
    """Portal renders at least one meaningful content section."""
    page.goto(PORTAL_URL, wait_until="domcontentloaded")
    body_text = page.inner_text("body")
    assert len(body_text.strip()) > 50, "Portal body appears empty"


def test_fr_pane_uses_live_iframe(page):
    """Feature Requests pane must embed the live server, not a static file.

    The FR pane must point to http://localhost:7474 so that signoff POSTs and
    auto-refresh work; a static fr_dashboard.html embed silently breaks both.
    """
    page.goto(PORTAL_URL, wait_until="domcontentloaded")
    # Find pane-9 (Feature Requests) and check its iframe src
    iframe_src = page.get_attribute("#pane-9 iframe", "src")
    assert iframe_src is not None, "No iframe found in #pane-9 (Feature Requests pane)"
    assert iframe_src.startswith("http://localhost:7474"), (
        f"FR pane iframe must be http://localhost:7474, got: {iframe_src!r}\n"
        "Regenerate portal: C:\\G\\python.exe tools/dashboard_portal.py --regen --no-open"
    )


def test_fr_nav_badge_is_live(page):
    """Feature Requests nav item must show 'Live' badge, not 'Static'."""
    page.goto(PORTAL_URL, wait_until="domcontentloaded")
    # nav-item with data-idx=9 holds the Feature Requests entry
    badge_text = page.inner_text("[data-idx='9'] .nav-badge")
    assert badge_text.strip().lower() == "live", (
        f"FR nav badge should be 'Live', got: {badge_text!r}"
    )


# ---------------------------------------------------------------------------
# Live FR board tests
# ---------------------------------------------------------------------------

def test_fr_board_live_loads(page):
    """FR board at http://localhost:7474 loads the DB-backed live panel."""
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(FR_BOARD_URL)
    page.wait_for_selector("h1", timeout=5000)
    title = page.inner_text("h1")
    assert "Feature Request" in title, f"Unexpected page title: {title!r}"
    assert errors == [], f"JS errors on FR board: {errors}"


def test_fr_board_uses_db_registry(page):
    """FR board footer must reference fr_ledgers.db, not deprecated markdown paths."""
    page.goto(FR_BOARD_URL)
    page.wait_for_selector("body", timeout=5000)
    body = page.inner_text("body")
    assert "fr_ledgers.db" in body, (
        "FR board footer should reference fr_ledgers.db — old static generator may be running"
    )
    assert "FEATURE_REQUESTS.md" not in body, (
        "FR board references deprecated FEATURE_REQUESTS.md — wrong server binary is running on :7474"
    )
