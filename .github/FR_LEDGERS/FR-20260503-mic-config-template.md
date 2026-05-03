# FR-20260503-mic-config-template — 1-page printable mic configuration tracking template

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260503-mic-config-template
- **Title:** 1-page printable mic configuration tracking template (Hyperthreat Studios)
- **Type:** feature
- **Risk:** low
- **Projects:** ❤Music (primary), ⊕Workspace (portal nav entry)
- **State:** BRANCHED (pending)
- **Branch:** feature/❤music/mic-config-template (❤Music), feature/⊕workspace/studio-portal-panel (⊕Workspace)
- **PRs:** pending (CI to open)
- **Cycle timer:** cd1c40b1-c242-4d26-b971-e7d0cbda2c00
- **Opened:** 2026-05-03
- **Last updated:** 2026-05-03
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `❤Music/studio/mic_config_template.html` — 16-row × 3-col table (Mic 1–16 prefilled; Wall + STUD i/o blank).
2. Single Letter sheet, 100% scale, pencil-writable column widths.
3. Header includes Hyperthreat logo + "Hyperthreat Studios — Mic Configuration".
4. Front/back identical for duplex print (template repeats on page 2).
5. Print CSS strips portal chrome AND swaps to ink-friendly inverted logo via `@media print`.
6. New "Studio" panel registered in `⊕Workspace/reports/portal.html` (icon, nav entry, iframe pane), positioned in ❤Music nav cluster.
7. Channel count parameterized (single loop/constant).

### Out of Scope
- DB persistence
- Digital fillable form
- Mics 17–32 UI

### Concurrency Notes
- Conflicts with: none
- Depends on: none

### Brand Asset Prerequisites
- **Source logo (Tyler must save):** `❤Music/Brand/hyperthreat/hyperthreat-logo.png` — silver gradient on transparent/dark. Tyler pasted the image in chat; he needs to save it to this path before implementer can complete AC3.
- **Print variant (implementer generates):** `❤Music/Brand/hyperthreat/hyperthreat-logo-print.png` — inverted/ink-friendly, derived from source.

### Deliverable Tracker

| #   | Deliverable                                                  | Owner               | Status      | Proof | Updated |
| --- | ------------------------------------------------------------ | ------------------- | ----------- | ----- | ------- |
| AC1 | `❤Music/studio/mic_config_template.html` table (16×3)        | ❤music-orchestrator | not-started | —     | —       |
| AC2 | Letter / 100% / pencil-writable widths                       | ❤music-orchestrator | not-started | —     | —       |
| AC3 | Hyperthreat header (logo + title)                            | ❤music-orchestrator | not-started | —     | —       |
| AC4 | Duplex page-2 repeat                                         | ❤music-orchestrator | not-started | —     | —       |
| AC5 | Print CSS (chrome strip + inverted logo via `@media print`)  | ❤music-orchestrator | not-started | —     | —       |
| AC6 | "Studio" portal panel in `⊕Workspace/reports/portal.html`    | ⊕workspace-ci       | not-started | —     | —       |
| AC7 | Parameterized channel count (single loop/constant)           | ❤music-orchestrator | not-started | —     | —       |

### Tyler's Original Request
> 1-page printable mic configuration tracking template for Hyperthreat Studios. 16-row × 3-col table (Mic 1–16 prefilled; Wall + STUD i/o blank), Letter / 100% / pencil-writable, Hyperthreat header (logo + title), duplex (front/back identical), print CSS strips portal chrome and swaps to inverted ink-friendly logo, new "Studio" panel in workspace portal positioned in ❤Music nav cluster, channel count parameterized. Out of scope: DB persistence, digital fillable form, mics 17–32 UI.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-05-03 — ⊕workspace-intake

**Event:** state-transition (OPEN → TRIAGED → BRANCHED pending)

**Summary:** FR opened, triage complete, Tyler approved scope (Revision 1). Routed to ⊕workspace-ci for branch + PR creation.

**Details:**
- Type: feature · Risk: low
- Projects: ❤Music (primary), ⊕Workspace (portal nav entry)
- 7 acceptance criteria drafted and approved by Tyler
- Concurrency check: clean — no conflicts, no dependencies
- Brand asset prerequisite flagged: Tyler must save pasted logo to `❤Music/Brand/hyperthreat/hyperthreat-logo.png` before AC3 implementation

**Next:** ⊕workspace-ci to create branches `feature/❤music/mic-config-template` (❤Music) and `feature/⊕workspace/studio-portal-panel` (⊕Workspace), open draft PRs, then route to ⊕workspace-overseer for fan-out.

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** cd1c40b1-c242-4d26-b971-e7d0cbda2c00 — fr-cycle-FR-20260503-mic-config-template (intake → close)
- **Proof artifacts:** —
- **PRs:** pending
- **Commits:** —
- **Reports / dashboards:** —
