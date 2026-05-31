#!/usr/bin/env python3
"""
⊕ Staleness Auditor — tools/staleness_auditor.py

Two-category workspace health check:

  1. Portal dashboard HTML freshness — reads all dashboard specs via
     dashboard_registry.build_manifest(), checks each output file's mtime.
     Thresholds:  warn  >= 2 h  (WARN_SECS)
                  stale >= 4 h  (STALE_SECS)

  2. Stuck FRs — reads fr_ledgers.db for active FRs whose updated_at is
     >= 48 h ago in any non-terminal state.  (STUCK_SECS)

Outputs:
  - Colored CLI table (dashboards section + stuck FRs section)
  - reports/staleness_audit.json  (structured findings for discovery agent)

Exit codes:
  0 = all clean
  1 = any warn / stale dashboard or stuck FR found

Usage:
    C:\\G\\python.exe tools/staleness_auditor.py
    C:\\G\\python.exe tools/staleness_auditor.py --no-open
    C:\\G\\python.exe tools/staleness_auditor.py --json   # machine-readable summary

FR-20260530-portal-staleness-auditor
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

WARN_SECS: int = 2 * 60 * 60    # 2 h
STALE_SECS: int = 4 * 60 * 60   # 4 h
STUCK_SECS: int = 48 * 60 * 60  # 48 h

# Active (non-terminal) states — any FR in one of these is eligible for
# stuck detection.  Mirrors ACTIVE_STATES in fr_cli.py.
ACTIVE_STATES: frozenset[str] = frozenset({
    "OPEN", "TRIAGED", "BRANCHED", "IN_PROGRESS",
    "FUNCTIONAL_QA", "ARCHITECTURE_REVIEW",
    "REVIEW_REQUESTED", "AUTO_REVIEWED", "TYLER_APPROVED",
    "CHANGES_REQUESTED", "SOAKING", "BRANCH_CHECKED_OUT",
})

# Kept for import compatibility and test assertions.
TERMINAL_STATES: frozenset[str] = frozenset({
    "MERGED", "SIGNED_OFF", "ARCHIVED", "CLOSED", "DONE",
})

# Dashboard types that produce a static output file we can mtime-check.
_STATIC_TYPES: frozenset[str] = frozenset({"static_html", "living_html"})

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_OUT = PROJECT_ROOT / "reports" / "staleness_audit.json"

# ANSI colour helpers (no extra deps)
_RESET = "\033[0m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_CYAN = "\033[36m"
_BOLD = "\033[1m"
_DIM = "\033[2m"


def _color(text: str, code: str) -> str:
    """Wrap text in ANSI colour code when stdout is a tty."""
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{_RESET}"


# ── Dashboard freshness ───────────────────────────────────────────────────────

def _fmt_age(secs: float) -> str:
    """Human-readable age string."""
    if secs < 60:
        return f"{int(secs)}s"
    if secs < 3600:
        return f"{secs / 60:.0f}m"
    if secs < 86400:
        return f"{secs / 3600:.1f}h"
    return f"{secs / 86400:.1f}d"


def classify_dashboard(dash: dict[str, Any]) -> dict[str, Any]:
    """Return a classification dict for one dashboard entry.

    Keys: id, title, project, type, status, age_secs, age_label, cli
    status: "fresh" | "warn" | "stale" | "missing"
    """
    output_abs = dash.get("output_abs")
    if not output_abs or not Path(output_abs).is_file():
        return {
            "id": dash.get("id", "?"),
            "title": dash.get("title", "?"),
            "project": dash.get("project", "?"),
            "type": dash.get("type", "?"),
            "status": "missing",
            "age_secs": None,
            "age_label": "never generated",
            "cli": dash.get("cli", ""),
        }

    age_secs = time.time() - Path(output_abs).stat().st_mtime
    if age_secs >= STALE_SECS:
        status = "stale"
    elif age_secs >= WARN_SECS:
        status = "warn"
    else:
        status = "fresh"

    return {
        "id": dash.get("id", "?"),
        "title": dash.get("title", "?"),
        "project": dash.get("project", "?"),
        "type": dash.get("type", "?"),
        "status": status,
        "age_secs": age_secs,
        "age_label": _fmt_age(age_secs),
        "cli": dash.get("cli", ""),
    }


def scan_dashboards(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify all static/living_html dashboards in the manifest."""
    results = []
    for dash in manifest.get("dashboards", []):
        if dash.get("type") not in _STATIC_TYPES:
            continue
        results.append(classify_dashboard(dash))
    return results


# ── Stuck FR detection ────────────────────────────────────────────────────────

def _parse_updated_at(ts: str) -> float:
    """Parse ISO timestamp (UTC) → Unix epoch seconds."""
    # Handles both "2026-05-30T12:00:00Z" and "2026-05-30T12:00:00+00:00"
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts).timestamp()


def scan_stuck_frs(conn: Any = None) -> list[dict[str, Any]]:
    """Return FRs in active states that have not been updated for >= STUCK_SECS.

    Parameters
    ----------
    conn:
        Optional DB connection (injected in tests).  If None, opens the real
        fr_ledgers.db via init_fr_db.get_connection().
    """
    close_after = False
    if conn is None:
        sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))
        try:
            from init_fr_db import get_connection, init_db  # type: ignore
            init_db()
            conn = get_connection()
            close_after = True
        except Exception as exc:
            print(
                f"  [warn] Could not open fr_ledgers.db: {exc}",
                file=sys.stderr,
            )
            return []

    active_placeholders = ",".join("?" * len(ACTIVE_STATES))
    # Only flag FRs in known active states — everything else (DONE, MERGED, etc.) is terminal.
    query = f"""
        SELECT id, title, state, updated_at
        FROM feature_requests
        WHERE state IN ({active_placeholders})
        ORDER BY updated_at ASC
    """  # nosec B608 — placeholders built from internal frozenset, not user input
    try:
        rows = conn.execute(query, list(ACTIVE_STATES)).fetchall()
    finally:
        if close_after:
            conn.close()

    stuck = []
    for row in rows:
        try:
            updated_epoch = _parse_updated_at(row["updated_at"])
        except (ValueError, TypeError):
            continue
        age_secs = time.time() - updated_epoch
        if age_secs < STUCK_SECS:
            continue
        stuck.append({
            "id": row["id"],
            "title": row["title"] or "",
            "state": row["state"],
            "hours_stuck": round(age_secs / 3600, 1),
            "updated_at": row["updated_at"],
        })

    return stuck


# ── Report writer ─────────────────────────────────────────────────────────────

def write_report(
    dashboards: list[dict[str, Any]],
    stuck_frs: list[dict[str, Any]],
    out_path: Path = REPORT_OUT,
) -> None:
    """Write structured JSON report to *out_path*."""
    warn_count = sum(1 for d in dashboards if d["status"] == "warn")
    stale_count = sum(1 for d in dashboards if d["status"] == "stale")
    missing_count = sum(1 for d in dashboards if d["status"] == "missing")

    all_clean = (warn_count + stale_count + missing_count + len(stuck_frs)) == 0

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboards": dashboards,
        "stuck_frs": stuck_frs,
        "summary": {
            "total_dashboards": len(dashboards),
            "fresh": sum(1 for d in dashboards if d["status"] == "fresh"),
            "warn": warn_count,
            "stale": stale_count,
            "missing": missing_count,
            "stuck_frs": len(stuck_frs),
            "all_clean": all_clean,
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


# ── CLI rendering ─────────────────────────────────────────────────────────────

_STATUS_COLOR: dict[str, str] = {
    "fresh": _GREEN,
    "warn": _YELLOW,
    "stale": _RED,
    "missing": _RED,
}


def _render_table(dashboards: list[dict], stuck_frs: list[dict]) -> None:
    """Print a human-readable summary to stdout."""
    print(_color("⊕ Staleness Auditor", _BOLD + _CYAN))
    print(_color(f"  Run at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", _DIM))
    print()

    # ── Dashboard section ──
    print(_color("Dashboard Freshness", _BOLD))
    col_w = (40, 15, 12, 8)
    header = (
        f"  {'ID':<{col_w[0]}}  {'PROJECT':<{col_w[1]}}  {'AGE':<{col_w[2]}}  {'STATUS':<{col_w[3]}}"
    )
    print(_color(header, _DIM))
    print(_color("  " + "-" * (sum(col_w) + 8), _DIM))

    if not dashboards:
        print("  (no static dashboards found)")
    else:
        for d in dashboards:
            status = d["status"]
            color = _STATUS_COLOR.get(status, "")
            age = d["age_label"] or "—"
            row = (
                f"  {d['id']:<{col_w[0]}}  {d['project']:<{col_w[1]}}  "
                f"{age:<{col_w[2]}}  {status:<{col_w[3]}}"
            )
            print(_color(row, color) if status != "fresh" else row)

    print()

    # ── Stuck FR section ──
    print(_color("Stuck Feature Requests (>= 48 h inactive)", _BOLD))
    fr_col_w = (50, 25, 12)
    fr_header = f"  {'ID':<{fr_col_w[0]}}  {'STATE':<{fr_col_w[1]}}  {'HOURS STUCK':<{fr_col_w[2]}}"
    print(_color(fr_header, _DIM))
    print(_color("  " + "-" * (sum(fr_col_w) + 6), _DIM))

    if not stuck_frs:
        print("  (no stuck FRs)")
    else:
        for fr in stuck_frs:
            row = (
                f"  {fr['id']:<{fr_col_w[0]}}  {fr['state']:<{fr_col_w[1]}}  "
                f"{fr['hours_stuck']:<{fr_col_w[2]}}"
            )
            print(_color(row, _YELLOW))

    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """Run the staleness audit.  Returns 0 if clean, 1 if any issues found."""
    parser = argparse.ArgumentParser(description="⊕ Staleness Auditor")
    parser.add_argument(
        "--json", action="store_true",
        help="Print machine-readable JSON summary to stdout instead of table",
    )
    parser.add_argument(
        "--no-report", action="store_true",
        help="Skip writing reports/staleness_audit.json",
    )
    args = parser.parse_args(argv)

    # Bootstrap registry path
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    try:
        from dashboard_registry import build_manifest  # type: ignore
    except ImportError as exc:
        print(f"[staleness_auditor] Could not import dashboard_registry: {exc}", file=sys.stderr)
        return 2

    manifest = build_manifest()
    dashboards = scan_dashboards(manifest)
    stuck_frs = scan_stuck_frs()

    if not args.no_report:
        write_report(dashboards, stuck_frs)

    if args.json:
        summary = {
            "dashboards": dashboards,
            "stuck_frs": stuck_frs,
            "all_clean": (
                all(d["status"] == "fresh" for d in dashboards) and not stuck_frs
            ),
        }
        print(json.dumps(summary, indent=2))
    else:
        _render_table(dashboards, stuck_frs)
        if not args.no_report:
            print(_color(f"  Report written: {REPORT_OUT}", _DIM))

    has_issues = any(d["status"] != "fresh" for d in dashboards) or bool(stuck_frs)
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
