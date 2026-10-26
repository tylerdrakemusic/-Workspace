from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from pathlib import Path
from typing import Any


CHECK_PATH_SENTINEL = "ruff-check-SENTINEL-private.py"
FORMAT_PATH_SENTINEL = "ruff-format-SENTINEL-private.py"
SOURCE_SENTINEL = "SENTINEL_SOURCE_SNIPPET"
SECRET_SENTINEL = "SENTINEL_SECRET_VALUE"
URL_SENTINEL = "https://private.example/SENTINEL_REMOTE_URL"
SCAN_SCOPE = (
    "All non-ignored Python .py files under the repository root; Ruff defaults "
    "and ruff.toml exclude environments, caches, .worktrees, tmp, and output. "
    "Non-Python files, including databases, are not scanned."
)


def test_ci_report_and_step_summary_contain_only_ruff_aggregates(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    helper = importlib.import_module("tools.ruff_ci_advisory")
    config_path = tmp_path / "ruff.toml"
    config_content = "line-length = 100\n"
    config_path.write_text(config_content, encoding="utf-8")
    local_dir = tmp_path / "ruff-advisory-local" / "run-123-1"
    ci_dir = tmp_path / "ruff-advisory-ci" / "run-123-1"
    step_summary = tmp_path / "step-summary.md"

    check_json = json.dumps(
        [
            {
                "code": "F401",
                "message": SECRET_SENTINEL,
                "filename": CHECK_PATH_SENTINEL,
                "location": {"row": 1, "column": 1},
                "source": SOURCE_SENTINEL,
            },
            {
                "code": "E501",
                "message": SECRET_SENTINEL,
                "filename": CHECK_PATH_SENTINEL,
                "location": {"row": 2, "column": 1},
                "source": SOURCE_SENTINEL,
            },
        ]
    )
    format_output = (
        f"Would reformat: {FORMAT_PATH_SENTINEL}\n"
        f"--- {FORMAT_PATH_SENTINEL}\n"
        f"+++ {FORMAT_PATH_SENTINEL}\n"
        "@@ -1 +1 @@\n"
        f"-{SOURCE_SENTINEL}\n"
        f"+{SECRET_SENTINEL}\n"
        "2 files would be reformatted\n"
    )
    raw_stderr = f"{URL_SENTINEL} {SECRET_SENTINEL}"
    commands: list[tuple[str, ...]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(tuple(command))
        if command[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(
                command, 0, "1234567890abcdef1234567890abcdef12345678\n", ""
            )
        if command[-1:] == ["--version"]:
            return subprocess.CompletedProcess(command, 0, "ruff 0.17.2\n", "")
        if "check" in command:
            return subprocess.CompletedProcess(command, 1, check_json, raw_stderr)
        if "format" in command:
            return subprocess.CompletedProcess(command, 1, format_output, raw_stderr)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    monkeypatch.setenv("GITHUB_REPOSITORY", "tylerdrakemusic/workspace")
    monkeypatch.setenv("RUFF_INSTALL_EXIT_CODE", "0")

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
    log_text = captured.out + captured.err
    artifact = json.loads(artifact_text)

    assert exit_code == 0, "Ruff findings must remain advisory"
    assert set(artifact) == {
        "repository",
        "commit",
        "ruff_version",
        "config",
        "scan_scope",
        "elapsed_seconds",
        "finding_counts",
        "command_exit_codes",
        "tool_errors",
    }
    assert artifact["repository"] == "tylerdrakemusic/workspace"
    assert artifact["commit"] == "1234567890abcdef1234567890abcdef12345678"
    assert artifact["ruff_version"] == "0.17.2"
    assert artifact["config"] == {
        "path": "ruff.toml",
        "sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    }
    assert artifact["scan_scope"] == SCAN_SCOPE
    assert isinstance(artifact["elapsed_seconds"], (int, float))
    assert artifact["elapsed_seconds"] >= 0
    assert artifact["finding_counts"] == {"ruff_check": 2, "ruff_format": 2}
    assert artifact["command_exit_codes"] == {
        "ruff_install": 0,
        "ruff_version": 0,
        "ruff_check": 1,
        "ruff_format_check": 1,
    }
    assert artifact["tool_errors"] == {
        "ruff_install": False,
        "ruff_version": False,
        "ruff_check": False,
        "ruff_format": False,
    }
    assert all("--fix" not in command for command in commands)
    assert "Repository: `tylerdrakemusic/workspace`" in summary_text
    assert "Scanned commit: `1234567890abcdef1234567890abcdef12345678`" in summary_text
    assert "Ruff pinned version: `0.17.2`" in summary_text
    assert f"Config: `ruff.toml` SHA-256 `{artifact['config']['sha256']}`" in summary_text
    assert f"Scope: {SCAN_SCOPE}" in summary_text
    assert "Findings: `ruff check` 2; `ruff format --check` 2" in summary_text
    assert "Command exit codes: install=0, version=0, check=1, format=1" in summary_text

    ci_directory_output = "\n".join(
        path.read_text(encoding="utf-8")
        for path in ci_dir.iterdir()
        if path.is_file()
    )
    assert {path.name for path in ci_dir.iterdir()} == {"summary.json"}
    ci_output = ci_directory_output + summary_text + log_text
    for sentinel in (
        CHECK_PATH_SENTINEL,
        FORMAT_PATH_SENTINEL,
        SOURCE_SENTINEL,
        SECRET_SENTINEL,
        URL_SENTINEL,
    ):
        assert sentinel not in ci_output

    local_output = "\n".join(
        path.read_text(encoding="utf-8") for path in local_dir.iterdir() if path.is_file()
    )
    assert CHECK_PATH_SENTINEL in local_output
    assert FORMAT_PATH_SENTINEL in local_output
    assert SOURCE_SENTINEL in local_output
    assert SECRET_SENTINEL in local_output
    assert URL_SENTINEL in local_output


def test_tool_failures_are_generic_and_do_not_gate_ci(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    helper = importlib.import_module("tools.ruff_ci_advisory")
    config_path = tmp_path / "ruff.toml"
    config_path.write_text("line-length = 100\n", encoding="utf-8")
    local_dir = tmp_path / "ruff-advisory-local" / "run-456-1"
    ci_dir = tmp_path / "ruff-advisory-ci" / "run-456-1"
    step_summary = tmp_path / "step-summary.md"
    raw_stderr = f"{URL_SENTINEL} {SECRET_SENTINEL}"

    def failing_run(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(
                command, 0, "abcdef0123456789abcdef0123456789abcdef01\n", ""
            )
        if command[-1:] == ["--version"]:
            return subprocess.CompletedProcess(command, 2, "", raw_stderr)
        if "check" in command:
            return subprocess.CompletedProcess(command, 2, "", raw_stderr)
        if "format" in command:
            return subprocess.CompletedProcess(command, 2, "", raw_stderr)
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(helper.subprocess, "run", failing_run)
    monkeypatch.setenv("GITHUB_REPOSITORY", "tylerdrakemusic/workspace")
    monkeypatch.setenv("RUFF_INSTALL_EXIT_CODE", "1")

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

    artifact_text = (ci_dir / "summary.json").read_text(encoding="utf-8")
    summary_text = step_summary.read_text(encoding="utf-8")
    captured = capsys.readouterr()
    artifact = json.loads(artifact_text)

    assert exit_code == 0, "Advisory tooling failures must not gate CI"
    assert artifact["finding_counts"] == {"ruff_check": None, "ruff_format": None}
    assert artifact["command_exit_codes"] == {
        "ruff_install": 1,
        "ruff_version": 2,
        "ruff_check": 2,
        "ruff_format_check": 2,
    }
    assert artifact["tool_errors"] == {
        "ruff_install": True,
        "ruff_version": True,
        "ruff_check": True,
        "ruff_format": True,
    }

    ci_output = artifact_text + summary_text + captured.out + captured.err
    assert URL_SENTINEL not in ci_output
    assert SECRET_SENTINEL not in ci_output
    local_output = "\n".join(
        path.read_text(encoding="utf-8") for path in local_dir.iterdir() if path.is_file()
    )
    assert URL_SENTINEL in local_output
    assert SECRET_SENTINEL in local_output