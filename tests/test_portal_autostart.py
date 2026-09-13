"""
Tests for FR-20260425-portal-autostart.

Covers:
  - launch_portal.ps1: has -NoOpen parameter; skips browser open when set
  - register_portal_protocol.ps1: passes -NoOpen to the handler command
  - Windows registry: portal:// handler command includes -NoOpen
    - portal.html launchServers(): posts Restart All directly to the supervisor
    - portal.html launchServers(): restores the button and polling after a bounded delay
    - portal.html autoLaunch(): fires on window load and polls authoritative state
"""
from __future__ import annotations

import re
import os
import sys
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
    if not PORTAL_HTML.is_file():
        pytest.skip(f"portal.html not generated — skipping: {PORTAL_HTML}")
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
    """`launch_portal.ps1` must forward no-open behavior to the supervisor."""
    assert 'if ($NoOpen) { $arguments += "--no-open" }' in launch_portal_text, (
        "launch_portal.ps1 does not forward --no-open to the supervisor"
    )


def test_launch_portal_delegates_readiness_to_supervisor(launch_portal_text: str) -> None:
    """The thin launcher must not own service readiness or port checks."""
    assert "portal_supervisor.py" in launch_portal_text
    assert "Wait-PortListening" not in launch_portal_text
    assert "Get-NetTCPConnection" not in launch_portal_text


def test_launch_portal_contains_no_browser_implementation(launch_portal_text: str) -> None:
    """Browser focus/open behavior belongs exclusively to the supervisor."""
    assert "$BRAVE" not in launch_portal_text
    assert "Start-Process" not in launch_portal_text


# ---------------------------------------------------------------------------
# register_portal_protocol.ps1 — -NoOpen in handler command
# ---------------------------------------------------------------------------

def test_register_protocol_includes_noopen_flag(register_protocol_text: str) -> None:
    """`register_portal_protocol.ps1` must bake --no-open into the staged command."""
    assert "--no-open" in register_protocol_text, (
        "register_portal_protocol.ps1 does not pass --no-open to the supervisor"
    )


def test_register_protocol_handler_command_structure(register_protocol_text: str) -> None:
    """Handler must stage PowerShell/VBS shims that invoke the supervisor."""
    assert "portal_supervisor.py" in register_protocol_text
    assert "--no-open" in register_protocol_text
    assert "powershell.exe" in register_protocol_text.lower()


# ---------------------------------------------------------------------------
# Windows Registry — live check (Windows-only)
# ---------------------------------------------------------------------------

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows registry not available on this platform")
operator_proof_only = pytest.mark.skipif(
    os.environ.get("PORTAL_SUPERVISOR_OPERATOR_PROOF") != "1",
    reason="set PORTAL_SUPERVISOR_OPERATOR_PROOF=1 after staging the reversible operator artifact",
)


def _resolve_staged_indirection(registry_command: str) -> str:
    """Follow a wscript.exe/.vbs registry handler command to its staged .ps1 content.

    register_portal_protocol.ps1 keeps the registry command pointed at an
    ASCII-safe .vbs shim (via wscript.exe) to avoid shell/protocol issues with
    the ⊕ sigil path. The .vbs shim in turn launches a staged .ps1 stub that
    actually contains "-NoOpen" and "launch_portal.ps1". Returns the staged
    .ps1 content (or empty string if not found/applicable) so callers can
    check both the registry command and its indirection target.
    """
    match = re.search(r'"([^"]+\.vbs)"', registry_command)
    if not match:
        return ""
    vbs_path = Path(match.group(1))
    if not vbs_path.is_file():
        return ""
    staged_ps1 = vbs_path.with_suffix(".ps1")
    if not staged_ps1.is_file():
        return ""
    return staged_ps1.read_text(encoding="utf-8-sig")


@windows_only
@operator_proof_only
def test_registry_portal_protocol_registered() -> None:
    """HKCU portal:// protocol handler must exist in the registry."""
    import winreg
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


@windows_only
@operator_proof_only
def test_registry_handler_includes_noopen() -> None:
    """Registered portal:// handler must include --no-open, either directly in the
    registry command or in the staged launcher script it indirects through
    (register_portal_protocol.ps1 wraps the real command in an ASCII-safe
    staged .ps1 invoked via wscript.exe + a .vbs shim, for shell/protocol
    stability with the ⊕ sigil path).
    """
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\portal\shell\open\command",
        )
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
    except FileNotFoundError:
        pytest.fail("portal:// protocol not registered")
    resolved = value + _resolve_staged_indirection(value)
    assert "--no-open" in resolved, (
        f"Registry handler command (and any staged launcher it delegates to) does not include --no-open: {value}"
    )


@windows_only
@operator_proof_only
def test_registry_handler_points_to_launch_portal() -> None:
    """Registered handler must reference portal_supervisor.py, either directly or
    via the staged .ps1 it indirects through."""
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\portal\shell\open\command",
        )
        value, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
    except FileNotFoundError:
        pytest.fail("portal:// protocol not registered")
    resolved = value + _resolve_staged_indirection(value)
    assert "portal_supervisor.py" in resolved, (
        f"Registry handler (and any staged launcher it delegates to) does not reference portal_supervisor.py: {value}"
    )


# ---------------------------------------------------------------------------
# portal.html — launchServers() uses the resident supervisor
# ---------------------------------------------------------------------------

def test_launch_servers_no_window_location(portal_text: str) -> None:
    """launchServers() must not navigate away from the resident supervisor shell."""
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
        "launchServers() must not navigate away while requesting Restart All"
    )


def test_launch_servers_posts_directly_to_supervisor(portal_text: str) -> None:
    """Restart All must use the resident API instead of the legacy portal protocol."""
    fn_match = re.search(
        r"function launchServers\(\)\s*\{(.*?)\n    \}",
        portal_text,
        re.DOTALL,
    )
    assert fn_match, "launchServers() not found in portal.html"
    body = fn_match.group(1)
    assert "fetch('/api/restart-all', {method: 'POST'})" in body
    assert "portal://launch" not in body
    assert "invokePortalLaunch" not in body


def test_launch_servers_resumes_polling_after_bounded_busy_state(portal_text: str) -> None:
    """Restart All must restore its button and live polling after a bounded delay."""
    fn_match = re.search(
        r"function launchServers\(\)\s*\{(.*?)\n    \}",
        portal_text,
        re.DOTALL,
    )
    assert fn_match, "launchServers() not found in portal.html"
    body = fn_match.group(1)
    assert "btn.disabled = true" in body
    assert "setTimeout" in body
    assert "1000" in body
    assert "pollServers()" in body
    assert "if (operationComplete)" in portal_text
    assert "btn.disabled = false" in portal_text


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
