"""
⊕ Workspace Hygiene Runner — headless scheduled sweep.

Invoked by Windows Scheduled Task 'WorkspaceHygiene' (weekly, Sunday 03:00).
Does NOT require VS Code or Copilot Chat to be running.

Sweep phases:
  1. tmp/ purge     — all 5 project tmp/ folders
  2. logs/ rotation — delete log files older than 30 days, all 5 projects
  3. worktree prune — git worktree prune on ⊕Workspace
  4. qbackups trim  — keep last 5 ty_string_cache_* backups in ⟨ψ⟩Quantum
  5. DB health      — PRAGMA integrity_check on workspace.db; file-stat for
                      other encrypted DBs whose keys are in env
  6. PNG hygiene    — move stray *.png from each project root into
                      <project>/proof/screenshots/<YYYY-MM-DD>/; skips PNG
                      files already inside a designated subdir

Proof output: one proof_artifacts row written to workspace.db on success.
              FAILED row + exit code 1 on any unhandled exception.

Usage:
    C:\\G\\python.exe f:\\⊕Workspace\\tools\\run_hygiene.py
    C:\\G\\python.exe f:\\⊕Workspace\\tools\\run_hygiene.py --dry-run
"""

import argparse
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ── Path bootstrap ─────────────────────────────────────────────────────────────
WORKSPACE_ROOT   = Path(__file__).resolve().parents[1]   # f:\⊕Workspace
WORKSPACE_UTILS  = WORKSPACE_ROOT / "src" / "utils"
INFLIFE_UTILS    = Path(r"f:\∞Life\src\utils")
MUSIC_UTILS      = Path(r"f:\❤Music\src\utils")

sys.path.insert(0, str(WORKSPACE_UTILS))
from init_db import get_connection, init_db  # type: ignore[import]

# ── Project roots ──────────────────────────────────────────────────────────────
PROJECTS: dict[str, Path] = {
    "⊕Workspace":  WORKSPACE_ROOT,
    "∞Life":        Path(r"f:\∞Life"),
    "❤Music":       Path(r"f:\❤Music"),
    "⟨ψ⟩Quantum":  Path(r"f:\⟨ψ⟩Quantum"),
    "👁AI-Manifest": Path(r"f:\👁AI-Manifest"),
}

QBACKUP_DIR = Path(r"f:\⟨ψ⟩Quantum\qbackups")
LOG_RETENTION_DAYS = 30
QBACKUP_KEEP = 5

# ── Subdirs where *.png files legitimately live (skip during PNG hygiene) ──────
_PNG_SAFE_SUBDIRS: frozenset[str] = frozenset({
    "proof", "output", "reports", "images", "Brand",
    "data", "docs", "research", "catalog", "src",
    ".github", ".vscode", ".playwright-mcp", ".worktrees",
    "node_modules", "dist", "build",
})

# ── Patterns that are always safe to delete from tmp/ ──────────────────────────
_TMP_DELETE_GLOBS = [
    "_test_*", "_temp_*", "_debug_*", "tmp_*",
    "write_*.py", "patch_*.py", "pr_*.json", "*_results.*",
    "reports_backup_*", "*_backup_*",
]
_TMP_MAX_AGE_DAYS = 7


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — tmp/ purge
# ─────────────────────────────────────────────────────────────────────────────

def purge_tmp(project: str, root: Path, dry_run: bool) -> list[str]:
    """Delete stale / known-transient files from <root>/tmp/."""
    tmp_dir = root / "tmp"
    if not tmp_dir.is_dir():
        return []

    deleted: list[str] = []
    cutoff = datetime.now() - timedelta(days=_TMP_MAX_AGE_DAYS)

    for glob in _TMP_DELETE_GLOBS:
        for f in tmp_dir.glob(glob):
            if not f.is_file():
                continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                if not dry_run:
                    f.unlink(missing_ok=True)
                deleted.append(f.name)

    # Also delete any file >7d with no recognised pattern but still in tmp/
    for f in tmp_dir.iterdir():
        if not f.is_file():
            continue
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff and f.name not in deleted:
            # Extra safety: skip if name is ty_string_cache (protected)
            if "ty_string_cache" in f.name.lower():
                continue
            if not dry_run:
                f.unlink(missing_ok=True)
            deleted.append(f.name)

    return deleted


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — logs/ rotation
# ─────────────────────────────────────────────────────────────────────────────

def rotate_logs(project: str, root: Path, dry_run: bool) -> list[str]:
    """Delete log files older than LOG_RETENTION_DAYS from <root>/logs/."""
    logs_dir = root / "logs"
    if not logs_dir.is_dir():
        return []

    deleted: list[str] = []
    cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)

    for f in logs_dir.rglob("*"):
        if not f.is_file():
            continue
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            if not dry_run:
                f.unlink(missing_ok=True)
            deleted.append(str(f.relative_to(root)))

    return deleted


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — git worktree prune
# ─────────────────────────────────────────────────────────────────────────────

def prune_worktrees(dry_run: bool) -> str:
    """Run git worktree prune --verbose in the ⊕Workspace repo."""
    if dry_run:
        return "DRY-RUN: skipped git worktree prune"
    try:
        result = subprocess.run(
            ["git", "worktree", "prune", "--verbose"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(WORKSPACE_ROOT),
            timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
        return output if output else "no stale worktrees"
    except subprocess.TimeoutExpired:
        return "TIMEOUT: git worktree prune exceeded 30s"
    except FileNotFoundError:
        return "SKIPPED: git not found in PATH"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 — qbackups trim
# ─────────────────────────────────────────────────────────────────────────────

def trim_qbackups(dry_run: bool) -> list[str]:
    """Keep only the last QBACKUP_KEEP ty_string_cache_* backups."""
    if not QBACKUP_DIR.is_dir():
        return []

    backups = sorted(
        [f for f in QBACKUP_DIR.glob("ty_string_cache_*.txt") if f.is_file()],
        key=lambda f: f.stat().st_mtime,
    )

    to_delete = backups[:-QBACKUP_KEEP] if len(backups) > QBACKUP_KEEP else []
    deleted: list[str] = []
    for f in to_delete:
        if not dry_run:
            f.unlink(missing_ok=True)
        deleted.append(f.name)
    return deleted


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 — DB health check
# ─────────────────────────────────────────────────────────────────────────────

def check_workspace_db() -> dict[str, str]:
    """Run PRAGMA integrity_check on workspace.db via init_db."""
    result: dict[str, str] = {}
    try:
        init_db()
        conn = get_connection()
        row = conn.execute("PRAGMA integrity_check").fetchone()
        result["workspace.db"] = row[0] if row else "unknown"
        row_counts: list[str] = []
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for (tbl,) in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]  # noqa: S608
            row_counts.append(f"{tbl}:{count}")
        result["workspace.db:row_counts"] = ",".join(row_counts)
        conn.close()
    except Exception as exc:  # noqa: BLE001
        result["workspace.db"] = f"ERROR: {exc}"
    return result


def stat_db(label: str, path: Path) -> dict[str, str]:
    """File-stat a DB we won't try to decrypt (no key in this scope)."""
    if not path.exists():
        return {label: "MISSING"}
    stat = path.stat()
    size_kb = stat.st_size // 1024
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M")
    return {label: f"ok  size={size_kb}KB  mtime={mtime}"}


def db_health() -> dict[str, str]:
    """Aggregate DB health check for all known project DBs."""
    results: dict[str, str] = {}
    results.update(check_workspace_db())
    results.update(stat_db(
        "infinitelife.db",
        Path(r"f:\∞Life\src\data\infinitelife.db"),
    ))
    results.update(stat_db(
        "heartmusic.db",
        Path(r"f:\❤Music\data\heartmusic.db"),
    ))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 — PNG hygiene
# ─────────────────────────────────────────────────────────────────────────────

def archive_root_pngs(project: str, root: Path, dry_run: bool) -> list[tuple[str, str]]:
    """Move stray *.png files from <root>/ into <root>/proof/screenshots/<date>/.

    Only scans the immediate project root (depth=1).  Any *.png already inside
    a _PNG_SAFE_SUBDIRS folder is left untouched.

    Returns a list of (src_name, dest_relative) tuples for reporting.
    """
    if not root.is_dir():
        return []

    pngs = [
        f for f in root.iterdir()
        if f.is_file() and f.suffix.lower() == ".png"
    ]
    if not pngs:
        return []

    date_str = datetime.now().strftime("%Y-%m-%d")
    dest_dir = root / "proof" / "screenshots" / date_str
    moved: list[tuple[str, str]] = []

    for src in pngs:
        dest = dest_dir / src.name
        # Make dest name unique if a file with that name already exists
        if dest.exists():
            stem, suffix = src.stem, src.suffix
            dest = dest_dir / f"{stem}_{uuid.uuid4().hex[:6]}{suffix}"

        rel_dest = str(dest.relative_to(root))
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            src.rename(dest)
        moved.append((src.name, rel_dest))

    return moved


# ─────────────────────────────────────────────────────────────────────────────
# Proof artifact writer
# ─────────────────────────────────────────────────────────────────────────────

def _write_proof(description: str, failed: bool = False) -> None:
    """Write a single proof_artifacts row to workspace.db."""
    proof_id = uuid.uuid4().hex[:12]
    run_id   = None   # no perf_run entry; FK is nullable
    agent    = "hygiene-scheduler"
    ptype    = "command_output"
    now_iso  = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    try:
        init_db()
        conn = get_connection()
        conn.execute(
            """INSERT INTO proof_artifacts
               (proof_id, run_id, agent, proof_type, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (proof_id, run_id, agent, ptype, description, now_iso),
        )
        conn.commit()
        conn.close()
        print(f"[proof] {proof_id}  run={run_id}")
    except Exception as exc:  # noqa: BLE001
        # Last-resort: print to stderr so Task Scheduler captures it in the event log
        print(f"[proof] WRITE FAILED: {exc}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="⊕Workspace headless hygiene sweep")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be done without deleting anything")
    args = parser.parse_args()
    dry = args.dry_run

    started = datetime.now()
    lines: list[str] = [
        f"hygiene-scheduler  {'DRY-RUN ' if dry else ''}started={started.strftime('%Y-%m-%dT%H:%M')}",
    ]

    try:
        # ── Phase 1: tmp/ purge ───────────────────────────────────────────────
        for name, root in PROJECTS.items():
            deleted = purge_tmp(name, root, dry)
            tag = "DRY" if dry else "DEL"
            lines.append(f"  tmp/{name}: [{tag}] {len(deleted)} files"
                         + (f" ({', '.join(deleted[:5])}{'…' if len(deleted)>5 else ''})"
                            if deleted else ""))

        # ── Phase 2: logs/ rotation ───────────────────────────────────────────
        for name, root in PROJECTS.items():
            deleted = rotate_logs(name, root, dry)
            tag = "DRY" if dry else "DEL"
            lines.append(f"  logs/{name}: [{tag}] {len(deleted)} files")

        # ── Phase 3: worktree prune ───────────────────────────────────────────
        wt_result = prune_worktrees(dry)
        lines.append(f"  worktrees: {wt_result}")

        # ── Phase 4: qbackups trim ────────────────────────────────────────────
        trimmed = trim_qbackups(dry)
        tag = "DRY" if dry else "DEL"
        lines.append(f"  qbackups: [{tag}] {len(trimmed)} old backups removed")

        # ── Phase 5: DB health ────────────────────────────────────────────────
        health = db_health()
        for db_label, status in health.items():
            if "row_counts" not in db_label:
                lines.append(f"  db/{db_label}: {status}")
        # ── Phase 6: PNG hygiene ──────────────────────────────────────────
        total_pngs_moved = 0
        for name, root in PROJECTS.items():
            moved = archive_root_pngs(name, root, dry)
            total_pngs_moved += len(moved)
            tag = "DRY" if dry else "MOV"
            if moved:
                sample = ", ".join(src for src, _ in moved[:5])
                ellipsis = "…" if len(moved) > 5 else ""
                lines.append(f"  png/{name}: [{tag}] {len(moved)} files → proof/screenshots/ ({sample}{ellipsis})")
            else:
                lines.append(f"  png/{name}: [{tag}] 0 stray PNGs")
        elapsed = (datetime.now() - started).total_seconds()
        lines.append(f"  elapsed={elapsed:.1f}s  status=OK")

        summary = " | ".join(lines)
        print("\n".join(lines))
        _write_proof(summary)
        return 0

    except Exception as exc:  # noqa: BLE001
        elapsed = (datetime.now() - started).total_seconds()
        fail_summary = f"FAILED: {exc} | elapsed={elapsed:.1f}s | " + " | ".join(lines)
        print(fail_summary, file=sys.stderr)
        _write_proof(fail_summary, failed=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
