# Generate or update the agent integrity manifest.
# Run this whenever Tyler legitimately adds/modifies agent files.
# Usage: C:\G\python.exe update_manifest.py
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_GITHUB_DIR = Path(__file__).resolve().parent.parent  # f:\⊕Workspace\.github\

WATCHED_DIRS = [
    _GITHUB_DIR / "agents",
    _GITHUB_DIR / "instructions",
    _GITHUB_DIR / "skills",
]
MANIFEST_PATH = _GITHUB_DIR / "!!☾⛧security" / "agent-manifest.json"
SKILL_SYNC_CONFIG = _GITHUB_DIR.parent / "tools" / "skill-sync-config.json"
EXTENSIONS = {".md", ".py", ".json", ".yaml", ".yml"}


@dataclass(frozen=True)
class SkillIntegrityEntry:
    target: str
    source: str
    source_repository: str
    provenance: str
    status: str


@dataclass(frozen=True)
class SkillIntegrityResult:
    entries: list[SkillIntegrityEntry]
    hard_findings: list[SkillIntegrityEntry]


def _skill_entries(config: dict[str, Any]) -> list[dict[str, str]]:
    destination = Path(config["destination"])
    entries: list[dict[str, str]] = []
    for repo in config["repos"]:
        provenance = repo.get("provenance", "external-source")
        for skill in repo["skills"]:
            source = Path(repo["path"]) / repo["skill_root"] / skill / "SKILL.md"
            target = destination / skill / "SKILL.md"
            entries.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "manifest_key": f".github/skills/{skill}/SKILL.md",
                    "source_repository": repo["name"],
                    "provenance": provenance,
                }
            )
    return entries


def verify_skill_integrity(config_path: Path, manifest_path: Path) -> SkillIntegrityResult:
    """Classify copied skills against their declared source and local baseline."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_files = manifest.get("files", {})
    entries: list[SkillIntegrityEntry] = []
    hard_findings: list[SkillIntegrityEntry] = []

    for item in _skill_entries(config):
        source = Path(item["source"])
        target = Path(item["target"])
        target_key = item["manifest_key"]
        manifest_hash = manifest_files.get(target_key)
        target_hash = sha256_file(target) if target.exists() else None
        source_hash = sha256_file(source) if source.exists() else None

        if target_hash is None or source_hash is None or manifest_hash is None:
            status = "integrity_failure"
        elif target_hash == source_hash:
            status = "source_match"
        elif target_hash == manifest_hash:
            status = "local_customization"
        else:
            status = "integrity_failure"

        entry = SkillIntegrityEntry(
            target=str(target),
            source=str(source),
            source_repository=item["source_repository"],
            provenance=item["provenance"],
            status=status,
        )
        entries.append(entry)
        if status == "integrity_failure":
            hard_findings.append(entry)

    return SkillIntegrityResult(entries=entries, hard_findings=hard_findings)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def update_manifest_entries(
    manifest_path: Path,
    paths: list[Path],
    repo_root: Path | None = None,
) -> None:
    """Update only the manifest hashes for the supplied existing files."""
    root = _repo_root(repo_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.setdefault("files", {})

    for path in paths:
        resolved_path = path.resolve()
        if not resolved_path.is_file():
            raise FileNotFoundError(resolved_path)
        key = _normalize_repo_key(str(resolved_path), root)
        files[key] = sha256_file(resolved_path)

    manifest["file_count"] = len(files)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _repo_root(repo_root: Path | None = None) -> Path:
    return (repo_root or _GITHUB_DIR.parent).resolve()


def _normalize_repo_key(key: str, repo_root: Path) -> str:
    normalized = key.replace("\\", "/")
    if not Path(key).is_absolute():
        return normalized.removeprefix("./")

    try:
        return Path(key).resolve().relative_to(repo_root).as_posix()
    except ValueError:
        marker = ".github/"
        marker_index = normalized.find(marker)
        if marker_index >= 0:
            return normalized[marker_index:]
        return normalized


def build_manifest(repo_root: Path | None = None) -> dict:
    root = _repo_root(repo_root)
    watched_dirs = [
        root / ".github" / "agents",
        root / ".github" / "instructions",
        root / ".github" / "skills",
    ]
    entries: dict[str, str] = {}
    for watched_dir in watched_dirs:
        if not watched_dir.exists():
            continue
        for path in sorted(watched_dir.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file() and path.suffix in EXTENSIONS:
                entries[path.relative_to(root).as_posix()] = sha256_file(path)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "update_manifest.py",
        "file_count": len(entries),
        "files": entries,
    }


def verify_manifest(repo_root: Path | None = None) -> None:
    root = _repo_root(repo_root)
    manifest_path = root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    if not manifest_path.exists():
        print("❌ No manifest found. Run without --verify to create one.")
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    known = {
        _normalize_repo_key(key, root): digest for key, digest in manifest["files"].items()
    }
    current = build_manifest(root)["files"]

    new_files = set(current) - set(known)
    missing = set(known) - set(current)
    modified = {p for p in known if p in current and current[p] != known[p]}

    issues = 0
    for p in sorted(new_files):
        print(f"  ⚠️  NEW (not in manifest):      {p}")
        issues += 1
    for p in sorted(missing):
        print(f"  ⚠️  MISSING (was in manifest):  {p}")
        issues += 1
    for p in sorted(modified):
        print(f"  ⚠️  MODIFIED (hash changed):    {p}")
        issues += 1

    if issues == 0:
        print(f"  ✅ All {len(known)} agent files match manifest.")
    else:
        print(f"\n  {issues} integrity issue(s) found. Review before proceeding.")

    if SKILL_SYNC_CONFIG.exists():
        skill_result = verify_skill_integrity(SKILL_SYNC_CONFIG, manifest_path)
        for entry in skill_result.entries:
            if entry.status == "local_customization":
                print(f"  ⚠️  SOURCE DRIFT (approval required): {entry.target}")
            elif entry.status == "source_match":
                print(f"  ✅ SOURCE MATCH: {entry.target}")
        if skill_result.hard_findings:
            for entry in skill_result.hard_findings:
                print(
                    f"  ❌ SKILL INTEGRITY: {entry.target} "
                    f"(source={entry.source})"
                )
            print(
                f"\n  {len(skill_result.hard_findings)} skill integrity issue(s) found."
            )
            issues += len(skill_result.hard_findings)

    if issues:
        sys.exit(2)


if __name__ == "__main__":
    if "--update-files" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--update-files", nargs="+", type=Path, required=True)
        parser.add_argument("--manifest", type=Path, required=True)
        parser.add_argument("--repo-root", type=Path, required=True)
        args = parser.parse_args()
        update_manifest_entries(args.manifest, args.update_files, args.repo_root)
        print(f"Manifest entries updated: {len(args.update_files)}")
    elif "--verify" in sys.argv:
        print("=== Agent File Integrity Check ===")
        verify_manifest()
    else:
        manifest = build_manifest()
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Manifest written: {manifest['file_count']} files → {MANIFEST_PATH}")
        print(f"   Generated at: {manifest['generated_at']}")
