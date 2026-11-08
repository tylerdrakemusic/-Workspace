"""Tests for the staged wizard template's credential boundaries."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = (
    PROJECT_ROOT
    / "tools"
    / "skill-sync-adaptations"
    / "wizard"
    / "template.sh"
)


def _bash_path(path: Path) -> str:
    posix_path = path.as_posix()
    if os.name == "nt":
        return f"/mnt/{path.drive[0].lower()}{posix_path[2:]}"
    return posix_path


def _run_wizard_library(
    tmp_path: Path,
    body: str,
    *,
    cwd: Path,
    script_directory: Path | None = None,
    input_text: str = "",
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    library, marker, _ = template.partition("\nrun_wizard() {")
    assert marker, "wizard template must keep its library separate from interactive stages"
    probe_directory = script_directory or tmp_path
    probe_directory.mkdir(parents=True, exist_ok=True)
    probe = probe_directory / ".wizard-library-probe.sh"
    probe.write_bytes(f"{library}\n{body}\n".replace("\r\n", "\n").encode("utf-8"))
    probe_path = probe.as_posix()
    if os.name == "nt" and "\\windows\\system32\\bash.exe" in bash.lower():
        probe_path = f"/mnt/{probe.drive[0].lower()}{probe_path[2:]}"
    return subprocess.run(
        [bash, probe_path],
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **(environment or {})},
        check=False,
    )


def _run_wizard_stages(tmp_path: Path) -> subprocess.CompletedProcess[str]:
        bash = shutil.which("bash")
        if bash is None:
                pytest.skip("Bash is unavailable")
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        stage_script, launcher, _ = template.rpartition('\nrun_wizard "$@"; exit')
        assert launcher, "wizard template must keep its launcher as the final command"
        capture_path = tmp_path / "set-secret-call.txt"
        stubs = f"""
banner() {{ :; }}
pause() {{ :; }}
stage() {{ :; }}
say() {{ :; }}
step() {{ :; }}
open_url() {{ :; }}
finish() {{ :; }}
ask() {{
    if [[ "$1" == "GITHUB_REPOSITORY" ]]; then
        printf -v "$1" '%s' "owner/repo"
    else
        printf -v "$1" '%s' "public-key"
    fi
}}
ask_secret() {{ printf -v "$1" '%s' "synthetic-secret"; }}
write_env() {{ :; }}
set_secret() {{ printf '%s\\n' "$#" "$*" > {shlex.quote(_bash_path(capture_path))}; }}
run_wizard
"""
        probe = tmp_path / "wizard-stages.sh"
        probe.write_bytes((stage_script + "\n" + stubs).replace("\r\n", "\n").encode("utf-8"))
        probe_path = probe.as_posix()
        if os.name == "nt" and "\\windows\\system32\\bash.exe" in bash.lower():
                probe_path = f"/mnt/{probe.drive[0].lower()}{probe_path[2:]}"
        return subprocess.run(
                [bash, probe_path],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
        )


def test_write_env_rejects_repository_env_files(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    caller_repository = tmp_path / "caller-repo"
    caller_repository.mkdir()
    subprocess.run(
        ["git", "init", str(repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "init", str(caller_repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    env_file = _bash_path(repository / ".env")
    body = (
        'stat() { if [[ "$1 $2 $3" == "-f -c %T" ]]; then printf "ext4\\n"; elif [[ "$1 $2 $3" == "-c %a"* ]]; then printf "600\\n"; else command stat "$@"; fi; }\n'
        'chmod() { return 0; }\n'
        f"ENV_FILE={shlex.quote(env_file)}\n"
        'TEST_SECRET="synthetic-secret"\n'
        'write_env "API_TOKEN" "$TEST_SECRET"\n'
    )

    result = _run_wizard_library(
        tmp_path,
        body,
        cwd=caller_repository,
        script_directory=repository,
    )

    assert result.returncode != 0
    assert not (repository / ".env").exists()
    assert "synthetic-secret" not in result.stdout + result.stderr


def test_ask_secret_does_not_read_repository_env_files(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(
        ["git", "init", str(repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    env_file = _bash_path(repository / ".env")
    body = (
        'stat() { if [[ "$1 $2 $3" == "-f -c %T" ]]; then printf "ext4\\n"; else command stat "$@"; fi; }\n'
        f"ENV_FILE={shlex.quote(env_file)}\n"
        'TEST_SECRET="sentinel-input"\n'
        'ask_secret API_TOKEN "API token"\n'
    )
    (repository / ".env").write_text("API_TOKEN='old-value'\n", encoding="utf-8")

    result = _run_wizard_library(
        tmp_path,
        body,
        cwd=repository,
        script_directory=repository,
        input_text="replacement-input\n",
    )

    assert result.returncode != 0
    assert "Enter keeps current" not in result.stdout
    assert "old-value" not in result.stdout + result.stderr
    assert "sentinel-input" not in result.stdout + result.stderr


def test_ask_rejects_piped_input_without_terminal(tmp_path: Path) -> None:
    result = _run_wizard_library(
        tmp_path,
        'if ask API_TOKEN "API token:"; then exit 20; fi\n',
        cwd=tmp_path,
        input_text="piped-input\n",
    )

    assert result.returncode == 0, result.stderr
    assert "interactive terminal is required" in result.stdout
    assert "piped-input" not in result.stdout + result.stderr


def test_write_env_rejects_repository_env_through_script_symlink(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(
        ["git", "init", str(repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    env_file = _bash_path(repository / ".env")
    body = (
        'stat() { if [[ "$1 $2 $3" == "-f -c %T" ]]; then printf "ext4\\n"; '
        'elif [[ "$1 $2" == "-c %a"* ]]; then printf "600\\n"; '
        'else command stat "$@"; fi; }\n'
        'chmod() { return 0; }\n'
        'git() { if [[ "$2" == "$CALLER_REPOSITORY" ]]; then '
        'printf "%s\\n" "$CALLER_REPOSITORY"; '
        'else printf "%s\\n" "$ACTUAL_REPOSITORY"; fi; }\n'
        'if [[ "${SYMLINK_PROBE:-}" != "1" ]]; then\n'
        '  caller_repository="$(mktemp -d /tmp/wizard-caller-repository.XXXXXX)"\n'
        '  trap \'rm -f "$caller_repository/probe.sh"; rmdir "$caller_repository"\' EXIT\n'
        '  ln -s "$BASH_SOURCE" "$caller_repository/probe.sh"\n'
        f'  if ACTUAL_REPOSITORY={shlex.quote(_bash_path(repository))} '
        f'CALLER_REPOSITORY="$caller_repository" ENV_FILE={shlex.quote(env_file)} '
        'SYMLINK_PROBE=1 "$caller_repository/probe.sh"; then\n'
        '    printf "unsafe-write\\n"\n'
        '    exit 20\n'
        '  fi\n'
        '  exit 0\n'
        'fi\n'
        'TEST_SECRET="synthetic-secret"\n'
        'write_env "API_TOKEN" "$TEST_SECRET"\n'
    )

    result = _run_wizard_library(
        tmp_path,
        body,
        cwd=repository,
        script_directory=repository,
    )

    assert result.returncode == 0, result.stderr
    assert "set ENV_FILE" in result.stdout
    assert "unsafe-write" not in result.stdout
    assert not (repository / ".env").exists()
    assert "synthetic-secret" not in result.stdout + result.stderr


def test_write_env_allows_an_explicit_external_environment_file(tmp_path: Path) -> None:
    body = (
        'git_root="$(mktemp -d /tmp/wizard-repository.XXXXXX)"\n'
        'approved_directory="$(mktemp -d /tmp/wizard-config.XXXXXX)"\n'
        'trap \'rm -f "$approved_directory/credentials.env"; rmdir "$approved_directory" "$git_root"\' EXIT\n'
        'git() { printf "%s\\n" "$git_root"; }\n'
        'ENV_FILE="$approved_directory/credentials.env"\n'
        'TEST_SECRET="synthetic-secret"\n'
        'write_env "API_TOKEN" "$TEST_SECRET" || exit 1\n'
        '[[ "$(stat -c "%a" "$ENV_FILE")" == "600" ]] || exit 2\n'
        "grep -qx \"API_TOKEN='synthetic-secret'\" \"$ENV_FILE\" || exit 3\n"
    )

    result = _run_wizard_library(
        tmp_path,
        body,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "synthetic-secret" not in result.stdout + result.stderr


def test_write_env_rejects_external_hardlink_to_repository_env(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(
        ["git", "init", str(repository)],
        check=True,
        capture_output=True,
        text=True,
    )
    env_file = repository / ".env"
    external_link = tmp_path / "linked.env"
    env_file.write_text("API_TOKEN='old-value'\n", encoding="utf-8")
    env_file.chmod(0o600)
    os.link(env_file, external_link)
    assert env_file.stat().st_nlink == 2
    body = (
        'stat() { if [[ "$1 $2 $3" == "-f -c %T" ]]; then printf "ext4\\n"; else command stat "$@"; fi; }\n'
        f"ENV_FILE={shlex.quote(_bash_path(external_link))}\n"
        'TEST_SECRET="synthetic-secret"\n'
        'if write_env "API_TOKEN" "$TEST_SECRET"; then exit 20; else printf "guarded\\n"; fi\n'
    )

    result = _run_wizard_library(
        tmp_path, body, cwd=repository, script_directory=repository
    )

    assert result.returncode == 0, result.stderr
    assert "guarded" in result.stdout
    assert env_file.read_text(encoding="utf-8") == "API_TOKEN='old-value'\n"
    assert "synthetic-secret" not in result.stdout + result.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows Bash/DrvFS path is required")
def test_write_env_rejects_drvfs_backed_external_file(tmp_path: Path) -> None:
    environment_file = tmp_path / "credentials.env"
    bash_path = f"/mnt/{environment_file.drive[0].lower()}{environment_file.as_posix()[2:]}"
    body = (
        'git_root="$(mktemp -d /tmp/wizard-repository.XXXXXX)"\n'
        'trap \'rm -f "$ENV_FILE"; rmdir "$git_root"\' EXIT\n'
        'git() { printf "%s\\n" "$git_root"; }\n'
        f"ENV_FILE={shlex.quote(bash_path)}\n"
        'TEST_SECRET="synthetic-secret"\n'
        'write_env "API_TOKEN" "$TEST_SECRET"\n'
    )

    result = _run_wizard_library(tmp_path, body, cwd=tmp_path)

    assert result.returncode != 0
    assert not environment_file.exists()
    assert "synthetic-secret" not in result.stdout + result.stderr


def test_set_secret_requires_confirmation_and_explicit_repository(
    tmp_path: Path,
) -> None:
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    gh_stub = (
        'GH_CALLS="capture/calls.txt"\n'
        'GH_VALUE="capture/value.txt"\n'
        'TEST_SECRET="synthetic-secret"\n'
        "gh() {\n"
        "  printf '%s\\n' \"$*\" >> \"$GH_CALLS\"\n"
        "  if [[ \"$1 $2\" == 'secret set' ]]; then cat > \"$GH_VALUE\"; fi\n"
        "}\n"
        "set_secret owner/repo API_TOKEN \"$TEST_SECRET\"\n"
    )
    result = _run_wizard_library(
        tmp_path,
        gh_stub,
        cwd=tmp_path,
        input_text="n\n",
    )

    assert result.returncode == 0, result.stderr
    calls = (capture_dir / "calls.txt").read_text(encoding="utf-8").splitlines()
    assert calls == ["auth status"]
    assert not (capture_dir / "value.txt").exists()
    assert "synthetic-secret" not in result.stdout + result.stderr


def test_set_secret_writes_only_after_repo_specific_confirmation(
    tmp_path: Path,
) -> None:
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    gh_stub = (
        'GH_CALLS="capture/calls.txt"\n'
        'GH_VALUE="capture/value.txt"\n'
        'TEST_SECRET="synthetic-secret"\n'
        'confirm() { return 0; }\n'
        "gh() {\n"
        "  printf '%s\\n' \"$*\" >> \"$GH_CALLS\"\n"
        "  if [[ \"$1 $2\" == 'secret set' ]]; then cat > \"$GH_VALUE\"; fi\n"
        "}\n"
        "set_secret owner/repo API_TOKEN \"$TEST_SECRET\"\n"
    )
    result = _run_wizard_library(
        tmp_path,
        gh_stub,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    calls = (capture_dir / "calls.txt").read_text(encoding="utf-8").splitlines()
    assert calls == ["auth status", "secret set API_TOKEN --repo owner/repo"]
    assert (capture_dir / "value.txt").read_text(encoding="utf-8") == "synthetic-secret"
    assert "synthetic-secret" not in result.stdout + result.stderr


def test_set_secret_rejects_piped_confirmation_without_terminal(
    tmp_path: Path,
) -> None:
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    gh_stub = (
        'GH_CALLS="capture/calls.txt"\n'
        'GH_VALUE="capture/value.txt"\n'
        'TEST_SECRET="synthetic-secret"\n'
        "gh() {\n"
        "  printf '%s\\n' \"$*\" >> \"$GH_CALLS\"\n"
        "  if [[ \"$1 $2\" == 'secret set' ]]; then cat > \"$GH_VALUE\"; fi\n"
        "}\n"
        "set_secret owner/repo API_TOKEN \"$TEST_SECRET\"\n"
    )
    result = _run_wizard_library(
        tmp_path,
        gh_stub,
        cwd=tmp_path,
        input_text="y\n",
    )

    assert result.returncode == 0, result.stderr
    calls = (capture_dir / "calls.txt").read_text(encoding="utf-8").splitlines()
    assert calls == ["auth status"]
    assert not (capture_dir / "value.txt").exists()
    assert "synthetic-secret" not in result.stdout + result.stderr


def test_set_var_sends_value_on_stdin_after_confirmation(
    tmp_path: Path,
) -> None:
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    gh_stub = (
        'GH_CALLS="capture/calls.txt"\n'
        'GH_VALUE="capture/value.txt"\n'
        'TEST_VALUE="public-build-label"\n'
        'confirm() { return 0; }\n'
        "gh() {\n"
        "  printf '%s\\n' \"$*\" >> \"$GH_CALLS\"\n"
        "  if [[ \"$1 $2\" == 'variable set' ]]; then cat > \"$GH_VALUE\"; fi\n"
        "}\n"
        "set_var owner/repo BUILD_LABEL \"$TEST_VALUE\"\n"
    )
    result = _run_wizard_library(
        tmp_path,
        gh_stub,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    calls = (capture_dir / "calls.txt").read_text(encoding="utf-8").splitlines()
    assert calls == ["auth status", "variable set BUILD_LABEL --repo owner/repo"]
    assert (capture_dir / "value.txt").read_text(encoding="utf-8") == "public-build-label"
    assert "public-build-label" not in "\n".join(calls) + result.stdout + result.stderr


def test_set_var_rejects_piped_confirmation_without_terminal(
    tmp_path: Path,
) -> None:
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    gh_stub = (
        'GH_CALLS="capture/calls.txt"\n'
        'GH_VALUE="capture/value.txt"\n'
        'TEST_VALUE="public-build-label"\n'
        "gh() {\n"
        "  printf '%s\\n' \"$*\" >> \"$GH_CALLS\"\n"
        "  if [[ \"$1 $2\" == 'variable set' ]]; then cat > \"$GH_VALUE\"; fi\n"
        "}\n"
        "set_var owner/repo BUILD_LABEL \"$TEST_VALUE\"\n"
    )
    result = _run_wizard_library(
        tmp_path,
        gh_stub,
        cwd=tmp_path,
        input_text="y\n",
    )

    assert result.returncode == 0, result.stderr
    calls = (capture_dir / "calls.txt").read_text(encoding="utf-8").splitlines()
    assert calls == ["auth status"]
    assert not (capture_dir / "value.txt").exists()
    assert "public-build-label" not in "\n".join(calls) + result.stdout + result.stderr


def test_sample_wizard_passes_explicit_repository_to_secret_writer(
    tmp_path: Path,
) -> None:
    result = _run_wizard_stages(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "set-secret-call.txt").read_text(encoding="utf-8").splitlines() == [
        "3",
        "owner/repo STRIPE_SECRET_KEY synthetic-secret",
    ]