from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.database_backup import (
    BackupDestination,
    DatabaseBackup,
    DestinationIdentityError,
    LocalVolumeDestination,
    RestoreApprovalError,
    discover_and_validate_manifest,
    validate_backup,
    validate_recent_backups,
)


class UnverifiedDestination(BackupDestination):
    def resolve_identity(self) -> str:
        return "unverified-volume"

    def is_verified(self, expected_identity: str) -> bool:
        return False

    def path(self) -> Path:
        return Path("unused")


def test_backup_refuses_unverified_destination_before_copying(tmp_path: Path) -> None:
    source = tmp_path / "workspace.db"
    source.write_bytes(b"encrypted-db-bytes")

    with pytest.raises(DestinationIdentityError):
        DatabaseBackup(
            manifest={
                "databases": [
                    {
                        "id": "workspace",
                        "path": "workspace.db",
                        "backup_allowed": True,
                    }
                ]
            },
            source_root=tmp_path,
            destination=UnverifiedDestination(),
            expected_destination_identity="approved-volume",
        ).run()

    assert list(tmp_path.glob("**/*.backup")) == []


def _manifest(path: str = "workspace.db") -> dict[str, object]:
    return {
        "schema_version": 1,
        "fr": "FR-20260816-workspace-local-database-backup",
        "policy_status": "reviewed",
        "purpose": "Test backup manifest",
        "content_boundary": "Encrypted database files only",
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
                "id": "workspace",
                "path": path,
                "backup_allowed": True,
                "classification": "canonical",
                        "reason": "Test database",
            }
        ],
        "exclusions": [],
        "not_implemented": [],
        "separate_todos": [],
    }


def test_backup_writes_hashed_manifest_and_prunes_old_generations(tmp_path: Path) -> None:
    source = tmp_path / "workspace.db"
    source.write_bytes(b"encrypted-db-bytes")
    destination_root = tmp_path / "external"
    destination = LocalVolumeDestination(destination_root, "approved-volume", provision=True)
    for index in range(31):
        generation = destination_root / "generations" / f"old-{index:02d}"
        generation.mkdir(parents=True)
        (generation / "manifest.json").write_text("{}", encoding="utf-8")

    result = DatabaseBackup(
        manifest=_manifest(),
        source_root=tmp_path,
        destination=destination,
        expected_destination_identity="approved-volume",
        now=lambda: "2026-08-16T12:00:00Z",
    ).run()

    assert result.manifest_path.is_file()
    assert (destination_root / "generations" / result.generation / "workspace.db").read_bytes() == source.read_bytes()
    assert len(list((destination_root / "generations").iterdir())) == 30
    assert validate_backup(result.manifest_path) is True


def test_restore_requires_approval_and_isolated_target(tmp_path: Path) -> None:
    source = tmp_path / "workspace.db"
    source.write_bytes(b"encrypted-db-bytes")
    destination = LocalVolumeDestination(tmp_path / "external", "approved-volume", provision=True)
    result = DatabaseBackup(
        manifest=_manifest(),
        source_root=tmp_path,
        destination=destination,
        expected_destination_identity="approved-volume",
        now=lambda: "2026-08-16T12:00:00Z",
    ).run()

    with pytest.raises(RestoreApprovalError):
        DatabaseBackup.restore(
            result.manifest_path,
            destination,
            tmp_path / "restore",
            operator_approved=False,
        )

    restore_root = tmp_path / "restore"
    DatabaseBackup.restore(
        result.manifest_path,
        destination,
        restore_root,
        operator_approved=True,
    )
    assert (restore_root / "workspace.db").read_bytes() == source.read_bytes()
    assert not (tmp_path / "workspace.db").samefile(restore_root / "workspace.db")


def test_discovery_fails_closed_for_unregistered_database(tmp_path: Path) -> None:
    (tmp_path / "workspace.db").touch()

    with pytest.raises(ValueError, match="unregistered"):
        discover_and_validate_manifest(
            _manifest(path="other.db"), [tmp_path]
        )


def test_periodic_validation_hook_audits_retained_generations(tmp_path: Path) -> None:
    source = tmp_path / "workspace.db"
    source.write_bytes(b"encrypted-db-bytes")
    destination = LocalVolumeDestination(tmp_path / "external", "approved-volume", provision=True)
    result = DatabaseBackup(
        manifest=_manifest(),
        source_root=tmp_path,
        destination=destination,
        expected_destination_identity="approved-volume",
        now=lambda: "2026-08-16T12:00:00Z",
    ).run()

    assert validate_recent_backups(destination) == [result.manifest_path]
    assert '"event": "validation"' in (destination.path() / "backup-audit.jsonl").read_text(encoding="utf-8")