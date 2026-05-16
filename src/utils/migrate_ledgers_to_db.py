"""
migrate_ledgers_to_db.py — One-time importer: .md ledger files → fr_ledgers.db

Parses all FR-*.md files in .github/FR_LEDGERS/ and inserts them into the
fr_ledgers.db database.  Run once; idempotent (skips existing FR IDs).

Usage:
    C:\\G\\python.exe f:\\⊕Workspace\\src\\utils\\migrate_ledgers_to_db.py [--dry-run]
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing init_fr_db from the same utils/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from init_fr_db import get_connection, init_db  # noqa: E402

LEDGERS_DIR = Path(__file__).resolve().parents[2] / ".github" / "FR_LEDGERS"
REGISTRY_FILE = Path(__file__).resolve().parents[2] / ".github" / "FEATURE_REQUESTS.md"

_HEADER_FIELD = re.compile(r"^\s*-\s*\*\*(.+?):\*\*\s*(.*)")
_EVENT_HEADING = re.compile(
    r"^###\s+(?P<ts>[0-9T:\-Z.]+)\s+[—–-]\s+(?P<agent>.+)"
)
_BOLD_FIELD = re.compile(r"^\*\*(?P<key>[^*]+):\*\*\s*(?P<val>.*)")


def _parse_header(text: str) -> dict[str, str]:
    header: dict[str, str] = {}
    in_header = False
    for line in text.splitlines():
        if line.strip() == "## Header":
            in_header = True
            continue
        if in_header and line.startswith("## "):
            break
        if in_header:
            m = _HEADER_FIELD.match(line)
            if m:
                header[m.group(1).strip()] = m.group(2).strip()
    return header


def _parse_events(text: str) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    in_log = False
    current: dict[str, str] | None = None
    detail_lines: list[str] = []
    capturing_details = False

    for line in text.splitlines():
        if line.strip() == "## Event Log":
            in_log = True
            continue
        if in_log and line.startswith("## "):
            break
        if not in_log:
            continue

        heading_m = _EVENT_HEADING.match(line)
        if heading_m:
            if current is not None:
                if detail_lines:
                    current["details"] = "\n".join(detail_lines).strip()
                events.append(current)
            current = {
                "ts": heading_m.group("ts"),
                "agent": heading_m.group("agent").strip(),
                "event_type": "",
                "summary": "",
                "details": "",
                "next_action": "",
            }
            detail_lines = []
            capturing_details = False
            continue

        if current is None:
            continue

        bold_m = _BOLD_FIELD.match(line.strip())
        if bold_m:
            key = bold_m.group("key").strip().lower()
            val = bold_m.group("val").strip()
            if key == "event":
                current["event_type"] = val
                capturing_details = False
            elif key == "summary":
                current["summary"] = val
                capturing_details = False
            elif key == "details":
                capturing_details = True
                if val:
                    detail_lines.append(val)
            elif key == "next":
                current["next_action"] = val
                capturing_details = False
        elif capturing_details and line.strip():
            detail_lines.append(line.strip())

    if current is not None:
        if detail_lines:
            current["details"] = "\n".join(detail_lines).strip()
        events.append(current)

    return events


def _parse_artifacts(text: str) -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    in_art = False
    for line in text.splitlines():
        if line.strip() == "## Artifacts":
            in_art = True
            continue
        if in_art and line.startswith("## "):
            break
        if not in_art:
            continue
        stripped = line.strip()
        if stripped.startswith("- **"):
            m = re.match(r"-\s+\*\*(.+?):\*\*\s+(.*)", stripped)
            if m:
                label = m.group(1).strip()
                val = m.group(2).strip()
                if val and val not in ("-", "—", "pending", ""):
                    artifacts.append({
                        "artifact_type": "note",
                        "label": label,
                        "path_or_url": val,
                    })
    return artifacts


def _parse_registry() -> dict[str, dict[str, str]]:
    """Parse FEATURE_REQUESTS.md into {fr_id: {title, type, projects, state, branch, prs, owner, opened, updated}}"""
    result: dict[str, dict[str, str]] = {}
    if not REGISTRY_FILE.exists():
        return result
    row_re = re.compile(
        r"^\|\s*(?P<id>FR-[\w-]+)\s*\|"
        r"\s*(?P<title>[^|]*?)\s*\|"
        r"\s*(?P<type>[^|]*?)\s*\|"
        r"\s*(?P<projects>[^|]*?)\s*\|"
        r"\s*(?P<state>[^|]*?)\s*\|"
        r"\s*(?P<branch>[^|]*?)\s*\|"
        r"\s*(?P<prs>[^|]*?)\s*\|"
        r"\s*(?P<owner>[^|]*?)\s*\|"
        r"\s*(?P<opened>[^|]*?)\s*\|"
        r"\s*(?P<updated>[^|]*?)\s*\|",
        re.MULTILINE,
    )
    text = REGISTRY_FILE.read_text(encoding="utf-8")
    for m in row_re.finditer(text):
        fr_id = m.group("id").strip()
        result[fr_id] = {
            "title": m.group("title").strip(),
            "type": m.group("type").strip(),
            "projects": m.group("projects").strip(),
            "state": m.group("state").strip(),
            "branch": m.group("branch").strip(),
            "prs": m.group("prs").strip(),
            "owner": m.group("owner").strip(),
            "opened": m.group("opened").strip(),
            "updated": m.group("updated").strip(),
        }
    return result


def migrate(dry_run: bool = False) -> None:
    if not LEDGERS_DIR.exists():
        print(f"[migrate] Ledgers directory not found: {LEDGERS_DIR}", file=sys.stderr)
        sys.exit(1)

    ledger_files = sorted(LEDGERS_DIR.glob("FR-*.md"))
    print(f"[migrate] Found {len(ledger_files)} ledger files")

    registry = _parse_registry()
    print(f"[migrate] Found {len(registry)} registry rows")

    if not dry_run:
        init_db()
        conn = get_connection()
    else:
        conn = None

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    imported = 0
    skipped = 0
    errors: list[str] = []

    for path in ledger_files:
        try:
            text = path.read_text(encoding="utf-8")
            header = _parse_header(text)
            fr_id = header.get("FR ID") or path.stem

            if not fr_id or not fr_id.startswith("FR-"):
                print(f"[migrate] Skip (no valid ID): {path.name}")
                skipped += 1
                continue

            # Prefer registry data for structured fields; fall back to header
            reg = registry.get(fr_id, {})
            title = reg.get("title") or header.get("Title", path.stem)
            fr_type = reg.get("type") or header.get("Type", "chore")
            projects = reg.get("projects") or header.get("Projects", "")
            state = reg.get("state") or header.get("State", "ARCHIVED")
            branch = reg.get("branch") or header.get("Branch", "")
            prs_val = reg.get("prs") or header.get("PRs", "")
            owner = reg.get("owner") or header.get("Owner", "")
            opened = reg.get("opened") or header.get("Opened", now[:10])
            updated = reg.get("updated") or header.get("Last updated", now[:10])
            risk = header.get("Risk", "")
            merged_at = header.get("Merged at") if header.get("Merged at") not in ("—", "-", "", None) else None
            signed_off_at = header.get("Signed off at") if header.get("Signed off at") not in ("—", "-", "", None) else None
            cycle_timer = header.get("Cycle timer") if header.get("Cycle timer") not in ("—", "-", "pending", "", None) else None

            # Normalise date strings to include time component
            if opened and len(opened) == 10:
                opened = opened + "T00:00:00Z"
            if updated and len(updated) == 10:
                updated = updated + "T00:00:00Z"

            events = _parse_events(text)
            artifacts = _parse_artifacts(text)

            if dry_run:
                print(f"[dry-run] {fr_id:50s} state={state:20s} events={len(events):3d} artifacts={len(artifacts):2d}")
                imported += 1
                continue

            # Skip if already in DB
            existing = conn.execute("SELECT id FROM feature_requests WHERE id=?", (fr_id,)).fetchone()
            if existing:
                skipped += 1
                continue

            conn.execute(
                """INSERT INTO feature_requests
                   (id, title, type, risk, projects, state, branch, prs, owner,
                    opened_at, updated_at, merged_at, signed_off_at, cycle_timer_run_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (fr_id, title, fr_type, risk, projects, state, branch, prs_val,
                 owner, opened, updated, merged_at, signed_off_at, cycle_timer),
            )

            for ev in events:
                conn.execute(
                    "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary, details, next_action) VALUES (?,?,?,?,?,?,?)",
                    (fr_id, ev["ts"], ev["agent"], ev["event_type"],
                     ev["summary"], ev.get("details"), ev.get("next_action")),
                )

            for art in artifacts:
                conn.execute(
                    "INSERT INTO fr_artifacts (fr_id, ts, artifact_type, label, path_or_url) VALUES (?,?,?,?,?)",
                    (fr_id, now, art["artifact_type"], art["label"], art.get("path_or_url")),
                )

            conn.commit()
            imported += 1

        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            print(f"[migrate] ERROR {path.name}: {exc}", file=sys.stderr)

    if conn:
        conn.close()

    print(f"\n[migrate] Done: {imported} imported, {skipped} skipped, {len(errors)} errors")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    migrate(dry_run=a.dry_run)
