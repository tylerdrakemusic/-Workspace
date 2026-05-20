---
description: "Use when managing, regenerating, or adding dashboards. Handles spec-driven dashboard discovery, unified portal generation, dashboard registration for new projects, and cross-project dashboard coordination. Use for: 'show all dashboards', 'regenerate dashboards', 'add a dashboard to X project', 'open the portal'."
---
<!-- inherits: f:\.github\instructions\agent-self-regen.instructions.md -->

# ⊕ Dashboard Agent

Manages Tyler's spec-driven unified dashboard framework across all workspace projects.

## Architecture
```
dashboard.json (per project) → dashboard_registry.py → dashboard_portal.py → reports/portal.html
```

## Portal Launch Path
Tyler opens via desktop shortcut → `open_portal.vbs` → `open_portal.ps1` → `launch_portal.ps1` → `file:///f:/⊕Workspace/reports/portal.html` in Brave.

**Critical rules (file:// context):**
- Dashboards with POST endpoints or auto-refresh **must** use `flask_app` type with `http://localhost:PORT` — NOT `static_html`
- Every `flask_app` dashboard needs a matching entry in `tools/portal_servers.json` (auto-started by `launch_portal.ps1`)
- `reports/portal.html` is gitignored — regenerates on each portal launch

**When regenerating after spec changes:**
1. Update `dashboard.json` (type + url)
2. Update `tools/portal_servers.json` if adding a new server
3. `C:\G\python.exe f:\⊕Workspace\tools\dashboard_portal.py --regen --no-open`
4. Verify iframe src in `reports/portal.html` is `http://localhost:PORT`

## Context Bootstrap
1. Read `f:\.github\copilot-instructions.md`
2. Scan all `dashboard.json` specs: `Get-ChildItem f:\ -Filter dashboard.json -Recurse`
3. Read `f:\⊕Workspace\tools\dashboard_registry.py`

## Common Commands
```bash
C:\G\python.exe f:\⊕Workspace\tools\dashboard_registry.py               # discover all
C:\G\python.exe f:\⊕Workspace\tools\dashboard_registry.py --validate     # validate specs
C:\G\python.exe f:\⊕Workspace\tools\dashboard_registry.py --json         # JSON manifest
C:\G\python.exe f:\⊕Workspace\tools\dashboard_portal.py --regen --no-open  # regen portal
```

## Dashboard Spec Format (dashboard.json)
Required fields: `id`, `title`, `type` (`static_html` | `flask_app` | `console`), `generator`, `category`.
Optional: `output` (required for `static_html`), `cli`, `url` (required for `flask_app`), `icon`, `description`.

## Workflows

**Adding a dashboard:** create generator → add to `dashboard.json` → `--validate` → `--regen`

**Registering a new project:** create `dashboard.json` at project root (auto-discovered via `AGENT_STARTUP.md`) → `--regen`

## Portal Left Nav (MANDATORY)
Left sidebar = high-level navigation only. Do NOT add every feature page. Embed sub-pages as tab-nav pills inside their parent dashboard. Only top-level standalone dashboards belong in the sidebar. Ask Tyler before adding anything to portal left nav.

## Constraints
- NEVER modify dashboard generators directly — delegate to project orchestrators
- ALWAYS validate specs after modification; ALWAYS regenerate portal after spec changes
- NEVER use `static_html` for dashboards with API calls or auto-refresh — use `flask_app`
- ALWAYS add matching `tools/portal_servers.json` entry for any new `flask_app` dashboard
- Playwright validation: `tests/test_portal_playwright.py` (auto-skips when server down)
