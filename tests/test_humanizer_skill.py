from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
import sys
import subprocess

import pytest

from skill_catalog import load_catalog, validate_catalog


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
HUMANIZER_PATH = WORKSPACE_ROOT / ".github" / "skills" / "humanizer" / "SKILL.md"
EXPECTED_COMMIT = "e2e92e7b4b8229253ed5c8e81dc65463fdeddda5"
EXPECTED_SHA256 = "14fc8a965b6e0a8dc100ba4dffeab55cb94bbac112abbde7e014d5c15a35c202"

sys.path.insert(0, str(WORKSPACE_ROOT / ".github" / "!!☾⛧security"))

import update_manifest


def test_humanizer_is_cataloged_with_pinned_provenance_and_routing_boundary() -> None:
    catalog_path = WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json"
    catalog = load_catalog(catalog_path)
    entries = {entry["name"]: entry for entry in catalog["skills"]}
    entry = entries["humanizer"]

    assert validate_catalog(catalog, catalog_path.parent) == []
    assert entry["invocation_mode"] == "model-invoked"
    assert entry["audience"] == "agnostic/public candidate"
    assert entry["canonical_id"] == "writing.humanizer"
    assert entry["disposition"] == "retain-external-provenance"
    assert entry["overlap_candidates"] == [
        "documentation-and-adrs",
        "teach",
        "writing-for-agents",
    ]
    assert entry["provenance"] == (
        "external-source; repository=https://github.com/blader/humanizer; "
        f"commit={EXPECTED_COMMIT}; sha256={EXPECTED_SHA256}; license=MIT; version=2.11.2"
    )
    assert entry["provenance_details"] == {
        "repository": "https://github.com/blader/humanizer",
        "commit": EXPECTED_COMMIT,
        "sha256": EXPECTED_SHA256,
        "license": "MIT",
        "version": "2.11.2",
    }
    assert "human-facing UI strings/copy only" in catalog["routing_boundaries"]["humanizer"]
    for excluded in (
        "code",
        "data",
        "YAML/frontmatter",
        "link targets",
        "localization keys",
        "accessibility semantics",
        "technical/reference prose",
        "agent-facing docs",
        "product logic",
    ):
        assert excluded in catalog["routing_boundaries"]["humanizer"]


def test_humanizer_source_is_byte_identical_to_declared_sha256() -> None:
    source_bytes = HUMANIZER_PATH.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(source_bytes).hexdigest()
    catalog = json.loads(
        (WORKSPACE_ROOT / ".github" / "skills" / "skill-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    entry = next(item for item in catalog["skills"] if item["name"] == "humanizer")

    assert digest == entry["provenance_details"]["sha256"]


def test_humanizer_sync_entry_is_immutable_and_does_not_enable_protected_overwrite() -> None:
    config = json.loads(
        (WORKSPACE_ROOT / "tools" / "skill-sync-config.json").read_text(encoding="utf-8")
    )
    mapping = next(repo for repo in config["repos"] if repo["name"] == "humanizer")

    assert mapping["remote"] == "https://github.com/blader/humanizer"
    assert mapping["pinned_commit"] == EXPECTED_COMMIT
    assert mapping["source_path"] == "SKILL.md"
    assert mapping["skills"] == ["humanizer"]
    assert mapping["provenance"] == "external-source"
    assert mapping["source_policy"] == "optional"
    assert mapping["protected_overwrite"] is False


def test_pinned_source_validation_detects_revision_drift() -> None:
    head = subprocess.run(
        ["git", "-C", str(WORKSPACE_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert update_manifest.validate_pinned_source(WORKSPACE_ROOT, head) is True
    assert update_manifest.validate_pinned_source(WORKSPACE_ROOT, "0" * 40) is False


def _run_sync_script(config_path: Path, manifest_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(WORKSPACE_ROOT / "tools" / "sync-skills.ps1"),
            "-ApproveProtectedSync",
            "-ConfigPath",
            str(config_path),
            "-ManifestPath",
            str(manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _write_pinned_sync_fixture(
    tmp_path: Path, *, expected_hash: str
) -> tuple[Path, Path, Path, str]:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "SKILL.md"
    source_file.write_text("pinned content\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source_root), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(source_root), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(source_root), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(source_root), "add", "SKILL.md"], check=True)
    subprocess.run(["git", "-C", str(source_root), "commit", "-m", "pinned"], check=True, capture_output=True)
    pinned_commit = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_file.write_text("drifted HEAD content\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source_root), "add", "SKILL.md"], check=True)
    subprocess.run(["git", "-C", str(source_root), "commit", "-m", "drift"], check=True, capture_output=True)

    destination = tmp_path / "destination"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"files": {}}), encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace_root": {"relative": "."},
                "destination": str(destination),
                "log_file": str(tmp_path / "sync.log"),
                "repos": [
                    {
                        "name": "local-pinned",
                        "path": str(source_root),
                        "remote": None,
                        "skill_root": ".",
                        "source_path": "SKILL.md",
                        "provenance": "external-source",
                        "source_policy": "required",
                        "pinned_commit": pinned_commit,
                        "sha256": expected_hash,
                        "skills": ["humanizer"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return config_path, manifest_path, destination / "humanizer" / "SKILL.md", pinned_commit


def test_sync_resolves_pinned_commit_before_copying(tmp_path: Path) -> None:
    if not shutil.which("pwsh"):
        pytest.skip("PowerShell is unavailable")

    config_path, manifest_path, target_file, _ = _write_pinned_sync_fixture(
        tmp_path, expected_hash=hashlib.sha256(b"pinned content\n").hexdigest()
    )

    result = _run_sync_script(config_path, manifest_path)

    assert result.returncode == 0, result.stderr
    assert target_file.read_text(encoding="utf-8") == "pinned content\n"


def test_sync_refuses_pinned_hash_mismatch_without_manifest_update(tmp_path: Path) -> None:
    if not shutil.which("pwsh"):
        pytest.skip("PowerShell is unavailable")

    config_path, manifest_path, target_file, _ = _write_pinned_sync_fixture(
        tmp_path, expected_hash="0" * 64
    )
    original_manifest = manifest_path.read_text(encoding="utf-8")

    result = _run_sync_script(config_path, manifest_path)

    assert result.returncode != 0
    assert not target_file.exists()
    assert manifest_path.read_text(encoding="utf-8") == original_manifest