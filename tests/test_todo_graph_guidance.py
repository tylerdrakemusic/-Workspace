"""Contracts for oversized-scope todo guidance."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_perfect_scoped_todo_proposes_approval_gated_child_chain() -> None:
    text = (ROOT / ".github" / "skills" / "perfect-scoped-td" / "SKILL.md").read_text(encoding="utf-8")
    assert "oversized" in text.lower()
    assert "approval-gated" in text.lower()
    assert "child" in text.lower()
    assert "Do not create FR transitions" in text


def test_intake_detects_oversized_scope_without_transitioning_fr_from_todo_code() -> None:
    text = (ROOT / ".github" / "agents" / "⊕workspace-intake.agent.md").read_text(encoding="utf-8")
    assert "oversized" in text.lower()
    assert "child chain" in text.lower()
    assert "create FR transitions" in text