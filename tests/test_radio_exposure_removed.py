from __future__ import annotations

import json
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
OPEN_PORTAL = WORKSPACE_ROOT / "open_portal.ps1"
SERVERS = WORKSPACE_ROOT / "tools" / "portal_servers.json"
PORTAL = WORKSPACE_ROOT / "reports" / "portal.html"
DISCOVERY_AGENT = WORKSPACE_ROOT / ".github" / "agents" / "⊕workspace-discovery.agent.md"
sys.path.insert(0, str(WORKSPACE_ROOT / "tools"))
import dashboard_registry  # noqa: E402


def test_portal_does_not_register_radio_or_icecast() -> None:
    entries = json.loads(SERVERS.read_text(encoding="utf-8-sig"))["servers"]
    names = {entry["name"] for entry in entries}
    ports = {entry["port"] for entry in entries}

    assert "TJD Radio" not in names
    assert "Icecast (TJD Radio)" not in names
    assert 8100 not in ports
    assert 18000 not in ports


def test_generated_portal_does_not_contain_retired_radio_surface() -> None:
    portal_text = PORTAL.read_text(encoding="utf-8")

    for marker in ("TJD Radio", "Icecast", "localhost:8100", "localhost:18000"):
        assert marker not in portal_text


def test_dashboard_discovery_does_not_reintroduce_retired_music_radio() -> None:
    manifest = dashboard_registry.build_manifest()

    assert all(
        not (
            dashboard.get("project") == "❤Music"
            and dashboard.get("id") == "tjd-radio"
        )
        for dashboard in manifest["dashboards"]
    )


def test_portal_launcher_does_not_start_radio_or_icecast() -> None:
    launcher_text = OPEN_PORTAL.read_text(encoding="utf-8").lower()

    assert "tjd radio" not in launcher_text
    assert "start_tjd_radio.ps1" not in launcher_text
    assert "start_icecast.ps1" not in launcher_text
    assert "8100" not in launcher_text
    assert "18000" not in launcher_text


def test_workspace_roadmap_does_not_advertise_active_tjd_radio_work() -> None:
    roadmap_text = DISCOVERY_AGENT.read_text(encoding="utf-8").lower()

    assert "ship public launch plan for tjd radio" not in roadmap_text
    assert "quantum-shuffle" not in roadmap_text


def test_neighboring_portal_services_remain_registered() -> None:
    entries = json.loads(SERVERS.read_text(encoding="utf-8-sig"))["servers"]
    names = {entry["name"] for entry in entries}

    assert "Music Dashboard" in names
    assert "Guitar Trainer" in names
    assert "Studio Equipment" in names