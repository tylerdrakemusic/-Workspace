"""Resident process supervisor for workspace portal services."""

from __future__ import annotations

import argparse
import base64
import binascii
import ctypes
import hmac
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess  # nosec B404 - fixed executable names and shell=False
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PureWindowsPath
from typing import Callable
from xml.etree import ElementTree as ET
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from fr_portal_server import database_backup_health_payload


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "tools" / "portal_servers.json"
SUPERVISOR_SCRIPT_PATH = PROJECT_ROOT / "tools" / "portal_supervisor.py"
PORTAL_PATH = PROJECT_ROOT / "reports" / "portal.html"
LOG_ROOT = PROJECT_ROOT / "logs" / "portal_supervisor"
SUPERVISOR_HOST = "127.0.0.1"
SUPERVISOR_PORT = 8790
OPTIONAL_REGEN_TIMEOUT_SECONDS = 180
OPTIONAL_REGEN_LOG_PATH = LOG_ROOT / "optional-regeneration.log"
SERVICE_MONITOR_INTERVAL_SECONDS = 30
SERVICE_PROBE_TIMEOUT_SECONDS = 3
SERVICE_RECOVERY_BASE_DELAY_SECONDS = 30
SERVICE_RECOVERY_MAX_DELAY_SECONDS = 300
SERVICE_ATTENTION_FAILURE_THRESHOLD = 3
LOGON_TASK_NAME = "Workspace Portal Supervisor - AtLogOn"
TASK_SCHEDULER_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"
TASK_PYTHON_PATH = r"C:\G\python.exe"


class ConfigurationError(ValueError):
    """Raised when the supervisor configuration is incomplete or invalid."""


def _windows_command_argv(command: str) -> list[str]:
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return [
            argument[1:-1]
            if len(argument) >= 2 and argument[0] == argument[-1] == '"'
            else argument
            for argument in shlex.split(command, posix=False)
        ]

    argument_count = ctypes.c_int()
    command_line_to_argv = windll.shell32.CommandLineToArgvW
    command_line_to_argv.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    command_line_to_argv.restype = ctypes.POINTER(wintypes.LPWSTR)
    arguments = command_line_to_argv(command, ctypes.byref(argument_count))
    if not arguments:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [arguments[index] for index in range(argument_count.value)]
    finally:
        local_free = windll.kernel32.LocalFree
        local_free.argtypes = [wintypes.HLOCAL]
        local_free.restype = wintypes.HLOCAL
        local_free(arguments)


def _launch_argv(command: str, working_directory: str) -> list[str]:
    arguments = _windows_command_argv(command)
    executable = Path(arguments[0]).name.casefold()
    if executable in {"powershell.exe", "pwsh.exe"} and any(
        argument.casefold() == "-file" for argument in arguments[1:]
    ):
        arguments.extend(["-ProjectRoot", working_directory])
    return arguments


def reclaim_port(
    port: int,
    *,
    run: Callable[..., object] = subprocess.run,
    require_managed_owner: bool = False,
    managed_process: object | None = None,
) -> list[int]:
    """Reclaim a listener, optionally requiring its live supervisor-owned process."""
    pattern = re.compile(
        rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    def listener_pids() -> list[int]:
        result = run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
            raise RuntimeError(f"port {port} reclaim failed: netstat: {detail}"[:160])
        return list(dict.fromkeys(int(pid) for pid in pattern.findall(result.stdout)))

    pids = listener_pids()
    if require_managed_owner:
        managed_pid: int | None = None
        process_active = False
        if managed_process is not None:
            try:
                managed_pid = int(getattr(managed_process, "pid"))
                poll = getattr(managed_process, "poll")
                process_active = callable(poll) and poll() is None
            except (AttributeError, TypeError, ValueError, OSError):
                process_active = False
        if pids and (not process_active or set(pids) != {managed_pid}):
            raise RuntimeError(f"port {port} reclaim failed: ownership unverified")
        if managed_pid is None or not process_active:
            return []
        try:
            managed_process.terminate()
            managed_process.wait(timeout=5)
        except Exception:
            raise RuntimeError(f"port {port} reclaim failed: managed process stop failed") from None
        remaining = listener_pids()
        if remaining:
            raise RuntimeError(f"port {port} reclaim failed: managed listener remains")
        return [managed_pid]

    for pid in pids:
        result = run(
            ["taskkill", "/PID", str(pid), "/F", "/T"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
            raise RuntimeError(
                f"port {port} reclaim failed: taskkill PID {pid}: {detail}"[:160]
            )
    remaining = listener_pids()
    if remaining:
        pid_list = ", ".join(str(pid) for pid in remaining)
        raise RuntimeError(
            f"port {port} reclaim failed: listener remains (PID {pid_list})"[:160]
        )
    return pids


def check_http_readiness(
    url: str,
    accepted_statuses: tuple[int, ...],
    deadline_seconds: int,
    *,
    opener: Callable[..., object] = urlopen,
    monotonic: Callable[[], float] = time.monotonic,
    wait: Callable[[float], None] = time.sleep,
) -> tuple[bool, str | None]:
    """Poll an HTTP URL until an accepted status or the attempt deadline."""
    deadline = monotonic() + deadline_seconds
    last_error = "readiness deadline exceeded"
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False, last_error[:160]
        status: int | None = None
        try:
            with opener(url, timeout=min(2.0, remaining)) as response:
                status = int(response.status)
        except HTTPError as exc:
            status = int(exc.code)
        except (OSError, TimeoutError) as exc:
            last_error = f"{type(exc).__name__}: {exc}" or type(exc).__name__
        if status is not None:
            if status in accepted_statuses:
                return True, None
            last_error = f"status {status}"
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False, last_error[:160]
        wait(min(0.25, remaining))


def launch_process(
    command: str,
    working_directory: str,
    stdout_path: Path,
    stderr_path: Path,
    *,
    popen: Callable[..., object] = subprocess.Popen,
    log_output: bool = True,
) -> object:
    """Launch one exact configured command with generation-scoped logs."""
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    if not log_output:
        return popen(  # nosec B603 - command is workspace-owned configuration
            _launch_argv(command, working_directory),
            cwd=working_directory,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=creation_flags,
        )
    with stdout_path.open("ab") as stdout_file, stderr_path.open("ab") as stderr_file:
        return popen(  # nosec B603 - command is workspace-owned configuration
            _launch_argv(command, working_directory),
            cwd=working_directory,
            stdout=stdout_file,
            stderr=stderr_file,
            shell=False,
            creationflags=creation_flags,
        )


def dispatch_launch(
    is_active: Callable[[], bool],
    focus_existing: Callable[[], None],
    start_resident: Callable[[], None],
) -> str:
    """Start the resident supervisor once, otherwise focus its portal."""
    if is_active():
        focus_existing()
        return "focused"
    start_resident()
    return "started"


def build_logon_task_plan(workspace_root: str | Path, user_sid: str) -> dict[str, object]:
    """Build the portable, credential-free current-user logon task contract."""
    if not re.fullmatch(r"S-1-\d+(?:-\d+)+", user_sid):
        raise ValueError("user_sid must be a Windows SID")
    root_path = PureWindowsPath(str(workspace_root))
    if not root_path.is_absolute():
        raise ValueError("workspace_root must be an absolute Windows path")
    if len(root_path.parts) >= 3 and root_path.parts[-2].casefold() == ".worktrees":
        root_path = PureWindowsPath(*root_path.parts[:-2])

    supervisor_path = root_path / "tools" / "portal_supervisor.py"
    action = {
        "command": TASK_PYTHON_PATH,
        "arguments": f'"{supervisor_path}" --no-open',
        "working_directory": str(root_path),
    }
    trigger = {"type": "Logon", "user_id": user_sid, "enabled": True}
    principal = {
        "user_id": user_sid,
        "logon_type": "InteractiveToken",
        "run_level": "LeastPrivilege",
    }
    settings = {"multiple_instances_policy": "IgnoreNew"}

    task = ET.Element(f"{{{TASK_SCHEDULER_NAMESPACE}}}Task", {"version": "1.2"})
    registration = ET.SubElement(task, f"{{{TASK_SCHEDULER_NAMESPACE}}}RegistrationInfo")
    ET.SubElement(registration, f"{{{TASK_SCHEDULER_NAMESPACE}}}Description").text = (
        "Dispatch the Workspace portal supervisor at current-user logon."
    )
    triggers = ET.SubElement(task, f"{{{TASK_SCHEDULER_NAMESPACE}}}Triggers")
    logon_trigger = ET.SubElement(triggers, f"{{{TASK_SCHEDULER_NAMESPACE}}}LogonTrigger")
    ET.SubElement(logon_trigger, f"{{{TASK_SCHEDULER_NAMESPACE}}}Enabled").text = "true"
    ET.SubElement(logon_trigger, f"{{{TASK_SCHEDULER_NAMESPACE}}}UserId").text = user_sid
    principals = ET.SubElement(task, f"{{{TASK_SCHEDULER_NAMESPACE}}}Principals")
    task_principal = ET.SubElement(
        principals,
        f"{{{TASK_SCHEDULER_NAMESPACE}}}Principal",
        {"id": "Author"},
    )
    ET.SubElement(task_principal, f"{{{TASK_SCHEDULER_NAMESPACE}}}UserId").text = user_sid
    ET.SubElement(task_principal, f"{{{TASK_SCHEDULER_NAMESPACE}}}LogonType").text = (
        principal["logon_type"]
    )
    ET.SubElement(task_principal, f"{{{TASK_SCHEDULER_NAMESPACE}}}RunLevel").text = (
        principal["run_level"]
    )
    task_settings = ET.SubElement(task, f"{{{TASK_SCHEDULER_NAMESPACE}}}Settings")
    ET.SubElement(
        task_settings,
        f"{{{TASK_SCHEDULER_NAMESPACE}}}MultipleInstancesPolicy",
    ).text = settings["multiple_instances_policy"]
    ET.SubElement(task_settings, f"{{{TASK_SCHEDULER_NAMESPACE}}}Enabled").text = "true"
    actions = ET.SubElement(
        task,
        f"{{{TASK_SCHEDULER_NAMESPACE}}}Actions",
        {"Context": "Author"},
    )
    execute = ET.SubElement(actions, f"{{{TASK_SCHEDULER_NAMESPACE}}}Exec")
    ET.SubElement(execute, f"{{{TASK_SCHEDULER_NAMESPACE}}}Command").text = action["command"]
    ET.SubElement(execute, f"{{{TASK_SCHEDULER_NAMESPACE}}}Arguments").text = action["arguments"]
    ET.SubElement(
        execute,
        f"{{{TASK_SCHEDULER_NAMESPACE}}}WorkingDirectory",
    ).text = action["working_directory"]

    return {
        "task_name": LOGON_TASK_NAME,
        "task_path": "\\",
        "action": action,
        "trigger": trigger,
        "principal": principal,
        "settings": settings,
        "stores_credentials": False,
        "task_xml": ET.tostring(task, encoding="unicode"),
    }


def task_xml_matches_identity(task_xml: str, plan: dict[str, object]) -> bool:
    """Check the action, principal, trigger, and instance policy of a task XML export."""
    namespace = {"task": TASK_SCHEDULER_NAMESPACE}
    try:
        root = ET.fromstring(task_xml)
        actions = root.findall("task:Actions/task:Exec", namespace)
        action_containers = root.findall("task:Actions", namespace)
        principals = root.findall("task:Principals/task:Principal", namespace)
        triggers = root.find("task:Triggers", namespace)
        trigger_children = list(triggers) if triggers is not None else []
        task_settings = root.find("task:Settings", namespace)
        action = plan["action"]
        principal = plan["principal"]
        trigger = plan["trigger"]
        settings = plan["settings"]
        return (
            root.tag == f"{{{TASK_SCHEDULER_NAMESPACE}}}Task"
            and len(action_containers) == 1
            and len(action_containers[0]) == 1
            and len(actions) == 1
            and actions[0].findtext("task:Command", namespaces=namespace)
            == action["command"]
            and actions[0].findtext("task:Arguments", namespaces=namespace)
            == action["arguments"]
            and actions[0].findtext("task:WorkingDirectory", namespaces=namespace)
            == action["working_directory"]
            and len(principals) == 1
            and principals[0].findtext("task:UserId", namespaces=namespace)
            == principal["user_id"]
            and principals[0].findtext("task:LogonType", namespaces=namespace)
            == principal["logon_type"]
            and principals[0].findtext("task:RunLevel", namespaces=namespace)
            == principal["run_level"]
            and len(trigger_children) == 1
            and trigger_children[0].tag
            == f"{{{TASK_SCHEDULER_NAMESPACE}}}LogonTrigger"
            and trigger_children[0].findtext("task:UserId", namespaces=namespace)
            == trigger["user_id"]
            and trigger_children[0].findtext("task:Enabled", namespaces=namespace)
            == "true"
            and task_settings is not None
            and task_settings.findtext("task:Enabled", namespaces=namespace) == "true"
            and task_settings.findtext(
                "task:MultipleInstancesPolicy", namespaces=namespace
            )
            == settings["multiple_instances_policy"]
        )
    except (AttributeError, ET.ParseError, TypeError):
        return False


def logon_task_operation(
    operation: str,
    existing_task_xml: str | None,
    plan: dict[str, object],
) -> str:
    """Resolve a safe registration or rollback action without changing machine state."""
    if operation not in {"register", "unregister"}:
        raise ValueError("operation must be register or unregister")
    if existing_task_xml is None:
        return "register" if operation == "register" else "noop"
    if not task_xml_matches_identity(existing_task_xml, plan):
        raise ValueError("existing scheduled task identity does not match the intended task")
    return "noop" if operation == "register" else "unregister"


def _supervisor_active() -> bool:
    try:
        with urlopen(
            f"http://{SUPERVISOR_HOST}:{SUPERVISOR_PORT}/api/state", timeout=0.5  # nosec A02 - validated local supervisor
        ) as response:
            return int(response.status) == 200
    except (OSError, TimeoutError):
        return False


def _post_supervisor(path: str) -> None:
    with urlopen(
        f"http://{SUPERVISOR_HOST}:{SUPERVISOR_PORT}/api/state", timeout=2  # nosec A02 - validated local supervisor
    ) as response:
        csrf_token = str(json.load(response)["csrf_token"])
    request = Request(
        f"http://{SUPERVISOR_HOST}:{SUPERVISOR_PORT}{path}",  # nosec A02 - validated local supervisor
        method="POST",
        headers={"X-Supervisor-CSRF": csrf_token},
    )
    with urlopen(request, timeout=2):
        return


def _start_resident_process(no_open: bool) -> None:
    reclaim_port(SUPERVISOR_PORT)
    command = [sys.executable, str(Path(__file__).resolve()), "--serve"]
    if no_open:
        command.append("--no-open")
    subprocess.Popen(  # nosec B603 - fixed local executable and script
        command,
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


def _generate_portal_shell(portal_path: Path = PORTAL_PATH) -> None:
    import dashboard_portal

    manifest = dashboard_portal.build_manifest()
    portal_path.parent.mkdir(parents=True, exist_ok=True)
    portal_path.write_text(
        dashboard_portal.render_portal(manifest),
        encoding="utf-8",
    )


def _regenerate_optional_dashboards(
    *,
    run: Callable[..., object] = subprocess.run,
    timeout_seconds: int = OPTIONAL_REGEN_TIMEOUT_SECONDS,
    log_path: Path = OPTIONAL_REGEN_LOG_PATH,
) -> None:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "dashboard_portal.py"),
        "--regen",
        "--no-open",
    ]
    try:
        result = run(  # nosec B603 - fixed local executable and script
            command,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        returncode = int(getattr(result, "returncode", 0))
        output = "\n".join(
            str(value or "")
            for value in (getattr(result, "stdout", ""), getattr(result, "stderr", ""))
        )
        diagnostic_lines = [
            line.strip()
            for line in output.splitlines()
            if re.search(r"error|timeout|missing|not found", line, re.IGNORECASE)
        ]
        if returncode:
            detail = diagnostic_lines[-1] if diagnostic_lines else f"exit {returncode}"
            message = f"optional dashboard regeneration failed: {detail}"
        elif diagnostic_lines:
            message = f"optional dashboard regeneration completed: {diagnostic_lines[-1]}"
        else:
            message = "optional dashboard regeneration completed"
    except subprocess.TimeoutExpired:
        message = f"optional dashboard regeneration timed out after {timeout_seconds}s"
    except OSError as exc:
        detail = str(exc).strip() or type(exc).__name__
        message = f"optional dashboard regeneration failed: {detail}"

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message[:240]}\n")


def _inject_generation_cache_busting(
    portal_html: str, generation: str, csrf_token: str = ""
) -> str:
    generation_json = json.dumps(generation)
    csrf_token_json = json.dumps(csrf_token)
    cache_busting = f"""<script>
(() => {{
  const generation = {generation_json};
    let csrfToken = {csrf_token_json};
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input, init = {{}}) => {{
        const url = new URL(typeof input === 'string' ? input : input.url, window.location.href);
        if ((init.method || 'GET').toUpperCase() === 'POST' && url.origin === window.location.origin) {{
            const headers = new Headers(init.headers || {{}});
            headers.set('X-Supervisor-CSRF', csrfToken);
            init = {{...init, headers}};
        }}
        const response = await originalFetch(input, init);
        const rotatedToken = response.headers.get('X-Supervisor-CSRF');
        if (url.origin === window.location.origin && rotatedToken) csrfToken = rotatedToken;
        return response;
    }};
  document.querySelectorAll('iframe[src]').forEach((frame) => {{
    const url = new URL(frame.src, window.location.href);
    url.searchParams.set('generation', generation);
    frame.src = url.toString();
  }});
}})();
</script>
"""
    return portal_html.replace("</body>", f"{cache_busting}</body>")


def create_http_server(
    address: tuple[str, int],
    supervisor: "PortalSupervisor",
    portal_path: Path,
    browser_open: Callable[[str], object],
    master_restart: Callable[[], str] | None = None,
) -> ThreadingHTTPServer:
    """Create the resident supervisor HTTP server without starting its loop."""

    class SupervisorHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(portal_path.parent), **kwargs)

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-store")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _json_response(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Supervisor-CSRF", supervisor.csrf_token)
            self.end_headers()
            self.wfile.write(body)

        def _mutation_authorized(self) -> bool:
            expected_host = f"{self.server.server_address[0]}:{self.server.server_port}"
            if self.headers.get("Host") != expected_host:
                return False
            origin = self.headers.get("Origin")
            if origin is not None and origin != f"http://{expected_host}":  # nosec A02 - local origin validation
                return False
            supplied_token = self.headers.get("X-Supervisor-CSRF", "")
            return hmac.compare_digest(supplied_token, supervisor.csrf_token)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/state":
                self._json_response(200, supervisor.snapshot(include_token=True))
                return
            if path == "/api/health/database-backup":
                self._json_response(200, database_backup_health_payload())
                return
            if path in ("/", "/portal.html"):
                portal_html = portal_path.read_text(encoding="utf-8")
                body = _inject_generation_cache_busting(
                    portal_html,
                    supervisor.current_generation or "starting",
                    supervisor.csrf_token,
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if not self._mutation_authorized():
                self._json_response(403, {"error": "forbidden"})
                return
            if path == "/api/restart-master":
                if master_restart is None:
                    self._json_response(503, {"error": "master restart unavailable"})
                    return
                generation = supervisor.prepare_restart_master()
                if generation is None:
                    self._json_response(409, {"error": "operation in progress"})
                    return
                try:
                    self._json_response(
                        202,
                        {"status": "restarting-master", "generation": generation},
                    )
                except Exception:
                    supervisor.finish_restart_master()
                    raise
                supervisor.finish_restart_master(master_restart)
                return
            if path == "/api/restart-all":
                generation = supervisor.start_restart_all()
                if generation is None:
                    self._json_response(409, {"error": "operation in progress"})
                    return
                self._json_response(
                    202, {"status": "restarting", "generation": generation}
                )
                return
            if path == "/api/focus":
                generation = supervisor.current_generation or "starting"
                browser_open(
                    f"http://127.0.0.1:{self.server.server_port}/portal.html?generation={generation}"
                )
                self._json_response(200, {"status": "focused"})
                return
            match = re.fullmatch(r"/api/services/([^/]+)/retry", path)
            if match:
                name = unquote(match.group(1))
                try:
                    started = supervisor.start_retry_service(name)
                except KeyError:
                    self._json_response(404, {"error": "service not found"})
                    return
                if not started:
                    self._json_response(409, {"error": "operation in progress"})
                    return
                self._json_response(202, {"status": "retrying", "service": name})
                return
            self._json_response(404, {"error": "not found"})

    return ThreadingHTTPServer(address, SupervisorHandler)


def run_resident(
    supervisor: "PortalSupervisor",
    *,
    generate_portal: Callable[[], object],
    regenerate_optional: Callable[[], object],
    server_factory: Callable[[], ThreadingHTTPServer],
    browser_open: Callable[[str], object],
    start_background: Callable[[Callable[[], object]], object],
    open_browser: bool,
    generation: str | None = None,
) -> None:
    """Generate, bind, warm services, and serve the resident portal."""
    generate_portal()
    server = server_factory()
    generation = (
        supervisor.new_generation()
        if generation is None
        else supervisor.new_generation(generation)
    )
    start_background(lambda: supervisor.restart_all(generation))
    start_background(supervisor.monitor_services)
    start_background(regenerate_optional)
    if open_browser:
        browser_open(
            f"http://127.0.0.1:{server.server_port}/portal.html?generation={generation}"
        )
    server.serve_forever()


class PortalSupervisor:
    """Own portal service launch generations and their runtime state."""

    def __init__(
        self,
        config: dict[str, object],
        *,
        log_root: Path,
        reclaim_port: Callable[[int], None],
        launch_process: Callable[..., object],
        check_readiness: Callable[..., tuple[bool, str | None]],
        now: Callable[[], float],
    ) -> None:
        self.config = config
        self.log_root = log_root
        self.reclaim_port = reclaim_port
        self.launch_process = launch_process
        self.check_readiness = check_readiness
        self.now = now
        self.state: dict[str, dict[str, object]] = {}
        self._processes: dict[str, object] = {}
        self._monitor_stop = threading.Event()
        self.current_generation: str | None = None
        self.generation_history: list[Path] = []
        self.csrf_token = secrets.token_urlsafe(32)
        self._operation_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._retain_latest_generations()

    @property
    def operation_active(self) -> bool:
        """Report whether a restart or retry operation currently owns the supervisor."""
        return self._operation_lock.locked()

    def snapshot(self, *, include_token: bool = False) -> dict[str, object]:
        """Return a consistent copy of the current generation and service state."""
        with self._state_lock:
            snapshot: dict[str, object] = {
                "generation": self.current_generation,
                "services": {
                    name: dict(service_state)
                    for name, service_state in self.state.items()
                },
            }
            if include_token:
                snapshot["csrf_token"] = self.csrf_token
            return snapshot

    def _start_operation(self, target: Callable[[], None]) -> bool:
        if not self._operation_lock.acquire(blocking=False):
            return False

        def run() -> None:
            try:
                target()
            finally:
                self._operation_lock.release()

        try:
            threading.Thread(target=run, daemon=True).start()
        except Exception:
            self._operation_lock.release()
            raise
        return True

    def start_restart_all(self) -> str | None:
        """Start Restart All unless another mutation operation is active."""
        if not self._operation_lock.acquire(blocking=False):
            return None
        try:
            generation = self.new_generation()

            def run() -> None:
                try:
                    self._restart_all(generation)
                finally:
                    self._operation_lock.release()

            threading.Thread(target=run, daemon=True).start()
        except Exception:
            self._operation_lock.release()
            raise
        return generation

    def prepare_restart_master(self) -> str | None:
        """Reserve the operation lock and generation for a resident-process handoff."""
        if not self._operation_lock.acquire(blocking=False):
            return None
        try:
            return self.new_generation()
        except Exception:
            self._operation_lock.release()
            raise

    def finish_restart_master(self, target: Callable[[], object] | None = None) -> None:
        """Release the handoff lock after the response is sent and launch is scheduled."""
        try:
            if target is not None:
                target()
        finally:
            self._operation_lock.release()

    def start_retry_service(self, name: str) -> bool:
        """Start one service retry unless another mutation operation is active."""
        service = self._service_named(name)
        return self._start_operation(lambda: self._retry_service(service))

    def new_generation(self, generation: str | None = None) -> str:
        """Allocate and retain a new launch generation before warmup starts."""
        generation = generation or uuid4().hex
        generation_logs = self.log_root / generation
        generation_logs.mkdir(parents=True, exist_ok=True)
        existing_mtimes = [
            path.stat().st_mtime_ns
            for path in self.log_root.iterdir()
            if path.is_dir() and path != generation_logs
        ]
        next_mtime = max(existing_mtimes, default=time.time_ns()) + 1_000_000
        os.utime(generation_logs, ns=(next_mtime, next_mtime))
        with self._state_lock:
            self.current_generation = generation
            self.csrf_token = secrets.token_urlsafe(32)
            self.generation_history.append(generation_logs)
        return generation

    def restart_all(self, generation: str | None = None) -> str:
        """Start a new launch generation for all enabled services."""
        with self._operation_lock:
            return self._restart_all(generation or self.new_generation())

    def _restart_all(self, generation: str) -> str:
        generation_logs = self.log_root / generation
        generation_logs.mkdir(parents=True, exist_ok=True)
        with self._state_lock:
            self.current_generation = generation
            if generation_logs not in self.generation_history:
                self.generation_history.append(generation_logs)
        services = [service for service in self.config.get("servers", []) if service.get("enabled", False)]
        launchable_services = []
        for service in services:
            try:
                self._reclaim_service_port(service)
            except Exception as exc:
                self._record_reclaim_failure(service, generation, 1, exc)
            else:
                launchable_services.append(service)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(
                    self._launch_service,
                    service,
                    generation,
                    generation_logs,
                    max_attempts=2,
                    port_already_reclaimed=True,
                    prior_attempts=0,
                )
                for service in launchable_services
            ]
            for future in futures:
                future.result()
        self._retain_latest_generations()
        return generation

    def retry_service(self, name: str) -> None:
        """Retry one service without replacing the active launch generation."""
        with self._operation_lock:
            self._retry_service(self._service_named(name))

    def _service_named(self, name: str) -> dict[str, object]:
        service = next(
            (
                item
                for item in self.config.get("servers", [])
                if item.get("enabled", False) and item.get("name") == name
            ),
            None,
        )
        if service is None:
            raise KeyError(name)
        return service

    def _reclaim_service_port(self, service: dict[str, object]) -> None:
        port = int(service["port"])
        if not service.get("require_managed_owner", False):
            self.reclaim_port(port)
            return
        self.reclaim_port(
            port,
            require_managed_owner=True,
            managed_process=self._processes.get(str(service["name"])),
        )

    def _retry_service(self, service: dict[str, object]) -> None:
        name = str(service["name"])
        with self._state_lock:
            if self.current_generation is None:
                raise RuntimeError("no active launch generation")
            generation = self.current_generation
            prior_attempts = int(self.state.get(name, {}).get("attempt", 0))
        self._launch_service(
            service,
            generation,
            self.log_root / generation,
            max_attempts=1,
            prior_attempts=prior_attempts,
        )

    def monitor_services(
        self,
        *,
        stop_event: threading.Event | None = None,
    ) -> None:
        """Probe monitored services until the resident supervisor is stopped."""
        stop_event = stop_event or self._monitor_stop
        while not stop_event.is_set():
            self.monitor_once()
            stop_event.wait(SERVICE_MONITOR_INTERVAL_SECONDS)

    def monitor_once(self) -> None:
        """Probe monitored services and recover due failures under the owner lock."""
        if not self._operation_lock.acquire(blocking=False):
            return
        try:
            services = [
                service
                for service in self.config.get("servers", [])
                if service.get("enabled", False) and service.get("monitor_health", False)
            ]
            for service in services:
                name = str(service["name"])
                with self._state_lock:
                    state = self.state.get(name)
                    process = self._processes.get(name)
                    if state is None:
                        continue
                    process_id = state.get("pid")
                poll = getattr(process, "poll", None)
                try:
                    process_active = callable(poll) and poll() is None
                except Exception:
                    process_active = False

                if process_id is None or not process_active:
                    with self._state_lock:
                        state = self.state.get(name)
                        if state is None:
                            continue
                        if state.get("readiness") != "failed":
                            self._record_health_failure_locked(state)
                        if state.get("next_retry_at") is None:
                            self._schedule_health_retry_locked(state)
                        retry_at = state.get("next_retry_at")
                    if retry_at is not None and self.now() >= float(retry_at):
                        self._retry_service(service)
                    continue

                try:
                    ready, _error = self.check_readiness(
                        str(service["readiness_url"]),
                        tuple(int(status) for status in service["accepted_statuses"]),
                        SERVICE_PROBE_TIMEOUT_SECONDS,
                    )
                except Exception:
                    ready = False

                with self._state_lock:
                    state = self.state.get(name)
                    if state is None:
                        continue
                    if ready:
                        state["readiness"] = "ready"
                        state["error"] = None
                        state["health_failures"] = 0
                        state["recovery_attempts"] = 0
                        state["next_retry_at"] = None
                        state["attention"] = False
                        continue
                    was_ready = state.get("readiness") == "ready"
                    self._record_health_failure_locked(state)
                    if was_ready and state.get("next_retry_at") is None:
                        self._schedule_health_retry_locked(state)
                    retry_at = state.get("next_retry_at")
                if retry_at is not None and self.now() >= float(retry_at):
                    self._retry_service(service)
        finally:
            self._operation_lock.release()

    @staticmethod
    def _record_health_failure_locked(
        state: dict[str, object],
        error: str = "service unavailable",
    ) -> None:
        failures = int(state.get("health_failures", 0)) + 1
        state["readiness"] = "failed"
        state["error"] = error
        state["health_failures"] = failures
        state["attention"] = failures >= SERVICE_ATTENTION_FAILURE_THRESHOLD

    def _schedule_health_retry_locked(self, state: dict[str, object]) -> None:
        attempts = int(state.get("recovery_attempts", 0)) + 1
        exponent = min(attempts - 1, 4)
        delay = min(
            SERVICE_RECOVERY_BASE_DELAY_SECONDS * (2**exponent),
            SERVICE_RECOVERY_MAX_DELAY_SECONDS,
        )
        state["recovery_attempts"] = attempts
        state["next_retry_at"] = self.now() + delay

    def _retain_latest_generations(self) -> None:
        with self._state_lock:
            if not self.log_root.exists():
                return
            generations = [
                path
                for path in self.log_root.iterdir()
                if path.is_dir()
                and re.fullmatch(r"[0-9a-f]{32}", path.name)
            ]
            generations.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
            current = next(
                (
                    path
                    for path in generations
                    if path.name == self.current_generation
                ),
                None,
            )
            candidates = [path for path in generations if path != current]
            retained = candidates[-(9 if current is not None else 10) :]
            if current is not None:
                retained.append(current)
            retained_paths = {path.resolve() for path in retained}
            for expired in generations:
                if expired.resolve() in retained_paths:
                    continue
                shutil.rmtree(expired)
            self.generation_history = [path for path in retained if path.exists()]

    def _record_reclaim_failure(
        self,
        service: dict[str, object],
        generation: str,
        attempt: int,
        error: Exception,
    ) -> None:
        port = int(service["port"])
        if service.get("require_managed_owner", False):
            message = f"port {port} reclaim failed"
            if "ownership unverified" in str(error).casefold():
                message += ": ownership unverified"
        else:
            message = str(error).strip() or type(error).__name__
            prefix = f"port {port} reclaim failed"
            if not message.casefold().startswith(prefix.casefold()):
                message = f"{prefix}: {message}"
        with self._state_lock:
            name = str(service["name"])
            previous = self.state.get(name, {})
            same_generation = previous.get("launch_generation") == generation
            state: dict[str, object] = {
                "pid": None,
                "command": str(service["cmd"]),
                "working_directory": str(service["working_directory"]),
                "started_at": None,
                "launch_generation": generation,
                "readiness": "failed",
                "attempt": attempt,
                "error": message[:160],
            }
            if service.get("monitor_health", False):
                state.update(
                    {
                        "health_failures": int(previous.get("health_failures", 0))
                        if same_generation
                        else 0,
                        "recovery_attempts": int(previous.get("recovery_attempts", 0))
                        if same_generation
                        else 0,
                        "next_retry_at": None,
                        "attention": bool(previous.get("attention", False))
                        if same_generation
                        else False,
                    }
                )
                self._record_health_failure_locked(state, message[:160])
                self._schedule_health_retry_locked(state)
            self.state[name] = state

    def _launch_service(
        self,
        service: dict[str, object],
        generation: str,
        generation_logs: Path,
        *,
        max_attempts: int,
        port_already_reclaimed: bool = False,
        prior_attempts: int = 0,
    ) -> None:
        port = int(service["port"])
        name = str(service["name"])
        command = str(service["cmd"])
        working_directory = str(service["working_directory"])
        for attempt in range(1, max_attempts + 1):
            if attempt > 1 or not port_already_reclaimed:
                try:
                    self._reclaim_service_port(service)
                except Exception as exc:
                    self._record_reclaim_failure(
                        service,
                        generation,
                        prior_attempts + attempt,
                        exc,
                    )
                    return
            launch_options = (
                {"log_output": False}
                if service.get("log_output", True) is False
                else {}
            )
            try:
                process = self.launch_process(
                    command,
                    working_directory,
                    generation_logs / f"{port}.stdout.log",
                    generation_logs / f"{port}.stderr.log",
                    **launch_options,
                )
            except Exception:
                if not service.get("monitor_health", False):
                    raise
                self._record_reclaim_failure(
                    service,
                    generation,
                    prior_attempts + attempt,
                    RuntimeError(f"port {port} reclaim failed: service unavailable"),
                )
                return
            with self._state_lock:
                self._processes[name] = process
            started_at = self.now()
            with self._state_lock:
                previous = self.state.get(name, {})
                same_generation = previous.get("launch_generation") == generation
                state: dict[str, object] = {
                    "pid": process.pid,
                    "command": command,
                    "working_directory": working_directory,
                    "started_at": started_at,
                    "launch_generation": generation,
                    "readiness": "starting",
                    "attempt": prior_attempts + attempt,
                    "error": None,
                }
                if service.get("monitor_health", False):
                    state.update(
                        {
                            "health_failures": int(previous.get("health_failures", 0))
                            if same_generation
                            else 0,
                            "recovery_attempts": int(previous.get("recovery_attempts", 0))
                            if same_generation
                            else 0,
                            "next_retry_at": None,
                            "attention": bool(previous.get("attention", False))
                            if same_generation
                            else False,
                        }
                    )
                self.state[name] = state
            try:
                ready, error = self.check_readiness(
                    str(service["readiness_url"]),
                    tuple(int(status) for status in service["accepted_statuses"]),
                    30,
                )
            except Exception:
                if not service.get("monitor_health", False):
                    raise
                ready, error = False, None
            with self._state_lock:
                state = self.state[name]
                if ready:
                    state["readiness"] = "ready"
                    state["error"] = None
                    if service.get("monitor_health", False):
                        state["health_failures"] = 0
                        state["recovery_attempts"] = 0
                        state["next_retry_at"] = None
                        state["attention"] = False
                elif service.get("monitor_health", False):
                    self._record_health_failure_locked(state)
                else:
                    state["readiness"] = "failed"
                    state["error"] = error
            if ready:
                return
        if service.get("monitor_health", False):
            with self._state_lock:
                state = self.state.get(name)
                if state is not None and state.get("next_retry_at") is None:
                    self._schedule_health_retry_locked(state)


def load_config(path: Path) -> dict[str, object]:
    """Load the supervisor service configuration."""
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    required = ("name", "port", "cmd", "working_directory", "readiness_url", "accepted_statuses")
    for service in config.get("servers", []):
        if not service.get("enabled", False):
            continue
        missing = [field for field in required if not service.get(field)]
        if missing:
            raise ConfigurationError(f"enabled service requires {', '.join(missing)}")
    return config


def _restart_master_process(
    server: ThreadingHTTPServer,
    generation: str,
    *,
    reclaim: Callable[[int], list[int]] = reclaim_port,
    popen: Callable[..., object] = subprocess.Popen,
) -> None:
    """Close the resident listener, reclaim it fail-closed, and launch fresh code."""
    server.shutdown()
    server.server_close()
    reclaim(SUPERVISOR_PORT)
    command = [
        sys.executable,
        str(SUPERVISOR_SCRIPT_PATH),
        "--serve",
        "--no-open",
        "--generation",
        generation,
    ]
    popen(  # nosec B603 - fixed local executable and script
        command,
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Workspace portal resident supervisor")
    parser.add_argument("--serve", action="store_true", help="run the resident supervisor")
    parser.add_argument("--no-open", action="store_true", help="do not open or focus a browser tab")
    parser.add_argument("--restart-all", action="store_true", help="restart all configured services")
    parser.add_argument("--restart-master", action="store_true", help="restart the resident supervisor")
    task_cli = parser.add_mutually_exclusive_group()
    task_cli.add_argument(
        "--logon-task-plan",
        action="store_true",
        help="print the current-user logon task plan as JSON",
    )
    task_cli.add_argument(
        "--logon-task-operation",
        choices=("register", "unregister"),
        help="resolve a safe task registration or rollback operation",
    )
    parser.add_argument("--user-sid", help="current user's Windows SID for task planning")
    parser.add_argument(
        "--workspace-root",
        default=str(PROJECT_ROOT),
        help="absolute Workspace checkout path for task planning",
    )
    parser.add_argument(
        "--task-xml-base64",
        help="base64-encoded exported task XML, if the named task exists",
    )
    parser.add_argument("--generation", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.logon_task_plan or args.logon_task_operation:
        if not args.user_sid:
            parser.error("--user-sid is required for logon task operations")
        try:
            plan = build_logon_task_plan(args.workspace_root, args.user_sid)
            if args.logon_task_plan:
                print(json.dumps(plan, ensure_ascii=False))
                return
            task_xml = (
                base64.b64decode(args.task_xml_base64, validate=True).decode("utf-8-sig")
                if args.task_xml_base64 is not None
                else None
            )
            print(logon_task_operation(args.logon_task_operation, task_xml, plan))
        except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
            parser.error(str(exc))
        return

    if not args.serve:
        if args.restart_master and _supervisor_active():
            _post_supervisor("/api/restart-master")
            print("restarting master")
            return
        if args.restart_all and _supervisor_active():
            _post_supervisor("/api/restart-all")
            print("restarting")
            return
        result = dispatch_launch(
            _supervisor_active,
            (lambda: None) if args.no_open else (lambda: _post_supervisor("/api/focus")),
            lambda: _start_resident_process(args.no_open),
        )
        print(result)
        return

    config = load_config(CONFIG_PATH)
    supervisor = PortalSupervisor(
        config,
        log_root=LOG_ROOT,
        reclaim_port=reclaim_port,
        launch_process=launch_process,
        check_readiness=check_http_readiness,
        now=time.time,
    )
    browser = lambda url: webbrowser.open(url, new=0, autoraise=True)
    server_ref: list[ThreadingHTTPServer] = []

    def restart_master() -> str:
        threading.Thread(
            target=_restart_master_process,
            args=(server_ref[0], str(supervisor.current_generation)),
            daemon=False,
        ).start()
        return str(supervisor.current_generation)

    def server_factory() -> ThreadingHTTPServer:
        server = create_http_server(
            (SUPERVISOR_HOST, SUPERVISOR_PORT),
            supervisor,
            PORTAL_PATH,
            browser,
            master_restart=restart_master,
        )
        server_ref.append(server)
        return server

    run_resident(
        supervisor,
        generate_portal=_generate_portal_shell,
        regenerate_optional=_regenerate_optional_dashboards,
        server_factory=server_factory,
        browser_open=browser,
        start_background=lambda target: threading.Thread(target=target, daemon=True).start(),
        open_browser=not args.no_open,
        generation=args.generation,
    )


if __name__ == "__main__":
    main()