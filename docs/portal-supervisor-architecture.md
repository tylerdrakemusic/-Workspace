# Portal Supervisor Architecture

## Purpose

[`tools/portal_supervisor.py`](../tools/portal_supervisor.py) is the canonical resident process for the Workspace portal and its configured localhost services. It replaces launch-time orchestration in PowerShell with one Python owner for process startup, readiness, retries, runtime state, logs, and browser focus.

The supervisor binds only to `127.0.0.1:8790`. This loopback listener is the trust boundary for portal control requests. It is not an authenticated remote administration API and must not be exposed on a non-loopback interface.

## Ownership

| Component | Owns |
|---|---|
| [`tools/portal_supervisor.py`](../tools/portal_supervisor.py) | Single-instance dispatch, launch generations, fail-closed port reclamation, process launch, readiness, serialized mutations, synchronized state, rotating CSRF authorization, log retention, HTTP serving, and browser focus |
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
4. If no supervisor is active, the dispatcher reclaims port `8790` and starts a detached resident Python process only after reclamation succeeds. A `netstat` failure, `taskkill` failure, or surviving listener aborts startup rather than adopting an unknown process.
5. The resident process synchronously regenerates the portal shell before binding its HTTP server.
6. After binding `127.0.0.1:8790`, it allocates a launch generation and starts both configured-service warmup and optional dashboard regeneration in background operations. Optional regeneration is bounded and may not delay bind or browser handoff. Browser opening is optional and points to `/portal.html?generation=<id>`.

The resident process is the single owner of supervisor state and the only owner of `127.0.0.1:8790`. Every PowerShell, VBS, desktop, `portal://`, and restart entry point is a thin shim: it dispatches to the resident process and contains no readiness loop, service process ownership, generation state, or independent browser implementation.

## HTTP Contract

All responses include `Cache-Control: no-store`, `Pragma: no-cache`, and `Expires: 0`.

| Request | Behavior |
|---|---|
| `GET /` or `GET /portal.html` | Serves the generated portal shell and injects the active generation into compatible iframe URLs |
| `GET /api/state` | Returns one synchronized snapshot of the active generation, supervisor-owned service state map, and current CSRF token |
| `POST /api/restart-all` | Allocates a new generation, starts restart work on a daemon thread, and returns `202` with the new generation |
| `POST /api/services/<name>/retry` | Runs one manual retry for the named enabled service in the active generation and returns `202` |
| `POST /api/focus` | Opens or focuses the current portal URL and returns `200`; it does not restart services |

Mutation requests are authorized only when the `Host` is exactly the bound loopback authority, any supplied `Origin` matches that authority, and `X-Supervisor-CSRF` matches the current token. The token rotates with every new generation and is returned in API response headers so the portal can advance without reloading the shell. Unknown POST paths return `404`. Service names in retry paths are URL-decoded before lookup.

A single non-blocking operation lock serializes restart-all and per-service retry. A concurrent mutation returns `409 operation in progress`; it cannot interleave process replacement or state writes. State updates and API snapshots share a re-entrant state lock, so a response cannot combine one generation with another generation's partially updated service map.

## Service Startup And Recovery

For every restart generation, the supervisor first force-terminates processes listening on every enabled configured port and verifies that no listener remains. Reclamation is fail-closed per service: a failed inspection, termination, or post-termination verification records that service as failed and prevents launch against the stale listener. It then launches only successfully reclaimed services through a `ThreadPoolExecutor` with exactly three workers. Commands are parsed into argument vectors and launched with `shell=False` from each configured working directory. PowerShell `-File` commands receive the configured project root through `-ProjectRoot`.

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

Retention is deterministic: generation directories are ordered by modification time with the generation name as the tie-breaker. Cleanup keeps the current generation plus the newest nine other generations, or the newest ten when there is no current generation. The active generation is therefore never removed merely because its directory timestamp is older.

## Portal Cache Behavior

Portal generation is synchronous at resident startup, so the shell exists before the HTTP server and browser handoff proceed. Optional dashboard regeneration starts only after the supervisor has bound port `8790`. The supervisor serves the shell and API with no-store headers.

The portal's `applyGeneration` function updates cache-bust-compatible frames even when they already have a loaded `src`; this prevents a visible pane from retaining the prior generation. Restart-all first quiesces managed frames by removing their live `src`. State polling restores each frame only when that service reports `ready` for the active generation, so an old document cannot remain interactive while its backing process is being replaced.

Some applications treat unknown query parameters as state. Those services set `iframe_cache_bust: false` in `portal_servers.json`; `dashboard_portal.py` emits them as deferred `data-src` frames and `applyGeneration` preserves their exact configured URL. Executive uses this contract, so its iframe remains the query-free root `http://127.0.0.1:8200/`. Trade Approval Gate uses its dedicated `http://127.0.0.1:7475/health` endpoint for readiness rather than treating a root-page response as process health.

## Thin Shims, Staging, And Rollback

`register_portal_protocol.ps1` stages protocol and desktop launchers under `%LOCALAPPDATA%\WorkspacePortal`, an ASCII-safe path for Windows shell handling. The staged PowerShell scripts invoke the canonical Python supervisor. VBS files hide the console window and delegate to those scripts or directly to the supervisor. The HKCU `portal://` command points to the staged protocol VBS shim.

Before overwriting an existing staged file, registration copies it to a timestamped `.backup-<timestamp>` sibling. Rollback is an operator action: copy each selected backup over its staged original, then restore or remove the HKCU protocol registration as appropriate. Staging changes the launch indirection only. It does not transfer service ownership away from `portal_supervisor.py`.

## Architectural Constraints

- Keep the supervisor bound to `127.0.0.1` unless authentication and a new trust model are designed and reviewed.
- Preserve exact loopback `Host`, matching `Origin`, and rotating CSRF checks on every mutation endpoint.
- Preserve the operation lock and synchronized snapshots; concurrent restart/retry requests must continue to return `409`.
- Add or change services through `portal_servers.json`; do not duplicate service orchestration in launch scripts.
- Keep PowerShell, VBS, desktop, protocol, and restart entry points as thin shims.
- Preserve fail-closed configured-port reclamation before launch and retry.
- Preserve the three-worker startup bound, the 30-second attempt deadline, one automatic retry, and explicit manual retry.
- Preserve generation-scoped logs and deterministic latest-ten retention that always keeps the current generation unless the operational contract is deliberately revised.
- Preserve frame quiescence and active-generation readiness gating before managed iframes reload.
- Treat `/api/state` as the authoritative live projection while the resident process is running.
