from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = PROJECT_ROOT / ".github" / "hooks" / "install-hooks.ps1"
HOOK_SCRIPTS = PROJECT_ROOT / ".github" / "hooks" / "scripts"
REPOSITORY_NAMES = (
    "⊕Workspace",
    "∞Life",
    "❤Music",
    "⟨ψ⟩Quantum",
    "👁AI-Manifest",
    "ΣCapital",
)
scenarios("workspace_hook_path_resolution.feature")


@pytest.fixture
def hook_case() -> dict[str, Any]:
    return {}


def _git(repo_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_path), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _make_checkout(
    root: Path,
    *,
    hooks_directory: str = "directory",
    copy_hooks: bool = False,
    previous_config: str | None = None,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    workspace_root = root / "workspace-checkout"
    hooks_root = workspace_root / ".github" / "hooks"
    hooks_root.mkdir(parents=True)
    installer_copy = hooks_root / "install-hooks.ps1"
    source = INSTALLER.read_text(encoding="utf-8")

    repo_paths = {"⊕Workspace": workspace_root}
    for name in REPOSITORY_NAMES:
        repo_paths.setdefault(name, root / "repositories" / name)
        source = source.replace(f'Path = "f:\\{name}"', f'Path = "{repo_paths[name]}"')
    installer_copy.write_text(source, encoding="utf-8")

    canonical_hooks = hooks_root / "scripts"
    if hooks_directory == "directory":
        canonical_hooks.mkdir()
        if copy_hooks:
            shutil.copytree(HOOK_SCRIPTS, canonical_hooks, dirs_exist_ok=True)
    elif hooks_directory == "file":
        canonical_hooks.write_text("not a directory", encoding="utf-8")

    repositories = repo_paths
    for repo_path in repositories.values():
        repo_path.mkdir(parents=True, exist_ok=True)
        _git(repo_path, "init", "--quiet")
        if previous_config is not None:
            _git(repo_path, "config", "--local", "core.hooksPath", previous_config)

    return {
        "workspace_root": workspace_root,
        "canonical_hooks": canonical_hooks,
        "installer": installer_copy,
        "repositories": repositories,
        "previous_config": previous_config,
    }


def _powershell() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is required to exercise install-hooks.ps1")
    return executable


def _run_installer(case: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    installer_path = str(case["installer"]).replace("'", "''")
    command = (
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        f"& '{installer_path}'"
    )
    return subprocess.run(
        [_powershell(), "-NoLogo", "-NoProfile", "-Command", command],
        cwd=case["workspace_root"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _configured_hooks(repo_path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo_path), "config", "--local", "--get", "core.hooksPath"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip() if result.returncode == 0 else None


@given(
    "a valid Workspace checkout with the canonical hook directory and six intended repositories",
    target_fixture="hook_case",
)
def valid_workspace_checkout(tmp_path: Path) -> dict[str, Any]:
    return _make_checkout(tmp_path / "valid")


@when("the hook installer runs for a valid checkout")
def run_hook_installer(hook_case: dict[str, Any]) -> None:
    hook_case["run"] = _run_installer(hook_case)


@then("all six repositories use the existing canonical hook directory under that checkout")
def all_repositories_use_canonical_hooks(hook_case: dict[str, Any]) -> None:
    run = hook_case["run"]
    assert run.returncode == 0, run.stdout + run.stderr
    expected = str(hook_case["canonical_hooks"].resolve())
    assert len(hook_case["repositories"]) == 6
    for repo_path in hook_case["repositories"].values():
        configured = _configured_hooks(repo_path)
        assert configured is not None
        assert Path(configured).resolve() == Path(expected)
        assert Path(configured).is_dir()


@given(
    "the canonical hook directory is missing or is not a directory",
    target_fixture="hook_case",
)
def invalid_canonical_hooks(tmp_path: Path) -> dict[str, Any]:
    return {
        "cases": [
            _make_checkout(
                tmp_path / "missing", hooks_directory="missing", previous_config="old-hooks"
            ),
            _make_checkout(tmp_path / "file", hooks_directory="file", previous_config="old-hooks"),
        ]
    }


@when("the hook installer runs with an invalid canonical directory")
def run_installer_for_invalid_paths(hook_case: dict[str, Any]) -> None:
    hook_case["runs"] = [_run_installer(case) for case in hook_case["cases"]]


@then("it fails without changing any repository hook configuration")
def invalid_hooks_fail_before_configuration_changes(hook_case: dict[str, Any]) -> None:
    assert len(hook_case["runs"]) == 2
    for case, run in zip(hook_case["cases"], hook_case["runs"], strict=True):
        assert run.returncode != 0, run.stdout + run.stderr
        for repo_path in case["repositories"].values():
            assert _configured_hooks(repo_path) == case["previous_config"]


@given(
    "the canonical pre-commit hook is installed in the six intended repositories",
    target_fixture="hook_case",
)
def installed_canonical_hook(tmp_path: Path) -> dict[str, Any]:
    case = _make_checkout(tmp_path / "installed", copy_hooks=True)
    canonical_path = str(case["canonical_hooks"].resolve())
    for repo_path in case["repositories"].values():
        _git(repo_path, "config", "--local", "core.hooksPath", canonical_path)
    case["bash"] = _bash()
    return case


def _bash() -> str:
    if os.name == "nt":
        git_executable = shutil.which("git")
        if git_executable:
            git_bash = Path(git_executable).resolve().parent.parent / "bin" / "bash.exe"
            if git_bash.is_file():
                return str(git_bash)
    executable = shutil.which("bash")
    if executable is None:
        pytest.skip("Bash is required to exercise the pre-commit hook")
    return executable


def _git_bash_path(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.drive:
        return resolved.as_posix()
    drive = resolved.drive[0].lower()
    return f"/{drive}/" + "/".join(resolved.parts[1:])


@pytest.mark.parametrize(
    ("resolved_path", "expected"),
    [
        (PurePosixPath("/home/runner/hooks/pre-commit"), "/home/runner/hooks/pre-commit"),
        (PureWindowsPath("F:\\workspace\\hooks\\pre-commit"), "/f/workspace/hooks/pre-commit"),
    ],
)
def test_git_bash_path_converts_windows_and_posix_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resolved_path: PurePosixPath | PureWindowsPath,
    expected: str,
) -> None:
    monkeypatch.setattr(Path, "resolve", lambda _: resolved_path)

    assert _git_bash_path(tmp_path / "pre-commit") == expected


def test_precommit_entrypoint_is_tracked_executable() -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(PROJECT_ROOT),
            "ls-files",
            "--stage",
            "--",
            ".github/hooks/scripts/pre-commit",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.stdout.startswith("100755 "), result.stdout


@when("the installed pre-commit hook processes staged violations")
def run_existing_safeguards(hook_case: dict[str, Any]) -> None:
    hook_path = hook_case["canonical_hooks"]
    scenarios = (
        ("⊕Workspace", ".worktrees/blocked.txt", "blocked", "worktree-guard"),
        ("❤Music", "credential.txt", "api_key = " + "A" * 20, "secret-scan"),
        ("∞Life", "data/genomics/blocked.txt", "blocked", "health-data-audit"),
    )
    hook_case["safeguard_runs"] = []
    for repo_name, staged_name, content, expected_check in scenarios:
        repo_path = hook_case["repositories"][repo_name]
        staged_path = repo_path / staged_name
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.write_text(content, encoding="utf-8")
        _git(repo_path, "add", "--", staged_name)
        run = subprocess.run(
            [
                hook_case["bash"],
                "-c",
                'exec "$@"',
                "pre-commit-test",
                _git_bash_path(hook_path / "pre-commit"),
            ],
            cwd=repo_path,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        hook_case["safeguard_runs"].append((expected_check, run))


@then("each existing safeguard rejects its matching violation")
def safeguards_reject_matching_violations(hook_case: dict[str, Any]) -> None:
    runs = hook_case["safeguard_runs"]
    assert len(runs) == 3
    for expected_check, run in runs:
        assert run.returncode != 0, run.stdout + run.stderr
        assert expected_check in run.stdout + run.stderr
