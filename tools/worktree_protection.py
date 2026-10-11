"""Validate a repository-local registry of worktrees protected from cleanup."""

import argparse
import json
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

REGISTRY_RELATIVE_PATH = ".worktrees/worktree-protection.json"
_ENTRY_FIELDS = {
    "path",
    "owner",
    "purpose",
    "reviewed_at",
    "review_interval_days",
}


def _safe_worktree_path(repo_root: Path, value: object) -> str | None:
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    posix_path = PurePosixPath(value.replace("\\", "/"))
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        return None
    parts = posix_path.parts
    if len(parts) < 2 or parts[0] != ".worktrees" or any(
        part in {".", ".."} for part in parts
    ):
        return None

    repo_resolved = repo_root.resolve()
    worktrees_resolved = (repo_resolved / ".worktrees").resolve()
    try:
        worktrees_resolved.relative_to(repo_resolved)
        candidate_resolved = (repo_resolved / Path(*parts)).resolve()
        candidate_resolved.relative_to(worktrees_resolved)
    except (OSError, ValueError):
        return None
    if candidate_resolved == worktrees_resolved:
        return None
    return "/".join(parts)


def _error_result(candidate: str, error: str) -> dict[str, Any]:
    return {
        "status": "invalid_registry",
        "candidate": candidate,
        "registry_path": REGISTRY_RELATIVE_PATH,
        "error": error,
    }


def check_candidate(repo_root: Path, candidate: str) -> dict[str, Any]:
    """Report whether a repository-relative worktree candidate is protected."""
    candidate_path = _safe_worktree_path(repo_root, candidate)
    if candidate_path is None:
        return _error_result(candidate, "unsafe_candidate")

    repo_resolved = repo_root.resolve()
    worktrees_resolved = (repo_resolved / ".worktrees").resolve()
    registry_lexical_path = repo_resolved / REGISTRY_RELATIVE_PATH
    registry_path = registry_lexical_path.resolve()
    canonical_registry_path = worktrees_resolved / "worktree-protection.json"
    if registry_path != canonical_registry_path:
        return _error_result(candidate_path, "unsafe_registry_path")

    def identity(path: str) -> Path | None:
        try:
            resolved = (repo_resolved / Path(*PurePosixPath(path).parts)).resolve()
            relative = resolved.relative_to(worktrees_resolved)
        except (OSError, ValueError):
            return None
        if not relative.parts:
            return None
        return Path(".worktrees", *relative.parts)

    candidate_identity = identity(candidate_path)
    if candidate_identity is None:
        return _error_result(candidate_path, "unsafe_candidate")
    try:
        worktrees_resolved.relative_to(repo_resolved)
        registry_path.relative_to(worktrees_resolved)
    except (OSError, ValueError):
        return _error_result(candidate_path, "unsafe_registry_path")

    if not registry_path.is_file():
        return _error_result(candidate_path, "missing_registry")

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _error_result(candidate_path, "malformed_registry")
    except (OSError, UnicodeDecodeError):
        return _error_result(candidate_path, "unreadable_registry")

    if (
        not isinstance(registry, dict)
        or set(registry) != {"version", "worktrees"}
        or type(registry["version"]) is not int
        or registry["version"] != 1
        or not isinstance(registry["worktrees"], list)
    ):
        return _error_result(candidate_path, "invalid_schema")

    entries: dict[Path, dict[str, Any]] = {}
    for entry in registry["worktrees"]:
        if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
            return _error_result(candidate_path, "invalid_schema")
        path = _safe_worktree_path(repo_root, entry["path"])
        if path is None:
            return _error_result(candidate_path, "unsafe_path")
        if (
            any(not isinstance(entry[field], str) or not entry[field].strip() for field in ("owner", "purpose", "reviewed_at"))
            or type(entry["review_interval_days"]) is not int
            or entry["review_interval_days"] <= 0
        ):
            return _error_result(candidate_path, "invalid_schema")
        try:
            reviewed_at = datetime.fromisoformat(entry["reviewed_at"].replace("Z", "+00:00"))
        except ValueError:
            return _error_result(candidate_path, "invalid_schema")
        if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
            return _error_result(candidate_path, "invalid_schema")
        path_identity = identity(path)
        if path_identity is None:
            return _error_result(candidate_path, "unsafe_path")
        if path_identity in entries:
            return _error_result(candidate_path, "invalid_schema")
        entries[path_identity] = entry

    protection = entries.get(candidate_identity)
    return {
        "status": "protected" if protection is not None else "unprotected",
        "candidate": candidate_path,
        "registry_path": REGISTRY_RELATIVE_PATH,
        "registry_version": 1,
        "protection": (
            {
                "owner": protection["owner"],
                "purpose": protection["purpose"],
                "reviewed_at": protection["reviewed_at"],
                "review_interval_days": protection["review_interval_days"],
            }
            if protection is not None
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="check one worktree candidate")
    check_parser.add_argument("candidate", help="repository-relative worktree path")
    args = parser.parse_args()

    result = check_candidate(args.repo_root, args.candidate)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 2 if result["status"] == "invalid_registry" else 0


if __name__ == "__main__":
    raise SystemExit(main())