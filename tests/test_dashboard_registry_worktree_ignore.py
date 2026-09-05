from __future__ import annotations

import json
import importlib.util
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "tools"))

import dashboard_registry as dr  # noqa: E402


def test_git_worktree_clone_is_skipped(tmp_path: Path) -> None:
    main_root = tmp_path / "⊕Workspace"
    worktree_root = tmp_path / "workspace-order-type-guidance"
    main_root.mkdir(parents=True)
    worktree_root.mkdir(parents=True)

    (main_root / "AGENT_STARTUP.md").write_text("root startup\n", encoding="utf-8")
    (worktree_root / "AGENT_STARTUP.md").write_text("worktree startup\n", encoding="utf-8")
    (worktree_root / ".git").write_text(
        "gitdir: F:/⊕Workspace/.git/worktrees/workspace-order-type-guidance\n",
        encoding="utf-8",
    )

    assert dr._is_git_worktree_root(worktree_root)

    with patch.object(dr, "WORKSPACE_ROOT", tmp_path):
        projects = dr.discover_projects()

    assert main_root in projects
    assert worktree_root not in projects


def test_non_live_snapshot_is_skipped_but_canonical_root_is_discovered(tmp_path: Path) -> None:
    canonical_root = tmp_path / "❤Music"
    snapshot_root = tmp_path / "qa-FR-20260905-music"
    canonical_root.mkdir(parents=True)
    snapshot_root.mkdir(parents=True)

    (canonical_root / "AGENT_STARTUP.md").write_text("root startup\n", encoding="utf-8")
    (snapshot_root / "AGENT_STARTUP.md").write_text("snapshot startup\n", encoding="utf-8")

    with patch.object(dr, "WORKSPACE_ROOT", tmp_path):
        projects = dr.discover_projects()

    assert canonical_root in projects
    assert snapshot_root not in projects


def test_build_manifest_ignores_worktree_clone(tmp_path: Path) -> None:
    main_root = tmp_path / "⊕Workspace"
    worktree_root = tmp_path / "workspace-order-type-guidance"
    main_root.mkdir(parents=True)
    worktree_root.mkdir(parents=True)

    (main_root / "AGENT_STARTUP.md").write_text("root startup\n", encoding="utf-8")
    (main_root / "dashboard.json").write_text(
        json.dumps({
            "project": "⊕Workspace",
            "sigil": "⊕",
            "dashboards": [{
                "id": "fr-board",
                "title": "Feature Requests",
                "type": "flask_app",
                "url": "http://localhost:7474",
                "category": "workflow",
                "icon": "📋",
            }],
        }),
        encoding="utf-8",
    )
    (worktree_root / "AGENT_STARTUP.md").write_text("worktree startup\n", encoding="utf-8")
    (worktree_root / "dashboard.json").write_text(
        json.dumps({
            "project": "⊕Workspace",
            "sigil": "⊕",
            "dashboards": [{
                "id": "fr-board",
                "title": "Feature Requests",
                "type": "flask_app",
                "url": "http://localhost:7474",
                "category": "workflow",
                "icon": "📋",
            }],
        }),
        encoding="utf-8",
    )
    (worktree_root / ".git").write_text(
        "gitdir: F:/⊕Workspace/.git/worktrees/workspace-order-type-guidance\n",
        encoding="utf-8",
    )

    with patch.object(dr, "WORKSPACE_ROOT", tmp_path):
        manifest = dr.build_manifest()

    assert len(manifest["dashboards"]) == 1
    assert manifest["dashboards"][0]["id"] == "fr-board"


def test_worktree_context_discovers_canonical_projects_without_root_patch(
    tmp_path: Path,
) -> None:
    expected_workspace_root = tmp_path / "host" / "⊕Workspace"
    worktree_root = tmp_path / "linked-worktree"
    source_root = worktree_root / "tools"
    expected_workspace_root.mkdir(parents=True)
    (expected_workspace_root / ".git" / "worktrees" / "feature").mkdir(parents=True)
    source_root.mkdir(parents=True)

    for project_name in dr.CANONICAL_PROJECT_ROOTS:
        project_root = expected_workspace_root.parent / project_name
        project_root.mkdir(exist_ok=True)
        (project_root / "AGENT_STARTUP.md").write_text("startup\n", encoding="utf-8")

    shutil.copy2(Path(dr.__file__), source_root / "dashboard_registry.py")
    (worktree_root / ".git").write_text(
        "gitdir: ../host/⊕Workspace/.git/worktrees/feature\n",
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location(
        "dashboard_registry_fake_worktree",
        source_root / "dashboard_registry.py",
    )
    assert spec is not None and spec.loader is not None
    fake_dr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fake_dr)

    projects = fake_dr.discover_projects()
    manifest = fake_dr.build_manifest()

    assert fake_dr.WORKSPACE_ROOT == expected_workspace_root
    assert {project.name for project in projects} == fake_dr.CANONICAL_PROJECT_ROOTS
    assert manifest["workspace_root"] == str(expected_workspace_root)
