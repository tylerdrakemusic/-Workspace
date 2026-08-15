# Generate or update the agent integrity manifest.
# Run this whenever Tyler legitimately adds/modifies agent files.
# Usage: C:\G\python.exe update_manifest.py
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_GITHUB_DIR = Path(__file__).resolve().parent.parent  # f:\⊕Workspace\.github\

WATCHED_DIRS = [
    _GITHUB_DIR / "agents",
    _GITHUB_DIR / "instructions",
    _GITHUB_DIR / "skills",
]
MANIFEST_PATH = _GITHUB_DIR / "!!☾⛧security" / "agent-manifest.json"
EXTENSIONS = {".md", ".py", ".json", ".yaml", ".yml"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
        sys.exit(2)


if __name__ == "__main__":
    if "--verify" in sys.argv:
        print("=== Agent File Integrity Check ===")
        verify_manifest()
    else:
        manifest = build_manifest()
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Manifest written: {manifest['file_count']} files → {MANIFEST_PATH}")
        print(f"   Generated at: {manifest['generated_at']}")
