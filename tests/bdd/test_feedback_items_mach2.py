import hashlib
import json
import os
import sqlite3
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from pytest_bdd import given, scenarios, then, when
from tests.test_coordination_mcp_server import _run_fr_cli_child_with_open_server_stdin
from tests.test_paired_revision_resolution_workflow import (
    PEER_REPOSITORY,
    PR_SHA,
    MAIN_SHA,
    _run_peer_setup,
)
from tests.test_agent_frontmatter_integrity import _prepare_scan_workspace, afi

PROJECT_ROOT = Path(__file__).resolve().parents[2]

scenarios("feedback_items_mach2.feature")


@given("the producer branch head is available", target_fixture="producer_branch_case")
def producer_branch_head_available() -> tuple[str, bool]:
    return "feature/feedback-items-mach-2", True


@when(
    "consumer CI resolves the producer peer revision",
    target_fixture="producer_peer_setup",
)
def resolve_available_producer_branch(
    tmp_path: Path,
    producer_branch_case: tuple[str, bool],
) -> tuple[subprocess.CompletedProcess[str], list[str], str, bool]:
    branch, _ = producer_branch_case
    return _run_peer_setup(
        tmp_path,
        event_name="pull_request",
        head_ref=branch,
    )


@then("it checks out the exact producer head before behavior tests")
def producer_peer_head_is_checked_out(
    producer_peer_setup: tuple[subprocess.CompletedProcess[str], list[str], str, bool],
) -> None:
    result, calls, summary, behavior_ran = producer_peer_setup

    assert result.returncode == 0, result.stderr
    assert f"ls-remote https://github.com/{PEER_REPOSITORY}.git refs/heads/feature/feedback-items-mach-2" in calls
    assert (
        f"-C ai-manifest-contract fetch --depth=1 "
        f"https://github.com/{PEER_REPOSITORY}.git {PR_SHA}"
    ) in calls
    assert "-C ai-manifest-contract checkout --detach FETCH_HEAD" in calls
    assert f"Checked-out SHA: {PR_SHA}" in summary
    assert not any(call.endswith("refs/heads/main") for call in calls)
    assert behavior_ran


@given(
    "the consumer pull request has no matching producer branch",
    target_fixture="missing_producer_branch",
)
def missing_producer_branch() -> str:
    return "feature/producer-branch-missing"


@when(
    "consumer CI resolves a missing producer branch",
    target_fixture="missing_producer_setup",
)
def resolve_missing_producer_branch(
    tmp_path: Path,
    missing_producer_branch: str,
) -> tuple[subprocess.CompletedProcess[str], list[str], str, bool]:
    return _run_peer_setup(
        tmp_path,
        event_name="pull_request",
        head_ref=missing_producer_branch,
        pr_found=False,
    )


@then("it uses peer main for the unpaired consumer PR")
def missing_producer_branch_uses_unpaired_baseline(
    missing_producer_setup: tuple[subprocess.CompletedProcess[str], list[str], str, bool],
    missing_producer_branch: str,
) -> None:
    result, calls, summary, behavior_ran = missing_producer_setup

    assert result.returncode == 0, result.stderr
    assert any(f"refs/heads/{missing_producer_branch}" in call for call in calls)
    assert any(call.endswith("refs/heads/main") for call in calls)
    assert f"-C ai-manifest-contract fetch --depth=1 https://github.com/{PEER_REPOSITORY}.git {MAIN_SHA}" in calls
    assert "Selected ref: main (unpaired consumer PR)" in summary
    assert f"Checked-out SHA: {MAIN_SHA}" in summary
    assert behavior_ran


@given("an isolated QA run needs to record two proof artifacts", target_fixture="qa_proof_run")
def isolated_qa_run(tmp_path: Path) -> tuple[Path, dict[str, str], str]:
    source_utils = PROJECT_ROOT / "src" / "utils"
    isolated_utils = tmp_path / "src" / "utils"
    shutil.copytree(source_utils, isolated_utils)

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONUTF8"] = "1"
    environment["WORKSPACE_DB_KEY"] = f"proof-serialization-{uuid.uuid4().hex}"
    start = subprocess.run(
        [sys.executable, str(isolated_utils / "perf_cli.py"), "start", "proof-serialization-test"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert start.returncode == 0, start.stderr
    return isolated_utils, environment, start.stdout.strip()


@when("the QA workflow starts overlapping proof CLI writers", target_fixture="qa_proof_results")
def run_overlapping_qa_proof_writers(
    tmp_path: Path,
    qa_proof_run: tuple[Path, dict[str, str], str],
) -> tuple[Path, dict[str, str], str, list[tuple[int, str, str]]]:
    isolated_utils, environment, run_id = qa_proof_run
    gate_directory = tmp_path / "proof-writer-gates"
    gate_directory.mkdir()
    slow_writer = """
import os
import sys
import time
from pathlib import Path
utils_dir, gate_dir, *cli_args = sys.argv[1:]
gate_dir = Path(gate_dir)
sys.path.insert(0, utils_dir)
import proof_cli
real_connect = proof_cli._connect
class SlowConnection:
    def __init__(self, connection):
        self.connection = connection
    def __getattr__(self, name):
        return getattr(self.connection, name)
    def execute(self, statement, parameters=()):
        if statement.lstrip().upper().startswith('INSERT INTO PROOF_ARTIFACTS'):
            (gate_dir / f"inserting-{os.getpid()}").touch()
            deadline = time.monotonic() + 0.5
            while len(list(gate_dir.glob('inserting-*'))) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.connection.execute('BEGIN IMMEDIATE')
            time.sleep(2.0)
        return self.connection.execute(statement, parameters)
proof_cli._connect = lambda: SlowConnection(real_connect())
sys.argv = ['proof_cli.py', *cli_args]
(gate_dir / f"started-{os.getpid()}").touch()
deadline = time.monotonic() + 10
while len(list(gate_dir.glob('started-*'))) < 2 and time.monotonic() < deadline:
    time.sleep(0.01)
if len(list(gate_dir.glob('started-*'))) < 2:
    raise RuntimeError('proof writer start gate timed out')
proof_cli.main()
"""
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                slow_writer,
                str(isolated_utils),
                str(gate_directory),
                "record",
                run_id,
                "⊕workspace-qa",
                "test_pass",
                description,
            ],
            cwd=tmp_path,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for description in ("first QA artifact", "second QA artifact")
    ]
    results = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=15)
        results.append((process.returncode, stdout, stderr))
    return isolated_utils, environment, run_id, results


@then("both writes succeed and each proof is readable from the report")
def qa_proofs_are_persisted_and_readable(
    qa_proof_results: tuple[Path, dict[str, str], str, list[tuple[int, str, str]]],
) -> None:
    isolated_utils, environment, run_id, results = qa_proof_results
    assert all(code == 0 for code, _, _ in results), results

    report = subprocess.run(
        [sys.executable, str(isolated_utils / "proof_cli.py"), "report", run_id],
        cwd=isolated_utils.parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert report.returncode == 0, report.stderr
    assert "Proofs: 2" in report.stdout
    assert report.stdout.count("first QA artifact") == 1
    assert report.stdout.count("second QA artifact") == 1


@given("the coordination FR CLI subprocess seam is available", target_fixture="coordination_server")
def coordination_server_module() -> ModuleType:
    from src.utils import coordination_mcp_server

    return coordination_mcp_server


@when(
    "setup, timeout, and CLI operation failures occur",
    target_fixture="coordination_failure_types",
)
def coordination_failure_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    coordination_server: ModuleType,
) -> dict[str, str]:
    server = coordination_server
    python_executable = server.sys.executable
    failures: dict[str, str] = {}

    monkeypatch.setattr(server.sys, "executable", str(tmp_path / "missing-python.exe"))
    try:
        server._run_fr_cli("fr.get", {"fr_id": "FR-TEST-SETUP"})
    except Exception as error:
        failures["setup"] = type(error).__name__

    command_script = tmp_path / "failing_fr_cli.py"
    command_script.write_text("raise SystemExit(7)\n", encoding="utf-8")
    monkeypatch.setattr(server.sys, "executable", python_executable)
    monkeypatch.setattr(server, "FR_CLI_PATH", command_script)
    try:
        server._run_fr_cli("fr.get", {"fr_id": "FR-TEST-OPERATION"})
    except Exception as error:
        failures["operation"] = type(error).__name__

    timeout_script = tmp_path / "slow_fr_cli.py"
    timeout_script.write_text("import time\ntime.sleep(1)\n", encoding="utf-8")
    monkeypatch.setattr(server, "FR_CLI_PATH", timeout_script)
    real_run = server.subprocess.run

    def bounded_run(*args, **kwargs):
        kwargs["timeout"] = 0.05
        return real_run(*args, **kwargs)

    monkeypatch.setattr(server.subprocess, "run", bounded_run)
    try:
        server._run_fr_cli("fr.get", {"fr_id": "FR-TEST-TIMEOUT"})
    except Exception as error:
        failures["timeout"] = type(error).__name__

    return failures


@then("each failure is reported as its own category")
def coordination_failures_are_classified(
    coordination_failure_types: dict[str, str],
) -> None:
    assert coordination_failure_types == {
        "setup": "FrCliSetupError",
        "timeout": "FrCliTimeoutError",
        "operation": "FrCliOperationError",
    }


@given(
    "the coordinator request leaves its stdio input pipe open",
    target_fixture="open_stdin_probe_directory",
)
def open_stdin_probe_directory(tmp_path: Path) -> Path:
    return tmp_path


@when(
    "the coordinator launches a CLI child that reads stdin",
    target_fixture="fr_cli_stdin_probe",
)
def invoke_fr_cli_with_open_server_stdin(
    open_stdin_probe_directory: Path,
) -> tuple[int, str, str]:
    return _run_fr_cli_child_with_open_server_stdin(open_stdin_probe_directory)


@then("the child receives EOF and completes before its deadline")
def fr_cli_child_receives_eof(
    fr_cli_stdin_probe: tuple[int, str, str],
) -> None:
    return_code, output, error_output = fr_cli_stdin_probe
    assert return_code == 0, error_output
    assert output.strip() == "stdin-eof"


@given("an identical completed SCAN TODO exists", target_fixture="completed_scan_case")
def completed_scan_todo_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, int]:
    manifest_db = _prepare_scan_workspace(tmp_path, monkeypatch)
    with sqlite3.connect(str(manifest_db)) as conn:
        cursor = conn.execute(
            "INSERT INTO todos (project, source, text, done, created_at) "
            "VALUES (?, ?, ?, 1, ?)",
            (
                afi.SCAN_TODO_PROJECT,
                afi.SCAN_TODO_SOURCE,
                afi.SCAN_TODO_TEXT,
                "2026-01-01T00:00:00+00:00",
            ),
        )
        completed_todo_id = int(cursor.lastrowid)
    return manifest_db, completed_todo_id


@when("the weekly integrity scan runs", target_fixture="weekly_scan_result")
def run_weekly_integrity_scan(
    completed_scan_case: tuple[Path, int],
) -> dict[str, object]:
    return afi.run_agent_frontmatter_integrity(fr_id="FR-TEST")


@then("it reuses the completed TODO and finishes without duplicate rows")
def weekly_scan_reuses_completed_todo(
    completed_scan_case: tuple[Path, int],
    weekly_scan_result: dict[str, object],
) -> None:
    manifest_db, completed_todo_id = completed_scan_case
    assert weekly_scan_result["issues"] == 0
    assert weekly_scan_result["warnings"] == 1
    assert weekly_scan_result["todo_id"] == completed_todo_id
    with sqlite3.connect(str(manifest_db)) as conn:
        rows = conn.execute(
            "SELECT id, done FROM todos WHERE project=? AND source=? AND text=?",
            (afi.SCAN_TODO_PROJECT, afi.SCAN_TODO_SOURCE, afi.SCAN_TODO_TEXT),
        ).fetchall()
    assert rows == [(completed_todo_id, 1)]


def _prepare_integrity_project(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    project_root = tmp_path / "integrity-project"
    verifier_dir = project_root / ".github" / "!!☾⛧security"
    verifier_dir.mkdir(parents=True)
    shutil.copy2(
        PROJECT_ROOT / ".github" / "!!☾⛧security" / "update_manifest.py",
        verifier_dir / "update_manifest.py",
    )

    agent_file = project_root / ".github" / "agents" / "integrity-check.agent.md"
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text("# Integrity fixture\n", encoding="utf-8")

    target_file = project_root / ".github" / "skills" / "example" / "SKILL.md"
    target_file.parent.mkdir(parents=True)
    source_file = project_root / "external-sources" / "skills" / "example" / "SKILL.md"
    source_file.parent.mkdir(parents=True)
    source_content = "# External source fixture\n"
    source_file.write_text(source_content, encoding="utf-8")
    target_file.write_text(source_content, encoding="utf-8")

    tools_dir = project_root / "tools"
    tools_dir.mkdir()
    config_path = tools_dir / "skill-sync-config.json"
    config_path.write_text(
        json.dumps(
            {
                "destination": ".github/skills",
                "repos": [
                    {
                        "name": "fixture-source",
                        "path": "external-sources",
                        "skill_root": "skills",
                        "source_path": "example/SKILL.md",
                        "skills": ["example"],
                        "provenance": "external-source",
                        "source_policy": "required",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = {
        "generated_at": "2026-01-01T00:00:00Z",
        "generated_by": "update_manifest.py",
        "file_count": 2,
        "files": {
            ".github/agents/integrity-check.agent.md": hashlib.sha256(
                agent_file.read_bytes()
            ).hexdigest(),
            ".github/skills/example/SKILL.md": hashlib.sha256(
                target_file.read_bytes()
            ).hexdigest(),
        },
    }
    manifest_path = verifier_dir / "agent-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return project_root, target_file, source_file, config_path


@given("a project has clean declared external skill sources", target_fixture="integrity_project")
def clean_integrity_project(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    return _prepare_integrity_project(tmp_path)


@when(
    "the pre-write security gate verifies the project and a confirmed mismatch",
    target_fixture="integrity_gate_results",
)
def verify_clean_and_mismatched_project(
    integrity_project: tuple[Path, Path, Path, Path],
) -> tuple[
    subprocess.CompletedProcess[str],
    subprocess.CompletedProcess[str],
    subprocess.CompletedProcess[str],
    subprocess.CompletedProcess[str],
]:
    project_root, _, source_file, _ = integrity_project
    gate_script = PROJECT_ROOT / "src" / "utils" / "prewrite_security_gate.py"
    verifier_script = project_root / ".github" / "!!☾⛧security" / "update_manifest.py"

    canonical_clean = subprocess.run(
        [sys.executable, str(verifier_script), "--verify"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )
    clean = subprocess.run(
        [sys.executable, str(gate_script), "--repo-root", str(project_root)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )
    source_file.write_text("# Confirmed upstream source drift\n", encoding="utf-8")
    canonical_mismatch = subprocess.run(
        [sys.executable, str(verifier_script), "--verify"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )
    mismatch = subprocess.run(
        [sys.executable, str(gate_script), "--repo-root", str(project_root)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )
    return canonical_clean, clean, canonical_mismatch, mismatch


@then("clean integrity passes and confirmed mismatch blocks the write")
def clean_passes_and_mismatch_blocks(
    integrity_gate_results: tuple[
        subprocess.CompletedProcess[str],
        subprocess.CompletedProcess[str],
        subprocess.CompletedProcess[str],
        subprocess.CompletedProcess[str],
    ],
) -> None:
    canonical_clean, clean, canonical_mismatch, mismatch = integrity_gate_results
    assert canonical_clean.returncode == 0, canonical_clean.stderr
    assert "SOURCE MATCH" in canonical_clean.stdout
    assert clean.returncode == 0, clean.stderr
    assert "SOURCE MATCH" in clean.stdout
    assert canonical_mismatch.returncode == 0
    assert "SOURCE DRIFT (approval required)" in canonical_mismatch.stdout
    assert mismatch.returncode == 1
    assert "BLOCKED" in mismatch.stderr


@given(
    "the canonical verifier encounters an operational error",
    target_fixture="operational_error_project",
)
def operational_error_project(tmp_path: Path) -> Path:
    project_root, _, _, config_path = _prepare_integrity_project(tmp_path)
    config_path.write_text("{invalid json", encoding="utf-8")
    return project_root


@when(
    "the pre-write security gate evaluates that failure",
    target_fixture="operational_gate_result",
)
def evaluate_operational_error(
    operational_error_project: Path,
) -> tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]]:
    gate_script = PROJECT_ROOT / "src" / "utils" / "prewrite_security_gate.py"
    verifier_script = operational_error_project / ".github" / "!!☾⛧security" / "update_manifest.py"
    canonical_result = subprocess.run(
        [sys.executable, str(verifier_script), "--verify"],
        cwd=operational_error_project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )
    gate_result = subprocess.run(
        [sys.executable, str(gate_script), "--repo-root", str(operational_error_project)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=10,
    )
    return canonical_result, gate_result


@then("the write remains allowed and a warning is emitted")
def operational_failure_fails_open(
    operational_gate_result: tuple[
        subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]
    ],
) -> None:
    canonical_result, gate_result = operational_gate_result
    assert canonical_result.returncode == 1
    assert gate_result.returncode == 0
    assert "WARNING" in gate_result.stderr
    assert "allowing write" in gate_result.stderr