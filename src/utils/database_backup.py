from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any, Callable, Mapping, Sequence

from src.utils.database_backup_scope import discover_databases, validate_manifest


class BackupError(RuntimeError):
    """Base error for local database backup operations."""


class DestinationIdentityError(BackupError):
    """Raised when the requested destination cannot be positively identified."""


class RestoreApprovalError(BackupError):
    """Raised when an isolated restore was not explicitly approved."""


class BackupDestination(ABC):
    """Provider-neutral destination contract for local backup volumes."""

    @abstractmethod
    def resolve_identity(self) -> str:
        """Return the stable identity observed for the destination."""

    @abstractmethod
    def is_verified(self, expected_identity: str) -> bool:
        """Return whether the destination matches the approved identity."""

    @abstractmethod
    def path(self) -> Path:
        """Return the mounted destination path."""


class LocalVolumeDestination(BackupDestination):
    """Filesystem adapter for a pre-authorized external volume."""

    def __init__(self, root: Path, identity: str, provision: bool = False) -> None:
        self._root = Path(root)
        self._identity_file = self._root / ".backup-volume-identity"
        if provision:
            self._root.mkdir(parents=True, exist_ok=True)
            if self._identity_file.exists():
                current = self._identity_file.read_text(encoding="utf-8").strip()
                if current != identity:
                    raise DestinationIdentityError("volume identity marker mismatch")
            else:
                self._identity_file.write_text(identity + "\n", encoding="utf-8")

    def resolve_identity(self) -> str:
        try:
            return self._identity_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def is_verified(self, expected_identity: str) -> bool:
        return self.resolve_identity() == expected_identity

    def path(self) -> Path:
        return self._root


@dataclass(frozen=True)
class BackupResult:
    """Summary of a completed backup generation."""

    generation: str
    manifest_path: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def validate_backup(manifest_path: Path) -> bool:
    """Verify every file listed by a backup manifest."""
    metadata = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    generation_root = Path(manifest_path).parent
    for entry in metadata.get("files", []):
        path = generation_root / entry["relative_path"]
        if not path.is_file() or _sha256(path) != entry["sha256"]:
            raise BackupError(f"backup hash validation failed: {path}")
    return True


def validate_recent_backups(
    destination: BackupDestination, limit: int = 30
) -> list[Path]:
    """Validate retained generations and append a validation audit record."""
    if limit < 1:
        raise ValueError("validation limit must be positive")
    generations_root = destination.path() / "generations"
    manifests = sorted(
        (path / "manifest.json" for path in generations_root.iterdir() if path.is_dir()),
        key=lambda path: path.parent.stat().st_mtime,
        reverse=True,
    )[:limit]
    for manifest_path in manifests:
        validate_backup(manifest_path)
    with (destination.path() / "backup-audit.jsonl").open("a", encoding="utf-8") as audit:
        audit.write(json.dumps({"event": "validation", "count": len(manifests)}) + "\n")
    return manifests


def discover_and_validate_manifest(
    manifest: dict[str, Any], roots: Sequence[Path] | Mapping[str, Path]
) -> list[dict[str, str]]:
    """Discover databases and reject any path absent from the manifest."""
    discovered = discover_databases(roots)
    validate_manifest(manifest, {entry["path"] for entry in discovered})
    return discovered


class DatabaseBackup:
    """Execute manifest-driven backups after verifying the destination identity."""

    def __init__(
        self,
        manifest: Mapping[str, Any],
        source_root: Path,
        destination: BackupDestination,
        expected_destination_identity: str,
        now: Callable[[], str] | None = None,
        retention: int = 30,
    ) -> None:
        self._manifest = manifest
        self._source_root = Path(source_root)
        self._destination = destination
        self._expected_destination_identity = expected_destination_identity
        self._now = now or (lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        if retention < 1:
            raise ValueError("retention must be positive")
        self._retention = retention

    def run(self) -> BackupResult:
        """Run the backup after the destination identity gate passes."""
        if not self._expected_destination_identity.strip():
            raise DestinationIdentityError("approved destination identity is required")
        if not self._destination.is_verified(self._expected_destination_identity):
            observed = self._destination.resolve_identity()
            raise DestinationIdentityError(
                "destination identity is not verified: "
                f"expected {self._expected_destination_identity!r}, observed {observed!r}"
            )
        entries = self._manifest.get("databases")
        if not isinstance(entries, list):
            raise BackupError("manifest databases must be a list")
        timestamp = self._now()
        generation = timestamp.replace("-", "").replace(":", "").replace("+", "").replace("Z", "Z")
        generation_root = self._destination.path() / "generations" / generation
        if generation_root.exists():
            raise BackupError(f"backup generation already exists: {generation}")
        temporary_root = generation_root.with_name(generation_root.name + ".tmp")
        temporary_root.mkdir(parents=True)
        files: list[dict[str, str]] = []
        try:
            for entry in entries:
                if not entry.get("backup_allowed", False):
                    continue
                relative_path = str(entry["path"])
                source = self._source_root / Path(relative_path)
                if not source.is_file():
                    raise BackupError(f"manifest source is missing: {source}")
                target = temporary_root / Path(relative_path)
                _atomic_copy(source, target)
                files.append({"relative_path": relative_path, "sha256": _sha256(target)})
            metadata = {
                "schema_version": 1,
                "generation": generation,
                "created_at": timestamp,
                "destination_identity": self._expected_destination_identity,
                "files": files,
            }
            manifest_path = temporary_root / "manifest.json"
            manifest_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(temporary_root, generation_root)
        finally:
            if temporary_root.exists():
                shutil.rmtree(temporary_root)
        self._prune_generations()
        final_manifest = generation_root / "manifest.json"
        audit_path = self._destination.path() / "backup-audit.jsonl"
        with audit_path.open("a", encoding="utf-8") as audit:
            audit.write(json.dumps({"event": "backup", "generation": generation, "manifest": str(final_manifest)}) + "\n")
        return BackupResult(generation=generation, manifest_path=final_manifest)

    def _prune_generations(self) -> None:
        generations_root = self._destination.path() / "generations"
        generations = sorted(
            (path for path in generations_root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for obsolete in generations[self._retention :]:
            shutil.rmtree(obsolete)

    @staticmethod
    def restore(
        manifest_path: Path,
        destination: BackupDestination,
        restore_root: Path,
        operator_approved: bool,
    ) -> None:
        """Restore verified files only into a separate operator-approved directory."""
        if not operator_approved:
            raise RestoreApprovalError("restore requires explicit operator approval")
        if Path(restore_root).resolve() == Path.cwd().resolve():
            raise RestoreApprovalError("restore target must be isolated")
        if not destination.is_verified(json.loads(Path(manifest_path).read_text(encoding="utf-8")).get("destination_identity", "")):
            raise DestinationIdentityError("restore destination identity is not verified")
        validate_backup(manifest_path)
        metadata = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        generation_root = Path(manifest_path).parent
        restore_root = Path(restore_root)
        restore_root.mkdir(parents=True, exist_ok=True)
        for entry in metadata["files"]:
            _atomic_copy(generation_root / entry["relative_path"], restore_root / entry["relative_path"])
        with (destination.path() / "backup-audit.jsonl").open("a", encoding="utf-8") as audit:
            audit.write(json.dumps({"event": "restore", "manifest": str(manifest_path), "target": str(restore_root)}) + "\n")