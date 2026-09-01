from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


def redact_failure(error: BaseException) -> dict[str, str]:
    """Return a stable failure category without paths, keys, or database names."""
    messages = {
        FileNotFoundError: "backup source is unavailable",
        PermissionError: "backup operation was denied",
        ValueError: "backup policy is invalid",
    }
    message = next(
        (text for error_type, text in messages.items() if isinstance(error, error_type)),
        "backup operation failed",
    )
    return {"error_type": type(error).__name__, "message": message}


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