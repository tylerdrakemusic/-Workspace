"""Tests for redacted output from the staged-diff secret scanner."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "hooks" / "scripts"
sys.path.insert(0, str(HOOK_SCRIPTS))

import secret_scan


def test_staged_secret_scan_redacts_values_and_avoids_bypass_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    source_file = repository / "src" / "settings.py"
    source_file.parent.mkdir(parents=True)
    synthetic_secret = "sk-" + "A" * 24
    source_file.write_text(f'API_KEY = "{synthetic_secret}"\n', encoding="utf-8")
    subprocess.run(
        ["git", "init", str(repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "add", "src/settings.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    monkeypatch.chdir(repository)

    exit_code = secret_scan.main()
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "src/settings.py" in output
    assert "[REDACTED]" in output
    assert synthetic_secret not in output, "scanner output contains the fixture secret"
    assert synthetic_secret[:4] not in output, "scanner output contains a secret prefix"
    assert "--no-verify" not in output, "scanner output suggests bypassing the hook"


def test_staged_secret_scan_redacts_token_like_file_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    path_secret = "sk-" + "P" * 24
    content_secret = "sk-" + "A" * 24
    source_file = repository / "src" / f"{path_secret}.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(f'API_KEY = "{content_secret}"\n', encoding="utf-8")
    subprocess.run(
        ["git", "init", str(repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "add", "src"],
        check=True,
        capture_output=True,
        text=True,
    )
    monkeypatch.chdir(repository)

    assert secret_scan.main() == 1
    output = capsys.readouterr().out

    assert "src/" in output
    assert path_secret not in output, "scanner output contains a token-like file name"
    assert path_secret[:4] not in output, "scanner output contains a path prefix"
    assert content_secret not in output, "scanner output contains the fixture secret"


def test_git_diff_error_output_does_not_echo_secret_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    synthetic_secret = "ghp_" + "B" * 36

    def failed_git_diff(
        arguments: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(arguments, 1, "", f"fatal: {synthetic_secret}")

    monkeypatch.setattr(secret_scan.subprocess, "run", failed_git_diff)

    assert secret_scan.main() == 1
    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert "git diff failed" in captured.err
    assert synthetic_secret not in output, "scanner output contains secret text from git stderr"
    assert synthetic_secret[:4] not in output, "scanner output contains a secret prefix"


def test_reviewed_hardening_patterns_adaptation_is_pinned_and_scans_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace_root = Path(__file__).resolve().parents[1]
    config = json.loads(
        (workspace_root / "tools" / "skill-sync-config.json").read_text(
            encoding="utf-8"
        )
    )
    repository = next(
        item for item in config["repos"] if item["name"] == "addyosmani-agent-skills"
    )
    companion = next(
        item
        for item in repository["companions"]
        if item["identity"]
        == "addyosmani-agent-skills:skills/security-and-hardening/references/hardening-patterns.md"
    )

    adaptation_relative = companion.get("reviewed_adaptation_source_relative_path")
    assert adaptation_relative == (
        "tools/skill-sync-adaptations/addyosmani/hardening-patterns.md"
    )
    adaptation_path = workspace_root / adaptation_relative
    adaptation_bytes = adaptation_path.read_bytes()
    adaptation_hash = hashlib.sha256(adaptation_bytes).hexdigest()
    contract = companion["hash_contract"]
    assert contract["accepted_baselines"] == ["reviewed-project-owned-adaptation"]
    assert contract["reviewed_adaptation_sha256"] == adaptation_hash

    target_relative = companion["target_relative_paths"][0]
    target_path = workspace_root / target_relative
    manifest = json.loads(
        (
            workspace_root
            / ".github"
            / "!!☾⛧security"
            / "agent-manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert hashlib.sha256(target_path.read_bytes()).hexdigest() == adaptation_hash
    assert manifest["files"][target_relative] == adaptation_hash

    repository_root = tmp_path / "scanner-fixture"
    staged_file = repository_root / "references" / "hardening-patterns.md"
    staged_file.parent.mkdir(parents=True)
    staged_file.write_bytes(adaptation_bytes)
    subprocess.run(
        ["git", "init", str(repository_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(repository_root), "add", "references/hardening-patterns.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    monkeypatch.chdir(repository_root)

    assert secret_scan.main() == 0
    assert capsys.readouterr().out == ""