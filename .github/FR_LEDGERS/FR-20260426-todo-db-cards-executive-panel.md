# FR-20260426-todo-db-cards-executive-panel — Todo DB Cards: Executive Panel Interactive Close + DB Migration

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260426-todo-db-cards-executive-panel
- **Title:** Todo DB Cards: Executive Panel Interactive Close + DB Migration from Flat Files
- **Type:** feature
- **Risk:** medium
- **Projects:** 👁AI-Manifest
- **State:** TRIAGED
- **Branch:** feature/ai-manifest/todo-db-cards-executive-panel | pending
- **PRs:** pending
- **Cycle timer:** 70e1cbbc-0390-4da5-9c46-d26052c5830c
- **Opened:** 2026-04-26
- **Last updated:** 2026-04-26
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. A `todos` table exists in 👁AI-Manifest's SQLite DB (`f:\👁AI-Manifest\src\data\aimanifest.db`), schema: `id, project, source (AI|TYLER), text, done INTEGER DEFAULT 0, created_at, closed_at`.
2. One-time migration script reads all 10 TODO flat files (`TODO_AI.md` + `TODO_TYLER.md` from each of the 5 project roots) and seeds the `todos` table; re-running is idempotent (skips items already present by text+project+source key).
3. Executive panel renders active (`done=0`) todo cards grouped by project; each card shows source label (AI | TYLER), text, and a "Mark Done" button.
4. Clicking "Mark Done" sends an async request that flips `done=1` + sets `closed_at` in the DB and removes/visually strikes the card **without a full page reload**.
5. The ElevenLabs voice/executive summary readout is built exclusively from `done=0` todos in the DB (no longer reads `TODO_AI.md` / `TODO_TYLER.md` files).
6. Completed todos (`done=1`) persist in DB as audit trail and are never deleted; they are simply excluded from the summary and readout.
7. The existing `TODO_AI.md` and `TODO_TYLER.md` flat files are NOT modified or deleted — they remain on disk as reference artifacts but are no longer the authoritative source for the portal.

### Concurrency Notes
- Conflicts with: none
- Depends on: none (predecessor FR-20260426-executive-audio-brief-panel is CLOSED/MERGED)

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | `todos` table + DB creation in 👁AI-Manifest | 👁AI-Manifest orchestrator | not-started | — | — |
| AC2 | Migration script (idempotent, reads all 10 TODO files) | 👁AI-Manifest orchestrator | not-started | — | — |
| AC3 | Executive panel renders DB-backed todo cards with Mark Done button | 👁AI-Manifest orchestrator | not-started | — | — |
| AC4 | Async/interactive Mark Done (no full reload) | 👁AI-Manifest orchestrator | not-started | — | — |
| AC5 | Audio brief generation reads from DB (done=0 only) | 👁AI-Manifest orchestrator | not-started | — | — |
| AC6 | Completed todos persist in DB, excluded from readout | 👁AI-Manifest orchestrator | not-started | — | — |
| AC7 | Flat TODO files untouched — not modified, not deleted | 👁AI-Manifest orchestrator | not-started | — | — |

### Tyler's Original Request
> new FR, we need to make the executive dashboard a bit cleaner and more living, not sure interacting with the TODO files in github is the right approach, if we had a db with Todo cards that might serve us better. That way we're not conflicting state with working branches in progress. Im thinking a binary state. Something is either done or it's not. I would like to be able to close ToDos interactively from the executive panel, keep the read out and voices to build executive summary from the ToDos. This would involve migrating the existing todo files to a db state

---

## Event Log

### 2026-04-26T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: 👁AI-Manifest (portal owner, DB host, audio brief, migration)
- Risk: medium — DB schema creation, migration script, portal UI changes, audio integration
- Interview skipped: intent unambiguous — problem (git-conflicting flat files), outcome (DB cards + interactive close + voice from DB), scope (👁AI-Manifest portal), and boundary (binary done/not-done, no priority system) all stated explicitly
- Acceptance criteria drafted: 7 ACs covering DB schema, migration, UI, async interaction, voice integration, audit trail, and flat-file preservation
- Concurrency check: no active FRs — clean

**Next:** awaiting Tyler: approve scope → then route to ⊕workspace-ci for branch creation

---

## Artifacts

- **Perf runs:** 70e1cbbc-0390-4da5-9c46-d26052c5830c — FR cycle timer started at intake
