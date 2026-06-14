r"""⊕ Agent Frontmatter Integrity Scanner.

Scans workspace agent files and shared instruction files for YAML
frontmatter issues, broken inheritance links, and applyTo pattern coverage.
If issues are found, writes or updates a SCAN todo in
`f:\👁AI-Manifest\src\data\manifest_todos.db`.
"""
from __future__ import annotations

import fnmatch
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

AGENT_DIRS: list[Path] = [
    Path(r"f:\.github\agents"),
    Path(r"f:\superpowers\agents"),
]
INSTRUCTION_DIR: Path = Path(r"f:\.github\instructions")
MANIFEST_DB: Path = Path(r"f:\👁AI-Manifest\src\data\manifest_todos.db")
SCAN_TODO_PROJECT = "workspace"
SCAN_TODO_SOURCE = "SCAN"
SCAN_TODO_TEXT = "Agent Frontmatter Integrity Weekly Scanner"
SCAN_TODO_PRIORITY = 7
SCAN_TODO_AUTONOMY = "supervised"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip()
    result: dict[str, str] = {}
    for key in ("description", "applyTo", "name"):
        match = re.search(rf"^{key}:\s*[\"']?(.*?)[\"']?\s*$", block, re.MULTILINE)
        if match:
            result[key] = match.group(1).strip()
    return result


def _extract_inherits(text: str) -> list[str]:
    return re.findall(r"<!--\s*inherits:\s*(.*?)\s*-->", text)


def _discover_agent_files() -> list[Path]:
    files: list[Path] = []
    for directory in AGENT_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("*.md"):
            if path.is_file():
                files.append(path)
    return sorted(files)


def _discover_instruction_files() -> list[Path]:
    if not INSTRUCTION_DIR.exists():
        return []
    return sorted(INSTRUCTION_DIR.glob("*.instructions.md"))


def _all_workspace_md_files() -> list[Path]:
    root = Path(r"f:\.github")
    if not root.exists():
        return []
    return [p for p in root.rglob("*.md") if p.is_file()]


def _apply_to_matches(pattern: str, all_files: list[Path]) -> bool:
    normalized_pattern = pattern.replace("\\", "/")
    for file_path in all_files:
        normalized = str(file_path).replace("\\", "/")
        if fnmatch.fnmatch(normalized, normalized_pattern):
            return True

        # Also match suffix paths so patterns like `.github/agents/*.agent.md`
        # match files under arbitrary temporary roots during tests or offline scans.
        parts = normalized.split("/")
        for i in range(len(parts)):
            suffix = "/".join(parts[i:])
            if fnmatch.fnmatch(suffix, normalized_pattern):
                return True
    return False


def _connect_manifest_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(MANIFEST_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _create_or_update_scan_todo(issue_summary: str, fr_id: str | None = None) -> int | None:
    if not MANIFEST_DB.exists():
        return None
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _connect_manifest_db() as conn:
            row = conn.execute(
                "SELECT id FROM todos WHERE done=0 AND project=? AND source=? AND text=?",
                (SCAN_TODO_PROJECT, SCAN_TODO_SOURCE, SCAN_TODO_TEXT),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE todos SET priority=?, autonomy_level=?, rationale=?, fr_id=?, created_at=? WHERE id=?",
                    (
                        SCAN_TODO_PRIORITY,
                        SCAN_TODO_AUTONOMY,
                        issue_summary,
                        fr_id,
                        now,
                        row["id"],
                    ),
                )
                return int(row["id"])
            cur = conn.execute(
                "INSERT INTO todos (project, source, text, done, created_at, priority, autonomy_level, rationale, fr_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    SCAN_TODO_PROJECT,
                    SCAN_TODO_SOURCE,
                    SCAN_TODO_TEXT,
                    0,
                    now,
                    SCAN_TODO_PRIORITY,
                    SCAN_TODO_AUTONOMY,
                    issue_summary,
                    fr_id,
                ),
            )
            return int(cur.lastrowid)
    except sqlite3.OperationalError:
        return None


def run_agent_frontmatter_integrity(fr_id: str | None = None) -> dict[str, Any]:
    all_md = _all_workspace_md_files()
    issues: list[str] = []
    warnings: list[str] = []

    for path in _discover_agent_files():
        text = _read_text(path)
        if not text.startswith("---"):
            issues.append(f"MISSING FRONTMATTER: {path}")
            continue
        fm = _frontmatter(text)
        if not fm:
            issues.append(f"INVALID FRONTMATTER: {path}")
            continue
        if not fm.get("description"):
            issues.append(f"MISSING DESCRIPTION: {path}")
        inherits = _extract_inherits(text)
        if not inherits:
            warnings.append(f"NO INHERITANCE: {path}")
        else:
            for inh in inherits:
                if not Path(inh).exists():
                    issues.append(f"BROKEN INHERIT: {path} → {inh}")

    for path in _discover_instruction_files():
        text = _read_text(path)
        fm = _frontmatter(text)
        if not fm:
            issues.append(f"INVALID FRONTMATTER: {path}")
            continue
        if not fm.get("description") and not fm.get("applyTo"):
            issues.append(f"NO DESCRIPTION OR applyTo: {path}")
        pattern = fm.get("applyTo")
        if pattern and not _apply_to_matches(pattern, all_md):
            warnings.append(f"applyTo MATCHES NOTHING: {path} pattern='{pattern}'")

    summary_lines = ["Agent Frontmatter Integrity Weekly Scanner"]
    if issues:
        summary_lines.append(f"ISSUES: {len(issues)}")
        summary_lines.extend(issues)
    if warnings:
        summary_lines.append(f"WARNINGS: {len(warnings)}")
        summary_lines.extend(warnings)
    summary = "\n".join(summary_lines)
    todo_id = None
    if issues or warnings:
        todo_id = _create_or_update_scan_todo(summary, fr_id=fr_id)

    return {
        "issues": len(issues),
        "warnings": len(warnings),
        "todo_id": todo_id,
        "summary": summary,
    }


def main() -> int:
    result = run_agent_frontmatter_integrity()
    print(result["summary"])
    return 0 if result["issues"] + result["warnings"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
