"""Tests for tools/diagrams_dashboard.py generator.

Covers:
- discover_diagrams: scans diagrams/ folder for .mmd files
- render_all: writes SVGs, returns results dict (mocked client)
- build_index: produces HTML with cards, live editor, project grouping
- error rendering: failed diagrams produce error cards
"""
from __future__ import annotations

import sys
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
        assert r["path"].exists()
        assert r["path"].read_bytes() == b"<svg/>"


def test_render_all_handles_errors(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-broken")
    fake_client = MagicMock()
    fake_client.render.side_effect = MermaidRenderError("backend down")

    results = dd.render_all(client=fake_client)
    assert results["workspace-broken"]["ok"] is False
    assert "backend down" in results["workspace-broken"]["error"]


def test_build_index_has_live_editor(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-architecture")
    fake_client = MagicMock()
    fake_client.render.return_value = b"<svg/>"
    results = dd.render_all(client=fake_client)
    html_str = dd.build_index(results)

    assert "<!DOCTYPE html>" in html_str
    assert "Diagrams Dashboard" in html_str
    # Live editor section
    assert 'id="mmd-input"' in html_str
    assert 'id="preview"' in html_str
    assert "mermaid.esm.min.mjs" in html_str
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


def test_build_index_renders_error_card(diagrams_workspace):
    _write_mmd(diagrams_workspace, "workspace-broken")
    fake_client = MagicMock()
    fake_client.render.side_effect = MermaidRenderError("nope")
    results = dd.render_all(client=fake_client)
    html_str = dd.build_index(results)
    assert "card error" in html_str
    assert "nope" in html_str


def test_project_of_classifier():
    assert dd._project_of("workspace-architecture") == "workspace"
    assert dd._project_of("life-db-schema") == "life"
    assert dd._project_of("music-tech-stack") == "music"
    assert dd._project_of("quantum-architecture") == "quantum"
    assert dd._project_of("manifest-tech-stack") == "manifest"
    assert dd._project_of("orphan-diagram") == "workspace"
