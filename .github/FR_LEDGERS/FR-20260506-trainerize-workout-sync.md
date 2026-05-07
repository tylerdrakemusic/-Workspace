# FR-20260506-trainerize-workout-sync — Trainerize Workout Sync for ∞Life (Auth + Workout Import)

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260506-trainerize-workout-sync
- **Title:** Trainerize Workout Sync for ∞Life (Auth + Workout Import)
- **Type:** feature
- **Risk:** medium
- **Projects:** ∞Life
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 5ddf64db-e798-4dff-a77a-20ee1cd233d8
- **Opened:** 2026-05-06
- **Last updated:** 2026-05-06
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Trainerize sync module performs authenticated fetch using TZ_USERNAME/TZ_PASSWORD env vars and writes normalized records to ∞Life DB tables plus sync_log.
2. Data synced includes: completed workouts (date, duration, calories), exercises/sets/reps/weights, and body metrics when present (weight/body fat).
3. Sync integrates into the master sync flow (not standalone-only).
4. 2FA challenge fallback is supported; session-cookie import fallback is allowed when direct login automation is blocked.
5. Sensitive auth data is never logged; sync_log stores only safe operational notes.
6. If primary auth fails due to MFA/login flow changes, fallback path is attempted and result clearly logged.
7. Tests cover parser/normalizer logic and auth-failure handling.
8. Source name in code and DB logs is `trainerize` (replaces `trainingzones` stub naming).

### Out of Scope
- Writing workouts back to Trainerize
- Historical backfill beyond initial supported window
- New dashboard/UI panel redesigns

### Concurrency Notes
- Conflicts with: none
- Depends on: none (FR-20260505-mfp-nutrition-sync-fix is in TRIAGED/BRANCHED but modifies mfp_sync.py, not the trainingzones stub — no conflict)

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Trainerize auth + session-cookie fallback | ∞life-orchestrator | not-started | — | — |
| AC2 | Workout / exercise / body-metric data fetch + normalize | ∞life-orchestrator | not-started | — | — |
| AC3 | DB write to workout/exercise tables + sync_log | ∞life-orchestrator | not-started | — | — |
| AC4 | Master sync integration | ∞life-orchestrator | not-started | — | — |
| AC5 | Auth-failure fallback logging | ∞life-orchestrator | not-started | — | — |
| AC6 | Tests: parser/normalizer + auth failure | ∞life-orchestrator | not-started | — | — |
| AC7 | Source rename: trainingzones → trainerize | ∞life-orchestrator | not-started | — | — |

### Tyler's Original Request
> explore https://www.trainerize.com/login.aspx for syncing my training workout data, my credentials start with TZ in system

---

## Event Log

### 2026-05-06T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, Phase A interview complete, Tyler confirmed scope → TRIAGED

**Details:**
- Scope: ∞Life only (single-project feature)
- Tyler confirmed: Trainerize source naming, workout+exercise+body-metrics data, master-sync integration, all three auth fallback constraints
- Concurrency check: no conflicts with in-flight FRs
- Existing stub: `f:\∞Life\src\sync\trainingzones_sync.py` — to be replaced/upgraded
- Pattern reference: `f:\∞Life\src\sync\mfp_sync.py`
- Acceptance criteria: 8 items drafted
- Risk: medium (web auth variability, potential 2FA/session flow complexity)

**Next:** awaiting Tyler: approve scope → then ⊕workspace-ci to branch

---

## Artifacts

- **Perf runs:** 5ddf64db-e798-4dff-a77a-20ee1cd233d8 — FR cycle timer (intake open)
- **Perf runs:** 33930c30-7e6f-4e90-a9b5-48ec19de49f5 — overseer Phase A intake run
- **Proof artifacts:** ac9ad1989755 — Phase A interview answers collected
- **PRs:** pending
- **Commits:** pending
- **Reports / dashboards:** —
