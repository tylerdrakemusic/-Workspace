# FR-20260427-print-setlist-button — Add Print Button to Setlist in Band Management Panel

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260427-print-setlist-button
- **Title:** Add Print Button to Setlist in Band Management Panel
- **Type:** feature
- **Risk:** low
- **Projects:** ❤Music
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** a1c35e9f-ac0a-4cab-b483-6ae386e4e81a
- **Opened:** 2026-04-27
- **Last updated:** 2026-04-27
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. A "Print Setlist" button is present in the band management panel header/controls area and is only visible when `currentView === 'setlist'`
2. Clicking the button triggers a clean print view (via `window.print()` or a focused print window) — browser print dialog opens
3. The print layout displays: band name, setlist name/date/venue metadata, and songs grouped by set with columns #, Title, Artist, Key, BPM
4. The print layout excludes: audio player controls, sheet music links, search/filter inputs, set-tab controls, dark background, and any nav/sidebar elements
5. `generate_band_mgmt_panel.py` is the sole source of truth — the button, print styles, and print JS are injected there; the static `band_management_panel.html` is regenerated from Python and must NOT be hand-edited
6. The regenerated `band_management_panel.html` reflects all changes and passes a visual smoke-check (panel loads, button appears in setlist view, hidden in catalog view)

### Concurrency Notes
- Conflicts with: FR-20260426-sheet-music-catalog (❤Music, `chore/heartmusic/sheet-music-catalog`) — low risk; that FR targets catalog data, not the band management panel generator. Monitor if it touches `generate_band_mgmt_panel.py`.
- Depends on: none

### Deliverable Tracker

| #   | Deliverable | Owner | Status | Proof | Updated |
| --- | ----------- | ----- | ------ | ----- | ------- |
| AC1 | Print Setlist button in header, hidden in catalog view | ❤music-orchestrator | not-started | — | — |
| AC2 | `window.print()` / print window triggered on click | ❤music-orchestrator | not-started | — | — |
| AC3 | Print layout: band name, metadata, grouped songs, correct columns | ❤music-orchestrator | not-started | — | — |
| AC4 | Print layout strips audio, links, controls, dark theme | ❤music-orchestrator | not-started | — | — |
| AC5 | Python generator (`generate_band_mgmt_panel.py`) is source of truth | ❤music-orchestrator | not-started | — | — |
| AC6 | Regenerated HTML smoke-check passes | ❤music-orchestrator | not-started | — | — |

### Tyler's Original Request
> New feature request intake. Title: "Add print button to pretty-print the setlist in the band management panel"
>
> Affected project: ❤Music
> Primary file (generator): `f:\❤Music\src\band_mgmt\generate_band_mgmt_panel.py`
> Output file (static HTML): `f:\❤Music\reports\band_management_panel.html`
>
> What the feature needs:
> 1. A "Print Setlist" button in the header/controls area (visible only when `currentView === 'setlist'`)
> 2. Clicking it opens a clean print-optimized view (browser `window.print()` or a new window) showing: band name + setlist name/date/venue metadata, songs grouped by set with #, Title, Artist, Key, BPM columns, minimal styling: white background, readable font, no sidebar/buttons/audio controls
> 3. Both the Python generator (`generate_band_mgmt_panel.py`) and the static output HTML need to be updated (the HTML is auto-regenerated from the Python, so the Python is the source of truth).

---

## Event Log

### 2026-04-27T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ❤Music (`generate_band_mgmt_panel.py` + regenerated `band_management_panel.html`)
- Type: feature / Risk: low
- Acceptance criteria drafted (6 ACs — see Header)
- Concurrency check: minor overlap flag on FR-20260426-sheet-music-catalog (❤Music), low risk — different files expected
- Phase A interview: skipped — all three skip conditions met (project explicit, outcome stated, scope boundary clear)

**Next:** awaiting Tyler: approve scope

---

## Artifacts

- **Perf runs:** a1c35e9f-ac0a-4cab-b483-6ae386e4e81a — fr-cycle-FR-20260427-print-setlist-button
