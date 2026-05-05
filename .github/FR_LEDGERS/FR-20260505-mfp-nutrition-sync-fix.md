# FR-20260505-mfp-nutrition-sync-fix — Fix MFP Nutrition Trend Live Sync (Auth Repair + Daily Auto-Refresh)

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260505-mfp-nutrition-sync-fix
- **Title:** Fix MFP Nutrition Trend Live Sync (Auth Repair + Daily Auto-Refresh)
- **Type:** fix
- **Risk:** medium
- **Projects:** ∞Life
- **State:** BRANCHED
- **Branch:** fix/life/fr-20260505-mfp-nutrition-sync-fix
- **PRs:** https://github.com/tylerdrakemusic/Life/pull/13 (draft)
- **Cycle timer:** d9e45bd6-af7c-4550-a4b9-89b4ced52a6f
- **Opened:** 2026-05-05
- **Last updated:** 2026-05-05
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Use the unofficial `myfitnesspal` Python package path as the primary MFP auth/sync path if it can still retrieve diary data reliably.
2. If package auth fails, implement automated fallback reauth that refreshes `MFP_SESSION_TOKEN` and `MFP_CF_CLEARANCE` (headless browser flow) and persists refreshed values to Windows User env vars.
3. Add `tools/mfp_reauth.py` and wire `master_sync.py` to invoke it automatically on auth expiry, then retry MFP sync once in the same run.
4. Ensure nightly automation runs without manual intervention and writes fresh daily rows to `nutrition_log` for the dashboard's MFP trend panel.
5. Validate end-to-end by running sync and confirming updated nutrition rows are visible to the biomarker dashboard query path.

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Primary MFP auth path hardening in `master_sync.py` | ∞life-orchestrator | not-started | — | — |
| AC2 | Automated fallback reauth flow for session cookies | ∞life-orchestrator | not-started | — | — |
| AC3 | New `tools/mfp_reauth.py` + retry wiring | ∞life-orchestrator | not-started | — | — |
| AC4 | Nightly unattended sync path verified | ∞life-orchestrator | not-started | — | — |
| AC5 | Data-path validation into dashboard nutrition trend | ∞life-orchestrator | not-started | — | — |

### Tyler's Original Request
> fix the live sync of 🍽 Nutrition Trend (MFP). There is an execution policy and integration, but it's currently broken in auth layer. We need to fix and have the live sync refresh the data daily without manual intervention

---

## Event Log

### 2026-05-05T23:31:47Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triage completed with approved scope → TRIAGED

**Details:**
- Scope: ∞Life only.
- Root cause identified in current implementation: cookie/session-token auth expiry with no automated reauth path.
- Existing code references `mfp_reauth.py` on auth expiration but the file is currently missing.
- Acceptance criteria drafted and approved by Tyler.
- Concurrency check: no conflicting ∞Life FR currently in active implementation for this exact subsystem.

**Next:** ⊕workspace-ci — create isolated branch/worktree + draft PR (BRANCHED)

### 2026-05-05T23:34:04Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** BRANCHED established for ∞Life implementation handoff

**Details:**
- Created implementation branch: `fix/life/fr-20260505-mfp-nutrition-sync-fix`
- Created isolated worktree: `F:\worktrees\life-fr-20260505-mfp-nutrition-sync-fix`
- Pushed branch to `origin` in `tylerdrakemusic/Life`
- Opened draft PR: https://github.com/tylerdrakemusic/Life/pull/13
- Bootstrap commit created to anchor branch/PR handoff: `45574fef695da307eb593f17fd25e14504c9fc57`

**Next:** ∞life-orchestrator — start implementation (IN_PROGRESS)

---

## Artifacts

- **Perf runs:** d9e45bd6-af7c-4550-a4b9-89b4ced52a6f — FR cycle timer started at intake/triage
- **Branch:** fix/life/fr-20260505-mfp-nutrition-sync-fix
- **Draft PR:** https://github.com/tylerdrakemusic/Life/pull/13
- **Commits:** 45574fef695da307eb593f17fd25e14504c9fc57 (∞Life bootstrap branch commit)
