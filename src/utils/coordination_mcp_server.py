"""Governed MCP operations for the workspace FR ledger."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from mcp.server.fastmcp import FastMCP

FR_CLI_PATH = Path(__file__).with_name("fr_cli.py")
_ALLOWED_OPERATIONS = frozenset(
    {
        "fr.get",
        "fr.record_event",
        "fr.record_artifact",
        "fr.reconcile_cost_unavailable",
    }
)
_FORBIDDEN_ARGUMENTS = frozenset({"db", "sql"})


def _run_fr_cli(operation: str, payload: dict[str, Any]) -> str:
    """Run one fixed fr_cli command; callers cannot supply a command or SQL."""
    if operation == "fr.get":
        args = ["get", payload["fr_id"]]
    elif operation == "fr.record_event":
        args = [
            "record-event",
            payload["fr_id"],
            payload["agent"],
            payload["event_type"],
            payload["summary"],
        ]
    elif operation == "fr.record_artifact":
        args = [
            "record-artifact",
            payload["fr_id"],
            payload["artifact_type"],
            payload["label"],
        ]
    else:
        args = [
            "cost-reconcile-unavailable",
            payload["fr_id"],
            "--source",
            payload["source"],
            "--reason",
            payload["reason"],
        ]
    if operation == "fr.record_artifact" and payload.get("path"):
        args.extend(["--path", payload["path"]])
    result = subprocess.run(  # nosec B603 — executable and arguments are fixed above
        [sys.executable, str(FR_CLI_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=10,
    )
    return result.stdout.strip()


def invoke_coordination(operation: str, payload: Mapping[str, Any]) -> str:
    """Invoke one allowlisted FR ledger operation."""
    if operation not in _ALLOWED_OPERATIONS:
        raise ValueError(f"unsupported coordination operation: {operation}")
    if _FORBIDDEN_ARGUMENTS.intersection(payload):
        raise ValueError("database and SQL arguments are not supported")
    allowed_fields = {
        "fr.get": {"fr_id"},
        "fr.record_event": {"fr_id", "agent", "event_type", "summary"},
        "fr.record_artifact": {"fr_id", "artifact_type", "label", "path"},
        "fr.reconcile_cost_unavailable": {"fr_id", "source", "reason"},
    }[operation]
    if set(payload) - allowed_fields:
        raise ValueError("unexpected arguments for coordination operation")
    return _run_fr_cli(operation, dict(payload))


mcp = FastMCP(
    "workspace-coordination",
    instructions=(
        "Governed FR ledger operations only. FR state mutations remain canonical "
        "through fr_cli.py; arbitrary database names and SQL are unsupported."
    ),
)


@mcp.tool()
def get_fr(fr_id: str) -> str:
    """Read one feature request from the canonical FR ledger."""
    return invoke_coordination("fr.get", {"fr_id": fr_id})


@mcp.tool()
def record_fr_event(fr_id: str, agent: str, event_type: str, summary: str) -> str:
    """Append an event through the canonical FR CLI."""
    return invoke_coordination(
        "fr.record_event",
        {"fr_id": fr_id, "agent": agent, "event_type": event_type, "summary": summary},
    )


@mcp.tool()
def record_fr_artifact(
    fr_id: str, artifact_type: str, label: str, path: str | None = None
) -> str:
    """Append an artifact through the canonical FR CLI."""
    payload: dict[str, Any] = {
        "fr_id": fr_id,
        "artifact_type": artifact_type,
        "label": label,
    }
    if path is not None:
        payload["path"] = path
    return invoke_coordination("fr.record_artifact", payload)


@mcp.tool()
def reconcile_fr_cost_unavailable(fr_id: str, source: str, reason: str) -> str:
    """Record an explicit unavailable historical cost outcome."""
    return invoke_coordination(
        "fr.reconcile_cost_unavailable",
        {"fr_id": fr_id, "source": source, "reason": reason},
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")