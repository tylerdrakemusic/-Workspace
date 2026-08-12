"""Tests for dashboard.json registry update — confirms the swap from
unified-benchmarks to diagrams entry.
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_JSON = PROJECT_ROOT / "dashboard.json"


def _load_specs():
    spec = json.loads(DASHBOARD_JSON.read_text(encoding="utf-8"))
    return {d["id"]: d for d in spec["dashboards"]}


def test_unified_benchmarks_is_removed():
    by_id = _load_specs()
    assert "unified-benchmarks" not in by_id, \
        "unified-benchmarks should have been replaced by 'diagrams'"


def test_diagrams_entry_registered():
    by_id = _load_specs()
    assert "diagrams" in by_id
    entry = by_id["diagrams"]
    assert entry["type"] == "static_html"
    assert entry["generator"] == "tools/diagrams_dashboard.py"
    assert entry["output"] == "reports/diagrams_dashboard.html"
    assert "category" in entry
    assert "icon" in entry
    assert "Mermaid-rendered" not in entry["description"]
    assert "provenance" in entry["description"]


def test_other_dashboards_unchanged():
    by_id = _load_specs()
    # These existing entries must still be present and untouched
    for keep in ("security-vulns", "agent-ops", "copilot-usage", "fr-board", "password-generator"):
        assert keep in by_id, f"expected dashboard '{keep}' to remain registered"
