"""Generate reports/diagrams_viewer.html — a Mermaid gallery for all workspace diagrams."""
import html as htmllib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from utils.diagram_federation import discover_diagram_sources

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIAGRAMS = ROOT / "diagrams"
OUT = ROOT / "reports" / "diagrams_viewer.html"

PROJECT_LABELS = {
    "∞Life": "∞ Life",
    "❤Music": "❤ Music",
    "⟨ψ⟩Quantum": "⟨ψ⟩ Quantum",
    "👁AI-Manifest": "👁 AI-Manifest",
    "⊕Workspace": "⊕ Workspace",
    "ΣCapital": "Σ Capital",
}

SIGIL_CLS = {
    "∞ Life": "life",
    "❤ Music": "music",
    "⟨ψ⟩ Quantum": "quantum",
    "👁 AI-Manifest": "manifest",
    "⊕ Workspace": "ws",
}

def main():
    sections = {}
    total = 0
    sources = discover_diagram_sources(ROOT.parent, DIAGRAMS)
    for p in sources:
            name = p.stem
            group = PROJECT_LABELS.get(p.parent.parent.name, "⊕ Workspace")
            content = p.read_text(encoding="utf-8")
            label = name.replace("-", " ").title()
            safe = htmllib.escape(content)
            card = (
                f'<div class="card" id="{name}">'
                f'<div class="card-title">{label}</div>'
                f'<div class="mermaid">{safe}</div>'
                f'</div>'
            )
            sections.setdefault(group, []).append(card)
            total += 1

    body_parts = []
    for group in PROJECT_LABELS.values():
        if group not in sections:
            continue
        cls = SIGIL_CLS[group]
        body_parts.append(
            f'<section class="project {cls}">'
            f'<h2>{group}</h2>'
            f'<div class="grid">{"".join(sections[group])}</div>'
            f'</section>'
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>&#x2295; Workspace &mdash; Diagram Gallery</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d0f14;color:#d0d8e8;font-family:'Segoe UI',system-ui,sans-serif;padding:24px 32px}}
h1{{font-size:1.5rem;margin-bottom:4px;color:#6ad4b4;letter-spacing:.04em}}
.meta{{color:#4a6a80;font-size:.82rem;margin-bottom:32px}}
section.project{{margin-bottom:44px}}
section.project h2{{font-size:1rem;padding:5px 14px;border-radius:5px;margin-bottom:14px;display:inline-block;font-weight:600}}
.life h2{{background:#1a2e3a;border-left:3px solid #6ab4d4;color:#6ab4d4}}
.music h2{{background:#3a1a24;border-left:3px solid #d47a8f;color:#d47a8f}}
.quantum h2{{background:#251a3a;border-left:3px solid #a07adf;color:#a07adf}}
.manifest h2{{background:#3a2e1a;border-left:3px solid #d4a96a;color:#d4a96a}}
.ws h2{{background:#1a3a30;border-left:3px solid #6ad4b4;color:#6ad4b4}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(560px,1fr));gap:16px}}
.card{{background:#141820;border:1px solid #242c3a;border-radius:10px;padding:18px;overflow:auto}}
.card-title{{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;color:#4a6a80;margin-bottom:12px}}
.mermaid{{display:flex;justify-content:center;align-items:flex-start;min-height:100px;overflow:auto}}
svg{{max-width:100%;height:auto}}
.loading{{color:#4a6a80;font-size:.8rem;text-align:center;padding:20px}}
</style>
</head>
<body>
<h1>&#x2295; Workspace &mdash; Diagram Gallery</h1>
<div class="meta">19 diagrams &mdash; styled with STYLE_GUIDE.md pastel palette (FR-20260425-architecture-beautifier-styling)</div>
{"".join(body_parts)}
<script>
mermaid.initialize({{
  startOnLoad: true,
  theme: 'base',
  securityLevel: 'loose',
  themeVariables: {{
    primaryColor: '#1a2e3a',
    primaryTextColor: '#d0ecf8',
    edgeLabelBackground: '#0f1318',
    lineColor: '#4a7a9a'
  }}
}});
</script>
</body>
</html>"""

    OUT.write_text(html, encoding="utf-8")
    print(f"Written: {OUT}  ({len(html):,} bytes, {total} diagrams)")


if __name__ == "__main__":
    main()
