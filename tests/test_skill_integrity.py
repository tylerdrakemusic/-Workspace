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