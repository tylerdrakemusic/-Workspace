# FR-20260513-mcp-autostart-awareness — MCP Server Auto-Start Awareness

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260513-mcp-autostart-awareness
- **Title:** MCP Server Auto-Start Awareness
- **Type:** chore
- **Risk:** medium
- **Projects:** ⊕Workspace (primary), ∞life-orchestrator, ❤music-orchestrator, ⟨ψ⟩quantum-orchestrator, 👁ai-manifest-orchestrator
- **State:** BRANCHED
- **Branch:** chore/workspace/fr-20260513-mcp-autostart-awareness
- **PRs:** [-Workspace#143](https://github.com/tylerdrakemusic/-Workspace/pull/143) (draft)
- **Cycle timer:** 65c276af-6bc2-46e1-96db-ccc19f79e871
- **Opened:** 2026-05-13
- **Last updated:** 2026-05-13
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. `mcp.json` updated with `autoStart: true` on all three command-type servers (`playwright`, `sqlite`, `filesystem`); servers no longer show Stopped on workspace open
2. VS Code startup Task writes `f:\⊕Workspace\src\config\mcp_status.json` with live per-server status at `folderOpen`
3. All 5 orchestrator agents (overseer + 4 project orchestrators) log an MCP status line in their Context Bootstrap, reading from `mcp_status.json`
4. If a server is confirmed down after auto-start, orchestrators fall back to built-in tools where possible (e.g. `grep_search`/`file_search` instead of filesystem MCP) and emit a named warning — they do not halt

### Concurrency Notes

- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | `mcp.json` — add `autoStart: true` to playwright, sqlite, filesystem entries | ⊕workspace-ci | not-started | — | — |
| AC2 | VS Code startup Task + `mcp_status.json` writer script | ⊕workspace-ci | not-started | — | — |
| AC3 | Overseer `.agent.md` — add MCP pre-flight block to Context Bootstrap | ⊕workspace-ci | not-started | — | — |
| AC4 | ∞life-orchestrator `.agent.md` — add MCP pre-flight block | ⊕workspace-ci | not-started | — | — |
| AC5 | ❤music-orchestrator `.agent.md` — add MCP pre-flight block | ⊕workspace-ci | not-started | — | — |
| AC6 | ⟨ψ⟩quantum-orchestrator `.agent.md` — add MCP pre-flight block | ⊕workspace-ci | not-started | — | — |
| AC7 | 👁ai-manifest-orchestrator `.agent.md` — add MCP pre-flight block | ⊕workspace-ci | not-started | — | — |

### Tyler's Original Request

> sometimes I forget to start the mcp servers, can we have the agents aware of installed mcp servers and start them?

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-13T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened via grill-me interview, triage complete → TRIAGED

**Details:**
- Root cause confirmed: command-type MCP servers (playwright, sqlite, filesystem) show as Stopped in the MCP panel at session start; github (HTTP) is always-on
- Fix shape: `mcp.json` `autoStart` flag as primary; VS Code startup Task writing `mcp_status.json` as agent-awareness layer; orchestrator-layer pre-flight checks (5 agents); graceful degradation with built-in tool fallback (no halt)
- Scope: ⊕Workspace config + all 5 orchestrator `.agent.md` files
- Out of scope: specialist agent updates, Memory MCP, container-tools MCP, sequential thinking MCP, external process spawning
- Tyler's grill-me answers: failure-mode=manual-click; fix-shape=both; trigger=workspace-open; agent-awareness=status-file; consumers=orchestrator-layer; autostart-mechanism=mcp.json-flag; degradation=fallback-warn

---

### 2026-05-13T00:00:00Z — ⊕workspace-ci

**Event:** state-transition → BRANCHED

**Summary:** Branch created; draft PR opened → BRANCHED

**Details:**
- Branch: `chore/workspace/fr-20260513-mcp-autostart-awareness` created from `main` (7f3b0f0)
- Draft PR opened on tylerdrakemusic/-Workspace
- Registry updated: TRIAGED → BRANCHED
- Ledger created with full triage context; BRANCHED state recorded
