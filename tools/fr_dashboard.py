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
import re
import sys
from datetime import datetime, timezone
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
        signoff_cta = (
            '<form class="cta signoff-form" method="POST" '
            f'action="/fr/signoff/{_esc(fr["fr_id"])}">'
            f'<div class="cta-text">{intro}</div>'
            '<div class="cta-actions">'
            '<input type="text" name="note" placeholder="optional note" maxlength="240">'
            '<button type="submit" class="signoff-btn">✓ Sign off</button>'
            '</div>'
            '<div class="cta-hint">'
            'Requires <code>fr_portal_server.py</code> running. '
            f'CLI fallback: <code>python tools/fr_signoff.py {_esc(fr["fr_id"])}</code>'
            '</div>'
            '</form>'
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
"""


def render_html(frs: list[dict]) -> str:
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

    html_content = render_html(frs)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html_content, encoding="utf-8")
    print(f"FR board written to {OUT_FILE}  ({len(frs)} FRs)")

    if args.open_browser:
        import webbrowser
        webbrowser.open(OUT_FILE.as_uri())


if __name__ == "__main__":
    main()
