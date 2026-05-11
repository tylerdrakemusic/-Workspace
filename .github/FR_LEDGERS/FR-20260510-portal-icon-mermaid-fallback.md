# FR-20260510-portal-icon-mermaid-fallback — Portal icon fallback + Mermaid architecture fallback cleanup

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260510-portal-icon-mermaid-fallback
- **Title:** Portal icon fallback + Mermaid architecture fallback cleanup
- **Type:** fix
- **Risk:** low-medium
- **Projects:** ⊕Workspace
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 4fbd2632-8d7a-4364-ae27-078cd71b92af
- **Opened:** 2026-05-10
- **Last updated:** 2026-05-10
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Portal favicon renders custom icon reliably instead of default Brave icon.
2. Favicon loading is resilient via cache-busting and SVG fallback when ICO path fails.
3. `portal_icon.ico` integrity is validated during generation flow; failures are surfaced clearly.
4. Architecture diagram panel no longer hard-fails when Mermaid backends are unavailable.
5. Portal uses inline SVG fallback for architecture diagrams when Mermaid CLI/HTTP rendering is unavailable.
6. Live editor behavior is removed from architecture panel/workflow (explicitly out of required UX).

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Reliable custom portal favicon rendering | ⊕workspace-overseer | not-started | — | — |
| AC2 | Favicon cache-bust + SVG fallback | ⊕workspace-overseer | not-started | — | — |
| AC3 | ICO integrity verification in generator path | ⊕workspace-overseer | not-started | — | — |
| AC4 | Mermaid backend failure handled gracefully | ⊕workspace-overseer | not-started | — | — |
| AC5 | Inline SVG architecture fallback wired | ⊕workspace-overseer | not-started | — | — |
| AC6 | Live editor removed from architecture UX | ⊕workspace-overseer | not-started | — | — |

### Tyler's Original Request
> portal icon still not fixed, I see the brave icon; all mermaid backends failed; live editor on architectural panel not needed.

---

## Event Log

### 2026-05-10T23:59:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triaged for portal icon + architecture rendering resilience.

**Details:**
- Scope: ⊕Workspace portal rendering behavior
- Intake decisions captured:
  - Treat icon + Mermaid issues as a single FR
  - Mermaid strategy: inline SVG fallback when renderer unavailable
  - Icon strategy: validate ICO integrity, add cache-busting, add SVG fallback
  - Live editor explicitly not needed for architecture panel
- Acceptance criteria drafted (see Header)
- Concurrency check: no direct conflicts detected
- Cycle timer started: 4fbd2632-8d7a-4364-ae27-078cd71b92af

**Next:** awaiting ⊕workspace-ci: create branch/worktree/draft PR (BRANCHED).

---

## Artifacts

- **Perf runs:** 4fbd2632-8d7a-4364-ae27-078cd71b92af — intake triage run for FR open
- **References:** reports/portal.html, tools/dashboard_portal.py, diagrams/music-icecast-primary-architecture.mmd
