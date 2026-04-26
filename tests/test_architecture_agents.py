"""Tests for the ⊕Workspace agent customization files.

Verifies that critical agents exist on disk and have valid YAML frontmatter
following the workspace conventions:
  - file starts with `---` on line 1
  - frontmatter contains a `description:` field
  - file body has a level-1 heading
  - inherits-block (if present) references real instruction files

Specific to FR-20260425-architecture-review-agents:
  - ⊕workspace-architecture-reviewer.agent.md exists
  - ⊕workspace-architecture-beautifier.agent.md exists
  - both inherit from feature-request-flow + agent-self-regen
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "agents"
INSTRUCTIONS_DIR = Path(__file__).resolve().parents[1] / ".github" / "instructions"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> str:
    """Return the YAML frontmatter block (excluding the --- delimiters)."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    return text[3:end].strip()


@pytest.mark.parametrize(
    "agent_filename",
    [
        "⊕workspace-architecture-reviewer.agent.md",
        "⊕workspace-architecture-beautifier.agent.md",
    ],
)
def test_architecture_agent_exists(agent_filename: str):
    path = AGENTS_DIR / agent_filename
    assert path.exists(), f"Missing agent file: {path}"
    text = _read(path)
    assert text.startswith("---"), "Agent must start with YAML frontmatter"


@pytest.mark.parametrize(
    "agent_filename",
    [
        "⊕workspace-architecture-reviewer.agent.md",
        "⊕workspace-architecture-beautifier.agent.md",
    ],
)
def test_architecture_agent_frontmatter_valid(agent_filename: str):
    path = AGENTS_DIR / agent_filename
    text = _read(path)
    fm = _frontmatter(text)
    assert fm, f"No frontmatter in {agent_filename}"
    assert re.search(r"^description:\s*\".+\"\s*$", fm, re.MULTILINE), \
        f"{agent_filename} frontmatter missing description field"


@pytest.mark.parametrize(
    "agent_filename",
    [
        "⊕workspace-architecture-reviewer.agent.md",
        "⊕workspace-architecture-beautifier.agent.md",
    ],
)
def test_architecture_agent_has_h1(agent_filename: str):
    path = AGENTS_DIR / agent_filename
    text = _read(path)
    body = text.split("---", 2)[-1]
    assert re.search(r"^#\s+\S", body, re.MULTILINE), \
        f"{agent_filename} body missing level-1 heading"


@pytest.mark.parametrize(
    "agent_filename",
    [
        "⊕workspace-architecture-reviewer.agent.md",
        "⊕workspace-architecture-beautifier.agent.md",
    ],
)
def test_architecture_agent_inherits_known_instructions(agent_filename: str):
    path = AGENTS_DIR / agent_filename
    text = _read(path)
    inherits = re.findall(r"<!--\s*inherits:\s*(.+?)\s*-->", text)
    assert inherits, f"{agent_filename} missing any <!-- inherits: ... --> block"
    for inh in inherits:
        # paths in inherits are absolute (start with f:\.github\instructions\)
        # ensure each referenced filename actually exists in the instructions dir
        filename = Path(inh).name
        assert (INSTRUCTIONS_DIR / filename).exists(), \
            f"{agent_filename} inherits unknown instruction file: {filename}"


def test_workspace_integrations_diagram_exists():
    diagrams_dir = Path(__file__).resolve().parents[1] / "diagrams"
    target = diagrams_dir / "workspace-integrations.mmd"
    assert target.exists(), f"Seed diagram missing: {target}"
    text = target.read_text(encoding="utf-8")
    assert "graph LR" in text or "graph TD" in text, "must be a graph diagram"
    # House style: classDef block present
    assert "classDef ext" in text and "classDef db" in text, \
        "workspace-integrations.mmd missing house-style classDef block"


def test_reviewer_has_architecture_gate():
    """⊕workspace-reviewer.agent.md must include the architecture-diagrams check
    introduced by FR-20260425-architecture-review-agents."""
    reviewer = AGENTS_DIR / "⊕workspace-reviewer.agent.md"
    text = reviewer.read_text(encoding="utf-8")
    assert "Architecture Diagrams" in text or "architecture-reviewer" in text, \
        "⊕workspace-reviewer must reference the architecture diagrams gate"


def test_fr_flow_has_architecture_review_state():
    flow = INSTRUCTIONS_DIR / "feature-request-flow.instructions.md"
    text = flow.read_text(encoding="utf-8")
    assert "ARCHITECTURE_REVIEW" in text, \
        "FR flow must define the ARCHITECTURE_REVIEW state"
