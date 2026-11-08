"""Tests for confined, hash-pinned adaptations of external skills."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import subprocess
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "!!☾⛧security"))

import update_manifest
from update_manifest import (
    preflight_sync_config,
    update_manifest_entries,
    verify_skill_integrity,
)


def test_code_review_mutation_experiment_guidance_is_authorized_and_isolated() -> None:
    """Checks guidance text only; it does not prove real-agent compliance."""
    skill_path = (
        PROJECT_ROOT
        / ".github"
        / "skills"
        / "code-review-and-quality"
        / "SKILL.md"
    )
    skill_text = skill_path.read_text(encoding="utf-8")
    review_tests = " ".join(
        skill_text.split("### Step 2: Review the Tests First", 1)[1]
        .split("### Step 3: Review the Implementation", 1)[0]
        .split()
    )

    assert "Do not mutate source worktrees during review." in review_tests
    assert "explicit per-task authorization" in review_tests
    assert "disposable isolated copy" in review_tests
    assert "isolated data and services" in review_tests
    assert "record the experiment as unperformed" in review_tests
    assert "Invert one condition" not in review_tests
    assert "restore the file from a copy" not in review_tests


def _commit_external_source(repo_root: Path) -> None:
    git = ["git", "-C", str(repo_root)]
    subprocess.run([*git, "init"], check=True, capture_output=True)
    subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
    subprocess.run([*git, "config", "user.name", "Reviewed Adaptation Test"], check=True)
    subprocess.run(
        [*git, "config", "user.email", "reviewed-adaptation@example.test"],
        check=True,
    )
    subprocess.run([*git, "add", "--all"], check=True, capture_output=True)
    subprocess.run(
        [*git, "commit", "-m", "Add external skill source"],
        check=True,
        capture_output=True,
    )


def _workspace_with_adaptation(
    tmp_path: Path,
    *,
    adaptation_relative_path: str = "tools/skill-sync-adaptations/example/SKILL.md",
    configured_hash: str | None = None,
) -> tuple[Path, Path, str]:
    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "external-source"
    skill_source = source_root / "skills" / "example" / "SKILL.md"
    skill_source.parent.mkdir(parents=True)
    skill_source.write_text("upstream skill\n", encoding="utf-8")
    _commit_external_source(source_root)

    adaptation_source = workspace_root / adaptation_relative_path
    adaptation_source.parent.mkdir(parents=True, exist_ok=True)
    adaptation_source.write_text("reviewed manual-only adaptation\n", encoding="utf-8")
    adaptation_hash = hashlib.sha256(
        adaptation_source.read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()

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
                        "skills": ["example"],
                        "reviewed_skill_adaptations": {
                            "example": {
                                "source_relative_path": adaptation_relative_path,
                                "sha256": configured_hash or adaptation_hash,
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path, adaptation_source, adaptation_hash


def test_preflight_resolves_separate_reviewed_skill_adaptation(
    tmp_path: Path,
) -> None:
    config_path, adaptation_source, adaptation_hash = _workspace_with_adaptation(
        tmp_path
    )

    result = preflight_sync_config(config_path)

    mapping = result["repos"][0]["mappings"][0]
    assert Path(mapping["source"]).parts[-3:] == (
        "skills",
        "example",
        "SKILL.md",
    )
    assert mapping["reviewed_adaptation_source"] == str(adaptation_source.resolve())
    assert mapping["reviewed_adaptation_sha256"] == adaptation_hash


def test_preflight_rejects_reviewed_skill_adaptation_hash_mismatch(
    tmp_path: Path,
) -> None:
    config_path, _, _ = _workspace_with_adaptation(
        tmp_path, configured_hash="0" * 64
    )

    with pytest.raises(ValueError, match="adaptation.*SHA-256"):
        preflight_sync_config(config_path)


def test_preflight_rejects_reviewed_skill_adaptation_symlink(
    tmp_path: Path,
) -> None:
    config_path, adaptation_source, _ = _workspace_with_adaptation(tmp_path)
    external_path = tmp_path / "outside" / "SKILL.md"
    external_path.parent.mkdir()
    external_path.write_text("external file\n", encoding="utf-8")
    adaptation_source.unlink()
    try:
        adaptation_source.symlink_to(external_path)
    except OSError as exc:
        pytest.skip(f"File symlinks are unavailable: {exc}")

    with pytest.raises(ValueError, match="symlink|reparse"):
        preflight_sync_config(config_path)


def test_preflight_rejects_reviewed_skill_adaptation_outside_workspace(
    tmp_path: Path,
) -> None:
    config_path, _, _ = _workspace_with_adaptation(
        tmp_path, adaptation_relative_path="../outside/SKILL.md"
    )

    with pytest.raises(ValueError, match="normalized tools/skill-sync-adaptations path"):
        preflight_sync_config(config_path)


def test_preflight_rejects_skill_target_symlink_to_another_workspace_file(
    tmp_path: Path,
) -> None:
    config_path, _, _ = _workspace_with_adaptation(tmp_path)
    workspace_root = config_path.parent.parent
    redirected_target = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    redirected_target.parent.mkdir(parents=True)
    protected_target = workspace_root / ".github" / "skills" / "unselected" / "SKILL.md"
    protected_target.parent.mkdir(parents=True)
    protected_target.write_text("unselected skill\n", encoding="utf-8")
    try:
        redirected_target.symlink_to(protected_target)
    except OSError as exc:
        pytest.skip(f"File symlinks are unavailable: {exc}")

    with pytest.raises(ValueError, match="symlink|reparse|canonical skill target"):
        preflight_sync_config(config_path)


def test_preflight_rejects_noncanonical_skill_target_alias(tmp_path: Path) -> None:
    config_path, _, _ = _workspace_with_adaptation(tmp_path)
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    repo = raw_config["repos"][0]
    alias = "example/../unselected"
    repo["skills"] = [alias]
    repo["reviewed_skill_adaptations"] = {
        alias: repo["reviewed_skill_adaptations"]["example"]
    }
    config_path.write_text(json.dumps(raw_config), encoding="utf-8")

    with pytest.raises(ValueError, match="normalized relative path"):
        preflight_sync_config(config_path)


def test_integrity_verifier_accepts_only_manifest_matched_reviewed_adaptation(
    tmp_path: Path,
) -> None:
    config_path, _, adaptation_hash = _workspace_with_adaptation(tmp_path)
    workspace_root = config_path.parent.parent
    target_path = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("reviewed manual-only adaptation\n", encoding="utf-8")
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 1,
                "files": {
                    ".github/skills/example/SKILL.md": hashlib.sha256(
                        target_path.read_bytes()
                    ).hexdigest(),
                },
            }
        ),
        encoding="utf-8",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert [entry.status for entry in result.entries] == [
        "reviewed_project_owned_adaptation"
    ]


@pytest.mark.parametrize(
    ("source_newline", "target_newline"),
    [(b"\n", b"\r\n"), (b"\r\n", b"\n")],
)
def test_reviewed_adaptation_hash_is_line_ending_portable_and_manual_only(
    tmp_path: Path, source_newline: bytes, target_newline: bytes
) -> None:
    config_path, adaptation_source, _ = _workspace_with_adaptation(tmp_path)
    canonical_text = (
        "---\n"
        "name: example\n"
        "user-invocable: true\n"
        "disable-model-invocation: true\n"
        "description: Manual-only adaptation.\n"
        "---\n"
        "\n"
        "Reviewed body.\n"
    )
    canonical_bytes = canonical_text.encode("utf-8")
    portable_hash = hashlib.sha256(canonical_bytes).hexdigest()
    adaptation_source.write_bytes(canonical_bytes.replace(b"\n", source_newline))

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["repos"][0]["reviewed_skill_adaptations"]["example"]["sha256"] = (
        portable_hash
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")
    preflight = preflight_sync_config(config_path)
    assert preflight["repos"][0]["mappings"][0]["reviewed_adaptation_sha256"] == (
        portable_hash
    )

    workspace_root = config_path.parent.parent
    target_path = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_bytes = canonical_bytes.replace(b"\n", target_newline)
    target_path.write_bytes(target_bytes)
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "files": {
                    ".github/skills/example/SKILL.md": hashlib.sha256(
                        target_bytes
                    ).hexdigest()
                }
            }
        ),
        encoding="utf-8",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert [entry.status for entry in result.entries] == [
        "reviewed_project_owned_adaptation"
    ]
    _, _, metadata_and_body = canonical_text.partition("---\n")
    metadata_text, _, _ = metadata_and_body.partition("\n---\n")
    metadata = yaml.safe_load(metadata_text)
    assert metadata["user-invocable"] is True
    assert metadata["disable-model-invocation"] is True


def test_reviewed_adaptation_target_non_eol_change_is_integrity_failure(
    tmp_path: Path,
) -> None:
    config_path, _, _ = _workspace_with_adaptation(tmp_path)
    workspace_root = config_path.parent.parent
    target_path = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_bytes(b"reviewed manual-only adaptation changed\n")
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "files": {
                    ".github/skills/example/SKILL.md": hashlib.sha256(
                        target_path.read_bytes()
                    ).hexdigest(),
                }
            }
        ),
        encoding="utf-8",
    )

    result = verify_skill_integrity(config_path, manifest_path)

    assert [entry.status for entry in result.entries] == ["integrity_failure"]
    assert len(result.hard_findings) == 1


def test_manifest_update_rejects_target_changed_from_reviewed_hash(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    target_path = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("concurrent replacement\n", encoding="utf-8")
    expected_hash = hashlib.sha256(b"reviewed adaptation\n").hexdigest()
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"files": {}}), encoding="utf-8")
    original_manifest = manifest_path.read_bytes()

    with pytest.raises(ValueError, match="expected SHA-256"):
        update_manifest_entries(
            manifest_path,
            [target_path],
            repo_root=workspace_root,
            expected_file_hashes={target_path.resolve(): expected_hash},
        )

    assert manifest_path.read_bytes() == original_manifest


def test_manifest_update_rechecks_expected_target_reparse_state_under_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    target_path = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("reviewed adaptation\n", encoding="utf-8")
    expected_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps({"files": {}}), encoding="utf-8")
    original_manifest = manifest_path.read_bytes()
    original_check = update_manifest._reject_path_reparse_components

    def reject_expected_target(path: Path, description: str) -> None:
        if Path(path) == target_path and description == "Reviewed manifest update target":
            raise ValueError("Reviewed manifest update target contains a simulated reparse point")
        original_check(path, description)

    monkeypatch.setattr(
        update_manifest, "_reject_path_reparse_components", reject_expected_target
    )

    with pytest.raises(ValueError, match="simulated reparse point"):
        update_manifest_entries(
            manifest_path,
            [target_path],
            repo_root=workspace_root,
            expected_file_hashes={target_path.resolve(): expected_hash},
        )

    assert manifest_path.read_bytes() == original_manifest


def _reviewed_sync_workspace(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "external-source"
    skill_source = source_root / "skills" / "example" / "SKILL.md"
    skill_source.parent.mkdir(parents=True)
    skill_source.write_text("upstream baseline\n", encoding="utf-8")
    _commit_external_source(source_root)

    target_path = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("trusted baseline\n", encoding="utf-8")
    adaptation_source = (
        workspace_root
        / "tools"
        / "skill-sync-adaptations"
        / "example"
        / "SKILL.md"
    )
    adaptation_source.parent.mkdir(parents=True)
    adaptation_source.write_text("reviewed manual-only adaptation\n", encoding="utf-8")

    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 1,
                "files": {
                    ".github/skills/example/SKILL.md": hashlib.sha256(
                        target_path.read_bytes()
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
                        "skills": ["example"],
                        "reviewed_skill_adaptations": {
                            "example": {
                                "source_relative_path": (
                                    "tools/skill-sync-adaptations/example/SKILL.md"
                                ),
                                "sha256": hashlib.sha256(
                                    adaptation_source.read_text(
                                        encoding="utf-8"
                                    ).encode("utf-8")
                                ).hexdigest(),
                            }
                        },
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
    return config_path, manifest_path, target_path, adaptation_source


def _add_pinned_skill(
    config_path: Path, manifest_path: Path
) -> tuple[Path, bytes, bytes]:
    workspace_root = config_path.parent.parent
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source_root = workspace_root.parent / "pinned-source"
    source_path = source_root / "skills" / "pinned" / "SKILL.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("pinned source baseline\n", encoding="utf-8")
    git = ["git", "-C", str(source_root)]
    subprocess.run([*git, "init"], check=True, capture_output=True, text=True)
    subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
    subprocess.run([*git, "config", "user.name", "Reviewed Adaptation Test"], check=True)
    subprocess.run(
        [*git, "config", "user.email", "reviewed-adaptation@example.test"],
        check=True,
    )
    subprocess.run([*git, "add", "--all"], check=True)
    subprocess.run([*git, "commit", "-m", "Pinned skill source"], check=True, capture_output=True)
    pinned_commit = subprocess.run(
        [*git, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    target_path = workspace_root / ".github" / "skills" / "pinned" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("trusted pinned target\n", encoding="utf-8")
    config["repos"].append(
        {
            "name": "pinned-source",
            "path": str(source_root),
            "remote": None,
            "skill_root": "skills",
            "provenance": "external-source",
            "source_policy": "required",
            "skills": ["pinned"],
            "pinned_commit": pinned_commit,
            "sha256": source_hash,
        }
    )
    config_path.write_text(json.dumps(config), encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][".github/skills/pinned/SKILL.md"] = hashlib.sha256(
        target_path.read_bytes()
    ).hexdigest()
    manifest["file_count"] = len(manifest["files"])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return target_path, config_path.read_bytes(), manifest_path.read_bytes()


def _run_reviewed_sync(
    config_path: Path,
    manifest_path: Path,
    *,
    allow_adaptation_install: bool,
    skills: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")
    if skills and len(skills) > 1:
        def quote(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        selected = "@(" + ", ".join(quote(skill) for skill in skills) + ")"
        script = PROJECT_ROOT / "tools" / "sync-skills.ps1"
        driver = config_path.parent / "reviewed-sync-driver.ps1"
        command = (
            f"& {quote(str(script))} -ApproveReviewedUpdates "
            f"-ReviewedSkills {selected} "
            f"-ReviewRationale {quote('Reviewed the scoped manual-only skill adaptation.')} "
            f"-ConfigPath {quote(str(config_path))} "
            f"-ManifestPath {quote(str(manifest_path))}"
        )
        if allow_adaptation_install:
            command += " -InstallReviewedAdaptations"
        driver.write_text(command + "\n", encoding="utf-8")
        return subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(driver)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
        )
    arguments = [
        "pwsh",
        "-NoProfile",
        "-File",
        str(PROJECT_ROOT / "tools" / "sync-skills.ps1"),
        "-ApproveReviewedUpdates",
        "-ReviewedSkills",
        *(skills or ["example"]),
        "-ReviewRationale",
        "Reviewed the scoped manual-only skill adaptation.",
        "-ConfigPath",
        str(config_path),
        "-ManifestPath",
        str(manifest_path),
    ]
    if allow_adaptation_install:
        arguments.append("-InstallReviewedAdaptations")
    return subprocess.run(
        arguments,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )


def _run_ordinary_protected_sync(
    config_path: Path, manifest_path: Path
) -> subprocess.CompletedProcess[str]:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")
    return subprocess.run(
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
        env={**os.environ, "PYTHON_EXECUTABLE": sys.executable, "PYTHONUTF8": "1"},
    )


def test_ordinary_protected_sync_cannot_overwrite_reviewed_adaptation(
    tmp_path: Path,
) -> None:
    config_path, manifest_path, target_path, _ = _reviewed_sync_workspace(tmp_path)
    original_manifest = manifest_path.read_bytes()
    original_target = target_path.read_bytes()

    result = _run_ordinary_protected_sync(config_path, manifest_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "C7" in result.stdout + result.stderr
    assert target_path.read_bytes() == original_target
    assert manifest_path.read_bytes() == original_manifest


def test_reviewed_adaptation_sync_rejects_mixed_pinned_config_update(
    tmp_path: Path,
) -> None:
    config_path, manifest_path, target_path, _ = _reviewed_sync_workspace(tmp_path)
    pinned_target, original_config, original_manifest = _add_pinned_skill(
        config_path, manifest_path
    )
    original_target = target_path.read_bytes()
    original_pinned_target = pinned_target.read_bytes()

    result = _run_reviewed_sync(
        config_path,
        manifest_path,
        allow_adaptation_install=True,
        skills=["example", "pinned"],
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert "reviewed sync" in result.stdout + result.stderr
    assert target_path.read_bytes() == original_target
    assert pinned_target.read_bytes() == original_pinned_target
    assert manifest_path.read_bytes() == original_manifest
    assert config_path.read_bytes() == original_config


def test_reviewed_skill_adaptation_install_requires_explicit_approval_and_updates_manifest(
    tmp_path: Path,
) -> None:
    config_path, manifest_path, target_path, adaptation_source = (
        _reviewed_sync_workspace(tmp_path)
    )
    original_manifest = manifest_path.read_bytes()
    original_target = target_path.read_bytes()

    denied = _run_reviewed_sync(
        config_path, manifest_path, allow_adaptation_install=False
    )

    assert denied.returncode != 0, denied.stdout + denied.stderr
    assert "InstallReviewedAdaptations" in denied.stdout + denied.stderr
    assert target_path.read_bytes() == original_target
    assert manifest_path.read_bytes() == original_manifest

    approved = _run_reviewed_sync(
        config_path, manifest_path, allow_adaptation_install=True
    )

    assert approved.returncode == 0, approved.stdout + approved.stderr
    assert target_path.read_bytes() == adaptation_source.read_bytes()
    files = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
    assert files[".github/skills/example/SKILL.md"] == hashlib.sha256(
        adaptation_source.read_bytes()
    ).hexdigest()


@pytest.mark.parametrize(
    "failure_mode",
    [
        "concurrent-replacement",
        "claim-hash-failure",
        "claim-hash-failure-blocked",
        "final-write-collision",
    ],
)
def test_reviewed_sync_config_claim_failure_preserves_canonical_path(
    tmp_path: Path, failure_mode: str
) -> None:
    if shutil.which("pwsh") is None:
        pytest.skip("PowerShell is unavailable; Python contract tests remain portable")

    workspace_root = tmp_path / "workspace"
    source_root = tmp_path / "external-source"
    source_path = source_root / "skills" / "example" / "SKILL.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("old pinned source\n", encoding="utf-8")
    git = ["git", "-C", str(source_root)]
    subprocess.run([*git, "init"], check=True, capture_output=True, text=True)
    subprocess.run([*git, "config", "core.autocrlf", "false"], check=True)
    subprocess.run([*git, "config", "user.name", "Reviewed Config Race Test"], check=True)
    subprocess.run(
        [*git, "config", "user.email", "reviewed-config-race@example.test"],
        check=True,
    )
    subprocess.run([*git, "add", "--all"], check=True)
    subprocess.run([*git, "commit", "-m", "Original pinned source"], check=True, capture_output=True)
    original_pin = subprocess.run(
        [*git, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    original_source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    source_path.write_text("reviewed pinned source update\n", encoding="utf-8")
    subprocess.run([*git, "add", "--all"], check=True)
    subprocess.run([*git, "commit", "-m", "Reviewed pinned source update"], check=True, capture_output=True)

    target_path = workspace_root / ".github" / "skills" / "example" / "SKILL.md"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("trusted target\n", encoding="utf-8")
    manifest_path = workspace_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "file_count": 1,
                "files": {
                    ".github/skills/example/SKILL.md": hashlib.sha256(
                        target_path.read_bytes()
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
                        "pinned_commit": original_pin,
                        "sha256": original_source_hash,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (workspace_root / ".github" / "agents").mkdir(parents=True)
    (workspace_root / ".github" / "instructions").mkdir(parents=True)
    gate_path = workspace_root / "src" / "utils" / "prewrite_security_gate.py"
    gate_path.parent.mkdir(parents=True)
    gate_path.write_text("raise SystemExit(1)\n", encoding="utf-8")
    security_dir = manifest_path.parent
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        security_dir / "update_manifest.py",
    )
    shutil.copy2(PROJECT_ROOT / "tools" / "sync-skills.ps1", config_path.parent)
    concurrent_config_path = tmp_path / "concurrent-config.json"
    concurrent_config_bytes = b"concurrent config replacement\n"
    concurrent_config_path.write_bytes(concurrent_config_bytes)
    injection_marker = tmp_path / "config-race-injected.txt"
    original_config_bytes = config_path.read_bytes()
    original_manifest_bytes = manifest_path.read_bytes()
    original_target_bytes = target_path.read_bytes()
    wrapper_path = config_path.parent / "sync-skills-race.ps1"
    wrapper_path.write_text(
        "$configPath = [IO.Path]::GetFullPath($env:SKILL_SYNC_RACE_CONFIG)\n"
        "$concurrentPath = [IO.Path]::GetFullPath($env:SKILL_SYNC_CONCURRENT_CONFIG)\n"
        "$failureMode = $env:SKILL_SYNC_FAILURE_MODE\n"
        "$script:configHashCalls = 0\n"
        "function Get-FileHash {\n"
        "    param([string]$LiteralPath, [string]$Path, [string]$Algorithm = 'SHA256')\n"
        "    $requestedPath = if ($LiteralPath) { $LiteralPath } else { $Path }\n"
        "    if ($failureMode -like 'claim-hash-failure*' -and $requestedPath -like '*.skill-sync-config-claim-*.tmp') {\n"
        "        if ($failureMode -eq 'claim-hash-failure-blocked') { [IO.Directory]::CreateDirectory($configPath) | Out-Null }\n"
        "        throw 'simulated claim hash failure'\n"
        "    }\n"
        "    $observed = Microsoft.PowerShell.Utility\\Get-FileHash -LiteralPath $requestedPath -Algorithm $Algorithm\n"
        "    if ($failureMode -eq 'final-write-collision' -and $requestedPath -like '*.skill-sync-config-claim-*.tmp') {\n"
        "        [IO.File]::WriteAllBytes($configPath, [IO.File]::ReadAllBytes($concurrentPath))\n"
        "        [IO.File]::WriteAllText($env:SKILL_SYNC_RACE_MARKER, 'injected')\n"
        "    }\n"
        "    if ([IO.Path]::GetFullPath($requestedPath) -eq $configPath) {\n"
        "        $script:configHashCalls++\n"
        "        if ($failureMode -eq 'concurrent-replacement' -and $script:configHashCalls -eq 3) {\n"
        "            [IO.File]::WriteAllBytes($configPath, [IO.File]::ReadAllBytes($concurrentPath))\n"
        "            [IO.File]::WriteAllText($env:SKILL_SYNC_RACE_MARKER, 'injected')\n"
        "        }\n"
        "    }\n"
        "    return $observed\n"
        "}\n"
        "try { & $env:SKILL_SYNC_SCRIPT @args } catch { Write-Output $_; exit 1 }\n"
        "exit $LASTEXITCODE\n",
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "PYTHON_EXECUTABLE": sys.executable,
        "PYTHONUTF8": "1",
        "SKILL_SYNC_SCRIPT": str(config_path.parent / "sync-skills.ps1"),
        "SKILL_SYNC_RACE_CONFIG": str(config_path),
        "SKILL_SYNC_FAILURE_MODE": failure_mode,
        "SKILL_SYNC_CONCURRENT_CONFIG": str(concurrent_config_path),
        "SKILL_SYNC_RACE_MARKER": str(injection_marker),
    }

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(wrapper_path),
            "-ApproveReviewedUpdates",
            "-ReviewedSkills",
            "example",
            "-ReviewRationale",
            "Reviewed the pinned source update in an isolated race fixture.",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )

    assert result.returncode != 0, result.stdout + result.stderr
    assert target_path.read_bytes() == original_target_bytes
    assert manifest_path.read_bytes() == original_manifest_bytes
    if failure_mode == "concurrent-replacement":
        assert injection_marker.exists(), "config edit was not injected in the intended window"
        assert "hash mismatch" in (result.stdout + result.stderr).lower()
        assert config_path.read_bytes() == concurrent_config_bytes
    elif failure_mode == "claim-hash-failure":
        assert "simulated claim hash failure" in result.stdout + result.stderr
        assert config_path.read_bytes() == original_config_bytes
        assert not list(config_path.parent.glob(".skill-sync-config-claim-*.tmp"))
    else:
        if failure_mode == "claim-hash-failure-blocked":
            assert "preserved at" in (result.stdout + result.stderr).lower()
            assert config_path.is_dir()
        else:
            assert injection_marker.exists()
            assert "preserved at" in (result.stdout + result.stderr).lower()
            assert config_path.read_bytes() == concurrent_config_bytes
        claim_files = list(config_path.parent.glob(".skill-sync-config-claim-*.tmp"))
        assert len(claim_files) == 1
        assert claim_files[0].read_bytes() == original_config_bytes
