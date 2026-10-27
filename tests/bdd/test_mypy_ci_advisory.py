from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from pathlib import Path
from typing import Any

from pytest_bdd import given, scenarios, then, when


scenarios("mypy_advisory.feature")


@given(
    "the Workspace pilot module scope is selected from its existing configuration, tests, and CI conventions",
    target_fixture="mypy_run",
)
def selected_workspace_mypy_scope(
    tmp_path: Path,
    monkeypatch: Any,
) -> dict[str, Any]:
    helper = importlib.import_module("tools.mypy_ci_advisory")
    config_path = tmp_path / "mypy.ini"
    config_content = (
        "[mypy]\n"
        "python_version = 3.11\n"
        "files = src/utils/roadmap_parsing.py, src/utils/roadmap_quarters.py\n"
    )
    config_path.write_text(config_content, encoding="utf-8")
    local_dir = tmp_path / "mypy-advisory-local" / "run-123-1"
    ci_dir = tmp_path / "mypy-advisory-ci" / "run-123-1"
    step_summary = tmp_path / "step-summary.md"
    finding_output = (
        "src/utils/roadmap_quarters.py:17: error: invalid return [return-value]\n"
        "src/utils/roadmap_parsing.py:4: error: incompatible assignment [assignment]\n"
    )
    commands: list[tuple[str, ...]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(tuple(command))
        if command[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(
                command, 0, "1234567890abcdef1234567890abcdef12345678\n", ""
            )
        if command[-1:] == ["--version"]:
            return subprocess.CompletedProcess(command, 0, "mypy 1.18.2 (compiled: yes)\n", "")
        return subprocess.CompletedProcess(command, 1, finding_output, "")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    monkeypatch.setenv("GITHUB_REPOSITORY", "tylerdrakemusic/-Workspace")
    monkeypatch.setenv("MYPY_INSTALL_EXIT_CODE", "0")
    return {
        "helper": helper,
        "args": [
            "--config-path",
            str(config_path),
            "--local-output-dir",
            str(local_dir),
            "--ci-output-dir",
            str(ci_dir),
            "--step-summary",
            str(step_summary),
        ],
        "config_path": config_path,
        "local_dir": local_dir,
        "ci_dir": ci_dir,
        "step_summary": step_summary,
        "finding_output": finding_output,
        "commands": commands,
    }


@when("advisory mypy runs")
def run_mypy_advisory(mypy_run: dict[str, Any], capsys: Any) -> None:
    mypy_run["exit_code"] = mypy_run["helper"].main(mypy_run["args"])
    mypy_run["captured"] = capsys.readouterr()
    mypy_run["artifact_path"] = mypy_run["ci_dir"] / "summary.json"
    mypy_run["artifact"] = json.loads(mypy_run["artifact_path"].read_text(encoding="utf-8"))


@then(
    "it reports findings for that scope without failing CI, and pytest remains the required quality gate"
)
def report_is_advisory_and_complete(mypy_run: dict[str, Any]) -> None:
    artifact = mypy_run["artifact"]
    config_path = mypy_run["config_path"]
    scope = ["src/utils/roadmap_parsing.py", "src/utils/roadmap_quarters.py"]
    summary_text = mypy_run["step_summary"].read_text(encoding="utf-8")

    assert mypy_run["exit_code"] == 0, "Mypy findings must remain advisory"
    assert artifact["repository"] == "tylerdrakemusic/-Workspace"
    assert artifact["commit"] == "1234567890abcdef1234567890abcdef12345678"
    assert artifact["mypy_version"] == "1.18.2"
    assert artifact["configuration"] == {
        "path": "mypy.ini",
        "sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    }
    assert artifact["scan_scope"] == scope
    assert isinstance(artifact["elapsed_seconds"], (int, float))
    assert artifact["elapsed_seconds"] >= 0
    assert artifact["finding_count"] == 2
    assert artifact["command_exit_codes"] == {
        "mypy_install": 0,
        "mypy_version": 0,
        "mypy_check": 1,
    }
    assert artifact["tool_errors"] == {
        "mypy_install": False,
        "mypy_version": False,
        "mypy_check": False,
    }

    mypy_command = next(command for command in mypy_run["commands"] if "--config-file" in command)
    assert mypy_command[-2:] == tuple(scope)
    assert "--fix" not in mypy_command
    assert "Repository: `tylerdrakemusic/-Workspace`" in summary_text
    assert "Scanned commit: `1234567890abcdef1234567890abcdef12345678`" in summary_text
    assert "Mypy version: `1.18.2`" in summary_text
    assert f"Config: `mypy.ini` SHA-256 `{artifact['configuration']['sha256']}`" in summary_text
    assert f"Scope: {', '.join(scope)}" in summary_text
    assert "Findings: `2`" in summary_text
    assert "Advisory only" in summary_text

    ci_output = (
        "\n".join(
            path.read_text(encoding="utf-8")
            for path in mypy_run["ci_dir"].iterdir()
            if path.is_file()
        )
        + summary_text
        + mypy_run["captured"].out
        + mypy_run["captured"].err
    )
    assert mypy_run["finding_output"] not in ci_output
    assert {path.name for path in mypy_run["ci_dir"].iterdir()} == {"summary.json"}
    local_output = "\n".join(
        path.read_text(encoding="utf-8")
        for path in mypy_run["local_dir"].iterdir()
        if path.is_file()
    )
    assert mypy_run["finding_output"] in local_output
