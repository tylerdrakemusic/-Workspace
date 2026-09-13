"""Resident process supervisor for workspace portal services."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404 - fixed executable names and shell=False
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
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


def reclaim_port(
    port: int,
    *,
    run: Callable[..., object] = subprocess.run,
) -> list[int]:
    """Force-terminate every Windows process listening on the TCP port."""
    result = run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    pattern = re.compile(
        rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    pids = list(dict.fromkeys(int(pid) for pid in pattern.findall(result.stdout)))
    for pid in pids:
        run(
            ["taskkill", "/PID", str(pid), "/F", "/T"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
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
            command,
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
    request = Request(
        f"http://{SUPERVISOR_HOST}:{SUPERVISOR_PORT}{path}", method="POST"
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


def _inject_generation_cache_busting(portal_html: str, generation: str) -> str:
    generation_json = json.dumps(generation)
    cache_busting = f"""<script>
(() => {{
  const generation = {generation_json};
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
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/state":
                self._json_response(
                    200,
                    {
                        "generation": supervisor.current_generation,
                        "services": supervisor.state,
                    },
                )
                return
            if path in ("/", "/portal.html"):
                portal_html = portal_path.read_text(encoding="utf-8")
                body = _inject_generation_cache_busting(
                    portal_html, supervisor.current_generation or "starting"
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
            if path == "/api/restart-all":
                generation = supervisor.new_generation()
                threading.Thread(
                    target=supervisor.restart_all, args=(generation,), daemon=True
                ).start()
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
                threading.Thread(target=supervisor.retry_service, args=(name,), daemon=True).start()
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

    def new_generation(self) -> str:
        """Allocate and retain a new launch generation before warmup starts."""
        generation = uuid4().hex
        self.current_generation = generation
        generation_logs = self.log_root / generation
        generation_logs.mkdir(parents=True, exist_ok=True)
        self.generation_history.append(generation_logs)
        return generation

    def restart_all(self, generation: str | None = None) -> str:
        """Start a new launch generation for all enabled services."""
        generation = generation or self.new_generation()
        self.current_generation = generation
        generation_logs = self.log_root / generation
        generation_logs.mkdir(parents=True, exist_ok=True)
        if generation_logs not in self.generation_history:
            self.generation_history.append(generation_logs)
        services = [service for service in self.config.get("servers", []) if service.get("enabled", False)]
        for service in services:
            self.reclaim_port(int(service["port"]))
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
                for service in services
            ]
            for future in futures:
                future.result()
        self._retain_latest_generations()
        return generation

    def retry_service(self, name: str) -> None:
        """Retry one service without replacing the active launch generation."""
        if self.current_generation is None:
            raise RuntimeError("no active launch generation")
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
        prior_attempts = int(self.state.get(name, {}).get("attempt", 0))
        self._launch_service(
            service,
            self.current_generation,
            self.log_root / self.current_generation,
            max_attempts=1,
            prior_attempts=prior_attempts,
        )

    def _retain_latest_generations(self) -> None:
        tracked = {path.resolve() for path in self.generation_history}
        existing = [
            path
            for path in self.log_root.iterdir()
            if path.is_dir()
            and re.fullmatch(r"[0-9a-f]{32}", path.name)
            and path.resolve() not in tracked
        ]
        generations = existing + self.generation_history
        for expired in generations[:-10]:
            shutil.rmtree(expired)
        self.generation_history = [path for path in generations[-10:] if path.exists()]

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
                self.reclaim_port(port)
            process = self.launch_process(
                command,
                working_directory,
                generation_logs / f"{port}.stdout.log",
                generation_logs / f"{port}.stderr.log",
            )
            started_at = self.now()
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