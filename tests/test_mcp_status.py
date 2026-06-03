from __future__ import annotations

from unittest.mock import Mock

from src.utils.mcp_status import _probe_command_server


def test_probe_npx_uses_npm_fallback_when_npx_missing(monkeypatch):
    monkeypatch.setattr("src.utils.mcp_status.which", lambda cmd: None if cmd in ("npx", "npx.cmd") else "C:\\Program Files\\nodejs\\npm.CMD")

    status = _probe_command_server("playwright", {"command": "npx", "args": []})

    assert status["status"] == "ok"
    assert "npm reachable" in status["detail"]


def test_probe_npx_reports_error_when_neither_npx_nor_npm_exist(monkeypatch):
    monkeypatch.setattr("src.utils.mcp_status.which", lambda cmd: None)

    status = _probe_command_server("playwright", {"command": "npx", "args": []})

    assert status["status"] == "error"
    assert status["detail"] == "npx not found on PATH"


def test_probe_npx_reports_ok_when_npx_resolves(monkeypatch):
    monkeypatch.setattr("src.utils.mcp_status.which", lambda cmd: "C:\\Program Files\\nodejs\\npx.CMD")
    mock_result = Mock(returncode=0, stdout="10.0.0", stderr="")
    monkeypatch.setattr(
        "src.utils.mcp_status.subprocess.run",
        lambda *args, **kwargs: mock_result,
    )

    status = _probe_command_server("playwright", {"command": "npx", "args": []})

    assert status["status"] == "ok"
    assert status["detail"] == "npx reachable"
