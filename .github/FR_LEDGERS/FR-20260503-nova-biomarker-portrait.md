# FR-20260503-nova-biomarker-portrait — ∞Life Nova Biomarker Portrait System

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260503-nova-biomarker-portrait
- **Title:** ∞Life Nova Biomarker Portrait System — AI persona portrait panel mirroring Lily architecture
- **Type:** feature
- **Risk:** medium
- **Projects:** ∞Life
- **State:** MERGED
- **Branch:** feature/life/nova-biomarker-portrait
- **PRs:** tylerdrakemusic/Life#9 (merged)
- **Cycle timer:** a6e90333-39ec-418f-8fcf-d58b3fa6475a
- **Opened:** 2026-05-03
- **Last updated:** 2026-05-03
- **Merged at:** 2026-05-03
- **Signed off at:** 2026-05-03
- **Closed:** 2026-05-03
- **Final state:** MERGED

### Acceptance Criteria

1. `nova_portrait.py` (in `∞Life/src/utils/`) generates a daily-cached AI portrait of "Nova" via FLUX.1-schnell (HF router, quantum-seeded random seed) — same generation + caching logic as `lily_portrait.py`.
2. `nova_config_db.py` (in `∞Life/src/utils/`) manages a `nova_prompts` SQLite table in a new `∞Life/src/data/nova_config.db` — same schema (`id`, `positive_prompt`, `negative_prompt`, `is_active`, `updated_at`) as `lily_prompts` in `lily_config.db`.
3. A seed script `∞Life/tools/seed_nova_config.py` initializes `nova_config.db` with a default positive prompt describing Nova's appearance.
4. `gen_biomarker_dashboard.py` (or its server wrapper) embeds Nova's portrait in the biomarker panel header — positioned analogously to Lily on the executive portal, labeled "Nova".
5. A ThreadedHTTPServer mode (analogous to `executive_audio_brief.py --serve`) serves the biomarker dashboard with Nova's portrait pre-embedded.
6. "Save & Regenerate" modal UX is behavior-identical to Lily's modal on the executive portal (single `POST /update-nova-prompt` endpoint, spinner state, in-place portrait refresh, no page reload). The trigger is a tiny edit-icon button (🖊 or pencil SVG, ~20×20px, `opacity: 0.35`, rising to `0.9` on hover) overlaid in the **top-right corner of the portrait image** — not a separate sidebar button.
7. Nova's portrait is never served from `👁AI-Manifest` paths — all files, DB, and image cache live within `∞Life/`.

### Concurrency Notes

- Conflicts with: FR-20260503-lily-prompt-externalization (different project, no file overlap — clean)
- Depends on: none (⊕Workspace HF client already has FLUX + quantum seed)

### Deliverable Tracker

| #   | Deliverable                              | Owner              | Status      | Proof | Updated    |
| --- | ---------------------------------------- | ------------------ | ----------- | ----- | ---------- |
| AC1 | `nova_portrait.py` generator             | ∞life-orchestrator | not-started | —     | —          |
| AC2 | `nova_config_db.py` + `nova_config.db`   | ∞life-orchestrator | not-started | —     | —          |
| AC3 | `seed_nova_config.py` init script        | ∞life-orchestrator | not-started | —     | —          |
| AC4 | Biomarker dashboard portrait embed       | ∞life-orchestrator | not-started | —     | —          |
| AC5 | ThreadedHTTPServer `--serve` mode        | ∞life-orchestrator | not-started | —     | —          |
| AC6 | Save & Regenerate modal + endpoint       | ∞life-orchestrator | not-started | —     | —          |
| AC7 | All Nova assets scoped to `∞Life/`       | ∞life-orchestrator | not-started | —     | —          |

### Tyler's Original Request

> Mirror the Lily portrait system (FLUX.1-schnell via HF router, quantum-seeded, ThreadedHTTPServer, SQLite prompt table, Save & Regenerate modal) for the ∞Life biomarker dashboard. New AI persona named "Nova". Separate SQLite table for positive_prompt (analogous to `lily_prompts` in `lily_config.db`). Portrait modal UX identical to the executive portal (single "Save & Regenerate" button). The biomarker dashboard lives in ∞Life (not 👁AI-Manifest).

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-03T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ∞Life
- Persona name confirmed by Tyler: **Nova**
- Type: feature | Risk: medium (new DB table, server infrastructure, new module files in ∞Life)
- Anchors on: `lily_portrait.py`, `lily_config_db.py` (👁AI-Manifest), `⊕Workspace` HF client (already has FLUX + quantum seed), `gen_biomarker_dashboard.py` (∞Life)
- Concurrency check: clean (FR-20260503-lily-prompt-externalization is same-day but different project, no file overlap)
- Acceptance criteria: 7 ACs drafted (see Header)

**Next:** awaiting Tyler scope confirmation → on approval, delegate to ⊕workspace-ci for branch creation

### 2026-05-03T00:01:00Z — ⊕workspace-overseer

**Event:** state-transition

**Summary:** Tyler approved scope → APPROVED. UI optimization added to AC6.

**Details:**
- Tyler confirmed all 7 ACs
- AC6 amended: edit prompt trigger is a tiny pencil icon overlaid top-right corner of portrait (opacity 0.35 → 0.9 on hover), not a separate button
- Routing to ⊕workspace-ci for branch `feature/life/nova-biomarker-portrait` + draft PR on ∞Life repo
- Then fanning out to ∞life-orchestrator for full implementation

---

## Artifacts

- **Perf runs:** a6e90333-39ec-418f-8fcf-d58b3fa6475a — fr-cycle-FR-20260503-nova-biomarker-portrait (started 2026-05-03)
- **Proof artifacts:** —
- **PRs:** [tylerdrakemusic/Life#9](https://github.com/tylerdrakemusic/Life/pull/9) (squash a0b69da)
- **Commits:** a0b69dade1c6fae8bbb0197f8e8da45524def449
- **Reports / dashboards:** —

---

### 2026-05-03 — ⊕workspace-ci

**Event:** state-transition

**Summary:** PR #9 squash-merged to main → MERGED

**Details:**
- Squash merge SHA: a0b69dade1c6fae8bbb0197f8e8da45524def449
- Local main synced (f:\∞Life — fast-forward, 5 files changed, 633 insertions)
- FR closed
