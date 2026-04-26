# FR-20260425-band-mgmt-playback-sheets — Band Management Panel: Per-Row Audio Playback + Sheet Music Viewer

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260425-band-mgmt-playback-sheets
- **Title:** Band Management Panel: Per-Row Audio Playback + Sheet Music Viewer
- **Type:** feature
- **Risk:** medium
- **Projects:** ❤Music
- **State:** BRANCHED
- **Branch:** feature/heartmusic/band-mgmt-playback-sheets (cut from feature/heartmusic/guitar-trainer-metronome)
- **PRs:** https://github.com/tylerdrakemusic/Music/pull/7
- **Cycle timer:** e1addcfd-eede-4d24-885c-0e90997eea03
- **Opened:** 2026-04-25
- **Last updated:** 2026-04-25 (branched)
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. In the Active Setlist view, each song row displays an inline play/pause button and progress bar that streams/plays audio from `G:\Muzic`.
2. In the Catalog view, each song row displays an inline play/pause button and progress bar that streams/plays audio from `G:\Muzic`.
3. The playback UI is minimalistic: a single play/pause button plus a progress bar per row — no other controls required.
4. In the Active Setlist view, each song row has a button that opens the associated sheet music in a separate browser tab.
5. In the Catalog view, each song row has a button that opens the associated sheet music in a separate browser tab.
6. Sheet music is served from `F:\❤Music\catalog\sheet_music` (including `originals/` and `covers/` subdirectories); supported formats: `.jpeg`, `.docx`, `.pdf`.
7. The feature is universal — it works for all bands managed in the Band Management panel, not only copperCreek.

### Concurrency Notes

- Conflicts with: none
- Depends on: FR-20260425-guitar-trainer-metronome (base branch — new branch cut from `feature/heartmusic/guitar-trainer-metronome`)

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Per-row play/pause + progress bar in Active Setlist (audio from G:\Muzic) | ❤music-orchestrator | not-started | — | — |
| AC2 | Per-row play/pause + progress bar in Catalog (audio from G:\Muzic) | ❤music-orchestrator | not-started | — | — |
| AC3 | Minimalistic UI — play/pause + progress bar only, no extra controls | ❤music-orchestrator | not-started | — | — |
| AC4 | Sheet music viewer button in Active Setlist opens file in separate browser tab | ❤music-orchestrator | not-started | — | — |
| AC5 | Sheet music viewer button in Catalog opens file in separate browser tab | ❤music-orchestrator | not-started | — | — |
| AC6 | Sheet music served from F:\❤Music\catalog\sheet_music; .jpeg/.docx/.pdf formats all open correctly | ❤music-orchestrator | not-started | — | — |
| AC7 | Feature works for all bands in the panel (universal, not copperCreek-only) | ❤music-orchestrator | not-started | — | — |

### Tyler's Original Request

> "next feature is for Band Management panel, for both Active Setlist and Catalog, I'd like to be able to play the song from the record on hand each row, minimalistic playback interface, I'd also like to be able to view the related sheet music for each song such that it pulls up in a separate tab, some of the sheets are in .jpeg, docx, or .pdf format so need to massage that into popping out for the user. Let's branch from clean main and go through new intake FR"

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-25T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, interview complete (Phase A skipped per Tyler's instruction), triage complete → TRIAGED

**Details:**
- Scope: ❤Music — Band Management panel (Active Setlist + Catalog views), `F:\❤Music\src\`
- Audio source confirmed: `G:\Muzic` (local files outside ❤Music project folder)
- Sheet music source confirmed: `F:\❤Music\catalog\sheet_music` (originals/ + covers/), formats: .jpeg, .docx, .pdf
- Playback UI style confirmed: single play/pause button + progress bar per row, in-browser, inline
- Scope: all bands (universal, not copperCreek-only)
- Branch strategy: cut from `feature/heartmusic/guitar-trainer-metronome` (PR #6), not from main
- Acceptance criteria drafted (7 criteria — all grounded in Tyler's stated requirements)
- Concurrency check: no conflicts; depends on FR-20260425-guitar-trainer-metronome (base branch)
- Cycle timer started: e1addcfd-eede-4d24-885c-0e90997eea03

**Next:** awaiting Tyler scope confirmation

### 2026-04-25 — BRANCHED by ⊕workspace-ci

- Branch `feature/heartmusic/band-mgmt-playback-sheets` created from `feature/heartmusic/guitar-trainer-metronome`
- Base branch `feature/heartmusic/guitar-trainer-metronome` pushed to origin (was local-only)
- Placeholder commit `6f3d634` pushed to satisfy GitHub PR diff requirement
- Draft PR opened: https://github.com/tylerdrakemusic/Music/pull/7
- State: TRIAGED → BRANCHED

---

## Artifacts

- **Perf runs:** e1addcfd-eede-4d24-885c-0e90997eea03 — FR cycle timer started at intake
