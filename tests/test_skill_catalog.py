from copy import deepcopy
from pathlib import Path

import pytest

from skill_catalog import load_catalog, validate_catalog


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def test_catalog_covers_local_skills_and_records_duplicate_dispositions() -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")

    assert validate_catalog(catalog, WORKSPACE_ROOT / ".github" / "skills") == []
    assert {entry["name"] for entry in catalog["skills"]} == {
        path.parent.name
        for path in (WORKSPACE_ROOT / ".github" / "skills").glob("*/SKILL.md")
    }

    entries = {entry["name"]: entry for entry in catalog["skills"]}
    assert entries["perfect-td"]["disposition"] == "retain-generic"
    assert entries["perfect-scoped-td"]["disposition"] == "retain-workspace-scoped"
    assert entries["tdd"]["disposition"] == "retain-reference"
    assert entries["test-driven-development"]["disposition"] == "retain-operational-gate"


def test_catalog_rejects_canonical_and_external_sync_collisions() -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["skills"][1]["canonical_id"] = invalid_catalog["skills"][0]["canonical_id"]
    invalid_catalog["external_sync"] = [
        {"source": "upstream-a", "target": "quality.code-review"},
        {"source": "upstream-b", "target": "quality.code-review"},
    ]

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert "duplicate canonical_id: workspace.before-building" in errors
    assert "external synchronization targets must be unique" in errors


def test_catalog_rejects_malformed_required_scalar_values() -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["skills"][0]["invocation_mode"] = None
    invalid_catalog["skills"][1]["audience"] = 42
    invalid_catalog["skills"][2]["provenance"] = ""

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert "skills[0].invocation_mode must be a non-empty string" in errors
    assert "skills[1].audience must be a non-empty string" in errors
    assert "skills[2].provenance must be a non-empty string" in errors


def test_catalog_rejects_duplicate_external_sync_sources_even_with_different_targets() -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["external_sync"] = [
        {"source": "upstream", "target": "quality.code-review"},
        {"source": "upstream", "target": "quality.doubt-driven"},
    ]

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert "duplicate external synchronization source: upstream" in errors


def test_catalog_rejects_malformed_external_sync_entries_without_raising() -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["external_sync"] = [None, "not-a-mapping"]

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert "external_sync[0] must be an object" in errors
    assert "external_sync[1] must be an object" in errors


@pytest.mark.parametrize("external_sync", [{}, "not-a-list", 42, None])
def test_catalog_rejects_non_list_external_sync_without_raising(
    external_sync: object,
) -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["external_sync"] = external_sync

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert "external_sync must be a list" in errors


@pytest.mark.parametrize(
    ("mapping", "expected_errors"),
    [
        ({}, ["external_sync[0].source must be a non-empty string", "external_sync[0].target must be a non-empty string"]),
        ({"source": "upstream"}, ["external_sync[0].target must be a non-empty string"]),
        ({"target": "quality.code-review"}, ["external_sync[0].source must be a non-empty string"]),
        ({"source": None, "target": None}, ["external_sync[0].source must be a non-empty string", "external_sync[0].target must be a non-empty string"]),
        ({"source": "", "target": ""}, ["external_sync[0].source must be a non-empty string", "external_sync[0].target must be a non-empty string"]),
        ({"source": 42, "target": ["quality.code-review"]}, ["external_sync[0].source must be a non-empty string", "external_sync[0].target must be a non-empty string"]),
    ],
)
def test_catalog_rejects_malformed_external_sync_mappings_without_raising(
    mapping: dict[str, object], expected_errors: list[str]
) -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["external_sync"] = [mapping]

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert all(expected_error in errors for expected_error in expected_errors)


def test_catalog_rejects_duplicate_external_sync_mappings() -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["external_sync"] = [
        {"source": "upstream", "target": "quality.code-review"},
        {"source": "upstream", "target": "quality.code-review"},
    ]

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert "duplicate external synchronization mapping" in errors


def test_catalog_rejects_duplicate_skill_names_with_different_canonical_ids() -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["skills"][1]["name"] = invalid_catalog["skills"][0]["name"]
    invalid_catalog["skills"][1]["canonical_id"] = "different-canonical-id"
    duplicate_name = invalid_catalog["skills"][0]["name"]

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert f"duplicate skill name: {duplicate_name}" in errors


def test_catalog_identifies_missing_local_skill_entry() -> None:
    catalog = load_catalog(WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json")
    invalid_catalog = deepcopy(catalog)
    invalid_catalog["skills"] = [
        entry for entry in invalid_catalog["skills"] if entry["name"] != "wayfinder"
    ]

    errors = validate_catalog(invalid_catalog, WORKSPACE_ROOT / ".github" / "skills")

    assert "catalog entry missing local skill directory: wayfinder" in errors