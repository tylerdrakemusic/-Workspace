from __future__ import annotations

from pathlib import Path
import re

import pytest


def test_fr_event_operation_delegates_to_canonical_fr_cli(monkeypatch):
    from src.utils.coordination_mcp_server import invoke_coordination

    calls: list[tuple[str, dict]] = []

    def fake_run(operation: str, payload: dict) -> str:
        calls.append((operation, payload))
        return "event recorded"

    monkeypatch.setattr(
        "src.utils.coordination_mcp_server._run_fr_cli", fake_run
    )

    result = invoke_coordination(
        "fr.record_event",
        {
            "fr_id": "FR-20260809-example",
            "agent": "test-agent",
            "event_type": "finding",
            "summary": "coverage recorded",
        },
    )

    assert result == "event recorded"
    assert calls == [
        (
            "fr.record_event",
            {
                "fr_id": "FR-20260809-example",
                "agent": "test-agent",
                "event_type": "finding",
                "summary": "coverage recorded",
            },
        )
    ]


def test_unknown_operation_is_rejected():
    from src.utils.coordination_mcp_server import invoke_coordination

    with pytest.raises(ValueError, match="unsupported coordination operation"):
        invoke_coordination("db.read_query", {})


def test_fr_cli_command_mapping_is_fixed(monkeypatch):
    from src.utils import coordination_mcp_server

    captured: dict[str, object] = {}

    class Result:
        stdout = "artifact recorded\n"

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return Result()

    monkeypatch.setattr(coordination_mcp_server.subprocess, "run", fake_run)

    result = coordination_mcp_server._run_fr_cli(
        "fr.record_artifact",
        {
            "fr_id": "FR-20260809-example",
            "artifact_type": "test_pass",
            "label": "focused tests",
            "path": "tests/test_coordination_mcp_server.py",
        },
    )

    assert result == "artifact recorded"
    assert captured["args"] == [
        coordination_mcp_server.sys.executable,
        str(coordination_mcp_server.FR_CLI_PATH),
        "record-artifact",
        "FR-20260809-example",
        "test_pass",
        "focused tests",
        "--path",
        "tests/test_coordination_mcp_server.py",
    ]


@pytest.mark.parametrize("field", ["db", "sql"])
def test_arbitrary_database_and_sql_inputs_are_rejected(field: str):
    from src.utils.coordination_mcp_server import invoke_coordination

    with pytest.raises(ValueError, match="database and SQL arguments are not supported"):
        invoke_coordination(
            "fr.record_event",
            {
                "fr_id": "FR-20260809-example",
                "agent": "test-agent",
                "event_type": "finding",
                "summary": "coverage recorded",
                field: "SELECT * FROM anything",
            },
        )


def test_coordination_mcp_docs_define_deterministic_routing_and_fallback():
    repo_root = Path(__file__).resolve().parents[1]
    registry = (repo_root / "MCP_REGISTRY.md").read_text(encoding="utf-8")
    instructions = (
        repo_root / ".github" / "instructions" / "feature-request-flow.instructions.md"
    ).read_text(encoding="utf-8")
    registry = re.sub(r"\s+", " ", registry)
    instructions = re.sub(r"\s+", " ", instructions)

    required_phrases = (
        "deterministic MCP-first invocation",
        "fixed allowlisted operations",
        "explicit local fallback",
        "coordination MCP is unavailable",
    )
    for phrase in required_phrases:
        assert phrase in registry
        assert phrase in instructions