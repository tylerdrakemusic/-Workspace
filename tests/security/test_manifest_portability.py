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


def test_copied_sync_config_resolves_from_relocated_checkout(tmp_path: Path, monkeypatch) -> None:
    module = load_manifest_module()
    clone_root = tmp_path / "relocated-checkout"
    config_path = clone_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    shutil.copy2(WORKTREE_ROOT / "tools" / "skill-sync-config.json", config_path)
    superpowers_root = clone_root / "external" / "superpowers"
    superpowers_root.mkdir(parents=True)
    monkeypatch.setenv("WORKSPACE_ROOT", str(clone_root))
    monkeypatch.setenv("SUPERPOWERS_ROOT", str(superpowers_root))

    config = module.resolve_sync_config(config_path)

    assert config["destination"] == clone_root / ".github" / "skills"
    assert config["log_file"] == clone_root / "logs" / "skill-sync.log"
    repo_names = [repo["name"] for repo in config["repos"]]
    assert repo_names.index("humanizer") < repo_names.index("superpowers")
    assert config["repos"][-1]["path"] == superpowers_root
    assert all(
        not str(path).lower().startswith("f:\\")
        for repo in config["repos"]
        for path in [repo["path"]]
    )


def test_davidondrej_mappings_are_explicitly_optional() -> None:
    config = json.loads(
        (WORKTREE_ROOT / "tools" / "skill-sync-config.json").read_text(encoding="utf-8")
    )
    mapping = next(repo for repo in config["repos"] if repo["name"] == "davidondrej-skills")

    assert mapping["source_policy"] == "optional"
    assert mapping["skills"] == [
        "agent-orchestration/git-worktree",
        "thinking-and-docs/before-building",
        "thinking-and-docs/decisions",
    ]


def test_all_external_mappings_are_explicitly_optional() -> None:
    config = json.loads(
        (WORKTREE_ROOT / "tools" / "skill-sync-config.json").read_text(encoding="utf-8")
    )

    assert config["repos"]
    assert all(repo["source_policy"] == "optional" for repo in config["repos"])


def test_verify_allows_absent_external_sources_in_clean_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_manifest_module()
    clone_root = tmp_path / "clone"
    monkeypatch.setenv("WORKSPACE_ROOT", str(clone_root))
    for environment_name in (
        "MP_SKILLS_ROOT",
        "ADDYOSMANI_AGENT_SKILLS_ROOT",
        "ANDREJ_KARPATHY_SKILLS_ROOT",
        "DAVIDONDREJ_SKILLS_ROOT",
        "SUPERPOWERS_ROOT",
    ):
        monkeypatch.setenv(
            environment_name, str(tmp_path / "missing-external" / environment_name)
        )
    for watched_dir in ("agents", "instructions", "skills"):
        shutil.copytree(
            WORKTREE_ROOT / ".github" / watched_dir,
            clone_root / ".github" / watched_dir,
        )

    config_path = clone_root / "tools" / "skill-sync-config.json"
    config_path.parent.mkdir(parents=True)
    manifest_path = clone_root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest = module.build_manifest(clone_root)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    manifest_skills = {
        key.removeprefix(".github/skills/").removesuffix("/SKILL.md")
        for key in manifest["files"]
        if key.startswith(".github/skills/")
    }
    config = json.loads(
        (WORKTREE_ROOT / "tools" / "skill-sync-config.json").read_text(encoding="utf-8")
    )
    config["repos"] = [
        {**repo, "skills": [skill for skill in repo["skills"] if skill in manifest_skills]}
        for repo in config["repos"]
    ]
    config["repos"] = [repo for repo in config["repos"] if repo["skills"]]
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")

    result = module.verify_skill_integrity(config_path, manifest_path)

    assert result.hard_findings == []
    assert result.entries
    assert {entry.status for entry in result.entries} == {"source_unavailable"}