from __future__ import annotations

import json
from pathlib import Path

from src.utils.diagram_federation import discover_diagram_manifests
from tools.gen_diagram_gallery import _project_group
from src.utils.diagram_budgets import (
    DiagramCategory,
    DiagramMetrics,
    DiagramSpec,
    Traceability,
    validate_diagram,
)


def _write_manifest(root: Path, repository: str) -> None:
    (root / "diagrams").mkdir(parents=True)
    (root / "diagrams" / "diagram-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repository": repository,
                "diagrams": [
                    {
                        "path": "diagrams/architecture.mmd",
                        "kind": "architecture",
                        "renderer_risk": "low",
                        "fallback_risk": "low",
                        "split_required": False,
                        "lineage": {"parent": None, "derived_views": []},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_discovery_aggregates_six_owned_manifests_and_excludes_worktrees(tmp_path: Path) -> None:
    repositories = ("workspace", "life", "music", "quantum", "manifest", "capital")
    roots = []
    for repository in repositories:
        root = tmp_path / repository
        _write_manifest(root, repository)
        roots.append(root)

    worktree = tmp_path / "workspace" / ".worktrees" / "feature"
    _write_manifest(worktree, "feature")

    discovered = discover_diagram_manifests(tmp_path)

    assert [manifest.repository for manifest in discovered] == list(repositories)
    assert all(manifest.root in roots for manifest in discovered)


def test_discovery_uses_sibling_repository_roots(tmp_path: Path) -> None:
    repository_roots = {
        "workspace": "⊕Workspace",
        "life": "∞Life",
        "music": "❤Music",
        "quantum": "⟨ψ⟩Quantum",
        "manifest": "👁AI-Manifest",
        "capital": "ΣCapital",
    }
    roots = []
    for repository, directory_name in repository_roots.items():
        root = tmp_path / directory_name
        _write_manifest(root, repository)
        roots.append(root)

    discovered = discover_diagram_manifests(tmp_path)

    assert [manifest.repository for manifest in discovered] == list(repository_roots)
    assert [manifest.root for manifest in discovered] == roots


def test_workspace_manifest_enumerates_workspace_owned_sources() -> None:
    project_root = Path(__file__).resolve().parent.parent
    manifest = json.loads(
        (project_root / "diagrams" / "diagram-manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["repository"] == "workspace"
    assert {diagram["path"] for diagram in manifest["diagrams"]} == {
        "diagrams/workspace-agent-topology.mmd",
        "diagrams/workspace-architecture-detail.mmd",
        "diagrams/workspace-architecture.mmd",
        "diagrams/workspace-db-schema.mmd",
        "diagrams/workspace-derived-backup-and-coordination.mmd",
        "diagrams/workspace-derived-decision-metadata-implementation.mmd",
        "diagrams/workspace-derived-services.mmd",
        "diagrams/workspace-fr-flow.mmd",
        "diagrams/workspace-integrations.mmd",
        "diagrams/workspace-scheduler-architecture.mmd",
        "diagrams/workspace-tech-stack.mmd",
    }


def test_manifest_contract_does_not_measure_utf8_bytes_or_characters(tmp_path: Path) -> None:
    root = tmp_path / "music"
    _write_manifest(root, "music")

    manifest = discover_diagram_manifests(tmp_path)[0]

    assert manifest.diagrams[0].path == "diagrams/architecture.mmd"
    assert not hasattr(manifest.diagrams[0], "utf8_bytes")
    assert not hasattr(manifest.diagrams[0], "utf8_characters")


def test_gallery_groups_sources_by_manifest_repository_when_root_is_a_worktree(tmp_path: Path) -> None:
    worktree = tmp_path / "feature-FR-20260901-mermaid-diagram-repository-ownership"
    source = worktree / "diagrams" / "capital-architecture.mmd"
    source.parent.mkdir(parents=True)
    source.write_text("graph LR\n A --> B\n", encoding="utf-8")

    assert _project_group(source, "capital") == "Σ Capital"


def test_validation_does_not_enforce_utf8_dimensions() -> None:
    result = validate_diagram(
        DiagramSpec(
            path="diagrams/architecture.mmd",
            category=DiagramCategory.OVERVIEW,
            metrics=DiagramMetrics(
                utf8_characters=100_000,
                utf8_bytes=100_000,
                nodes=1,
                edges=1,
                renderer_url_risk="low",
                fallback_risk="low",
            ),
            traceability=Traceability(parent=None, derived_views=()),
        )
    )

    assert result.is_compliant