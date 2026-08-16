from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.utils.database_backup as database_backup_module
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
            expected_destination_identity="approved-volume",
        )

    restore_root = tmp_path / "restore"
    DatabaseBackup.restore(
        result.manifest_path,
        destination,
        restore_root,
        operator_approved=True,
        expected_destination_identity="approved-volume",
        allow_canonical_restore=True,
    )
    assert (restore_root / "workspace.db").read_bytes() == source.read_bytes()
    assert not (tmp_path / "workspace.db").samefile(restore_root / "workspace.db")


def test_restore_uses_trusted_identity_and_never_manifest_identity(tmp_path: Path) -> None:
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
    metadata = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    metadata["destination_identity"] = "attacker-volume"
    result.manifest_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(DestinationIdentityError):
        DatabaseBackup.restore(
            result.manifest_path,
            destination,
            tmp_path / "restore",
            operator_approved=True,
            expected_destination_identity="attacker-volume",
            allow_canonical_restore=True,
        )

    DatabaseBackup.restore(
        result.manifest_path,
        destination,
        tmp_path / "restore",
        operator_approved=True,
        expected_destination_identity="approved-volume",
        allow_canonical_restore=True,
    )


def test_restore_rejects_existing_targets_until_separately_authorized(tmp_path: Path) -> None:
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
    restore_root = tmp_path / "restore"
    restore_root.mkdir()
    (restore_root / "workspace.db").write_bytes(b"existing")

    with pytest.raises(RestoreApprovalError, match="existing restore target"):
        DatabaseBackup.restore(
            result.manifest_path,
            destination,
            restore_root,
            operator_approved=True,
            expected_destination_identity="approved-volume",
            allow_canonical_restore=True,
        )
    with pytest.raises(RestoreApprovalError, match="overwrite authorization"):
        DatabaseBackup.restore(
            result.manifest_path,
            destination,
            restore_root,
            operator_approved=True,
            expected_destination_identity="approved-volume",
            overwrite=True,
            allow_canonical_restore=True,
        )

    DatabaseBackup.restore(
        result.manifest_path,
        destination,
        restore_root,
        operator_approved=True,
        expected_destination_identity="approved-volume",
        overwrite=True,
        overwrite_operator_approved=True,
        allow_canonical_restore=True,
    )
    assert (restore_root / "workspace.db").read_bytes() == source.read_bytes()


def test_canonical_restore_is_prohibited_by_default(tmp_path: Path) -> None:
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

    with pytest.raises(RestoreApprovalError, match="canonical"):
        DatabaseBackup.restore(
            result.manifest_path,
            destination,
            tmp_path / "restore",
            operator_approved=True,
            expected_destination_identity="approved-volume",
        )


def test_restore_audit_contains_only_redacted_locators(tmp_path: Path) -> None:
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
    DatabaseBackup.restore(
        result.manifest_path,
        destination,
        tmp_path / "restore",
        operator_approved=True,
        expected_destination_identity="approved-volume",
        allow_canonical_restore=True,
    )

    audit = (destination.path() / "backup-audit.jsonl").read_text(encoding="utf-8")
    assert str(result.manifest_path) not in audit
    assert str(tmp_path / "restore") not in audit
    assert '"manifest_locator": "generations/' in audit
    assert '"target_id": "restore-' in audit


def test_periodic_validation_uses_real_validator_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    calls: list[Path] = []
    monkeypatch.setattr(
        database_backup_module,
        "_validate_restored_databases",
        lambda restore_root, metadata: calls.append(restore_root),
    )

    assert validate_recent_backups(destination, "approved-volume") == [result.manifest_path]
    assert calls


def test_discovery_fails_closed_for_unregistered_database(tmp_path: Path) -> None:
    (tmp_path / "workspace.db").touch()

    with pytest.raises(ValueError, match="unregistered"):
        discover_and_validate_manifest(
            _manifest(path="other.db"), [tmp_path]
        )


def test_approved_project_inventory_entry_uses_discovery_for_generic_lifecycle(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "music"
    (project_root / "src" / "data").mkdir(parents=True)
    source = project_root / "src" / "data" / "future_store.sqlite3"
    source.write_bytes(b"encrypted-db-bytes")
    manifest = _manifest(path="music/future-store")
    manifest["databases"][0]["discovery"] = {
        "project": "music",
        "basename": "future_store.sqlite3",
    }
    destination = LocalVolumeDestination(tmp_path / "external", "approved-volume", provision=True)

    result = DatabaseBackup(
        manifest=manifest,
        source_root={"music": project_root},
        destination=destination,
        expected_destination_identity="approved-volume",
        now=lambda: "2026-08-16T12:00:00Z",
    ).run()

    assert (result.manifest_path.parent / "music/future-store").read_bytes() == source.read_bytes()


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

    assert validate_recent_backups(destination, "approved-volume") == [result.manifest_path]
    assert '"event": "validation"' in (destination.path() / "backup-audit.jsonl").read_text(encoding="utf-8")


def test_recent_validation_restores_isolated_generation_and_validates_metadata(
    tmp_path: Path,
) -> None:
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
    observed: list[Path] = []

    def validate_restored_metadata(restore_root: Path, metadata: dict[str, object]) -> None:
        observed.append(restore_root)
        assert metadata["generation"] == result.generation
        assert (restore_root / "workspace.db").read_bytes() == source.read_bytes()

    assert validate_recent_backups(
        destination,
        "approved-volume",
        restore_validator=validate_restored_metadata,
    ) == [result.manifest_path]
    assert observed
    assert observed[0] != source.parent
    assert source.read_bytes() == b"encrypted-db-bytes"