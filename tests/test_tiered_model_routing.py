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


def test_recycled_changes_requested_routing_is_light_even_after_repeated_recycling() -> None:
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)

    first = cr.select_routing_path(initial_tier="heavy", current_state="CHANGES_REQUESTED")
    repeated = cr.select_routing_path(initial_tier=first.tier, current_state="CHANGES_REQUESTED")

    assert first.tier == "light"
    assert first.path == "recycled-light"
    assert repeated.tier == "light"
    assert repeated.path == "recycled-light"


def test_eligible_bounded_fix_bypasses_only_qa_and_architecture_review() -> None:
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)

    evidence = cr.BoundedFixEvidence(
        files_changed=2,
        project_count=1,
        has_schema_change=False,
        has_dependency_change=False,
        has_agent_change=False,
        has_integration_change=False,
        has_authentication_change=False,
        has_secret_change=False,
        has_security_change=False,
        defect_classification="localized",
        focused_tests_passed=True,
        cross_module_change=False,
        contract_changed=False,
    )
    decision = cr.select_routing_path(
        initial_tier="standard",
        current_state="CHANGES_REQUESTED",
        bounded_fix=evidence,
    )

    assert decision.path == "bounded-fix"
    assert decision.tier == "light"
    assert decision.bypasses == ("FUNCTIONAL_QA", "ARCHITECTURE_REVIEW")
    assert decision.preserved_gates == ("approval", "merge", "soak", "signoff")


@pytest.mark.parametrize("current_state", ["IN_PROGRESS", "OPEN"])
def test_bounded_fix_requires_changes_requested_state(current_state: str) -> None:
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)

    evidence = cr.BoundedFixEvidence(
        files_changed=2,
        project_count=1,
        has_schema_change=False,
        has_dependency_change=False,
        has_agent_change=False,
        has_integration_change=False,
        has_authentication_change=False,
        has_secret_change=False,
        has_security_change=False,
        defect_classification="localized",
        focused_tests_passed=True,
        cross_module_change=False,
        contract_changed=False,
    )

    decision = cr.select_routing_path(
        initial_tier="standard",
        current_state=current_state,
        bounded_fix=evidence,
    )

    assert decision.path == "normal"
    assert decision.tier == "standard"
    assert decision.bypasses == ()
    assert decision.rejection_reason == "bounded-fix requires CHANGES_REQUESTED state"


def test_bounded_fix_rejects_architectural_or_security_sensitive_work() -> None:
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)

    evidence = cr.BoundedFixEvidence(
        files_changed=1,
        project_count=1,
        has_schema_change=False,
        has_dependency_change=False,
        has_agent_change=False,
        has_integration_change=False,
        has_authentication_change=True,
        has_secret_change=False,
        has_security_change=False,
        defect_classification="localized",
        focused_tests_passed=True,
        cross_module_change=False,
        contract_changed=False,
    )
    decision = cr.select_routing_path(
        initial_tier="heavy",
        current_state="CHANGES_REQUESTED",
        bounded_fix=evidence,
    )

    assert decision.path == "recycled-light"
    assert decision.bypasses == ()
    assert "authentication" in decision.rejection_reason


def test_routing_decision_produces_fr_history_evidence() -> None:
    import importlib, sys
    sys.path.insert(0, str(SRC_UTILS))
    cr = importlib.import_module("complexity_router")
    importlib.reload(cr)

    decision = cr.select_routing_path(initial_tier="heavy", current_state="CHANGES_REQUESTED")

    summary = cr.format_routing_event(decision)

    assert "ROUTING_PATH: recycled-light" in summary
    assert "TIER: light" in summary
    assert "EVIDENCE:" in summary


def test_recycled_routing_contract_names_all_light_gate_agents() -> None:
    flow = _read(INSTRUCTIONS_DIR / "feature-request-flow.instructions.md")
    overseer = _read(AGENTS_DIR / "⊕workspace-overseer.agent.md")

    for agent in (
        "⊕workspace-tdd-light",
        "⊕workspace-qa-light",
        "⊕workspace-architecture-reviewer-light",
        "⊕workspace-reviewer-light",
    ):
        assert agent in flow
        assert agent in overseer
    assert "repeated recycling" in flow.lower()
    assert "ROUTING_PATH" in flow


def test_light_architecture_reviewer_preserves_standard_hard_gates() -> None:
    path = AGENTS_DIR / "⊕workspace-architecture-reviewer-light.agent.md"
    assert path.exists()
    text = _read(path)
    assert "model: claude-haiku-4-5" in text
    assert "STALE" in text and "MISSING" in text
    assert "do not modify any `.mmd` file" in text.lower()
    assert "hard gates" in text.lower()


def test_bounded_fix_contract_is_fail_closed_and_preserves_final_gates() -> None:
    flow = _read(INSTRUCTIONS_DIR / "feature-request-flow.instructions.md")

    assert re.search(r"<=2\s+changed files", flow)
    assert "focused tests pass" in flow
    assert "bypass full QA and architecture review" in flow
    for gate in ("approval", "merge", "soak", "signoff"):
        assert gate in flow.lower()
    for excluded in ("architectural", "security-sensitive", "multi-project", "contract-changing"):
        assert excluded in flow.lower()
