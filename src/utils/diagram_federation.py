"""Federated discovery contract for repository-owned Mermaid diagrams."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_RELATIVE_PATH = Path("diagrams") / "diagram-manifest.json"
SCHEMA_VERSION = 1
REPOSITORIES = ("workspace", "life", "music", "quantum", "manifest", "capital")
REPOSITORY_ROOT_NAMES = {
    "workspace": "⊕Workspace",
    "life": "∞Life",
    "music": "❤Music",
    "quantum": "⟨ψ⟩Quantum",
    "manifest": "👁AI-Manifest",
    "capital": "ΣCapital",
}
_REQUIRED_DIAGRAM_FIELDS = {
    "path",
    "kind",
    "renderer_risk",
    "fallback_risk",
    "split_required",
    "lineage",
}


@dataclass(frozen=True)
class DiagramLineage:
    parent: str | None
    derived_views: tuple[str, ...]


@dataclass(frozen=True)
class DiagramRecord:
    path: str
    kind: str
    renderer_risk: str
    fallback_risk: str
    split_required: bool
    lineage: DiagramLineage


@dataclass(frozen=True)
class DiagramManifest:
    repository: str
    root: Path
    schema_version: int
    diagrams: tuple[DiagramRecord, ...]


def _lineage(value: Any, manifest_path: Path) -> DiagramLineage:
    if not isinstance(value, dict):
        raise ValueError(f"{manifest_path}: lineage must be an object")
    parent = value.get("parent")
    derived_views = value.get("derived_views")
    if parent is not None and not isinstance(parent, str):
        raise ValueError(f"{manifest_path}: lineage.parent must be a string or null")
    if not isinstance(derived_views, list) or not all(
        isinstance(path, str) for path in derived_views
    ):
        raise ValueError(f"{manifest_path}: lineage.derived_views must be a string list")
    return DiagramLineage(parent=parent, derived_views=tuple(derived_views))


def _load_manifest(manifest_path: Path) -> DiagramManifest:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{manifest_path}: invalid JSON manifest") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{manifest_path}: manifest must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{manifest_path}: unsupported schema version")
    repository = payload.get("repository")
    if not isinstance(repository, str) or not repository:
        raise ValueError(f"{manifest_path}: repository is required")
    diagrams = payload.get("diagrams")
    if not isinstance(diagrams, list):
        raise ValueError(f"{manifest_path}: diagrams must be a list")
    records = []
    for diagram in diagrams:
        if not isinstance(diagram, dict) or not _REQUIRED_DIAGRAM_FIELDS <= diagram.keys():
            raise ValueError(f"{manifest_path}: diagram record is incomplete")
        if not all(isinstance(diagram[field], str) for field in ("path", "kind", "renderer_risk", "fallback_risk")):
            raise ValueError(f"{manifest_path}: diagram text fields must be strings")
        if not isinstance(diagram["split_required"], bool):
            raise ValueError(f"{manifest_path}: split_required must be boolean")
        records.append(
            DiagramRecord(
                path=diagram["path"],
                kind=diagram["kind"],
                renderer_risk=diagram["renderer_risk"],
                fallback_risk=diagram["fallback_risk"],
                split_required=diagram["split_required"],
                lineage=_lineage(diagram["lineage"], manifest_path),
            )
        )
    return DiagramManifest(
        repository=repository,
        root=manifest_path.parent.parent,
        schema_version=SCHEMA_VERSION,
        diagrams=tuple(records),
    )


def discover_diagram_manifests(workspace_root: Path) -> tuple[DiagramManifest, ...]:
    """Discover one owned diagram manifest per direct repository root."""
    manifests = []
    for repository in REPOSITORIES:
        root_names = (REPOSITORY_ROOT_NAMES[repository], repository)
        for root_name in root_names:
            root = workspace_root / root_name
            manifest_path = root / MANIFEST_RELATIVE_PATH
            if ".worktrees" in manifest_path.parts or not manifest_path.is_file():
                continue
            manifest = _load_manifest(manifest_path)
            if manifest.repository != repository:
                raise ValueError(
                    f"{manifest_path}: repository {manifest.repository!r} does not match {repository!r}"
                )
            manifests.append(manifest)
            break
    return tuple(manifests)


def discover_diagram_sources(
    workspace_root: Path,
    local_root: Path | None = None,
) -> tuple[Path, ...]:
    """Resolve federated manifest records to existing Mermaid source files."""
    manifests = discover_diagram_manifests(workspace_root)
    sources = [
        manifest.root / record.path
        for manifest in manifests
        for record in manifest.diagrams
        if (manifest.root / record.path).is_file()
    ]
    if sources:
        return tuple(sorted(sources))
    if local_root is None:
        local_root = workspace_root / "diagrams"
    return tuple(sorted(local_root.glob("*.mmd")))