from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))
scenarios("pinned_skill_restore.feature")


@pytest.fixture
def restore_case() -> dict[str, Any]:
    return {}


def _git(source_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(source_root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _make_restore_fixture(root: Path, invalid: str | None = None) -> dict[str, Any]:
    workspace_root = root / "workspace"
    tools_dir = workspace_root / "tools"
    security_dir = workspace_root / ".github" / "!!\u263e\u26e7security"
    skills_dir = workspace_root / ".github" / "skills"
    tools_dir.mkdir(parents=True)
    security_dir.mkdir(parents=True)
    (skills_dir / "humanizer").mkdir(parents=True)
    (skills_dir / "other").mkdir(parents=True)
    _git(workspace_root, "init")
    shutil.copy2(PROJECT_ROOT / "tools" / "sync-skills.ps1", tools_dir)
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!\u263e\u26e7security" / "update_manifest.py",
        security_dir,
    )

    source_root = root / "humanizer-source"
    source_root.mkdir()
    pinned_content = b"trusted pinned Humanizer content\n"
    source_file = source_root / "SKILL.md"
    source_file.write_bytes(pinned_content)
    _git(source_root, "init")
    _git(source_root, "config", "user.email", "restore-test@example.test")
    _git(source_root, "config", "user.name", "Pinned Restore Test")
    _git(source_root, "add", "SKILL.md")
    _git(source_root, "commit", "-m", "Pinned Humanizer skill")
    pinned_commit = _git(source_root, "rev-parse", "HEAD").stdout.strip()
    source_file.write_bytes(b"uncommitted source update\n")
    pinned_sha256 = hashlib.sha256(pinned_content).hexdigest()

    other_source_root = root / "other-source"
    other_source = other_source_root / "skills" / "other" / "SKILL.md"
    other_source.parent.mkdir(parents=True)
    other_source.write_bytes(b"unreviewed external update\n")
    target_file = skills_dir / "humanizer" / "SKILL.md"
    target_file.write_bytes(b"drifted installed target\n")
    other_target = skills_dir / "other" / "SKILL.md"
    other_target.write_bytes(b"approved other target\n")

    manifest_path = security_dir / "agent-manifest.json"
    manifest_files = {
        ".github/skills/humanizer/SKILL.md": pinned_sha256,
        ".github/skills/other/SKILL.md": hashlib.sha256(other_target.read_bytes()).hexdigest(),
    }
    if invalid == "manifest":
        manifest_files[".github/skills/humanizer/SKILL.md"] = "0" * 64
    manifest = {"file_count": len(manifest_files), "files": manifest_files}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    humanizer_repo = {
        "name": "humanizer",
        "path": {"relative": "../humanizer-source", "env": "BLADER_HUMANIZER_ROOT"},
        "remote": "https://github.com/blader/humanizer",
        "skill_root": ".",
        "source_path": "SKILL.md",
        "provenance": "external-source",
        "source_policy": "optional",
        "pinned_commit": pinned_commit,
        "sha256": pinned_sha256,
        "protected_overwrite": False,
        "skills": ["humanizer"],
    }
    other_repo = {
        "name": "other-external-skill",
        "path": str(other_source_root),
        "remote": None,
        "skill_root": "skills",
        "provenance": "external-source",
        "source_policy": "optional",
        "skills": ["other"],
    }
    repos = [humanizer_repo, other_repo]
    if invalid == "pin":
        humanizer_repo["sha256"] = "0" * 64
    elif invalid == "mapping":
        duplicate_repo = dict(humanizer_repo)
        duplicate_repo["name"] = "duplicate-humanizer"
        repos.append(duplicate_repo)
    elif invalid == "blob":
        humanizer_repo["source_path"] = "missing.md"

    config_path = tools_dir / "skill-sync-config.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": repos,
            }
        ),
        encoding="utf-8",
    )
    return {
        "workspace_root": workspace_root,
        "config_path": config_path,
        "manifest_path": manifest_path,
        "target_file": target_file,
        "other_target": other_target,
        "source_root": source_root,
        "source_file": source_file,
        "pinned_content": pinned_content,
        "pinned_sha256": pinned_sha256,
        "pinned_commit": pinned_commit,
        "log_file": workspace_root / "logs" / "skill-sync.log",
        "rationale": "Restore the approved Humanizer pin without changing its baseline.",
        "empty_rationale": invalid == "rationale",
        "omit_target": invalid == "missing-target",
    }


def _run_restore(case: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell is unavailable")

    command = [
        executable,
        "-NoProfile",
        "-File",
        str(case["workspace_root"] / "tools" / "sync-skills.ps1"),
    ]
    if not case.get("omit_target", False):
        command.extend(["-RestorePinnedTarget", "humanizer"])
    if not case["empty_rationale"]:
        command.extend(["-RestoreRationale", case["rationale"]])
    environment = os.environ.copy()
    environment["BLADER_HUMANIZER_ROOT"] = str(case["source_root"])
    environment["PYTHON_EXECUTABLE"] = shutil.which("python") or sys.executable
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )


def _workspace_snapshot(workspace_root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(workspace_root).as_posix(): path.read_bytes()
        for path in workspace_root.rglob("*")
        if path.is_file()
    }


def _run_prewrite_gate(case: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["BLADER_HUMANIZER_ROOT"] = str(case["source_root"])
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "src" / "utils" / "prewrite_security_gate.py"),
            "--repo-root",
            str(case["workspace_root"]),
            "--quarantine-external-skill",
            "other",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )


@given("the configured Humanizer pin and manifest hash agree")
def valid_pinned_restore_case(tmp_path: Path, restore_case: dict[str, Any]) -> None:
    restore_case.update(_make_restore_fixture(tmp_path / "valid"))


@when("the explicit one-target restore runs")
def run_valid_pinned_restore(restore_case: dict[str, Any]) -> None:
    restore_case["config_before"] = restore_case["config_path"].read_bytes()
    restore_case["manifest_before"] = restore_case["manifest_path"].read_bytes()
    restore_case["source_before"] = restore_case["source_file"].read_bytes()
    restore_case["run"] = _run_restore(restore_case)


@then("only the installed target is restored and its SHA matches the existing pin and manifest")
def valid_restore_changes_only_the_named_target(restore_case: dict[str, Any]) -> None:
    run = restore_case["run"]
    assert run.returncode == 0, run.stdout + run.stderr
    assert restore_case["target_file"].read_bytes() == restore_case["pinned_content"]
    assert (
        hashlib.sha256(restore_case["target_file"].read_bytes()).hexdigest()
        == (restore_case["pinned_sha256"])
    )
    assert restore_case["other_target"].read_bytes() == b"approved other target\n"
    assert restore_case["source_file"].read_bytes() == restore_case["source_before"]
    assert restore_case["config_path"].read_bytes() == restore_case["config_before"]
    assert restore_case["manifest_path"].read_bytes() == restore_case["manifest_before"]


@given("the pinned blob, SHA, target mapping, or manifest entry is invalid or ambiguous")
def invalid_pinned_restore_cases(tmp_path: Path, restore_case: dict[str, Any]) -> None:
    restore_case["invalid_cases"] = [
        _make_restore_fixture(tmp_path / case_name, invalid=case_name)
        for case_name in (
            "pin",
            "manifest",
            "mapping",
            "blob",
            "rationale",
            "missing-target",
        )
    ]


@when("restore is requested")
def run_invalid_pinned_restores(restore_case: dict[str, Any]) -> None:
    results = []
    for case in restore_case["invalid_cases"]:
        source_status_before = _git(case["source_root"], "status", "--short").stdout
        results.append(
            {
                "case": case,
                "workspace_before": _workspace_snapshot(case["workspace_root"]),
                "source_before": case["source_file"].read_bytes(),
                "source_status_before": source_status_before,
                "run": _run_restore(case),
            }
        )
    restore_case["invalid_results"] = results


@then("it fails before changing any file")
def invalid_restores_make_no_changes(restore_case: dict[str, Any]) -> None:
    assert len(restore_case["invalid_results"]) == 6
    for result in restore_case["invalid_results"]:
        case = result["case"]
        assert result["run"].returncode != 0, result["run"].stdout + result["run"].stderr
        assert _workspace_snapshot(case["workspace_root"]) == result["workspace_before"]
        assert case["source_file"].read_bytes() == result["source_before"]
        assert (
            _git(case["source_root"], "status", "--short").stdout
            == (result["source_status_before"])
        )
        assert not case["log_file"].exists()


@given("the restore succeeds")
def restore_completes_for_verification(tmp_path: Path, restore_case: dict[str, Any]) -> None:
    case = _make_restore_fixture(tmp_path / "verification")
    case["run"] = _run_restore(case)
    assert case["run"].returncode == 0, case["run"].stdout + case["run"].stderr
    restore_case["verification_case"] = case


@when("canonical verification runs")
def run_canonical_verification(restore_case: dict[str, Any]) -> None:
    restore_case["verification"] = _run_prewrite_gate(restore_case["verification_case"])


@then(
    "no local manifest mismatch remains; unrelated external source updates remain quarantined only for that verification run"
)
def canonical_verification_passes_with_temporary_quarantine(
    restore_case: dict[str, Any],
) -> None:
    verification = restore_case["verification"]
    assert verification.returncode == 0, verification.stdout + verification.stderr
    assert "INTEGRITY_OK: canonical verifier passed." in verification.stdout
    assert "SOURCE UPDATE QUARANTINED:" in verification.stdout
