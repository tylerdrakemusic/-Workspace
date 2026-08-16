from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TaskSpec:
    """Pure task registration values used by the Windows launcher."""

    executable: Path
    arguments: tuple[str, ...]
    trigger: str
    frequency: str
    environment_names: tuple[str, ...]


def build_task_spec(workspace_root: Path, python_path: Path) -> TaskSpec:
    """Build the daily backup task without embedding secrets or drive fallbacks."""
    launcher = workspace_root / "tools" / "run_database_backup.ps1"
    project_roots = (
        ("❤Music", workspace_root.parent / "❤Music"),
        ("⟨ψ⟩Quantum", workspace_root.parent / "⟨ψ⟩Quantum"),
        ("👁AI-Manifest", workspace_root.parent / "👁AI-Manifest"),
        ("⊕Workspace", workspace_root),
    )
    return TaskSpec(
        executable=Path("PowerShell.exe"),
        arguments=(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher),
            "-Python",
            str(python_path),
            "-Manifest",
            str(workspace_root / "src" / "config" / "database_backup_scope.json"),
            "-ProjectRoot",
            ",".join(f"{label}={root}" for label, root in project_roots),
        ),
        trigger="02:00",
        frequency="DAILY",
        environment_names=(
            "WORKSPACE_BACKUP_VOLUME",
            "WORKSPACE_BACKUP_VOLUME_ID",
            "WORKSPACE_BACKUP_MANIFEST_KEY",
        ),
    )