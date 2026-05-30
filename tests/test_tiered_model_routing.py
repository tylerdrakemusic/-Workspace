"""Tests for FR-20260529-tiered-model-routing.

Verifies:
  1. All 9 tiered pipeline agents exist with correct model: frontmatter
  2. Existing ⊕workspace-qa and ⊕workspace-reviewer are pinned to standard-tier models
  3. COMPLEXITY_ASSESSED routing table appears in feature-request-flow.instructions.md
  4. complexity_router.py routes FR signals to the correct tier
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "agents"
INSTRUCTIONS_DIR = Path(__file__).resolve().parents[1] / ".github" / "instructions"
SRC_UTILS = Path(__file__).resolve().parents[1] / "src" / "utils"

# ── model matrix ─────────────────────────────────────────────────────────────
# Maps each agent filename → expected value of the model: frontmatter field.
TIERED_AGENT_MODELS: dict[str, str] = {
    # TDD agents (Anthropic)
    "⊕workspace-tdd-light.agent.md": "claude-haiku-4-5",
    "⊕workspace-tdd-standard.agent.md": "claude-sonnet-4-6",
    "⊕workspace-tdd-heavy.agent.md": "claude-opus-4-8",
    # QA agents (OpenAI) — existing file becomes standard
    "⊕workspace-qa-light.agent.md": "gpt-5.4-mini",
    "⊕workspace-qa.agent.md": "gpt-5.3-codex",
    "⊕workspace-qa-heavy.agent.md": "gpt-5.5",
    # Review agents (Google) — existing file becomes standard
    "⊕workspace-reviewer-light.agent.md": "gemini-3-flash",
    "⊕workspace-reviewer.agent.md": "gemini-2.5-pro",
    "⊕workspace-reviewer-heavy.agent.md": "gemini-3.1-pro",
}


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


# ── AC1/AC2: agent files exist with correct model: frontmatter ────────────────

@pytest.mark.parametrize("filename,expected_model", list(TIERED_AGENT_MODELS.items()))
def test_tiered_agent_exists(filename: str, expected_model: str) -> None:
    path = AGENTS_DIR / filename
    assert path.exists(), f"Missing tiered agent file: {path}"


@pytest.mark.parametrize("filename,expected_model", list(TIERED_AGENT_MODELS.items()))
def test_tiered_agent_has_model_frontmatter(filename: str, expected_model: str) -> None:
    path = AGENTS_DIR / filename
    text = _read(path)
    fm = _frontmatter(text)
    assert fm, f"No YAML frontmatter in {filename}"
    match = re.search(r"^model:\s*(.+)\s*$", fm, re.MULTILINE)
    assert match, f"{filename} frontmatter missing 'model:' field"
    actual = match.group(1).strip().strip('"').strip("'")
    assert actual == expected_model, (
        f"{filename}: expected model '{expected_model}', got '{actual}'"
    )


@pytest.mark.parametrize("filename,expected_model", list(TIERED_AGENT_MODELS.items()))
def test_tiered_agent_has_description(filename: str, expected_model: str) -> None:
    path = AGENTS_DIR / filename
    text = _read(path)
    fm = _frontmatter(text)
    assert re.search(r'^description:\s*".+"', fm, re.MULTILINE), (
        f"{filename} frontmatter missing description field"
    )


# ── AC3: COMPLEXITY_ASSESSED in feature-request-flow ─────────────────────────

def test_feature_request_flow_has_complexity_assessed() -> None:
    path = INSTRUCTIONS_DIR / "feature-request-flow.instructions.md"
    assert path.exists(), "feature-request-flow.instructions.md not found"
    text = _read(path)
    assert "COMPLEXITY_ASSESSED" in text, (
        "feature-request-flow.instructions.md missing COMPLEXITY_ASSESSED state"
    )


def test_feature_request_flow_has_tier_routing_table() -> None:
    path = INSTRUCTIONS_DIR / "feature-request-flow.instructions.md"
    text = _read(path)
    for keyword in ("light", "standard", "heavy"):
        assert keyword in text.lower(), (
            f"feature-request-flow.instructions.md missing tier '{keyword}' in routing table"
        )


# ── AC4/AC6: complexity_router.py routing logic ───────────────────────────────

def test_complexity_router_module_exists() -> None:
    assert (SRC_UTILS / "complexity_router.py").exists(), (
        "src/utils/complexity_router.py not found"
    )


def test_complexity_router_light() -> None:
    """1 file, no schema change, single project → light."""
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)
    assert cr.assess_tier(files_changed=1, has_new_schema=False,
                          has_new_agents=False, project_count=1,
                          is_security_sensitive=False) == "light"


def test_complexity_router_standard() -> None:
    """5 files, schema edit, 2 projects → standard."""
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)
    assert cr.assess_tier(files_changed=5, has_new_schema=False,
                          has_new_agents=False, project_count=2,
                          is_security_sensitive=False) == "standard"


def test_complexity_router_heavy_by_file_count() -> None:
    """15 files → heavy."""
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)
    assert cr.assess_tier(files_changed=15, has_new_schema=False,
                          has_new_agents=False, project_count=1,
                          is_security_sensitive=False) == "heavy"


def test_complexity_router_heavy_by_new_schema() -> None:
    """New DB schema → heavy regardless of file count."""
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)
    assert cr.assess_tier(files_changed=2, has_new_schema=True,
                          has_new_agents=False, project_count=1,
                          is_security_sensitive=False) == "heavy"


def test_complexity_router_heavy_by_security() -> None:
    """Security-sensitive (health data / auth) → heavy."""
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)
    assert cr.assess_tier(files_changed=1, has_new_schema=False,
                          has_new_agents=False, project_count=1,
                          is_security_sensitive=True) == "heavy"


def test_complexity_router_heavy_by_new_agents() -> None:
    """New agents/integrations → heavy."""
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)
    assert cr.assess_tier(files_changed=3, has_new_schema=False,
                          has_new_agents=True, project_count=1,
                          is_security_sensitive=False) == "heavy"


def test_complexity_router_standard_boundary() -> None:
    """3 files, single project, no special flags → standard (above light threshold)."""
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)
    assert cr.assess_tier(files_changed=3, has_new_schema=False,
                          has_new_agents=False, project_count=1,
                          is_security_sensitive=False) == "standard"
