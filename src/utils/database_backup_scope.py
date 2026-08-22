from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


CLASSIFICATIONS = {
    "canonical",
    "coordination",
    "derived",
    "temporary",
    "legacy",
    "unknown",
    "approval-required",
}
REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "fr",
    "policy_status",
    "purpose",
    "content_boundary",
    "classifications",
    "databases",
    "exclusions",
    "not_implemented",
    "separate_todos",
}
REQUIRED_DATABASE_FIELDS = {
    "id",
    "path",
    "classification",
    "backup_allowed",
    "reason",
}
OPTIONAL_DATABASE_FIELDS = {"discovery", "encryption", "key_env", "schema_tables"}
EXCLUSION_FIELDS = {"pattern", "reason"}
DISCOVERY_FIELDS = {"project", "basename"}
DATABASE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
TODO_ID_PATTERN = re.compile(r"^[0-9]+$")
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "venv",
    ".worktrees",
    "__pycache__",
    "node_modules",
    ".cache",
    "cache",
    "caches",
    "output",
    "tmp",
    "logs",
    "backups",
    "qbackups",
}
DISPLAY_PROJECT_KEYS = {
    "∞Life": "life",
    "ΣCapital": "capital",
}


def validate_manifest(
    manifest: dict[str, Any], discovered_paths: set[str] | None = None
) -> None:
    """Validate the required structure and classifications of a policy manifest."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    unknown_fields = manifest.keys() - REQUIRED_MANIFEST_FIELDS
    if unknown_fields:
        raise ValueError(f"unknown manifest fields: {sorted(unknown_fields)}")
    missing_fields = REQUIRED_MANIFEST_FIELDS - manifest.keys()
    if missing_fields:
        raise ValueError(
            f"manifest missing required fields: {sorted(missing_fields)}"
        )
    if not isinstance(manifest["schema_version"], int) or isinstance(
        manifest["schema_version"], bool
    ):
        raise ValueError("manifest schema_version must be an integer")
    for field in ("fr", "policy_status", "purpose", "content_boundary"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ValueError(f"manifest {field} must be a non-empty string")

    classifications = manifest.get("classifications")
    if (
        not isinstance(classifications, list)
        or len(classifications) != len(CLASSIFICATIONS)
        or not all(isinstance(classification, str) for classification in classifications)
        or set(classifications) != CLASSIFICATIONS
    ):
        raise ValueError("manifest classifications must enumerate the complete taxonomy")

    databases = manifest.get("databases")
    if not isinstance(databases, list):
        raise ValueError("manifest databases must be a list")
    if not isinstance(manifest["exclusions"], list):
        raise ValueError("manifest exclusions must be a list")
    if not isinstance(manifest["not_implemented"], list):
        raise ValueError("manifest not_implemented must be a list")
    if not isinstance(manifest["separate_todos"], list):
        raise ValueError("manifest separate_todos must be a list")
    if not all(
        isinstance(item, str)
        and bool(IDENTIFIER_PATTERN.fullmatch(item))
        for item in manifest["not_implemented"]
    ):
        raise ValueError(
            "manifest not_implemented entries must be non-empty snake_case strings"
        )
    if not all(
        isinstance(item, str) and bool(TODO_ID_PATTERN.fullmatch(item))
        for item in manifest["separate_todos"]
    ):
        raise ValueError(
            "manifest separate_todos entries must be non-empty numeric strings"
        )

    for exclusion in manifest["exclusions"]:
        if not isinstance(exclusion, dict):
            raise ValueError("each exclusion must be an object")
        unknown_fields = exclusion.keys() - EXCLUSION_FIELDS
        if unknown_fields:
            raise ValueError(f"unknown exclusion fields: {sorted(unknown_fields)}")
        if set(exclusion) != EXCLUSION_FIELDS:
            raise ValueError("each exclusion must have pattern and reason")
        if (
            not isinstance(exclusion["pattern"], str)
            or not exclusion["pattern"].strip()
            or not isinstance(exclusion["reason"], str)
            or not exclusion["reason"].strip()
        ):
            raise ValueError("each exclusion pattern and reason must be non-empty strings")

    registered_ids: set[str] = set()
    registered_paths: set[str] = set()
    for database in databases:
        if not isinstance(database, dict):
            raise ValueError("each database entry must be an object")
        unknown_fields = database.keys() - REQUIRED_DATABASE_FIELDS - OPTIONAL_DATABASE_FIELDS
        if unknown_fields:
            raise ValueError(f"unknown database fields: {sorted(unknown_fields)}")
        missing_fields = REQUIRED_DATABASE_FIELDS - database.keys()
        if missing_fields:
            raise ValueError(
                f"database entry missing required fields: {sorted(missing_fields)}"
            )
        database_id = database["id"]
        if not isinstance(database_id, str) or not database_id.strip():
            raise ValueError("each database entry must have a non-empty id")
        if database_id in registered_ids:
            raise ValueError(f"duplicate database id: {database_id}")
        registered_ids.add(database_id)
        path = database.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("each database entry must have a non-empty path")
        normalized_path = path.replace("\\", "/")
        path_parts = normalized_path.split("/")
        if (
            Path(normalized_path).is_absolute()
            or normalized_path.startswith("/")
            or any(part in {"", ".", ".."} for part in path_parts)
            or "\\" in path
            or ":" in path
            or any(ord(character) < 32 or ord(character) == 127 for character in path)
        ):
            raise ValueError("database paths must be relative and traversal-free")
        if normalized_path in registered_paths:
            raise ValueError(f"duplicate database path: {normalized_path}")
        registered_paths.add(normalized_path)
        classification = database.get("classification")
        if not isinstance(classification, str) or classification not in CLASSIFICATIONS:
            raise ValueError(
                f"database {database.get('id', '<unknown>')} has invalid classification"
            )
        if not isinstance(database["backup_allowed"], bool):
            raise ValueError(
                f"database {database.get('id', '<unknown>')} backup_allowed must be boolean"
            )
        if not isinstance(database["reason"], str) or not database["reason"].strip():
            raise ValueError(
                f"database {database.get('id', '<unknown>')} must have a non-empty reason"
            )
        if "encryption" in database and database["encryption"] != "sqlcipher":
            raise ValueError("database encryption must be sqlcipher")
        if "key_env" in database and (
            not isinstance(database["key_env"], str)
            or not re.fullmatch(r"[A-Z][A-Z0-9_]*", database["key_env"])
        ):
            raise ValueError("database key_env must be an environment variable name")
        if classification == "approval-required" and database.get("backup_allowed") is not False:
            if database.get("id") != "capital-sigmacapital":
                raise ValueError(
                    f"database {database.get('id', '<unknown>')} must be default-denied"
                )
            if manifest["policy_status"] != "approved":
                raise ValueError("Capital database backup requires governed approval")
            if normalized_path != "capital/financial-store" or database.get("discovery") != {
                "project": "capital",
                "basename": "sigmacapital.db",
            }:
                raise ValueError("approved Capital scope is limited to capital/financial-store")
            if database.get("encryption") != "sqlcipher" or database.get("key_env") != "SIGMACAPITAL_DB_KEY":
                raise ValueError("approved Capital scope requires SQLCipher key metadata")

        discovery = database.get("discovery")
        if discovery is not None:
            if not isinstance(discovery, dict):
                raise ValueError("database discovery must be an object")
            unknown_fields = discovery.keys() - DISCOVERY_FIELDS
            if unknown_fields:
                raise ValueError(f"unknown discovery fields: {sorted(unknown_fields)}")
            if set(discovery) != DISCOVERY_FIELDS:
                raise ValueError("database discovery must have project and basename")
            for field in DISCOVERY_FIELDS:
                value = discovery[field]
                if (
                    not isinstance(value, str)
                    or not value.strip()
                    or "/" in value
                    or "\\" in value
                    or ":" in value
                    or any(ord(character) < 32 or ord(character) == 127 for character in value)
                ):
                    raise ValueError("database discovery values must be safe identifiers")

        life_discovery = (
            isinstance(discovery, dict) and discovery.get("project") == "life"
        )
        if database.get("backup_allowed") and (
            normalized_path.startswith("life/") or life_discovery
        ):
            if manifest["policy_status"] != "approved":
                raise ValueError(
                    "Life database backup requires governed approval"
                )
            if normalized_path != "life/health-store" or discovery != {
                "project": "life",
                "basename": "infinitelife.db",
            }:
                raise ValueError(
                    "approved Life scope is limited to life/health-store"
                )
            if database.get("encryption") != "sqlcipher" or not database.get("key_env"):
                raise ValueError(
                    "approved Life scope requires SQLCipher key metadata"
                )

    if discovered_paths is not None:
        normalized_discovered = {path.replace("\\", "/") for path in discovered_paths}
        missing = set()
        for discovered_path in normalized_discovered:
            if discovered_path in registered_paths:
                continue
            if any(
                f"{manifest_key}/" in discovered_path
                and f"{display_label}/{discovered_path.split('/', 1)[1]}" in registered_paths
                for display_label, manifest_key in DISPLAY_PROJECT_KEYS.items()
            ):
                continue
            path_parts = discovered_path.split("/")
            basename = path_parts[-1]
            project = path_parts[0] if path_parts else ""
            if not any(
                database.get("discovery") == {"project": project, "basename": basename}
                for database in databases
            ):
                missing.add(discovered_path)
        if missing:
            raise ValueError(f"unregistered discovered databases: {sorted(missing)}")


def discover_databases(
    roots: Sequence[Path] | Mapping[str, Path],
) -> list[dict[str, str]]:
    """Return database paths under roots, excluding transient directory names.

    Mapping labels are display project names; explicit entries in
    ``DISPLAY_PROJECT_KEYS`` translate them to manifest discovery keys.
    """
    discovered: list[dict[str, str]] = []
    discovery_keys: dict[tuple[str, str], str] = {}
    root_items = roots.items() if isinstance(roots, Mapping) else ((None, root) for root in roots)
    for label, root in root_items:
        root = Path(root)
        if not root.is_dir():
            continue
        for candidate in root.rglob("*"):
            if not candidate.is_file() or candidate.suffix.lower() not in DATABASE_SUFFIXES:
                continue
            relative_parts = candidate.relative_to(root).parts
            if any(part.casefold() in EXCLUDED_DIRECTORY_NAMES for part in relative_parts[:-1]):
                continue
            if candidate.name.casefold().startswith("tmp"):
                continue
            relative_path = "/".join(relative_parts)
            project = (
                DISPLAY_PROJECT_KEYS.get(label, label)
                if label
                else (relative_parts[0] if len(relative_parts) > 1 else "")
            )
            discovery_key = (project.casefold(), candidate.name.casefold())
            path = f"{project}/{relative_path}" if label else relative_path
            previous_path = discovery_keys.get(discovery_key)
            if previous_path is not None:
                raise ValueError(
                    "discovery collision for "
                    f"(project={project!r}, basename={candidate.name!r}): "
                    f"{previous_path!r} and {path!r}"
                )
            discovery_keys[discovery_key] = path
            discovered.append({"path": path})
    return sorted(discovered, key=lambda entry: entry["path"])


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a JSON database backup policy manifest."""
    with Path(path).open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    validate_manifest(manifest)
    return manifest


def render_report(manifest: dict[str, Any]) -> str:
    """Render a deterministic Markdown report from a validated manifest."""
    validate_manifest(manifest)
    lines = [
        "# Workspace Database Backup Scope",
        "",
        f"Manifest schema version: {manifest.get('schema_version', 'unknown')}",
        "",
        "This report is generated from the versioned policy manifest. It contains database paths and policy metadata only; no database contents are read or copied.",
        "",
        "## Classification Taxonomy",
        "",
        ", ".join(manifest.get("classifications", sorted(CLASSIFICATIONS))),
        "",
        "## Database Inventory",
        "",
        "| ID | Path | Classification | Backup allowed | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for database in manifest["databases"]:
        lines.append(
            "| {id} | {path} | {classification} | {backup_allowed} | {reason} |".format(
                id=database.get("id", ""),
                path=database["path"],
                classification=database["classification"],
                backup_allowed="yes" if database.get("backup_allowed") else "no",
                reason=database.get("reason", ""),
            )
        )
    lines.extend(["", "## Explicit Exclusions", ""])
    for exclusion in manifest.get("exclusions", []):
        lines.append(f"- `{exclusion['pattern']}`: {exclusion['reason']}")
    lines.extend(["", "## Scope Boundary", "", "No upload, cloud provider, encryption-key, retention, or restore behavior is implemented by this policy.", ""])
    return "\n".join(lines)