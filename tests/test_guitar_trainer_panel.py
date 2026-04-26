"""
Tests for FR-20260425-guitar-trainer-panel-startup.

Covers:
  - Port uniqueness: 5055 does not conflict with any other portal service
  - open_portal.ps1: Guitar Trainer server startup block is present and correct
  - portal.html pane-9: no live-dash/live-header/open-btn chrome; bare iframe only
  - portal.html SERVERS array: 5055 entry is present for status polling
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PORTAL_HTML    = WORKSPACE_ROOT / "reports" / "portal.html"
OPEN_PORTAL_PS = WORKSPACE_ROOT / "open_portal.ps1"
SERVERS_JSON   = WORKSPACE_ROOT / "tools" / "portal_servers.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def portal_text() -> str:
    return PORTAL_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def open_portal_text() -> str:
    return OPEN_PORTAL_PS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def servers_json() -> dict:
    import json
    # portal_servers.json may be written by PowerShell with a UTF-8 BOM
    return json.loads(SERVERS_JSON.read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------------------
# Port conflict checks
# ---------------------------------------------------------------------------

_KNOWN_PORTS: dict[str, int] = {
    "infinitelife_http": 9999,
    "fr_ledger":         7474,
    "music_dashboard":   5050,
    "tjd_radio":         8100,
    "guitar_trainer":    5055,
}


def test_port_registry_no_duplicates() -> None:
    """All workspace portal ports must be unique."""
    ports = list(_KNOWN_PORTS.values())
    assert len(ports) == len(set(ports)), (
        f"Duplicate port found: {[p for p in ports if ports.count(p) > 1]}"
    )


def test_guitar_trainer_port_not_used_by_other_services() -> None:
    """5055 must not match any other named service port."""
    gt_port = _KNOWN_PORTS["guitar_trainer"]
    others = {k: v for k, v in _KNOWN_PORTS.items() if k != "guitar_trainer"}
    conflicts = [k for k, v in others.items() if v == gt_port]
    assert not conflicts, f"Port {gt_port} also claimed by: {conflicts}"


def test_servers_json_guitar_trainer_port(servers_json: dict) -> None:
    """portal_servers.json entry for Guitar Trainer must use port 5055."""
    entries = servers_json.get("servers", [])
    gt = next((s for s in entries if s.get("name") == "Guitar Trainer"), None)
    assert gt is not None, "Guitar Trainer entry missing from portal_servers.json"
    assert gt["port"] == 5055, f"Expected port 5055, got {gt['port']}"


def test_servers_json_all_ports_unique(servers_json: dict) -> None:
    """portal_servers.json must have no duplicate ports."""
    ports = [s["port"] for s in servers_json.get("servers", [])]
    assert len(ports) == len(set(ports)), (
        f"Duplicate port in portal_servers.json: {[p for p in ports if ports.count(p) > 1]}"
    )


# ---------------------------------------------------------------------------
# open_portal.ps1 — Guitar Trainer startup block
# ---------------------------------------------------------------------------

def test_open_portal_starts_guitar_trainer(open_portal_text: str) -> None:
    """open_portal.ps1 must reference port 5055 for Guitar Trainer."""
    assert "5055" in open_portal_text, (
        "open_portal.ps1 does not reference Guitar Trainer port 5055"
    )


def test_open_portal_uses_start_guitar_trainer_script(open_portal_text: str) -> None:
    """open_portal.ps1 must invoke start_guitar_trainer.ps1."""
    assert "start_guitar_trainer.ps1" in open_portal_text, (
        "open_portal.ps1 does not reference start_guitar_trainer.ps1"
    )


def test_open_portal_guitar_trainer_checks_existing_process(open_portal_text: str) -> None:
    """Guitar Trainer startup must guard with Get-NetTCPConnection (skip-if-running)."""
    # The block must contain a Get-NetTCPConnection guard for 5055
    pattern = re.compile(r"Get-NetTCPConnection.*5055", re.DOTALL)
    assert pattern.search(open_portal_text), (
        "open_portal.ps1 is missing a Get-NetTCPConnection guard for port 5055"
    )


def test_open_portal_guitar_trainer_before_open(open_portal_text: str) -> None:
    """Guitar Trainer startup block must appear before the portal is opened."""
    gt_idx = open_portal_text.find("start_guitar_trainer.ps1")
    # Portal is now opened via HTTP server (Start-Process $PortalUrl) rather than
    # the old direct file open (Start-Process $PortalFile). Accept either form.
    open_idx = open_portal_text.find("Start-Process $PortalUrl")
    if open_idx == -1:
        open_idx = open_portal_text.find("Start-Process $PortalFile")
    assert gt_idx != -1, "start_guitar_trainer.ps1 not found in open_portal.ps1"
    assert open_idx != -1, "Portal open command not found in open_portal.ps1"
    assert gt_idx < open_idx, (
        "Guitar Trainer startup must come before portal is opened"
    )


# ---------------------------------------------------------------------------
# portal.html pane-9 — bare iframe, no live-dash chrome
# ---------------------------------------------------------------------------

def test_pane9_has_no_live_dash_wrapper(portal_text: str) -> None:
    """pane-9 must not contain a .live-dash wrapper."""
    pane9_match = re.search(r'id="pane-9"[^>]*>(.*?)</div>', portal_text, re.DOTALL)
    assert pane9_match, "pane-9 not found in portal.html"
    inner = pane9_match.group(1)
    assert "live-dash" not in inner, (
        "pane-9 still contains 'live-dash' wrapper — should be bare iframe"
    )


def test_pane9_has_no_live_header(portal_text: str) -> None:
    """pane-9 must not contain the live-header div."""
    pane9_match = re.search(r'id="pane-9"[^>]*>(.*?)</div>', portal_text, re.DOTALL)
    assert pane9_match, "pane-9 not found in portal.html"
    inner = pane9_match.group(1)
    assert "live-header" not in inner, (
        "pane-9 still contains 'live-header' element"
    )


def test_pane9_has_no_open_in_browser_button(portal_text: str) -> None:
    """pane-9 must not contain the 'Open in Browser' link."""
    pane9_match = re.search(r'id="pane-9"[^>]*>(.*?)</div>', portal_text, re.DOTALL)
    assert pane9_match, "pane-9 not found in portal.html"
    inner = pane9_match.group(1)
    assert "open-btn" not in inner, (
        "pane-9 still contains 'open-btn' element"
    )
    assert "Open in Browser" not in inner, (
        "pane-9 still contains 'Open in Browser' text"
    )


def test_pane9_iframe_points_to_5055(portal_text: str) -> None:
    """pane-9 iframe src must point to localhost:5055."""
    pane9_match = re.search(r'id="pane-9"[^>]*>.*?</div>', portal_text, re.DOTALL)
    assert pane9_match, "pane-9 not found in portal.html"
    block = pane9_match.group(0)
    assert 'src="http://localhost:5055"' in block, (
        "pane-9 iframe does not point to http://localhost:5055"
    )


def test_pane9_is_bare_iframe(portal_text: str) -> None:
    """pane-9 full element must be exactly: dash-pane div containing a single iframe."""
    # Match the complete pane-9 div (self-contained on one line as generated)
    pane9_match = re.search(
        r'<div class="dash-pane" id="pane-9"[^>]*>(.*?)</div>',
        portal_text,
        re.DOTALL,
    )
    assert pane9_match, "pane-9 not found in portal.html"
    inner = pane9_match.group(1).strip()
    # Inner content should be a single iframe tag and nothing else
    assert inner.startswith("<iframe"), f"pane-9 inner content does not start with <iframe>: {inner[:80]}"
    assert inner.endswith(">") or inner.endswith("></iframe>"), (
        f"pane-9 inner content has unexpected trailing content: {inner[-80:]}"
    )
    assert inner.count("<div") == 0, "pane-9 contains unexpected nested <div> elements"


# ---------------------------------------------------------------------------
# portal.html SERVERS array — 5055 present for status polling
# ---------------------------------------------------------------------------

def test_servers_array_contains_guitar_trainer_port(portal_text: str) -> None:
    """The SERVERS JS array in portal.html must include port 5055."""
    servers_match = re.search(r"const SERVERS\s*=\s*(\[.*?\]);", portal_text)
    assert servers_match, "SERVERS array not found in portal.html"
    servers_literal = servers_match.group(1)
    assert "5055" in servers_literal, (
        "SERVERS array does not include Guitar Trainer port 5055"
    )
    assert "Guitar Trainer" in servers_literal, (
        "SERVERS array does not include 'Guitar Trainer' label"
    )
