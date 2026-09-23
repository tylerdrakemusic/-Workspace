from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import tools.run_database_backup as runner
from src.utils.database_backup import DestinationIdentityError


APPROVED_VOLUME_ID = (
    "volume-guid={433dc510-613d-11f1-b66e-9cb6d0f5b996};volume-serial=0x76e8cacf"
)


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


def test_destination_requires_marker_and_physical_volume_identity(tmp_path: Path) -> None:
    from src.utils.database_backup import LocalVolumeDestination

    volume = tmp_path / "volume"
    destination = LocalVolumeDestination(
        volume,
        APPROVED_VOLUME_ID,
        provision=True,
        volume_identity_reader=lambda _: APPROVED_VOLUME_ID,
    )

    assert destination.is_verified(APPROVED_VOLUME_ID) is True

    physical_mismatch = LocalVolumeDestination(
        volume,
        APPROVED_VOLUME_ID,
        volume_identity_reader=lambda _: "volume-guid={different};volume-serial=0x1",
    )
    assert physical_mismatch.is_verified(APPROVED_VOLUME_ID) is False


@pytest.mark.parametrize("marker", [b"\x00" * len(APPROVED_VOLUME_ID), b"not-a-volume-id\x00"])
def test_destination_rejects_malformed_or_zero_filled_marker(
    tmp_path: Path, marker: bytes
) -> None:
    from src.utils.database_backup import LocalVolumeDestination

    volume = tmp_path / "volume"
    volume.mkdir()
    (volume / ".backup-volume-identity").write_bytes(marker)
    destination = LocalVolumeDestination(
        volume,
        APPROVED_VOLUME_ID,
        volume_identity_reader=lambda _: APPROVED_VOLUME_ID,
    )

    assert destination.resolve_identity() == ""
    assert destination.is_verified(APPROVED_VOLUME_ID) is False


def test_volume_guid_normalization_uses_canonical_guid_form() -> None:
    from src.utils.database_backup import _normalize_volume_guid

    assert _normalize_volume_guid(
        "\\\\?\\Volume{433dc510-613d-11f1-b66e-9cb6d0f5b996}\\"
    ) == (
        "{433dc510-613d-11f1-b66e-9cb6d0f5b996}"
    )


def test_powershell_launcher_forwards_verified_volume_identity_to_python() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "run_database_backup.ps1"
    ).read_text(encoding="utf-8")

    assert "'--volume-identity', $env:WORKSPACE_BACKUP_VOLUME_ID" in script


@pytest.mark.skipif(os.name != "nt", reason="PowerShell launcher requires Windows")
def test_launcher_exports_machine_environment_configuration_to_runner(
    tmp_path: Path,
) -> None:
    tools = Path(__file__).resolve().parents[1] / "tools"
    launcher = (tools / "run_database_backup.ps1").read_text(encoding="utf-8")
    volume = tmp_path / "volume"
    volume.mkdir()
    (volume / ".backup-volume-identity").write_text("machine-volume-id\n", encoding="utf-8")
    output = tmp_path / "runner-output.json"
    (tmp_path / "approved-manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "run_database_backup.py").write_text(
        "import json, os, sys\n"
        "Path = __import__('pathlib').Path\n"
        "Path(os.environ['BACKUP_TEST_OUTPUT']).write_text(json.dumps({\n"
        "    'volume': os.environ.get('WORKSPACE_BACKUP_VOLUME'),\n"
        "    'volume_id': os.environ.get('WORKSPACE_BACKUP_VOLUME_ID'),\n"
        "    'manifest_key': os.environ.get('WORKSPACE_BACKUP_MANIFEST_KEY'),\n"
        "    'arguments': sys.argv[1:],\n"
        "}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    launcher = launcher.replace(
        "[Environment]::GetEnvironmentVariable($name, 'Machine')",
        "Get-TestEnvironmentVariable $name 'Machine'",
    ).replace(
        "[IO.Path]::GetFullPath('E:\\WorkspaceBackup')",
        f"[IO.Path]::GetFullPath('{volume}')",
    )
    test_environment_provider = (
        "function Get-TestEnvironmentVariable([string] $Name, [string] $Target) {\n"
        "    if ($Target -eq 'Machine') {\n"
        "        return @{\n"
        "            WORKSPACE_BACKUP_VOLUME = $env:BACKUP_TEST_VOLUME\n"
        "            WORKSPACE_BACKUP_VOLUME_ID = 'machine-volume-id'\n"
        "            WORKSPACE_BACKUP_MANIFEST_KEY = 'machine-manifest-key'\n"
        "        }[$Name]\n"
        "    }\n"
        "    return [Environment]::GetEnvironmentVariable($Name, $Target)\n"
        "}\n"
    )
    launcher = launcher.replace("Set-StrictMode -Version Latest", test_environment_provider + "Set-StrictMode -Version Latest", 1)
    launcher_path = tmp_path / "run_database_backup.ps1"
    launcher_path.write_text(launcher, encoding="utf-8")

    environment = os.environ.copy()
    for name in (
        "WORKSPACE_BACKUP_VOLUME",
        "WORKSPACE_BACKUP_VOLUME_ID",
        "WORKSPACE_BACKUP_MANIFEST_KEY",
    ):
        environment.pop(name, None)
    environment["BACKUP_TEST_VOLUME"] = str(volume)
    environment["BACKUP_TEST_OUTPUT"] = str(output)
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("Windows PowerShell is unavailable on this runner")
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher_path),
            "-Python",
            sys.executable,
            "-Manifest",
            str(tmp_path / "approved-manifest.json"),
            "-SourceRoot",
            str(tmp_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    consumed = json.loads(output.read_text(encoding="utf-8"))
    assert consumed["volume"] == str(volume)
    assert consumed["volume_id"] == "machine-volume-id"
    assert consumed["manifest_key"] == "machine-manifest-key"
    assert "machine-manifest-key" not in consumed["arguments"]


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


def test_provisioning_replaces_marker_only_with_explicit_authorization(
    tmp_path: Path,
) -> None:
    from tools.provision_backup_volume import provision_volume

    volume = tmp_path / "volume"
    volume.mkdir()
    marker = volume / ".backup-volume-identity"
    marker.write_text("original-volume\n", encoding="utf-8")

    provision_volume(volume, "replacement-volume", replace_existing=True)

    assert marker.read_text(encoding="utf-8") == "replacement-volume\n"


def test_provisioning_cli_runs_from_repository_root(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "tools" / "provision_backup_volume.py"
    volume = tmp_path / "volume"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--volume-root",
            str(volume),
            "--volume-identity",
            "approved-volume",
        ],
        cwd=script.parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (volume / ".backup-volume-identity").read_text(encoding="utf-8") == (
        "approved-volume\n"
    )


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
            ("∞Life", workspace_root.parent / "∞Life"),
            ("❤Music", workspace_root.parent / "❤Music"),
            ("⟨ψ⟩Quantum", workspace_root.parent / "⟨ψ⟩Quantum"),
            ("👁AI-Manifest", workspace_root.parent / "👁AI-Manifest"),
            ("⊕Workspace", workspace_root),
            ("ΣCapital", workspace_root.parent / "ΣCapital"),
        )
    )
    assert expected_roots in arguments


def test_manifest_explicitly_authorizes_sigmacapital_backup() -> None:
    manifest_path = Path(__file__).parents[1] / "src" / "config" / "database_backup_scope.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(item for item in manifest["databases"] if item["id"] == "capital-sigmacapital")

    assert set(entry) == {
        "id",
        "path",
        "discovery",
        "classification",
        "backup_allowed",
        "reason",
        "encryption",
        "key_env",
    }
    assert entry["id"] == "capital-sigmacapital"
    assert entry["path"] == "capital/financial-store"
    assert entry["discovery"] == {"project": "capital", "basename": "sigmacapital.db"}
    assert entry["classification"] == "approval-required"
    assert entry["backup_allowed"] is True
    assert "explicitly authorized" in entry["reason"]
    assert entry["encryption"] == "sqlcipher"
    assert entry["key_env"] == "SIGMACAPITAL_DB_KEY"
    assert not set(entry) & {
        "account_number",
        "account_numbers",
        "secret",
        "token",
        "password",
        "database_contents",
        "financial_records",
    }


def test_powershell_registration_includes_the_authorized_sigmacapital_root() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "register_database_backup_task.ps1"
    ).read_text(encoding="utf-8")

    assert "$CapitalLabel = [char]0x03A3 + 'Capital'" in script
    assert "$CapitalLabel" in script.split("$ApprovedProjectLabels", 1)[1].split("if ($ApprovedProject", 1)[0]
    assert "if ($ApprovedProject -eq $CapitalLabel)" in script
    capital_root = "($CapitalLabel + \"=\" + (Join-Path (Split-Path -Parent $WorkspaceRoot) $CapitalLabel))"
    assert script.count(capital_root) == 2


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


def test_scheduler_spec_can_select_only_the_approved_life_root(tmp_path: Path) -> None:
    from tools.register_database_backup_task import build_task_spec

    canonical_workspace = tmp_path / "workspace"
    active_worktree = canonical_workspace / ".worktrees" / "feature-backup"
    spec = build_task_spec(
        active_worktree,
        Path("C:/G/python.exe"),
        approved_projects=("∞Life",),
    )
    project_root_argument = spec.arguments[spec.arguments.index("-ProjectRoot") + 1]

    assert project_root_argument == f"∞Life={canonical_workspace.parent / '∞Life'}"
    assert ".worktrees" not in project_root_argument


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

    assert "$Python = [Environment]::GetEnvironmentVariable('WORKSPACE_BACKUP_PYTHON', 'Process')" in registration
    assert "$Python = 'C:\\G\\python.exe'" not in registration
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
    assert "if ($ApprovedProject -eq $MusicLabel)" in script
    assert "Join-Path (Split-Path -Parent $WorkspaceRoot)" in script
    assert "$ApprovedProject" not in script.split("$action", 1)[1]
    assert "WORKSPACE_BACKUP_MANIFEST_KEY" not in script.split(
        "$action", 1
    )[1].split("$trigger", 1)[0]


def test_registration_script_is_ascii_source_and_parses_with_windows_powershell() -> None:
    if os.name != "nt":
        pytest.skip("Windows PowerShell is unavailable on this platform")
    script_path = Path(__file__).resolve().parents[1] / "tools" / "register_database_backup_task.ps1"
    script = script_path.read_bytes().decode("ascii")

    assert "[char]0x2764" in script
    assert "[char]0x27E8" in script
    assert "[char]0xD83D" in script
    assert "[char]0xDC41" in script

    powershell = shutil.which("powershell.exe")
    if powershell is None:
        return
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"[void][scriptblock]::Create((Get-Content -Raw -LiteralPath '{script_path}'))",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr

def test_powershell_registration_uses_canonical_workspace_launcher() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "register_database_backup_task.ps1"
    ).read_text(encoding="utf-8")

    assert "$Launcher = Join-Path $WorkspaceRoot 'tools\\run_database_backup.ps1'" in script


def test_scheduler_action_is_secret_free_and_uses_one_normalized_project_root_argument() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "register_database_backup_task.ps1"
    ).read_text(encoding="utf-8")

    action = script.split("$action =", 1)[1].split("$trigger =", 1)[0]
    assert "run_database_backup.ps1" not in action
    assert '-File `"$Launcher`"' in action
    assert "$ProjectRootArguments" in action
    assert action.count("-ProjectRoot") == 0
    assert "WORKSPACE_BACKUP_MANIFEST_KEY" not in action
    assert "-WorkingDirectory" not in action


def test_scheduler_registration_hydrates_user_scope_environment_for_action() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "register_database_backup_task.ps1"
    ).read_text(encoding="utf-8")

    assert 'Set-Item -Path "Env:$name" -Value $value' in script