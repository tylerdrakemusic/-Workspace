from __future__ import annotations

import json
import re
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = WORKSPACE_ROOT / "tools"
CONFIG_PATH = TOOLS_ROOT / "portal_servers.json"
sys.path.insert(0, str(TOOLS_ROOT))

import portal_supervisor


def _read_launcher(name: str) -> str:
    return (TOOLS_ROOT / name).read_text(encoding="utf-8")


def test_music_launchers_accept_supervisor_project_root_and_preserve_contract() -> None:
    band_launcher = _read_launcher("start_band_mgmt.ps1")
    dashboard_launcher = _read_launcher("start_music_dashboard.ps1")

    for launcher in (band_launcher, dashboard_launcher):
        assert re.search(r"param\(\[string\]\$ProjectRoot", launcher)
        assert '$env:PYTHONUTF8 = "1"' in launcher

    assert "Get-ChildItem" not in band_launcher
    assert "Join-Path $ProjectRoot" in band_launcher
    assert "--serve" in band_launcher
    assert "--port','8765" in band_launcher

    assert "Join-Path $ProjectRoot" in dashboard_launcher
    assert "--port 5050 --no-open" in dashboard_launcher


def test_music_portal_config_keeps_expected_services_and_readiness_urls() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    services = {
        service["name"]: service
        for service in config["servers"]
        if service.get("name") in {"Band Management", "Music Dashboard"}
    }

    assert services["Band Management"]["port"] == 8765
    assert services["Band Management"]["readiness_url"] == "http://127.0.0.1:8765/"
    assert services["Band Management"]["working_directory"] == "f:\\❤Music"
    assert services["Music Dashboard"]["port"] == 5050
    assert services["Music Dashboard"]["readiness_url"] == "http://127.0.0.1:5050/"
    assert services["Music Dashboard"]["working_directory"] == "f:\\❤Music"


def test_supervisor_injects_project_root_into_power_shell_file_launchers() -> None:
    command = (
        "powershell.exe -NoProfile -File "
        "f:\\⊕Workspace\\tools\\start_music_dashboard.ps1"
    )

    assert portal_supervisor._launch_argv(command, r"f:\❤Music")[-2:] == [
        "-ProjectRoot",
        r"f:\❤Music",
    ]