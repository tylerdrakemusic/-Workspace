#!/usr/bin/env python3
"""Generate source-backed architecture diagrams from canonical Mermaid text."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS_DIR = PROJECT_ROOT / "diagrams"
REPORTS_DIR = PROJECT_ROOT / "reports"
HTML_OUT_DIR = REPORTS_DIR / "diagrams"
INDEX_PATH = REPORTS_DIR / "diagrams_dashboard.html"
MANIFEST_PATH = HTML_OUT_DIR / "migration-manifest.json"
PROJECT_ORDER = ["workspace", "life", "music", "quantum", "manifest", "capital"]
PROJECT_LABELS = {"workspace": "⊕ Workspace", "life": "∞ Life", "music": "❤ Music", "quantum": "⟨ψ⟩ Quantum", "manifest": "👁 AI-Manifest", "capital": "ΣCapital"}

_DECLARATION_RE = re.compile(r"^\s*(graph|flowchart)\s+(?P<direction>\w+)", re.I)
_SUBGRAPH_RE = re.compile(r'^\s*subgraph\s+(?P<id>[A-Za-z_][\w-]*)?(?:\[?["\']?(?P<label>[^\]"\']+)["\']?\]?)?\s*$', re.I)
_NODE_RE = re.compile(r"(?<![/A-Za-z0-9_-])(?P<id>[A-Za-z_][\w-]*|\[\*\])\s*(?P<body>\[\(.*?\)\]|\(\[.*?\]\)|\[\[.*?\]\]|\[.*?\]|\(\(.*?\)\)|\{.*?\})")
_EDGE_RE = re.compile(r"(?P<source>[A-Za-z_][\w-]*|\[\*\])\s*(?P<operator>(?:-{1,3}>|={1,3}>|-\.\->|-(?:\.[^>\n]*\.)?->))\s*(?:\|(?P<pipe_label>[^|]*)\|\s*)?(?P<target>[A-Za-z_][\w-]*|\[\*\])(?:\s*:\s*(?P<colon_label>[^\n]+))?")
_ER_EDGE_RE = re.compile(r"(?P<source>[A-Za-z_][\w-]*)\s+(?P<operator>[^\s]+)\s+(?P<target>[A-Za-z_][\w-]*)\s*:\s*(?P<label>[^\n]+)")
_ER_ENTITY_RE = re.compile(r"^\s*(?P<id>[A-Za-z_][\w-]*)\s*\{\s*$")


def discover_diagrams() -> list[Path]:
    return sorted(DIAGRAMS_DIR.glob("*.mmd")) if DIAGRAMS_DIR.exists() else []


def _clean_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.replace("<br/>", " ").replace("<br>", " ").strip()).strip('"\'()[]{}')


def _add_node(nodes: dict[str, dict[str, str | None]], identifier: str, label: str | None = None, group: str | None = None) -> None:
    if identifier == "[*]":
        return
    existing = nodes.get(identifier)
    if existing is None:
        nodes[identifier] = {"id": identifier, "label": _clean_label(label or identifier), "group": group}
    else:
        if label and existing["label"] == identifier:
            existing["label"] = _clean_label(label)
        if group and not existing["group"]:
            existing["group"] = group


def parse_mermaid_source(source: str) -> dict[str, list | str]:
    """Parse graph, state, and ER relationships without inventing edges."""
    nodes: dict[str, dict[str, str | None]] = {}
    groups: list[dict[str, str | None]] = []
    edges: list[dict[str, str]] = []
    unsupported: list[dict[str, str | int]] = []
    group_stack: list[str] = []
    direction = "TB"
    diagram_type = "unknown"
    for line_number, raw_line in enumerate(source.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("%%"):
            continue
        if declaration := _DECLARATION_RE.match(raw_line):
            diagram_type, direction = declaration.group(1).lower(), declaration.group("direction").upper()
            continue
        if line.lower().startswith(("statediagram", "erdiagram")):
            diagram_type = "state" if line.lower().startswith("state") else "er"
            continue
        if line.lower() == "end":
            if group_stack:
                group_stack.pop()
            continue
        if subgraph := _SUBGRAPH_RE.match(raw_line):
            group_id = subgraph.group("id") or _clean_label(subgraph.group("label") or "group")
            group_label = _clean_label(subgraph.group("label") or group_id)
            groups.append({"id": group_id, "label": group_label, "parent": group_stack[-1] if group_stack else None})
            group_stack.append(group_id)
            continue
        if line.startswith(("class ", "classDef ", "style ", "linkStyle ", "direction ")):
            continue
        if line.startswith("click "):
            unsupported.append({"line": line_number, "text": raw_line.strip()})
            continue
        if diagram_type == "er" and (entity := _ER_ENTITY_RE.match(raw_line)):
            _add_node(nodes, entity.group("id"), group=group_stack[-1] if group_stack else None)
            continue
        edge = _ER_EDGE_RE.match(line) if diagram_type == "er" else _EDGE_RE.search(line)
        if edge:
            source_id, target_id = edge.group("source"), edge.group("target")
            label = edge.groupdict().get("pipe_label") or edge.groupdict().get("colon_label") or edge.groupdict().get("label") or ""
            _add_node(nodes, source_id, group=group_stack[-1] if group_stack else None)
            _add_node(nodes, target_id, group=group_stack[-1] if group_stack else None)
            edge_data = {"source": source_id, "target": target_id, "label": _clean_label(label)}
            if "." in edge.group("operator"):
                edge_data["style"] = "dotted"
            edges.append(edge_data)
        node_matches = list(_NODE_RE.finditer(line))
        for node_match in node_matches:
            identifier = node_match.group("id")
            if identifier not in {"graph", "flowchart", "subgraph", "class", "classDef", "style", "direction"}:
                body = node_match.group("body")
                label = body[2:-2] if body.startswith(("[[", "((", "[(")) else body[1:-1]
                _add_node(nodes, identifier, label, group_stack[-1] if group_stack else None)
        if not edge and not node_matches and diagram_type in {"graph", "flowchart", "state", "er"}:
            unsupported.append({"line": line_number, "text": raw_line.strip()})
        elif not edge and diagram_type not in {"graph", "flowchart", "state", "er"}:
            unsupported.append({"line": line_number, "text": raw_line.strip()})
    return {"type": diagram_type, "direction": direction, "nodes": list(nodes.values()), "groups": groups, "edges": edges, "flows": edges, "unsupported": unsupported}


def _artifact_name(source_path: Path, source_bytes: bytes) -> str:
    return f"{source_path.stem}--{hashlib.sha256(source_bytes).hexdigest()[:12]}.html"


def _node_html(node: dict[str, str | None]) -> str:
    return f'<div class="diagram-node" data-node-id="{html.escape(str(node["id"]))}" tabindex="0"><strong>{html.escape(str(node["label"]))}</strong><small>{html.escape(str(node["id"]))}</small></div>'


def _edge_html(edge: dict[str, str]) -> str:
    label = f'<span class="edge-label">{html.escape(edge["label"])}</span>' if edge["label"] else ""
    edge_style = edge.get("style", "solid")
    edge_class = " edge-line-dotted" if edge_style == "dotted" else ""
    edge_marker = f' data-edge-style="{html.escape(edge_style)}"'
    edge_glyph = "······▶" if edge_style == "dotted" else "──────▶"
    return f'<div class="diagram-edge" data-source="{html.escape(edge["source"])}" data-target="{html.escape(edge["target"])}" role="img" aria-label="{html.escape(edge["source"])} to {html.escape(edge["target"])}"><span class="edge-endpoint">{html.escape(edge["source"])}</span><span class="edge-line{edge_class}"{edge_marker} aria-hidden="true">{edge_glyph}</span>{label}<span class="edge-endpoint">{html.escape(edge["target"])}</span></div>'


def build_architecture_page(*, source_path: Path, source: str, model: dict, overview: str) -> str:
    """Build an accessible native HTML architecture diagram."""
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    title = source_path.stem.replace("-", " ").title()
    grouped: dict[str | None, list[dict]] = {}
    for node in model["nodes"]:
        grouped.setdefault(node.get("group"), []).append(node)
    groups_by_parent: dict[str | None, list[dict]] = {}
    for group in model["groups"]:
        groups_by_parent.setdefault(group.get("parent"), []).append(group)

    def render_group(group: dict) -> str:
        group_id = str(group["id"])
        parent = group.get("parent")
        parent_marker = f' data-parent-group-id="{html.escape(str(parent))}"' if parent else ""
        nodes = "".join(_node_html(node) for node in grouped.get(group_id, []))
        children = "".join(render_group(child) for child in groups_by_parent.get(group_id, []))
        return f'<section class="diagram-group" data-group-id="{html.escape(group_id)}"{parent_marker}><h3>{html.escape(str(group["label"]))}</h3><div class="node-grid">{nodes}</div>{children}</section>'

    regions = [render_group(group) for group in groups_by_parent.get(None, [])]
    ungrouped = "".join(_node_html(node) for node in grouped.get(None, []))
    if ungrouped:
        regions.append(f'<section class="diagram-group diagram-ungrouped"><h3>Declared components</h3><div class="node-grid">{ungrouped}</div></section>')
    edges = "".join(_edge_html(edge) for edge in model["edges"])
    unsupported = "".join(f'<li>Line {item["line"]}: <code>{html.escape(str(item["text"]))}</code></li>' for item in model["unsupported"])
    unsupported_section = f'<section class="unsupported"><h2>Unsupported source constructs</h2><p>These lines remain visible for review and were not interpreted as diagram semantics.</p><ul>{unsupported}</ul></section>' if unsupported else ""
    style = ':root{--ink:#172a31;--muted:#536970;--paper:#eef3f0;--panel:#fff;--accent:#b44f3b;--group:#6a8f84}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 Georgia,serif}main{max-width:1180px;margin:auto;padding:clamp(24px,5vw,72px) 20px}h1,h2,h3{font-family:"Trebuchet MS",sans-serif;line-height:1.15}h1{font-size:clamp(2rem,5vw,4rem);margin:.2em 0}.kicker{color:var(--accent);font:700 .75rem "Trebuchet MS",sans-serif;letter-spacing:.12em;text-transform:uppercase}.architecture-overview{max-width:72ch;color:var(--muted);font-size:1.15rem}.architecture-diagram{display:flex;flex-direction:column;gap:16px;margin:32px 0;padding:18px;border:2px solid #829b96;background:#ffffff73}.diagram-group{border:2px solid var(--group);border-radius:8px;padding:14px;background:#ffffffb3}.diagram-group h3{margin:0 0 12px;color:var(--group)}.node-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.diagram-node{min-height:72px;display:flex;flex-direction:column;justify-content:center;gap:4px;padding:12px;border:2px solid var(--accent);border-radius:6px;background:var(--panel);box-shadow:3px 3px #172a311f;overflow-wrap:anywhere}.diagram-node small{color:var(--muted);font:12px Consolas,monospace}.diagram-edge{display:flex;align-items:center;flex-wrap:wrap;gap:8px;min-height:42px;padding:8px 12px;border-left:4px solid var(--accent);background:#fffaf4;overflow-wrap:anywhere}.edge-line{color:var(--accent);font:700 1.1rem Consolas,monospace;white-space:nowrap}.edge-line-dotted{letter-spacing:.18em;text-decoration:underline dotted}.edge-label{color:var(--accent);font-style:italic}.edge-endpoint{font-weight:700}.unsupported{margin-top:24px;padding:16px;border:2px solid var(--accent);background:#fff4ed}code,pre{overflow-wrap:anywhere}details{margin-top:28px;border-top:1px solid #b8c8c3;padding-top:16px}summary{cursor:pointer;font-weight:700}pre{max-height:420px;overflow:auto;white-space:pre-wrap;background:#172a31;color:#f4f0e8;padding:16px;font:13px/1.45 Consolas,monospace}@media(max-width:560px){main{padding:28px 14px}.architecture-diagram{padding:10px;margin-left:-4px;margin-right:-4px}.diagram-edge{display:block}.edge-line{display:block;margin:2px 0}}'
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} architecture</title><style>{style}</style></head><body><main><p class="kicker">Architecture diagram / {html.escape(str(model["direction"]))}</p><h1>{html.escape(title)}</h1><p class="architecture-overview">{html.escape(overview)}</p><section class="architecture-diagram" aria-label="{html.escape(title)} architecture diagram" data-direction="{html.escape(str(model["direction"]))}"><div class="diagram-regions">{"".join(regions)}</div><section class="diagram-connections"><h2>Declared connections</h2>{edges or "<p>No directed connections declared.</p>"}</section></section>{unsupported_section}<details><summary>Source provenance</summary><p>Canonical source: <code>{html.escape(source_path.as_posix())}</code><br>sha256: <code>{digest}</code></p><pre>{html.escape(source)}</pre></details></main></body></html>'


def _project_of(stem: str) -> str:
    head = stem.split("-", 1)[0]
    return head if head in PROJECT_LABELS else "workspace"


def _overview_for(path: Path, model: dict) -> str:
    return f"A source-backed view of {len(model['nodes'])} declared components and {len(model['edges'])} directed connections in {path.stem.replace('-', ' ')}."


def render_all() -> dict[str, dict]:
    """Generate stable HTML artifacts and a raw-source hash manifest."""
    HTML_OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    manifest: list[dict[str, str]] = []
    for source_path in discover_diagrams():
        source_bytes = source_path.read_bytes()
        source = source_bytes.decode("utf-8")
        model = parse_mermaid_source(source)
        artifact = HTML_OUT_DIR / _artifact_name(source_path, source_bytes)
        artifact.write_text(build_architecture_page(source_path=source_path, source=source, model=model, overview=_overview_for(source_path, model)), encoding="utf-8")
        digest = hashlib.sha256(source_bytes).hexdigest()
        entry = {"source": (Path("diagrams") / source_path.name).as_posix(), "sha256": digest, "artifact": artifact.relative_to(REPORTS_DIR).as_posix()}
        manifest.append(entry)
        results[source_path.stem] = {"ok": True, "path": artifact, "source": source, "mmd_path": source_path, "model": model, "manifest": entry}
    MANIFEST_PATH.write_text(json.dumps({"diagrams": manifest}, indent=2), encoding="utf-8")
    return results


def build_index(results: dict[str, dict]) -> str:
    """Build the architecture index with links to standalone pages."""
    groups: dict[str, list[tuple[str, dict]]] = {project: [] for project in PROJECT_ORDER}
    for stem, info in sorted(results.items()):
        groups.setdefault(_project_of(stem), []).append((stem, info))
    sections = []
    for project in PROJECT_ORDER:
        cards = "".join(f'<article><h3>{html.escape(stem.replace("-", " ").title())}</h3><p>Source-backed diagram with visible components, grouping, and declared connections.</p><a href="{html.escape(info["path"].relative_to(REPORTS_DIR).as_posix())}">Open architecture page</a></article>' for stem, info in groups.get(project, []))
        if cards:
            sections.append(f'<section><h2>{html.escape(PROJECT_LABELS[project])}</h2><div class="grid">{cards}</div></section>')
    body = "".join(sections) or "<p>No canonical diagrams found.</p>"
    style = 'body{margin:0;background:#172a31;color:#f7f0e5;font:16px/1.5 Georgia,serif}main{max-width:1100px;margin:auto;padding:clamp(24px,5vw,70px) 20px}h1,h2,h3{font-family:"Trebuchet MS",sans-serif}h1{font-size:clamp(2.2rem,6vw,5rem);margin:.1em 0}h2{color:#e59c5f;border-bottom:1px solid #536467;padding-bottom:8px;margin-top:42px}.intro{color:#d2dad5;max-width:60em;font-size:1.1rem}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}article{background:#f7f0e5;color:#18252b;padding:18px;border-top:5px solid #bd4b31}article p{color:#536467}a{color:#9d3e2a;font-weight:700}'
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Architecture Atlas</title><style>{style}</style></head><body><main><small>⊕ WORKSPACE / ARCHITECTURE</small><h1>Architecture Atlas</h1><p class="intro">A navigable index of source-backed architecture diagrams. Each page keeps the canonical source and provenance alongside the visual structure.</p>{body}</main></body></html>'


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate readable architecture diagrams")
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    results = render_all()
    INDEX_PATH.write_text(build_index(results), encoding="utf-8")
    print(f"[diagrams] Wrote {len(results)} architecture pages and {INDEX_PATH}")
    if not args.no_open:
        webbrowser.open(INDEX_PATH.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
