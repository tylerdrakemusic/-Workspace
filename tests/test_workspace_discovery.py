"""Tests for workspace_discovery.py — FR-20260530-workspace-discovery-test-suite.

Groups:
  TestDiscovery   — discover_projects(), discover_agents()
  TestRouting     — route_request() classifier
  TestAlignment   — alignment_report()
  Perf            — full pipeline < 500 ms
"""
from __future__ import annotations

import os
import time
import sys
from pathlib import Path

import pytest

# conftest already inserts src/utils; explicit fallback for direct runs
_WORKTREE = Path(__file__).resolve().parent.parent
if str(_WORKTREE / "src" / "utils") not in sys.path:
    sys.path.insert(0, str(_WORKTREE / "src" / "utils"))

import workspace_discovery as wd

# ---------------------------------------------------------------------------
# TestDiscovery
# ---------------------------------------------------------------------------

class TestDiscovery:
    def test_discovers_all_projects(self):
        projects = wd.discover_projects()
        assert isinstance(projects, list)
        assert len(projects) == 5

    def test_discovers_all_agents(self):
        agents = wd.discover_agents()
        assert isinstance(agents, list)
        assert len(agents) > 0
        for agent in agents:
            assert "name" in agent, f"agent missing 'name': {agent}"
            assert "sigil" in agent, f"agent missing 'sigil': {agent}"

    def test_agent_groups_have_orchestrators(self):
        agents = wd.discover_agents()
        # Group by sigil
        from collections import defaultdict
        groups: dict[str, list[dict]] = defaultdict(list)
        for a in agents:
            groups[a["sigil"]].append(a)
        for sigil, group_agents in groups.items():
            names = [a["name"] for a in group_agents]
            assert any("orchestrator" in n for n in names), (
                f"No orchestrator found for sigil '{sigil}'. Agents: {names}"
            )

    def test_project_metadata_correct(self):
        projects = wd.discover_projects()
        for p in projects:
            assert "name" in p, f"project missing 'name': {p}"
            assert "root" in p, f"project missing 'root': {p}"
            assert "sigil" in p, f"project missing 'sigil': {p}"
            assert isinstance(p["root"], Path), (
                f"project['root'] should be Path, got {type(p['root'])}"
            )
            assert isinstance(p["sigil"], str) and len(p["sigil"]) > 0, (
                f"project['sigil'] should be non-empty str, got {p['sigil']!r}"
            )


# ---------------------------------------------------------------------------
# TestRouting
# ---------------------------------------------------------------------------

_ROUTING_CASES = [
    ("Add test harness to all projects",            "fan-out-doer"),
    ("Scaffold identical CI configs in all projects", "fan-out-doer"),
    ("Status update on all projects",               "fan-out-orchestrators"),
    ("Run ∞Life budget check",                      "single-project"),
    ("What's the weather?",                         "ambiguous"),
]


class TestRouting:
    @pytest.mark.parametrize("req,expected_strategy", _ROUTING_CASES)
    def test_routing_strategy(self, req: str, expected_strategy: str):
        result = wd.route_request(req)
        assert result["strategy"] == expected_strategy, (
            f"request={req!r}: expected {expected_strategy!r}, got {result['strategy']!r}"
        )

    def test_single_project_routing(self):
        result = wd.route_request("Check ❤Music catalog")
        assert result["strategy"] == "single-project"

    def test_multi_request_has_alignment_delegate(self):
        result = wd.route_request("Status update on all projects")
        assert "alignment_delegate" in result, (
            f"result missing 'alignment_delegate' key: {result}"
        )


# ---------------------------------------------------------------------------
# TestAlignment
# ---------------------------------------------------------------------------

class TestAlignment:
    def test_alignment_report_structure(self):
        report = wd.alignment_report()
        assert isinstance(report, list)
        for entry in report:
            assert "project" in entry,    f"entry missing 'project': {entry}"
            assert "has_tests" in entry,  f"entry missing 'has_tests': {entry}"
            assert "test_count" in entry, f"entry missing 'test_count': {entry}"

    @pytest.mark.skipif(
        os.getenv("CI") == "true",
        reason="requires local multi-root workspace filesystem (all 5 projects checked out)",
    )
    def test_all_projects_have_tests(self):
        report = wd.alignment_report()
        assert len(report) == 5
        for entry in report:
            assert entry["has_tests"] is True, (
                f"Project {entry['project']!r} has no tests (has_tests=False)"
            )


# ---------------------------------------------------------------------------
# Perf
# ---------------------------------------------------------------------------

class TestPerf:
    def test_full_pipeline_perf(self):
        start = time.perf_counter()
        wd.discover_projects()
        wd.discover_agents()
        wd.route_request("Add test harness to all projects")
        wd.alignment_report()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500, f"Full pipeline took {elapsed_ms:.1f} ms (limit: 500 ms)"
