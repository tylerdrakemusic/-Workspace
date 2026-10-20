from __future__ import annotations

import base64
import http.client
import json
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_bdd import given, parsers, scenarios, then, when


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = WORKSPACE_ROOT / "tools"
CONFIG_PATH = TOOLS_ROOT / "portal_servers.json"
sys.path.insert(0, str(TOOLS_ROOT))

import dashboard_portal
import portal_supervisor
from portal_supervisor import PortalSupervisor, load_config


scenarios("workout_portal_reliability.feature")


def _workout_service() -> dict[str, object]:
    config = load_config(CONFIG_PATH)
    return next(
        service for service in config["servers"] if service.get("name") == "Workout"
    )


def _test_workout_service() -> dict[str, object]:
    return {
        "name": "Workout",
        "port": 8770,
        "cmd": r"C:\G\python.exe f:\∞Life\tools\workout_server.py --port 8770",
        "working_directory": r"f:\∞Life",
        "readiness_url": "http://127.0.0.1:8770/health",
        "accepted_statuses": [200],
        "enabled": True,
        "monitor_health": True,
        "require_managed_owner": True,
        "log_output": False,
    }


def _build_supervisor(
    tmp_path: Path,
    readiness: Callable[..., tuple[bool, str | None]],
    *,
    now: Callable[[], float] = lambda: 1000.0,
    launch_records: list[dict[str, object]] | None = None,
    reclaim_records: list[tuple[int, dict[str, object]]] | None = None,
) -> PortalSupervisor:
    launch_records = launch_records if launch_records is not None else []
    reclaim_records = reclaim_records if reclaim_records is not None else []

    def launch(
        command: str,
        working_directory: str,
        stdout_path: Path,
        stderr_path: Path,
        **options: object,
    ) -> SimpleNamespace:
        process = SimpleNamespace(
            pid=5200 + len(launch_records),
            poll=lambda: None,
            terminate=lambda: None,
            wait=lambda **_kwargs: None,
        )
        launch_records.append(
            {
                "command": command,
                "working_directory": working_directory,
                "stdout_path": stdout_path,
                "stderr_path": stderr_path,
                **options,
            }
        )
        return process

    def reclaim(port: int, **options: object) -> None:
        reclaim_records.append((port, options))

    return PortalSupervisor(
        {"servers": [_test_workout_service()]},
        log_root=tmp_path / "logs",
        reclaim_port=reclaim,
        launch_process=launch,
        check_readiness=readiness,
        now=now,
    )


@given("the portal service manifest", target_fixture="portal_services")
def portal_services() -> dict[str, dict[str, object]]:
    config = load_config(CONFIG_PATH)
    return {str(item["name"]): item for item in config["servers"]}


@when("I resolve Workout's configured launch contract", target_fixture="workout_contract")
def workout_launch_contract(
    portal_services: dict[str, dict[str, object]],
    tmp_path: Path,
) -> dict[str, object]:
    assert "Workout" in portal_services, "Workout must be registered as an enabled portal service"
    service = portal_services["Workout"]
    argv = portal_supervisor._launch_argv(
        str(service["cmd"]), str(service["working_directory"])
    )
    launch_options: dict[str, object] = {}

    def popen(command: list[str], **options: object) -> SimpleNamespace:
        launch_options.update(options)
        launch_options["argv"] = command
        return SimpleNamespace(pid=5199)

    stdout_path = tmp_path / "workout.stdout.log"
    stderr_path = tmp_path / "workout.stderr.log"
    portal_supervisor.launch_process(
        str(service["cmd"]),
        str(service["working_directory"]),
        stdout_path,
        stderr_path,
        popen=popen,
        log_output=bool(service.get("log_output", True)),
    )
    return {
        "service": service,
        "argv": argv,
        "launch_options": launch_options,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
    }


@then("Workout launches from the primary Life checkout on its loopback health endpoint")
def workout_contract_is_primary_checkout(
    workout_contract: dict[str, object],
) -> None:
    service = workout_contract["service"]
    argv = workout_contract["argv"]
    assert service["enabled"] is True
    assert service["port"] == 8770
    assert service["working_directory"] == r"f:\∞Life"
    assert argv == [
        r"C:\G\python.exe",
        r"f:\∞Life\tools\workout_server.py",
        "--port",
        "8770",
    ]
    assert service["readiness_url"] == "http://127.0.0.1:8770/health"
    assert service["accepted_statuses"] == [200]
    assert service["monitor_health"] is True
    assert service["require_managed_owner"] is True
    assert service["log_output"] is False
    launch_options = workout_contract["launch_options"]
    assert launch_options["argv"] == argv
    assert launch_options["stdout"] == subprocess.DEVNULL
    assert launch_options["stderr"] == subprocess.DEVNULL
    assert workout_contract["stdout_path"].exists() is False
    assert workout_contract["stderr_path"].exists() is False


@then("the existing Music service remains registered on port 8765")
def music_port_is_preserved(portal_services: dict[str, dict[str, object]]) -> None:
    music = portal_services["Band Management"]
    assert music["enabled"] is True
    assert music["port"] == 8765
    assert music["readiness_url"] == "http://127.0.0.1:8765/"


@given("a supervisor with a healthy running Workout service", target_fixture="monitor_context")
def healthy_monitor_context(tmp_path: Path) -> dict[str, object]:
    probes: list[tuple[str, int]] = []

    def readiness(url: str, _statuses: tuple[int, ...], deadline: int) -> tuple[bool, str | None]:
        probes.append((url, deadline))
        return True, None

    supervisor = _build_supervisor(tmp_path, readiness)
    supervisor.restart_all()
    probes.clear()
    return {"supervisor": supervisor, "probes": probes}


@when("its resident health monitor runs for two intervals")
def run_monitor_for_two_intervals(monitor_context: dict[str, object]) -> None:
    class StopAfterTwoWaits:
        def __init__(self) -> None:
            self.waits: list[float] = []

        def is_set(self) -> bool:
            return len(self.waits) == 2

        def wait(self, seconds: float) -> bool:
            self.waits.append(seconds)
            return False

    supervisor = monitor_context["supervisor"]
    monitor = getattr(supervisor, "monitor_services", None)
    assert callable(monitor), "the resident supervisor must own a periodic health monitor"
    stop_event = StopAfterTwoWaits()
    monitor(stop_event=stop_event)
    monitor_context["waits"] = stop_event.waits


@then("the monitor waits 30 seconds between health sweeps")
def monitor_cadence_is_30_seconds(monitor_context: dict[str, object]) -> None:
    assert monitor_context["waits"] == [30, 30]
    assert len(monitor_context["probes"]) == 2
    assert all(url == "http://127.0.0.1:8770/health" for url, _ in monitor_context["probes"])


@given("a supervisor whose running Workout service becomes unhealthy", target_fixture="recovery_context")
def unhealthy_running_service(tmp_path: Path) -> dict[str, object]:
    clock = [0.0]
    outcomes = iter([(True, None), (False, "private response"), (False, "private response"), (True, None)])
    launches: list[dict[str, object]] = []
    probes: list[tuple[str, int]] = []

    def readiness(url: str, _statuses: tuple[int, ...], deadline: int) -> tuple[bool, str | None]:
        probes.append((url, deadline))
        return next(outcomes)

    supervisor = _build_supervisor(
        tmp_path, readiness, now=lambda: clock[0], launch_records=launches
    )
    generation = supervisor.restart_all()
    return {
        "supervisor": supervisor,
        "clock": clock,
        "generation": generation,
        "launches": launches,
        "probes": probes,
    }


@when("the due recovery attempt succeeds")
def run_due_recovery(recovery_context: dict[str, object]) -> None:
    supervisor = recovery_context["supervisor"]
    monitor_once = getattr(supervisor, "monitor_once", None)
    assert callable(monitor_once), "the resident supervisor must perform service health sweeps"
    clock = recovery_context["clock"]
    clock[0] = 30.0
    monitor_once()
    recovery_context["state_after_failure"] = dict(supervisor.state["Workout"])
    clock[0] = float(supervisor.state["Workout"]["next_retry_at"])
    monitor_once()


@then("the service returns to ready without changing its launch generation")
def recovered_in_current_generation(recovery_context: dict[str, object]) -> None:
    supervisor = recovery_context["supervisor"]
    failed_state = recovery_context["state_after_failure"]
    state = supervisor.state["Workout"]
    assert failed_state["readiness"] == "failed"
    assert state["readiness"] == "ready"
    assert state["launch_generation"] == recovery_context["generation"]
    assert state["attention"] is False
    assert len(recovery_context["launches"]) == 2
    assert all("private response" not in str(item) for item in supervisor.snapshot().values())


@given("a Workout service that remains unhealthy through six recovery attempts", target_fixture="backoff_context")
def unhealthy_service_for_backoff(tmp_path: Path) -> dict[str, object]:
    clock = [0.0]
    launches: list[dict[str, object]] = []
    probes: list[int] = []

    def readiness(_url: str, _statuses: tuple[int, ...], deadline: int) -> tuple[bool, str | None]:
        probes.append(deadline)
        return False, "generic unavailable"

    supervisor = _build_supervisor(
        tmp_path, readiness, now=lambda: clock[0], launch_records=launches
    )
    supervisor.restart_all()
    return {
        "supervisor": supervisor,
        "clock": clock,
        "launches": launches,
        "probes": probes,
    }


@when("the supervisor advances through each retry deadline")
def advance_backoff_deadlines(backoff_context: dict[str, object]) -> None:
    supervisor = backoff_context["supervisor"]
    monitor_once = getattr(supervisor, "monitor_once", None)
    assert callable(monitor_once), "the resident supervisor must keep retrying failed services"
    delays: list[float] = []
    for _ in range(6):
        due_at = float(supervisor.state["Workout"]["next_retry_at"])
        previous = float(backoff_context["clock"][0])
        delays.append(due_at - previous)
        backoff_context["clock"][0] = due_at
        monitor_once()
    backoff_context["delays"] = delays
    backoff_context["clock"][0] = float(supervisor.state["Workout"]["next_retry_at"])
    supervisor.check_readiness = lambda *_args: (True, None)
    monitor_once()


@then("retry delays increase to a 300-second cap and continue until recovery")
def capped_retries_continue(backoff_context: dict[str, object]) -> None:
    supervisor = backoff_context["supervisor"]
    assert backoff_context["delays"] == [30, 60, 120, 240, 300, 300]
    assert len(backoff_context["launches"]) == 8
    assert supervisor.state["Workout"]["readiness"] == "ready"
    assert supervisor.state["Workout"]["attention"] is False


@given("a running Workout service that fails repeatedly", target_fixture="attention_context")
def repeated_failure_context(tmp_path: Path) -> dict[str, object]:
    clock = [0.0]
    outcomes = iter(
        [
            (True, None),
            (False, "workout data must not appear"),
            (False, "workout data must not appear"),
            (False, "workout data must not appear"),
            (True, None),
        ]
    )
    launches: list[dict[str, object]] = []

    def readiness(*_args: object) -> tuple[bool, str | None]:
        return next(outcomes)

    supervisor = _build_supervisor(
        tmp_path, readiness, now=lambda: clock[0], launch_records=launches
    )
    supervisor.restart_all()
    return {"supervisor": supervisor, "clock": clock, "launches": launches}


@when("the supervisor exposes the repeated failure and then Retry succeeds")
def expose_attention_then_retry(attention_context: dict[str, object]) -> None:
    supervisor = attention_context["supervisor"]
    monitor_once = getattr(supervisor, "monitor_once", None)
    assert callable(monitor_once), "the supervisor must track repeated health failures"
    clock = attention_context["clock"]
    clock[0] = 30.0
    monitor_once()
    clock[0] = float(supervisor.state["Workout"]["next_retry_at"])
    monitor_once()
    attention_context["attention_state"] = dict(supervisor.state["Workout"])
    supervisor.retry_service("Workout")


@then("the portal shows Attention while failed and clears it after recovery")
def attention_is_user_visible_and_clears(attention_context: dict[str, object]) -> None:
    supervisor = attention_context["supervisor"]
    assert attention_context["attention_state"]["attention"] is True
    assert supervisor.state["Workout"]["attention"] is False
    service = _test_workout_service()
    with (
        patch("dashboard_portal._load_servers", return_value=[service]),
        patch("dashboard_portal._render_api_health_widget", return_value=""),
    ):
        html = dashboard_portal.render_portal({"dashboards": [], "projects": []})
    assert 'class="server-state"' in html
    assert 'state.attention ? "Attention" : ""' in html
    assert "workout data must not appear" not in json.dumps(supervisor.snapshot())


@given("a Workout service is running under the portal supervisor", target_fixture="api_context")
def running_service_api_context(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> dict[str, object]:
    launches: list[dict[str, object]] = []
    supervisor = _build_supervisor(
        tmp_path,
        lambda *_args: (True, None),
        launch_records=launches,
    )
    generation = supervisor.restart_all()
    portal_path = tmp_path / "portal.html"
    portal_path.write_text("<html><body></body></html>", encoding="utf-8")
    server = portal_supervisor.create_http_server(
        ("127.0.0.1", 0), supervisor, portal_path, lambda _url: None
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def cleanup_server() -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    request.addfinalizer(cleanup_server)
    return {
        "supervisor": supervisor,
        "generation": generation,
        "launches": launches,
        "server": server,
    }


@when("I submit Retry through the authorized portal API")
def retry_through_portal_api(api_context: dict[str, object]) -> None:
    server = api_context["server"]
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    connection.request("GET", "/api/state")
    state_response = connection.getresponse()
    token = json.loads(state_response.read())["csrf_token"]
    connection.close()

    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    connection.request(
        "POST",
        "/api/services/Workout/retry",
        headers={"X-Supervisor-CSRF": token},
    )
    retry_response = connection.getresponse()
    api_context["retry_status"] = retry_response.status
    api_context["retry_payload"] = json.loads(retry_response.read())
    connection.close()

    completed = threading.Event()
    launches = api_context["launches"]
    deadline = threading.Event()
    for _ in range(100):
        if len(launches) == 2:
            completed.set()
            break
        deadline.wait(0.01)
    api_context["completed"] = completed.is_set()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    connection.request("GET", "/api/state")
    response = connection.getresponse()
    api_context["api_state"] = json.loads(response.read())
    connection.close()


@then("the same supervisor updates the service state in its current generation")
def retry_updates_authoritative_state(api_context: dict[str, object]) -> None:
    supervisor = api_context["supervisor"]
    assert api_context["retry_status"] == 202
    assert api_context["retry_payload"] == {"status": "retrying", "service": "Workout"}
    assert api_context["completed"] is True
    assert api_context["api_state"]["generation"] == api_context["generation"]
    assert api_context["api_state"]["services"]["Workout"]["readiness"] == "ready"
    assert len(api_context["launches"]) == 2
    assert supervisor.snapshot()["generation"] == api_context["generation"]
    with (
        patch("dashboard_portal._load_servers", return_value=[_test_workout_service()]),
        patch("dashboard_portal._render_api_health_widget", return_value=""),
    ):
        html = dashboard_portal.render_portal({"dashboards": [], "projects": []})
    assert "fetch('/api/state', {cache: 'no-store'})" in html
    assert "fetch('/api/services/' + encodeURIComponent(name) + '/retry', {method: 'POST'})" in html


@given("an unverified process is listening on the Workout port", target_fixture="listener_context")
def unverified_listener() -> dict[str, object]:
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(command)
        if command[0] == "netstat":
            return SimpleNamespace(
                returncode=0,
                stdout="  TCP    127.0.0.1:8770    0.0.0.0:0    LISTENING    9999\n",
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return {"commands": commands, "run": run}


@when("the supervisor attempts a managed-only port reclaim")
def reclaim_unverified_listener(listener_context: dict[str, object]) -> None:
    with pytest.raises(RuntimeError, match="ownership unverified"):
        try:
            portal_supervisor.reclaim_port(
                8770,
                require_managed_owner=True,
                run=listener_context["run"],
            )
        except TypeError as exc:
            pytest.fail(f"managed-only reclaim must fail closed instead of accepting this listener: {exc}")


@then("it reports an ownership failure and leaves the listener untouched")
def unverified_listener_is_not_killed(listener_context: dict[str, object]) -> None:
    commands = listener_context["commands"]
    assert commands == [["netstat", "-ano", "-p", "tcp"]]
    assert all(command[0] != "taskkill" for command in commands)


@given("the resident portal is started with one supervisor instance", target_fixture="resident_context")
def resident_with_one_supervisor(tmp_path: Path) -> dict[str, object]:
    supervisor = _build_supervisor(tmp_path, lambda *_args: (True, None))
    background: list[object] = []
    server = SimpleNamespace(server_port=8790, serve_forever=lambda: None)
    portal_supervisor.run_resident(
        supervisor,
        generate_portal=lambda: None,
        regenerate_optional=lambda: None,
        server_factory=lambda: server,
        browser_open=lambda _url: None,
        start_background=background.append,
        open_browser=False,
        generation="a" * 32,
    )
    return {"supervisor": supervisor, "background": background}


@when("background work is registered")
def verify_background_monitor_registration(resident_context: dict[str, object]) -> None:
    background = resident_context["background"]
    monitor = next(
        (
            target
            for target in background
            if getattr(target, "__name__", None) == "monitor_services"
        ),
        None,
    )
    assert monitor is not None, "the existing supervisor must own the health-monitor loop"
    resident_context["monitor_owner"] = monitor.__self__


@then("health monitoring is bound to that same supervisor instance")
def monitor_uses_existing_supervisor(resident_context: dict[str, object]) -> None:
    assert resident_context["monitor_owner"] is resident_context["supervisor"]


def _build_logon_task_plan(workspace_root: str, user_sid: str) -> dict[str, object]:
    builder = getattr(portal_supervisor, "build_logon_task_plan", None)
    assert callable(builder), "the supervisor must expose a portable logon task-plan builder"
    return builder(workspace_root=workspace_root, user_sid=user_sid)


def _task_identity_matches(task_xml: str, plan: dict[str, object]) -> bool:
    matcher = getattr(portal_supervisor, "task_xml_matches_identity", None)
    assert callable(matcher), "the supervisor must expose a portable task identity check"
    return bool(matcher(task_xml, plan))


def _task_operation(
    operation: str,
    task_xml: str | None,
    plan: dict[str, object],
) -> str:
    arguments = [
        sys.executable,
        str(portal_supervisor.SUPERVISOR_SCRIPT_PATH),
        "--logon-task-operation",
        operation,
        "--user-sid",
        str(plan["principal"]["user_id"]),
        "--workspace-root",
        str(plan["action"]["working_directory"]),
    ]
    if task_xml is not None:
        arguments.extend(
            [
                "--task-xml-base64",
                base64.b64encode(task_xml.encode("utf-8")).decode("ascii"),
            ]
        )
    result = subprocess.run(
        arguments,
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        expected_rejection = (
            "existing scheduled task identity does not match the intended task"
        )
        if result.returncode == 2 and expected_rejection in result.stderr:
            raise ValueError(expected_rejection)
        raise AssertionError(f"task operation CLI failed: {result.stderr}")
    return result.stdout.strip()


@given("a Workspace root and current-user SID", target_fixture="logon_plan_context")
def logon_plan_context() -> dict[str, str]:
    return {
        "workspace_root": r"F:\Workspace with spaces\⊕Workspace",
        "user_sid": "S-1-5-21-1000-2000-3000-1001",
    }


@given(
    "a Workspace feature-worktree root and current-user SID",
    target_fixture="logon_plan_context",
)
def logon_worktree_context() -> dict[str, str]:
    return {
        "workspace_root": r"F:\⊕Workspace\.worktrees\feature-workout",
        "user_sid": "S-1-5-21-1000-2000-3000-1001",
    }


@when("I build the current-user logon task plan", target_fixture="logon_plan")
def build_current_user_logon_plan(
    logon_plan_context: dict[str, str],
) -> dict[str, object]:
    return _build_logon_task_plan(
        logon_plan_context["workspace_root"], logon_plan_context["user_sid"]
    )


@when(
    "I request the task plan from the supervisor CLI",
    target_fixture="installer_task_plan",
)
def request_task_plan_from_cli(
    logon_plan_context: dict[str, str],
) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            str(portal_supervisor.SUPERVISOR_SCRIPT_PATH),
            "--logon-task-plan",
            "--user-sid",
            logon_plan_context["user_sid"],
            "--workspace-root",
            logon_plan_context["workspace_root"],
        ],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@then("the CLI returns the same current-user logon contract")
def cli_returns_current_user_logon_contract(
    installer_task_plan: dict[str, object],
    logon_plan_context: dict[str, str],
) -> None:
    sid = logon_plan_context["user_sid"]
    assert installer_task_plan["action"]["command"] == r"C:\G\python.exe"
    assert installer_task_plan["action"]["arguments"] == (
        f'"{logon_plan_context["workspace_root"]}\\tools\\portal_supervisor.py" --no-open'
    )
    assert installer_task_plan["principal"]["user_id"] == sid
    assert installer_task_plan["trigger"]["user_id"] == sid
    assert installer_task_plan["settings"]["multiple_instances_policy"] == "IgnoreNew"
    assert installer_task_plan["stores_credentials"] is False


@then("the task invokes the existing supervisor dispatcher once")
def logon_plan_dispatches_existing_supervisor(logon_plan: dict[str, object]) -> None:
    action = logon_plan["action"]
    assert action["command"] == r"C:\G\python.exe"
    assert action["arguments"] == (
        '"F:\\Workspace with spaces\\⊕Workspace\\tools\\portal_supervisor.py" --no-open'
    )
    assert action["working_directory"] == r"F:\Workspace with spaces\⊕Workspace"
    root = ET.fromstring(logon_plan["task_xml"])
    namespace = {"task": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    actions = root.findall("task:Actions/task:Exec", namespace)
    assert len(actions) == 1
    assert actions[0].findtext("task:Command", namespaces=namespace) == r"C:\G\python.exe"


@then("the task uses the current user's interactive least-privilege principal")
def logon_plan_uses_interactive_current_user(logon_plan: dict[str, object]) -> None:
    sid = "S-1-5-21-1000-2000-3000-1001"
    assert logon_plan["trigger"] == {"type": "Logon", "user_id": sid, "enabled": True}
    assert logon_plan["principal"] == {
        "user_id": sid,
        "logon_type": "InteractiveToken",
        "run_level": "LeastPrivilege",
    }


@then("the task targets the primary Workspace checkout, not the disposable worktree")
def logon_plan_uses_primary_workspace_root(logon_plan: dict[str, object]) -> None:
    action = logon_plan["action"]
    assert action["working_directory"] == r"F:\⊕Workspace"
    assert action["arguments"] == (
        r'"F:\⊕Workspace\tools\portal_supervisor.py" --no-open'
    )


@then("duplicate task instances are ignored without stored credentials")
def logon_plan_ignores_duplicates_without_credentials(
    logon_plan: dict[str, object],
) -> None:
    assert logon_plan["settings"]["multiple_instances_policy"] == "IgnoreNew"
    assert logon_plan["stores_credentials"] is False
    assert "Password" not in logon_plan["task_xml"]


@given("the intended current-user logon task", target_fixture="task_identity_context")
def intended_current_user_logon_task() -> dict[str, object]:
    plan = _build_logon_task_plan(
        r"F:\Workspace with spaces\⊕Workspace", "S-1-5-21-1000-2000-3000-1001"
    )
    return {"plan": plan, "task_xml": plan["task_xml"]}


@when("I verify its exported scheduled-task definition")
def verify_exact_task_identity(task_identity_context: dict[str, object]) -> None:
    task_identity_context["matches"] = _task_identity_matches(
        task_identity_context["task_xml"], task_identity_context["plan"]
    )


@when(parsers.parse("the existing task is evaluated for {operation}"))
def evaluate_existing_task_operation(
    operation: str,
    task_identity_context: dict[str, object],
) -> None:
    normalized_operation = "register" if operation == "registration" else "unregister"
    task_identity_context["decision"] = _task_operation(
        normalized_operation,
        task_identity_context["task_xml"],
        task_identity_context["plan"],
    )


@given("a planned current-user logon task", target_fixture="task_operation_context")
def planned_current_user_logon_task() -> dict[str, object]:
    plan = _build_logon_task_plan(
        r"F:\Workspace with spaces\⊕Workspace", "S-1-5-21-1000-2000-3000-1001"
    )
    return {"plan": plan}


@when(parsers.parse("a missing task is evaluated for {operation}"))
def evaluate_missing_task_operation(
    operation: str,
    task_operation_context: dict[str, object],
) -> None:
    normalized_operation = "register" if operation == "registration" else "unregister"
    task_operation_context["decision"] = _task_operation(
        normalized_operation, None, task_operation_context["plan"]
    )


@then(parsers.parse('the installer decision is "{expected}"'))
def installer_decision_is(
    expected: str,
    request: pytest.FixtureRequest,
) -> None:
    context_fixture = next(
        name
        for name in ("task_identity_context", "task_operation_context")
        if name in request.fixturenames
    )
    context = request.getfixturevalue(context_fixture)
    assert context["decision"] == expected


@when(
    parsers.parse("the exported task has a different {identity}"),
    target_fixture="task_identity_context",
)
def change_task_identity(
    identity: str,
    task_identity_context: dict[str, object],
) -> dict[str, object]:
    namespace_uri = "http://schemas.microsoft.com/windows/2004/02/mit/task"
    namespace = {"task": namespace_uri}
    root = ET.fromstring(task_identity_context["task_xml"])
    if identity == "action":
        root.find("task:Actions/task:Exec/task:Command", namespace).text = r"C:\Other\python.exe"
    elif identity == "principal":
        root.find("task:Principals/task:Principal/task:UserId", namespace).text = "S-1-5-21-9999"
    elif identity == "trigger":
        root.find("task:Triggers/task:LogonTrigger", namespace).tag = (
            f"{{{namespace_uri}}}TimeTrigger"
        )
    else:
        root.find("task:Settings/task:MultipleInstancesPolicy", namespace).text = "Parallel"
    task_identity_context["task_xml"] = ET.tostring(root, encoding="unicode")
    task_identity_context["matches"] = _task_identity_matches(
        task_identity_context["task_xml"], task_identity_context["plan"]
    )
    return task_identity_context


@when(
    "the exported task is disabled",
    target_fixture="task_identity_context",
)
def disable_exported_task(
    task_identity_context: dict[str, object],
) -> dict[str, object]:
    namespace = {"task": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    root = ET.fromstring(task_identity_context["task_xml"])
    root.find("task:Settings/task:Enabled", namespace).text = "false"
    task_identity_context["task_xml"] = ET.tostring(root, encoding="unicode")
    task_identity_context["matches"] = _task_identity_matches(
        task_identity_context["task_xml"], task_identity_context["plan"]
    )
    return task_identity_context


@when(
    parsers.parse("an existing task has a different {identity} during {operation}"),
    target_fixture="task_identity_context",
)
def evaluate_mismatched_task_operation(
    identity: str,
    operation: str,
    task_identity_context: dict[str, object],
) -> dict[str, object]:
    namespace_uri = "http://schemas.microsoft.com/windows/2004/02/mit/task"
    namespace = {"task": namespace_uri}
    root = ET.fromstring(task_identity_context["task_xml"])
    if identity == "action":
        root.find("task:Actions/task:Exec/task:Command", namespace).text = r"C:\Other\python.exe"
    elif identity == "principal":
        root.find("task:Principals/task:Principal/task:UserId", namespace).text = "S-1-5-21-9999"
    elif identity == "trigger":
        root.find("task:Triggers/task:LogonTrigger", namespace).tag = (
            f"{{{namespace_uri}}}TimeTrigger"
        )
    else:
        root.find("task:Settings/task:MultipleInstancesPolicy", namespace).text = "Parallel"
    altered_xml = ET.tostring(root, encoding="unicode")
    task_identity_context["original_xml"] = task_identity_context["task_xml"]
    task_identity_context["altered_xml"] = altered_xml
    normalized_operation = "register" if operation == "registration" else "unregister"
    try:
        task_identity_context["decision"] = _task_operation(
            normalized_operation,
            altered_xml,
            task_identity_context["plan"],
        )
    except ValueError:
        task_identity_context["decision"] = "rejected"
    return task_identity_context


@then("the installer rejects the existing task without changing its definition")
def mismatched_task_is_rejected_without_rewrite(
    task_identity_context: dict[str, object],
) -> None:
    assert task_identity_context["decision"] == "rejected"
    assert task_identity_context["task_xml"] == task_identity_context["original_xml"]
    assert task_identity_context["altered_xml"] != task_identity_context["original_xml"]


@then("the task identity matches the intended plan")
def exact_task_identity_matches(task_identity_context: dict[str, object]) -> None:
    assert task_identity_context["matches"] is True


@then("the task identity does not match the intended plan")
def changed_task_identity_is_rejected(task_identity_context: dict[str, object]) -> None:
    assert task_identity_context["matches"] is False


@given(
    "a logon dispatcher whose resident supervisor is inactive",
    target_fixture="logon_dispatch_context",
)
def inactive_logon_dispatcher() -> dict[str, object]:
    return {"active": False, "starts": 0, "focuses": 0, "results": []}


@when("the same automatic start is dispatched twice")
def dispatch_automatic_start_twice(logon_dispatch_context: dict[str, object]) -> None:
    context = logon_dispatch_context

    def start_resident() -> None:
        context["starts"] += 1
        context["active"] = True

    for _ in range(2):
        context["results"].append(
            portal_supervisor.dispatch_launch(
                lambda: context["active"],
                lambda: None,
                start_resident,
            )
        )


@then("the duplicate invocation does not start or focus another process")
def duplicate_automatic_start_is_noop(
    logon_dispatch_context: dict[str, object],
) -> None:
    assert logon_dispatch_context["results"] == ["started", "focused"]
    assert logon_dispatch_context["starts"] == 1
    assert logon_dispatch_context["focuses"] == 0