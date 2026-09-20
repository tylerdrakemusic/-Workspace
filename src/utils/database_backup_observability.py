from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any


BACKUP_TASK_NAME = "⊕Workspace-DatabaseBackup"
BACKUP_RPO_HOURS = 24
_FAILURE_CATEGORIES = frozenset({
    "task_missing",
    "task_disabled",
    "last_run_failed",
    "missing_evidence",
    "stale_evidence",
    "scope_incomplete",
    "probe_failure",
})


def redact_failure(error: BaseException) -> dict[str, str]:
    """Return a stable failure category without paths, keys, or database names."""
    messages = {
        FileNotFoundError: "backup source is unavailable",
        PermissionError: "backup operation was denied",
        ValueError: "backup policy is invalid",
    }
    if type(error).__name__ == "BackupError" and "source changed during backup" in str(error):
        return {
            "error_type": type(error).__name__,
            "message": "source changed during backup; retry when database writes are idle",
        }
    message = next(
        (text for error_type, text in messages.items() if isinstance(error, error_type)),
        "backup operation failed",
    )
    return {"error_type": type(error).__name__, "message": message}


def record_backup_attempt(
    evidence_path: Path, attempt: int, error: BaseException
) -> None:
    """Append redacted failure evidence for one backup attempt."""
    evidence_path = Path(evidence_path)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": "backup_attempt",
        "attempt": attempt,
        "status": "failed",
        "failure": redact_failure(error),
    }
    with evidence_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def enforce_retention(
    generations_root: Path,
    retention: int = 30,
    valid_generations: set[str] | None = None,
) -> list[str]:
    """Delete old generations while retaining the newest valid recovery point."""
    if retention < 1:
        raise ValueError("retention must be positive")
    generations = sorted(
        (path for path in Path(generations_root).iterdir() if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    keep = {path.name for path in generations[:retention]}
    valid = sorted(valid_generations or set(), reverse=True)
    if valid and valid[0] not in keep and keep:
        keep.remove(min(keep))
        keep.add(valid[0])
    removed: list[str] = []
    for generation in generations:
        if generation.name in keep:
            continue
        for child in generation.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                import shutil

                shutil.rmtree(child)
        generation.rmdir()
        removed.append(generation.name)
    return removed


def record_restore_drill(evidence_path: Path, generation: str, status: str) -> None:
    """Append redacted restore-drill evidence without copying database contents."""
    evidence_path = Path(evidence_path)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generation": generation,
        "status": status,
    }
    with evidence_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def latest_restore_drills(evidence_path: Path, limit: int = 12) -> list[dict[str, Any]]:
    """Read the newest bounded restore-drill evidence records."""
    if limit < 1:
        raise ValueError("evidence limit must be positive")
    path = Path(evidence_path)
    if not path.is_file():
        return []
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return list(reversed(records[-limit:]))


def recovery_objectives_report() -> dict[str, int | str]:
    """Report the approved recovery point and recovery time objectives."""
    return {"rpo_hours": 24, "rto_hours": 4, "status": "defined"}


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _failure_categories(categories: list[str]) -> list[str]:
    return [category for category in categories if category in _FAILURE_CATEGORIES]


def evaluate_backup_health(
    *,
    task: dict[str, Any] | None,
    generation: dict[str, Any] | None,
    approved_targets: list[str],
    checked_at: datetime,
) -> dict[str, Any]:
    """Evaluate read-only backup observations into a redacted portal contract."""
    checked = checked_at.astimezone(timezone.utc)
    categories: list[str] = []
    if not task or not task.get("registered"):
        categories.append("task_missing")
    elif not task.get("enabled"):
        categories.append("task_disabled")
    elif task.get("last_run_result") != 0:
        categories.append("last_run_failed")

    last_success_age: int | None = None
    if generation is None:
        categories.append("missing_evidence")
    else:
        try:
            completed_at = _parse_timestamp(str(generation["completed_at"]))
            age = (checked - completed_at).total_seconds()
            if age < 0 or age > BACKUP_RPO_HOURS * 3600:
                categories.append("stale_evidence")
            else:
                last_success_age = int(age)
        except (KeyError, TypeError, ValueError):
            categories.append("missing_evidence")
        if generation.get("status") != "succeeded":
            categories.append("last_run_failed")
        covered = set(generation.get("covered_targets", []))
        if not set(approved_targets).issubset(covered):
            categories.append("scope_incomplete")

    categories = _failure_categories(list(dict.fromkeys(categories)))
    state = "Healthy" if not categories else "Attention"
    return {
        "state": state,
        "checked_at": checked.isoformat().replace("+00:00", "Z"),
        "last_success_age_seconds": last_success_age,
        "failure_categories": categories,
    }


def _read_backup_task() -> dict[str, Any]:
    query = (
        "$task = Get-ScheduledTask -TaskName '⊕Workspace-DatabaseBackup' "
        "-ErrorAction SilentlyContinue; "
        "if ($null -eq $task) { @{registered=$false} | ConvertTo-Json -Compress } "
        "else { $info = Get-ScheduledTaskInfo -InputObject $task -ErrorAction Stop; "
        "@{registered=$true; enabled=[bool]$task.Settings.Enabled; "
        "last_run_result=[int64]$info.LastTaskResult} | ConvertTo-Json -Compress }"
    )
    output = subprocess.run(
        ["PowerShell.exe", "-NoProfile", "-Command", query],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        shell=False,
        timeout=10,
    ).stdout.strip()
    return json.loads(output) if output else {"registered": False}


def _read_latest_generation(volume_root: Path) -> dict[str, Any] | None:
    generations = volume_root / "generations"
    candidates = [path for path in generations.iterdir() if path.is_dir()]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        manifest = candidate / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            from src.utils.database_backup import _authenticate_manifest

            _authenticate_manifest(metadata)
        except (OSError, TypeError, ValueError, KeyError):
            continue
        if (
            metadata.get("generation") != candidate.name
            or not isinstance(metadata.get("created_at"), str)
            or not isinstance(metadata.get("databases"), list)
            or not isinstance(metadata.get("manifest_auth"), dict)
        ):
            continue
        return {
            "status": "succeeded",
            "completed_at": metadata.get("created_at"),
            "covered_targets": [item.get("id") for item in metadata.get("databases", [])],
        }
    return None


def collect_backup_health() -> dict[str, Any]:
    """Read scheduler and generation metadata without starting backup work."""
    from src.utils.database_backup_scope import load_manifest

    workspace_root = Path(__file__).resolve().parents[2]
    manifest = load_manifest(workspace_root / "src" / "config" / "database_backup_scope.json")
    approved_targets = [
        str(entry["id"])
        for entry in manifest["databases"]
        if entry.get("backup_allowed") is True
    ]
    volume_value = os.environ.get("WORKSPACE_BACKUP_VOLUME", "").strip()
    if not volume_value:
        raise RuntimeError("backup volume is not configured")
    checked_at = datetime.now(timezone.utc)
    return evaluate_backup_health(
        task=_read_backup_task(),
        generation=_read_latest_generation(Path(volume_value)),
        approved_targets=approved_targets,
        checked_at=checked_at,
    )