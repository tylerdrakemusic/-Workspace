"""FR-20260912 child 644 (Workspace portion): every Workspace-owned Mermaid
source must satisfy its category budget through the shared budget validator.

The federation manifest records a diagram ``kind``; the budget validator keys
off :class:`DiagramCategory`. ``category_for_kind`` is the deterministic bridge
so the manifest can be validated without a hand-maintained source table. This
test is the failing contract that drives splitting the oversized architecture
sources into bounded, traceable derived views.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from diagram_budgets import (
    BUDGETS,
    DiagramCategory,
    DiagramSpec,
    Traceability,
    category_for_kind,
    measure_source,
    validate_diagram,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "diagrams" / "diagram-manifest.json"


def _manifest_records() -> list[dict]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return list(payload["diagrams"])


def _spec_for(record: dict) -> DiagramSpec:
    source_path = PROJECT_ROOT / record["path"]
    lineage = record["lineage"]
    return DiagramSpec(
        path=record["path"],
        category=category_for_kind(record["kind"]),
        metrics=measure_source(source_path),
        traceability=Traceability(
            parent=lineage["parent"],
            derived_views=tuple(lineage["derived_views"]),
        ),
        is_derived_view=lineage["parent"] is not None,
    )


def test_category_for_kind_maps_every_manifest_kind_to_a_budget() -> None:
    kinds = {record["kind"] for record in _manifest_records()}
    for kind in kinds:
        category = category_for_kind(kind)
        assert isinstance(category, DiagramCategory)
        assert category in BUDGETS


def test_category_for_kind_grounds_orientation_and_detail_rules() -> None:
    # Orientation kinds share the overview budget; implementation detail is wider.
    assert category_for_kind("architecture") is DiagramCategory.OVERVIEW
    assert category_for_kind("agent-topology") is DiagramCategory.OVERVIEW
    assert category_for_kind("architecture-detail") is DiagramCategory.DETAIL
    assert category_for_kind("database-schema") is DiagramCategory.DATABASE_SCHEMA
    assert category_for_kind("workflow") is DiagramCategory.WORKFLOW
    assert category_for_kind("technology-stack") is DiagramCategory.TECHNOLOGY_STACK


def test_category_for_kind_rejects_unknown_kind() -> None:
    with pytest.raises(KeyError):
        category_for_kind("not-a-real-kind")


def test_every_workspace_manifest_source_is_budget_compliant() -> None:
    offenders: dict[str, list[str]] = {}
    for record in _manifest_records():
        result = validate_diagram(_spec_for(record))
        if not result.is_compliant:
            offenders[record["path"]] = [f"{f.code}: {f.message}" for f in result.findings]
    assert offenders == {}, "Oversized Workspace sources: " + json.dumps(offenders, indent=2)


def test_no_workspace_manifest_source_requires_a_split() -> None:
    still_oversized = [
        record["path"]
        for record in _manifest_records()
        if validate_diagram(_spec_for(record)).split_required
    ]
    assert still_oversized == []


def test_manifest_sources_all_exist_on_disk() -> None:
    missing = [
        record["path"]
        for record in _manifest_records()
        if not (PROJECT_ROOT / record["path"]).is_file()
    ]
    assert missing == []
