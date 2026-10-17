"""Tests for provenance-aware copied skill integrity checks."""
from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "!!☾⛧security"))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

from update_manifest import (
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
        ["git", "-C", str(repo_path), "commit", "-m", "Add pinned skill sources"],
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
    source_file.write_text(source_text, encoding="utf-8")

    destination = tmp_path / "workspace" / ".github" / "skills"
    target_file = destination / skill / "SKILL.md"
    target_file.parent.mkdir(parents=True)
    target_file.write_text(target_text, encoding="utf-8")

    manifest_path = tmp_path / "workspace" / ".github" / "!!security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    baseline_file = tmp_path / "manifest-baseline.md"
    baseline_file.write_text(manifest_text, encoding="utf-8")
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
        [*git, "commit", "-m", "pinned source"], check=True, capture_output=True
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
        other_source = source_root / "skills" / "other" / "SKILL.md"
        other_source.parent.mkdir(parents=True)
        other_source.write_bytes(b"different pinned path\n")
        subprocess.run([*git, "add", "skills/other/SKILL.md"], check=True)
    else:
        subprocess.run([*git, "add", "skills/example/SKILL.md"], check=True)

    subprocess.run([*git, "commit", "-m", "pinned source"], check=True, capture_output=True)
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
    subprocess.run([*git, "commit", "-m", "pinned source"], check=True, capture_output=True)

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

    update_manifest_entries(
        manifest_path,
        [target_file],
        repo_root=tmp_path / "workspace",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"][".github/skills/example/SKILL.md"] == _sha256(target_file)
    assert manifest["files"][".github/skills/unrelated/SKILL.md"] == "preserve-this-hash"
    result = verify_skill_integrity(config_path, manifest_path)
    assert result.hard_findings == []
    assert result.entries[0].status == "source_match"


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
    assert "target for external-skills path resolves outside configured root" in output.lower()
    assert target_file.read_text(encoding="utf-8") == "local customization\n"
    assert not escaped_target.exists()


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

    with pytest.raises(ValueError, match="(?i)target.*outside"):
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