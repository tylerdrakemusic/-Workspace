from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.database_backup_scope import discover_databases, load_manifest, validate_manifest
from tools.register_database_backup_task import build_task_spec
import tools.run_database_backup as backup_runner


def test_scheduler_requires_a_configured_interpreter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKSPACE_BACKUP_PYTHON", raising=False)

    with pytest.raises(RuntimeError, match="configured Python interpreter"):
        build_task_spec(Path("F:/workspace"))


def test_scheduler_uses_configured_interpreter_without_secret_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    interpreter = tmp_path / "python.exe"
    interpreter.write_bytes(b"test interpreter")
    monkeypatch.setenv("WORKSPACE_BACKUP_PYTHON", str(interpreter))

    spec = build_task_spec(tmp_path)

    assert spec.python_path == interpreter
    assert str(interpreter) not in spec.arguments
    assert all("KEY" not in argument for argument in spec.arguments)


def test_approved_scheduler_project_root_action_maps_all_display_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    interpreter = tmp_path / "python.exe"
    interpreter.write_bytes(b"test interpreter")
    monkeypatch.setenv("WORKSPACE_BACKUP_PYTHON", str(interpreter))
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    approved_roots = {
        "∞Life": ("life", "infinitelife.db"),
        "❤Music": ("music", "heartmusic.db"),
        "⟨ψ⟩Quantum": ("quantum", "quantumpsi.db"),
        "👁AI-Manifest": ("manifest", "manifest_todos.db"),
        "⊕Workspace": ("workspace", "workspace.db"),
        "ΣCapital": ("capital", "sigmacapital.db"),
    }
    for label, (_, basename) in approved_roots.items():
        root = workspace_root if label == "⊕Workspace" else tmp_path / label
        database_path = root / "src" / "data" / basename
        database_path.parent.mkdir(parents=True)
        database_path.write_bytes(b"temporary test database")

    spec = build_task_spec(workspace_root, python_path=interpreter)
    encoded_roots = spec.arguments[spec.arguments.index("-ProjectRoot") + 1]
    project_roots = dict(
        backup_runner._parse_project_root(value)
        for value in encoded_roots.split(",")
    )

    discovered = discover_databases(project_roots)

    assert {entry["path"].split("/", 1)[0] for entry in discovered} == {
        "life",
        "❤Music",
        "⟨ψ⟩Quantum",
        "👁AI-Manifest",
        "⊕Workspace",
        "capital",
    }


def test_scheduled_life_root_action_resolves_redacted_manifest_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    interpreter = tmp_path / "python.exe"
    interpreter.write_bytes(b"test interpreter")
    monkeypatch.setenv("WORKSPACE_BACKUP_PYTHON", str(interpreter))
    monkeypatch.setenv("WORKSPACE_BACKUP_MANIFEST_KEY", "temporary-manifest-key")
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    life_root = tmp_path / "∞Life"
    life_source = life_root / "src" / "data" / "infinitelife.db"
    life_source.parent.mkdir(parents=True)
    life_source.write_bytes(b"temporary SQLCipher fixture")

    spec = build_task_spec(workspace_root, python_path=interpreter)
    encoded_roots = spec.arguments[spec.arguments.index("-ProjectRoot") + 1]
    project_roots = dict(
        backup_runner._parse_project_root(value)
        for value in encoded_roots.split(",")
    )
    project_roots = {
        label: (life_root if label == "∞Life" else tmp_path / label)
        for label in project_roots
    }
    for label, basenames in {
        "❤Music": ("heartmusic.db",),
        "⟨ψ⟩Quantum": ("quantumpsi.db",),
        "👁AI-Manifest": ("manifest_todos.db",),
        "⊕Workspace": ("agent_perf.db", "fr_ledgers.db", "manifest_todos.db", "workspace.db"),
        "ΣCapital": ("sigmacapital.db",),
    }.items():
        for basename in basenames:
            source = project_roots[label] / "src" / "data" / basename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"temporary SQLCipher fixture")
    volume = tmp_path / "backup-volume"
    volume.mkdir()
    (volume / ".backup-volume-identity").write_text("temporary-volume\n", encoding="utf-8")
    manifest_path = Path(__file__).parents[1] / "src" / "config" / "database_backup_scope.json"

    result = backup_runner.run_scheduled_backups(
        manifest_path=manifest_path,
        project_roots=project_roots,
        volume_root=volume,
        volume_identity="temporary-volume",
    )

    assert result.overall_status == "succeeded"
    assert result.project_outcomes["∞Life"].status == "succeeded"


def test_scope_contains_all_six_canonical_project_roots_and_redacted_capital_entry() -> None:
    manifest_path = Path(__file__).parents[1] / "src" / "config" / "database_backup_scope.json"
    manifest = load_manifest(manifest_path)
    allowed = {
        entry["id"]: entry for entry in manifest["databases"] if entry["backup_allowed"]
    }

    assert set(allowed) >= {
        "life-infinitelife",
        "music-heartmusic",
        "quantum-quantumpsi",
        "manifest-todos",
        "workspace-agent-perf",
        "workspace-fr-ledgers",
        "workspace-manifest-todos",
        "workspace",
        "capital-sigmacapital",
    }
    capital = allowed["capital-sigmacapital"]
    assert capital["path"] == "capital/financial-store"
    assert capital["discovery"] == {"project": "capital", "basename": "sigmacapital.db"}
    assert capital["key_env"] == "SIGMACAPITAL_DB_KEY"
    assert "account" not in json.dumps(capital).lower()


@pytest.mark.parametrize("classification", ["derived", "legacy", "temporary", "unknown"])
def test_denied_database_classifications_are_not_backup_sources(classification: str) -> None:
    manifest_path = Path(__file__).parents[1] / "src" / "config" / "database_backup_scope.json"
    manifest = load_manifest(manifest_path)
    denied = [
        entry for entry in manifest["databases"]
        if entry["classification"] == classification
    ]

    assert denied
    assert all(entry["backup_allowed"] is False for entry in denied)


def test_capital_scope_requires_explicit_approval() -> None:
    manifest_path = Path(__file__).parents[1] / "src" / "config" / "database_backup_scope.json"
    manifest = load_manifest(manifest_path)
    capital = next(entry for entry in manifest["databases"] if entry["id"] == "capital-sigmacapital")
    unapproved = {**manifest, "policy_status": "reviewed", "databases": [{**capital, "backup_allowed": True}]}

    with pytest.raises(ValueError, match="Capital database backup requires governed approval"):
        validate_manifest(unapproved)


def test_scheduled_backup_reports_each_project_and_overall_failure(tmp_path: Path) -> None:
    run_scheduled_backups = getattr(backup_runner, "run_scheduled_backups", None)
    assert callable(run_scheduled_backups)
    result = run_scheduled_backups(
        manifest_path=tmp_path / "manifest.json",
        project_roots={"workspace": tmp_path},
        volume_root=tmp_path / "missing-volume",
        volume_identity="trusted",
    )

    assert result.overall_status == "failed"
    assert result.project_outcomes["workspace"].status == "failed"
    assert result.failure_reason