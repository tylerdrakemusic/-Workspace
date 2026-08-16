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
    workspace_root = _canonical_workspace_root(workspace_root)
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


def _canonical_workspace_root(workspace_root: Path) -> Path:
    """Resolve a worktree path to the repository root used by scheduled jobs."""
    configured_root = Path(workspace_root)
    parts = [part.casefold() for part in configured_root.parts]
    if ".worktrees" not in parts:
        return configured_root
    resolved = configured_root.resolve()
    parts = [part.casefold() for part in resolved.parts]
    worktrees_index = parts.index(".worktrees")
    if worktrees_index == 0:
        raise ValueError("workspace worktree path has no repository root")
    return Path(*resolved.parts[:worktrees_index])
