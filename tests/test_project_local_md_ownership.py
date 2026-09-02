from __future__ import annotations

from pathlib import Path

import agent_frontmatter_integrity as integrity
import workspace_discovery as discovery


def test_discovery_includes_project_local_agent_directories(tmp_path: Path, monkeypatch) -> None:
    workspace_agents = tmp_path / "workspace" / ".github" / "agents"
    project_agents = tmp_path / "project" / ".github" / "agents"
    workspace_agents.mkdir(parents=True)
    project_agents.mkdir(parents=True)
    (workspace_agents / "⊕workspace-example.agent.md").write_text(
        "---\ndescription: workspace\n---\n", encoding="utf-8"
    )
    (project_agents / "❤music-example.agent.md").write_text(
        "---\ndescription: music\n---\n", encoding="utf-8"
    )

    monkeypatch.setattr(discovery, "AGENT_DIRS", [workspace_agents, project_agents])
    names = {agent["name"] for agent in discovery.discover_agents()}

    assert names == {"⊕workspace-example", "❤music-example"}


def test_integrity_scans_project_local_markdown(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    agents_dir = project_root / ".github" / "agents"
    instructions_dir = project_root / ".github" / "instructions"
    agents_dir.mkdir(parents=True)
    instructions_dir.mkdir(parents=True)
    agent_file = agents_dir / "❤music-example.agent.md"
    agent_file.write_text(
        "---\ndescription: music\napplyTo: '.github/agents/*.agent.md'\n---\n"
        "<!-- inherits: ../../.github/instructions/❤music-base.instructions.md -->\n",
        encoding="utf-8",
    )
    instruction_file = instructions_dir / "❤music-base.instructions.md"
    instruction_file.write_text(
        "---\napplyTo: '.github/agents/*.agent.md'\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(integrity, "AGENT_DIRS", [agents_dir])
    monkeypatch.setattr(integrity, "INSTRUCTION_DIRS", [instructions_dir])
    monkeypatch.setattr(integrity, "MD_ROOTS", [project_root / ".github"])
    monkeypatch.setattr(integrity, "INSTRUCTION_DIR", instructions_dir)
    monkeypatch.setattr(integrity, "_create_or_update_scan_todo", lambda *args, **kwargs: None)

    result = integrity.run_agent_frontmatter_integrity()

    assert result["issues"] == 0


def test_workspace_tree_keeps_shared_markdown_and_removes_project_copies() -> None:
    workspace_root = Path(__file__).resolve().parents[1]
    project_owned = (
        ".github/agents/∞life-orchestrator.agent.md",
        ".github/instructions/∞life-base.instructions.md",
        ".github/agents/❤music-orchestrator.agent.md",
        ".github/instructions/❤music-base.instructions.md",
        ".github/agents/⟨ψ⟩quantum-orchestrator.agent.md",
        ".github/instructions/⟨ψ⟩quantum-base.instructions.md",
        ".github/agents/👁ai-manifest-orchestrator.agent.md",
        ".github/agents/Σcapital-orchestrator.agent.md",
        ".github/instructions/sigmacapital-watchlist-workflow.instructions.md",
        ".github/prompts/sigmacapital-picker-flow.prompt.md",
    )
    shared = (
        ".github/agents/⊕workspace-overseer.agent.md",
        ".github/instructions/feature-request-flow.instructions.md",
        ".github/skills/test-driven-development/SKILL.md",
        ".github/copilot-instructions.md",
    )

    assert all(not (workspace_root / path).exists() for path in project_owned)
    assert all((workspace_root / path).exists() for path in shared)