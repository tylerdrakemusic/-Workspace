# FR-20260501-weight-trend-sync-fix — Restore Weight Trend live sync (Withings + Garmin)

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260501-weight-trend-sync-fix
- **Title:** Restore Weight Trend live sync (Withings + Garmin)
- **Type:** fix
- **Risk:** medium
- **Projects:** ∞Life
- **State:** AWAITING_CI
- **Branch:** fix/∞life/weight-trend-sync-fix (fallback: fix/life/weight-trend-sync-fix if sigil branch naming chokes)
- **PRs:** pending (⊕workspace-ci to open draft PR)
- **Cycle timer:** 046bc7a3-cbc4-4f6d-9139-9094a79e2d68
- **Repo visibility:** 🔒 PRIVATE — `tylerdrakemusic/Life` (real medical/biometric data; gitignore audit required pre-commit)
- **Opened:** 2026-05-01
- **Last updated:** 2026-05-01
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Weight Trend panel in the ∞Life dashboard pulls **fresh** data from Withings (live API) on regen — no stale-only behavior
2. Garmin weight sync is restored: replace/repair the Garmin Connect client (current library known broken) with a working library or auth flow that successfully fetches body composition data
3. Both providers' fetched samples land in the canonical `infinitelife.db` weight/body-composition table (existing schema; no migrations unless strictly required, then documented)
4. Weight Trend panel renders the latest samples from both sources with last-sync timestamps visible
5. Auth/token refresh paths are explicit and documented (Withings token refresh; Garmin OAuth/MFA flow) — Tyler is available **interactively** to walk through MFA/OAuth prompts during implementation
6. New/updated tests in `∞Life/tests/` cover sync success path with mocked HTTP responses; passes locally and in CI
7. No real biometric values, tokens, or PII are committed; `.gitignore` audit clean before any push

### Out of Scope
- Other biomarker panels (HRV, sleep, etc.) — Weight Trend only
- Schema migrations beyond what's strictly necessary
- Historical backfill beyond what providers return on a normal sync
- Public surfacing of any sample data (∞Life is PRIVATE)

### Concurrency Notes
- Conflicts with: none (no other active FR touches ∞Life sync code)
- Depends on: none

### Files Likely Touched (best inference; implementing agent confirms)
- `∞Life/src/integrations/withings_*.py` (or equivalent client + sync entrypoint)
- `∞Life/src/integrations/garmin_*.py` (likely full client swap)
- `∞Life/src/dashboard/` weight trend panel renderer
- `∞Life/src/data/infinitelife.db` (data writes only; no schema change expected)
- `∞Life/requirements.txt` (Garmin library swap)
- `∞Life/tests/` (sync tests)

### Deliverable Tracker

<!-- Mutable table. Agents flip their own row's Status + Proof + Updated in place.
     Status vocab: not-started → in-progress → blocked → done → verified. -->

| #   | Deliverable                                                  | Owner                | Status      | Proof | Updated    |
| --- | ------------------------------------------------------------ | -------------------- | ----------- | ----- | ---------- |
| AC1 | Withings live fetch on regen (no stale-only)                 | ∞life-orchestrator   | not-started | —     | —          |
| AC2 | Garmin client repaired/replaced; body-comp fetch succeeds    | ∞life-orchestrator   | not-started | —     | —          |
| AC3 | Both sources persist to `infinitelife.db` weight table       | ∞life-orchestrator   | not-started | —     | —          |
| AC4 | Panel renders latest samples + last-sync timestamps          | ∞life-orchestrator   | not-started | —     | —          |
| AC5 | Auth/token refresh paths explicit + documented               | ∞life-orchestrator   | not-started | —     | —          |
| AC6 | Sync tests added/updated; CI green                           | ∞life-orchestrator   | not-started | —     | —          |
| AC7 | Pre-push gitignore audit clean (no biometric data / secrets) | ⊕workspace-security  | not-started | —     | —          |

### Tyler's Original Request
> Restore Weight Trend live sync — Withings + Garmin. Withings is showing stale/no fresh fetch on regen; Garmin sync is broken because the Garmin Connect library is broken. Need to fix both so Weight Trend panel updates live again.

### Tyler approval (Phase A → Phase B gateway, 2026-05-01)
> "yes, I'm here to help get through auth"

**Tyler is available interactively during implementation** to step through:
- Garmin OAuth/MFA prompts (likely required when swapping the Garmin client library)
- Withings token refresh if the stored refresh token is expired
- Any other interactive auth dance the implementing agent encounters

The implementing agent **MUST** engage Tyler interactively rather than fail silently or stub out auth.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-01 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, Phase A interview complete (Tyler clarified scope: Withings stale + Garmin library broken), Phase B triage complete, scope card approved by Tyler ("yes, I'm here to help get through auth") → TRIAGED → AWAITING_CI

**Details:**
- Type: fix; Risk: medium (private repo + auth + biometric data path)
- Projects: ∞Life only
- Acceptance criteria drafted (7 ACs; see Header)
- Concurrency check: clean — no active FR touches ∞Life sync code
- Tyler approved scope and committed to interactive auth assistance during implementation

**Next:** ⊕workspace-ci → create branch `fix/∞life/weight-trend-sync-fix` (fallback `fix/life/...`), set up worktree per Lightweight Agent Branch Protocol, open draft PR titled `fix(∞life): restore Weight Trend live sync (Withings + Garmin)` linking this FR ID. Then route to ∞life-orchestrator.

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** 046bc7a3-cbc4-4f6d-9139-9094a79e2d68 — fr-cycle-FR-20260501-weight-trend-sync-fix (started at intake)
- **Proof artifacts:** —
- **PRs:** pending (⊕workspace-ci)
- **Commits:** —
- **Reports / dashboards:** —
