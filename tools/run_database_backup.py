from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.database_backup import (
    BackupResult,
    DatabaseBackup,
    DestinationIdentityError,
    LocalVolumeDestination,
)
from src.utils.database_backup_scope import load_manifest


@dataclass(frozen=True)
class ProjectOutcome:
    """Redacted outcome for one scheduled project root."""

    status: str
    detail: str = ""


@dataclass(frozen=True)
class ScheduledBackupResult:
    """Aggregate status for one scheduled backup invocation."""

    overall_status: str
    project_outcomes: dict[str, ProjectOutcome]
    failure_reason: str = ""


def run_backup(
    manifest_path: Path,
    source_root: Path | dict[str, Path],
    volume_root: Path,
    volume_identity: str,
) -> BackupResult:
    """Run the approved manifest backup after a fail-closed volume preflight."""
    if not volume_root.is_dir():
        raise DestinationIdentityError(f"backup destination is missing: {volume_root}")
    return DatabaseBackup(
        manifest=load_manifest(manifest_path),
        source_root=source_root,
        destination=LocalVolumeDestination(volume_root, volume_identity),
        expected_destination_identity=volume_identity,
    ).run()


def run_scheduled_backups(
    manifest_path: Path,
    project_roots: dict[str, Path],
    volume_root: Path,
    volume_identity: str,
) -> ScheduledBackupResult:
    """Run the shared backup once and report a redacted outcome per project."""
    outcomes = {label: ProjectOutcome("failed") for label in project_roots}
    try:
        run_backup(manifest_path, project_roots, volume_root, volume_identity)
    except Exception as error:  # noqa: BLE001 - scheduler must report all project failures
        detail = type(error).__name__
        return ScheduledBackupResult(
            overall_status="failed",
            project_outcomes={label: ProjectOutcome("failed", detail) for label in project_roots},
            failure_reason=detail,
        )
    return ScheduledBackupResult(
        overall_status="succeeded",
        project_outcomes={label: ProjectOutcome("succeeded") for label in outcomes},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily local database backup.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=None)
    parser.add_argument("--project-root", action="append", type=str, default=[])
    parser.add_argument("--volume-root", type=Path, default=None)
    parser.add_argument("--volume-identity", default=None)
    args = parser.parse_args()
    project_roots: list[str] = []
    for value in args.project_root:
        if isinstance(value, tuple):
            project_roots.append(f"{value[0]}={value[1]}")
            continue
        project_roots.extend(
            item.strip().strip("'\"")
            for item in value.split(",")
            if item.strip().strip("'\"")
        )
    if project_roots and args.source_root is not None:
        parser.error("--source-root and --project-root cannot be combined")
    if project_roots:
        source_root = dict(_parse_project_root(item) for item in project_roots)
    elif args.source_root is not None:
        source_root = args.source_root
    else:
        parser.error("one of --source-root or --project-root is required")
    volume_root = args.volume_root or _required_path("WORKSPACE_BACKUP_VOLUME")
    volume_identity = args.volume_identity or _required_value("WORKSPACE_BACKUP_VOLUME_ID")
    result = run_scheduled_backups(
        args.manifest,
        source_root if isinstance(source_root, dict) else {"source": source_root},
        volume_root,
        volume_identity,
    )
    print(json.dumps({
        "overall_status": result.overall_status,
        "projects": {label: outcome.status for label, outcome in result.project_outcomes.items()},
        "failure": result.failure_reason,
    }, sort_keys=True))
    return 0 if result.overall_status == "succeeded" else 1


def _parse_project_root(value: str) -> tuple[str, Path]:
    label, separator, root = value.partition("=")
    if not separator or not label.strip() or not root.strip():
        raise argparse.ArgumentTypeError("project root must be LABEL=PATH")
    return label, Path(root)


def _required_path(name: str) -> Path:
    return Path(_required_value(name))


def _required_value(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())