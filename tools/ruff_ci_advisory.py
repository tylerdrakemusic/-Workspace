from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


RUFF_VERSION = "0.17.2"
SCAN_SCOPE = (
    "All non-ignored Python .py files under the repository root; Ruff defaults "
    "and ruff.toml exclude environments, caches, .worktrees, tmp, and output. "
    "Non-Python files, including databases, are not scanned."
)
FORMAT_COUNT_PATTERN = re.compile(r"(?m)^(\d+) files? would be reformatted\b")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None
    stdout: str = ""
    stderr: str = ""


def _run_command(command: Sequence[str], cwd: Path) -> CommandResult:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            check=False,
            cwd=cwd,
            encoding="utf-8",
            errors="replace",
            text=True,
        )
    except OSError as error:
        return CommandResult(returncode=None, stderr=str(error))
    return CommandResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _check_count(stdout: str) -> int | None:
    try:
        findings = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    return len(findings) if isinstance(findings, list) else None


def _format_count(result: CommandResult) -> int | None:
    output = f"{result.stdout}\n{result.stderr}"
    match = FORMAT_COUNT_PATTERN.search(output)
    if match:
        return int(match.group(1))
    return 0 if result.returncode == 0 else None


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _write_local_reports(
    local_output_dir: Path,
    report: dict[str, object],
    version_result: CommandResult,
    check_result: CommandResult,
    format_result: CommandResult,
) -> None:
    raw_files = {
        "ruff-version.stdout.txt": version_result.stdout,
        "ruff-version.stderr.txt": version_result.stderr,
        "ruff-check.json": check_result.stdout,
        "ruff-check.stderr.txt": check_result.stderr,
        "ruff-format.diff.txt": format_result.stdout,
        "ruff-format.stderr.txt": format_result.stderr,
    }
    for filename, content in raw_files.items():
        _write_atomic(local_output_dir / filename, content)

    local_report = {
        **report,
        "raw_tool_errors": {
            "ruff_version": version_result.stderr,
            "ruff_check": check_result.stderr,
            "ruff_format": format_result.stderr,
        },
    }
    _write_atomic(
        local_output_dir / "summary.json",
        json.dumps(local_report, indent=2, ensure_ascii=False) + "\n",
    )


def _render_step_summary(report: dict[str, object]) -> str:
    finding_counts = report["finding_counts"]
    command_exit_codes = report["command_exit_codes"]
    tool_errors = report["tool_errors"]
    assert isinstance(finding_counts, dict)
    assert isinstance(command_exit_codes, dict)
    assert isinstance(tool_errors, dict)

    check_count = finding_counts["ruff_check"]
    format_count = finding_counts["ruff_format"]
    check_text = "unavailable" if check_count is None else str(check_count)
    format_text = "unavailable" if format_count is None else str(format_count)
    config = report["config"]
    assert isinstance(config, dict)
    config_hash = config["sha256"] or "unavailable"
    elapsed_seconds = report["elapsed_seconds"]
    assert isinstance(elapsed_seconds, (int, float))

    return "\n".join(
        [
            "## Ruff advisory",
            "",
            f"- Repository: `{report['repository']}`",
            f"- Scanned commit: `{report['commit']}`",
            f"- Ruff pinned version: `{report['ruff_version']}`",
            f"- Config: `{config['path']}` SHA-256 `{config_hash}`",
            f"- Scope: {report['scan_scope']}",
            f"- Elapsed: {elapsed_seconds:.3f} seconds",
            f"- Findings: `ruff check` {check_text}; `ruff format --check` {format_text}",
            "- Command exit codes: "
            f"install={command_exit_codes['ruff_install']}, "
            f"version={command_exit_codes['ruff_version']}, "
            f"check={command_exit_codes['ruff_check']}, "
            f"format={command_exit_codes['ruff_format_check']}",
            "- Tool errors: "
            f"install={tool_errors['ruff_install']}, "
            f"version={tool_errors['ruff_version']}, "
            f"check={tool_errors['ruff_check']}, "
            f"format={tool_errors['ruff_format']}",
            "- Advisory only: findings and Ruff command errors do not gate CI.",
            "",
        ]
    )


def _append_step_summary(path: Path, content: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    _write_atomic(path, existing + content)


def _installation_exit_code() -> int | None:
    value = os.environ.get("RUFF_INSTALL_EXIT_CODE")
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _build_report(
    config_path: Path,
    repository: str,
    commit: str,
    elapsed_seconds: float,
    installation_exit_code: int | None,
    version_result: CommandResult,
    check_result: CommandResult,
    format_result: CommandResult,
) -> dict[str, object]:
    check_findings = _check_count(check_result.stdout)
    format_findings = _format_count(format_result)
    try:
        config_hash: str | None = hashlib.sha256(config_path.read_bytes()).hexdigest()
    except OSError:
        config_hash = None

    version_ok = (
        version_result.returncode == 0
        and version_result.stdout.strip() == f"ruff {RUFF_VERSION}"
    )
    check_ok = check_result.returncode in (0, 1) and check_findings is not None
    format_ok = format_result.returncode in (0, 1) and format_findings is not None
    safe_repository = repository if REPOSITORY_PATTERN.fullmatch(repository) else "local"
    safe_commit = commit if re.fullmatch(r"[0-9a-f]{40,64}", commit) else "unavailable"

    return {
        "repository": safe_repository,
        "commit": safe_commit,
        "ruff_version": RUFF_VERSION,
        "config": {"path": config_path.name, "sha256": config_hash},
        "scan_scope": SCAN_SCOPE,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "finding_counts": {
            "ruff_check": check_findings,
            "ruff_format": format_findings,
        },
        "command_exit_codes": {
            "ruff_install": installation_exit_code,
            "ruff_version": version_result.returncode,
            "ruff_check": check_result.returncode,
            "ruff_format_check": format_result.returncode,
        },
        "tool_errors": {
            "ruff_install": installation_exit_code not in (None, 0),
            "ruff_version": not version_ok,
            "ruff_check": not check_ok,
            "ruff_format": not format_ok,
        },
    }


def _run_id() -> str:
    github_run_id = os.environ.get("GITHUB_RUN_ID")
    github_run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    if github_run_id:
        return f"{github_run_id}-{github_run_attempt}"
    return f"local-{os.getpid()}-{time.time_ns()}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-path", default="ruff.toml")
    parser.add_argument("--local-output-dir")
    parser.add_argument("--ci-output-dir")
    parser.add_argument("--step-summary")
    args = parser.parse_args(argv)

    run_id = _run_id()
    local_output_dir = Path(
        args.local_output_dir
        or os.environ.get("RUFF_ADVISORY_LOCAL_DIR")
        or PROJECT_ROOT / "tmp" / "ruff-advisory-local" / run_id
    )
    ci_output_dir = Path(
        args.ci_output_dir
        or os.environ.get("RUFF_ADVISORY_CI_DIR")
        or PROJECT_ROOT / "tmp" / "ruff-advisory-ci" / run_id
    )
    config_path = Path(args.config_path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    summary_path_value = args.step_summary or os.environ.get("GITHUB_STEP_SUMMARY")

    try:
        ruff_command = [sys.executable, "-m", "ruff"]
        started = time.perf_counter()
        version_result = _run_command(ruff_command + ["--version"], PROJECT_ROOT)
        check_result = _run_command(
            ruff_command + ["check", "--config", str(config_path), "--output-format=json", "."],
            PROJECT_ROOT,
        )
        format_result = _run_command(
            ruff_command + ["format", "--config", str(config_path), "--check", "--diff", "."],
            PROJECT_ROOT,
        )
        elapsed_seconds = time.perf_counter() - started
        git_result = _run_command(["git", "rev-parse", "HEAD"], PROJECT_ROOT)
        commit = git_result.stdout.strip() if git_result.returncode == 0 else "unavailable"
        report = _build_report(
            config_path=config_path,
            repository=os.environ.get("GITHUB_REPOSITORY", "local"),
            commit=commit,
            elapsed_seconds=elapsed_seconds,
            installation_exit_code=_installation_exit_code(),
            version_result=version_result,
            check_result=check_result,
            format_result=format_result,
        )
        _write_local_reports(
            local_output_dir,
            report,
            version_result,
            check_result,
            format_result,
        )
        artifact_path = ci_output_dir / "summary.json"
        _write_atomic(
            artifact_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        step_summary = _render_step_summary(report)
        if summary_path_value:
            _append_step_summary(Path(summary_path_value), step_summary)
        print(step_summary, end="")
    except Exception:
        print(
            "Ruff advisory report generation failed; CI remains advisory.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())