"""Tests for tools/diagrams_dashboard.py generator.

Covers:
- discover_diagrams: scans diagrams/ folder for .mmd files
- render_all: writes SVGs, returns results dict (mocked client)
- build_index: produces HTML with cards and project grouping
- fallback rendering: failed diagrams produce fallback SVG + metadata
"""
from __future__ import annotations

import sys
import html
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import diagrams_dashboard as dd  # noqa: E402
from integrations.mermaid import MermaidRenderError  # noqa: E402


@pytest.fixture
def diagrams_workspace(tmp_path, monkeypatch):
    """Set up a temp diagrams/ + reports/ tree and patch module paths."""
    diagrams = tmp_path / "diagrams"
    reports = tmp_path / "reports"
    svg_out = reports / "diagrams"
    diagrams.mkdir()
    reports.mkdir()
    monkeypatch.setattr(dd, "DIAGRAMS_DIR", diagrams)
    monkeypatch.setattr(dd, "REPORTS_DIR", reports)
    monkeypatch.setattr(dd, "SVG_OUT_DIR", svg_out)
    monkeypatch.setattr(dd, "HTML_OUT_DIR", svg_out)
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


def test_discover_diagrams_recurses_into_proof_sources(diagrams_workspace):
    root_source = _write_mmd(diagrams_workspace, "capital-architecture")
    proof_dir = diagrams_workspace / "proof" / "FR-20260602-cap-picker-pipeline"
    proof_dir.mkdir(parents=True)
    proof_source = proof_dir / "capital-db-schema.mmd"
    proof_source.write_text("erDiagram\n A ||--o{ B : has\n", encoding="utf-8")

    assert dd.discover_diagrams() == [root_source, proof_source]


def test_collision_safe_artifact_names_preserve_proof_provenance(diagrams_workspace):
    root_source = _write_mmd(diagrams_workspace, "capital-architecture")
    proof_dir = diagrams_workspace / "proof" / "FR-20260602-cap-picker-pipeline"
    proof_dir.mkdir(parents=True)
    proof_source = proof_dir / "capital-architecture.mmd"
    proof_source.write_text("graph LR\n Proof --> Snapshot\n", encoding="utf-8")

    root_artifact = dd.publish_html_artifact(root_source)
    proof_artifact = dd.publish_html_artifact(proof_source)

    assert root_artifact.name == "capital-architecture.html"
    assert proof_artifact.name == "proof--FR-20260602-cap-picker-pipeline--capital-architecture.html"
    assert root_artifact != proof_artifact
    proof_html = proof_artifact.read_text(encoding="utf-8")
    assert 'data-source="proof/FR-20260602-cap-picker-pipeline/capital-architecture.mmd"' in proof_html
    assert html.escape("graph LR\n Proof --> Snapshot\n") in proof_html


def test_publish_html_artifact_is_deterministic_and_traceable(diagrams_workspace):
    source = "graph LR\n A --> B\n"
    source_path = _write_mmd(diagrams_workspace, "workspace-architecture", source)

    first = dd.publish_html_artifact(source_path)
    first_bytes = first.read_bytes()
    second = dd.publish_html_artifact(source_path)

    assert first == diagrams_workspace / "reports" / "diagrams" / "workspace-architecture.html"
    assert second.read_bytes() == first_bytes
    html_text = first.read_text(encoding="utf-8")
    assert html.escape(source) in html_text
    assert 'data-source="diagrams/workspace-architecture.mmd"' in html_text


def test_render_all_success(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")
    _write_mmd(diagrams_workspace, "music-tech-stack")

    fake_client = MagicMock()
    fake_client.render.return_value = b"<svg/>"

    results = dd.render_all(client=fake_client)
    assert set(results.keys()) == {"workspace-architecture", "music-tech-stack"}
    for r in results.values():
        assert r["ok"] is True
        assert r["path"].exists()
        assert r["path"].read_bytes() == b"<svg/>"


def test_render_all_handles_errors(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-broken")
    fake_client = MagicMock()
    fake_client.render.side_effect = MermaidRenderError("backend down")

    results = dd.render_all(client=fake_client)
    assert results["workspace-broken"]["ok"] is True
    assert results["workspace-broken"]["path"].exists()
    assert "fallback_error" in results["workspace-broken"]
    assert "backend down" in results["workspace-broken"]["fallback_error"]
    assert results["workspace-broken"]["artifact_path"].exists()


def test_build_index_uses_html_artifacts_as_canonical_output(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")
    fake_client = MagicMock()
    fake_client.render.return_value = b"<svg/>"

    html_str = dd.build_index(dd.render_all(client=fake_client))

    assert 'src="diagrams/workspace-architecture.html"' in html_str
    assert "Open HTML" in html_str
    assert 'type="image/svg+xml"' not in html_str


def test_dashboard_includes_recursive_collision_safe_artifacts(diagrams_workspace):
    _write_mmd(diagrams_workspace, "capital-architecture", "graph LR\n Root --> Diagram\n")
    proof_dir = diagrams_workspace / "proof" / "FR-20260602-cap-picker-pipeline"
    proof_dir.mkdir(parents=True)
    (proof_dir / "capital-architecture.mmd").write_text(
        "graph LR\n Proof --> Snapshot\n", encoding="utf-8"
    )

    fake_client = MagicMock()
    fake_client.render.return_value = b"<svg/>"
    results = dd.render_all(client=fake_client)
    html_str = dd.build_index(results)

    assert len(results) == 2
    assert 'src="diagrams/capital-architecture.html"' in html_str
    assert 'src="diagrams/proof--FR-20260602-cap-picker-pipeline--capital-architecture.html"' in html_str
    assert "proof/FR-20260602-cap-picker-pipeline/capital-architecture.mmd" in html_str


def test_publish_all_html_covers_every_canonical_source(diagrams_workspace):
    for name in ["workspace-one", "workspace-two", "music-one"]:
        _write_mmd(diagrams_workspace, name)

    artifacts = dd.publish_all_html()

    assert set(artifacts) == {"workspace-one", "workspace-two", "music-one"}
    assert all(path.suffix == ".html" and path.exists() for path in artifacts.values())


def test_discover_html_artifacts_finds_published_outputs(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")
    dd.publish_all_html()

    found = dd.discover_html_artifacts()

    assert found == {"workspace-architecture": diagrams_workspace / "reports" / "diagrams" / "workspace-architecture.html"}


def test_build_index_excludes_live_editor(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")
    fake_client = MagicMock()
    fake_client.render.return_value = b"<svg/>"
    results = dd.render_all(client=fake_client)
    html_str = dd.build_index(results)

    assert "<!DOCTYPE html>" in html_str
    assert "Diagrams Dashboard" in html_str
    assert "Live Editor" not in html_str
    assert 'id="mmd-input"' not in html_str
    assert 'id="preview"' not in html_str
    assert "mermaid.esm.min.mjs" not in html_str
    # Project grouping
    assert "⊕ Workspace" in html_str


def test_build_index_groups_by_project(diagrams_workspace):
    for name in [
        "workspace-architecture",
        "life-architecture",
        "music-db-schema",
        "quantum-tech-stack",
        "manifest-architecture",
    ]:
        _write_mmd(diagrams_workspace, name)
    fake_client = MagicMock()
    fake_client.render.return_value = b"<svg/>"
    results = dd.render_all(client=fake_client)
    html_str = dd.build_index(results)
    for label in ["⊕ Workspace", "∞ Life", "❤ Music", "⟨ψ⟩ Quantum", "👁 AI-Manifest"]:
        assert label in html_str


def test_build_index_renders_fallback_details(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-broken")
    fake_client = MagicMock()
    fake_client.render.side_effect = MermaidRenderError("nope")
    results = dd.render_all(client=fake_client)
    html_str = dd.build_index(results)
    assert "fallback details" in html_str
    assert "fallback-pill" in html_str
    assert "nope" in html_str


def test_project_of_classifier():
    assert dd._project_of("workspace-architecture") == "workspace"
    assert dd._project_of("life-db-schema") == "life"
    assert dd._project_of("music-tech-stack") == "music"
    assert dd._project_of("quantum-architecture") == "quantum"
    assert dd._project_of("manifest-tech-stack") == "manifest"
    assert dd._project_of("orphan-diagram") == "workspace"
