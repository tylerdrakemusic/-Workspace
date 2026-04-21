#!/usr/bin/env python3
"""
⊕ Security Vulnerability Dashboard

Manages the vulnerability inventory in workspace.db and renders an
interactive HTML dashboard with override/remediation controls.

Usage:
  python tools/security_dashboard.py                 # generate + open
  python tools/security_dashboard.py --no-open       # generate only
  python tools/security_dashboard.py --seed           # seed current scan findings + generate
  python tools/security_dashboard.py --scan           # run OWASP grep scan, upsert findings, generate
"""

import argparse
import hashlib
import html
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "reports" / "security_dashboard.html"

sys.path.insert(0, str(PROJECT_ROOT / "src"))
from utils.init_db import get_connection

# Register Brave
_BRAVE_PATHS = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]
for _bp in _BRAVE_PATHS:
    if os.path.isfile(_bp):
        webbrowser.register("brave", None, webbrowser.BackgroundBrowser(_bp))
        break

SCAN_ROOTS = [
    Path(r"f:\∞Life"),
    Path(r"f:\❤Music"),
    Path(r"f:\⟨ψ⟩Quantum"),
    Path(r"f:\👁AI-Manifest"),
    Path(r"f:\⊕Workspace"),
]


# ── Vuln ID ────────────────────────────────────────────────────

def _vuln_id(category: str, file_path: str, line: int, desc: str) -> str:
    """Deterministic vuln_id so re-scans upsert rather than duplicate."""
    raw = f"{category}|{file_path}|{line}|{desc}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── OWASP Scan Patterns ───────────────────────────────────────

SCAN_PATTERNS: list[tuple[str, str, str, re.Pattern]] = [
    ("A03", "high", "SQL injection — f-string in execute()",
     re.compile(r'execute\s*\(\s*f["\']', re.IGNORECASE)),
    ("A03", "high", "Dangerous eval() call",
     re.compile(r'\beval\s*\(')),
    ("A03", "high", "Dangerous exec() call",
     re.compile(r'\bexec\s*\(')),
    ("A03", "high", "Shell injection — shell=True",
     re.compile(r'shell\s*=\s*True')),
    ("A02", "low", "Weak hash — MD5 for security",
     re.compile(r'hashlib\.md5\s*\(')),
    ("A02", "low", "Weak hash — SHA1 for security",
     re.compile(r'hashlib\.sha1\s*\(')),
    ("A04", "critical", "Hardcoded secret in source",
     re.compile(r'(?:api_key|password|secret|token)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE)),
    ("A08", "medium", "Pickle deserialization on potentially untrusted data",
     re.compile(r'pickle\.loads?\s*\(')),
    ("A02", "low", "HTTP URL (not HTTPS)",
     re.compile(r'http://(?!localhost|127\.0\.0\.1)')),
]

# Known false-positive patterns to auto-mark
_FP_PATTERNS = [
    # Image.eval is PIL, not dangerous eval()
    re.compile(r'Image\.eval\s*\('),
    # Test fixtures with fake keys
    re.compile(r'api_key\s*=\s*["\']test-key'),
    # String matching/docs referencing http://
    re.compile(r'startswith\s*\(\s*["\']http://'),
    re.compile(r'["\']URL must start with'),
    # random_token = "fallback" (not a real secret)
    re.compile(r'random_token\s*=\s*["\']fallback'),
]


def _is_false_positive(line_text: str) -> bool:
    return any(fp.search(line_text) for fp in _FP_PATTERNS)


def run_owasp_scan() -> list[dict]:
    """Grep Python files for OWASP vulnerability patterns. Returns findings."""
    findings = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for pyfile in root.rglob("*.py"):
            # Skip test files, clones, __pycache__
            rel = str(pyfile)
            if "__pycache__" in rel or "pyClones" in rel:
                continue
            try:
                lines = pyfile.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                for owasp_id, severity, desc, pattern in SCAN_PATTERNS:
                    if pattern.search(line):
                        if _is_false_positive(line):
                            continue
                        findings.append({
                            "category": "OWASP",
                            "severity": severity,
                            "file_path": str(pyfile),
                            "line_number": i,
                            "description": desc,
                            "owasp_id": owasp_id,
                        })
    return findings


# ── Seed data (manual findings from security audit) ───────────

SEED_FINDINGS = [
    {
        "category": "SECRETS",
        "severity": "critical",
        "file_path": r"f:\cobraKing\$$~~$$tyja.py",
        "line_number": 321,
        "description": "OpenAI API key hardcoded in source",
        "owasp_id": "A04",
    },
    {
        "category": "SECRETS",
        "severity": "critical",
        "file_path": r"f:\facebook_graph_api_call.py",
        "line_number": 402,
        "description": "Facebook user token hardcoded in source",
        "owasp_id": "A04",
    },
    {
        "category": "SECRETS",
        "severity": "critical",
        "file_path": r"f:\ty_py\openai_helper.py",
        "line_number": 7,
        "description": "OpenAI API key hardcoded in source",
        "owasp_id": "A04",
    },
    {
        "category": "SECRETS",
        "severity": "critical",
        "file_path": r"f:\ty_py\tokenReturns.py",
        "line_number": 5,
        "description": "IBM Quantum token hardcoded in source (twice)",
        "owasp_id": "A04",
    },
    {
        "category": "SECRETS",
        "severity": "critical",
        "file_path": r"f:\ty_py\yt_utils.py",
        "line_number": 4,
        "description": "Google API key hardcoded in source",
        "owasp_id": "A04",
    },
    {
        "category": "SECRETS",
        "severity": "high",
        "file_path": r"f:\∞Life\tools\withings_sync.py",
        "line_number": 51,
        "description": "Withings CLIENT_SECRET hardcoded — should be in .env",
        "owasp_id": "A04",
    },
    {
        "category": "INTEGRITY",
        "severity": "medium",
        "file_path": r"f:\.github\agents",
        "line_number": 0,
        "description": "Agent manifest has 4 new + 4 modified files since last baseline — regenerate",
        "owasp_id": None,
    },
    {
        "category": "GIT",
        "severity": "high",
        "file_path": r"f:\⊕Workspace\tokens",
        "line_number": 0,
        "description": "git rm --cached tokens/ changes not yet committed — tokens still in staging",
        "owasp_id": None,
    },
]


# ── DB Operations ─────────────────────────────────────────────

def upsert_findings(findings: list[dict]) -> tuple[int, int]:
    """Upsert findings into vulnerabilities table. Returns (inserted, skipped)."""
    conn = get_connection()
    inserted = 0
    skipped = 0
    scan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for f in findings:
        vid = _vuln_id(f["category"], f.get("file_path", ""), f.get("line_number", 0), f["description"])
        existing = conn.execute("SELECT status FROM vulnerabilities WHERE vuln_id = ?", (vid,)).fetchone()
        if existing:
            skipped += 1
            continue
        conn.execute(
            "INSERT INTO vulnerabilities (vuln_id, scan_date, category, severity, file_path, "
            "line_number, description, owasp_id, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (vid, scan_date, f["category"], f["severity"],
             f.get("file_path"), f.get("line_number"), f["description"],
             f.get("owasp_id"), "open"),
        )
        inserted += 1
    conn.commit()
    conn.close()
    return inserted, skipped


def load_all_vulns() -> list[dict]:
    """Load all vulnerabilities for dashboard display."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT vuln_id, scan_date, category, severity, file_path, line_number, "
        "description, owasp_id, status, override_note, remediated_at, created_at "
        "FROM vulnerabilities ORDER BY "
        "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
        "WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, scan_date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_vuln_status(vuln_id: str, new_status: str, note: str = "") -> None:
    """Update a vulnerability's status and optional override note."""
    conn = get_connection()
    remediated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status in ("remediated", "accepted", "false_positive") else None
    conn.execute(
        "UPDATE vulnerabilities SET status = ?, override_note = ?, remediated_at = ? WHERE vuln_id = ?",
        (new_status, note or None, remediated_at, vuln_id),
    )
    conn.commit()
    conn.close()


# ── HTML Rendering ────────────────────────────────────────────

def _esc(val) -> str:
    return html.escape(str(val)) if val else "&mdash;"


def _severity_badge(sev: str) -> str:
    cls = {"critical": "critical", "high": "fail", "medium": "partial", "low": "info", "info": "info"}
    return f'<span class="badge {cls.get(sev, "info")}">{_esc(sev.upper())}</span>'


def _status_badge(status: str) -> str:
    cls = {"open": "fail", "remediated": "success", "accepted": "accepted", "false_positive": "muted"}
    return f'<span class="badge {cls.get(status, "fail")}">{_esc(status.upper().replace("_", " "))}</span>'


def _summary_cards(vulns: list[dict]) -> str:
    total = len(vulns)
    open_v = sum(1 for v in vulns if v["status"] == "open")
    remediated = sum(1 for v in vulns if v["status"] == "remediated")
    accepted = sum(1 for v in vulns if v["status"] in ("accepted", "false_positive"))
    crit = sum(1 for v in vulns if v["severity"] == "critical" and v["status"] == "open")
    high = sum(1 for v in vulns if v["severity"] == "high" and v["status"] == "open")
    medium = sum(1 for v in vulns if v["severity"] == "medium" and v["status"] == "open")
    low = sum(1 for v in vulns if v["severity"] == "low" and v["status"] == "open")

    return f"""
    <div class="summary-grid">
      <div class="card security-card">
        <h3>Inventory</h3>
        <div class="stat">{total}</div><div class="label">Total Findings</div>
        <div class="stat open-stat">{open_v}</div><div class="label">Open</div>
        <div class="stat remediated-stat">{remediated}</div><div class="label">Remediated</div>
        <div class="stat accepted-stat">{accepted}</div><div class="label">Accepted / FP</div>
      </div>
      <div class="card severity-card">
        <h3>Open by Severity</h3>
        <div class="sev-row"><span class="badge critical">CRITICAL</span> <span class="sev-count">{crit}</span></div>
        <div class="sev-row"><span class="badge fail">HIGH</span> <span class="sev-count">{high}</span></div>
        <div class="sev-row"><span class="badge partial">MEDIUM</span> <span class="sev-count">{medium}</span></div>
        <div class="sev-row"><span class="badge info">LOW</span> <span class="sev-count">{low}</span></div>
      </div>
    </div>"""


def _vuln_table(vulns: list[dict]) -> str:
    if not vulns:
        return '<p class="empty">No vulnerability data. Run with --scan or --seed to populate.</p>'

    lines = ['<table class="vuln-table sortable" id="vuln-table">',
             "<thead><tr>",
             '<th>#</th>',
             '<th class="sort-header" data-sort-type="string">Severity <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">Category <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">OWASP <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">File <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="number">Line <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">Description <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">Status <span class="sort-icon"></span></th>',
             '<th>Override Note</th>',
             '<th class="sort-header" data-sort-type="string">Scan Date <span class="sort-icon"></span></th>',
             '<th>Actions</th>',
             "</tr></thead><tbody>"]

    for i, v in enumerate(vulns, 1):
        vid = _esc(v["vuln_id"])
        fp = v.get("file_path", "") or ""
        # Shorten file_path for display
        short_fp = fp.replace("f:\\", "").replace("\\", "/")
        ln = v.get("line_number") or ""
        note = v.get("override_note") or ""
        sev_val = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(v["severity"], 4)

        lines.append(f'<tr data-vuln-id="{vid}" data-status="{_esc(v["status"])}">')
        lines.append(f'<td>{i}</td>')
        lines.append(f'<td data-sort-val="{sev_val}">{_severity_badge(v["severity"])}</td>')
        lines.append(f'<td data-sort-val="{_esc(v["category"])}">{_esc(v["category"])}</td>')
        lines.append(f'<td data-sort-val="{_esc(v.get("owasp_id",""))}">{_esc(v.get("owasp_id",""))}</td>')
        lines.append(f'<td class="file-cell" data-sort-val="{_esc(short_fp)}" title="{_esc(fp)}">{_esc(short_fp)}</td>')
        lines.append(f'<td class="num" data-sort-val="{ln}">{ln if ln else "&mdash;"}</td>')
        lines.append(f'<td class="desc-cell" data-sort-val="{_esc(v["description"])}">{_esc(v["description"])}</td>')
        lines.append(f'<td data-sort-val="{_esc(v["status"])}">{_status_badge(v["status"])}</td>')
        lines.append(f'<td class="note-cell">{_esc(note)}</td>')
        lines.append(f'<td class="ts" data-sort-val="{_esc(v["scan_date"])}">{_esc(v["scan_date"])}</td>')
        lines.append(f'<td class="actions-cell">')
        lines.append(f'  <select class="status-select" data-vid="{vid}">')
        for st in ["open", "remediated", "accepted", "false_positive"]:
            sel = " selected" if st == v["status"] else ""
            label = st.replace("_", " ").title()
            lines.append(f'    <option value="{st}"{sel}>{label}</option>')
        lines.append(f'  </select>')
        lines.append(f'  <input type="text" class="note-input" data-vid="{vid}" placeholder="Note..." value="{_esc(note)}">')
        lines.append(f'  <button class="save-btn" data-vid="{vid}">Save</button>')
        lines.append(f'</td></tr>')

    lines.append("</tbody></table>")
    return "\n".join(lines)


def render_html(vulns: list[dict]) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = _summary_cards(vulns)
    table = _vuln_table(vulns)
    total = len(vulns)
    open_v = sum(1 for v in vulns if v["status"] == "open")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>⊕ Security Vulnerability Dashboard</title>
<style>
  :root {{
    --security-accent: #f87171;
    --success: #0d904f;
    --fail: #d93025;
    --partial: #f9ab00;
    --info: #60a5fa;
    --accepted-color: #a78bfa;
    --muted-badge: #6b7280;
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --critical-bg: rgba(248,113,113,0.12);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
    max-width: 1600px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 1.8rem;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  h1 .sigil {{ color: var(--security-accent); font-size: 2rem; }}
  .subtitle {{ color: var(--muted); margin-bottom: 1.5rem; font-size: 0.9rem; }}

  /* ── Filter bar ── */
  .filter-bar {{
    display: flex;
    gap: 0.8rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    align-items: center;
  }}
  .filter-bar label {{ color: var(--muted); font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
  .filter-btn {{
    padding: 0.4rem 1rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--muted);
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .filter-btn:hover {{ color: var(--text); border-color: var(--text); }}
  .filter-btn.active {{ color: var(--text); border-color: var(--security-accent); background: rgba(248,113,113,0.1); }}

  /* ── Summary cards ── */
  .summary-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 2.5rem;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
  }}
  .card h3 {{ margin-bottom: 1rem; font-size: 1.1rem; }}
  .security-card {{ border-top: 3px solid var(--security-accent); }}
  .security-card h3 {{ color: var(--security-accent); }}
  .severity-card {{ border-top: 3px solid var(--partial); }}
  .severity-card h3 {{ color: var(--partial); }}
  .stat {{ font-size: 2rem; font-weight: 700; line-height: 1.2; }}
  .open-stat {{ color: var(--fail); }}
  .remediated-stat {{ color: var(--success); }}
  .accepted-stat {{ color: var(--accepted-color); }}
  .label {{
    color: var(--muted); font-size: 0.8rem;
    text-transform: uppercase; letter-spacing: 0.05em;
    margin-bottom: 0.8rem;
  }}
  .sev-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.4rem 0.8rem;
    margin: 0.3rem 0;
  }}
  .sev-count {{
    font-size: 1.4rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }}

  /* ── Tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    margin-bottom: 2rem;
  }}
  thead {{ background: var(--surface); }}
  th {{
    text-align: left; padding: 0.6rem 0.6rem;
    font-weight: 600; color: var(--muted);
    text-transform: uppercase; font-size: 0.7rem;
    letter-spacing: 0.05em;
    border-bottom: 2px solid var(--border);
  }}
  td {{
    padding: 0.5rem 0.6rem;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }}
  tr:hover {{ background: rgba(255,255,255,0.03); }}
  tr[data-status="open"] {{ background: var(--critical-bg); }}
  tr[data-status="open"]:hover {{ background: rgba(248,113,113,0.18); }}
  tr[data-status="remediated"] {{ opacity: 0.6; }}
  tr[data-status="false_positive"] {{ opacity: 0.4; }}
  tr[data-status="accepted"] {{ opacity: 0.7; }}
  .num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  .ts {{ color: var(--muted); font-size: 0.8rem; }}
  .file-cell {{
    max-width: 250px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 0.8rem;
  }}
  .desc-cell {{
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .note-cell {{
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--muted);
    font-size: 0.8rem;
  }}
  .actions-cell {{
    display: flex;
    gap: 0.3rem;
    align-items: center;
    flex-wrap: nowrap;
    min-width: 280px;
  }}
  .status-select {{
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.3rem 0.4rem;
    font-size: 0.8rem;
    cursor: pointer;
  }}
  .note-input {{
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.3rem 0.4rem;
    font-size: 0.8rem;
    width: 120px;
  }}
  .save-btn {{
    background: var(--security-accent);
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 0.3rem 0.6rem;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }}
  .save-btn:hover {{ opacity: 0.85; }}
  .save-btn.saved {{
    background: var(--success);
    pointer-events: none;
  }}

  /* ── Badges ── */
  .badge {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }}
  .badge.critical {{ background: rgba(248,113,113,0.2); color: #f87171; }}
  .badge.fail {{ background: rgba(217,48,37,0.15); color: var(--fail); }}
  .badge.partial {{ background: rgba(249,171,0,0.15); color: var(--partial); }}
  .badge.info {{ background: rgba(96,165,250,0.15); color: var(--info); }}
  .badge.success {{ background: rgba(13,144,79,0.15); color: var(--success); }}
  .badge.accepted {{ background: rgba(167,139,250,0.15); color: var(--accepted-color); }}
  .badge.muted {{ background: rgba(107,114,128,0.15); color: var(--muted-badge); }}
  .empty {{ color: var(--muted); font-style: italic; padding: 1rem; }}

  /* ── Sortable headers ── */
  .sort-header {{
    cursor: pointer; user-select: none; transition: color 0.15s;
  }}
  .sort-header:hover {{ color: var(--text); }}
  .sort-icon::after {{ content: "⇅"; opacity: 0.3; margin-left: 0.3rem; font-size: 0.65rem; }}
  .sort-header.asc .sort-icon::after {{ content: "▲"; opacity: 1; }}
  .sort-header.desc .sort-icon::after {{ content: "▼"; opacity: 1; }}

  /* ── Toast notification ── */
  .toast {{
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    background: var(--surface);
    border: 1px solid var(--success);
    border-radius: 8px;
    padding: 0.8rem 1.2rem;
    color: var(--success);
    font-weight: 600;
    font-size: 0.9rem;
    opacity: 0;
    transform: translateY(10px);
    transition: all 0.3s;
    pointer-events: none;
    z-index: 1000;
  }}
  .toast.show {{
    opacity: 1;
    transform: translateY(0);
  }}

  .footer {{
    margin-top: 3rem; padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--muted); font-size: 0.8rem;
    text-align: center;
  }}

  @media (max-width: 800px) {{
    .summary-grid {{ grid-template-columns: 1fr; }}
    body {{ padding: 1rem; }}
    .actions-cell {{ flex-wrap: wrap; min-width: auto; }}
  }}
</style>
</head>
<body>
  <h1><span class="sigil">⊕</span> Security Vulnerability Dashboard</h1>
  <div class="subtitle">
    Generated: {generated} &bull; {total} findings
  </div>

  {summary}

  <div id="zero-open-banner" style="display:{'flex' if open_v == 0 else 'none'}; align-items:center; gap:1rem; background:rgba(13,144,79,0.1); border:1px solid var(--success); border-radius:12px; padding:1.2rem 1.5rem; margin:2rem 0 1rem;">
    <span style="font-size:2rem;">\u2705</span>
    <div>
      <div style="font-size:1.1rem; font-weight:700; color:var(--success);">All Clear</div>
      <div style="color:var(--muted); font-size:0.85rem;">0 open vulnerabilities &mdash; {total} findings resolved</div>
    </div>
    <button onclick="toggleInventory()" style="margin-left:auto; padding:0.4rem 1rem; background:var(--surface); border:1px solid var(--border); border-radius:6px; color:var(--muted); font-size:0.85rem; cursor:pointer;" id="toggle-btn">Show Details \u25BC</button>
  </div>

  <div id="inventory-section" style="display:{'none' if open_v == 0 else 'block'};">
    <div class="filter-bar" id="detail-filter-bar">
      <label>Status:</label>
      <button class="filter-btn active" data-filter="all" onclick="filterStatus('all', this)">All ({total})</button>
      <button class="filter-btn" data-filter="open" onclick="filterStatus('open', this)">Open</button>
      <button class="filter-btn" data-filter="remediated" onclick="filterStatus('remediated', this)">Remediated</button>
      <button class="filter-btn" data-filter="accepted" onclick="filterStatus('accepted', this)">Accepted</button>
      <button class="filter-btn" data-filter="false_positive" onclick="filterStatus('false_positive', this)">False Positive</button>
    </div>
    <h2 style="color: var(--security-accent); border-bottom: 2px solid var(--security-accent); padding-bottom: 0.5rem; margin: 2rem 0 1rem;">Vulnerability Inventory</h2>
    {table}
  </div>

  <div class="toast" id="toast">Saved!</div>

  <div class="footer">
    ⊕Workspace &mdash; Security Vulnerability Dashboard &bull;
    Override a finding: change status + add note + Save &bull;
    Re-scan: <code>python tools/security_dashboard.py --scan</code>
  </div>

  <script>
    // ── Toggle inventory section ──
    function toggleInventory() {{
      const sec = document.getElementById('inventory-section');
      const btn = document.getElementById('toggle-btn');
      if (sec.style.display === 'none') {{
        sec.style.display = 'block';
        sec._userToggled = true;
        btn.textContent = 'Hide Details \u25B2';
      }} else {{
        sec.style.display = 'none';
        sec._userToggled = false;
        btn.textContent = 'Show Details \u25BC';
      }}
    }}

    // ── Filtering ──
    function filterStatus(status, btn) {{
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('#vuln-table tbody tr').forEach(row => {{
        if (status === 'all' || row.dataset.status === status) {{
          row.style.display = '';
        }} else {{
          row.style.display = 'none';
        }}
      }});
    }}

    // ── Save override (writes to a local JSON sidecar for the next --scan to pick up) ──
    document.querySelectorAll('.save-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const vid = btn.dataset.vid;
        const row = btn.closest('tr');
        const select = row.querySelector('.status-select');
        const noteInput = row.querySelector('.note-input');
        const newStatus = select.value;
        const note = noteInput.value;

        // Update the row visually
        applyOverrideVisual(row, newStatus, note);

        // Save to localStorage for persistence + write sidecar
        const overrides = JSON.parse(localStorage.getItem('vuln_overrides') || '{{}}');
        overrides[vid] = {{ status: newStatus, note: note, ts: new Date().toISOString() }};
        localStorage.setItem('vuln_overrides', JSON.stringify(overrides));

        // Write sidecar file via hidden download
        const blob = new Blob([JSON.stringify(overrides, null, 2)], {{type: 'application/json'}});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'vuln_overrides.json';
        a.click();
        URL.revokeObjectURL(a.href);

        // Update summary counts
        refreshSummary();

        // Flash confirmation with CLI command
        btn.classList.add('saved');
        btn.textContent = '✓';
        const toast = document.getElementById('toast');
        const cmd = 'C:\\G\\python.exe tools/security_dashboard.py --set-status ' + vid + ' ' + newStatus + (note ? ' "' + note + '"' : '');
        toast.innerHTML = 'Visual saved. Persist to DB:<br><code style="user-select:all;font-size:0.8em">' + cmd + '</code>';
        toast.classList.add('show');
        setTimeout(() => {{
          toast.classList.remove('show');
          btn.classList.remove('saved');
          btn.textContent = 'Save';
        }}, 6000);
      }});
    }});

    // ── Apply override visuals to a single row ──
    function applyOverrideVisual(row, newStatus, note) {{
      row.dataset.status = newStatus;
      const statusCell = row.children[7];
      const badgeCls = {{open:'fail', remediated:'success', accepted:'accepted', false_positive:'muted'}}[newStatus] || 'fail';
      statusCell.innerHTML = '<span class="badge ' + badgeCls + '">' + newStatus.replace('_',' ').toUpperCase() + '</span>';
      statusCell.dataset.sortVal = newStatus;
      row.children[8].textContent = note || '';
      const select = row.querySelector('.status-select');
      const noteInput = row.querySelector('.note-input');
      if (select) select.value = newStatus;
      if (noteInput) noteInput.value = note || '';
    }}

    function refreshSummary() {{
      const rows = Array.from(document.querySelectorAll('#vuln-table tbody tr'));
      let total=rows.length, open=0, remediated=0, accepted=0, crit=0, high=0, med=0, low=0;
      rows.forEach(r => {{
        const st = r.dataset.status;
        if (st === 'open') open++;
        else if (st === 'remediated') remediated++;
        else accepted++;
        if (st === 'open') {{
          const sevCell = r.children[1];
          const sev = (sevCell.textContent || '').trim().toLowerCase();
          if (sev === 'critical') crit++;
          else if (sev === 'high') high++;
          else if (sev === 'medium') med++;
          else if (sev === 'low') low++;
        }}
      }});
      const cards = document.querySelectorAll('.security-card .stat');
      if (cards[0]) cards[0].textContent = total;
      if (cards[1]) cards[1].textContent = open;
      if (cards[2]) cards[2].textContent = remediated;
      if (cards[3]) cards[3].textContent = accepted;
      const sevCounts = document.querySelectorAll('.severity-card .sev-count');
      if (sevCounts[0]) sevCounts[0].textContent = crit;
      if (sevCounts[1]) sevCounts[1].textContent = high;
      if (sevCounts[2]) sevCounts[2].textContent = med;
      if (sevCounts[3]) sevCounts[3].textContent = low;

      // Toggle banner/inventory visibility based on open count
      const banner = document.getElementById('zero-open-banner');
      const invSec = document.getElementById('inventory-section');
      if (banner) {{
        if (open === 0) {{
          banner.style.display = 'flex';
          banner.querySelector('div > div:last-child').textContent = '0 open vulnerabilities \u2014 ' + total + ' findings resolved';
          if (invSec && !invSec._userToggled) invSec.style.display = 'none';
        }} else {{
          banner.style.display = 'none';
          if (invSec) invSec.style.display = 'block';
        }}
      }}
    }}

    // ── Load overrides from localStorage on page load ──
    (function() {{
      const overrides = JSON.parse(localStorage.getItem('vuln_overrides') || '{{}}');
      let applied = 0;
      for (const [vid, data] of Object.entries(overrides)) {{
        const row = document.querySelector('tr[data-vuln-id="' + vid + '"');
        if (!row) continue;
        applyOverrideVisual(row, data.status, data.note);
        applied++;
      }}
      if (applied > 0) refreshSummary();
    }})();

    // ── Sortable table columns ──
    document.querySelectorAll('.sort-header').forEach(th => {{
      th.addEventListener('click', (e) => {{
        e.stopPropagation();
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        const colIdx = Array.from(th.parentNode.children).indexOf(th);
        const sortType = th.dataset.sortType || 'string';
        const isAsc = th.classList.contains('asc');
        table.querySelectorAll('.sort-header').forEach(h => h.classList.remove('asc','desc'));
        th.classList.add(isAsc ? 'desc' : 'asc');
        const dir = isAsc ? -1 : 1;
        const rows = Array.from(tbody.querySelectorAll('tr'));
        rows.sort((a, b) => {{
          const aCell = a.children[colIdx];
          const bCell = b.children[colIdx];
          let aVal = aCell ? (aCell.dataset.sortVal || aCell.textContent.trim()) : '';
          let bVal = bCell ? (bCell.dataset.sortVal || bCell.textContent.trim()) : '';
          if (sortType === 'number') {{
            aVal = parseFloat(aVal) || 0;
            bVal = parseFloat(bVal) || 0;
            return (aVal - bVal) * dir;
          }}
          return aVal.localeCompare(bVal) * dir;
        }});
        const frag = document.createDocumentFragment();
        rows.forEach((row, idx) => {{
          row.children[0].textContent = idx + 1;
          frag.appendChild(row);
        }});
        tbody.appendChild(frag);
      }});
    }});
  </script>
</body>
</html>"""


# ── Override import ────────────────────────────────────────────

def import_overrides() -> int:
    """Import overrides from vuln_overrides.json sidecar file."""
    sidecar = PROJECT_ROOT / "reports" / "vuln_overrides.json"
    if not sidecar.exists():
        return 0
    import json
    overrides = json.loads(sidecar.read_text(encoding="utf-8"))
    count = 0
    for vid, data in overrides.items():
        update_vuln_status(vid, data["status"], data.get("note", ""))
        count += 1
    # Remove sidecar after import
    sidecar.unlink()
    return count


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="⊕ Security Vulnerability Dashboard")
    parser.add_argument("--no-open", action="store_true", help="Generate without opening browser")
    parser.add_argument("--seed", action="store_true", help="Seed manual audit findings + generate")
    parser.add_argument("--scan", action="store_true", help="Run OWASP grep scan, upsert, generate")
    parser.add_argument("--set-status", nargs="+", metavar=("VULN_ID", "STATUS"),
                        help="Set status for a vuln: VULN_ID STATUS [NOTE]")
    args = parser.parse_args()

    # Direct status update via CLI
    if args.set_status:
        vid = args.set_status[0]
        status = args.set_status[1] if len(args.set_status) > 1 else "remediated"
        note = args.set_status[2] if len(args.set_status) > 2 else ""
        valid = ("open", "remediated", "accepted", "false_positive")
        if status not in valid:
            print(f"  Error: status must be one of {valid}")
            return
        update_vuln_status(vid, status, note)
        print(f"  Updated {vid} → {status}" + (f" ({note})" if note else ""))

    # Import any pending overrides from sidecar
    imported = import_overrides()
    if imported:
        print(f"  Imported {imported} overrides from vuln_overrides.json")

    if args.seed:
        inserted, skipped = upsert_findings(SEED_FINDINGS)
        print(f"  Seed: {inserted} inserted, {skipped} already present")

    if args.scan:
        print("  Scanning Python files for OWASP patterns...")
        findings = run_owasp_scan()
        print(f"  Found {len(findings)} potential issues")
        inserted, skipped = upsert_findings(findings)
        print(f"  Scan: {inserted} new, {skipped} already tracked")

    vulns = load_all_vulns()
    print(f"  Total vulnerabilities in DB: {len(vulns)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html_content = render_html(vulns)
    OUT_PATH.write_text(html_content, encoding="utf-8")
    print(f"  Dashboard written to {OUT_PATH.as_posix()}")

    if not args.no_open:
        try:
            webbrowser.get("brave").open(OUT_PATH.as_uri())
        except Exception:
            webbrowser.open(OUT_PATH.as_uri())


if __name__ == "__main__":
    main()
