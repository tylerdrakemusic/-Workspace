"""
Tests for FR-20260425-guitar-trainer-panel-startup.

Covers:
  - Port uniqueness: 5055 does not conflict with any other portal service
  - open_portal.ps1: Guitar Trainer server startup block is present and correct
  - portal.html pane-3: no live-dash/live-header/open-btn chrome; bare iframe only
  - portal.html SERVERS array: 5055 entry is present for status polling
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

_ON_CI = bool(os.getenv("CI"))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WORKSPACE_ROOT    = Path(__file__).resolve().parents[1]
PORTAL_HTML       = WORKSPACE_ROOT / "reports" / "portal.html"
OPEN_PORTAL_PS    = WORKSPACE_ROOT / "open_portal.ps1"
LAUNCH_PORTAL_PS  = WORKSPACE_ROOT / "tools" / "launch_portal.ps1"
SERVERS_JSON      = WORKSPACE_ROOT / "tools" / "portal_servers.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def portal_text() -> str:
    if not PORTAL_HTML.is_file():
        pytest.skip(f"portal.html not generated — skipping: {PORTAL_HTML}")
    return PORTAL_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def open_portal_text() -> str:
    return OPEN_PORTAL_PS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def launch_portal_text() -> str:
    return LAUNCH_PORTAL_PS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def servers_json() -> dict:
    import json
    # portal_servers.json may be written by PowerShell with a UTF-8 BOM
    return json.loads(SERVERS_JSON.read_text(encoding="utf-8-sig"))


@pytest.fixture(scope="module")
def guitar_trainer_pane_id(portal_text: str) -> str:
    """Resolve the dash-pane id whose iframe points at :5055.

    Pane indices are assigned by dashboard registry order, which shifts
    whenever a new dashboard is added (e.g. Band Management). Do not
    hardcode a pane number — look it up by iframe src instead.
    """
    match = re.search(
        r'<div class="dash-pane" id="(pane-\d+)"[^>]*>\s*'
        r'<iframe src="http://localhost:5055"',
        portal_text,
    )
    if not match:
        pytest.skip("No pane with a :5055 iframe found in portal.html")
    return match.group(1)


# ---------------------------------------------------------------------------
# Port conflict checks
# ---------------------------------------------------------------------------

_KNOWN_PORTS: dict[str, int] = {
    "infinitelife_http": 9999,
    "fr_ledger":         7474,
    "music_dashboard":   5050,
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
# Supervisor-owned Guitar Trainer startup
# ---------------------------------------------------------------------------

def test_supervisor_config_starts_guitar_trainer(servers_json: dict) -> None:
    """The canonical supervisor config owns the Guitar Trainer launch contract."""
    entry = next(s for s in servers_json["servers"] if s["name"] == "Guitar Trainer")
    assert entry["port"] == 5055
    assert entry["cmd"].endswith("start_guitar_trainer.ps1")
    assert entry["working_directory"] == "f:\\❤Music"


def test_supervisor_config_checks_guitar_trainer_http_readiness(servers_json: dict) -> None:
    """Guitar Trainer readiness must use its configured HTTP endpoint."""
    entry = next(s for s in servers_json["servers"] if s["name"] == "Guitar Trainer")
    assert entry["readiness_url"] == "http://127.0.0.1:5055/"
    assert 200 in entry["accepted_statuses"]


def test_manual_launcher_delegates_guitar_trainer_ownership(open_portal_text: str) -> None:
    """The manual launcher delegates all service behavior to the supervisor."""
    assert "portal_supervisor.py" in open_portal_text
    assert "start_guitar_trainer.ps1" not in open_portal_text
    assert "Get-NetTCPConnection" not in open_portal_text


def test_manual_launcher_contains_no_browser_open_implementation(open_portal_text: str) -> None:
    """The resident supervisor owns browser timing while services warm."""
    assert "Start-Process" not in open_portal_text
    assert "portal_supervisor.py" in open_portal_text


# ---------------------------------------------------------------------------
# portal.html pane-3 — bare iframe, no live-dash chrome
# ---------------------------------------------------------------------------

def test_pane9_has_no_live_dash_wrapper(portal_text: str, guitar_trainer_pane_id: str) -> None:
    """Guitar Trainer pane must not contain a .live-dash wrapper."""
    pane9_match = re.search(rf'id="{guitar_trainer_pane_id}"[^>]*>(.*?)</div>', portal_text, re.DOTALL)
    assert pane9_match, f"{guitar_trainer_pane_id} not found in portal.html"
    inner = pane9_match.group(1)
    assert "live-dash" not in inner, (
        f"{guitar_trainer_pane_id} still contains 'live-dash' wrapper — should be bare iframe"
    )


def test_pane9_has_no_live_header(portal_text: str, guitar_trainer_pane_id: str) -> None:
    """Guitar Trainer pane must not contain the live-header div."""
    pane9_match = re.search(rf'id="{guitar_trainer_pane_id}"[^>]*>(.*?)</div>', portal_text, re.DOTALL)
    assert pane9_match, f"{guitar_trainer_pane_id} not found in portal.html"
    inner = pane9_match.group(1)
    assert "live-header" not in inner, (
        f"{guitar_trainer_pane_id} still contains 'live-header' element"
    )


def test_pane9_has_no_open_in_browser_button(portal_text: str, guitar_trainer_pane_id: str) -> None:
    """Guitar Trainer pane must not contain the 'Open in Browser' link."""
    pane9_match = re.search(rf'id="{guitar_trainer_pane_id}"[^>]*>(.*?)</div>', portal_text, re.DOTALL)
    assert pane9_match, f"{guitar_trainer_pane_id} not found in portal.html"
    inner = pane9_match.group(1)
    assert "open-btn" not in inner, (
        f"{guitar_trainer_pane_id} still contains 'open-btn' element"
    )
    assert "Open in Browser" not in inner, (
        f"{guitar_trainer_pane_id} still contains 'Open in Browser' text"
    )


def test_pane9_iframe_points_to_5055(portal_text: str, guitar_trainer_pane_id: str) -> None:
    """Guitar Trainer pane iframe src must point to localhost:5055."""
    if _ON_CI:
        pytest.skip("Guitar Trainer pane content is environment-specific; requires local multi-project checkout")
    pane9_match = re.search(rf'id="{guitar_trainer_pane_id}"[^>]*>.*?</div>', portal_text, re.DOTALL)
    assert pane9_match, f"{guitar_trainer_pane_id} not found in portal.html"
    block = pane9_match.group(0)
    assert 'src="http://localhost:5055"' in block, (
        f"{guitar_trainer_pane_id} iframe does not point to http://localhost:5055"
    )


def test_pane9_is_bare_iframe(portal_text: str, guitar_trainer_pane_id: str) -> None:
    """Guitar Trainer pane's full element must be exactly: dash-pane div containing a single iframe."""
    if _ON_CI:
        pytest.skip("Guitar Trainer pane content is environment-specific; requires local multi-project checkout")
    # Match the complete pane div (self-contained on one line as generated)
    pane9_match = re.search(
        rf'<div class="dash-pane" id="{guitar_trainer_pane_id}"[^>]*>(.*?)</div>',
        portal_text,
        re.DOTALL,
    )
    assert pane9_match, f"{guitar_trainer_pane_id} not found in portal.html"
    inner = pane9_match.group(1).strip()
    # Inner content should be a single iframe tag and nothing else
    assert inner.startswith("<iframe"), f"{guitar_trainer_pane_id} inner content does not start with <iframe>: {inner[:80]}"
    assert inner.endswith(">") or inner.endswith("></iframe>"), (
        f"{guitar_trainer_pane_id} inner content has unexpected trailing content: {inner[-80:]}"
    )
    assert inner.count("<div") == 0, f"{guitar_trainer_pane_id} contains unexpected nested <div> elements"


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


# ---------------------------------------------------------------------------
# launch_portal.ps1 delegates readiness and browser timing
# ---------------------------------------------------------------------------

def test_launch_portal_delegates_readiness_and_browser_timing(launch_portal_text: str) -> None:
    """The compatibility launcher must delegate cold-start handling."""
    assert "portal_supervisor.py" in launch_portal_text
    assert "Wait-PortListening" not in launch_portal_text
    assert "Start-Process" not in launch_portal_text
