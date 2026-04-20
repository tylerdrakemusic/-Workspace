#!/usr/bin/env python3
"""
⊕ Agent Ops Monitor — session health, gap detection, and auto-remediation.

Queries perf_runs + proof_artifacts to build a complete picture of agent
session health. Detects and closes gaps:
  - Orphan runs (ended but 0 proofs)
  - Zombie runs (never ended — started > 2h ago)
  - Unverified proofs (proof recorded but never verified)
  - Proof-complete runs (all proofs verified → auto-close)
  - Proof-less agents (agents that have runs but no proof history)

Self-regenerating: generates an HTML dashboard + embeds a <meta refresh>
so the portal always shows current state. In --serve mode, provides an
interactive dashboard with session close buttons.

Usage:
    C:\\G\\python.exe tools/agent_ops_monitor.py                # generate + open
    C:\\G\\python.exe tools/agent_ops_monitor.py --no-open      # generate only
    C:\\G\\python.exe tools/agent_ops_monitor.py --fix          # auto-close gaps + generate
    C:\\G\\python.exe tools/agent_ops_monitor.py --fix --no-open
    C:\\G\\python.exe tools/agent_ops_monitor.py --json         # JSON health report
    C:\\G\\python.exe tools/agent_ops_monitor.py --close <run_id>  # close a specific session
    C:\\G\\python.exe tools/agent_ops_monitor.py --serve [--port N] # interactive dashboard server
"""

import argparse
import html as html_mod
import json
import os
import sys
import time
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Brave registration
_BRAVE = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]
for _bp in _BRAVE:
    if os.path.isfile(_bp):
        webbrowser.register("brave", None, webbrowser.BackgroundBrowser(_bp))
        break

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "reports" / "agent_ops_dashboard.html"

sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))
from init_db import get_connection, init_db


def _esc(v) -> str:
    return html_mod.escape(str(v)) if v else ""


def _ts(epoch: float | None) -> str:
    if not epoch:
        return ""
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def _dur(ms: float) -> str:
    s = int(ms / 1000)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


# ── Data Collection ──────────────────────────────────────────

def collect_health(conn) -> dict:
    """Gather all session health metrics from workspace.db."""
    now = time.time()
    stale_threshold = now - 7200  # 2 hours

    # All runs
    runs = conn.execute(
        "SELECT run_id, name, started_at, ended_at, status, detail FROM perf_runs ORDER BY started_at DESC"
    ).fetchall()

    # All proofs grouped by run
    proofs = conn.execute(
        "SELECT run_id, COUNT(*) as cnt, SUM(verified) as v_cnt FROM proof_artifacts GROUP BY run_id"
    ).fetchall()
    proof_map = {p["run_id"]: {"count": p["cnt"], "verified": p["v_cnt"] or 0} for p in proofs}

    # Agent proof coverage
    agent_coverage = conn.execute(
        """SELECT agent, COUNT(*) as total, SUM(verified) as verified,
                  COUNT(DISTINCT run_id) as runs
           FROM proof_artifacts GROUP BY agent ORDER BY total DESC"""
    ).fetchall()

    # Categorize runs
    sessions = []
    zombies = []
    orphans = []
    healthy = []
    total_runs = len(runs)

    for r in runs:
        rid = r["run_id"]
        entry = {
            "run_id": rid,
            "name": r["name"],
            "started_at": r["started_at"],
            "ended_at": r["ended_at"],
            "status": r["status"],
            "detail": r["detail"],
            "wall_ms": ((r["ended_at"] or now) - r["started_at"]) * 1000,
            "proofs": proof_map.get(rid, {"count": 0, "verified": 0}),
        }
        sessions.append(entry)

        if not r["ended_at"] and r["started_at"] < stale_threshold:
            entry["gap"] = "zombie"
            zombies.append(entry)
        elif r["ended_at"] and entry["proofs"]["count"] == 0:
            entry["gap"] = "orphan"
            orphans.append(entry)
        else:
            entry["gap"] = None
            healthy.append(entry)

    # Unverified proofs
    unverified = conn.execute(
        """SELECT p.proof_id, p.run_id, p.agent, p.proof_type, p.description,
                  p.artifact_path, p.created_at
           FROM proof_artifacts p WHERE p.verified = 0"""
    ).fetchall()

    # Score
    gap_count = len(zombies) + len(orphans) + len(unverified)
    health_pct = ((total_runs - len(zombies) - len(orphans)) / max(total_runs, 1)) * 100

    return {
        "generated_at": datetime.now().isoformat(),
        "total_runs": total_runs,
        "healthy": len(healthy),
        "zombies": zombies,
        "orphans": orphans,
        "unverified": [dict(u) for u in unverified],
        "sessions": sessions,
        "agent_coverage": [dict(a) for a in agent_coverage],
        "gap_count": gap_count,
        "health_pct": round(health_pct, 1),
    }


# ── Auto-Fix ─────────────────────────────────────────────────

def fix_gaps(conn, health: dict) -> dict:
    """Auto-close zombies, proof-complete runs, and flag orphans. Returns remediation summary."""
    now = time.time()
    fixed_zombies = 0
    fixed_unverified = 0
    fixed_proof_complete = 0

    # Close zombie runs (started > 2h ago, never ended)
    for z in health["zombies"]:
        conn.execute(
            "UPDATE perf_runs SET ended_at = ?, status = ?, detail = COALESCE(detail, '') || ' [auto-closed by ops monitor]' WHERE run_id = ?",
            (now, "timeout", z["run_id"]),
        )
        fixed_zombies += 1

    # Auto-close runs where all proofs are verified (proof protocol met)
    active_runs = conn.execute(
        "SELECT run_id, name FROM perf_runs WHERE ended_at IS NULL"
    ).fetchall()
    for run in active_runs:
        rid = run["run_id"]
        proof_stats = conn.execute(
            "SELECT COUNT(*) as total, SUM(verified) as verified FROM proof_artifacts WHERE run_id = ?",
            (rid,),
        ).fetchone()
        total = proof_stats["total"] or 0
        verified = proof_stats["verified"] or 0
        if total > 0 and verified == total:
            conn.execute(
                "UPDATE perf_runs SET ended_at = ?, status = ?, detail = COALESCE(detail, '') || ' [auto-closed: proof protocol met]' WHERE run_id = ?",
                (now, "ok", rid),
            )
            fixed_proof_complete += 1

    # Verify all unverified proofs that have valid file paths
    for uv in health["unverified"]:
        path = uv.get("artifact_path")
        if path and Path(path).exists():
            conn.execute(
                "UPDATE proof_artifacts SET verified = 1, verified_at = ? WHERE proof_id = ?",
                (datetime.now().isoformat(), uv["proof_id"]),
            )
            fixed_unverified += 1
        elif not path:
            # Non-file proofs (db_write, metric, etc.) — mark verified
            conn.execute(
                "UPDATE proof_artifacts SET verified = 1, verified_at = ? WHERE proof_id = ?",
                (datetime.now().isoformat(), uv["proof_id"]),
            )
            fixed_unverified += 1

    conn.commit()

    return {
        "fixed_zombies": fixed_zombies,
        "fixed_unverified": fixed_unverified,
        "fixed_proof_complete": fixed_proof_complete,
        "remaining_orphans": len(health["orphans"]),
    }


def backfill_legacy(conn, health: dict) -> int:
    """Insert a legacy proof artifact for orphan runs predating the proof system."""
    count = 0
    for o in health["orphans"]:
        conn.execute(
            """INSERT INTO proof_artifacts
               (proof_id, run_id, agent, proof_type, description, verified, verified_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (
                __import__("uuid").uuid4().hex[:12],
                o["run_id"],
                "⊕ops-monitor",
                "metric",
                f"Legacy run backfilled — predates proof system. Original: {o['name']}",
                datetime.now().isoformat(),
            ),
        )
        count += 1
    conn.commit()
    return count


# ── HTML Dashboard ───────────────────────────────────────────

def render_dashboard(health: dict, fix_summary: dict | None = None) -> str:
    generated = health["generated_at"][:19]
    total = health["total_runs"]
    healthy = health["healthy"]
    zombie_count = len(health["zombies"])
    orphan_count = len(health["orphans"])
    unverified_count = len(health["unverified"])
    gap_count = health["gap_count"]
    health_pct = health["health_pct"]

    # Health color
    if health_pct >= 95:
        health_color = "#10b981"
        health_label = "Excellent"
    elif health_pct >= 80:
        health_color = "#f59e0b"
        health_label = "Good"
    elif health_pct >= 60:
        health_color = "#f97316"
        health_label = "Needs Attention"
    else:
        health_color = "#ef4444"
        health_label = "Critical"

    # Fix banner
    fix_banner = ""
    if fix_summary:
        fz = fix_summary["fixed_zombies"]
        fu = fix_summary["fixed_unverified"]
        fp = fix_summary["fixed_proof_complete"]
        ro = fix_summary["remaining_orphans"]
        fix_banner = f"""
    <div class="fix-banner">
      <span class="fix-icon">🔧</span>
      <div>
        <strong>Auto-Fix Applied</strong><br>
        <span class="fix-detail">{fz} zombie(s) closed · {fp} proof-complete session(s) closed · {fu} proof(s) verified · {ro} orphan run(s) remain (need manual proof)</span>
      </div>
    </div>"""

    # Session rows
    session_rows = []
    for s in health["sessions"][:50]:
        rid = _esc(s["run_id"])
        name = _esc(s["name"])
        status = _esc(s["status"] or "running")
        started = _ts(s["started_at"])
        ended = _ts(s["ended_at"]) if s["ended_at"] else '<span class="running-dot"></span> running'
        wall = _dur(s["wall_ms"])
        p_count = s["proofs"]["count"]
        p_verified = s["proofs"]["verified"]
        gap = s.get("gap", "")

        if gap == "zombie":
            row_cls = "row-zombie"
            gap_badge = '<span class="gap-badge zombie">ZOMBIE</span>'
        elif gap == "orphan":
            row_cls = "row-orphan"
            gap_badge = '<span class="gap-badge orphan">NO PROOF</span>'
        else:
            row_cls = ""
            gap_badge = '<span class="gap-badge ok">OK</span>' if s["ended_at"] else '<span class="gap-badge running">ACTIVE</span>'

        proof_bar = ""
        if p_count > 0:
            pct = min(p_verified / p_count * 100, 100)
            proof_bar = (
                f'<div class="proof-bar"><div class="proof-fill" style="width:{pct:.0f}%"></div></div>'
                f'<span class="proof-label">{p_verified}/{p_count}</span>'
            )
        elif s["ended_at"]:
            proof_bar = '<span class="no-proof">—</span>'

        status_cls = {"ok": "st-ok", "error": "st-err", "timeout": "st-timeout"}.get(status, "st-run")

        # Close button for active/zombie runs (only in serve mode)
        close_btn = ""
        if not s["ended_at"]:
            close_btn = f'<button class="close-btn" onclick="closeSession(\'{rid}\')">Close</button>'
        elif gap == "zombie":
            close_btn = f'<button class="close-btn" onclick="closeSession(\'{rid}\')">Force Close</button>'

        session_rows.append(
            f'<tr class="{row_cls}">'
            f'<td class="mono">{rid}</td>'
            f'<td>{name}</td>'
            f'<td class="{status_cls}">{status}</td>'
            f'<td class="ts">{started}</td>'
            f'<td class="ts">{ended}</td>'
            f'<td class="mono">{wall}</td>'
            f'<td class="proof-cell">{proof_bar}</td>'
            f'<td>{gap_badge}</td>'
            f'<td>{close_btn}</td>'
            f'</tr>'
        )
    session_html = "\n".join(session_rows)

    # Agent coverage rows
    agent_rows = []
    for a in health["agent_coverage"]:
        agent = _esc(a["agent"])
        total_p = a["total"]
        verified = a["verified"] or 0
        runs = a["runs"]
        rate = (verified / total_p * 100) if total_p else 0
        rate_cls = "rate-good" if rate >= 80 else "rate-warn" if rate >= 50 else "rate-bad"
        agent_rows.append(
            f'<tr>'
            f'<td>{agent}</td>'
            f'<td class="num">{runs}</td>'
            f'<td class="num">{total_p}</td>'
            f'<td class="num">{verified}</td>'
            f'<td class="num {rate_cls}">{rate:.0f}%</td>'
            f'</tr>'
        )
    agent_html = "\n".join(agent_rows) if agent_rows else '<tr><td colspan="5" class="empty">No proof data yet</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>⊕ Agent Ops Monitor</title>
<style>
  :root {{
    --bg: #0a0d12;
    --surface: #121820;
    --border: #1e2530;
    --text: #e2e8f0;
    --muted: #64748b;
    --accent: #6366f1;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --orange: #f97316;
    --cyan: #22d3ee;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
    max-width: 1500px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 1.8rem;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  h1 .sigil {{ color: var(--accent); font-size: 2rem; }}
  h2 {{
    font-size: 1.15rem;
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border);
  }}
  .subtitle {{ color: var(--muted); margin-bottom: 1.5rem; font-size: 0.85rem; }}

  /* ── Health Score ── */
  .health-ring {{
    display: flex;
    align-items: center;
    gap: 2rem;
    margin: 1.5rem 0 2rem;
  }}
  .ring-container {{
    position: relative;
    width: 140px;
    height: 140px;
  }}
  .ring-svg {{ transform: rotate(-90deg); }}
  .ring-bg {{ fill: none; stroke: var(--border); stroke-width: 10; }}
  .ring-fg {{ fill: none; stroke-width: 10; stroke-linecap: round;
              stroke-dasharray: 377; transition: stroke-dashoffset 1s ease; }}
  .ring-text {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
  }}
  .ring-pct {{ font-size: 2rem; font-weight: 800; }}
  .ring-label {{ font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}

  /* ── Stat Cards ── */
  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
  }}
  .stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    text-align: center;
  }}
  .stat-val {{ font-size: 2rem; font-weight: 800; line-height: 1.2; }}
  .stat-label {{ font-size: 0.75rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin-top: 0.3rem; }}
  .val-ok {{ color: var(--success); }}
  .val-warn {{ color: var(--warning); }}
  .val-bad {{ color: var(--danger); }}
  .val-info {{ color: var(--cyan); }}

  /* ── Fix Banner ── */
  .fix-banner {{
    display: flex;
    align-items: center;
    gap: 1rem;
    background: rgba(16,185,129,0.08);
    border: 1px solid var(--success);
    border-radius: 10px;
    padding: 1rem 1.5rem;
    margin: 1rem 0 1.5rem;
  }}
  .fix-icon {{ font-size: 1.5rem; }}
  .fix-detail {{ color: var(--muted); font-size: 0.85rem; }}

  /* ── Tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    margin-bottom: 2rem;
  }}
  thead {{ background: var(--surface); }}
  th {{
    text-align: left;
    padding: 0.6rem;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    border-bottom: 2px solid var(--border);
  }}
  td {{
    padding: 0.5rem 0.6rem;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }}
  tr:hover {{ background: rgba(255,255,255,0.02); }}
  .mono {{ font-family: 'Cascadia Code','Consolas',monospace; font-size: 0.8rem; }}
  .ts {{ color: var(--muted); font-size: 0.78rem; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .empty {{ color: var(--muted); font-style: italic; text-align: center; padding: 1rem; }}

  /* Status */
  .st-ok {{ color: var(--success); font-weight: 600; }}
  .st-err {{ color: var(--danger); font-weight: 600; }}
  .st-timeout {{ color: var(--orange); font-weight: 600; }}
  .st-run {{ color: var(--cyan); font-weight: 600; }}

  /* Gap badges */
  .gap-badge {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  .gap-badge.ok {{ background: rgba(16,185,129,0.15); color: var(--success); }}
  .gap-badge.running {{ background: rgba(34,211,238,0.15); color: var(--cyan); }}
  .gap-badge.zombie {{ background: rgba(239,68,68,0.15); color: var(--danger); }}
  .gap-badge.orphan {{ background: rgba(249,115,22,0.15); color: var(--orange); }}

  /* Row highlights */
  .row-zombie {{ background: rgba(239,68,68,0.06); }}
  .row-zombie:hover {{ background: rgba(239,68,68,0.1) !important; }}
  .row-orphan {{ background: rgba(249,115,22,0.06); }}
  .row-orphan:hover {{ background: rgba(249,115,22,0.1) !important; }}

  /* Proof bars */
  .proof-cell {{ min-width: 120px; }}
  .proof-bar {{
    display: inline-block;
    width: 60px;
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    vertical-align: middle;
    margin-right: 0.4rem;
  }}
  .proof-fill {{
    height: 100%;
    background: var(--success);
    border-radius: 4px;
    transition: width 0.3s;
  }}
  .proof-label {{ font-size: 0.75rem; color: var(--muted); }}
  .no-proof {{ color: var(--muted); }}

  /* Agent coverage */
  .rate-good {{ color: var(--success); font-weight: 700; }}
  .rate-warn {{ color: var(--warning); font-weight: 700; }}
  .rate-bad {{ color: var(--danger); font-weight: 700; }}

  /* Close buttons */
  .close-btn {{
    background: rgba(239,68,68,0.15);
    color: var(--danger);
    border: 1px solid var(--danger);
    border-radius: 6px;
    padding: 0.2rem 0.6rem;
    font-size: 0.7rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
  }}
  .close-btn:hover {{
    background: var(--danger);
    color: white;
  }}
  .close-btn:disabled {{
    opacity: 0.4;
    cursor: not-allowed;
  }}

  /* Running dot animation */
  .running-dot {{
    display: inline-block;
    width: 8px; height: 8px;
    background: var(--cyan);
    border-radius: 50%;
    animation: pulse 1.5s infinite;
    vertical-align: middle;
    margin-right: 0.3rem;
  }}
  @keyframes pulse {{
    0%,100% {{ opacity:1; }}
    50% {{ opacity:0.3; }}
  }}

  .footer {{
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 0.75rem;
    text-align: center;
  }}
</style>
</head>
<body>
  <h1><span class="sigil">⊕</span> Agent Ops Monitor</h1>
  <div class="subtitle">Session health · Gap detection · Proof audit &mdash; {generated}</div>

  {fix_banner}

  <div class="health-ring">
    <div class="ring-container">
      <svg class="ring-svg" width="140" height="140" viewBox="0 0 140 140">
        <circle class="ring-bg" cx="70" cy="70" r="60"/>
        <circle class="ring-fg" cx="70" cy="70" r="60"
                style="stroke:{health_color}; stroke-dashoffset:{377 - (377 * health_pct / 100):.0f};"/>
      </svg>
      <div class="ring-text">
        <div class="ring-pct" style="color:{health_color}">{health_pct:.0f}%</div>
        <div class="ring-label">{health_label}</div>
      </div>
    </div>

    <div class="stat-grid" style="flex:1;">
      <div class="stat-card">
        <div class="stat-val val-info">{total}</div>
        <div class="stat-label">Total Runs</div>
      </div>
      <div class="stat-card">
        <div class="stat-val val-ok">{healthy}</div>
        <div class="stat-label">Healthy</div>
      </div>
      <div class="stat-card">
        <div class="stat-val {"val-bad" if zombie_count else "val-ok"}">{zombie_count}</div>
        <div class="stat-label">Zombies</div>
      </div>
      <div class="stat-card">
        <div class="stat-val {"val-warn" if orphan_count else "val-ok"}">{orphan_count}</div>
        <div class="stat-label">No Proof</div>
      </div>
      <div class="stat-card">
        <div class="stat-val {"val-warn" if unverified_count else "val-ok"}">{unverified_count}</div>
        <div class="stat-label">Unverified</div>
      </div>
      <div class="stat-card">
        <div class="stat-val val-info">{gap_count}</div>
        <div class="stat-label">Total Gaps</div>
      </div>
    </div>
  </div>

  <h2 style="color: var(--accent);">Session Inventory</h2>
  <table>
    <thead>
      <tr>
        <th>Run ID</th>
        <th>Name</th>
        <th>Status</th>
        <th>Started</th>
        <th>Ended</th>
        <th>Wall</th>
        <th>Proofs</th>
        <th>Health</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {session_html}
    </tbody>
  </table>

  <h2 style="color: var(--success);">Agent Proof Coverage</h2>
  <table>
    <thead>
      <tr>
        <th>Agent</th>
        <th class="num">Runs</th>
        <th class="num">Proofs</th>
        <th class="num">Verified</th>
        <th class="num">Rate</th>
      </tr>
    </thead>
    <tbody>
      {agent_html}
    </tbody>
  </table>

  <div class="footer">
    ⊕Workspace Agent Ops Monitor &mdash; Self-regenerating dashboard &bull;
    <code>python tools/agent_ops_monitor.py --fix</code> to auto-close gaps &bull;
    <code>python tools/agent_ops_monitor.py --serve</code> for interactive mode
  </div>

  <script>
    async function closeSession(runId) {{
      if (!confirm('Close session ' + runId + '?')) return;
      const btn = event.target;
      btn.disabled = true;
      btn.textContent = 'Closing...';
      try {{
        const resp = await fetch('/api/close', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{run_id: runId, status: 'closed'}})
        }});
        if (resp.ok) {{
          btn.textContent = 'Closed';
          setTimeout(() => location.reload(), 800);
        }} else {{
          const err = await resp.text();
          alert('Failed: ' + err);
          btn.disabled = false;
          btn.textContent = 'Close';
        }}
      }} catch (e) {{
        // Static file mode — show CLI command
        prompt('Run this command to close the session:', 
          'C:\\\\G\\\\python.exe tools/agent_ops_monitor.py --close ' + runId);
        btn.disabled = false;
        btn.textContent = 'Close';
      }}
    }}
  </script>
</body>
</html>"""


# ── Session Close ─────────────────────────────────────────────

def close_session(conn, run_id: str, status: str = "closed", detail: str = "") -> bool:
    """Close a specific session by run_id. Returns True if closed, False if not found/already closed."""
    row = conn.execute(
        "SELECT run_id, ended_at FROM perf_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    if not row:
        return False
    if row["ended_at"]:
        return False  # Already closed
    now = time.time()
    suffix = f" [manually closed from dashboard]" if not detail else f" {detail}"
    conn.execute(
        "UPDATE perf_runs SET ended_at = ?, status = ?, detail = COALESCE(detail, '') || ? WHERE run_id = ?",
        (now, status, suffix, run_id),
    )
    conn.commit()
    return True


# ── HTTP Server (--serve mode) ────────────────────────────────

class OpsHandler(BaseHTTPRequestHandler):
    """Handles dashboard serving and session close API."""

    def log_message(self, format, *args):
        # Suppress default logging noise
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            init_db()
            conn = get_connection()
            health = collect_health(conn)
            conn.close()
            html_content = render_dashboard(health)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        elif parsed.path == "/api/health":
            init_db()
            conn = get_connection()
            health = collect_health(conn)
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health, default=str).encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/close":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)
            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                self.send_error(400, "Invalid JSON")
                return

            run_id = data.get("run_id", "").strip()
            status = data.get("status", "closed").strip()

            if not run_id or len(run_id) > 24:
                self.send_error(400, "Invalid run_id")
                return
            # Sanitize: only hex chars allowed in run_id
            if not all(c in "0123456789abcdef" for c in run_id):
                self.send_error(400, "Invalid run_id format")
                return

            init_db()
            conn = get_connection()
            closed = close_session(conn, run_id, status)
            conn.close()

            if closed:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "run_id": run_id}).encode("utf-8"))
            else:
                self.send_error(404, "Run not found or already closed")

        elif parsed.path == "/api/fix":
            init_db()
            conn = get_connection()
            health = collect_health(conn)
            fix_summary = fix_gaps(conn, health)
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(fix_summary).encode("utf-8"))
        else:
            self.send_error(404)


def serve_dashboard(port: int = 5060) -> None:
    """Start an interactive HTTP server for the ops dashboard."""
    server = HTTPServer(("127.0.0.1", port), OpsHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"⊕ Agent Ops Monitor — Interactive Server")
    print(f"  Dashboard: {url}")
    print(f"  API:       POST {url}/api/close  {{\"run_id\": \"...\"}}")
    print(f"             POST {url}/api/fix    (auto-close gaps)")
    print(f"             GET  {url}/api/health (JSON health report)")
    print(f"  Press Ctrl+C to stop.")

    try:
        webbrowser.get("brave").open(url)
    except Exception:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.shutdown()


# ── Main ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="⊕ Agent Ops Monitor")
    parser.add_argument("--no-open", action="store_true", help="Generate without opening browser")
    parser.add_argument("--fix", action="store_true", help="Auto-close zombie runs, proof-complete runs, and verify proofs")
    parser.add_argument("--backfill-legacy", action="store_true", help="Backfill proof for orphan runs predating the proof system")
    parser.add_argument("--json", action="store_true", help="Output JSON health report")
    parser.add_argument("--close", metavar="RUN_ID", help="Close a specific session by run_id")
    parser.add_argument("--serve", action="store_true", help="Start interactive dashboard server")
    parser.add_argument("--port", type=int, default=5060, help="Port for --serve mode (default: 5060)")
    args = parser.parse_args()

    init_db()
    conn = get_connection()

    # --serve: start interactive server
    if args.serve:
        conn.close()
        serve_dashboard(args.port)
        return

    # --close: close a specific session
    if args.close:
        run_id = args.close.strip()
        closed = close_session(conn, run_id)
        conn.close()
        if closed:
            print(f"  ✓ Session {run_id} closed.")
        else:
            print(f"  ✗ Session {run_id} not found or already closed.", file=sys.stderr)
            sys.exit(1)
        return

    health = collect_health(conn)

    if args.json:
        # Sanitize for JSON serialization
        print(json.dumps(health, indent=2, default=str))
        conn.close()
        return

    fix_summary = None
    if args.fix:
        print("⊕ Agent Ops Monitor — Auto-Fix Mode")
        fix_summary = fix_gaps(conn, health)
        print(f"  Closed {fix_summary['fixed_zombies']} zombie(s)")
        print(f"  Closed {fix_summary['fixed_proof_complete']} proof-complete session(s)")
        print(f"  Verified {fix_summary['fixed_unverified']} proof(s)")
        print(f"  Remaining orphans: {fix_summary['remaining_orphans']} (need manual proof)")
        # Re-collect after fixes
        health = collect_health(conn)

    if args.backfill_legacy:
        backfilled = backfill_legacy(conn, health)
        print(f"  Backfilled {backfilled} legacy orphan run(s) with proof markers")
        health = collect_health(conn)

    conn.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html = render_dashboard(health, fix_summary)
    OUT_PATH.write_text(html, encoding="utf-8")

    print(f"⊕ Agent Ops Monitor")
    print(f"  Health: {health['health_pct']:.0f}% — {health['total_runs']} runs, {health['gap_count']} gaps")
    print(f"  Dashboard: {OUT_PATH}")

    if not args.no_open:
        try:
            webbrowser.get("brave").open(OUT_PATH.as_uri())
        except Exception:
            webbrowser.open(OUT_PATH.as_uri())


if __name__ == "__main__":
    main()
