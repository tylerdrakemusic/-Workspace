"""Tests for provenance-aware copied skill integrity checks."""
from __future__ import annotations

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

from update_manifest import (
    resolve_sync_config,
    update_manifest_entries,
    verify_skill_integrity,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    assert mapping["source_policy"] == "required"


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