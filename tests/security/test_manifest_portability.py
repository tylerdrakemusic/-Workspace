from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_MODULE_PATH = (
    WORKTREE_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py"
)


def load_manifest_module():
    spec = importlib.util.spec_from_file_location(
        "manifest_portability_target", MANIFEST_MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_keys_are_stable_across_checkout_roots(tmp_path: Path) -> None:
    module = load_manifest_module()
    clone_root = tmp_path / "clone"
    for watched_dir in ("agents", "instructions", "skills"):
        shutil.copytree(
            WORKTREE_ROOT / ".github" / watched_dir,
            clone_root / ".github" / watched_dir,
        )

    worktree_manifest = module.build_manifest(WORKTREE_ROOT)
    clone_manifest = module.build_manifest(clone_root)

    assert worktree_manifest["files"] == clone_manifest["files"]
    assert any(key.startswith(".github/agents/") for key in worktree_manifest["files"])
    assert all(
        key.startswith(".github/") and not Path(key).is_absolute()
        for key in worktree_manifest["files"]
    )


def test_verify_normalizes_legacy_absolute_keys_without_external_skill_config(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_manifest_module()
    clone_root = tmp_path / "clone"
    for watched_dir in ("agents", "instructions", "skills"):
        shutil.copytree(
            WORKTREE_ROOT / ".github" / watched_dir,
            clone_root / ".github" / watched_dir,
        )

    current = module.build_manifest(clone_root)
    legacy_files = {
        str(clone_root / key): digest
        for key, digest in current["files"].items()
    }
    manifest_path = clone_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"files": legacy_files}, ensure_ascii=False), encoding="utf-8"
    )

    external_config = tmp_path / "external-live" / "tools" / "skill-sync-config.json"
    external_config.parent.mkdir(parents=True)
    external_config.write_text("not clone config", encoding="utf-8")
    monkeypatch.setattr(module, "SKILL_SYNC_CONFIG", external_config, raising=False)
    assert not (clone_root / "tools" / "skill-sync-config.json").exists()

    module.verify_manifest(clone_root)