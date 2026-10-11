import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = PROJECT_ROOT / "tools" / "worktree_protection.py"
REGISTRY_RELATIVE_PATH = ".worktrees/worktree-protection.json"


def _entry(path: str) -> dict[str, object]:
    return {
        "path": path,
        "owner": "release-maintainer",
        "purpose": "active migration investigation",
        "reviewed_at": "2026-10-11T10:00:00Z",
        "review_interval_days": 30,
    }


def _write_registry(repo_root: Path, entries: list[dict[str, object]]) -> None:
    registry_path = repo_root / REGISTRY_RELATIVE_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps({"version": 1, "worktrees": entries}), encoding="utf-8"
    )


def _check(repo_root: Path, candidate: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(CLI_PATH),
            "--repo-root",
            str(repo_root),
            "check",
            candidate,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_valid_registered_worktree_is_reported_protected_without_reading_contents(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    candidate = ".worktrees/feature-branch"
    worktree = repo_root / candidate
    worktree.mkdir(parents=True)
    private_marker = worktree / "private-data.txt"
    private_marker.write_text("worktree payload must not be disclosed", encoding="utf-8")
    _write_registry(repo_root, [_entry(candidate)])

    result = _check(repo_root, candidate)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "status": "protected",
        "candidate": candidate,
        "registry_path": REGISTRY_RELATIVE_PATH,
        "registry_version": 1,
        "protection": {
            "owner": "release-maintainer",
            "purpose": "active migration investigation",
            "reviewed_at": "2026-10-11T10:00:00Z",
            "review_interval_days": 30,
        },
    }
    assert "worktree payload must not be disclosed" not in result.stdout
    assert private_marker.read_text(encoding="utf-8") == "worktree payload must not be disclosed"


def test_unregistered_worktree_is_reported_unprotected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    candidate = ".worktrees/feature-branch"
    _write_registry(repo_root, [_entry(".worktrees/another-branch")])

    result = _check(repo_root, candidate)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "status": "unprotected",
        "candidate": candidate,
        "registry_path": REGISTRY_RELATIVE_PATH,
        "registry_version": 1,
        "protection": None,
    }


@pytest.mark.parametrize(
    "unsafe_path",
    [".worktrees/../outside", "C:/outside"],
)
def test_registry_with_traversal_or_absolute_path_fails_closed(
    tmp_path: Path, unsafe_path: str
) -> None:
    repo_root = tmp_path / "repo"
    candidate = ".worktrees/feature-branch"
    _write_registry(repo_root, [_entry(unsafe_path)])

    result = _check(repo_root, candidate)

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "status": "invalid_registry",
        "candidate": candidate,
        "registry_path": REGISTRY_RELATIVE_PATH,
        "error": "unsafe_path",
    }


def test_registry_path_resolving_outside_worktrees_fails_closed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    worktrees = repo_root / ".worktrees"
    worktrees.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    redirect = worktrees / "redirect"
    try:
        redirect.symlink_to(outside, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("directory symlinks are unavailable")
        junction = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(redirect), str(outside)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip("directory symlinks and junctions are unavailable")
    _write_registry(repo_root, [_entry(".worktrees/redirect")])

    result = _check(repo_root, ".worktrees/feature-branch")

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "status": "invalid_registry",
        "candidate": ".worktrees/feature-branch",
        "registry_path": REGISTRY_RELATIVE_PATH,
        "error": "unsafe_path",
    }


def test_alias_to_registered_worktree_is_reported_protected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    worktrees = repo_root / ".worktrees"
    protected = worktrees / "Protected"
    worktrees.mkdir(parents=True)
    protected.mkdir()
    alias = worktrees / "alias"
    try:
        alias.symlink_to(protected, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("directory symlinks are unavailable")
        junction = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(alias), str(protected)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip("directory symlinks and junctions are unavailable")

    _write_registry(repo_root, [_entry(".worktrees/Protected")])
    result = _check(repo_root, ".worktrees/alias")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "protected"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows paths are case-insensitive")
def test_case_alias_to_registered_worktree_is_reported_protected(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    protected = repo_root / ".worktrees" / "Protected"
    protected.mkdir(parents=True)
    _write_registry(repo_root, [_entry(".worktrees/Protected")])

    result = _check(repo_root, ".worktrees/protected")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "protected"


def test_registry_symlink_to_worktree_file_fails_closed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    worktrees = repo_root / ".worktrees"
    worktrees.mkdir(parents=True)
    linked_registry = worktrees / "feature-branch" / "worktree-protection.json"
    linked_registry.parent.mkdir()
    linked_registry.write_text(
        json.dumps({"version": 1, "worktrees": [_entry(".worktrees/protected")]}),
        encoding="utf-8",
    )
    canonical_registry = worktrees / "worktree-protection.json"
    try:
        canonical_registry.symlink_to(linked_registry)
    except OSError:
        if sys.platform != "win32":
            pytest.skip("file symlinks are unavailable")
        symlink = subprocess.run(
            ["cmd.exe", "/c", "mklink", str(canonical_registry), str(linked_registry)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if symlink.returncode != 0:
            pytest.skip("file symlinks are unavailable")

    result = _check(repo_root, ".worktrees/protected")

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "invalid_registry"
    assert payload["error"] == "unsafe_registry_path"


def test_registry_path_resolved_to_worktree_alias_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.worktree_protection import check_candidate

    repo_root = tmp_path / "repo"
    worktrees = repo_root / ".worktrees"
    candidate = ".worktrees/protected"
    _write_registry(repo_root, [_entry(candidate)])
    alias_registry = worktrees / "feature-branch" / "worktree-protection.json"
    alias_registry.parent.mkdir(parents=True)
    alias_registry.write_text(
        json.dumps({"version": 1, "worktrees": [_entry(candidate)]}),
        encoding="utf-8",
    )
    canonical_registry = repo_root / REGISTRY_RELATIVE_PATH
    resolve_path = Path.resolve

    def resolve_with_registry_alias(
        path: Path, *args: object, **kwargs: object
    ) -> Path:
        if path == canonical_registry:
            return resolve_path(alias_registry, *args, **kwargs)
        return resolve_path(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve_with_registry_alias)

    result = check_candidate(repo_root, candidate)

    assert result == {
        "status": "invalid_registry",
        "candidate": candidate,
        "registry_path": REGISTRY_RELATIVE_PATH,
        "error": "unsafe_registry_path",
    }


def test_malformed_registry_fails_closed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    registry_path = repo_root / REGISTRY_RELATIVE_PATH
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text("{not-json", encoding="utf-8")
    candidate = ".worktrees/feature-branch"

    result = _check(repo_root, candidate)

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "status": "invalid_registry",
        "candidate": candidate,
        "registry_path": REGISTRY_RELATIVE_PATH,
        "error": "malformed_registry",
    }


def test_missing_registry_fails_closed(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    candidate = ".worktrees/feature-branch"

    result = _check(repo_root, candidate)

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "status": "invalid_registry",
        "candidate": candidate,
        "registry_path": REGISTRY_RELATIVE_PATH,
        "error": "missing_registry",
    }