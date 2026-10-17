# Generate or update the agent integrity manifest.
# Run this whenever Tyler legitimately adds/modifies agent files.
# Usage: C:\G\python.exe update_manifest.py
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

_GITHUB_DIR = Path(__file__).resolve().parent.parent  # f:\⊕Workspace\.github\

WATCHED_DIRS = [
    _GITHUB_DIR / "agents",
    _GITHUB_DIR / "instructions",
    _GITHUB_DIR / "skills",
]
MANIFEST_PATH = _GITHUB_DIR / "!!☾⛧security" / "agent-manifest.json"
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


class _SkillSyncPathViolation(ValueError):
    pass


class _QuarantineRequestViolation(ValueError):
    pass


def _skill_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    destination = Path(config["destination"])
    entries: list[dict[str, Any]] = []
    for repo_index, repo in enumerate(config["repos"]):
        provenance = repo.get("provenance", "external-source")
        source_policy = repo.get("source_policy", "required")
        for skill in repo["skills"]:
            source = Path(repo["path"]) / repo["skill_root"] / repo.get(
                "source_path", f"{skill}/SKILL.md"
            )
            target = destination / skill / "SKILL.md"
            entries.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "manifest_key": f".github/skills/{skill}/SKILL.md",
                    "source_repository": repo["name"],
                    "repo_index": repo_index,
                    "skill": skill,
                    "repository_path": str(repo["path"]),
                    "provenance": provenance,
                    "source_policy": source_policy,
                    "pinned_commit": repo.get("pinned_commit", ""),
                    "pinned_sha256": repo.get("sha256", ""),
                    "pin_fields_present": (
                        "pinned_commit" in repo or "sha256" in repo
                    ),
                }
            )
    return entries


def _confined_path(path: Path, root: Path, description: str) -> Path:
    try:
        resolved_root = root.resolve()
        resolved_path = path.resolve()
    except (OSError, RuntimeError) as exc:
        raise _SkillSyncPathViolation(
            f"{description} path could not be resolved: {path}"
        ) from exc
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise _SkillSyncPathViolation(
            f"{description} path resolves outside configured root: {resolved_path}"
        ) from exc
    return resolved_path


def _preflight_skill_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    workspace_root = Path(config["workspace_root"])
    destination = _confined_path(
        Path(config["destination"]), workspace_root, "Skill destination"
    )
    log_file = _confined_path(
        Path(config["log_file"]), workspace_root, "Configured log file"
    )
    entries = _skill_entries(config)
    for item in entries:
        repository_root = Path(item["repository_path"])
        try:
            repository_root = repository_root.resolve()
        except (OSError, RuntimeError) as exc:
            raise _SkillSyncPathViolation(
                "Source repository root for "
                f"{item['source_repository']} could not be resolved: {repository_root}"
            ) from exc
        source = _confined_path(
            Path(item["source"]),
            repository_root,
            f"Source for {item['source_repository']}",
        )
        item["source"] = str(source)
        item["source_relative_path"] = source.relative_to(repository_root).as_posix()
        item["target"] = str(
            _confined_path(
                Path(item["target"]),
                destination,
                f"Target for {item['source_repository']}",
            )
        )
    mapped_targets = {Path(item["target"]) for item in entries}
    mapped_sources = {Path(item["source"]) for item in entries}
    if log_file in mapped_targets:
        raise _SkillSyncPathViolation(
            f"Configured log file path collides with a mapped skill target: {log_file}"
        )
    if log_file in mapped_sources:
        raise _SkillSyncPathViolation(
            f"Configured log file path collides with a mapped skill source: {log_file}"
        )
    if log_file.exists():
        for target in mapped_targets:
            if target.exists() and os.path.samefile(log_file, target):
                raise _SkillSyncPathViolation(
                    f"Configured log file path aliases a mapped skill target: {log_file}"
                )
        for source in mapped_sources:
            if source.exists() and os.path.samefile(log_file, source):
                raise _SkillSyncPathViolation(
                    f"Configured log file path aliases a mapped skill source: {log_file}"
                )
    try:
        log_file.relative_to(destination)
    except ValueError:
        try:
            destination.relative_to(log_file)
        except ValueError:
            pass
        else:
            raise _SkillSyncPathViolation(
                f"Configured log file path overlaps the skill destination: {log_file}"
            )
    else:
        raise _SkillSyncPathViolation(
            f"Configured log file path overlaps the skill destination: {log_file}"
        )
    return entries


def preflight_sync_config(config_path: Path) -> dict[str, Any]:
    """Return a resolved sync plan after validating every source and target."""
    config = resolve_sync_config(config_path)
    entries = _preflight_skill_entries(config)
    resolved = dict(config)
    resolved["workspace_root"] = str(config["workspace_root"])
    resolved["destination"] = str(config["destination"])
    resolved["log_file"] = str(config["log_file"])
    resolved_repos: list[dict[str, Any]] = []
    for repo_index, repo in enumerate(config["repos"]):
        resolved_repo = dict(repo)
        resolved_repo["path"] = str(repo["path"])
        resolved_repo["mappings"] = [
            {
                "skill": item["skill"],
                "source": item["source"],
                "source_relative_path": item["source_relative_path"],
                "target": item["target"],
            }
            for item in entries
            if item["repo_index"] == repo_index
        ]
        resolved_repos.append(resolved_repo)
    resolved["repos"] = resolved_repos
    return resolved


def _resolve_path(value: Any, root: Path) -> Path:
    if isinstance(value, dict):
        environment_name = value.get("env")
        if environment_name and (environment_value := os.environ.get(environment_name)):
            value = environment_value
        else:
            value = value.get("relative", ".")
    path = Path(value)
    try:
        return path.resolve() if path.is_absolute() else (root / path).resolve()
    except (OSError, RuntimeError) as exc:
        raise _SkillSyncPathViolation(
            f"Configured path could not be resolved: {path}"
        ) from exc


def resolve_sync_config(config_path: Path) -> dict[str, Any]:
    """Resolve a sync config relative to its checkout or explicit environment roots."""
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    root_spec = raw_config.get("workspace_root", {"relative": "."})
    root = _resolve_path(root_spec, config_path.parent.parent)
    resolved = dict(raw_config)
    resolved["workspace_root"] = root
    resolved["destination"] = _resolve_path(raw_config["destination"], root)
    resolved["log_file"] = _resolve_path(
        raw_config.get("log_file", "logs/skill-sync.log"), root
    )
    resolved["repos"] = []
    for repo in raw_config["repos"]:
        resolved_repo = dict(repo)
        resolved_repo["path"] = _resolve_path(repo["path"], root)
        resolved["repos"].append(resolved_repo)
    return resolved


def verify_skill_integrity(
    config_path: Path,
    manifest_path: Path,
    quarantined_external_skills: list[str] | None = None,
) -> SkillIntegrityResult:
    """Classify copied skills against their declared source and local baseline."""
    config = resolve_sync_config(config_path)
    items = _preflight_skill_entries(config)
    quarantine_names = set(quarantined_external_skills or [])
    if len(quarantine_names) != len(quarantined_external_skills or []):
        raise _QuarantineRequestViolation(
            "A quarantined external skill may be named only once"
        )
    external_name_counts: dict[str, int] = {}
    for item in items:
        if item["provenance"] == "external-source":
            external_name_counts[item["skill"]] = external_name_counts.get(item["skill"], 0) + 1
    invalid_quarantine_names = {
        name for name in quarantine_names if external_name_counts.get(name) != 1
    }
    if invalid_quarantine_names:
        raise _QuarantineRequestViolation(
            "Quarantine requires exactly one configured external-source mapping: "
            + ", ".join(sorted(invalid_quarantine_names))
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_files = manifest.get("files", {})
    entries: list[SkillIntegrityEntry] = []
    hard_findings: list[SkillIntegrityEntry] = []

    for item in items:
        source = Path(item["source"])
        target = Path(item["target"])
        target_key = item["manifest_key"]
        manifest_hash = manifest_files.get(target_key)
        target_hash = sha256_file(target) if target.exists() else None
        pinned_commit = item["pinned_commit"]
        pinned_sha256 = item["pinned_sha256"]
        pin_configured = bool(
            item["pin_fields_present"] or pinned_commit or pinned_sha256
        )
        pin_pair_complete = (
            pin_configured
            and isinstance(pinned_commit, str)
            and bool(pinned_commit.strip())
            and isinstance(pinned_sha256, str)
            and len(pinned_sha256) == 64
            and all(
                character in "0123456789abcdefABCDEF"
                for character in pinned_sha256
            )
        )
        if pin_pair_complete:
            source_hash = pinned_git_blob_sha256(
                Path(item["repository_path"]), source, pinned_commit
            )
            pinned_blob_matches = source_hash == pinned_sha256.lower()
        elif pin_configured:
            source_hash = None
            pinned_blob_matches = False
        else:
            source_hash = sha256_file(source) if source.exists() else None
            pinned_blob_matches = True
        pinned_source_matches = validate_pinned_source(
            Path(item["repository_path"]), pinned_commit
        ) if pin_pair_complete else not pin_configured
        quarantine_source_update = (
            item["skill"] in quarantine_names
            and item["provenance"] == "external-source"
            and target_hash is not None
            and manifest_hash is not None
            and target_hash == manifest_hash
            and (
                (
                    pin_configured
                    and pin_pair_complete
                    and pinned_blob_matches
                    and source_hash == target_hash
                    and not pinned_source_matches
                )
                or (
                    not pin_configured
                    and source_hash is not None
                    and source_hash != target_hash
                )
            )
        )

        if target_hash is None or manifest_hash is None:
            status = "integrity_failure"
        elif pin_configured and (
            not pin_pair_complete
            or not pinned_blob_matches
            or (not pinned_source_matches and not quarantine_source_update)
        ):
            status = "integrity_failure"
        elif (
            item["source_policy"] == "optional"
            and not Path(item["repository_path"]).exists()
        ):
            status = "source_unavailable"
        elif source_hash is None and item["source_policy"] == "optional":
            status = "source_unavailable"
        elif source_hash is None:
            status = "integrity_failure"
        elif quarantine_source_update:
            status = "source_update_quarantined"
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


def pinned_git_blob_sha256(
    repository_path: Path, source_path: Path, pinned_commit: str
) -> str | None:
    """Return the SHA-256 of a source file at its pinned Git revision."""
    if not pinned_commit or not (repository_path / ".git").exists():
        return None
    try:
        source_relative_path = source_path.relative_to(repository_path).as_posix()
        blob = _read_pinned_git_blob(
            repository_path, pinned_commit, source_relative_path
        )
    except (OSError, ValueError):
        return None
    if blob is None:
        return None
    return hashlib.sha256(blob).hexdigest()


def _repository_relative_git_path(source_relative_path: str) -> str:
    normalized = source_relative_path.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(source_relative_path)
    if (
        not normalized
        or "\x00" in normalized
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
    ):
        raise ValueError("Pinned Git blob source path must be repository-relative")
    return posix_path.as_posix()


def _read_pinned_git_blob(
    repository_path: Path, pinned_commit: str, source_relative_path: str
) -> bytes | None:
    relative_path = _repository_relative_git_path(source_relative_path)
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository_path),
                "cat-file",
                "blob",
                f"{pinned_commit}:{relative_path}",
            ],
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def write_pinned_git_blob(
    repository_path: Path,
    pinned_commit: str,
    source_relative_path: str,
    output_path: Path,
    worktree_root: Path,
) -> str:
    """Write raw pinned Git blob bytes to a file confined to a Git worktree."""
    blob = _read_pinned_git_blob(
        repository_path, pinned_commit, source_relative_path
    )
    if blob is None:
        raise ValueError(
            f"Pinned Git blob is unavailable: {pinned_commit}:{source_relative_path}"
        )

    root = worktree_root.resolve()
    if not root.is_dir() or not (root / ".git").exists():
        raise ValueError("Pinned blob output root must be a materialized Git worktree")
    output = _confined_path(output_path, root, "Pinned blob output")
    if output == root:
        raise ValueError("Pinned blob output must be a file under the worktree root")
    output.parent.mkdir(parents=True, exist_ok=True)
    output = _confined_path(output, root, "Pinned blob output")
    if output.is_dir():
        raise ValueError(f"Pinned blob output is not a file: {output}")
    output.write_bytes(blob)
    return hashlib.sha256(blob).hexdigest()


def validate_pinned_source(repository_path: Path, pinned_commit: str) -> bool:
    """Return whether an available git source is at its declared revision."""
    if not pinned_commit:
        return True
    if not (repository_path / ".git").exists():
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(repository_path), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == pinned_commit


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


def reconcile_reviewed_manifest_entries(
    manifest_path: Path,
    paths: list[Path],
    repo_root: Path | None = None,
) -> None:
    """Reconcile only reviewed watched paths, including additions and deletions."""
    root = _repo_root(repo_root)
    manifest_candidate = manifest_path if manifest_path.is_absolute() else root / manifest_path
    requested_manifest = Path(os.path.abspath(manifest_candidate))
    canonical_manifest = root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    if requested_manifest != canonical_manifest:
        raise ValueError("Reviewed reconciliation output must be the agent manifest")
    cursor = root
    for component in canonical_manifest.relative_to(root).parts:
        cursor /= component
        if cursor.is_symlink():
            raise ValueError(f"Agent manifest path contains a symbolic link: {cursor}")
    manifest_file = _confined_path(requested_manifest, root, "Agent manifest")
    if manifest_file != canonical_manifest:
        raise ValueError("Reviewed reconciliation output must resolve to the agent manifest")
    if not paths:
        raise ValueError("At least one reviewed path is required")

    external_targets: set[Path] = set()
    sync_config_path = root / "tools" / "skill-sync-config.json"
    if sync_config_path.exists():
        sync_config = resolve_sync_config(sync_config_path)
        external_targets = {
            Path(item["target"]).resolve()
            for item in _preflight_skill_entries(sync_config)
            if item["provenance"] == "external-source"
        }

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("Agent manifest must contain a files object")

    operations: list[tuple[str, str | None]] = []
    seen_keys: set[str] = set()
    watched_roots = {
        ".github/agents": root / ".github" / "agents",
        ".github/instructions": root / ".github" / "instructions",
        ".github/skills": root / ".github" / "skills",
    }
    for path in paths:
        candidate = path if path.is_absolute() else root / path
        lexical_path = Path(os.path.abspath(candidate))
        try:
            lexical_relative = lexical_path.relative_to(root)
            resolved_path = candidate.resolve(strict=False)
            resolved_relative = resolved_path.relative_to(root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError(f"Reviewed path is outside the repository: {path}") from exc

        key = lexical_relative.as_posix()
        watched_root = next(
            (directory for prefix, directory in watched_roots.items() if key.startswith(prefix + "/")),
            None,
        )
        if watched_root is None or Path(key).suffix not in EXTENSIONS:
            raise ValueError(f"Reviewed path is outside watched project-owned files: {key}")

        cursor = root
        for component in lexical_relative.parts:
            cursor /= component
            if cursor.is_symlink():
                raise ValueError(f"Reviewed path contains a symbolic link: {key}")
        try:
            resolved_path.relative_to(watched_root.resolve())
        except ValueError as exc:
            raise ValueError(f"Reviewed path escapes its watched directory: {key}") from exc

        if key in seen_keys:
            raise ValueError(f"Reviewed path was supplied more than once: {key}")
        seen_keys.add(key)
        if resolved_path in external_targets:
            raise ValueError(f"External-skill target cannot use project-owned reconciliation: {key}")

        if candidate.is_file():
            operations.append((key, sha256_file(candidate)))
        elif candidate.exists():
            raise ValueError(f"Reviewed path is not a file: {key}")
        elif key in files:
            operations.append((key, None))
        else:
            raise ValueError(f"Deleted reviewed path is absent from the manifest: {key}")

    for key, digest in operations:
        if digest is None:
            del files[key]
        else:
            files[key] = digest

    manifest["file_count"] = len(files)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


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


def verify_manifest(
    repo_root: Path | None = None,
    quarantined_external_skills: list[str] | None = None,
) -> None:
    root = _repo_root(repo_root)
    manifest_path = root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    skill_sync_config = root / "tools" / "skill-sync-config.json"
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

    if skill_sync_config.exists():
        try:
            skill_result = verify_skill_integrity(
                skill_sync_config, manifest_path, quarantined_external_skills
            )
        except _SkillSyncPathViolation as error:
            print(f"\n  ❌ SKILL SYNC PATH POLICY: {error}")
            sys.exit(2)
        except _QuarantineRequestViolation as error:
            print(f"\n  ❌ INVALID QUARANTINE REQUEST: {error}")
            sys.exit(2)
        for entry in skill_result.entries:
            if entry.status == "local_customization":
                print(f"  ⚠️  SOURCE DRIFT (approval required): {entry.target}")
            elif entry.status == "source_match":
                print(f"  ✅ SOURCE MATCH: {entry.target}")
            elif entry.status == "source_update_quarantined":
                print(
                    f"  ℹ️  SOURCE UPDATE QUARANTINED: {entry.target} "
                    "(installed copy matches trusted baseline)"
                )
            elif entry.status == "source_unavailable":
                print(f"  ℹ️  SOURCE UNAVAILABLE: {entry.target} (optional source)")
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
    elif quarantined_external_skills:
        print("\n  ❌ INVALID QUARANTINE REQUEST: no skill sync config is available")
        sys.exit(2)

    if issues:
        sys.exit(2)


if __name__ == "__main__":
    if "--write-pinned-git-blob" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--write-pinned-git-blob",
            nargs=3,
            required=True,
            metavar=("REPOSITORY", "COMMIT", "SOURCE_RELATIVE_PATH"),
        )
        parser.add_argument("--output", type=Path, required=True)
        parser.add_argument("--root", type=Path, required=True)
        args = parser.parse_args()
        repository, commit, source_relative_path = args.write_pinned_git_blob
        digest = write_pinned_git_blob(
            Path(repository), commit, source_relative_path, args.output, args.root
        )
        print(digest)
    elif "--confine-path" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--confine-path", type=Path, required=True)
        parser.add_argument("--root", type=Path, required=True)
        args = parser.parse_args()
        print(_confined_path(args.confine_path, args.root, "Source"))
    elif "--preflight-sync-config" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--preflight-sync-config", type=Path, required=True)
        args = parser.parse_args()
        print(json.dumps(preflight_sync_config(args.preflight_sync_config), ensure_ascii=False))
    elif "--update-files" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--update-files", nargs="+", type=Path, required=True)
        parser.add_argument("--manifest", type=Path, required=True)
        parser.add_argument("--repo-root", type=Path, required=True)
        args = parser.parse_args()
        update_manifest_entries(args.manifest, args.update_files, args.repo_root)
        print(f"Manifest entries updated: {len(args.update_files)}")
    elif "--reconcile-reviewed-files" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--reconcile-reviewed-files", nargs="+", type=Path, required=True)
        parser.add_argument("--manifest", type=Path, required=True)
        parser.add_argument("--repo-root", type=Path, required=True)
        args = parser.parse_args()
        reconcile_reviewed_manifest_entries(
            args.manifest, args.reconcile_reviewed_files, args.repo_root
        )
        print(f"Reviewed manifest paths reconciled: {len(args.reconcile_reviewed_files)}")
    elif "--verify" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--verify", action="store_true")
        parser.add_argument("--quarantine-external-skill", action="append", default=[])
        args = parser.parse_args()
        print("=== Agent File Integrity Check ===")
        verify_manifest(quarantined_external_skills=args.quarantine_external_skill)
    else:
        if len(sys.argv) > 1:
            raise SystemExit(f"Unsupported update_manifest.py arguments: {' '.join(sys.argv[1:])}")
        manifest = build_manifest()
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✅ Manifest written: {manifest['file_count']} files → {MANIFEST_PATH}")
        print(f"   Generated at: {manifest['generated_at']}")
