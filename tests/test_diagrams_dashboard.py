"""Tests for tools/diagrams_dashboard.py generator.

Covers:
- discover_diagrams: scans diagrams/ folder for .mmd files
- render_all: writes SVGs, returns results dict (mocked client)
- build_index: produces HTML with cards and project grouping
- fallback rendering: failed diagrams produce fallback SVG + metadata
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import diagrams_dashboard as dd  # noqa: E402


@pytest.fixture
def diagrams_workspace(tmp_path, monkeypatch):
    """Set up a temp diagrams/ + reports/ tree and patch module paths."""
    diagrams = tmp_path / "diagrams"
    reports = tmp_path / "reports"
    html_out = reports / "diagrams"
    diagrams.mkdir()
    reports.mkdir()
    monkeypatch.setattr(dd, "DIAGRAMS_DIR", diagrams)
    monkeypatch.setattr(dd, "REPORTS_DIR", reports)
    monkeypatch.setattr(dd, "HTML_OUT_DIR", html_out)
    monkeypatch.setattr(dd, "MANIFEST_PATH", html_out / "migration-manifest.json")
    monkeypatch.setattr(dd, "INDEX_PATH", reports / "diagrams_dashboard.html")
    return tmp_path


def _write_mmd(root: Path, name: str, body: str = "graph LR\n A --> B\n") -> Path:
    p = root / "diagrams" / f"{name}.mmd"
    p.write_text(body, encoding="utf-8")
    return p


def test_discover_diagrams_empty(diagrams_workspace):
    assert dd.discover_diagrams() == []


def test_discover_diagrams_finds_mmd(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")
    _write_mmd(diagrams_workspace, "music-architecture")
    found = dd.discover_diagrams()
    assert len(found) == 2
    assert all(p.suffix == ".mmd" for p in found)


def test_render_all_writes_html_and_manifest(diagrams_workspace):
    first = _write_mmd(diagrams_workspace, "workspace-architecture")
    second = _write_mmd(diagrams_workspace, "music-tech-stack")

    results = dd.render_all()

    assert set(results) == {"workspace-architecture", "music-tech-stack"}
    assert all(info["path"].suffix == ".html" for info in results.values())
    manifest = dd.MANIFEST_PATH.read_text(encoding="utf-8")
    assert first.name in manifest and second.name in manifest
    assert "sha256" in manifest
    assert all("mermaid" not in info["path"].read_text(encoding="utf-8").lower() for info in results.values())


def test_render_all_is_idempotent_and_hash_named(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")

    first = dd.render_all()["workspace-architecture"]["path"].name
    second = dd.render_all()["workspace-architecture"]["path"].name

    assert first == second
    assert len(list((diagrams_workspace / "reports" / "diagrams").glob("*.html"))) == 1


def test_render_all_manifest_hashes_exact_source_bytes(diagrams_workspace):
    """Manifest hashes must match the raw .mmd bytes, including line endings."""
    source_path = _write_mmd(diagrams_workspace, "workspace-byte-hash", "graph LR\r\n A --> B\r\n")

    dd.render_all()

    manifest = json.loads(dd.MANIFEST_PATH.read_text(encoding="utf-8"))
    entry = next(item for item in manifest["diagrams"] if item["source"].endswith(source_path.name))
    assert entry["sha256"] == hashlib.sha256(source_path.read_bytes()).hexdigest()


def test_build_index_links_standalone_pages(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")
    results = dd.render_all()

    html_str = dd.build_index(results)

    assert "Architecture Atlas" in html_str
    assert "Open architecture page" in html_str
    assert "⊕ Workspace" in html_str
    assert "mermaid" not in html_str.lower()


def test_build_architecture_page_escapes_source_and_overview(diagrams_workspace):
    source = "graph LR\n A[<script>alert(1)</script>] --> B\n"
    source_path = _write_mmd(diagrams_workspace, "workspace-security", source)

    page = dd.build_architecture_page(
        source_path=source_path,
        source=source,
        model=dd.parse_mermaid_source(source),
        overview="<script>bad</script>",
    )

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_parse_mermaid_source_preserves_graph_structure_and_unsupported_lines():
    source = """graph TB
    subgraph Core[Core services]
        API[Public API]
        DB[(Workspace DB)]
    end
    API -->|writes| DB
    class API service
    click API "https://example.test"
    """

    model = dd.parse_mermaid_source(source)

    assert model["nodes"] == [
        {"id": "API", "label": "Public API", "group": "Core"},
        {"id": "DB", "label": "Workspace DB", "group": "Core"},
    ]
    assert model["groups"] == [{"id": "Core", "label": "Core services", "parent": None}]
    assert model["edges"] == [{"source": "API", "target": "DB", "label": "writes"}]
    assert model["direction"] == "TB"
    assert model["unsupported"] == [{"line": 8, "text": 'click API "https://example.test"'}]


def test_parse_mermaid_source_does_not_turn_label_text_into_nodes():
    model = dd.parse_mermaid_source(
        "graph TB\n"
        "    Portal[reports/portal.html<br/>Unified Dashboard Portal]\n"
        "    Portal --> Registry[dashboard_registry.py Spec Discovery]\n"
    )

    assert [node["id"] for node in model["nodes"]] == ["Portal", "Registry"]


def test_dotted_labeled_edges_render_as_supported_native_connections(diagrams_workspace):
    source = "graph LR\n    A -.->|dotted| B\n"
    source_path = _write_mmd(diagrams_workspace, "workspace-dotted", source)
    model = dd.parse_mermaid_source(source)

    page = dd.build_architecture_page(
        source_path=source_path,
        source=source,
        model=model,
        overview="A source-backed architecture view.",
    )

    assert model["edges"] == [{"source": "A", "target": "B", "label": "dotted", "style": "dotted"}]
    assert model["unsupported"] == []
    assert 'class="diagram-edge"' in page
    assert 'data-source="A"' in page and 'data-target="B"' in page
    assert 'data-edge-style="dotted"' in page
    assert "dotted" in page


def test_parse_mermaid_source_supports_generic_classed_round_nodes():
    model = dd.parse_mermaid_source("graph LR\n    L_ws([⊕ Workspace]):::ws\n")

    assert model["nodes"] == [{"id": "L_ws", "label": "⊕ Workspace", "group": None}]
    assert model["unsupported"] == []


def test_render_all_is_byte_idempotent_including_manifest(diagrams_workspace):
    source_path = _write_mmd(diagrams_workspace, "workspace-idempotent", "graph LR\n A --> B\n")

    dd.render_all()
    first_html = next((diagrams_workspace / "reports" / "diagrams").glob("*.html")).read_bytes()
    first_manifest = dd.MANIFEST_PATH.read_bytes()
    first_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()

    dd.render_all()
    second_html = next((diagrams_workspace / "reports" / "diagrams").glob("*.html")).read_bytes()
    second_manifest = dd.MANIFEST_PATH.read_bytes()
    manifest = json.loads(second_manifest)

    assert first_html == second_html
    assert first_manifest == second_manifest
    assert manifest["diagrams"][0]["sha256"] == first_sha256


def test_build_architecture_page_contains_native_diagram_geometry_and_reports_unsupported(
    diagrams_workspace,
):
    source = """graph LR
    subgraph Core[Core services]
        API[Public API]
        DB[(Workspace DB)]
    end
    API -->|writes| DB
    click API "https://example.test"
    """
    source_path = _write_mmd(diagrams_workspace, "workspace-native", source)
    model = dd.parse_mermaid_source(source)

    page = dd.build_architecture_page(
        source_path=source_path,
        source=source,
        model=model,
        overview="A source-backed architecture view.",
    )

    assert 'class="architecture-diagram"' in page
    assert 'class="diagram-node"' in page
    assert 'data-node-id="API"' in page
    assert 'class="diagram-group"' in page
    assert 'class="diagram-edge"' in page
    assert 'data-source="API"' in page and 'data-target="DB"' in page
    assert "writes" in page
    assert "Unsupported source constructs" in page
    assert "click API &quot;" in page
    assert "mermaid" not in page.lower()


def test_build_architecture_page_preserves_nested_group_hierarchy(diagrams_workspace):
    source = """graph TB
    subgraph Outer[Outer systems]
        subgraph Inner[Inner services]
            API[Public API]
        end
    end
    """
    source_path = _write_mmd(diagrams_workspace, "workspace-nested", source)
    model = dd.parse_mermaid_source(source)

    page = dd.build_architecture_page(
        source_path=source_path,
        source=source,
        model=model,
        overview="A source-backed nested architecture view.",
    )

    outer_start = page.index('data-group-id="Outer"')
    inner_start = page.index('data-group-id="Inner"')
    outer_end = page.index("</section>", outer_start)
    assert outer_start < inner_start < outer_end
    assert 'data-parent-group-id="Outer"' in page
