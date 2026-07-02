"""
roadmap_generator.py — P8 Cross-Project Roadmap Generator (⊕Workspace half)

Reads active FRs from fr_ledgers.db and open todos from
👁AI-Manifest/src/data/manifest_todos.db, parses FR-to-FR dependencies,
rolls them up to project-to-project dependency edges, buckets FRs into
quarters (manual override via `target_quarter`, else a heuristic based on
risk + state + age), and writes a structured JSON artifact.

Usage:
    C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\roadmap_generator.py [--out <path>]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Terminal/completed states, per feature-request-flow.instructions.md (DONE,
# MERGED, SOAKING, SIGNED_OFF, ARCHIVED, CLOSED). These are excluded from the
# roadmap because the work is finished (or merged and only awaiting Tyler's
# post-merge signoff) — not forward-looking. Rather than excluding a blocklist
# (whose vocabulary drifts as new terminal states like "DONE" are added), the
# generator uses the INCLUDE-list below.

# Active/in-flight FR lifecycle states (see feature-request-flow.instructions.md
# state machine). This is an INCLUDE-list rather than relying on excluding
# ARCHIVED_STATES, because terminal-state vocabulary varies across DBs and new
# terminal states (e.g. "DONE") have been added to fr_ledgers.db that predate
# this generator.
ACTIVE_FR_STATES = {
    "OPEN",
    "TRIAGED",
    "BRANCHED",
    "IN_PROGRESS",
    "CHANGES_REQUESTED",
    "FUNCTIONAL_QA",
    "ARCHITECTURE_REVIEW",
    "REVIEW_REQUESTED",
    "AUTO_REVIEWED",
    "TYLER_APPROVED",
    "BRANCH_CHECKED_OUT",
}

# manifest_todos.db has no lifecycle-state column (only a `done` 0/1 flag), so
# there is no equivalent ACTIVE_TODO_STATES set to define — `fetch_open_todos`
# already filters on `done = 0`.

CANONICAL_PROJECTS = ["∞Life", "❤Music", "⟨ψ⟩Quantum", "👁AI-Manifest", "⊕Workspace", "ΣCapital"]
UNMAPPED_PROJECT = "Unmapped"

# Ordered (specific-before-generic) keyword -> canonical project map. Matching is
# substring-based against a normalized (lowercased, ascii-letters-only) token, so
# more specific / composite keywords must be listed before the generic single-word
# keywords they contain (e.g. "heartmusic" before "music") to avoid ambiguity.
_PROJECT_KEYWORDS: list[tuple[str, str]] = [
    ("infinitelife", "∞Life"),
    ("psiquantum", "⟨ψ⟩Quantum"),
    ("sigmacapital", "ΣCapital"),
    ("heartmusic", "❤Music"),
    ("oplusworkspace", "⊕Workspace"),
    ("aimanifest", "👁AI-Manifest"),
    ("inflife", "∞Life"),
    ("quantum", "⟨ψ⟩Quantum"),
    ("workspace", "⊕Workspace"),
    ("music", "❤Music"),
    ("capital", "ΣCapital"),
    ("life", "∞Life"),
]

_NON_LETTER_RE = re.compile(r"[^a-z]")


def _normalize_project_token(raw: str) -> str:
    """Lowercase and strip everything but ascii letters (drops sigils, digits,
    punctuation, mojibake artifacts like leading '?' or '8', parentheticals)."""
    return _NON_LETTER_RE.sub("", raw.lower())


def canonicalize_project(raw: str | None) -> str:
    """Map a raw project string (any known alias, mojibake variant, or casing)
    to exactly one of the 6 canonical project names, or `Unmapped` if no known
    keyword is found.
    """
    if not raw or not raw.strip():
        return UNMAPPED_PROJECT
    token = _normalize_project_token(raw)
    if not token:
        return UNMAPPED_PROJECT
    for keyword, canonical in _PROJECT_KEYWORDS:
        if keyword in token:
            return canonical
    return UNMAPPED_PROJECT

MANIFEST_TODOS_DB_PATH = (
    Path(__file__).resolve().parents[3] / "👁AI-Manifest" / "src" / "data" / "manifest_todos.db"
)
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "roadmap.json"

# Matches "Depends on: FR-20260524-tts-batch-queue, FR-20260601-foo"
_DEPENDS_ON_RE = re.compile(r"Depends on:\s*([A-Za-z0-9_,\s-]*FR-\d{8}-[\w-]+[A-Za-z0-9_,\s-]*)", re.IGNORECASE)
_FR_ID_RE = re.compile(r"FR-\d{8}-[\w-]+")

STATE_ORDER = {
    "OPEN": 0,
    "TRIAGED": 1,
    "BRANCHED": 2,
    "IN_PROGRESS": 3,
    "CHANGES_REQUESTED": 3,
    "FUNCTIONAL_QA": 4,
    "ARCHITECTURE_REVIEW": 5,
    "REVIEW_REQUESTED": 6,
    "AUTO_REVIEWED": 7,
    "TYLER_APPROVED": 8,
    "BRANCH_CHECKED_OUT": 8,
    "SOAKING": 9,
    "MERGED": 9,
}

RISK_WEIGHT = {"low": 0, "medium": 1, "high": 2}


# ─────────────────────────────────────────────────────────────────────────────
# Dependency parsing

def parse_dependencies(text: str | None) -> list[str]:
    """Extract FR IDs referenced by "Depends on: FR-..." patterns in text.

    Returns a de-duplicated, order-preserving list of FR IDs.
    """
    if not text:
        return []
    found: list[str] = []
    for m in _DEPENDS_ON_RE.finditer(text):
        for fr_id in _FR_ID_RE.findall(m.group(1)):
            if fr_id not in found:
                found.append(fr_id)
    return found


def extract_fr_dependencies(fr: dict[str, Any]) -> list[str]:
    """Collect FR-to-FR dependency IDs referenced anywhere in an FR's text fields."""
    deps: list[str] = []
    for field in ("title", "acceptance_criteria", "concurrency_notes"):
        for fr_id in parse_dependencies(fr.get(field)):
            if fr_id not in deps and fr_id != fr.get("id"):
                deps.append(fr_id)
    return deps


def extract_todo_fr_references(todo_text: str | None) -> list[str]:
    """Extract explicit FR-ID references from a todo's text (no "Depends on" prefix required)."""
    if not todo_text:
        return []
    found: list[str] = []
    for fr_id in _FR_ID_RE.findall(todo_text):
        if fr_id not in found:
            found.append(fr_id)
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Quarterly bucketing heuristic

def current_quarter(today: date | None = None) -> str:
    today = today or date.today()
    q = (today.month - 1) // 3 + 1
    return f"{today.year}-Q{q}"


def add_quarters(quarter_str: str, n: int) -> str:
    """Return the quarter string n quarters after quarter_str (n may be 0)."""
    year_str, q_str = quarter_str.split("-Q")
    year = int(year_str)
    q = int(q_str)
    total = (year * 4 + (q - 1)) + n
    new_year, new_q = divmod(total, 4)
    return f"{new_year}-Q{new_q + 1}"


def _age_days(opened_at: str | None, today: date) -> int:
    if not opened_at:
        return 0
    try:
        opened = datetime.strptime(opened_at[:10], "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max(0, (today - opened).days)


def assign_quarter(fr: dict[str, Any], today: date | None = None) -> str:
    """Assign a target quarter to an FR.

    Manual override (`target_quarter` set on the FR) always wins. Otherwise
    apply a heuristic: lower risk, more-advanced state, and older age all
    pull the FR into an earlier quarter; higher risk and early-stage FRs
    push it later. Bucket offset is clamped to [0, 3] quarters out.
    """
    override = fr.get("target_quarter")
    if override:
        return override

    today = today or date.today()
    base = current_quarter(today)

    bucket = 1  # neutral starting offset

    risk = (fr.get("risk") or "medium").lower()
    bucket += RISK_WEIGHT.get(risk, 1) - 1  # low:-1, medium:0, high:+1

    state = (fr.get("state") or "OPEN").upper()
    state_order = STATE_ORDER.get(state, 0)
    if state_order >= 4:
        bucket -= 1
    elif state_order <= 1:
        bucket += 1

    age = _age_days(fr.get("opened_at"), today)
    if age >= 60:
        bucket -= 1
    elif age < 14:
        bucket += 1

    bucket = max(0, min(3, bucket))
    return add_quarters(base, bucket)


# ─────────────────────────────────────────────────────────────────────────────
# DB reads

def fetch_active_frs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    placeholders = ",".join("?" * len(ACTIVE_FR_STATES))
    rows = conn.execute(
        f"SELECT * FROM feature_requests WHERE state IN ({placeholders})",  # nosec B608
        list(ACTIVE_FR_STATES),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_open_todos(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM todos WHERE done = 0").fetchall()
    return [dict(row) for row in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Roadmap graph construction

def build_roadmap(
    frs: list[dict[str, Any]],
    todos: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Build the roadmap graph structure from active FRs (+ optional todos).

    Returns a dict with: nodes, fr_edges, project_edges, todo_refs, quarters.
    """
    todos = todos or []
    today = today or date.today()
    active_ids = {fr["id"] for fr in frs}

    nodes: list[dict[str, Any]] = []
    fr_edges: list[dict[str, str]] = []
    project_pairs: set[tuple[str, str]] = set()
    quarters: dict[str, list[str]] = {}

    for fr in frs:
        quarter = assign_quarter(fr, today=today)
        raw_project = (fr.get("projects") or "").split(",")[0].strip()
        project = canonicalize_project(raw_project)
        deps = extract_fr_dependencies(fr)
        node = {
            "id": fr["id"],
            "title": fr.get("title"),
            "project": project,
            "state": fr.get("state"),
            "risk": fr.get("risk"),
            "quarter": quarter,
            "depends_on": deps,
        }
        nodes.append(node)
        quarters.setdefault(quarter, []).append(fr["id"])

        for dep_id in deps:
            fr_edges.append({"from": fr["id"], "to": dep_id})
            if dep_id in active_ids:
                dep_project = next(
                    (
                        canonicalize_project((f.get("projects") or "").split(",")[0].strip())
                        for f in frs
                        if f["id"] == dep_id
                    ),
                    UNMAPPED_PROJECT,
                )
                if dep_project and dep_project != project:
                    project_pairs.add((project, dep_project))

    todo_refs: list[dict[str, Any]] = []
    for todo in todos:
        for fr_id in extract_todo_fr_references(todo.get("text")):
            todo_refs.append({
                "todo_id": todo.get("id"),
                "todo_project": todo.get("project"),
                "fr_id": fr_id,
                "fr_active": fr_id in active_ids,
            })

    project_edges = [{"from": a, "to": b} for a, b in sorted(project_pairs)]

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nodes": nodes,
        "fr_edges": fr_edges,
        "project_edges": project_edges,
        "todo_refs": todo_refs,
        "quarters": quarters,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point

def generate_roadmap(
    output_path: Path | None = None,
    fr_connection: sqlite3.Connection | None = None,
    todos_db_path: Path | None = None,
) -> dict[str, Any]:
    """Generate the roadmap JSON artifact.

    `fr_connection` and `todos_db_path` are injectable so tests can run this
    end-to-end against a seeded fixture DB instead of the real (encrypted)
    `fr_ledgers.db` / `manifest_todos.db` paths.
    """
    owns_fr_conn = False
    if fr_connection is None:
        from init_fr_db import get_connection, init_db  # noqa: E402

        init_db()
        fr_connection = get_connection()
        owns_fr_conn = True
    try:
        frs = fetch_active_frs(fr_connection)
    finally:
        if owns_fr_conn:
            fr_connection.close()

    todos_path = todos_db_path if todos_db_path is not None else MANIFEST_TODOS_DB_PATH
    todos: list[dict[str, Any]] = []
    if todos_path.is_file():
        todo_conn = sqlite3.connect(str(todos_path))
        todo_conn.row_factory = sqlite3.Row
        try:
            todos = fetch_open_todos(todo_conn)
        finally:
            todo_conn.close()

    roadmap = build_roadmap(frs, todos)

    output_path = output_path or DEFAULT_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(roadmap, indent=2, ensure_ascii=False), encoding="utf-8")
    return roadmap


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the cross-project roadmap JSON artifact")
    parser.add_argument("--out", default=None, help="Output path (default: src/data/roadmap.json)")
    args = parser.parse_args()
    out_path = Path(args.out) if args.out else None
    roadmap = generate_roadmap(out_path)
    print(f"[roadmap_generator] Wrote roadmap with {len(roadmap['nodes'])} nodes to "
          f"{out_path or DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
