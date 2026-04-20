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

# Import registry
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
from dashboard_registry import build_manifest


def _esc(val) -> str:
    return html_mod.escape(str(val)) if val else ""


def regenerate_dashboards(manifest: dict) -> list[dict]:
    """Run CLI generators for all static_html dashboards. Returns results."""
    results = []
    for dash in manifest["dashboards"]:
        if dash["type"] != "static_html":
            results.append({**dash, "regen_status": "skipped", "regen_detail": "not static_html"})
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
                results.append({**dash, "regen_status": "ok", "regen_detail": proc.stdout.strip()})
                print(f"    ✓ OK")
            else:
                results.append({**dash, "regen_status": "error", "regen_detail": proc.stderr.strip()[:200]})
                print(f"    ✗ Error: {proc.stderr.strip()[:100]}")
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
        badge_cls = {"static_html": "static", "flask_app": "live", "console": "console"}.get(dtype, "static")
        badge_label = {"static_html": "Static", "flask_app": "Live", "console": "CLI"}.get(dtype, dtype)
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


def _content_frames(manifest: dict) -> str:
    """Generate content panes — iframes for static/flask, info cards for console."""
    panes = []
    for i, dash in enumerate(manifest["dashboards"]):
        display = "block" if i == 0 else "none"
        if dash["type"] == "static_html":
            out = dash.get("output_abs", "")
            if out and Path(out).exists():
                file_uri = Path(out).as_uri()
                panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">'
                             f'<iframe src="{file_uri}" frameborder="0"></iframe></div>')
            else:
                panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">'
                             f'<div class="placeholder">Dashboard not yet generated.<br>'
                             f'<code>{_esc(dash.get("cli", ""))}</code></div></div>')
        elif dash["type"] == "flask_app":
            url = dash.get("url", "http://localhost:5050")
            cli = _esc(dash.get("cli", ""))
            panes.append(f'<div class="dash-pane" id="pane-{i}" style="display:{display}">'
                         f'<div class="live-dash">'
                         f'<div class="live-header">'
                         f'<span class="live-dot"></span> Live Dashboard'
                         f'<a href="{_esc(url)}" target="_blank" class="open-btn">Open in Browser ↗</a></div>'
                         f'<div class="live-info">Start the server first:</div>'
                         f'<code class="live-cmd">{cli}</code>'
                         f'<iframe src="{_esc(url)}" frameborder="0" class="live-frame" '
                         f'onerror="this.style.display=\'none\'"></iframe>'
                         f'</div></div>')
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


def render_portal(manifest: dict) -> str:
    """Render the unified portal HTML."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nav = _nav_items(manifest)
    frames = _content_frames(manifest)
    stats = _stats_bar(manifest)

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
  .sidebar-header h1 .sigil {{ color: var(--accent); font-size: 1.5rem; }}
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
  .nav-badge.console {{ background: rgba(16,185,129,0.15); color: #34d399; }}

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
</style>
</head>
<body>
  <aside class="sidebar">
    <div class="sidebar-header">
      <h1><span class="sigil">⊕</span> Dashboard Portal</h1>
      <div class="subtitle">Spec-driven discovery across all projects</div>
    </div>
    {stats}
    <div class="nav-section">
      {nav}
    </div>
    <div class="sidebar-footer">
      Generated {generated} &middot; {len(manifest['dashboards'])} dashboards
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
    }}
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

    if args.regen:
        print("\n  Regenerating static dashboards...")
        results = regenerate_dashboards(manifest)
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
