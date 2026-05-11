"""Tests for FR-20260511-worktree-local-migration.

Verifies that all acceptance criteria artifacts are in place:
  AC1/AC5: ⊕workspace-ci.agent.md documents local worktree path + batch SOP
  AC2:     .gitignore contains .worktrees/ entry
  AC3:     workspace.code-workspace excludes .worktrees/ from IDE explorer/search
  AC4:     pre-commit hook script exists and contains the guard logic
  AC6:     ⊕workspace-reviewer.agent.md has Gate 3.6 worktree path audit
  AC7:     ⊕workspace-hygiene.agent.md has stale worktree cleanup section
  AC8:     ⊕workspace-ci.agent.md deprecates external worktrees
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / ".github" / "agents"
HOOKS_DIR = REPO_ROOT / ".github" / "hooks" / "scripts"
GITIGNORE = REPO_ROOT / ".gitignore"
CODE_WORKSPACE = REPO_ROOT / "workspace.code-workspace"
CI_AGENT = AGENTS_DIR / "⊕workspace-ci.agent.md"
REVIEWER_AGENT = AGENTS_DIR / "⊕workspace-reviewer.agent.md"
HYGIENE_AGENT = AGENTS_DIR / "⊕workspace-hygiene.agent.md"
HOOK_SCRIPT = HOOKS_DIR / "pre-commit-worktree-guard.sh"


# ── AC2: .gitignore ──────────────────────────────────────────────────────────

def test_gitignore_has_worktrees_entry():
    """AC2: .gitignore must contain a .worktrees/ entry."""
    text = GITIGNORE.read_text(encoding="utf-8")
    assert ".worktrees/" in text, ".gitignore missing .worktrees/ entry"


# ── AC3: VS Code exclusions ──────────────────────────────────────────────────

def test_vscode_workspace_excludes_worktrees():
    """AC3: workspace.code-workspace must exclude .worktrees/ from explorer and search."""
    data = json.loads(CODE_WORKSPACE.read_text(encoding="utf-8"))
    settings = data.get("settings", {})

    files_exclude = settings.get("files.exclude", {})
    assert any(".worktrees" in k for k in files_exclude), \
        "workspace.code-workspace files.exclude must include .worktrees"

    search_exclude = settings.get("search.exclude", {})
    assert any(".worktrees" in k for k in search_exclude), \
        "workspace.code-workspace search.exclude must include .worktrees"


# ── AC4: pre-commit hook ─────────────────────────────────────────────────────

def test_precommit_hook_script_exists():
    """AC4: pre-commit-worktree-guard.sh must exist."""
    assert HOOK_SCRIPT.exists(), f"Pre-commit hook script missing: {HOOK_SCRIPT}"


def test_precommit_hook_blocks_worktrees():
    """AC4: hook script must contain .worktrees/ guard logic."""
    text = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert ".worktrees/" in text, "Hook script missing .worktrees/ guard pattern"
    assert "exit 1" in text, "Hook script must exit with code 1 on violation"


# ── AC1+AC5: CI agent ────────────────────────────────────────────────────────

def test_ci_agent_documents_local_worktree_path():
    """AC1: CI agent must document .worktrees/{branch-slug}/ as the new path."""
    text = CI_AGENT.read_text(encoding="utf-8")
    assert ".worktrees/" in text, \
        "⊕workspace-ci.agent.md must document .worktrees/ worktree path"
    assert ".worktrees" in text and "branch-slug" in text, \
        "CI agent must show the .worktrees/{branch-slug} path pattern"


def test_ci_agent_has_batch_sop():
    """AC5: CI agent must document batch git worktree add SOP (single terminal session)."""
    text = CI_AGENT.read_text(encoding="utf-8")
    assert "batch" in text.lower() or "single terminal session" in text.lower(), \
        "CI agent must mention batching worktree adds into one terminal session"
    assert "git worktree add" in text, \
        "CI agent must include git worktree add example"


# ── AC6: reviewer Gate 3.6 ──────────────────────────────────────────────────

def test_reviewer_has_worktree_path_audit_gate():
    """AC6: reviewer agent must have a worktree path audit gate."""
    text = REVIEWER_AGENT.read_text(encoding="utf-8")
    assert ".worktrees/" in text, \
        "⊕workspace-reviewer.agent.md must include .worktrees/ path audit"
    assert "3.6" in text or "Worktree Path Audit" in text, \
        "Reviewer must name the worktree path audit gate"


# ── AC7: hygiene cleanup ─────────────────────────────────────────────────────

def test_hygiene_agent_has_worktree_cleanup():
    """AC7: hygiene agent must include stale worktree cleanup section."""
    text = HYGIENE_AGENT.read_text(encoding="utf-8")
    assert ".worktrees" in text, \
        "⊕workspace-hygiene.agent.md must reference .worktrees/ cleanup"
    assert "worktree prune" in text or "git worktree" in text, \
        "Hygiene agent must include git worktree prune / remove steps"
    assert "stale" in text.lower(), \
        "Hygiene agent must describe stale worktree detection"


# ── AC8: migration / deprecation note ───────────────────────────────────────

def test_ci_agent_deprecates_external_worktrees():
    """AC8: CI agent must mark legacy external worktree paths as deprecated."""
    text = CI_AGENT.read_text(encoding="utf-8")
    assert "deprecated" in text.lower() or "Deprecated" in text, \
        "CI agent must mark external worktrees as deprecated"
