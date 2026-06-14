"""Unit tests for src/utils/agent_frontmatter_integrity.py."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

import agent_frontmatter_integrity as afi  # noqa: E402


def _init_manifest_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE todos (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               project TEXT NOT NULL,
               source TEXT NOT NULL,
               text TEXT NOT NULL,
               done INTEGER NOT NULL DEFAULT 0,
               created_at TEXT NOT NULL,
               closed_at TEXT,
               priority INTEGER NOT NULL DEFAULT 5,
               autonomy_level TEXT NOT NULL DEFAULT 'supervised',
               rationale TEXT,
               fr_id TEXT
           )"""
    )
    conn.commit()
    conn.close()


def test_frontmatter_parsing() -> None:
    text = """---\ndescription: \"Example agent\"\napplyTo: \".github/agents/*.agent.md\"\n---\n# Body\n"""
    fm = afi._frontmatter(text)
    assert fm["description"] == "Example agent"
    assert fm["applyTo"] == ".github/agents/*.agent.md"


def test_apply_to_matches() -> None:
    files = [Path(r"f:\.github\agents\foo.agent.md"), Path(r"f:\.github\instructions\bar.instructions.md")]
    assert afi._apply_to_matches(".github/agents/*.agent.md", files)
    assert not afi._apply_to_matches(".github/prompts/*.prompt.md", files)


def test_run_agent_frontmatter_integrity_creates_scan_todo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    agents_dir = workspace / ".github" / "agents"
    instructions_dir = workspace / ".github" / "instructions"
    agents_dir.mkdir(parents=True)
    instructions_dir.mkdir(parents=True)

    agent_file = agents_dir / "⊕workspace-example.agent.md"
    agent_file.write_text(
        "---\n"
        "description: \"Example agent\"\n"
        "applyTo: \".github/agents/*.agent.md\"\n"
        "---\n"
        "# Example agent\n",
        encoding="utf-8",
    )

    instruction_file = instructions_dir / "hygiene-base.instructions.md"
    instruction_file.write_text(
        "---\napplyTo: \".github/agents/*.agent.md\"\n---\n# Hygiene base\n",
        encoding="utf-8",
    )

    manifest_db = tmp_path / "manifest_todos.db"
    _init_manifest_db(manifest_db)

    monkeypatch.setattr(afi, "AGENT_DIRS", [agents_dir])
    monkeypatch.setattr(afi, "INSTRUCTION_DIR", instructions_dir)
    monkeypatch.setattr(afi, "MANIFEST_DB", manifest_db)
    monkeypatch.setattr(
        afi,
        "_all_workspace_md_files",
        lambda: [agent_file, instruction_file],
    )

    result = afi.run_agent_frontmatter_integrity(fr_id="FR-TEST")
    assert result["issues"] == 0
    assert result["warnings"] == 1
    assert result["todo_id"] is not None
    assert "NO INHERITANCE" in result["summary"]

    conn = sqlite3.connect(str(manifest_db))
    row = conn.execute("SELECT project, source, text, fr_id FROM todos").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "workspace"
    assert row[1] == "SCAN"
    assert row[2] == afi.SCAN_TODO_TEXT
    assert row[3] == "FR-TEST"


def test_run_agent_frontmatter_integrity_reports_invalid_frontmatter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    agents_dir = workspace / ".github" / "agents"
    instructions_dir = workspace / ".github" / "instructions"
    agents_dir.mkdir(parents=True)
    instructions_dir.mkdir(parents=True)

    agent_file = agents_dir / "broken.agent.md"
    agent_file.write_text("# Missing frontmatter\n", encoding="utf-8")

    instruction_file = instructions_dir / "broken.instructions.md"
    instruction_file.write_text("# Missing frontmatter\n", encoding="utf-8")

    manifest_db = tmp_path / "manifest_todos.db"
    _init_manifest_db(manifest_db)

    monkeypatch.setattr(afi, "AGENT_DIRS", [agents_dir])
    monkeypatch.setattr(afi, "INSTRUCTION_DIR", instructions_dir)
    monkeypatch.setattr(afi, "MANIFEST_DB", manifest_db)
    monkeypatch.setattr(
        afi,
        "_all_workspace_md_files",
        lambda: [agent_file, instruction_file],
    )

    result = afi.run_agent_frontmatter_integrity()
    assert result["issues"] >= 1
    assert result["warnings"] == 0
    assert result["todo_id"] is not None
    assert "INVALID FRONTMATTER" in result["summary"]
