# ⊕Workspace — AI Agent TODO

**Workflow:** Pick the top uncompleted task, mark it `[IN PROGRESS]`, execute, mark `[DONE]`.

---

## Infrastructure — MCP Servers

MCP (Model Context Protocol) servers extend agent capabilities inside VS Code Copilot.
These need analysis before install — let them soak.

- [x] **Audit: inventory all currently active MCP servers** — Playwright MCP (`@playwright/mcp`) + GitHub MCP (`api.githubcopilot.com/mcp`) confirmed wired in `C:\Users\tyler\AppData\Roaming\Code\User\mcp.json`. Both active. (2026-04-24)

- [ ] **Research: identify gold-standard MCP servers for this workspace** — candidate list to evaluate:
  - **Playwright MCP** (`@playwright/mcp`) — browser automation: headless print, web scraping, Spotify/DistroKid UI automation, screenshot capture for ❤Music 1-pagers
  - **Filesystem MCP** — structured file reads/writes across all project roots with path sandboxing
  - **SQLite MCP** — direct DB introspection for `heartmusic.db`, `infinitelife.db`, `agent_perf.db` without needing Python scripts
  - **GitHub MCP** — PR/issue/commit operations for the `f:\executedcode\` repo
  - **Fetch/Browser MCP** — web fetch for ∞Life research agent (PubMed, supplement databases)
  - **Memory MCP** — persistent knowledge graph across sessions (evaluate vs. current `/memories/` file approach)
  - **Sequential Thinking MCP** — structured reasoning chains for ∞life-risk and ∞life-research agents

- [x] **Decision: install Playwright MCP** — DONE. `@playwright/mcp@latest` wired in user-level `mcp.json`. FR-20260422-playwright-mcp-setup REVIEW_REQUESTED. (2026-04-24)

- [ ] **Decision: install SQLite MCP** — direct DB queries from agent context without Python subprocess round-trips. Evaluate read-only vs. read-write mode for safety.

- [x] **Decision: install GitHub MCP** — DONE. GitHub MCP (`api.githubcopilot.com/mcp`, type: http) wired in user-level `mcp.json`. Agents use it actively. (2026-04-24)

- [ ] **Post-install: alignment audit** — after any MCP installs, run `⊕workspace-alignment` to verify all agent startup files reference new capabilities correctly.

---

## Workspace Utilities

- [ ] Add `workspace_discovery.py` tests — currently untested
- [ ] Add perf report aggregation command to `perf_cli.py` — `perf_cli.py summary --last 7d` showing all runs
