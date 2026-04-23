#!/usr/bin/env python3
"""
⊕ FR Status Dashboard — workspace-wide view of in-flight Feature Requests.

Reads .github/FR_LEDGERS/FR-*.md, parses the Header key/values and the
Deliverable Tracker markdown table, and prints a grouped dashboard.

Usage:
    C:\\G\\python.exe tools/fr_status.py                    # human-readable dashboard
    C:\\G\\python.exe tools/fr_status.py --json             # machine-readable dump
    C:\\G\\python.exe tools/fr_status.py --agent <name>     # filter by agent ownership
    C:\\G\\python.exe tools/fr_status.py --state <STATE>    # filter by FR state
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = PROJECT_ROOT / ".github" / "FR_LEDGERS"

_SKIP = {"_TEMPLATE.md", "README.md"}

# Matches lines like  "- **FR ID:** FR-20260423-foo"  and extracts ("FR ID","FR-20260423-foo").
_HEADER_RE = re.compile(r"^\s*-\s+\*\*([^:*]+):\*\*\s+(.*?)\s*$")


def _parse_header(text: str) -> dict:
    """Extract key/value pairs from the ## Header section."""
    out: dict[str, str] = {}
    in_header = False
    for line in text.splitlines():
        if line.strip().startswith("## Header"):
            in_header = True
            continue
        if in_header:
            if line.startswith("## ") or line.startswith("### "):
                break
            m = _HEADER_RE.match(line)
            if m:
                out[m.group(1).strip()] = m.group(2).strip()
    return out


def _parse_tracker(text: str) -> list[dict]:
    """Extract rows from the ### Deliverable Tracker markdown table."""
    lines = text.splitlines()
    rows: list[dict] = []
    in_section = False
    header: list[str] | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### Deliverable Tracker") or stripped == "Deliverable Tracker":
            in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("### ") or stripped.startswith("## "):
            break
        if not stripped.startswith("|"):
            continue
        # Split pipe-cells, drop leading/trailing empties.
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        # Skip separator row (---).
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) < len(header):
            continue
        row = dict(zip(header, cells))
        # Only keep actual deliverable rows (# cell looks like AC<n> or similar).
        if row.get("#", "").startswith("AC") or re.match(r"^\d+$", row.get("#", "")):
            rows.append(row)
    return rows


def parse_ledger(path: Path) -> dict:
    """Parse a single FR ledger markdown file."""
    text = path.read_text(encoding="utf-8")
    header = _parse_header(text)
    tracker = _parse_tracker(text)
    return {
        "file": str(path),
        "fr_id": header.get("FR ID", path.stem),
        "title": header.get("Title", ""),
        "type": header.get("Type", ""),
        "risk": header.get("Risk", ""),
        "projects": header.get("Projects", ""),
        "state": header.get("State", "OPEN"),
        "branch": header.get("Branch", ""),
        "opened": header.get("Opened", ""),
        "last_updated": header.get("Last updated", ""),
        "closed": header.get("Closed", ""),
        "deliverables": tracker,
    }


def collect_all() -> list[dict]:
    """Return every parsed FR ledger (skipping template/readme)."""
    if not LEDGER_DIR.is_dir():
        return []
    out: list[dict] = []
    for md in sorted(LEDGER_DIR.glob("FR-*.md")):
        if md.name in _SKIP:
            continue
        out.append(parse_ledger(md))
    return out


def _filter(frs: list[dict], *, agent: str | None, state: str | None) -> list[dict]:
    filtered = []
    for fr in frs:
        if state and fr["state"].upper() != state.upper():
            continue
        if agent:
            owners = {d.get("Owner", "") for d in fr["deliverables"]}
            if agent not in owners:
                continue
        filtered.append(fr)
    return filtered


def render_dashboard(frs: list[dict]) -> str:
    """Human-readable grouped dashboard."""
    lines: list[str] = []
    lines.append(f"⊕ FR Status Dashboard ({len(frs)} active FRs)")
    lines.append("=" * 64)
    if not frs:
        lines.append("(no FR ledgers found)")
        return "\n".join(lines)

    # Group by State.
    by_state: dict[str, list[dict]] = {}
    for fr in frs:
        by_state.setdefault(fr["state"] or "UNKNOWN", []).append(fr)

    for state in sorted(by_state.keys()):
        bucket = by_state[state]
        lines.append("")
        lines.append(f"{state} — {len(bucket)}")
        for fr in bucket:
            title = fr["title"] or "(no title)"
            lines.append(f'  {fr["fr_id"]} — "{title[:80]}"')
            if fr["branch"]:
                lines.append(f"    Branch: {fr['branch']}")
            for d in fr["deliverables"]:
                num = d.get("#", "??")
                name = d.get("Deliverable", "")
                status = d.get("Status", "?")
                owner = d.get("Owner", "")
                # Pad name for alignment — codepoint-based is fine here.
                lines.append(f"    [{num}] {name[:38]:<38} — {status} ({owner})")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="⊕ FR Status Dashboard")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--agent", metavar="NAME", help="Filter to FRs where NAME owns a deliverable")
    parser.add_argument("--state", metavar="STATE", help="Filter by FR state (e.g. BRANCHED)")
    args = parser.parse_args()

    frs = collect_all()
    frs = _filter(frs, agent=args.agent, state=args.state)

    if args.json:
        print(json.dumps(frs, indent=2, ensure_ascii=False))
        return

    # stdout may be cp1252 on Windows; reconfigure for sigils.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(render_dashboard(frs))


if __name__ == "__main__":
    main()
