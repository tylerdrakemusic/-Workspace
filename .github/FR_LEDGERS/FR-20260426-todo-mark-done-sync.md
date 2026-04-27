# FR-20260426-todo-mark-done-sync — Executive Panel Todo: Mark Done Not Syncing to UI

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-todo-mark-done-sync
- **Title:** Executive Panel Todo: Mark Done Not Syncing to UI
- **Type:** fix
- **Risk:** low
- **Projects:** 👁AI-Manifest
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 692cdba2-b612-4332-a9e6-84d2d63d2898
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. Clicking ✓ on any **open** todo at `127.0.0.1:8200` immediately removes the `<li>` from the UI with a fade-out and does **not** show the "Could not mark done" alert.
2. The `mark_done()` DB call succeeds (returns `True`) for any todo whose `done=0` row exists in `manifest_todos.db`, confirming the write path works end-to-end.
3. The progress bar (X of Y tasks done) updates dynamically client-side after each successful mark-done — it must not require a full page reload to reflect the new count.
4. If a stale portal HTML contains a todo ID that no longer exists in the DB (or is already done), the UI shows a clear inline message ("Already done" or silently hides the button) instead of the generic "Could not mark done" alert.
5. The root cause of the ID mismatch (stale HTML baking in auto-increment IDs that drift after DB migrations) is diagnosed and fixed — either by serving the portal HTML dynamically from the live DB on each request, or by adding an ID-resync step that keeps portal button IDs in sync with current DB state.
6. Existing tests (`test_mark_done_returns_true_on_success`, `test_mark_done_removes_from_open`, `test_mark_done_sets_closed_at`) pass. A new integration test covering the HTTP `/api/todo/done` endpoint returning 200 for a valid open todo is added.

### Concurrency Notes

- Conflicts with: none (no active FRs touching AI-Manifest todos)
- Depends on: none

### Deliverable Tracker

| #   | Deliverable                                          | Owner      | Status      | Proof | Updated    |
| --- | ---------------------------------------------------- | ---------- | ----------- | ----- | ---------- |
| AC1 | mark-done click removes `<li>` without alert         | 👁ai-manifest-orchestrator | not-started | —     | 2026-04-26 |
| AC2 | DB write confirmed for open todos                    | 👁ai-manifest-orchestrator | not-started | —     | 2026-04-26 |
| AC3 | Progress bar updates client-side dynamically         | 👁ai-manifest-orchestrator | not-started | —     | 2026-04-26 |
| AC4 | Stale ID returns graceful inline message             | 👁ai-manifest-orchestrator | not-started | —     | 2026-04-26 |
| AC5 | Root cause (ID drift) fixed                          | 👁ai-manifest-orchestrator | not-started | —     | 2026-04-26 |
| AC6 | New HTTP endpoint integration test added + all pass  | 👁ai-manifest-orchestrator | not-started | —     | 2026-04-26 |

### Tyler's Original Request

> "I don't think the executive panel todo interface is syncing correctly. For example I tried to mark register with ASCAP as done, I think it changed the DB state, but the UI did not reflect that back properly, the todo should have been cleared and progress on the tasks should have been reflected."

---

## Event Log

### 2026-04-26T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened via interview, triage complete → TRIAGED

**Details:**
- Bug discovered in `👁AI-Manifest/tools/executive_audio_brief.py` + `executive_brief_portal.html` served on port 8200
- Root cause hypothesis: pre-rendered portal HTML bakes in SQLite auto-increment IDs at generation time; if DB is re-seeded or migrated without regenerating the portal, button IDs become stale → server's `mark_done()` gets `rowcount=0` → HTTP 404 → `alert('Could not mark done')`
- DB write is **unconfirmed** (suspected write did NOT happen — the alert path means the UPDATE matched 0 rows)
- DB location is `👁AI-Manifest/src/data/manifest_todos.db` (NOT workspace.db as Tyler initially thought)
- Alert fires quickly (~immediate) consistent with fast 404 response, not a JS pre-fetch crash
- Bug is reproducible for any todo, not just "Register with ASCAP"
- Scope: single-project fix in `👁AI-Manifest`
- Concurrency check: clean (no active FRs on AI-Manifest todos)

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** 692cdba2-b612-4332-a9e6-84d2d63d2898 — FR-20260426-todo-mark-done-sync cycle timer (intake)
- **Proof artifacts:** —
- **PRs:** pending
- **Commits:** pending
- **Reports / dashboards:** —
