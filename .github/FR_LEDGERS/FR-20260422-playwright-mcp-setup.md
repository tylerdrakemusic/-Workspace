# FR-20260422-playwright-mcp-setup — Wire Playwright MCP into Workspace

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260422-playwright-mcp-setup
- **Title:** Wire Playwright MCP into workspace — install Node.js + @playwright/mcp + configure mcp.json
- **Type:** chore
- **Risk:** low
- **Projects:** ⊕Workspace
- **State:** BRANCHED
- **Branch:** chore/workspace/playwright-mcp-setup
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/5 (draft)
- **Cycle timer:** 40ab5d3d-bda6-47b0-bbf6-d77e77576f0a
- **Opened:** 2026-04-22
- **Last updated:** 2026-04-22 (branched by ⊕workspace-ci)
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `node --version` and `npm --version` succeed in a new terminal (Node.js LTS installed system-wide).
2. `npm list -g @playwright/mcp` confirms the package is installed globally.
3. Chromium browser binary is present (`npx playwright install chromium` completes without error).
4. `C:\Users\tyler\AppData\Roaming\Code\User\mcp.json` contains a `"playwright"` server entry with `"command": "npx"` and `"args": ["@playwright/mcp@latest"]`.
5. After reloading VS Code, the Playwright MCP tools (e.g., `open_browser_page`, `click_element`) appear in the Copilot tool palette.
6. A smoke-test browser session (navigate to `https://example.com`, read page title) succeeds via MCP.
7. Setup documented in `f:\⊕Workspace\docs\mcp-setup.md` with install steps and verification commands.

### Concurrency Notes
- Conflicts with: FR-20260422-disable-plumbing-agents-dropdown (different files — clean)
- Depends on: none

### Tyler's Original Request
> Open a Feature Request for wiring Playwright MCP into the ⊕Workspace project.
>
> **Title:** Wire Playwright MCP into workspace — install Node.js + @playwright/mcp + configure mcp.json
>
> **Scope:** ⊕Workspace (primarily), but benefits all projects since Playwright MCP enables browser automation in agent workflows
>
> **Problem statement:**
> The Playwright MCP server is not configured. Investigation shows:
> - `C:\Users\tyler\AppData\Roaming\Code\User\mcp.json` only has the GitHub MCP server
> - Node.js is NOT installed on this machine (no node/npm/npx in PATH)
> - `@playwright/mcp` npm package is not installed
>
> **Work required:**
> 1. Install Node.js LTS (e.g., via winget or direct installer) — system-level
> 2. Install `@playwright/mcp` globally: `npm install -g @playwright/mcp`
> 3. Install Playwright browsers: `npx playwright install chromium` (at minimum)
> 4. Add Playwright MCP server entry to `C:\Users\tyler\AppData\Roaming\Code\User\mcp.json`
> 5. Verify the MCP server starts and tools appear in VS Code Copilot
> 6. Document setup in `f:\⊕Workspace\docs\mcp-setup.md` or similar
>
> **Type:** chore (infrastructure setup)
> **Priority:** medium
> **Projects affected:** ⊕Workspace (all projects benefit)

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-22T00:00:00 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (system-level Node.js install benefits all projects; mcp.json is user-scoped)
- Risk: low — no code changes to project source, no DB schema changes, no auth/secrets, no health interventions; mcp.json edit is reversible
- Acceptance criteria drafted (see Header)
- Concurrency check: no conflicts with FR-20260422-disable-plumbing-agents-dropdown (touches different files)
- Perf timer started: 40ab5d3d-bda6-47b0-bbf6-d77e77576f0a

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** 40ab5d3d-bda6-47b0-bbf6-d77e77576f0a — FR-20260422-playwright-mcp-setup cycle timer
