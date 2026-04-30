#!/usr/bin/env python3
"""
⊕ Dashboard Portal — Unified dashboard launcher and renderer

Discovers all dashboards via the registry, optionally regenerates static
dashboards, and produces a single master HTML portal with embedded
navigation.

Usage:
    C:\\G\\python.exe tools/dashboard_portal.py                # generate + open
    C:\\G\\python.exe tools/dashboard_portal.py --no-open      # generate only
    C:\\G\\python.exe tools/dashboard_portal.py --regen        # regenerate all statics first
    C:\\G\\python.exe tools/dashboard_portal.py --regen --no-open
"""

import argparse
import html as html_mod
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

# Brave registration
_BRAVE_PATHS = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]
for _bp in _BRAVE_PATHS:
    if os.path.isfile(_bp):
        webbrowser.register("brave", None, webbrowser.BackgroundBrowser(_bp))
        break

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORTAL_OUT = PROJECT_ROOT / "reports" / "portal.html"
AGENT_OPS_OUT = PROJECT_ROOT / "reports" / "agent_ops_dashboard.html"
SERVERS_CONFIG = PROJECT_ROOT / "tools" / "portal_servers.json"

# Import registry
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
from dashboard_registry import build_manifest

# Import agent-ops collector + DB connection for live health card (AC4).
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))
try:
    from agent_ops_monitor import collect_health as _collect_agent_health  # type: ignore
    from init_db import get_connection as _get_workspace_conn  # type: ignore
except Exception:  # pragma: no cover - keep portal rendering even if import fails
    _collect_agent_health = None
    _get_workspace_conn = None


# ── AC4: Agent-ops health + freshness card ─────────────────────────────────

_AGENT_OPS_DASH_ID = "agent-ops"
_FRESH_GREEN_SECS = 15 * 60      # <15m = fresh
_FRESH_YELLOW_SECS = 2 * 60 * 60  # <2h = stale warning, >=2h = stale/red


def _health_label(pct: float) -> tuple[str, str]:
    """(label, css_modifier) for a health percentage."""
    if pct >= 95:
        return "Excellent", "excellent"
    if pct >= 80:
        return "Good", "good"
    if pct >= 50:
        return "Needs Attention", "warn"
    return "Critical", "critical"


def _fmt_age(secs: float) -> str:
    secs = int(secs)
    if secs < 60:
        return f"{secs}s ago"
    m = secs // 60
    if m < 60:
        return f"{m}m ago"
    h = m // 60
    if h < 24:
        rem = m % 60
        return f"{h}h{rem:02d}m ago" if rem else f"{h}h ago"
    d = h // 24
    return f"{d}d ago"


def _freshness_class(age_secs: float | None) -> str:
    if age_secs is None:
        return "stale"
    if age_secs < _FRESH_GREEN_SECS:
        return "fresh"
    if age_secs < _FRESH_YELLOW_SECS:
        return "warn"
    return "stale"


def collect_portal_health(manifest: dict) -> dict:
    """Live agent-ops health snapshot + freshness for the portal card.

    Always returns a dict even on failure so the portal still renders.
    Read-only against workspace.db.
    """
    snapshot: dict = {
        "available": False,
        "reason": None,
        "health_pct": None,
        "label": "Unknown",
        "label_mod": "warn",
        "gap_count": None,
        "zombies": 0,
        "orphans": 0,
        "unverified": 0,
        "age_secs": None,
        "age_label": "never generated",
        "freshness_class": "stale",
        "regen_cmd": "C:\\G\\python.exe tools/agent_ops_monitor.py --fix --no-open",
        "dash_idx": None,
        "dash_url": None,
    }

    # Locate the agent-ops dashboard in the manifest for click-through.
    for i, d in enumerate(manifest.get("dashboards", [])):
        if d.get("id") == _AGENT_OPS_DASH_ID:
            snapshot["dash_idx"] = i
            out = d.get("output_abs") or d.get("output")
            if out and Path(out).exists():
                snapshot["dash_url"] = Path(out).as_uri()
            cli = d.get("cli")
            if cli:
                snapshot["regen_cmd"] = cli
            break

    # Freshness from the generated HTML mtime.
    if AGENT_OPS_OUT.exists():
        age = time.time() - AGENT_OPS_OUT.stat().st_mtime
        snapshot["age_secs"] = age
        snapshot["age_label"] = f"Generated {_fmt_age(age)}"
        snapshot["freshness_class"] = _freshness_class(age)

    # Live DB snapshot.
    if _collect_agent_health is None or _get_workspace_conn is None:
        snapshot["reason"] = "agent_ops_monitor / init_db import failed"
        return snapshot

    try:
        conn = _get_workspace_conn()
        try:
            health = _collect_agent_health(conn)
        finally:
            try:
                conn.close()
            except Exception:
                pass
        pct = float(health.get("health_pct", 0.0))
        label, mod = _health_label(pct)
        snapshot.update({
            "available": True,
            "health_pct": pct,
            "label": label,
            "label_mod": mod,
            "gap_count": health.get("gap_count", 0),
            "zombies": len(health.get("zombies", [])),
            "orphans": len(health.get("orphans", [])),
            "unverified": len(health.get("unverified", [])),
        })
    except Exception as e:  # pragma: no cover
        snapshot["reason"] = f"health query failed: {e}"

    return snapshot


def _render_health_card(snapshot: dict) -> str:
    """Render the agent-ops health card for the sidebar top."""
    idx = snapshot.get("dash_idx")
    click_attr = f'onclick="switchDashById({idx})"' if idx is not None else ""
    clickable_cls = " clickable" if idx is not None else ""

    if not snapshot["available"]:
        reason = _esc(snapshot.get("reason") or "Run agent_ops_monitor to populate health.")
        return (
            '<div class="health-card unavailable">'
            '<div class="health-card-title">🔬 Agent Ops Health</div>'
            f'<div class="health-sub">Unavailable · {reason}</div>'
            f'<div class="health-regen">Run: <code>{_esc(snapshot["regen_cmd"])}</code></div>'
            '</div>'
        )

    pct = snapshot["health_pct"]
    label = _esc(snapshot["label"])
    label_mod = _esc(snapshot["label_mod"])
    gap = snapshot["gap_count"]
    zombies = snapshot["zombies"]
    orphans = snapshot["orphans"]
    unverified = snapshot["unverified"]
    age_label = _esc(snapshot["age_label"])
    fresh_cls = _esc(snapshot["freshness_class"])
    stale = fresh_cls == "stale"
    regen_cmd = _esc(snapshot["regen_cmd"])

    regen_html = ""
    if stale:
        regen_html = (
            '<div class="health-regen">'
            '⚠ Stale — regenerate: '
            f'<code>{regen_cmd}</code>'
            '</div>'
        )

    return f"""
    <div class="health-card{clickable_cls}" {click_attr}>
      <div class="health-card-top">
        <span class="health-card-title">🔬 Agent Ops Health</span>
        <span class="health-fresh {fresh_cls}" title="Dashboard mtime">{age_label}</span>
      </div>
      <div class="health-score-row">
        <div class="health-pct {label_mod}">{pct:.0f}<span class="pct-sym">%</span></div>
        <div class="health-meta">
          <div class="health-label {label_mod}">{label}</div>
          <div class="health-gaps">{gap} gap{'' if gap == 1 else 's'}
            <span class="gap-breakdown">({zombies}z · {orphans}o · {unverified}u)</span>
          </div>
        </div>
      </div>
      {regen_html}
    </div>"""


_HEALTH_CARD_CSS = """
  .health-card {
    margin: 0.7rem 0.9rem 0.3rem;
    padding: 0.7rem 0.8rem;
    background: linear-gradient(135deg, rgba(99,102,241,0.10), rgba(99,102,241,0.02));
    border: 1px solid var(--border);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    transition: all .15s;
  }
  .health-card.clickable { cursor: pointer; }
  .health-card.clickable:hover {
    border-color: var(--accent);
    background: linear-gradient(135deg, rgba(99,102,241,0.18), rgba(99,102,241,0.05));
  }
  .health-card.unavailable { opacity: 0.75; }
  .health-card-top {
    display: flex; justify-content: space-between; align-items: center; gap: 0.5rem;
  }
  .health-card-title {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--text);
  }
  .health-fresh {
    font-size: 0.62rem; font-weight: 600; padding: 0.15rem 0.45rem;
    border-radius: 10px; white-space: nowrap;
  }
  .health-fresh.fresh { background: rgba(16,185,129,0.15); color: #34d399; }
  .health-fresh.warn  { background: rgba(245,158,11,0.15); color: #fbbf24; }
  .health-fresh.stale { background: rgba(239,68,68,0.15);  color: #f87171; }
  .health-score-row { display: flex; align-items: center; gap: 0.7rem; }
  .health-pct {
    font-size: 1.75rem; font-weight: 800; line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .health-pct .pct-sym { font-size: 0.9rem; opacity: 0.6; margin-left: 0.1rem; }
  .health-pct.excellent, .health-label.excellent { color: #34d399; }
  .health-pct.good,      .health-label.good      { color: #a5f3fc; }
  .health-pct.warn,      .health-label.warn      { color: #fbbf24; }
  .health-pct.critical,  .health-label.critical  { color: #f87171; }
  .health-meta { flex: 1; display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; }
  .health-label { font-size: 0.78rem; font-weight: 700; }
  .health-gaps { font-size: 0.7rem; color: var(--muted); }
  .gap-breakdown { opacity: 0.7; margin-left: 0.25rem; }
  .health-regen {
    font-size: 0.62rem; color: var(--muted); border-top: 1px solid var(--border);
    padding-top: 0.35rem; word-break: break-all;
  }
  .health-regen code {
    font-size: 0.6rem; color: #a5f3fc; background: var(--surface);
    padding: 0.1rem 0.3rem; border-radius: 3px; user-select: all;
  }
  .health-sub { font-size: 0.68rem; color: var(--muted); }
"""


def _load_servers() -> list[dict]:
    """Load enabled servers from portal_servers.json."""
    import json
    if not SERVERS_CONFIG.exists():
        return []
    try:
        # portal_servers.json may be written by PowerShell with a UTF-8 BOM
        data = json.loads(SERVERS_CONFIG.read_text(encoding="utf-8-sig"))
        return [s for s in data.get("servers", []) if s.get("enabled", True)]
    except Exception:
        return []


def _esc(val) -> str:
    return html_mod.escape(str(val)) if val else ""


def regenerate_dashboards(manifest: dict) -> list[dict]:
    """Run CLI generators for all static_html dashboards. Returns results."""
    results = []
    for dash in manifest["dashboards"]:
        if dash["type"] not in ("static_html", "living_html"):
            results.append({**dash, "regen_status": "skipped", "regen_detail": f"not regen-able ({dash['type']})"})
            continue
        cli = dash.get("cli")
        if not cli:
            results.append({**dash, "regen_status": "skipped", "regen_detail": "no cli defined"})
            continue
        cwd = dash.get("project_root", str(PROJECT_ROOT))
        print(f"  Regenerating {dash['project']} / {dash['title']}...")
        try:
            proc = subprocess.run(
                cli, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if proc.returncode == 0:
                results.append({**dash, "regen_status": "ok", "regen_detail": (proc.stdout or "").strip()})
                print(f"    ✓ OK")
            else:
                results.append({**dash, "regen_status": "error", "regen_detail": (proc.stderr or proc.stdout or "")[:200].strip()})
                print(f"    ✗ Error: {(proc.stderr or proc.stdout or '')[:100].strip()}")
        except subprocess.TimeoutExpired:
            results.append({**dash, "regen_status": "timeout", "regen_detail": "Generator exceeded 120s"})
            print(f"    ✗ Timeout")
        except Exception as e:
            results.append({**dash, "regen_status": "error", "regen_detail": str(e)[:200]})
            print(f"    ✗ {e}")
    return results


def _nav_items(manifest: dict) -> str:
    """Generate navigation sidebar items."""
    items = []
    for i, dash in enumerate(manifest["dashboards"]):
        icon = _esc(dash.get("icon", "📊"))
        title = _esc(dash["title"])
        project = _esc(dash.get("project", ""))
        sigil = _esc(dash.get("sigil", ""))
        active = " active" if i == 0 else ""
        dtype = dash["type"]
        badge_cls = {"static_html": "static", "living_html": "living", "flask_app": "live", "console": "console", "inline_html": "static"}.get(dtype, "static")
        badge_label = {"static_html": "Static", "living_html": "Living", "flask_app": "Live", "console": "CLI", "inline_html": "Inline"}.get(dtype, dtype)
        items.append(f"""
        <div class="nav-item{active}" data-idx="{i}" onclick="switchDash({i}, this)">
          <span class="nav-icon">{icon}</span>
          <div class="nav-text">
            <span class="nav-title">{title}</span>
            <span class="nav-project">{project}</span>
          </div>
          <span class="nav-badge {badge_cls}">{badge_label}</span>
        </div>""")
    return "\n".join(items)


_PASSWORD_GEN_HTML = """
<div class="inline-tool pwgen">
  <div class="pwgen-title">🔑 Password Generator</div>
  <div class="pwgen-sub">Quantum-assisted · stateless · never stored</div>
  <div class="pwgen-field">
    <label>Length <span id="pg-len-val">16</span></label>
    <input type="range" id="pg-len" min="8" max="64" value="16" oninput="pgLen(this.value)">
  </div>
  <div class="pwgen-toggles">
    <span class="pg-tog on" id="pg-nums" onclick="pgToggle(this)">Numbers</span>
    <span class="pg-tog"    id="pg-sym"  onclick="pgToggle(this)">Symbols</span>
  </div>
  <div class="pwgen-out-row">
    <span id="pg-display">—</span>
    <button class="pg-copy" onclick="pgCopy()" title="Copy">⧉</button>
    <button class="pg-regen" onclick="pgGenerate()" title="New">↺</button>
  </div>
  <div class="pwgen-strength-row">
    <div class="pwgen-bar-bg"><div class="pwgen-bar-fill" id="pg-fill"></div></div>
    <span class="pwgen-str-lbl" id="pg-str-lbl">—</span>
  </div>
  <div id="pg-feedback"></div>
</div>
<style>
  .inline-tool {
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    height:100%; padding:2rem; background:var(--bg);
  }
  .pwgen { gap:0.85rem; }
  .pwgen-title { font-size:1.25rem; font-weight:700; }
  .pwgen-sub { font-size:0.75rem; color:var(--muted); margin-top:-0.3rem; }
  .pwgen-field { width:100%; max-width:360px; }
  .pwgen-field label {
    display:block; font-size:0.72rem; font-weight:600; color:var(--muted);
    text-transform:uppercase; letter-spacing:.05em; margin-bottom:0.3rem;
  }
  .pwgen-field input[type=text] {
    width:100%; background:var(--surface); border:1px solid var(--border);
    border-radius:6px; padding:0.5rem 0.7rem; color:var(--text);
    font-size:0.88rem; outline:none;
  }
  .pwgen-field input[type=text]:focus { border-color:var(--accent); }
  .pwgen-field input[type=range] {
    width:100%; -webkit-appearance:none; height:4px;
    background:var(--border); border-radius:2px; cursor:pointer;
  }
  .pwgen-field input[type=range]::-webkit-slider-thumb {
    -webkit-appearance:none; width:14px; height:14px;
    border-radius:50%; background:var(--accent); cursor:pointer;
  }
  .pwgen-toggles { display:flex; gap:0.5rem; }
  .pg-tog {
    background:var(--surface); border:1px solid var(--border);
    border-radius:20px; padding:0.25rem 0.8rem; font-size:0.78rem;
    color:var(--muted); cursor:pointer; user-select:none; transition:all .15s;
  }
  .pg-tog.on { background:rgba(99,102,241,.15); border-color:var(--accent); color:#818cf8; }
  .pwgen-out-row {
    display:flex; align-items:center; gap:0.5rem; width:100%; max-width:360px;
    background:var(--surface); border:1px solid var(--border); border-radius:8px;
    padding:0.55rem 0.75rem;
  }
  #pg-display {
    flex:1; font-family:'Cascadia Code','Consolas',monospace; font-size:1rem;
    color:#a5f3fc; word-break:break-all; letter-spacing:.05em;
  }
  .pg-copy, .pg-regen {
    background:none; border:none; color:var(--muted); cursor:pointer;
    font-size:1rem; padding:0.1rem 0.3rem; transition:color .15s;
  }
  .pg-copy:hover, .pg-regen:hover { color:var(--accent); }
  .pwgen-strength-row { display:flex; align-items:center; gap:0.5rem; width:100%; max-width:360px; }
  .pwgen-bar-bg { flex:1; height:3px; background:var(--border); border-radius:2px; overflow:hidden; }
  .pwgen-bar-fill { height:100%; width:0%; border-radius:2px; transition:width .3s,background .3s; }
  .pwgen-str-lbl { font-size:0.7rem; color:var(--muted); min-width:5rem; text-align:right; }
  #pg-feedback { font-size:0.7rem; color:var(--success); height:0.9rem; }
</style>
<script>
(function(){
  const CHARS = {lower:'abcdefghijklmnopqrstuvwxyz', upper:'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                 digits:'0123456789', sym:'!@#$%^&*()-_=+[]{}|;:,.<>?'};
  function pgLen(v){ document.getElementById('pg-len-val').textContent=v; }
  function pgToggle(el){ el.classList.toggle('on'); }
  function pgStrength(pwd){
    if(!pwd||pwd==='—') return;
    const pools=((/[a-z]/.test(pwd)?26:0)+(/[A-Z]/.test(pwd)?26:0)+(/[0-9]/.test(pwd)?10:0)+(/[^a-zA-Z0-9]/.test(pwd)?32:0));
    const bits=pools>0?pwd.length*Math.log2(pools):0;
    const map=bits<40?[15,'Weak','#ef4444']:bits<60?[35,'Fair','#f59e0b']:bits<80?[60,'Good','#eab308']:bits<110?[80,'Strong','#10b981']:[100,'Very strong','#6366f1'];
    document.getElementById('pg-fill').style.width=map[0]+'%';
    document.getElementById('pg-fill').style.background=map[2];
    document.getElementById('pg-str-lbl').style.color=map[2];
    document.getElementById('pg-str-lbl').textContent=map[1];
  }
  function pgGenerate(){
    const len=parseInt(document.getElementById('pg-len').value);
    const nums=document.getElementById('pg-nums').classList.contains('on');
    const syms=document.getElementById('pg-sym').classList.contains('on');
    let pool=CHARS.lower+CHARS.upper+(nums?CHARS.digits:'')+(syms?CHARS.sym:'');
    const arr=new Uint32Array(len);
    crypto.getRandomValues(arr);
    const pwd=Array.from(arr).map(n=>pool[n%pool.length]).join('');
    document.getElementById('pg-display').textContent=pwd;
    pgStrength(pwd);
    window._pg_pwd=pwd;
  }
  function pgCopy(){
    if(!window._pg_pwd) return;
    navigator.clipboard.writeText(window._pg_pwd).then(()=>{
      const fb=document.getElementById('pg-feedback');
      fb.textContent='✓ Copied'; setTimeout(()=>fb.textContent='',2000);
    });
  }
  window.pgLen=pgLen; window.pgToggle=pgToggle;
  window.pgGenerate=pgGenerate; window.pgCopy=pgCopy;
  document.addEventListener('DOMContentLoaded', pgGenerate);
})();
</script>
"""

_INLINE_CONTENT = {"password-generator": _PASSWORD_GEN_HTML}


def _inline_html_content(inline_id: str) -> str:
    return _INLINE_CONTENT.get(inline_id, '<div class="placeholder">No inline content registered.</div>')


def _content_frames(manifest: dict) -> str:
    """Generate content panes — iframes for static/flask, info cards for console."""
    panes = []
    for i, dash in enumerate(manifest["dashboards"]):
        display = "block" if i == 0 else "none"
        if dash["type"] in ("static_html", "living_html"):
            out = dash.get("output_abs", "")
            if out and Path(out).exists():
                # Use relative path for files in the same reports/ directory so the
                # portal works when served via HTTP (file:// iframes are blocked by
                # browsers when the parent page is on http://).
                out_path = Path(out)
                if out_path.parent.resolve() == PORTAL_OUT.parent.resolve():
                    iframe_src = out_path.name
                else:
                    iframe_src = out_path.as_uri()
                panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">'
                             f'<iframe src="{iframe_src}" frameborder="0"></iframe></div>')
            else:
                panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">'
                             f'<div class="placeholder">Dashboard not yet generated.<br>'
                             f'<code>{_esc(dash.get("cli", ""))}</code></div></div>')
        elif dash["type"] == "flask_app":
            url = dash.get("url", "http://localhost:5050")
            cli = _esc(dash.get("cli", ""))
            # Guitar Trainer renders best as a bare iframe — the live-dash chrome
            # (header bar + Open in Browser link) crowds the practice UI.
            # See FR-20260425-guitar-trainer-panel-startup.
            if dash.get("id") == "guitar-trainer":
                panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">'
                             f'<iframe src="{_esc(url)}" frameborder="0"></iframe></div>')
            else:
                panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">'
                             f'<div class="live-dash">'
                             f'<div class="live-header">'
                             f'<span class="live-dot"></span> Live Dashboard'
                             f'<a href="{_esc(url)}" target="_blank" class="open-btn">Open in Browser ↗</a></div>'
                             f'<iframe src="{_esc(url)}" frameborder="0" class="live-frame" '
                             f'onerror="this.style.display=\'none\'"></iframe>'
                             f'</div></div>')
        elif dash["type"] == "inline_html":
            inline_id = dash.get("inline_id", "")
            panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">' +
                         _inline_html_content(inline_id) + '</div>')
        elif dash["type"] == "console":
            cli = _esc(dash.get("cli", ""))
            panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">'
                         f'<div class="console-dash">'
                         f'<div class="console-header">Terminal Dashboard</div>'
                         f'<div class="console-info">Run in terminal:</div>'
                         f'<code class="console-cmd">{cli}</code>'
                         f'</div></div>')
    return "\n".join(panes)


def _stats_bar(manifest: dict) -> str:
    """Generate stats summary."""
    total = len(manifest["dashboards"])
    projects = len([p for p in manifest["projects"] if p["has_spec"]])
    static = sum(1 for d in manifest["dashboards"] if d["type"] == "static_html")
    live = sum(1 for d in manifest["dashboards"] if d["type"] == "flask_app")
    console = sum(1 for d in manifest["dashboards"] if d["type"] == "console")
    cats = len(set(d["category"] for d in manifest["dashboards"]))
    return f"""
    <div class="stats-bar">
      <div class="stat-chip"><span class="stat-num">{total}</span> Dashboards</div>
      <div class="stat-chip"><span class="stat-num">{projects}</span> Projects</div>
      <div class="stat-chip"><span class="stat-num">{static}</span> Static</div>
      <div class="stat-chip"><span class="stat-num">{live}</span> Live</div>
      <div class="stat-chip"><span class="stat-num">{console}</span> Console</div>
      <div class="stat-chip"><span class="stat-num">{cats}</span> Categories</div>
    </div>"""


def _render_server_sidebar(servers: list[dict]) -> str:
    """Render the server status sidebar section from config."""
    if not servers:
        return ""
    rows = ""
    for s in servers:
        dot_id = f"dot-{s['port']}"
        port = s['port']
        name = _esc(s['name'])
        rows += (
            f'<div class="server-row">'
            f'<span class="server-dot" id="{dot_id}"></span>'
            f'<span class="server-name">{name} :{port}</span>'
            f'<button class="server-launch" onclick="openServer({port})" title="Open">&nearr;</button>'
            f'</div>\n      '
        )
    return (
        '<div class="server-status" id="server-status-block">\n      '
        + rows
        + '<div style="margin-top:.2rem">'
        '<button class="server-launch" id="launch-btn" style="width:100%;text-align:center;padding:.25rem 0;" '
        'onclick="launchServers()">&#9889; Start all servers</button>'
        '</div>\n    </div>'
    )


def render_portal(manifest: dict) -> str:
    """Render the unified portal HTML."""
    import json as _json
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nav = _nav_items(manifest)
    frames = _content_frames(manifest)
    stats = _stats_bar(manifest)
    servers = _load_servers()
    server_js_list = _json.dumps([{"port": s["port"], "name": s["name"]} for s in servers])
    server_sidebar = _render_server_sidebar(servers)
    health_snapshot = collect_portal_health(manifest)
    health_card = _render_health_card(health_snapshot)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>⊕ Dashboard Portal</title>
<style>
  :root {{
    --bg: #0a0d12;
    --sidebar-bg: #0f1318;
    --surface: #151a22;
    --border: #1e2530;
    --accent: #6366f1;
    --accent-glow: rgba(99,102,241,0.15);
    --text: #e2e8f0;
    --muted: #64748b;
    --success: #10b981;
    --warning: #f59e0b;
    --live-dot: #ef4444;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ height:100%; overflow:hidden; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    display: flex;
  }}

  /* ── Sidebar ── */
  .sidebar {{
    width: 280px;
    min-width: 280px;
    background: var(--sidebar-bg);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow-y: auto;
  }}
  .sidebar-header {{
    padding: 1.2rem 1rem 0.8rem;
    border-bottom: 1px solid var(--border);
  }}
  .sidebar-header h1 {{
    font-size: 1.3rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }}
  .sidebar-header h1 .sigil {{ color: var(--accent); font-size: 1.5rem; cursor: help; position: relative; }}
  .sidebar-header h1 .sigil[data-icon-prompt]:hover::after {{
    content: attr(data-icon-prompt);
    position: absolute;
    left: 0; top: 2rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    font-size: 0.7rem;
    font-weight: 400;
    color: var(--muted);
    white-space: pre-wrap;
    max-width: 340px;
    z-index: 999;
    pointer-events: none;
  }}
  .sidebar-header .subtitle {{
    color: var(--muted);
    font-size: 0.75rem;
    margin-top: 0.3rem;
  }}

  /* Stats */
  .stats-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    padding: 0.8rem 1rem;
    border-bottom: 1px solid var(--border);
  }}
  .stat-chip {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.2rem 0.5rem;
    font-size: 0.7rem;
    color: var(--muted);
  }}
  .stat-num {{ color: var(--text); font-weight: 700; margin-right: 0.2rem; }}

  /* Nav items */
  .nav-section {{ padding: 0.6rem 0; flex: 1; }}
  .nav-item {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.7rem 1rem;
    cursor: pointer;
    transition: all 0.15s;
    border-left: 3px solid transparent;
  }}
  .nav-item:hover {{
    background: var(--accent-glow);
  }}
  .nav-item.active {{
    background: var(--accent-glow);
    border-left-color: var(--accent);
  }}
  .nav-icon {{ font-size: 1.3rem; flex-shrink: 0; }}
  .nav-text {{ flex: 1; min-width: 0; }}
  .nav-title {{
    display: block;
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .nav-project {{
    display: block;
    font-size: 0.7rem;
    color: var(--muted);
  }}
  .nav-badge {{
    font-size: 0.6rem;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    flex-shrink: 0;
  }}
  .nav-badge.static {{ background: rgba(99,102,241,0.15); color: #818cf8; }}
  .nav-badge.live {{ background: rgba(239,68,68,0.15); color: #f87171; }}
  .nav-badge.living {{ background: rgba(34,197,94,0.15); color: #4ade80; position: relative; }}
  .nav-badge.living::before {{ content: ''; display: inline-block; width: 6px; height: 6px; background: #4ade80; border-radius: 50%; margin-right: 0.35rem; vertical-align: middle; animation: livingPulse 2s ease-in-out infinite; }}
  @keyframes livingPulse {{ 0%,100% {{ opacity: 1; box-shadow: 0 0 0 0 rgba(74,222,128,0.6); }} 50% {{ opacity: 0.6; box-shadow: 0 0 0 4px rgba(74,222,128,0); }} }}
  .nav-badge.console {{ background: rgba(16,185,129,0.15); color: #34d399; }}

  /* Server status */
  .server-status {{
    padding: 0.6rem 1rem;
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }}
  .server-row {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.7rem;
  }}
  .server-dot {{
    width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
    background: var(--muted);
  }}
  .server-dot.up {{ background: var(--success); }}
  .server-dot.down {{ background: #ef4444; }}
  .server-name {{ flex: 1; color: var(--muted); }}
  .server-launch {{
    background: none; border: 1px solid var(--border); border-radius: 4px;
    color: var(--muted); font-size: 0.62rem; padding: 0.1rem 0.35rem;
    cursor: pointer; transition: all .15s;
  }}
  .server-launch:hover {{ border-color: var(--accent); color: var(--accent); }}

  /* Footer */
  .sidebar-footer {{
    padding: 0.6rem 1rem;
    border-top: 1px solid var(--border);
    font-size: 0.7rem;
    color: var(--muted);
  }}

  /* ── Main content ── */
  .main-content {{
    flex: 1;
    position: relative;
    height: 100vh;
    overflow: hidden;
  }}
  .dash-pane {{
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
  }}
  .dash-pane iframe {{
    width: 100%;
    height: 100%;
    border: none;
    background: var(--bg);
  }}

  /* Placeholder */
  .placeholder {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--muted);
    font-size: 1.1rem;
    gap: 1rem;
    text-align: center;
  }}
  .placeholder code {{
    background: var(--surface);
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.8rem;
    color: var(--text);
    user-select: all;
  }}

  /* Live dash pane */
  .live-dash, .console-dash {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 1rem;
    text-align: center;
  }}
  .live-header {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.1rem;
    font-weight: 600;
  }}
  .live-dot {{
    width: 10px; height: 10px;
    background: var(--live-dot);
    border-radius: 50%;
    animation: pulse 1.5s infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.4; }}
  }}
  .open-btn {{
    margin-left: 1rem;
    padding: 0.4rem 1rem;
    background: var(--accent);
    color: white;
    border-radius: 6px;
    text-decoration: none;
    font-size: 0.8rem;
    font-weight: 600;
  }}
  .open-btn:hover {{ opacity: 0.85; }}
  .live-info, .console-info {{
    color: var(--muted);
    font-size: 0.9rem;
  }}
  .live-cmd, .console-cmd {{
    background: var(--surface);
    padding: 0.6rem 1.2rem;
    border-radius: 8px;
    font-size: 0.8rem;
    color: var(--text);
    user-select: all;
    border: 1px solid var(--border);
  }}
  .live-frame {{
    width: 90%;
    height: 70vh;
    border-radius: 8px;
    border: 1px solid var(--border);
  }}
  .console-header {{
    font-size: 1.1rem;
    font-weight: 600;
    color: #34d399;
  }}
{_HEALTH_CARD_CSS}
</style>
</head>
<body>
  <aside class="sidebar">
    <div class="sidebar-header">
      <h1><span class="sigil">⊕</span> Dashboard Portal</h1>
      <div class="subtitle">Spec-driven discovery across all projects</div>
    </div>
    {health_card}
    {stats}
    <div class="nav-section">
      {nav}
    </div>
    {server_sidebar}
    <div class="sidebar-footer">
      Generated {generated} &middot; {len(manifest['dashboards'])} dashboards<br>
      <span style="opacity:.6">Add services: <code style="font-size:.65rem">tools/portal_servers.json</code></span>
    </div>
  </aside>
  <main class="main-content">
    {frames}
  </main>
  <script>
    function switchDash(idx, el) {{
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      document.querySelectorAll('.dash-pane').forEach(p => p.style.display = 'none');
      el.classList.add('active');
      const pane = document.getElementById('pane-' + idx);
      if (pane) pane.style.display = 'block';
      try {{ localStorage.setItem('portal_active_pane', idx); }} catch {{}}
    }}

    function switchDashById(idx) {{
      const navs = document.querySelectorAll('.nav-item');
      const target = Array.from(navs).find(n => parseInt(n.dataset.idx) === idx);
      if (target) switchDash(idx, target);
    }}

    // Restore last active pane on load.
    (function restorePane() {{
      try {{
        const saved = localStorage.getItem('portal_active_pane');
        if (saved !== null) switchDashById(parseInt(saved));
      }} catch {{}}
    }})();

    function openServer(port) {{ window.open('http://localhost:' + port, '_blank'); }}
    function launchServers() {{
      const btn = document.getElementById('launch-btn');
      if (btn) {{ btn.textContent = 'Launching…'; btn.disabled = true; }}
      // Use a hidden anchor click to invoke portal:// without navigating away
      const a = document.createElement('a');
      a.href = 'portal://launch';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      // Re-poll for server status after 4s and 9s
      setTimeout(() => {{ pollServers(); }}, 4000);
      setTimeout(() => {{
        if (btn) {{ btn.textContent = '\u25b6 Start all servers'; btn.disabled = false; btn.style.animation = ''; }}
        pollServers();
      }}, 9000);
    }}
    const SERVERS = {server_js_list};
    async function checkServer(port, dotId) {{
      const dot = document.getElementById(dotId);
      if (!dot) return;
      try {{
        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 1500);
        await fetch('http://localhost:' + port, {{ mode: 'no-cors', signal: ctrl.signal }});
        clearTimeout(tid);
        dot.classList.add('up'); dot.classList.remove('down');
      }} catch {{ dot.classList.add('down'); dot.classList.remove('up'); }}
    }}
    function pollServers() {{ SERVERS.forEach(s => checkServer(s.port, 'dot-' + s.port)); }}
    async function autoLaunch() {{
      let anyUp = false;
      for (const s of SERVERS) {{
        try {{
          const ctrl = new AbortController();
          setTimeout(() => ctrl.abort(), 800);
          await fetch('http://localhost:' + s.port, {{ mode: 'no-cors', signal: ctrl.signal }});
          anyUp = true;
        }} catch {{}}
      }}
      const block = document.getElementById('server-status-block');
      if (block) block.style.display = 'block';
      // Requires a user gesture to invoke portal://, so we show the pulsed button if none are up.
      if (!anyUp) {{
        const btn = document.getElementById('launch-btn');
        if (btn) {{
          btn.textContent = '\u25b6 Start all servers';
          btn.style.animation = 'livingPulse 1.5s ease-in-out infinite';
        }}
      }}
    }}
    pollServers();
    setInterval(pollServers, 5000);
    window.addEventListener('load', () => setTimeout(autoLaunch, 500));
  </script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="⊕ Dashboard Portal")
    parser.add_argument("--no-open", action="store_true", help="Generate without opening browser")
    parser.add_argument("--regen", action="store_true", help="Regenerate all static dashboards first")
    args = parser.parse_args()

    manifest = build_manifest()

    print(f"⊕ Dashboard Portal")
    print(f"  Discovered {len(manifest['dashboards'])} dashboards across "
          f"{sum(1 for p in manifest['projects'] if p['has_spec'])} projects")

    # Auto-regen any static dashboard whose HTML is stale (>= yellow threshold).
    # This runs silently unless --regen is explicit (which forces ALL dashboards).
    if args.regen:
        print("\n  Regenerating all static dashboards...")
        results = regenerate_dashboards(manifest)
    else:
        import time as _time
        stale_dashboards = []
        for dash in manifest["dashboards"]:
            if dash["type"] not in ("static_html", "living_html") or not dash.get("cli"):
                continue
            out = dash.get("output_abs") or dash.get("output")
            if not out:
                continue
            p = Path(out)
            if not p.exists():
                stale_dashboards.append(dash)
                continue
            age = _time.time() - p.stat().st_mtime
            if age >= _FRESH_YELLOW_SECS:
                stale_dashboards.append(dash)
        if stale_dashboards:
            print(f"\n  Auto-regenerating {len(stale_dashboards)} stale dashboard(s)...")
            results = regenerate_dashboards({"dashboards": stale_dashboards})
            ok = sum(1 for r in results if r.get("regen_status") == "ok")
            err = sum(1 for r in results if r.get("regen_status") in ("error", "timeout"))
            print(f"  Auto-regen: {ok} ok, {err} errors")
            if ok:
                # Rebuild manifest so freshness reflects updated mtimes.
                manifest = build_manifest()
        results = []

    if args.regen:
        ok = sum(1 for r in results if r.get("regen_status") == "ok")
        skip = sum(1 for r in results if r.get("regen_status") == "skipped")
        err = sum(1 for r in results if r.get("regen_status") in ("error", "timeout"))
        print(f"  Regen complete: {ok} ok, {skip} skipped, {err} errors")

    PORTAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    html_content = render_portal(manifest)
    PORTAL_OUT.write_text(html_content, encoding="utf-8")
    print(f"  Portal written to {PORTAL_OUT}")

    if not args.no_open:
        try:
            webbrowser.get("brave").open(PORTAL_OUT.as_uri())
        except Exception:
            webbrowser.open(PORTAL_OUT.as_uri())


if __name__ == "__main__":
    main()
