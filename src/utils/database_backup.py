from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable, Mapping, Sequence

from src.utils.database_backup_scope import (
    DISPLAY_PROJECT_KEYS,
    discover_databases,
    validate_manifest,
)


MANIFEST_KEY_ENV = "WORKSPACE_BACKUP_MANIFEST_KEY"
SQLCIPHER_RESTORE_PRAGMAS = (
    "PRAGMA cipher_page_size=4096",
    "PRAGMA kdf_iter=256000",
    "PRAGMA cipher_hmac_algorithm=HMAC_SHA512",
)


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


def _manifest_key() -> bytes:
    value = os.environ.get(MANIFEST_KEY_ENV, "")
    if not value:
        raise BackupError(f"missing manifest authentication key: {MANIFEST_KEY_ENV}")
    return value.encode("utf-8")


def _canonical_metadata(metadata: Mapping[str, Any]) -> bytes:
    unsigned = {key: value for key, value in metadata.items() if key != "manifest_auth"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _authenticate_manifest(metadata: Mapping[str, Any]) -> dict[str, str]:
    authentication = metadata.get("manifest_auth")
    if not isinstance(authentication, Mapping):
        raise BackupError("manifest authentication metadata is missing")
    if authentication.get("algorithm") != "HMAC-SHA256":
        raise BackupError("manifest authentication algorithm is unsupported")
    signature = authentication.get("signature")
    if not isinstance(signature, str) or not signature:
        raise BackupError("manifest authentication signature is missing")
    expected = hmac.new(_manifest_key(), _canonical_metadata(metadata), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise BackupError("manifest authentication failed")
    return dict(authentication)


def _contained_path(root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if (
        not relative_path
        or candidate.is_absolute()
        or candidate.drive
        or "\\" in relative_path
        or any(part in {"", ".", ".."} for part in relative_path.split("/"))
    ):
        raise BackupError(f"manifest path is not strict relative path: {relative_path!r}")
    resolved_root = root.resolve()
    resolved_candidate = (resolved_root / candidate).resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as error:
        raise BackupError(f"manifest path escapes root: {relative_path!r}") from error
    return resolved_candidate


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _redacted_target_id(restore_root: Path) -> str:
    digest = hashlib.sha256(str(restore_root.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"restore-{digest}"


def validate_backup(manifest_path: Path) -> bool:
    """Verify every file listed by a backup manifest."""
    metadata = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    _authenticate_manifest(metadata)
    generation_root = Path(manifest_path).parent
    for entry in metadata.get("files", []):
        path = _contained_path(generation_root, entry["relative_path"])
        if not path.is_file() or _sha256(path) != entry["sha256"]:
            raise BackupError(f"backup hash validation failed: {path}")
    return True


def validate_recent_backups(
    destination: BackupDestination,
    expected_destination_identity: str,
    limit: int = 30,
    restore_validator: Callable[[Path, dict[str, Any]], None] | None = None,
) -> list[Path]:
    """Restore retained generations into temporary roots and validate metadata."""
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
        metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(
            prefix="backup-restore-validation-", dir=destination.path()
        ) as restore_root:
            DatabaseBackup.restore(
                manifest_path,
                destination,
                Path(restore_root),
                operator_approved=True,
                expected_destination_identity=expected_destination_identity,
                allow_canonical_restore=True,
            )
            if restore_validator is not None:
                restore_validator(Path(restore_root), metadata)
            else:
                _validate_restored_databases(Path(restore_root), metadata)
    with (destination.path() / "backup-audit.jsonl").open("a", encoding="utf-8") as audit:
        audit.write(json.dumps({"event": "validation", "count": len(manifests)}) + "\n")
    return manifests


def _validate_restored_databases(restore_root: Path, metadata: dict[str, Any]) -> None:
    """Open declared SQLCipher files and inspect schema metadata only."""
    for database in metadata.get("databases", []):
        key_env = database.get("key_env")
        if database.get("encryption") != "sqlcipher" or not key_env:
            continue
        key = os.environ.get(str(key_env), "")
        if not key:
            raise BackupError(f"missing SQLCipher key environment variable: {key_env}")
        try:
            import sqlcipher3
        except ImportError as error:  # pragma: no cover - dependency is deployment-specific
            raise BackupError("sqlcipher3 is required for restore validation") from error
        database_path = restore_root / str(database["relative_path"])
        connection = sqlcipher3.connect(str(database_path))
        try:
            raw_key = key.encode("utf-8").hex()
            connection.execute(f'PRAGMA key="x\'{raw_key}\'"')
            for pragma in SQLCIPHER_RESTORE_PRAGMAS:
                connection.execute(pragma)
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name LIMIT 1"
            ).fetchone()
            if tables is None:
                raise BackupError(f"restored database has no schema metadata: {database_path}")
        finally:
            connection.close()


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
        source_root: Path | Mapping[str, Path],
        destination: BackupDestination,
        expected_destination_identity: str,
        now: Callable[[], str] | None = None,
        retention: int = 30,
    ) -> None:
        self._manifest = manifest
        self._source_root = (
            {label: Path(root) for label, root in source_root.items()}
            if isinstance(source_root, Mapping)
            else Path(source_root)
        )
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
        discovered = discover_databases(
            self._source_root if isinstance(self._source_root, Mapping) else [self._source_root]
        )
        validate_manifest(self._manifest, {entry["path"] for entry in discovered})
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
                source = self._resolve_source(entry, relative_path, discovered)
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
                "databases": [
                    {
                        "id": entry.get("id", str(entry["path"])),
                        "relative_path": str(entry["path"]),
                        **{
                            field: entry[field]
                            for field in (
                                "classification",
                                "encryption",
                                "key_env",
                                "schema_tables",
                            )
                            if field in entry
                        },
                    }
                    for entry in entries
                    if entry.get("backup_allowed", False)
                ],
            }
            manifest_path = temporary_root / "manifest.json"
            metadata["manifest_auth"] = {
                "algorithm": "HMAC-SHA256",
                "signature": hmac.new(
                    _manifest_key(), _canonical_metadata(metadata), hashlib.sha256
                ).hexdigest(),
            }
            manifest_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(temporary_root, generation_root)
        finally:
            if temporary_root.exists():
                shutil.rmtree(temporary_root)
        self._prune_generations()
        final_manifest = generation_root / "manifest.json"
        audit_path = self._destination.path() / "backup-audit.jsonl"
        with audit_path.open("a", encoding="utf-8") as audit:
            audit.write(
                json.dumps(
                    {
                        "event": "backup",
                        "generation": generation,
                        "manifest_locator": f"generations/{generation}/manifest.json",
                    }
                )
                + "\n"
            )
        return BackupResult(generation=generation, manifest_path=final_manifest)

    def _resolve_source(
        self,
        entry: Mapping[str, Any],
        relative_path: str,
        discovered: Sequence[dict[str, str]],
    ) -> Path:
        if isinstance(self._source_root, Path):
            return self._source_root / Path(relative_path)
        discovery = entry.get("discovery")
        if isinstance(discovery, Mapping):
            matches = [
                item["path"]
                for item in discovered
                if item["path"].split("/", 1)[0] == discovery["project"]
                and item["path"].rsplit("/", 1)[-1] == discovery["basename"]
            ]
            if len(matches) == 1:
                project, local_path = matches[0].split("/", 1)
                source_label = next(
                    (
                        label
                        for label in self._source_root
                        if DISPLAY_PROJECT_KEYS.get(label, label) == project
                    ),
                    project,
                )
                if source_label not in self._source_root:
                    raise BackupError(f"manifest source root is not registered: {project}")
                return Path(self._source_root[source_label]) / Path(local_path)
            if len(matches) > 1:
                raise BackupError(f"ambiguous database discovery: {discovery}")
        for project, root in self._source_root.items():
            prefix = f"{project}/"
            if relative_path.startswith(prefix):
                return Path(root) / Path(relative_path[len(prefix) :])
        raise BackupError(f"manifest source root is not registered: {relative_path}")

    def _prune_generations(self) -> None:
        generations_root = self._destination.path() / "generations"
        generations = sorted(
            (path for path in generations_root.iterdir() if path.is_dir()),
            key=lambda path: (path.name[:8].isdigit(), path.name),
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
        expected_destination_identity: str,
        overwrite: bool = False,
        overwrite_operator_approved: bool = False,
        allow_canonical_restore: bool = False,
    ) -> None:
        """Restore verified files only into a separate operator-approved directory."""
        if not operator_approved:
            raise RestoreApprovalError("restore requires explicit operator approval")
        if not expected_destination_identity.strip():
            raise DestinationIdentityError("trusted destination identity is required")
        if Path(restore_root).resolve() == Path.cwd().resolve():
            raise RestoreApprovalError("restore target must be isolated")
        if not destination.is_verified(expected_destination_identity):
            raise DestinationIdentityError("restore destination identity is not verified")
        validate_backup(manifest_path)
        metadata = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if any(
            database.get("classification") == "canonical"
            for database in metadata.get("databases", [])
        ) and not allow_canonical_restore:
            raise RestoreApprovalError("canonical database restore is prohibited by default")
        if overwrite and not overwrite_operator_approved:
            raise RestoreApprovalError("overwrite requires separate overwrite authorization")
        generation_root = Path(manifest_path).parent
        restore_root = Path(restore_root)
        restore_root.mkdir(parents=True, exist_ok=True)
        for entry in metadata["files"]:
            target = _contained_path(restore_root, entry["relative_path"])
            if target.exists() and not overwrite:
                raise RestoreApprovalError(f"existing restore target: {entry['relative_path']}")
            _atomic_copy(_contained_path(generation_root, entry["relative_path"]), target)
        with (destination.path() / "backup-audit.jsonl").open("a", encoding="utf-8") as audit:
            audit.write(
                json.dumps(
                    {
                        "event": "restore",
                        "manifest_locator": f"generations/{generation_root.name}/manifest.json",
                        "target_id": _redacted_target_id(restore_root),
                    }
                )
                + "\n"
            )