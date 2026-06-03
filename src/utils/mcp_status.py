"""
MCP Server Status Writer
Probes each command-type MCP server defined in the user's mcp.json and writes
a status snapshot to src/config/mcp_status.json.

Run at workspace open via VS Code task (folderOpen trigger).
Read by orchestrator agents during Context Bootstrap for pre-flight awareness.

Usage:
    C:/G/python.exe f:/⊕Workspace/src/utils/mcp_status.py
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone
from pathlib import Path
from shutil import which

APPDATA_PATH = os.environ.get("APPDATA")
if APPDATA_PATH is None:
    APPDATA_PATH = Path.home() / ".config" / "Code"
MCP_JSON_PATH = Path(APPDATA_PATH) / "User" / "mcp.json"
OUTPUT_PATH = Path(__file__).parent.parent / "config" / "mcp_status.json"

# HTTP servers are always-on (managed by VS Code / GitHub Copilot extension).
# Only command-type servers need probing.
HTTP_SERVERS = {"github"}


def _probe_command_server(name: str, server: dict) -> dict:
    """
    Try to start the server command with --version or --help to verify the
    executable is reachable. We only care about exit code / error, not output.
    Returns a status dict: {"status": "ok"|"error", "detail": str}.
    """
    command = server.get("command", "")
    args = server.get("args", [])

    # For npx-based servers check that npx itself resolves.
    # For python-based servers check that the script file exists.
    if command in ("npx", "npx.cmd"):
        # Quick check: can we resolve npx, or fall back to npm if npx is missing.
        npx_path = which(command)
        if npx_path is None:
            if which("npm") is not None:
                return {
                    "status": "ok",
                    "detail": "npm reachable; npx fallback available",
                }
            return {"status": "error", "detail": "npx not found on PATH"}

        try:
            result = subprocess.run(  # nosec B603,B607
                [npx_path, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )
            if result.returncode == 0:
                return {"status": "ok", "detail": "npx reachable"}
            return {"status": "error", "detail": f"npx exit {result.returncode}"}
        except FileNotFoundError:
            return {"status": "error", "detail": "npx not found on PATH"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "detail": "npx probe timed out"}

    elif command.endswith("python.exe") or command == "python":
        # Check that the script argument exists on disk.
        script = next((a for a in args if a.endswith(".py")), None)
        if script and not Path(script).exists():
            return {"status": "error", "detail": f"script not found: {script}"}
        try:
            result = subprocess.run(  # nosec B603,B607
                [command, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )
            if result.returncode == 0:
                return {"status": "ok", "detail": result.stdout.strip() or "python reachable"}
            return {"status": "error", "detail": f"python exit {result.returncode}"}
        except FileNotFoundError:
            return {"status": "error", "detail": f"python not found: {command}"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "detail": "python probe timed out"}

    return {"status": "ok", "detail": "unchecked (unknown command type)"}


def write_status() -> dict:
    """Read mcp.json, probe each command-type server, write mcp_status.json."""
    if not MCP_JSON_PATH.exists():
        print(f"[mcp_status] WARNING: mcp.json not found at {MCP_JSON_PATH}", file=sys.stderr)
        status = {"generated_at": datetime.now(timezone.utc).isoformat(), "servers": {}}
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")
        return status

    with open(MCP_JSON_PATH, encoding="utf-8") as f:
        mcp_config = json.load(f)

    servers = mcp_config.get("servers", {})
    results: dict[str, dict] = {}

    for name, server_cfg in servers.items():
        server_type = server_cfg.get("type", "command")
        if name in HTTP_SERVERS or server_type == "http":
            results[name] = {"status": "http", "detail": "always-on (HTTP)"}
        else:
            probe = _probe_command_server(name, server_cfg)
            auto_start = server_cfg.get("autoStart", False)
            results[name] = {
                "status": probe["status"],
                "detail": probe["detail"],
                "autoStart": auto_start,
            }

    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "servers": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")

    # Print a banner for the VS Code terminal output
    print(f"[mcp_status] Status written → {OUTPUT_PATH}")
    for name, info in results.items():
        icon = "✓" if info["status"] in ("ok", "http") else "✗"
        print(f"  {icon} {name}: {info['status']} — {info['detail']}")

    return status


if __name__ == "__main__":
    write_status()
