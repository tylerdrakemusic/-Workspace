"""Resident process supervisor for workspace portal services."""

from __future__ import annotations

import argparse
import ctypes
import hmac
import json
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
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "tools" / "portal_servers.json"
PORTAL_PATH = PROJECT_ROOT / "reports" / "portal.html"
LOG_ROOT = PROJECT_ROOT / "logs" / "portal_supervisor"
SUPERVISOR_HOST = "127.0.0.1"
SUPERVISOR_PORT = 8790


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
) -> list[int]:
    """Force-terminate every Windows process listening on the TCP port."""
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
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
            raise RuntimeError(f"port {port} reclaim failed: netstat: {detail}"[:160])
        return list(dict.fromkeys(int(pid) for pid in pattern.findall(result.stdout)))

    pids = listener_pids()
    for pid in pids:
        result = run(
            ["taskkill", "/PID", str(pid), "/F", "/T"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
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
) -> object:
    """Launch one exact configured command with generation-scoped logs."""
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
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


def _supervisor_active() -> bool:
    try:
        with urlopen(
            f"http://{SUPERVISOR_HOST}:{SUPERVISOR_PORT}/api/state", timeout=0.5
        ) as response:
            return int(response.status) == 200
    except (OSError, TimeoutError):
        return False


def _post_supervisor(path: str) -> None:
    with urlopen(
        f"http://{SUPERVISOR_HOST}:{SUPERVISOR_PORT}/api/state", timeout=2
    ) as response:
        csrf_token = str(json.load(response)["csrf_token"])
    request = Request(
        f"http://{SUPERVISOR_HOST}:{SUPERVISOR_PORT}{path}",
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


def _generate_portal() -> None:
    subprocess.run(  # nosec B603 - fixed local executable and script
        [sys.executable, str(PROJECT_ROOT / "tools" / "dashboard_portal.py"), "--regen", "--no-open"],
        cwd=str(PROJECT_ROOT),
        check=True,
        shell=False,
    )


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
            if origin is not None and origin != f"http://{expected_host}":
                return False
            supplied_token = self.headers.get("X-Supervisor-CSRF", "")
            return hmac.compare_digest(supplied_token, supervisor.csrf_token)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/state":
                self._json_response(200, supervisor.snapshot(include_token=True))
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
    server_factory: Callable[[], ThreadingHTTPServer],
    browser_open: Callable[[str], object],
    start_background: Callable[[Callable[[], object]], object],
    open_browser: bool,
) -> None:
    """Generate, bind, warm services, and serve the resident portal."""
    generate_portal()
    server = server_factory()
    generation = supervisor.new_generation()
    start_background(lambda: supervisor.restart_all(generation))
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

    def start_retry_service(self, name: str) -> bool:
        """Start one service retry unless another mutation operation is active."""
        service = self._service_named(name)
        return self._start_operation(lambda: self._retry_service(service))

    def new_generation(self) -> str:
        """Allocate and retain a new launch generation before warmup starts."""
        generation = uuid4().hex
        generation_logs = self.log_root / generation
        generation_logs.mkdir(parents=True, exist_ok=True)
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
                self.reclaim_port(int(service["port"]))
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
        message = str(error).strip() or type(error).__name__
        prefix = f"port {port} reclaim failed"
        if not message.casefold().startswith(prefix.casefold()):
            message = f"{prefix}: {message}"
        with self._state_lock:
            self.state[str(service["name"])] = {
                "pid": None,
                "command": str(service["cmd"]),
                "working_directory": str(service["working_directory"]),
                "started_at": None,
                "launch_generation": generation,
                "readiness": "failed",
                "attempt": attempt,
                "error": message[:160],
            }

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
                    self.reclaim_port(port)
                except Exception as exc:
                    self._record_reclaim_failure(
                        service,
                        generation,
                        prior_attempts + attempt,
                        exc,
                    )
                    return
            process = self.launch_process(
                command,
                working_directory,
                generation_logs / f"{port}.stdout.log",
                generation_logs / f"{port}.stderr.log",
            )
            started_at = self.now()
            with self._state_lock:
                self.state[name] = {
                    "pid": process.pid,
                    "command": command,
                    "working_directory": working_directory,
                    "started_at": started_at,
                    "launch_generation": generation,
                    "readiness": "starting",
                    "attempt": prior_attempts + attempt,
                    "error": None,
                }
            ready, error = self.check_readiness(
                str(service["readiness_url"]),
                tuple(int(status) for status in service["accepted_statuses"]),
                30,
            )
            with self._state_lock:
                self.state[name]["readiness"] = "ready" if ready else "failed"
                self.state[name]["error"] = error
            if ready:
                return


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Workspace portal resident supervisor")
    parser.add_argument("--serve", action="store_true", help="run the resident supervisor")
    parser.add_argument("--no-open", action="store_true", help="do not open or focus a browser tab")
    parser.add_argument("--restart-all", action="store_true", help="restart all configured services")
    args = parser.parse_args()

    if not args.serve:
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
    run_resident(
        supervisor,
        generate_portal=_generate_portal,
        server_factory=lambda: create_http_server(
            (SUPERVISOR_HOST, SUPERVISOR_PORT), supervisor, PORTAL_PATH, browser
        ),
        browser_open=browser,
        start_background=lambda target: threading.Thread(target=target, daemon=True).start(),
        open_browser=not args.no_open,
    )


if __name__ == "__main__":
    main()