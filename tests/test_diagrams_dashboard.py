"""Tests for tools/diagrams_dashboard.py generator.

Covers:
- discover_diagrams: scans diagrams/ folder for .mmd files
- render_all: writes SVGs, returns results dict (mocked client)
- build_index: produces HTML with cards and project grouping
- fallback rendering: failed diagrams produce fallback SVG + metadata
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import diagrams_dashboard as dd  # noqa: E402
from diagram_system import validate_gallery  # noqa: E402
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


def test_render_all_success(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")
    _write_mmd(diagrams_workspace, "music-tech-stack")

    fake_client = MagicMock()
    fake_client.render.return_value = b"<svg/>"

    results = dd.render_all(client=fake_client)
    assert set(results.keys()) == {"workspace-architecture", "music-tech-stack"}
    for r in results.values():
        assert r["ok"] is True
        assert r["status"] == "rendered"
        assert r["path"].exists()
        assert r["path"].read_bytes() == b"<svg/>"


def test_render_all_handles_errors(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-broken")
    fake_client = MagicMock()
    fake_client.render.side_effect = MermaidRenderError("backend down")

    results = dd.render_all(client=fake_client)
    assert results["workspace-broken"]["ok"] is False
    assert results["workspace-broken"]["status"] == "fallback"
    assert results["workspace-broken"]["path"].exists()
    assert "fallback_error" in results["workspace-broken"]
    assert "backend down" in results["workspace-broken"]["fallback_error"]


def test_main_no_render_no_open_rebuilds_index_from_existing_svgs(diagrams_workspace, monkeypatch):
    _write_mmd(diagrams_workspace, "workspace-existing")
    _write_mmd(diagrams_workspace, "workspace-missing")
    existing_svg = diagrams_workspace / "reports" / "diagrams" / "workspace-existing.svg"
    existing_svg.parent.mkdir(parents=True, exist_ok=True)
    existing_svg.write_text('<svg viewBox="0 0 1200 760"></svg>', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["diagrams_dashboard.py", "--no-render", "--no-open"])

    assert dd.main() == 0

    index = (diagrams_workspace / "reports" / "diagrams_dashboard.html").read_text(encoding="utf-8")
    assert "1 rendered" in index
    assert "Not rendered yet" in index


def test_main_no_render_preserves_persisted_fallback_diagnostics(diagrams_workspace, monkeypatch):
    _write_mmd(diagrams_workspace, "workspace-fallback")
    fake_client = MagicMock()
    fake_client.render.side_effect = MermaidRenderError("backend unavailable")

    rendered = dd.render_all(client=fake_client)
    assert rendered["workspace-fallback"]["status"] == "fallback"

    monkeypatch.setattr(sys, "argv", ["diagrams_dashboard.py", "--no-render", "--no-open"])

    assert dd.main() == 0

    index = (diagrams_workspace / "reports" / "diagrams_dashboard.html").read_text(encoding="utf-8")
    assert "0 rendered" in index
    assert "1 fallback" in index
    assert "fallback details" in index
    assert "backend unavailable" in index


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


def test_gallery_validation_requires_complete_sources_and_interaction_views() -> None:
    results = {
        "workspace-architecture": {
            "status": "rendered",
            "path": dd.REPORTS_DIR / "diagrams" / "workspace-architecture.svg",
            "source": "graph LR\n A --> B\n",
        }
    }

    html_str = dd.build_index(results)
    findings = validate_gallery(results, ["workspace-architecture", "life-architecture"], html_str)

    assert any(finding.code == "gallery_missing" for finding in findings)
    assert not any(finding.code == "gallery_interaction_contract" for finding in findings)
    assert 'class="lightbox"' in html_str
    assert 'class="zoom-btn"' in html_str
    assert '<details><summary>source</summary>' in html_str


def test_ci_gallery_contract_covers_every_canonical_mermaid_source() -> None:
    sources = dd.discover_diagrams()
    results = {
        source.stem: {
            "status": "fallback",
            "path": dd.SVG_OUT_DIR / f"{source.stem}.svg",
            "source": source.read_text(encoding="utf-8"),
            "fallback_error": "renderer unavailable in deterministic CI contract test",
        }
        for source in sources
    }

    html_str = dd.build_index(results)
    findings = validate_gallery(results, [source.stem for source in sources], html_str)

    assert len(sources) == 33
    assert not [finding for finding in findings if finding.code != "gallery_interaction_contract"]
    assert html_str.count('class="card"') == len(sources)


def test_gallery_includes_client_error_detection_hook() -> None:
    html_str = dd.build_index({})

    assert "window.addEventListener(\"error\"" in html_str
    assert "window.addEventListener(\"unhandledrejection\"" in html_str
