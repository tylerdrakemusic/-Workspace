#!/usr/bin/env python3
"""
⊕ Stale Vulnerability Deduplicator — tools/stale_vuln_dedup.py

Re-verifies all open vulnerability findings and marks stale/duplicate ones.

Staleness criteria (all three must hold for a finding to remain "open"):
  1. File at file_path exists on disk
  2. line_number is within the file's actual line count (skipped when line_number=0)
  3. An OWASP pattern is still detectable at that line (skipped when line_number=0)

Deduplication:
  Same file_path + line_number + description → keep oldest (lowest created_at),
  mark all others stale with override_note='auto-stale: exact-duplicate'.

Modes:
  --dry-run  (default): print candidate table, zero DB writes
  --apply: write changes to DB (status='stale', override_note='auto-stale: …'),
           write a row to scan_run_log

Usage:
  C:\\G\\python.exe tools/stale_vuln_dedup.py             # dry-run
  C:\\G\\python.exe tools/stale_vuln_dedup.py --dry-run   # explicit dry-run
  C:\\G\\python.exe tools/stale_vuln_dedup.py --apply     # apply to DB

FR-20260530-stale-vuln-dedup-report
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

# ── OWASP patterns for lightweight line-content check ─────────────────────────
# Mirrors security_dashboard.SCAN_PATTERNS for consistency.
_OWASP_PATTERNS: list[re.Pattern] = [
    re.compile(r'execute\s*\(\s*f["\']', re.IGNORECASE),
    re.compile(r'\beval\s*\('),
    re.compile(r'\bexec\s*\('),
    re.compile(r'shell\s*=\s*True'),
    re.compile(r'hashlib\.md5\s*\('),
    re.compile(r'hashlib\.sha1\s*\('),
    re.compile(r'(?:api_key|password|secret|token)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE),
    re.compile(r'pickle\.loads?\s*\('),
    re.compile(r'http://(?!localhost|127\.0\.0\.1)'),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Core predicates ───────────────────────────────────────────────────────────

def check_file_exists(file_path: str | None) -> bool:
    """True if file exists on disk. Empty/None path always returns True."""
    if not file_path:
        return True
    return Path(file_path).exists()


def check_line_in_range(file_path: str, line_number: int) -> bool:
    """True if line_number is within the file's actual line count.

    line_number=0 (safety findings) is always considered in-range.
    """
    if line_number == 0:
        return True
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
        return line_number <= len(lines)
    except (OSError, IOError):
        return False


def check_pattern_at_line(file_path: str, line_number: int) -> bool:
    """True if any OWASP pattern is detectable at the given line.

    line_number=0 (safety findings) always returns True (no line to check).
    """
    if line_number == 0:
        return True
    try:
        lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
        if line_number > len(lines):
            return False
        line_text = lines[line_number - 1]
        return any(p.search(line_text) for p in _OWASP_PATTERNS)
    except (OSError, IOError):
        return False


def classify_vuln(vuln: dict[str, Any]) -> str | None:
    """Return the stale reason, or None if the finding is still valid.

    Returns: 'file_gone' | 'line_shifted' | 'pattern_gone' | None
    """
    fp = vuln.get("file_path") or ""
    ln = int(vuln.get("line_number") or 0)

    if not check_file_exists(fp):
        return "file_gone"

    if ln > 0 and not check_line_in_range(fp, ln):
        return "line_shifted"

    if ln > 0 and not check_pattern_at_line(fp, ln):
        return "pattern_gone"

    return None


# ── Deduplication ─────────────────────────────────────────────────────────────

def find_dedup_candidates(vulns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the newer duplicate vulns to mark stale.

    Groups by (file_path, line_number, description).
    Keeps the entry with the lowest created_at; marks all others.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for v in vulns:
        key = (
            v.get("file_path") or "",
            int(v.get("line_number") or 0),
            v.get("description") or "",
        )
        groups[key].append(v)

    to_mark: list[dict] = []
    for group in groups.values():
        if len(group) <= 1:
            continue
        # Sort ascending by created_at; first entry (oldest) is kept
        sorted_group = sorted(group, key=lambda x: x.get("created_at") or "")
        for dup in sorted_group[1:]:
            to_mark.append({**dup, "reason": "exact-duplicate"})

    return to_mark


# ── DB helpers ────────────────────────────────────────────────────────────────

def load_open_vulns(conn: Any) -> list[dict[str, Any]]:
    """Load all open vulnerabilities ordered by created_at ASC."""
    rows = conn.execute(
        """SELECT vuln_id, file_path, line_number, description, created_at,
                  category, severity, owasp_id, scan_date, status
           FROM vulnerabilities
           WHERE status = 'open'
           ORDER BY created_at ASC"""
    ).fetchall()
    return [dict(r) for r in rows]


def _apply_changes(
    conn: Any,
    stale_candidates: list[dict[str, Any]],
    dedup_candidates: list[dict[str, Any]],
) -> None:
    """Write stale status and notes to DB."""
    now = _now_iso()
    for v in stale_candidates:
        reason = v.get("reason", "auto-stale")
        conn.execute(
            "UPDATE vulnerabilities SET status='stale', override_note=?, remediated_at=? WHERE vuln_id=?",
            (f"auto-stale: {reason}", now, v["vuln_id"]),
        )
    for v in dedup_candidates:
        conn.execute(
            "UPDATE vulnerabilities SET status='stale', override_note=?, remediated_at=? WHERE vuln_id=?",
            ("auto-stale: exact-duplicate", now, v["vuln_id"]),
        )
    conn.commit()


def _write_sweep_log(conn: Any, result: dict[str, Any]) -> None:
    """Write a scan_run_log row summarising the sweep."""
    run_id = str(uuid.uuid4())
    fg = result["stale_file_gone"]
    ls = result["stale_line_shifted"]
    pg = result["stale_pattern_gone"]
    dd = result["deduped"]
    total = result["total_stale"]
    note = (
        f"stale sweep: {total} stale "
        f"({fg} file-gone, {ls} line-shifted, {pg} pattern-gone), "
        f"{dd} deduped"
    )
    conn.execute(
        """INSERT INTO scan_run_log
           (run_id, started_at, completed_at, projects_scanned, new_vulns_count,
            total_findings, bandit_exit_code, safety_exit_code, status, error_detail)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            run_id, _now_iso(), _now_iso(),
            json.dumps(["stale_sweep"]),
            0, total, 0, 0, "ok", note,
        ),
    )
    conn.commit()


# ── Main sweep function ───────────────────────────────────────────────────────

def run_sweep(conn: Any, *, dry_run: bool = True) -> dict[str, Any]:
    """Run the stale/dedup sweep and return a summary dict.

    Deduplication runs first on ALL open vulns so that the newer of an
    exact-duplicate pair is always tagged 'exact-duplicate' (not 'file_gone'),
    even when the file also happens to be missing.

    Keys: stale_file_gone, stale_line_shifted, stale_pattern_gone, deduped,
          total_stale, stale_candidates, dedup_candidates
    """
    vulns = load_open_vulns(conn)

    # Step 1: dedup over the full set — newer duplicates are set aside first
    dedup_candidates = find_dedup_candidates(vulns)
    dedup_ids = {v["vuln_id"] for v in dedup_candidates}

    # Step 2: classify the remaining (non-dedup) open vulns
    stale_by_reason: dict[str, list[dict]] = {
        "file_gone": [],
        "line_shifted": [],
        "pattern_gone": [],
    }

    for v in vulns:
        if v["vuln_id"] in dedup_ids:
            continue  # already handled as exact-duplicate
        reason = classify_vuln(v)
        if reason:
            stale_by_reason[reason].append({**v, "reason": reason})

    all_stale = (
        stale_by_reason["file_gone"]
        + stale_by_reason["line_shifted"]
        + stale_by_reason["pattern_gone"]
    )

    result: dict[str, Any] = {        "stale_file_gone": len(stale_by_reason["file_gone"]),
        "stale_line_shifted": len(stale_by_reason["line_shifted"]),
        "stale_pattern_gone": len(stale_by_reason["pattern_gone"]),
        "deduped": len(dedup_candidates),
        "total_stale": len(all_stale) + len(dedup_candidates),
        "stale_candidates": all_stale,
        "dedup_candidates": dedup_candidates,
    }

    if not dry_run:
        _apply_changes(conn, all_stale, dedup_candidates)
        _write_sweep_log(conn, result)

    return result


# ── CLI output helpers ────────────────────────────────────────────────────────

def _print_table(result: dict[str, Any]) -> None:
    all_candidates = result["stale_candidates"] + result["dedup_candidates"]
    if not all_candidates:
        print("  No stale or duplicate candidates found.")
        return

    header = f"{'vuln_id':<20} {'reason':<20} {'file_path':<55} {'line':>6}"
    print(f"\n{header}")
    print("-" * len(header))
    for v in all_candidates:
        fp = (v.get("file_path") or "")
        if len(fp) > 52:
            fp = "..." + fp[-49:]
        ln = v.get("line_number") or 0
        reason = v.get("reason", "exact-duplicate")
        print(f"  {v['vuln_id']:<18} {reason:<20} {fp:<55} {ln:>6}")


def _print_summary(result: dict[str, Any], *, applied: bool) -> None:
    tag = "[APPLIED]" if applied else "[DRY-RUN]"
    print(
        f"\n{tag} Stale sweep summary:\n"
        f"  {result['stale_file_gone']} stale (file-gone)\n"
        f"  {result['stale_line_shifted']} stale (line-shifted)\n"
        f"  {result['stale_pattern_gone']} stale (pattern-gone)\n"
        f"  {result['deduped']} exact-dupes collapsed\n"
        f"  Total: {result['total_stale']} candidates"
    )
    if applied:
        print("  DB updated. scan_run_log row written.")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="⊕ Stale Vulnerability Deduplicator")
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Print candidates only, no DB writes (default when neither flag given)",
    )
    parser.add_argument(
        "--apply", action="store_true", default=False,
        help="Apply changes: update DB, write scan_run_log",
    )
    args = parser.parse_args(argv)

    # --apply wins over --dry-run; if neither specified, default to dry-run
    dry_run = not args.apply

    from init_db import get_connection, init_db  # noqa: PLC0415
    init_db()
    conn = get_connection()

    try:
        result = run_sweep(conn, dry_run=dry_run)
        _print_table(result)
        _print_summary(result, applied=not dry_run)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
