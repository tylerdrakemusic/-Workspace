#!/usr/bin/env python3
"""⊕ Diagrams Dashboard Generator

Scans `diagrams/*.mmd`, renders each to `reports/diagrams/*.svg` via the
mermaid integration (local mmdc CLI preferred, mermaid.ink HTTP fallback),
and writes a `reports/diagrams_dashboard.html` index.

Usage:
    C:\\G\\python.exe tools/diagrams_dashboard.py              # render + open
    C:\\G\\python.exe tools/diagrams_dashboard.py --no-open    # render only
    C:\\G\\python.exe tools/diagrams_dashboard.py --no-render  # rebuild index only
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS_DIR = PROJECT_ROOT / "diagrams"
REPORTS_DIR = PROJECT_ROOT / "reports"
SVG_OUT_DIR = REPORTS_DIR / "diagrams"
INDEX_PATH = REPORTS_DIR / "diagrams_dashboard.html"

sys.path.insert(0, str(PROJECT_ROOT / "src"))
from integrations.mermaid import MermaidClient, MermaidRenderError  # noqa: E402
from utils.diagram_federation import discover_diagram_sources  # noqa: E402

# Project sigil → display order
PROJECT_ORDER = ["workspace", "life", "music", "quantum", "manifest", "capital"]
PROJECT_LABELS = {
    "workspace": "⊕ Workspace",
    "life": "∞ Life",
    "music": "❤ Music",
    "quantum": "⟨ψ⟩ Quantum",
    "manifest": "👁 AI-Manifest",
    "capital": "Σ Capital",
}
FALLBACK_MARKER = "diagrams-dashboard:fallback"


def discover_diagrams() -> list[Path]:
  workspace_root = PROJECT_ROOT
  for candidate in (PROJECT_ROOT, PROJECT_ROOT.parent.parent.parent):
    if (candidate / "⊕Workspace").is_dir():
      workspace_root = candidate
      break
  return list(discover_diagram_sources(workspace_root, DIAGRAMS_DIR))


def _fallback_svg_bytes(title: str, source: str, error: str) -> bytes:
  """Build a minimal inline SVG fallback card when Mermaid rendering fails."""
  safe_title = html.escape(title)
  safe_error = html.escape(error)
  source_lines = [html.escape(line) for line in source.splitlines()[:18]]
  source_block = "\n".join(source_lines) if source_lines else "(empty diagram source)"
  svg = (
    f'<!-- {FALLBACK_MARKER} -->'
    '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">'
    '<rect width="100%" height="100%" fill="#ffffff" />'
    '<rect x="24" y="24" width="1152" height="712" rx="12" fill="#fff8f8" stroke="#f5c2c7" />'
    f'<text x="48" y="72" font-size="28" font-family="Segoe UI, sans-serif" fill="#842029">'
    f'Fallback Preview: {safe_title}</text>'
    '<text x="48" y="112" font-size="18" font-family="Segoe UI, sans-serif" fill="#842029">'
    'Mermaid backend unavailable; showing source snapshot.</text>'
    f'<text x="48" y="148" font-size="14" font-family="Consolas, monospace" fill="#5c0011">'
    f'Error: {safe_error}</text>'
    '<foreignObject x="48" y="176" width="1104" height="536">'
    '<div xmlns="http://www.w3.org/1999/xhtml" '
    'style="font-family:Consolas,monospace;font-size:14px;color:#111;white-space:pre-wrap;line-height:1.4;">'
    f'{source_block}'
    '</div>'
    '</foreignObject>'
    '</svg>'
  )
  return svg.encode("utf-8")


def _fallback_provenance(svg_path: Path) -> str | None:
    """Return the persisted fallback error, or None for a genuine SVG."""
    try:
        svg = svg_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if FALLBACK_MARKER not in svg and "Fallback Preview:" not in svg:
        return None
    match = re.search(r"Error:\s*(.*?)</text>", svg, flags=re.DOTALL)
    return html.unescape(match.group(1).strip()) if match else "Mermaid render failed"


def render_all(client: MermaidClient | None = None) -> dict[str, dict]:
    """Render each .mmd to SVG. Returns {stem: {ok, path|error, source}}."""
    SVG_OUT_DIR.mkdir(parents=True, exist_ok=True)
    if client is None:
        client = MermaidClient()
    results: dict[str, dict] = {}
    for mmd_path in discover_diagrams():
        stem = mmd_path.stem
        source = mmd_path.read_text(encoding="utf-8")
        try:
            svg_bytes = client.render(source, fmt="svg")
            out_path = SVG_OUT_DIR / f"{stem}.svg"
            out_path.write_bytes(svg_bytes)
            results[stem] = {
                "ok": True,
                "status": "rendered",
                "path": out_path,
                "source": source,
                "mmd_path": mmd_path,
            }
        except MermaidRenderError as exc:
            fallback_path = SVG_OUT_DIR / f"{stem}.svg"
            fallback_svg = _fallback_svg_bytes(stem, source, str(exc))
            fallback_path.write_bytes(fallback_svg)
            results[stem] = {
                "ok": False,
                "status": "fallback",
                "path": fallback_path,
                "source": source,
                "mmd_path": mmd_path,
                "fallback_error": str(exc),
            }
    return results


def _project_of(stem: str) -> str:
    head = stem.split("-", 1)[0]
    return head if head in PROJECT_LABELS else "workspace"


def _group_by_project(results: dict[str, dict]) -> dict[str, list[tuple[str, dict]]]:
    groups: dict[str, list[tuple[str, dict]]] = {p: [] for p in PROJECT_ORDER}
    for stem, info in sorted(results.items()):
        proj = _project_of(stem)
        groups.setdefault(proj, []).append((stem, info))
    return groups


_VIEWBOX_RE = re.compile(r'viewBox="([^"]+)"')


def _svg_dims(svg_path: Path) -> tuple[float, float]:
    """Extract natural width/height from SVG viewBox. Returns (w, h) or (800, 600)."""
    try:
        head = svg_path.read_text(encoding="utf-8", errors="ignore")[:1024]
    except OSError:
        return (800.0, 600.0)
    m = _VIEWBOX_RE.search(head)
    if not m:
        return (800.0, 600.0)
    parts = m.group(1).replace(",", " ").split()
    if len(parts) != 4:
        return (800.0, 600.0)
    try:
        w = float(parts[2])
        h = float(parts[3])
        return (w if w > 0 else 800.0, h if h > 0 else 600.0)
    except ValueError:
        return (800.0, 600.0)


def build_index(results: dict[str, dict]) -> str:
    """Build the dashboard HTML string."""
    groups = _group_by_project(results)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    ok_count = sum(1 for r in results.values() if r.get("status") == "rendered")
    fallback_count = sum(1 for r in results.values() if r.get("status") == "fallback")

    cards = []
    for proj in PROJECT_ORDER:
        items = groups.get(proj, [])
        if not items:
            continue
        cards.append(f'<h2 class="proj-header">{html.escape(PROJECT_LABELS[proj])}</h2>')
        cards.append('<div class="grid">')
        for stem, info in items:
            title = stem.replace(f"{proj}-", "").replace("-", " ").title()
            if info.get("path") and info.get("status") in {"rendered", "fallback"}:
                rel = info["path"].relative_to(REPORTS_DIR).as_posix()
                w, h = _svg_dims(info["path"])
                fallback_note = ""
                fallback_details = ""
                if info.get("status") == "fallback":
                    fallback_note = (
                        '<span class="fallback-pill" title="Source snapshot; Mermaid render failed">fallback</span>'
                    )
                    fallback_details = (
                        '<details><summary>fallback details</summary><pre class="err">'
                        + html.escape(info["fallback_error"])
                        + "</pre></details>"
                    )
                cards.append(
                    f'<div class="card">'
                    f'<div class="card-title">{html.escape(title)}'
                    f'{fallback_note}'
                    f'<button class="zoom-btn" data-svg="{html.escape(rel)}" '
                    f'data-title="{html.escape(title)}" '
                    f'data-w="{w:.0f}" data-h="{h:.0f}" title="Zoom">⛶</button>'
                    f'</div>'
                    f'<div class="svg-wrap" data-svg="{html.escape(rel)}" '
                    f'data-title="{html.escape(title)}" '
                    f'data-w="{w:.0f}" data-h="{h:.0f}">'
                    f'<object type="image/svg+xml" data="{html.escape(rel)}">'
                    f'<a href="{html.escape(rel)}">View SVG</a></object></div>'
                    f'{fallback_details}'
                    f'<details><summary>source</summary>'
                    f'<pre>{html.escape(info["source"])}</pre></details>'
                    f'</div>'
                )
            else:
                cards.append(
                    f'<div class="card error">'
                    f'<div class="card-title">{html.escape(title)} ⚠️</div>'
                    f'<pre class="err">{html.escape(info["error"])}</pre>'
                    f'<details><summary>source</summary>'
                    f'<pre>{html.escape(info["source"])}</pre></details>'
                    f'</div>'
                )
        cards.append('</div>')

    body = "\n".join(cards) if cards else '<p class="muted">No diagrams found in <code>diagrams/</code>.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>⊕ Diagrams Dashboard</title>
<style>
  :root {{
    --bg: #0d1117; --panel: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff; --err: #f85149;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, "Segoe UI", sans-serif;
         background: var(--bg); color: var(--text); }}
  header {{ padding: 16px 24px; border-bottom: 1px solid var(--border);
           display: flex; align-items: baseline; gap: 16px; }}
  header h1 {{ margin: 0; font-size: 20px; }}
  header .meta {{ color: var(--muted); font-size: 13px; }}
  main {{ padding: 16px 24px; }}
  .proj-header {{ margin: 28px 0 12px; font-size: 16px; color: var(--accent);
                  border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
           gap: 16px; }}
  .card {{ background: var(--panel); border: 1px solid var(--border);
           border-radius: 8px; padding: 12px; overflow: hidden; }}
  .card.error {{ border-color: var(--err); }}
  .card-title {{ font-weight: 600; margin-bottom: 8px;
                 display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
  .zoom-btn {{ background: var(--panel); color: var(--accent);
               border: 1px solid var(--border); border-radius: 4px;
               padding: 2px 8px; cursor: pointer; font-size: 14px; line-height: 1; }}
  .zoom-btn:hover {{ background: var(--accent); color: #fff; }}
  .svg-wrap {{ background: #fff; border-radius: 4px; padding: 8px;
               min-height: 200px; display: flex; align-items: center; justify-content: center;
               cursor: zoom-in; }}
  .svg-wrap object {{ width: 100%; max-height: 500px; pointer-events: none; }}
  details {{ margin-top: 8px; }}
  summary {{ color: var(--muted); cursor: pointer; font-size: 12px; }}
  pre {{ background: #0a0e13; padding: 8px; border-radius: 4px; overflow: auto;
         font-size: 11px; color: var(--text); margin: 6px 0 0; }}
  .err {{ color: var(--err); }}
  .muted {{ color: var(--muted); }}
  .editor-section {{ margin-top: 32px; border-top: 2px solid var(--border); padding-top: 24px; }}
  .editor-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  textarea#mmd-input {{ width: 100%; height: 360px; background: #0a0e13;
                        color: var(--text); border: 1px solid var(--border);
                        border-radius: 4px; padding: 12px; font-family: "Cascadia Code", monospace;
                        font-size: 13px; resize: vertical; }}
  #preview {{ background: #fff; border-radius: 4px; padding: 12px;
              min-height: 360px; overflow: auto; }}
  #preview-status {{ color: var(--muted); font-size: 12px; margin-bottom: 6px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px;
            background: var(--panel); border: 1px solid var(--border);
            font-size: 12px; margin-left: 6px; }}

  /* Lightbox / zoom modal */
  .lightbox {{ position: fixed; inset: 0; background: rgba(0,0,0,0.92);
               display: none; flex-direction: column; z-index: 9999; }}
  .lightbox.open {{ display: flex; }}
  .lightbox-bar {{ display: flex; align-items: center; gap: 12px;
                   padding: 10px 18px; background: var(--panel);
                   border-bottom: 1px solid var(--border); color: var(--text); }}
  .lightbox-bar .lb-title {{ font-weight: 600; flex: 1; }}
  .lightbox-bar button {{ background: var(--bg); color: var(--text);
                          border: 1px solid var(--border); border-radius: 4px;
                          padding: 4px 12px; cursor: pointer; font-size: 14px; }}
  .lightbox-bar button:hover {{ background: var(--accent); color: #fff; }}
  .lightbox-bar .lb-zoom {{ color: var(--muted); font-variant-numeric: tabular-nums;
                            min-width: 60px; text-align: right; }}
  .lightbox-stage {{ flex: 1; overflow: hidden; position: relative;
                     background: #fff; cursor: grab; }}
  .lightbox-stage.dragging {{ cursor: grabbing; }}
  .lightbox-stage .lb-content {{ position: absolute; top: 0; left: 0;
                                 transform-origin: 0 0; transition: none; }}
  .lightbox-stage .lb-content svg {{ display: block; }}
  .lightbox-stage .lb-content object {{ display: block; pointer-events: none; }}
</style>
</head>
<body>
<header>
  <h1>⊕ Diagrams Dashboard</h1>
  <span class="meta">{total} diagrams · {ok_count} rendered · {fallback_count} fallback · generated {generated}</span>
  <span class="badge">mermaid.js</span>
</header>
<main>
{body}
</main>

<div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-hidden="true">
  <div class="lightbox-bar">
    <span class="lb-title" id="lb-title"></span>
    <button id="lb-zoom-out" title="Zoom out (−)">−</button>
    <span class="lb-zoom" id="lb-zoom">100%</span>
    <button id="lb-zoom-in" title="Zoom in (+)">+</button>
    <button id="lb-fit" title="Fit to window (0)">Fit</button>
    <button id="lb-100" title="Actual size (1)">1:1</button>
    <a id="lb-open" target="_blank" rel="noopener"><button>Open SVG</button></a>
    <button id="lb-close" title="Close (Esc)">✕</button>
  </div>
  <div class="lightbox-stage" id="lb-stage">
    <div class="lb-content" id="lb-content"></div>
  </div>
</div>

<script>
  const dashboardErrors = [];
  window.addEventListener("error", event => {{
    dashboardErrors.push(String(event.error || event.message || "Unknown dashboard error"));
    document.documentElement.dataset.dashboardJsErrors = String(dashboardErrors.length);
  }});
  window.addEventListener("unhandledrejection", event => {{
    dashboardErrors.push(String(event.reason || "Unhandled dashboard rejection"));
    document.documentElement.dataset.dashboardJsErrors = String(dashboardErrors.length);
  }});
  // Lightbox: click thumb or zoom button → fullscreen pan/zoom view.
  (function() {{
    const lb = document.getElementById("lightbox");
    const stage = document.getElementById("lb-stage");
    const content = document.getElementById("lb-content");
    const lbTitle = document.getElementById("lb-title");
    const lbZoom = document.getElementById("lb-zoom");
    const lbOpen = document.getElementById("lb-open");
    let scale = 1, tx = 0, ty = 0;
    let dragging = false, lastX = 0, lastY = 0;
    let naturalW = 0, naturalH = 0;

    function apply() {{
      content.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")";
      lbZoom.textContent = Math.round(scale * 100) + "%";
    }}
    function fit() {{
      if (!naturalW || !naturalH) return;
      const sw = stage.clientWidth, sh = stage.clientHeight;
      scale = Math.min(sw / naturalW, sh / naturalH) * 0.95;
      tx = (sw - naturalW * scale) / 2;
      ty = (sh - naturalH * scale) / 2;
      apply();
    }}
    function actual() {{
      scale = 1;
      tx = (stage.clientWidth - naturalW) / 2;
      ty = (stage.clientHeight - naturalH) / 2;
      apply();
    }}
    function open(svgPath, title, hintW, hintH) {{
      lbTitle.textContent = title;
      lbOpen.href = svgPath;
      content.innerHTML = "";
      const img = new Image();
      img.onload = () => {{
        // Prefer dimensions hint embedded at generation time (from viewBox)
        // because mermaid SVGs use width="100%" which yields tiny naturalWidth.
        naturalW = hintW || img.naturalWidth || img.width || 800;
        naturalH = hintH || img.naturalHeight || img.height || 600;
        img.style.display = "block";
        img.style.width = naturalW + "px";
        img.style.height = naturalH + "px";
        content.appendChild(img);
        fit();
      }};
      img.onerror = () => {{
        content.innerHTML = "<div style='color:#c00;padding:20px'>Failed to load " + svgPath + "</div>";
      }};
      img.src = svgPath;
      lb.classList.add("open");
      lb.setAttribute("aria-hidden", "false");
    }}
    function close() {{
      lb.classList.remove("open");
      lb.setAttribute("aria-hidden", "true");
      content.innerHTML = "";
    }}
    function zoomBy(factor, cx, cy) {{
      const newScale = Math.max(0.05, Math.min(20, scale * factor));
      // Zoom toward (cx, cy) in stage coordinates
      const sx = (cx - tx) / scale;
      const sy = (cy - ty) / scale;
      scale = newScale;
      tx = cx - sx * scale;
      ty = cy - sy * scale;
      apply();
    }}

    // Wire up triggers
    document.querySelectorAll(".zoom-btn, .svg-wrap").forEach(el => {{
      el.addEventListener("click", e => {{
        e.preventDefault();
        e.stopPropagation();
        const svg = el.dataset.svg;
        const title = el.dataset.title || "Diagram";
        const w = parseFloat(el.dataset.w) || 0;
        const h = parseFloat(el.dataset.h) || 0;
        if (svg) open(svg, title, w, h);
      }});
    }});
    document.getElementById("lb-close").addEventListener("click", close);
    document.getElementById("lb-zoom-in").addEventListener("click", () =>
      zoomBy(1.25, stage.clientWidth / 2, stage.clientHeight / 2));
    document.getElementById("lb-zoom-out").addEventListener("click", () =>
      zoomBy(0.8, stage.clientWidth / 2, stage.clientHeight / 2));
    document.getElementById("lb-fit").addEventListener("click", fit);
    document.getElementById("lb-100").addEventListener("click", actual);

    // Wheel zoom
    stage.addEventListener("wheel", e => {{
      e.preventDefault();
      const rect = stage.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      zoomBy(e.deltaY < 0 ? 1.15 : 0.87, cx, cy);
    }}, {{ passive: false }});

    // Pan
    stage.addEventListener("mousedown", e => {{
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      stage.classList.add("dragging");
    }});
    window.addEventListener("mousemove", e => {{
      if (!dragging) return;
      tx += e.clientX - lastX; ty += e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
      apply();
    }});
    window.addEventListener("mouseup", () => {{
      dragging = false; stage.classList.remove("dragging");
    }});

    // Keyboard
    window.addEventListener("keydown", e => {{
      if (!lb.classList.contains("open")) return;
      if (e.key === "Escape") close();
      else if (e.key === "+" || e.key === "=")
        zoomBy(1.25, stage.clientWidth / 2, stage.clientHeight / 2);
      else if (e.key === "-" || e.key === "_")
        zoomBy(0.8, stage.clientWidth / 2, stage.clientHeight / 2);
      else if (e.key === "0") fit();
      else if (e.key === "1") actual();
    }});

    // Click outside content (on backdrop) closes
    lb.addEventListener("click", e => {{ if (e.target === lb) close(); }});
  }})();
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ⊕ Diagrams Dashboard")
    parser.add_argument("--no-open", action="store_true", help="Do not open the dashboard in a browser")
    parser.add_argument("--no-render", action="store_true",
                        help="Skip rendering — rebuild index from existing SVGs only")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SVG_OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.no_render:
        # Build results from existing SVGs
        results: dict[str, dict] = {}
        for mmd_path in discover_diagrams():
            stem = mmd_path.stem
            svg_path = SVG_OUT_DIR / f"{stem}.svg"
            source = mmd_path.read_text(encoding="utf-8")
            if svg_path.exists():
                fallback_error = _fallback_provenance(svg_path)
                if fallback_error is not None:
                    results[stem] = {
                        "ok": False,
                        "status": "fallback",
                        "path": svg_path,
                        "source": source,
                        "mmd_path": mmd_path,
                        "fallback_error": fallback_error,
                    }
                    continue
                results[stem] = {
                    "ok": True,
                    "status": "rendered",
                    "path": svg_path,
                    "source": source,
                    "mmd_path": mmd_path,
                }
            else:
                results[stem] = {
                    "ok": False,
                    "status": "error",
                    "error": "Not rendered yet",
                    "source": source,
                    "mmd_path": mmd_path,
                }
    else:
        client = MermaidClient()
        backend = "mmdc CLI" if client.cli_available() else "mermaid.ink HTTP"
        print(f"[diagrams] Backend: {backend}")
        results = render_all(client)
        ok = sum(1 for r in results.values() if r["ok"])
        fallback = sum(1 for r in results.values() if r.get("fallback_error"))
        print(f"[diagrams] Rendered {ok}/{len(results)} diagrams")
        if fallback:
            print(f"[diagrams] Fallback used for {fallback} diagram(s)")
        for stem, info in results.items():
            if info.get("fallback_error"):
                print(f"  [FALLBACK] {stem}: {info['fallback_error']}", file=sys.stderr)

    INDEX_PATH.write_text(build_index(results), encoding="utf-8")
    print(f"[diagrams] Wrote {INDEX_PATH}")

    if not args.no_open:
        webbrowser.open(INDEX_PATH.as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
