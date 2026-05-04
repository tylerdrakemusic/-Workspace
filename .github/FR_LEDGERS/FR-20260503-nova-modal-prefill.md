# FR-20260503-nova-modal-prefill — Nova modal prefill + graceful server-error UX

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260503-nova-modal-prefill
- **Title:** Nova modal prefill + graceful server-error UX
- **Type:** bug+feature
- **Risk:** low
- **Projects:** ∞Life
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 035a7ee2-b868-44d0-b90f-a15a450c9265
- **Opened:** 2026-05-03
- **Last updated:** 2026-05-03
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `GET /get-nova-prompt` endpoint added to `do_GET` handler in `gen_biomarker_dashboard.py` — returns `{"prompt": "<active positive_prompt>"}` from `nova_config_db`
2. `openNovaModal()` fetches `/get-nova-prompt` on open and sets `#nova-prompt-input.value` to the current prompt before showing the modal
3. If the fetch fails (static file mode), the modal opens with empty textarea — no error shown
4. Replace `alert('Server error...')` in `novaModalSave()` `.catch()` with an inline error `<div>` inside the modal (styled like other error states)

### Concurrency Notes
- Conflicts with: FR-20260503-nova-biomarker-portrait (MERGED — safe, base is current main)
- Depends on: FR-20260503-nova-biomarker-portrait (must be merged first — provides the nova modal + nova_config_db infrastructure)

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | `GET /get-nova-prompt` endpoint in `do_GET` | ∞life-orchestrator | not-started | — | — |
| AC2 | `openNovaModal()` prefill fetch + textarea population | ∞life-orchestrator | not-started | — | — |
| AC3 | Static-mode graceful fallback (silent catch) | ∞life-orchestrator | not-started | — | — |
| AC4 | Replace `alert()` with inline error `<div>` in modal footer | ∞life-orchestrator | not-started | — | — |

### Tyler's Original Request
> "checking main seeing this message on save and regenerate, we should also prefill the edit nova's prompt with the text that's already in the db"

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-03T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ∞Life (`f:\∞Life\src\dashboard\gen_biomarker_dashboard.py`)
- Phase A skipped — intent fully deterministic from codebase inspection
- Two sub-issues identified: (1) modal opens with empty textarea — needs `/get-nova-prompt` prefill endpoint + JS fetch; (2) `alert()` in `.catch()` of `novaModalSave()` — replace with inline error div
- Concurrency check: FR-20260503-nova-biomarker-portrait is MERGED — nova modal infrastructure exists on main; no active conflicts
- Risk: low — isolated JS + Python handler change, no DB schema changes, no auth/secrets touch

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** 035a7ee2-b868-44d0-b90f-a15a450c9265 — fr-cycle-FR-20260503-nova-modal-prefill
- **Proof artifacts:** —
- **PRs:** pending
- **Commits:** —
- **Reports / dashboards:** —
