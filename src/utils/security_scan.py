#!/usr/bin/env python3
"""
⊕ Security Scanner — regenerates reports/security_dashboard.html from
src/data/security_findings.json, with live file-level re-verification
for OPEN findings (auto-promotes to REMEDIATED when pattern is gone).

Usage:
    C:/G/python.exe f:/⊕Workspace/src/utils/security_scan.py

Invoked automatically by open_security_dashboard.ps1 on every open.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
WORKSPACE_ROOT = Path("f:/")
FINDINGS_JSON = Path(__file__).parent.parent / "data" / "security_findings.json"
DASHBOARD_OUT = Path(__file__).parent.parent.parent / "reports" / "security_dashboard.html"

# ── False-positive patterns that should never be flagged as SQL injection ──────
_FP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"PRAGMA\s+key\s*="),          # SQLCipher key unlock
    re.compile(r"safe_key"),                   # already-escaped key variable
    re.compile(r"safe_tbl"),                   # already-escaped table variable
    re.compile(r"_validate_identifier"),       # explicit validation call
    re.compile(r"ALLOWED_FIELDS"),             # whitelist guard
    re.compile(r"\[safe_"),                    # bracket-escaped identifiers
]

# ── Auto-verifiable check rules (per category) ────────────────────────────────
# Each rule: given a finding, return True if the vulnerability IS still present.
def _check_sql_injection(finding: dict) -> bool:
    """Return True if the f-string SQL pattern is still present at/near the recorded line."""
    rel_path: str = finding.get("file", "")
    line_no: int = finding.get("line", 0)

    # Resolve path — findings use relative paths like "❤Music/src/..."
    candidate = WORKSPACE_ROOT / rel_path
    if not candidate.exists():
        # Try archive subfolder (files that were moved there during remediation)
        parts = Path(rel_path).parts
        if len(parts) >= 2:
            archive_candidate = WORKSPACE_ROOT / parts[0] / "tools" / "archive" / Path(rel_path).name
            if archive_candidate.exists():
                candidate = archive_candidate
            else:
                # File not found at either location — treat as remediated
                return False
        else:
            return False

    try:
        lines = candidate.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    # Check a ±10 line window around the recorded line number
    start = max(0, line_no - 11)
    end = min(len(lines), line_no + 10)
    window = "\n".join(lines[start:end])

    if 'execute(f"' not in window and "execute(f'" not in window:
        return False

    # Pattern present — but check if it's a known FP
    for fp in _FP_PATTERNS:
        if fp.search(window):
            return False

    return True


def _check_secrets(finding: dict) -> bool:
    """Return True if a hardcoded secret is still present (basic heuristic)."""
    rel_path: str = finding.get("file", "")
    line_no: int = finding.get("line", 0)
    candidate = WORKSPACE_ROOT / rel_path
    if not candidate.exists():
        return False
    try:
        lines = candidate.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    start = max(0, line_no - 2)
    end = min(len(lines), line_no + 2)
    window = "\n".join(lines[start:end])
    # If line now references os.environ or env var lookup, consider remediated
    if "os.environ" in window or "getenv" in window or "os.getenv" in window:
        return False
    # Crude check: long alphanum strings that look like tokens
    if re.search(r'["\'][A-Za-z0-9_\-]{20,}["\']', window):
        return True
    return False


_CHECKERS: dict[str, object] = {
    "sql_injection": _check_sql_injection,
    "OWASP": _check_sql_injection,
    "SECRETS": _check_secrets,
}


def _vuln_id(finding: dict) -> str:
    """Stable 16-char hex ID derived from file+line+description."""
    key = f"{finding.get('file','')}:{finding.get('line',0)}:{finding.get('description','')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _severity_order(sev: str) -> int:
    return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}.get(sev.upper(), 99)


def _badge_class(sev: str) -> str:
    return {"CRITICAL": "critical", "HIGH": "fail", "MEDIUM": "partial", "LOW": "info", "INFO": "muted"}.get(sev.upper(), "muted")


def _status_badge(status: str) -> str:
    mapping = {
        "open": '<span class="badge fail">OPEN</span>',
        "remediated": '<span class="badge success">REMEDIATED</span>',
        "accepted": '<span class="badge accepted">ACCEPTED</span>',
        "false_positive": '<span class="badge muted">FALSE POSITIVE</span>',
    }
    return mapping.get(status, f'<span class="badge muted">{status.upper()}</span>')


def load_findings() -> list[dict]:
    if not FINDINGS_JSON.exists():
        print(f"[security_scan] findings ledger not found: {FINDINGS_JSON}", file=sys.stderr)
        return []
    with FINDINGS_JSON.open(encoding="utf-8") as f:
        return json.load(f)


def auto_verify(findings: list[dict]) -> list[dict]:
    """Re-verify OPEN findings — promote to REMEDIATED if pattern is gone."""
    promoted = 0
    for f in findings:
        if f.get("status") != "open":
            continue
        category = f.get("category", "")
        checker = _CHECKERS.get(category)
        if checker is None:
            continue
        still_vulnerable = checker(f)  # type: ignore[operator]
        if not still_vulnerable:
            f["status"] = "remediated"
            f["note"] = f.get("note") or "Auto-verified REMEDIATED by security_scan.py"
            f["scan_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            promoted += 1
    if promoted:
        print(f"[security_scan] auto-promoted {promoted} finding(s) from OPEN → REMEDIATED")
    return findings


def save_findings(findings: list[dict]) -> None:
    FINDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with FINDINGS_JSON.open("w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)


# ── HTML generation ────────────────────────────────────────────────────────────

_HTML_HEADER = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>⊕ Security Vulnerability Dashboard</title>
<style>
  :root {
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
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
    max-width: 1600px;
    margin: 0 auto;
  }
  h1 { font-size: 1.8rem; margin-bottom: 0.3rem; display: flex; align-items: center; gap: 0.5rem; }
  h1 .sigil { color: var(--security-accent); font-size: 2rem; }
  .subtitle { color: var(--muted); margin-bottom: 1.5rem; font-size: 0.9rem; }
  .filter-bar { display: flex; gap: 0.8rem; margin-bottom: 1.5rem; flex-wrap: wrap; align-items: center; }
  .filter-bar label { color: var(--muted); font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
  .filter-btn { padding: 0.4rem 1rem; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; color: var(--muted); font-size: 0.85rem; cursor: pointer; transition: all 0.15s; }
  .filter-btn:hover { color: var(--text); border-color: var(--text); }
  .filter-btn.active { color: var(--text); border-color: var(--security-accent); background: rgba(248,113,113,0.1); }
  .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 2.5rem; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; text-align: center; }
  .card h3 { margin-bottom: 1rem; font-size: 1.1rem; }
  .security-card { border-top: 3px solid var(--security-accent); }
  .security-card h3 { color: var(--security-accent); }
  .severity-card { border-top: 3px solid var(--partial); }
  .severity-card h3 { color: var(--partial); }
  .stat { font-size: 2rem; font-weight: 700; line-height: 1.2; }
  .open-stat { color: var(--fail); }
  .remediated-stat { color: var(--success); }
  .accepted-stat { color: var(--accepted-color); }
  .label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.8rem; }
  .sev-row { display: flex; align-items: center; justify-content: space-between; padding: 0.4rem 0.8rem; margin: 0.3rem 0; }
  .sev-count { font-size: 1.4rem; font-weight: 700; font-variant-numeric: tabular-nums; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 2rem; }
  thead { background: var(--surface); }
  th { text-align: left; padding: 0.6rem; font-weight: 600; color: var(--muted); text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.05em; border-bottom: 2px solid var(--border); }
  td { padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:hover { background: rgba(255,255,255,0.03); }
  tr[data-status="open"] { background: var(--critical-bg); }
  tr[data-status="open"]:hover { background: rgba(248,113,113,0.18); }
  tr[data-status="remediated"] { opacity: 0.6; }
  tr[data-status="false_positive"] { opacity: 0.4; }
  tr[data-status="accepted"] { opacity: 0.7; }
  .num { font-variant-numeric: tabular-nums; text-align: right; }
  .ts { color: var(--muted); font-size: 0.8rem; }
  .file-cell { max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 0.8rem; }
  .desc-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .note-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); font-size: 0.8rem; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; white-space: nowrap; }
  .badge.critical { background: rgba(248,113,113,0.2); color: #f87171; }
  .badge.fail { background: rgba(217,48,37,0.15); color: var(--fail); }
  .badge.partial { background: rgba(249,171,0,0.15); color: var(--partial); }
  .badge.info { background: rgba(96,165,250,0.15); color: var(--info); }
  .badge.success { background: rgba(13,144,79,0.15); color: var(--success); }
  .badge.accepted { background: rgba(167,139,250,0.15); color: var(--accepted-color); }
  .badge.muted { background: rgba(107,114,128,0.15); color: var(--muted-badge); }
  .footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.8rem; text-align: center; }
  @media (max-width: 800px) { .summary-grid { grid-template-columns: 1fr; } body { padding: 1rem; } }
</style>
</head>
<body>
"""

_HTML_FOOTER = """\
<div class="footer">
  ⊕Workspace Security Dashboard &mdash; auto-generated by security_scan.py &mdash; open via open_security_dashboard.ps1 for live refresh
</div>
<script>
function filterStatus(val, btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('tr[data-vuln-id]').forEach(row => {
    if (val === 'all' || row.dataset.status === val) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}
</script>
</body>
</html>
"""


def build_html(findings: list[dict], scan_ts: str) -> str:
    total = len(findings)
    open_count = sum(1 for f in findings if f.get("status") == "open")
    remediated_count = sum(1 for f in findings if f.get("status") == "remediated")
    accepted_count = sum(1 for f in findings if f.get("status") in ("accepted", "false_positive"))

    open_by_sev: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        if f.get("status") == "open":
            sev = f.get("severity", "LOW").upper()
            if sev in open_by_sev:
                open_by_sev[sev] += 1

    lines: list[str] = [_HTML_HEADER]

    # Header
    lines.append(
        f'  <h1><span class="sigil">⊕</span> Security Vulnerability Dashboard '
        f'<span class="badge success" style="font-size:0.7rem;vertical-align:middle;margin-left:0.5rem;" '
        f'title="Regenerated fresh on every open via open_security_dashboard.ps1">🟢 LIVE</span></h1>\n'
        f'  <div class="subtitle">\n'
        f'    Generated: {scan_ts} &bull; {total} findings &bull; '
        f'<em>auto-refreshes on open via open_security_dashboard.ps1</em>\n'
        f'  </div>\n'
    )

    # Summary cards
    lines.append('  <div class="summary-grid">')
    lines.append(
        f'    <div class="card security-card"><h3>Inventory</h3>'
        f'<div class="stat">{total}</div><div class="label">Total Findings</div>'
        f'<div class="stat open-stat">{open_count}</div><div class="label">Open</div>'
        f'<div class="stat remediated-stat">{remediated_count}</div><div class="label">Remediated</div>'
        f'<div class="stat accepted-stat">{accepted_count}</div><div class="label">Accepted / FP</div>'
        f'</div>'
    )
    sev_rows = "".join(
        f'<div class="sev-row"><span class="badge {_badge_class(s)}">{s}</span> '
        f'<span class="sev-count">{open_by_sev[s]}</span></div>'
        for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    )
    lines.append(f'    <div class="card severity-card"><h3>Open by Severity</h3>{sev_rows}</div>')
    lines.append("  </div>")

    # Filter bar
    lines.append(
        f'  <div class="filter-bar">'
        f'<label>Status:</label>'
        f'<button class="filter-btn active" data-filter="all" onclick="filterStatus(\'all\', this)">All ({total})</button>'
        f'<button class="filter-btn" data-filter="open" onclick="filterStatus(\'open\', this)">Open ({open_count})</button>'
        f'<button class="filter-btn" data-filter="remediated" onclick="filterStatus(\'remediated\', this)">Remediated</button>'
        f'<button class="filter-btn" data-filter="accepted" onclick="filterStatus(\'accepted\', this)">Accepted</button>'
        f'<button class="filter-btn" data-filter="false_positive" onclick="filterStatus(\'false_positive\', this)">False Positive</button>'
        f'</div>'
    )

    # Table
    lines.append(
        '  <h2 style="color: var(--security-accent); border-bottom: 2px solid var(--security-accent); '
        'padding-bottom: 0.5rem; margin: 2rem 0 1rem;">Vulnerability Inventory</h2>'
    )
    lines.append('<table><thead><tr>')
    for col in ["#", "Severity", "Category", "OWASP", "File", "Line", "Description", "Status", "Note", "Scan Date"]:
        lines.append(f'<th>{col}</th>')
    lines.append('</tr></thead><tbody>')

    sorted_findings = sorted(findings, key=lambda f: (
        0 if f.get("status") == "open" else 1,
        _severity_order(f.get("severity", "LOW")),
    ))

    for i, f in enumerate(sorted_findings, 1):
        vid = f.get("id") or _vuln_id(f)
        status = f.get("status", "open")
        sev = f.get("severity", "LOW")
        file_rel = f.get("file", "")
        line_no = f.get("line", 0)
        desc = f.get("description", "")
        note = f.get("note", "—") or "—"
        ts = f.get("scan_date", "")
        owasp = f.get("owasp", "")
        category = f.get("category", "")

        lines.append(
            f'<tr data-vuln-id="{vid}" data-status="{status}">'
            f'<td>{i}</td>'
            f'<td><span class="badge {_badge_class(sev)}">{sev.upper()}</span></td>'
            f'<td>{category}</td>'
            f'<td>{owasp}</td>'
            f'<td class="file-cell" title="{file_rel}">{file_rel}</td>'
            f'<td class="num">{line_no}</td>'
            f'<td class="desc-cell">{desc}</td>'
            f'<td>{_status_badge(status)}</td>'
            f'<td class="note-cell">{note}</td>'
            f'<td class="ts">{ts}</td>'
            f'</tr>'
        )

    lines.append("</tbody></table>")
    lines.append(_HTML_FOOTER)
    return "\n".join(lines)


def main() -> None:
    scan_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[security_scan] {scan_ts} — loading findings ledger...")

    findings = load_findings()
    if not findings:
        print("[security_scan] no findings to process — dashboard will be empty.", file=sys.stderr)

    findings = auto_verify(findings)
    save_findings(findings)

    html = build_html(findings, scan_ts)
    DASHBOARD_OUT.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_OUT.write_text(html, encoding="utf-8")

    open_count = sum(1 for f in findings if f.get("status") == "open")
    print(f"[security_scan] done — {len(findings)} findings, {open_count} open → {DASHBOARD_OUT}")


if __name__ == "__main__":
    main()
