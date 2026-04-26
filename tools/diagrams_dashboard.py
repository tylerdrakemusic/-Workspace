#!/usr/bin/env python3
"""⊕ Diagrams Dashboard Generator

Scans `diagrams/*.mmd`, renders each to `reports/diagrams/*.svg` via the
mermaid integration (local mmdc CLI preferred, mermaid.ink HTTP fallback),
and writes a `reports/diagrams_dashboard.html` index with a built-in
live editor.

Usage:
    C:\\G\\python.exe tools/diagrams_dashboard.py              # render + open
    C:\\G\\python.exe tools/diagrams_dashboard.py --no-open    # render only
    C:\\G\\python.exe tools/diagrams_dashboard.py --no-render  # rebuild index only
"""

from __future__ import annotations

import argparse
import html
import os
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

# Project sigil → display order
PROJECT_ORDER = ["workspace", "life", "music", "quantum", "manifest"]
PROJECT_LABELS = {
    "workspace": "⊕ Workspace",
    "life": "∞ Life",
    "music": "❤ Music",
    "quantum": "⟨ψ⟩ Quantum",
    "manifest": "👁 AI-Manifest",
}


def discover_diagrams() -> list[Path]:
    if not DIAGRAMS_DIR.exists():
        return []
    return sorted(DIAGRAMS_DIR.glob("*.mmd"))


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
                "path": out_path,
                "source": source,
                "mmd_path": mmd_path,
            }
        except MermaidRenderError as exc:
            results[stem] = {
                "ok": False,
                "error": str(exc),
                "source": source,
                "mmd_path": mmd_path,
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


def build_index(results: dict[str, dict]) -> str:
    """Build the dashboard HTML string."""
    groups = _group_by_project(results)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    ok_count = sum(1 for r in results.values() if r["ok"])

    cards = []
    for proj in PROJECT_ORDER:
        items = groups.get(proj, [])
        if not items:
            continue
        cards.append(f'<h2 class="proj-header">{html.escape(PROJECT_LABELS[proj])}</h2>')
        cards.append('<div class="grid">')
        for stem, info in items:
            title = stem.replace(f"{proj}-", "").replace("-", " ").title()
            if info["ok"]:
                rel = info["path"].relative_to(REPORTS_DIR).as_posix()
                cards.append(
                    f'<div class="card">'
                    f'<div class="card-title">{html.escape(title)}</div>'
                    f'<div class="svg-wrap"><object type="image/svg+xml" data="{html.escape(rel)}">'
                    f'<a href="{html.escape(rel)}">View SVG</a></object></div>'
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

    sample_mmd = (
        "graph LR\n"
        "    A[Edit me] --> B(Live preview)\n"
        "    B --> C{Mermaid}\n"
        "    C -->|svg| D[mermaid.ink]\n"
    )

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
  .card-title {{ font-weight: 600; margin-bottom: 8px; }}
  .svg-wrap {{ background: #fff; border-radius: 4px; padding: 8px;
               min-height: 200px; display: flex; align-items: center; justify-content: center; }}
  .svg-wrap object {{ width: 100%; max-height: 500px; }}
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
</style>
</head>
<body>
<header>
  <h1>⊕ Diagrams Dashboard</h1>
  <span class="meta">{total} diagrams · {ok_count} rendered · generated {generated}</span>
  <span class="badge">mermaid.js</span>
</header>
<main>
{body}

<section class="editor-section">
  <h2 class="proj-header">Live Editor</h2>
  <p class="muted">Edit mermaid source on the left — preview renders client-side via mermaid.js. No server round-trip.</p>
  <div class="editor-grid">
    <div>
      <textarea id="mmd-input" spellcheck="false">{html.escape(sample_mmd)}</textarea>
    </div>
    <div>
      <div id="preview-status">Initializing…</div>
      <div id="preview"></div>
    </div>
  </div>
</section>
</main>

<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: false, theme: "default", securityLevel: "loose" }});

  const ta = document.getElementById("mmd-input");
  const preview = document.getElementById("preview");
  const status = document.getElementById("preview-status");
  let timer = null;
  let renderId = 0;

  async function renderPreview() {{
    const id = ++renderId;
    const src = ta.value;
    status.textContent = "Rendering…";
    try {{
      const {{ svg }} = await mermaid.render("preview-svg-" + id, src);
      if (id !== renderId) return;
      preview.innerHTML = svg;
      status.textContent = "OK · " + new Date().toLocaleTimeString();
    }} catch (err) {{
      if (id !== renderId) return;
      preview.innerHTML = "<pre style='color:#c00;white-space:pre-wrap'>" +
                         String(err.message || err) + "</pre>";
      status.textContent = "Error";
    }}
  }}

  ta.addEventListener("input", () => {{
    clearTimeout(timer);
    timer = setTimeout(renderPreview, 350);
  }});
  renderPreview();
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
                results[stem] = {"ok": True, "path": svg_path, "source": source, "mmd_path": mmd_path}
            else:
                results[stem] = {"ok": False, "error": "Not rendered yet", "source": source, "mmd_path": mmd_path}
    else:
        client = MermaidClient()
        backend = "mmdc CLI" if client.cli_available() else "mermaid.ink HTTP"
        print(f"[diagrams] Backend: {backend}")
        results = render_all(client)
        ok = sum(1 for r in results.values() if r["ok"])
        print(f"[diagrams] Rendered {ok}/{len(results)} diagrams")
        for stem, info in results.items():
            if not info["ok"]:
                print(f"  [FAIL] {stem}: {info['error']}", file=sys.stderr)

    INDEX_PATH.write_text(build_index(results), encoding="utf-8")
    print(f"[diagrams] Wrote {INDEX_PATH}")

    if not args.no_open:
        webbrowser.open(INDEX_PATH.as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
