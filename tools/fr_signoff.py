#!/usr/bin/env python3
"""
⊕ FR Signoff — transition a merged/soaking FR ledger to SIGNED_OFF.

Stamps `Signed off at` in the header, flips `State` to SIGNED_OFF, appends an
append-only event log entry, and (optionally) regenerates the FR dashboard.

Usage:
    C:\\G\\python.exe tools/fr_signoff.py <FR-ID> [--note "short reason"] [--backfill]

    --backfill  permit signoff even if current state is not MERGED/SOAKING
                (used by the legacy-ledger backfill pass; also stamps a
                best-effort Merged at when missing).

Called by:
    - fr_portal_server.py on POST /fr/signoff/<FR-ID>
    - direct CLI for manual/agent signoff
    - tools/fr_backfill_legacy.py (bulk historical backfill)
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = PROJECT_ROOT / ".github" / "FR_LEDGERS"

_HEADER_LINE_RE = re.compile(r"^(\s*-\s+\*\*([^:*]+):\*\*)\s+(.*?)\s*$")


def _find_ledger(fr_id: str) -> Path:
    direct = LEDGER_DIR / f"{fr_id}.md"
    if direct.is_file():
        return direct
    matches = list(LEDGER_DIR.glob(f"{fr_id}*.md"))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SystemExit(f"FR ledger not found for id={fr_id}")
    raise SystemExit(f"Ambiguous FR id {fr_id}; matches: {[m.name for m in matches]}")


def _split_header(text: str) -> tuple[list[str], int, int]:
    """Return (lines, header_start_idx, header_end_idx) — bounds of the header block."""
    lines = text.splitlines()
    header_start = None
    header_end = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## Header"):
            header_start = i + 1
            continue
        if header_start is not None and (line.startswith("### ") or line.startswith("## ")):
            header_end = i
            break
    if header_start is None:
        raise SystemExit("Ledger has no '## Header' section")
    if header_end is None:
        header_end = len(lines)
    return lines, header_start, header_end


def _header_get(lines: list[str], start: int, end: int, key: str) -> tuple[int, str] | tuple[None, None]:
    """Return (line_index, value) for a header key, or (None, None)."""
    for i in range(start, end):
        m = _HEADER_LINE_RE.match(lines[i])
        if m and m.group(2).strip() == key:
            return i, m.group(3).strip()
    return None, None


def _header_set(lines: list[str], start: int, end: int, key: str, value: str) -> None:
    """Update header key in place, or insert before the section end if missing."""
    idx, _ = _header_get(lines, start, end, key)
    if idx is not None:
        # Preserve prefix indentation/bullet.
        prefix_match = _HEADER_LINE_RE.match(lines[idx])
        prefix = prefix_match.group(1) if prefix_match else f"- **{key}:**"
        lines[idx] = f"{prefix} {value}"
    else:
        # Insert before the blank line trailing the header, or at end-1.
        insert_at = end
        while insert_at > start and not lines[insert_at - 1].strip():
            insert_at -= 1
        lines.insert(insert_at, f"- **{key}:** {value}")


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_event_log(text: str, entry: str) -> str:
    if "## Event Log" not in text:
        # Should not happen for template-compliant ledgers; append a section.
        return text.rstrip() + "\n\n## Event Log\n\n" + entry + "\n"
    # Insert just before the next "## " after Event Log, or at end.
    lines = text.splitlines()
    log_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## Event Log"):
            log_idx = i
            break
    next_section = len(lines)
    for j in range(log_idx + 1, len(lines)):
        if lines[j].startswith("## ") and not lines[j].startswith("## Event Log"):
            next_section = j
            break
    # Trim trailing blank lines inside the Event Log section.
    insert_at = next_section
    while insert_at > log_idx + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    block = ["", entry, ""]
    lines[insert_at:insert_at] = block
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def signoff(fr_id: str, note: str = "", *, backfill: bool = False,
            signoff_at: str | None = None, merged_at: str | None = None) -> dict:
    """Transition a ledger to SIGNED_OFF. Returns a summary dict."""
    path = _find_ledger(fr_id)
    original = path.read_text(encoding="utf-8")
    lines, start, end = _split_header(original)

    _, state_raw = _header_get(lines, start, end, "State")
    state_first = (state_raw or "").strip().upper().split()[0] if state_raw else ""

    legal_source_states = {"MERGED", "SOAKING"}
    if not backfill and state_first not in legal_source_states:
        raise SystemExit(
            f"{path.name}: current State is '{state_raw}'; "
            f"expected MERGED or SOAKING (use --backfill to override)."
        )

    now_iso = signoff_at or _iso_now()

    # Ensure Merged at is set (best-effort backfill from Closed or Last updated).
    _, merged_raw = _header_get(lines, start, end, "Merged at")
    if not merged_raw or merged_raw in {"—", "-", "pending", ""}:
        if merged_at:
            _header_set(lines, start, end, "Merged at", merged_at)
        else:
            # Fallback: use Closed date, then Last updated.
            _, closed_raw = _header_get(lines, start, end, "Closed")
            _, lastup_raw = _header_get(lines, start, end, "Last updated")
            fallback = None
            for candidate in (closed_raw, lastup_raw):
                if candidate and candidate not in {"—", "-", "pending", ""}:
                    fallback = candidate
                    break
            if fallback:
                _header_set(lines, start, end, "Merged at", fallback)

    # Stamp state + signoff timestamp + last updated.
    _header_set(lines, start, end, "State", "SIGNED_OFF")
    _header_set(lines, start, end, "Signed off at", now_iso)
    _header_set(lines, start, end, "Last updated", now_iso.split("T")[0])

    new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")

    event = (
        f"### {now_iso} — tyler (via fr_signoff.py)\n\n"
        f"**Event:** state-transition\n\n"
        f"**Summary:** {'Retroactive signoff backfilled' if backfill else 'Tyler signed off after soak'} "
        f"→ SIGNED_OFF\n\n"
        f"**Details:**\n"
        f"- Previous state: {state_raw or '(unknown)'}\n"
        f"- Signed off at: {now_iso}\n"
        + (f"- Note: {note}\n" if note else "")
        + "\n**Next:** FR drops off the active board; ledger retained for audit."
    )
    new_text = _append_event_log(new_text, event)

    path.write_text(new_text, encoding="utf-8")

    return {
        "fr_id": fr_id,
        "ledger": str(path),
        "previous_state": state_raw,
        "new_state": "SIGNED_OFF",
        "signed_off_at": now_iso,
        "backfill": backfill,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="⊕ FR Signoff")
    parser.add_argument("fr_id", help="FR identifier (e.g. FR-20260423-fr-portal-soak-gate)")
    parser.add_argument("--note", default="", help="Optional short note included in the event log")
    parser.add_argument("--backfill", action="store_true",
                        help="Allow signoff from a non-MERGED/SOAKING state (legacy backfill)")
    parser.add_argument("--at", default=None,
                        help="Override the signoff timestamp (ISO-8601 UTC, e.g. 2026-04-22T00:00:00Z)")
    parser.add_argument("--merged-at", default=None,
                        help="Backfill Merged at with this value if missing (ISO-8601)")
    parser.add_argument("--regenerate-dashboard", action="store_true",
                        help="After signoff, run tools/fr_dashboard.py to refresh HTML")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    result = signoff(
        args.fr_id,
        note=args.note,
        backfill=args.backfill,
        signoff_at=args.at,
        merged_at=args.merged_at,
    )

    print(f"✓ {result['fr_id']}: {result['previous_state']} → {result['new_state']} @ {result['signed_off_at']}")

    if args.regenerate_dashboard:
        import subprocess
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "tools" / "fr_dashboard.py")],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode == 0:
            print("✓ dashboard regenerated")
        else:
            print("! dashboard regen failed:", r.stderr[:300], file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
