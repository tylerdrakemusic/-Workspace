# FR-20260509-portal-hygiene-sprint — ⊕Workspace Portal Hygiene Sprint

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260509-portal-hygiene-sprint
- **Title:** ⊕Workspace Portal Hygiene Sprint — desktop launcher, studio dedup, biomarker live server, Agent Ops sync, console errors
- **Type:** fix + chore
- **Risk:** low-medium
- **Projects:** ⊕Workspace, ❤Music, ∞Life
- **State:** MERGED
- **Branch:** fix/workspace/fr-20260509-portal-hygiene-sprint
- **PRs:** #113 (⊕Workspace, merged), #20 (∞Life, merged), #35 (❤Music, merged)
- **Cycle timer:** 30819e22-8e38-41ef-bb77-5a27938b07dd
- **Opened:** 2026-05-09
- **Last updated:** 2026-05-09
- **Merged at:** 2026-05-09 (SHA: 30e63b16)
- **Signed off at:** —
- **Closed:** —
- **Final state:** MERGED

### Acceptance Criteria

1. **Desktop shortcut calls `open_portal.ps1` directly** — the staged PS1 written during step 8 of `open_portal.ps1` must invoke `open_portal.ps1` (not bare `Start-Process portal.html`). All servers start on desktop launch.
2. **Single studio entry in portal sidebar** — `⊕Workspace/dashboard.json` stale `studio-equipment-panel` entry (port 5060) removed. `❤Music/dashboard.json` studio entry renamed to `"❤ Studio"`.
3. **Biomarker Dashboard typed as `flask_app`** — `∞Life/dashboard.json` updated: `type` → `flask_app`, `url` → `http://localhost:8300`. Sidebar shows LIVE badge instead of STATIC.
4. **FR dashboard + Agent Ops auto-regen on portal launch** — `open_portal.ps1` runs `fr_dashboard.py` and `agent_ops_monitor.py --fix --no-open` before opening the browser. FR panel and health badge always reflect current state.
5. **CORS bug fixed in agent_ops_dashboard** — `tools/agent_ops_monitor.py` health-check URL corrected from `file:///F:/api/health` to a valid `http://localhost:<port>/api/health` or health-check removed if unused.
6. **Mermaid NaN fix in diagrams dashboard** — `tools/diagrams_dashboard.py` corrected so no `translate(undefined, NaN)` transforms appear in the rendered output.

### Out of Scope
- No new dashboards or features
- No changes to server startup scripts other than `open_portal.ps1`
- No changes to ∞Life health data or database

### Concurrency Notes
- Conflicts with: none
- Depends on: nothing (all targets are config/tooling, no logic changes)

### Deliverable Tracker

| #   | Deliverable                                          | Owner                  | Status      | Proof | Updated    |
| --- | ---------------------------------------------------- | ---------------------- | ----------- | ----- | ---------- |
| AC1 | Desktop shortcut calls open_portal.ps1               | ⊕workspace-overseer    | done        | open_portal.ps1 step 8 writes launcher | 2026-05-09 |
| AC2 | Remove stale studio entry from ⊕Workspace dashboard.json; rename ❤Music entry to "❤ Studio" | ⊕workspace-overseer | done | dashboard.json committed | 2026-05-09 |
| AC3 | ∞Life dashboard.json: type=flask_app, url=:8300      | ⊕workspace-overseer    | done        | PR #20 merged | 2026-05-09 |
| AC4 | open_portal.ps1: auto-regen FR + Agent Ops on launch | ⊕workspace-overseer    | done        | open_portal.ps1 step 8 pre-launch block | 2026-05-09 |
| AC5 | Fix CORS URL in agent_ops_monitor.py                 | ⊕workspace-overseer    | done        | file:// guard added | 2026-05-09 |
| AC6 | Fix Mermaid NaN in diagrams_dashboard.py             | ⊕workspace-overseer    | done        | useMaxWidth: false added | 2026-05-09 |

### Tyler's Original Request

> Portal hygiene sprint observed via Playwright on file:///F:/%E2%8A%95Workspace/reports/portal.html.
> Issues found: servers not restarted when launching from desktop; multiple studio equipment panels
> (should be just 1 named "❤ Studio"); discrepancy between Agent Ops Health (22 gaps) and Agent Ops
> Monitor (21 gaps); Studio Equipment server port 5065 not starting on desktop launch; Biomarker
> Dashboard panel showing as Static instead of Live; Feature Requests panel out of sync.
> Include console error fixes (CORS in agent_ops_dashboard, Mermaid NaN in diagrams).

---

## Event Log

| Date | Event | Agent |
|------|-------|-------|
| 2026-05-09 | FR opened, scoped, triaged | ⊕workspace-intake |
| 2026-05-09 | Tyler confirmed FR draft via grill-me interview | Tyler |
| 2026-05-09 | All 6 ACs implemented and committed | ⊕workspace-overseer |
| 2026-05-09 | PR #20 (∞Life) merged | ⊕workspace-ci |
| 2026-05-09 | PR #35 (❤Music) merged | ⊕workspace-ci |
| 2026-05-09 | Fixed pre-existing CI failures: favicon + data-icon-prompt in portal | ⊕workspace-overseer |
| 2026-05-09 | PR #113 (⊕Workspace) merged — SHA 30e63b16 | ⊕workspace-ci |
