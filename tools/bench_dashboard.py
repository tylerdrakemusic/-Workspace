#!/usr/bin/env python3
"""
⊕ Unified Benchmark Dashboard

Pulls data from two encrypted SQLCipher databases:
  1. ⟨ψ⟩Quantum  → Shor's algorithm benchmarks  (QUANTUM_DB_KEY)
  2. ⊕Workspace  → Agent performance runs         (WORKSPACE_DB_KEY)

Renders a single static HTML file with tab-switching between views.

Usage:
  python tools/bench_dashboard.py              # generate + open in browser
  python tools/bench_dashboard.py --no-open    # generate only
"""

import argparse
import html
import os
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "reports" / "benchmark_dashboard.html"

# Register Brave on Windows (not known to webbrowser by default)
_BRAVE_PATHS = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]
for _bp in _BRAVE_PATHS:
    if os.path.isfile(_bp):
        webbrowser.register("brave", None, webbrowser.BackgroundBrowser(_bp))
        break

# DB access — both projects
sys.path.insert(0, str(PROJECT_ROOT / "src"))

QUANTUM_ROOT = PROJECT_ROOT.parent / "⟨ψ⟩Quantum"
QUANTUM_DB = QUANTUM_ROOT / "src" / "data" / "quantumpsi.db"
WORKSPACE_DB = PROJECT_ROOT / "src" / "data" / "workspace.db"


# ── Data loaders ───────────────────────────────────────────────

def _sqlcipher_conn(db_path: Path, env_key: str):
    """Open a read-only SQLCipher connection."""
    import sqlcipher3
    key = os.environ.get(env_key, "")
    if not key:
        return None
    if not db_path.exists():
        return None
    conn = sqlcipher3.connect(str(db_path))
    safe_key = key.replace("'", "''")
    conn.execute(f"PRAGMA key='{safe_key}'")
    conn.execute("PRAGMA cipher_page_size=4096")
    conn.execute("PRAGMA kdf_iter=256000")
    conn.execute("PRAGMA cipher_hmac_algorithm=HMAC_SHA512")
    conn.row_factory = sqlcipher3.Row
    return conn


def load_quantum_benchmarks() -> list[dict]:
    """Load Shor's algorithm benchmark rows from quantumpsi.db."""
    conn = _sqlcipher_conn(QUANTUM_DB, "QUANTUM_DB_KEY")
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT total_time_sec, required_qubits, n_value, order_r, "
            "factor1, factor2, backend, timestamp FROM benchmarks ORDER BY id"
        ).fetchall()
    except Exception:
        conn.close()
        return []
    conn.close()
    result = []
    for r in rows:
        result.append({
            "total_time_sec": str(r["total_time_sec"]),
            "required_qubits": str(r["required_qubits"]),
            "N": str(r["n_value"]),
            "order_r": str(r["order_r"]) if r["order_r"] is not None else "",
            "factor1": str(r["factor1"]) if r["factor1"] is not None else "",
            "factor2": str(r["factor2"]) if r["factor2"] is not None else "",
            "backend": r["backend"] or "",
            "timestamp": r["timestamp"] or "",
        })
    return result


def load_quantum_policy_events(limit: int = 20) -> list[dict]:
    """Load latest benchmark/cache execution policy events from quantumpsi.db."""
    conn = _sqlcipher_conn(QUANTUM_DB, "QUANTUM_DB_KEY")
    if conn is None:
        return []
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='policy_events'"
        ).fetchone()
        if not exists:
            conn.close()
            return []
        rows = conn.execute(
            "SELECT event_time, policy_id, event_type, status, source, detail, next_run_at "
            "FROM policy_events "
            "WHERE policy_id='shors_monthly_benchmark' "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except Exception:
        conn.close()
        return []
    conn.close()

    result = []
    for r in rows:
        result.append(
            {
                "event_time": r["event_time"] or "",
                "policy_id": r["policy_id"] or "",
                "event_type": r["event_type"] or "",
                "status": r["status"] or "",
                "source": r["source"] or "",
                "detail": r["detail"] or "",
                "next_run_at": r["next_run_at"] or "",
            }
        )
    return result


def load_quantum_schedule_policy() -> dict:
    """Load canonical monthly schedule policy from quantum config file."""
    config_path = QUANTUM_ROOT / "src" / "config" / "execution_policy.json"
    try:
        import json

        with open(config_path, encoding="utf-8") as fh:
            data = json.load(fh)
        schedule = data.get("schedules", {}).get("shors_monthly_benchmark", {})
        cap = int(data.get("qpu_caps_seconds", {}).get("shors_monthly_benchmark", 300))
        day = int(schedule.get("day_of_month", 1))
        hour = int(schedule.get("hour", 2))
        minute = int(schedule.get("minute", 0))
        return {
            "day": day,
            "hour": hour,
            "minute": minute,
            "qpu_cap_seconds": cap,
            "task_name": schedule.get("task_name", "ShorsMonthlyBench"),
        }
    except Exception:
        return {
            "day": 1,
            "hour": 2,
            "minute": 0,
            "qpu_cap_seconds": 300,
            "task_name": "ShorsMonthlyBench",
        }


def _next_monthly_run_iso(day: int, hour: int, minute: int) -> str:
    """Compute next monthly run timestamp in UTC."""
    now = datetime.now(timezone.utc)
    candidate = datetime(now.year, now.month, day, hour, minute, tzinfo=timezone.utc)
    if candidate <= now:
        if now.month == 12:
            candidate = datetime(now.year + 1, 1, day, hour, minute, tzinfo=timezone.utc)
        else:
            candidate = datetime(now.year, now.month + 1, day, hour, minute, tzinfo=timezone.utc)
    return candidate.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_agent_perf() -> list[dict]:
    """Load agent perf runs + steps from workspace.db."""
    conn = _sqlcipher_conn(WORKSPACE_DB, "WORKSPACE_DB_KEY")
    if conn is None:
        return []
    try:
        runs = conn.execute(
            "SELECT r.run_id, r.name, r.status, r.started_at, r.ended_at, r.detail, "
            "  COUNT(s.step_id) AS step_count, "
            "  COALESCE(SUM(s.elapsed_ms), 0) AS step_ms "
            "FROM perf_runs r LEFT JOIN perf_steps s ON r.run_id = s.run_id "
            "GROUP BY r.run_id ORDER BY r.started_at DESC"
        ).fetchall()
    except Exception:
        conn.close()
        return []

    result = []
    for r in runs:
        started = r["started_at"] or 0
        ended = r["ended_at"] or time.time()
        wall_ms = (ended - started) * 1000
        ts = datetime.fromtimestamp(started).strftime("%Y-%m-%d %H:%M:%S") if started else ""
        result.append({
            "run_id": r["run_id"],
            "name": r["name"] or "",
            "status": r["status"] or "running",
            "started": ts,
            "wall_ms": wall_ms,
            "step_count": r["step_count"],
            "step_ms": r["step_ms"] or 0,
            "detail": r["detail"] or "",
        })

    # Also load steps for the expandable view
    steps_by_run: dict[str, list[dict]] = {}
    try:
        steps = conn.execute(
            "SELECT step_id, run_id, agent, description, elapsed_ms, status, detail "
            "FROM perf_steps ORDER BY started_at"
        ).fetchall()
        for s in steps:
            rid = s["run_id"]
            if rid not in steps_by_run:
                steps_by_run[rid] = []
            steps_by_run[rid].append({
                "agent": s["agent"] or "",
                "description": s["description"] or "",
                "elapsed_ms": s["elapsed_ms"] or 0,
                "status": s["status"] or "incomplete",
                "detail": s["detail"] or "",
            })
    except Exception:
        pass

    conn.close()

    for r in result:
        r["steps"] = steps_by_run.get(r["run_id"], [])

    return result


# ── Helpers ────────────────────────────────────────────────────

def _esc(val: str) -> str:
    return html.escape(val) if val else "&mdash;"


def _fmt_duration(ms: float) -> str:
    total_s = int(ms / 1000)
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    if h >= 24:
        d, h = divmod(h, 24)
        return f"{d}d {h:02d}:{m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def _status_badge(status: str) -> str:
    low = status.lower()
    if low in ("ok", "success"):
        return '<span class="badge success">OK</span>'
    if low in ("error", "fail", "failed"):
        return '<span class="badge fail">ERROR</span>'
    if low in ("running", "in-progress"):
        return '<span class="badge running">RUNNING</span>'
    return f'<span class="badge partial">{_esc(status.upper())}</span>'


def _quantum_status_badge(order_r: str, f1: str, f2: str) -> str:
    if f1 and f2 and f1 not in ("", "None") and f2 not in ("", "None"):
        return '<span class="badge success">SUCCESS</span>'
    if order_r == "-1" or not order_r:
        return '<span class="badge fail">FAILED</span>'
    return '<span class="badge partial">PARTIAL</span>'


def _classify_backend(backend: str) -> str:
    if not backend:
        return "hardware"
    low = backend.lower()
    if "aer" in low or "sim" in low or "fake" in low:
        return "simulator"
    return "hardware"


def _policy_badge(status: str) -> str:
    low = status.lower()
    if low in ("succeeded", "started"):
        return '<span class="badge success">{}</span>'.format(_esc(low.upper()))
    if low in ("failed", "deferred", "manual_override"):
        return '<span class="badge fail">{}</span>'.format(_esc(low.upper()))
    if low in ("skipped",):
        return '<span class="badge partial">{}</span>'.format(_esc(low.upper()))
    return '<span class="badge partial">UNKNOWN</span>'


def _quantum_policy_panel(events: list[dict], policy: dict) -> str:
    next_run = events[0].get("next_run_at", "") if events else ""
    if not next_run:
        next_run = _next_monthly_run_iso(policy["day"], policy["hour"], policy["minute"])

    latest = events[0] if events else {
        "status": "unknown",
        "event_type": "none",
        "event_time": "no events",
        "detail": "No execution-policy events found yet.",
    }

    alert_text = "Operational"
    alert_class = "badge success"
    if latest["status"].lower() in ("failed", "deferred", "manual_override"):
        alert_text = "Attention Needed"
        alert_class = "badge fail"
    elif latest["status"].lower() in ("skipped", "unknown"):
        alert_text = "Check Policy"
        alert_class = "badge partial"

    rows = []
    for event in events[:6]:
        rows.append(
            "<tr>"
            f"<td class='ts'>{_esc(event['event_time'])}</td>"
            f"<td>{_esc(event['event_type'])}</td>"
            f"<td>{_policy_badge(event['status'])}</td>"
            f"<td class='detail-cell'>{_esc(event['detail'])}</td>"
            "</tr>"
        )
    events_table = (
        "<table class='policy-table'><thead><tr><th>Event Time</th><th>Event</th><th>Status</th><th>Detail</th></tr></thead><tbody>"
        + ("".join(rows) if rows else "<tr><td colspan='4' class='empty'>No events yet.</td></tr>")
        + "</tbody></table>"
    )

    return f"""
    <div class="summary-grid summary-grid-3">
      <div class="card policy-card">
        <h3>Benchmark Policy Health</h3>
        <div class="stat">{_policy_badge(latest['status'])}</div>
        <div class="label">Latest Status</div>
        <div class="label">{_esc(latest['event_type'])} @ {_esc(latest['event_time'])}</div>
      </div>
      <div class="card policy-card">
        <h3>Next Scheduled Run (UTC)</h3>
        <div class="stat" style="font-size:1.2rem">{_esc(next_run)}</div>
        <div class="label">Task { _esc(policy['task_name']) }</div>
        <div class="label">Day {policy['day']} @ {policy['hour']:02d}:{policy['minute']:02d}</div>
      </div>
      <div class="card policy-card">
        <h3>Alert</h3>
        <div class="stat"><span class="{alert_class}">{alert_text}</span></div>
        <div class="label">Shown near next-run context</div>
        <div class="label">QPU cap: {policy['qpu_cap_seconds']}s</div>
      </div>
    </div>
    <h2 class="policy-heading">Execution Policy Events</h2>
    {events_table}
    """


# ── Quantum tab builders ──────────────────────────────────────

def _quantum_summary(hw_rows: list[dict], sim_rows: list[dict]) -> str:
    def stats(rows):
        total = len(rows)
        successes = sum(1 for r in rows if r.get("factor1") and r.get("factor2"))
        times = [float(r["total_time_sec"]) for r in rows if r.get("total_time_sec")]
        avg_time = sum(times) / len(times) if times else 0
        return {"total": total, "successes": successes, "avg_time": avg_time}

    hw = stats(hw_rows)
    sim = stats(sim_rows)
    return f"""
    <div class="summary-grid">
      <div class="card hw-card">
        <h3>IBM Quantum Hardware</h3>
        <div class="stat">{hw['total']}</div><div class="label">Total Runs</div>
        <div class="stat">{hw['successes']}/{hw['total']}</div><div class="label">Successful</div>
        <div class="stat">{hw['avg_time']:.1f}s</div><div class="label">Avg Time</div>
      </div>
      <div class="card sim-card">
        <h3>Aer Simulator</h3>
        <div class="stat">{sim['total']}</div><div class="label">Total Runs</div>
        <div class="stat">{sim['successes']}/{sim['total']}</div><div class="label">Successful</div>
        <div class="stat">{sim['avg_time']:.1f}s</div><div class="label">Avg Time</div>
      </div>
    </div>"""


def _quantum_table(rows: list[dict], section_class: str) -> str:
    if not rows:
        return "<p class='empty'>No benchmark data.</p>"
    lines = [f'<table class="{section_class} sortable">',
             "<thead><tr>",
             '<th>#</th>',
             '<th class="sort-header" data-sort-type="string">Timestamp <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">Backend <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="number">N <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="number">Qubits <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="number">Time (s) <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="number">Order r <span class="sort-icon"></span></th>',
             '<th>Factors</th>',
             '<th class="sort-header" data-sort-type="string">Status <span class="sort-icon"></span></th>',
             "</tr></thead><tbody>"]
    for i, r in enumerate(rows, 1):
        ts = r.get("timestamp", "") or "unknown (pre-schema)"
        backend = r.get("backend", "") or "ibm_quantum (legacy)"
        f1, f2 = r.get("factor1", ""), r.get("factor2", "")
        factors = f"{f1} × {f2}" if f1 and f2 else "&mdash;"
        badge = _quantum_status_badge(r.get("order_r", ""), f1, f2)
        time_val = r.get('total_time_sec', '')
        lines.append(f'<tr><td>{i}</td><td class="ts" data-sort-val="{_esc(ts)}">{_esc(ts)}</td>')
        lines.append(f'<td data-sort-val="{_esc(backend)}">{_esc(backend)}</td>')
        lines.append(f'<td data-sort-val="{_esc(r.get("N",""))}">{_esc(r.get("N",""))}</td>')
        lines.append(f'<td data-sort-val="{_esc(r.get("required_qubits",""))}">{_esc(r.get("required_qubits",""))}</td>')
        lines.append(f'<td class="num" data-sort-val="{_esc(time_val)}">{_esc(time_val)}</td>')
        lines.append(f'<td data-sort-val="{_esc(r.get("order_r",""))}">{_esc(r.get("order_r",""))}</td>')
        lines.append(f'<td>{factors}</td>')
        lines.append(f'<td data-sort-val="{"success" if f1 and f2 else "fail"}">{badge}</td></tr>')
    lines.append("</tbody></table>")
    return "\n".join(lines)


def build_quantum_tab(rows: list[dict], policy_events: list[dict], schedule_policy: dict) -> str:
    hw = [r for r in rows if _classify_backend(r.get("backend", "")) == "hardware"]
    sim = [r for r in rows if _classify_backend(r.get("backend", "")) == "simulator"]
    policy_panel = _quantum_policy_panel(policy_events, schedule_policy)
    summary = _quantum_summary(hw, sim)
    hw_table = _quantum_table(hw, "hw-table")
    sim_table = _quantum_table(sim, "sim-table")
    return f"""
    {policy_panel}
    {summary}
    <h2 class="hw-heading">IBM Quantum Hardware</h2>
    {hw_table}
    <h2 class="sim-heading">Aer Simulator (Local)</h2>
    {sim_table}"""


# ── Agent perf tab builders ───────────────────────────────────

def _agent_summary(runs: list[dict]) -> str:
    total = len(runs)
    ok = sum(1 for r in runs if r["status"] == "ok")
    errors = sum(1 for r in runs if r["status"] == "error")
    running = sum(1 for r in runs if r["status"] == "running")
    walls = [r["wall_ms"] for r in runs if r["status"] == "ok"]
    avg_wall = sum(walls) / len(walls) if walls else 0
    fastest = min(walls) if walls else 0
    return f"""
    <div class="summary-grid summary-grid-3">
      <div class="card agent-card">
        <h3>Runs</h3>
        <div class="stat">{total}</div><div class="label">Total</div>
        <div class="stat">{ok}</div><div class="label">Completed OK</div>
        <div class="stat">{errors}</div><div class="label">Errors</div>
        <div class="stat">{running}</div><div class="label">In Progress</div>
      </div>
      <div class="card agent-card">
        <h3>Wall-Clock (OK runs)</h3>
        <div class="stat">{_fmt_duration(avg_wall)}</div><div class="label">Average</div>
        <div class="stat">{_fmt_duration(fastest)}</div><div class="label">Fastest</div>
      </div>
      <div class="card agent-card">
        <h3>Step Breakdown</h3>
        <div class="stat">{sum(r['step_count'] for r in runs)}</div><div class="label">Total Steps</div>
        <div class="stat">{sum(r['step_ms'] for r in runs) / 1000:.1f}s</div><div class="label">Total Step Time</div>
      </div>
    </div>"""


def _agent_table(runs: list[dict]) -> str:
    if not runs:
        return "<p class='empty'>No agent performance data.</p>"
    lines = ['<table class="agent-table sortable">',
             "<thead><tr>",
             '<th>#</th>',
             '<th class="sort-header" data-sort-type="string">Timestamp <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">Name <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="number">Steps <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="number">Wall-Clock <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="number">Step Time <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">Status <span class="sort-icon"></span></th>',
             '<th class="sort-header" data-sort-type="string">Detail <span class="sort-icon"></span></th>',
             "</tr></thead><tbody>"]
    for i, r in enumerate(runs, 1):
        badge = _status_badge(r["status"])
        detail_trunc = r["detail"][:80] + "…" if len(r["detail"]) > 80 else r["detail"]
        wall_fmt = _fmt_duration(r["wall_ms"])
        step_fmt = _fmt_duration(r["step_ms"])

        # Steps sub-rows
        has_steps = len(r.get("steps", [])) > 0
        toggle_cls = "expandable" if has_steps else ""
        toggle_attr = f'data-run="{_esc(r["run_id"])}"' if has_steps else ""

        lines.append(f'<tr class="run-row {toggle_cls}" {toggle_attr}>')
        lines.append(f'<td>{i}</td><td class="ts" data-sort-val="{_esc(r["started"])}">{_esc(r["started"])}</td>')
        lines.append(f'<td class="name-cell" data-sort-val="{_esc(r["name"])}">{_esc(r["name"])}</td>')
        lines.append(f'<td class="num" data-sort-val="{r["step_count"]}">{r["step_count"]}</td>')
        lines.append(f'<td class="num" data-sort-val="{r["wall_ms"]:.0f}">{wall_fmt}</td>')
        lines.append(f'<td class="num" data-sort-val="{r["step_ms"]:.0f}">{step_fmt}</td>')
        lines.append(f'<td data-sort-val="{_esc(r["status"])}">{badge}</td>')
        lines.append(f'<td class="detail-cell" data-sort-val="{_esc(r["detail"])}">{_esc(detail_trunc)}</td></tr>')

        # Expandable step rows
        for s in r.get("steps", []):
            s_badge = _status_badge(s["status"])
            s_dur = _fmt_duration(s["elapsed_ms"])
            s_detail = s["detail"][:60] + "…" if len(s["detail"]) > 60 else s["detail"]
            lines.append(
                f'<tr class="step-row" data-parent="{_esc(r["run_id"])}" style="display:none">'
                f'<td></td><td></td>'
                f'<td class="step-indent">↳ {_esc(s["agent"])}</td>'
                f'<td></td><td class="num">{s_dur}</td><td></td>'
                f'<td>{s_badge}</td>'
                f'<td class="detail-cell">{_esc(s["description"])}'
                f'{"<br><small>" + _esc(s_detail) + "</small>" if s_detail else ""}'
                f'</td></tr>'
            )

    lines.append("</tbody></table>")
    return "\n".join(lines)


def build_agent_tab(runs: list[dict]) -> str:
    summary = _agent_summary(runs)
    table = _agent_table(runs)
    return f"""
    {summary}
    <h2 class="agent-heading">Agent Performance Runs</h2>
    {table}"""


# ── Full HTML render ──────────────────────────────────────────

def render_html(
    quantum_rows: list[dict],
    agent_runs: list[dict],
    policy_events: list[dict],
    schedule_policy: dict,
) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    quantum_tab = build_quantum_tab(quantum_rows, policy_events, schedule_policy)
    agent_tab = build_agent_tab(agent_runs)

    q_count = len(quantum_rows)
    a_count = len(agent_runs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>⊕ Unified Benchmark Dashboard</title>
<style>
  :root {{
    --quantum-accent: #a78bfa;
    --agent-accent: #22d3ee;
    --hw-accent: #1a73e8;
    --sim-accent: #e8710a;
    --success: #0d904f;
    --fail: #d93025;
    --partial: #f9ab00;
    --running: #60a5fa;
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
    max-width: 1400px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 1.8rem;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  h1 .sigil {{ color: var(--quantum-accent); font-size: 2rem; }}
  .subtitle {{ color: var(--muted); margin-bottom: 1.5rem; font-size: 0.9rem; }}

  /* ── Tab bar ── */
  .tab-bar {{
    display: flex;
    gap: 0;
    margin-bottom: 2rem;
    border-bottom: 2px solid var(--border);
  }}
  .tab-btn {{
    padding: 0.7rem 1.6rem;
    background: none;
    border: none;
    border-bottom: 3px solid transparent;
    color: var(--muted);
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  .tab-btn:hover {{ color: var(--text); }}
  .tab-btn.active {{
    color: var(--text);
    border-bottom-color: var(--quantum-accent);
  }}
  .tab-btn[data-tab="agent"].active {{
    border-bottom-color: var(--agent-accent);
  }}
  .tab-btn .count {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 9999px;
    padding: 0.1rem 0.5rem;
    font-size: 0.75rem;
    color: var(--muted);
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}

  /* ── Summary cards ── */
  .summary-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 2.5rem;
  }}
  .summary-grid-3 {{
    grid-template-columns: 1fr 1fr 1fr;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
  }}
  .card h3 {{ margin-bottom: 1rem; font-size: 1.1rem; }}
  .hw-card {{ border-top: 3px solid var(--hw-accent); }}
  .hw-card h3 {{ color: var(--hw-accent); }}
  .sim-card {{ border-top: 3px solid var(--sim-accent); }}
  .sim-card h3 {{ color: var(--sim-accent); }}
  .agent-card {{ border-top: 3px solid var(--agent-accent); }}
  .agent-card h3 {{ color: var(--agent-accent); }}
  .policy-card {{ border-top: 3px solid var(--quantum-accent); }}
  .policy-card h3 {{ color: var(--quantum-accent); }}
  .stat {{ font-size: 2rem; font-weight: 700; line-height: 1.2; }}
  .label {{
    color: var(--muted); font-size: 0.8rem;
    text-transform: uppercase; letter-spacing: 0.05em;
    margin-bottom: 0.8rem;
  }}

  /* ── Section headings ── */
  h2 {{
    font-size: 1.3rem; margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border);
  }}
  h2.hw-heading {{ color: var(--hw-accent); border-color: var(--hw-accent); }}
  h2.sim-heading {{ color: var(--sim-accent); border-color: var(--sim-accent); }}
  h2.agent-heading {{ color: var(--agent-accent); border-color: var(--agent-accent); }}
  h2.policy-heading {{ color: var(--quantum-accent); border-color: var(--quantum-accent); }}

  /* ── Tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
    margin-bottom: 2rem;
  }}
  thead {{ background: var(--surface); }}
  th {{
    text-align: left; padding: 0.6rem 0.8rem;
    font-weight: 600; color: var(--muted);
    text-transform: uppercase; font-size: 0.75rem;
    letter-spacing: 0.05em;
    border-bottom: 2px solid var(--border);
  }}
  td {{
    padding: 0.6rem 0.8rem;
    border-bottom: 1px solid var(--border);
  }}
  tr:hover {{ background: rgba(255,255,255,0.03); }}
  .num {{ font-variant-numeric: tabular-nums; text-align: right; }}
  .ts {{ color: var(--muted); font-size: 0.85rem; }}
  .name-cell {{ font-weight: 500; }}
  .detail-cell {{
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--muted);
    font-size: 0.85rem;
  }}
  .step-indent {{
    padding-left: 2rem;
    color: var(--muted);
    font-size: 0.85rem;
  }}
  .step-row {{ background: rgba(34,211,238,0.03); }}
  .step-row:hover {{ background: rgba(34,211,238,0.07); }}

  /* ── Expandable rows ── */
  .expandable {{ cursor: pointer; }}
  .expandable .name-cell::before {{
    content: "▸ ";
    color: var(--agent-accent);
    font-size: 0.8rem;
  }}
  .expandable.expanded .name-cell::before {{ content: "▾ "; }}

  /* ── Badges ── */
  .badge {{
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  .badge.success {{ background: rgba(13,144,79,0.15); color: var(--success); }}
  .badge.fail {{ background: rgba(217,48,37,0.15); color: var(--fail); }}
  .badge.partial {{ background: rgba(249,171,0,0.15); color: var(--partial); }}
  .badge.running {{ background: rgba(96,165,250,0.15); color: var(--running); }}
  .empty {{ color: var(--muted); font-style: italic; padding: 1rem; }}

  /* ── Sortable headers ── */
  .sort-header {{
    cursor: pointer;
    user-select: none;
    position: relative;
    transition: color 0.15s;
  }}
  .sort-header:hover {{ color: var(--text); }}
  .sort-icon::after {{ content: "⇅"; opacity: 0.3; margin-left: 0.3rem; font-size: 0.7rem; }}
  .sort-header.asc .sort-icon::after {{ content: "▲"; opacity: 1; }}
  .sort-header.desc .sort-icon::after {{ content: "▼"; opacity: 1; }}

  /* ── Footer ── */
  .footer {{
    margin-top: 3rem; padding-top: 1rem;
    border-top: 1px solid var(--border);
    color: var(--muted); font-size: 0.8rem;
    text-align: center;
  }}

  /* ── No-data banner ── */
  .no-data {{
    background: var(--surface);
    border: 1px dashed var(--border);
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    color: var(--muted);
  }}
  .no-data code {{
    background: rgba(255,255,255,0.06);
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }}

  @media (max-width: 800px) {{
    .summary-grid, .summary-grid-3 {{
      grid-template-columns: 1fr;
    }}
    body {{ padding: 1rem; }}
  }}
</style>
</head>
<body>
  <h1><span class="sigil">⊕</span> Unified Benchmark Dashboard</h1>
  <div class="subtitle">
    Generated: {generated}
  </div>

  <div class="tab-bar">
    <button class="tab-btn active" data-tab="quantum" onclick="switchTab('quantum')">
      ⟨ψ⟩ Quantum Benchmarks <span class="count">{q_count}</span>
    </button>
    <button class="tab-btn" data-tab="agent" onclick="switchTab('agent')">
      ⊕ Agent Performance <span class="count">{a_count}</span>
    </button>
  </div>

  <div id="tab-quantum" class="tab-panel active">
    {quantum_tab}
    {'' if quantum_rows else '<div class="no-data">No quantum benchmark rows yet.<br>Execution policy schedule and event panel is still shown above.</div>'}
  </div>

  <div id="tab-agent" class="tab-panel">
    {agent_tab if agent_runs else '<div class="no-data">No agent perf data.<br>Set <code>WORKSPACE_DB_KEY</code> env var and ensure <code>workspace.db</code> exists.</div>'}
  </div>

  <div class="footer">
    ⊕Workspace &mdash; Unified Benchmark Dashboard &bull; Static report
  </div>

  <script>
    function switchTab(name) {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.querySelector('[data-tab="' + name + '"]').classList.add('active');
      document.getElementById('tab-' + name).classList.add('active');
    }}

    // Expandable step rows
    document.querySelectorAll('.expandable').forEach(row => {{
      row.addEventListener('click', (e) => {{
        if (e.target.closest('th')) return;  // don't toggle on header clicks
        const runId = row.dataset.run;
        const expanded = row.classList.toggle('expanded');
        document.querySelectorAll('.step-row[data-parent="' + runId + '"]').forEach(s => {{
          s.style.display = expanded ? '' : 'none';
        }});
      }});
    }});

    // ── Sortable table columns ──
    document.querySelectorAll('.sort-header').forEach(th => {{
      th.addEventListener('click', (e) => {{
        e.stopPropagation();
        const table = th.closest('table');
        const tbody = table.querySelector('tbody');
        const colIdx = Array.from(th.parentNode.children).indexOf(th);
        const sortType = th.dataset.sortType || 'string';

        // Toggle direction
        const isAsc = th.classList.contains('asc');
        table.querySelectorAll('.sort-header').forEach(h => h.classList.remove('asc','desc'));
        th.classList.add(isAsc ? 'desc' : 'asc');
        const dir = isAsc ? -1 : 1;

        // Collect only primary rows (not step sub-rows)
        const isAgentTable = table.classList.contains('agent-table');
        const rows = Array.from(tbody.querySelectorAll(isAgentTable ? 'tr.run-row' : 'tr:not(.step-row)'));

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

        // Rebuild tbody preserving step rows after their parent
        const frag = document.createDocumentFragment();
        rows.forEach((row, idx) => {{
          row.children[0].textContent = idx + 1;  // renumber
          frag.appendChild(row);
          if (isAgentTable && row.dataset.run) {{
            document.querySelectorAll('.step-row[data-parent="' + row.dataset.run + '"]').forEach(s => {{
              frag.appendChild(s);
            }});
          }}
        }});
        tbody.appendChild(frag);
      }});
    }});
  </script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────

def main(open_browser: bool = True) -> None:
    quantum_rows = load_quantum_benchmarks()
    policy_events = load_quantum_policy_events()
    schedule_policy = load_quantum_schedule_policy()
    agent_runs = load_agent_perf()

    print(f"  Quantum benchmarks: {len(quantum_rows)} rows")
    print(f"  Quantum policy events: {len(policy_events)} rows")
    print(f"  Agent perf runs:    {len(agent_runs)} runs")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html_content = render_html(quantum_rows, agent_runs, policy_events, schedule_policy)
    OUT_PATH.write_text(html_content, encoding="utf-8")
    print(f"Dashboard written to {OUT_PATH.as_posix()}")

    if open_browser:
        url = OUT_PATH.as_uri()
        opened = False
        for name in ("brave", "chrome", "firefox"):
            try:
                webbrowser.get(name).open(url)
                print(f"Opened in {name}.")
                opened = True
                break
            except webbrowser.Error:
                continue
        if not opened:
            webbrowser.open(url)
            print("Opened in default browser.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified benchmark dashboard")
    parser.add_argument("--no-open", action="store_true", help="Don't open in browser")
    args = parser.parse_args()
    main(open_browser=not args.no_open)
