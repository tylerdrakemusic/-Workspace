from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

import src.utils.database_backup as database_backup_module
from src.utils.database_backup import DatabaseBackup, LocalVolumeDestination, validate_backup
from src.utils.database_backup_scope import load_manifest
from tools.run_database_backup import ScheduledBackupResult, run_scheduled_backups


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TEST_SQLCIPHER_PRAGMAS = (
    "PRAGMA cipher_page_size=4096",
    "PRAGMA kdf_iter=256000",
    "PRAGMA cipher_hmac_algorithm=HMAC_SHA512",
)

scenarios("database_backup_publication.feature")


@dataclass
class BackupScenario:
    manifest: dict[str, Any]
    manifest_path: Path
    source_roots: dict[str, Path]
    source_paths: dict[str, Path]
    synthetic_keys: dict[str, str]
    destination_root: Path
    destination: LocalVolumeDestination
    prior_manifest: Path | None = None
    result: ScheduledBackupResult | None = None


def _create_sqlcipher_database(path: Path, key: str, key_format: str, database_id: str) -> None:
    sqlcipher3 = pytest.importorskip("sqlcipher3")
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlcipher3.connect(str(path))
    try:
        if key_format == "hex":
            connection.execute(f'PRAGMA key="x\'{key.encode().hex()}\'"')
        else:
            connection.execute(f"PRAGMA key='{key}'")
        for pragma in _TEST_SQLCIPHER_PRAGMAS:
            connection.execute(pragma)
        connection.execute("CREATE TABLE fixture (value TEXT NOT NULL)")
        connection.execute("INSERT INTO fixture VALUES (?)", (f"synthetic:{database_id}",))
        connection.commit()
    finally:
        connection.close()


def _new_backup_scenario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BackupScenario:
    manifest_path = PROJECT_ROOT / "src" / "config" / "database_backup_scope.json"
    manifest = load_manifest(manifest_path)
    source_roots: dict[str, Path] = {}
    source_paths: dict[str, Path] = {}
    synthetic_keys: dict[str, str] = {}

    for entry in manifest["databases"]:
        if not entry["backup_allowed"]:
            continue
        discovery = entry.get("discovery")
        if discovery:
            project = discovery["project"]
            root_label = {"life": "∞Life", "capital": "ΣCapital"}.get(project, project)
            local_path = (
                Path("src/data") / discovery["basename"]
                if project == "life"
                else Path("data") / discovery["basename"]
            )
        else:
            root_label, relative_path = entry["path"].split("/", 1)
            local_path = Path(relative_path)

        source_root = source_roots.setdefault(root_label, tmp_path / "sources" / root_label)
        source_path = source_root / local_path
        source_paths[entry["id"]] = source_path
        if entry.get("encryption") == "sqlcipher":
            key_env = entry["key_env"]
            key = "q" * 32 if entry.get("key_format") == "hex" else f"synthetic-{key_env.lower()}"
            synthetic_keys[key_env] = key
            monkeypatch.setenv(key_env, key)
            _create_sqlcipher_database(
                source_path, key, entry.get("key_format", "literal"), entry["id"]
            )
        else:
            source_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(source_path)
            try:
                connection.execute("CREATE TABLE fixture (value TEXT NOT NULL)")
                connection.execute(
                    "INSERT INTO fixture VALUES (?)", (f"synthetic:{entry['id']}",)
                )
                connection.commit()
            finally:
                connection.close()

    destination_root = tmp_path / "external"
    destination = LocalVolumeDestination(
        destination_root, "approved-volume", provision=True
    )
    temporary_manifest = tmp_path / "approved-manifest.json"
    temporary_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    return BackupScenario(
        manifest=manifest,
        manifest_path=temporary_manifest,
        source_roots=source_roots,
        source_paths=source_paths,
        synthetic_keys=synthetic_keys,
        destination_root=destination_root,
        destination=destination,
    )


def _run_prior_backup(case: BackupScenario) -> Path:
    result = DatabaseBackup(
        manifest=case.manifest,
        source_root=case.source_roots,
        destination=case.destination,
        expected_destination_identity="approved-volume",
        now=lambda: "2026-11-18T12:00:00Z",
    ).run()
    return result.manifest_path


def _run_scheduled_backup(case: BackupScenario) -> ScheduledBackupResult:
    return run_scheduled_backups(
        case.manifest_path,
        case.source_roots,
        case.destination_root,
        "approved-volume",
    )


@given(
    "a valid recovery generation and synthetic approved backup sources",
    target_fixture="backup_case",
)
def prior_recovery_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> BackupScenario:
    case = _new_backup_scenario(tmp_path, monkeypatch)
    case.prior_manifest = _run_prior_backup(case)
    return case


@given(
    "healthy synthetic sources for every approved manifest entry",
    target_fixture="backup_case",
)
def healthy_approved_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> BackupScenario:
    return _new_backup_scenario(tmp_path, monkeypatch)


@when("the copied workspace FR ledger SQLCipher artifact is corrupted")
def corrupt_sqlcipher_output(
    backup_case: BackupScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_copy = database_backup_module._copy_sqlcipher_database

    def copy_then_corrupt(
        source_path: Path,
        destination_path: Path,
        key_env: str,
        key_format: str = "literal",
    ) -> None:
        original_copy(source_path, destination_path, key_env, key_format=key_format)
        if destination_path.name == "fr_ledgers.db":
            destination_path.write_bytes(b"synthetic-invalid-sqlcipher-output")

    monkeypatch.setattr(database_backup_module, "_copy_sqlcipher_database", copy_then_corrupt)
    backup_case.result = _run_scheduled_backup(backup_case)


@when("a copied Workspace database is corrupted during publication")
def corrupt_published_artifact(
    backup_case: BackupScenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_replace = database_backup_module.os.replace
    generations_root = backup_case.destination_root / "generations"
    relative_path = Path("⊕Workspace/src/data/workspace.db")

    def replace_and_corrupt(
        source_path: str | os.PathLike[str], target_path: str | os.PathLike[str]
    ) -> None:
        source_file = Path(source_path)
        target_file = Path(target_path)
        if source_file.is_dir() and source_file.name.endswith(".tmp"):
            original_replace(source_file, target_file)
            (target_file / relative_path).write_bytes(b"synthetic-checksum-mismatch")
            return

        original_replace(source_file, target_file)
        try:
            relative_target = target_file.relative_to(generations_root)
        except ValueError:
            return
        if (
            target_file.name == "manifest.json"
            and relative_target.parts
            and not relative_target.parts[0].endswith(".tmp")
        ):
            (target_file.parent / relative_path).write_bytes(b"synthetic-checksum-mismatch")

    monkeypatch.setattr(database_backup_module.os, "replace", replace_and_corrupt)
    backup_case.result = _run_scheduled_backup(backup_case)


@when("the scheduled backup runner publishes a generation")
def run_complete_backup(backup_case: BackupScenario) -> None:
    backup_case.result = _run_scheduled_backup(backup_case)


@when(
    "the scheduled backup runner publishes a generation on an exFAT-like volume"
)
def run_backup_with_directory_rename_corruption(
    backup_case: BackupScenario, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_replace = database_backup_module.os.replace
    affected_paths = (
        Path("⊕Workspace/src/data/fr_ledgers.db"),
        Path("⊕Workspace/src/data/workspace.db"),
        Path("capital/financial-store"),
    )

    def replace_and_corrupt_directory_move(
        source_path: str | os.PathLike[str], target_path: str | os.PathLike[str]
    ) -> None:
        source = Path(source_path)
        target = Path(target_path)
        original_replace(source, target)
        if source.is_dir() and source.name.endswith(".tmp"):
            for relative_path in affected_paths:
                (target / relative_path).write_bytes(b"exFAT directory-rename corruption")

    monkeypatch.setattr(
        database_backup_module.os, "replace", replace_and_corrupt_directory_move
    )
    backup_case.result = _run_scheduled_backup(backup_case)


@then(
    "the backup fails without publishing success and retains the prior recovery generation"
)
def failed_backup_preserves_prior_generation(backup_case: BackupScenario) -> None:
    assert backup_case.result is not None
    assert backup_case.result.overall_status == "failed"
    assert backup_case.result.failure is not None
    assert backup_case.result.failure["error_type"] == "BackupError"
    assert backup_case.prior_manifest is not None
    assert validate_backup(backup_case.prior_manifest) is True

    generations_root = backup_case.destination_root / "generations"
    generations = sorted(path.name for path in generations_root.iterdir() if path.is_dir())
    assert generations == [backup_case.prior_manifest.parent.name]
    audit_path = backup_case.destination_root / "backup-audit.jsonl"
    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    successful = [record for record in records if record["event"] == "backup"]
    assert [record["generation"] for record in successful] == [
        backup_case.prior_manifest.parent.name
    ]
    assert any(record["event"] == "backup_attempt" for record in records)
    serialized_evidence = json.dumps(records + [backup_case.result.failure])
    for source_path in backup_case.source_paths.values():
        assert str(source_path) not in serialized_evidence
    for synthetic_key in backup_case.synthetic_keys.values():
        assert synthetic_key not in serialized_evidence
    assert "WORKSPACE_DB_KEY" not in serialized_evidence
    assert "SIGMACAPITAL_DB_KEY" not in serialized_evidence


@then(
    "every approved artifact is hash-valid and every SQLCipher artifact passes integrity checks"
)
def complete_manifest_is_verified(backup_case: BackupScenario) -> None:
    sqlcipher3 = pytest.importorskip("sqlcipher3")
    assert backup_case.result is not None
    assert backup_case.result.overall_status == "succeeded"

    generations_root = backup_case.destination_root / "generations"
    manifests = list(generations_root.glob("*/manifest.json"))
    assert len(manifests) == 1
    manifest_path = manifests[0]
    assert validate_backup(manifest_path) is True
    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    approved_paths = {
        entry["path"] for entry in backup_case.manifest["databases"] if entry["backup_allowed"]
    }
    assert {entry["relative_path"] for entry in metadata["files"]} == approved_paths

    checked_ids: set[str] = set()
    for entry in backup_case.manifest["databases"]:
        if not entry["backup_allowed"] or entry.get("encryption") != "sqlcipher":
            continue
        output_path = manifest_path.parent / entry["path"]
        key = backup_case.synthetic_keys[entry["key_env"]]
        connection = sqlcipher3.connect(str(output_path))
        try:
            if entry.get("key_format") == "hex":
                connection.execute(f'PRAGMA key="x\'{key.encode().hex()}\'"')
            else:
                connection.execute(f"PRAGMA key='{key}'")
            for pragma in _TEST_SQLCIPHER_PRAGMAS:
                connection.execute(pragma)
            cipher_results = connection.execute("PRAGMA cipher_integrity_check").fetchall()
            assert cipher_results in ([], [("ok",)])
            assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            checked_ids.add(entry["id"])
        finally:
            connection.close()

    assert checked_ids == {
        entry["id"]
        for entry in backup_case.manifest["databases"]
        if entry["backup_allowed"] and entry.get("encryption") == "sqlcipher"
    }
    assert "life-infinitelife" in checked_ids
    assert {"workspace-fr-ledgers", "workspace", "capital-sigmacapital"}.issubset(
        checked_ids
    )