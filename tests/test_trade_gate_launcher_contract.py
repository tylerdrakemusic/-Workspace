from __future__ import annotations

import json
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = WORKTREE_ROOT / "tools" / "start_trade_gate.ps1"
PORTAL_SERVERS = WORKTREE_ROOT / "tools" / "portal_servers.json"


def test_trade_gate_launcher_owns_source_port_and_stale_process_cleanup() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert '[string]$ProjectRoot = "f:\\ΣCapital"' in launcher
    assert "$Port = 7475" in launcher
    assert "TRADE_GATE_PROCESS_OWNER" in launcher
    assert "TRADE_GATE_SOURCE_ENTRYPOINT" in launcher
    assert "Get-CimInstance Win32_Process" in launcher
    assert "Stop-Process" in launcher
    assert "src\\utils\\trade_gate.py" in launcher
    assert "Get-NetTCPConnection -LocalPort $Port -State Listen" in launcher


def test_trade_gate_launcher_fails_closed_on_listener_inspection_errors() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue" not in launcher
    assert "-ErrorAction Stop" in launcher
    assert "catch" in launcher
    assert "${Port}:" in launcher


def test_trade_gate_launcher_requires_exact_normalized_source_entrypoint_match() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    assert "GetFullPath" in launcher
    assert "ToLowerInvariant" in launcher
    assert "-notlike \"*$sourceEntrypoint*\"" not in launcher
    assert "src\\utils\\trade_gate.py*" not in launcher


def test_portal_registers_the_same_authoritative_launcher() -> None:
    config = json.loads(PORTAL_SERVERS.read_text(encoding="utf-8-sig"))
    trade_gate = next((item for item in config["servers"] if item["port"] == 7475), None)

    assert trade_gate is not None, "Trade Gate server entry for port 7475 is missing from portal_servers.json"

    assert trade_gate["project"] == "ΣCapital"
    assert "start_trade_gate.ps1" in trade_gate["cmd"]