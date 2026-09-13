from __future__ import annotations

import json
import http.client
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen
from urllib.request import Request

import pytest


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PORTAL_CONFIG = WORKSPACE_ROOT / "tools" / "portal_servers.json"
LAUNCH_PORTAL = WORKSPACE_ROOT / "tools" / "launch_portal.ps1"
OPEN_PORTAL = WORKSPACE_ROOT / "open_portal.ps1"
REGISTER_PROTOCOL = WORKSPACE_ROOT / "tools" / "register_portal_protocol.ps1"
RESTART_SERVERS = WORKSPACE_ROOT / "tools" / "restart_servers.ps1"
SUPERVISOR_SCRIPT = WORKSPACE_ROOT / "tools" / "portal_supervisor.py"
sys.path.insert(0, str(WORKSPACE_ROOT / "tools"))

import portal_supervisor as supervisor_module
import dashboard_portal
from portal_supervisor import ConfigurationError, PortalSupervisor, load_config


def _service(name: str, port: int) -> dict[str, object]:
    return {
        "name": name,
        "port": port,
        "cmd": f"server-{port}.exe --serve",
        "working_directory": f"C:\\services\\{port}",
        "readiness_url": f"http://127.0.0.1:{port}/health",
        "accepted_statuses": [200, 204],
        "enabled": True,
    }


def test_enabled_service_requires_complete_launch_and_readiness_contract(tmp_path: Path) -> None:
    config_path = tmp_path / "portal_servers.json"
    config_path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "Incomplete",
                        "port": 5050,
                        "cmd": "server.exe",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="working_directory, readiness_url, accepted_statuses"):
        load_config(config_path)


def test_fresh_launch_reclaims_ports_and_records_exact_process_metadata(tmp_path: Path) -> None:
    reclaimed: list[int] = []
    launched: list[tuple[str, str, Path, Path]] = []

    def launch(command: str, cwd: str, stdout_path: Path, stderr_path: Path) -> SimpleNamespace:
        launched.append((command, cwd, stdout_path, stderr_path))
        return SimpleNamespace(pid=4100 + len(launched))

    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101), _service("Beta", 5102)]},
        log_root=tmp_path,
        reclaim_port=reclaimed.append,
        launch_process=launch,
        check_readiness=lambda *_args: (True, None),
        now=lambda: 1000.0,
    )

    generation = supervisor.restart_all()

    assert reclaimed == [5101, 5102]
    assert [(item[0], item[1]) for item in launched] == [
        ("server-5101.exe --serve", r"C:\services\5101"),
        ("server-5102.exe --serve", r"C:\services\5102"),
    ]
    assert generation
    assert supervisor.state["Alpha"] == {
        "pid": 4101,
        "command": "server-5101.exe --serve",
        "working_directory": r"C:\services\5101",
        "started_at": 1000.0,
        "launch_generation": generation,
        "readiness": "ready",
        "attempt": 1,
        "error": None,
    }


def test_readiness_failure_restarts_once_then_stays_failed(tmp_path: Path) -> None:
    reclaimed: list[int] = []
    deadlines: list[int] = []
    outcomes = iter([(False, "timed out"), (False, "status 503")])
    launched: list[SimpleNamespace] = []

    def launch(*_args: object) -> SimpleNamespace:
        process = SimpleNamespace(pid=4200 + len(launched))
        launched.append(process)
        return process

    def readiness(_url: str, _statuses: tuple[int, ...], deadline: int) -> tuple[bool, str | None]:
        deadlines.append(deadline)
        return next(outcomes)

    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101)]},
        log_root=tmp_path,
        reclaim_port=reclaimed.append,
        launch_process=launch,
        check_readiness=readiness,
        now=lambda: 1000.0,
    )

    supervisor.restart_all()

    assert len(launched) == 2
    assert reclaimed == [5101, 5101]
    assert deadlines == [30, 30]
    assert supervisor.state["Alpha"]["attempt"] == 2
    assert supervisor.state["Alpha"]["readiness"] == "failed"
    assert supervisor.state["Alpha"]["error"] == "status 503"


def test_restart_all_uses_exactly_three_startup_workers(tmp_path: Path) -> None:
    services = [_service(f"Service {port}", port) for port in range(5101, 5106)]
    supervisor = PortalSupervisor(
        {"servers": services},
        log_root=tmp_path,
        reclaim_port=lambda _port: None,
        launch_process=lambda *_args: SimpleNamespace(pid=4300),
        check_readiness=lambda *_args: (True, None),
        now=lambda: 1000.0,
    )

    with patch("portal_supervisor.ThreadPoolExecutor", wraps=__import__("concurrent.futures").futures.ThreadPoolExecutor) as executor:
        supervisor.restart_all()

    executor.assert_called_once_with(max_workers=3)


def test_restart_all_retains_only_latest_ten_unique_generations(tmp_path: Path) -> None:
    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101)]},
        log_root=tmp_path,
        reclaim_port=lambda _port: None,
        launch_process=lambda *_args: SimpleNamespace(pid=4400),
        check_readiness=lambda *_args: (True, None),
        now=lambda: 1000.0,
    )

    generations = [supervisor.restart_all() for _ in range(12)]

    assert len(set(generations)) == 12
    assert {path.name for path in tmp_path.iterdir()} == set(generations[-10:])


def test_restart_cleanup_retains_latest_ten_by_mtime_tie_break_and_current_generation(
    tmp_path: Path,
) -> None:
    existing_names = [f"{index:032x}" for index in range(12)]
    creation_order = [7, 0, 11, 2, 9, 1, 5, 10, 3, 8, 4, 6]
    for index in creation_order:
        path = tmp_path / existing_names[index]
        path.mkdir()
        mtime = 100.0 if index < 4 else 200.0 + index
        os.utime(path, (mtime, mtime))

    current_name = "f" * 32

    def launch(*_args: object) -> SimpleNamespace:
        current_path = tmp_path / current_name
        os.utime(current_path, (1.0, 1.0))
        return SimpleNamespace(pid=4450)

    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101)]},
        log_root=tmp_path,
        reclaim_port=lambda _port: None,
        launch_process=launch,
        check_readiness=lambda *_args: (True, None),
        now=lambda: 1000.0,
    )

    original_iterdir = Path.iterdir

    def shuffled_iterdir(path: Path) -> object:
        if path == tmp_path:
            return iter(
                [tmp_path / existing_names[index] for index in creation_order]
                + [tmp_path / current_name]
            )
        return original_iterdir(path)

    with (
        patch("portal_supervisor.uuid4", return_value=SimpleNamespace(hex=current_name)),
        patch.object(Path, "iterdir", new=shuffled_iterdir),
    ):
        generation = supervisor.restart_all()

    expected = set(existing_names[3:] + [current_name])
    assert generation == current_name
    assert {path.name for path in tmp_path.iterdir()} == expected
    assert [path.name for path in supervisor.generation_history] == existing_names[
        3:
    ] + [current_name]


def test_manual_retry_restarts_only_named_service_in_current_generation(tmp_path: Path) -> None:
    reclaimed: list[int] = []
    launched: list[str] = []

    def launch(command: str, *_args: object) -> SimpleNamespace:
        launched.append(command)
        return SimpleNamespace(pid=4500 + len(launched))

    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101), _service("Beta", 5102)]},
        log_root=tmp_path,
        reclaim_port=reclaimed.append,
        launch_process=launch,
        check_readiness=lambda *_args: (True, None),
        now=lambda: 1000.0,
    )
    generation = supervisor.restart_all()
    beta_before = dict(supervisor.state["Beta"])
    reclaimed.clear()
    launched.clear()

    supervisor.retry_service("Alpha")

    assert reclaimed == [5101]
    assert launched == ["server-5101.exe --serve"]
    assert supervisor.state["Alpha"]["attempt"] == 2
    assert supervisor.state["Alpha"]["launch_generation"] == generation
    assert supervisor.state["Beta"] == beta_before


def test_dispatch_starts_once_then_focuses_existing_supervisor() -> None:
    active = False
    starts = 0
    focuses = 0

    def is_active() -> bool:
        return active

    def start() -> None:
        nonlocal active, starts
        active = True
        starts += 1

    def focus() -> None:
        nonlocal focuses
        focuses += 1

    assert supervisor_module.dispatch_launch(is_active, focus, start) == "started"
    assert supervisor_module.dispatch_launch(is_active, focus, start) == "focused"
    assert starts == 1
    assert focuses == 1


def test_server_sidebar_places_failed_only_retry_before_open() -> None:
    sidebar = dashboard_portal._render_server_sidebar([_service("Alpha", 5101)])

    retry = (
        '<button class="server-launch server-retry" data-service="Alpha" '
        'onclick="retryService(this.dataset.service)" aria-label="Retry Alpha" '
        'title="Retry Alpha" hidden>'
    )
    open_button = (
        '<button class="server-launch" onclick="openServer(5101)" '
        'aria-label="Open Alpha" title="Open Alpha">'
    )
    assert retry in sidebar
    assert open_button in sidebar
    assert sidebar.index(retry) < sidebar.index(open_button)
    assert 'id="launch-btn"' in sidebar
    assert "Restart All" in sidebar


def test_generated_portal_uses_authoritative_supervisor_state_and_restart_actions() -> None:
    portal = (WORKSPACE_ROOT / "reports" / "portal.html").read_text(encoding="utf-8")

    assert 'id="supervisor-controls"' not in portal
    assert "fetch('/api/state', {cache: 'no-store'})" in portal
    assert "fetch('/api/services/' + encodeURIComponent(name) + '/retry', {method: 'POST'})" in portal
    assert "retry.hidden = state.readiness !== 'failed'" in portal
    assert "dot.classList.toggle('up', state.readiness === 'ready')" in portal
    assert "dot.classList.toggle('down', state.readiness === 'failed')" in portal
    assert "row.title = state.error ||" in portal
    assert "async function probe" not in portal
    assert "async function checkServer" not in portal

    launch_body = portal.split("async function launchServers()", 1)[1].split("\n    }", 1)[0]
    assert "fetch('/api/restart-all', {method: 'POST'})" in launch_body
    assert "invokePortalLaunch" not in launch_body
    assert "btn.disabled = true" in launch_body
    assert "setTimeout" in launch_body
    assert "btn.disabled = false" in launch_body


def test_supervisor_serves_no_store_shell_without_duplicate_controls_and_with_cache_busting(tmp_path: Path) -> None:
    portal_path = tmp_path / "portal.html"
    portal_path.write_text(
        '<html><body><aside id="server-status-block"></aside>'
        '<iframe src="http://localhost:5101/"></iframe></body></html>',
        encoding="utf-8",
    )
    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101)]},
        log_root=tmp_path / "logs",
        reclaim_port=lambda _port: None,
        launch_process=lambda *_args: SimpleNamespace(pid=4600),
        check_readiness=lambda *_args: (True, None),
        now=lambda: 1000.0,
    )
    supervisor.current_generation = "generation-1"
    supervisor.state["Alpha"] = {
        "readiness": "failed",
        "attempt": 2,
        "error": "status 503",
    }
    server = supervisor_module.create_http_server(
        ("127.0.0.1", 0), supervisor, portal_path, lambda _url: None
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        with urlopen(f"{base_url}/portal.html?generation=generation-1") as response:
            body = response.read().decode("utf-8")
            assert response.headers["Cache-Control"] == "no-store"
        assert 'id="server-status-block"' in body
        assert 'id="supervisor-controls"' not in body
        assert "generation-1" in body
        with urlopen(f"{base_url}/api/state") as response:
            payload = json.load(response)
            assert response.headers["Cache-Control"] == "no-store"
        assert payload["generation"] == "generation-1"
        assert payload["services"]["Alpha"]["error"] == "status 503"
        assert payload["csrf_token"] == supervisor.csrf_token
        assert supervisor.csrf_token in body
        assert "X-Supervisor-CSRF" in body
        request = Request(
            f"{base_url}/api/restart-all",
            method="POST",
            headers={
                "Origin": base_url,
                "X-Supervisor-CSRF": supervisor.csrf_token,
            },
        )
        with urlopen(request) as response:
            restarted = json.load(response)
        assert restarted["generation"] != "generation-1"
        assert supervisor.current_generation == restarted["generation"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_mutation_endpoints_reject_forged_host_hostile_origin_and_invalid_csrf(
    tmp_path: Path,
) -> None:
    portal_path = tmp_path / "portal.html"
    portal_path.write_text("<html><body></body></html>", encoding="utf-8")
    supervisor = PortalSupervisor(
        {"servers": []},
        log_root=tmp_path / "logs",
        reclaim_port=lambda _port: None,
        launch_process=lambda *_args: SimpleNamespace(pid=4700),
        check_readiness=lambda *_args: (True, None),
        now=lambda: 1000.0,
    )
    server = supervisor_module.create_http_server(
        ("127.0.0.1", 0), supervisor, portal_path, lambda _url: None
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        origin = f"http://127.0.0.1:{port}"
        token = supervisor.csrf_token
        cases = [
            ({"Host": "attacker.example", "Origin": origin, "X-Supervisor-CSRF": token}, 403),
            ({"Origin": "https://attacker.example", "X-Supervisor-CSRF": token}, 403),
            ({"Origin": origin}, 403),
            ({"Origin": origin, "X-Supervisor-CSRF": "wrong-token"}, 403),
        ]
        for headers, expected_status in cases:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            connection.request("POST", "/api/restart-all", headers=headers)
            response = connection.getresponse()
            assert response.status == expected_status
            response.read()
            connection.close()

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request(
            "POST",
            "/api/restart-all",
            headers={"Origin": origin, "X-Supervisor-CSRF": token},
        )
        response = connection.getresponse()
        assert response.status == 202
        response.read()
        assert response.headers["X-Supervisor-CSRF"] == supervisor.csrf_token
        connection.close()
        assert supervisor.csrf_token != token

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request(
            "POST",
            "/api/focus",
            headers={"Origin": origin, "X-Supervisor-CSRF": token},
        )
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_restart_all_and_retry_contention_returns_conflict_without_stale_state(
    tmp_path: Path,
) -> None:
    portal_path = tmp_path / "portal.html"
    portal_path.write_text("<html><body></body></html>", encoding="utf-8")
    readiness_entered = threading.Event()
    release_readiness = threading.Event()
    reclaimed: list[int] = []
    launched: list[int] = []

    def check_readiness(*_args: object) -> tuple[bool, str | None]:
        readiness_entered.set()
        assert release_readiness.wait(timeout=2)
        return True, None

    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101)]},
        log_root=tmp_path / "logs",
        reclaim_port=reclaimed.append,
        launch_process=lambda *_args: launched.append(4800) or SimpleNamespace(pid=4800),
        check_readiness=check_readiness,
        now=lambda: 1000.0,
    )
    server = supervisor_module.create_http_server(
        ("127.0.0.1", 0), supervisor, portal_path, lambda _url: None
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        origin = f"http://127.0.0.1:{port}"
        headers = {"Origin": origin, "X-Supervisor-CSRF": supervisor.csrf_token}
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request("POST", "/api/restart-all", headers=headers)
        restart_response = connection.getresponse()
        headers["X-Supervisor-CSRF"] = restart_response.headers["X-Supervisor-CSRF"]
        restart_payload = json.loads(restart_response.read())
        connection.close()
        assert restart_response.status == 202
        assert readiness_entered.wait(timeout=2)

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request("POST", "/api/services/Alpha/retry", headers=headers)
        retry_response = connection.getresponse()
        retry_payload = json.loads(retry_response.read())
        connection.close()
        assert retry_response.status == 409
        assert retry_payload == {"error": "operation in progress"}

        release_readiness.set()
        deadline = time.monotonic() + 2
        while supervisor.operation_active and time.monotonic() < deadline:
            time.sleep(0.01)

        state = supervisor.snapshot()
        assert supervisor.operation_active is False
        assert state["generation"] == restart_payload["generation"]
        assert state["services"]["Alpha"]["launch_generation"] == restart_payload["generation"]
        assert state["services"]["Alpha"]["readiness"] == "ready"
        assert reclaimed == [5101]
        assert launched == [4800]
        assert len(supervisor.generation_history) == 1
    finally:
        release_readiness.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_reclaim_port_force_terminates_every_listener_pid() -> None:
    commands: list[list[str]] = []
    netstat_calls = 0

    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        nonlocal netstat_calls
        commands.append(command)
        if command[0] == "netstat":
            netstat_calls += 1
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    (
                        "  TCP    127.0.0.1:5101    0.0.0.0:0    LISTENING    1234\n"
                        "  TCP    [::]:5101         [::]:0       LISTENING    5678\n"
                    )
                    if netstat_calls == 1
                    else ""
                ),
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    killed = supervisor_module.reclaim_port(5101, run=run)

    assert killed == [1234, 5678]
    assert ["taskkill", "/PID", "1234", "/F", "/T"] in commands
    assert ["taskkill", "/PID", "5678", "/F", "/T"] in commands


def test_reclaim_port_reports_taskkill_failure() -> None:
    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[0] == "netstat":
            return SimpleNamespace(
                returncode=0,
                stdout="  TCP    127.0.0.1:5101    0.0.0.0:0    LISTENING    1234\n",
                stderr="",
            )
        return SimpleNamespace(returncode=5, stdout="", stderr="Access denied")

    with pytest.raises(
        RuntimeError,
        match=r"port 5101 reclaim failed: taskkill PID 1234: Access denied",
    ):
        supervisor_module.reclaim_port(5101, run=run)


def test_reclaim_port_reports_listener_that_remains_after_taskkill() -> None:
    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[0] == "netstat":
            return SimpleNamespace(
                returncode=0,
                stdout="  TCP    127.0.0.1:5101    0.0.0.0:0    LISTENING    1234\n",
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with pytest.raises(
        RuntimeError,
        match=r"port 5101 reclaim failed: listener remains \(PID 1234\)",
    ):
        supervisor_module.reclaim_port(5101, run=run)


def test_failed_reclaim_does_not_launch_or_adopt_stale_listener(tmp_path: Path) -> None:
    launched: list[str] = []
    readiness_checks: list[str] = []

    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[0] == "netstat":
            return SimpleNamespace(
                returncode=0,
                stdout="  TCP    127.0.0.1:5101    0.0.0.0:0    LISTENING    1234\n",
                stderr="",
            )
        return SimpleNamespace(returncode=5, stdout="", stderr="Access denied")

    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101)]},
        log_root=tmp_path,
        reclaim_port=lambda port: supervisor_module.reclaim_port(port, run=run),
        launch_process=lambda command, *_args: launched.append(command),
        check_readiness=lambda url, *_args: readiness_checks.append(url) or (True, None),
        now=lambda: 1000.0,
    )

    generation = supervisor.restart_all()

    error = "port 5101 reclaim failed: taskkill PID 1234: Access denied"
    assert launched == []
    assert readiness_checks == []
    assert supervisor.state["Alpha"] == {
        "pid": None,
        "command": "server-5101.exe --serve",
        "working_directory": r"C:\services\5101",
        "started_at": None,
        "launch_generation": generation,
        "readiness": "failed",
        "attempt": 1,
        "error": error,
    }
    assert len(error) <= 160


def test_http_readiness_waits_for_a_configured_accepted_status() -> None:
    statuses = iter([503, 204])
    seen_timeouts: list[float] = []

    class Response:
        def __init__(self, status: int) -> None:
            self.status = status

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def opener(_url: str, *, timeout: float) -> Response:
        seen_timeouts.append(timeout)
        return Response(next(statuses))

    ready, error = supervisor_module.check_http_readiness(
        "http://127.0.0.1:5101/health",
        (200, 204),
        30,
        opener=opener,
        monotonic=iter([0.0, 0.0, 0.1, 0.1]).__next__,
        wait=lambda _seconds: None,
    )

    assert ready is True
    assert error is None
    assert len(seen_timeouts) == 2
    assert all(0 < timeout <= 2 for timeout in seen_timeouts)


def test_http_readiness_accepts_configured_http_error_status() -> None:
    def opener(url: str, **_kwargs: object) -> object:
        raise HTTPError(url, 401, "Unauthorized", {}, None)

    ready, error = supervisor_module.check_http_readiness(
        "http://127.0.0.1:8766/",
        (200, 401),
        30,
        opener=opener,
        monotonic=iter([0.0, 0.0, 0.0, 31.0]).__next__,
        wait=lambda _seconds: None,
    )

    assert ready is True
    assert error is None


def test_service_start_time_is_recorded_before_readiness_wait(tmp_path: Path) -> None:
    events: list[str] = []
    supervisor = PortalSupervisor(
        {"servers": [_service("Alpha", 5101)]},
        log_root=tmp_path,
        reclaim_port=lambda _port: None,
        launch_process=lambda *_args: SimpleNamespace(pid=4650),
        check_readiness=lambda *_args: events.append("readiness") or (True, None),
        now=lambda: events.append("started_at") or 1000.0,
    )

    supervisor.restart_all()

    assert events == ["started_at", "readiness"]


def test_launch_process_parses_windows_command_without_windows_ctypes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def popen(command: list[str], **_kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        return SimpleNamespace(pid=4699)

    monkeypatch.delattr(supervisor_module.ctypes, "windll", raising=False)

    supervisor_module.launch_process(
        'C:\\G\\python.exe "f:\\ΣCapital\\src\\trade gate.py" --serve',
        r"f:\ΣCapital",
        tmp_path / "5101.stdout.log",
        tmp_path / "5101.stderr.log",
        popen=popen,
    )

    assert captured["command"] == [
        r"C:\G\python.exe",
        r"f:\ΣCapital\src\trade gate.py",
        "--serve",
    ]


def test_launch_process_preserves_sigma_path_in_structured_argv(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def popen(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(pid=4700)

    stdout_path = tmp_path / "5101.stdout.log"
    stderr_path = tmp_path / "5101.stderr.log"
    process = supervisor_module.launch_process(
        'C:\\G\\python.exe "f:\\ΣCapital\\src\\trade_gate.py" --serve',
        r"f:\ΣCapital",
        stdout_path,
        stderr_path,
        popen=popen,
    )

    assert process.pid == 4700
    assert captured["command"] == [
        r"C:\G\python.exe",
        r"f:\ΣCapital\src\trade_gate.py",
        "--serve",
    ]
    assert captured["cwd"] == r"f:\ΣCapital"
    assert captured["shell"] is False
    assert Path(captured["stdout"].name) == stdout_path
    assert Path(captured["stderr"].name) == stderr_path


def test_launch_process_preserves_powershell_wrapper_arguments(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def popen(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(pid=4701)

    supervisor_module.launch_process(
        "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass "
        r"-File f:\⊕Workspace\tools\start_trade_gate.ps1",
        r"f:\ΣCapital",
        tmp_path / "7475.stdout.log",
        tmp_path / "7475.stderr.log",
        popen=popen,
    )

    assert captured["command"] == [
        "powershell.exe",
        "-NoProfile",
        "-WindowStyle",
        "Hidden",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        r"f:\⊕Workspace\tools\start_trade_gate.ps1",
        "-ProjectRoot",
        r"f:\ΣCapital",
    ]
    assert captured["cwd"] == r"f:\ΣCapital"
    assert captured["shell"] is False


def test_resident_generates_shell_before_serving_and_opening_browser() -> None:
    events: list[str] = []

    class Server:
        server_port = 8790

        def serve_forever(self) -> None:
            events.append("serve")

    supervisor = SimpleNamespace(
        new_generation=lambda: events.append("generation") or "generation-1",
        restart_all=lambda generation=None: events.append(f"restart:{generation}"),
    )

    supervisor_module.run_resident(
        supervisor,
        generate_portal=lambda: events.append("generate"),
        server_factory=lambda: events.append("server") or Server(),
        browser_open=lambda url: events.append(f"browser:{url}"),
        start_background=lambda target: events.append("background") or target(),
        open_browser=True,
    )

    assert events == [
        "generate",
        "server",
        "generation",
        "background",
        "restart:generation-1",
        "browser:http://127.0.0.1:8790/portal.html?generation=generation-1",
        "serve",
    ]


def test_supervisor_uses_reserved_port_8790_everywhere() -> None:
    supervisor_text = SUPERVISOR_SCRIPT.read_text(encoding="utf-8")
    protocol_text = REGISTER_PROTOCOL.read_text(encoding="utf-8")

    assert supervisor_module.SUPERVISOR_PORT == 8790
    assert "8080" not in supervisor_text
    assert "127.0.0.1:8790/api/state" in protocol_text
    assert "127.0.0.1:8080" not in protocol_text


def test_living_html_regeneration_does_not_wait_for_serve_mode() -> None:
    manifest = {
        "dashboards": [
            {
                "id": "band-mgmt",
                "title": "Band Management",
                "type": "living_html",
                "cli": "C:\\G\\python.exe src/band_mgmt/generate_band_mgmt_panel.py --serve",
                "project": "Music",
                "project_root": r"F:\Music",
            }
        ]
    }
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(command)
        if "--serve" in command:
            raise subprocess.TimeoutExpired(command, timeout=120)
        return SimpleNamespace(returncode=0, stdout="generated", stderr="")

    with patch("dashboard_portal.subprocess.run", side_effect=run):
        results = dashboard_portal.regenerate_dashboards(manifest)

    assert commands == [[r"C:\G\python.exe", "src/band_mgmt/generate_band_mgmt_panel.py"]]
    assert results[0]["regen_status"] == "ok"


def test_canonical_config_declares_launch_and_http_readiness_for_every_service() -> None:
    config = load_config(PORTAL_CONFIG)

    for service in config["servers"]:
        if service["enabled"]:
            assert service["working_directory"]
            assert service["readiness_url"].startswith("http://")
            assert service["accepted_statuses"]


@pytest.mark.parametrize("path", [LAUNCH_PORTAL, OPEN_PORTAL])
def test_powershell_launchers_are_thin_supervisor_shims(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    assert "portal_supervisor.py" in text
    assert "portal_servers.json" not in text
    assert "Get-NetTCPConnection" not in text
    assert "Stop-Process" not in text
    assert "start_music_dashboard" not in text


def test_protocol_registration_stages_only_thin_supervisor_shims() -> None:
    text = REGISTER_PROTOCOL.read_text(encoding="utf-8")

    assert "portal_supervisor.py" in text
    assert "portal_protocol_launch.vbs" in text
    assert '"open_portal.vbs"' in text
    assert '"open_portal.ps1"' in text
    assert "Copy-Item" in text
    assert ".backup-" in text
    assert "portal_servers.json" not in text
    assert "Get-NetTCPConnection" not in text


def test_protocol_registration_stages_desktop_vbs_as_direct_supervisor_shim() -> None:
    text = REGISTER_PROTOCOL.read_text(encoding="utf-8")

    assert '$supervisorPath = Join-Path $PSScriptRoot "portal_supervisor.py"' in text
    assert 'WshShell.Run """C:\\G\\python.exe"" ""$supervisorPath""", 0, False' in text
    assert "WriteAllText($desktopVbs, $desktopVbsText, [System.Text.Encoding]::Unicode)" in text
    assert "restart_servers.ps1" not in text
    assert "launch_portal.ps1" not in text


def test_legacy_restart_script_is_a_thin_supervisor_shim() -> None:
    text = RESTART_SERVERS.read_text(encoding="utf-8")

    assert "portal_supervisor.py" in text
    assert "--restart-all" in text
    assert "Get-NetTCPConnection" not in text
    assert "Stop-Process" not in text


def test_supervisor_cli_exposes_resident_and_no_open_modes() -> None:
    result = subprocess.run(
        [sys.executable, str(SUPERVISOR_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0
    assert "--serve" in result.stdout
    assert "--no-open" in result.stdout