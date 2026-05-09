# FR-20260508-upcoming-workouts-dashboard — Upcoming Workouts Panel for Biomarker Dashboard

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260508-upcoming-workouts-dashboard
- **Title:** Upcoming Workouts Panel for Biomarker Dashboard
- **Type:** feature (integration)
- **Risk:** medium
- **Projects:** ∞Life
- **State:** TRIAGED
- **Branch:** —
- **PRs:** —
- **Cycle timer:** aa54eb29-563b-49cb-a543-7323bf4ae6b8
- **Opened:** 2026-05-08
- **Last updated:** 2026-05-08
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. `fetch_upcoming_workouts()` function written + tested — fetches planned workouts from Trainerize
2. `upcoming_workouts` DB table created; sync_log entries written for upcoming-workouts sync
3. Biomarker dashboard panel implemented with calendar-like grid (days as columns, workouts as rows)
4. This-week filtering + display logic (Monday-Sunday current week, future-only from today onward)
5. Integration with existing Trainerize sync cycle (updates on each run)
6. Tests: fetch logic, DB writes, panel data queries

### Deliverables

- `src/sync/trainerize_sync.py` — New `fetch_upcoming_workouts()` function
- DB schema update — `upcoming_workouts` table + index
- Dashboard panel — Biomarker dashboard component (calendar grid)
- Tests — Upcoming fetch + DB writes + panel queries

### Out of Scope

- Editing/modifying workouts in dashboard (view only)
- Syncing back to Trainerize
- Other trainer integrations
- Mobile-responsive redesign

### Motivation

Trainer sets workouts days/weeks ahead in Trainerize. Need weekly plan visibility on biomarker dashboard (Monday-Sunday at a glance).

### Tyler's Original Request

> ok merged. So we should be able to get future workout data from those same credentials, my trainer setups up a workout plan ahead of time. My idea is to be able to see my up coming workout week from the biomarker dashboard Monday-Sunday current week view, design and implement an integration into that panel for this FR, please grill me get to know what I would want to see

---

## Event Log

### 2026-05-08T01:45:00Z — ⊕workspace-intake

**Event:** Phase A interview + draft confirmation

**Summary:** FR scope confirmed via detailed grill session → TRIAGED

**Details:**
- Scope: ∞Life only, biomarker dashboard integration
- Data source: Trainerize planned-workouts API (separate from completed-workouts)
- Display format: Calendar-like grid (days as columns, workouts as rows)
- Time window: Current week (Mon-Sun) only, future-only (today onward)
- Data fields: name, date/time, duration, exercises (sets/reps/weights), difficulty, notes
- Sync frequency: Piggyback on existing Trainerize sync cycle
- Database: Store upcoming workouts in new `upcoming_workouts` table for persistence
- Dashboard placement: Dedicated new panel/card on biomarker dashboard
- Risk: medium (new Trainerize API endpoint, dashboard rendering, schema changes)
- Concurrency: No known conflicts

**Next:** awaiting Tyler confirmation → then ⊕workspace-ci to branch

### 2026-05-08T00:00:00Z — ⊕workspace-architecture-reviewer

**Event:** architecture-review

**Summary:** BLOCKED — new dashboard module + upcoming_workouts schema require diagram updates before review can pass

**Details:**
- `src/dashboard/gen_upcoming_workouts_dashboard.py` introduces a new `src/dashboard/` module under ∞Life
- `src/utils/setup_db.py` adds the `upcoming_workouts` table and index
- No new external dependency or cross-project import detected
- Affected diagrams not yet updated: `diagrams/life-architecture.mmd`, `diagrams/life-db-schema.mmd`

**Next:** delegate to ⊕workspace-architecture-beautifier with the diagram updates below

---

## Artifacts

- **Perf runs:** aa54eb29-563b-49cb-a543-7323bf4ae6b8 — FR cycle timer (intake)
- **Architecture review:** 2026-05-08 — BLOCKED; diagram updates required for `diagrams/life-architecture.mmd` and `diagrams/life-db-schema.mmd`
- **Perf runs:** c426c0dd-5dd6-4c01-98d4-07510d5c4d81 — ⊕workspace-architecture-beautifier render pass
- **Diagram render:** `reports/diagrams/life-architecture.svg`, `reports/diagrams/life-db-schema.svg`, `reports/diagrams_dashboard.html`

### 2026-05-08T03:00:00Z — ⊕workspace-architecture-beautifier

**Event:** artifact

**Summary:** Updated the life architecture and DB schema diagrams for the upcoming workouts dashboard and verified render output.

**Details:**
- Added the new `src/sync/trainerize_sync.py` sync path and `src/dashboard/gen_upcoming_workouts_dashboard.py` generator to `diagrams/life-architecture.mmd`
- Added the `UPCOMING_WORKOUTS` table to `diagrams/life-db-schema.mmd` with the requested columns and documented its uniqueness/index constraints
- Verified `tools/diagrams_dashboard.py --no-open` rendered all 19/19 diagrams successfully

**Next:** commit the diagram and ledger updates, then record the resulting commit SHA
