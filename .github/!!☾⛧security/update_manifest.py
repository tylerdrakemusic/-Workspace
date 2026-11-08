# Generate or update the agent integrity manifest.
# Run this whenever Tyler legitimately adds/modifies agent files.
# Usage: C:\G\python.exe update_manifest.py
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterator

_GITHUB_DIR = Path(__file__).resolve().parent.parent  # f:\⊕Workspace\.github\

WATCHED_DIRS = [
    _GITHUB_DIR / "agents",
    _GITHUB_DIR / "instructions",
    _GITHUB_DIR / "skills",
]
MANIFEST_PATH = _GITHUB_DIR / "!!☾⛧security" / "agent-manifest.json"
EXTENSIONS = {".md", ".py", ".json", ".yaml", ".yml"}
COMPANION_EXTENSIONS = {".sh"}


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


_manifest_thread_locks: dict[str, threading.RLock] = {}
_manifest_thread_locks_guard = threading.Lock()


@contextmanager
def _manifest_write_lock(manifest_path: Path) -> Iterator[None]:
    canonical_path = manifest_path.resolve()
    lock_key = hashlib.sha256(
        os.path.normcase(str(canonical_path)).encode("utf-8")
    ).hexdigest()
    with _manifest_thread_locks_guard:
        thread_lock = _manifest_thread_locks.setdefault(lock_key, threading.RLock())

    lock_path = Path(tempfile.gettempdir()) / f"workspace-manifest-{lock_key}.lock"
    with thread_lock, lock_path.open("a+b") as lock_stream:
        if os.name == "nt":
            import msvcrt

            lock_stream.seek(0, os.SEEK_END)
            if lock_stream.tell() == 0:
                lock_stream.write(b"\0")
                lock_stream.flush()
            lock_stream.seek(0)
            msvcrt.locking(lock_stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_stream.seek(0)
                msvcrt.locking(lock_stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


def _is_watched_file(
    path: Path,
    watched_root: Path,
    allowlisted_companion_keys: set[str] | None = None,
) -> bool:
    if path.suffix in EXTENSIONS:
        return True
    if watched_root.name != "skills" or path.suffix not in COMPANION_EXTENSIONS:
        return False
    if not allowlisted_companion_keys:
        return False
    if path.is_absolute():
        try:
            key = path.relative_to(watched_root.parents[1]).as_posix()
        except ValueError:
            return False
    else:
        key = path.as_posix().removeprefix("./")
    return key in allowlisted_companion_keys


def _skill_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    destination = Path(config["destination"])
    entries: list[dict[str, Any]] = []
    for repo_index, repo in enumerate(config["repos"]):
        provenance = repo.get("provenance", "external-source")
        source_policy = repo.get("source_policy", "required")
        skills = repo["skills"]
        if not isinstance(skills, list):
            raise _SkillSyncPathViolation(
                f"Skills for {repo['name']} must be a list"
            )
        for skill in skills:
            skill_path = PurePosixPath(skill) if isinstance(skill, str) else None
            if (
                skill_path is None
                or not skill
                or "\\" in skill
                or skill_path.is_absolute()
                or PureWindowsPath(skill).is_absolute()
                or PureWindowsPath(skill).drive
                or any(part in {"", ".", ".."} for part in skill.split("/"))
                or skill_path.as_posix() != skill
            ):
                raise _SkillSyncPathViolation(
                    f"Skill mapping must be a normalized relative path: {skill!r}"
                )
        adaptations = repo.get("reviewed_skill_adaptations", {})
        if not isinstance(adaptations, dict):
            raise _SkillSyncPathViolation(
                f"Reviewed skill adaptations for {repo['name']} must be an object"
            )
        if any(skill not in skills for skill in adaptations):
            raise _SkillSyncPathViolation(
                f"Reviewed skill adaptations for {repo['name']} must map configured skills only"
            )
        if adaptations and provenance != "external-source":
            raise _SkillSyncPathViolation(
                f"Reviewed skill adaptations require external-source provenance for {repo['name']}"
            )
        for skill in repo["skills"]:
            adaptation = adaptations.get(skill)
            if adaptation is not None and (
                not isinstance(adaptation, dict)
                or set(adaptation) != {"source_relative_path", "sha256"}
            ):
                raise _SkillSyncPathViolation(
                    f"Reviewed skill adaptation for {repo['name']}:{skill} requires only source_relative_path and sha256"
                )
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
                    "reviewed_adaptation_source_relative_path": (
                        adaptation.get("source_relative_path")
                        if adaptation is not None
                        else None
                    ),
                    "reviewed_adaptation_sha256": (
                        adaptation.get("sha256") if adaptation is not None else None
                    ),
                }
            )
    return entries


def _companion_relative_path(value: Any, description: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).is_absolute()
        or PureWindowsPath(value).drive
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise _SkillSyncPathViolation(
            f"Companion {description} must be a normalized relative path: {value!r}"
        )
    return PurePosixPath(value)


def _reject_companion_reparse_components(path: Path, root: Path, description: str) -> None:
    resolved_root = root.resolve()
    try:
        relative_path = path.relative_to(resolved_root)
    except ValueError as exc:
        raise _SkillSyncPathViolation(
            f"Companion {description} is outside its governed root: {path}"
        ) from exc

    current_path = resolved_root
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for component in relative_path.parts:
        current_path = current_path / component
        try:
            metadata = current_path.lstat()
        except FileNotFoundError:
            continue
        except (OSError, RuntimeError) as exc:
            raise _SkillSyncPathViolation(
                f"Companion {description} path could not be inspected: {current_path}"
            ) from exc
        if current_path.is_symlink() or getattr(metadata, "st_file_attributes", 0) & reparse_flag:
            raise _SkillSyncPathViolation(
                f"Companion {description} path contains a symlink or reparse point: {current_path}"
            )


def _preflight_companion_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    workspace_root = Path(config["workspace_root"])
    destination = _confined_path(
        Path(config["destination"]), workspace_root, "Companion destination"
    )
    entries: list[dict[str, Any]] = []
    identities: set[str] = set()
    source_identities: set[tuple[str, str]] = set()
    targets: set[str] = set()

    for repo_index, repo in enumerate(config["repos"]):
        companions = repo.get("companions", [])
        if not isinstance(companions, list):
            raise _SkillSyncPathViolation(
                f"Companion inventory for {repo['name']} must be a list"
            )
        try:
            repository_root = Path(repo["path"]).resolve()
        except (OSError, RuntimeError) as exc:
            raise _SkillSyncPathViolation(
                f"Source repository root for {repo['name']} could not be resolved: {repo['path']}"
            ) from exc

        for companion_index, companion in enumerate(companions):
            description = f"inventory entry {repo['name']}[{companion_index}]"
            if not isinstance(companion, dict):
                raise _SkillSyncPathViolation(f"Companion {description} must be an object")

            source_relative = _companion_relative_path(
                companion.get("source_relative_path"), f"source path for {description}"
            )
            source_identity = (repo["name"], source_relative.as_posix())
            expected_identity = f"{repo['name']}:{source_relative.as_posix()}"
            identity = companion.get("identity")
            if identity != expected_identity:
                raise _SkillSyncPathViolation(
                    f"Companion {description} identity must be {expected_identity}"
                )
            if identity in identities or source_identity in source_identities:
                raise _SkillSyncPathViolation(
                    f"Companion {description} duplicates a source identity"
                )
            identities.add(identity)
            source_identities.add(source_identity)

            hash_contract = companion.get("hash_contract")
            accepted_baselines = (
                hash_contract.get("accepted_baselines")
                if isinstance(hash_contract, dict)
                else None
            )
            reviewed_adaptation_sha256 = (
                hash_contract.get("reviewed_adaptation_sha256")
                if isinstance(hash_contract, dict)
                else None
            )
            if (
                not isinstance(hash_contract, dict)
                or hash_contract.get("algorithm") != "sha256"
                or not isinstance(accepted_baselines, list)
                or not accepted_baselines
                or any(
                    baseline
                    not in {"approved-source", "reviewed-project-owned-adaptation"}
                    for baseline in accepted_baselines
                )
                or len(accepted_baselines) != len(set(accepted_baselines))
                or (
                    reviewed_adaptation_sha256 is not None
                    and (
                        not isinstance(reviewed_adaptation_sha256, str)
                        or len(reviewed_adaptation_sha256) != 64
                        or any(
                            character not in "0123456789abcdefABCDEF"
                            for character in reviewed_adaptation_sha256
                        )
                    )
                )
            ):
                raise _SkillSyncPathViolation(
                    f"Companion {description} requires an explicit SHA-256 baseline contract"
                )

            reviewed_adaptation_source = None
            reviewed_adaptation_relative = companion.get(
                "reviewed_adaptation_source_relative_path"
            )
            if reviewed_adaptation_relative is not None:
                if (
                    "reviewed-project-owned-adaptation" not in accepted_baselines
                    or not isinstance(reviewed_adaptation_sha256, str)
                ):
                    raise _SkillSyncPathViolation(
                        f"Companion {description} adaptation source requires a reviewed SHA-256 baseline"
                    )
                adaptation_relative = _companion_relative_path(
                    reviewed_adaptation_relative,
                    f"reviewed adaptation source for {description}",
                )
                adaptation_candidate = workspace_root.joinpath(
                    *adaptation_relative.parts
                )
                _reject_companion_reparse_components(
                    adaptation_candidate,
                    workspace_root,
                    f"reviewed adaptation source for {description}",
                )
                adaptation_path = _confined_path(
                    adaptation_candidate,
                    workspace_root,
                    f"Reviewed adaptation source for {description}",
                )
                if not adaptation_path.is_file():
                    raise _SkillSyncPathViolation(
                        f"Reviewed adaptation source for {description} is missing"
                    )
                if sha256_text_file(adaptation_path) != reviewed_adaptation_sha256.lower():
                    raise _SkillSyncPathViolation(
                        f"Reviewed adaptation source for {description} does not match its SHA-256 baseline"
                    )
                reviewed_adaptation_source = str(adaptation_path)

            consumers = companion.get("consumers")
            target_relative_paths = companion.get("target_relative_paths")
            required = companion.get("required")
            if (
                not isinstance(consumers, list)
                or not consumers
                or any(not isinstance(consumer, str) or not consumer for consumer in consumers)
                or len(consumers) != len(set(consumers))
                or not isinstance(target_relative_paths, list)
                or len(target_relative_paths) != len(consumers)
                or not isinstance(required, bool)
            ):
                raise _SkillSyncPathViolation(
                    f"Companion {description} requires explicit requiredness and one unique governed target per consumer"
                )

            source_path = repository_root.joinpath(*source_relative.parts)
            _reject_companion_reparse_components(
                source_path, repository_root, f"source for {description}"
            )
            source_path = _confined_path(
                source_path, repository_root, f"Companion source for {description}"
            )

            resolved_targets: list[str] = []
            normalized_targets: list[str] = []
            for consumer, target_value in zip(consumers, target_relative_paths, strict=True):
                target_relative = _companion_relative_path(
                    target_value, f"target path for {description}"
                )
                normalized_target = target_relative.as_posix()
                expected_prefix = f".github/skills/{consumer}/"
                if not normalized_target.startswith(expected_prefix):
                    raise _SkillSyncPathViolation(
                        f"Companion target for {description} must be governed by consumer {consumer}"
                    )
                target_path = workspace_root.joinpath(*target_relative.parts)
                _reject_companion_reparse_components(
                    target_path, destination, f"target for {description}"
                )
                target_path = _confined_path(
                    target_path, destination, f"Companion target for {description}"
                )
                if str(target_path) in targets:
                    raise _SkillSyncPathViolation(
                        f"Companion {description} duplicates a governed target"
                    )
                targets.add(str(target_path))
                normalized_targets.append(normalized_target)
                resolved_targets.append(str(target_path))

            required_constraints = companion.get("required_constraints", [])
            if (
                not isinstance(required_constraints, list)
                or any(not isinstance(item, str) or not item for item in required_constraints)
            ):
                raise _SkillSyncPathViolation(
                    f"Companion {description} constraints must be non-empty strings"
                )

            entries.append(
                {
                    "repo_index": repo_index,
                    "source_repository": repo["name"],
                    "repository_path": str(repository_root),
                    "source_policy": repo.get("source_policy", "required"),
                    "provenance": repo.get("provenance", "external-source"),
                    "source": str(source_path),
                    "source_relative_path": source_relative.as_posix(),
                    "target_relative_paths": normalized_targets,
                    "targets": resolved_targets,
                    "identity": identity,
                    "hash_contract": hash_contract,
                    "reviewed_adaptation_source": reviewed_adaptation_source,
                    "consumers": consumers,
                    "required": required,
                    "required_constraints": required_constraints,
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


def _reject_path_reparse_components(path: Path, description: str) -> None:
    candidate = Path(os.path.abspath(path))
    components = [candidate, *candidate.parents]
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for component in reversed(components):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except (OSError, RuntimeError) as exc:
            raise _SkillSyncPathViolation(
                f"{description} path could not be inspected: {component}"
            ) from exc
        if component.is_symlink() or getattr(metadata, "st_file_attributes", 0) & reparse_flag:
            raise _SkillSyncPathViolation(
                f"{description} path contains a symlink or reparse point: {component}"
            )


def _write_manifest_atomically(
    manifest_path: Path,
    manifest: dict[str, Any],
    expected_hash: str | None = None,
) -> str:
    payload = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
    return _write_bytes_atomically(manifest_path, payload, expected_hash)


def _write_bytes_atomically(
    manifest_path: Path,
    payload: bytes,
    expected_hash: str | None = None,
) -> str:
    _reject_path_reparse_components(manifest_path, "Agent manifest output")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _reject_path_reparse_components(manifest_path, "Agent manifest output")
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".agent-manifest-",
            suffix=".tmp",
            dir=manifest_path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if manifest_path.exists():
            os.chmod(temporary_path, stat.S_IMODE(manifest_path.stat().st_mode))
        _reject_path_reparse_components(manifest_path, "Agent manifest output")
        if expected_hash is not None and sha256_file(manifest_path) != expected_hash:
            raise ValueError(
                "Manifest changed during update; refusing to overwrite concurrent update"
            )
        os.replace(temporary_path, manifest_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return hashlib.sha256(payload).hexdigest()


def _link_or_atomic_rename(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except OSError as exc:
        if getattr(exc, "winerror", None) not in {1, 50}:
            raise
        os.rename(source, destination)


def _restore_manifest_bytes_if_unchanged(
    manifest_path: Path,
    payload: bytes,
    expected_hash: str,
) -> str:
    temporary_path: Path | None = None
    displaced_path: Path | None = None
    displaced_manifest = False
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".agent-manifest-restore-",
            suffix=".tmp",
            dir=manifest_path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

        displaced_descriptor, displaced_name = tempfile.mkstemp(
            prefix=".agent-manifest-current-",
            suffix=".tmp",
            dir=manifest_path.parent,
        )
        os.close(displaced_descriptor)
        displaced_path = Path(displaced_name)
        _reject_path_reparse_components(manifest_path, "Manifest restore target")
        os.replace(manifest_path, displaced_path)
        displaced_manifest = True

        current_hash = sha256_file(displaced_path)
        if current_hash != expected_hash:
            try:
                _link_or_atomic_rename(displaced_path, manifest_path)
            except FileExistsError as exc:
                raise ValueError(
                    "Manifest changed by another writer; displaced file preserved "
                    f"at {displaced_path}"
                ) from exc
                displaced_path.unlink(missing_ok=True)
            displaced_manifest = False
            raise ValueError("Manifest changed by another writer; rollback refused")

        os.chmod(temporary_path, stat.S_IMODE(displaced_path.stat().st_mode))
        _reject_path_reparse_components(manifest_path, "Manifest restore target")
        _link_or_atomic_rename(temporary_path, manifest_path)
        temporary_path.unlink(missing_ok=True)
        temporary_path = None
        displaced_path.unlink()
        displaced_manifest = False
        return hashlib.sha256(payload).hexdigest()
    except Exception as exc:
        if displaced_manifest and displaced_path is not None and displaced_path.exists():
            if not manifest_path.exists():
                try:
                    _link_or_atomic_rename(displaced_path, manifest_path)
                    displaced_path.unlink(missing_ok=True)
                    displaced_manifest = False
                except FileExistsError:
                    pass
            if displaced_manifest:
                raise ValueError(
                    "Manifest rollback failed; displaced manifest preserved "
                    f"at {displaced_path}"
                ) from exc
        raise
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        if displaced_path is not None and not displaced_manifest:
            displaced_path.unlink(missing_ok=True)


def restore_manifest_backup(
    manifest_path: Path,
    backup_path: Path,
    expected_original_hash: str,
    expected_current_hash: str | None,
    repo_root: Path | None = None,
) -> str:
    """Restore a reviewed-sync manifest backup only if its transaction still owns the file."""
    root = _repo_root(repo_root)
    manifest_file = manifest_path if manifest_path.is_absolute() else root / manifest_path
    canonical_manifest = root / ".github" / "!!☾⛧security" / "agent-manifest.json"
    if Path(os.path.abspath(manifest_file)) != canonical_manifest:
        raise ValueError("Manifest restore target must be the canonical agent manifest")
    backup_file = Path(os.path.abspath(backup_path))
    if (
        backup_file.parent != canonical_manifest.parent
        or not backup_file.name.startswith(".skill-sync-manifest-backup-")
        or not backup_file.name.endswith(".tmp")
    ):
        raise ValueError("Manifest backup must be a same-directory reviewed-sync backup")
    _reject_path_reparse_components(manifest_file, "Agent manifest restore target")
    _reject_path_reparse_components(backup_file, "Agent manifest backup")
    backup_bytes = backup_file.read_bytes()
    if hashlib.sha256(backup_bytes).hexdigest() != expected_original_hash:
        raise ValueError("Manifest backup does not match the original transaction hash")

    with _manifest_write_lock(manifest_file):
        _reject_path_reparse_components(manifest_file, "Agent manifest restore target")
        current_hash = sha256_file(manifest_file)
        if current_hash == expected_original_hash:
            backup_file.unlink(missing_ok=True)
            return current_hash
        if (
            expected_current_hash is None
            or not re.fullmatch(r"[0-9a-f]{64}", expected_current_hash)
            or current_hash != expected_current_hash
        ):
            raise ValueError("Manifest changed by another writer; rollback refused")
        restored_hash = _restore_manifest_bytes_if_unchanged(
            manifest_file, backup_bytes, expected_current_hash
        )
        backup_file.unlink(missing_ok=True)
        return restored_hash


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
        target_candidate = Path(item["target"])
        _reject_path_reparse_components(
            target_candidate,
            f"Target for {item['source_repository']}:{item['skill']}",
        )
        item["target"] = str(
            _confined_path(
                target_candidate,
                destination,
                f"Target for {item['source_repository']}",
            )
        )
        expected_target = destination.joinpath(
            *PurePosixPath(item["skill"]).parts, "SKILL.md"
        )
        if Path(item["target"]) != expected_target:
            raise _SkillSyncPathViolation(
                f"Target for {item['skill']} does not match its canonical skill path"
            )
        adaptation_relative_value = item["reviewed_adaptation_source_relative_path"]
        if adaptation_relative_value is not None:
            if (
                not isinstance(adaptation_relative_value, str)
                or not adaptation_relative_value
                or "\\" in adaptation_relative_value
                or PurePosixPath(adaptation_relative_value).is_absolute()
                or PureWindowsPath(adaptation_relative_value).is_absolute()
                or PureWindowsPath(adaptation_relative_value).drive
                or any(
                    part in {"", ".", ".."}
                    for part in adaptation_relative_value.split("/")
                )
                or not adaptation_relative_value.startswith(
                    "tools/skill-sync-adaptations/"
                )
            ):
                raise _SkillSyncPathViolation(
                    f"Reviewed skill adaptation source must be a normalized tools/skill-sync-adaptations path: {adaptation_relative_value!r}"
                )
            adaptation_hash = item["reviewed_adaptation_sha256"]
            if (
                not isinstance(adaptation_hash, str)
                or not re.fullmatch(r"[0-9a-fA-F]{64}", adaptation_hash)
            ):
                raise _SkillSyncPathViolation(
                    f"Reviewed skill adaptation for {item['skill']} requires a SHA-256 baseline"
                )
            adaptation_candidate = workspace_root.joinpath(
                *PurePosixPath(adaptation_relative_value).parts
            )
            _reject_path_reparse_components(
                adaptation_candidate,
                f"Reviewed skill adaptation for {item['skill']}",
            )
            adaptation_source = _confined_path(
                adaptation_candidate,
                workspace_root,
                f"Reviewed skill adaptation for {item['skill']}",
            )
            _reject_path_reparse_components(
                adaptation_source,
                f"Reviewed skill adaptation for {item['skill']}",
            )
            if not adaptation_source.is_file():
                raise _SkillSyncPathViolation(
                    f"Reviewed skill adaptation source for {item['skill']} is missing"
                )
            if sha256_text_file(adaptation_source) != adaptation_hash.lower():
                raise _SkillSyncPathViolation(
                    f"Reviewed skill adaptation source for {item['skill']} does not match its SHA-256 baseline"
                )
            item["reviewed_adaptation_source"] = str(adaptation_source)
            item["reviewed_adaptation_sha256"] = adaptation_hash.lower()
        else:
            item["reviewed_adaptation_source"] = None
    mapped_targets = {Path(item["target"]) for item in entries}
    mapped_sources = {Path(item["source"]) for item in entries}
    mapped_adaptations = {
        Path(item["reviewed_adaptation_source"])
        for item in entries
        if item["reviewed_adaptation_source"]
    }
    if mapped_adaptations.intersection(mapped_targets | mapped_sources):
        raise _SkillSyncPathViolation(
            "Reviewed skill adaptation source collides with a mapped skill source or target"
        )
    if log_file in mapped_targets:
        raise _SkillSyncPathViolation(
            f"Configured log file path collides with a mapped skill target: {log_file}"
        )
    if log_file in mapped_sources:
        raise _SkillSyncPathViolation(
            f"Configured log file path collides with a mapped skill source: {log_file}"
        )
    if log_file in mapped_adaptations:
        raise _SkillSyncPathViolation(
            f"Configured log file path collides with a reviewed skill adaptation: {log_file}"
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
    companion_entries = _preflight_companion_entries(config)
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
                "reviewed_adaptation_source": item["reviewed_adaptation_source"],
                "reviewed_adaptation_sha256": item["reviewed_adaptation_sha256"],
            }
            for item in entries
            if item["repo_index"] == repo_index
        ]
        resolved_repo["companions"] = [
            {key: value for key, value in item.items() if key != "repo_index"}
            for item in companion_entries
            if item["repo_index"] == repo_index
        ]
        resolved_repos.append(resolved_repo)
    resolved["repos"] = resolved_repos
    return resolved


def _resolve_path(value: Any, root: Path, description: str) -> Path:
    if isinstance(value, dict):
        environment_name = value.get("env")
        if environment_name and (environment_value := os.environ.get(environment_name)):
            value = environment_value
        else:
            value = value.get("relative", ".")
    path = Path(value)
    candidate = path if path.is_absolute() else root / path
    _reject_path_reparse_components(candidate, description)
    try:
        return candidate.resolve()
    except (OSError, RuntimeError) as exc:
        raise _SkillSyncPathViolation(
            f"Configured path could not be resolved: {path}"
        ) from exc


def resolve_sync_config(config_path: Path) -> dict[str, Any]:
    """Resolve a sync config relative to its checkout or explicit environment roots."""
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    root_spec = raw_config.get("workspace_root", {"relative": "."})
    root = _resolve_path(root_spec, config_path.parent.parent, "Workspace root")
    resolved = dict(raw_config)
    resolved["workspace_root"] = root
    has_companions = any(repo.get("companions") for repo in raw_config["repos"])
    destination_description = "Companion target root" if has_companions else "Skill destination"
    resolved["destination"] = _resolve_path(
        raw_config["destination"], root, destination_description
    )
    resolved["log_file"] = _resolve_path(
        raw_config.get("log_file", "logs/skill-sync.log"), root, "Configured log file"
    )
    resolved["repos"] = []
    for repo in raw_config["repos"]:
        resolved_repo = dict(repo)
        source_description = (
            f"Companion source root for {repo['name']}"
            if repo.get("companions")
            else f"Source repository root for {repo['name']}"
        )
        resolved_repo["path"] = _resolve_path(repo["path"], root, source_description)
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
        reviewed_adaptation_match = (
            target_hash is not None
            and manifest_hash is not None
            and target_hash == manifest_hash
            and isinstance(item.get("reviewed_adaptation_sha256"), str)
            and sha256_text_file(target)
            == item["reviewed_adaptation_sha256"].lower()
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
        elif reviewed_adaptation_match:
            status = "reviewed_project_owned_adaptation"
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

    for item in _preflight_companion_entries(config):
        source = Path(item["source"])
        source_hash = sha256_file(source) if source.is_file() else None
        for target_key, target_value in zip(
            item["target_relative_paths"], item["targets"], strict=True
        ):
            target = Path(target_value)
            manifest_hash = manifest_files.get(target_key)
            target_hash = sha256_file(target) if target.is_file() else None
            if target_hash is None and manifest_hash is None and not item["required"]:
                continue
            if target_hash is None or manifest_hash is None:
                status = "integrity_failure"
            elif target_hash != manifest_hash:
                status = "integrity_failure"
            elif source_hash is None:
                status = (
                    "source_unavailable"
                    if item["source_policy"] == "optional" and not item["required"]
                    else "integrity_failure"
                )
            elif target_hash == source_hash:
                status = (
                    "source_match"
                    if "approved-source"
                    in item["hash_contract"]["accepted_baselines"]
                    else "integrity_failure"
                )
            elif (
                "reviewed-project-owned-adaptation"
                in item["hash_contract"]["accepted_baselines"]
            ):
                reviewed_hash = item["hash_contract"].get(
                    "reviewed_adaptation_sha256"
                )
                status = (
                    "reviewed_project_owned_adaptation"
                    if reviewed_hash is not None
                    and sha256_text_file(target) == reviewed_hash.lower()
                    else "integrity_failure"
                )
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


def sha256_text_file(path: Path) -> str:
    """Return the SHA-256 of UTF-8 text after universal newline normalization."""
    normalized_text = path.read_text(encoding="utf-8")
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


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
    expected_manifest_hash: str | None = None,
    expected_file_hashes: dict[Path, str] | None = None,
) -> str:
    """Update only the manifest hashes for the supplied existing files."""
    with _manifest_write_lock(manifest_path):
        return _update_manifest_entries_locked(
            manifest_path,
            paths,
            repo_root,
            expected_manifest_hash,
            expected_file_hashes,
        )


def _update_manifest_entries_locked(
    manifest_path: Path,
    paths: list[Path],
    repo_root: Path | None = None,
    expected_manifest_hash: str | None = None,
    expected_file_hashes: dict[Path, str] | None = None,
) -> str:
    root = _repo_root(repo_root)
    original_manifest_hash = sha256_file(manifest_path)
    if expected_manifest_hash is not None:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_hash):
            raise ValueError("Expected manifest hash must be a lowercase SHA-256 digest")
        if original_manifest_hash != expected_manifest_hash:
            raise ValueError("Agent manifest changed after reviewed sync preflight")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.setdefault("files", {})
    resolved_paths: list[Path] = []
    for path in paths:
        candidate = Path(os.path.abspath(path))
        if expected_file_hashes is not None:
            _reject_path_reparse_components(
                candidate, "Reviewed manifest update target"
            )
        resolved_path = candidate.resolve()
        if expected_file_hashes is not None:
            if candidate != resolved_path:
                raise ValueError(
                    f"Reviewed manifest update target is not canonical: {candidate}"
                )
            key = _normalize_repo_key(str(resolved_path), root)
            if not key.startswith(".github/skills/"):
                raise ValueError(
                    f"Reviewed manifest update target is outside .github/skills: {key}"
                )
        resolved_paths.append(resolved_path)
    resolved_expected_hashes = {
        Path(path).resolve(): digest
        for path, digest in (expected_file_hashes or {}).items()
    }
    if expected_file_hashes is not None:
        if set(resolved_paths) != set(resolved_expected_hashes):
            raise ValueError(
                "Expected file hashes must match the reviewed manifest update paths"
            )
        if any(
            not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for digest in resolved_expected_hashes.values()
        ):
            raise ValueError("Expected file hash must be a lowercase SHA-256 digest")

    for resolved_path in resolved_paths:
        if not resolved_path.is_file():
            raise FileNotFoundError(resolved_path)
        key = _normalize_repo_key(str(resolved_path), root)
        observed_hash = sha256_file(resolved_path)
        expected_hash = resolved_expected_hashes.get(resolved_path)
        if expected_hash is not None and observed_hash != expected_hash:
            raise ValueError(
                f"Reviewed file no longer matches its expected SHA-256: {resolved_path}"
            )
        files[key] = observed_hash

    manifest["file_count"] = len(files)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    return _write_manifest_atomically(
        manifest_path, manifest, expected_hash=original_manifest_hash
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
    with _manifest_write_lock(manifest_path):
        _reconcile_reviewed_manifest_entries_locked(manifest_path, paths, repo_root)


def _reconcile_reviewed_manifest_entries_locked(
    manifest_path: Path,
    paths: list[Path],
    repo_root: Path | None = None,
) -> None:
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
    original_manifest_hash = sha256_file(manifest_file)

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
        if watched_root is None or not _is_watched_file(Path(key), watched_root):
            raise ValueError(f"Reviewed path is outside watched project-owned files: {key}")

        _reject_path_reparse_components(candidate, f"Reviewed path {key}")
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
    _write_manifest_atomically(
        manifest_file, manifest, expected_hash=original_manifest_hash
    )


def build_manifest(repo_root: Path | None = None) -> dict:
    root = _repo_root(repo_root)
    companion_targets: set[str] = set()
    sync_config_path = root / "tools" / "skill-sync-config.json"
    if sync_config_path.is_file():
        sync_config = resolve_sync_config(sync_config_path)
        for item in _preflight_companion_entries(sync_config):
            for target in item["target_relative_paths"]:
                if Path(target).suffix in COMPANION_EXTENSIONS:
                    companion_targets.add(f".github/skills/{target.split('.github/skills/', 1)[-1]}")

    watched_dirs = [
        root / ".github" / "agents",
        root / ".github" / "instructions",
        root / ".github" / "skills",
    ]
    entries: dict[str, str] = {}
    for watched_dir in watched_dirs:
        if not watched_dir.exists():
            continue
        _reject_path_reparse_components(watched_dir, "Manifest watched root")
        for path in sorted(watched_dir.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file() and _is_watched_file(
                path, watched_dir, companion_targets
            ):
                _reject_path_reparse_components(path, "Manifest file")
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
    try:
        current = build_manifest(root)["files"]
    except _SkillSyncPathViolation as error:
        print(f"\n  ❌ SKILL SYNC PATH POLICY: {error}")
        sys.exit(2)

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
            elif entry.status == "reviewed_project_owned_adaptation":
                print(
                    f"  ✅ REVIEWED PROJECT ADAPTATION: {entry.target} "
                    "(matches the approved SHA-256 baseline)"
                )
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
    elif "--sha256-reviewed-text" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--sha256-reviewed-text", type=Path, required=True)
        args = parser.parse_args()
        print(sha256_text_file(args.sha256_reviewed_text))
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
        parser.add_argument("--expected-manifest-hash")
        parser.add_argument(
            "--expected-file-hash",
            action="append",
            nargs=2,
            type=str,
            metavar=("PATH", "SHA256"),
            default=[],
        )
        args = parser.parse_args()
        expected_file_hashes: dict[Path, str] | None = None
        if args.expected_file_hash:
            expected_file_hashes = {}
            for path_value, digest in args.expected_file_hash:
                path = Path(path_value)
                resolved_path = path.resolve()
                if resolved_path in expected_file_hashes:
                    parser.error(f"Expected file hash supplied more than once for {path}")
                expected_file_hashes[resolved_path] = digest
        manifest_hash = update_manifest_entries(
            args.manifest,
            args.update_files,
            args.repo_root,
            args.expected_manifest_hash,
            expected_file_hashes,
        )
        print(f"Manifest entries updated: {len(args.update_files)}")
        print(f"MANIFEST_SHA256={manifest_hash}")
    elif "--restore-manifest-backup" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--restore-manifest-backup", type=Path, required=True)
        parser.add_argument("--expected-original-hash", required=True)
        parser.add_argument("--expected-current-hash")
        parser.add_argument("--manifest", type=Path, required=True)
        parser.add_argument("--repo-root", type=Path, required=True)
        args = parser.parse_args()
        restored_hash = restore_manifest_backup(
            args.manifest,
            args.restore_manifest_backup,
            args.expected_original_hash,
            args.expected_current_hash,
            args.repo_root,
        )
        print(f"Manifest rollback complete: {restored_hash}")
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
        with _manifest_write_lock(MANIFEST_PATH):
            manifest = build_manifest()
            _write_manifest_atomically(MANIFEST_PATH, manifest)
        print(f"✅ Manifest written: {manifest['file_count']} files → {MANIFEST_PATH}")
        print(f"   Generated at: {manifest['generated_at']}")
