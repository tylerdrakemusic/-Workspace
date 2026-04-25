"""
Tests for FR-20260425-portal-autostart.

Covers:
  - launch_portal.ps1: has -NoOpen parameter; skips browser open when set
  - register_portal_protocol.ps1: passes -NoOpen to the handler command
  - Windows registry: portal:// handler command includes -NoOpen
  - portal.html launchServers(): uses hidden anchor click, not window.location
  - portal.html launchServers(): re-polls twice (4s and 9s) after trigger
  - portal.html autoLaunch(): fires on window load, checks all 3 servers
"""
from __future__ import annotations

import re
import winreg
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE_ROOT       = Path(__file__).resolve().parents[1]
PORTAL_HTML          = WORKSPACE_ROOT / "reports" / "portal.html"
LAUNCH_PORTAL_PS     = WORKSPACE_ROOT / "tools" / "launch_portal.ps1"
REGISTER_PROTOCOL_PS = WORKSPACE_ROOT / "tools" / "register_portal_protocol.ps1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def portal_text() -> str:
    return PORTAL_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def launch_portal_text() -> str:
    return LAUNCH_PORTAL_PS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def register_protocol_text() -> str:
    return REGISTER_PROTOCOL_PS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# launch_portal.ps1 — -NoOpen parameter
# ---------------------------------------------------------------------------

def test_launch_portal_has_noopen_param(launch_portal_text: str) -> None:
    """`launch_portal.ps1` must declare a [switch]$NoOpen parameter."""
    assert "[switch]$NoOpen" in launch_portal_text, (
        "launch_portal.ps1 does not declare [switch]$NoOpen parameter"
    )


def test_launch_portal_skips_browser_when_noopen(launch_portal_text: str) -> None:
    """`launch_portal.ps1` must guard the browser-open block behind -not $NoOpen."""
    assert "-not $NoOpen" in launch_portal_text, (
        "launch_portal.ps1 does not gate browser open behind '-not $NoOpen'"
    )


def test_launch_portal_noopen_before_browser_open(launch_portal_text: str) -> None:
    """The -NoOpen guard must wrap the Start-Process / Brave open call."""
    noopen_idx   = launch_portal_text.find("-not $NoOpen")
    brave_idx    = launch_portal_text.find("$BRAVE $portalUri")
    start_idx    = launch_portal_text.find("Start-Process $portalUri")
    browser_idx  = max(brave_idx, start_idx)
    assert noopen_idx != -1,   "-not $NoOpen not found in launch_portal.ps1"
    assert browser_idx != -1,  "browser-open call not found in launch_portal.ps1"
    assert noopen_idx < browser_idx, (
        "NoOpen guard must appear before the browser-open call"
    )


# ---------------------------------------------------------------------------
# register_portal_protocol.ps1 — -NoOpen in handler command
# ---------------------------------------------------------------------------

def test_register_protocol_includes_noopen_flag(register_protocol_text: str) -> None:
    """`register_portal_protocol.ps1` must bake -NoOpen into the handler command."""
    assert "-NoOpen" in register_protocol_text, (
        "register_portal_protocol.ps1 does not pass -NoOpen to the handler"
    )


def test_register_protocol_handler_command_structure(register_protocol_text: str) -> None:
    """Handler command must include powershell.exe, launch_portal.ps1, and -NoOpen."""
    assert "launch_portal.ps1" in register_protocol_text
    assert "-NoOpen" in register_protocol_text
    assert "powershell.exe" in register_protocol_text.lower()


# ---------------------------------------------------------------------------
# Windows Registry — live check
# ---------------------------------------------------------------------------

def test_registry_portal_protocol_registered() -> None:
    """HKCU portal:// protocol handler must exist in the registry."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\portal\shell\open\command",
        )
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        assert value, "Registry handler command is empty"
    except FileNotFoundError:
        pytest.fail(
            "portal:// protocol not registered — run tools/register_portal_protocol.ps1"
        )


def test_registry_handler_includes_noopen() -> None:
    """Registered portal:// handler command must include -NoOpen."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\portal\shell\open\command",
        )
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        assert "-NoOpen" in value, (
            f"Registry handler command does not include -NoOpen: {value}"
        )
    except FileNotFoundError:
        pytest.fail("portal:// protocol not registered")


def test_registry_handler_points_to_launch_portal() -> None:
    """Registered handler must reference launch_portal.ps1."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\portal\shell\open\command",
        )
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
        assert "launch_portal.ps1" in value, (
            f"Registry handler does not reference launch_portal.ps1: {value}"
        )
    except FileNotFoundError:
        pytest.fail("portal:// protocol not registered")


# ---------------------------------------------------------------------------
# portal.html — launchServers() uses anchor, not window.location
# ---------------------------------------------------------------------------

def test_launch_servers_no_window_location(portal_text: str) -> None:
    """launchServers() must not use `window.location = 'portal://...'` (navigates away)."""
    # Extract launchServers function body
    fn_match = re.search(
        r"function launchServers\(\)\s*\{(.*?)\n    \}",
        portal_text,
        re.DOTALL,
    )
    assert fn_match, "launchServers() not found in portal.html"
    body = fn_match.group(1)
    # Strip comment lines before checking — comments may reference window.location by name
    non_comment_lines = [
        l for l in body.splitlines() if not l.strip().startswith("//")
    ]
    non_comment = "\n".join(non_comment_lines)
    assert "window.location" not in non_comment, (
        "launchServers() still uses window.location in code — replace with hidden anchor click"
    )


def test_launch_servers_uses_hidden_anchor(portal_text: str) -> None:
    """launchServers() must create a hidden anchor element to invoke portal://."""
    fn_match = re.search(
        r"function launchServers\(\)\s*\{(.*?)\n    \}",
        portal_text,
        re.DOTALL,
    )
    assert fn_match, "launchServers() not found in portal.html"
    body = fn_match.group(1)
    assert "createElement('a')" in body, (
        "launchServers() does not create an <a> element for protocol invocation"
    )
    assert "portal://launch" in body, (
        "launchServers() does not reference portal://launch"
    )


def test_launch_servers_polls_twice(portal_text: str) -> None:
    """launchServers() must schedule two pollServers() calls (4s and 9s)."""
    fn_match = re.search(
        r"function launchServers\(\)\s*\{(.*?)\n    \}",
        portal_text,
        re.DOTALL,
    )
    assert fn_match, "launchServers() not found in portal.html"
    body = fn_match.group(1)
    poll_count = body.count("pollServers()")
    assert poll_count >= 2, (
        f"launchServers() only calls pollServers() {poll_count} time(s) — need at least 2"
    )
    assert "4000" in body and "9000" in body, (
        "launchServers() should re-poll at 4000ms and 9000ms"
    )


# ---------------------------------------------------------------------------
# portal.html — autoLaunch() checks all 3 servers
# ---------------------------------------------------------------------------

def test_autolaunched_on_window_load(portal_text: str) -> None:
    """autoLaunch must be wired to the window load event."""
    assert "window.addEventListener('load'" in portal_text
    assert "autoLaunch" in portal_text


def test_autolaunched_checks_guitar_trainer_port(portal_text: str) -> None:
    """SERVERS array used by autoLaunch must include Guitar Trainer on port 5055."""
    servers_match = re.search(r"const SERVERS\s*=\s*(\[.*?\]);", portal_text)
    assert servers_match, "SERVERS array not found in portal.html"
    servers_literal = servers_match.group(1)
    assert "5055" in servers_literal, "SERVERS array missing Guitar Trainer port 5055"


def test_launch_btn_element_exists_in_html(portal_text: str) -> None:
    """portal.html must have an element with id='launch-btn' for user-gesture invocation."""
    assert 'id="launch-btn"' in portal_text, (
        "launch-btn element is missing — browser blocks programmatic protocol invocation; "
        "user must click the button (real gesture)"
    )


def test_autolaunched_shows_server_status_block(portal_text: str) -> None:
    """autoLaunch() must reveal the server-status block (id='server-status-block')."""
    fn_match = re.search(
        r"async function autoLaunch\(\)\s*\{(.*?)\n    \}",
        portal_text,
        re.DOTALL,
    )
    assert fn_match, "autoLaunch() not found in portal.html"
    body = fn_match.group(1)
    assert "server-status-block" in body, (
        "autoLaunch() must set server-status-block visible"
    )


def test_autolaunched_does_not_call_launch_servers_without_gesture(portal_text: str) -> None:
    """autoLaunch() must NOT call launchServers() directly (requires user gesture)."""
    fn_match = re.search(
        r"async function autoLaunch\(\)\s*\{(.*?)\n    \}",
        portal_text,
        re.DOTALL,
    )
    assert fn_match, "autoLaunch() not found in portal.html"
    body = fn_match.group(1)
    non_comment_lines = [l for l in body.splitlines() if not l.strip().startswith("//")]
    non_comment = "\n".join(non_comment_lines)
    assert "launchServers()" not in non_comment, (
        "autoLaunch() must not call launchServers() automatically — browser blocks protocol "
        "invocations from setTimeout; user must click launch-btn instead"
    )
