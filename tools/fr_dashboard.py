#!/usr/bin/env python3
"""
⊕ FR Board — Portal dashboard of active Feature Requests.

Reads `.github/FR_LEDGERS/FR-*.md` ledger headers plus the
`.github/FEATURE_REQUESTS.md` registry and renders a self-contained HTML
dashboard that surfaces:

  - Short description (title + one-line summary)
  - Current state
  - Branch name
  - Merged-to-main timestamp (if any)
  - Soak duration (time since merge, for SOAKING FRs)
  - Link to the ledger file

Active FRs (any state other than SIGNED_OFF / ARCHIVED / CLOSED) render at the
top. Archived FRs render in a collapsed section below so post-signoff history
stays auditable.

Usage:
    C:\\G\\python.exe tools/fr_dashboard.py              # generate HTML
    C:\\G\\python.exe tools/fr_dashboard.py --no-open    # generate only (default; no browser)
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from math import ceil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = PROJECT_ROOT / ".github" / "FR_LEDGERS"
REGISTRY = PROJECT_ROOT / ".github" / "FEATURE_REQUESTS.md"
OUT_FILE = PROJECT_ROOT / "reports" / "fr_dashboard.html"

_SKIP = {"_TEMPLATE.md", "README.md"}
_HEADER_RE = re.compile(r"^\s*-\s+\*\*([^:*]+):\*\*\s+(.*?)\s*$")

# States treated as "active" — show in the main board.
ACTIVE_STATES = {
    "OPEN", "TRIAGED", "BRANCHED", "IN_PROGRESS", "REVIEW_REQUESTED",
    "AUTO_REVIEWED", "BRANCH_CHECKED_OUT", "CHANGES_REQUESTED",
    "TYLER_APPROVED", "MERGED", "SOAKING",
}
# Terminal states — collapse into "Archived" bucket.
ARCHIVED_STATES = {"SIGNED_OFF", "ARCHIVED", "CLOSED"}

_PERF_NAME_RE = re.compile(r"^fr-cycle-(FR-[A-Za-z0-9][A-Za-z0-9-]*)$", re.IGNORECASE)


def _row_value(row, key: str):
    if hasattr(row, "keys") and key in row.keys():
        return row[key]
    if hasattr(row, "get"):
        return row.get(key)
    return None


def adapt_perf_run(row: dict) -> dict | None:
    """Adapt one perf run into an immutable FR cycle measurement or marker."""
    name = str(_row_value(row, "name") or "")
    match = _PERF_NAME_RE.match(name.strip())
    if not match:
        return None
    started_at = float(_row_value(row, "started_at") or 0)
    ended_raw = _row_value(row, "ended_at")
    ended_at = float(ended_raw) if ended_raw is not None else None
    duration = ended_at - started_at if ended_at is not None else None
    valid = duration is not None and duration > 0 and started_at > 0
    return {
        "fr_id": match.group(1),
        "run_id": str(_row_value(row, "run_id")),
        "project": str(_row_value(row, "project") or "⊕Workspace"),
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration if valid else None,
        "kind": "measurement" if valid else "active" if ended_at is None else "invalid",
        "status": str(_row_value(row, "status") or "unknown"),
        "data_quality": "valid" if valid else "invalid-duration" if ended_at is not None else "active",
    }


def canonicalize_perf_runs(rows: list[dict | None]) -> dict:
  """Reconcile duplicate immutable perf rows into one row per FR."""
  groups: dict[str, list[dict]] = {}
  counts = {"active": 0, "invalid": 0, "legacy": 0, "duplicates": 0, "measurements": 0}
  for row in rows:
    if row is None:
      continue
    groups.setdefault(row["fr_id"], []).append(row)
    if row.get("data_quality") == "invalid-duration":
      counts["invalid"] += 1
    if row.get("status", "").lower() == "legacy":
      counts["legacy"] += 1

  result = []
  for fr_id, group in sorted(groups.items()):
    group.sort(key=lambda row: (row["started_at"], row["run_id"]))
    base = dict(group[0])
    valid_ends = [
      row["ended_at"] for row in group
      if row.get("ended_at") is not None
      and row["ended_at"] > row["started_at"]
      and row["started_at"] > 0
    ]
    base["ended_at"] = max(valid_ends) if valid_ends else None
    base["duration_seconds"] = (
      base["ended_at"] - base["started_at"] if base["ended_at"] is not None else None
    )
    if base["duration_seconds"] is not None and base["duration_seconds"] > 0:
      base["kind"] = "measurement"
      base["data_quality"] = "valid"
      counts["measurements"] += 1
    elif any(row.get("ended_at") is None for row in group):
      base["kind"] = "active"
      base["data_quality"] = "active"
      counts["active"] += 1
    else:
      base["kind"] = "invalid"
      base["data_quality"] = "invalid-duration"
    base["duplicate_count"] = len(group) - 1
    counts["duplicates"] += base["duplicate_count"]
    base["provenance_run_ids"] = [row["run_id"] for row in group]
    base["provenance_statuses"] = [row.get("status", "unknown") for row in group]
    result.append(base)
  return {"rows": result, "counts": counts}


def filter_cycle_rows(rows: list[dict], project: str | None = None) -> list[dict]:
  """Filter chart rows by project while retaining active markers."""
  if not project or project == "all":
    return list(rows)
  return [row for row in rows if row.get("project") == project]


def cycle_summary(rows: list[dict]) -> dict:
  durations = sorted(
    row["duration_seconds"] for row in rows
    if row.get("kind") == "measurement" and row.get("duration_seconds") is not None
  )
  if not durations:
    return {"sample": 0, "median_seconds": None, "p75_seconds": None}
  median = durations[len(durations) // 2] if len(durations) % 2 else (
    durations[len(durations) // 2 - 1] + durations[len(durations) // 2]
  ) / 2
  p75 = durations[max(0, ceil(len(durations) * 0.75) - 1)]
  return {"sample": len(durations), "median_seconds": median, "p75_seconds": p75}


def collect_perf_runs(frs: list[dict], now: float | None = None) -> dict:
  """Read the immutable perf history and return the last 90 days of cycles."""
  src_path = str(PROJECT_ROOT / "src")
  if src_path not in sys.path:
    sys.path.insert(0, src_path)
  from utils.init_db import get_connection, use_worktree_aware_db_path

  use_worktree_aware_db_path(PROJECT_ROOT)
  conn = get_connection()
  try:
    raw = conn.execute(
      "SELECT run_id, name, agent, started_at, ended_at, status, detail "
      "FROM perf_runs WHERE name LIKE 'fr-cycle-%' ORDER BY started_at"
    ).fetchall()
  finally:
    conn.close()
  projects = {fr["fr_id"]: fr.get("projects") or "⊕Workspace" for fr in frs}
  adapted = []
  for row in raw:
    item = adapt_perf_run(row)
    if item is not None:
      item["project"] = projects.get(item["fr_id"], item["project"])
      adapted.append(item)
  cutoff = (now if now is not None else datetime.now(timezone.utc).timestamp()) - 90 * 86400
  return canonicalize_perf_runs([row for row in adapted if row["started_at"] >= cutoff])


# ── Parsing ──────────────────────────────────────────────────────────────

def _parse_header(text: str) -> dict:
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


def _first_paragraph_after(heading: str, text: str) -> str:
    """Return the first non-empty paragraph after a given heading line."""
    lines = text.splitlines()
    capture = False
    buf: list[str] = []
    for line in lines:
        if line.strip().startswith(heading):
            capture = True
            continue
        if capture:
            if line.startswith("## ") or line.startswith("### "):
                break
            if line.strip().startswith(">"):
                buf.append(line.strip().lstrip("> ").strip())
            elif not line.strip() and buf:
                break
            elif line.strip() and not line.strip().startswith("-"):
                buf.append(line.strip())
    return " ".join(buf).strip()


def _one_line_summary(text: str, title: str) -> str:
    """Best-effort short summary from the ledger body."""
    quote = _first_paragraph_after("### Tyler's Original Request", text)
    if quote:
        return quote[:240]
    # Fall back to first acceptance criterion.
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("### Acceptance Criteria"):
            for j in range(i + 1, min(i + 12, len(lines))):
                s = lines[j].strip()
                if s.startswith("1.") or s.startswith("- "):
                    return re.sub(r"\*\*", "", s.lstrip("-1. ").strip())[:240]
    return title


def parse_ledger(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    header = _parse_header(text)
    raw_state = (header.get("State") or "OPEN").upper()
    # Respect compound states like "MERGED → CLOSED": take the LAST segment as
    # the current state, earlier segments are history.
    segments = [s.strip() for s in re.split(r"[→>]+", raw_state) if s.strip()]
    state = (segments[-1] if segments else "OPEN").split()[0]
    # Normalize some legacy freeform states.
    if state not in ACTIVE_STATES and state not in ARCHIVED_STATES:
        if "SIGNED_OFF" in raw_state:
            state = "SIGNED_OFF"
        elif "CLOSED" in raw_state:
            state = "CLOSED"
        elif "MERGED" in raw_state:
            state = "MERGED"
    return {
        "file": path,
        "relpath": path.relative_to(PROJECT_ROOT).as_posix(),
        "fr_id": header.get("FR ID", path.stem),
        "title": header.get("Title", path.stem),
        "type": header.get("Type", ""),
        "risk": header.get("Risk", ""),
        "projects": header.get("Projects", ""),
        "state": state,
        "state_raw": header.get("State", ""),
        "branch": header.get("Branch", ""),
        "prs": header.get("PRs", ""),
        "opened": header.get("Opened", ""),
        "last_updated": header.get("Last updated", ""),
        "merged_at": header.get("Merged at", ""),
        "signed_off_at": header.get("Signed off at", ""),
        "closed": header.get("Closed", ""),
        "summary": _one_line_summary(text, header.get("Title", path.stem)),
    }


def collect_all() -> list[dict]:
    if not LEDGER_DIR.is_dir():
        return []
    rows: list[dict] = []
    for md in sorted(LEDGER_DIR.glob("FR-*.md")):
        if md.name in _SKIP:
            continue
        rows.append(parse_ledger(md))
    return rows


# ── Soak duration ────────────────────────────────────────────────────────

def _parse_iso(ts: str) -> datetime | None:
    ts = (ts or "").strip()
    if not ts or ts in {"—", "-", "pending"}:
        return None
    # Accept date-only or full ISO 8601.
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(ts, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        # Python 3.11+: fromisoformat accepts "Z".
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _humanize_duration(delta_secs: float) -> str:
    secs = int(max(0, delta_secs))
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"{d}d {h}h" if h else f"{d}d"
    if h:
        return f"{h}h {m}m" if m else f"{h}h"
    if m:
        return f"{m}m"
    return "<1m"


def soak_duration(fr: dict) -> str | None:
    merged = _parse_iso(fr.get("merged_at", ""))
    if merged is None:
        return None
    return _humanize_duration((datetime.now(timezone.utc) - merged).total_seconds())


# ── Rendering ────────────────────────────────────────────────────────────

def _esc(v) -> str:
    return html_mod.escape(str(v)) if v not in (None, "") else ""


STATE_CLASSES = {
    "OPEN": "warn", "TRIAGED": "warn",
    "BRANCHED": "info", "IN_PROGRESS": "info",
    "REVIEW_REQUESTED": "info", "AUTO_REVIEWED": "info",
    "BRANCH_CHECKED_OUT": "info", "CHANGES_REQUESTED": "danger",
    "TYLER_APPROVED": "ok", "MERGED": "ok",
    "SOAKING": "soak",
    "SIGNED_OFF": "done", "ARCHIVED": "muted", "CLOSED": "muted",
}


def _pr_links_html(prs: str) -> str:
    if not prs or prs.strip() in {"—", "-", "pending"}:
        return '<span class="muted">pending</span>'
    # Extract URLs.
    urls = re.findall(r"https?://\S+", prs)
    if not urls:
        return _esc(prs)
    parts = []
    for u in urls:
        u_clean = u.rstrip(").,;")
        m = re.search(r"/pull/(\d+)", u_clean)
        label = f"#{m.group(1)}" if m else u_clean
        parts.append(f'<a href="{_esc(u_clean)}" target="_blank" rel="noopener">{_esc(label)}</a>')
    return " · ".join(parts)


def _card_html(fr: dict) -> str:
    state = fr["state"]
    state_cls = STATE_CLASSES.get(state, "info")
    soak = soak_duration(fr) if state == "SOAKING" else None

    merged_display = fr.get("merged_at") or "—"
    signed_display = fr.get("signed_off_at") or "—"

    meta_rows = [
        ("Projects", _esc(fr["projects"]) or "—"),
        ("Branch", f'<code>{_esc(fr["branch"])}</code>' if fr["branch"] and fr["branch"] != "—" else "—"),
        ("PR", _pr_links_html(fr["prs"])),
        ("Opened", _esc(fr["opened"]) or "—"),
        ("Merged", _esc(merged_display)),
    ]
    if state in ARCHIVED_STATES:
        meta_rows.append(("Signed off", _esc(signed_display)))

    soak_badge = ""
    if soak is not None:
        soak_badge = f'<span class="soak-badge" title="Time since merge">Soaking for {soak}</span>'

    signoff_cta = ""
    if state in {"SOAKING", "MERGED"}:
        intro = (
            "Exercise the feature on <code>main</code>. When satisfied:"
            if state == "SOAKING"
            else "Verify the feature is live on <code>main</code>. When satisfied:"
        )
        fr_id_q = urllib.parse.quote(fr["fr_id"], safe="")
        # Uses the `frsignoff:` protocol handler (no server required).
        # Register once via tools/register_frsignoff_protocol.ps1.
        signoff_cta = (
            '<div class="cta signoff-cta">'
            f'<div class="cta-text">{intro}</div>'
            '<div class="cta-actions">'
            f'<a class="signoff-btn" href="frsignoff:{fr_id_q}">✓ Sign off</a>'
            '</div>'
            '<div class="cta-hint">'
            'Launches the Windows protocol handler — signs off, commits, and pushes.<br>'
            f'CLI fallback: <code>python tools/fr_signoff.py {_esc(fr["fr_id"])}</code>'
            '</div>'
            '</div>'
        )

    ledger_link = f'<a href="../{_esc(fr["relpath"])}" target="_blank" rel="noopener">ledger →</a>'

    meta_html = "\n".join(
        f'<div class="meta-row"><span class="meta-key">{k}</span><span class="meta-val">{v}</span></div>'
        for k, v in meta_rows
    )

    return f"""
    <div class="fr-card">
      <div class="fr-top">
        <div class="fr-id">{_esc(fr["fr_id"])}</div>
        <div class="fr-badges">
          <span class="state-badge state-{state_cls}">{_esc(state)}</span>
          {soak_badge}
        </div>
      </div>
      <div class="fr-title">{_esc(fr["title"])}</div>
      <div class="fr-summary">{_esc(fr["summary"])}</div>
      <div class="fr-meta">
        {meta_html}
      </div>
      {signoff_cta}
      <div class="fr-foot">{ledger_link}</div>
    </div>"""


_CSS = """
:root {
  --bg: #0a0d12;
  --surface: #151a22;
  --surface-2: #1b2230;
  --border: #1e2530;
  --accent: #6366f1;
  --text: #e2e8f0;
  --muted: #64748b;
  --ok: #10b981;
  --warn: #f59e0b;
  --danger: #ef4444;
  --info: #60a5fa;
  --soak: #a78bfa;
  --done: #34d399;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  padding: 1.5rem;
  min-height: 100vh;
}
h1 { font-size: 1.35rem; font-weight: 700; margin-bottom: 0.25rem; }
h1 .sigil { color: var(--accent); margin-right: 0.3rem; }
.subtitle { color: var(--muted); font-size: 0.78rem; margin-bottom: 1.2rem; }
.section-title {
  font-size: 0.78rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--muted);
  margin: 1.5rem 0 0.6rem; display: flex; align-items: center; gap: 0.5rem;
}
.section-title .count {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.05rem 0.5rem; font-size: 0.7rem; color: var(--text);
}
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 0.9rem; }
.fr-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.85rem 0.95rem;
  display: flex; flex-direction: column; gap: 0.55rem;
  transition: border-color .15s, transform .15s;
}
.fr-card:hover { border-color: var(--accent); }
.fr-top { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; }
.fr-id {
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.72rem; color: var(--muted); letter-spacing: 0.02em;
}
.fr-badges { display: flex; gap: 0.35rem; align-items: center; flex-wrap: wrap; }
.state-badge {
  font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.05em; padding: 0.18rem 0.45rem; border-radius: 4px;
  white-space: nowrap;
}
.state-ok    { background: rgba(16,185,129,0.16); color: var(--ok); }
.state-warn  { background: rgba(245,158,11,0.16); color: var(--warn); }
.state-danger{ background: rgba(239,68,68,0.16);  color: var(--danger); }
.state-info  { background: rgba(96,165,250,0.16); color: var(--info); }
.state-soak  { background: rgba(167,139,250,0.18); color: var(--soak); }
.state-done  { background: rgba(52,211,153,0.18); color: var(--done); }
.state-muted { background: var(--surface-2); color: var(--muted); }
.soak-badge {
  font-size: 0.62rem; font-weight: 600; padding: 0.18rem 0.5rem;
  border-radius: 10px; background: rgba(167,139,250,0.12);
  color: var(--soak); border: 1px solid rgba(167,139,250,0.35);
  white-space: nowrap;
}
.fr-title { font-size: 0.98rem; font-weight: 700; line-height: 1.25; }
.fr-summary {
  font-size: 0.8rem; color: var(--text); opacity: 0.78; line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}
.fr-meta {
  display: flex; flex-direction: column; gap: 0.2rem;
  border-top: 1px solid var(--border); padding-top: 0.5rem;
  font-size: 0.72rem;
}
.meta-row { display: flex; justify-content: space-between; gap: 0.5rem; }
.meta-key { color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.66rem; }
.meta-val { color: var(--text); text-align: right; overflow: hidden; text-overflow: ellipsis; max-width: 65%; }
.meta-val code {
  background: var(--surface-2); padding: 0.05rem 0.35rem;
  border-radius: 3px; font-size: 0.7rem; color: #a5f3fc; word-break: break-all;
}
.meta-val a { color: var(--accent); text-decoration: none; }
.meta-val a:hover { text-decoration: underline; }
.cta {
  font-size: 0.72rem; color: var(--soak);
  background: rgba(167,139,250,0.06);
  border: 1px dashed rgba(167,139,250,0.35);
  border-radius: 6px; padding: 0.55rem 0.6rem;
  display: flex; flex-direction: column; gap: 0.4rem;
}
.cta code {
  background: var(--surface-2); padding: 0.05rem 0.35rem;
  border-radius: 3px; color: #a5f3fc;
}
.cta-actions { display: flex; gap: 0.4rem; align-items: center; }
.cta-actions input[type="text"] {
  flex: 1; background: var(--surface-2); color: var(--text);
  border: 1px solid var(--border); border-radius: 4px;
  padding: 0.3rem 0.5rem; font-size: 0.72rem; font-family: inherit;
}
.cta-actions input[type="text"]:focus { outline: none; border-color: var(--soak); }
.signoff-btn {
  background: var(--soak); color: #0a0d12;
  border: none; border-radius: 4px;
  padding: 0.35rem 0.75rem; font-size: 0.72rem; font-weight: 700;
  cursor: pointer; white-space: nowrap;
  transition: filter .1s;
  display: inline-block; text-decoration: none;
}
.signoff-btn:hover { filter: brightness(1.15); }
.signoff-btn:active { filter: brightness(0.9); }
.cta-hint { font-size: 0.66rem; color: var(--muted); }
.flash {
  margin: 0 0 1rem; padding: 0.6rem 0.9rem;
  background: rgba(52,211,153,0.12); border: 1px solid rgba(52,211,153,0.4);
  color: var(--done); border-radius: 6px; font-size: 0.8rem;
}
.fr-foot {
  font-size: 0.72rem; border-top: 1px solid var(--border); padding-top: 0.4rem;
  text-align: right;
}
.fr-foot a { color: var(--accent); text-decoration: none; }
.fr-foot a:hover { text-decoration: underline; }
.muted { color: var(--muted); }
details.archive { margin-top: 1rem; }
details.archive > summary {
  cursor: pointer; padding: 0.5rem 0; color: var(--muted);
  font-size: 0.8rem; font-weight: 600;
  list-style: none;
}
details.archive > summary::before {
  content: '▸ '; display: inline-block; transition: transform .15s;
}
details.archive[open] > summary::before { transform: rotate(90deg); }
.empty {
  padding: 1.5rem; text-align: center; color: var(--muted);
  background: var(--surface); border: 1px dashed var(--border); border-radius: 8px;
}
.footer {
  margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border);
  color: var(--muted); font-size: 0.68rem;
}
.footer code {
  background: var(--surface); padding: 0.1rem 0.35rem;
  border-radius: 3px; color: #a5f3fc;
}
@media (max-width: 900px) {
  body { padding: 1rem; }
  .grid { grid-template-columns: 1fr; }
  .cycle-chart { overflow-x: auto; }
}
.cycle-panel {
  margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border);
}
.cycle-toolbar { display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; }
.cycle-toolbar select {
  background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.3rem 0.5rem; font: inherit; font-size: 0.72rem;
}
.cycle-summary { display: flex; gap: 1rem; flex-wrap: wrap; color: var(--muted); font-size: 0.72rem; margin: 0.7rem 0; }
.cycle-summary strong { color: var(--text); }
.cycle-chart { min-height: 4rem; }
.cycle-row { display: grid; grid-template-columns: 12rem minmax(8rem, 1fr) 7rem; gap: 0.6rem; align-items: center; font-size: 0.7rem; padding: 0.22rem 0; }
.cycle-bar { height: 0.6rem; background: var(--accent); border-radius: 3px; min-width: 2px; }
.cycle-active { color: var(--warn); font-style: italic; }
.cycle-disclosure { color: var(--muted); font-size: 0.68rem; margin-top: 0.6rem; }
"""


def _format_seconds(seconds: float | None) -> str:
    return "active" if seconds is None else _humanize_duration(seconds)


def _cycle_chart_html(perf_runs: dict) -> str:
    rows = perf_runs.get("rows", [])
    counts = perf_runs.get("counts", {})
    projects = sorted({row.get("project", "⊕Workspace") for row in rows})
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    disclosures = (
        f"{counts.get('active', 0)} active · {counts.get('invalid', 0)} invalid-duration · "
        f"{counts.get('duplicates', 0)} duplicate · {counts.get('legacy', 0)} legacy"
    )
    options = "".join(f'<option value="{_esc(project)}">{_esc(project)}</option>' for project in projects)
    return f"""
  <section class="cycle-panel" aria-labelledby="cycle-title">
    <div class="section-title" id="cycle-title">Cycle time, last 90 days</div>
    <div class="cycle-toolbar">
      <label for="project-filter">Project</label>
      <select id="project-filter" class="project-filter"><option value="all">All projects</option>{options}</select>
    </div>
    <div class="cycle-summary" id="cycle-summary"></div>
    <div class="cycle-chart" id="cycle-chart" aria-live="polite"></div>
    <div class="cycle-disclosure">{_esc(disclosures)} · completed positive durations are measurements; active cycles are aging markers.</div>
    <script id="cycle-data" type="application/json">{payload}</script>
    <script>
    (() => {{
      const data = JSON.parse(document.getElementById('cycle-data').textContent);
      const filter = document.getElementById('project-filter');
      const chart = document.getElementById('cycle-chart');
      const summary = document.getElementById('cycle-summary');
      const human = seconds => seconds < 3600 ? Math.round(seconds / 60) + 'm' : Math.round(seconds / 3600 * 10) / 10 + 'h';
      const draw = () => {{
        const rows = data.filter(row => filter.value === 'all' || row.project === filter.value);
        const measured = rows.filter(row => row.kind === 'measurement').map(row => row.duration_seconds).sort((a, b) => a - b);
        const median = measured.length ? (measured.length % 2
          ? measured[Math.floor(measured.length / 2)]
          : (measured[measured.length / 2 - 1] + measured[measured.length / 2]) / 2) : null;
        const p75 = measured.length ? measured[Math.ceil(measured.length * .75) - 1] : null;
        summary.innerHTML = '<span>sample <strong>' + measured.length + '</strong></span><span>median <strong>' + (median === null ? 'n/a' : human(median)) + '</strong></span><span>p75 <strong>' + (p75 === null ? 'n/a' : human(p75)) + '</strong></span>';
        const max = Math.max(1, ...measured);
        const escapeHtml = value => String(value).replace(/[&<>\"']/g, character => ({{
          '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }})[character]);
        chart.innerHTML = rows.map(row => row.kind === 'active'
          ? '<div class="cycle-row cycle-active"><span>' + escapeHtml(row.fr_id) + '</span><span>active aging marker</span><span>' + escapeHtml(row.project) + '</span></div>'
          : row.kind === 'invalid'
          ? '<div class="cycle-row cycle-invalid"><span>' + escapeHtml(row.fr_id) + '</span><span>invalid duration</span><span>' + escapeHtml(row.project) + '</span></div>'
          : '<div class="cycle-row"><span>' + escapeHtml(row.fr_id) + '</span><span class="cycle-bar" style="width:' + Math.max(2, row.duration_seconds / max * 100) + '%"></span><span>' + human(row.duration_seconds) + '</span></div>').join('') || '<div class="empty">No cycle data in the last 90 days.</div>';
      }};
      filter.addEventListener('change', draw); draw();
    }})();
    </script>
  </section>"""


def render_html(frs: list[dict], perf_runs: dict | None = None) -> str:
    active = [f for f in frs if f["state"] in ACTIVE_STATES]
    archived = [f for f in frs if f["state"] in ARCHIVED_STATES]

    # Order: soaking first (needs Tyler attention), then by state, then by opened date desc.
    state_order = ["SOAKING", "BRANCH_CHECKED_OUT", "AUTO_REVIEWED", "REVIEW_REQUESTED",
                   "CHANGES_REQUESTED", "IN_PROGRESS", "TYLER_APPROVED", "MERGED",
                   "BRANCHED", "TRIAGED", "OPEN"]
    def _sort_key(f):
        try:
            idx = state_order.index(f["state"])
        except ValueError:
            idx = 99
        return (idx, f.get("opened", ""))
    active.sort(key=_sort_key)
    archived.sort(key=lambda f: f.get("signed_off_at") or f.get("closed") or f.get("opened") or "", reverse=True)

    soaking_count = sum(1 for f in active if f["state"] == "SOAKING")

    active_html = "".join(_card_html(f) for f in active) or '<div class="empty">No active feature requests.</div>'
    archived_html = "".join(_card_html(f) for f in archived) or '<div class="empty">No archived feature requests yet.</div>'

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tyler_nudge = ""
    if soaking_count:
        word = "FR" if soaking_count == 1 else "FRs"
        tyler_nudge = f' · <strong style="color:#a78bfa">{soaking_count} {word} awaiting signoff</strong>'

    flash_script = (
        "<script>document.addEventListener('DOMContentLoaded',()=>{"
        "const p=new URLSearchParams(location.search);"
        "const id=p.get('signed_off');"
        "if(!id)return;"
        "const slot=document.getElementById('flash-slot');"
        "if(!slot)return;"
        "slot.className='flash';"
        "slot.textContent='✓ Signed off on '+id+' — FR moved to Archived.';"
        "history.replaceState({},'',location.pathname);"
        "});</script>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>⊕ Feature Request Board</title>
<style>{_CSS}</style>
</head>
<body>
  <h1><span class="sigil">⊕</span> Feature Request Board</h1>
  <div class="subtitle">
    Generated {generated}{tyler_nudge} ·
    Ledger: <code>.github/FR_LEDGERS/</code> · Registry: <code>.github/FEATURE_REQUESTS.md</code>
  </div>
  {flash_script}
  <div id="flash-slot"></div>

  {_cycle_chart_html(perf_runs) if perf_runs is not None else ''}

  <div class="section-title">Active <span class="count">{len(active)}</span></div>
  <div class="grid">
    {active_html}
  </div>

  <details class="archive">
    <summary>Archived / Signed off <span class="count">{len(archived)}</span></summary>
    <div class="grid" style="margin-top:0.6rem">
      {archived_html}
    </div>
  </details>

  <div class="footer">
    Soak protocol: after merge, FRs enter <code>SOAKING</code> so Tyler can verify
    the feature is actually present on <code>main</code> before signing off.
    Signoff moves the FR to <code>SIGNED_OFF → ARCHIVED</code> and it drops off the
    active board. <br>
    Regenerate HTML: <code>C:\\G\\python.exe tools/fr_dashboard.py</code> ·
    Serve + enable signoff buttons: <code>C:\\G\\python.exe tools/fr_portal_server.py</code>
  </div>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="⊕ FR Board")
    parser.add_argument("--no-open", action="store_true", default=True,
                        help="Do not open a browser (default; flag kept for compatibility)")
    parser.add_argument("--open", dest="open_browser", action="store_true",
                        help="Open the generated HTML in the default browser")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of writing HTML")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    frs = collect_all()

    if args.json:
        import json
        # Drop non-serializable Path for JSON.
        dumpable = [{k: (v if not isinstance(v, Path) else str(v)) for k, v in f.items()} for f in frs]
        print(json.dumps(dumpable, indent=2, ensure_ascii=False))
        return

    perf_runs = collect_perf_runs(frs)
    html_content = render_html(frs, perf_runs=perf_runs)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html_content, encoding="utf-8")
    print(f"FR board written to {OUT_FILE}  ({len(frs)} FRs)")

    if args.open_browser:
        import webbrowser
        webbrowser.open(OUT_FILE.as_uri())


if __name__ == "__main__":
    main()
