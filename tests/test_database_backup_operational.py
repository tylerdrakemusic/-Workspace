from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.run_database_backup as runner
from src.utils.database_backup import DestinationIdentityError


def _manifest(*paths: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "fr": "FR-20260816-workspace-local-database-backup-operational-pilot",
        "policy_status": "reviewed",
        "purpose": "Operational backup test manifest.",
        "content_boundary": "Approved non-sensitive database files only.",
        "classifications": [
            "canonical",
            "coordination",
            "derived",
            "temporary",
            "legacy",
            "unknown",
            "approval-required",
        ],
        "databases": [
            {
                "id": path.replace(".", "-").replace("/", "-"),
                "path": path,
                "classification": "coordination",
                "backup_allowed": True,
                "reason": "Approved test entry.",
            }
            for path in paths
        ],
        "exclusions": [],
        "not_implemented": [],
        "separate_todos": [],
    }


def _write_manifest(path: Path, *entries: str) -> None:
    path.write_text(json.dumps(_manifest(*entries)), encoding="utf-8")


def test_runner_fails_closed_when_destination_is_missing(tmp_path: Path) -> None:
    run_backup = getattr(runner, "run_backup", None)
    assert callable(run_backup)

    with pytest.raises(RuntimeError, match="destination"):
        run_backup(
            manifest_path=tmp_path / "approved-manifest.json",
            source_root=tmp_path,
            volume_root=tmp_path / "missing-volume",
            volume_identity="approved-volume",
        )


def test_runner_fails_closed_when_destination_marker_mismatches(tmp_path: Path) -> None:
    source = tmp_path / "workspace.db"
    source.write_bytes(b"workspace-bytes")
    manifest_path = tmp_path / "approved-manifest.json"
    _write_manifest(manifest_path, "workspace.db")
    volume = tmp_path / "volume"
    volume.mkdir()
    (volume / ".backup-volume-identity").write_text("different-volume\n", encoding="utf-8")

    with pytest.raises(DestinationIdentityError, match="identity"):
        runner.run_backup(manifest_path, tmp_path, volume, "approved-volume")


def test_runner_copies_every_backup_allowed_manifest_entry_byte_for_byte(
    tmp_path: Path,
) -> None:
    first = tmp_path / "workspace.db"
    second = tmp_path / "coordination.sqlite3"
    first.write_bytes(b"first-db-bytes")
    second.write_bytes(b"second-db-bytes")
    manifest_path = tmp_path / "approved-manifest.json"
    _write_manifest(manifest_path, "workspace.db", "coordination.sqlite3")
    volume = tmp_path / "volume"
    volume.mkdir()
    (volume / ".backup-volume-identity").write_text("approved-volume\n", encoding="utf-8")

    result = runner.run_backup(manifest_path, tmp_path, volume, "approved-volume")

    assert (result.manifest_path.parent / "workspace.db").read_bytes() == first.read_bytes()
    assert (
        result.manifest_path.parent / "coordination.sqlite3"
    ).read_bytes() == second.read_bytes()


def test_runner_accepts_workspace_qualified_approved_manifest_entry(tmp_path: Path) -> None:
    source = tmp_path / "⊕Workspace" / "src" / "data" / "workspace.db"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"approved-workspace-db")
    manifest_path = tmp_path / "approved-manifest.json"
    _write_manifest(manifest_path, "⊕Workspace/src/data/workspace.db")
    volume = tmp_path / "volume"
    volume.mkdir()
    (volume / ".backup-volume-identity").write_text("approved-volume\n", encoding="utf-8")

    result = runner.run_backup(
        manifest_path, tmp_path, volume, "approved-volume"
    )

    assert (
        result.manifest_path.parent / "⊕Workspace/src/data/workspace.db"
    ).read_bytes() == source.read_bytes()


def test_runner_executes_manifest_backup_with_repeated_labeled_project_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    music_root = tmp_path / "❤Music"
    workspace_root = tmp_path / "⊕Workspace"
    music_source = music_root / "src" / "data" / "heartmusic.db"
    workspace_source = workspace_root / "src" / "data" / "workspace.db"
    music_source.parent.mkdir(parents=True)
    workspace_source.parent.mkdir(parents=True)
    music_source.write_bytes(b"music-db-bytes")
    workspace_source.write_bytes(b"workspace-db-bytes")
    manifest_path = tmp_path / "approved-manifest.json"
    _write_manifest(
        manifest_path,
        "❤Music/src/data/heartmusic.db",
        "⊕Workspace/src/data/workspace.db",
    )
    volume = tmp_path / "volume"
    volume.mkdir()
    (volume / ".backup-volume-identity").write_text("approved-volume\n", encoding="utf-8")
    monkeypatch.setenv("WORKSPACE_BACKUP_MANIFEST_KEY", "test-manifest-key")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_database_backup.py",
            "--manifest",
            str(manifest_path),
            "--project-root",
            f"❤Music={music_root}",
            "--project-root",
            f"⊕Workspace={workspace_root}",
            "--volume-root",
            str(volume),
            "--volume-identity",
            "approved-volume",
        ],
    )

    assert runner.main() == 0
    generation = next((volume / "generations").iterdir())
    assert (generation / "❤Music/src/data/heartmusic.db").read_bytes() == b"music-db-bytes"
    assert (generation / "⊕Workspace/src/data/workspace.db").read_bytes() == b"workspace-db-bytes"


def test_provisioning_refuses_to_overwrite_mismatched_marker(tmp_path: Path) -> None:
    from tools.provision_backup_volume import provision_volume

    volume = tmp_path / "volume"
    volume.mkdir()
    marker = volume / ".backup-volume-identity"
    marker.write_text("original-volume\n", encoding="utf-8")

    with pytest.raises(DestinationIdentityError, match="mismatch"):
        provision_volume(volume, "replacement-volume")

    assert marker.read_text(encoding="utf-8") == "original-volume\n"


def test_scheduler_spec_is_daily_at_two_without_secret_arguments() -> None:
    from tools.register_database_backup_task import build_task_spec

    spec = build_task_spec(Path("F:/workspace"), Path("C:/G/python.exe"))

    assert spec.trigger == "02:00"
    assert spec.frequency == "DAILY"
    assert "WORKSPACE_BACKUP_VOLUME" in spec.environment_names
    assert "WORKSPACE_BACKUP_VOLUME_ID" in spec.environment_names
    assert "WORKSPACE_BACKUP_MANIFEST_KEY" in spec.environment_names
    assert "WORKSPACE_BACKUP_MANIFEST_KEY" not in " ".join(spec.arguments)


def test_scheduler_spec_uses_only_explicit_manifest_aligned_project_roots() -> None:
    from tools.register_database_backup_task import build_task_spec

    workspace_root = Path(r"F:\⊕Workspace")
    spec = build_task_spec(workspace_root, Path(r"C:\G\python.exe"))
    arguments = " ".join(spec.arguments)

    assert "-SourceRoot" not in arguments
    assert "-ProjectRoot" in arguments
    expected_roots = ",".join(
        f"{label}={root}"
        for label, root in (
            ("❤Music", workspace_root.parent / "❤Music"),
            ("⟨ψ⟩Quantum", workspace_root.parent / "⟨ψ⟩Quantum"),
            ("👁AI-Manifest", workspace_root.parent / "👁AI-Manifest"),
            ("⊕Workspace", workspace_root),
        )
    )
    assert expected_roots in arguments
    assert "∞Life" not in arguments
    assert "ΣCapital" not in arguments


def test_scheduler_spec_resolves_canonical_roots_from_an_active_worktree(
    tmp_path: Path,
) -> None:
    from tools.register_database_backup_task import build_task_spec

    canonical_workspace = tmp_path / "workspace"
    active_worktree = canonical_workspace / ".worktrees" / "feature-backup"
    spec = build_task_spec(active_worktree, Path(r"C:\G\python.exe"))
    arguments = " ".join(spec.arguments)

    assert f"⊕Workspace={canonical_workspace}" in arguments
    assert f"⟨ψ⟩Quantum={canonical_workspace.parent / '⟨ψ⟩Quantum'}" in arguments
    assert ".worktrees" not in arguments


def test_scheduler_spec_music_selector_registers_only_canonical_music_root(
    tmp_path: Path,
) -> None:
    from tools.register_database_backup_task import build_task_spec

    canonical_workspace = tmp_path / "workspace"
    active_worktree = canonical_workspace / ".worktrees" / "feature-backup"
    spec = build_task_spec(
        active_worktree,
        Path("C:/G/python.exe"),
        approved_projects=("❤Music",),
    )
    arguments = list(spec.arguments)
    project_root_argument = arguments[arguments.index("-ProjectRoot") + 1]

    assert project_root_argument == f"❤Music={canonical_workspace.parent / '❤Music'}"
    assert ".worktrees" not in project_root_argument
    assert all(
        excluded not in project_root_argument
        for excluded in ("∞Life", "⟨ψ⟩Quantum", "👁AI-Manifest", "⊕Workspace", "ΣCapital")
    )


def test_scheduler_spec_preserves_non_worktree_root_on_foreign_platform() -> None:
    from tools.register_database_backup_task import build_task_spec

    configured_root = Path("/ci/workspace")
    spec = build_task_spec(configured_root, Path("/ci/python"))

    assert str(configured_root / "tools" / "run_database_backup.ps1") in spec.arguments
    assert f"⊕Workspace={configured_root}" in " ".join(spec.arguments)


def test_scheduler_registration_renders_the_canonical_runner_command() -> None:
    from tools.register_database_backup_task import build_task_spec

    workspace_root = Path(__file__).parents[1]
    spec = build_task_spec(workspace_root, Path(r"C:\G\python.exe"))
    registration = (
        workspace_root / "tools" / "register_database_backup_task.ps1"
    ).read_text(encoding="utf-8")

    assert "$Python = 'C:\\G\\python.exe'" in registration
    assert '-File `"$Launcher`" -Python `"$Python`"' in registration
    assert f'-Manifest `"$Manifest`" $ProjectRootArguments' in registration
    assert "$SourceRoot" not in registration
    assert "$ProjectRoots" in registration
    assert spec.arguments[0] in registration
    assert spec.arguments[1] in registration
    assert spec.arguments[2] in registration
    assert "WORKSPACE_BACKUP_MANIFEST_KEY" not in registration.split(
        "$action", 1
    )[1].split("$trigger", 1)[0]


def test_music_registration_selector_is_explicit_and_secret_free() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "register_database_backup_task.ps1"
    ).read_text(encoding="utf-8")

    assert "[string]$ApprovedProject = $null" in script
    assert "if ($ApprovedProject -eq '❤Music')" in script
    assert "Join-Path (Split-Path -Parent $WorkspaceRoot)" in script
    assert "$ApprovedProject" not in script.split("$action", 1)[1]
    assert "WORKSPACE_BACKUP_MANIFEST_KEY" not in script.split(
        "$action", 1
    )[1].split("$trigger", 1)[0]

def test_powershell_registration_uses_canonical_workspace_launcher() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "register_database_backup_task.ps1"
    ).read_text(encoding="utf-8")

    assert "$Launcher = Join-Path $WorkspaceRoot 'tools\\run_database_backup.ps1'" in script