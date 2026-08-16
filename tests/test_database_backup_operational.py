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