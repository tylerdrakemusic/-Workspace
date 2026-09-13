# Portal Supervisor Architecture

## Purpose

[`tools/portal_supervisor.py`](../tools/portal_supervisor.py) is the canonical resident process for the Workspace portal and its configured localhost services. It replaces launch-time orchestration in PowerShell with one Python owner for process startup, readiness, retries, runtime state, logs, and browser focus.

The supervisor binds only to `127.0.0.1:8790`. This loopback listener is the trust boundary for portal control requests. It is not an authenticated remote administration API and must not be exposed on a non-loopback interface.

## Ownership

| Component | Owns |
|---|---|
| [`tools/portal_supervisor.py`](../tools/portal_supervisor.py) | Single-instance dispatch, launch generations, port reclamation, process launch, readiness, retries, state, log retention, HTTP serving, and browser focus |
| [`tools/portal_servers.json`](../tools/portal_servers.json) | Enabled services and each service's command, working directory, configured port, readiness URL, accepted HTTP statuses, and optional iframe cache-bust capability |
| [`tools/dashboard_portal.py`](../tools/dashboard_portal.py) | Synchronous generation of `reports/portal.html`, including application of `iframe_cache_bust: false` for services that cannot accept generation query parameters |
| [`reports/portal.html`](../reports/portal.html) | Browser UI that reads authoritative state and sends control requests to the resident supervisor |
| [`tools/launch_portal.ps1`](../tools/launch_portal.ps1) and [`open_portal.ps1`](../open_portal.ps1) | Thin compatibility entry points that invoke Python and forward `--no-open` |
| [`tools/register_portal_protocol.ps1`](../tools/register_portal_protocol.ps1) | Reversible staging and HKCU registration for the `portal://` protocol and desktop shims |

`portal_servers.json` is the service inventory and launch contract. The supervisor rejects an enabled service missing `name`, `port`, `cmd`, `working_directory`, `readiness_url`, or `accepted_statuses`. The `enabled` flag controls inclusion. The optional `iframe_cache_bust` field is consumed during portal generation and defaults to cache-bust-compatible behavior when omitted.

## Launch And Single Instance Flow

1. A manual, PowerShell, VBS, desktop, or `portal://` entry point invokes `portal_supervisor.py`.
2. The dispatcher probes `GET http://127.0.0.1:8790/api/state` with a bounded timeout.
3. If a supervisor is active, the dispatcher sends `POST /api/focus` unless `--no-open` was requested. It does not create another launch generation or restart service processes.
4. If no supervisor is active, the dispatcher force-reclaims port `8790` and starts a detached resident Python process.
5. The resident process synchronously regenerates the portal shell before binding its HTTP server.
6. After binding, it allocates a launch generation and starts the configured services in a background restart operation. Browser opening is optional and points to `/portal.html?generation=<id>`.

The resident process is the single owner of supervisor state. The PowerShell, VBS, protocol, and desktop layers contain no readiness loop, service process ownership, or browser implementation.

## HTTP Contract

All responses include `Cache-Control: no-store`, `Pragma: no-cache`, and `Expires: 0`.

| Request | Behavior |
|---|---|
| `GET /` or `GET /portal.html` | Serves the generated portal shell and injects the active generation into compatible iframe URLs |
| `GET /api/state` | Returns the active generation and the supervisor-owned service state map |
| `POST /api/restart-all` | Allocates a new generation, starts restart work on a daemon thread, and returns `202` with the new generation |
| `POST /api/services/<name>/retry` | Runs one manual retry for the named enabled service in the active generation and returns `202` |
| `POST /api/focus` | Opens or focuses the current portal URL and returns `200`; it does not restart services |

Unknown POST paths return `404`. Service names in retry paths are URL-decoded before lookup.

## Service Startup And Recovery

For every restart generation, the supervisor first force-terminates processes listening on every enabled configured port. It then launches services through a `ThreadPoolExecutor` with exactly three workers. Commands are parsed into argument vectors and launched with `shell=False` from each configured working directory. PowerShell `-File` commands receive the configured project root through `-ProjectRoot`.

Each launch attempt polls its configured readiness URL for up to 30 seconds. Only configured accepted HTTP statuses mark the service ready. A failed first attempt receives one automatic retry, for a maximum of two attempts in the generation. The retry reclaims the service port before relaunching. After both attempts fail, the service remains failed until a user requests its per-service retry or starts a new restart-all generation.

A manual per-service retry stays in the active generation, reclaims that service's configured port, performs one launch attempt, and continues the attempt counter already recorded for the service.

## State And Logs

The in-memory state entry for each launched service contains:

- `pid`
- `command`
- `working_directory`
- `started_at`
- `launch_generation`
- `readiness`, one of `starting`, `ready`, or `failed`
- `attempt`
- `error`

The supervisor writes each process's stdout and stderr to port-named files under `logs/portal_supervisor/<generation>/`. It retains the latest ten generation directories and removes older generation directories after restart-all completes. Logs do not replace the in-memory API state and are not a cross-process persistence mechanism.

## Portal Cache Behavior

Portal generation is synchronous at resident startup, so the shell exists before the HTTP server and browser handoff proceed. The supervisor serves the shell and API with no-store headers. It injects the current generation as an iframe query parameter to force a fresh service document after restart-all.

Some applications treat unknown query parameters as state. Those services set `iframe_cache_bust: false` in `portal_servers.json`; `dashboard_portal.py` emits them as deferred `data-src` frames so supervisor generation injection does not rewrite their service URL.

## Thin Shims, Staging, And Rollback

`register_portal_protocol.ps1` stages protocol and desktop launchers under `%LOCALAPPDATA%\WorkspacePortal`, an ASCII-safe path for Windows shell handling. The staged PowerShell scripts invoke the canonical Python supervisor. VBS files hide the console window and delegate to those scripts or directly to the supervisor. The HKCU `portal://` command points to the staged protocol VBS shim.

Before overwriting an existing staged file, registration copies it to a timestamped `.backup-<timestamp>` sibling. Rollback is an operator action: copy each selected backup over its staged original, then restore or remove the HKCU protocol registration as appropriate. Staging changes the launch indirection only. It does not transfer service ownership away from `portal_supervisor.py`.

## Architectural Constraints

- Keep the supervisor bound to `127.0.0.1` unless authentication and a new trust model are designed and reviewed.
- Add or change services through `portal_servers.json`; do not duplicate service orchestration in launch scripts.
- Keep PowerShell, VBS, desktop, and protocol entry points as thin shims.
- Preserve configured-port reclamation before launch and retry.
- Preserve the three-worker startup bound, the 30-second attempt deadline, one automatic retry, and explicit manual retry.
- Preserve generation-scoped logs and ten-generation retention unless the operational contract is deliberately revised.
- Treat `/api/state` as the authoritative live projection while the resident process is running.