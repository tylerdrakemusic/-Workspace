import json
import os
import shutil
import socket
import subprocess
import textwrap
import time
from pathlib import Path
from typing import cast
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from pytest_bdd import given, scenarios, then, when

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = PROJECT_ROOT / "tools" / "start_trade_gate.ps1"
WORKER_ENVIRONMENT_KEYS = (
    "SIGMACAPITAL_WORKER_DEPLOYMENT_ROOT",
    "SIGMACAPITAL_WORKER_STATUS_PATH",
    "SIGMACAPITAL_WORKER_RESTART_ENABLED",
)

scenarios("trade_gate_launch_settings.feature")


def _prepare_project_root(tmp_path: Path, project_name: str) -> dict[str, object]:
    project_root = tmp_path / project_name
    source = project_root / "src" / "utils" / "trade_gate.py"
    source.parent.mkdir(parents=True)
    capture_path = tmp_path / "child-environment.json"
    program_data = tmp_path / "ProgramData"
    source.write_text(
        textwrap.dedent(
            """
            import json
            import os
            from http.server import BaseHTTPRequestHandler, HTTPServer
            from pathlib import Path

            names = (
                "TRADE_GATE_PORT",
                "SIGMACAPITAL_WORKER_DEPLOYMENT_ROOT",
                "SIGMACAPITAL_WORKER_STATUS_PATH",
                "SIGMACAPITAL_WORKER_RESTART_ENABLED",
            )

            class HealthHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    body = b'{"scheduler_health":"available"}'
                    self.send_response(200 if self.path == "/health" else 404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, format, *args):
                    pass

            server = HTTPServer(("127.0.0.1", int(os.environ["TRADE_GATE_PORT"])), HealthHandler)
            server.timeout = float(os.environ.get("TRADE_GATE_TEST_TIMEOUT", "10"))
            Path(os.environ["TRADE_GATE_PROBE_FILE"]).write_text(
                json.dumps({name: os.environ.get(name) for name in names}),
                encoding="utf-8",
            )
            server.handle_request()
            server.server_close()
            """
        ),
        encoding="utf-8",
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    supervisor_environment = {
        name: os.environ.get(name) for name in WORKER_ENVIRONMENT_KEYS
    }
    launch_environment = os.environ.copy()
    for name in WORKER_ENVIRONMENT_KEYS:
        launch_environment.pop(name, None)
    for name in tuple(launch_environment):
        if name.casefold() == "programdata":
            launch_environment.pop(name)
    launch_environment["ProgramData"] = str(program_data)
    launch_environment["TRADE_GATE_PROBE_FILE"] = str(capture_path)
    return {
        "project_root": project_root,
        "capture_path": capture_path,
        "program_data": program_data,
        "port": port,
        "launch_environment": launch_environment,
        "supervisor_environment": supervisor_environment,
    }


@given("a disposable SigmaCapital project root", target_fixture="launcher_context")
def sigma_capital_project_root(tmp_path: Path) -> dict[str, object]:
    return _prepare_project_root(tmp_path, chr(0x03A3) + "Capital")


@given("a disposable non-SigmaCapital project root", target_fixture="launcher_context")
def other_project_root(tmp_path: Path) -> dict[str, object]:
    return _prepare_project_root(tmp_path, "OtherProject")


@when("the real Trade Gate launcher starts a fresh child", target_fixture="launch_result")
def launch_fresh_child(launcher_context: dict[str, object]) -> dict[str, object]:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("The Trade Gate launcher integration scenario requires Windows PowerShell")

    project_root = cast(Path, launcher_context["project_root"])
    port = cast(int, launcher_context["port"])
    process = subprocess.Popen(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LAUNCHER),
            "-Port",
            str(port),
            "-ProjectRoot",
            str(project_root),
        ],
        cwd=project_root,
        env=cast(dict[str, str], launcher_context["launch_environment"]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    health_status = None
    health_body = None
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline and process.poll() is None:
            try:
                with urlopen(f"http://127.0.0.1:{port}/health", timeout=0.25) as response:
                    health_status = response.status
                    health_body = json.load(response)
                    break
            except (OSError, TimeoutError, URLError):
                time.sleep(0.05)
        output, _ = process.communicate(timeout=12)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()

    capture_path = cast(Path, launcher_context["capture_path"])
    child_environment = (
        json.loads(capture_path.read_text(encoding="utf-8"))
        if capture_path.exists()
        else {}
    )
    return {
        "child_environment": child_environment,
        "health_status": health_status,
        "health_body": health_body,
        "returncode": process.returncode,
        "output": output,
    }


@then("the child inherits SigmaCapital worker settings and Scheduler Health responds")
def sigma_capital_launch_has_worker_settings(
    launcher_context: dict[str, object], launch_result: dict[str, object]
) -> None:
    project_root = cast(Path, launcher_context["project_root"])
    program_data = cast(Path, launcher_context["program_data"])
    child_environment = cast(dict[str, str | None], launch_result["child_environment"])

    assert child_environment["SIGMACAPITAL_WORKER_DEPLOYMENT_ROOT"] == str(
        project_root / ".worktrees" / "SigmaCapitalIntentWorker"
    ), launch_result["output"]
    assert child_environment["SIGMACAPITAL_WORKER_STATUS_PATH"] == str(
        program_data / "SigmaCapital" / "worker-status.json"
    ), launch_result["output"]
    assert child_environment["SIGMACAPITAL_WORKER_RESTART_ENABLED"] == "1"
    assert launch_result["health_status"] == 200, launch_result["output"]
    assert launch_result["health_body"] == {"scheduler_health": "available"}
    assert launch_result["returncode"] == 0, launch_result["output"]
    assert {
        name: os.environ.get(name) for name in WORKER_ENVIRONMENT_KEYS
    } == launcher_context["supervisor_environment"]


@then("the child does not inherit SigmaCapital worker settings")
def non_sigma_capital_launch_has_no_worker_settings(
    launcher_context: dict[str, object], launch_result: dict[str, object]
) -> None:
    child_environment = cast(dict[str, str | None], launch_result["child_environment"])

    assert all(child_environment.get(name) is None for name in WORKER_ENVIRONMENT_KEYS), (
        launch_result["output"]
    )
    assert launch_result["health_status"] == 200, launch_result["output"]
    assert launch_result["health_body"] == {"scheduler_health": "available"}
    assert launch_result["returncode"] == 0, launch_result["output"]
    assert {
        name: os.environ.get(name) for name in WORKER_ENVIRONMENT_KEYS
    } == launcher_context["supervisor_environment"]


@given(
    "SigmaCapital and another project root are prepared",
    target_fixture="sequential_launcher_context",
)
def prepare_sequential_launcher_context(tmp_path: Path) -> dict[str, object]:
    sigma = _prepare_project_root(tmp_path / "sigma-fixture", "ΣCapital")
    other = _prepare_project_root(tmp_path / "other-fixture", "OtherProject")
    launch_environment = cast(dict[str, str], sigma["launch_environment"])
    for index, name in enumerate(WORKER_ENVIRONMENT_KEYS):
        launch_environment[name] = f"caller-worker-setting-{index}"
    original_worker_environment = {
        name: launch_environment.get(name) for name in WORKER_ENVIRONMENT_KEYS
    }
    return {
        "sigma": sigma,
        "other": other,
        "original_worker_environment": original_worker_environment,
        "supervisor_environment": sigma["supervisor_environment"],
    }


@when(
    "both launch sequentially from one PowerShell process",
    target_fixture="sequential_launch_result",
)
def launch_projects_sequentially(
    sequential_launcher_context: dict[str, object], tmp_path: Path
) -> dict[str, object]:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("The sequential launcher scenario requires Windows PowerShell")

    sigma = cast(dict[str, object], sequential_launcher_context["sigma"])
    other = cast(dict[str, object], sequential_launcher_context["other"])
    sigma_root = cast(Path, sigma["project_root"])
    other_root = cast(Path, other["project_root"])
    sigma_capture = cast(Path, sigma["capture_path"])
    other_capture = cast(Path, other["capture_path"])
    sigma_port = cast(int, sigma["port"])
    other_port = cast(int, other["port"])

    def quote(value: object) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    names = ",".join(quote(name) for name in WORKER_ENVIRONMENT_KEYS)
    script = tmp_path / "run-sequential-launches.ps1"
    script.write_text(
        "\n".join(
            (
                "$ErrorActionPreference = 'Stop'",
                "$env:TRADE_GATE_TEST_TIMEOUT = '0.05'",
                f"$env:TRADE_GATE_PROBE_FILE = {quote(sigma_capture)}",
                f"& {quote(LAUNCHER)} -Port {sigma_port} -ProjectRoot {quote(sigma_root)}",
                "$after_sigma = @{}",
                f"foreach ($name in @({names})) {{ $after_sigma[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }}",
                f"$env:TRADE_GATE_PROBE_FILE = {quote(other_capture)}",
                f"& {quote(LAUNCHER)} -Port {other_port} -ProjectRoot {quote(other_root)}",
                "$after_other = @{}",
                f"foreach ($name in @({names})) {{ $after_other[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }}",
                "[pscustomobject]@{ after_sigma = $after_sigma; after_other = $after_other } | ConvertTo-Json -Compress",
            )
        ),
        encoding="utf-8-sig",
    )
    completed = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        cwd=tmp_path,
        env=cast(dict[str, str], sigma["launch_environment"]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    shell_state = {}
    if completed.returncode == 0:
        shell_state = json.loads(completed.stdout.splitlines()[-1])
    return {
        "child_sigma": json.loads(sigma_capture.read_text(encoding="utf-8"))
        if sigma_capture.exists()
        else {},
        "child_other": json.loads(other_capture.read_text(encoding="utf-8"))
        if other_capture.exists()
        else {},
        "shell_state": shell_state,
        "returncode": completed.returncode,
        "output": completed.stdout + completed.stderr,
    }


@then("the later child and launcher shell do not retain the SigmaCapital worker settings")
def sequential_launch_has_no_worker_environment_leak(
    sequential_launcher_context: dict[str, object],
    sequential_launch_result: dict[str, object],
) -> None:
    sigma_child = cast(dict[str, str | None], sequential_launch_result["child_sigma"])
    other_child = cast(dict[str, str | None], sequential_launch_result["child_other"])
    shell_state = cast(dict[str, dict[str, str | None]], sequential_launch_result["shell_state"])
    original_worker_environment = cast(
        dict[str, str | None], sequential_launcher_context["original_worker_environment"]
    )
    supervisor_environment = cast(
        dict[str, str | None], sequential_launcher_context["supervisor_environment"]
    )

    assert sequential_launch_result["returncode"] == 0, sequential_launch_result["output"]
    assert sigma_child["SIGMACAPITAL_WORKER_RESTART_ENABLED"] == "1"
    assert {
        name: other_child.get(name) for name in WORKER_ENVIRONMENT_KEYS
    } == original_worker_environment
    assert shell_state["after_sigma"] == original_worker_environment
    assert shell_state["after_other"] == original_worker_environment
    assert {
        name: os.environ.get(name) for name in WORKER_ENVIRONMENT_KEYS
    } == supervisor_environment
