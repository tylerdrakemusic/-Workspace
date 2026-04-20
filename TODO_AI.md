# ⊕Workspace — AI Agent TODO

**Workflow:** Pick the top uncompleted task, mark it `[IN PROGRESS]`, execute, mark `[DONE]`.

---

## Infrastructure — MCP Servers

MCP (Model Context Protocol) servers extend agent capabilities inside VS Code Copilot.
These need analysis before install — let them soak.

- [ ] **Audit: inventory all currently active MCP servers** — check `settings.json` / `.vscode/mcp.json` for what is already installed and enabled. Document what each does and which projects benefit.

- [ ] **Research: identify gold-standard MCP servers for this workspace** — candidate list to evaluate:
  - **Playwright MCP** (`@playwright/mcp`) — browser automation: headless print, web scraping, Spotify/DistroKid UI automation, screenshot capture for ❤Music 1-pagers
  - **Filesystem MCP** — structured file reads/writes across all project roots with path sandboxing
  - **SQLite MCP** — direct DB introspection for `heartmusic.db`, `infinitelife.db`, `agent_perf.db` without needing Python scripts
  - **GitHub MCP** — PR/issue/commit operations for the `f:\executedcode\` repo
  - **Fetch/Browser MCP** — web fetch for ∞Life research agent (PubMed, supplement databases)
  - **Memory MCP** — persistent knowledge graph across sessions (evaluate vs. current `/memories/` file approach)
  - **Sequential Thinking MCP** — structured reasoning chains for ∞life-risk and ∞life-research agents

- [ ] **Decision: install Playwright MCP** — highest immediate ROI: replaces the Edge headless subprocess hack in `❤Music/tools/print_doc.py`, enables Spotify web scraping for ❤Music catalog, enables DistroKid automation. After analysis soak, install via `npm i @playwright/mcp` and wire into `.vscode/mcp.json`.

- [ ] **Decision: install SQLite MCP** — direct DB queries from agent context without Python subprocess round-trips. Evaluate read-only vs. read-write mode for safety.

- [ ] **Decision: install GitHub MCP** — needed for `⊕workspace-ci` agent to commit/push without terminal approval gates. Evaluate OAuth scope requirements.

- [ ] **Post-install: alignment audit** — after any MCP installs, run `⊕workspace-alignment` to verify all agent startup files reference new capabilities correctly.

---

## Workspace Utilities

- [ ] Add `workspace_discovery.py` tests — currently untested
- [ ] Add perf report aggregation command to `perf_cli.py` — `perf_cli.py summary --last 7d` showing all runs
