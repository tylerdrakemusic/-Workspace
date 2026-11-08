"""Tests for provenance-aware copied skill integrity checks."""
from __future__ import annotations

import errno
import base64
import hashlib
import json
import os
import runpy
import shutil
import stat
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "!!☾⛧security"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

from update_manifest import (
    preflight_sync_config,
    resolve_sync_config,
    update_manifest_entries,
    verify_manifest,
    verify_skill_integrity,
)
import update_manifest
from prewrite_security_gate import run_prewrite_security_gate


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _create_file_symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target)
    except OSError as exc:
        unsupported = {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
        if exc.errno in unsupported or getattr(exc, "winerror", None) == 1314:
            pytest.skip(f"File symlinks are unsupported here: {exc}")
        raise


def _commit_git_repo(repo_path: Path) -> str:
    subprocess.run(["git", "init", str(repo_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "core.autocrlf", "false"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "core.symlinks", "true"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Skill Sync Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "skill-sync@example.test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "--all"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "commit",
            "--allow-empty",
            "-m",
            "Add pinned skill sources",
        ],
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _run_git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _assert_no_temporary_git_worktrees(repo_path: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.stdout.count("worktree ") == 1


def _create_directory_link_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            command_shell = shutil.which("cmd.exe")
            if command_shell is None:
                pytest.skip("Neither directory symlinks nor junction creation is available")
            command = f'mklink /J "{link}" "{target}"'
            result = subprocess.run(
                [command_shell, "/d", "/c", command],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode == 0:
                return
            junction_error = (result.stdout + result.stderr).lower()
            if "not supported" in junction_error or "local ntfs volumes are required" in junction_error:
                pytest.skip("This filesystem does not support directory junctions")
            raise OSError(result.stdout + result.stderr) from exc
        unsupported = {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
        if exc.errno in unsupported:
            pytest.skip(f"Directory links are unsupported here: {exc}")
        raise


def _write_skill_fixture(
    tmp_path: Path,
    *,
    source_text: str,
    target_text: str,
    manifest_text: str,
    skill: str = "example",
    repo_name: str = "external-skills",
) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "source" / "skills"
    source_file = source_root / skill / "SKILL.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(source_text.encode("utf-8"))
    _commit_git_repo(tmp_path / "source")

    destination = tmp_path / "workspace" / ".github" / "skills"
    target_file = destination / skill / "SKILL.md"
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(target_text.encode("utf-8"))

    manifest_path = tmp_path / "workspace" / ".github" / "!!security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    baseline_file = tmp_path / "manifest-baseline.md"
    baseline_file.write_bytes(manifest_text.encode("utf-8"))
    manifest_path.write_text(
        json.dumps(
            {
                "files": {
                    f".github/skills/{skill}/SKILL.md": _sha256(baseline_file),
                    ".github/skills/unrelated/SKILL.md": "preserve-this-hash",
                }
            }
        ),
        encoding="utf-8",
    )

    config_path = tmp_path / "skill-sync-config.json"
    config_path.write_text(
        json.dumps(
            {
                "destination": str(destination),
                "repos": [
                    {
                        "name": repo_name,
                        "path": str(tmp_path / "source"),
                        "remote": None,
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "skills": [skill],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path, target_file, manifest_path


def _write_companion_config_fixture(
    tmp_path: Path,
    *,
    source_relative_path: str = "guides/check.md",
    target_relative_paths: list[str] | None = None,
) -> tuple[Path, Path, Path]:
    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True)
    source_file = source_root / "guides" / "check.md"
    source_file.parent.mkdir()
    source_file.write_bytes(b"approved companion\n")
    _commit_git_repo(source_root)
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    targets = target_relative_paths or [
        ".github/skills/example/references/check.md"
    ]
    config_path.write_text(
        json.dumps(
            {
                "destination": {"relative": ".github/skills"},
                "repos": [
                    {
                        "name": "external-skills",
                        "path": str(source_root),
                        "skill_root": "skills",
                        "skills": [],
                        "companions": [
                            {
                                "source_relative_path": source_relative_path,
                                "target_relative_paths": targets,
                                "identity": "external-skills:guides/check.md",
                                "consumers": ["example"],
                                "required": True,
                                "hash_contract": {
                                    "algorithm": "sha256",
                                    "accepted_baselines": [
                                        "approved-source",
                                        "reviewed-project-owned-adaptation",
                                    ],
                                },
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path, workspace_root, source_root


def _write_mp_source_config(
    workspace_root: Path, companions: list[dict[str, object]] | None = None
) -> Path:
    source_config = json.loads(
        (PROJECT_ROOT / "tools" / "skill-sync-config.json").read_text(
            encoding="utf-8"
        )
    )
    repo = dict(
        next(
            item
            for item in source_config["repos"]
            if item["name"] == "mp-skills-engineering"
        )
    )
    repo["skills"] = ["example"]
    repo["skill_root"] = "skills"
    repo.pop("reviewed_skill_adaptations", None)
    repo["companions"] = companions or []
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [repo],
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_quarantine_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str, str]:
    source_root = tmp_path / "external-source"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"trusted installed skill\n")
    old_commit = _commit_git_repo(source_root)
    source_file.write_bytes(b"unreviewed candidate skill\n")
    subprocess.run(
        ["git", "-C", str(source_root), "add", "skills/example/SKILL.md"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(source_root), "commit", "-m", "Candidate revision"],
        check=True,
        capture_output=True,
    )
    new_commit = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()

    workspace_root = tmp_path / "workspace"
    target_file = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(b"trusted installed skill\n")
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 1,
                "files": {
                    ".github/skills/example/SKILL.md": hashlib.sha256(
                        b"trusted installed skill\n"
                    ).hexdigest()
                },
            }
        ),
        encoding="utf-8",
    )
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [
                    {
                        "name": "external-source",
                        "path": str(source_root),
                        "remote": None,
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "source_policy": "required",
                        "pinned_commit": old_commit,
                        "sha256": hashlib.sha256(
                            b"trusted installed skill\n"
                        ).hexdigest(),
                        "skills": ["example"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        manifest_path.parent / "update_manifest.py",
    )
    return workspace_root, config_path, target_file, old_commit, new_commit


def _run_quarantine_gate(workspace_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "src" / "utils" / "prewrite_security_gate.py"),
            "--repo-root",
            str(workspace_root),
            "--quarantine-external-skill",
            "example",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_strict_prewrite_gate_fails_closed_when_verifier_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_verifier(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError("simulated verifier startup failure")

    monkeypatch.setattr(subprocess, "run", fail_verifier)

    result = run_prewrite_security_gate(tmp_path, strict=True)

    assert result == 1


def test_strict_prewrite_gate_rejects_incomplete_zero_exit_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def incomplete_verifier(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="partial output", stderr="")

    monkeypatch.setattr(subprocess, "run", incomplete_verifier)

    assert run_prewrite_security_gate(tmp_path, strict=True) == 1


def test_source_match_is_authorized(tmp_path: Path) -> None:
    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="source\n",
        target_text="source\n",
        manifest_text="source\n",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert result.entries[0].status == "source_match"
    assert result.entries[0].target == str(target_file)


def test_unpinned_external_skill_uses_head_blob_for_crlf_checkout(
    tmp_path: Path,
) -> None:
    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="source\n",
        target_text="source\n",
        manifest_text="source\n",
    )
    source_root = config_path.parent / "source"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    source_file.write_bytes(b"source\n")
    target_file.write_bytes(b"source\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][".github/skills/example/SKILL.md"] = hashlib.sha256(
        b"source\n"
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _commit_git_repo(source_root)
    source_file.write_bytes(b"source\r\n")

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert result.entries[0].status == "source_match"
    assert source_file.read_bytes() == b"source\r\n"
    assert target_file.read_bytes() == b"source\n"


def test_unpinned_external_skill_rejects_non_eol_worktree_edits(
    tmp_path: Path,
) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="source\n",
        target_text="source\n",
        manifest_text="source\n",
    )
    source_root = config_path.parent / "source"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    _commit_git_repo(source_root)
    source_file.write_bytes(b"changed source\r\n")

    result = verify_skill_integrity(config_path, manifest_path)

    assert [entry.status for entry in result.entries] == ["integrity_failure"]
    assert len(result.hard_findings) == 1


def test_unpinned_external_skill_must_exist_in_head(
    tmp_path: Path,
) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="source\n",
        target_text="source\n",
        manifest_text="source\n",
    )
    source_root = config_path.parent / "source"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    source_file.unlink()
    (source_root / "README.md").write_text("committed\n", encoding="utf-8")
    _commit_git_repo(source_root)
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_bytes(b"source\n")

    result = verify_skill_integrity(config_path, manifest_path)

    assert [entry.status for entry in result.entries] == ["integrity_failure"]
    assert len(result.hard_findings) == 1


def test_unpinned_companion_uses_head_blob_for_crlf_checkout(
    tmp_path: Path,
) -> None:
    config_path, workspace_root, source_root = _write_companion_config_fixture(tmp_path)
    source_file = source_root / "guides" / "check.md"
    source_file.write_bytes(b"approved companion\n")
    _commit_git_repo(source_root)
    source_file.write_bytes(b"approved companion\r\n")
    target_file = workspace_root / ".github" / "skills" / "example" / "references" / "check.md"
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(b"approved companion\n")
    manifest_path = workspace_root / ".github" / "!!security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 1,
                "files": {".github/skills/example/references/check.md": _sha256(target_file)},
            }
        ),
        encoding="utf-8",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert [entry.status for entry in result.entries] == ["source_match"]
    assert source_file.read_bytes() == b"approved companion\r\n"


def test_reviewed_sync_stages_head_blob_bytes_for_unpinned_skill_and_companion(
    tmp_path: Path,
) -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is required to exercise reviewed skill sync")

    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "external-source"
    skill_source = source_root / "skills" / "example" / "SKILL.md"
    companion_source = source_root / "guides" / "check.md"
    skill_source.parent.mkdir(parents=True)
    companion_source.parent.mkdir(parents=True)
    skill_source.write_bytes(b"new skill\n")
    companion_source.write_bytes(b"new companion\n")
    _commit_git_repo(source_root)
    skill_source.write_bytes(b"new skill\r\n")
    companion_source.write_bytes(b"new companion\r\n")

    tools_dir = workspace_root / "tools"
    tools_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "tools" / "sync-skills.ps1", tools_dir)
    security_dir = workspace_root / ".github" / "!!☾⛧security"
    security_dir.mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        security_dir / "update_manifest.py",
    )
    utils_dir = workspace_root / "src" / "utils"
    utils_dir.mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / "src" / "utils" / "prewrite_security_gate.py",
        utils_dir / "prewrite_security_gate.py",
    )
    target_skill = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_companion = (
        workspace_root / ".github" / "skills" / "example" / "references" / "check.md"
    )
    target_skill.parent.mkdir(parents=True)
    target_companion.parent.mkdir(parents=True)
    target_skill.write_bytes(b"old skill\n")
    target_companion.write_bytes(b"new companion\n")
    manifest_path = security_dir / "agent-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 2,
                "files": {
                    ".github/skills/example/SKILL.md": _sha256(target_skill),
                    ".github/skills/example/references/check.md": _sha256(target_companion),
                },
            }
        ),
        encoding="utf-8",
    )
    config_path = tools_dir / "skill-sync-config.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [
                    {
                        "name": "external-source",
                        "path": str(source_root),
                        "remote": None,
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "source_policy": "required",
                        "skills": ["example"],
                        "companions": [
                            {
                                "source_relative_path": "guides/check.md",
                                "target_relative_paths": [
                                    ".github/skills/example/references/check.md"
                                ],
                                "identity": "external-source:guides/check.md",
                                "consumers": ["example"],
                                "required": True,
                                "hash_contract": {
                                    "algorithm": "sha256",
                                    "accepted_baselines": ["approved-source"],
                                },
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(tools_dir / "sync-skills.ps1"),
            "-ApproveReviewedUpdates",
            "-ReviewedSkills",
            "example",
            "-ReviewRationale",
            "Verify committed source bytes are staged",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert target_skill.read_bytes() == b"new skill\n"
    assert target_companion.read_bytes() == b"new companion\n"
    assert skill_source.read_bytes() == b"new skill\r\n"
    assert companion_source.read_bytes() == b"new companion\r\n"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"][".github/skills/example/SKILL.md"] == hashlib.sha256(
        b"new skill\n"
    ).hexdigest()
    assert manifest["files"][".github/skills/example/references/check.md"] == hashlib.sha256(
        b"new companion\n"
    ).hexdigest()


@pytest.mark.parametrize(
    "refresh_sources",
    [False, True],
    ids=["default-no-fetch", "explicit-refresh"],
)
def test_ordinary_sync_requires_explicit_source_refresh_opt_in(
    tmp_path: Path, refresh_sources: bool
) -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is required to exercise ordinary skill sync")

    remote_root = tmp_path / "external-source.git"
    seed_root = tmp_path / "seed"
    checkout_root = tmp_path / "checkout"
    _run_git("init", "--bare", "--initial-branch=main", str(remote_root))
    _run_git("init", "--initial-branch=main", str(seed_root))
    for key, value in (
        ("user.name", "Skill Sync Test"),
        ("user.email", "skill-sync@example.test"),
    ):
        _run_git("-C", str(seed_root), "config", key, value)
    seed_skill = seed_root / "skills" / "example" / "SKILL.md"
    seed_skill.parent.mkdir(parents=True)
    seed_skill.write_bytes(b"original source\n")
    _run_git("-C", str(seed_root), "add", "--all")
    _run_git("-C", str(seed_root), "commit", "-m", "Initial skill")
    _run_git("-C", str(seed_root), "remote", "add", "origin", str(remote_root))
    _run_git("-C", str(seed_root), "push", "-u", "origin", "main")
    _run_git("clone", "--branch", "main", str(remote_root), str(checkout_root))

    initial_commit = _run_git("-C", str(checkout_root), "rev-parse", "HEAD")
    seed_skill.write_bytes(b"advanced source\n")
    _run_git("-C", str(seed_root), "add", "--all")
    _run_git("-C", str(seed_root), "commit", "-m", "Advance skill")
    _run_git("-C", str(seed_root), "push", "origin", "main")
    advanced_remote_commit = _run_git("-C", str(seed_root), "rev-parse", "HEAD")

    workspace_root = tmp_path / "workspace"
    tools_dir = workspace_root / "tools"
    tools_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "tools" / "sync-skills.ps1", tools_dir)
    security_dir = workspace_root / ".github" / "!!☾⛧security"
    security_dir.mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        security_dir / "update_manifest.py",
    )
    target_file = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(b"original source\n")
    manifest_path = security_dir / "agent-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 1,
                "files": {".github/skills/example/SKILL.md": _sha256(target_file)},
            }
        ),
        encoding="utf-8",
    )
    config_path = tools_dir / "skill-sync-config.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [
                    {
                        "name": "external-source",
                        "path": str(checkout_root),
                        "remote": str(remote_root),
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "source_policy": "optional",
                        "skills": ["example"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(tools_dir / "sync-skills.ps1"),
        "-ConfigPath",
        str(config_path),
        "-ManifestPath",
        str(manifest_path),
    ]
    if refresh_sources:
        command.append("-RefreshExternalSources")
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    checkout_head = _run_git("-C", str(checkout_root), "rev-parse", "HEAD")
    remote_tracking_head = _run_git(
        "-C", str(checkout_root), "rev-parse", "origin/main"
    )
    expected_head = advanced_remote_commit if refresh_sources else initial_commit
    assert checkout_head == expected_head
    assert remote_tracking_head == expected_head


def test_eol_expanded_manifest_migration_changes_only_exact_git_blob_matches(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "workspace"
    exact_path = repo_root / ".github" / "skills" / "exact" / "SKILL.md"
    stable_path = repo_root / ".github" / "skills" / "stable" / "SKILL.md"
    changed_path = repo_root / ".github" / "skills" / "changed" / "SKILL.md"
    for path in (exact_path, stable_path, changed_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    exact_path.write_bytes(b"exact line\n")
    stable_path.write_bytes(b"stable line\n")
    changed_path.write_bytes(b"current content\n")
    _commit_git_repo(repo_root)

    security_dir = repo_root / ".github" / "!!☾⛧security"
    security_dir.mkdir(parents=True)
    manifest_path = security_dir / "agent-manifest.json"
    original_files = {
        ".github/skills/exact/SKILL.md": hashlib.sha256(
            b"exact line\r\n"
        ).hexdigest(),
        ".github/skills/stable/SKILL.md": hashlib.sha256(
            b"stable line\n"
        ).hexdigest(),
        ".github/skills/changed/SKILL.md": hashlib.sha256(
            b"previous content\r\n"
        ).hexdigest(),
    }
    manifest_path.write_text(
        json.dumps({"file_count": 3, "files": original_files}, indent=2),
        encoding="utf-8",
    )
    original_manifest_hash = _sha256(manifest_path)
    original_target_bytes = {
        path: path.read_bytes() for path in (exact_path, stable_path, changed_path)
    }

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py"),
            "--reconcile-eol-expanded-manifest",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo_root),
            "--expected-manifest-hash",
            original_manifest_hash,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    updated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated_manifest["files"] == {
        ".github/skills/exact/SKILL.md": hashlib.sha256(b"exact line\n").hexdigest(),
        ".github/skills/stable/SKILL.md": original_files[
            ".github/skills/stable/SKILL.md"
        ],
        ".github/skills/changed/SKILL.md": original_files[
            ".github/skills/changed/SKILL.md"
        ],
    }
    assert "Manifest entries reconciled: 1" in result.stdout
    manifest_hash_line = next(
        line for line in result.stdout.splitlines() if line.startswith("MANIFEST_SHA256=")
    )
    assert manifest_hash_line == f"MANIFEST_SHA256={_sha256(manifest_path)}"
    assert {path: path.read_bytes() for path in original_target_bytes} == original_target_bytes

    updated_manifest_bytes = manifest_path.read_bytes()
    stale_result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py"),
            "--reconcile-eol-expanded-manifest",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo_root),
            "--expected-manifest-hash",
            original_manifest_hash,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert stale_result.returncode != 0
    assert manifest_path.read_bytes() == updated_manifest_bytes


@pytest.mark.parametrize("checkout_layout", ["main", "feature-worktree"])
def test_mp_skill_source_root_resolves_to_canonical_main_or_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    checkout_layout: str,
) -> None:
    monkeypatch.delenv("MP_SKILLS_ROOT", raising=False)
    workspace_root = tmp_path / "workspace"
    checkout_root = (
        workspace_root
        if checkout_layout == "main"
        else workspace_root / ".worktrees" / "feature-branch"
    )
    config_path = _write_mp_source_config(checkout_root)
    canonical_root = workspace_root / ".worktrees" / "mp-skills"
    canonical_root.mkdir(parents=True)
    stale_root = workspace_root.parent / "mp-skills"
    stale_root.mkdir()

    resolved = resolve_sync_config(config_path)

    assert Path(resolved["repos"][0]["path"]) == canonical_root.resolve()


def test_mp_skill_source_environment_override_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    config_path = _write_mp_source_config(workspace_root)
    canonical_root = workspace_root / ".worktrees" / "mp-skills"
    canonical_root.mkdir(parents=True)
    override_root = tmp_path / "explicit-mp-skills"
    override_root.mkdir()
    monkeypatch.setenv("MP_SKILLS_ROOT", str(override_root))

    resolved = resolve_sync_config(config_path)

    assert Path(resolved["repos"][0]["path"]) == override_root.resolve()


def test_missing_optional_canonical_mp_root_does_not_fall_back_to_stale_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MP_SKILLS_ROOT", raising=False)
    workspace_root = tmp_path / "workspace"
    canonical_root = workspace_root / ".worktrees" / "mp-skills"
    stale_root = workspace_root.parent / "mp-skills"
    stale_companion = stale_root / "guides" / "check.md"
    stale_companion.parent.mkdir(parents=True)
    stale_companion.write_bytes(b"approved companion\n")
    target_path = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_bytes(b"installed skill\n")
    companion_target = (
        workspace_root / ".github" / "skills" / "example" / "references" / "check.md"
    )
    companion_target.parent.mkdir(parents=True)
    companion_target.write_bytes(stale_companion.read_bytes())
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 2,
                "files": {
                    ".github/skills/example/SKILL.md": _sha256(target_path),
                    ".github/skills/example/references/check.md": _sha256(
                        companion_target
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    original_manifest = manifest_path.read_bytes()
    original_target = target_path.read_bytes()
    config_path = _write_mp_source_config(
        workspace_root,
        companions=[
            {
                "source_relative_path": "guides/check.md",
                "target_relative_paths": [
                    ".github/skills/example/references/check.md"
                ],
                "identity": "mp-skills-engineering:guides/check.md",
                "consumers": ["example"],
                "required": True,
                "hash_contract": {
                    "algorithm": "sha256",
                    "accepted_baselines": ["approved-source"],
                },
            }
        ],
    )

    plan = preflight_sync_config(config_path)
    resolved_repo = plan["repos"][0]

    assert resolved_repo["source_policy"] == "optional"
    assert Path(resolved_repo["path"]) == canonical_root.resolve()
    assert Path(resolved_repo["mappings"][0]["source"]) == (
        canonical_root / "skills" / "example" / "SKILL.md"
    ).resolve()
    assert Path(resolved_repo["companions"][0]["source"]) == (
        canonical_root / "guides" / "check.md"
    ).resolve()
    assert not canonical_root.exists()
    assert target_path.read_bytes() == original_target
    assert manifest_path.read_bytes() == original_manifest
    assert stale_companion.read_bytes() == b"approved companion\n"
    assert not (workspace_root / "logs" / "skill-sync.log").exists()


def test_skill_and_adaptation_checkout_uses_lf_with_autocrlf_true(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "checkout"
    repository.mkdir()
    attributes = PROJECT_ROOT / ".gitattributes"
    if attributes.is_file():
        shutil.copy2(attributes, repository / ".gitattributes")
    skill_file = repository / ".github" / "skills" / "sample" / "SKILL.md"
    adaptation_markdown = (
        repository / "tools" / "skill-sync-adaptations" / "sample" / "SKILL.md"
    )
    adaptation_script = (
        repository / "tools" / "skill-sync-adaptations" / "sample" / "template.sh"
    )
    unrelated_markdown = repository / "README.md"
    for path in (skill_file, adaptation_markdown, adaptation_script, unrelated_markdown):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"line one\nline two\n")

    git = ["git", "-C", str(repository)]
    subprocess.run([*git, "init"], check=True, capture_output=True)
    subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
    subprocess.run([*git, "config", "user.name", "Skill Sync Test"], check=True)
    subprocess.run(
        [*git, "config", "user.email", "skill-sync@example.test"], check=True
    )
    subprocess.run([*git, "add", "--all"], check=True, capture_output=True)
    subprocess.run(
        [*git, "commit", "-m", "Add scoped skill EOL attributes"],
        check=True,
        capture_output=True,
    )
    subprocess.run([*git, "config", "core.autocrlf", "true"], check=True)
    for path in (skill_file, adaptation_markdown, adaptation_script, unrelated_markdown):
        path.unlink()
    subprocess.run(
        [*git, "checkout", "--force", "HEAD", "--", "."],
        check=True,
        capture_output=True,
    )

    assert skill_file.read_bytes() == b"line one\nline two\n"
    assert adaptation_markdown.read_bytes() == b"line one\nline two\n"
    assert adaptation_script.read_bytes() == b"line one\nline two\n"
    assert unrelated_markdown.read_bytes() == b"line one\r\nline two\r\n"


def test_manifest_verification_rejects_line_ending_change_to_tracked_file(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    tracked_file = workspace_root / ".github" / "agents" / "example.agent.md"
    tracked_file.parent.mkdir(parents=True)
    tracked_file.write_bytes(b"tracked text\n")
    security_dir = workspace_root / ".github" / "!!☾⛧security"
    security_dir.mkdir(parents=True)
    manifest_path = security_dir / "agent-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 1,
                "files": {
                    ".github/agents/example.agent.md": _sha256(tracked_file)
                },
            }
        ),
        encoding="utf-8",
    )
    verifier_path = security_dir / "update_manifest.py"
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        verifier_path,
    )
    tracked_file.write_bytes(b"tracked text\r\n")

    result = subprocess.run(
        [sys.executable, str(verifier_path), "--verify"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode != 0, result.stdout + result.stderr


def test_build_manifest_rejects_watched_symlink_before_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    skills_dir = repo_root / ".github" / "skills" / "example"
    skills_dir.mkdir(parents=True)
    watched_file = skills_dir / "unexpected.md"
    watched_file.write_text("external file contents\n", encoding="utf-8")
    original_is_symlink = Path.is_symlink

    def report_symlink(path: Path) -> bool:
        return path == watched_file or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_symlink)

    with pytest.raises(ValueError, match="(?i)(symlink|reparse)"):
        update_manifest.build_manifest(repo_root)


@pytest.mark.parametrize("uppercase_sha", [False, True], ids=["lowercase", "uppercase"])
def test_pinned_source_match_uses_commit_blob_with_crlf_worktree(
    tmp_path: Path, uppercase_sha: bool
) -> None:
    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="pinned source\n",
        target_text="pinned source\n",
        manifest_text="pinned source\n",
    )
    target_file.write_bytes(b"pinned source\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][".github/skills/example/SKILL.md"] = hashlib.sha256(
        b"pinned source\n"
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_root = tmp_path / "source"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    git = ["git", "-C", str(source_root)]
    subprocess.run([*git, "init"], check=True, capture_output=True, text=True, encoding="utf-8")
    subprocess.run([*git, "config", "core.autocrlf", "true"], check=True)
    subprocess.run([*git, "config", "user.email", "test@example.com"], check=True)
    subprocess.run([*git, "config", "user.name", "Test"], check=True)
    subprocess.run(
        [*git, "add", "skills/example/SKILL.md"], check=True, capture_output=True
    )
    subprocess.run(
        [*git, "commit", "--allow-empty", "-m", "pinned source"],
        check=True,
        capture_output=True,
    )
    pinned_commit = subprocess.run(
        [*git, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    blob = subprocess.run(
        [*git, "cat-file", "blob", f"{pinned_commit}:skills/example/SKILL.md"],
        check=True,
        capture_output=True,
    ).stdout
    source_file.write_bytes(b"pinned source\r\n")
    assert blob == b"pinned source\n"
    assert source_file.read_bytes() == b"pinned source\r\n"

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["pinned_commit"] = pinned_commit
    pinned_sha = hashlib.sha256(b"pinned source\n").hexdigest()
    config["repos"][0]["sha256"] = pinned_sha.upper() if uppercase_sha else pinned_sha
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert result.entries[0].status == "source_match"


@pytest.mark.parametrize("failure", ["missing_blob", "bad_sha256", "git_unavailable"])
def test_pinned_source_blob_failures_are_hard_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="pinned source\n",
        target_text="pinned source\n",
        manifest_text="pinned source\n",
    )
    source_root = tmp_path / "source"
    git = ["git", "-C", str(source_root)]
    subprocess.run([*git, "init"], check=True, capture_output=True, text=True, encoding="utf-8")
    subprocess.run([*git, "config", "user.email", "test@example.com"], check=True)
    subprocess.run([*git, "config", "user.name", "Test"], check=True)

    if failure == "missing_blob":
        subprocess.run(
            [*git, "rm", "--cached", "skills/example/SKILL.md"],
            check=True,
            capture_output=True,
        )
        other_source = source_root / "skills" / "other" / "SKILL.md"
        other_source.parent.mkdir(parents=True)
        other_source.write_bytes(b"different pinned path\n")
        subprocess.run([*git, "add", "skills/other/SKILL.md"], check=True)
    else:
        subprocess.run([*git, "add", "skills/example/SKILL.md"], check=True)

    subprocess.run(
        [*git, "commit", "--allow-empty", "-m", "pinned source"],
        check=True,
        capture_output=True,
    )
    pinned_commit = subprocess.run(
        [*git, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["pinned_commit"] = pinned_commit
    config["repos"][0]["sha256"] = (
        "0" * 64
        if failure == "bad_sha256"
        else hashlib.sha256(b"pinned source\n").hexdigest()
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")

    if failure == "git_unavailable":
        def fail_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            raise FileNotFoundError("git executable missing")

        monkeypatch.setattr(subprocess, "run", fail_git)

    result = verify_skill_integrity(config_path, manifest_path)

    assert len(result.hard_findings) == 1
    assert result.entries[0].status == "integrity_failure"


def test_pinned_sha_without_commit_is_an_integrity_failure(tmp_path: Path) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="pinned source\n",
        target_text="pinned source\n",
        manifest_text="pinned source\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["sha256"] = hashlib.sha256(
        b"pinned source\n"
    ).hexdigest()
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert len(result.hard_findings) == 1
    assert result.entries[0].status == "integrity_failure"


@pytest.mark.parametrize(
    "pin_fields",
    [
        pytest.param({"pinned_commit": "", "sha256": ""}, id="empty-pair"),
        pytest.param({"pinned_commit": ""}, id="empty-commit"),
        pytest.param({"sha256": ""}, id="empty-sha"),
    ],
)
def test_explicit_empty_pin_fields_are_integrity_failures(
    tmp_path: Path, pin_fields: dict[str, str]
) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="pinned source\n",
        target_text="pinned source\n",
        manifest_text="pinned source\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0].update(pin_fields)
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert len(result.hard_findings) == 1
    assert result.entries[0].status == "integrity_failure"


def test_missing_optional_repository_with_pinned_source_is_an_integrity_failure(
    tmp_path: Path,
) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="pinned source\n",
        target_text="pinned source\n",
        manifest_text="pinned source\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["source_policy"] = "optional"
    config["repos"][0]["path"] = str(tmp_path / "missing-source")
    config["repos"][0]["pinned_commit"] = "a" * 40
    config["repos"][0]["sha256"] = hashlib.sha256(
        b"pinned source\n"
    ).hexdigest()
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert len(result.hard_findings) == 1
    assert result.entries[0].status == "integrity_failure"


def test_malformed_pinned_commit_is_an_integrity_failure(tmp_path: Path) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="pinned source\n",
        target_text="pinned source\n",
        manifest_text="pinned source\n",
    )
    source_root = tmp_path / "source"
    git = ["git", "-C", str(source_root)]
    subprocess.run(
        [*git, "init"], check=True, capture_output=True, text=True, encoding="utf-8"
    )
    subprocess.run([*git, "config", "user.email", "test@example.com"], check=True)
    subprocess.run([*git, "config", "user.name", "Test"], check=True)
    subprocess.run([*git, "add", "skills/example/SKILL.md"], check=True)
    subprocess.run(
        [*git, "commit", "--allow-empty", "-m", "pinned source"],
        check=True,
        capture_output=True,
    )

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["pinned_commit"] = "not-a-commit"
    config["repos"][0]["sha256"] = hashlib.sha256(
        b"pinned source\n"
    ).hexdigest()
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert len(result.hard_findings) == 1
    assert result.entries[0].status == "integrity_failure"


def test_local_customization_matching_manifest_is_preserved(tmp_path: Path) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="upstream\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert result.entries[0].status == "local_customization"


def test_target_mismatch_against_source_and_manifest_is_hard_finding(tmp_path: Path) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="upstream\n",
        target_text="unexpected edit\n",
        manifest_text="authorized baseline\n",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert len(result.hard_findings) == 1
    assert result.hard_findings[0].status == "integrity_failure"


def test_approved_sync_updates_only_the_affected_manifest_entry(tmp_path: Path) -> None:
    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="approved source\n",
        target_text="approved source\n",
        manifest_text="old baseline\n",
    )

    manifest_hash = update_manifest_entries(
        manifest_path,
        [target_file],
        repo_root=tmp_path / "workspace",
    )

    assert manifest_hash == _sha256(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"][".github/skills/example/SKILL.md"] == _sha256(target_file)
    assert manifest["files"][".github/skills/unrelated/SKILL.md"] == "preserve-this-hash"
    result = verify_skill_integrity(config_path, manifest_path)
    assert result.hard_findings == []
    assert result.entries[0].status == "source_match"


def test_manifest_update_replace_failure_preserves_original_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="approved source\n",
        target_text="approved source\n",
        manifest_text="trusted manifest baseline\n",
    )
    original_manifest = manifest_path.read_bytes()

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(update_manifest.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated atomic replace failure"):
        update_manifest_entries(
            manifest_path,
            [target_file],
            repo_root=tmp_path / "workspace",
        )

    assert manifest_path.read_bytes() == original_manifest
    assert not list(manifest_path.parent.glob(".agent-manifest-*.tmp"))


def test_initial_manifest_generation_is_atomic_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    github_dir = repo_root / ".github"
    for directory in ("agents", "instructions", "skills", "!!☾⛧security"):
        (github_dir / directory).mkdir(parents=True, exist_ok=True)
    script_path = github_dir / "!!☾⛧security" / "update_manifest.py"
    shutil.copy2(PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py", script_path)
    manifest_path = github_dir / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.write_bytes(b"trusted manifest bytes\n")
    original_manifest = manifest_path.read_bytes()
    monkeypatch.setattr(sys, "argv", [str(script_path)])

    def fail_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("simulated manifest replace failure")

    monkeypatch.setattr(update_manifest.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated manifest replace failure"):
        runpy.run_path(str(script_path), run_name="__main__")

    assert manifest_path.read_bytes() == original_manifest
    assert list(manifest_path.parent.glob("*.tmp")) == []


def test_reviewed_manifest_reconciliation_changes_only_named_watched_paths(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "workspace"
    agents_dir = repo_root / ".github" / "agents"
    instructions_dir = repo_root / ".github" / "instructions"
    agents_dir.mkdir(parents=True)
    instructions_dir.mkdir(parents=True)

    edited = agents_dir / "overseer.agent.md"
    edited.write_text("reviewed agent revision\n", encoding="utf-8")
    added = instructions_dir / "new.instructions.md"
    added.write_text("reviewed instruction\n", encoding="utf-8")
    unrelated = instructions_dir / "unrelated.instructions.md"
    unrelated.write_text("unchanged trusted instruction\n", encoding="utf-8")
    deleted = agents_dir / "retired.agent.md"
    deleted_key = ".github/agents/retired.agent.md"
    deleted.write_text("old trusted file\n", encoding="utf-8")
    deleted.unlink()
    unrelated_key = ".github/instructions/unrelated.instructions.md"
    unrelated_hash = _sha256(unrelated)
    edited_key = ".github/agents/overseer.agent.md"
    manifest_path = repo_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "files": {
                    edited_key: "old-edited-hash",
                    deleted_key: "old-deleted-hash",
                    unrelated_key: unrelated_hash,
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py"),
            "--reconcile-reviewed-files",
            str(edited),
            str(added),
            str(deleted),
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    files = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
    assert files == {
        edited_key: _sha256(edited),
        ".github/instructions/new.instructions.md": _sha256(added),
        unrelated_key: unrelated_hash,
    }
    verify_manifest(repo_root)


def test_reviewed_manifest_reconciliation_is_atomic_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    agent_file = repo_root / ".github" / "agents" / "overseer.agent.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("reviewed agent revision\n", encoding="utf-8")
    manifest_path = repo_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"files": {".github/agents/overseer.agent.md": "old-hash"}}),
        encoding="utf-8",
    )
    original_manifest = manifest_path.read_bytes()

    def fail_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(update_manifest.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated atomic replace failure"):
        update_manifest.reconcile_reviewed_manifest_entries(
            manifest_path, [agent_file], repo_root=repo_root
        )

    assert manifest_path.read_bytes() == original_manifest
    assert list(manifest_path.parent.glob("*.tmp")) == []


def test_reviewed_manifest_reconciliation_refuses_concurrent_manifest_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    agent_file = repo_root / ".github" / "agents" / "overseer.agent.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("reviewed agent revision\n", encoding="utf-8")
    manifest_path = repo_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"files": {".github/agents/overseer.agent.md": "old-hash"}}),
        encoding="utf-8",
    )
    concurrent_manifest = json.dumps(
        {"files": {"unrelated": "concurrent-writer-hash"}}
    ).encode("utf-8")
    original_dumps = json.dumps

    def write_concurrent_manifest(value: object, *args: object, **kwargs: object) -> str:
        serialized = original_dumps(value, *args, **kwargs)
        manifest_path.write_bytes(concurrent_manifest)
        return serialized

    monkeypatch.setattr(update_manifest.json, "dumps", write_concurrent_manifest)

    with pytest.raises(ValueError, match="(?i)manifest changed during"):
        update_manifest.reconcile_reviewed_manifest_entries(
            manifest_path, [agent_file], repo_root=repo_root
        )

    assert manifest_path.read_bytes() == concurrent_manifest
    assert list(manifest_path.parent.glob("*.tmp")) == []


def test_manifest_update_apis_serialize_concurrent_read_modify_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    agent_file = repo_root / ".github" / "agents" / "overseer.agent.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("reviewed agent revision\n", encoding="utf-8")
    instruction_file = repo_root / ".github" / "instructions" / "new.instructions.md"
    instruction_file.parent.mkdir(parents=True)
    instruction_file.write_text("reviewed instruction\n", encoding="utf-8")
    manifest_path = repo_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"files": {}}), encoding="utf-8")

    first_serialized = threading.Event()
    second_started = threading.Event()
    second_serialized = threading.Event()
    release_first = threading.Event()
    count_lock = threading.Lock()
    serialization_count = 0
    original_dumps = json.dumps
    errors: list[BaseException] = []

    def controlled_dumps(value: object, *args: object, **kwargs: object) -> str:
        nonlocal serialization_count
        serialized = original_dumps(value, *args, **kwargs)
        with count_lock:
            serialization_count += 1
            call_number = serialization_count
        if call_number == 1:
            first_serialized.set()
            if not release_first.wait(5):
                raise TimeoutError("first writer was not released")
        else:
            second_serialized.set()
        return serialized

    monkeypatch.setattr(update_manifest.json, "dumps", controlled_dumps)

    def reconcile_first() -> None:
        try:
            update_manifest.reconcile_reviewed_manifest_entries(
                manifest_path, [agent_file], repo_root=repo_root
            )
        except BaseException as error:
            errors.append(error)

    def update_second() -> None:
        try:
            second_started.set()
            update_manifest.update_manifest_entries(
                manifest_path, [instruction_file], repo_root=repo_root
            )
        except BaseException as error:
            errors.append(error)

    first_writer = threading.Thread(target=reconcile_first)
    second_writer = threading.Thread(target=update_second)
    first_writer.start()
    assert first_serialized.wait(3), "first writer did not reach manifest serialization"
    second_writer.start()
    assert second_started.wait(3), "second writer did not start"
    second_entered_manifest_write = second_serialized.wait(1)
    release_first.set()
    first_writer.join(5)
    second_writer.join(5)

    assert not first_writer.is_alive()
    assert not second_writer.is_alive()
    assert not second_entered_manifest_write
    assert errors == []
    files = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
    assert files == {
        ".github/agents/overseer.agent.md": _sha256(agent_file),
        ".github/instructions/new.instructions.md": _sha256(instruction_file),
    }


@pytest.mark.parametrize("concurrent_update", [False, True])
def test_locked_manifest_restore_preserves_concurrent_writer(
    tmp_path: Path, concurrent_update: bool
) -> None:
    repo_root = tmp_path / "workspace"
    manifest_path = repo_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    original_bytes = json.dumps({"files": {"original": "trusted"}}).encode("utf-8")
    written_bytes = json.dumps(
        {"files": {"original": "trusted", "reviewed": "updated"}}
    ).encode("utf-8")
    concurrent_bytes = json.dumps(
        {"files": {"original": "trusted", "other-writer": "preserve"}}
    ).encode("utf-8")
    manifest_path.write_bytes(concurrent_bytes if concurrent_update else written_bytes)
    backup_path = manifest_path.parent / ".skill-sync-manifest-backup-test.tmp"
    backup_path.write_bytes(original_bytes)

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py"),
            "--restore-manifest-backup",
            str(backup_path),
            "--expected-current-hash",
            hashlib.sha256(written_bytes).hexdigest(),
            "--expected-original-hash",
            hashlib.sha256(original_bytes).hexdigest(),
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if concurrent_update:
        assert result.returncode != 0
        assert manifest_path.read_bytes() == concurrent_bytes
        assert backup_path.read_bytes() == original_bytes
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert manifest_path.read_bytes() == original_bytes
        assert not backup_path.exists()


def test_locked_manifest_restore_falls_back_when_hardlinks_are_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    manifest_path = repo_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    original_bytes = json.dumps({"files": {"original": "trusted"}}).encode("utf-8")
    written_bytes = json.dumps(
        {"files": {"original": "trusted", "reviewed": "updated"}}
    ).encode("utf-8")
    manifest_path.write_bytes(written_bytes)
    backup_path = manifest_path.parent / ".skill-sync-manifest-backup-no-hardlinks.tmp"
    backup_path.write_bytes(original_bytes)

    def unsupported_hardlink(
        source: str | os.PathLike[str], destination: str | os.PathLike[str]
    ) -> None:
        error = OSError("hard links are unsupported")
        error.winerror = 1
        raise error

    monkeypatch.setattr(update_manifest.os, "link", unsupported_hardlink)

    restored_hash = update_manifest.restore_manifest_backup(
        manifest_path,
        backup_path,
        hashlib.sha256(original_bytes).hexdigest(),
        hashlib.sha256(written_bytes).hexdigest(),
        repo_root,
    )

    assert restored_hash == hashlib.sha256(original_bytes).hexdigest()
    assert manifest_path.read_bytes() == original_bytes
    assert not backup_path.exists()
    assert not list(manifest_path.parent.glob(".agent-manifest-restore-*.tmp"))
    assert not list(manifest_path.parent.glob(".agent-manifest-current-*.tmp"))


def test_locked_manifest_restore_preserves_writer_arriving_during_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    manifest_path = repo_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    original_bytes = json.dumps({"files": {"original": "trusted"}}).encode("utf-8")
    written_bytes = json.dumps(
        {"files": {"original": "trusted", "reviewed": "updated"}}
    ).encode("utf-8")
    concurrent_bytes = json.dumps(
        {"files": {"original": "trusted", "late-writer": "preserve"}}
    ).encode("utf-8")
    manifest_path.write_bytes(written_bytes)
    backup_path = manifest_path.parent / ".skill-sync-manifest-backup-race.tmp"
    backup_path.write_bytes(original_bytes)
    original_replace = update_manifest.os.replace

    def inject_concurrent_writer(
        source: str | os.PathLike[str], destination: str | os.PathLike[str]
    ) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == manifest_path:
            manifest_path.write_bytes(concurrent_bytes)
            original_replace(source_path, destination_path)
            return
        original_replace(source_path, destination_path)
        if source_path == manifest_path:
            manifest_path.write_bytes(concurrent_bytes)

    monkeypatch.setattr(update_manifest.os, "replace", inject_concurrent_writer)

    with pytest.raises(ValueError, match="(?i)(concurrent|changed|preserv)"):
        update_manifest.restore_manifest_backup(
            manifest_path,
            backup_path,
            hashlib.sha256(original_bytes).hexdigest(),
            hashlib.sha256(written_bytes).hexdigest(),
            repo_root,
        )

    assert manifest_path.read_bytes() == concurrent_bytes
    assert backup_path.read_bytes() == original_bytes


def test_reviewed_manifest_reconciliation_rejects_reparse_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "workspace"
    agent_file = repo_root / ".github" / "agents" / "overseer.agent.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("reviewed agent revision\n", encoding="utf-8")
    manifest_path = repo_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"files": {".github/agents/overseer.agent.md": "old-hash"}}),
        encoding="utf-8",
    )
    original_manifest = manifest_path.read_bytes()
    reparse_component = agent_file.parent
    original_lstat = Path.lstat

    def report_reparse(path: Path, *args: object, **kwargs: object) -> os.stat_result | SimpleNamespace:
        if path == reparse_component:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR,
                st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
            )
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", report_reparse)

    with pytest.raises(ValueError, match="(?i)(reparse|symbolic link)"):
        update_manifest.reconcile_reviewed_manifest_entries(
            manifest_path, [agent_file], repo_root=repo_root
        )

    assert manifest_path.read_bytes() == original_manifest


def test_reviewed_manifest_reconciliation_cannot_write_to_sync_config(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "workspace"
    agent_file = repo_root / ".github" / "agents" / "overseer.agent.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("reviewed agent revision\n", encoding="utf-8")
    config_path = repo_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [],
                "files": {"protected-policy": "unchanged"},
            }
        ),
        encoding="utf-8",
    )
    original_config = config_path.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py"),
            "--reconcile-reviewed-files",
            str(agent_file),
            "--manifest",
            str(config_path),
            "--repo-root",
            str(repo_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode != 0
    assert config_path.read_bytes() == original_config


def test_reviewed_manifest_reconciliation_rejects_sibling_manifest_path(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "workspace"
    agent_file = repo_root / ".github" / "agents" / "overseer.agent.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("reviewed agent revision\n", encoding="utf-8")
    alternate_manifest = repo_root / ".github" / "!!other" / "agent-manifest.json"
    alternate_manifest.parent.mkdir(parents=True)
    alternate_manifest.write_text(
        json.dumps({"files": {".github/agents/overseer.agent.md": "old-hash"}}),
        encoding="utf-8",
    )
    original_manifest = alternate_manifest.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py"),
            "--reconcile-reviewed-files",
            str(agent_file),
            "--manifest",
            str(alternate_manifest),
            "--repo-root",
            str(repo_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode != 0
    assert alternate_manifest.read_bytes() == original_manifest


def test_quarantine_allows_a_pinned_candidate_only_when_trusted_copy_matches(
    tmp_path: Path,
) -> None:
    workspace_root, _, _, _, _ = _write_quarantine_fixture(tmp_path)

    default_run = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "src" / "utils" / "prewrite_security_gate.py"),
            "--repo-root",
            str(workspace_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    quarantined_run = _run_quarantine_gate(workspace_root)

    assert default_run.returncode == 1
    assert quarantined_run.returncode == 0, quarantined_run.stdout + quarantined_run.stderr


@pytest.mark.parametrize("drift", ["target", "project-owned"])
def test_quarantine_does_not_suppress_target_or_project_owned_drift(
    tmp_path: Path, drift: str
) -> None:
    workspace_root, _, target_file, _, _ = _write_quarantine_fixture(tmp_path)
    if drift == "target":
        target_file.write_bytes(b"tampered installed skill\n")
    else:
        agent_file = workspace_root / ".github" / "agents" / "new.agent.md"
        agent_file.parent.mkdir(parents=True)
        agent_file.write_text("unreviewed project-owned content\n", encoding="utf-8")

    result = _run_quarantine_gate(workspace_root)

    assert result.returncode == 1, result.stdout + result.stderr


def test_quarantine_does_not_suppress_an_incomplete_pin_pair(tmp_path: Path) -> None:
    workspace_root, config_path, _, _, _ = _write_quarantine_fixture(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["sha256"] = "not-a-valid-sha"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = _run_quarantine_gate(workspace_root)

    assert result.returncode == 1, result.stdout + result.stderr


def test_reviewed_sync_updates_unpinned_external_skill_without_adding_pin(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "external-source"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"reviewed unpinned source update\n")
    _commit_git_repo(source_root)
    target_file = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_file.parent.mkdir(parents=True)
    target_file.write_bytes(b"trusted installed skill\n")

    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 1,
                "files": {
                    ".github/skills/example/SKILL.md": hashlib.sha256(
                        b"trusted installed skill\n"
                    ).hexdigest()
                },
            }
        ),
        encoding="utf-8",
    )
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [
                    {
                        "name": "external-source",
                        "path": str(source_root),
                        "remote": None,
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "source_policy": "required",
                        "skills": ["example"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (workspace_root / ".github" / "agents").mkdir(parents=True)
    (workspace_root / ".github" / "instructions").mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        manifest_path.parent / "update_manifest.py",
    )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveReviewedUpdates",
            "-ReviewedSkills",
            "example",
            "-ReviewRationale",
            "Reviewed the unpinned source diff as a benign content update.",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    saved_config = json.loads(config_path.read_text(encoding="utf-8"))
    source_mapping = saved_config["repos"][0]
    assert "pinned_commit" not in source_mapping
    assert "sha256" not in source_mapping
    assert target_file.read_bytes() == b"reviewed unpinned source update\n"
    files = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
    assert files == {
        ".github/skills/example/SKILL.md": hashlib.sha256(
            b"reviewed unpinned source update\n"
        ).hexdigest()
    }


@pytest.mark.parametrize(
    "sync_case",
    [
        "success",
        "late-gate-failure",
        "required-source-missing",
        "required-source-missing-optional-repo",
        "modified-target",
        "unexpected-target",
        "missing-target",
        "adaptation-only-new-target",
        "adaptation-only-source-matching-target",
        "adaptation-only-reviewed-target",
        "reviewed-adaptation-install",
        "reviewed-adaptation-install-without-approval",
    ],
)
def test_reviewed_sync_installs_only_selected_allowlisted_companion(
    tmp_path: Path, sync_case: str
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    is_adaptation_install = sync_case in {
        "reviewed-adaptation-install",
        "reviewed-adaptation-install-without-approval",
    }
    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "external-source"
    skill_source = source_root / "skills" / "example" / "SKILL.md"
    skill_source.parent.mkdir(parents=True)
    skill_source.write_bytes(b"reviewed skill update\n")
    unselected_skill_source = source_root / "skills" / "unselected" / "SKILL.md"
    unselected_skill_source.parent.mkdir(parents=True)
    unselected_skill_source.write_bytes(b"unchanged unselected skill\n")
    companion_source = source_root / "guides" / "check.md"
    companion_source.parent.mkdir(parents=True)
    companion_source.write_bytes(b"reviewed companion\n")
    (companion_source.parent / "unreviewed.md").write_bytes(b"not allowlisted\n")
    _commit_git_repo(source_root)

    skill_target = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    skill_target.parent.mkdir(parents=True)
    skill_target.write_bytes(b"trusted installed skill\n")
    unselected_skill_target = workspace_root / ".github" / "skills" / "unselected" / "SKILL.md"
    unselected_skill_target.parent.mkdir(parents=True)
    unselected_skill_target.write_bytes(b"unchanged unselected skill\n")
    unrelated_target = workspace_root / ".github" / "skills" / "unrelated" / "SKILL.md"
    unrelated_target.parent.mkdir(parents=True)
    unrelated_target.write_bytes(b"unrelated installed skill\n")
    companion_target = (
        workspace_root
        / ".github"
        / "skills"
        / "example"
        / "references"
        / "check.md"
    )
    reviewed_adaptation_source = (
        workspace_root
        / "tools"
        / "skill-sync-adaptations"
        / "wizard"
        / "template.sh"
    )
    if is_adaptation_install:
        reviewed_adaptation_source.parent.mkdir(parents=True)
        reviewed_adaptation_source.write_bytes(b"reviewed project adaptation\n")
    unselected_companion_target = (
        workspace_root
        / ".github"
        / "skills"
        / "unselected"
        / "references"
        / "check.md"
    )
    if sync_case in {
        "modified-target",
        "unexpected-target",
        "adaptation-only-source-matching-target",
            "adaptation-only-reviewed-target",
    }:
        companion_target.parent.mkdir(parents=True)
        companion_target.write_bytes(
            companion_source.read_bytes()
            if sync_case == "adaptation-only-source-matching-target"
                else b"reviewed project adaptation\n"
                if sync_case == "adaptation-only-reviewed-target"
            else b"unexpected companion target\n"
        )
    if sync_case in {
        "required-source-missing",
        "required-source-missing-optional-repo",
    }:
        companion_source.unlink()

    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_files = {
        ".github/skills/example/SKILL.md": _sha256(skill_target),
        ".github/skills/unselected/SKILL.md": _sha256(unselected_skill_target),
        ".github/skills/unrelated/SKILL.md": _sha256(unrelated_target),
    }
    if sync_case in {
        "modified-target",
        "missing-target",
        "adaptation-only-source-matching-target",
            "adaptation-only-reviewed-target",
    }:
        manifest_files[
            ".github/skills/example/references/check.md"
            ] = (
                _sha256(companion_target)
                if sync_case == "adaptation-only-reviewed-target"
                else _sha256(companion_source)
            )
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": len(manifest_files),
                "files": manifest_files,
            }
        ),
        encoding="utf-8",
    )
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [
                    {
                        "name": "external-source",
                        "path": str(source_root),
                        "remote": None,
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "source_policy": (
                            "optional"
                            if sync_case == "required-source-missing-optional-repo"
                            else "required"
                        ),
                        "skills": ["example", "unselected"],
                        "companions": [
                            {
                                "source_relative_path": "guides/check.md",
                                    "target_relative_paths": (
                                        [".github/skills/example/references/check.md"]
                                        if sync_case in {
                                            "success",
                                            "adaptation-only-reviewed-target",
                                            "reviewed-adaptation-install",
                                            "reviewed-adaptation-install-without-approval",
                                        }
                                        else [
                                            ".github/skills/example/references/check.md",
                                            ".github/skills/unselected/references/check.md",
                                        ]
                                    ),
                                "identity": "external-source:guides/check.md",
                                    "consumers": (
                                        ["example"]
                                        if sync_case in {
                                            "success",
                                            "adaptation-only-reviewed-target",
                                            "reviewed-adaptation-install",
                                            "reviewed-adaptation-install-without-approval",
                                        }
                                        else ["example", "unselected"]
                                    ),
                                "hash_contract": {
                                    "algorithm": "sha256",
                                    "accepted_baselines": [
                                        *(
                                            ["reviewed-project-owned-adaptation"]
                                            if sync_case in {
                                                "adaptation-only-new-target",
                                                "adaptation-only-source-matching-target",
                                                "adaptation-only-reviewed-target",
                                                "reviewed-adaptation-install",
                                                "reviewed-adaptation-install-without-approval",
                                            }
                                            else [
                                                "approved-source",
                                                "reviewed-project-owned-adaptation",
                                            ]
                                        ),
                                    ],
                                        "reviewed_adaptation_sha256": (
                                            _sha256(
                                                reviewed_adaptation_source
                                                if is_adaptation_install
                                                else companion_target
                                            )
                                            if sync_case
                                            in {
                                                "adaptation-only-reviewed-target",
                                                "reviewed-adaptation-install",
                                                "reviewed-adaptation-install-without-approval",
                                            }
                                            else None
                                        ),
                                },
                                "required": True,
                                **(
                                    {
                                        "reviewed_adaptation_source_relative_path": (
                                            "tools/skill-sync-adaptations/wizard/template.sh"
                                        )
                                    }
                                    if is_adaptation_install
                                    else {}
                                ),
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (workspace_root / ".github" / "agents").mkdir(parents=True)
    instructions_dir = workspace_root / ".github" / "instructions"
    instructions_dir.mkdir(parents=True)
    if sync_case == "late-gate-failure":
        (instructions_dir / "unreviewed.instructions.md").write_bytes(
            b"late gate failure fixture\n"
        )
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        manifest_path.parent / "update_manifest.py",
    )
    original_config = config_path.read_bytes()
    original_manifest = manifest_path.read_bytes()
    original_skill_target = skill_target.read_bytes()
    original_companion_target = (
        companion_target.read_bytes() if companion_target.exists() else None
    )

    sync_arguments = [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveReviewedUpdates",
                "-ReviewedSkills",
                "example",
            "-ReviewRationale",
            "Reviewed the companion source and target mapping.",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ]
    if sync_case == "reviewed-adaptation-install":
        sync_arguments.append("-InstallReviewedAdaptations")
    result = subprocess.run(
        sync_arguments,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )

    if sync_case not in {
        "success",
        "adaptation-only-reviewed-target",
        "reviewed-adaptation-install",
    }:
        assert result.returncode != 0, result.stdout + result.stderr
        if sync_case == "reviewed-adaptation-install-without-approval":
            assert "InstallReviewedAdaptations" in result.stdout + result.stderr
        assert skill_target.read_bytes() == original_skill_target
        if companion_target.exists():
            assert companion_target.read_bytes() == original_companion_target
        else:
            assert original_companion_target is None
        assert manifest_path.read_bytes() == original_manifest
        assert config_path.read_bytes() == original_config
        if sync_case == "late-gate-failure":
            assert not companion_target.parent.exists()
        return

    assert result.returncode == 0, result.stdout + result.stderr
    assert skill_target.read_bytes() == skill_source.read_bytes()
    expected_companion = (
        b"reviewed project adaptation\n"
        if sync_case in {
            "adaptation-only-reviewed-target",
            "reviewed-adaptation-install",
        }
        else companion_source.read_bytes()
    )
    assert companion_target.read_bytes() == expected_companion
    assert unselected_skill_target.read_bytes() == unselected_skill_source.read_bytes()
    assert not unselected_companion_target.exists()
    assert not (companion_target.parent / "unreviewed.md").exists()
    files = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
    expected_files = {
        ".github/skills/example/SKILL.md": _sha256(skill_source),
        ".github/skills/example/references/check.md": hashlib.sha256(
            expected_companion
        ).hexdigest(),
        ".github/skills/unselected/SKILL.md": _sha256(unselected_skill_target),
        ".github/skills/unrelated/SKILL.md": _sha256(unrelated_target),
    }
    assert files == expected_files


@pytest.mark.parametrize(
    (
        "target_existed",
        "delete_target",
        "race_target_after_hash",
    ),
    [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, False, True),
    ],
)
def test_reviewed_sync_rollback_preserves_concurrent_companion_change(
    tmp_path: Path,
    target_existed: bool,
    delete_target: bool,
    race_target_after_hash: bool,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "external-source"
    skill_source = source_root / "skills" / "example" / "SKILL.md"
    skill_source.parent.mkdir(parents=True)
    skill_source.write_bytes(b"reviewed skill update\n")
    companion_source = source_root / "guides" / "check.md"
    companion_source.parent.mkdir(parents=True)
    companion_source.write_bytes(b"reviewed companion\n")
    _commit_git_repo(source_root)

    skill_target = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    skill_target.parent.mkdir(parents=True)
    skill_target.write_bytes(b"trusted installed skill\n")
    companion_target = skill_target.parent / "references" / "check.md"
    original_companion = None
    if target_existed:
        companion_target.parent.mkdir(parents=True)
        companion_target.write_bytes(companion_source.read_bytes())
        original_companion = companion_target.read_bytes()
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    original_manifest = {
        "file_count": 1,
        "files": {".github/skills/example/SKILL.md": _sha256(skill_target)},
    }
    if target_existed:
        original_manifest["file_count"] = 2
        original_manifest["files"][
            ".github/skills/example/references/check.md"
        ] = _sha256(companion_target)
    manifest_path.write_text(json.dumps(original_manifest), encoding="utf-8")
    original_manifest_bytes = manifest_path.read_bytes()

    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [
                    {
                        "name": "external-source",
                        "path": str(source_root),
                        "remote": None,
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "source_policy": "required",
                        "skills": ["example"],
                        "companions": [
                            {
                                "source_relative_path": "guides/check.md",
                                "target_relative_paths": [
                                    ".github/skills/example/references/check.md"
                                ],
                                "identity": "external-source:guides/check.md",
                                "consumers": ["example"],
                                "hash_contract": {
                                    "algorithm": "sha256",
                                    "accepted_baselines": ["approved-source"],
                                },
                                "required": True,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    tools_dir = workspace_root / "tools"
    security_dir = manifest_path.parent
    scripts_dir = workspace_root / "src" / "utils"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "tools" / "sync-skills.ps1", tools_dir)
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        security_dir / "update_manifest.py",
    )
    (workspace_root / ".github" / "agents").mkdir(parents=True)
    (workspace_root / ".github" / "instructions").mkdir(parents=True)
    gate_action = (
        "target.unlink()\n"
        if delete_target
        else (
            "(root / '.skill-sync-race-after-hash').write_text('ready', encoding='utf-8')\n"
            if race_target_after_hash
            else "target.write_bytes(b'concurrent occupant\\n')\n"
        )
    )
    (scripts_dir / "prewrite_security_gate.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "root = Path(sys.argv[sys.argv.index('--repo-root') + 1])\n"
        "target = root / '.github' / 'skills' / 'example' / 'references' / 'check.md'\n"
        f"{gate_action}"
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )
    original_config = config_path.read_bytes()
    original_skill = skill_target.read_bytes()
    sync_script = tools_dir / "sync-skills.ps1"
    sync_environment = {
        **os.environ,
        "PYTHON_EXECUTABLE": sys.executable,
        "PYTHONUTF8": "1",
    }
    if race_target_after_hash:
        wrapper_path = tools_dir / "sync-skills-race.ps1"
        wrapper_path.write_text(
            "$targetPath = [IO.Path]::GetFullPath($env:SKILL_SYNC_RACE_TARGET)\n"
            "$markerPath = [IO.Path]::GetFullPath($env:SKILL_SYNC_RACE_MARKER)\n"
            "function Get-FileHash {\n"
            "    param([string]$LiteralPath, [string]$Path, [string]$Algorithm = 'SHA256')\n"
            "    $requestedPath = if ($LiteralPath) { $LiteralPath } else { $Path }\n"
            "    $result = Microsoft.PowerShell.Utility\\Get-FileHash -LiteralPath $requestedPath -Algorithm $Algorithm\n"
            "    if (Test-Path -LiteralPath $markerPath -PathType Leaf) {\n"
            "        Remove-Item -LiteralPath $markerPath -Force\n"
            "        [IO.File]::WriteAllBytes($targetPath, [Text.Encoding]::UTF8.GetBytes('concurrent occupant'))\n"
            "    }\n"
            "    return $result\n"
            "}\n"
            "& $env:SKILL_SYNC_SCRIPT @args\n"
            "exit $LASTEXITCODE\n",
            encoding="utf-8",
        )
        sync_script = wrapper_path
        sync_environment.update(
            {
                "SKILL_SYNC_SCRIPT": str(tools_dir / "sync-skills.ps1"),
                "SKILL_SYNC_RACE_TARGET": str(companion_target),
                "SKILL_SYNC_RACE_MARKER": str(
                    workspace_root / ".skill-sync-race-after-hash"
                ),
            }
        )

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(sync_script),
            "-ApproveReviewedUpdates",
            "-ReviewedSkills",
            "example",
            "-ReviewRationale",
            "Reviewed the companion source and target mapping.",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=sync_environment,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    if delete_target:
        assert not companion_target.exists(), result.stdout + result.stderr
    elif race_target_after_hash:
        assert companion_target.read_bytes() == b"concurrent occupant"
    else:
        assert companion_target.exists(), result.stdout + result.stderr
        assert companion_target.read_bytes() == b"concurrent occupant\n"
    if target_existed:
        backup_files = list(companion_target.parent.glob(".skill-sync-backup-*.tmp"))
        assert any(backup.read_bytes() == original_companion for backup in backup_files)
    assert skill_target.read_bytes() == original_skill
    assert manifest_path.read_bytes() == original_manifest_bytes
    assert config_path.read_bytes() == original_config


@pytest.mark.parametrize(
    "concurrent_action", ["before-update", "update", "delete"]
)
def test_reviewed_sync_rollback_preserves_concurrent_manifest_change(
    tmp_path: Path, concurrent_action: str
) -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("PowerShell is unavailable; Python restore contract remains covered")

    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "external-source"
    skill_source = source_root / "skills" / "example" / "SKILL.md"
    skill_source.parent.mkdir(parents=True)
    skill_source.write_bytes(b"reviewed skill update\n")
    companion_source = source_root / "guides" / "check.md"
    companion_source.parent.mkdir(parents=True)
    companion_source.write_bytes(b"reviewed companion\n")
    _commit_git_repo(source_root)

    skill_target = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    skill_target.parent.mkdir(parents=True)
    skill_target.write_bytes(b"trusted installed skill\n")
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    original_manifest = {
        "file_count": 1,
        "files": {".github/skills/example/SKILL.md": _sha256(skill_target)},
    }
    manifest_path.write_text(json.dumps(original_manifest), encoding="utf-8")
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [
                    {
                        "name": "external-source",
                        "path": str(source_root),
                        "remote": None,
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "source_policy": "required",
                        "skills": ["example"],
                        "companions": [
                            {
                                "source_relative_path": "guides/check.md",
                                "target_relative_paths": [
                                    ".github/skills/example/references/check.md"
                                ],
                                "identity": "external-source:guides/check.md",
                                "consumers": ["example"],
                                "hash_contract": {
                                    "algorithm": "sha256",
                                    "accepted_baselines": ["approved-source"],
                                },
                                "required": True,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    tools_dir = workspace_root / "tools"
    security_dir = manifest_path.parent
    scripts_dir = workspace_root / "src" / "utils"
    scripts_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "tools" / "sync-skills.ps1", tools_dir)
    real_updater = PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py"
    wrapper = (
        "import json, runpy, sys\n"
        "from pathlib import Path\n"
        f"real_updater = {str(real_updater)!r}\n"
        f"concurrent_action = {concurrent_action!r}\n"
        "arguments = sys.argv[1:]\n"
        "def apply_concurrent_change(manifest_path):\n"
        "    if concurrent_action == 'delete':\n"
        "        Path(manifest_path).unlink()\n"
        "        return\n"
        "    manifest = json.loads(open(manifest_path, encoding='utf-8').read())\n"
        "    manifest['files']['.github/skills/concurrent-writer.txt'] = 'preserve-me'\n"
        "    open(manifest_path, 'w', encoding='utf-8').write(json.dumps(manifest))\n"
        "if '--update-files' in arguments and concurrent_action == 'before-update':\n"
        "    manifest_path = arguments[arguments.index('--manifest') + 1]\n"
        "    apply_concurrent_change(manifest_path)\n"
        "sys.argv = [real_updater, *arguments]\n"
        "runpy.run_path(real_updater, run_name='__main__')\n"
        "if '--update-files' in arguments and concurrent_action != 'before-update':\n"
        "    manifest_path = arguments[arguments.index('--manifest') + 1]\n"
        "    apply_concurrent_change(manifest_path)\n"
    )
    (security_dir / "update_manifest.py").write_text(wrapper, encoding="utf-8")
    (workspace_root / ".github" / "agents").mkdir(parents=True)
    (workspace_root / ".github" / "instructions").mkdir(parents=True)
    (scripts_dir / "prewrite_security_gate.py").write_text(
        "raise SystemExit(1)\n", encoding="utf-8"
    )
    original_skill = skill_target.read_bytes()
    backup_pattern = ".skill-sync-manifest-backup-*.tmp"

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-File",
            str(tools_dir / "sync-skills.ps1"),
            "-ApproveReviewedUpdates",
            "-ReviewedSkills",
            "example",
            "-ReviewRationale",
            "Reviewed the companion source and target mapping.",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert skill_target.read_bytes() == original_skill
    if concurrent_action == "delete":
        assert not manifest_path.exists()
    else:
        files = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
        assert files[".github/skills/concurrent-writer.txt"] == "preserve-me"
    backup_files = list(manifest_path.parent.glob(backup_pattern))
    assert backup_files
    assert any(backup.read_bytes() == json.dumps(original_manifest).encode("utf-8") for backup in backup_files)


def test_reviewed_sync_rejects_noncanonical_manifest_before_target_write(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, target_file, fixture_manifest = _write_skill_fixture(
        tmp_path,
        source_text="candidate skill update\n",
        target_text="trusted installed skill\n",
        manifest_text="trusted installed skill\n",
    )
    workspace_root = target_file.parents[3]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["workspace_root"] = {"relative": "."}
    config["destination"] = {"relative": ".github/skills"}
    config["log_file"] = {"relative": "logs/skill-sync.log"}
    workspace_config = workspace_root / "tools" / "skill-sync-config.json"
    workspace_config.parent.mkdir(parents=True)
    workspace_config.write_text(json.dumps(config), encoding="utf-8")
    canonical_dir = workspace_root / ".github" / "!!☾⛧security"
    canonical_dir.mkdir(parents=True)
    canonical_manifest = canonical_dir / "agent-manifest.json"
    manifest = json.loads(fixture_manifest.read_text(encoding="utf-8"))
    manifest["files"] = {
        ".github/skills/example/SKILL.md": _sha256(target_file)
    }
    canonical_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    alternate_manifest = canonical_dir / "alternate-manifest.json"
    alternate_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    (workspace_root / ".github" / "agents").mkdir(parents=True)
    (workspace_root / ".github" / "instructions").mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        canonical_dir / "update_manifest.py",
    )
    original_target = target_file.read_bytes()
    original_config = workspace_config.read_bytes()
    original_alternate_manifest = alternate_manifest.read_bytes()

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveReviewedUpdates",
            "-ReviewedSkills",
            "example",
            "-ReviewRationale",
            "Reviewed the skill diff as benign.",
            "-ConfigPath",
            str(workspace_config),
            "-ManifestPath",
            str(alternate_manifest),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )

    assert result.returncode != 0
    assert target_file.read_bytes() == original_target
    assert workspace_config.read_bytes() == original_config
    assert alternate_manifest.read_bytes() == original_alternate_manifest


def test_reviewed_sync_rejects_noncanonical_config_before_target_write(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, target_file, fixture_manifest = _write_skill_fixture(
        tmp_path,
        source_text="candidate skill update\n",
        target_text="trusted installed skill\n",
        manifest_text="trusted installed skill\n",
    )
    workspace_root = target_file.parents[3]
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["workspace_root"] = {"relative": "."}
    config["destination"] = {"relative": ".github/skills"}
    config["log_file"] = {"relative": "logs/skill-sync.log"}
    tools_dir = workspace_root / "tools"
    tools_dir.mkdir(parents=True)
    canonical_config = tools_dir / "skill-sync-config.json"
    canonical_config.write_text(json.dumps(config), encoding="utf-8")
    alternate_config = tools_dir / "alternate-skill-sync-config.json"
    alternate_config.write_text(json.dumps(config), encoding="utf-8")
    canonical_dir = workspace_root / ".github" / "!!☾⛧security"
    canonical_dir.mkdir(parents=True)
    manifest_path = canonical_dir / "agent-manifest.json"
    manifest = json.loads(fixture_manifest.read_text(encoding="utf-8"))
    manifest["files"] = {
        ".github/skills/example/SKILL.md": _sha256(target_file)
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (workspace_root / ".github" / "agents").mkdir(parents=True)
    (workspace_root / ".github" / "instructions").mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        canonical_dir / "update_manifest.py",
    )
    original_target = target_file.read_bytes()
    original_config = alternate_config.read_bytes()

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveReviewedUpdates",
            "-ReviewedSkills",
            "example",
            "-ReviewRationale",
            "Reviewed the skill diff as benign.",
            "-ConfigPath",
            str(alternate_config),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )

    assert result.returncode != 0
    assert target_file.read_bytes() == original_target
    assert alternate_config.read_bytes() == original_config


def test_reviewed_sync_rejects_a_candidate_older_than_the_existing_pin(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    workspace_root, config_path, target_file, old_commit, new_commit = (
        _write_quarantine_fixture(tmp_path)
    )
    source_root = tmp_path / "external-source"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    candidate_content = b"unreviewed candidate skill\n"
    target_file.write_bytes(candidate_content)
    subprocess.run(
        ["git", "-C", str(source_root), "checkout", "--detach", old_commit],
        check=True,
        capture_output=True,
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["pinned_commit"] = new_commit
    config["repos"][0]["sha256"] = hashlib.sha256(candidate_content).hexdigest()
    config_path.write_text(json.dumps(config), encoding="utf-8")
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][".github/skills/example/SKILL.md"] = _sha256(target_file)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    original_config = config_path.read_bytes()
    original_target = target_file.read_bytes()

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveReviewedUpdates",
            "-ReviewedSkills",
            "example",
            "-ReviewRationale",
            "Reviewed the source candidate as benign.",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )

    assert result.returncode != 0
    assert config_path.read_bytes() == original_config
    assert target_file.read_bytes() == original_target
    assert source_file.read_bytes() == b"trusted installed skill\n"


def test_default_sync_leaves_existing_target_unchanged(tmp_path: Path) -> None:
    _, target_file, _ = _write_skill_fixture(
        tmp_path,
        source_text="new upstream\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )

    original = target_file.read_text(encoding="utf-8")

    # The default sync contract is represented by refusing to overwrite an existing target.
    assert target_file.read_text(encoding="utf-8") == original


def test_sync_script_default_and_approved_flows(tmp_path: Path) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="new upstream\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["log_file"] = str(tmp_path / "sync.log")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    script_path = PROJECT_ROOT / "tools" / "sync-skills.ps1"

    default_run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script_path),
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert default_run.returncode == 0, default_run.stderr
    assert target_file.read_text(encoding="utf-8") == "local customization\n"

    approved_run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(script_path),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert approved_run.returncode == 0, approved_run.stderr
    assert target_file.read_text(encoding="utf-8") == "new upstream\n"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"][".github/skills/example/SKILL.md"] == _sha256(target_file)
    assert manifest["files"][".github/skills/unrelated/SKILL.md"] == "preserve-this-hash"


def test_approved_sync_does_not_overwrite_non_external_mapping(tmp_path: Path) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="new upstream\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["provenance"] = "workspace-managed"
    config["log_file"] = str(tmp_path / "sync.log")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert run.returncode == 0, run.stderr
    assert target_file.read_text(encoding="utf-8") == "local customization\n"


def test_sync_preflights_all_mappings_before_writing_any_target(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="approved source\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repo = config["repos"][0]
    repo["skills"] = ["example", "../escape"]
    repo["source_path"] = "example/SKILL.md"
    config["log_file"] = str(tmp_path / "sync.log")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    escaped_target = manifest_path.parent.parent / "escape" / "SKILL.md"
    output = run.stdout + run.stderr
    assert run.returncode != 0
    assert "skill mapping must be a normalized relative path" in output.lower()
    assert target_file.read_text(encoding="utf-8") == "local customization\n"
    assert not escaped_target.exists()


def test_sync_preflight_resolves_companion_inventory_without_writing(
    tmp_path: Path,
) -> None:
    config_path, workspace_root, source_root = _write_companion_config_fixture(
        tmp_path
    )

    plan = update_manifest.preflight_sync_config(config_path)

    companion = plan["repos"][0]["companions"][0]
    assert companion["source"] == str(source_root / "guides" / "check.md")
    assert companion["source_relative_path"] == "guides/check.md"
    assert companion["identity"] == "external-skills:guides/check.md"
    assert companion["consumers"] == ["example"]
    assert companion["hash_contract"] == {
        "algorithm": "sha256",
        "accepted_baselines": [
            "approved-source",
            "reviewed-project-owned-adaptation",
        ],
    }
    assert companion["target_relative_paths"] == [
        ".github/skills/example/references/check.md"
    ]
    assert companion["targets"] == [
        str(
            workspace_root
            / ".github"
            / "skills"
            / "example"
            / "references"
            / "check.md"
        )
    ]
    assert not Path(companion["targets"][0]).exists()


def test_sync_preflight_preserves_shared_companion_fanout_targets(
    tmp_path: Path,
) -> None:
    shared_targets = [
        ".github/skills/example/references/check.md",
        ".github/skills/second-consumer/references/check.md",
    ]
    config_path, workspace_root, source_root = _write_companion_config_fixture(
        tmp_path, target_relative_paths=shared_targets
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["companions"][0]["consumers"] = [
        "example",
        "second-consumer",
    ]
    config_path.write_text(json.dumps(config), encoding="utf-8")

    plan = update_manifest.preflight_sync_config(config_path)

    companion = plan["repos"][0]["companions"][0]
    assert companion["source"] == str(source_root / "guides" / "check.md")
    assert companion["target_relative_paths"] == shared_targets
    assert companion["targets"] == [
        str(workspace_root / ".github" / "skills" / "example" / "references" / "check.md"),
        str(
            workspace_root
            / ".github"
            / "skills"
            / "second-consumer"
            / "references"
            / "check.md"
        ),
    ]


@pytest.mark.parametrize(
    ("source_relative_path", "target_relative_paths"),
    [
        ("../outside.md", [".github/skills/example/references/check.md"]),
        ("guides/check.md", [".github/skills/../outside.md"]),
        ("guides/check.md", ["C:/outside.md"]),
    ],
)
def test_sync_preflight_rejects_companion_path_traversal(
    tmp_path: Path,
    source_relative_path: str,
    target_relative_paths: list[str],
) -> None:
    config_path, _, _ = _write_companion_config_fixture(
        tmp_path,
        source_relative_path=source_relative_path,
        target_relative_paths=target_relative_paths,
    )

    with pytest.raises(ValueError, match="(?i)companion"):
        update_manifest.preflight_sync_config(config_path)


@pytest.mark.parametrize("duplicate", ["identity", "target"])
def test_sync_preflight_rejects_duplicate_companion_mappings(
    tmp_path: Path, duplicate: str
) -> None:
    config_path, _, source_root = _write_companion_config_fixture(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    original = config["repos"][0]["companions"][0]
    second = json.loads(json.dumps(original))
    if duplicate == "target":
        second["source_relative_path"] = "guides/second.md"
        second["identity"] = "external-skills:guides/second.md"
        (source_root / "guides" / "second.md").write_bytes(b"second companion\n")
    config["repos"][0]["companions"].append(second)
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)duplicate"):
        update_manifest.preflight_sync_config(config_path)


@pytest.mark.parametrize("side", ["source", "target"])
def test_sync_preflight_rejects_companion_symlink_components(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    side: str,
) -> None:
    config_path, workspace_root, source_root = _write_companion_config_fixture(
        tmp_path
    )
    if side == "source":
        symlink_component = source_root / "guides"
    else:
        symlink_component = workspace_root / ".github" / "skills" / "example"
        symlink_component.mkdir(parents=True)

    original_is_symlink = Path.is_symlink

    def report_symlink(path: Path) -> bool:
        return path == symlink_component or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_symlink)

    with pytest.raises(ValueError, match="(?i)companion.*(symlink|reparse)"):
        update_manifest.preflight_sync_config(config_path)


def test_sync_preflight_rejects_companion_source_root_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, _, source_root = _write_companion_config_fixture(tmp_path)
    original_is_symlink = Path.is_symlink

    def report_symlink(path: Path) -> bool:
        return path == source_root or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_symlink)

    with pytest.raises(ValueError, match="(?i)companion.*source.*(symlink|reparse)"):
        update_manifest.preflight_sync_config(config_path)


@pytest.mark.parametrize("side", ["workspace", "target"])
def test_sync_preflight_rejects_companion_root_reparse_points(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, side: str
) -> None:
    config_path, workspace_root, _ = _write_companion_config_fixture(tmp_path)
    symlink_root = (
        workspace_root
        if side == "workspace"
        else workspace_root / ".github" / "skills"
    )
    if side == "target":
        symlink_root.mkdir(parents=True)
    original_is_symlink = Path.is_symlink

    def report_symlink(path: Path) -> bool:
        return path == symlink_root or original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", report_symlink)

    with pytest.raises(ValueError, match="(?i)(workspace root|companion target root).*(symlink|reparse)"):
        update_manifest.preflight_sync_config(config_path)


def test_powershell_sync_rejects_reparse_point_in_root_ancestor(
    tmp_path: Path,
) -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("PowerShell is unavailable; Python root confinement remains covered")

    root = tmp_path / "workspace"
    target_path = root / ".github" / "skills" / "example" / "file.md"

    sync_script = (PROJECT_ROOT / "tools" / "sync-skills.ps1").read_text(
        encoding="utf-8"
    )
    function_start = sync_script.index("function Assert-NoReparsePointsInPath {")
    function_end = sync_script.index("\nfunction Invoke-PinnedTargetRestore {", function_start)
    function_text = sync_script[function_start:function_end]
    encoded_function = base64.b64encode(
        function_text.encode("utf-16-le")
    ).decode("ascii")
    root_literal = "'" + str(root).replace("'", "''") + "'"
    target_literal = "'" + str(target_path).replace("'", "''") + "'"
    command = (
        f"$functionText = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('{encoded_function}')); "
        f"$rootPath = [IO.Path]::GetFullPath({root_literal}); "
        "$ancestorPath = Split-Path -Parent $rootPath; "
        "function Get-Item { param([string]$LiteralPath, [switch]$Force); "
        "if ($LiteralPath -eq $rootPath) { return [pscustomobject]@{ Attributes = [IO.FileAttributes]::Directory } }; "
        "if ($LiteralPath -eq $ancestorPath) { return [pscustomobject]@{ Attributes = [IO.FileAttributes]::ReparsePoint } }; "
        "throw \"Unexpected Get-Item path: $LiteralPath\" }; "
        "Invoke-Expression $functionText; "
        f"Assert-NoReparsePointsInPath -RootPath $rootPath -Path {target_literal} -Description 'test'"
    )
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-Command",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "reparse point" in (result.stdout + result.stderr).lower()


def test_configured_companion_inventory_has_exact_sources_targets_and_hash_contracts() -> None:
    config_path = PROJECT_ROOT / "tools" / "skill-sync-config.json"
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    records = [
        (repo["name"], companion)
        for repo in raw_config["repos"]
        for companion in repo.get("companions", [])
    ]
    expected_mappings = [
        ("mp-skills-engineering", "skills/engineering/tdd/tests.md", [".github/skills/tdd/tests.md"], ["tdd"]),
        ("mp-skills-engineering", "skills/engineering/tdd/mocking.md", [".github/skills/tdd/mocking.md"], ["tdd"]),
        ("mp-skills-engineering", "skills/engineering/prototype/LOGIC.md", [".github/skills/prototype/LOGIC.md"], ["prototype"]),
        ("mp-skills-engineering", "skills/engineering/prototype/UI.md", [".github/skills/prototype/UI.md"], ["prototype"]),
        ("mp-skills-engineering", "skills/engineering/wizard/template.sh", [".github/skills/wizard/template.sh"], ["wizard"]),
        ("mp-skills-productivity", "skills/productivity/teach/MISSION-FORMAT.md", [".github/skills/teach/MISSION-FORMAT.md"], ["teach"]),
        ("mp-skills-productivity", "skills/productivity/teach/RESOURCES-FORMAT.md", [".github/skills/teach/RESOURCES-FORMAT.md"], ["teach"]),
        ("mp-skills-productivity", "skills/productivity/teach/LEARNING-RECORD-FORMAT.md", [".github/skills/teach/LEARNING-RECORD-FORMAT.md"], ["teach"]),
        (
            "addyosmani-agent-skills",
            "references/definition-of-done.md",
            [
                ".github/skills/incremental-implementation/references/definition-of-done.md",
                ".github/skills/planning-and-task-breakdown/references/definition-of-done.md",
            ],
            ["incremental-implementation", "planning-and-task-breakdown"],
        ),
        (
            "addyosmani-agent-skills",
            "references/orchestration-patterns.md",
            [".github/skills/doubt-driven-development/references/orchestration-patterns.md"],
            ["doubt-driven-development"],
        ),
        (
            "addyosmani-agent-skills",
            "references/security-checklist.md",
            [
                ".github/skills/code-review-and-quality/references/security-checklist.md",
                ".github/skills/security-and-hardening/references/security-checklist.md",
            ],
            ["code-review-and-quality", "security-and-hardening"],
        ),
        (
            "addyosmani-agent-skills",
            "references/performance-checklist.md",
            [".github/skills/code-review-and-quality/references/performance-checklist.md"],
            ["code-review-and-quality"],
        ),
        (
            "addyosmani-agent-skills",
            "skills/security-and-hardening/references/hardening-patterns.md",
            [".github/skills/security-and-hardening/references/hardening-patterns.md"],
            ["security-and-hardening"],
        ),
        (
            "addyosmani-agent-skills",
            "references/observability-checklist.md",
            [".github/skills/observability-and-instrumentation/references/observability-checklist.md"],
            ["observability-and-instrumentation"],
        ),
    ]
    actual_mappings = [
        (
            repo_name,
            companion["source_relative_path"],
            companion["target_relative_paths"],
            companion["consumers"],
        )
        for repo_name, companion in records
    ]

    assert len(records) == 14
    assert actual_mappings == expected_mappings
    assert len(
        {
            (repo_name, companion["source_relative_path"])
            for repo_name, companion in records
        }
    ) == 14
    assert len({companion["identity"] for _, companion in records}) == 14
    assert all(companion["required"] is True for _, companion in records)
    assert all(
        companion["hash_contract"]["algorithm"] == "sha256"
        and companion["hash_contract"]["accepted_baselines"]
        for _, companion in records
    )
    assert all(
        target.startswith(".github/skills/")
        for _, companion in records
        for target in companion["target_relative_paths"]
    )
    wizard = next(
        companion
        for repo_name, companion in records
        if repo_name == "mp-skills-engineering"
        and companion["source_relative_path"]
        == "skills/engineering/wizard/template.sh"
    )
    assert wizard["hash_contract"]["accepted_baselines"] == [
        "reviewed-project-owned-adaptation"
    ]
    assert wizard["required_constraints"] == [
        "user-terminal-or-environment-only",
        "no-repository-env-files",
        "no-model-context-or-logs",
    ]


def test_manifest_tracks_allowlisted_shell_companion(tmp_path: Path) -> None:
    target = tmp_path / ".github" / "skills" / "wizard" / "template.sh"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"printf 'reviewed fixture'\n")
    source_root = tmp_path / "wizard-source"
    source_root.mkdir()
    (source_root / "template.sh").write_bytes(b"approved source\n")
    config_path = tmp_path / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": {"relative": ".github/skills"},
                "log_file": {"relative": "logs/skill-sync.log"},
                "repos": [
                    {
                        "name": "reviewed-wizard",
                        "path": str(source_root),
                        "skill_root": ".",
                        "skills": [],
                        "companions": [
                            {
                                "source_relative_path": "template.sh",
                                "target_relative_paths": [
                                    ".github/skills/wizard/template.sh"
                                ],
                                "identity": "reviewed-wizard:template.sh",
                                "consumers": ["wizard"],
                                "required": True,
                                "hash_contract": {
                                    "algorithm": "sha256",
                                    "accepted_baselines": [
                                        "reviewed-project-owned-adaptation"
                                    ],
                                },
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    outside_root = tmp_path / "outside.sh"
    outside_root.write_bytes(b"unapproved shell content\n")
    unapproved_shell = tmp_path / ".github" / "skills" / "unapproved" / "script.sh"
    unapproved_shell.parent.mkdir(parents=True)
    unapproved_shell.write_bytes(b"unconfigured shell content\n")
    unapproved_link = unapproved_shell.parent / "linked.sh"
    try:
        unapproved_link.symlink_to(outside_root)
    except OSError:
        pass

    manifest = update_manifest.build_manifest(tmp_path)

    assert manifest["files"] == {
        ".github/skills/wizard/template.sh": hashlib.sha256(
            b"printf 'reviewed fixture'\n"
        ).hexdigest()
    }


def test_companion_integrity_reports_source_match(tmp_path: Path) -> None:
    config_path, workspace_root, source_root = _write_companion_config_fixture(tmp_path)
    source = source_root / "guides" / "check.md"
    source.write_bytes(b"approved companion\n")
    target = workspace_root / ".github" / "skills" / "example" / "references" / "check.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"approved companion\n")
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"files": {".github/skills/example/references/check.md": _sha256(target)}}),
        encoding="utf-8",
    )
    assert source.read_bytes() == target.read_bytes()

    result = verify_skill_integrity(config_path, manifest_path)

    assert [(entry.target, entry.status) for entry in result.entries] == [
        (str(target), "source_match")
    ]
    assert result.hard_findings == []


def test_companion_integrity_rejects_missing_required_target(
    tmp_path: Path,
) -> None:
    config_path, workspace_root, _ = _write_companion_config_fixture(tmp_path)
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"files": {}}), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert len(result.hard_findings) == 1
    assert result.hard_findings[0].status == "integrity_failure"


def test_companion_integrity_rejects_source_match_for_adaptation_only_policy(
    tmp_path: Path,
) -> None:
    config_path, workspace_root, source_root = _write_companion_config_fixture(tmp_path)
    source = source_root / "guides" / "check.md"
    source.write_bytes(b"upstream companion\n")
    _commit_git_repo(source_root)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["companions"][0]["hash_contract"]["accepted_baselines"] = [
        "reviewed-project-owned-adaptation"
    ]
    config_path.write_text(json.dumps(config), encoding="utf-8")
    target = workspace_root / ".github" / "skills" / "example" / "references" / "check.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"files": {".github/skills/example/references/check.md": _sha256(target)}}),
        encoding="utf-8",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.entries[0].status == "integrity_failure"
    assert result.hard_findings == result.entries


def test_companion_integrity_accepts_exact_reviewed_adaptation_hash(
    tmp_path: Path,
) -> None:
    config_path, workspace_root, source_root = _write_companion_config_fixture(tmp_path)
    source = source_root / "guides" / "check.md"
    source.write_bytes(b"upstream companion\n")
    _commit_git_repo(source_root)
    target = workspace_root / ".github" / "skills" / "example" / "references" / "check.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"reviewed adapted companion\n")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["companions"][0]["hash_contract"].update(
        {
            "accepted_baselines": ["reviewed-project-owned-adaptation"],
            "reviewed_adaptation_sha256": _sha256(target),
        }
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"files": {".github/skills/example/references/check.md": _sha256(target)}}),
        encoding="utf-8",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert result.entries[0].status == "reviewed_project_owned_adaptation"


@pytest.mark.parametrize("log_target", ["destination_subtree", "mapped_skill"])
def test_sync_rejects_log_path_overlapping_destination_before_logging(
    tmp_path: Path, log_target: str
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="approved source\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    destination = Path(config["destination"])
    log_path = (
        destination / "sync-logs" / "skill-sync.log"
        if log_target == "destination_subtree"
        else target_file
    )
    config["log_file"] = str(log_path)
    config_path.write_text(json.dumps(config), encoding="utf-8")

    run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    output = run.stdout + run.stderr
    assert run.returncode != 0, output
    assert "log" in output.lower()
    assert target_file.read_text(encoding="utf-8") == "local customization\n"
    if log_target == "destination_subtree":
        assert not log_path.parent.exists()


def test_sync_preflight_rejects_log_ancestor_of_missing_destination_without_creating_paths(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    config_path = workspace / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    source_root = tmp_path / "source"
    destination = workspace / "output" / "skills"
    output_root = destination.parent
    config = {
        "destination": str(destination),
        "log_file": str(output_root),
        "repos": [
            {
                "name": "external-skills",
                "path": str(source_root),
                "remote": None,
                "skill_root": "skills",
                "provenance": "external-source",
                "skills": ["example"],
            }
        ],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="log"):
        update_manifest.preflight_sync_config(config_path)

    assert not output_root.exists()
    assert not destination.exists()

    config["log_file"] = str(workspace / "logs" / "skill-sync.log")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    plan = update_manifest.preflight_sync_config(config_path)

    assert plan["destination"] == str(destination)
    assert not (workspace / "logs").exists()


def test_sync_preflight_rejects_external_hard_link_to_mapped_target_without_modifying_bytes(
    tmp_path: Path,
) -> None:
    config_path, target_file, _ = _write_skill_fixture(
        tmp_path,
        source_text="approved source\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    log_path = tmp_path / "external-skill-sync.log"
    try:
        os.link(target_file, log_path)
    except OSError as exc:
        unsupported = {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
        if exc.errno in unsupported or getattr(exc, "winerror", None) in {1, 50}:
            pytest.skip(f"Hard links are unsupported here: {exc}")
        raise

    assert os.path.samefile(target_file, log_path)
    original_bytes = target_file.read_bytes()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["log_file"] = str(log_path)
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="mapped skill target"):
        update_manifest.preflight_sync_config(config_path)

    assert target_file.read_bytes() == original_bytes


def test_sync_preflight_rejects_external_hard_link_to_mapped_source_under_workspace_root_without_modifying_bytes(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    config_path = workspace / "tools" / "skill-sync-config.json"
    source_root = workspace / "source-repo"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"approved source bytes\n")

    destination = workspace / ".github" / "skills"
    log_path = workspace / "logs" / "skill-sync.log"
    config_path.parent.mkdir(parents=True)
    log_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": str(workspace),
                "destination": str(destination),
                "log_file": str(log_path),
                "repos": [
                    {
                        "name": "workspace-skills",
                        "path": str(source_root),
                        "remote": None,
                        "skill_root": "skills",
                        "provenance": "external-source",
                        "skills": ["example"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    try:
        os.link(source_file, log_path)
    except OSError as exc:
        unsupported = {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
        if exc.errno in unsupported or getattr(exc, "winerror", None) in {1, 50}:
            pytest.skip(f"Hard links are unsupported here: {exc}")
        raise

    assert os.path.samefile(source_file, log_path)
    original_bytes = source_file.read_bytes()

    with pytest.raises(ValueError, match="mapped skill source"):
        update_manifest.preflight_sync_config(config_path)

    assert source_file.read_bytes() == original_bytes


@pytest.mark.parametrize("destination_preexists", [True, False])
def test_pinned_sync_validates_later_hash_before_changing_destination(
    tmp_path: Path, destination_preexists: bool
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, first_target, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="valid pinned source\n",
        target_text="preserve first target\n",
        manifest_text="preserve first target\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    destination = Path(config["destination"])
    if not destination_preexists:
        shutil.rmtree(destination)
    first_repo = config["repos"][0]
    first_root = Path(first_repo["path"])
    first_commit = _commit_git_repo(first_root)

    later_root = tmp_path / "later-source"
    later_file = later_root / "skills" / "later" / "SKILL.md"
    later_file.parent.mkdir(parents=True)
    later_file.write_text("later pinned source\n", encoding="utf-8")
    later_commit = _commit_git_repo(later_root)
    first_repo["pinned_commit"] = first_commit
    first_repo["sha256"] = _sha256(first_root / "skills" / "example" / "SKILL.md")
    config["repos"].append(
        {
            "name": "later-source",
            "path": str(later_root),
            "remote": None,
            "skill_root": "skills",
            "provenance": "external-source",
            "pinned_commit": later_commit,
            "sha256": hashlib.sha256(b"wrong expected hash\n").hexdigest(),
            "skills": ["later"],
        }
    )
    log_path = tmp_path / "external-logs" / "sync.log"
    config["log_file"] = str(log_path)
    config_path.write_text(json.dumps(config), encoding="utf-8")

    run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    output = run.stdout + run.stderr
    assert run.returncode != 0
    assert "pinned source hash mismatch for later-source" in output.lower()
    assert not log_path.exists()
    assert not log_path.parent.exists()
    if destination_preexists:
        assert first_target.read_text(encoding="utf-8") == "preserve first target\n"
    else:
        assert not destination.exists()
    assert not (destination / "later" / "SKILL.md").exists()
    _assert_no_temporary_git_worktrees(first_root)
    _assert_no_temporary_git_worktrees(later_root)


def test_pinned_sync_validates_later_symlink_before_writing_earlier_mapping(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    expected_content = "same pinned content\n"
    config_path, first_target, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text=expected_content,
        target_text="preserve first target\n",
        manifest_text="preserve first target\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repo = config["repos"][0]
    repo_root = Path(repo["path"])
    later_file = repo_root / "skills" / "later" / "SKILL.md"
    later_file.parent.mkdir(parents=True)
    later_file.write_text(expected_content, encoding="utf-8")
    outside_source = tmp_path / "outside-source.md"
    outside_source.write_text(expected_content, encoding="utf-8")
    later_file.unlink()
    _create_file_symlink_or_skip(later_file, outside_source)
    pinned_commit = _commit_git_repo(repo_root)
    later_file.unlink()
    later_file.write_text(expected_content, encoding="utf-8")

    repo["skills"] = ["example", "later"]
    repo["pinned_commit"] = pinned_commit
    repo["sha256"] = _sha256(outside_source)
    config["log_file"] = str(tmp_path / "sync.log")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    output = run.stdout + run.stderr
    assert run.returncode != 0
    assert "outside configured root" in output.lower()
    assert first_target.read_text(encoding="utf-8") == "preserve first target\n"
    assert not (manifest_path.parent.parent / "later" / "SKILL.md").exists()
    _assert_no_temporary_git_worktrees(repo_root)


def test_pinned_sync_preserves_dot_prefixed_source_path_with_windows_separators(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    expected_content = "approved dot-prefixed pinned source\n"
    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="working tree source\n",
        target_text="old target\n",
        manifest_text="old target\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repo = config["repos"][0]
    repo_root = Path(repo["path"])
    source_file = repo_root / ".hidden" / "release.v1" / "SKILL.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(expected_content, encoding="utf-8")
    repo["skill_root"] = "."
    repo["source_path"] = r".hidden\release.v1\SKILL.md"
    repo["pinned_commit"] = _commit_git_repo(repo_root)
    repo["sha256"] = _sha256(source_file)
    config["log_file"] = str(tmp_path / "sync.log")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert target_file.read_text(encoding="utf-8") == expected_content
    _assert_no_temporary_git_worktrees(repo_root)


def test_pinned_sync_removes_materialized_worktree_after_success(tmp_path: Path) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="approved pinned source\n",
        target_text="old target\n",
        manifest_text="old target\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repo = config["repos"][0]
    repo_root = Path(repo["path"])
    pinned_commit = _commit_git_repo(repo_root)
    repo["pinned_commit"] = pinned_commit
    repo["sha256"] = _sha256(repo_root / "skills" / "example" / "SKILL.md")
    config["log_file"] = str(tmp_path / "sync.log")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert run.returncode == 0, run.stderr
    assert target_file.read_text(encoding="utf-8") == "approved pinned source\n"
    _assert_no_temporary_git_worktrees(repo_root)


def test_pinned_sync_rejects_symlink_escape_in_materialized_commit(
    tmp_path: Path,
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="working tree source\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repo = config["repos"][0]
    source_file = Path(repo["path"]) / "skills" / "example" / "SKILL.md"
    outside_source = tmp_path / "outside-source.md"
    outside_source.write_text("outside pinned content\n", encoding="utf-8")

    subprocess.run(["git", "init", str(repo["path"])], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", repo["path"], "config", "core.symlinks", "true"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo["path"], "config", "user.name", "Skill Sync Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo["path"], "config", "user.email", "skill-sync@example.test"],
        check=True,
    )
    source_file.unlink()
    _create_file_symlink_or_skip(source_file, outside_source)
    subprocess.run(
        ["git", "-C", repo["path"], "add", "skills/example/SKILL.md"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo["path"], "commit", "-m", "Add escaping symlink"],
        check=True,
        capture_output=True,
    )
    pinned_commit = subprocess.run(
        ["git", "-C", repo["path"], "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    source_file.unlink()
    source_file.write_text("working tree source\n", encoding="utf-8")

    repo["pinned_commit"] = pinned_commit
    repo["sha256"] = hashlib.sha256(outside_source.read_bytes()).hexdigest()
    config["log_file"] = str(tmp_path / "sync.log")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    run = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    output = run.stdout + run.stderr
    assert run.returncode != 0
    assert "outside configured root" in output.lower()
    assert target_file.read_text(encoding="utf-8") == "local customization\n"


def test_superpowers_tdd_mapping_is_explicitly_provenanced(tmp_path: Path) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="tdd source\n",
        target_text="tdd source\n",
        manifest_text="tdd source\n",
        skill="test-driven-development",
        repo_name="superpowers",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["provenance"] = "external-source"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert result.entries[0].source_repository == "superpowers"
    assert result.entries[0].provenance == "external-source"


def test_workspace_config_declares_superpowers_tdd_provenance() -> None:
    config_path = PROJECT_ROOT / "tools" / "skill-sync-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    mapping = next(repo for repo in config["repos"] if repo["name"] == "superpowers")

    assert mapping["path"]["relative"] == "../superpowers"
    assert mapping["skill_root"] == "skills"
    assert mapping["skills"] == ["test-driven-development"]
    assert mapping["provenance"] == "external-source"
    assert mapping["source_policy"] == "optional"


def test_relocated_config_resolves_all_paths_from_checkout_root(tmp_path: Path) -> None:
    checkout = tmp_path / "relocated-checkout"
    config_path = checkout / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    source_root = checkout / "external" / "mp-skills"
    (source_root / "skills" / "tdd").mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"env": "TEST_WORKSPACE_ROOT", "default": "."},
                "destination": ".github/skills",
                "log_file": "logs/skill-sync.log",
                "repos": [
                    {
                        "name": "mp-skills",
                        "path": "external/mp-skills",
                        "skill_root": "skills",
                        "source_policy": "required",
                        "skills": ["tdd"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    old_root = os.environ.get("TEST_WORKSPACE_ROOT")
    os.environ["TEST_WORKSPACE_ROOT"] = str(checkout)
    try:
        config = resolve_sync_config(config_path)
    finally:
        if old_root is None:
            os.environ.pop("TEST_WORKSPACE_ROOT", None)
        else:
            os.environ["TEST_WORKSPACE_ROOT"] = old_root

    assert config["destination"] == checkout / ".github/skills"
    assert config["log_file"] == checkout / "logs/skill-sync.log"
    assert config["repos"][0]["path"] == source_root
    assert all(
        "f:\\" not in str(value).lower()
        for value in config.values()
        if isinstance(value, Path)
    )


def test_optional_missing_source_is_informational(tmp_path: Path) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="unused\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["path"] = str(tmp_path / "missing-source")
    config["repos"][0]["source_policy"] = "optional"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert result.entries[0].status == "source_unavailable"


def test_required_missing_source_remains_hard(tmp_path: Path) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="unused\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["path"] = str(tmp_path / "missing-source")
    config["repos"][0]["source_policy"] = "required"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = verify_skill_integrity(config_path, manifest_path)

    assert len(result.hard_findings) == 1
    assert result.entries[0].status == "integrity_failure"


def test_integrity_verification_rejects_source_outside_repository_root(
    tmp_path: Path,
) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="unused\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    outside_source = tmp_path / "outside" / "example" / "SKILL.md"
    outside_source.parent.mkdir(parents=True)
    outside_source.write_text("outside source\n", encoding="utf-8")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["skill_root"] = "../outside"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)source.*outside"):
        verify_skill_integrity(config_path, manifest_path)


def test_integrity_verification_rejects_source_link_outside_repository_root(
    tmp_path: Path,
) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="unused\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    outside_root = tmp_path / "outside-source"
    outside_file = outside_root / "example" / "SKILL.md"
    outside_file.parent.mkdir(parents=True)
    outside_file.write_text("outside source\n", encoding="utf-8")
    link = Path(json.loads(config_path.read_text(encoding="utf-8"))["repos"][0]["path"])
    link = link / "source-link"
    _create_directory_link_or_skip(link, outside_root)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["skill_root"] = "source-link"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)source.*outside"):
        verify_skill_integrity(config_path, manifest_path)


def test_integrity_verification_rejects_target_link_outside_destination(
    tmp_path: Path,
) -> None:
    config_path, target_file, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="upstream\n",
        target_text="local customization\n",
        manifest_text="local customization\n",
    )
    outside_target = tmp_path / "outside-target" / "example"
    outside_target.mkdir(parents=True)
    (outside_target / "SKILL.md").write_text("outside target\n", encoding="utf-8")
    target_link = target_file.parent
    target_file.unlink()
    target_link.rmdir()
    _create_directory_link_or_skip(target_link, outside_target)

    with pytest.raises(
        ValueError, match="(?i)(target.*outside|path contains a symlink or reparse point)"
    ):
        verify_skill_integrity(config_path, manifest_path)


def test_integrity_preflights_later_mappings_before_reading_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path, _, manifest_path = _write_skill_fixture(
        tmp_path,
        source_text="valid source\n",
        target_text="valid source\n",
        manifest_text="valid source\n",
    )
    outside_source = tmp_path / "outside" / "later" / "SKILL.md"
    outside_source.parent.mkdir(parents=True)
    outside_source.write_text("must not be read\n", encoding="utf-8")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"].append(
        {
            "name": "later-source",
            "path": str(tmp_path / "later-repository"),
            "remote": None,
            "skill_root": "../outside",
            "skills": ["later"],
        }
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")
    read_paths: list[Path] = []

    def record_read(path: Path) -> str:
        read_paths.append(path)
        return "unused"

    monkeypatch.setattr(update_manifest, "sha256_file", record_read)

    with pytest.raises(ValueError, match="(?i)source.*outside"):
        verify_skill_integrity(config_path, manifest_path)

    assert read_paths == []


@pytest.mark.parametrize("redirected_setting", ["destination", "log_file"])
def test_prewrite_security_gate_blocks_output_path_outside_workspace_before_writing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    redirected_setting: str,
) -> None:
    workspace_root = tmp_path / "Workspace"
    security_dir = workspace_root / ".github" / "!!☾⛧security"
    security_dir.mkdir(parents=True)
    destination = workspace_root / ".github" / "skills"
    destination.mkdir(parents=True)
    (workspace_root / ".github" / "agents").mkdir()
    (workspace_root / ".github" / "instructions").mkdir()
    (workspace_root / "tools").mkdir()
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        security_dir / "update_manifest.py",
    )

    source_root = tmp_path / "external-source-repository"
    source_file = source_root / "skills" / "example" / "SKILL.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("matching source\n", encoding="utf-8")
    target_file = destination / "example" / "SKILL.md"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("matching source\n", encoding="utf-8")

    manifest_path = security_dir / "agent-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"files": {".github/skills/example/SKILL.md": _sha256(target_file)}}
        ),
        encoding="utf-8",
    )
    outside_destination = tmp_path / "outside-destination" / "skills"
    outside_log = tmp_path / "outside-log" / "skill-sync.log"
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config = {
        "destination": str(
            outside_destination if redirected_setting == "destination" else destination
        ),
        "log_file": str(
            outside_log if redirected_setting == "log_file"
            else workspace_root / "logs" / "skill-sync.log"
        ),
        "repos": [
            {
                "name": "external-skills",
                "path": str(source_root),
                "skill_root": "skills",
                "skills": ["example"],
            }
        ],
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = run_prewrite_security_gate(workspace_root)

    captured = capsys.readouterr()
    assert result == 1
    assert "SKILL SYNC PATH POLICY:" in captured.out
    assert "outside configured root" in captured.out.lower()
    if redirected_setting == "destination":
        assert not outside_destination.exists()
        assert target_file.read_text(encoding="utf-8") == "matching source\n"
    else:
        assert not outside_log.parent.exists()
        assert target_file.read_text(encoding="utf-8") == "matching source\n"


def test_prewrite_security_gate_blocks_skill_config_path_escape(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace_root = tmp_path / "Workspace"
    security_dir = workspace_root / ".github" / "!!☾⛧security"
    security_dir.mkdir(parents=True)
    (workspace_root / ".github" / "agents").mkdir()
    (workspace_root / ".github" / "instructions").mkdir()
    (workspace_root / ".github" / "skills").mkdir()
    (workspace_root / "tools").mkdir()
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        security_dir / "update_manifest.py",
    )
    (security_dir / "agent-manifest.json").write_text(
        json.dumps({"files": {}}), encoding="utf-8"
    )

    outside_source = workspace_root / "external" / "outside" / "escape" / "SKILL.md"
    outside_source.parent.mkdir(parents=True)
    outside_source.write_text("outside source\n", encoding="utf-8")
    (workspace_root / "external" / "source").mkdir(parents=True)
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.write_text(
        json.dumps(
            {
                "destination": ".github/skills",
                "repos": [
                    {
                        "name": "external-skills",
                        "path": "external/source",
                        "skill_root": "../outside",
                        "skills": ["escape"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = run_prewrite_security_gate(workspace_root)

    captured = capsys.readouterr()
    assert result == 1
    assert "BLOCKED: canonical integrity verification" in captured.err


@pytest.mark.parametrize("failure_side", ["source", "target", "source-root"])
def test_prewrite_security_gate_blocks_path_resolution_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure_side: str,
) -> None:
    workspace_root = tmp_path / "Workspace"
    security_dir = workspace_root / ".github" / "!!☾⛧security"
    security_dir.mkdir(parents=True)
    (workspace_root / ".github" / "agents").mkdir()
    (workspace_root / ".github" / "instructions").mkdir()
    destination = workspace_root / ".github" / "skills"
    source_repository = workspace_root / "external" / "source"
    source_file = source_repository / "skills" / "escape" / "SKILL.md"
    target_file = destination / "escape" / "SKILL.md"
    source_file.parent.mkdir(parents=True)
    target_file.parent.mkdir(parents=True)
    source_file.write_text("source\n", encoding="utf-8")
    target_file.write_text("target\n", encoding="utf-8")
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        security_dir / "update_manifest.py",
    )
    manifest_path = security_dir / "agent-manifest.json"
    manifest_path.write_text(json.dumps({"files": {}}), encoding="utf-8")
    config_path = workspace_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "destination": ".github/skills",
                "repos": [
                    {
                        "name": "external-skills",
                        "path": "external/source",
                        "skill_root": "skills",
                        "skills": ["escape"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    resolution_failure = (
        source_file
        if failure_side == "source"
        else target_file
        if failure_side == "target"
        else source_repository
    )
    original_resolve = Path.resolve
    source_root_resolutions = 0

    def fail_path_resolution(path: Path, *args: object, **kwargs: object) -> Path:
        nonlocal source_root_resolutions
        if failure_side == "source-root" and path == source_repository:
            source_root_resolutions += 1
            if source_root_resolutions == 2:
                raise RuntimeError("symlink loop during source root resolution")
        elif path == resolution_failure:
            raise RuntimeError("symlink loop during path resolution")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fail_path_resolution)

    with pytest.raises(SystemExit) as verifier_exit:
        update_manifest.verify_manifest(workspace_root)

    verifier_output = capsys.readouterr()
    assert verifier_exit.value.code == 2
    assert "SKILL SYNC PATH POLICY:" in verifier_output.out
    expected_context = (
        "Source repository root for external-skills"
        if failure_side == "source-root"
        else f"{failure_side.title()} for external-skills"
    )
    assert expected_context in verifier_output.out

    def completed_verifier(
        args: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=verifier_exit.value.code,
            stdout=f"=== Agent File Integrity Check ===\n{verifier_output.out}",
            stderr=verifier_output.err,
        )

    monkeypatch.setattr(subprocess, "run", completed_verifier)

    result = run_prewrite_security_gate(workspace_root)

    captured = capsys.readouterr()
    assert result == 1
    assert "SKILL SYNC PATH POLICY:" in captured.out
    assert "BLOCKED: canonical integrity verification" in captured.err


def test_prewrite_security_gate_warns_and_allows_incomplete_verifier_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_verification(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=1,
            stdout="",
            stderr="verifier failed unexpectedly",
        )

    monkeypatch.setattr(subprocess, "run", fail_verification)

    result = run_prewrite_security_gate(tmp_path)

    captured = capsys.readouterr()
    assert result == 0
    assert "WARNING" in captured.err
    assert "allowing write" in captured.err