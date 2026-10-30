from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from pathlib import Path
from typing import Any


def test_mypy_findings_are_reported_with_metadata_without_gating_ci(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
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
        "Found 2 errors in 2 files (checked 2 source files)\n"
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

    exit_code = helper.main(
        [
            "--config-path",
            str(config_path),
            "--local-output-dir",
            str(local_dir),
            "--ci-output-dir",
            str(ci_dir),
            "--step-summary",
            str(step_summary),
        ]
    )

    artifact_path = ci_dir / "summary.json"
    artifact_text = artifact_path.read_text(encoding="utf-8")
    summary_text = step_summary.read_text(encoding="utf-8")
    captured = capsys.readouterr()
    artifact = json.loads(artifact_text)
    scope = ["src/utils/roadmap_parsing.py", "src/utils/roadmap_quarters.py"]

    assert exit_code == 0, "Mypy findings must remain advisory"
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
    mypy_command = next(command for command in commands if "--config-file" in command)
    assert mypy_command[-2:] == tuple(scope)
    assert "Repository: `tylerdrakemusic/-Workspace`" in summary_text
    assert "Scanned commit: `1234567890abcdef1234567890abcdef12345678`" in summary_text
    assert "Mypy version: `1.18.2`" in summary_text
    assert f"Config: `mypy.ini` SHA-256 `{artifact['configuration']['sha256']}`" in summary_text
    assert f"Scope: {', '.join(scope)}" in summary_text
    assert "Findings: `2`" in summary_text
    assert "Advisory only" in summary_text

    ci_output = (
        "\n".join(path.read_text(encoding="utf-8") for path in ci_dir.iterdir() if path.is_file())
        + summary_text
        + captured.out
        + captured.err
    )
    assert finding_output not in ci_output
    assert {path.name for path in ci_dir.iterdir()} == {"summary.json"}
    local_output = "\n".join(
        path.read_text(encoding="utf-8") for path in local_dir.iterdir() if path.is_file()
    )
    assert finding_output in local_output


def test_missing_mypy_reports_unavailable_findings_and_check_error(tmp_path: Path) -> None:
    helper = importlib.import_module("tools.mypy_ci_advisory")
    config_path = tmp_path / "mypy.ini"
    config_path.write_text("[mypy]\n", encoding="utf-8")
    check_result = helper.CommandResult(1, stderr="No module named mypy")

    report = helper._build_report(
        config_path=config_path,
        scope=["src/utils/roadmap_parsing.py"],
        repository="tylerdrakemusic/-Workspace",
        commit="1234567890abcdef1234567890abcdef12345678",
        elapsed_seconds=0.1,
        installation_exit_code=1,
        version_result=helper.CommandResult(1, stderr="No module named mypy"),
        check_result=check_result,
    )

    assert helper._finding_count(check_result.stdout, check_result.returncode) is None
    assert report["finding_count"] is None
    assert report["tool_errors"]["mypy_check"] is True
