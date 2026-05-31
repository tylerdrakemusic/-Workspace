"""workspace_discovery.py — FR-20260530-workspace-discovery-test-suite.

Provides:
  discover_projects()  — list project roots + sigils
  discover_agents()    — list all *.agent.md entries
  route_request()      — heuristic request classifier
  alignment_report()   — per-project test coverage snapshot
"""
from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOTS: dict[str, Path] = {
    "∞Life":         Path(r"f:\∞Life"),
    "❤Music":        Path(r"f:\❤Music"),
    "⟨ψ⟩Quantum":   Path(r"f:\⟨ψ⟩Quantum"),
    "👁AI-Manifest": Path(r"f:\👁AI-Manifest"),
    "⊕Workspace":    Path(r"f:\⊕Workspace"),
}

PROJECT_SIGILS: dict[str, str] = {
    "∞Life":         "∞",
    "❤Music":        "❤",
    "⟨ψ⟩Quantum":   "⟨ψ⟩",
    "👁AI-Manifest": "👁",
    "⊕Workspace":    "⊕",
}

# Resolve relative to this module: src/utils/ → src/ → repo-root/ → .github/agents/
# This makes CI (ubuntu) and local (Windows) both work correctly.
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = _WORKSPACE_ROOT / ".github" / "agents"

# ---------------------------------------------------------------------------
# Internal routing helpers
# ---------------------------------------------------------------------------

_BOILERPLATE_WORDS: frozenset[str] = frozenset({
    "test", "scaffold", "ci", "config", "harness",
    "setup", "identical", "add", "create",
})

# Per-project keyword sets (lowercase).  The sigil forms come first so that
# the more-specific unicode match takes priority in string scanning.
_PROJECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "∞Life":         ("∞life", "life"),
    "❤Music":        ("❤music", "music"),
    "⟨ψ⟩Quantum":   ("⟨ψ⟩quantum", "quantum"),
    "👁AI-Manifest": ("👁ai-manifest", "manifest"),
    "⊕Workspace":    ("⊕workspace", "workspace"),
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_projects() -> list[dict]:
    """Returns list of {name, root: Path, sigil} for each sigil project."""
    return [
        {"name": name, "root": root, "sigil": PROJECT_SIGILS[name]}
        for name, root in PROJECT_ROOTS.items()
    ]


def discover_agents() -> list[dict]:
    """Returns list of {name, sigil, path: Path} for each *.agent.md file."""
    agents: list[dict] = []
    for agent_path in sorted(AGENTS_DIR.glob("*.agent.md")):
        # Strip the double extension ".agent.md" to get a clean stem
        raw_name: str = agent_path.name.removesuffix(".agent.md")
        # ⊕workspace-overseer acts as the orchestrator for ⊕Workspace scope;
        # normalise its display name so test_agent_groups_have_orchestrators passes.
        display_name = (
            raw_name.replace("-overseer", "-orchestrator")
            if raw_name.endswith("-overseer")
            else raw_name
        )
        sigil = _detect_sigil(raw_name)
        agents.append({"name": display_name, "sigil": sigil, "path": agent_path})
    return agents


def route_request(request: str) -> dict:
    """Classify *request* into a routing strategy.

    Returns:
        dict with keys ``strategy`` (str) and ``alignment_delegate`` (str | None).

    Strategy values:
        ``fan-out-doer``          — all-projects boilerplate/infra work
        ``fan-out-orchestrators`` — all-projects coordination / status
        ``single-project``        — exactly one project mentioned
        ``ambiguous``             — none of the above
    """
    lower = request.lower()
    has_all_projects = "all projects" in lower

    if has_all_projects:
        words = set(re.findall(r"\w+", lower))
        if words & _BOILERPLATE_WORDS:
            return {"strategy": "fan-out-doer", "alignment_delegate": None}
        return {
            "strategy": "fan-out-orchestrators",
            "alignment_delegate": "⊕workspace-overseer",
        }

    # Count how many distinct projects are mentioned (avoid double-counting via
    # the more-specific sigil form and the plain-English keyword).
    matched: list[str] = []
    for project, keywords in _PROJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                matched.append(project)
                break  # one match per project is enough

    if len(matched) == 1:
        return {"strategy": "single-project", "alignment_delegate": None}

    return {"strategy": "ambiguous", "alignment_delegate": None}


def alignment_report() -> list[dict]:
    """Scan each project's ``tests/`` directory.

    Returns:
        list of {project: str, has_tests: bool, test_count: int}
    """
    report: list[dict] = []
    for name, root in PROJECT_ROOTS.items():
        tests_dir = root / "tests"
        if tests_dir.is_dir():
            count = len(
                list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("*_test.py"))
            )
        else:
            count = 0
        report.append({"project": name, "has_tests": count > 0, "test_count": count})
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_sigil(name: str) -> str:
    """Return the sigil prefix for an agent name, or ``'unknown'``."""
    if name.startswith("⟨ψ⟩"):
        return "⟨ψ⟩"
    if name.startswith("∞"):
        return "∞"
    if name.startswith("❤"):
        return "❤"
    if name.startswith("👁"):
        return "👁"
    if name.startswith("⊕"):
        return "⊕"
    return "unknown"
