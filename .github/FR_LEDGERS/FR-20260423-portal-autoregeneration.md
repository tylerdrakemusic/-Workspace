# FR-20260423-portal-autoregeneration — Portal Auto-Regeneration + Gap Count Accuracy

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-portal-autoregeneration
- **Title:** Portal Auto-Regeneration + Gap Count Accuracy
- **Type:** chore/feature
- **Risk:** low
- **Projects:** ⊕Workspace
- **State:** REVIEW_REQUESTED
- **Branch:** chore/workspace/portal-autoregeneration
- **PRs:** #18 https://github.com/tylerdrakemusic/-Workspace/pull/18
- **Cycle timer:** 1f51e007-9e12-4472-8fb8-aa7e73d489ff
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-24
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Portal regenerates all stale dashboards automatically on every run without requiring `--regen` flag.
2. Agent Ops health card gap count reflects current data from a fresh run (not a stale HTML file).
3. Live agents section in the portal accurately reflects running sessions.
4. No stale-warning with manual CLI regen command is shown to the user.
5. Existing `--regen` flag behavior is preserved (if present) for backward compatibility.

### Concurrency Notes
- Conflicts with: FR-20260423-vscode-session-autodetect (touches portal/agent ops monitor — coordinate if both in-progress simultaneously)
- Depends on: none

### Deliverable Tracker

| #   | Deliverable                                         | Owner   | Status      | Proof | Updated |
| --- | --------------------------------------------------- | ------- | ----------- | ----- | ------- |
| AC1 | Portal auto-regens stale dashboards without --regen | pending | not-started | —     | —       |
| AC2 | Gap count reflects fresh run data                   | pending | not-started | —     | —       |
| AC3 | Live agents section is accurate                     | pending | not-started | —     | —       |
| AC4 | No manual regen warning shown to user               | pending | not-started | —     | —       |

### Tyler's Original Request
> "The Agent Ops health card in the portal shows a stale warning with a manual CLI regen command — that should be automatic, not a user task. The portal currently auto-regens only when `--regen` is passed. Additionally there is a gap count discrepancy: the health card shows 76 gaps (from a 17h-old HTML) while a fresh run shows 38. The live agents section also appears non-reflective. Fix: (1) portal auto-regens stale dashboards on every run without needing --regen flag, (2) gap count in portal health card always reflects current data, (3) live agents display is accurate."

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED (pending Tyler scope confirmation)

**Details:**
- Scope: ⊕Workspace
- Acceptance criteria drafted (see Header)
- Concurrency check: overlapping file surface with FR-20260423-vscode-session-autodetect (SOAKING); no active in-progress conflict
- Related FR: FR-20260423-vscode-session-autodetect (SOAKING — auto-detect live sessions)

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** 1f51e007-9e12-4472-8fb8-aa7e73d489ff — FR cycle timer started at intake
