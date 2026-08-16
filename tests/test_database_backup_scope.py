from __future__ import annotations

import pytest
from pathlib import Path

from src.utils.database_backup_scope import (
    discover_databases,
    load_manifest,
    render_report,
    validate_manifest,
)


def _manifest(databases: list[dict[str, object]], **overrides: object) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": 1,
        "fr": "FR-20260815-workspace-database-backup-scope",
        "policy_status": "reviewed",
        "purpose": "Inventory authoritative workspace databases before backup implementation.",
        "content_boundary": "Path and policy metadata only.",
        "classifications": [
            "canonical",
            "coordination",
            "derived",
            "temporary",
            "legacy",
            "unknown",
            "approval-required",
        ],
        "databases": databases,
        "exclusions": [],
        "not_implemented": ["upload"],
        "separate_todos": [],
    }
    manifest.update(overrides)
    return manifest


def _database(**overrides: object) -> dict[str, object]:
    database: dict[str, object] = {
        "id": "workspace-example",
        "path": "src/data/example.db",
        "classification": "canonical",
        "backup_allowed": True,
        "reason": "Authoritative application database.",
    }
    database.update(overrides)
    return database


def test_validate_manifest_rejects_unclassified_database() -> None:
    manifest = _manifest([_database(classification=None)])

    with pytest.raises(ValueError, match="classification"):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("path", "C:/workspace/example.db", "relative"),
        ("path", "../outside.db", "relative"),
        ("path", "src/../outside.db", "relative"),
        ("backup_allowed", "true", "boolean"),
        ("id", None, "id"),
        ("reason", None, "reason"),
    ],
)
def test_validate_manifest_rejects_malformed_database_entry(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_manifest(_manifest([_database(**{field: value})]))


@pytest.mark.parametrize("path", ["C:workspace/example.db", "volume:example.db"])
def test_validate_manifest_rejects_drive_relative_and_colon_paths(path: str) -> None:
    with pytest.raises(ValueError, match="relative"):
        validate_manifest(_manifest([_database(path=path)]))


def test_validate_manifest_rejects_control_character_paths() -> None:
    with pytest.raises(ValueError, match="relative"):
        validate_manifest(_manifest([_database(path="src/data/example\x00.db")]))


def test_validate_manifest_rejects_unknown_root_keys() -> None:
    with pytest.raises(ValueError, match="unknown manifest fields"):
        validate_manifest(_manifest([_database()], unexpected=True))


@pytest.mark.parametrize("field", ["not_implemented", "separate_todos"])
@pytest.mark.parametrize("value", [[{}], [1], [""], ["valid", 2]])
def test_validate_manifest_rejects_malformed_root_metadata_entries(
    field: str, value: list[object]
) -> None:
    with pytest.raises(ValueError, match=field):
        validate_manifest(_manifest([_database()], **{field: value}))


def test_validate_manifest_rejects_unknown_database_entry_keys() -> None:
    with pytest.raises(ValueError, match="unknown database fields"):
        validate_manifest(_manifest([_database(unexpected=True)]))


@pytest.mark.parametrize(
    "exclusions",
    [
        [{}],
        [{"pattern": "**/*.db"}],
        [{"reason": "not enough"}],
        [{"pattern": 1, "reason": "bad"}],
    ],
)
def test_validate_manifest_rejects_malformed_exclusions(
    exclusions: list[dict[str, object]],
) -> None:
    with pytest.raises(ValueError, match="exclusion"):
        validate_manifest(_manifest([_database()], exclusions=exclusions))


def test_validate_manifest_rejects_missing_required_boolean_fields() -> None:
    database = _database()
    del database["backup_allowed"]
    with pytest.raises(ValueError, match="missing required fields"):
        validate_manifest(_manifest([database]))


@pytest.mark.parametrize(
    "missing_field", ["id", "path", "classification", "backup_allowed", "reason"]
)
def test_validate_manifest_rejects_missing_database_entry_field(
    missing_field: str,
) -> None:
    database = _database()
    del database[missing_field]

    with pytest.raises(ValueError, match="missing required fields"):
        validate_manifest(_manifest([database]))


def test_validate_manifest_rejects_duplicate_database_ids() -> None:
    with pytest.raises(ValueError, match="duplicate database id"):
        validate_manifest(
            _manifest([_database(), _database(path="src/data/other.db")])
        )


def test_validate_manifest_rejects_duplicate_database_paths() -> None:
    with pytest.raises(ValueError, match="duplicate database path"):
        validate_manifest(
            _manifest([_database(), _database(id="other")])
        )


@pytest.mark.parametrize(
    "missing_field",
    [
        "schema_version",
        "fr",
        "policy_status",
        "purpose",
        "content_boundary",
        "classifications",
        "databases",
        "exclusions",
        "not_implemented",
        "separate_todos",
    ],
)
def test_validate_manifest_rejects_missing_required_root_field(missing_field: str) -> None:
    manifest = _manifest([_database()])
    del manifest[missing_field]

    with pytest.raises(ValueError, match="required"):
        validate_manifest(manifest)


def test_validate_manifest_rejects_incomplete_classification_taxonomy() -> None:
    with pytest.raises(ValueError, match="complete taxonomy"):
        validate_manifest(_manifest([_database()], classifications=["canonical"]))


def test_validate_manifest_rejects_unhashable_classification_values() -> None:
    with pytest.raises(ValueError, match="complete taxonomy"):
        validate_manifest(_manifest([_database()], classifications=[{}]))


def test_validate_manifest_rejects_unhashable_database_classification() -> None:
    with pytest.raises(ValueError, match="invalid classification"):
        validate_manifest(_manifest([_database(classification={})]))


def test_discover_databases_excludes_transient_directories(tmp_path) -> None:
    (tmp_path / "src" / "data").mkdir(parents=True)
    (tmp_path / ".venv").mkdir()
    (tmp_path / "output").mkdir()
    (tmp_path / "src" / "data" / "canonical.sqlite3").touch()
    (tmp_path / ".venv" / "ignored.db").touch()
    (tmp_path / "output" / "generated.db").touch()
    (tmp_path / "backups").mkdir()
    (tmp_path / "backups" / "existing.db").touch()
    (tmp_path / "tmp_debug.db").touch()

    discovered = discover_databases([tmp_path])

    assert [entry["path"] for entry in discovered] == [
        "src/data/canonical.sqlite3"
    ]


def test_discover_databases_rejects_duplicate_project_basename_keys(tmp_path) -> None:
    (tmp_path / "first").mkdir()
    (tmp_path / "second").mkdir()
    (tmp_path / "first" / "workspace.db").touch()
    (tmp_path / "second" / "workspace.db").touch()

    with pytest.raises(ValueError, match="discovery collision"):
        discover_databases({"workspace": tmp_path})


def test_discover_databases_accepts_unique_project_basename_keys(tmp_path) -> None:
    (tmp_path / "first").mkdir()
    (tmp_path / "second").mkdir()
    (tmp_path / "first" / "workspace.db").touch()
    (tmp_path / "second" / "other.sqlite3").touch()

    discovered = discover_databases({"workspace": tmp_path})

    assert [entry["path"] for entry in discovered] == [
        "workspace/first/workspace.db",
        "workspace/second/other.sqlite3",
    ]


def test_validate_manifest_rejects_unregistered_discovered_database() -> None:
    manifest = _manifest([_database()])

    with pytest.raises(ValueError, match="unregistered"):
        validate_manifest(manifest, discovered_paths={"src/data/other.db"})


@pytest.mark.parametrize("locator", ["life/health-store", "capital/financial-store"])
def test_validate_manifest_default_denies_sensitive_databases(locator: str) -> None:
    manifest = _manifest(
        [_database(id="sensitive", path=locator, classification="approval-required", backup_allowed=True)]
    )

    with pytest.raises(ValueError, match="default-denied"):
        validate_manifest(manifest)


def test_render_report_is_derived_from_manifest_entries() -> None:
    manifest = _manifest(
        [_database(
            id="life-health",
            path="life/health-store",
            discovery={"project": "life", "basename": "infinitelife.db"},
            classification="approval-required",
            backup_allowed=False,
            reason="Health and genomic store; default-denied.",
        )],
        exclusions=[
            {"pattern": "**/.venv/**", "reason": "Virtual environments."}
        ],
    )

    report = render_report(manifest)

    assert "life-health" in report
    assert "approval-required" in report
    assert "Health and genomic store" in report
    assert "**/.venv/**" in report


def test_validate_manifest_matches_local_sensitive_candidate_by_safe_discovery_key() -> None:
    manifest = _manifest(
        [_database(
            id="life-health",
            path="life/health-store",
            discovery={"project": "life", "basename": "infinitelife.db"},
            classification="approval-required",
            backup_allowed=False,
            reason="Health and genomic store; default-denied.",
        )]
    )

    validate_manifest(
        manifest,
        discovered_paths={"/".join(["life", "src", "data", "infinitelife.db"])},
    )


def test_render_report_does_not_require_or_emit_local_sensitive_path() -> None:
    manifest = _manifest(
        [_database(
            id="life-health",
            path="life/health-store",
            discovery={"project": "life", "basename": "infinitelife.db"},
            classification="approval-required",
            backup_allowed=False,
            reason="Health and genomic store; default-denied.",
        )]
    )

    report = render_report(manifest)

    assert "life/health-store" in report
    assert "/".join(["life", "src", "data", "infinitelife.db"]) not in report


def test_committed_manifest_registers_every_allowed_database() -> None:
    worktree = Path(__file__).resolve().parent.parent
    manifest = load_manifest(worktree / "src" / "config" / "database_backup_scope.json")

    assert manifest["fr"] == "FR-20260815-workspace-database-backup-scope"
    assert all(entry["classification"] for entry in manifest["databases"])


def test_scheduler_registration_uses_canonical_music_project_root() -> None:
    from tools.register_database_backup_task import build_task_spec

    workspace_root = Path(__file__).resolve().parents[1]
    resolved_root = workspace_root.resolve()
    root_parts = [part.casefold() for part in resolved_root.parts]
    if ".worktrees" in root_parts:
        worktrees_index = root_parts.index(".worktrees")
        repository_root = Path(*resolved_root.parts[:worktrees_index])
    else:
        repository_root = resolved_root
    task = build_task_spec(workspace_root, Path("C:/G/python.exe"))

    project_root_argument = task.arguments[task.arguments.index("-ProjectRoot") + 1]
    entries = dict(item.split("=", 1) for item in project_root_argument.split(","))

    assert entries["❤Music"] == str(repository_root.parent / "❤Music")
    assert ".worktrees" not in entries["❤Music"]